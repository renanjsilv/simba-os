#!/usr/bin/env python3
"""Reproducible benchmark of the "Draco" wake word: recall and false alarms per hour,
before (1 step at the threshold, old lenient Whisper check) and after (wake.py now).

Audio (from wake-train/, see wake_train.py; nothing is recorded or sent anywhere):
  positives, each said after 1.5 s of the recorded room (ambiente.raw), then 3 s of it:
    minhas      Renan's takes (wake_record.py)
    edge-teste  two Microsoft voices the detector never trained on
    antonio     pt-BR-AntonioNeural, the voice Draco itself speaks with
  negatives:
    librivox    the LibriVox Portuguese the detector never trained on (~1 h of nonstop talk)
    reais       things that used to trigger it (negativos-reais/)
    parecidas   sound-alikes and sentences ("Drácula", "braço", "fraco"...) by 3 voices
    ambiente    the room around the positives (people talking)
Each detection is checked by the verifier on the same audio wake.py would give it.
Scores are cached in ~/.cache/draco-bench (delete it after retraining the model).

  venv/bin/python -I tests/bench_wake.py
"""
import collections
import glob
import hashlib
import os
import pickle
import sys
import time

import numpy as np

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.argv = sys.argv[:1]
sys.path.insert(0, CODE)
import wake  # noqa: E402
import wake_train as wt  # noqa: E402

T = os.path.join(wake.DATA, "wake-train")
CACHE = os.path.expanduser("~/.cache/draco-bench")
SR, STEP = wake.RATE, wake.CHUNK
rng = np.random.default_rng(3)


def room(n, amb):
    s = rng.integers(0, len(amb) - n)
    return amb[s:s + n].copy()


def positives(amb):
    items = [("minhas", f) for f in sorted(glob.glob(f"{T}/minhas/*.wav"))]
    for f in sorted(glob.glob(f"{T}/edge/pos/*.mp3")):
        if any(v in f for v in wt.HELD_OUT_EDGE):
            items.append(("edge-teste", f))
        elif "AntonioNeural" in f:
            items.append(("antonio", f))
    segs, marks, pos = [], [], 0
    for kind, f in items:
        w = wt.trim(wt.load(f))
        if kind == "minhas" and len(w) > 1.2 * SR and "_emendado_" not in f:
            w = w[:int(0.9 * SR)]  # old long takes start with "Draco"
        w = w / (np.sqrt(np.mean(w ** 2)) + 1e-6) * rng.uniform(1500, 4000)
        a = np.concatenate([room(int(1.5 * SR), amb), np.zeros(len(w)), room(3 * SR, amb)])
        a[int(1.5 * SR):int(1.5 * SR) + len(w)] += w
        marks.append((kind, pos + 1.5 * SR, pos + 1.5 * SR + len(w)))
        segs.append(a)
        pos += len(a)
    return np.concatenate(segs), marks


def negatives(amb):
    _, test = wt.librivox_files()
    out = [("librivox", wt.load(f)) for f in test]
    out += [("reais", wt.load(f)) for f in sorted(glob.glob(f"{T}/negativos-reais/*.wav"))]
    voices = wt.HELD_OUT_EDGE + ("AntonioNeural",)
    ed = [f for f in sorted(glob.glob(f"{T}/edge/neg/*.mp3")) if any(v in f for v in voices)]
    out.append(("parecidas", np.concatenate([np.concatenate([wt.load(f), room(SR, amb)]) for f in ed])))
    return out


def analyze(x):
    """(score, seconds since speech) of every 80 ms step, by wake.py's own Detector."""
    det = wake.Detector(wake.Classifier(), wake.Features(), wake.VAD())
    pcm = np.clip(x, -32768, 32767).astype(np.int16)
    r = []
    for i in range(0, len(pcm) - STEP + 1, STEP):
        r.append((det.analyze(pcm[i:i + STEP].tobytes()), det.since_speech))
    return np.array(r, np.float32).reshape(-1, 2)


def cached_streams():
    key = hashlib.sha1(open(wake.MODEL, "rb").read()).hexdigest()[:10]
    path = os.path.join(CACHE, f"streams-{key}.pkl")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return pickle.load(f)
    amb = wt.load(f"{T}/ambiente.raw")
    t = time.time()
    x, marks = positives(amb)
    pos = (x.astype(np.int16), analyze(x))
    negs = [(k, a.astype(np.int16), analyze(a)) for k, a in negatives(amb)]
    print(f"(detector rodou em {time.time() - t:.0f} s; guardado em {path})", flush=True)
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump((pos, marks, negs), f)
    return pos, marks, negs


def fires(r, th, hits):
    trig, out = wake.Trigger(hits), []
    for i, (s, since) in enumerate(r):
        if trig((i + 1) * STEP / SR, s, th, since):
            out.append((i, trig.peak))
    return out


def clip(pcm, i, tail):
    end = (i + 1) * STEP
    return pcm[max(0, end - int(wake.WAKE_AUDIO * SR)):end + tail * STEP].tobytes()


class Before:
    """wake.py until 2026-11: Whisper tiny with "Draco" as hotword over the 2 s before the
    detection; rejected only when it was confident and heard a word not like "draco"."""
    name, tail = "antes", 0

    def __init__(self, v):
        self.v = v

    def __call__(self, pcm, peak):
        import difflib
        import re
        import unicodedata
        audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
        segs = list(self.v.tiny.transcribe(
            audio, language=wake.LINGUA, hotwords="Draco", beam_size=1, temperature=0.0, max_new_tokens=12,
            without_timestamps=True, condition_on_previous_text=False)[0])
        text = " ".join(s.text for s in segs).strip()
        confident = segs and max(s.no_speech_prob for s in segs) < 0.5 and min(s.avg_logprob for s in segs) > -1.0
        words = re.findall(r"[a-z]+", unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode())
        like = any(difflib.SequenceMatcher(None, w, "draco").ratio() >= 0.75 for w in words)
        return not (confident and text and not like)


class After:
    name, tail = "depois", wake.VERIFY_TAIL

    def __init__(self, v):
        self.v = v

    def __call__(self, pcm, peak):
        plain, biased = self.v.local(pcm)
        return wake.confirms(plain, biased, peak)


def run(label, pcm_pos, r_pos, marks, negs, th, hits, verify):
    found, total, ms = collections.Counter(), collections.Counter(), []
    ends = []
    for i, peak in fires(r_pos, th, hits):
        t0 = time.monotonic()
        ok = verify(clip(pcm_pos, i, verify.tail), peak)
        ms.append(time.monotonic() - t0)
        ends.append(((i + 1) * STEP, peak, ok))
    for kind, a, b in marks:
        total[kind] += 1
        hit = [ok for e, _, ok in ends if a <= e <= b + SR]
        found[kind + "/1"] += bool(hit)
        found[kind] += any(hit)
    inside = lambda e: any(a <= e <= b + SR for _, a, b in marks)  # noqa: E731
    amb_s1 = sum(1 for e, _, _ in ends if not inside(e))
    amb_s2 = sum(1 for e, _, ok in ends if ok and not inside(e))
    fa1, fa2, hours = collections.Counter(), collections.Counter(), collections.Counter()
    for kind, pcm, r in negs:
        hours[kind] += len(pcm) / SR / 3600
        for i, peak in fires(r, th, hits):
            fa1[kind] += 1
            t0 = time.monotonic()
            fa2[kind] += bool(verify(clip(pcm, i, verify.tail), peak))
            ms.append(time.monotonic() - t0)
    amb_h = len(pcm_pos) / SR / 3600  # the room around the positives
    print(f"\n== {label}: limiar {th:.2f}, {hits} passo(s) seguido(s), verificação {verify.name} "
          f"(mediana {np.median(ms) * 1000:.0f} ms)")
    print("  acerta (detector -> com verificação):")
    for kind in total:
        n = total[kind]
        print(f"    {kind:11s} {found[kind + '/1']:3d}/{n} ({found[kind + '/1'] / n:5.1%}) -> "
              f"{found[kind]:3d}/{n} ({found[kind] / n:5.1%})")
    print("  alarmes falsos por hora (detector -> com verificação):")
    for kind in hours:
        print(f"    {kind:11s} {fa1[kind] / hours[kind]:7.1f} -> {fa2[kind] / hours[kind]:6.1f}   "
              f"({fa1[kind]} -> {fa2[kind]} em {hours[kind] * 60:.0f} min)")
    print(f"    {'ambiente':11s} {amb_s1 / amb_h:7.1f} -> {amb_s2 / amb_h:6.1f}   ({amb_s1} -> {amb_s2} em {amb_h * 60:.0f} min)")


def main():
    (pcm_pos, r_pos), marks, negs = cached_streams()
    v = wake.Verifier()
    v.load()
    limiar = wake.Classifier().threshold
    run("ANTES", pcm_pos, r_pos, marks, negs, 0.85, 1, Before(v))
    run("DEPOIS", pcm_pos, r_pos, marks, negs, limiar, wake.HITS, After(v))
    if abs(limiar - wake.THRESHOLD) > 1e-6:
        run("DEPOIS (limiar padrão)", pcm_pos, r_pos, marks, negs, wake.THRESHOLD, wake.HITS, After(v))


if __name__ == "__main__":
    main()
