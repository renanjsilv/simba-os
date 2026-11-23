"""Visualizador do Simba Remoto no Windows (Tkinter): mostra a tela do outro computador e manda
mouse/teclado. A imagem é convertida já no tamanho da janela numa thread própria (quadros.py)."""
import asyncio
import logging
import queue
import threading
import time
import tkinter as tk
from typing import Optional

from . import tk_estilo as E
from .quadros import ConversorQuadros, caber

log = logging.getLogger("simba-remoto.visualizador_tk")

TECLAS_TK = {
    "Return": "Enter", "KP_Enter": "Enter", "BackSpace": "Backspace", "Tab": "Tab", "Escape": "Escape",
    "Delete": "Delete", "KP_Delete": "Delete", "Insert": "Insert", "Home": "Home", "End": "End",
    "Prior": "PageUp", "Next": "PageDown", "Up": "Up", "Down": "Down", "Left": "Left", "Right": "Right",
    "space": "Space", "Print": "Print", "App": "Menu", "Menu": "Menu",
    "Super_L": "Super", "Super_R": "Super", "Win_L": "Super", "Win_R": "Super",
    **{f"F{i}": f"F{i}" for i in range(1, 13)},
}
SO_MODIFICADORES = {"Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Caps_Lock",
                    "Num_Lock", "ISO_Level3_Shift", "Meta_L", "Meta_R"}


def _fmt(c):
    from .sinal import formatar_codigo
    return formatar_codigo(c)


class JanelaVisualizadorTk(tk.Toplevel):
    def __init__(self, pai, codigo: str, meu_nome: Optional[str] = None, servidor=None, loop=None):
        super().__init__(pai, bg=E.FUNDO)
        from .config import carregar_config
        self.codigo = "".join(c for c in codigo if c.isdigit())
        self.meu_nome = meu_nome or carregar_config().get("nome", "PC")
        self.title(f"Simba Remoto — {_fmt(self.codigo)}")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(E.px(1280), int(sw * 0.8)), min(E.px(800), int(sh * 0.8))
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 3)}")
        self.minsize(E.px(560), E.px(400))

        self.eventos = queue.Queue()
        self.servidor = servidor            # app já rodando: usa o loop e a DHT aquecida dele
        self.loop = loop
        self._loop_proprio = loop is None
        self.cliente = None
        self._geracao = None
        self._conectado = False
        self._tem_imagem = False
        self._fechando = False
        self._tela_cheia = False
        self._reconexoes = 0
        self._img = None
        self._item_img = None
        self._pendente = None              # (dados, w, h, w_orig, h_orig) vindo do conversor
        self._ret = (0, 0, 0, 0)            # onde a imagem está no canvas
        self._tam_orig = (0, 0)
        self._ultimo_mov = 0.0
        self._nome_remoto = _fmt(self.codigo)
        self.conversor = ConversorQuadros(self._quadro_convertido)

        self._montar()
        E.janela_escura(self)
        self.protocol("WM_DELETE_WINDOW", self.fechar)
        self._iniciar_loop()
        self._conectar()
        self.after(15, self._tique)

    # ------------------------------------------------------------------ interface
    def _montar(self):
        self.barra = tk.Frame(self, bg=E.CARTAO, highlightthickness=0)
        self.barra.pack(fill="x", side="top")
        self._separador = tk.Frame(self, bg=E.BORDA, height=1)
        self._separador.pack(fill="x", side="top")

        esq = tk.Frame(self.barra, bg=E.CARTAO)
        esq.pack(side="left", padx=E.px(14), pady=E.px(7))
        self.ponto = E.Ponto(esq, E.AVISO)
        self.ponto.pack(side="left", padx=(0, E.px(10)))
        txt = tk.Frame(esq, bg=E.CARTAO)
        txt.pack(side="left")
        self.lbl_nome = tk.Label(txt, text=self._nome_remoto, bg=E.CARTAO, fg=E.TEXTO, font=E.fonte(10, "bold"))
        self.lbl_nome.pack(anchor="w")
        self.lbl_estado = tk.Label(txt, text="Conectando…", bg=E.CARTAO, fg=E.APAGADO, font=E.fonte(8))
        self.lbl_estado.pack(anchor="w")
        self.lbl_sas = tk.Label(self.barra, text="", bg=E.CAMPO, fg=E.TEXTO, font=E.fonte(9, "bold"),
                                padx=E.px(10), pady=E.px(3))

        dir_ = tk.Frame(self.barra, bg=E.CARTAO)
        dir_.pack(side="right", padx=E.px(10))
        E.Botao(dir_, "Desconectar", self.fechar, estilo="perigo", tam=9, pady=5).pack(side="right", padx=(6, 0))
        self.bt_cheia = E.Botao(dir_, "Tela cheia", self._alternar_tela_cheia, estilo="plano", tam=9, pady=5)
        self.bt_cheia.pack(side="right", padx=3)
        self.bt_teclas = E.Botao(dir_, "Teclas ▾", self._menu_teclas, estilo="plano", tam=9, pady=5)
        self.bt_teclas.pack(side="right", padx=3)

        self.menu = tk.Menu(self, tearoff=0, bg=E.CARTAO, fg=E.TEXTO, activebackground=E.HOVER,
                            activeforeground=E.TEXTO, bd=0, font=E.fonte(9))
        for rot, k, mods in (("Ctrl + Alt + Del", "Delete", ["ctrl", "alt"]),
                             ("Tecla Windows / Super", "Super", []),
                             ("Alt + Tab", "Tab", ["alt"]),
                             ("Alt + F4", "F4", ["alt"]),
                             ("Ctrl + Shift + Esc", "Escape", ["ctrl", "shift"]),
                             ("Print Screen", "Print", [])):
            self.menu.add_command(label=rot, command=lambda k=k, m=mods: self._enviar_tecla(k, m))

        self.corpo = tk.Frame(self, bg=E.FUNDO)
        self.corpo.pack(fill="both", expand=True)

        # --- painel de estado (procurando / aguardando / erro)
        self.painel = tk.Frame(self.corpo, bg=E.FUNDO)
        caixa = E.Cartao(self.painel, padding=28)
        caixa.place(relx=0.5, rely=0.45, anchor="center")
        self.spinner = E.Carregando(caixa)
        self.spinner.pack(pady=(0, E.px(14)))
        self.lbl_titulo = tk.Label(caixa, text="Conectando…", bg=E.CARTAO, fg=E.TEXTO, font=E.fonte(14, "bold"))
        self.lbl_titulo.pack()
        self.lbl_desc = tk.Label(caixa, text="", bg=E.CARTAO, fg=E.APAGADO, font=E.fonte(9),
                                 wraplength=E.px(380), justify="center")
        self.lbl_desc.pack(pady=(E.px(6), 0))
        self.lbl_sas_grande = tk.Label(caixa, text="", bg=E.CARTAO, fg=E.TEXTO, font=E.fonte(22, "bold"))

        self.caixa_senha = tk.Frame(caixa, bg=E.CARTAO)
        tk.Frame(self.caixa_senha, bg=E.BORDA, height=1).pack(fill="x", pady=(E.px(16), E.px(14)))
        tk.Label(self.caixa_senha, text="Ou entre com a senha de acesso deste computador",
                 bg=E.CARTAO, fg=E.TEXTO, font=E.fonte(9, "bold")).pack(anchor="w")
        linha = tk.Frame(self.caixa_senha, bg=E.CARTAO)
        linha.pack(fill="x", pady=(E.px(8), 0))
        self.campo_senha = E.Campo(linha, dica="Senha", senha=True, width=26)
        self.campo_senha.pack(side="left", fill="x", expand=True)
        self.campo_senha.entrada.bind("<Return>", lambda e: self._enviar_senha())
        E.Botao(linha, "Entrar", self._enviar_senha, estilo="principal", peso="bold").pack(side="left", padx=(8, 0))
        self.var_salvar = tk.BooleanVar(value=True)
        tk.Checkbutton(self.caixa_senha, text="Lembrar neste computador", variable=self.var_salvar,
                       bg=E.CARTAO, fg=E.APAGADO, selectcolor=E.CAMPO, activebackground=E.CARTAO,
                       activeforeground=E.TEXTO, font=E.fonte(8), bd=0, highlightthickness=0
                       ).pack(anchor="w", pady=(E.px(6), 0))

        self.botoes_painel = tk.Frame(caixa, bg=E.CARTAO)
        self.botoes_painel.pack(pady=(E.px(18), 0))
        self.bt_tentar = E.Botao(self.botoes_painel, "Tentar de novo", self._tentar_de_novo, estilo="principal",
                                 peso="bold")
        self.bt_cancelar = E.Botao(self.botoes_painel, "Cancelar", self.fechar)
        self.bt_cancelar.pack(side="left", padx=4)
        self.painel.pack(fill="both", expand=True)

        # --- tela remota
        self.canvas = tk.Canvas(self.corpo, bg="#000000", highlightthickness=0, cursor="arrow", takefocus=1)
        c = self.canvas
        c.bind("<Motion>", self._mover)
        for n, b in ((1, "esq"), (2, "meio"), (3, "dir")):
            c.bind(f"<ButtonPress-{n}>", lambda e, b=b: self._botao(e, b, "desce"))
            c.bind(f"<ButtonRelease-{n}>", lambda e, b=b: self._botao(e, b, "sobe"))
        c.bind("<MouseWheel>", self._roda)
        c.bind("<Shift-MouseWheel>", lambda e: self._roda(e, horizontal=True))
        c.bind("<Button-4>", lambda e: self._rolar(0, 1))
        c.bind("<Button-5>", lambda e: self._rolar(0, -1))
        c.bind("<Configure>", self._redimensionou)
        c.bind("<KeyPress>", self._tecla)
        c.bind("<Enter>", lambda e: c.focus_set())
        self.lbl_aguarda_img = tk.Label(self.corpo, text="Recebendo a imagem…", bg="#000000", fg=E.APAGADO,
                                        font=E.fonte(11))
        self.bind("<F11>", lambda e: self._alternar_tela_cheia())

    def _painel(self, titulo, desc="", ocupado=True, senha=False, erro=False, sas=None):
        self.lbl_titulo.config(text=titulo)
        self.lbl_desc.config(text=desc)
        if ocupado:
            self.spinner.pack(pady=(0, E.px(14)), before=self.lbl_titulo)
            self.spinner.iniciar()
        else:
            self.spinner.parar()
            self.spinner.pack_forget()
        if sas:
            self.lbl_sas_grande.config(text=sas)
            self.lbl_sas_grande.pack(pady=(E.px(10), 0), after=self.lbl_desc)
        else:
            self.lbl_sas_grande.pack_forget()
        if senha:
            self.caixa_senha.pack(fill="x", before=self.botoes_painel)
        else:
            self.caixa_senha.pack_forget()
        self.bt_tentar.pack_forget()
        self.bt_cancelar.config(text="Fechar" if erro else "Cancelar")
        if erro:
            self.bt_tentar.pack(side="left", padx=4, before=self.bt_cancelar)
        if not self.painel.winfo_ismapped():
            self.canvas.pack_forget()
            self.lbl_aguarda_img.place_forget()
            self.painel.pack(fill="both", expand=True)

    def _mostrar_tela(self):
        if self.painel.winfo_ismapped():
            self.painel.pack_forget()
            self.spinner.parar()
            self.canvas.pack(fill="both", expand=True)
        if not self._tem_imagem:
            self.lbl_aguarda_img.place(relx=0.5, rely=0.5, anchor="center")
        self.canvas.focus_set()

    def _menu_teclas(self):
        x = self.bt_teclas.winfo_rootx()
        y = self.bt_teclas.winfo_rooty() + self.bt_teclas.winfo_height()
        self.menu.tk_popup(x, y)

    def _alternar_tela_cheia(self):
        self._tela_cheia = not self._tela_cheia
        self.attributes("-fullscreen", self._tela_cheia)
        if self._tela_cheia:
            self._esconder_barra()
            self.bt_cheia.config(text="Sair da tela cheia")
        else:
            self._mostrar_barra()
            self.bt_cheia.config(text="Tela cheia")
        self.canvas.focus_set()

    def _mostrar_barra(self):
        if not self.barra.winfo_ismapped():
            self.barra.pack(fill="x", side="top", before=self.corpo)
            self._separador.pack(fill="x", side="top", before=self.corpo)

    def _esconder_barra(self):
        self.barra.pack_forget()
        self._separador.pack_forget()

    # ------------------------------------------------------------------ conexão
    def _iniciar_loop(self):
        if self.loop is not None:
            return
        pronto = threading.Event()

        def rodar():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            pronto.set()
            self.loop.run_forever()
        threading.Thread(target=rodar, daemon=True, name="cliente-remoto").start()
        pronto.wait()

    def _conectar(self, ficha=None):
        from .cliente import ConexaoCliente
        from .config import obter_senha_remota
        senha_salva = obter_senha_remota(self.codigo)
        self._conectado = False
        self._tem_imagem = False
        if ficha:
            self._painel("Reconectando…", "A conexão caiu; retomando automaticamente.")
        else:
            self._painel("Procurando o computador…",
                         "Na rede local e na rede P2P mundial. Pode levar alguns segundos.")
        gen = object()
        self._geracao = gen

        def evento(t, d, gen=gen):
            self.eventos.put(("evento", gen, t, d))

        def criar():
            preparo, ip = None, None
            if self.servidor is not None:
                try:
                    preparo = self.servidor.preaquecer(self.codigo)
                    ip = self.servidor.vizinhos.get(self.codigo, {}).get("ip")
                except Exception as e:
                    log.debug("preaquecer: %s", e)
            c = ConexaoCliente(codigo=self.codigo, meu_nome=self.meu_nome, ficha=ficha,
                               on_evento=evento, on_quadro=self.conversor.novo_quadro, loop=self.loop,
                               preparo=preparo, ip_vizinho=ip)
            if senha_salva:
                try:
                    c.chave_senha = bytes.fromhex(senha_salva)
                except ValueError:
                    pass
            self.cliente = c
            asyncio.ensure_future(c.iniciar())
        self.loop.call_soon_threadsafe(criar)

    def _tentar_de_novo(self):
        self._reconexoes = 0
        self._encerrar_cliente()
        self._conectar()

    def _encerrar_cliente(self):
        c = self.cliente
        self.cliente = None
        self._geracao = None
        if c and self.loop:
            asyncio.run_coroutine_threadsafe(c.fechar(), self.loop)

    def fechar(self):
        if self._fechando:
            return
        self._fechando = True
        c = self.cliente
        self.cliente = None
        self.conversor.parar()
        if c and self.loop:
            try:
                asyncio.run_coroutine_threadsafe(c.fechar(), self.loop).result(3)
            except Exception:
                pass
        if self.loop and self._loop_proprio:
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.destroy()

    def _enviar_senha(self):
        s = self.campo_senha.get()
        if not s or not self.cliente:
            return
        from .sinal import chave_senha
        if self.var_salvar.get():
            from .config import salvar_senha_remota
            salvar_senha_remota(self.codigo, chave_senha(s, self.codigo).hex())
        self.campo_senha.limpar()
        self._painel("Conferindo a senha…", "")
        asyncio.run_coroutine_threadsafe(self.cliente.entrar_com_senha(s), self.loop)

    # ------------------------------------------------------------------ laço da interface
    def _quadro_convertido(self, dados, w, h, wo, ho):       # thread do conversor
        self._pendente = (dados, w, h, wo, ho)

    def _tique(self):
        if self._fechando:
            return
        try:
            while True:
                _, gen, t, d = self.eventos.get_nowait()
                if gen is self._geracao:
                    try:
                        self._evento(t, d)
                    except Exception:
                        log.exception("evento %s", t)
        except queue.Empty:
            pass
        p = self._pendente
        if p is not None:
            self._pendente = None
            self._desenhar(*p)
        self.after(15, self._tique)

    def _desenhar(self, dados, w, h, wo, ho):
        if not self._conectado:
            return
        if (wo, ho) != self._tam_orig:
            primeiro = self._tam_orig == (0, 0)
            self._tam_orig = (wo, ho)
            self._redimensionou()
            if primeiro and (w, h) != self.conversor._tamanho:
                return          # o próximo quadro já vem no tamanho certo
        try:
            img = tk.PhotoImage(master=self, data=b"P6 %d %d 255\n" % (w, h) + dados, format="PPM")
        except tk.TclError as e:
            log.warning("quadro inválido: %s", e)
            return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if self._item_img is None:
            self._item_img = self.canvas.create_image(cw // 2, ch // 2, image=img, anchor="center")
        else:
            self.canvas.itemconfig(self._item_img, image=img)
            self.canvas.coords(self._item_img, cw // 2, ch // 2)
        self._img = img
        self._ret = (cw // 2 - w // 2, ch // 2 - h // 2, w, h)
        if not self._tem_imagem:
            self._tem_imagem = True
            self.lbl_aguarda_img.place_forget()

    def _redimensionou(self, _e=None):
        wo, ho = self._tam_orig
        if not wo:
            return
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        _, _, w, h = caber(wo, ho, cw, ch)
        if w > 0:
            self.conversor.definir_tamanho(w, h)
        if self._item_img is not None:
            self.canvas.coords(self._item_img, cw // 2, ch // 2)
            if self._img is not None:
                iw, ih = self._img.width(), self._img.height()
                self._ret = (cw // 2 - iw // 2, ch // 2 - ih // 2, iw, ih)

    def _evento(self, tipo, d):
        log.info("visualizador: %s %s", tipo, {k: v for k, v in d.items() if k != "k"})
        if tipo == "aguardando_pc":
            self._painel("Aguardando aceitarem do outro lado…",
                         "Alguém no outro computador precisa clicar em Aceitar.")
        elif tipo == "pedir_senha":
            if not self.caixa_senha.winfo_ismapped():
                self._painel("Aguardando aceitarem do outro lado…",
                             "Alguém no outro computador precisa clicar em Aceitar.", senha=True)
                self.campo_senha.entrada.focus_set()
        elif tipo == "senha_errada":
            from .config import remover_senha_remota
            remover_senha_remota(self.codigo)
            motivo = d.get("motivo", "")
            self._painel("Senha incorreta", motivo if "muitas" in motivo else
                         "Confira a senha de acesso do outro computador.", ocupado=False, senha=True)
            self.campo_senha.entrada.focus_set()
        elif tipo == "conectando":
            if d.get("nome"):
                self._nome_remoto = d["nome"]
                self.lbl_nome.config(text=d["nome"])
            self._painel("Conectando…", "Abrindo o caminho direto entre os computadores. "
                                        "O código abaixo deve ser igual ao mostrado do outro lado.",
                         sas=d.get("sas"))
        elif tipo == "conectado":
            from .config import salvar_recente
            self._conectado = True
            self._reconexoes = 0
            self.ponto.cor(E.OK)
            self.lbl_estado.config(text=f"Conectado • {d.get('caminho', 'P2P')}")
            if d.get("sas"):
                self.lbl_sas.config(text=f"Verificação  {d['sas']}")
                self.lbl_sas.pack(side="left", padx=E.px(6))
            salvar_recente(self.codigo, d.get("nome") or self._nome_remoto)
            self._mostrar_tela()
        elif tipo == "tela":
            if d.get("nome"):
                from .config import salvar_recente
                self._nome_remoto = d["nome"]
                self.lbl_nome.config(text=d["nome"])
                self.title(f"{d['nome']} — Simba Remoto")
                salvar_recente(self.codigo, d["nome"])
        elif tipo == "recusado":
            self._fim("Conexão recusada", d.get("motivo") or "O outro computador recusou o pedido.", "Recusado")
        elif tipo == "erro":
            self._fim("Não foi possível conectar", d.get("texto", ""), "Falhou")
        elif tipo == "desconectado":
            ficha = self.cliente.ficha_recebida if self.cliente else None
            if d.get("caiu") and ficha and self._reconexoes < 3:
                self._reconexoes += 1
                self._conectado = False
                self._tam_orig = (0, 0)
                self.ponto.cor(E.AVISO)
                self._encerrar_cliente()
                self._conectar(ficha=ficha)
                return
            self._fim("Conexão encerrada", d.get("texto", ""), "Desconectado")

    def _fim(self, titulo, texto, estado):
        self._conectado = False
        self._tam_orig = (0, 0)
        self.ponto.cor(E.PERIGO if estado != "Desconectado" else E.APAGADO)
        self.lbl_estado.config(text=estado)
        self.lbl_sas.pack_forget()
        if self._tela_cheia:
            self._alternar_tela_cheia()
        self._painel(titulo, texto, ocupado=False, erro=True)

    # ------------------------------------------------------------------ entrada
    def _norm(self, x, y):
        rx, ry, rw, rh = self._ret
        if rw <= 0 or rh <= 0:
            return None, None
        return max(0.0, min(1.0, (x - rx) / rw)), max(0.0, min(1.0, (y - ry) / rh))

    def _mover(self, e):
        if self._tela_cheia:
            if e.y <= 2:
                self._mostrar_barra()
            elif self.barra.winfo_ismapped() and e.y > E.px(60):
                self._esconder_barra()
        if not (self.cliente and self._conectado):
            return
        agora = time.monotonic()
        if agora - self._ultimo_mov < 0.012:
            return
        self._ultimo_mov = agora
        nx, ny = self._norm(e.x, e.y)
        if nx is not None:
            self.cliente.mover(nx, ny)

    def _botao(self, e, qual, acao):
        self.canvas.focus_set()
        if not (self.cliente and self._conectado):
            return
        nx, ny = self._norm(e.x, e.y)
        self.cliente.botao(qual, acao, nx, ny)

    def _roda(self, e, horizontal=False):
        passos = int(e.delta / 120) or (1 if e.delta > 0 else -1)
        self._rolar(passos if horizontal else 0, 0 if horizontal else passos)

    def _rolar(self, dx, dy):
        if self.cliente and self._conectado:
            self.cliente.rolar(dx, dy)

    def _enviar_tecla(self, k, mods):
        if self.cliente and self._conectado:
            self.cliente.tecla(k, mods=mods)
        self.canvas.focus_set()

    def _tecla(self, e):
        if not (self.cliente and self._conectado):
            return "break"
        if e.keysym == "F11":
            self._alternar_tela_cheia()
            return "break"
        if e.keysym in SO_MODIFICADORES:
            return "break"
        windows = self.tk.call("tk", "windowingsystem") == "win32"
        mods = []
        if e.state & 0x4:
            mods.append("ctrl")
        # Alt: bit 0x20000 no Windows, Mod1 (0x8) no X11
        if (e.state & 0x20000) if windows else (e.state & 0x8):
            mods.append("alt")
        if e.state & 0x1:
            mods.append("shift")
        if e.keysym in TECLAS_TK:
            self.cliente.tecla(TECLAS_TK[e.keysym], mods=mods)
            return "break"
        # AltGr no Windows chega como Ctrl+Alt com o caractere já pronto (ex.: @, €)
        altgr = "ctrl" in mods and "alt" in mods
        if e.char and e.char.isprintable() and (not mods or mods == ["shift"] or altgr):
            self.cliente.texto(e.char)
            return "break"
        if "ctrl" in mods or "alt" in mods:
            k = e.keysym.lower() if len(e.keysym) == 1 else ""
            if not k and windows and 65 <= e.keycode <= 90:
                k = chr(e.keycode).lower()
            if k:
                self.cliente.tecla(k, mods=mods)
        return "break"
