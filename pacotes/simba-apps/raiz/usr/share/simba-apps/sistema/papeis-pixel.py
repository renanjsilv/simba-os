#!/usr/bin/env python3
"""Papéis de parede em pixel art do Simba OS (o único gato é o retrato da marca, em pixel-retrato).

Desenha em 640x360 (paletas curtas, pontilhado ordenado nos degradês) e amplia
6x sem suavizar → 3840x2160. Só Python + ImageMagick.
Uso: papeis-pixel.py <saída> [nome ...]
"""
import math, os, random, subprocess, sys

W, H, ESCALA = 640, 360, 6
OUT = sys.argv[1]
SO = set(sys.argv[2:])
BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class Tela:
    def __init__(self, cor="#000000"):
        c = rgb(cor)
        self.p = [list(c) for _ in range(W * H)]

    def get(self, x, y):
        return self.p[y * W + x]

    def px(self, x, y, c):
        if 0 <= x < W and 0 <= y < H:
            self.p[y * W + x] = list(c if isinstance(c, tuple) else rgb(c))

    def mistura(self, x, y, c, prob):
        """Pinta com probabilidade `prob` pelo padrão de Bayer (pontilhado estável)."""
        if 0 <= x < W and 0 <= y < H and prob * 16 > BAYER[y % 4][x % 4] + 0.5:
            self.px(x, y, c)

    def rect(self, x, y, w, h, c):
        c = rgb(c)
        for j in range(max(0, y), min(H, y + h)):
            for i in range(max(0, x), min(W, x + w)):
                self.p[j * W + i] = list(c)

    def degrade(self, y0, y1, cores):
        cs = [rgb(c) for c in cores]
        n = len(cs) - 1
        for y in range(max(0, y0), min(H, y1)):
            t = (y - y0) / max(1, y1 - y0 - 1) * n
            i = min(int(t), n - 1)
            f = t - i
            for x in range(W):
                self.p[y * W + x] = list(cs[i + 1] if f * 16 > BAYER[y % 4][x % 4] + 0.5 else cs[i])

    def disco(self, cx, cy, r, c):
        for y in range(int(cy - r - 1), int(cy + r + 2)):
            for x in range(int(cx - r - 1), int(cx + r + 2)):
                if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                    self.px(x, y, c)

    def halo(self, cx, cy, r0, r1, c, forca=0.8):
        for y in range(int(cy - r1), int(cy + r1) + 1):
            for x in range(int(cx - r1), int(cx + r1) + 1):
                d = math.hypot(x - cx, y - cy)
                if r0 < d < r1:
                    self.mistura(x, y, c, forca * (1 - (d - r0) / (r1 - r0)) ** 1.6)

    def nevoa(self, y0, y1, c, forca=0.7, subindo=True):
        """Faixa de névoa: mais densa embaixo (subindo=True) ou em cima."""
        for y in range(max(0, y0), min(H, y1)):
            t = (y - y0) / max(1, y1 - y0)
            p = forca * (math.sin(math.pi * t) if subindo is None else (t if subindo else 1 - t))
            for x in range(W):
                self.mistura(x, y, c, p)

    def salvar(self, nome):
        caminho = os.path.join(OUT, nome + ".png")
        dados = bytearray()
        for c in self.p:
            dados += bytes(c)
        cab = f"P6 {W} {H} 255\n".encode()
        subprocess.run(["magick", "ppm:-", "-filter", "point", "-resize", f"{ESCALA * 100}%",
                        "-strip", "-define", "png:compression-level=9", caminho],
                       input=cab + bytes(dados), check=True)
        print(caminho)


def quer(nome):
    return not SO or nome in SO


def cume(seed, base, amp, n=4, suave=1.0):
    """Altura de uma serra para cada x (soma de senoides com fase aleatória)."""
    r = random.Random(seed)
    ondas = [(r.uniform(0.004, 0.012) * (k + 1) ** 1.25 / suave, r.uniform(0, 6.28), amp / (k + 1) ** 1.1) for k in range(n)]
    return [int(base - sum(a * math.sin(f * x + fa) for f, fa, a in ondas)) for x in range(W)]


def serra(t, alturas, cor, borda=None, ate=H):
    for x, h in enumerate(alturas):
        for y in range(max(0, h), ate):
            t.px(x, y, cor)
        if borda:
            t.px(x, h, borda)


def estrelas(t, seed, n, y_max, cores=("#5a5f68", "#8a8f98", "#c8ccd2")):
    r = random.Random(seed)
    for _ in range(n):
        x, y = r.randrange(W), r.randrange(int(y_max))
        c = r.choices(cores, (6, 3, 1))[0]
        t.px(x, y, c)
        if c == cores[-1] and r.random() < 0.35:
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                t.mistura(x + dx, y + dy, cores[0], 0.9)


# ───────────────────────────────────────────── o gato (de costas, sentado)
def gato(t, cx, base, s, corpo, sombra, luz, listra, lado=1, cauda=1):
    """Gato cinza de costas. `lado` = de onde vem a luz (1 direita, -1 esquerda)."""
    def dentro(x, y):
        def el(ex, ey, rx, ry):
            return ((x - ex) / rx) ** 2 + ((y - ey) / ry) ** 2 <= 1
        if y > 0:
            return False
        # ombros estreitos, quadris largos, cabeça redonda e larga
        if el(0, -10.2 * s, 5.4 * s, 6.6 * s) or el(0, -4.6 * s, 8.4 * s, 5.4 * s) or el(0, -20.4 * s, 6.5 * s, 5.0 * s):
            return True
        for sx in (-1, 1):                    # orelhas largas, inclinadas para fora
            ax, ay = sx * 6.2 * s, -19.6 * s
            bx, by = sx * 0.9 * s, -24.6 * s
            px_, py_ = sx * 5.3 * s, -28.6 * s
            d = (by - py_) * (ax - px_) + (px_ - bx) * (ay - py_)
            if d:
                a = ((by - py_) * (x - px_) + (px_ - bx) * (y - py_)) / d
                b = ((py_ - ay) * (x - px_) + (ax - px_) * (y - py_)) / d
                if a >= 0 and b >= 0 and a + b <= 1:
                    return True
        return False

    pts = set()
    for y in range(int(-31 * s), 1):
        for x in range(int(-10 * s), int(10 * s) + 1):
            if dentro(x, y):
                pts.add((x, y))
    # cauda enrolada no chão
    for k in range(60):
        u = k / 59
        x = cauda * ((6.5 + 9 * u) * s)
        y = -(1.2 + 6 * u ** 2.2) * s
        r = (1.5 - 0.4 * u) * s
        for yy in range(int(y - r) - 1, int(y + r) + 2):
            for xx in range(int(x - r) - 1, int(x + r) + 2):
                if (xx - x) ** 2 + (yy - y) ** 2 <= r * r and yy <= 0:
                    pts.add((xx, yy))
    passo = max(3, round(3.4 * s))
    for (x, y) in pts:
        c = corpo
        if (x, y + 1) not in pts and y > -2 * s:
            c = sombra
        # listras finas no dorso, curvas, só no meio das costas
        curva = y + (x * x) / (16 * s)
        if -15 * s < curva < -8 * s and abs(x) < 4.5 * s and (round(curva) % passo == 0):
            c = listra
        # duas listrinhas na nuca
        if -24.5 * s < y < -22 * s and round(abs(x)) == round(1.6 * s):
            c = listra
        if (x + lado, y) not in pts or ((x, y - 1) not in pts and x * lado >= -s):
            c = luz
        elif (x - lado, y) not in pts:
            c = sombra
        t.px(int(cx + x), int(base + y), c)


# ───────────────────────────────────────────── 1. cidade à noite (telhado)
if quer("pixel-cidade"):
    t = Tela()
    t.degrade(0, 300, ["#07080b", "#0a0c10", "#0e1116", "#13171d", "#1a1e25", "#22262e"])
    estrelas(t, 1, 140, 170)
    t.halo(472, 78, 24, 110, "#1c2028", 0.9)
    t.halo(472, 78, 24, 58, "#2a2f38", 0.8)
    t.disco(472, 78, 24, "#d6d6d1")
    for cx, cy, r in ((462, 70, 5), (480, 88, 4), (470, 92, 2.5), (486, 66, 3)):
        t.disco(cx, cy, r, "#bdbdb7")
    t.halo(472, 78, 21, 25, "#ecece8", 0.5)
    r = random.Random(4)
    # três planos de prédios
    for cor, jan, hmin, hmax, wmin, wmax, chance, base in (
            ("#171a20", "#1f232a", 50, 115, 10, 26, 0.05, 302),
            ("#101217", "#4d4a44", 70, 165, 14, 34, 0.045, 302),
            ("#0b0c10", "#8a8576", 40, 120, 18, 40, 0.035, 302)):
        x = -r.randrange(20)
        while x < W:
            w, h = r.randrange(wmin, wmax), r.randrange(hmin, hmax)
            topo = base - h
            t.rect(x, topo, w, h, cor)
            if r.random() < 0.3:
                t.rect(x + w // 2, topo - r.randrange(6, 18), 1, 20, cor)
            if r.random() < 0.25:
                t.rect(x + 2, topo - 3, w - 4, 3, cor)
            for wy in range(topo + 4, base - 4, 5):
                for wx in range(x + 2, x + w - 2, 4):
                    if r.random() < chance:
                        t.rect(wx, wy, 2, 2, jan)
            x += w + r.randrange(0, 4)
    t.nevoa(220, 300, "#1d2129", 0.55)
    # telhado em primeiro plano
    t.rect(0, 300, W, 60, "#060709")
    t.rect(0, 300, W, 2, "#23262d")
    t.rect(0, 302, W, 4, "#121418")
    for x in range(0, W, 16):
        t.rect(x, 302, 1, 4, "#0b0c0f")
    # caixa d'água
    t.rect(60, 210, 54, 54, "#08090c"); t.rect(56, 206, 62, 6, "#08090c")
    t.rect(60, 210, 2, 54, "#1b1e24")
    for i in range(5):
        t.rect(60, 218 + i * 10, 54, 1, "#0d0f12")
    for lx in (64, 84, 106):
        t.rect(lx, 264, 3, 36, "#08090c")
    t.rect(62, 280, 50, 2, "#08090c")
    t.rect(86, 190, 1, 16, "#08090c"); t.px(86, 189, "#7a3b3b")
    t.salvar("pixel-cidade")

# ───────────────────────────────────────────── 2. serras na névoa
if quer("pixel-montanhas"):
    t = Tela()
    t.degrade(0, 260, ["#0a0c10", "#0f1217", "#151a21", "#1d232c", "#27303b", "#323c48"])
    estrelas(t, 2, 110, 120)
    t.halo(176, 112, 12, 80, "#3b4552", 0.7)
    t.disco(176, 112, 12, "#cfd3d8")
    camadas = [(150, 26, "#2f3844", "#3c4653"), (182, 30, "#252c36", "#313a46"), (214, 26, "#1b2129", "#262d37"),
               (246, 22, "#13171d", "#1c2129"), (282, 16, "#0b0d11", "#151820")]
    for i, (base, amp, cor, borda) in enumerate(camadas):
        alt = cume(10 + i, base, amp, 5, 1 + i * 0.25)
        serra(t, alt, cor, borda)
        if i < len(camadas) - 1:
            t.nevoa(base - 26, base + 30, "#3a4452" if i < 2 else "#2a323d", 0.5 - i * 0.08, None)
    # pedra no primeiro plano
    for y in range(300, 341):
        for x in range(470, 610):
            if ((x - 540) / 72) ** 2 + ((y - 344) / 42) ** 2 <= 1:
                t.px(x, y, "#07080a")
    for x in range(476, 600):
        for y in range(296, 344):
            if ((x - 540) / 72) ** 2 + ((y - 344) / 42) ** 2 <= 1:
                t.px(x, y, "#1a1e25"); break
    t.rect(0, 340, W, 20, "#07080a")
    t.salvar("pixel-montanhas")

# ───────────────────────────────────────────── 3. chuva na janela
if quer("pixel-chuva"):
    t = Tela("#08080a")
    X0, Y0, X1, Y1 = 150, 26, 500, 286
    r = random.Random(3)
    for y in range(Y0, Y1):
        tt = (y - Y0) / (Y1 - Y0)
        cs = ["#0c0f14", "#11151b", "#171b22", "#1d222a"]
        i = min(int(tt * 3), 2); f = tt * 3 - i
        for x in range(X0, X1):
            t.px(x, y, cs[i + 1] if f * 16 > BAYER[y % 4][x % 4] + 0.5 else cs[i])
    # luzes da cidade desfocadas
    for _ in range(70):
        bx, by = r.randrange(X0, X1), r.randrange(Y0 + 90, Y1)
        rad = r.choice((2, 3, 4, 5, 6))
        cor = r.choice(("#2c3038", "#3a3e46", "#4f4b44", "#5f5a50", "#3a434f"))
        for y in range(by - rad, by + rad + 1):
            for x in range(bx - rad, bx + rad + 1):
                d2 = (x - bx) ** 2 + (y - by) ** 2
                if X0 <= x < X1 and Y0 <= y < Y1 and d2 <= rad * rad:
                    if d2 <= (rad - 1.2) ** 2:
                        t.px(x, y, cor)
                    else:
                        t.mistura(x, y, cor, 0.5)
    # chuva
    for _ in range(420):
        x, y, L = r.randrange(X0, X1), r.randrange(Y0, Y1), r.randrange(4, 12)
        cor = r.choice(("#2a2f37", "#363c45", "#4a515c"))
        for k in range(L):
            xx, yy = x - k // 3, y + k
            if X0 <= xx < X1 and Y0 <= yy < Y1:
                t.px(xx, yy, cor)
    # gotas no vidro
    for _ in range(60):
        x, y = r.randrange(X0 + 2, X1 - 2), r.randrange(Y0 + 2, Y1 - 2)
        t.px(x, y, "#6b727c"); t.px(x, y + 1, "#2e333a")
    # parede, moldura e parapeito
    for y in range(H):
        for x in range(W):
            if not (X0 <= x < X1 and Y0 <= y < Y1):
                d = min(abs(x - (X0 + X1) / 2) / 260, 1)
                t.p[y * W + x] = list(rgb("#0e0f12" if (1 - d) * 0.6 * 16 > BAYER[y % 4][x % 4] + 0.5 else "#08080a"))
    for (x, y, w, h) in ((X0 - 6, Y0 - 6, X1 - X0 + 12, 6), (X0 - 6, Y0, 6, Y1 - Y0), (X1, Y0, 6, Y1 - Y0),
                         ((X0 + X1) // 2 - 3, Y0, 6, Y1 - Y0), (X0, (Y0 + Y1) // 2 - 3, X1 - X0, 6)):
        t.rect(x, y, w, h, "#15171b")
    t.rect((X0 + X1) // 2 - 3, Y0, 1, Y1 - Y0, "#23262c")
    t.rect(X0 - 24, Y1, X1 - X0 + 48, 6, "#1b1d21")
    t.rect(X0 - 24, Y1, X1 - X0 + 48, 1, "#2e3137")
    t.rect(X0 - 20, Y1 + 6, X1 - X0 + 40, 3, "#0b0b0d")
    # caneca no parapeito
    t.rect(430, Y1 - 12, 10, 12, "#2a2c31"); t.rect(440, Y1 - 9, 3, 6, "#2a2c31"); t.rect(441, Y1 - 8, 1, 4, "#08080a")
    t.rect(430, Y1 - 12, 10, 1, "#4a4d54")
    t.salvar("pixel-chuva")

# ───────────────────────────────────────────── 4. floresta na névoa (claro)
if quer("pixel-floresta"):
    t = Tela()
    t.degrade(0, 230, ["#f1f1ee", "#e9e9e6", "#e0e0dc", "#d6d6d2"])
    t.halo(470, 70, 16, 120, "#f8f8f5", 0.7)
    t.disco(470, 70, 16, "#fbfbf9")
    r = random.Random(5)
    camadas = [(170, "#c9c9c4", 0.9), (205, "#b1b1ac", 1.1), (240, "#93938e", 1.35), (282, "#5d5d59", 1.7)]
    for i, (base, cor, esc) in enumerate(camadas):
        alt = cume(30 + i, base, 10 + i * 3, 3, 1.6)
        serra(t, alt, cor)
        x = -r.randrange(10)
        while x < W:
            h = int(r.randrange(18, 34) * esc)
            b = alt[min(max(x, 0), W - 1)] + 2
            for k in range(h):                 # pinheiro em degraus
                larg = int((k / h) * 7 * esc * (1 + 0.35 * ((h - k) % 6 == 0))) + 1
                t.rect(x - larg, b - h + k, larg * 2 + 1, 1, cor)
            t.rect(x, b - h - 2, 1, 3, cor)
            x += int(r.randrange(5, 12) * esc)
        if i < len(camadas) - 1:
            t.nevoa(base - 40, base + 16, "#e6e6e2", 0.7 - i * 0.12, None)
    t.rect(0, 318, W, 42, "#3d3d3a")
    for x in range(W):
        h = 318 - int(3 * math.sin(x * 0.03) + 2 * math.sin(x * 0.11))
        t.rect(x, h, 1, 318 - h + 1, "#3d3d3a")
        t.px(x, h, "#55554f")
    # tronco caído
    t.rect(70, 304, 110, 12, "#2a2a28"); t.rect(70, 304, 110, 1, "#4a4a46")
    t.disco(70, 310, 6, "#33332f"); t.disco(70, 310, 3, "#24241f")
    t.salvar("pixel-floresta")

# ───────────────────────────────────────────── 5. retrato em pixel (marca)
if quer("pixel-retrato"):
    t = Tela()
    t.degrade(0, H, ["#0c0c0d", "#0a0a0b", "#080809", "#060607"])
    t.halo(430, 170, 10, 260, "#141416", 0.9)
    arte = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "marca-pixel", "retrato.txt")
    linhas = [l.rstrip("\n") for l in open(arte) if l.strip() and not l.startswith("#")]
    cores = {"K": "#0a0a0c", "D": "#18181b", "G": "#3c3c40", "L": "#727278", "W": "#c4c4ca"}
    s = 5
    ox = 430 - len(linhas[0]) * s // 2
    oy = 170 - len(linhas) * s // 2
    for j, l in enumerate(linhas):
        for i, ch in enumerate(l):
            if ch in cores:
                c = cores[ch]
                t.rect(ox + i * s, oy + j * s, s, s, c)
                if ch == "G":
                    t.rect(ox + i * s, oy + j * s, s, 1, "#48484e")
    # linhas de varredura sutis
    for y in range(0, H, 3):
        for x in range(W):
            t.mistura(x, y, "#050505", 0.25)
    t.salvar("pixel-retrato")
