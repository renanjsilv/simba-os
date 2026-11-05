"""Index of installed apps (.desktop entries) with spoken aliases and window classes.

  apps.py resolve "<spoken name>"   JSON {id, name, launch, window} of the best match;
                                    exit 4 + candidates if ambiguous, 5 if nothing matches
  apps.py list [filter]             installed apps: name | id
"""
import os as _os
_PT = (_os.environ.get("LC_ALL") or _os.environ.get("LC_MESSAGES") or _os.environ.get("LANG") or "pt").startswith("pt")  # nome no idioma da sessão
import configparser
import difflib
import glob
import json
import os
import re
import sys
import unicodedata

DIRS = [os.path.expanduser("~/.local/share/applications"), "/usr/share/applications"]

# Spoken words -> desktop id (or a special entry below). Extend freely.
ALIASES = {
    "navegador": "brave-browser", "internet": "brave-browser", "browser": "brave-browser", "brave": "brave-browser",
    "arquivos": "org.gnome.Nautilus", "pastas": "org.gnome.Nautilus", "explorador de arquivos": "org.gnome.Nautilus",
    "gerenciador de arquivos": "org.gnome.Nautilus", "nautilus": "org.gnome.Nautilus",
    "terminal": "@terminal", "console": "@terminal",
    "editor": "@editor", "editor de texto": "@editor",
    "calculadora": "omacalc",
    "word": "libreoffice-writer", "documento": "libreoffice-writer", "writer": "libreoffice-writer",
    "planilha": "libreoffice-calc", "excel": "libreoffice-calc",
    "apresentacao": "libreoffice-impress", "powerpoint": "libreoffice-impress", "slides": "libreoffice-impress",
    "pdf": "org.gnome.Evince", "leitor de pdf": "org.gnome.Evince",
    "musica": "spotify", "gravador de tela": "com.obsproject.Studio", "obs": "com.obsproject.Studio",
    "monitor do sistema": "btop", "gerenciador de tarefas": "btop",
    "editor de video": "org.kde.kdenlive", "editor de imagem": "com.github.PintaProject.Pinta", "paint": "com.github.PintaProject.Pinta",
    "notas": "obsidian", "zap": "WhatsApp", "twitter": "X", "fotos": "Google Photos", "google fotos": "Google Photos",
    "mapas": "Google Maps", "maps": "Google Maps", "mensagens": "Google Messages", "sms": "Google Messages",
    "contatos": "Google Contacts", "maquina virtual": "virt-manager", "discos": "org.gnome.DiskUtility",
}

SPECIAL = {
    "@terminal": {"id": "@terminal", "name": "Terminal", "launch": "simba-launch-terminal",
                  "window": "^(foot|Alacritty|kitty|com\\.mitchellh\\.ghostty)$"},
    "@editor": {"id": "@editor", "name": "Editor", "launch": "simba-launch-editor", "window": ""},
}


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def window_regex(app_id, exec_line, wmclass):
    m = re.search(r"simba-launch-webapp\s+(https?://[^\s\"']+)", exec_line)
    if m:  # Simba web app in Brave: class is brave-<host><path>-Default
        host = re.sub(r"^www\.", "", re.match(r"https?://([^/]+)", m.group(1)).group(1))
        return "^brave-(www\\.)?" + re.escape(host)
    if wmclass and not wmclass.startswith("@@"):
        return "^" + re.escape(wmclass) + "$"
    binary = os.path.basename(exec_line.split()[0].strip('"')) if exec_line else ""
    names = {re.escape(app_id)}
    if binary and binary not in ("env", "xdg-terminal-exec", "steam", "simba-webapp-handler-zoom", "simba-webapp-handler-hey"):
        names.add(re.escape(binary))
    return "^(" + "|".join(sorted(names)) + ")$"


def load():
    apps = {}
    for d in DIRS:
        for path in sorted(glob.glob(os.path.join(d, "*.desktop"))):
            app_id = os.path.basename(path)[:-8]
            if app_id in apps:
                continue  # user entries override system ones
            cp = configparser.ConfigParser(interpolation=None, strict=False)
            cp.optionxform = str
            try:
                cp.read(path, encoding="utf-8")
                e = cp["Desktop Entry"]
            except (configparser.Error, KeyError, UnicodeDecodeError):
                continue
            if e.get("NoDisplay") == "true" or e.get("Hidden") == "true" or e.get("Type", "Application") != "Application":
                continue
            exec_line = e.get("Exec", "")
            apps[app_id] = {
                "id": app_id,
                "name": (e.get("Name[pt_BR]") if _PT else None) or e.get("Name", app_id),
                "names": {e.get("Name", ""), e.get("Name[pt_BR]", ""), e.get("GenericName[pt_BR]", ""), app_id},
                # uwsm-app takes desktop ids, but not ones with spaces ("Google Photos"):
                # those run their Exec line instead (minus %U-style field codes).
                "launch": (f"uwsm-app -- {app_id}.desktop" if " " not in app_id
                           else "uwsm-app -- " + re.sub(r"\s%[a-zA-Z]", "", exec_line)),
                "window": window_regex(app_id, exec_line, e.get("StartupWMClass", "")),
            }
    return apps


def public(app):
    return {k: app[k] for k in ("id", "name", "launch", "window")}


def resolve(query, apps):
    q = norm(query)
    q = re.sub(r"^(o|a|os|as|meu|minha|app|aplicativo|programa) ", "", q)
    target = ALIASES.get(q)
    if target in SPECIAL:
        return [SPECIAL[target]]
    if target and target in apps:
        return [public(apps[target])]
    scored = []
    for app in apps.values():
        names = [norm(n) for n in app["names"] if n]
        if q in names:
            return [public(app)]
        best = 0.0
        for n in names:
            if n.startswith(q) or q in n.split():
                best = max(best, 0.9)
            best = max(best, difflib.SequenceMatcher(None, q, n).ratio())
        if best >= 0.75:
            scored.append((best, app))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return []
    top = [a for s, a in scored if s >= scored[0][0] - 0.05]
    return [public(a) for a in top]


if __name__ == "__main__":
    apps = load()
    if sys.argv[1] == "resolve":
        found = resolve(" ".join(sys.argv[2:]), apps)
        if len(found) == 1:
            print(json.dumps(found[0], ensure_ascii=False))
            sys.exit(0)
        for a in found:
            print(f"{a['name']} | {a['id']}")
        sys.exit(4 if found else 5)
    if sys.argv[1] == "list":
        f = norm(" ".join(sys.argv[2:]))
        for a in sorted(apps.values(), key=lambda a: a["name"].lower()):
            if not f or f in norm(a["name"]) or f in norm(a["id"]):
                print(f"{a['name']} | {a['id']}")
