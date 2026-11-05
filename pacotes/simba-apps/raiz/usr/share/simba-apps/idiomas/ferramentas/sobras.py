#!/usr/bin/env python3
"""sobras.py — literais que parecem português e NÃO estão marcados (para revisar à mão)."""
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from marcar import literais
PT = re.compile(r"[ãõçáéíóúâêôà]|\b(de|da|do|para|com|não|uma?|os?|as?|que|em|no|na|ao|se|por|mais|ou|sem|este|esta)\b", re.I)
for p in sys.argv[1:]:
    src = open(p, encoding="utf-8").read()
    for ini, fim, q, c in literais(src):
        antes = src[max(0, ini - 12):ini]
        if re.search(r"(I18n\.[tf]|_t|_n|simba-t)\(\s*$", antes) or "simba-t" in antes: continue
        if len(re.findall(r"[A-Za-zÀ-ÿ]{2,}", c)) < 2 or not PT.search(c): continue
        if re.search(r"[{};$=<>]|https?:|\\n|/\w+/|\.(sh|py|qml|json|conf|lua)\b", c): continue
        linha = src.count("\n", 0, ini) + 1
        l = src.splitlines()[linha - 1].strip()
        if l.startswith(("//", "#", "*")): continue
        print(f"{p}:{linha}\t{c[:90]}")
