#!/usr/bin/env python3
"""Draco wake word: say "Draco", the orb shows up at once and waits for what you want.

A dedicated keyword spotter (openWakeWord's speech features + a small classifier
trained by wake_train.py on "Draco") runs on the mic in 80 ms steps, locally and
cheaply, gated by the Silero VAD (no speech, no detection). On "Draco", recording starts.
If the detector is sure (score >= the model's "instant" bar), the orb shows at once,
written straight to the orb's command file (no script in between: ~0 ms). Either way
the 2 s that triggered it are double-checked: Whisper large in the cloud (Groq/OpenAI, per the settings; ~0.5 s;
lib/transcript.py decides), or Whisper tiny locally when offline. Then
    `draco wake-listen`            the orb appears (only once confirmed, or after
                                   ANNOUNCE_MAX s if the check is slow), so false alarms
                                   neither flash the orb nor interrupt Draco speaking
    waits up to COMMAND_WAIT s for you to start talking, records until you stop
    for END_SILENCE s (Silero VAD), then
    `draco wake-process <wav> <s> <trigger.wav> [trigger.json]`
                                   same pipeline as F10; the wav starts with the <s>
                                   seconds before the detection (the trigger), and
                                   lib/transcript.py cuts the request after "Draco"
If you say nothing, the orb goes away (`draco wake-cancel`).

When Draco's reply ends with a question, the draco script creates $RUN/wake.followup:
the mic opens for your answer right away, no "Draco" needed (`draco wake-process <wav> -`).

  wake.py                  run the detector (systemd user service draco-wake)
  wake.py --teste          print detection scores; trigger nothing
  wake.py --teste --arquivo <wav>   same, reading a file instead of the mic
  wake.py --gravar         = `draco treinar`: teach it your voice (wake_record.py)

Pause with `draco escuta desliga` (the mic is closed while paused).
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))
from simba_i18n import idioma as _idioma  # noqa: E402
_l = _idioma()
LINGUA = "pt" if not _l or _l.startswith("pt") else _l.split("_")[0]   # idioma da sessão (Whisper)
import collections
import difflib
import os
import re
import threading
import unicodedata
import subprocess
import sys
import time
import wave

import numpy as np
import onnxruntime as ort
from scipy.signal import butter, sosfilt
from openwakeword.utils import AudioFeatures

RUN = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "draco")
CODIGO = os.path.dirname(os.path.abspath(__file__))   # /usr/share/draco (pacote)
DATA = os.path.expanduser("~/.local/share/draco")     # dados do usuário
DRACO = os.path.expanduser("/usr/bin/draco")
DISABLED = os.path.join(DATA, "wake.disabled")
ABORT = os.path.join(RUN, "wake.abort")
FOLLOWUP = os.path.join(RUN, "wake.followup" + (".teste" if "--teste" in sys.argv else ""))
MODEL = os.path.join(DATA, "models", "draco_wake.npz")
if not os.path.exists(MODEL):
    MODEL = os.path.join(CODIGO, "models", "draco_wake.npz")
TRANSCRIPT = os.path.join(CODIGO, "lib", "transcript.py")
sys.path.insert(0, os.path.join(CODIGO, "lib"))
import config as settings  # noqa: E402  (~/.config/draco: transcription service, timings)

RATE = 16000
CHUNK = 1280                # 80 ms: openWakeWord's step
VAD_FRAME = 512             # 32 ms: Silero's frame
THRESHOLD = 0.75            # classifier score needed (unless the model brings its own, from wake_train.py)...
HITS = 1                    # ...on this many consecutive 80 ms steps (Whisper and the transcript double-check)
SPEECH_RECENT = 1.0         # a detection needs speech (Silero) within this many seconds
REFRACTORY = 2.0            # seconds before another detection
ANNOUNCE_MAX = 1.5          # show the orb after this long even if the check hasn't answered
INSTANT = 0.97              # score that shows the orb before the check (unless the model brings its own)
ORB_CMD = os.path.join(RUN, "orb.cmd")
COMMAND_WAIT = 5.0          # how long the orb waits for you to start talking (settings: ESPERA)
END_SILENCE = 2.0           # pause that ends the command (settings: SILENCIO)
MIN_SPEECH = 0.2            # voiced time that counts as "started talking" (not a click or a breath)
MAX_COMMAND = 30.0
PREROLL = 0.4               # audio kept from just before the command starts
TAIL = 0.3                  # silence kept after the command
WAKE_AUDIO = 2.0            # audio before the detection: Whisper's check, and the start of the wav
SPEECH_ON, SPEECH_OFF = 0.5, 0.35   # Silero hysteresis
NEAR = 0.2                  # speech quieter than this share of the "Draco" level is someone else
                            # (TV, people talking farther away): it neither starts nor holds the recording

TEST = "--teste" in sys.argv
FILE = sys.argv[sys.argv.index("--arquivo") + 1] if "--arquivo" in sys.argv else None
# Só o caminho do modelo VAD que vem no faster_whisper: achar o pacote sem importá-lo
# (o import puxa o ctranslate2 e atrasava o início do serviço).
import importlib.util  # noqa: E402
SILERO = os.path.join(os.path.dirname(importlib.util.find_spec("faster_whisper").origin), "assets", "silero_vad_v6.onnx")


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


class Classifier:
    """The MLP trained by wake_train.py, in plain numpy."""

    def __init__(self):
        m = np.load(MODEL)
        self.mean, self.scale = m["mean"], m["scale"]
        self.W1, self.b1, self.W2, self.b2 = m["W1"], m["b1"], m["W2"], m["b2"]
        self.threshold = float(m["threshold"]) if "threshold" in m.files else THRESHOLD
        self.instant = float(m["instant"]) if "instant" in m.files else INSTANT
        cfg = settings.load()
        if cfg.get("LIMIAR"):  # settings override: lower = more sensitive
            self.threshold = settings.number(cfg, "LIMIAR")

    def score(self, feats):
        x = (feats.reshape(1, -1) - self.mean) / self.scale
        h = np.maximum(x @ self.W1 + self.b1, 0)
        z = (h @ self.W2 + self.b2).item()
        return 1 / (1 + np.exp(-z))


class Features(AudioFeatures):
    """openWakeWord's streaming features, resettable without reloading the ONNX models."""

    def __init__(self):
        o = ort.SessionOptions()
        o.inter_op_num_threads = o.intra_op_num_threads = 1
        o.log_severity_level = 3
        d = os.path.join(os.path.dirname(__import__("openwakeword").__file__), "resources", "models")
        self.melspec_model = ort.InferenceSession(os.path.join(d, "melspectrogram.onnx"), o, providers=["CPUExecutionProvider"])
        self.embedding_model = ort.InferenceSession(os.path.join(d, "embedding_model.onnx"), o, providers=["CPUExecutionProvider"])
        self.onnx_execution_provider = "CPUExecutionProvider"
        self.melspectrogram_max_len = 10 * 97
        self.feature_buffer_max_len = 120
        self.blank = self._get_embeddings(np.zeros(160000).astype(np.int16))
        self.reset()

    def reset(self):
        self.raw_data_buffer = collections.deque(maxlen=RATE * 10)
        self.melspectrogram_buffer = np.ones((76, 32))
        self.accumulated_samples = 0
        self.feature_buffer = self.blank.copy()


class VAD:
    """Silero VAD (the one bundled with faster-whisper), streaming, 32 ms frames."""

    def __init__(self):
        o = ort.SessionOptions()
        o.inter_op_num_threads = o.intra_op_num_threads = 1
        o.log_severity_level = 4
        self.session = ort.InferenceSession(SILERO, o, providers=["CPUExecutionProvider"])
        self.reset()

    def reset(self):
        self.h = np.zeros((1, 1, 128), np.float32)
        self.c = np.zeros((1, 1, 128), np.float32)
        self.context = np.zeros(64, np.float32)
        self.pending = np.zeros(0, np.float32)

    def __call__(self, raw):
        """(speech probability, RMS) of each whole 32 ms frame completed by `raw`."""
        a = np.concatenate([self.pending, np.frombuffer(raw, np.int16).astype(np.float32) / 32768])
        n = len(a) // VAD_FRAME * VAD_FRAME
        self.pending = a[n:]
        probs = []
        for i in range(0, n, VAD_FRAME):
            frame = a[i:i + VAD_FRAME]
            x = np.concatenate([self.context, frame])[None]
            self.context = frame[-64:]
            p, self.h, self.c = self.session.run(None, {"input": x, "h": self.h, "c": self.c})
            probs.append((float(p.ravel()[0]), float(np.sqrt(np.mean(frame ** 2)))))
        return probs


class Verifier:
    """Second opinion on the audio that triggered the detector."""

    def __init__(self):
        self.tiny = None  # local fallback, loaded on first need

    def check(self, pcm, out_json):
        """"sim"/"nao" from the cloud Whisper (writes its transcript to out_json); None if
        there is none configured or it failed."""
        service = settings.stt()
        if not service:
            return None
        base, key, model = service
        wav = save_wav(pcm, out_json[:-5] + ".wav")
        try:
            subprocess.run(
                ["curl", "-sS", "--max-time", "4", f"{base}/audio/transcriptions",
                 "-H", f"Authorization: Bearer {key}", "-F", f"model={model}", "-F", f"language={LINGUA}",
                 "-F", "temperature=0", "-F", "response_format=verbose_json", "-F", f"file=@{wav}", "-o", out_json],
                check=True, stderr=subprocess.DEVNULL, timeout=6)
            with open(out_json) as f:
                if "segments" not in f.read():
                    return None
        except (subprocess.SubprocessError, OSError):
            return None
        verdict = subprocess.run([sys.executable, "-I", TRANSCRIPT, "gatilho", out_json]).returncode
        if TEST:
            import json
            with open(out_json) as f:
                log(f"  verificação (nuvem): {json.load(f).get('text', '').strip()!r} -> {'sim' if verdict == 0 else 'não'}")
        return "sim" if verdict == 0 else "nao"

    @staticmethod
    def sounds_like_draco(text):
        words = re.findall(r"[a-z]+", unicodedata.normalize("NFKD", text.lower()).encode("ascii", "ignore").decode())
        return any(difflib.SequenceMatcher(None, w, "draco").ratio() >= 0.75 for w in words)

    def rejects_locally(self, pcm):
        """Whisper tiny: True only when it clearly heard something else (when unsure, trust the detector)."""
        if self.tiny is None:
            from faster_whisper import WhisperModel
            self.tiny = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=4,
                                     download_root=os.path.join(DATA, "models", "whisper"))
        audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
        segs = list(self.tiny.transcribe(
            audio, language=LINGUA, hotwords="Draco", beam_size=1, temperature=0.0, max_new_tokens=12,
            without_timestamps=True, condition_on_previous_text=False)[0])
        text = " ".join(s.text for s in segs).strip()
        confident = segs and max(s.no_speech_prob for s in segs) < 0.5 and min(s.avg_logprob for s in segs) > -1.0
        if TEST:
            log(f"  verificação (local): {text!r} ({'confiante' if confident else 'incerta'})")
        return bool(confident and text and not self.sounds_like_draco(text))

    def run(self, pcm, out_json, rejected, done):
        """Thread body: set `rejected` if it wasn't "Draco"; `done` when decided."""
        try:
            verdict = self.check(pcm, out_json)
            if verdict == "nao" or (verdict is None and self.rejects_locally(pcm)):
                rejected.set()
        finally:
            done.set()


class Mic:
    # High-pass at 80 Hz (below any voice): a fan / table rumble under 30 Hz was
    # reaching 0 dB and burying the speech for both the detector and Whisper.
    HIGHPASS = butter(4, 80, "highpass", fs=RATE, output="sos")

    def __init__(self):
        # --raw: sem ele o pw-record (PipeWire >= 1.6.10) escreve na saída padrão um arquivo
        # AU (cabeçalho ".snd" + amostras big-endian), que lido como s16 little-endian é só
        # chiado: o detector ficava surdo sem dar erro nenhum.
        self.proc = subprocess.Popen(
            ["pw-record", "--raw", "--rate", str(RATE), "--channels", "1", "--format", "s16", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.zi = np.zeros((len(self.HIGHPASS), 2))

    def read(self, n):
        raw = self.proc.stdout.read(n * 2)
        if len(raw) < n * 2:
            raise EOFError
        x, self.zi = sosfilt(self.HIGHPASS, np.frombuffer(raw, np.int16).astype(np.float32), zi=self.zi)
        return np.clip(x, -32768, 32767).astype(np.int16).tobytes()

    def close(self):
        self.proc.terminate()
        self.proc.wait()


class FileMic:
    """--arquivo: a wav instead of the mic (read faster than real time), then 8 s of silence."""

    def __init__(self, path):
        with wave.open(path) as w:
            assert w.getframerate() == RATE and w.getnchannels() == 1 and w.getsampwidth() == 2, "use wav 16 kHz mono s16"
            self.data = w.readframes(w.getnframes()) + bytes(RATE * 8 * 2)
        self.pos = 0

    def read(self, n):
        raw = self.data[self.pos:self.pos + n * 2]
        self.pos += n * 2
        if len(raw) < n * 2:
            raise EOFError
        return raw

    def close(self):
        pass


def draco(*args):
    if TEST:
        log(f"(teste) draco {' '.join(args)}")
        return
    subprocess.Popen([DRACO, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def orb(cmd):
    """Straight to the on-screen orb (it watches this file), skipping the draco script."""
    if TEST:
        log(f"(teste) orb {cmd}")
        return
    try:
        with open(ORB_CMD, "a") as f:
            f.write(f'{{"s":"{time.time_ns()}","c":"{cmd}","a":[]}}\n')
    except OSError:
        pass


def save_wav(pcm, path):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    return path


def aborted():
    if os.path.exists(ABORT):
        os.unlink(ABORT)
        return True
    return False


def speech_level(vad_frames):
    """Loudness of the voice in some audio: a high percentile of its voiced frames."""
    rms = [r for p, r in vad_frames if p >= SPEECH_ON]
    return float(np.percentile(rms, 80)) if rms else 0.0


def keep(pcm, kind):
    """Used to save the trigger for retraining (wake_train.py); disabled for privacy:
    nothing you say is kept on disk."""
    return
    folder = os.path.join(DATA, "wake-train", kind)
    os.makedirs(folder, exist_ok=True)
    save_wav(pcm, os.path.join(folder, time.strftime("%Y-%m-%d_%H%M%S.wav")))
    for old in sorted(os.listdir(folder))[:-300]:
        os.unlink(os.path.join(folder, old))


def capture_command(mic, vad, rejected, level, tick=lambda: None, wait=COMMAND_WAIT, end_silence=END_SILENCE):
    """After "Draco": wait up to COMMAND_WAIT s for speech, record until END_SILENCE s
    of silence. Only speech near the "Draco" `level` counts. None if nothing was said
    (or the verifier set `rejected`)."""
    before = collections.deque(maxlen=int(PREROLL * RATE / CHUNK) + 1)
    pcm = bytearray()
    started, speaking = False, False
    voiced = silent = waited = 0.0  # audio time, so --arquivo behaves like the mic
    frame = VAD_FRAME / RATE
    while True:
        raw = mic.read(CHUNK)
        tick()
        if aborted() or rejected.is_set():
            return None
        for p, rms in vad(raw):
            speaking = rms >= NEAR * level and (p >= SPEECH_ON or (speaking and p >= SPEECH_OFF))
            if not started:
                voiced = voiced + frame if speaking else max(0.0, voiced - frame / 2)
            else:
                silent = 0.0 if speaking else silent + frame
        if not started:
            before.append(raw)
            waited += CHUNK / RATE
            if voiced >= MIN_SPEECH:
                started = True
                pcm.extend(b"".join(before))  # keep the start of the first word
            elif waited > wait:
                return None
            continue
        pcm.extend(raw)
        if silent >= end_silence:
            keep = len(pcm) - int((silent - TAIL) * RATE) * 2
            return bytes(pcm[:max(keep, 0)])
        if len(pcm) / 2 / RATE > MAX_COMMAND:
            return bytes(pcm)


def follow_up(mic, vad, level):
    """Draco asked something: take the answer without the wake word."""
    log("Draco perguntou algo: ouvindo a resposta")
    if os.path.exists(ABORT):
        os.unlink(ABORT)
    draco("wake-listen")
    cfg = settings.load()
    command = capture_command(mic, vad, threading.Event(), level, wait=settings.number(cfg, "ESPERA"),
                              end_silence=settings.number(cfg, "SILENCIO"))
    if command is None:
        draco("wake-cancel")
        log("sem resposta; orb fechado")
        return
    draco("wake-process", save_wav(command, os.path.join(RUN, "wake-command.wav")), "-")
    log(f"resposta: {len(command) / 2 / RATE:.1f}s")


def busy():
    """F10 push-to-talk is recording: stay out of the way."""
    return os.path.exists(os.path.join(RUN, "rec.pid"))


def listen(clf, verifier, feats, vad, mic):
    log(f"ouvindo (diga 'Draco'; limiar {clf.threshold:.2f})")
    hits, last, since_speech, t, peak = 0, -REFRACTORY, 99.0, 0.0, 0.0
    speaking = False
    history = collections.deque(maxlen=int(WAKE_AUDIO * RATE / CHUNK))
    recent = collections.deque(maxlen=int(1.2 * RATE / VAD_FRAME))  # VAD of the last ~1.2 s: the "Draco"
    voice = 0.0  # loudness of your last "Draco": answers quieter than a fifth of it are someone else
    while not os.path.exists(DISABLED):
        raw = mic.read(CHUNK)
        t += CHUNK / RATE
        if os.path.exists(FOLLOWUP):
            os.unlink(FOLLOWUP)
            vad.reset()
            follow_up(mic, vad, voice)
            feats.reset()
            history.clear()
            recent.clear()
            hits, last = 0, t
            continue
        history.append(raw)
        frames = vad(raw)
        recent.extend(frames)
        for p, _ in frames:
            speaking = p >= SPEECH_ON or (speaking and p >= SPEECH_OFF)
            since_speech = 0.0 if speaking else since_speech + VAD_FRAME / RATE
        feats(np.frombuffer(raw, np.int16))
        score = clf.score(feats.get_features(16))
        if TEST and score > 0.3:
            log(f"  [{t:6.2f}s] score {score:.2f}{'' if since_speech <= SPEECH_RECENT else ' (sem voz: ignorado)'}")
        hits = hits + 1 if score >= clf.threshold and since_speech <= SPEECH_RECENT else 0
        peak = score if hits == 1 else max(peak, score)
        if hits < HITS or t - last < REFRACTORY or busy():
            continue
        early = peak >= clf.instant and not busy()
        if early:
            orb("listening")  # first thing: you see it while still finishing the word
        log(f"Draco! ({peak:.3f}{', orb na hora' if early else ''})")
        if os.path.exists(ABORT):
            os.unlink(ABORT)
        rejected, checked = threading.Event(), threading.Event()
        shown, t_hit = [False], time.monotonic()

        def announce():
            """Show the orb once the check confirms it (or takes too long)."""
            if not shown[0] and not rejected.is_set() and (checked.is_set() or time.monotonic() - t_hit > ANNOUNCE_MAX):
                shown[0] = True
                draco("wake-listen")
        heard = b"".join(history)
        trigger_json = os.path.join(RUN, "wake-trigger.json")
        if os.path.exists(trigger_json):
            os.unlink(trigger_json)
        threading.Thread(target=verifier.run, args=(heard, trigger_json, rejected, checked), daemon=True).start()
        if FILE:
            checked.wait()  # a file is read faster than real time
        level = speech_level(recent)
        if TEST:
            log(f"  nível da voz: {level:.3f}")
        cfg = settings.load()
        command = capture_command(mic, vad, rejected, level, announce,
                                  settings.number(cfg, "ESPERA"), settings.number(cfg, "SILENCIO"))
        if not rejected.is_set() and command is not None:
            checked.wait(3)  # the request is ready; the check should be too (wake-process shows the orb)
        if rejected.is_set():
            if early and not shown[0]:
                orb("hide")
            if shown[0]:
                draco("wake-cancel")
            keep(heard, "auto-nao")
            log("alarme falso (o Whisper ouviu outra coisa); orb fechado")
        elif command is None:
            if early and not shown[0]:
                orb("hide")
            if shown[0]:
                draco("wake-cancel")
            log("nada foi dito; orb fechado")
        else:
            wav = save_wav(heard + command, os.path.join(RUN, "wake-command.wav"))
            trigger = save_wav(heard, os.path.join(RUN, "wake-trigger.wav"))
            voice = level or voice
            draco("wake-process", wav, f"{len(heard) / 2 / RATE:.2f}", trigger,
                  *([trigger_json] if os.path.exists(trigger_json) else []))
            log(f"comando: {len(command) / 2 / RATE:.1f}s")
        # start the features fresh, so the command itself can't re-trigger
        feats.reset()
        history.clear()
        recent.clear()
        hits, last = 0, t


def record_samples():
    """Moved: the guided session (wake_record.py, `draco treinar`) records and retrains."""
    os.execv(sys.executable, [sys.executable, "-I", os.path.join(CODIGO, "wake_record.py")])


def main():
    if "--gravar" in sys.argv:
        record_samples()
        return
    os.makedirs(RUN, exist_ok=True)
    clf, verifier, feats, vad = Classifier(), Verifier(), Features(), VAD()
    if FILE:
        try:
            listen(clf, verifier, feats, vad, FileMic(FILE))
        except EOFError:
            pass
        return
    while True:
        if os.path.exists(DISABLED):
            time.sleep(1)  # paused: mic closed
            continue
        mic = Mic()
        try:
            listen(clf, verifier, feats, vad, mic)
        except EOFError:
            log("microfone fechou; reabrindo")
            time.sleep(1)
        finally:
            mic.close()
            feats.reset()
            vad.reset()


if __name__ == "__main__":
    main()
