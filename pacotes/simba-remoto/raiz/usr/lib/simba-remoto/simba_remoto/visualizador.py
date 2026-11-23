"""Janela do visualizador do cliente Simba Remoto (GTK4 + libadwaita).
Exibe a tela remota com baixa latência, mapeia entrada de mouse/teclado e fornece
atalhos essenciais (Ctrl+Alt+Del, Super, Tela cheia, etc.).
"""
import asyncio
import logging
import threading
from typing import Optional

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from .cliente import ConexaoCliente  # noqa: E402
from .config import (carregar_config, obter_senha_remota, remover_senha_remota, salvar_recente,  # noqa: E402
                     salvar_senha_remota)
from .quadros import ConversorQuadros  # noqa: E402
from .sinal import formatar_codigo  # noqa: E402

log = logging.getLogger("simba-remoto.visualizador")

TECLAS_MAPA = {
    "Return": "Enter",
    "KP_Enter": "Enter",
    "BackSpace": "Backspace",
    "Tab": "Tab",
    "ISO_Left_Tab": "Tab",
    "Escape": "Escape",
    "Delete": "Delete",
    "Insert": "Insert",
    "Home": "Home",
    "End": "End",
    "Prior": "PageUp",
    "Next": "PageDown",
    "Up": "Up",
    "Down": "Down",
    "Left": "Left",
    "Right": "Right",
    "space": "Space",
    **{f"F{i}": f"F{i}" for i in range(1, 13)},
}


class JanelaVisualizador(Adw.Window):
    def __init__(self, app, codigo: str, meu_nome: Optional[str] = None, servidor=None, loop=None):
        super().__init__(application=app, title=f"Simba Remoto — {formatar_codigo(codigo)}",
                         default_width=1024, default_height=680)
        self.app = app
        self.codigo = "".join(c for c in codigo if c.isdigit())
        self.meu_nome = meu_nome or carregar_config().get("nome", "PC")
        self.servidor = servidor            # app já rodando: usa o loop e a DHT aquecida dele
        self.loop = loop
        self._loop_proprio = loop is None
        self.cliente = None
        self.largura_frame = 0
        self.altura_frame = 0
        self._quadro_pendente = None
        self._atualizando_frame = False
        self._em_tela_cheia = False
        self._fechando = False
        self._conectado = False
        self._reconexoes = 0
        self._geracao = None
        self.conversor = ConversorQuadros(self._quadro_convertido)

        self._montar_ui()
        self.connect("close-request", self._ao_fechar)
        self._iniciar_cliente()

    def _montar_ui(self):
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        # Barra de topo
        self.barra = Adw.HeaderBar()
        tit_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        self.lbl_titulo = Gtk.Label(label=formatar_codigo(self.codigo), css_classes=["title-4"])
        self.lbl_subtitulo = Gtk.Label(label="Conectando…", css_classes=["caption", "dim-label"])
        tit_box.append(self.lbl_titulo)
        tit_box.append(self.lbl_subtitulo)
        self.barra.set_title_widget(tit_box)

        # Selo de verificação SAS
        self.pill_sas = Gtk.Box(spacing=4, css_classes=["pill", "card"], margin_start=6, margin_end=6,
                                visible=False)
        self.pill_sas.append(Gtk.Image(icon_name="security-high-symbolic", pixel_size=14))
        self.lbl_sas = Gtk.Label(label="", css_classes=["caption"])
        self.pill_sas.append(self.lbl_sas)
        self.barra.pack_start(self.pill_sas)

        # Menu de teclas especiais
        menu_teclas = Gio.Menu()
        menu_teclas.append("Enviar Ctrl+Alt+Del", "vis.ctrl-alt-del")
        menu_teclas.append("Pressionar tecla Super (Windows)", "vis.super")
        menu_teclas.append("Enviar Alt+Tab", "vis.alt-tab")
        menu_teclas.append("Enviar Ctrl+Esc", "vis.ctrl-esc")
        btn_teclas = Gtk.MenuButton(icon_name="input-keyboard-symbolic", tooltip_text="Ações de teclado",
                                    menu_model=menu_teclas)
        self.barra.pack_end(btn_teclas)

        # Ações do menu
        self._criar_acao("ctrl-alt-del", lambda *_: self.cliente and self.cliente.enviar_ctrl_alt_del())
        self._criar_acao("super", lambda *_: self.cliente and self.cliente.enviar_super())
        self._criar_acao("alt-tab", lambda *_: self.cliente and self.cliente.tecla("Tab", mods=["alt"]))
        self._criar_acao("ctrl-esc", lambda *_: self.cliente and self.cliente.tecla("Escape", mods=["ctrl"]))

        # Botão de tela cheia
        self.btn_tela_cheia = Gtk.Button(icon_name="view-fullscreen-symbolic", tooltip_text="Tela cheia (F11)")
        self.btn_tela_cheia.connect("clicked", lambda *_: self._alternar_tela_cheia())
        self.barra.pack_end(self.btn_tela_cheia)

        # Botão desconectar
        btn_desc = Gtk.Button(label="Desconectar", css_classes=["destructive-action"])
        btn_desc.connect("clicked", lambda *_: self.close())
        self.barra.pack_end(btn_desc)

        vbox.append(self.barra)

        # Pilha de telas (Carregando / Senha / Remoto / Erro)
        self.pilha = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)

        # 1. Tela de Carregando
        self.pag_carregando = Adw.StatusPage(title="Conectando…",
                                             description="Procurando o computador remoto na rede…")
        caixa_carregando = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, halign=Gtk.Align.CENTER)
        self.spinner = Gtk.Spinner(spinning=True, width_request=36, height_request=36)
        caixa_carregando.append(self.spinner)
        btn_cancelar = Gtk.Button(label="Cancelar", css_classes=["pill"], halign=Gtk.Align.CENTER)
        btn_cancelar.connect("clicked", lambda *_: self.close())
        caixa_carregando.append(btn_cancelar)
        self.pag_carregando.set_child(caixa_carregando)
        self.pilha.add_named(self.pag_carregando, "carregando")

        # 2. Tela de Senha (se o host pedir senha de acesso não supervisionado)
        self.pag_senha = Adw.StatusPage(title="Aguardando aceitarem do outro lado",
                                        description="Alguém no outro computador pode clicar em Aceitar — "
                                                    "ou entre com a senha de acesso dele.",
                                        icon_name="dialog-password-symbolic")
        caixa_senha = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, halign=Gtk.Align.CENTER,
                              width_request=360)
        self.entrada_senha = Adw.PasswordEntryRow(title="Senha")
        self.entrada_senha.connect("entry-activated", lambda *_: self._enviar_senha())
        lista_senha = Gtk.ListBox(css_classes=["boxed-list"])
        lista_senha.append(self.entrada_senha)
        caixa_senha.append(lista_senha)

        self.chk_salvar_senha = Gtk.CheckButton(label="Salvar senha para este computador", active=True)
        caixa_senha.append(self.chk_salvar_senha)

        self.lbl_erro_senha = Gtk.Label(label="", css_classes=["error", "caption"], visible=False)
        caixa_senha.append(self.lbl_erro_senha)

        botoes_senha = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        btn_canc_senha = Gtk.Button(label="Cancelar")
        btn_canc_senha.connect("clicked", lambda *_: self.close())
        botoes_senha.append(btn_canc_senha)
        btn_ok_senha = Gtk.Button(label="Entrar", css_classes=["suggested-action"])
        btn_ok_senha.connect("clicked", lambda *_: self._enviar_senha())
        botoes_senha.append(btn_ok_senha)
        caixa_senha.append(botoes_senha)

        self.pag_senha.set_child(caixa_senha)
        self.pilha.add_named(self.pag_senha, "senha")

        # 3. Tela do Visualizador Remoto
        self.picture = Gtk.Picture()
        self.picture.set_can_shrink(True)
        self.picture.set_content_fit(Gtk.ContentFit.CONTAIN)
        self.picture.set_hexpand(True)
        self.picture.set_vexpand(True)
        self.picture.set_focusable(True)

        # Controladores de entrada (Mouse e Teclado)
        ctrl_motion = Gtk.EventControllerMotion()
        ctrl_motion.connect("motion", self._ao_mover_mouse)
        self.picture.add_controller(ctrl_motion)

        ctrl_click = Gtk.GestureClick()
        ctrl_click.set_button(0)
        ctrl_click.connect("pressed", self._ao_pressionar_mouse)
        ctrl_click.connect("released", self._ao_soltar_mouse)
        self.picture.add_controller(ctrl_click)

        ctrl_scroll = Gtk.EventControllerScroll()
        ctrl_scroll.set_flags(Gtk.EventControllerScrollFlags.BOTH_AXES | Gtk.EventControllerScrollFlags.DISCRETE)
        ctrl_scroll.connect("scroll", self._ao_rolar_mouse)
        self.picture.add_controller(ctrl_scroll)

        ctrl_key = Gtk.EventControllerKey()
        ctrl_key.connect("key-pressed", self._ao_tecla)
        self.add_controller(ctrl_key)

        caixa_remoto = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, css_classes=["tela-remota"])
        prov = Gtk.CssProvider()
        prov.load_from_data(b".tela-remota { background: #000; }")
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        caixa_remoto.append(self.picture)
        self.pilha.add_named(caixa_remoto, "remoto")

        # 4. Tela de Erro / Desconectado
        self.pag_erro = Adw.StatusPage(title="Conexão encerrada", icon_name="network-offline-symbolic")
        btn_fechar_erro = Gtk.Button(label="Fechar", css_classes=["pill"], halign=Gtk.Align.CENTER)
        btn_fechar_erro.connect("clicked", lambda *_: self.close())
        self.pag_erro.set_child(btn_fechar_erro)
        self.pilha.add_named(self.pag_erro, "erro")

        vbox.append(self.pilha)
        self.set_content(vbox)

    def _criar_acao(self, nome, callback):
        if not hasattr(self, "_acoes"):
            self._acoes = Gio.SimpleActionGroup()
            self.insert_action_group("vis", self._acoes)
        act = Gio.SimpleAction.new(nome, None)
        act.connect("activate", callback)
        self._acoes.add_action(act)

    def _alternar_tela_cheia(self):
        if self._em_tela_cheia:
            self.unfullscreen()
            self._em_tela_cheia = False
            self.btn_tela_cheia.set_icon_name("view-fullscreen-symbolic")
            self.barra.set_visible(True)
        else:
            self.fullscreen()
            self._em_tela_cheia = True
            self.btn_tela_cheia.set_icon_name("view-restore-symbolic")

    # ------------------------------------------------------------- Ciclo de conexão
    def _iniciar_cliente(self):
        if self.loop is not None:
            self._conectar()
            return
        pronto = threading.Event()

        def rodar():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            pronto.set()
            self.loop.run_forever()
        threading.Thread(target=rodar, daemon=True, name="cliente-remoto").start()
        pronto.wait()
        self._conectar()

    def _conectar(self, ficha=None):
        senha_salva = obter_senha_remota(self.codigo)
        self._conectado = False
        self.largura_frame = self.altura_frame = 0
        gen = object()
        self._geracao = gen
        if ficha:
            self.pag_carregando.set_title("Reconectando…")
            self.pag_carregando.set_description("A conexão caiu; retomando automaticamente.")
        else:
            self.pag_carregando.set_title("Conectando…")
        self.pilha.set_visible_child_name("carregando")

        def evento(t, d, gen=gen):
            GLib.idle_add(lambda: self._geracao is gen and self._tratar_evento(t, d))

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

    def _encerrar_cliente(self):
        c, self.cliente, self._geracao = self.cliente, None, None
        if c and self.loop:
            asyncio.run_coroutine_threadsafe(c.fechar(), self.loop)

    def _ao_fechar(self, *_):
        self._fechando = True
        self.conversor.parar()
        c, self.cliente, self._geracao = self.cliente, None, None
        if self.loop and c:
            fut = asyncio.run_coroutine_threadsafe(c.fechar(), self.loop)
            try:
                fut.result(3)
            except Exception:
                pass
        if self.loop and self._loop_proprio:
            self.loop.call_soon_threadsafe(self.loop.stop)
        return False

    def _quadro_convertido(self, dados, w, h, wo, ho):        # thread do conversor
        self._quadro_pendente = (dados, w, h, wo, ho)
        if not self._atualizando_frame:
            self._atualizando_frame = True
            GLib.idle_add(self._desenhar_quadro)

    def _desenhar_quadro(self):
        self._atualizando_frame = False
        p, self._quadro_pendente = self._quadro_pendente, None
        if not p or not self._conectado:
            return False
        dados, w, h, wo, ho = p
        tex = Gdk.MemoryTexture.new(w, h, Gdk.MemoryFormat.R8G8B8, GLib.Bytes.new(dados), w * 3)
        self.picture.set_paintable(tex)
        self.largura_frame, self.altura_frame = wo, ho
        # converte já no tamanho exibido (pixels reais da tela), sem passar do original
        esc = self.picture.get_scale_factor() or 1
        pw, ph = self.picture.get_width() * esc, self.picture.get_height() * esc
        if pw > 0 and ph > 0:
            f = min(pw / wo, ph / ho, 1.0)
            self.conversor.definir_tamanho(int(wo * f), int(ho * f))
        return False

    def _tratar_evento(self, tipo: str, d: dict):
        log.info("Visualizador ev: %s %s", tipo, d)
        if tipo == "procurando":
            self.lbl_subtitulo.set_label(d.get("texto", "Procurando…"))
            self.pag_carregando.set_description(d.get("texto", "Procurando computador…"))
            self.pilha.set_visible_child_name("carregando")
        elif tipo == "aguardando_pc":
            self.lbl_subtitulo.set_label("Aguardando aceite…")
            self.pag_carregando.set_description(d.get("texto", "Aguardando o computador remoto aceitar…"))
            self.pilha.set_visible_child_name("carregando")
        elif tipo == "pedir_senha":
            if self.pilha.get_visible_child_name() == "senha":
                return False
            self.lbl_subtitulo.set_label("Aguardando aceite ou senha")
            self.lbl_erro_senha.set_visible(False)
            self.pilha.set_visible_child_name("senha")
            self.entrada_senha.grab_focus()
        elif tipo == "senha_errada":
            remover_senha_remota(self.codigo)
            motivo = d.get("motivo", "")
            self.lbl_erro_senha.set_label(motivo[:1].upper() + motivo[1:] if "muitas" in motivo
                                          else "Senha incorreta. Tente novamente.")
            self.lbl_erro_senha.set_visible(True)
            self.pilha.set_visible_child_name("senha")
            self.entrada_senha.grab_focus()
        elif tipo == "conectando":
            self.lbl_subtitulo.set_label("Abrindo conexão direta…")
            self.pag_carregando.set_description(d.get("texto", "Conectando via P2P…"))
            if d.get("sas"):
                self.lbl_sas.set_label(f"Verificação: {d['sas']}")
                self.pill_sas.set_visible(True)
            if d.get("nome"):
                self.lbl_titulo.set_label(d["nome"])
        elif tipo == "conectado":
            self._conectado = True
            self._reconexoes = 0
            nome = d.get("nome") or formatar_codigo(self.codigo)
            self.lbl_titulo.set_label(nome)
            self.lbl_subtitulo.set_label(f"Conectado • {d.get('caminho', 'P2P')}")
            if d.get("sas"):
                self.lbl_sas.set_label(f"Verificação: {d['sas']}")
                self.pill_sas.set_visible(True)
            salvar_recente(self.codigo, nome)
            self.pilha.set_visible_child_name("remoto")
            self.picture.grab_focus()
        elif tipo == "recusado":
            self.pag_erro.set_title("Conexão recusada")
            self._conectado = False
            self.pag_erro.set_description(d.get("motivo") or "O computador remoto recusou a conexão.")
            self.pilha.set_visible_child_name("erro")
        elif tipo == "desconectado" and d.get("caiu") and self.cliente and self.cliente.ficha_recebida \
                and self._reconexoes < 3 and not self._fechando:
            ficha = self.cliente.ficha_recebida
            self._reconexoes += 1
            self._encerrar_cliente()
            self._conectar(ficha=ficha)
        elif tipo in ("desconectado", "erro"):
            self._conectado = False
            if self._em_tela_cheia:
                self._alternar_tela_cheia()
            self.pag_erro.set_title("Desconectado" if tipo == "desconectado" else "Falha na conexão")
            self.pag_erro.set_description(d.get("texto", "A conexão foi finalizada."))
            self.pilha.set_visible_child_name("erro")
        elif tipo == "tela":
            if d.get("nome"):
                self.lbl_titulo.set_label(d["nome"])
                salvar_recente(self.codigo, d["nome"])
        return False

    def _enviar_senha(self):
        senha = self.entrada_senha.get_text()
        if not senha or not self.cliente:
            return
        if self.chk_salvar_senha.get_active():
            from .sinal import chave_senha
            salvar_senha_remota(self.codigo, chave_senha(senha, self.codigo).hex())
        self.pilha.set_visible_child_name("carregando")
        self.pag_carregando.set_description("Enviando senha para validação…")
        asyncio.run_coroutine_threadsafe(self.cliente.entrar_com_senha(senha), self.loop)

    # ------------------------------------------------------------- Mapeamento de Entrada
    def _calcular_norm(self, x, y):
        pw = self.picture.get_width()
        ph = self.picture.get_height()
        if pw <= 0 or ph <= 0 or not self.largura_frame or not self.altura_frame:
            return None, None
        scale = min(pw / self.largura_frame, ph / self.altura_frame)
        disp_w = self.largura_frame * scale
        disp_h = self.altura_frame * scale
        ox = (pw - disp_w) / 2.0
        oy = (ph - disp_h) / 2.0
        nx = (x - ox) / disp_w
        ny = (y - oy) / disp_h
        return max(0.0, min(1.0, nx)), max(0.0, min(1.0, ny))

    def _ao_mover_mouse(self, _ctrl, x, y):
        if not self.cliente:
            return
        nx, ny = self._calcular_norm(x, y)
        if nx is not None:
            self.cliente.mover(nx, ny)

    def _ao_pressionar_mouse(self, gesture, _n_press, x, y):
        if not self.cliente:
            return
        btn_num = gesture.get_current_button()
        botao = {1: "esq", 2: "meio", 3: "dir"}.get(btn_num, "esq")
        nx, ny = self._calcular_norm(x, y)
        self.picture.grab_focus()
        self.cliente.botao(botao, "desce", nx, ny)

    def _ao_soltar_mouse(self, gesture, _n_press, x, y):
        if not self.cliente:
            return
        btn_num = gesture.get_current_button()
        botao = {1: "esq", 2: "meio", 3: "dir"}.get(btn_num, "esq")
        nx, ny = self._calcular_norm(x, y)
        self.cliente.botao(botao, "sobe", nx, ny)

    def _ao_rolar_mouse(self, ctrl, dx, dy):
        if not self.cliente:
            return False
        # No protocolo: dy positivo = rolar para cima; dy negativo = rolar para baixo
        passo_y = -int(dy) if dy else 0
        passo_x = int(dx) if dx else 0
        self.cliente.rolar(passo_x, passo_y)
        return True

    def _ao_tecla(self, _ctrl, keyval, _keycode, state):
        if not self.cliente or self.pilha.get_visible_child_name() != "remoto":
            return False

        # F11: alternar tela cheia local
        if keyval == Gdk.KEY_F11:
            self._alternar_tela_cheia()
            return True

        mods = []
        if state & Gdk.ModifierType.CONTROL_MASK:
            mods.append("ctrl")
        if state & Gdk.ModifierType.ALT_MASK:
            mods.append("alt")
        if state & Gdk.ModifierType.SUPER_MASK:
            mods.append("super")
        if state & Gdk.ModifierType.SHIFT_MASK:
            mods.append("shift")

        key_name = Gdk.keyval_name(keyval)
        if not key_name:
            return False

        if key_name in TECLAS_MAPA:
            # Tecla especial
            self.cliente.tecla(TECLAS_MAPA[key_name], mods=[m for m in mods if m != "shift"])
            return True

        if any(m in mods for m in ("ctrl", "alt", "super")):
            # Combinação de atalho com modificador (ex.: Ctrl+C, Ctrl+V, Alt+F4)
            unichar = Gdk.keyval_to_unicode(keyval)
            ch = chr(unichar).lower() if unichar else key_name
            self.cliente.tecla(ch, mods=mods)
            return True

        # Digitação comum
        unichar = Gdk.keyval_to_unicode(keyval)
        if unichar and chr(unichar).isprintable():
            self.cliente.texto(chr(unichar))
            return True

        return False
