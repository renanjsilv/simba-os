/*
 * Simba nos Telhados — mini game do instalador do Simba OS (pendrive).
 *
 * Desenha direto na tela gráfica (/dev/fb0), com o console em modo gráfico
 * (KD_GRAPHICS) enquanto roda: tamanhos proporcionais à resolução, pixels nítidos.
 * O gato do jogo é um tigrado de perfil (GATO); o retrato da marca (arte.h) aparece
 * nas telas de texto (--logo) e com Esc.
 *
 *   simba-jogo <arquivo-de-progresso>      jogo + progresso ("PCT TEXTO" no arquivo)
 *   simba-jogo --logo <linha> <linhas>     só desenha o retrato numa faixa do console
 *                                          (telas de texto do instalador) e sai
 *   simba-jogo --restaurar                 devolve o console ao modo texto
 *   simba-jogo --captura <arquivo.ppm> [pct]   desenha um quadro num arquivo (testes)
 *
 * Variáveis: SYS_LANG=en_US (textos em inglês), NOME (nome do sistema).
 * Sem framebuffer ou sem console virtual, sai com código 3 e o instalador
 * mostra o progresso em texto, como antes.
 */
#define _GNU_SOURCE
#include <fcntl.h>
#include <linux/fb.h>
#include <linux/kd.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/select.h>
#include <termios.h>
#include <time.h>
#include <unistd.h>

#include "arte.h"
#include "fonte.h"

/* O gato do jogo (tigrado, de perfil) — parte de cima; as patas são desenhadas à parte */
#define GATO_W 36
#define GATO_TOPO 15
static const char *GATO[] = {
  ".........................K.....K....",
  "........................KLK...KLK...",
  "........................KLGK.KGLK...",
  ".KK.....................KGGGKGGGGK..",
  "KDDK...................KGGDGGDGGGK..",
  "KD.K...................KGGDGGDGGGGK.",
  "KDK....................KGGGGGGKKGGK.",
  ".KDK...................KGGGGGGKWKGGK",
  "..KDK..................KGGGGGGGKGWWK",
  "...KDKKKKKKKKKKKKKKKKKKGGGGGGGGWWWKK",
  "....KGGDGGGDGGGDGGGDGGGGGGGGGGWWKWK.",
  "....KGGDGGGDGGGDGGGDGGGGGGGGGGWWWK..",
  "....KGGGGGGGGGGGGGGGGGGGGGGGGKKKK...",
  "....KGGGGGGGGGGGGGGGGGGGGGGGGK......",
  "....KGLLLLLLLLLLLLLLLLLLLLLGGK......"
};

/* ------------------------------------------------------------------ cores */
#define RGB(r, g, b) ((uint32_t)(((r) << 16) | ((g) << 8) | (b)))
static const uint32_t C_FUNDO = RGB(10, 10, 10);
static const uint32_t C_TEXTO = RGB(236, 236, 236);
static const uint32_t C_TEXTO2 = RGB(150, 150, 152);
static const uint32_t C_TEXTO3 = RGB(96, 96, 98);
static uint32_t cor_arte(char c) {
    switch (c) {
    case 'K': return RGB(16, 16, 16);
    case 'D': return RGB(70, 70, 72);
    case 'G': return RGB(150, 150, 152);
    case 'L': return RGB(200, 200, 202);
    case 'W': return RGB(245, 245, 245);
    }
    return 0xFFFFFFFF;
}

/* ------------------------------------------------------------- tela/buffer */
static int W, H;               /* tamanho real em pixels */
static uint32_t *buf;          /* quadro em memória (0xRRGGBB) */
static uint8_t *fbmem;
static int fb_bpp, fb_stride, fb_xoff, fb_yoff;
static struct fb_var_screeninfo vinfo;
static int tty_fd = -1, modo_grafico = 0;
static struct termios term_orig;
static int term_raw = 0;
static volatile sig_atomic_t rodando = 1;

static void restaurar(void) {
    if (modo_grafico && tty_fd >= 0) {
        ioctl(tty_fd, KDSETMODE, KD_TEXT);
        modo_grafico = 0;
    }
    if (term_raw) {
        tcsetattr(STDIN_FILENO, TCSAFLUSH, &term_orig);
        term_raw = 0;
    }
}
static void ao_sinal(int s) { (void)s; rodando = 0; }

static int abrir_fb(void) {
    int fd = open("/dev/fb0", O_RDWR);
    if (fd < 0) return -1;
    struct fb_fix_screeninfo finfo;
    if (ioctl(fd, FBIOGET_FSCREENINFO, &finfo) < 0 || ioctl(fd, FBIOGET_VSCREENINFO, &vinfo) < 0) { close(fd); return -1; }
    fb_bpp = vinfo.bits_per_pixel;
    if (fb_bpp != 32 && fb_bpp != 24 && fb_bpp != 16) { close(fd); return -1; }
    W = vinfo.xres; H = vinfo.yres; fb_stride = finfo.line_length;
    fb_xoff = vinfo.xoffset; fb_yoff = vinfo.yoffset;
    fbmem = mmap(NULL, finfo.smem_len, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);
    if (fbmem == MAP_FAILED) { fbmem = NULL; return -1; }
    buf = calloc((size_t)W * H, 4);
    return buf ? 0 : -1;
}

static inline uint32_t para_fb(uint32_t c) {
    uint32_t r = (c >> 16) & 255, g = (c >> 8) & 255, b = c & 255;
    return ((r >> (8 - vinfo.red.length)) << vinfo.red.offset) |
           ((g >> (8 - vinfo.green.length)) << vinfo.green.offset) |
           ((b >> (8 - vinfo.blue.length)) << vinfo.blue.offset);
}

/* copia só as linhas [y0, y1) do quadro para a tela */
static void enviar(int y0, int y1) {
    if (!fbmem) return;
    for (int y = y0; y < y1; y++) {
        uint8_t *d = fbmem + (size_t)(y + fb_yoff) * fb_stride + (size_t)fb_xoff * (fb_bpp / 8);
        const uint32_t *s = buf + (size_t)y * W;
        if (fb_bpp == 32 && vinfo.red.offset == 16 && vinfo.green.offset == 8 && vinfo.blue.offset == 0) {
            memcpy(d, s, (size_t)W * 4);
        } else if (fb_bpp == 32) {
            uint32_t *o = (uint32_t *)d;
            for (int x = 0; x < W; x++) o[x] = para_fb(s[x]);
        } else if (fb_bpp == 24) {
            for (int x = 0; x < W; x++) { uint32_t v = para_fb(s[x]); d[3 * x] = v; d[3 * x + 1] = v >> 8; d[3 * x + 2] = v >> 16; }
        } else {
            uint16_t *o = (uint16_t *)d;
            for (int x = 0; x < W; x++) o[x] = (uint16_t)para_fb(s[x]);
        }
    }
}

static void ret(int x, int y, int w, int h, uint32_t c) {
    if (x < 0) { w += x; x = 0; }
    if (y < 0) { h += y; y = 0; }
    if (x + w > W) w = W - x;
    if (y + h > H) h = H - y;
    if (w <= 0 || h <= 0) return;
    for (int j = y; j < y + h; j++) {
        uint32_t *p = buf + (size_t)j * W + x;
        for (int i = 0; i < w; i++) p[i] = c;
    }
}

/* recorte (o jogo desenha dentro do painel) */
static int cx0 = 0, cy0 = 0, cx1 = 1 << 30, cy1 = 1 << 30;
static void ret_c(int x, int y, int w, int h, uint32_t c) {
    int x1 = x + w, y1 = y + h;
    if (x < cx0) x = cx0;
    if (y < cy0) y = cy0;
    if (x1 > cx1) x1 = cx1;
    if (y1 > cy1) y1 = cy1;
    if (x1 > x && y1 > y) ret(x, y, x1 - x, y1 - y, c);
}

static void retrato(int x, int y, int u) {
    for (int j = 0; j < RETRATO_H; j++)
        for (int i = 0; i < RETRATO_W; i++) {
            uint32_t c = cor_arte(RETRATO[j][i]);
            if (c != 0xFFFFFFFF) ret_c(x + i * u, y + j * u, u, u, c);
        }
}

/* ------------------------------------------------------------------- texto */
static const Fonte *fonte(int i) { return &FONTES[i < 0 ? 0 : i > 2 ? 2 : i]; }
static int glifo_de(uint32_t cp) {
    for (int i = 0; i < FONTE_N; i++) if (FONTE_CP[i] == cp) return i;
    return '?' - 32;
}
static uint32_t utf8(const char **s) {
    const unsigned char *p = (const unsigned char *)*s;
    uint32_t c = *p++;
    if (c >= 0xF0) { c = (c & 7) << 18 | (p[0] & 63) << 12 | (p[1] & 63) << 6 | (p[2] & 63); p += 3; }
    else if (c >= 0xE0) { c = (c & 15) << 12 | (p[0] & 63) << 6 | (p[1] & 63); p += 2; }
    else if (c >= 0xC0) { c = (c & 31) << 6 | (p[0] & 63); p += 1; }
    *s = (const char *)p;
    return c;
}
static int largura_txt(const Fonte *f, const char *s) {
    int n = 0;
    while (*s) { utf8(&s); n++; }
    return n * f->w;
}
static void texto(const Fonte *f, int x, int y, const char *s, uint32_t cor) {
    int bpl = (f->w + 7) / 8;
    while (*s) {
        int g = glifo_de(utf8(&s));
        const unsigned char *d = f->d + (size_t)g * bpl * f->h;
        for (int j = 0; j < f->h; j++)
            for (int i = 0; i < f->w; i++)
                if (d[j * bpl + i / 8] & (0x80 >> (i % 8))) {
                    int px = x + i, py = y + j;
                    if (px >= 0 && px < W && py >= 0 && py < H) buf[(size_t)py * W + px] = cor;
                }
        x += f->w;
    }
}
static void texto_centro(const Fonte *f, int cx, int y, const char *s, uint32_t cor) {
    texto(f, cx - largura_txt(f, s) / 2, y, s, cor);
}
/* corta com "…" para caber em `larg` pixels */
static void cortar(const Fonte *f, char *s, int larg) {
    int max = larg / f->w, n = 0;
    char *p = s;
    while (*p) {
        const char *q = p;
        utf8(&q);
        if (++n > max - 1 && q[0]) { strcpy(p, "…"); return; }
        p = (char *)q;
    }
}

/* ------------------------------------------------------------- idioma */
static int ingles;
static const char *T(const char *pt, const char *en) { return ingles ? en : pt; }

/* ------------------------------------------------------------------ jogo */
#define MAX_OBS 6
#define MAX_PEIXE 6
typedef struct { float x; int tipo, ativo; } Obs;   /* tipo 0 chaminé, 1 antena */
typedef struct { float x; int y, ativo; } Peixe;

static int u;                  /* tamanho do pixel da arte (px reais) */
#define SX 14                  /* x do gato (unidades, dentro do painel) */
#define ALTURA (GATO_TOPO + 5) /* corpo + patas */
static int PX, PY, PW, PH;     /* painel do jogo em px reais */
static int GW, GH;             /* painel em unidades */
static int chao;               /* y do telhado (unidades, dentro do painel) */

static float gy, gvy;          /* altura do Simba acima do telhado (unidades) */
static int pulando, tropeco, peixes, recorde, quadro, parado_desde;
static float rolagem;
static Obs obs[MAX_OBS];
static Peixe peixe[MAX_PEIXE];
static int pct, terminou, so_progresso;
static char etapa[256], ultima_linha[256];
static unsigned semente = 12345;
static int aleat(int n) { semente = semente * 1103515245 + 12345; return (int)((semente >> 16) % (unsigned)n); }

/* unidades do painel → px reais */
#define UX(x) (PX + (int)((x) * u))
#define UY(y) (PY + (int)((y) * u))

static void calcular_layout(void) {
    u = (H + 125) / 250; if (u < 2) u = 2;
    GW = W / u - 24; if (GW > 220) GW = 220;
    GH = H / u - 92; if (GH > 110) GH = 110; if (GH < 60) GH = 60;
    PW = GW * u; PH = GH * u;
    PX = (W - PW) / 2;
    int rodape = (H >= 900 ? 24 + 32 + 24 * 4 : 16 + 24 + 16 * 4) + 20 * u / 4;
    int total = PH + 6 * u + rodape;
    PY = (H - total) / 2; if (PY < 2 * u) PY = 2 * u;
    /* o mundo do jogo em pixels 1,5× maiores que os da moldura (gato e cenário maiores) */
    int uw = u * 3 / 2;
    GW = PW / uw; GH = PH / uw; u = uw;
    PX += (PW - GW * u) / 2; PW = GW * u; PH = GH * u;
    chao = GH - 12;
}

static void novo_obstaculo(float x) {
    for (int i = 0; i < MAX_OBS; i++) if (!obs[i].ativo) { obs[i] = (Obs){x, aleat(2), 1}; return; }
}
static void novo_peixe(float x) {
    for (int i = 0; i < MAX_PEIXE; i++)
        if (!peixe[i].ativo) { peixe[i] = (Peixe){x, chao - 14 - aleat(30), 1}; return; }
}

static int pular_pedido;
static void atualizar(void) {
    quadro++;
    float vel = 1.6f;
    rolagem += vel;
    /* pulo: automático se ninguém jogar há 6 s */
    int auto_jogo = quadro - parado_desde > 30 * 6;
    if (auto_jogo && !pulando)
        for (int i = 0; i < MAX_OBS; i++)
            if (obs[i].ativo && obs[i].x > SX && obs[i].x < SX + GATO_W + 10) pular_pedido = 1;
    if (pular_pedido && !pulando) { pulando = 1; gvy = 4.1f; }
    pular_pedido = 0;
    if (pulando) {
        gy += gvy; gvy -= 0.26f;
        if (gy <= 0) { gy = 0; gvy = 0; pulando = 0; }
    }
    if (tropeco) tropeco--;
    /* obstáculos e peixes */
    float ultimo = 0;
    for (int i = 0; i < MAX_OBS; i++) if (obs[i].ativo) {
        obs[i].x -= vel;
        if (obs[i].x < -12) obs[i].ativo = 0;
        if (obs[i].x > ultimo) ultimo = obs[i].x;
        int ow = obs[i].tipo ? 5 : 9, oh = obs[i].tipo ? 20 : 15;
        /* colisão: base do retrato (com folga nas bordas) contra o obstáculo */
        if (!tropeco && obs[i].x < SX + GATO_W - 4 && obs[i].x + ow > SX + 5 && gy < oh - 2) {
            tropeco = 30; peixes = peixes > 2 ? peixes - 2 : 0;
        }
    }
    /* um obstáculo por vez na tela, com folga para o pulo (o voo cobre ~50 unidades) */
    static float vao = 120;
    if (ultimo < GW + 4 - vao) { novo_obstaculo(GW + 4); vao = 100 + aleat(90); }
    if (quadro % 70 == 0) novo_peixe(GW + 4);
    for (int i = 0; i < MAX_PEIXE; i++) if (peixe[i].ativo) {
        peixe[i].x -= vel;
        if (peixe[i].x < -10) peixe[i].ativo = 0;
        int topo = chao - ALTURA - (int)gy;
        if (peixe[i].x < SX + GATO_W && peixe[i].x + 8 > SX && peixe[i].y + 5 > topo && peixe[i].y < topo + ALTURA) {
            peixe[i].ativo = 0; peixes++;
            if (peixes > recorde) recorde = peixes;
        }
    }
}

static void desenhar_peixe(float x, int y) {
    static const char *P[] = { ".K..KKK.", "KLKKWWLK", "KLLWWKWK", "KLKKWWLK", ".K..KKK." };
    for (int j = 0; j < 5; j++)
        for (int i = 0; i < 8; i++) {
            uint32_t c = cor_arte(P[j][i]);
            if (c != 0xFFFFFFFF) ret_c(UX(x + i), UY(y + j), u, u, c);
        }
}

static void desenhar_obstaculo(const Obs *o) {
    int b = chao;
    if (o->tipo == 0) {          /* chaminé de tijolos */
        ret_c(UX(o->x), UY(b - 15), 9 * u, 3 * u, RGB(16, 16, 16));
        ret_c(UX(o->x + 1), UY(b - 14), 7 * u, u, RGB(200, 200, 202));
        ret_c(UX(o->x + 1), UY(b - 12), 7 * u, 12 * u, RGB(16, 16, 16));
        for (int j = 0; j < 11; j++)
            for (int i = 0; i < 5; i++)
                ret_c(UX(o->x + 2 + i), UY(b - 11 + j), u, u, ((i + (j % 2) * 2) % 4 == 0) ? RGB(70, 70, 72) : RGB(120, 120, 122));
    } else {                     /* antena */
        ret_c(UX(o->x + 2), UY(b - 18), u, 18 * u, RGB(16, 16, 16));
        ret_c(UX(o->x), UY(b - 20), u, 2 * u, RGB(16, 16, 16));
        ret_c(UX(o->x + 4), UY(b - 20), u, 2 * u, RGB(16, 16, 16));
        ret_c(UX(o->x + 1), UY(b - 18), 3 * u, u, RGB(16, 16, 16));
        ret_c(UX(o->x + 1), UY(b - 1), 3 * u, u, RGB(16, 16, 16));
    }
}

static void desenhar_cenario(void) {
    /* céu em faixas (degradê em pixels) */
    for (int j = 0; j < chao; j++) {
        int t = j * 14 / chao;
        ret_c(PX, UY(j), PW, u, RGB(22 + t, 22 + t, 25 + t));
    }
    /* estrelas (piscam devagar) */
    for (int k = 0; k < 40; k++) {
        int sx = (k * 37 + k * k * 11 + 5) % GW, sy = 2 + (k * 53 + k * k * 3) % (chao - 30);
        if ((k + quadro / 20) % 7) ret_c(UX(sx), UY(sy), u, u, k % 3 ? RGB(80, 80, 84) : RGB(140, 140, 144));
    }
    /* lua */
    int lx = GW - 30, ly = 10, r = 7;
    for (int j = -r; j <= r; j++)
        for (int i = -r; i <= r; i++)
            if (i * i + j * j <= r * r) ret_c(UX(lx + i), UY(ly + j), u, u, (i * i + j * j > (r - 1) * (r - 1)) ? RGB(150, 150, 152) : RGB(210, 210, 212));
    ret_c(UX(lx - 3), UY(ly - 1), 2 * u, 2 * u, RGB(175, 175, 178));
    ret_c(UX(lx + 2), UY(ly + 3), u * 2, u, RGB(175, 175, 178));
    /* prédios em duas camadas (parallax) */
    for (int camada = 0; camada < 2; camada++) {
        float desl = rolagem * (camada ? 0.5f : 0.2f);
        uint32_t cor = camada ? RGB(44, 44, 47) : RGB(32, 32, 35);
        unsigned s = camada ? 777 : 333;
        int x = -(int)desl % 400;
        int idx = (int)desl / 400 * 0;
        (void)idx;
        for (int k = 0; x < GW + 40 && k < 200; k++) {
            s = s * 1103515245 + 12345; int bw = 10 + (s >> 16) % 14;
            s = s * 1103515245 + 12345; int bh = (camada ? 14 : 24) + (s >> 16) % (camada ? 22 : 26);
            ret_c(UX(x), UY(chao - bh), bw * u, bh * u, cor);
            for (int jy = chao - bh + 2; jy < chao - 2; jy += 3)
                for (int jx = x + 2; jx < x + bw - 2; jx += 3) {
                    s = s * 1103515245 + 12345;
                    if ((s >> 16) % 9 == 0) ret_c(UX(jx), UY(jy), u, u, camada ? RGB(120, 120, 118) : RGB(80, 80, 80));
                }
            x += bw + 1;
            if (x > 400 + GW) break;
        }
    }
    /* telhado */
    ret_c(PX, UY(chao), PW, (GH - chao) * u, RGB(62, 62, 64));
    ret_c(PX, UY(chao), PW, u, RGB(150, 150, 152));
    int off = (int)rolagem % 8;
    for (int j = 0; j < 3; j++)
        for (int i = -8; i < GW + 8; i += 8)
            ret_c(UX(i - off + (j % 2) * 4), UY(chao + 3 + j * 4), 4 * u, u, RGB(44, 44, 46));
}

/* bloco com contorno preto (unidades) */
static void caixa(int x, int y, int w, int h, uint32_t cor) {
    ret_c(UX(x), UY(y), w * u, h * u, RGB(16, 16, 16));
    if (w > 2 && h > 2) ret_c(UX(x + 1), UY(y + 1), (w - 2) * u, (h - 2) * u, cor);
}
/* O gato correndo: as patas alternam (dois quadros); no pulo, esticadas. */
static void gato(int gx, int gy_) {
    for (int j = 0; j < GATO_TOPO; j++)
        for (int i = 0; i < GATO_W; i++) {
            uint32_t c = cor_arte(GATO[j][i]);
            if (c != 0xFFFFFFFF) ret_c(UX(gx + i), UY(gy_ + j), u, u, c);
        }
    static const int PERNA[4] = {5, 10, 21, 26};
    int fase = pulando ? 2 : (quadro / 4) % 2;
    for (int k = 0; k < 4; k++) {
        int dx = 0, alt = 5;
        if (fase == 2) { dx = k < 2 ? -1 - (1 - k) : 1 + (k - 2); alt = 4; }
        else if ((k % 2) == fase) { dx = 1; alt = 4; }
        else dx = -1;
        int x = gx + PERNA[k] + dx, y = gy_ + GATO_TOPO;
        caixa(x, y - 1, 4, alt + 1, RGB(150, 150, 152));
        ret_c(UX(x + 1), UY(y + alt - 2), 2 * u, u, RGB(200, 200, 202));
    }
}

static void desenhar_jogo(void) {
    cx0 = PX; cy0 = PY; cx1 = PX + PW; cy1 = PY + PH;
    desenhar_cenario();
    for (int i = 0; i < MAX_OBS; i++) if (obs[i].ativo) desenhar_obstaculo(&obs[i]);
    for (int i = 0; i < MAX_PEIXE; i++) if (peixe[i].ativo) desenhar_peixe(peixe[i].x, peixe[i].y);
    /* o Simba: o retrato da marca, quicando enquanto corre */
    int quique = pulando ? 0 : ((quadro / 5) % 2);
    int topo = chao - ALTURA - (int)gy - quique;
    if (!(tropeco && (quadro / 3) % 2)) gato(SX, topo);
    if (!pulando && quadro % 6 < 3) ret_c(UX(SX + 2 - (quadro % 6)), UY(chao - 2), u, u, RGB(110, 110, 112));
    cx0 = 0; cy0 = 0; cx1 = 1 << 30; cy1 = 1 << 30;
}

static void desenhar_so_progresso(void) {
    ret(PX, PY, PW, PH, RGB(18, 18, 20));
    int ur = u * 2;   /* retrato maior no meio */
    while (RETRATO_H * ur > PH * 3 / 4 && ur > 1) ur--;
    cx0 = PX; cy0 = PY; cx1 = PX + PW; cy1 = PY + PH;
    retrato(PX + (PW - RETRATO_W * ur) / 2, PY + (PH - RETRATO_H * ur) / 2, ur);
    cx0 = 0; cy0 = 0; cx1 = 1 << 30; cy1 = 1 << 30;
}

static void desenhar_tudo(void) {
    ret(0, 0, W, H, C_FUNDO);
    int fi = H >= 1300 ? 2 : H >= 900 ? 1 : 0;
    const Fonte *f = fonte(fi), *ft = fonte(fi + 1), *fp = fonte(fi > 0 ? fi - 1 : 0);
    /* moldura do painel */
    ret(PX - u, PY - u, PW + 2 * u, PH + 2 * u, RGB(52, 52, 54));
    if (so_progresso) desenhar_so_progresso(); else desenhar_jogo();
    /* placar dentro do painel */
    if (!so_progresso) {
        char s[96];
        snprintf(s, sizeof s, "%s %d   %s %d", T("Peixes", "Fish"), peixes, T("Recorde", "Best"), recorde);
        texto(f, PX + 3 * u, PY + 3 * u, s, C_TEXTO);
    }
    /* rodapé: título, barra, etapa, dicas */
    int y = PY + PH + 6 * u;
    int col = PX, larg = PW;
    char titulo[160];
    const char *nome = getenv("NOME");
    if (!nome || !*nome) nome = "Simba OS";
    if (terminou) snprintf(titulo, sizeof titulo, "%s", T("Quase pronto…", "Almost done…"));
    else snprintf(titulo, sizeof titulo, "%s %s", T("Instalando o", "Installing"), nome);
    texto(ft, col, y, titulo, C_TEXTO);
    char p[16]; snprintf(p, sizeof p, "%d%%", pct);
    texto(ft, col + larg - largura_txt(ft, p), y, p, C_TEXTO);
    y += ft->h + u * 2;
    int bh = 3 * u, cheio = larg * (pct < 0 ? 0 : pct > 100 ? 100 : pct) / 100;
    ret(col, y, larg, bh, RGB(36, 36, 38));
    ret(col, y, cheio, bh, RGB(200, 200, 202));
    for (int x = col; x < col + cheio; x += 2 * u) ret(x, y + bh - u, u, u, RGB(150, 150, 152));
    y += bh + u * 3;
    char e[256]; snprintf(e, sizeof e, "%s", etapa); cortar(f, e, larg);
    texto(f, col, y, e, C_TEXTO2);
    y += f->h + u;
    char l[256]; snprintf(l, sizeof l, "%s", ultima_linha); cortar(fp, l, larg);
    texto(fp, col, y, l, C_TEXTO3);
    y += fp->h + u * 3;
    const char *dica = so_progresso ? T("Esc  voltar ao jogo", "Esc  back to the game")
                                    : T("Espaço ou ↑  pular      Esc  esconder o jogo      o jogo não atrapalha a instalação",
                                        "Space or ↑  jump      Esc  hide the game      the game doesn't slow the installation");
    if (largura_txt(fp, dica) > PW)
        dica = so_progresso ? T("Esc  voltar ao jogo", "Esc  back to the game") : T("Espaço ou ↑  pular      Esc  esconder o jogo", "Space or ↑  jump      Esc  hide the game");
    texto_centro(fp, W / 2, y, dica, C_TEXTO3);
}

/* -------------------------------------------------------------- entrada */
static void ler_teclas(void) {
    unsigned char c[16];
    for (;;) {
        fd_set fds; FD_ZERO(&fds); FD_SET(STDIN_FILENO, &fds);
        struct timeval tv = {0, 0};
        if (select(STDIN_FILENO + 1, &fds, NULL, NULL, &tv) <= 0) return;
        ssize_t n = read(STDIN_FILENO, c, sizeof c);
        if (n <= 0) return;
        parado_desde = quadro;
        for (ssize_t i = 0; i < n; i++) {
            if (c[i] == 27 && i + 2 < n && c[i + 1] == '[') { if (c[i + 2] == 'A') pular_pedido = 1; i += 2; }
            else if (c[i] == 27) so_progresso = !so_progresso;
            else if (c[i] == ' ' || c[i] == 'w' || c[i] == 'W' || c[i] == 'k') pular_pedido = 1;
        }
    }
}

static void ler_progresso(const char *arq) {
    FILE *f = fopen(arq, "r");
    if (f) {
        int p; char t[256] = "";
        if (fscanf(f, "%d %255[^\n]", &p, t) >= 1) { pct = p; if (t[0]) snprintf(etapa, sizeof etapa, "%s", t); }
        fclose(f);
    }
    if (pct >= 100) terminou = 1;
    f = fopen("/tmp/instalacao.log", "r");
    if (f) {
        char b[2048]; fseek(f, 0, SEEK_END); long tam = ftell(f);
        fseek(f, tam > (long)sizeof b - 1 ? tam - (long)sizeof b + 1 : 0, SEEK_SET);
        size_t n = fread(b, 1, sizeof b - 1, f); b[n] = 0; fclose(f);
        while (n && (b[n - 1] == '\n' || b[n - 1] == '\r' || b[n - 1] == ' ')) b[--n] = 0;
        char *ini = strrchr(b, '\n'); ini = ini ? ini + 1 : b;
        char *cr = strrchr(ini, '\r'); if (cr) ini = cr + 1;
        /* sem códigos de cor nem caracteres de controle */
        char *o = ultima_linha;
        for (char *s = ini; *s && o < ultima_linha + sizeof ultima_linha - 4; s++) {
            if (*s == 27) { while (*s && !((*s >= 'a' && *s <= 'z') || (*s >= 'A' && *s <= 'Z'))) s++; if (!*s) break; continue; }
            if ((unsigned char)*s >= 32) *o++ = *s;
        }
        *o = 0;
    }
}

/* ---------------------------------------------------- retrato no console */
static int modo_logo(int linha, int linhas) {
    if (abrir_fb() < 0) return 3;
    struct winsize ws;
    if (ioctl(STDOUT_FILENO, TIOCGWINSZ, &ws) < 0 || !ws.ws_row) return 3;
    int ch = H / ws.ws_row;                   /* altura de uma linha do console */
    int y0 = linha * ch, alt = linhas * ch;
    int k = alt / RETRATO_H; if (k < 1) return 0;
    if (k > H / 160) k = H / 160 > 0 ? H / 160 : 1;   /* nunca gigante: ~1/5 da tela */
    int x = (W - RETRATO_W * k) / 2, y = y0 + (alt - RETRATO_H * k) / 2;
    for (int j = 0; j < RETRATO_H; j++)
        for (int i = 0; i < RETRATO_W; i++) {
            uint32_t c = cor_arte(RETRATO[j][i]);
            if (c == 0xFFFFFFFF) continue;
            for (int b = 0; b < k; b++) {
                uint8_t *d = fbmem + (size_t)(y + j * k + b + fb_yoff) * fb_stride + (size_t)(x + i * k + fb_xoff) * (fb_bpp / 8);
                for (int a = 0; a < k; a++) {
                    uint32_t v = para_fb(c);
                    if (fb_bpp == 32) ((uint32_t *)d)[a] = v;
                    else if (fb_bpp == 16) ((uint16_t *)d)[a] = (uint16_t)v;
                    else { d[3 * a] = v; d[3 * a + 1] = v >> 8; d[3 * a + 2] = v >> 16; }
                }
            }
        }
    return 0;
}

/* --------------------------------------------------------------- captura */
static int captura(const char *saida, int p) {
    W = 1920; H = 1080;
    if (getenv("CAPTURA_W")) W = atoi(getenv("CAPTURA_W"));
    if (getenv("CAPTURA_H")) H = atoi(getenv("CAPTURA_H"));
    buf = calloc((size_t)W * H, 4);
    calcular_layout();
    pct = p; snprintf(etapa, sizeof etapa, "%s", T("Copiando o sistema", "Copying the system"));
    snprintf(ultima_linha, sizeof ultima_linha, "unsquashfs: 2041/3310");
    peixes = 7; recorde = 12;
    for (int i = 0; i < 150; i++) atualizar();
    if (getenv("CAPTURA_ESC")) so_progresso = 1;
    desenhar_tudo();
    FILE *f = fopen(saida, "wb");
    if (!f) return 1;
    fprintf(f, "P6 %d %d 255\n", W, H);
    for (size_t i = 0; i < (size_t)W * H; i++) { unsigned char c[3] = {buf[i] >> 16, buf[i] >> 8, buf[i]}; fwrite(c, 1, 3, f); }
    fclose(f);
    return 0;
}

int main(int argc, char **argv) {
    const char *lang = getenv("SYS_LANG");
    ingles = lang && !strncmp(lang, "en", 2);
    snprintf(etapa, sizeof etapa, "%s", T("Iniciando…", "Starting…"));
    if (argc > 1 && !strcmp(argv[1], "--restaurar")) {
        ioctl(STDIN_FILENO, KDSETMODE, KD_TEXT);
        return 0;
    }
    if (argc > 3 && !strcmp(argv[1], "--logo")) return modo_logo(atoi(argv[2]), atoi(argv[3]));
    if (argc > 2 && !strcmp(argv[1], "--captura")) return captura(argv[2], argc > 3 ? atoi(argv[3]) : 62);
    const char *arq = argc > 1 ? argv[1] : "/tmp/simba-progresso";

    if (abrir_fb() < 0) return 3;
    tty_fd = STDIN_FILENO;
    if (ioctl(tty_fd, KDSETMODE, KD_GRAPHICS) < 0) return 3;
    modo_grafico = 1;
    atexit(restaurar);
    struct sigaction sa = {0};
    sa.sa_handler = ao_sinal;
    sigaction(SIGTERM, &sa, NULL); sigaction(SIGINT, &sa, NULL); sigaction(SIGHUP, &sa, NULL);
    if (tcgetattr(STDIN_FILENO, &term_orig) == 0) {
        struct termios r = term_orig;
        r.c_lflag &= ~(ICANON | ECHO | ISIG);
        r.c_cc[VMIN] = 0; r.c_cc[VTIME] = 0;
        tcsetattr(STDIN_FILENO, TCSAFLUSH, &r);
        term_raw = 1;
    }
    calcular_layout();
    recorde = 0;
    novo_obstaculo(GW + 20);

    struct timespec t0; clock_gettime(CLOCK_MONOTONIC, &t0);
    long prox = 0;
    while (rodando) {
        ler_teclas();
        if (quadro % 6 == 0) ler_progresso(arq);
        if (!so_progresso) atualizar(); else quadro++;
        desenhar_tudo();
        enviar(0, H);
        /* 30 quadros por segundo, sem acumular atraso */
        prox += 1000000000L / 30;
        struct timespec ag; clock_gettime(CLOCK_MONOTONIC, &ag);
        long dec = (ag.tv_sec - t0.tv_sec) * 1000000000L + (ag.tv_nsec - t0.tv_nsec);
        if (prox > dec) { struct timespec d = {0, prox - dec}; nanosleep(&d, NULL); }
        else prox = dec;
    }
    restaurar();
    return 0;
}
