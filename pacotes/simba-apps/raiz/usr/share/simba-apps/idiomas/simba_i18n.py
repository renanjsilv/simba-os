"""Tradução dos componentes próprios do Simba OS (ver LEIA-ME.md).

    import sys, os; sys.path.insert(0, os.path.expanduser("/usr/share/simba-apps/idiomas"))
    from simba_i18n import t
    t("Texto em português")            → no idioma da sessão (ou o próprio texto)
    t("%1 de %2", a, b)                → com argumentos
"""
import json
import os
import re

PASTA = os.path.dirname(os.path.abspath(__file__))


def idioma():
    l = (os.environ.get("SIMBA_IDIOMA") or os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES")
         or os.environ.get("LANG") or "pt_BR")
    l = l.split(".")[0].split("@")[0]
    return "en" if l in ("C", "POSIX") else l


def _carregar():
    l = idioma()
    if not l or l.startswith("pt"):
        return {}
    mapa = {}
    for nome in (l.split("_")[0], l if "_" in l else None):
        if not nome:
            continue
        try:
            with open(os.path.join(PASTA, nome + ".json"), encoding="utf-8") as f:
                mapa.update(json.load(f))
        except (OSError, ValueError):
            pass
    return mapa


_MAPA = _carregar()
# separador decimal do idioma da sessão: f"{x:.1f}".replace(".", DECIMAL)
DECIMAL = "," if idioma().startswith("pt") or not idioma() else "."
_PONTAS = re.compile(r"^(\s*)(.*?)(\s*)$", re.S)


def t(s, *args):
    s = "" if s is None else str(s)
    if _MAPA and s:
        v = _MAPA.get(s)
        if v is None:
            a, meio, b = _PONTAS.match(s).groups()
            v = a + _MAPA[meio] + b if meio in _MAPA else s
        s = v
    for k, a in enumerate(args, 1):
        s = s.replace(f"%{k}", str(a))
    return s


def n(s):
    """Marca a frase para o catálogo sem traduzir aqui (chave interna; traduza ao exibir com t)."""
    return s
