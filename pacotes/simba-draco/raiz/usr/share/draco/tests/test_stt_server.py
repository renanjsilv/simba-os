"""lib/stt_server.py: WAV header of a growing file, joining words, client without a server,
and the incremental decoding (with a fake model: no download needed).
The session part needs numpy: it runs with the Draco venv python if there is one."""
import os
import struct
import subprocess
import sys
import tempfile

LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib")
VENV = os.path.expanduser("~/.local/share/draco/venv/bin/python")
try:
    import numpy as np
except ImportError:
    if os.path.exists(VENV) and os.environ.get("_STT_TESTE") is None:
        sys.exit(subprocess.run([VENV, "-I", *sys.argv], env={**os.environ, "_STT_TESTE": "1"}).returncode)
    np = None
sys.path.insert(0, LIB)
os.environ["XDG_RUNTIME_DIR"] = tempfile.mkdtemp()  # no real server here
import stt_server as S  # noqa: E402

ok = bad = 0


def check(name, got, exp):
    global ok, bad
    if got == exp:
        ok += 1
        print("ok  ", name)
    else:
        bad += 1
        print("FAIL", name, repr(got), "!=", repr(exp))


def header(rate=16000, ch=1, bits=16, extra=b""):
    fmt = struct.pack("<HHIIHH", 1, ch, rate, rate * ch * bits // 8, ch * bits // 8, bits)
    return b"RIFF" + struct.pack("<I", 0) + b"WAVE" + b"fmt " + struct.pack("<I", 16) + fmt + extra + \
        b"data" + struct.pack("<I", 0xFFFFFFFF)


check("cabeçalho simples", S.wav_data_offset(header()), 44)
check("cabeçalho com PEAK/LIST", S.wav_data_offset(header(extra=b"LIST" + struct.pack("<I", 4) + b"INFO")), 56)
check("cabeçalho ainda incompleto", S.wav_data_offset(header()[:30]), None)
check("44,1 kHz recusado", S.wav_data_offset(header(rate=44100)), None)
check("juntar palavras", S.join(["abre", "o", "Spotify", "."]), "abre o Spotify.")
check("tira o 'Uh' do fim", S.join(S.strip_fillers(["Diminui", "o", "brilho.", "Uh"])), "Diminui o brilho.")
check("mantém 'Um' e 'É' (palavras de verdade)", S.join(S.strip_fillers(["Um", "homem", "É"])), "Um homem É")
r = subprocess.run([sys.executable, "-I", os.path.join(LIB, "stt_server.py"), "fim", "1"], capture_output=True,
                   env={**os.environ})
check("cliente sem servidor falha logo", r.returncode, 1)

if np is None:
    print("(sem numpy: pulando a sessão)")
else:
    RATE = 16000
    rng = np.random.default_rng(1)
    # 0.4 s of silence, then 4 phrases of 3 words (each word 0.3 s of loud noise, 0.1 s gap
    # inside the phrase), with 0.5 s pauses between the phrases.
    parts, WORDS, t = [rng.normal(0, 8, int(0.4 * RATE))], [], 0.4
    for f in range(4):
        for w in range(3):
            WORDS.append((f"f{f}p{w}", t))
            parts += [rng.normal(0, 3000, int(0.3 * RATE)), rng.normal(0, 8, int(0.1 * RATE))]
            t += 0.4
        parts.append(rng.normal(0, 8, int(0.4 * RATE)))
        t += 0.4
    full = np.clip(np.concatenate(parts), -32767, 32767).astype(np.int16)
    index = {full[i:i + 6].tobytes(): i for i in range(len(full) - 6)}

    class Fake:
        """Finds where the window is in the full recording and returns the words in it."""
        np = np

        def __init__(self):
            self.calls = []

        def recognize(self, audio):
            a = (audio[:6] * 32768).round().astype(np.int16).tobytes()
            start = index[a] / RATE
            end = start + len(audio) / RATE
            self.calls.append((round(start, 2), round(end, 2)))
            # a word counts if its middle is in the window (split words would show up twice or never)
            return [(w, t0 - start) for w, t0 in WORDS if start <= t0 + 0.15 < end]

    d = tempfile.mkdtemp()
    wav = os.path.join(d, "input.wav")
    with open(wav, "wb") as f:
        f.write(header())
    eng = Fake()
    s = S.Session(eng, wav, background=False)
    step = int(S.CHECK * RATE)
    with open(wav, "ab") as f:
        for i in range(0, len(full), step):  # as the server's loop would see it
            f.write(full[i:i + step].tobytes())
            f.flush()
            s.read_new()
            s.step()
    text = s.finish()
    check("sessão: todas as palavras, em ordem, sem repetir", text, " ".join(w for w, _ in WORDS))
    check("sessão: frases transcritas durante a gravação", len(eng.calls) >= 3, True)
    last = eng.calls[-1]
    check("sessão: no fim sobrou só a última frase (< 2 s)", last[1] - last[0] < 2.0, True)
    cuts = [c[0] for c in eng.calls[1:]]
    check("sessão: cortes só nas pausas", all(not any(t0 <= c <= t0 + 0.3 for _, t0 in WORDS) for c in cuts), True)

    # Without any pause (one long word), nothing is decoded until the end, and all of it then.
    eng2 = Fake()
    s2 = S.Session(eng2, wav, background=False)
    s2.words, s2.chunks, s2.total = [], [full[: int(1.6 * RATE)]], int(1.6 * RATE)
    s2.fh = open(wav, "rb"); s2.offset = 0; s2.fh.seek(0, 2)
    s2.step()
    check("sem pausa: nada durante a gravação", eng2.calls, [])

print(f"\n{ok} ok, {bad} falhas")
sys.exit(1 if bad else 0)
