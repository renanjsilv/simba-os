#!/usr/bin/env python3
"""Teach the detector your voice: a ~4 minute session guided by Draco's own voice.

Draco asks for "Draco" said in different ways (normal, fast, slow, quiet, from across
the room, run into a request) and then for some talk without the name. After each
request a beep marks when to start. Each phase is one recording, cut into takes at the
pauses; each take is checked on its own by the cloud Whisper (a whole phase at once
doesn't work: Whisper collapses repeated words, 4 "Draco"s came back as 1), only real
"Draco"s are kept (other people talking in the room too are dropped), and they go to
wake-train/minhas/; your talk without the name goes to wake-train/minha-fala/
(negatives: it must not fire on your normal speech). Then wake_train.py runs
and Draco tells you whether the new model is better (it's only installed if it is).

  draco treinar              (same as: venv/bin/python -I wake_record.py)
  wake_record.py --sem-treino   record only

The wake word listener is paused during the session.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))
from simba_i18n import idioma as _idioma  # noqa: E402
_l = _idioma()
LINGUA = "pt" if not _l or _l.startswith("pt") else _l.split("_")[0]   # idioma da sessão (Whisper)
import json
import math
import os
import re
import subprocess
import sys
import time
import wave

import numpy as np

CODIGO = os.path.dirname(os.path.abspath(__file__))   # /usr/share/draco (pacote)
DATA = os.path.expanduser("~/.local/share/draco")     # dados do usuário
sys.path.insert(0, os.path.join(CODIGO, "lib"))
import config as settings  # noqa: E402
from transcript import is_draco  # noqa: E402

RATE = 16000
DRACO = os.path.expanduser("/usr/bin/draco")
TRAIN = os.path.join(DATA, "wake-train")
MINE = os.path.join(TRAIN, "minhas")
MY_TALK = os.path.join(TRAIN, "minha-fala")
DISABLED = os.path.join(DATA, "wake.disabled")
RUN = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "draco")

# (name, what Draco says, seconds to record, seconds to get ready, keep after the word)
# "emendado" keeps 0.35 s after the word: in real use the detector fires while you are
# already saying the request, so it must learn "Draco" followed by more speech.
PHASES = [
    ("normal", "Primeiro, diga Draco do seu jeito normal, oito vezes, com uma pausa curtinha entre cada uma.", 17, 0, 0.0),
    ("rapido", "Agora rápido, como quem chama de passagem. Oito vezes.", 14, 0, 0.0),
    ("emendado", "Agora diga Draco já emendando um pedido, tipo: Draco abre o Spotify. "
                 "Seis vezes, com pedidos diferentes e uma pausa entre eles.", 26, 0, 0.35),
    ("devagar", "Agora devagar e bem claro. Quatro vezes.", 10, 0, 0.0),
    ("baixo", "Agora baixinho, quase sussurrando. Cinco vezes.", 12, 0, 0.0),
    ("longe", "Agora se afaste do notebook, uns dois metros, ou vire de costas. "
              "Depois do bipe, diga Draco seis vezes, num volume normal.", 16, 4, 0.0),
    ("alto", "Pode voltar. Agora um pouco mais alto, como se eu estivesse em outro cômodo. Quatro vezes.", 11, 2, 0.0),
]
FREE_TALK = ("Por último, fale qualquer coisa por vinte segundos, sem dizer Draco. "
             "Pode contar como foi o seu dia, ou ler algo da tela.", 20)


def say(text):
    print(f"\n🔊 {text}", flush=True)
    subprocess.run([DRACO, "say", text], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def beep(freq=880, ms=140):
    t = np.arange(int(RATE * ms / 1000)) / RATE
    tone = (np.sin(2 * math.pi * freq * t) * np.hanning(len(t)) * 9000).astype(np.int16)
    subprocess.run(["pw-play", "--raw", "--rate", str(RATE), "--channels", "1", "--format", "s16", "-"],
                   input=tone.tobytes(), stderr=subprocess.DEVNULL)


def record(seconds):
    proc = subprocess.Popen(["pw-record", "--rate", str(RATE), "--channels", "1", "--format", "s16", "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    raw, need = bytearray(), int(seconds * RATE) * 2
    t0 = time.monotonic()
    while len(raw) < need:
        chunk = proc.stdout.read(min(3200, need - len(raw)))
        if not chunk:
            break
        raw.extend(chunk)
        left = seconds - (time.monotonic() - t0)
        print(f"\r   gravando... {max(left, 0):4.1f} s", end="", flush=True)
    proc.terminate()
    proc.wait()
    print()
    return np.frombuffer(bytes(raw), np.int16)


def save(audio, path):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(audio.astype(np.int16).tobytes())


_calls = []


def words(audio):
    """Word timestamps of a take from the cloud Whisper (None if not configured/failed).
    Kept under Groq's free 20 requests/minute."""
    service = settings.stt()
    if not service:
        return None
    while len(_calls) >= 18 and time.monotonic() - _calls[-18] < 60:
        time.sleep(1)
    _calls.append(time.monotonic())
    base, key, model = service
    path = os.path.join(RUN, "treino-take.wav")
    pad = np.zeros(int(0.3 * RATE), np.int16)
    save(np.concatenate([pad, audio, pad]), path)
    ws = None
    for attempt in range(4):  # rate limited: wait as told and try again
        try:
            out = subprocess.run(
                ["curl", "-sS", "--max-time", "20", f"{base}/audio/transcriptions", "-H", f"Authorization: Bearer {key}",
                 "-F", f"model={model}", "-F", f"language={LINGUA}", "-F", "temperature=0", "-F", "response_format=verbose_json",
                 "-F", "timestamp_granularities[]=word", "-F", f"file=@{path}"],
                capture_output=True, text=True, timeout=30).stdout
            data = json.loads(out)
        except (subprocess.SubprocessError, ValueError):
            return None
        if "words" in data:
            ws = data["words"]
            break
        msg = str(data.get("error", {}).get("message", ""))
        if "rate limit" not in msg.lower():
            return None
        wait = re.search(r"try again in ([\d.]+)s", msg)
        time.sleep(min(float(wait.group(1)) + 0.5, 20) if wait else 5)
    if ws is None:
        return None
    for w in ws:  # back to the take's own time
        w["start"], w["end"] = max(w["start"] - 0.3, 0), max(w["end"] - 0.3, 0)
    return ws


def trim_sound(clip):
    """Cut the silence around a take (keeps ~30 ms margin)."""
    env = np.convolve(np.abs(clip.astype(np.float32)), np.ones(160) / 160, "same")
    loud = np.where(env > max(0.08 * env.max(), 120))[0]
    if len(loud) == 0:
        return None
    return clip[max(loud[0] - 480, 0):loud[-1] + 480]


def segments(audio, max_len):
    """The takes: loud stretches separated by pauses of 0.25 s or more."""
    env = np.convolve(np.abs(audio.astype(np.float32)), np.ones(480) / 480, "same")
    on = env > max(np.percentile(env, 20) * 3, 0.1 * np.percentile(env, 99), 150)
    on = np.convolve(on, np.ones(int(0.25 * RATE)), "same") > 0  # bridge pauses shorter than 0.25 s
    edges = np.flatnonzero(np.diff(np.r_[0, on.astype(np.int8), 0]))
    segs = []
    for i, j in zip(edges[::2], edges[1::2]):
        i, j = i + int(0.125 * RATE), j - int(0.125 * RATE)  # undo the bridging margin
        if 0.2 * RATE <= j - i <= max_len * RATE:
            segs.append(audio[max(i - 1600, 0):min(j + 1600, len(audio))])
    return segs


def takes(audio, joined):
    """Every "Draco" in a phase recording, checked one by one."""
    out, heard = [], []
    for seg in segments(audio, 5.0 if joined else 1.4):
        ws = words(seg)
        if ws is None:  # no cloud Whisper configured: trust the pauses (single-word phases only)
            if settings.stt() is None and not joined and (c := trim_sound(seg)) is not None:
                out.append(c)
            continue
        heard.append(" ".join(w["word"] for w in ws).strip())
        hit = next((w for w in ws if is_draco(w["word"])), None)
        if hit is None:
            continue
        if joined:  # the word plus the start of the request after it
            a = max(int((hit["start"] - 0.15) * RATE), 0)
            c = seg[a:min(int((hit["end"] + 0.35) * RATE), len(seg))]
            c = c[max(np.argmax(np.abs(c) > 300) - 480, 0):] if np.any(np.abs(c) > 300) else None
        else:
            c = trim_sound(seg)
        if c is not None and 0.2 * RATE <= len(c) <= 1.6 * RATE:
            out.append(c)
    return out, heard


def main():
    os.makedirs(MINE, exist_ok=True)
    os.makedirs(MY_TALK, exist_ok=True)
    os.makedirs(RUN, exist_ok=True)
    was_paused = os.path.exists(DISABLED)
    open(DISABLED, "a").close()  # the listener would trigger on every take
    stamp = time.strftime("%Y%m%d-%H%M")
    total = 0
    try:
        say("Vamos treinar o reconhecimento da sua voz. Vou pedir para você dizer Draco de vários jeitos. "
            "Comece a falar sempre depois do bipe.")
        for name, text, seconds, ready, after in PHASES:
            say(text)
            time.sleep(ready + 0.3)
            beep()
            audio = record(seconds)
            beep(660, 90)
            clips, heard = takes(audio, after > 0)
            if heard:
                print(f"   ouvi: {' | '.join(heard)[:200]}")
            for i, c in enumerate(clips):
                save(c, os.path.join(MINE, f"{stamp}_{name}_{i + 1:02d}.wav"))
            total += len(clips)
            print(f"   {name}: {len(clips)} 'Draco' guardados")
            if len(clips) < 2:
                say("Não peguei quase nenhum Draco nessa. Tudo bem, vamos seguir.")
        text, seconds = FREE_TALK
        say(text)
        time.sleep(0.3)
        beep()
        audio = record(seconds)
        beep(660, 90)
        ws = words(audio)
        if ws is not None and any(is_draco(w["word"]) for w in ws):
            print("   (você disse Draco nessa parte; descartei)")
        else:
            save(audio, os.path.join(MY_TALK, f"{stamp}.wav"))
    finally:
        if not was_paused and os.path.exists(DISABLED):
            os.unlink(DISABLED)
    print(f"\nTotal: {total} gravações de 'Draco' em {MINE}")
    if "--sem-treino" in sys.argv:
        say(f"Pronto, gravei {total} vezes.")
        return
    say(f"Pronto! Peguei {total} Draco. Agora vou treinar com a sua voz. Leva uns quinze minutos, "
        "pode continuar usando o computador. Te aviso quando terminar.")
    log = os.path.join(DATA, "wake-train", "treino.log")
    with open(log, "w") as f:
        r = subprocess.run(["nice", "-n", "5", sys.executable, "-I", os.path.join(CODIGO, "wake_train.py")],
                           stdout=f, stderr=subprocess.STDOUT)
    result = open(log).read()
    if "instalado:" in result:
        subprocess.run(["systemctl", "--user", "restart", "draco-wake.service"])
        line = next((l for l in result.splitlines() if l.startswith("sua voz:")), "")
        say("Treino concluído e o detector novo já está valendo. " + line.replace("sua voz:", "Com a sua voz, ele").strip())
    elif r.returncode != 0:
        say("O treino deu erro. Os detalhes ficaram no arquivo treino ponto log.")
    else:
        say("Terminei o treino, mas o modelo novo não ficou melhor que o atual, então mantive o atual.")
    print(result[-1500:])


if __name__ == "__main__":
    main()
