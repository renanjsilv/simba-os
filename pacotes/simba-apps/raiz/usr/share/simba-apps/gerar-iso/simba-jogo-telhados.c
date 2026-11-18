/*
 * Simba nos Telhados — Mini game em paralelo com a instalação do Simba OS.
 * Roda no console Linux (160x45 ou menor) com taxa de 30 FPS.
 * Lê o progresso em /tmp/simba-progresso (ou argv[1]) gravado pelo instalar-clone.
 *
 * Controles:
 *   Espaço ou Seta Cima: Pular chaminés e antenas e pegar peixes
 *   Esc: Alternar entre o jogo e a tela de progresso detalhada
 *   Enter: Reiniciar após conclusão da instalação
 *
 * Se ninguém tocar no teclado, o Simba corre e salta automaticamente,
 * e a instalação segue normalmente.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <termios.h>
#include <signal.h>
#include <time.h>
#include <sys/select.h>
#include <sys/ioctl.h>
#include <fcntl.h>

#define FPS 30
#define FRAME_US (1000000 / FPS)
#define MAX_OBSTACLES 8
#define MAX_FISH 8

static struct termios orig_termios;
static int raw_mode = 0;
static volatile sig_atomic_t running = 1;

/* Configuração do terminal */
static void restore_terminal(void) {
    if (raw_mode) {
        printf("\033[?25h\033[0m\033[2J\033[H");
        fflush(stdout);
        tcsetattr(STDIN_FILENO, TCSAFLUSH, &orig_termios);
        raw_mode = 0;
    }
}

static void sig_handler(int sig) {
    (void)sig;
    running = 0;
}

static void init_terminal(void) {
    if (tcgetattr(STDIN_FILENO, &orig_termios) == 0) {
        struct termios raw = orig_termios;
        raw.c_lflag &= ~(ICANON | ECHO | ISIG);
        raw.c_cc[VMIN] = 0;
        raw.c_cc[VTIME] = 0;
        tcsetattr(STDIN_FILENO, TCSAFLUSH, &raw);
        raw_mode = 1;
    }
    signal(SIGINT, sig_handler);
    signal(SIGTERM, sig_handler);
    signal(SIGHUP, sig_handler);
    atexit(restore_terminal);
    printf("\033[?25l\033[2J\033[H");
    fflush(stdout);
}

/* Sprites do jogo */
static const char *GATO_RUN1[] = {
    "...........K..K.",
    "..........KLKKLK",
    ".K........KGGGGK",
    "KDK.......KGKGGK",
    ".KDK.KKKKKGGGGWK",
    "..KDKGGGGGGGGGK.",
    "...KGGDGDGGGGK..",
    "...KGGGGGGGGGK..",
    "...KGK.KK..KGK..",
    "..KK....KK..KK.."
};
#define GATO_RUN_H 10
#define GATO_RUN_W 16

static const char *GATO_RUN2[] = {
    "...........K..K.",
    "..........KLKKLK",
    ".K........KGGGGK",
    "KDK.......KGKGGK",
    ".KDK.KKKKKGGGGWK",
    "..KDKGGGGGGGGGK.",
    "...KGGDGDGGGGK..",
    "...KGGGGGGGGGK..",
    "....KK.KGK.KK...",
    "...KK..KK...KK.."
};

static const char *GATO_JUMP[] = {
    "..............K..K.",
    ".............KLKKLK",
    ".............KGGGGK",
    ".............KGKGGGK",
    "KK...........KGGGGWK",
    "KDK.KKKKKKKKKKGGGKK",
    ".KDKGGGGGGGGGGGGK..",
    "..KKGGGGDGGGGGGGKK.",
    "...KKGGGGGGGGGGWGKK",
    ".KKGGKKKKKKKKKKKKGGK",
    "KGGKK...........KKK.",
    "KK.................."
};
#define GATO_JUMP_H 12
#define GATO_JUMP_W 20

static const char *SPRITE_FISH[] = {
    ".K..KKK.",
    "KLKKWWLK",
    "KLLWWKWK",
    "KLKKWWLK",
    ".K..KKK."
};
#define FISH_H 5
#define FISH_W 8

static const char *SPRITE_CHIMNEY[] = {
    "KKKKKKKKK",
    "KLLLLLLLK",
    "KKKKKKKKK",
    ".KGGDGGK.",
    ".KDDDDDK.",
    ".KGDGGGK.",
    ".KDDDDDK.",
    ".KGGGDGK."
};
#define CHIMNEY_H 8
#define CHIMNEY_W 9

static const char *SPRITE_ANTENNA[] = {
    "K...K",
    ".K.K.",
    "..K..",
    "..K..",
    "..K..",
    "..K..",
    "..K..",
    ".KKK."
};
#define ANTENNA_H 8
#define ANTENNA_W 5

static const char *SPRITE_MOON[] = {
    "..KKKK..",
    ".KLLLLK.",
    "KLLWLLLK",
    "KLLLLLDK",
    "KLLLLLLK",
    "KLDLLLLK",
    ".KLLLLK.",
    "..KKKK.."
};
#define MOON_H 8
#define MOON_W 8

/* Rosto do Simba em Pixel Art (Opção A) no selo claro */
static const char *SELO_SIMBA[] = {
    ".BBSSSSSSSSSSSSSSBB.",
    ".BSKSSSSSSSSSSSSKSB.",
    "BSSKKSSSSSSSSSSKKSSB",
    "BSSKLKSSSSSSSSKLKSSB",
    "BSSKLLKKKKKKKKLLKSSB",
    "BSKGGGGDGDDGDGGGGKSB",
    "BSKGGGGGGGGGGGGGGKSB",
    "BSKGKKGGGGGGGGKKGKSB",
    "BSKGGKKKGGGGKKKGGKSB",
    "BSKGGGGGKKKKGGGGGKSB",
    "BDDDGGWWWKKWWWGGDDDB",
    "BSSKGWWWWWWWWWWGKSSB",
    "BDDDGWKKKKKKKKWGDDDB",
    "BSSKGWKWKKKKWKWGKSSB",
    "BSSSKWKKKKKKKKWKSSSB",
    "BSSSSKWWKWWKWWKSSSSB",
    ".BSSSSKKKKKKKKSSSSB.",
    ".BBSSSSSSSSSSSSSSBB."
};
#define SELO_H 18
#define SELO_W 20

/* Estruturas do jogo */
typedef struct {
    int x;
    int type; /* 1 = chamine, 2 = antena */
    int active;
} Obstacle;

typedef struct {
    int x;
    int y;
    int active;
} Fish;

static int is_linux_console = 0;

/* Converte código de cor para sequência ANSI */
static const char *ansi_cor(char c) {
    if (is_linux_console) {
        /* Paleta do setvtrgb do instalador */
        switch (c) {
            case 'K': return "\033[0;32;40m"; /* preto (2) */
            case 'D': return "\033[0;34;40m"; /* cinza escuro (4) */
            case 'G': return "\033[1;31;40m"; /* cinza (9) */
            case 'L': return "\033[1;32;40m"; /* cinza claro (10) */
            case 'B': return "\033[1;32;40m"; /* borda selo (10) */
            case 'W': return "\033[1;33;40m"; /* branco (11) */
            case 'S': return "\033[1;34;40m"; /* selo (12) */
            case 'c': return "\033[0;37;40m";
            case 'e': return "\033[0;34;40m";
            case 'm': return "\033[0;34;40m";
            case 'j': return "\033[1;31;40m";
            case 'P': return "\033[0;34;40m"; /* predios */
            case 'R': return "\033[1;31;40m"; /* telhado */
            case 'r': return "\033[0;34;40m";
            default:  return "\033[0;37;40m";
        }
    } else {
        /* Truecolor RGB para emuladores de terminal */
        switch (c) {
            case 'K': return "\033[38;2;16;16;16m";
            case 'D': return "\033[38;2;70;70;72m";
            case 'G': return "\033[38;2;150;150;152m";
            case 'L': return "\033[38;2;200;200;202m";
            case 'B': return "\033[38;2;200;200;198m";
            case 'W': return "\033[38;2;245;245;245m";
            case 'S': return "\033[38;2;234;234;232m";
            case 'c': return "\033[38;2;95;95;93m";
            case 'e': return "\033[38;2;36;36;38m";
            case 'm': return "\033[38;2;52;52;54m";
            case 'j': return "\033[38;2;120;120;118m";
            case 'P': return "\033[38;2;56;56;58m";
            case 'R': return "\033[38;2;84;84;86m";
            case 'r': return "\033[38;2;62;62;64m";
            default:  return "\033[38;2;236;236;236m";
        }
    }
}

int main(int argc, char **argv) {
    const char *progress_file = (argc > 1) ? argv[1] : "/tmp/simba-progresso";
    const char *term = getenv("TERM");
    if (term && strcmp(term, "linux") == 0) {
        is_linux_console = 1;
    }

    init_terminal();

    /* Estado do jogo */
    int term_cols = 160, term_lines = 45;
    struct winsize ws;
    if (ioctl(STDOUT_FILENO, TIOCGWINSZ, &ws) == 0 && ws.ws_col >= 60 && ws.ws_row >= 20) {
        term_cols = ws.ws_col;
        term_lines = ws.ws_row;
    }

    int game_w = 70; /* pixels do jogo (cada pixel = 2 colunas) */
    if (game_w * 2 + 4 > term_cols) {
        game_w = (term_cols - 4) / 2;
    }
    int game_h = (term_lines >= 40) ? 24 : 16;
    int chao_y = game_h - 5;

    int simba_x = 12;
    float simba_y = 0.0f;
    float simba_vy = 0.0f;
    int is_jumping = 0;
    int stumble_frames = 0;

    int peixes = 0;
    int distancia = 0;
    int recorde = 31;
    int frame = 0;
    int show_log = 0;
    int finished = 0;

    Obstacle obstacles[MAX_OBSTACLES];
    memset(obstacles, 0, sizeof(obstacles));
    Fish fishes[MAX_FISH];
    memset(fishes, 0, sizeof(fishes));

    /* Inicializa alguns prédios ao fundo */
    int bld_x[16], bld_w[16], bld_h[16];
    int num_bld = 0, bx = 0;
    srand(42);
    while (bx < game_w + 30 && num_bld < 16) {
        bld_x[num_bld] = bx;
        bld_w[num_bld] = 5 + rand() % 5;
        bld_h[num_bld] = 6 + rand() % 7;
        bx += bld_w[num_bld] + (rand() % 3);
        num_bld++;
    }

    /* Buffer da tela do jogo (pixels) */
    char **grid = (char **)malloc(game_h * sizeof(char *));
    for (int y = 0; y < game_h; y++) {
        grid[y] = (char *)malloc(game_w + 1);
    }

    char out_buf[131072];
    int pct = 0;
    char etapa[128] = "Iniciando a instalação…";
    char log_tail[512] = "";

    while (running) {
        /* Lê entrada do teclado (não bloqueante se houver terminal) */
        int key_pressed = 0;
        if (isatty(STDIN_FILENO)) {
            fd_set fds;
            FD_ZERO(&fds);
            FD_SET(STDIN_FILENO, &fds);
            struct timeval tv = {0, 0};

            while (select(STDIN_FILENO + 1, &fds, NULL, NULL, &tv) > 0) {
                char ch;
                ssize_t n = read(STDIN_FILENO, &ch, 1);
                if (n <= 0) break;
                if (ch == 27) { /* Esc ou sequência de escape */
                    char seq[3];
                    if (read(STDIN_FILENO, &seq[0], 1) > 0) {
                        if (seq[0] == '[') {
                            if (read(STDIN_FILENO, &seq[1], 1) > 0) {
                                if (seq[1] == 'A') { /* Seta Cima */
                                    key_pressed = 1;
                                }
                            }
                        }
                    } else {
                        /* Esc solto: alterna visão */
                        show_log = !show_log;
                    }
                } else if (ch == ' ' || ch == 'w' || ch == 'W') {
                    key_pressed = 1;
                } else if (ch == 'q' || ch == 'Q') {
                    show_log = !show_log;
                } else if (ch == '\n' || ch == '\r') {
                    if (pct >= 100) running = 0;
                }
                FD_ZERO(&fds);
                FD_SET(STDIN_FILENO, &fds);
                tv.tv_sec = 0;
                tv.tv_usec = 0;
            }
        }

        /* Lê arquivo de progresso periodicamente */
        if (frame % 5 == 0) {
            FILE *fp = fopen(progress_file, "r");
            if (fp) {
                int p = 0;
                char buf[128] = "";
                if (fscanf(fp, "%d %[^\n]", &p, buf) >= 1) {
                    pct = p;
                    if (buf[0]) snprintf(etapa, sizeof(etapa), "%s", buf);
                }
                fclose(fp);
            }
            if (pct >= 100) finished = 1;

            /* Lê últimas linhas do log da instalação */
            FILE *fl = fopen("/tmp/instalacao.log", "r");
            if (fl) {
                fseek(fl, -512, SEEK_END);
                char lbuf[512];
                size_t nr = fread(lbuf, 1, sizeof(lbuf) - 1, fl);
                if (nr > 0) {
                    lbuf[nr] = '\0';
                    char *last_nl = strrchr(lbuf, '\n');
                    if (last_nl && *(last_nl - 1)) {
                        char *prev_nl = last_nl - 1;
                        while (prev_nl > lbuf && *prev_nl != '\n') prev_nl--;
                        if (*prev_nl == '\n') prev_nl++;
                        *last_nl = '\0';
                        snprintf(log_tail, sizeof(log_tail), "%s", prev_nl);
                    }
                }
                fclose(fl);
            }
        }

        /* Física do Simba */
        if (key_pressed && !is_jumping) {
            simba_vy = 1.35f;
            is_jumping = 1;
        }

        /* Auto-pilot: salta se estiver a ponto de bater */
        if (!is_jumping) {
            for (int i = 0; i < MAX_OBSTACLES; i++) {
                if (obstacles[i].active && obstacles[i].x > simba_x && obstacles[i].x < simba_x + 6) {
                    simba_vy = 1.35f;
                    is_jumping = 1;
                    break;
                }
            }
        }

        if (is_jumping) {
            simba_y += simba_vy;
            simba_vy -= 0.18f; /* gravidade */
            if (simba_y <= 0.0f) {
                simba_y = 0.0f;
                simba_vy = 0.0f;
                is_jumping = 0;
            }
        }

        if (stumble_frames > 0) stumble_frames--;

        /* Spawna obstáculos e peixes */
        if (frame % 35 == 0 && (rand() % 100) < 65) {
            for (int i = 0; i < MAX_OBSTACLES; i++) {
                if (!obstacles[i].active) {
                    obstacles[i].active = 1;
                    obstacles[i].type = (rand() % 2) ? 1 : 2;
                    obstacles[i].x = game_w - 2;
                    break;
                }
            }
        }

        if (frame % 28 == 0 && (rand() % 100) < 55) {
            for (int i = 0; i < MAX_FISH; i++) {
                if (!fishes[i].active) {
                    fishes[i].active = 1;
                    fishes[i].x = game_w - 2;
                    fishes[i].y = chao_y - 4 - (rand() % 4);
                    break;
                }
            }
        }

        /* Move obstáculos e peixes para a esquerda */
        for (int i = 0; i < MAX_OBSTACLES; i++) {
            if (obstacles[i].active) {
                obstacles[i].x--;
                if (obstacles[i].x < -10) obstacles[i].active = 0;

                /* Colisão com Simba */
                int obs_w = (obstacles[i].type == 1) ? CHIMNEY_W : ANTENNA_W;
                int obs_h = (obstacles[i].type == 1) ? CHIMNEY_H : ANTENNA_H;
                int obs_top = chao_y - obs_h;
                int cat_bottom = chao_y - (int)simba_y;

                if (obstacles[i].x < simba_x + 12 && obstacles[i].x + obs_w > simba_x + 4) {
                    if (cat_bottom >= obs_top && stumble_frames == 0) {
                        stumble_frames = 12; /* tropecou */
                    }
                }
            }
        }

        for (int i = 0; i < MAX_FISH; i++) {
            if (fishes[i].active) {
                fishes[i].x--;
                if (fishes[i].x < -5) fishes[i].active = 0;

                /* Coleta de peixe */
                int cat_top = chao_y - (int)simba_y - 10;
                int cat_bottom = chao_y - (int)simba_y;
                if (fishes[i].x < simba_x + 14 && fishes[i].x + FISH_W > simba_x + 2) {
                    if (fishes[i].y >= cat_top - 2 && fishes[i].y <= cat_bottom + 2) {
                        fishes[i].active = 0;
                        peixes++;
                        if (peixes > recorde) recorde = peixes;
                    }
                }
            }
        }

        distancia += 1;

        /* Limpa buffer do jogo com céu noturno */
        for (int y = 0; y < game_h; y++) {
            memset(grid[y], '.', game_w);
            grid[y][game_w] = '\0';
        }

        /* Desenha prédios ao fundo (parallax: move 1 pixel a cada 3 frames) */
        int p_offset = (frame / 3) % (game_w + 30);
        for (int b = 0; b < num_bld; b++) {
            int bx_pos = bld_x[b] - p_offset;
            while (bx_pos < -15) bx_pos += (game_w + 30);
            int bw = bld_w[b];
            int bh = bld_h[b];
            int by_top = chao_y - bh;
            for (int y = by_top; y < chao_y; y++) {
                if (y >= 0 && y < game_h) {
                    for (int x = bx_pos; x < bx_pos + bw; x++) {
                        if (x >= 0 && x < game_w) {
                            /* Janelas acesas aleatórias */
                            if ((x + y + b) % 4 == 0 && (x * 7 + y * 3) % 5 == 0) {
                                grid[y][x] = 'j';
                            } else {
                                grid[y][x] = 'P';
                            }
                        }
                    }
                }
            }
        }

        /* Lua */
        int moon_x = game_w - 14;
        int moon_y = 2;
        for (int y = 0; y < MOON_H; y++) {
            for (int x = 0; x < MOON_W; x++) {
                char c = SPRITE_MOON[y][x];
                if (c != '.' && moon_y + y < game_h && moon_x + x < game_w) {
                    grid[moon_y + y][moon_x + x] = c;
                }
            }
        }

        /* Estrelas */
        static const int stars[][2] = {{10, 3}, {22, 5}, {34, 2}, {48, 6}, {60, 4}, {15, 8}, {42, 9}};
        for (size_t s = 0; s < sizeof(stars) / sizeof(stars[0]); s++) {
            int sx = (stars[s][0] - (frame / 6)) % game_w;
            if (sx < 0) sx += game_w;
            int sy = stars[s][1];
            if (sy < chao_y && grid[sy][sx] == '.') {
                grid[sy][sx] = 'j';
            }
        }

        /* Telhado (chão) */
        for (int x = 0; x < game_w; x++) {
            if (chao_y < game_h) grid[chao_y][x] = 'G'; /* linha superior brilhante */
            for (int y = chao_y + 1; y < game_h; y++) {
                /* Padrão de tijolos */
                if ((x + (y % 2) * 2) % 4 < 2) {
                    grid[y][x] = 'r';
                } else {
                    grid[y][x] = 'R';
                }
            }
        }

        /* Obstáculos */
        for (int i = 0; i < MAX_OBSTACLES; i++) {
            if (obstacles[i].active) {
                if (obstacles[i].type == 1) { /* Chaminé */
                    for (int y = 0; y < CHIMNEY_H; y++) {
                        for (int x = 0; x < CHIMNEY_W; x++) {
                            char c = SPRITE_CHIMNEY[y][x];
                            int gx = obstacles[i].x + x;
                            int gy = chao_y - CHIMNEY_H + y;
                            if (c != '.' && gy >= 0 && gy < game_h && gx >= 0 && gx < game_w) {
                                grid[gy][gx] = c;
                            }
                        }
                    }
                } else { /* Antena */
                    for (int y = 0; y < ANTENNA_H; y++) {
                        for (int x = 0; x < ANTENNA_W; x++) {
                            char c = SPRITE_ANTENNA[y][x];
                            int gx = obstacles[i].x + x;
                            int gy = chao_y - ANTENNA_H + y;
                            if (c != '.' && gy >= 0 && gy < game_h && gx >= 0 && gx < game_w) {
                                grid[gy][gx] = c;
                            }
                        }
                    }
                }
            }
        }

        /* Peixes */
        for (int i = 0; i < MAX_FISH; i++) {
            if (fishes[i].active) {
                for (int y = 0; y < FISH_H; y++) {
                    for (int x = 0; x < FISH_W; x++) {
                        char c = SPRITE_FISH[y][x];
                        int gx = fishes[i].x + x;
                        int gy = fishes[i].y + y;
                        if (c != '.' && gy >= 0 && gy < game_h && gx >= 0 && gx < game_w) {
                            grid[gy][gx] = c;
                        }
                    }
                }
            }
        }

        /* Simba */
        if (stumble_frames == 0 || (stumble_frames % 2 == 0)) {
            if (is_jumping) {
                for (int y = 0; y < GATO_JUMP_H; y++) {
                    for (int x = 0; x < GATO_JUMP_W; x++) {
                        char c = GATO_JUMP[y][x];
                        int gx = simba_x + x;
                        int gy = chao_y - (int)simba_y - GATO_JUMP_H + y;
                        if (c != '.' && gy >= 0 && gy < game_h && gx >= 0 && gx < game_w) {
                            grid[gy][gx] = c;
                        }
                    }
                }
            } else {
                const char **run_sprite = ((frame / 4) % 2 == 0) ? GATO_RUN1 : GATO_RUN2;
                for (int y = 0; y < GATO_RUN_H; y++) {
                    for (int x = 0; x < GATO_RUN_W; x++) {
                        char c = run_sprite[y][x];
                        int gx = simba_x + x;
                        int gy = chao_y - GATO_RUN_H + y;
                        if (c != '.' && gy >= 0 && gy < game_h && gx >= 0 && gx < game_w) {
                            grid[gy][gx] = c;
                        }
                    }
                }
            }
        }

        /* Monta frame completo em out_buf para escrita atômica (sem flicker) */
        char *p = out_buf;
        p += sprintf(p, "\033[H"); /* Move cursor para o topo */

        if (!show_log) {
            /* ── Placar superior ── */
            p += sprintf(p, "\033[1;37m SIMBA NOS TELHADOS \033[0m   Peixes: \033[1;33m%d\033[0m   Recorde: \033[0;37m%d\033[0m   Distância: \033[0;37m%d m\033[0m\n",
                         peixes, recorde, distancia);

            /* ── Borda superior do jogo ── */
            p += sprintf(p, "\033[38;2;52;52;54m┌");
            for (int x = 0; x < game_w * 2; x++) p += sprintf(p, "─");
            p += sprintf(p, "┐\033[0m\n");

            /* ── Grade de pixels do jogo ── */
            for (int y = 0; y < game_h; y++) {
                p += sprintf(p, "\033[38;2;52;52;54m│\033[0m");
                char last_color = 0;
                for (int x = 0; x < game_w; x++) {
                    char c = grid[y][x];
                    if (c == '.') {
                        p += sprintf(p, "\033[48;2;42;42;44m  ");
                        last_color = 0;
                    } else {
                        if (c != last_color) {
                            p += sprintf(p, "%s", ansi_cor(c));
                            last_color = c;
                        }
                        p += sprintf(p, "██");
                    }
                }
                p += sprintf(p, "\033[0m\033[38;2;52;52;54m│\033[0m\n");
            }

            /* ── Borda inferior do jogo ── */
            p += sprintf(p, "\033[38;2;52;52;54m└");
            for (int x = 0; x < game_w * 2; x++) p += sprintf(p, "─");
            p += sprintf(p, "┘\033[0m\n");

            /* ── Rodapé com o Simba (Opção A) e Progresso ── */
            int bar_width = 46;
            int filled = (pct * bar_width) / 100;
            if (filled > bar_width) filled = bar_width;

            for (int row = 0; row < SELO_H; row++) {
                /* Selo do Simba à esquerda */
                char last_c = 0;
                p += sprintf(p, "  ");
                for (int col = 0; col < SELO_W; col++) {
                    char c = SELO_SIMBA[row][col];
                    if (c == '.') {
                        p += sprintf(p, "\033[0m  ");
                        last_c = 0;
                    } else {
                        if (c != last_c) {
                            p += sprintf(p, "%s", ansi_cor(c));
                            last_c = c;
                        }
                        p += sprintf(p, "██");
                    }
                }
                p += sprintf(p, "\033[0m   ");

                /* Informações de progresso à direita */
                if (row == 2) {
                    p += sprintf(p, "\033[1;37mInstalando o Simba OS\033[0m");
                } else if (row == 4) {
                    p += sprintf(p, "\033[0;37m%s\033[0m", etapa);
                } else if (row == 7) {
                    /* Barra de progresso em pixel art */
                    p += sprintf(p, "\033[38;2;200;200;202m");
                    for (int b = 0; b < filled; b++) p += sprintf(p, "█");
                    p += sprintf(p, "\033[38;2;36;36;38m");
                    for (int b = filled; b < bar_width; b++) p += sprintf(p, "█");
                    p += sprintf(p, "\033[0m  \033[1;37m%3d%%\033[0m", pct);
                } else if (row == 10) {
                    p += sprintf(p, "\033[38;2;95;95;93mo jogo não atrapalha a instalação  ·  pressione Esc para ver o log\033[0m");
                } else if (row == 12 && log_tail[0]) {
                    p += sprintf(p, "\033[38;2;70;70;72m› %-.55s\033[0m", log_tail);
                } else if (row == 15) {
                    if (finished) {
                        p += sprintf(p, "\033[1;32m★  INSTALAÇÃO CONCLUÍDA COM SUCESSO!  Pressione Enter  ★\033[0m");
                    } else {
                        p += sprintf(p, "\033[38;2;120;120;118mEspaço ou ↑  pular        Esc  esconder o jogo\033[0m");
                    }
                }
                p += sprintf(p, "\n");
            }
        } else {
            /* Modo log puro */
            p += sprintf(p, "\033[1;37m INSTALAÇÃO DO SIMBA OS \033[0m   Progresso: \033[1;33m%3d%%\033[0m   (Pressione Esc para voltar ao jogo)\n\n", pct);
            p += sprintf(p, "  Etapa atual: \033[1;37m%s\033[0m\n\n", etapa);
            p += sprintf(p, "  Últimas mensagens do log:\n");
            FILE *fl = fopen("/tmp/instalacao.log", "r");
            if (fl) {
                fseek(fl, -1500, SEEK_END);
                char lbuf[1500];
                size_t nr = fread(lbuf, 1, sizeof(lbuf) - 1, fl);
                if (nr > 0) {
                    lbuf[nr] = '\0';
                    char *line = strtok(lbuf, "\n");
                    int lc = 0;
                    while (line && lc < 25) {
                        p += sprintf(p, "  \033[0;37m%.120s\033[0m\n", line);
                        line = strtok(NULL, "\n");
                        lc++;
                    }
                }
                fclose(fl);
            }
        }

        /* Escreve o buffer completo de uma só vez */
        write(STDOUT_FILENO, out_buf, p - out_buf);

        frame++;
        usleep(FRAME_US);
    }

    restore_terminal();
    return 0;
}
