#!/usr/bin/env python3
"""Gera fonte.h (glifos da Terminus em PSF2, só os caracteres usados pelo jogo).
  gerar-fonte.py ter-v16b.psf ter-v24b.psf ter-v32b.psf > fonte.h
Terminus Font © Dimitar Toshkov Zhekov — SIL Open Font License 1.1."""
import struct, sys
CHARS = [chr(c) for c in range(32, 127)] + list("áàâãéêíóôõúçÁÀÂÃÉÊÍÓÔÕÚÇ…·—–º°↑↓←→")

def ler(p):
    d = open(p, "rb").read()
    if d[:2] == b"\x36\x04":                     # PSF1: 8 px de largura, tabela em UCS-2
        modo, h = d[2], d[3]; n = 512 if modo & 1 else 256; cb = h; w = 8; hs = 4
        gl = d[hs:hs + n * cb]; mapa = {}; i = hs + n * cb; g = 0
        while g < n and i + 1 < len(d):
            u = d[i] | d[i + 1] << 8; i += 2
            if u == 0xFFFF: g += 1; continue
            if u == 0xFFFE:   # sequências: pula até o fim do glifo
                while d[i] | d[i + 1] << 8 != 0xFFFF: i += 2
                continue
            mapa.setdefault(chr(u), g)
        return w, h, cb, gl, mapa
    mag, ver, hs, flags, n, cb, h, w = struct.unpack("<8I", d[:32])
    assert mag == 0x864ab572
    glifos = d[hs:hs + n * cb]
    mapa = {}
    tab = d[hs + n * cb:]
    i = g = 0
    while g < n and i < len(tab):
        j = tab.index(b"\xff", i)
        seq = tab[i:j]
        for parte in seq.split(b"\xfe")[:1]:
            for ch in parte.decode("utf-8", "ignore"):
                mapa.setdefault(ch, g)
        i = j + 1; g += 1
    return w, h, cb, glifos, mapa

print("/* gerado por gerar-fonte.py — Terminus Font (SIL OFL 1.1) */")
print("static const unsigned int FONTE_CP[] = {" + ",".join(str(ord(c)) for c in CHARS) + "};")
print(f"#define FONTE_N {len(CHARS)}")
nomes = []
for p in sys.argv[1:]:
    w, h, cb, gl, mapa = ler(p)
    bpl = (w + 7) // 8
    nome = f"F{w}x{h}"; nomes.append((nome, w, h))
    dados = []
    for c in CHARS:
        g = mapa.get(c, mapa.get("?"))
        dados += list(gl[g * cb:(g + 1) * cb])
    print(f"static const unsigned char {nome}[] = {{" + ",".join(map(str, dados)) + "};")
print("typedef struct { const unsigned char *d; int w, h; } Fonte;")
print("static const Fonte FONTES[] = {" + ",".join(f"{{{n},{w},{h}}}" for n, w, h in nomes) + "};")
