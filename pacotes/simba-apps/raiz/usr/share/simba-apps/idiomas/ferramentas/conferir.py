#!/usr/bin/env python3
"""conferir.py — acha textos marcados para tradução que também aparecem SEM marca no mesmo
arquivo (comparações, chaves de dict…). Ex.: status = _t("Desativado") … if status == "Desativado":
em inglês a comparação falharia. Cada achado precisa de revisão.

    conferir.py ARQUIVOS...
"""
import re, sys
MARCA = re.compile(r'(?:I18n\.[tf]|_t)\(\s*"((?:\\.|[^"\\\n])*)"')
for p in sys.argv[1:]:
    try: src = open(p, encoding="utf-8").read()
    except (OSError, UnicodeDecodeError): continue
    marcados = set(m.group(1) for m in MARCA.finditer(src))
    for i, linha in enumerate(src.splitlines(), 1):
        sem = MARCA.sub("", linha)
        for m in re.finditer(r'"((?:\\.|[^"\\\n])*)"', sem):
            if m.group(1) in marcados and m.group(1).strip():
                print(f"{p}:{i}\t\"{m.group(1)}\"\t{linha.strip()[:150]}")
