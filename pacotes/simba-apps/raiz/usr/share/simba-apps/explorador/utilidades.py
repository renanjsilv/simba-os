"""Explorador de Arquivos: configuração, formatação, ícones e miniaturas."""
import hashlib
import json
import os
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gi
import sys as _sys, os as _os  # noqa: E401
_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))
from simba_i18n import t as _t, DECIMAL as _DEC  # noqa: E402  (traduções: /usr/share/simba-apps/idiomas)

gi.require_version("Gtk", "4.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, Gio, GLib  # noqa: E402

HOME = Path.home()
CONFIG = HOME / ".config/explorador/config.json"

# Atributos lidos de cada arquivo (DirectoryList / query_info)
ATRIBUTOS = ",".join([
    "standard::name", "standard::display-name", "standard::type", "standard::size", "standard::icon",
    # fast-content-type: só pelo nome (o content-type lê o começo do arquivo, o que numa
    # pasta de nuvem significa baixá-lo)
    "standard::symbolic-icon", "standard::fast-content-type", "standard::is-hidden", "standard::is-backup",
    "standard::is-symlink", "standard::target-uri", "standard::edit-name",
    "time::modified", "time::created", "time::access", "unix::mode", "owner::user",
    "access::can-read", "access::can-write", "access::can-execute", "access::can-trash", "access::can-delete",
    "access::can-rename", "thumbnail::path", "thumbnail::failed", "trash::orig-path", "trash::deletion-date",
])
# (sem filesystem::free/size: viraria um statfs por arquivo — numa nuvem, uma consulta à API cada)


def tipo(info):
    """Tipo MIME do item (content-type, se lido, senão o rápido pelo nome)."""
    return info.get_content_type() or info.get_attribute_string("standard::fast-content-type") or ""


# Pastas montadas de nuvem (rclone): sem miniaturas nem leitura de conteúdo nelas.
_nuvens = {"t": 0.0, "pontos": ()}


def pontos_nuvem():
    agora = time.monotonic()
    if agora - _nuvens["t"] > 3:
        pts = []
        try:
            for l in open("/proc/self/mounts"):
                c = l.split()
                if len(c) > 2 and c[2].startswith("fuse.rclone"):
                    pts.append(c[1].encode().decode("unicode_escape"))
        except OSError:
            pass
        _nuvens["t"], _nuvens["pontos"] = agora, tuple(pts)
    return _nuvens["pontos"]


def em_nuvem(caminho_):
    return bool(caminho_) and any(caminho_ == p or caminho_.startswith(p + "/") for p in pontos_nuvem())


def pasta_xdg(tipo, padrao):
    p = GLib.get_user_special_dir(tipo)
    return Path(p) if p else HOME / padrao


PASTAS = [  # (id, nome, ícone, caminho)
    ("desktop", _t("Área de Trabalho"), "user-desktop", pasta_xdg(GLib.UserDirectory.DIRECTORY_DESKTOP, _t("Desktop"))),
    ("downloads", _t("Downloads"), "folder-download", pasta_xdg(GLib.UserDirectory.DIRECTORY_DOWNLOAD, _t("Downloads"))),
    ("documentos", _t("Documentos"), "folder-documents", pasta_xdg(GLib.UserDirectory.DIRECTORY_DOCUMENTS, _t("Documents"))),
    ("imagens", _t("Imagens"), "folder-pictures", pasta_xdg(GLib.UserDirectory.DIRECTORY_PICTURES, _t("Pictures"))),
    ("musicas", _t("Músicas"), "folder-music", pasta_xdg(GLib.UserDirectory.DIRECTORY_MUSIC, _t("Music"))),
    ("videos", _t("Vídeos"), "folder-videos", pasta_xdg(GLib.UserDirectory.DIRECTORY_VIDEOS, _t("Videos"))),
]
ICONE_PASTA = {str(p): i for _, _, i, p in PASTAS}
ICONE_PASTA[str(HOME)] = "user-home"
NOME_PASTA = {str(p): n for _, n, _, p in PASTAS}
NOME_PASTA[str(HOME)] = os.environ.get("USER", "Pasta pessoal").capitalize()


# ── configuração ────────────────────────────────────────────────────────────
PADRAO = {
    "fixados": [str(p) for _, _, _, p in PASTAS],
    "favoritos": [],
    "visao": "grande",            # extragrande | grande | media | pequena | lista | detalhes | blocos
    "ordem": "nome", "desc": False,
    "ocultos": False, "extensoes": True,
    "painel": "",                 # "" | "detalhes" | "visualizar"
    "lateral": 240,
    "abrirEm": "inicio",          # inicio | pessoal
    "cliqueUnico": False,
    "visaoPorPasta": {},
}


def ler_config():
    try:
        c = json.loads(CONFIG.read_text())
    except (OSError, ValueError):
        c = {}
    out = dict(PADRAO)
    out.update(c)
    return out


_trava_cfg = threading.Lock()


def gravar_config(c):
    with _trava_cfg:
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG.with_suffix(".tmp")
        tmp.write_text(json.dumps(c, ensure_ascii=False, indent=1))
        tmp.replace(CONFIG)


# ── formatação ──────────────────────────────────────────────────────────────
def tamanho(n):
    if n is None:
        return ""
    for u in ("bytes", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            if u == "bytes":
                return f"{n} bytes" if n != 1 else _t("1 byte")
            return f"{n:.1f} {u}".replace(".", _DEC) if n < 100 else f"{n:.0f} {u}"
        n /= 1024
    return ""


def data(dt):
    """GLib.DateTime → '02/11/2026 14:30' (hoje: 'Hoje, 14:30')."""
    if dt is None:
        return ""
    local = dt.to_local()
    agora = GLib.DateTime.new_now_local()
    if local.get_year() == agora.get_year() and local.get_day_of_year() == agora.get_day_of_year():
        return _t("Hoje, ") + local.format("%H:%M")
    ontem = agora.add_days(-1)
    if local.get_year() == ontem.get_year() and local.get_day_of_year() == ontem.get_day_of_year():
        return _t("Ontem, ") + local.format("%H:%M")
    return local.format("%d/%m/%Y %H:%M")


def tipo_desc(info):
    if info.get_file_type() == Gio.FileType.DIRECTORY:
        return _t("Pasta de arquivos")
    ct = tipo(info)
    d = Gio.content_type_get_description(ct) if ct else ""
    return d[:1].upper() + d[1:] if d else _t("Arquivo")


def arquivo_de(info):
    return info.get_attribute_object("standard::file")


def eh_pasta(info):
    return info.get_file_type() in (Gio.FileType.DIRECTORY, Gio.FileType.MOUNTABLE)


def caminho(gfile):
    return gfile.get_path() if gfile else None


def info_de(gfile):
    """FileInfo com standard::file (como os itens do Gtk.DirectoryList)."""
    try:
        i = gfile.query_info(ATRIBUTOS, Gio.FileQueryInfoFlags.NONE, None)
    except GLib.Error:
        return None
    i.set_attribute_object("standard::file", gfile)
    return i


def nome_livre(pasta, nome):
    """'foto.png' → 'foto (2).png' se já existir (Windows: 'foto - Cópia')."""
    alvo = Path(pasta) / nome
    if not alvo.exists() and not alvo.is_symlink():
        return alvo
    base, ext = os.path.splitext(nome)
    if base.endswith(".tar"):
        base, ext = base[:-4], ".tar" + ext
    n = 2
    while True:
        alvo = Path(pasta) / f"{base} ({n}){ext}"
        if not alvo.exists() and not alvo.is_symlink():
            return alvo
        n += 1


def abrir_terminal(pasta):
    subprocess.Popen(["xdg-terminal-exec", f"--dir={pasta}"], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ── miniaturas (padrão freedesktop: ~/.cache/thumbnails) ────────────────────
CACHE_MINI = HOME / ".cache/thumbnails"
_falhas = set()
_executor = ThreadPoolExecutor(max_workers=3)
IMAGENS = ("image/",)
VIDEOS = ("video/",)


def miniaturavel(ct):
    return bool(ct) and (ct.startswith(IMAGENS) or ct.startswith(VIDEOS) or ct == "application/pdf") \
        and ct not in ("image/x-icon",)


def _arquivo_mini(uri, grande):
    pasta = CACHE_MINI / ("x-large" if grande else "large")
    return pasta / (hashlib.md5(uri.encode()).hexdigest() + ".png")


def copia_em_cache(caminho_, tamanho_):
    """Arquivo completo no cache do rclone mount (~/.cache/rclone/vfs/<remote>/...) ou None."""
    raiz = str(HOME / _t("Nuvem"))
    if not caminho_.startswith(raiz + "/"):
        return None
    rel = caminho_[len(raiz) + 1:]
    try:
        # o cache é esparso: só vale se os metadados disserem que o arquivo inteiro está lá
        meta = json.loads((HOME / ".cache/rclone/vfsMeta" / rel).read_text())
        rs = meta.get("Rs") or []
        inteiro = len(rs) == 1 and rs[0].get("Pos") == 0 and rs[0].get("Size") == meta.get("Size") == tamanho_
        return str(HOME / ".cache/rclone/vfs" / rel) if inteiro and tamanho_ > 0 else None
    except (OSError, ValueError, AttributeError):
        return None


def _gerar(gfile, ct, mtime, grande, local=None):
    uri = gfile.get_uri()
    destino = _arquivo_mini(uri, grande)
    try:
        if destino.exists():
            pb = GdkPixbuf.Pixbuf.new_from_file(str(destino))
            if pb.get_option("tEXt::Thumb::MTime") == str(mtime):
                return str(destino)
    except GLib.Error:
        pass
    origem = local or gfile.get_path()
    if not origem or uri in _falhas:
        return None
    lado = 512 if grande else 256
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(f".{os.getpid()}.{threading.get_ident()}.png")
    try:
        if ct.startswith(IMAGENS):
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(origem, lado, lado, True)
            pb = pb.apply_embedded_orientation() or pb
        else:
            if ct.startswith(VIDEOS):
                cmd = ["ffmpegthumbnailer", "-i", origem, "-o", str(tmp), "-s", str(lado), "-c", "png", "-t", "15%"]
            else:
                cmd = ["pdftoppm", "-png", "-singlefile", "-scale-to", str(lado), "-f", "1", "-l", "1", origem, str(tmp)[:-4]]
            subprocess.run(cmd, capture_output=True, timeout=25)
            if not tmp.exists():
                raise OSError(_t("sem imagem"))
            pb = GdkPixbuf.Pixbuf.new_from_file(str(tmp))
        pb.savev(str(tmp), "png", ["tEXt::Thumb::URI", "tEXt::Thumb::MTime"], [uri, str(mtime)])
        tmp.replace(destino)
        return str(destino)
    except Exception:  # noqa: BLE001
        _falhas.add(uri)
        try:
            tmp.unlink()
        except OSError:
            pass
        return None


def pedir_miniatura(info, grande, pronto):
    """Gera/acha a miniatura em segundo plano; pronto(caminho) no laço do GTK."""
    gfile = arquivo_de(info)
    ct = tipo(info)
    mtime = info.get_attribute_uint64("time::modified")
    if not gfile or not miniaturavel(ct):
        return
    local = None
    if em_nuvem(gfile.get_path()):
        # gerar baixaria o arquivo inteiro da nuvem: só se já estiver no cache do rclone
        local = copia_em_cache(gfile.get_path(), info.get_size())
        if not local:
            return
    if not grande:
        p = info.get_attribute_byte_string("thumbnail::path") if info.has_attribute("thumbnail::path") else None
        if p and os.path.exists(p):
            pronto(p)
            return

    def trabalho():
        r = _gerar(gfile, ct, mtime, grande, local)
        if r:
            GLib.idle_add(pronto, r)
    _executor.submit(trabalho)


def mostrar_uso(barra, legenda, usado, total, curto=False):
    """Barra + texto de espaço de um disco ou nuvem. Conta acima da cota (nuvem cujo
    plano diminuiu) não estoura a barra: fica cheia, vermelha e diz quanto passou."""
    frac = usado / total
    barra.set_value(min(1.0, max(0.0, frac)))
    barra.set_visible(True)
    if frac >= 0.9:
        barra.add_css_class("cheio")
    if usado > total:
        acima = tamanho(usado - total)
        legenda.set_label(_t("Cheio · %1 acima do limite de %2", acima, tamanho(total)) if curto else
                          _t("Armazenamento cheio · %1 usados de %2 (%3 acima do limite)", tamanho(usado), tamanho(total), acima))
        legenda.add_css_class("perigo")
        legenda.set_tooltip_text(_t("Libere espaço ou aumente o plano: enquanto estiver acima do limite, "
                                 "arquivos novos não são enviados para a nuvem."))
    else:
        legenda.set_label(_t("%1 livres de %2", tamanho(total - usado), tamanho(total)))


def mini_no_icone(info, img):
    """Ícones pequenos (lista, detalhes, recentes): troca o ícone do tipo pela miniatura
    de verdade quando ela fica pronta. Linhas são recicladas: um token por pedido."""
    token = object()
    img._token_mini = token
    if not miniaturavel(tipo(info)):
        return

    def pronto(path):
        if getattr(img, "_token_mini", None) is token:
            img.set_from_file(path)
        return False
    pedir_miniatura(info, False, pronto)


def tempo():
    return time.monotonic()


def coords(widget, alvo, x, y):
    """translate_coordinates em qualquer versão do PyGObject: (x, y) ou (ok, x, y)."""
    r = widget.translate_coordinates(alvo, x, y)
    if r is None:
        return x, y
    return (r[1], r[2]) if len(r) == 3 else (r[0], r[1])


def retangulo(x, y, w=1, h=1):
    from gi.repository import Gdk
    r = Gdk.Rectangle()
    r.x, r.y, r.width, r.height = int(x), int(y), int(w), int(h)
    return r
