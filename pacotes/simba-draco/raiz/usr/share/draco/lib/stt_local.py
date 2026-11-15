#!/usr/bin/env python3
"""Draco: transcription on this computer, one request at a time (no resident server).

  stt_local.py <wav 16 kHz mono s16> [modelo]    prints the text (one line)

Runs with the Draco venv python (~/.local/share/draco/venv). Model: the argument, else
MODELO_LOCAL in the settings, else "parakeet".
"parakeet" (default): NVIDIA Parakeet TDT 0.6B v3 int8 (onnx-asr). Asks the resident server
(lib/stt_server.py, draco-stt.service) first; without it, loads the model here (~5 s).
If its files are missing (draco preparar not done), falls back to Whisper base.
"tiny"/"base"/"small": faster-whisper int8, loaded on every call (the old local path). Measured on an i5-8250U, 4-6 s requests in
Portuguese: tiny 0.4 s (26% of words wrong), base 0.8 s (14%), small 2.7 s (9%), plus
~1 s to load; the old path (voxtype, whisper.cpp small) took ~11 s. Whisper large-v3-turbo
took 16 s here: only worth it in the cloud (Groq, ~0.4 s, 7%).
The first use of a model downloads it into ~/.local/share/draco/models/whisper.
"""
import os
import sys
import wave

DATA = os.path.expanduser("~/.local/share/draco")
MODELS = ("parakeet", "tiny", "base", "small")
PARAKEET = os.path.join(DATA, "models", "parakeet")


def lingua():
    sys.path.insert(0, "/usr/share/simba-apps/idiomas")
    try:
        from simba_i18n import idioma
        l = idioma()
    except ImportError:
        l = ""
    return "pt" if not l or l.startswith("pt") else l.split("_")[0]


def chosen_model():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import config
    m = config.model_of(config.load(), "local")
    return m if m in MODELS else "parakeet"


def parakeet_ok():
    return os.path.exists(os.path.join(PARAKEET, "encoder-model.int8.onnx"))


def transcribe_parakeet(path):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import stt_server
    r = stt_server.request("arquivo " + os.path.abspath(path), 30.0)
    if r and r.get("ok"):
        return r["texto"]
    eng = stt_server.Engine()
    return stt_server.join(w for w, _ in eng.recognize(stt_server.read_wav(path)))


def transcribe(path, model):
    if model == "parakeet":
        if parakeet_ok():
            return transcribe_parakeet(path)
        model = "base"
    import numpy as np
    from faster_whisper import WhisperModel
    with wave.open(path) as w:
        audio = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768
        if w.getnchannels() > 1:
            audio = audio.reshape(-1, w.getnchannels()).mean(axis=1)
        rate = w.getframerate()
    if rate != 16000:  # pw-record/F10 is 16 kHz already; just in case
        n = int(len(audio) * 16000 / rate)
        audio = np.interp(np.linspace(0, len(audio), n, endpoint=False), np.arange(len(audio)), audio).astype(np.float32)
    # The audio goes in as an array: faster-whisper's own file reader (PyAV) breaks with
    # the PyAV in the venv ("unexpected keyword argument 'metadata_errors'").
    m = WhisperModel(model, device="cpu", compute_type="int8", cpu_threads=min(os.cpu_count() or 4, 4),
                     download_root=os.path.join(DATA, "models", "whisper"))
    segs, _ = m.transcribe(audio, language=lingua(), beam_size=1, temperature=0.0,
                           condition_on_previous_text=False, vad_filter=True,
                           vad_parameters={"min_silence_duration_ms": 500})
    # drop what Whisper makes up over silence
    return " ".join(s.text.strip() for s in segs if s.no_speech_prob < 0.6).strip()


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    model = sys.argv[2] if len(sys.argv) > 2 else chosen_model()
    print(transcribe(sys.argv[1], model))


if __name__ == "__main__":
    main()
