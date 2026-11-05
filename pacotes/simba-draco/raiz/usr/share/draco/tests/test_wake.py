#!/usr/bin/env python3
"""Scenario test for wake.py: builds audio files (Renan's "Draco" from wake-train/minhas,
requests in a Piper voice, optional background talk from wake-train/ambiente.raw),
runs `wake.py --teste --arquivo` on each and checks what it would have done.
Uses Groq for the trigger check (~2 calls per scenario). Nothing is triggered for real.

  venv/bin/python -I tests/test_wake.py
"""
import os
import subprocess
import sys
import tempfile
import wave

import numpy as np
from piper import PiperVoice
from scipy.signal import resample_poly

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 16000
rng = np.random.default_rng(1)
amb = np.frombuffer(open(os.path.join(D, "wake-train", "ambiente.raw"), "rb").read(), np.int16).astype(np.float32)
voice = PiperVoice.load(os.path.join(D, "voices", "pt_BR-faber-medium.onnx"))


def tts(text):
    a = np.concatenate([c.audio_int16_array for c in voice.synthesize(text)]).astype(np.float32)
    a = resample_poly(a, SR, voice.config.sample_rate)
    return a / np.sqrt(np.mean(a ** 2)) * 3500


def wav(path):
    with wave.open(path) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32)


def trim(x, th=300):
    i = np.where(np.abs(x) > th)[0]
    return x[i[0]:i[-1] + 1]


def quiet(s):
    return rng.standard_normal(int(s * SR)).astype(np.float32) * 30


MINE = os.path.join(D, "wake-train", "minhas")
draco = trim(wav(os.path.join(MINE, "draco-2.wav")))[: int(0.8 * SR)]
draco_req = trim(wav(os.path.join(MINE, "draco-1.wav")))  # "Draco, abrir o Spotify" in one go

# name: (parts, background level, expected outcome, expected recorded seconds range)
SCENARIOS = {
    "pausa no meio do pedido": ([quiet(1.5), draco, quiet(3.0), tts("abre o Spotify"), quiet(1.5),
                                 tts("e coloca uma música animada"), quiet(4)], 0, "comando", (3.5, 6)),
    "fala direto após o nome": ([quiet(1.5), draco_req, quiet(4)], 0, "comando", (0.8, 4)),
    "diz o nome e fica quieto": ([quiet(1.5), draco, quiet(7)], 0, "nada", None),
    "fala depois de 6 s": ([quiet(1.5), draco, quiet(6.0), tts("que horas são"), quiet(3)], 0, "nada", None),
    "conversa sem o nome": ([quiet(1), tts("Muito obrigada pelo convite. Não, não vou deixar. Será? Eu quero ver."),
                             quiet(1), tts("Ele está fraco hoje, quebrou o braço, claro que sim."), quiet(3)], 0, "sem disparo", None),
    "pedido com conversa ao fundo": ([quiet(1.5), draco, quiet(3.0), tts("abre o Spotify"), quiet(1.5),
                                      tts("e coloca uma música animada"), quiet(4)], 0.3, "comando", (3.5, 7)),
}


def build(parts, bg, path):
    a = np.concatenate(parts)
    if bg:
        a = a + np.tile(amb, int(np.ceil(len(a) / len(amb))))[: len(a)] * bg
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(np.clip(a, -32768, 32767).astype(np.int16).tobytes())


def outcome(log):
    if "comando:" in log:
        return "comando", float(log.split("comando:")[-1].split("s")[0])
    if "nada foi dito" in log:
        return "nada", None
    return "sem disparo", None  # no detection, or detections the check rejected


failures = 0
tmp = tempfile.mkdtemp()
for name, (parts, bg, expected, dur) in SCENARIOS.items():
    path = os.path.join(tmp, "cenario.wav")
    build(parts, bg, path)
    log = subprocess.run([sys.executable, "-I", os.path.join(D, "wake.py"), "--teste", "--arquivo", path],
                         capture_output=True, text=True).stdout
    got, secs = outcome(log)
    ok = got == expected and (dur is None or dur[0] <= secs <= dur[1])
    failures += not ok
    print(f"{'ok  ' if ok else 'FALHA'} {name}: {got}{f' ({secs:.1f}s)' if secs else ''}"
          f"{'' if ok else f' — esperado {expected} {dur or ''}'}")
    if not ok:
        print("    " + "\n    ".join(l for l in log.splitlines() if "score" not in l))
print(f"\n{len(SCENARIOS) - failures} ok, {failures} falhas")
sys.exit(1 if failures else 0)
