"""Ditado por voz no chat: grava com pw-record e transcreve como o Draco.

Usa o serviço de transcrição configurado no Draco (Groq/OpenAI em
~/.config/draco) e, sem ele ou se falhar, o Whisper local (voxtype). Só
fica disponível quando o pacote simba-draco está instalado.
"""
import array
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import uuid
import urllib.request

DRACO_LIB = Path("/usr/share/draco/lib")
WHISPER_LOCAL = "small"  # mesmo modelo de reserva do Draco
# Volume mínimo de fala. Medido no Draco: ambiente ≈ −35 dB, voz ≈ −20 dB. Sem
# nenhum trecho acima disto é silêncio, e o Whisper inventaria frases ("E aí").
LIMIAR_FALA_DB = -30.0


def pico_db(wav):
    """Maior volume RMS (dBFS) em janelas de 100 ms de um WAV s16 mono 16 kHz."""
    dados = Path(wav).read_bytes()[44:]
    amostras = array.array("h")
    amostras.frombytes(dados[: len(dados) // 2 * 2])
    if sys.byteorder == "big":
        amostras.byteswap()
    maior = 0.0
    for i in range(0, len(amostras), 1600):
        bloco = amostras[i:i + 1600]
        if bloco:
            maior = max(maior, math.sqrt(sum(x * x for x in bloco) / len(bloco)))
    return 20 * math.log10(maior / 32768) if maior > 0 else -120.0


def disponivel():
    return DRACO_LIB.joinpath("config.py").exists() and bool(shutil.which("pw-record"))


def _config_draco():
    if str(DRACO_LIB) not in sys.path:
        sys.path.insert(0, str(DRACO_LIB))
    import config as dcfg  # noqa: E402  (lib do Draco)
    return dcfg


class Gravador:
    def __init__(self):
        pasta = Path(os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()) / "simba-agentes"
        pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.wav = pasta / "ditado.wav"
        self.proc = None

    @property
    def gravando(self):
        return self.proc is not None and self.proc.poll() is None

    def iniciar(self):
        self.wav.unlink(missing_ok=True)
        self.proc = subprocess.Popen(
            ["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16", str(self.wav)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def parar(self):
        if not self.proc:
            return
        try:
            self.proc.send_signal(signal.SIGINT)
            self.proc.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            self.proc.kill()
        self.proc = None

    def cancelar(self):
        self.parar()
        self.wav.unlink(missing_ok=True)

    def transcrever(self):
        """Texto falado (bloqueante: chame numa thread). Levanta RuntimeError se falhar."""
        if not self.wav.exists() or self.wav.stat().st_size < 16000:  # < ~0,5 s de áudio
            raise RuntimeError("curto")
        audio = self.wav
        # mesmo filtro do Draco: corta o ronco grave (< 80 Hz) que abafa a voz
        filtrado = self.wav.with_name("ditado-hp.wav")
        if shutil.which("ffmpeg") and subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(self.wav), "-af", "highpass=f=80", str(filtrado)],
            capture_output=True, timeout=20,
        ).returncode == 0:
            audio = filtrado
        # medido depois do filtro: o ronco grave sozinho passa de −30 dB
        if pico_db(audio) < LIMIAR_FALA_DB:
            for f in (self.wav, filtrado):
                f.unlink(missing_ok=True)
            raise RuntimeError("vazio")
        try:
            dcfg = _config_draco()
            lingua = getattr(dcfg, "LING", "pt")
            servico = dcfg.stt()
        except Exception:  # noqa: BLE001
            lingua, servico = "pt", None
        texto = None
        if servico:
            try:
                texto = _nuvem(audio, *servico, lingua)
            except Exception:  # noqa: BLE001
                texto = None
        if texto is None and shutil.which("voxtype"):
            r = subprocess.run(["voxtype", "-q", "--model", WHISPER_LOCAL, "--language", lingua,
                                "transcribe", str(audio)], capture_output=True, text=True, timeout=180)
            linhas = [x for x in r.stdout.strip().splitlines() if x.strip()]
            texto = linhas[-1] if linhas else None
        for f in (self.wav, filtrado):
            f.unlink(missing_ok=True)
        if not texto or not texto.strip():
            raise RuntimeError("vazio")
        return _limpar(texto)


def _limpar(texto):
    try:
        from transcript import HALLUCINATIONS  # lib do Draco: frases inventadas no silêncio
        if HALLUCINATIONS.match(texto.strip()):
            raise RuntimeError("vazio")
    except ImportError:
        pass
    return texto.strip()


def _nuvem(wav, base, chave, modelo, lingua):
    """POST multipart em <base>/audio/transcriptions (formato OpenAI/Groq)."""
    limite = uuid.uuid4().hex
    campos = {"model": modelo, "language": lingua, "temperature": "0", "response_format": "json"}
    corpo = b""
    for k, v in campos.items():
        corpo += (f"--{limite}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n").encode()
    corpo += (f"--{limite}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"ditado.wav\"\r\n"
              "Content-Type: audio/wav\r\n\r\n").encode() + Path(wav).read_bytes() + f"\r\n--{limite}--\r\n".encode()
    req = urllib.request.Request(
        base.rstrip("/") + "/audio/transcriptions", data=corpo, method="POST",
        headers={"Authorization": f"Bearer {chave}", "Content-Type": f"multipart/form-data; boundary={limite}",
                 "User-Agent": "simba-agentes"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8")).get("text")
