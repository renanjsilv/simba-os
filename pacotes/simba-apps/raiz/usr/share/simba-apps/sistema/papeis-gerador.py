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


# ───────────────────────────────────────────── o gato (silhueta de costas, sentado)
def gato(cx, base_y, s, cor, cauda=1):
    """Gato sentado visto de costas; s = altura em px. Formas unidas na mesma cor."""
    u = s / 100.0
    def P(x, y):
        return f"{cx + x * u:.1f} {base_y - y * u:.1f}"
    corpo = (f"M{P(-26, 0)} C{P(-34, 18)} {P(-30, 44)} {P(-17, 58)} "
             f"C{P(-11, 66)} {P(11, 66)} {P(17, 58)} C{P(30, 44)} {P(34, 18)} {P(26, 0)} Z")
    cabeca = f'<ellipse cx="{cx}" cy="{base_y - 72 * u}" rx="{17 * u}" ry="{15.5 * u}"/>'
    orelhas = (f"M{P(-15, 76)} L{P(-14.5, 94)} L{P(-4, 84)} Z "
               f"M{P(15, 76)} L{P(14.5, 94)} L{P(4, 84)} Z")
    pescoco = f"M{P(-13, 62)} L{P(13, 62)} L{P(10, 72)} L{P(-10, 72)} Z"
    rabo = (f"M{P(22 * cauda, 2)} C{P(44 * cauda, 2)} {P(56 * cauda, 6)} {P(58 * cauda, 20)} "
            f"C{P(59 * cauda, 30)} {P(52 * cauda, 34)} {P(47 * cauda, 30)}")
    return (f'<g fill="{cor}"><path d="{corpo}"/>{cabeca}<path d="{orelhas}"/><path d="{pescoco}"/></g>'
            f'<path d="{rabo}" fill="none" stroke="{cor}" stroke-width="{7.5 * u}" stroke-linecap="round"/>')


def estrelas(n, seed, area=(0, 0, W, H * 0.62), cor="#ffffff"):
    r = random.Random(seed)
    out = []
    for _ in range(n):
        x = r.uniform(area[0], area[2]); y = r.uniform(area[1], area[3])
        rad = r.choice([1.6, 1.8, 2.2, 2.6, 3.4]); a = r.uniform(0.25, 0.85)
        out.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{rad}" fill="{cor}" fill-opacity="{a:.2f}"/>')
    return "".join(out)


# ───────────────────────────────────────────── 1. Lua (escuro)
if quer("simba-lua"):
    img = degrade_v("#05060b", "#161925", 1.3)
    mx, my, mr = W * 0.64, H * 0.50, 400
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt((x - mx) ** 2 + (y - my) ** 2)
    halo = np.exp(-((d - mr).clip(0)) / 520)[..., None] * 0.20
    img = img + halo * hexrgb("#c9d2ee")
    corpo = svg(
        estrelas(150, 7)
        + f'<circle cx="{mx}" cy="{my}" r="{mr}" fill="#eef0f5"/>'
        + f'<circle cx="{mx - 90}" cy="{my - 60}" r="48" fill="#dfe2ea"/>'
        + f'<circle cx="{mx + 110}" cy="{my + 70}" r="70" fill="#e4e7ee"/>'
        + f'<circle cx="{mx + 40}" cy="{my - 150}" r="26" fill="#e1e4ec"/>'
        + f'<path d="M0 {H - 300} L{W} {H - 300} L{W} {H} L0 {H} Z" fill="#030305"/>'
        + gato(W * 0.66, H - 298, 560, "#030305"))
    img = over(img, svg_png(corpo))
    salvar("simba-lua", vinheta(img, 0.3), 1)

# ───────────────────────────────────────────── 2. Pôr do sol (cor)
if quer("simba-por-do-sol"):
    img = degrade_v("#2b2147", "#f3a37a", 1.1)
    img = manchas(img, [(0.5, 0.62, 0.30, "#ffcf9c", 0.9), (0.15, 0.2, 0.3, "#3a2a5c", 0.6)], blur=300)
    sol = f'<circle cx="{W * 0.5}" cy="{H * 0.66}" r="300" fill="#ffe3c2" fill-opacity="0.95"/>'
    def colina(y0, amp, fase, cor):
        pts = " ".join(f"L{x} {y0 + amp * math.sin(x / W * 2.6 * math.pi + fase) + amp * 0.35 * math.sin(x / W * 7 * math.pi + fase * 2):.1f}"
                       for x in range(0, W + 40, 40))
        return f'<path d="M0 {H} {pts} L{W} {H} Z" fill="{cor}"/>'
    corpo = svg(sol + colina(H * 0.74, 60, 0.4, "#b5607a") + colina(H * 0.80, 70, 2.0, "#7d3f67")
                + colina(H * 0.88, 50, 4.1, "#4a2650")
                + gato(W * 0.30, H * 0.88 + 50 * math.sin(0.30 * 2.6 * math.pi + 4.1) + 17 * math.sin(0.3 * 7 * math.pi + 8.2) + 12, 330, "#2a1532"))
    img = over(img, svg_png(corpo))
    salvar("simba-por-do-sol", img, 2)

# ───────────────────────────────────────────── 3/4. Gato em traço contínuo
def gato_traco(cor, fundo1, fundo2, nome, seed):
    if not quer(nome):
        return
    img = radial(fundo1, fundo2, 0.6, 0.45, 1.1, 1.4)
    cx, by, s = W * 0.64, H * 0.78, 1150
    u = s / 100
    def P(x, y):
        return f"{cx + x * u:.1f} {by - y * u:.1f}"
    # um único traço: chão → costas → cabeça com orelhas → peito → patas → rabo
    d = (f"M{P(-62, 0)} L{P(-22, 0)} "
         f"C{P(-30, 14)} {P(-32, 40)} {P(-20, 55)} "
         f"C{P(-16, 60)} {P(-14, 63)} {P(-15, 67)} "
         f"C{P(-19, 74)} {P(-18, 81)} {P(-15, 85)} "
         f"L{P(-14, 95)} L{P(-6, 88)} "
         f"C{P(-2, 89.5)} {P(2, 89.5)} {P(6, 88)} "
         f"L{P(14, 95)} L{P(15, 85)} "
         f"C{P(18, 81)} {P(19, 74)} {P(15, 67)} "
         f"C{P(14, 63)} {P(16, 60)} {P(20, 55)} "
         f"C{P(32, 40)} {P(30, 14)} {P(22, 0)} "
         f"C{P(40, 0)} {P(52, 2)} {P(54, 12)} "
         f"C{P(55, 20)} {P(48, 24)} {P(44, 19)}")
    pata = f"M{P(-8, 0)} C{P(-8, 8)} {P(-6, 14)} {P(-4, 18)} M{P(8, 0)} C{P(8, 8)} {P(6, 14)} {P(4, 18)}"
    corpo = svg(f'<path d="{d}" fill="none" stroke="{cor}" stroke-width="13" stroke-linecap="round" stroke-linejoin="round"/>'
                f'<path d="{pata}" fill="none" stroke="{cor}" stroke-width="9" stroke-linecap="round" stroke-opacity="0.7"/>')
    img = over(img, svg_png(corpo))
    salvar(nome, img, seed, 0.014)


gato_traco("#1b1b1b", "#f7f6f2", "#e6e4de", "simba-traco-claro", 3)
gato_traco("#ececec", "#1a1a1c", "#050506", "simba-traco-escuro", 4)

# ───────────────────────────────────────────── 5. Espiando (escuro)
if quer("simba-espiando"):
    img = radial("#15161b", "#040405", 0.5, 1.0, 1.0, 1.2)
    cx, top = W * 0.5, H * 0.58
    r = 720
    cabeca = (f'<path d="M{cx - r} {H + 50} C{cx - r} {top + 60} {cx - r * 0.6} {top - 10} {cx} {top - 10} '
              f'C{cx + r * 0.6} {top - 10} {cx + r} {top + 60} {cx + r} {H + 50} Z" fill="#000"/>'
              f'<path d="M{cx - r * 0.93} {top + 160} L{cx - r * 0.80} {top - 330} L{cx - r * 0.30} {top + 20} Z" fill="#000"/>'
              f'<path d="M{cx + r * 0.93} {top + 160} L{cx + r * 0.80} {top - 330} L{cx + r * 0.30} {top + 20} Z" fill="#000"/>')
    olho = lambda ox: (f'<ellipse cx="{cx + ox}" cy="{top + 330}" rx="92" ry="70" fill="url(#iris)"/>'
                       f'<ellipse cx="{cx + ox}" cy="{top + 330}" rx="16" ry="62" fill="#050505"/>'
                       f'<circle cx="{cx + ox + 30}" cy="{top + 306}" r="11" fill="#fff" fill-opacity="0.85"/>')
    defs = ('<radialGradient id="iris"><stop offset="0" stop-color="#ffe27a"/>'
            '<stop offset="0.7" stop-color="#e9a43a"/><stop offset="1" stop-color="#8a5414"/></radialGradient>')
    camada = svg_png(svg(cabeca + olho(-250) + olho(250), defs))
    # brilho discreto dos olhos
    brilho = np.zeros((H, W, 4), np.float32)
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    for ox in (-250, 250):
        g = np.exp(-(((x - cx - ox) ** 2 + (y - top - 330) ** 2) / (2 * 140 ** 2)))
        brilho[..., :3] += hexrgb("#f0b040") * g[..., None]
        brilho[..., 3] = np.maximum(brilho[..., 3], g * 0.35)
    img = over(img, camada)
    img = img + brilho[..., :3] * brilho[..., 3:4] * 0.6
    salvar("simba-espiando", img, 5)

# ───────────────────────────────────────────── 6. Enrolado (claro, geométrico)
if quer("simba-dormindo"):
    img = radial("#f3f1ec", "#dedbd3", 0.5, 0.5, 1.0, 1.6)
    cx, cy = W * 0.5, H * 0.55
    corpo = svg(
        f'<ellipse cx="{cx}" cy="{cy + 240}" rx="430" ry="40" fill="#000" fill-opacity="0.06"/>'
        f'<path d="M{cx - 380} {cy + 210} A380 300 0 1 1 {cx + 380} {cy + 210} Z" fill="#8c8a85"/>'
        f'<circle cx="{cx - 210}" cy="{cy + 90}" r="150" fill="#9b9993"/>'
        f'<path d="M{cx - 330} {cy + 10} L{cx - 320} {cy - 130} L{cx - 230} {cy - 52} Z" fill="#9b9993"/>'
        f'<path d="M{cx - 140} {cy - 52} L{cx - 90} {cy - 140} L{cx - 72} {cy + 10} Z" fill="#9b9993"/>'
        f'<path d="M{cx - 285} {cy + 95} q 25 18 50 0 M{cx - 175} {cy + 95} q 25 18 50 0" stroke="#3b3a37" stroke-width="10" fill="none" stroke-linecap="round"/>'
        f'<path d="M{cx + 380} {cy + 210} C{cx + 380} {cy + 290} {cx - 120} {cy + 300} {cx - 300} {cy + 225}" '
        f'stroke="#7a7873" stroke-width="72" fill="none" stroke-linecap="round"/>'
        f'<path d="M{cx + 40} {cy - 40} q 60 -30 120 -10 M{cx + 70} {cy + 10} q 70 -25 140 0" stroke="#7d7b76" stroke-width="14" fill="none" stroke-linecap="round" stroke-opacity="0.6"/>'
        f'<text x="{cx + 260}" y="{cy - 180}" font-family="Adwaita Sans, sans-serif" font-size="70" font-weight="600" fill="#a8a59f">z</text>'
        f'<text x="{cx + 320}" y="{cy - 260}" font-family="Adwaita Sans, sans-serif" font-size="96" font-weight="600" fill="#b8b5af">z</text>')
    img = over(img, svg_png(corpo))
    salvar("simba-dormindo", img, 6, 0.012)

# ───────────────────────────────────────────── 7. Patinhas (escuro)
if quer("simba-patinhas"):
    img = radial("#1a1a1d", "#070708", 0.3, 0.3, 1.2, 1.3)
    def pata(x, y, ang, s, a):
        t = f'transform="translate({x:.0f} {y:.0f}) rotate({ang:.1f}) scale({s})"'
        return (f'<g {t} fill="#ffffff" fill-opacity="{a:.2f}">'
                '<path d="M0 10 C -34 10 -44 44 -28 58 C -16 68 -6 60 0 60 C 6 60 16 68 28 58 C 44 44 34 10 0 10 Z"/>'
                '<ellipse cx="-40" cy="-18" rx="13" ry="17"/><ellipse cx="-15" cy="-36" rx="13" ry="18"/>'
                '<ellipse cx="15" cy="-36" rx="13" ry="18"/><ellipse cx="40" cy="-18" rx="13" ry="17"/></g>')
    passos = []
    n = 11
    for i in range(n):
        t = i / (n - 1)
        x = W * 0.1 + t * W * 0.82
        y = H * 0.86 - t * H * 0.66 + 60 * math.sin(t * math.pi * 2)
        lado = 1 if i % 2 else -1
        ang = -math.degrees(math.atan2(H * 0.66, W * 0.82)) + 90 + 4 * lado
        dx, dy = 48 * lado * math.cos(math.radians(ang)), 48 * lado * math.sin(math.radians(ang))
        passos.append(pata(x + dx, y + dy, ang, 1.15, 0.05 + 0.20 * t))
    img = over(img, svg_png(svg("".join(passos))))
    salvar("simba-patinhas", img, 7)

# ───────────────────────────────────────────── 8. Retrato do Simba (marca)
RET = os.path.expanduser("~/.local/share/gerar-iso/marca/opcoes")
for nome, arq, f1, f2, op in (("simba-retrato-escuro", "carc-escuro.png", "#202022", "#050505", 0.16),
                              ("simba-retrato-claro", "carc-claro.png", "#f6f5f1", "#d9d8d3", 0.20)):
    if not quer(nome):
        continue
    img = radial(f1, f2, 0.62, 0.48, 1.0, 1.3)
    gato_img = Image.open(os.path.join(RET, arq)).convert("RGBA")
    bb = gato_img.getbbox(); gato_img = gato_img.crop(bb)
    alvo = 1650
    gato_img = gato_img.resize((int(gato_img.width * alvo / gato_img.height), alvo), Image.LANCZOS)
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
