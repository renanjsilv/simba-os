#!/usr/bin/env python3
"""extrair.py — todas as frases marcadas para tradução nos componentes próprios do Simba OS.

    extrair.py                 lista as frases (uma por linha, em JSON)
    extrair.py --faltando en   frases sem tradução em en.json (+ as do catálogo que sobraram)
    extrair.py --novo es       esqueleto de um idioma novo: {"frase": ""} (traduza os valores)
    extrair.py --onde "Frase"  em que arquivos a frase aparece

Onde procura: ver RAIZES. Marcas reconhecidas: I18n.t("…") / I18n.f("…") (QML),
t("…") (Python com simba_i18n), simba-t "…" (bash) e o índice de busca das Configurações.
"""
import ast
import json
import os
import re
import sys

HOME = os.path.expanduser("~")
PASTA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # idiomas/ (catálogos)
# Fonte: o repositório simba-os (SIMBA_REPO ou ~/simba-os); sem ele, o sistema instalado.
_REPO = os.environ.get("SIMBA_REPO", os.path.join(HOME, "simba-os"))
_P = os.path.join(_REPO, "pacotes")
if os.path.isdir(_P):
    _A, _D = os.path.join(_P, "simba-apps", "raiz"), os.path.join(_P, "simba-draco", "raiz")
else:
    _A = _D = "/"
RAIZES = [
    f"{_A}/etc/xdg/quickshell/configuracoes", f"{_A}/etc/xdg/quickshell/botoes-janela",
    f"{_A}/usr/share/simba-apps", f"{_A}/usr/bin",
    f"{_D}/etc/xdg/quickshell/draco", f"{_D}/etc/xdg/quickshell/draco-config",
    f"{_D}/usr/share/draco/lib", f"{_D}/usr/bin/draco",
]
EXTS = (".qml", ".js", ".py", ".sh", "")
STR = r'"((?:\\.|[^"\\\n])*)"'
PADROES = [
    re.compile(r"I18n\.[tf]\(\s*" + STR),
    re.compile(r"(?<![\w.])_?[tn]\(\s*" + STR),        # Python: t("…") / _t("…") / _n("…")
    re.compile(r"\bsimba-t\s+" + STR),
]
BUSCA = re.compile(r'^\s*\[\s*"[^"]*",\s*"[^"]*",\s*' + STR + r",\s*" + STR + r",\s*" + STR + r"\s*\]", re.M)


def desescapar(s):
    try:
        return json.loads('"' + s + '"')
    except ValueError:
        return s


def arquivos():
    for raiz in RAIZES:
        if os.path.isfile(raiz):
            yield raiz; continue
        for d, subs, fs in os.walk(raiz):
            subs[:] = [x for x in subs if not x.startswith((".", "__")) and x not in ("venv", "build", "node_modules")]
            for f in fs:
                if ".bak" in f or not f.endswith(EXTS):
                    continue
                p = os.path.join(d, f)
                if f.endswith(EXTS[:-1]) or (os.access(p, os.X_OK) and os.path.getsize(p) < 300_000):
                    yield p


def frases():
    achadas = {}
    for p in arquivos():
        try:
            src = open(p, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        if p.endswith(".py") or src.startswith(("#!/usr/bin/env python", "#!/usr/bin/python")):
            if "simba_i18n" not in src:
                continue
            # pela árvore sintática: pega o texto inteiro mesmo quando escrito em pedaços
            try:
                arv = ast.parse(src)
            except SyntaxError:
                continue
            for no in ast.walk(arv):
                if isinstance(no, ast.Call) and getattr(no.func, "id", "") in ("t", "_t", "n", "_n") and no.args \
                        and isinstance(no.args[0], ast.Constant) and isinstance(no.args[0].value, str):
                    achadas.setdefault(no.args[0].value.strip(), set()).add(p)
            continue
        elif p.endswith((".qml", ".js")):
            pads = PADROES[:1]
        else:
            pads = PADROES[2:]
        for pad in pads:
            for m in pad.finditer(src):
                achadas.setdefault(desescapar(m.group(1)).strip(), set()).add(p)
        if p.endswith("Busca.js"):
            for m in BUSCA.finditer(src):
                for g in m.groups():
                    if g.strip():
                        achadas.setdefault(desescapar(g).strip(), set()).add(p)
    achadas.pop("", None)
    return achadas


def main():
    a = sys.argv[1:]
    fr = frases()
    if not a:
        for k in sorted(fr):
            print(json.dumps(k, ensure_ascii=False))
        print(f"# {len(fr)} frases", file=sys.stderr)
    elif a[0] == "--faltando":
        try:
            cat = json.load(open(os.path.join(PASTA, a[1] + ".json"), encoding="utf-8"))
        except OSError:
            cat = {}
        try:
            fixas = {json.loads(l) for l in open(os.path.join(PASTA, "nao-traduzir.txt"), encoding="utf-8")
                     if l.strip() and not l.startswith("#")}
        except OSError:
            fixas = set()
        falta = sorted(k for k in fr if k not in cat and k not in fixas)
        sobra = sorted(k for k in cat if k not in fr)
        for k in falta:
            print(json.dumps(k, ensure_ascii=False))
        print(f"# {len(falta)} sem tradução em {a[1]}.json · {len(sobra)} no catálogo sem uso", file=sys.stderr)
    elif a[0] == "--novo":
        print(json.dumps({k: "" for k in sorted(fr)}, ensure_ascii=False, indent=1))
    elif a[0] == "--onde":
        for p in sorted(fr.get(a[1], ())):
            print(p)


if __name__ == "__main__":
    main()
