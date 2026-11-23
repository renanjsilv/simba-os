"""Visual do Simba Remoto no Windows (Tkinter): cores, escala de DPI e componentes simples
(botão plano com hover, cartão com borda, campo com dica, interruptor, ponto de estado)."""
import sys
import tkinter as tk

FUNDO = "#131417"
CARTAO = "#1c1d21"
BORDA = "#2a2c31"
CAMPO = "#25272c"
HOVER = "#2c2e34"
TEXTO = "#ececea"
APAGADO = "#8e9097"
ACENTO = "#e8e8e6"         # botão principal claro (cinza/branco, identidade do Simba)
ACENTO_TXT = "#111214"
PERIGO = "#c2453f"
OK = "#79c47f"
AVISO = "#e0a060"
FONTE = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"
MONO = "Cascadia Mono" if sys.platform == "win32" else "DejaVu Sans Mono"

_ESCALA = [1.0]


def configurar_dpi():
    """Deve ser chamado ANTES de criar o Tk: pixels reais em telas com escala 125%/150%."""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                import ctypes
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


def iniciar_escala(root):
    try:
        _ESCALA[0] = max(1.0, root.winfo_fpixels("1i") / 96.0)
    except Exception:
        _ESCALA[0] = 1.0
    return _ESCALA[0]


def px(n):
    """Converte medidas pensadas para 100% de escala."""
    return int(round(n * _ESCALA[0]))


def fonte(tam, peso="normal"):
    return (FONTE, tam, peso) if peso != "normal" else (FONTE, tam)


def janela_escura(janela):
    """Barra de título escura no Windows 10/11."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        janela.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(janela.winfo_id())
        v = ctypes.c_int(1)
        for attr in (20, 19):      # DWMWA_USE_IMMERSIVE_DARK_MODE (novo, antigo)
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(v), ctypes.sizeof(v)) == 0:
                break
    except Exception:
        pass


class Botao(tk.Label):
    """Botão plano com hover (tk.Button no Windows ignora boa parte das cores)."""

    ESTILOS = {
        "normal": (CAMPO, TEXTO, HOVER),
        "principal": (ACENTO, ACENTO_TXT, "#ffffff"),
        "perigo": (PERIGO, "#ffffff", "#d4554e"),
        "plano": (None, TEXTO, HOVER),
        "fantasma": (None, APAGADO, HOVER),
    }

    def __init__(self, pai, texto, comando=None, estilo="normal", tam=10, peso="normal",
                 padx=14, pady=7, **kw):
        fundo, cor, hover = self.ESTILOS[estilo]
        self._fundo = fundo or pai.cget("bg")
        self._hover = hover
        self._cor = cor
        self._comando = comando
        self._ativo = True
        super().__init__(pai, text=texto, bg=self._fundo, fg=cor, font=fonte(tam, peso),
                         padx=px(padx), pady=px(pady), cursor="hand2", **kw)
        self.bind("<Enter>", lambda e: self._ativo and self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._fundo))
        self.bind("<ButtonRelease-1>", self._clique)

    def _clique(self, e):
        if not self._ativo or not self._comando:
            return
        # só dispara se soltou em cima do botão
        if 0 <= e.x < self.winfo_width() and 0 <= e.y < self.winfo_height():
            self._comando()

    def ativar(self, sim=True):
        self._ativo = sim
        self.config(fg=self._cor if sim else APAGADO, cursor="hand2" if sim else "arrow")


class Cartao(tk.Frame):
    def __init__(self, pai, padding=18, **kw):
        super().__init__(pai, bg=CARTAO, highlightthickness=1, highlightbackground=BORDA,
                         highlightcolor=BORDA, padx=px(padding), pady=px(padding - 2), **kw)


class Campo(tk.Frame):
    """Entrada com borda que acende no foco e texto de dica."""

    def __init__(self, pai, dica="", tam=11, peso="normal", senha=False, centro=False, **kw):
        super().__init__(pai, bg=CAMPO, highlightthickness=1, highlightbackground=BORDA,
                         highlightcolor="#5a5d66")
        self.dica = dica
        self._senha = senha
        self._mostrando_dica = False
        self.entrada = tk.Entry(self, bg=CAMPO, fg=TEXTO, insertbackground=TEXTO, relief="flat",
                                font=fonte(tam, peso), justify="center" if centro else "left",
                                disabledbackground=CAMPO, **kw)
        self.entrada.pack(fill="x", padx=px(10), pady=px(8))
        self.entrada.bind("<FocusIn>", self._foco)
        self.entrada.bind("<FocusOut>", self._sem_foco)
        self.bind("<Button-1>", lambda e: self.entrada.focus_set())
        self._sem_foco()

    def _foco(self, _e=None):
        self.config(highlightbackground="#5a5d66")
        if self._mostrando_dica:
            self.entrada.delete(0, tk.END)
            self.entrada.config(fg=TEXTO, show="•" if self._senha else "")
            self._mostrando_dica = False

    def _sem_foco(self, _e=None):
        self.config(highlightbackground=BORDA)
        if not self.entrada.get() and self.dica:
            self._mostrando_dica = True
            self.entrada.config(fg=APAGADO, show="")
            self.entrada.insert(0, self.dica)
        elif self._senha:
            self.entrada.config(show="•")

    def get(self):
        return "" if self._mostrando_dica else self.entrada.get()

    def set(self, texto):
        self._foco()
        self.entrada.delete(0, tk.END)
        self.entrada.insert(0, texto)

    def limpar(self):
        self.entrada.delete(0, tk.END)
        if self.focus_get() is not self.entrada:
            self._sem_foco()


class Interruptor(tk.Canvas):
    """Interruptor liga/desliga desenhado (o Checkbutton do Tk fica feio no tema escuro)."""

    def __init__(self, pai, valor=False, ao_mudar=None):
        self.w, self.h = px(40), px(22)
        super().__init__(pai, width=self.w, height=self.h, bg=pai.cget("bg"), highlightthickness=0,
                         cursor="hand2")
        self.valor = valor
        self.ao_mudar = ao_mudar
        self.bind("<Button-1>", lambda e: self._alternar())
        self._desenhar()

    def _desenhar(self):
        self.delete("all")
        w, h, r = self.w, self.h, self.h // 2
        cor = ACENTO if self.valor else "#3a3c42"
        self.create_oval(0, 0, h, h, fill=cor, outline=cor)
        self.create_oval(w - h, 0, w, h, fill=cor, outline=cor)
        self.create_rectangle(r, 0, w - r, h, fill=cor, outline=cor)
        m = px(3)
        x = w - h + m if self.valor else m
        bola = ACENTO_TXT if self.valor else "#c9cacd"
        self.create_oval(x, m, x + h - 2 * m, h - m, fill=bola, outline=bola)

    def definir(self, valor):
        self.valor = bool(valor)
        self._desenhar()

    def _alternar(self):
        self.definir(not self.valor)
        if self.ao_mudar:
            self.ao_mudar(self.valor)


class Ponto(tk.Canvas):
    """Bolinha de estado (verde/âmbar/cinza)."""

    def __init__(self, pai, cor=APAGADO, tam=9):
        t = px(tam)
        super().__init__(pai, width=t, height=t, bg=pai.cget("bg"), highlightthickness=0)
        self._oval = self.create_oval(0, 0, t - 1, t - 1, fill=cor, outline=cor)

    def cor(self, c):
        self.itemconfig(self._oval, fill=c, outline=c)


class Carregando(tk.Canvas):
    """Indicador de atividade (arco girando)."""

    def __init__(self, pai, tam=34):
        t = px(tam)
        super().__init__(pai, width=t, height=t, bg=pai.cget("bg"), highlightthickness=0)
        m = px(3)
        self.create_oval(m, m, t - m, t - m, outline="#2e3036", width=px(3))
        self._arco = self.create_arc(m, m, t - m, t - m, start=0, extent=90, style="arc",
                                     outline=TEXTO, width=px(3))
        self._ang = 0
        self._rodando = False

    def iniciar(self):
        if not self._rodando:
            self._rodando = True
            self._girar()

    def parar(self):
        self._rodando = False

    def _girar(self):
        if not self._rodando or not self.winfo_exists():
            return
        self._ang = (self._ang - 12) % 360
        self.itemconfig(self._arco, start=self._ang)
        self.after(33, self._girar)
