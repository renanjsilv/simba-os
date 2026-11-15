#!/usr/bin/env python3
"""Draco: speech recognition server on this computer (Parakeet Ultra, ONNX, CPU).

Keeps the model in memory and transcribes WHILE F10 is held: `draco start` tells it which
WAV pw-record is writing and it follows the file as it grows. Whenever the speech has a
pause (≥ PAUSE s of silence), the phrase before it is decoded right away and the audio is
cut in the middle of the pause, so no word is ever split (cutting at the model's word
timestamps did split them: repeated words, 17% of words wrong). When F10 is released only
the phrase after the last pause is left. Parakeet needs ~0.2 s per second of speech on an
i5-8250U: a 3 s command is ready ~0.6 s after release; a long request with pauses, about
the same.

  stt_server.py serve                       run the server (socket $XDG_RUNTIME_DIR/draco/stt.sock)
  stt_server.py start <wav>                 begin following a recording
  stt_server.py fim [segundos]              recording is over: print the text (exit 1 on failure/timeout)
  stt_server.py arquivo <wav> [segundos]    transcribe a whole file
  stt_server.py cancelar | ping

The client commands use only the standard library (python3 -I is enough, ~30 ms) and fail
fast when the server is not running: lib/stt_local.py (faster-whisper) is the fallback.
Model files: ~/.local/share/draco/models/parakeet (downloaded by draco-preparar).
Measured on an i5-8250U (124 clips, pt-BR, see ~/.cache/stt-bench): Parakeet Ultra w4a8 3.3%
words wrong on human speech vs 3.8% for Whisper large-v3-turbo on Groq, 18% faster-whisper base.
"""
import json
import os
import socket
import struct
import sys
import threading
import time

RUN = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "draco")
SOCK = os.path.join(RUN, "stt.sock")
DATA = os.path.expanduser("~/.local/share/draco")
MODEL_DIR = os.environ.get("DRACO_STT_MODELO_DIR", os.path.join(DATA, "models", "parakeet"))
RATE = 16000
THREADS = int(os.environ.get("DRACO_STT_THREADS", "4"))
FRAME = 320         # samples (20 ms) per energy frame
PAUSE = 0.30        # s of silence that ends a phrase (the audio is cut in its middle)
MIN_PHRASE = 0.8    # s; shorter phrases wait for the next pause (less context, more errors)
CHECK = 0.2         # s of new audio between looks for a pause while recording
MAX_WINDOW = 15.0   # s without any pause: cut at the quietest point anyway
TAIL = 0.25         # s of silence appended to the end (the last word is decoded better)


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- client side (stdlib only)

def request(cmd, timeout=10.0):
    """Send one command line, return the reply (dict) or None if the server isn't there."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect(SOCK)
            s.sendall((cmd + "\n").encode())
            data = b""
            while not data.endswith(b"\n"):
                chunk = s.recv(65536)
                if not chunk:
                    break
                data += chunk
        return json.loads(data or b"null")
    except (OSError, ValueError):
        return None


def client(argv):
    cmd = argv[0]
    if cmd == "start":
        r = request("start " + os.path.abspath(argv[1]), 2.0)
    elif cmd == "fim":
        r = request("fim", float(argv[1]) if len(argv) > 1 else 10.0)
    elif cmd == "arquivo":
        r = request("arquivo " + os.path.abspath(argv[1]), float(argv[2]) if len(argv) > 2 else 30.0)
    elif cmd in ("cancelar", "ping"):
        r = request(cmd, 2.0)
    else:
        sys.exit(__doc__)
    if not r or not r.get("ok"):
        if r:
            print(r.get("erro", ""), file=sys.stderr)
        sys.exit(1)
    if "texto" in r:
        print(r["texto"])
    elif cmd == "ping":
        print(json.dumps(r, ensure_ascii=False))


# ---------------------------------------------------------------- server side

def wav_data_offset(head):
    """Byte offset of the samples in a (possibly still growing) WAV header, or None."""
    if len(head) < 12 or head[:4] != b"RIFF" or head[8:12] != b"WAVE":
        return None
    pos, fmt_ok = 12, False
    while pos + 8 <= len(head):
        cid, size = head[pos:pos + 4], struct.unpack("<I", head[pos + 4:pos + 8])[0]
        if cid == b"fmt ":
            if pos + 24 > len(head):
                return None
            ch, rate = struct.unpack("<HI", head[pos + 10:pos + 16])
            bits = struct.unpack("<H", head[pos + 22:pos + 24])[0]
            fmt_ok = (ch, rate, bits) == (1, RATE, 16)
        elif cid == b"data":
            return pos + 8 if fmt_ok else None
        pos += 8 + size + (size & 1)
    return None


class Engine:
    def __init__(self):
        import numpy as np
        import onnx_asr
        import onnxruntime as rt
        self.np = np
        so = rt.SessionOptions()
        so.intra_op_num_threads = THREADS
        so.inter_op_num_threads = 1
        t = time.perf_counter()
        self.model = onnx_asr.load_model("nemo-conformer-tdt", MODEL_DIR, quantization="int8",
                                         sess_options=so).with_timestamps()
        self.lock = threading.Lock()
        self.recognize(np.zeros(RATE * 2, np.float32))  # warm-up: first run allocates
        log(f"modelo carregado em {time.perf_counter() - t:.1f} s ({MODEL_DIR})")

    def recognize(self, audio):
        """[(word, start s)] of a float32 16 kHz array."""
        np = self.np
        audio = np.concatenate([audio, np.zeros(int(TAIL * RATE), np.float32)])
        with self.lock:
            r = self.model.recognize(audio, sample_rate=RATE)
        words = []
        for tok, ts in zip(r.tokens or [], r.timestamps or []):
            if tok.startswith(" ") or not words:
                words.append([tok.lstrip(), ts])
            else:
                words[-1][0] += tok
        return [(w, t) for w, t in words if w]


FILLERS = {"uh", "uhm", "hum", "hm", "hmm", "ah", "eh", "ã", "mm"}  # not "um"/"é": real words in pt


def strip_fillers(words):
    """Drop hesitation sounds ("Uh", "Hum") at the start and the end of the request."""
    import re
    key = lambda w: re.sub(r"[^\w]", "", w.lower())
    words = list(words)
    while words and key(words[-1]) in FILLERS:
        words.pop()
    while words and key(words[0]) in FILLERS:
        words.pop(0)
    return words


def join(words):
    import re
    text = " ".join(words)
    return re.sub(r"\s+([,.!?;:…])", r"\1", text).strip()


class Session:
    """One F10 recording: follows the WAV, decodes the pending audio in the background."""

    def __init__(self, engine, path, background=True):
        self.e, self.path, self.np = engine, path, engine.np
        self.chunks, self.total = [], 0          # audio received (int16 arrays), samples
        self.commit_at = 0                       # samples already turned into words
        self.words = []                          # committed words
        self.offset, self.fh, self.carry = None, None, b""
        self.done = threading.Event()            # recording over (fim)
        self.cancelled = False
        self.decodes = 0
        self.noise, self.noise_at = None, 0       # noise floor (dBFS) and when it was measured
        self.thread = threading.Thread(target=self.run, daemon=True) if background else None
        if self.thread:
            self.thread.start()

    def read_new(self):
        if self.fh is None:
            try:
                self.fh = open(self.path, "rb")
            except OSError:
                return
        if self.offset is None:
            self.fh.seek(0)
            self.offset = wav_data_offset(self.fh.read(4096))
            if self.offset is None:
                return
            self.fh.seek(self.offset)
        data = self.carry + self.fh.read()
        n = len(data) & ~1
        self.carry = data[n:]
        if n:
            self.chunks.append(self.np.frombuffer(data[:n], self.np.int16))
            self.total += n // 2

    def audio(self, a, b):
        np = self.np
        if len(self.chunks) > 1:
            self.chunks = [np.concatenate(self.chunks)]
        return self.chunks[0][a:b].astype(np.float32) / 32768 if self.chunks else np.zeros(0, np.float32)

    def quietest(self, a, b):
        """Sample index of the quietest 20 ms frame in [a, b)."""
        x = self.audio(a, b)
        n = len(x) // FRAME
        if n < 1:
            return (a + b) // 2
        e = (x[: n * FRAME].reshape(n, FRAME) ** 2).mean(axis=1)
        return a + int(e.argmin()) * FRAME + FRAME // 2

    def frames_db(self, a, b):
        """Energy (dBFS) of each 20 ms frame in [a, b)."""
        np = self.np
        x = self.audio(a, b)
        n = len(x) // FRAME
        return 10 * np.log10((x[: n * FRAME].reshape(n, FRAME) ** 2).mean(axis=1) + 1e-10) if n else np.zeros(0)

    def threshold(self):
        """Silence/speech boundary: 10 dB over the noise floor of the whole recording so far."""
        if self.total - self.noise_at >= RATE // 2 or self.noise is None:
            db = self.frames_db(0, self.total)
            if len(db):
                self.noise = float(self.np.percentile(db, 10))
                self.noise_at = self.total
        return min(max((self.noise or -70) + 10, -55), -30)

    def has_speech(self, a, b):
        db = self.frames_db(a, b)
        return bool(len(db)) and int((db > self.threshold() + 6).sum()) >= 3  # ≥ 60 ms clearly above

    def find_pause(self):
        """Middle of the last pause (≥ PAUSE s) that ends a phrase of ≥ MIN_PHRASE s, or None."""
        a = self.commit_at
        db = self.frames_db(a, self.total)
        quiet = db < self.threshold()
        need = int(PAUSE * RATE / FRAME)
        best, run = None, 0
        for i, q in enumerate(quiet):
            run = run + 1 if q else 0
            if run >= need:
                mid = a + (i - run // 2) * FRAME
                if mid - a >= MIN_PHRASE * RATE:
                    best = mid
        return best

    def speech_end(self):
        """End of the audio to decode: 0.25 s after the last clearly loud frame. The silence
        after the request (F10 keeps recording 0.3 s) made Parakeet invent an "Uh"."""
        db = self.frames_db(self.commit_at, self.total)
        loud = self.np.nonzero(db > self.threshold() + 6)[0] if len(db) else []
        if not len(loud):
            return self.total
        return min(self.total, self.commit_at + (int(loud[-1]) + 1) * FRAME + int(0.25 * RATE))

    def decode(self, a, b):
        self.decodes += 1
        return [w for w, _ in self.e.recognize(self.audio(a, b))]

    def step(self):
        """Commit the phrase that ends at the last pause, if there is one."""
        cut = self.find_pause()
        if cut is None and (self.total - self.commit_at) / RATE > MAX_WINDOW:
            cut = self.quietest(self.commit_at + RATE, self.total - RATE // 2)
        if cut is None:
            return
        if self.has_speech(self.commit_at, cut):
            self.words += self.decode(self.commit_at, cut)
        self.commit_at = cut

    def run(self):
        last = 0
        while not self.done.is_set() and not self.cancelled:
            self.read_new()
            if (self.total - last) / RATE >= CHECK:
                last = self.total
                try:
                    self.step()
                except Exception as ex:  # noqa: BLE001 — keep the session alive; fim decodes all
                    log("erro ao decodificar:", ex)
                continue
            self.done.wait(0.1)
        if self.cancelled and self.fh:
            self.fh.close()

    def finish(self):
        t = time.perf_counter()
        self.done.set()
        if self.thread:
            self.thread.join()  # a decode may be running: its words count
        waited = time.perf_counter() - t
        # pw-record is gone: the file is complete (the header was rewritten, offset unchanged)
        self.read_new()
        if self.fh:
            self.fh.close()
        during = self.decodes
        rest = (self.total - self.commit_at) / RATE
        if rest > 0.1:  # always: with no clear silence in the recording, has_speech can't judge
            self.words += self.decode(self.commit_at, self.speech_end())
        text = join(strip_fillers(self.words))
        log(f"fim: {self.total / RATE:.1f} s de áudio, {during} frases já transcritas durante a gravação, "
            f"último pedaço {rest:.1f} s; {time.perf_counter() - t:.2f} s (esperando: {waited:.2f} s)")
        return text


def read_wav(path):
    import wave
    import numpy as np
    with wave.open(path) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        ch, rate = w.getnchannels(), w.getframerate()
    if ch > 1:
        a = a.reshape(-1, ch).mean(axis=1)
    if rate != RATE:
        n = int(len(a) * RATE / rate)
        a = np.interp(np.linspace(0, len(a), n, endpoint=False), np.arange(len(a)), a).astype(np.float32)
    return a


def serve():
    os.makedirs(RUN, exist_ok=True)
    # one server per user: if the socket answers, another one is running
    if request("ping", 1.0):
        log("já está rodando")
        return
    engine = Engine()
    try:
        os.unlink(SOCK)
    except FileNotFoundError:
        pass
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCK)
    os.chmod(SOCK, 0o600)
    srv.listen(8)
    state = {"session": None}
    slock = threading.Lock()

    def handle(conn):
        with conn:
            f = conn.makefile("rwb")
            line = f.readline().decode(errors="replace").strip()
            cmd, _, arg = line.partition(" ")
            try:
                if cmd == "ping":
                    rep = {"ok": True, "modelo": os.path.basename(MODEL_DIR), "threads": THREADS}
                elif cmd == "start":
                    with slock:
                        old, state["session"] = state["session"], Session(engine, arg)
                    if old:
                        old.cancelled = True
                    rep = {"ok": True}
                elif cmd == "cancelar":
                    with slock:
                        old, state["session"] = state["session"], None
                    if old:
                        old.cancelled = True
                    rep = {"ok": True}
                elif cmd == "fim":
                    with slock:
                        s, state["session"] = state["session"], None
                    rep = {"ok": True, "texto": s.finish()} if s else {"ok": False, "erro": "nenhuma gravação"}
                elif cmd == "arquivo":
                    t = time.perf_counter()
                    rep = {"ok": True, "texto": join(strip_fillers(w for w, _ in engine.recognize(read_wav(arg))))}
                    log(f"arquivo: {time.perf_counter() - t:.2f} s")
                else:
                    rep = {"ok": False, "erro": "comando desconhecido"}
            except Exception as ex:  # noqa: BLE001
                log("erro:", cmd, ex)
                rep = {"ok": False, "erro": str(ex)}
            f.write((json.dumps(rep, ensure_ascii=False) + "\n").encode())
            f.flush()

    log("pronto em", SOCK)
    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "serve":
        serve()
    else:
        client(sys.argv[1:])
