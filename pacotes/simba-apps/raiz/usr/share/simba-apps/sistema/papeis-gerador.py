#!/usr/bin/env python3
"""Papéis de parede do Simba OS: gatos e minimalistas, 3840x2160.

Vetores em SVG (rsvg-convert) + pós-processamento em numpy (desfoque, granulação
fina para não formar degraus nos degradês). Uso: gerar.py <saída> [nome ...]
"""
import math, os, random, subprocess, sys, tempfile
import numpy as np
from PIL import Image, ImageFilter

W, H = 3840, 2160
OUT = sys.argv[1]
SO = set(sys.argv[2:])


# ───────────────────────────────────────────── utilidades
def svg_png(svg, w=W, h=H):
    with tempfile.NamedTemporaryFile("w", suffix=".svg", delete=False) as f:
        f.write(svg)
    png = f.name[:-4] + ".png"
    subprocess.run(["rsvg-convert", "-w", str(w), "-h", str(h), "-o", png, f.name], check=True)
    img = np.asarray(Image.open(png).convert("RGBA"), dtype=np.float32) / 255
    os.unlink(f.name); os.unlink(png)
    return img


def svg(body, defs=""):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<defs>{defs}</defs>{body}</svg>')


def hexrgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


def over(base, top):
    a = top[..., 3:4]
    return base * (1 - a) + top[..., :3] * a


def grain(img, amt=0.018, seed=0):
    rng = np.random.default_rng(seed)
    n = rng.normal(0, 1, img.shape[:2]).astype(np.float32)[..., None]
    return np.clip(img + n * amt, 0, 1)


def vinheta(img, k=0.35):
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((x - W / 2) / (W / 2)) ** 2 + ((y - H / 2) / (H / 2)) ** 2) / math.sqrt(2)
    return img * (1 - k * d[..., None] ** 2.2)


def degrade_v(c1, c2, curva=1.0):
    t = (np.linspace(0, 1, H, dtype=np.float32) ** curva)[:, None, None]
    return np.broadcast_to(hexrgb(c1) * (1 - t) + hexrgb(c2) * t, (H, W, 3)).copy()


def radial(c_dentro, c_fora, cx=0.5, cy=0.5, r=1.0, curva=1.0):
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt(((x - cx * W) / W) ** 2 + ((y - cy * H) / W) ** 2) / r
    t = np.clip(d, 0, 1)[..., None] ** curva
    return hexrgb(c_dentro) * (1 - t) + hexrgb(c_fora) * t


def manchas(base, blobs, blur=380, escala=8):
    """Manchas de cor desfocadas (estilo 'mesh gradient'). blobs: (x, y, raio, cor, alfa)."""
    w, h = W // escala, H // escala
    acc = Image.fromarray((base[::escala, ::escala] * 255).astype(np.uint8)).convert("RGB")
    camada = np.asarray(acc, np.float32) / 255
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    for bx, by, br, cor, a in blobs:
        m = np.exp(-(((x - bx * w) ** 2 + (y - by * h) ** 2) / (2 * (br * w) ** 2)))[..., None] * a
        camada = camada * (1 - m) + hexrgb(cor) * m
    im = Image.fromarray((np.clip(camada, 0, 1) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur / escala))
    im = im.resize((W, H), Image.BICUBIC)
    return np.asarray(im, np.float32) / 255


def salvar(nome, img, seed=0, amt=0.016):
    if SO and nome not in SO:
        return
    img = grain(img, amt, seed)
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(
        os.path.join(OUT, nome + ".jpg"), quality=90, subsampling=0, optimize=True, progressive=True)
    print(nome)


def quer(nome):
    return not SO or nome in SO


# (gatos ilustrados removidos em 2026-11-19: o único gato do Simba OS é o retrato em pixel art)

# ───────────────────────────────────────────── 8. Retrato do Simba (marca)
PIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "marca-pixel", "retrato-1152.png")
for nome, f1, f2, op in (("simba-retrato-escuro", "#202022", "#050505", 0.40),
                         ("simba-retrato-claro", "#f6f5f1", "#d9d8d3", 0.45)):
    if not quer(nome):
        continue
    img = radial(f1, f2, 0.62, 0.48, 1.0, 1.3)
    gato_img = Image.open(PIX).convert("RGBA")
    bb = gato_img.getbbox(); gato_img = gato_img.crop(bb)
    alvo = 1296
    gato_img = gato_img.resize((int(gato_img.width * alvo / gato_img.height), alvo), Image.NEAREST)
    cam = np.zeros((H, W, 4), np.float32)
    g = np.asarray(gato_img, np.float32) / 255
    x0, y0 = int(W * 0.63 - g.shape[1] / 2), int(H * 0.5 - g.shape[0] / 2)
    cam[y0:y0 + g.shape[0], x0:x0 + g.shape[1]] = g
    cam[..., 3] *= op
    img = over(img, cam)
    salvar(nome, img, 8)

# ───────────────────────────────────────────── minimalistas
if quer("aurora-escura"):
    img = np.zeros((H, W, 3), np.float32) + hexrgb("#050507")
    img = manchas(img, [(0.22, 0.30, 0.20, "#22488a", 0.95), (0.70, 0.25, 0.22, "#5a2a8a", 0.85),
                        (0.55, 0.75, 0.25, "#0f5a5c", 0.85), (0.90, 0.80, 0.15, "#1a2550", 0.6)], blur=420)
    salvar("aurora-escura", vinheta(img, 0.25), 9, 0.02)

if quer("nevoa-clara"):
    img = np.zeros((H, W, 3), np.float32) + hexrgb("#f4f3f0")
    img = manchas(img, [(0.18, 0.22, 0.24, "#cfdaef", 1.0), (0.82, 0.28, 0.24, "#ecd2e2", 1.0),
                        (0.50, 0.85, 0.28, "#d3eadf", 1.0), (0.55, 0.45, 0.12, "#f6efe2", 0.8)], blur=420)
    salvar("nevoa-clara", img, 10, 0.012)


def dunas(nome, cores, fundo, seed):
    if not quer(nome):
        return
    img = degrade_v(*fundo)
    r = random.Random(seed)
    camadas = []
    for i, cor in enumerate(cores):
        y0 = H * (0.42 + i * 0.12)
        a1, a2, f1, f2 = r.uniform(60, 120), r.uniform(20, 50), r.uniform(0, 6), r.uniform(0, 6)
        pts = " ".join(f"L{x} {y0 + a1 * math.sin(x / W * 2 * math.pi * 0.9 + f1) + a2 * math.sin(x / W * 2 * math.pi * 2.3 + f2):.1f}"
                       for x in range(0, W + 30, 30))
        camadas.append(f'<path d="M0 {H} {pts} L{W} {H} Z" fill="{cor}"/>')
    img = over(img, svg_png(svg("".join(camadas))))
    salvar(nome, img, seed)


dunas("dunas-escuras", ["#1b1c20", "#141518", "#0e0f11", "#08090a", "#030304"], ("#2a2c33", "#121317"), 11)
dunas("dunas-claras", ["#e3e1dc", "#d6d4ce", "#c8c5be", "#b9b6ae", "#a9a59d"], ("#f7f6f3", "#eceae5"), 12)

if quer("eclipse"):
    img = np.zeros((H, W, 3), np.float32) + hexrgb("#020203")
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy, r = W / 2, H / 2, 420
    d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    anel = np.exp(-np.abs(d - r) / 9) * 0.95 + np.exp(-np.clip(d - r, 0, None) / 160) * 0.35 * (d > r)
    ang = np.arctan2(y - cy, x - cx)
    anel *= 0.55 + 0.45 * np.cos(ang + 2.3) ** 2
    img = img + anel[..., None] * hexrgb("#e9ecf5")
    img[d < r - 6] = hexrgb("#020203")
    salvar("eclipse", img, 13, 0.018)


def topografia(nome, cor_linha, fundo, seed, a=0.55):
    if not quer(nome):
        return
    from skimage import measure
    rng = np.random.default_rng(seed)
    h, w = 216, 384
    campo = np.zeros((h, w), np.float32)
    for oit in range(5):
        f = 2 ** oit
        n = rng.normal(0, 1, (3 * f + 2, 5 * f + 2)).astype(np.float32)
        im = Image.fromarray(n).resize((w, h), Image.BICUBIC)
        campo += np.asarray(im) / (f ** 1.4)
    from skimage.filters import gaussian; campo = gaussian(campo, 2)
    paths = []
    sx, sy = W / (w - 1), H / (h - 1)
    niveis = np.linspace(campo.min(), campo.max(), 34)[1:-1]
    for k, nv in enumerate(niveis):
        for c in measure.find_contours(campo, nv):
            if len(c) < 8:
                continue
            pts = " L".join(f"{p[1] * sx:.1f} {p[0] * sy:.1f}" for p in c[::1])
            sw = 4.2 if k % 5 == 0 else 2.2
            paths.append(f'<path d="M{pts}" fill="none" stroke="{cor_linha}" stroke-width="{sw}" stroke-opacity="{a if k % 5 == 0 else a * 0.6}"/>')
    img = radial(*fundo, 0.5, 0.5, 1.1, 1.3)
    img = over(img, svg_png(svg("".join(paths))))
    salvar(nome, img, seed)


topografia("topografia-escura", "#ffffff", ("#15161a", "#060607"), 14, 0.22)
topografia("topografia-clara", "#2b2b2b", ("#f5f4f0", "#e2e0da"), 15, 0.28)

if quer("montanhas"):
    img = degrade_v("#c3cedb", "#eef1f4", 0.9)
    r = random.Random(16)
    camadas = []
    cores = ["#aab6c6", "#909fb2", "#76869c", "#5c6c84", "#43526a", "#2c384e"]
    for i, cor in enumerate(cores):
        y0 = H * (0.40 + i * 0.085)
        fs = [(r.uniform(0.6, 1.4), r.uniform(0, 6), r.uniform(50, 110) - i * 6) for _ in range(3)]
        pts = []
        for x in range(0, W + 41, 40):
            t = x / W
            y = y0 + sum(a * math.sin(t * math.pi * 2 * f * (k + 1) + ph) / (k + 1) for k, (f, ph, a) in enumerate(fs))
            y -= 140 * max(0, math.sin(t * math.pi * (1.2 + i * 0.35) + i * 1.7)) ** 3
            pts.append(f"L{x} {y:.1f}")
        camadas.append(f'<path d="M0 {H} {" ".join(pts)} L{W} {H} Z" fill="{cor}"/>')
        if i < len(cores) - 1:
            camadas.append(f'<rect width="{W}" height="{H}" fill="#e8edf2" fill-opacity="0.12"/>')
    img = over(img, svg_png(svg("".join(camadas))))
    salvar("montanhas", img, 16)

if quer("ondas"):
    img = radial("#131418", "#040405", 0.5, 0.4, 1.1, 1.2)
    linhas = []
    n = 70
    for i in range(n):
        t = i / (n - 1)
        y0 = H * (0.22 + 0.62 * t)
        amp = 260 * math.sin(t * math.pi) + 30
        pts = " ".join(f"L{x} {y0 + amp * math.sin(x / W * 2 * math.pi * 1.1 + t * 3.2) * math.exp(-((x - W * 0.55) / (W * 0.45)) ** 2):.1f}"
                       for x in range(-20, W + 40, 24))
        a = 0.14 + 0.62 * math.sin(t * math.pi) ** 2
        linhas.append(f'<path d="M-20 {y0} {pts}" fill="none" stroke="#dfe3ee" stroke-width="2.4" stroke-opacity="{a:.2f}"/>')
    img = over(img, svg_png(svg("".join(linhas))))
    salvar("ondas", img, 17)
