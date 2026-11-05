#!/usr/bin/env python3
"""Motor do Transcrever: transcreve UM vídeo com faster-whisper e emite eventos JSON (uma linha cada) no stdout.

Uso: worker.py <vídeo> [--rapido]

Eventos: preparando · modelo · audio · progresso{pos,total,texto?} · concluido{destino,segundos} · erro{mensagem}
Saída em <pasta do vídeo>/Transcrições/<nome>.txt; um .parcial interrompido é retomado de onde parou.
"""
import ctypes
import fcntl
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import sys as _sys, os as _os  # noqa: E401
_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))
from simba_i18n import t as _t  # noqa: E402  (traduções: /usr/share/simba-apps/idiomas)

MODEL = "large-v3-turbo"
PARAGRAFO_SEG = 60
SR = 16000
TS_RE = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\] ", re.M)


def emitir(ev: str, **dados) -> None:
    print(json.dumps({"ev": ev, **dados}, ensure_ascii=False), flush=True)


def ts(s: float) -> str:
    s = int(s)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def duracao(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        check=True, capture_output=True, text=True,
    ).stdout
    return float(out)


def carregar_audio(video: Path, inicio: float) -> np.ndarray:
    # ffmpeg do sistema no lugar do PyAV (o PyAV 19 quebra o decode_audio do faster-whisper)
    pcm = subprocess.run(
        ["ffmpeg", "-nostdin", "-v", "error", "-ss", str(inicio), "-i", str(video),
         "-vn", "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"],
        check=True, capture_output=True,
    ).stdout
    return np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0


def ponto_de_retomada(parcial: Path) -> float:
    """Descarta o último parágrafo (pode estar incompleto) e devolve o instante em que ele começava."""
    texto = parcial.read_text(encoding="utf-8", errors="replace")
    if "\0" in texto:  # escrita concorrente antiga: fica só a parte íntegra
        texto = texto[: texto.index("\0")]
    marcas = list(TS_RE.finditer(texto))
    if not marcas:
        parcial.write_text(texto, encoding="utf-8")
        return 0.0
    ultima = marcas[-1]
    parcial.write_text(texto[: ultima.start()], encoding="utf-8")
    h, m, s = map(int, ultima.groups())
    return h * 3600 + m * 60 + s


def outro_processo_usando(video: Path) -> bool:
    """Detecta a versão de terminal (sem trava) transcrevendo o mesmo vídeo."""
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) == os.getpid():
            continue
        try:
            cmd = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        args = [a.decode(errors="replace") for a in cmd]
        if any(a.endswith("transcrever.py") for a in args) and any(a.endswith(video.name) for a in args):
            return True
    return False


def travar(video: Path):
    pasta = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "transcrever"
    pasta.mkdir(exist_ok=True)
    trava = (pasta / hashlib.sha1(str(video).encode()).hexdigest()).open("w")
    try:
        fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return None
    return trava


def main() -> None:
    video = Path(sys.argv[1]).resolve()
    beam = 1 if "--rapido" in sys.argv[2:] else 5
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    ctypes.CDLL(None).prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG: morre junto com a interface

    saida_dir = video.parent / _t("Transcrições")
    destino = saida_dir / f"{video.stem}.txt"
    parcial = destino.with_suffix(".parcial")
    if destino.exists():
        emitir("concluido", destino=str(destino), segundos=0, existente=True)
        return

    trava = travar(video)
    if trava is None or outro_processo_usando(video):
        emitir("erro", mensagem=_t("Este vídeo já está sendo transcrito por outro processo."))
        sys.exit(1)

    emitir("preparando")
    total = duracao(video)
    saida_dir.mkdir(exist_ok=True)
    inicio = ponto_de_retomada(parcial) if parcial.exists() else 0.0
    if inicio == 0.0:
        parcial.write_text(
            f"Transcrição — {video.stem}\nOrigem: {video.parent.name}\nDuração: {ts(total)}\n\n",
            encoding="utf-8",
        )
    emitir("progresso", pos=inicio, total=total, retomado=inicio > 0)

    emitir("modelo")
    from faster_whisper import WhisperModel
    model = WhisperModel(MODEL, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)

    emitir("audio")
    audio = carregar_audio(video, inicio)
    segmentos, _ = model.transcribe(
        audio, language="pt", beam_size=beam, vad_filter=True, condition_on_previous_text=False,
    )
    emitir("transcrevendo", pos=inicio, total=total)

    t0 = time.time()
    with parcial.open("a", encoding="utf-8") as f:
        bloco, bloco_ini = [], None
        for seg in segmentos:
            ini, fim = seg.start + inicio, seg.end + inicio
            if bloco_ini is None:
                bloco_ini = ini
            bloco.append(seg.text.strip())
            texto = None
            if fim - bloco_ini >= PARAGRAFO_SEG:
                texto = f"[{ts(bloco_ini)}] {' '.join(bloco)}"
                f.write(texto + "\n\n")
                f.flush()
                bloco, bloco_ini = [], None
            emitir("progresso", pos=min(fim, total), total=total, texto=texto)
        if bloco:
            texto = f"[{ts(bloco_ini)}] {' '.join(bloco)}"
            f.write(texto + "\n")
            emitir("progresso", pos=total, total=total, texto=texto)

    parcial.rename(destino)
    emitir("concluido", destino=str(destino), segundos=time.time() - t0)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001 — qualquer falha vira mensagem na interface
        emitir("erro", mensagem=str(e))
        sys.exit(1)
