"""Temas de ícones: catálogo, variantes (cor + claro/escuro) e resolução de ícones.

Usado por bin/icones (Configurações › Personalização › Ícones), bin/iniciar
(menu Iniciar) e pela barra de tarefas (lista de pastas via `icones cadeia`).
"""
import colorsys
import json
import os
import subprocess
from pathlib import Path

HOME = Path.home()
PREFS = HOME / ".config/configuracoes/preferencias.json"
SIMBA = HOME / ".local/state/simba/current/theme"
BASES = [HOME / ".local/share/icons", HOME / ".icons"] + \
    [Path(d) / "icons" for d in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":") if d]

# Catálogo: família → como montar o nome da pasta do tema.
#   cores: nomes aceitos (o 1º é o padrão, sem sufixo); escuro/claro: sufixos.
CATALOGO = [
    {"id": "fluent", "nome": "Fluent", "desc": "O visual do Windows 11", "pacote": "fluent-icon-theme-git", "fonte": "aur",
     "base": "Fluent", "cores": ["standard", "green", "grey", "orange", "pink", "purple", "red", "yellow", "teal"],
     "escuro": "-dark", "claro": "-light"},
    {"id": "tela", "nome": "Tela Circle", "desc": "Ícones redondos, 14 cores", "pacote": "tela-circle-icon-theme-all", "fonte": "oficial",
     "base": "Tela-circle", "cores": ["standard", "black", "blue", "brown", "dracula", "green", "grey", "manjaro", "nord",
                                      "orange", "pink", "purple", "red", "ubuntu", "yellow"],
     "escuro": "-dark", "claro": "-light"},
    {"id": "papirus", "nome": "Papirus", "desc": "Plano e completo, cobre quase todo app", "pacote": "papirus-icon-theme", "fonte": "oficial",
     "base": "Papirus", "cores": [], "escuro": "-Dark", "claro": "-Light"},
    {"id": "colloid", "nome": "Colloid", "desc": "Suave e moderno, com cores", "pacote": "colloid-icon-theme", "fonte": "aur",
     "base": "Colloid", "cores": ["standard", "purple", "pink", "red", "orange", "yellow", "green", "teal", "grey"],
     "escuro": "-dark", "claro": "-light"},
    {"id": "whitesur", "nome": "WhiteSur", "desc": "No estilo do macOS", "pacote": "whitesur-icon-theme", "fonte": "aur",
     "base": "WhiteSur", "cores": [], "escuro": "-dark", "claro": "-light"},
    {"id": "qogir", "nome": "Qogir", "desc": "Plano, discreto", "pacote": "qogir-icon-theme", "fonte": "aur",
     "base": "Qogir", "cores": ["standard", "manjaro", "ubuntu"], "escuro": "-dark", "claro": "-light"},
    {"id": "yaru", "nome": "Yaru", "desc": "O padrão do Ubuntu (o que o Simba usa)", "pacote": "yaru-icon-theme", "fonte": "oficial",
     "base": "Yaru", "cores": ["standard", "blue", "magenta", "olive", "prussiangreen", "purple", "red", "sage", "wartybrown", "yellow"],
     "escuro": "-dark", "claro": ""},
    {"id": "breeze", "nome": "Breeze", "desc": "O padrão do KDE", "pacote": "breeze-icons", "fonte": "oficial",
     "base": "breeze", "cores": [], "escuro": "-dark", "claro": ""},
    {"id": "cosmic", "nome": "COSMIC", "desc": "O do System76 Pop!_OS", "pacote": "cosmic-icon-theme", "fonte": "oficial",
     "base": "Cosmic", "cores": [], "escuro": "", "claro": ""},
    {"id": "adwaita", "nome": "Adwaita", "desc": "O padrão do GNOME", "pacote": "adwaita-icon-theme", "fonte": "oficial",
     "base": "Adwaita", "cores": [], "escuro": "", "claro": ""},
]
POR_ID = {f["id"]: f for f in CATALOGO}

# Matiz (graus) de cada nome de cor, para casar com o destaque do tema do Simba.
MATIZ = {"red": 0, "orange": 28, "brown": 25, "wartybrown": 25, "yellow": 50, "olive": 65, "green": 120, "sage": 140,
         "teal": 175, "prussiangreen": 185, "blue": 215, "nord": 210, "ubuntu": 20, "manjaro": 150,
         "purple": 270, "dracula": 265, "magenta": 300, "pink": 330}
NEUTRAS = ["grey", "black", "standard"]


def existe(nome):
    return any((b / nome / "index.theme").exists() for b in BASES)


def instalados():
    out = set()
    for b in BASES:
        if b.is_dir():
            for d in b.iterdir():
                if (d / "index.theme").exists():
                    out.add(d.name)
    return out


def cadeia(tema):
    """O tema, os que ele herda (index.theme) e, no fim, Adwaita e hicolor."""
    ordem, fila = [], [tema] if tema else []
    while fila:
        n = fila.pop(0)
        if not n or n in ordem:
            continue
        ordem.append(n)
        for b in BASES:
            idx = b / n / "index.theme"
            if idx.exists():
                for l in idx.read_text(errors="replace").splitlines():
                    if l.startswith("Inherits="):
                        fila += [x.strip() for x in l[9:].split(",")]
                break
    for extra in ("Adwaita", "hicolor"):
        if extra not in ordem:
            ordem.append(extra)
    return ordem


def tema_atual():
    try:
        return subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "icon-theme"],
                              capture_output=True, text=True, timeout=2).stdout.strip().strip("'")
    except Exception:  # noqa: BLE001
        return ""


_DIRS = {}


def pastas(tema):
    """[(caminho, tamanho)] das pastas do tema (index.theme → Directories), maiores primeiro."""
    if tema in _DIRS:
        return _DIRS[tema]
    out = []
    for b in BASES:
        raiz = b / tema
        idx = raiz / "index.theme"
        if not idx.exists():
            continue
        secao, dirs, info = "", [], {}
        for l in idx.read_text(errors="replace").splitlines():
            l = l.strip()
            if l.startswith("["):
                secao = l[1:-1]
            elif "=" in l:
                k, v = l.split("=", 1)
                if secao == "Icon Theme" and k in ("Directories", "ScaledDirectories"):
                    dirs += [d for d in v.split(",") if d]
                elif secao:
                    info.setdefault(secao, {})[k] = v
        for d in dict.fromkeys(dirs):
            i = info.get(d, {})
            if "symbolic" in d or i.get("Context", "").lower() == "status":
                continue
            tipo = i.get("Type", "Threshold")
            tam = 10000 if tipo == "Scalable" else int(i.get("Size", "0") or 0) * int(i.get("Scale", "1") or 1)
            out.append((raiz / d, tam))
    out.sort(key=lambda x: -x[1])
    _DIRS[tema] = out
    return out


def resolver(nomes, tema=None):
    """nome do ícone → arquivo, no tema dado (padrão: o ativo) e nos que ele herda."""
    faltam, out = list(dict.fromkeys(nomes)), {}
    for t in cadeia(tema or tema_atual()):
        if not faltam:
            break
        ps = pastas(t)
        for n in list(faltam):
            for d, _ in ps:
                f = next((str(d / (n + e)) for e in (".svg", ".png") if (d / (n + e)).exists()), None)
                if f:
                    out[n] = f
                    faltam.remove(n)
                    break
    gen = {n: n.split("-")[0] + "-x-generic" for n in faltam if "-" in n}
    if gen and set(gen.values()) - set(nomes):
        resto = resolver(list(set(gen.values())), tema)
        for n, g in gen.items():
            if g in resto:
                out[n] = resto[g]
    return out


# ── tema do Simba: claro/escuro e cor de destaque ──────────────────────────
def _hex(c):
    c = c.strip().strip('"').lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)) if len(c) >= 6 else None


def simba_cores():
    import tomllib
    try:
        d = tomllib.loads((SIMBA / "colors.toml").read_text())
    except Exception:  # noqa: BLE001
        return {"escuro": True, "acento": None}
    fundo = _hex(str(d.get("background", "#000000")))
    lum = 0.2126 * fundo[0] + 0.7152 * fundo[1] + 0.0722 * fundo[2] if fundo else 0
    modo = str(d.get("mode", "")).lower()
    escuro = modo != "light" if modo else lum < 0.45
    if (SIMBA / "light.mode").exists():
        escuro = False
    return {"escuro": escuro, "acento": _hex(str(d.get("accent", d.get("color4", "")))) }


def cor_do_acento(familia, acento):
    """Nome de cor da família mais perto do destaque do tema (cinza se for neutro)."""
    cores = familia["cores"]
    if not cores:
        return None
    if not acento:
        return cores[0]
    h, l, s = colorsys.rgb_to_hls(*acento)
    if s < 0.22 or l < 0.12 or l > 0.92:
        return next((c for c in NEUTRAS if c in cores), cores[0])
    graus = h * 360
    cand = [c for c in cores if c in MATIZ and c not in ("manjaro", "ubuntu", "dracula", "nord")]
    if not cand:
        return cores[0]
    return min(cand, key=lambda c: min(abs(MATIZ[c] - graus), 360 - abs(MATIZ[c] - graus)))


def nome_variante(fam, cor, escuro):
    """Pasta do tema para a família/cor/modo, caindo para o que estiver instalado."""
    base = fam["base"]
    sufixo = fam["escuro"] if escuro else fam["claro"]
    tentativas = []
    if cor and cor != "standard" and fam["cores"]:
        tentativas += [f"{base}-{cor}{sufixo}", f"{base}-{cor}"]
    tentativas += [base + sufixo, base]
    # Yaru: a cor padrão é "Yaru"; o Breeze escuro é "breeze-dark"
    for t in tentativas:
        if existe(t):
            return t
    return None


# ── preferências ─────────────────────────────────────────────────────────────
def prefs():
    try:
        return json.loads(PREFS.read_text()).get("icones", {}) or {}
    except Exception:  # noqa: BLE001
        return {}


def escolher(p=None):
    """Tema final pelas preferências: {tema: id|"simba", cor: "auto"|nome, modo: "auto"|"claro"|"escuro"}."""
    p = prefs() if p is None else p
    fam_id = p.get("tema", "simba")
    oc = simba_cores()
    escuro = {"claro": False, "escuro": True}.get(p.get("modo", "auto"), oc["escuro"])
    if fam_id == "simba" or fam_id not in POR_ID:
        try:
            t = (SIMBA / "icons.theme").read_text().strip()
        except OSError:
            t = ""
        if t and existe(t):
            return t
        # icons.theme do Simba aponta para um tema que não está instalado (ex.: Yaru-gray):
        # usa o Yaru instalado mais próximo da cor do tema
        fam = POR_ID["yaru"]
        return nome_variante(fam, cor_do_acento(fam, oc["acento"]), escuro) or "Adwaita"
    fam = POR_ID[fam_id]
    cor = p.get("cor", "auto")
    if cor == "auto":
        cor = cor_do_acento(fam, oc["acento"])
    return nome_variante(fam, cor, escuro) or "Adwaita"
