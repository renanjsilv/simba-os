"""Janela do Simba Remoto para Windows (Tkinter). Mesmo servidor/protocolo da versão do Simba OS.

A janela abre na hora: o servidor (aiortc/av/numpy, pesados) é importado e iniciado numa thread."""
import asyncio
import logging
import os
import queue
import sys
import threading
import tkinter as tk

from . import tk_estilo as E
from .config import (carregar_config, definir_senha, novo_codigo, obter_recentes, remover_recente,
                     salvar_config)
from .sinal import formatar_codigo

log = logging.getLogger("simba-remoto")
VERSAO = "1.8"


def _recurso(nome):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, nome)


def _centralizar(janela, pai=None):
    janela.update_idletasks()
    w, h = janela.winfo_reqwidth(), janela.winfo_reqheight()
    if pai is not None and pai.winfo_ismapped():
        x = pai.winfo_rootx() + (pai.winfo_width() - w) // 2
        y = pai.winfo_rooty() + (pai.winfo_height() - h) // 3
    else:
        x = (janela.winfo_screenwidth() - w) // 2
        y = (janela.winfo_screenheight() - h) // 3
    janela.geometry(f"+{max(0, x)}+{max(0, y)}")


class App:
    def __init__(self, codigo_inicial=None):
        E.configurar_dpi()
        self.root = tk.Tk()
        E.iniciar_escala(self.root)
        self.root.withdraw()
        self.root.title("Simba Remoto")
        self.root.configure(bg=E.FUNDO)
        try:
            self.icone = tk.PhotoImage(file=_recurso("simba.png"))
            self.root.iconphoto(True, self.icone)
            fator = max(1, self.icone.width() // E.px(40))
            self.icone_peq = self.icone.subsample(fator) if fator > 1 else self.icone
        except Exception:
            self.icone = self.icone_peq = None
        if sys.platform == "win32":
            try:
                self.root.iconbitmap(default=_recurso("simba.ico"))
            except Exception:
                pass

        self.eventos = queue.Queue()
        self.loop = None
        self.servidor = None
        self.dialogo = None
        self.cfg = carregar_config()

        self._montar()
        self.root.update_idletasks()
        largura = E.px(460)
        self.root.minsize(largura, 0)
        self.root.geometry(f"{largura}x{self.root.winfo_reqheight()}")
        _centralizar(self.root)
        self.root.deiconify()
        E.janela_escura(self.root)
        self.root.protocol("WM_DELETE_WINDOW", self._sair)
        self.root.after(80, self._processar_eventos)
        # o servidor começa depois que a janela já apareceu
        self.root.after(50, self._iniciar_servidor)
        if codigo_inicial:
            self.root.after(300, lambda: self._conectar(codigo_inicial))

    # ------------------------------------------------------------------ interface
    def _montar(self):
        r = self.root
        base = tk.Frame(r, bg=E.FUNDO, padx=E.px(18), pady=E.px(14))
        base.pack(fill="both", expand=True)
        self.base = base

        # cabeçalho
        cab = tk.Frame(base, bg=E.FUNDO)
        cab.pack(fill="x", pady=(0, E.px(14)))
        if self.icone_peq:
            tk.Label(cab, image=self.icone_peq, bg=E.FUNDO).pack(side="left", padx=(0, E.px(10)))
        t = tk.Frame(cab, bg=E.FUNDO)
        t.pack(side="left")
        tk.Label(t, text="Simba Remoto", bg=E.FUNDO, fg=E.TEXTO, font=E.fonte(15, "bold")).pack(anchor="w")
        tk.Label(t, text="Acesso remoto direto, sem servidor", bg=E.FUNDO, fg=E.APAGADO,
                 font=E.fonte(9)).pack(anchor="w")
        self.bt_menu = E.Botao(cab, "⋯", self._abrir_menu, estilo="fantasma", tam=14, padx=10, pady=0)
        self.bt_menu.pack(side="right")
        self.menu = tk.Menu(r, tearoff=0, bg=E.CARTAO, fg=E.TEXTO, activebackground=E.HOVER,
                            activeforeground=E.TEXTO, bd=0, font=E.fonte(9))
        self.menu.add_command(label="Gerar novo endereço", command=self._novo_codigo)
        self.menu.add_command(label="Sobre o Simba Remoto", command=self._sobre)
        self.menu.add_separator()
        self.menu.add_command(label="Sair", command=self._sair)

        # --- acessar outro computador
        c = E.Cartao(base)
        c.pack(fill="x", pady=(0, E.px(12)))
        tk.Label(c, text="Acessar outro computador", bg=E.CARTAO, fg=E.TEXTO,
                 font=E.fonte(11, "bold")).pack(anchor="w")
        tk.Label(c, text="Digite o endereço de 9 dígitos que aparece no outro computador",
                 bg=E.CARTAO, fg=E.APAGADO, font=E.fonte(9)).pack(anchor="w", pady=(E.px(2), E.px(10)))
        linha = tk.Frame(c, bg=E.CARTAO)
        linha.pack(fill="x")
        self.campo_codigo = E.Campo(linha, dica="000 000 000", tam=16, peso="bold", centro=True, width=12)
        self.campo_codigo.pack(side="left", fill="x", expand=True)
        self.campo_codigo.entrada.bind("<KeyRelease>", self._formatar_codigo)
        self.campo_codigo.entrada.bind("<Return>", lambda e: self._conectar())
        self.bt_conectar = E.Botao(linha, "Conectar", self._conectar, estilo="principal", tam=11, peso="bold",
                                   padx=20, pady=11)
        self.bt_conectar.pack(side="left", padx=(E.px(8), 0), fill="y")
        self.lbl_aviso_codigo = tk.Label(c, text="", bg=E.CARTAO, fg=E.AVISO, font=E.fonte(8))
        self.lbl_aviso_codigo.pack(anchor="w")
        self.caixa_vizinhos = tk.Frame(c, bg=E.CARTAO)
        self.caixa_vizinhos.pack(fill="x")
        self.vizinhos = []
        self.caixa_recentes = tk.Frame(c, bg=E.CARTAO)
        self.caixa_recentes.pack(fill="x")
        self._atualizar_recentes()

        # --- este computador
        c = E.Cartao(base)
        c.pack(fill="x", pady=(0, E.px(12)))
        topo = tk.Frame(c, bg=E.CARTAO)
        topo.pack(fill="x")
        tk.Label(topo, text="Este computador", bg=E.CARTAO, fg=E.TEXTO, font=E.fonte(11, "bold")).pack(side="left")
        self.bt_copiar = E.Botao(topo, "Copiar", self._copiar, estilo="plano", tam=9, padx=10, pady=3)
        self.bt_copiar.pack(side="right")
        tk.Label(c, text="Passe este endereço para quem vai acessar", bg=E.CARTAO, fg=E.APAGADO,
                 font=E.fonte(9)).pack(anchor="w", pady=(E.px(2), 0))
        self.lbl_codigo = tk.Label(c, text=formatar_codigo(self.cfg["codigo"]), bg=E.CARTAO, fg=E.TEXTO,
                                   font=E.fonte(26, "bold"))
        self.lbl_codigo.pack(pady=(E.px(8), E.px(8)))

        est = tk.Frame(c, bg=E.CAMPO, padx=E.px(12), pady=E.px(9))
        est.pack(fill="x")
        self.ponto_estado = E.Ponto(est, E.AVISO)
        self.ponto_estado.pack(side="left", padx=(0, E.px(10)))
        tx = tk.Frame(est, bg=E.CAMPO)
        tx.pack(side="left", fill="x", expand=True)
        self.lbl_estado = tk.Label(tx, text="Iniciando…", bg=E.CAMPO, fg=E.TEXTO, font=E.fonte(10, "bold"),
                                   anchor="w")
        self.lbl_estado.pack(fill="x")
        self.lbl_sub_estado = tk.Label(tx, text="Entrando na rede P2P", bg=E.CAMPO, fg=E.APAGADO,
                                       font=E.fonte(8), anchor="w", justify="left", wraplength=E.px(300))
        self.lbl_sub_estado.pack(fill="x")
        self.bt_desconectar = E.Botao(est, "Desconectar", self._desconectar, estilo="perigo", tam=9, pady=4)

        # acesso sem supervisão
        tk.Frame(c, bg=E.BORDA, height=1).pack(fill="x", pady=(E.px(14), E.px(12)))
        a = tk.Frame(c, bg=E.CARTAO)
        a.pack(fill="x")
        txa = tk.Frame(a, bg=E.CARTAO)
        txa.pack(side="left", fill="x", expand=True)
        tk.Label(txa, text="Acesso sem supervisão", bg=E.CARTAO, fg=E.TEXTO, font=E.fonte(10)).pack(anchor="w")
        self.lbl_senha = tk.Label(txa, text="", bg=E.CARTAO, fg=E.APAGADO, font=E.fonte(8), cursor="hand2")
        self.lbl_senha.pack(anchor="w")
        self.lbl_senha.bind("<Button-1>", lambda e: self._dialogo_senha())
        self.interruptor = E.Interruptor(a, ao_mudar=self._alternar_auto)
        self.interruptor.pack(side="right")
        self._atualizar_senha()

        # --- rede (compacto)
        rede = tk.Frame(base, bg=E.FUNDO)
        rede.pack(fill="x")
        self.rede = {}
        for i, (chave, nome) in enumerate((("lan", "Rede local"), ("dht", "Rede P2P"), ("ipv6", "IPv6"),
                                           ("upnp", "UPnP"), ("stun", "NAT"))):
            f = tk.Frame(rede, bg=E.FUNDO)
            f.pack(side="left", padx=(0, E.px(12)))
            p = E.Ponto(f, "#3a3c42", tam=7)
            p.pack(side="left", padx=(0, E.px(5)))
            lb = tk.Label(f, text=nome, bg=E.FUNDO, fg=E.APAGADO, font=E.fonte(8))
            lb.pack(side="left")
            self.rede[chave] = (p, lb, nome)
        self.lbl_rede = tk.Label(base, text="", bg=E.FUNDO, fg="#6c6e75", font=E.fonte(8), anchor="w",
                                 justify="left", wraplength=E.px(420))
        self.lbl_rede.pack(fill="x", pady=(E.px(4), 0))
        self.detalhes_rede = {}

    def _abrir_menu(self):
        self.menu.tk_popup(self.bt_menu.winfo_rootx(), self.bt_menu.winfo_rooty() + self.bt_menu.winfo_height())

    def _sobre(self):
        d = self._dialogo_base("Sobre")
        tk.Label(d.caixa, text=f"Simba Remoto {VERSAO}", bg=E.CARTAO, fg=E.TEXTO,
                 font=E.fonte(13, "bold")).pack(anchor="w")
        tk.Label(d.caixa, text="Acesso remoto P2P sem servidor: a conexão é encontrada pela rede local ou pela "
                               "DHT do BitTorrent e vai direto entre os computadores, com criptografia de ponta "
                               "a ponta (WebRTC/DTLS).\n\nSimba OS",
                 bg=E.CARTAO, fg=E.APAGADO, font=E.fonte(9), wraplength=E.px(340), justify="left"
                 ).pack(anchor="w", pady=(E.px(6), E.px(14)))
        E.Botao(d.caixa, "Fechar", d.destroy, estilo="principal").pack(anchor="e")
        _centralizar(d, self.root)

    # ------------------------------------------------------------------ acessar
    def _formatar_codigo(self, e=None):
        if e is not None and e.keysym in ("Left", "Right", "Home", "End", "Tab", "Return"):
            return
        ent = self.campo_codigo.entrada
        if self.campo_codigo._mostrando_dica:
            return
        d = "".join(c for c in ent.get() if c.isdigit())[:9]
        fmt = " ".join(d[i:i + 3] for i in range(0, len(d), 3))
        if fmt != ent.get():
            ent.delete(0, tk.END)
            ent.insert(0, fmt)
            ent.icursor(tk.END)
        self.lbl_aviso_codigo.config(text="")
        if len(d) == 9:
            self._preaquecer(d)         # enquanto a pessoa vai até o botão, o caminho já é preparado

    def _preaquecer(self, codigo):
        if self.loop and self.servidor and getattr(self.servidor, "canal", None):
            self.loop.call_soon_threadsafe(self.servidor.preaquecer, codigo)

    def _conectar(self, codigo=None):
        texto = codigo if codigo is not None else self.campo_codigo.get()
        d = "".join(c for c in texto if c.isdigit())
        if len(d) != 9:
            self.lbl_aviso_codigo.config(text="O endereço tem 9 dígitos.")
            self.campo_codigo.entrada.focus_set()
            return
        if d == self.cfg.get("codigo"):
            self.lbl_aviso_codigo.config(text="Esse é o endereço deste próprio computador.")
            return
        self.lbl_aviso_codigo.config(text="")
        from .visualizador_tk import JanelaVisualizadorTk
        pronto = bool(self.loop and self.servidor and getattr(self.servidor, "canal", None))
        v = JanelaVisualizadorTk(self.root, d, self.cfg.get("nome"),
                                 servidor=self.servidor if pronto else None, loop=self.loop if pronto else None)
        v.bind("<Destroy>", lambda e: e.widget is v and self.root.after(200, self._atualizar_recentes), add="+")
        self.root.after(1500, self._atualizar_recentes)

    def _atualizar_vizinhos(self, lista):
        self.vizinhos = lista
        for w in self.caixa_vizinhos.winfo_children():
            w.destroy()
        self.caixa_vizinhos.configure(height=1)      # Tk não encolhe um quadro que ficou vazio
        if lista:
            tk.Label(self.caixa_vizinhos, text="NESTA REDE", bg=E.CARTAO, fg="#6c6e75",
                     font=E.fonte(7, "bold")).pack(anchor="w", pady=(E.px(12), E.px(4)))
        for v in lista[:6]:
            self._linha_pc(self.caixa_vizinhos, v["codigo"], v["nome"],
                           "Windows" if v.get("so") == "windows" else "Linux", E.OK, remover=False)
        self._atualizar_recentes()

    def _atualizar_recentes(self):
        for w in self.caixa_recentes.winfo_children():
            w.destroy()
        self.caixa_recentes.configure(height=1)      # Tk não encolhe um quadro que ficou vazio
        na_rede = {v["codigo"] for v in self.vizinhos}
        recentes = [r for r in obter_recentes() if r.get("codigo") not in na_rede][:5]
        if recentes:
            tk.Label(self.caixa_recentes, text="RECENTES", bg=E.CARTAO, fg="#6c6e75",
                     font=E.fonte(7, "bold")).pack(anchor="w", pady=(E.px(12), E.px(4)))
        for r in recentes:
            cod = r.get("codigo", "")
            nome = r.get("nome") or formatar_codigo(cod)
            if nome == cod:
                nome = formatar_codigo(cod)
            self._linha_pc(self.caixa_recentes, cod, nome, formatar_codigo(cod), "#55575e")
        self._ajustar_altura()

    def _linha_pc(self, pai, cod, nome, detalhe, cor, remover=True):
        linha = tk.Frame(pai, bg=E.CARTAO, cursor="hand2")
        linha.pack(fill="x")
        ic = E.Ponto(linha, cor, tam=7)
        ic.pack(side="left", padx=(E.px(6), E.px(10)), pady=E.px(9))
        n = tk.Label(linha, text=nome, bg=E.CARTAO, fg=E.TEXTO, font=E.fonte(10))
        n.pack(side="left")
        cl = tk.Label(linha, text=detalhe, bg=E.CARTAO, fg=E.APAGADO, font=E.fonte(9))
        cl.pack(side="left", padx=(E.px(8), 0))
        x = tk.Label(linha, text="✕" if remover else "", bg=E.CARTAO, fg="#5c5e65", font=E.fonte(9),
                     padx=E.px(8), cursor="hand2")
        x.pack(side="right")
        partes = (linha, ic, n, cl, x)

        def hover(cor, ps=partes):
            for p in ps:
                p.config(bg=cor)
        for p in partes:
            p.bind("<Enter>", lambda e, h=hover: h(E.HOVER))
            p.bind("<Leave>", lambda e, h=hover: h(E.CARTAO))
        for p in partes[:-1]:
            p.bind("<Button-1>", lambda e, cd=cod: self._conectar(cd))
        if remover:
            x.bind("<Button-1>", lambda e, cd=cod: self._remover_recente(cd))

    def _remover_recente(self, codigo):
        remover_recente(codigo)
        self._atualizar_recentes()

    def _ajustar_altura(self):
        self.root.update_idletasks()
        if self.root.state() == "normal":
            self.root.geometry(f"{self.root.winfo_width()}x{self.root.winfo_reqheight()}")

    # ------------------------------------------------------------------ este PC
    def _copiar(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.cfg["codigo"])
        self.bt_copiar.config(text="Copiado ✓")
        self.root.after(1500, lambda: self.bt_copiar.config(text="Copiar"))

    def _estado(self, titulo, sub, cor=E.OK, conectado=False):
        self.lbl_estado.config(text=titulo)
        self.lbl_sub_estado.config(text=sub)
        self.ponto_estado.cor(cor)
        if conectado:
            self.bt_desconectar.pack(side="right", padx=(E.px(8), 0))
        else:
            self.bt_desconectar.pack_forget()

    def _rede(self, chave, ok, detalhe):
        p, lb, nome = self.rede[chave]
        p.cor(E.OK if ok else E.AVISO)
        lb.config(fg=E.TEXTO if ok else E.APAGADO)
        self.detalhes_rede[chave] = detalhe
        partes = []
        if self.detalhes_rede.get("stun"):
            partes.append(self.detalhes_rede["stun"])
        if self.detalhes_rede.get("ipv6"):
            partes.append(self.detalhes_rede["ipv6"])
        self.lbl_rede.config(text="  •  ".join(partes))

    def _atualizar_senha(self):
        tem = bool(self.cfg.get("senha_chave"))
        self.lbl_senha.config(text="Senha definida — clique para trocar" if tem else
                              "Entrar sem ninguém aceitar, usando uma senha — clique para definir")
        self.interruptor.definir(bool(self.cfg.get("autonomo")) and tem)

    def _alternar_auto(self, ligado):
        if ligado:
            if not self.cfg.get("senha_chave"):
                self.interruptor.definir(False)
                self._dialogo_senha()
                return
            self.cfg["autonomo"] = True
            salvar_config(self.cfg)
        else:
            self.cfg = definir_senha(None)
        if self.servidor:
            self.servidor.cfg = self.cfg
        self._atualizar_senha()

    def _dialogo_base(self, titulo):
        d = tk.Toplevel(self.root, bg=E.FUNDO)
        d.title(titulo)
        d.transient(self.root)
        d.resizable(False, False)
        d.caixa = E.Cartao(d, padding=22)
        d.caixa.pack(fill="both", expand=True, padx=1, pady=1)
        E.janela_escura(d)
        return d

    def _dialogo_senha(self):
        d = self._dialogo_base("Senha de acesso")
        cx = d.caixa
        tk.Label(cx, text="Senha de acesso sem supervisão", bg=E.CARTAO, fg=E.TEXTO,
                 font=E.fonte(12, "bold")).pack(anchor="w")
        tk.Label(cx, text="Com ela dá para entrar neste computador sem ninguém aceitar aqui.\n"
                          "Mínimo de 8 caracteres. Fica guardada só uma chave derivada.",
                 bg=E.CARTAO, fg=E.APAGADO, font=E.fonte(9), justify="left").pack(anchor="w", pady=(E.px(4), E.px(12)))
        e1 = E.Campo(cx, dica="Senha", senha=True, width=32)
        e1.pack(fill="x", pady=(0, E.px(8)))
        e2 = E.Campo(cx, dica="Repita a senha", senha=True, width=32)
        e2.pack(fill="x")
        aviso = tk.Label(cx, text="", bg=E.CARTAO, fg="#ff8a80", font=E.fonte(9))
        aviso.pack(anchor="w", pady=(E.px(6), 0))

        def salvar(*_):
            a, b = e1.get(), e2.get()
            if len(a) < 8:
                aviso.config(text="Use pelo menos 8 caracteres.")
                return
            if a != b:
                aviso.config(text="As senhas não são iguais.")
                return
            self.cfg = definir_senha(a)
            if self.servidor:
                self.servidor.cfg = self.cfg
            self._atualizar_senha()
            d.destroy()
        bt = tk.Frame(cx, bg=E.CARTAO)
        bt.pack(fill="x", pady=(E.px(12), 0))
        E.Botao(bt, "Salvar", salvar, estilo="principal", peso="bold").pack(side="right")
        E.Botao(bt, "Cancelar", d.destroy).pack(side="right", padx=E.px(8))
        if self.cfg.get("senha_chave"):
            def desligar():
                self.cfg = definir_senha(None)
                if self.servidor:
                    self.servidor.cfg = self.cfg
                self._atualizar_senha()
                d.destroy()
            E.Botao(bt, "Remover senha", desligar, estilo="fantasma").pack(side="left")
        e1.entrada.bind("<Return>", lambda e: e2.entrada.focus_set())
        e2.entrada.bind("<Return>", salvar)
        _centralizar(d, self.root)
        e1.entrada.focus_set()
        d.grab_set()

    # ------------------------------------------------------------------ servidor
    def _iniciar_servidor(self):
        def rodar():
            from .host import Servidor          # importa aiortc/av/numpy aqui, fora da interface
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.servidor = Servidor(aprovar=self._aprovar,
                                     evento=lambda tipo, dados: self.eventos.put(("evento", tipo, dados)))
            try:
                self.loop.run_until_complete(self.servidor.iniciar())
            except Exception as e:
                log.exception("servidor")
                self.eventos.put(("evento", "erro", {"texto": f"Falha ao iniciar: {e}"}))
            self.loop.run_forever()
        threading.Thread(target=rodar, daemon=True, name="servidor").start()

    def _parar_servidor(self):
        if self.loop and self.servidor:
            try:
                asyncio.run_coroutine_threadsafe(self.servidor.parar(), self.loop).result(5)
            except Exception:
                pass
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.loop = self.servidor = None

    async def _aprovar(self, nome, sas):
        fut = self.loop.create_future()
        loop = self.loop

        def responder(ok):
            loop.call_soon_threadsafe(lambda: fut.done() or fut.set_result(ok))
        self.eventos.put(("pedido", nome, sas, responder))
        try:
            return await asyncio.wait_for(fut, 60)
        except asyncio.TimeoutError:
            self.eventos.put(("fechar_pedido",))
            return False
        except asyncio.CancelledError:
            self.eventos.put(("fechar_pedido",))
            raise

    def _processar_eventos(self):
        try:
            while True:
                ev = self.eventos.get_nowait()
                try:
                    if ev[0] == "pedido":
                        self._dialogo_pedido(*ev[1:])
                    elif ev[0] == "fechar_pedido":
                        if self.dialogo:
                            self.dialogo.destroy()
                            self.dialogo = None
                    else:
                        self._evento(ev[1], ev[2])
                except Exception:
                    log.exception("evento %s", ev[0])
        except queue.Empty:
            pass
        self.root.after(100, self._processar_eventos)

    def _dialogo_pedido(self, nome, sas, responder):
        d = self._dialogo_base("Pedido de acesso")
        d.transient(None)
        d.attributes("-topmost", True)
        cx = d.caixa
        tk.Label(cx, text=f"{nome} quer acessar este computador", bg=E.CARTAO, fg=E.TEXTO,
                 font=E.fonte(13, "bold"), wraplength=E.px(380)).pack()
        tk.Label(cx, text="Só aceite se foi você ou alguém de confiança.\n"
                          "O código abaixo deve ser igual ao do outro computador.",
                 bg=E.CARTAO, fg=E.APAGADO, font=E.fonte(9)).pack(pady=(E.px(6), E.px(10)))
        tk.Label(cx, text=sas, bg=E.CARTAO, fg=E.TEXTO, font=E.fonte(28, "bold")).pack(pady=(0, E.px(16)))
        bt = tk.Frame(cx, bg=E.CARTAO)
        bt.pack()

        def r(ok):
            responder(ok)
            d.destroy()
            self.dialogo = None
        E.Botao(bt, "Recusar", lambda: r(False), padx=22).pack(side="left", padx=E.px(6))
        E.Botao(bt, "Aceitar", lambda: r(True), estilo="principal", peso="bold", padx=22).pack(side="left",
                                                                                              padx=E.px(6))
        d.protocol("WM_DELETE_WINDOW", lambda: r(False))
        self.dialogo = d
        if self.root.state() == "iconic":
            self.root.deiconify()
        _centralizar(d)
        self.root.bell()
        d.lift()
        d.focus_force()
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.user32.FlashWindow(ctypes.windll.user32.GetParent(d.winfo_id()), True)
            except Exception:
                pass

    def _evento(self, tipo, d):
        if tipo == "vizinhos":
            self._atualizar_vizinhos(d.get("lista", []))
        elif tipo == "pronto":
            for r in obter_recentes()[:3]:          # recentes já ficam com o caminho preparado
                self._preaquecer(r.get("codigo", ""))
            self._estado("Pronto para receber conexões", "Aguardando um pedido pelo endereço acima")
            self._rede("dht", True, "")
            lan = getattr(self.servidor, "lan", None)
            self._rede("lan", bool(lan and lan.transporte), "")
        elif tipo == "rede":
            self._rede("ipv6", bool(d.get("ipv6")), "IPv6 público" if d.get("ipv6") else "")
            self._rede("upnp", bool(d.get("upnp")), "")
            ip = d.get("ip_externo")
            self._rede("stun", bool(ip), f"IP público {ip}" if ip else "")
        elif tipo == "pedido":
            self._estado(f"Pedido de {d['nome']}", f"Verificação {d['verificacao']}", E.AVISO)
        elif tipo == "conectando":
            self._estado(f"Conectando com {d['nome']}…", "Abrindo caminho direto", E.AVISO)
        elif tipo == "conectado":
            total = d.get("total", 1)
            titulo = f"Conectado ({total} ativos)" if total > 1 else f"{d['nome']} está conectado"
            self._estado(titulo, d.get("caminho", "P2P"), E.OK, True)
        elif tipo == "sessao_encerrada":
            restantes = d.get("restantes", 0)
            nomes = d.get("nomes", [])
            if restantes > 0:
                self._estado(f"{restantes} conexões ativas", ", ".join(nomes), E.OK, True)
            else:
                self._estado("Pronto para receber conexões", "Conexão encerrada")
        elif tipo == "autonomo":
            self._estado(f"{d['nome']} entrou com a senha", "Acesso sem supervisão", E.OK, True)
        elif tipo == "reconectado":
            self._estado(f"{d['nome']} reconectou", "Conexão retomada automaticamente", E.OK, True)
        elif tipo == "senha_errada":
            self.lbl_sub_estado.config(text=f"Tentativa com senha errada: {d['nome']}")
        elif tipo in ("desconectado", "recusado"):
            self._estado("Pronto para receber conexões",
                         "Conexão encerrada" if tipo == "desconectado" else "Pedido recusado")
        elif tipo == "erro":
            self.lbl_sub_estado.config(text=d.get("texto", "erro"))

    def _desconectar(self):
        if self.loop and self.servidor:
            self.loop.call_soon_threadsafe(self.servidor.desconectar)

    def _novo_codigo(self):
        d = self._dialogo_base("Novo endereço")
        tk.Label(d.caixa, text="Gerar um novo endereço?", bg=E.CARTAO, fg=E.TEXTO,
                 font=E.fonte(12, "bold")).pack(anchor="w")
        tk.Label(d.caixa, text="Quem usa o endereço atual não vai mais conseguir conectar,\n"
                               "e a senha de acesso precisa ser definida de novo.",
                 bg=E.CARTAO, fg=E.APAGADO, font=E.fonte(9), justify="left").pack(anchor="w", pady=(E.px(4), E.px(14)))
        bt = tk.Frame(d.caixa, bg=E.CARTAO)
        bt.pack(fill="x")

        def gerar():
            d.destroy()
            self._parar_servidor()
            novo_codigo()
            self.cfg = carregar_config()
            self.lbl_codigo.config(text=formatar_codigo(self.cfg["codigo"]))
            self._atualizar_senha()
            self._estado("Reiniciando…", "Novo endereço", E.AVISO)
            self._iniciar_servidor()
        E.Botao(bt, "Gerar", gerar, estilo="principal", peso="bold").pack(side="right")
        E.Botao(bt, "Cancelar", d.destroy).pack(side="right", padx=E.px(8))
        _centralizar(d, self.root)
        d.grab_set()

    def _sair(self):
        self._parar_servidor()
        self.root.destroy()

    def rodar(self):
        self.root.mainloop()


def main(codigo_alvo=None):
    fmt = "%(asctime)s %(name)s %(message)s"
    if sys.stderr is None:           # .exe sem console: registro em %APPDATA%\Simba Remoto\simba-remoto.log
        from .config import CONFIG
        try:
            CONFIG.mkdir(parents=True, exist_ok=True)
            arq = CONFIG / "simba-remoto.log"
            if arq.exists() and arq.stat().st_size > 2_000_000:
                arq.unlink()
            logging.basicConfig(level=logging.INFO, format=fmt, filename=str(arq), encoding="utf-8")
        except OSError:
            pass
    else:
        logging.basicConfig(level=logging.INFO, format=fmt)
    for n in ("aioice", "aiortc"):
        logging.getLogger(n).setLevel(logging.WARNING)
    App(codigo_inicial=codigo_alvo).rodar()
