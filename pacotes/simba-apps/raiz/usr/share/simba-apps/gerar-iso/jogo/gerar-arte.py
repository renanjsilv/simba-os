#!/usr/bin/env python3
"""Gera arte.h com o retrato do Simba (a única arte de gato: marca-pixel/retrato.txt)."""
import os, sys
p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "marca-pixel", "retrato.txt")
l = [x.rstrip("\n") for x in open(p) if x.strip() and not x.startswith("#")]
while set(l[0]) <= {"."}: l.pop(0)
while set(l[-1]) <= {"."}: l.pop()
w = max(map(len, l)); l = [x.ljust(w, ".") for x in l]
print("/* gerado por gerar-arte.py a partir de marca-pixel/retrato.txt */")
print(f"#define RETRATO_W {w}\n#define RETRATO_H {len(l)}")
print("static const char *RETRATO[] = {\n" + ",\n".join(f'  "{x}"' for x in l) + "\n};")
