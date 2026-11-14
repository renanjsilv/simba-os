#!/usr/bin/env python3
"""Print a 0..1 loudness value ~30 times per second.

  level.py            listen to the default microphone (via pw-record)
  level.py file.wav   read a WAV file, paced in real time (speech playback)
"""
import array, math, signal, subprocess, sys, time, wave

CHUNK = 533  # ~1/30 s at 16 kHz


floor = None  # adaptive noise floor (dB), so room hiss reads as silence


def loudness(raw, adaptive=False):
    global floor
    s = array.array("h", raw)
    if not s:
        return 0.0
    rms = math.sqrt(sum(x * x for x in s) / len(s)) / 32768.0
    db = 20 * math.log10(max(rms, 1e-6))
    if not adaptive:
        return min(max((db + 52) / 36, 0.0), 1.0)
    floor = db if floor is None else min(db, floor + 0.08)
    return min(max((db - floor - 4) / 28, 0.0), 1.0)


def emit(v):
    sys.stdout.write(f"{v:.3f}\n")
    sys.stdout.flush()


try:
    if len(sys.argv) > 1:
        with wave.open(sys.argv[1]) as w:
            rate, width = w.getframerate(), w.getsampwidth()
            n = max(rate // 30, 1)
            start = time.monotonic()
            frames = 0
            while True:
                raw = w.readframes(n)
                if not raw or width != 2:
                    break
                frames += n
                emit(loudness(raw))
                time.sleep(max(start + frames / rate - time.monotonic(), 0))
        emit(0)
    else:
        signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
        rec = subprocess.Popen(
            ["pw-record", "--raw", "--rate", "16000", "--channels", "1", "--format", "s16", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            while raw := rec.stdout.read(CHUNK * 2):
                emit(loudness(raw, adaptive=True))
        finally:
            rec.terminate()
except (BrokenPipeError, KeyboardInterrupt):
    pass
