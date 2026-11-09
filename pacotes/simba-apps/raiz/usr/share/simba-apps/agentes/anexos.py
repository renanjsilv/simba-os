"""Imagens e arquivos anexados ao pedido (prints colados, arrastados ou escolhidos).

Prints colados viram PNG em ~/.cache/simba/agentes/anexos (apagados depois de
30 dias). Os agentes recebem os caminhos no texto do pedido: Claude Code, Codex,
Grok e os demais abrem a imagem com a própria ferramenta de leitura.
"""
from datetime import datetime
import os
from pathlib import Path
import time
import uuid

PASTA = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "simba/agentes/anexos"
VALIDADE = 30 * 24 * 3600
EXT_IMAGEM = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".svg", ".avif", ".heic"}


def eh_imagem(caminho):
    return Path(str(caminho)).suffix.lower() in EXT_IMAGEM


def novo_caminho(ext="png"):
    PASTA.mkdir(parents=True, exist_ok=True, mode=0o700)
    nome = f"print-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}.{ext}"
    return PASTA / nome


def salvar_textura(textura):
    """Grava uma Gdk.Texture (print da área de transferência) e devolve o caminho."""
    destino = novo_caminho("png")
    textura.save_to_png(str(destino))
    os.chmod(destino, 0o600)
    return destino


def miniatura(caminho, largura, altura):
    """Gdk.Texture reduzida (proporção mantida) para mostrar o anexo; None se não abrir."""
    import gi
    gi.require_version("Gdk", "4.0")
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import Gdk, GdkPixbuf, GLib
    try:
        pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(str(caminho), largura, altura, True)
        return Gdk.Texture.new_for_pixbuf(pb)
    except GLib.Error:
        return None


def limpar_antigos():
    try:
        limite = time.time() - VALIDADE
        for arq in PASTA.glob("*"):
            if arq.is_file() and arq.stat().st_mtime < limite:
                arq.unlink(missing_ok=True)
    except OSError:
        pass


def texto_para_agente(texto, caminhos):
    """Pedido com os anexos: o agente recebe os caminhos para abrir os arquivos."""
    if not caminhos:
        return texto
    imagens = [c for c in caminhos if eh_imagem(c)]
    outros = [c for c in caminhos if not eh_imagem(c)]
    linhas = []
    if imagens:
        linhas.append("Imagens anexadas pelo usuário (abra e analise cada uma antes de responder):")
        linhas += [f"- {c}" for c in imagens]
    if outros:
        linhas.append("Arquivos anexados pelo usuário:")
        linhas += [f"- {c}" for c in outros]
    anexo = "\n".join(linhas)
    return f"{texto}\n\n{anexo}" if texto else anexo
