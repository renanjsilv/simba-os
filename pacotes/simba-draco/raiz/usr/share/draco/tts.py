#!/usr/bin/env python3
"""Draco speech server: keeps the voice loaded so replies start instantly.

Voices (VOZ in the settings): "pt_BR-..." = Piper, on this computer (instant, a bit
robotic); "edge:pt-BR-..." = Microsoft's neural voices (natural, free, over the
internet: ~1 s more to start). If the neural voice fails or takes over EDGE_WAIT s,
the local Piper voice (VOZ_LOCAL) speaks instead.

  tts.py serve                      run the server (needs the piper venv python)
  tts.py say [--levels FILE] TEXT   speak TEXT; blocks until it finishes playing

While speaking, FILE receives "d <total ms>" and then one loudness value (0..1)
per ~1/30 s, in sync with playback; the on-screen orb reads it. Neural voices also
send "w <ms>" when each word starts (the orb lights words exactly as they're spoken:
pauses at commas and periods made the even-paced caption drift).
Killing a `say` client stops its speech immediately (that's how cancel works),
and a new `say` interrupts the previous one.
"""
import array, json, math, os, queue, select, socket, subprocess, sys, threading, time

RUN = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "draco")
SOCK = os.path.join(RUN, "tts.sock")
DATA = os.path.expanduser("~/.local/share/draco")
VOICE = os.path.join(DATA, "voices", "pt_BR-faber-medium.onnx")
CONFIG = os.path.expanduser("~/.config/draco/config.env")


EDGE_WAIT = 4.0


def setting(key):
    try:
        for line in open(CONFIG):
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip().strip("'\"")
    except OSError:
        pass
    return ""


def _lingua():
    import sys as _s
    _s.path.insert(0, os.path.expanduser("/usr/share/simba-apps/idiomas"))
    from simba_i18n import idioma
    l = idioma()
    return "pt" if not l or l.startswith("pt") else l.split("_")[0]


LINGUA = _lingua()
SUF = "" if LINGUA == "pt" else "_" + LINGUA.upper()
# voz padrão de cada idioma quando nada foi escolhido (inglês: neural Andrew; sem internet, Piper Ryan)
PADRAO = {"pt": ("", "pt_BR-faber-medium"), "en": ("en-US-AndrewNeural", "en_US-ryan-medium")}.get(LINGUA, ("", ""))


def chosen_voice():
    """(neural voice name or None, Piper .onnx path) from the settings of the session language
    (VOZ/VOZ_LOCAL in Portuguese, VOZ_EN/VOZ_LOCAL_EN in English; lib/config.py restarts this server)."""
    voz = setting("VOZ" + SUF) or (("edge:" + PADRAO[0]) if PADRAO[0] else PADRAO[1])
    edge = voz[5:] if voz.startswith("edge:") else None
    local = (setting("VOZ_LOCAL" + SUF) or PADRAO[1]) if edge else voz
    path = os.path.join(DATA, "voices", (local or "") + ".onnx")
    if local and os.path.exists(path):
        return edge, path
    alt = os.path.join(DATA, "voices", PADRAO[1] + ".onnx")
    return edge, alt if os.path.exists(alt) else VOICE
PYTHON = os.path.join(DATA, "venv", "bin", "python")


def loudness(raw):
    s = array.array("h", raw)
    if not s:
        return 0.0
    rms = math.sqrt(sum(x * x for x in s) / len(s)) / 32768.0
    db = 20 * math.log10(max(rms, 1e-6))
    return min(max((db + 52) / 36, 0.0), 1.0)


def serve():
    from piper import PiperVoice

    os.makedirs(RUN, exist_ok=True)
    # Only one server: two clients starting at once used to leave two running.
    lockf = open(os.path.join(RUN, "tts.lock"), "w")
    try:
        import fcntl
        fcntl.flock(lockf, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        sys.exit(0)
    edge, piper_path = chosen_voice()
    voice = (edge, PiperVoice.load(piper_path))
    try:
        os.unlink(SOCK)
    except FileNotFoundError:
        pass
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCK)
    srv.listen(4)

    lock = threading.Lock()
    current = {"stop": None}

    def handle(conn):
        stop = threading.Event()
        with lock:
            if current["stop"]:
                current["stop"].set()
            current["stop"] = stop
        try:
            req = json.loads(conn.makefile().readline() or "{}")
            speak(voice, req.get("text", ""), req.get("levels"), conn, stop)
            conn.sendall(b"ok\n")
        except (OSError, ValueError):
            pass
        finally:
            conn.close()

    while True:
        conn, _ = srv.accept()
        threading.Thread(target=handle, args=(conn,), daemon=True).start()


CHAR_MS = {"piper": 62, "edge": 110}  # ms of audio per character of text, roughly (measured)


def edge_stream(name, text, out, halt):
    """Microsoft neural voice -> 24 kHz PCM chunks into `out` (None at the end)."""
    import asyncio
    import edge_tts
    dec = subprocess.Popen(["ffmpeg", "-nostdin", "-loglevel", "error", "-f", "mp3", "-i", "pipe:0",
                            "-f", "s16le", "-ac", "1", "-ar", "24000", "pipe:1"],
                           stdin=subprocess.PIPE, stdout=subprocess.PIPE)

    def read():
        while True:
            b = dec.stdout.read(4800)  # 0.1 s
            if not b:
                break
            out.put((b, 24000))
    reader = threading.Thread(target=read, daemon=True)
    reader.start()

    async def feed():
        async for ch in edge_tts.Communicate(text, name, boundary="WordBoundary").stream():
            if halt.is_set():
                break
            if ch["type"] == "audio":
                dec.stdin.write(ch["data"])
                dec.stdin.flush()
            elif ch["type"] == "WordBoundary":
                out.put(("w", round(ch["offset"] / 1e4)))  # 100 ns ticks -> ms
    try:
        asyncio.run(asyncio.wait_for(feed(), 60))
    except Exception:
        pass
    finally:
        try:
            dec.stdin.close()
        except OSError:
            pass
        if halt.is_set():
            dec.kill()
        reader.join()
        dec.wait()
        out.put(None)


def speak(voice, text, levels_path, conn, stop):
    """Play while synthesizing: the first sentence starts as soon as it's ready (a long
    reply used to wait ~2.5 s for all of it). The orb gets an estimated duration ("d"),
    corrected once synthesis is done."""
    halt = threading.Event()

    def cancelled():
        if stop.is_set() or halt.is_set():
            return True
        r, _, _ = select.select([conn], [], [], 0)
        return bool(r) and conn.recv(1, socket.MSG_PEEK) == b""  # client went away

    pieces = queue.Queue()
    edge, piper = voice
    engine = ["edge" if edge else "piper"]

    def piper_synth():
        for chunk in piper.synthesize(text):
            if halt.is_set() or stop.is_set():
                break
            pieces.put((chunk.audio_int16_bytes, chunk.sample_rate))

    def produce():
        try:
            if edge:
                got, edge_halt = queue.Queue(), threading.Event()
                threading.Thread(target=edge_stream, args=(edge, text, got, edge_halt), daemon=True).start()
                words, first, t0 = [], None, time.monotonic()
                try:  # word timings may come before the first audio: audio goes first
                    while True:
                        item = got.get(timeout=max(EDGE_WAIT - (time.monotonic() - t0), 0.01))
                        if item is None or item[0] != "w":
                            first = item
                            break
                        words.append(item)
                except queue.Empty:
                    first = None
                if first is not None:
                    pieces.put(first)
                    for w in words:
                        pieces.put(w)
                    while (item := got.get()) is not None:
                        if halt.is_set() or stop.is_set():
                            edge_halt.set()
                            break
                        pieces.put(item)
                    return
                edge_halt.set()  # offline or too slow: the local voice instead
                engine[0] = "piper"
            piper_synth()
        finally:
            pieces.put(None)
    threading.Thread(target=produce, daemon=True).start()

    first = pieces.get()
    if first is None or cancelled():
        halt.set()
        return
    rate = first[1]

    out = open(levels_path, "w", buffering=1) if levels_path else None
    if out:
        out.write(f"d {len(text) * CHAR_MS[engine[0]]}\n")  # estimate; corrected below

    play = subprocess.Popen(
        ["pw-play", "--raw", "--rate", str(rate), "--channels", "1", "--format", "s16", "-"],
        stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    step = (rate // 30) * 2
    lead = 0.08  # keep pw-play slightly ahead so levels match what you hear
    start = time.monotonic()
    sent = 0  # bytes played so far
    buf, done = first[0], False
    try:
        while buf or not done:
            if len(buf) < step and not done:  # need more audio
                nxt = pieces.get()
                if nxt is None:
                    done = True
                    if out:
                        out.write(f"d {(sent + len(buf)) * 500 // rate}\n")  # real duration
                elif nxt[0] == "w":
                    if out:
                        out.write(f"w {nxt[1]}\n")  # a word starts at this audio time
                else:
                    buf += nxt[0]
                continue
            if cancelled():
                halt.set()
                play.kill()
                play.wait()
                return
            piece, buf = buf[:step], buf[step:]
            play.stdin.write(piece)
            play.stdin.flush()
            sent += len(piece)
            if out:
                out.write(f"{loudness(piece):.3f}\n")
            ahead = start + sent / 2 / rate - lead - time.monotonic()
            if ahead > 0:
                time.sleep(ahead)
        play.stdin.close()
        while play.poll() is None:
            if cancelled():
                play.kill()
                play.wait()
                return
            time.sleep(0.03)
    except BrokenPipeError:
        pass
    finally:
        halt.set()
        if out:
            out.write("0\n")
            out.close()


def say(text, levels):
    def connect():
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(SOCK)
        return s

    try:
        s = connect()
    except OSError:
        subprocess.Popen([PYTHON, os.path.abspath(__file__), "serve"],
                         start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            time.sleep(0.05)
            try:
                s = connect()
                break
            except OSError:
                continue
        else:
            sys.exit("draco tts: server did not start")
    s.sendall((json.dumps({"text": text, "levels": levels}) + "\n").encode())
    s.recv(16)  # returns when playback ends


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["serve"]:
        serve()
    elif args[:1] == ["say"]:
        levels = None
        if args[1:2] == ["--levels"]:
            levels, args = args[2], args[2:]
        say(" ".join(args[1:]), levels)
    else:
        sys.exit(__doc__)
