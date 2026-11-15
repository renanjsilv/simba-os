#!/usr/bin/env python3
"""Draco wake word: say "Draco", the orb shows up and waits for what you want.

Two stages, like the commercial assistants:
  1. Detector (always on, cheap): openWakeWord's speech features + a small classifier
     trained by wake_train.py on "Draco", run on the mic in 80 ms steps, gated by the
     Silero VAD. It fires on HITS consecutive steps over the threshold (one lucky step
     was the main source of false alarms). While Draco itself is talking it is muted
     (its own voice in the speakers is not "Draco"); while other audio plays (a video,
     music) its bar goes up.
  2. Verifier (only on a detection): Whisper transcribes the ~2 s around the detection
     and it must contain the word "Draco" (or how Whisper writes it: Drako, Dracu...).
     The cloud Whisper (Groq/OpenAI, per the settings) when there is one, else Whisper
     tiny on this computer, loaded at start so it answers in ~0.2 s. Sound-alikes
     ("fraco", "braço", "Drácula", "dragão") are rejected.
Recording starts at the detection, so nothing you say is lost while it checks:
    `draco wake-listen`            the orb appears once the verifier confirms it
    waits up to COMMAND_WAIT s for you to start talking, records until you stop
    for END_SILENCE s (Silero VAD), then
    `draco wake-process <wav> <s> <trigger.wav> [trigger.json]`
                                   same pipeline as F10; the wav starts with the <s>
                                   seconds before the detection (the trigger), and
                                   lib/transcript.py cuts the request after "Draco"
If you say nothing, the orb goes away (`draco wake-cancel`).

Every detection is logged (journal, and numbers only in ~/.local/share/draco/wake-metrics.jsonl:
score, threshold, noise, audio playing, verdict, latency) to calibrate it; no audio or text is kept.

When Draco's reply ends with a question, the draco script creates $RUN/wake.followup:
the mic opens for your answer right away, no "Draco" needed (`draco wake-process <wav> -`).

  wake.py                  run the detector (systemd user service draco-wake)
  wake.py --teste          print detection scores and transcripts; trigger nothing
  wake.py --teste --arquivo <wav>   same, reading a file instead of the mic
  wake.py --gravar         = `draco treinar`: teach it your voice (wake_record.py)
  tests/bench_wake.py      reproducible benchmark (recall / false alarms per hour)

Turn it off with `draco escuta desliga` (or the settings): the service is stopped and
disabled, so it uses no memory; F10 still works. When the package updates this file,
the running service notices and restarts itself (systemd brings it back) with the new code.
"""
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))
from simba_i18n import idioma as _idioma  # noqa: E402
_l = _idioma()
LINGUA = "pt" if not _l or _l.startswith("pt") else _l.split("_")[0]   # idioma da sessão (Whisper)
import collections
import json
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
THRESHOLD = 0.85            # detector score needed (settings LIMIAR overrides; lower = more sensitive)...
HITS = 2                    # ...on this many consecutive 80 ms steps. tests/bench_wake.py: two steps
                            # catch as many "Draco"s as one and give a third of the false alarms on
                            # nonstop talk (a single-step spike is rarely the word). The model's own
                            # stored threshold was tuned for one step and no verifier: not used.
PLAYING_BUMP = 0.06         # threshold raise while other audio plays (videos, music: "the TV said it")
NOISY_DB, NOISY_BUMP = 10.0, 0.03    # and while the room is this many dB louder than usual (a TV,
                            # a blender): relative, since this laptop's mic idles at ~-27 dBFS (max gain)
SPEECH_RECENT = 1.0         # a detection needs speech (Silero) within this many seconds
REFRACTORY = 2.0            # seconds before another detection
TTS_HOLD = 0.6              # Draco's own voice: deaf while it talks and this long after (echo tail)
VERIFY_TAIL = 4             # 80 ms steps after the detection given to the verifier (the end of the word)
VERIFY_MAX = 2.5            # verifier taking longer than this: trust a sure detector (>= SURE), else drop it
SURE = 0.98
SURE_ASR = 0.97             # detector this sure: Whisper biased towards "Draco" is enough (see confirms)
FRAMES = 1000               # Whisper's encoder sees 10 s, not 30: 2x faster, and more "Draco"s confirmed
ORB_CMD = os.path.join(RUN, "orb.cmd")
SPEECH_LEVEL = os.path.join(RUN, "speech.level")   # written ~30x/s by tts.py while Draco talks
METRICS = os.path.join(DATA, "wake-metrics.jsonl")
COMMAND_WAIT = 5.0          # how long the orb waits for you to start talking (settings: ESPERA)
END_SILENCE = 2.0           # pause that ends the command (settings: SILENCIO)
MIN_SPEECH = 0.2            # voiced time that counts as "started talking" (not a click or a breath)
MAX_COMMAND = 15.0          # a TV or a conversation behind you kept 30 s recordings open
PREROLL = 0.4               # audio kept from just before the command starts
TAIL = 0.3                  # silence kept after the command
WAKE_AUDIO = 2.0            # audio before the detection: Whisper's check, and the start of the wav
SPEECH_ON, SPEECH_OFF = 0.5, 0.35   # Silero hysteresis
NEAR = 0.2                  # speech quieter than this share of the "Draco" level is someone else
                            # (TV, people talking farther away): it neither starts nor holds the recording

TEST = "--teste" in sys.argv
CODE_MTIME = os.path.getmtime(os.path.abspath(__file__))


class Updated(Exception):
    """wake.py changed on disk (package update): exit so systemd starts the new code."""


def check_updated():
    try:
        if os.path.getmtime(os.path.abspath(__file__)) != CODE_MTIME:
            raise Updated
    except OSError:
        pass
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
        self.threshold = THRESHOLD
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


# How Whisper writes "Draco" (accents stripped, k/q -> c), measured on held-out voices and
# Renan's takes (tests/bench_wake.py): Draco, Dracu, Dracur, Drac, Drago, Drico, "O Raco",
# and glued to what came before ("Podraco", "Odraco").
DRACO_WORD = re.compile(r"^[a-z]{0,2}(drac|draco|dracos|dracco|dracu|dracur|dracu(?!l)[a-z]+|drago|drico)$|^raco$")
# What Whisper writes for the sound-alikes ("ç" kept apart: "braço" is not "Braco").
SOUNDALIKE = re.compile(r"^(dracul[a-z]*|bracul[a-z]*|dragon|dragao|draga|dragas|fraco|brasso|trasso|trago|"
                        r"trato|traste|trafico|praco|parco|barco|franco|craco|macaco|grassa|arco|claro|dado)$")


def ascii_words(text):
    t = unicodedata.normalize("NFKD", text.lower().replace("ç", "ss")).encode("ascii", "ignore").decode()
    return re.findall(r"[a-z]+", t.replace("k", "c").replace("q", "c"))


def says_draco(text):
    """The matched word if `text` has "Draco" in it (also split: "Dra co", "O d'raco"), else None."""
    words = ascii_words(text)
    for i, w in enumerate(words):
        if DRACO_WORD.match(w):
            return w
        if i + 1 < len(words) and len(w) <= 4 and DRACO_WORD.match(w + words[i + 1]):
            return w + words[i + 1]
    return None


# What plain Whisper writes for a real "Draco" it didn't get right ("Traco", "braco" without
# the ç, "O daco", "Dra a corpo"); the sound-alikes almost never come out like this.
NEAR_WORD = re.compile(r"^(dra[a-z]*|trac+o|brac+o?|daco|racol?)$")


def confirms(plain, biased, peak):
    """The verifier's rule, from two transcripts of the same audio: `plain` (no bias) and
    `biased` (Whisper told to expect "Draco"), plus the detector's score. Plain alone is
    safe but deaf (it writes "Traco", "Drico" for half of the real ones); biased alone
    hears "Draco" in "Drácula", "braço" and in random talk. So: plain hears it; or biased
    hears exactly "Draco", plain heard no sound-alike, and either plain heard something
    close or the detector was sure. Measured in tests/bench_wake.py."""
    if says_draco(plain):
        return True
    words, bwords = ascii_words(plain), ascii_words(biased)
    if any(SOUNDALIKE.match(w) for w in words):
        return False
    if peak >= 0.99 and any(re.match(r"^(trac+o|raco)$", w) for w in words + bwords) \
            and not any(SOUNDALIKE.match(w) for w in bwords):
        return True  # "Ei, Traco": a near-certain detector and Whisper one letter off
    if "draco" not in bwords:
        return False
    pairs = words + [a + b for a, b in zip(words, words[1:]) if len(a) <= 4]
    return peak >= SURE_ASR or any(NEAR_WORD.match(w) and not SOUNDALIKE.match(w) for w in pairs)


class Verifier:
    """Second stage: Whisper must hear "Draco" in the audio that triggered the detector."""

    def __init__(self):
        self.tiny = None
        self.lock = threading.Lock()

    def load(self):
        """Whisper tiny on the CPU (~75 MB), loaded once: each check then takes ~0.25 s here
        (one encoder pass over 10 s; the two decodes of a word are cheap)."""
        with self.lock:
            if self.tiny is None:
                from faster_whisper import WhisperModel
                from faster_whisper.tokenizer import Tokenizer
                m = WhisperModel("tiny", device="cpu", compute_type="int8", cpu_threads=4,
                                 download_root=os.path.join(DATA, "models", "whisper"))
                tok = Tokenizer(m.hf_tokenizer, True, task="transcribe", language=LINGUA)
                start = list(tok.sot_sequence) + [tok.no_timestamps]
                self.prompts = (start, [tok.sot_prev] + tok.encode(" Draco") + start)
                self.tok, self.tiny = tok, m
                self.local(np.zeros(RATE, np.int16).tobytes())  # warm up
        return self.tiny

    def cloud(self, pcm, out_json):
        """The cloud Whisper's transcript (also written to out_json for the draco script);
        None if there is none configured or it failed."""
        service = settings.stt()
        if not service:
            return None
        base, key, model = service
        wav = save_wav(pcm, out_json[:-5] + ".wav")
        try:
            subprocess.run(
                ["curl", "-sS", "--max-time", "2", f"{base}/audio/transcriptions",
                 "-H", f"Authorization: Bearer {key}", "-F", f"model={model}", "-F", f"language={LINGUA}",
                 "-F", "temperature=0", "-F", "response_format=verbose_json", "-F", f"file=@{wav}", "-o", out_json],
                check=True, stderr=subprocess.DEVNULL, timeout=3)
            with open(out_json) as f:
                data = json.load(f)
            if "segments" not in data:
                return None
        except (subprocess.SubprocessError, OSError, ValueError):
            return None
        # drop what Whisper makes up over silence/noise (lib/transcript.py does the same)
        return " ".join(s.get("text", "") for s in data["segments"] if s.get("no_speech_prob", 0) < 0.6)

    def local(self, pcm):
        """(plain, biased) transcripts of `pcm` by Whisper tiny, sharing one encoder pass."""
        from faster_whisper.audio import pad_or_trim
        audio = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
        enc = self.tiny.encode(pad_or_trim(self.tiny.feature_extractor(audio), FRAMES))
        out = []
        for prompt in self.prompts:
            r = self.tiny.model.generate(enc, [prompt], beam_size=1, max_length=len(prompt) + 12,
                                         return_no_speech_prob=True, suppress_blank=True, suppress_tokens=[-1])[0]
            out.append("" if r.no_speech_prob > 0.8 else self.tok.decode(r.sequences_ids[0]).strip())
        return tuple(out)

    def check(self, pcm, out_json, peak=0.0):
        """(verdict True/False, transcript, source)."""
        text = self.cloud(pcm, out_json)
        if text is not None:
            return says_draco(text) is not None, text.strip(), "nuvem"
        self.load()
        plain, biased = self.local(pcm)
        return confirms(plain, biased, peak), f"{plain} | {biased}", "local"

    def run(self, pcm, out_json, result, done, peak=0.0):
        """Thread body: result = {"ok", "text", "source", "ms"}; `done` when decided."""
        t = time.monotonic()
        try:
            result["ok"], result["text"], result["source"] = self.check(pcm, out_json, peak)
        except Exception as e:  # never take the listener down; a sure detector alone decides
            result.update(ok=None, text="", source=f"erro: {e}")
        finally:
            result["ms"] = int((time.monotonic() - t) * 1000)
            done.set()


class Playback:
    """Is sound coming out of the speakers? Draco's own voice (tts.py writes speech.level
    while talking) mutes the detector; anything else playing (a video, music) raises its bar.
    The sinks' state is polled once a second in a thread (pactl: ~5 ms)."""

    def __init__(self):
        self.playing = False
        if not FILE:
            threading.Thread(target=self.poll, daemon=True).start()

    def poll(self):
        while True:
            try:
                out = subprocess.run(["pactl", "list", "short", "sinks"], capture_output=True, text=True, timeout=3).stdout
                self.playing = any(line.split("\t")[-1].strip() == "RUNNING" for line in out.splitlines())
            except (subprocess.SubprocessError, OSError):
                self.playing = False
            time.sleep(1.0)

    @staticmethod
    def draco_talking():
        try:
            return time.time() - os.path.getmtime(SPEECH_LEVEL) < TTS_HOLD
        except OSError:
            return False


class Trigger:
    """The firing rule over the detector's scores: HITS steps in a row over the threshold,
    with speech (VAD) within SPEECH_RECENT s, and REFRACTORY s since the last one."""

    def __init__(self, hits=HITS):
        self.need, self.hits, self.peak, self.last = hits, 0, 0.0, -REFRACTORY

    def __call__(self, t, score, threshold, since_speech):
        if score >= threshold and since_speech <= SPEECH_RECENT:
            self.hits += 1
            self.peak = score if self.hits == 1 else max(self.peak, score)
        else:
            self.hits = 0
        if self.hits < self.need or t - self.last < REFRACTORY:
            return False
        self.hits, self.last = 0, t
        return True


class Detector:
    """First stage, one 80 ms chunk at a time: VAD + features + classifier (analyze), then
    the Trigger rule with a threshold that goes up while other audio plays or the room is
    loud, and nothing at all while Draco itself talks. Shared by the service and
    tests/bench_wake.py."""

    def __init__(self, clf, feats, vad, playback=None):
        self.clf, self.feats, self.vad, self.playback = clf, feats, vad, playback
        self.recent = collections.deque(maxlen=int(1.2 * RATE / VAD_FRAME))  # VAD of the last ~1.2 s
        self.noise = None  # running noise floor (RMS of non-speech frames)...
        self.usual = None  # ...and its slow average over minutes: what "quiet" is with this mic
        self.trigger = Trigger()
        self.t = 0.0
        self.reset()

    def reset(self):
        """Fresh features (so the command itself can't re-trigger); the clock keeps running."""
        self.feats.reset()
        self.recent.clear()
        self.since_speech, self.speaking, self.score = 99.0, False, 0.0
        self.trigger.hits = 0
        self.trigger.last = self.t

    @property
    def peak(self):
        return self.trigger.peak

    def noise_db(self):
        return 20 * np.log10(max(self.noise or 0, 1e-6))

    def louder_than_usual(self):
        if self.noise is None:
            return 0.0
        return 20 * np.log10(max(self.noise, 3e-4) / max(self.usual, 3e-4))

    def threshold(self):
        th = self.clf.threshold
        if self.playback and self.playback.playing:
            th += PLAYING_BUMP
        if self.louder_than_usual() > NOISY_DB and self.noise_db() > -50:
            th += NOISY_BUMP
        return min(th, 0.995)

    def analyze(self, raw):
        """Feed 80 ms: VAD state, noise floor and the classifier's score."""
        self.t += CHUNK / RATE
        frames = self.vad(raw)
        self.recent.extend(frames)
        for p, rms in frames:
            self.speaking = p >= SPEECH_ON or (self.speaking and p >= SPEECH_OFF)
            self.since_speech = 0.0 if self.speaking else self.since_speech + VAD_FRAME / RATE
            if p < SPEECH_OFF:  # follower of the background level (rises slowly, falls fast)
                if self.noise is None:
                    self.noise = self.usual = rms
                self.noise += (rms - self.noise) * (0.02 if rms > self.noise else 0.1)
                self.usual += (self.noise - self.usual) * 0.0003
        self.feats(np.frombuffer(raw, np.int16))
        self.score = self.clf.score(self.feats.get_features(16))
        return self.score

    def step(self, raw):
        """Feed 80 ms; True when "Draco" was detected (stage 1)."""
        score = self.analyze(raw)
        th = self.threshold()
        if TEST and score > 0.3:
            log(f"  [{self.t:6.2f}s] score {score:.2f} (limiar {th:.2f})"
                f"{'' if self.since_speech <= SPEECH_RECENT else ' (sem voz: ignorado)'}")
        if not self.trigger(self.t, score, th, self.since_speech):
            return False
        if self.playback and self.playback.draco_talking():
            log(f"ignorado: o próprio Draco está falando ({self.peak:.2f})")
            return False
        return True


class Mic:
    # High-pass at 80 Hz (below any voice): a fan / table rumble under 30 Hz was
    # reaching 0 dB and burying the speech for both the detector and Whisper.
    HIGHPASS = butter(4, 80, "highpass", fs=RATE, output="sos")

    def __init__(self):
        self.swap = False  # big-endian samples (an AU stream, see below)
        # --raw: sem ele o pw-record (PipeWire >= 1.6.10) escreve na saída padrão um arquivo
        # AU (cabeçalho ".snd" + amostras big-endian), que lido como s16 little-endian é só
        # chiado: o detector ficava surdo sem dar erro nenhum.
        self.proc = subprocess.Popen(
            ["pw-record", "--raw", "--rate", str(RATE), "--channels", "1", "--format", "s16", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.zi = np.zeros((len(self.HIGHPASS), 2))
        self.skip_au_header()

    def skip_au_header(self):
        """In case some pw-record ignores --raw: an AU stream starts with ".snd", the offset
        of the samples (big-endian) and their encoding; skip the header, swap the bytes."""
        head = self.proc.stdout.read(4)
        if head == b".snd":
            rest = self.proc.stdout.read(20)
            offset = int.from_bytes(rest[0:4], "big")
            self.proc.stdout.read(max(offset - 24, 0))
            self.swap = True
            log("aviso: o pw-record mandou áudio AU (big-endian); convertendo")
            self.pending = b""
        else:
            self.pending = head

    def read(self, n):
        need = n * 2 - len(self.pending)
        raw = self.pending + self.proc.stdout.read(need)
        self.pending = b""
        if len(raw) < n * 2:
            raise EOFError
        pcm = np.frombuffer(raw, ">i2" if self.swap else np.int16)
        x, self.zi = sosfilt(self.HIGHPASS, pcm.astype(np.float32), zi=self.zi)
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


def capture_command(mic, vad, rejected, level, tick=lambda raw: None, wait=COMMAND_WAIT, end_silence=END_SILENCE):
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
        tick(raw)
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


def metric(**kv):
    """One line of numbers per detection (no audio, no text): to calibrate the thresholds."""
    if TEST or FILE:
        return
    try:
        with open(METRICS, "a") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), **kv}) + "\n")
        if os.path.getsize(METRICS) > 1_000_000:
            os.replace(METRICS, METRICS + ".1")
    except OSError:
        pass


def listen(clf, verifier, feats, vad, mic, playback=None):
    det = Detector(clf, feats, vad, playback)
    log(f"ouvindo (diga 'Draco'; limiar {clf.threshold:.2f} em {HITS} passos seguidos, confirmado pelo Whisper)")
    history = collections.deque(maxlen=int(WAKE_AUDIO * RATE / CHUNK))
    voice = 0.0  # loudness of your last "Draco": answers quieter than a fifth of it are someone else
    while FILE or not os.path.exists(DISABLED):  # --arquivo: tests run even with it switched off
        raw = mic.read(CHUNK)
        if not FILE and int(det.t / 0.08) % 60 == 0:  # every ~5 s
            check_updated()
        if os.path.exists(FOLLOWUP):
            os.unlink(FOLLOWUP)
            vad.reset()
            follow_up(mic, vad, voice)
            det.reset()
            history.clear()
            continue
        history.append(raw)
        if not det.step(raw) or busy():
            continue
        peak, th, noise_db = det.peak, det.threshold(), det.noise_db()
        playing = bool(playback and playback.playing)
        log(f"Draco? (detector {peak:.3f}, limiar {th:.2f}, ruído {noise_db:.0f} dBFS, {det.louder_than_usual():+.0f} dB do normal"
            f"{', áudio tocando' if playing else ''}): conferindo")
        if os.path.exists(ABORT):
            os.unlink(ABORT)
        heard = b"".join(history)
        level = speech_level(det.recent)
        trigger_json = os.path.join(RUN, "wake-trigger.json")
        if os.path.exists(trigger_json):
            os.unlink(trigger_json)
        result, checked, rejected = {}, threading.Event(), threading.Event()
        st = {"tail": [], "started": False, "shown": False, "t0": time.monotonic()}

        def decide(final=False):
            """Show the orb once the verifier says yes; reject when it says no (or is too slow)."""
            if st["shown"] or rejected.is_set():
                return
            if checked.is_set():
                ok = result.get("ok")
                if ok or (ok is None and peak >= SURE):  # verifier broken: only a sure detector
                    st["shown"] = True
                    draco("wake-listen")
                else:
                    rejected.set()
            elif final or time.monotonic() - st["t0"] > VERIFY_MAX:
                result.setdefault("source", "demorou")
                if peak >= SURE:
                    st["shown"] = True
                    draco("wake-listen")
                else:
                    rejected.set()

        def tick(raw):
            if not st["started"]:  # the verifier gets the end of the word too
                st["tail"].append(raw)
                if len(st["tail"]) >= VERIFY_TAIL:
                    st["started"] = True
                    threading.Thread(target=verifier.run, daemon=True,
                                     args=(heard + b"".join(st["tail"]), trigger_json, result, checked, peak)).start()
                    if FILE:
                        checked.wait()  # a file is read faster than real time
                return
            decide()

        cfg = settings.load()
        command = capture_command(mic, vad, rejected, level, tick,
                                  settings.number(cfg, "ESPERA"), settings.number(cfg, "SILENCIO"))
        if st["started"] and not checked.is_set():
            checked.wait(max(0.0, VERIFY_MAX - (time.monotonic() - st["t0"])))
        decide(final=True)
        text = result.get("text", "")
        if TEST:
            log(f"  verificação ({result.get('source')}, {result.get('ms', 0)} ms): {text!r} -> "
                f"{'sim' if result.get('ok') else 'não'}")
        if rejected.is_set():
            outcome = "rejeitado"
            log(f"alarme falso: o Whisper ({result.get('source')}, {result.get('ms', 0)} ms) não ouviu 'Draco'")
        elif command is None:
            outcome = "nada dito"
            draco("wake-cancel")
            log(f"confirmado ({result.get('ms', 0)} ms), mas nada foi dito; orb fechado")
        else:
            outcome = "comando"
            wav = save_wav(heard + command, os.path.join(RUN, "wake-command.wav"))
            trigger = save_wav(heard, os.path.join(RUN, "wake-trigger.wav"))
            voice = level or voice
            draco("wake-process", wav, f"{len(heard) / 2 / RATE:.2f}", trigger,
                  *([trigger_json] if os.path.exists(trigger_json) else []))
            log(f"confirmado ({result.get('source')}, {result.get('ms', 0)} ms); comando: {len(command) / 2 / RATE:.1f}s")
        metric(score=round(peak, 3), limiar=round(th, 3), ruido_db=round(noise_db, 1), tocando=playing,
               verificador=result.get("source"), ms=result.get("ms"), ok=result.get("ok"), resultado=outcome,
               palavras=len(ascii_words(text)))
        det.reset()  # start the features fresh, so the command itself can't re-trigger
        history.clear()


def record_samples():
    """Moved: the guided session (wake_record.py, `draco treinar`) records and retrains."""
    os.execv(sys.executable, [sys.executable, "-I", os.path.join(CODIGO, "wake_record.py")])


def main():
    if "--gravar" in sys.argv:
        record_samples()
        return
    os.makedirs(RUN, exist_ok=True)
    clf, verifier, feats, vad = Classifier(), Verifier(), Features(), VAD()
    if not settings.stt() or FILE:  # local check: load Whisper tiny now, not on the first "Draco"
        threading.Thread(target=verifier.load, daemon=True).start()
    if FILE:
        try:
            listen(clf, verifier, feats, vad, FileMic(FILE))
        except EOFError:
            pass
        return
    playback = Playback()
    while True:
        if os.path.exists(DISABLED):
            time.sleep(1)  # paused: mic closed
            continue
        mic = Mic()
        try:
            listen(clf, verifier, feats, vad, mic, playback)
        except Updated:
            log("wake.py foi atualizado: reiniciando com o código novo")
            mic.close()
            sys.exit(75)  # Restart=on-failure brings it back
        except EOFError:
            log("microfone fechou; reabrindo")
            time.sleep(1)
        finally:
            mic.close()
            feats.reset()
            vad.reset()


if __name__ == "__main__":
    main()
