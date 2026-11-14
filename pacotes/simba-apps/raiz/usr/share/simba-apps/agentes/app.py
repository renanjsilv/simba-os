#!/usr/bin/env python3
"""Agentes de IA do Simba OS — Frontend gráfico unificado de Chat (GTK4/libadwaita).

Permite interagir com todos os agentes de IA instalados (Claude Code, Antigravity,
Codex, Grok, Copilot, etc.) em uma interface centralizada de chat.
Quando o limite de uso de um agente é atingido, a conversa é continuada automaticamente
no próximo agente de forma transparente, sem fechar a janela ou quebrar o fluxo.

Módulos: parser.py (saída das CLIs), markdown.py (renderização), historico.py
(conversas salvas), central.py (gerenciar agentes), voz.py (ditado), estilo.py (CSS).
"""
import codecs
from datetime import datetime
import fcntl
import os
from pathlib import Path
import pty
import re
import select
import shutil
import struct
import subprocess
import sys
import termios
import threading
import time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Pango  # noqa: E402

sys.path.insert(0, "/usr/share/simba-apps/idiomas")
from simba_i18n import t as _t  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motor as M  # noqa: E402
import anexos  # noqa: E402
from busca import BuscaMixin  # noqa: E402
from seletor import Seletor  # noqa: E402
from central import CentralMixin  # noqa: E402
import marcas  # noqa: E402
from estilo import CSS  # noqa: E402
from historico import HistoricoMixin  # noqa: E402
from markdown import MarkdownMixin  # noqa: E402
from painel import PainelMixin  # noqa: E402
from parser import AgentStreamParser  # noqa: E402
import atividade  # noqa: E402
import integracoes  # noqa: E402
import lateral  # noqa: E402
import voz  # noqa: E402
try:  # navegador embutido (WebKitGTK 6); sem ele o chat funciona igual
    import navegador  # noqa: E402
except (ImportError, ValueError):
    navegador = None

# AGENTES_DEV=1 abre uma instância separada (para testar sem mexer na janela aberta).
APP_ID = "com.simba.AgentesDev" if os.environ.get("AGENTES_DEV") else "com.simba.Agentes"
HOME = Path.home()


def _vigiar_interface():
    """Se a interface ficar mais de 3 s sem responder, grava onde o programa estava
    em ~/.local/state/agentes/travamentos.log (para achar a causa de um congelamento)."""
    import faulthandler
    try:
        M.ESTADO.mkdir(parents=True, exist_ok=True)
        arq = open(M.ESTADO / "travamentos.log", "a", buffering=1)
        if arq.tell() > 400000:
            arq.truncate(0)
    except OSError:
        return

    ultimo = [time.monotonic()]

    def rearmar():
        agora = time.monotonic()
        if agora - ultimo[0] > 3:
            arq.write(f"# a interface ficou {agora - ultimo[0]:.1f} s parada, até "
                      f"{datetime.now().isoformat(timespec='seconds')} (pilha acima)\n\n")
        ultimo[0] = agora
        faulthandler.dump_traceback_later(3, file=arq)
        return True
    rearmar()
    GLib.timeout_add(1000, rearmar)


def formatar_uso(uso):
    """'12,3 mil tokens · US$ 0,004' a partir do uso informado pelo agente."""
    if not uso:
        return ""
    partes = []
    total = (int(uso.get("entrada", 0) or 0) + int(uso.get("saida", 0) or 0)
             + int(uso.get("subagentes", 0) or 0))
    if total:
        partes.append(f"{total / 1000:.1f}k tokens" if total >= 1000 else f"{total} tokens")
    custo = uso.get("custo")
    if custo:
        partes.append(f"US$ {custo:.3f}")
    return " · ".join(partes)


# Vigia das execuções (ver MainWindow._vigiar). Os limites de silêncio vêm da
# configuração: semSinalMin (20) e semSinalFundoMin (150, com comando em segundo plano).
VIGIA_PASSO = 5          # s entre uma conferida e outra
VIGIA_AVISO = 90         # s sem sinal para o status começar a contar o tempo parado
VIGIA_SAIDA = 120        # s que o processo pode ficar aberto depois de responder, sem nada pendente
VIGIA_MINIMO = 60        # s: piso do limite de silêncio, por mais baixo que esteja na configuração
VIGIA_REPETICOES = 30    # mesma ação seguida tantas vezes = preso num laço

_DIAS = ("seg", "ter", "qua", "qui", "sex", "sáb", "dom")


def _epoch_iso(iso):
    """'2026-11-10T18:40:00Z' → epoch (0 se não der para ler)."""
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0


def _quando(epoch, longo=False):
    """Quando um limite zera: '15:40' hoje, 'amanhã 09:00', senão 'sex 09:00'."""
    t = datetime.fromtimestamp(epoch)
    hoje = datetime.now().date()
    hora = t.strftime("%H:%M")
    if t.date() == hoje:
        return f"{_t('hoje às')} {hora}" if longo else hora
    if (t.date() - hoje).days == 1:
        return f"{_t('amanhã às')} {hora}" if longo else f"{_t('amanhã')} {hora}"
    dia = _t(_DIAS[t.weekday()])
    return f"{dia} {t.strftime('%d/%m')} {_t('às')} {hora}" if longo else f"{dia} {hora}"


def _falta(seg):
    """Tempo até zerar: '45 min', '2 h 10 min', '3 dias 4 h'."""
    m = max(0, int(seg // 60))
    if m < 60:
        return f"{m} min"
    h, m = divmod(m, 60)
    if h < 24:
        return f"{h} h {m:02d} min" if m else f"{h} h"
    d, h = divmod(h, 24)
    return f"{d} {_t('dia') if d == 1 else _t('dias')}" + (f" {h} h" if h else "")


def definir_tamanho_pty(fd, linhas=40, colunas=120):
    try:
        ws = struct.pack("HHHH", linhas, colunas, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, ws)
    except Exception:
        pass




class AnelUso(Gtk.DrawingArea):
    """Anel de progresso pequeno (uso do limite), como o medidor do Claude."""

    def __init__(self, tamanho=16):
        super().__init__()
        self.frac = 0.0
        self.set_content_width(tamanho)
        self.set_content_height(tamanho)
        self.set_valign(Gtk.Align.CENTER)
        self.set_draw_func(self._desenhar)

    def definir(self, frac):
        frac = max(0.0, min(1.0, float(frac or 0)))
        if abs(frac - self.frac) > 0.001:
            self.frac = frac
            self.queue_draw()

    def _desenhar(self, _area, cr, larg, alt):
        import math
        cor = self.get_color()
        r = min(larg, alt) / 2 - 1.6
        cx, cy = larg / 2, alt / 2
        cr.set_line_width(2.6)
        cr.set_source_rgba(cor.red, cor.green, cor.blue, 0.18)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.stroke()
        if self.frac > 0:
            cr.set_source_rgba(cor.red, cor.green, cor.blue, 0.95)
            cr.set_line_cap(1)  # redondo
            cr.arc(cx, cy, r, -math.pi / 2, -math.pi / 2 + 2 * math.pi * self.frac)
            cr.stroke()


class MainWindow(CentralMixin, HistoricoMixin, MarkdownMixin, BuscaMixin, PainelMixin, Adw.ApplicationWindow):
    def __init__(self, app, pasta=None, prompt_inicial=None):
        super().__init__(application=app, title=_t("Agentes de IA"))
        self.set_default_size(1100, 780)
        self.set_size_request(540, 520)
        self.add_css_class("chat-bg")
        self.maximize()

        # Estado da sessão
        if pasta and Path(pasta).is_dir():
            self.work_dir = Path(pasta).expanduser().resolve()
        else:
            self.work_dir = HOME / "Work" if (HOME / "Work").is_dir() else HOME
        self.proc = None
        self.agente_atual = None
        self.usados = set()
        self.conversas_iniciadas = set()
        self.anterior_passagem = None
        self.inicio_agente = 0.0
        # Execução atual: cada uma ganha um número; eventos atrasados de uma
        # execução antiga (thread de leitura, callbacks) são ignorados.
        self.exec_seq = 0
        self.exec_atual = 0
        self.finalizado = True
        # Mensagens enviadas enquanto o agente responde: saem quando ele terminar.
        self.fila = []
        # id da sessão de cada agente nesta conversa (retoma a sessão certa)
        self.sessoes = {}
        self.interrompido = False
        self.janelas_uso = {}
        self.janelas_volta = {}   # agente → {"5h": epoch, "7d": epoch}: quando cada limite zera
        # o horário de reinício passa: a cada minuto tira do rótulo as janelas que já zeraram
        GLib.timeout_add_seconds(60, lambda: (self._atualizar_uso_ui(), True)[1])
        self.ativo_texto = ""
        self.render_fonte = 0
        self.gravador = voz.Gravador() if voz.disponivel() else None

        # Histórico persistente de conversas
        self.conversa_id = None
        self.conversa_criada = None
        self.conversa_mensagens = []
        self.ativo_registro = None
        self.precisa_contexto = False
        self.salvar_fonte = 0
        self.historico_dialog = None

        # Elementos da bolha ativa
        self.ativo_mensagem = None
        self.ativo_bloco = None        # bloco "Pensando" (atividade.BlocoPensando)
        self.ativo_digitando = None    # indicador de digitação, no fim da resposta
        self.ativo_duracao_lbl = None
        self.ativo_parser = None
        self.ativo_renderizado = False

        # Central de agentes (Configurações dentro do chat)
        self.central_dialog = None
        self.central_toast = None
        self.central_estado = None
        self.central_widgets = {}
        self.central_add_widgets = {}
        self.central_ids_inst = ()
        self.central_ids_disp = ()
        self.central_poll_id = 0
        self.central_refresh_id = 0
        self.central_espera_id = 0
        self.central_carregando = False
        self.central_pendente = False
        self.modelo_opcoes = []
        self.dropdown_items = []

        self.perguntas = []          # perguntas do agente esperando resposta (simba-chat perguntar)
        self._construir_ui()
        self._carregar_agentes()
        self.connect("close-request", self._ao_fechar)
        self.integracoes = integracoes.Servidor(self._tratar_integracao)
        try:
            self.integracoes.iniciar(APP_ID)
        except (GLib.Error, OSError) as e:
            print("simba-chat: controle indisponível:", e, file=sys.stderr)
        self.connect("close-request", lambda *_: (self.integracoes.parar(), False)[1])
        if self.navegador:
            try:
                self.navegador.iniciar_controle(APP_ID)
            except GLib.Error as e:
                print("navegador: controle indisponível:", e.message, file=sys.stderr)
            self.connect("close-request", lambda *_: (self.navegador.parar_controle(), False)[1])

        # Atalho de teclado global na janela (Esc interrompe geração em execução)
        win_key_ctrl = Gtk.EventControllerKey()
        win_key_ctrl.connect("key-pressed", self._on_window_key_pressed)
        self.add_controller(win_key_ctrl)

        if prompt_inicial:
            self.definir_prompt(prompt_inicial)

    def definir_pasta(self, pasta):
        caminho = Path(pasta).expanduser().resolve()
        if caminho.is_dir():
            self._mudar_pasta(caminho)

    def definir_prompt(self, texto):
        if texto and hasattr(self, "text_input_buf") and self.text_input_buf:
            self.text_input_buf.set_text(texto)
            if hasattr(self, "text_input") and self.text_input:
                self.text_input.grab_focus()

    def _construir_ui(self):
        # Toolbar View
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_css_class("chat-bg")
        self.set_content(toolbar_view)

        # Header Bar
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Seletor de agente: pílula com logo + nome; a lista abre num popover com
        # o logo, o modelo e o estado do limite de cada agente.
        marcas.registrar()
        self.dropdown = Seletor(lambda: self.dropdown_items, self._on_agente_selecionado,
                                cabecalho=_t("Agente de IA"), classe="agent-pill",
                                icone_fn=lambda it: self._icone_item(it.get("id")))
        self.icone_seletor = self.dropdown.icone
        header.pack_start(self.dropdown)

        # Botão Nova Conversa
        btn_novo = Gtk.Button(icon_name="document-new-symbolic")
        btn_novo.add_css_class("flat")
        btn_novo.add_css_class("icon-button")
        btn_novo.set_tooltip_text(_t("Nova conversa (Ctrl+L)"))
        btn_novo.connect("clicked", lambda _: self._limpar_chat())
        header.pack_start(btn_novo)

        header.set_title_widget(
            Adw.WindowTitle(title=_t("Agentes de IA"))
        )

        # Ações do cabeçalho, agrupadas e com o mesmo tamanho
        acoes = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        acoes.add_css_class("header-actions")

        # Histórico removido: botão oculto mas mantido para compatibilidade interna
        self.btn_historico = Gtk.Button(icon_name="document-open-recent-symbolic")
        self.btn_historico.set_visible(False)

        btn_busca = Gtk.Button(icon_name="edit-find-symbolic")
        btn_busca.add_css_class("flat")
        btn_busca.add_css_class("icon-button")
        btn_busca.set_tooltip_text(_t("Buscar na conversa (Ctrl+F)"))
        btn_busca.connect("clicked", lambda _: self._abrir_busca())
        acoes.append(btn_busca)

        marcas.registrar()
        btn_uso = Gtk.Button(icon_name="simba-ia-uso-symbolic")
        btn_uso.add_css_class("flat")
        btn_uso.add_css_class("icon-button")
        btn_uso.set_tooltip_text(_t("Uso e custo dos agentes"))
        btn_uso.connect("clicked", lambda _: self._abrir_painel_uso())
        acoes.append(btn_uso)

        # Central de agentes: tudo o que existe em Configurações, sem sair do chat
        btn_central = Gtk.Button(icon_name="simba-agente")
        btn_central.add_css_class("flat")
        btn_central.add_css_class("icon-button")
        btn_central.set_tooltip_text(f"{_t('Central de agentes')} (Ctrl+Shift+A)")
        btn_central.connect("clicked", lambda _: self._abrir_central())
        acoes.append(btn_central)

        # Navegador embutido: a pessoa abre por aqui; o agente, pelo simba-navegador
        self.btn_navegador = Gtk.ToggleButton(icon_name="web-browser-symbolic")
        self.btn_navegador.add_css_class("flat")
        self.btn_navegador.add_css_class("icon-button")
        self.btn_navegador.set_tooltip_text(f"{_t('Navegador')} (Ctrl+Shift+B)")
        self.btn_navegador.set_visible(navegador is not None)
        self.btn_navegador.connect("toggled", self._on_alternar_navegador)
        acoes.append(self.btn_navegador)

        header.pack_end(acoes)

        # Área Central de Mensagens: coluna central ergonômica para leitura agradável
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.set_vexpand(True)
        self.scroller.set_hexpand(True)
        self.scroller.add_css_class("chat-scroll")

        # A conversa ocupa a largura inteira da janela (que abre maximizada);
        # só as margens laterais mudam com a largura (breakpoints mais abaixo).
        self.box_mensagens = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.box_mensagens.set_hexpand(True)
        self.box_mensagens.set_halign(Gtk.Align.FILL)
        self.box_mensagens.set_margin_top(18)
        self.box_mensagens.set_margin_bottom(18)
        self.box_mensagens.set_margin_start(24)
        self.box_mensagens.set_margin_end(24)

        # Coluna de leitura centralizada (como Claude/ChatGPT): até ~900 px de largura
        self.coluna = Adw.Clamp(maximum_size=920, tightening_threshold=760)
        self.coluna.add_css_class("coluna-chat")
        self.coluna.set_child(self.box_mensagens)
        self.scroller.set_child(self.coluna)
        # Seguir o fim: enquanto a pessoa está no fim da conversa, a rolagem
        # acompanha o texto novo; se ela rolar para cima para ler, para de seguir.
        self.seguir_fim = True
        adj = self.scroller.get_vadjustment()
        adj.connect("value-changed", self._rolagem_mudou)
        adj.connect("notify::upper", lambda *_: self.seguir_fim and GLib.idle_add(self._do_scroll))

        # O estado vazio fica sobreposto à área de rolagem para centralizar de verdade
        self.empty_state = self._criar_estado_vazio()
        if hasattr(self, "candidatos"):
            self._atualizar_estado_gratis()
        # a dica de teclas só aparece na conversa vazia (depois é ruído)
        self.empty_state.connect("notify::visible",
                                 lambda e, _p: hasattr(self, "lbl_dica") and self.lbl_dica.set_visible(e.get_visible()))
        self.overlay = Gtk.Overlay()
        self.overlay.set_vexpand(True)
        self.overlay.set_child(self.scroller)
        self.overlay.add_overlay(self.empty_state)

        # Barra Inferior de Entrada (alinhada à coluna de leitura do chat)
        box_inferior = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box_inferior.set_margin_start(24)
        box_inferior.set_margin_end(24)
        box_inferior.set_margin_bottom(14)
        box_inferior.set_margin_top(4)
        self.box_inferior = box_inferior
        clamp_composer = Adw.Clamp(maximum_size=920, tightening_threshold=760)
        clamp_composer.set_child(self._criar_composer())
        box_inferior.append(clamp_composer)

        # Atalho de teclado no TextView (Enter envia, Shift+Enter nova linha)
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.text_input.add_controller(key_ctrl)

        # Colar prints (Ctrl+V com imagem na área de transferência)
        self.text_input.connect("paste-clipboard", self._on_colar)

        # Layout principal
        box_principal = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box_principal.add_css_class("chat-bg")
        box_principal.append(self._criar_barra_busca())
        box_principal.append(self.overlay)
        box_principal.append(box_inferior)
        # Lado direito: navegador embutido ou painel de código (um de cada vez)
        self.navegador = None
        self.lateral = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.lateral.set_visible(False)
        self.lateral.set_size_request(420, -1)
        if navegador is not None:
            self.navegador = navegador.PainelNavegador(ao_mostrar=self._mostrar_navegador,
                                                       ao_esconder=self._esconder_navegador)
            self.navegador.set_visible(False)
            self.navegador.set_hexpand(True)
            self.lateral.append(self.navegador)
        self.painel_codigo = lateral.PainelCodigo(ao_fechar=self._painel_codigo_fechado,
                                                  pasta=lambda: self.work_dir)
        self.painel_codigo.set_visible(False)
        self.painel_codigo.set_hexpand(True)
        self.lateral.append(self.painel_codigo)
        self.divisao = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        self.divisao.set_wide_handle(True)
        self.divisao.set_start_child(box_principal)
        self.divisao.set_end_child(self.lateral)
        self.divisao.set_resize_start_child(True)
        self.divisao.set_resize_end_child(True)
        self.divisao.set_shrink_start_child(False)
        self.divisao.set_shrink_end_child(False)
        box_principal.set_size_request(420, -1)
        toolbar_view.set_content(self.divisao)

        # Arrastar e soltar arquivos/imagens em qualquer lugar da janela
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_file_drop)
        box_principal.add_controller(drop_target)
        drop_imagem = Gtk.DropTarget.new(Gdk.Texture, Gdk.DragAction.COPY)
        drop_imagem.connect("drop", self._on_textura_drop)
        box_principal.add_controller(drop_imagem)

        # Margens laterais acompanham a largura da janela (breakpoints do Adwaita)
        for condicao, margem in (("max-width: 720sp", 10), ("min-width: 1600sp", 48)):
            bp = Adw.Breakpoint.new(Adw.BreakpointCondition.parse(condicao))
            for alvo in (self.box_mensagens, self.box_inferior):
                bp.add_setter(alvo, "margin-start", margem)
                bp.add_setter(alvo, "margin-end", margem)
            self.add_breakpoint(bp)

        self._atualizar_pasta_ui()
        self._atualizar_botao_enviar()
        # Uma vez só: grab_focus devolve True, e um idle que devolve True se repete
        # para sempre (o chat ficava a 100% de CPU roubando o foco para a caixa de texto).
        GLib.idle_add(lambda: (self.text_input.grab_focus(), False)[1])

    def _criar_estado_vazio(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.add_css_class("empty-state")
        box.set_halign(Gtk.Align.CENTER)
        box.set_valign(Gtk.Align.CENTER)

        icone = Gtk.Image.new_from_icon_name("simba-agente")
        icone.set_pixel_size(64)
        icone.set_halign(Gtk.Align.CENTER)
        icone.add_css_class("empty-icon-img")
        box.append(icone)

        titulo = Gtk.Label(label=_t("Como posso ajudar?"))
        titulo.add_css_class("empty-title")
        titulo.set_margin_top(8)
        box.append(titulo)

        descricao = Gtk.Label(
            label=_t("Converse com seus agentes em um só lugar. Quando o limite de um acaba, o próximo continua automaticamente.")
        )
        descricao.set_wrap(True)
        descricao.set_justify(Gtk.Justification.CENTER)
        descricao.set_max_width_chars(58)
        descricao.add_css_class("empty-desc")
        box.append(descricao)

        sugestoes = Gtk.FlowBox()
        sugestoes.set_selection_mode(Gtk.SelectionMode.NONE)
        sugestoes.set_max_children_per_line(3)
        sugestoes.set_min_children_per_line(1)
        sugestoes.set_row_spacing(8)
        sugestoes.set_column_spacing(8)
        sugestoes.set_halign(Gtk.Align.CENTER)
        sugestoes.set_margin_top(10)
        for texto in (
            _t("Revise este código e aponte problemas"),
            _t("Explique este erro"),
            _t("Escreva testes para esta função"),
        ):
            b = Gtk.Button(label=texto)
            b.add_css_class("suggestion")
            b.set_halign(Gtk.Align.CENTER)
            b.connect("clicked", lambda _b, t=texto: self._usar_sugestao(t))
            sugestoes.append(b)
        box.append(sugestoes)
        self.sugestoes_vazio = sugestoes

        # Primeiro uso (nenhum agente pronto): um clique e já dá para conversar,
        # com os modelos grátis do OpenCode, sem conta nem chave.
        gratis = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        gratis.set_halign(Gtk.Align.CENTER)
        gratis.set_margin_top(14)
        self.btn_gratis = Gtk.Button()
        conteudo = Gtk.Box(spacing=8)
        self.spinner_gratis = Gtk.Spinner()
        self.spinner_gratis.set_visible(False)
        conteudo.append(self.spinner_gratis)
        self.lbl_btn_gratis = Gtk.Label(label=_t("Começar grátis"))
        conteudo.append(self.lbl_btn_gratis)
        self.btn_gratis.set_child(conteudo)
        self.btn_gratis.add_css_class("suggested-action")
        self.btn_gratis.add_css_class("pill")
        self.btn_gratis.set_halign(Gtk.Align.CENTER)
        self.btn_gratis.connect("clicked", lambda _b: self._comecar_gratis())
        gratis.append(self.btn_gratis)
        sub = Gtk.Label(label=_t("Sem conta e sem chave. Você pode conectar Claude, ChatGPT ou Gemini depois."))
        sub.set_wrap(True)
        sub.set_justify(Gtk.Justification.CENTER)
        sub.set_max_width_chars(58)
        sub.add_css_class("empty-desc")
        gratis.append(sub)
        contas = Gtk.Button(label=_t("Usar minha conta"))
        contas.add_css_class("flat")
        contas.set_halign(Gtk.Align.CENTER)
        contas.connect("clicked", lambda _b: self._abrir_central())
        gratis.append(contas)
        gratis.set_visible(False)
        self.box_gratis = gratis
        box.append(gratis)

        # Transparência: no modo grátis, as conversas podem ir para o treino do provedor.
        self.lbl_aviso_gratis = Gtk.Label(label=_t(M.AVISO_GRATIS))
        self.lbl_aviso_gratis.set_wrap(True)
        self.lbl_aviso_gratis.set_justify(Gtk.Justification.CENTER)
        self.lbl_aviso_gratis.set_max_width_chars(64)
        self.lbl_aviso_gratis.set_margin_top(12)
        self.lbl_aviso_gratis.add_css_class("empty-desc")
        self.lbl_aviso_gratis.add_css_class("dim-label")
        self.lbl_aviso_gratis.add_css_class("caption")
        self.lbl_aviso_gratis.set_visible(False)
        box.append(self.lbl_aviso_gratis)
        return box

    def _atualizar_estado_gratis(self):
        """Mostra o "Começar grátis" sem nenhum agente pronto, e o aviso no modo grátis."""
        if not hasattr(self, "box_gratis"):
            return
        sem_agente = not self.candidatos
        self.box_gratis.set_visible(sem_agente)
        self.sugestoes_vazio.set_visible(not sem_agente)
        self.lbl_aviso_gratis.set_visible(bool(self.candidatos) and M.modo_gratis(self.candidatos[0]))

    def _comecar_gratis(self):
        self.btn_gratis.set_sensitive(False)
        self.spinner_gratis.set_visible(True)
        self.spinner_gratis.start()
        instalado = bool(M._achar("opencode"))
        self.lbl_btn_gratis.set_label(_t("Preparando…") if instalado else _t("Instalando, pode levar alguns minutos…"))

        def worker():
            ok = True
            try:
                if not instalado:
                    subprocess.run(["/usr/bin/agentes", "instalar", "opencode"], stdin=subprocess.DEVNULL,
                                   capture_output=True, timeout=1800)
                    ok = bool(M._achar("opencode"))
                if ok:
                    cfg = M.ler_config(verificar=False)
                    if "opencode" not in cfg["ordem"]:
                        cfg["ordem"].append("opencode")
                    cfg["inativos"] = [a for a in cfg["inativos"] if a != "opencode"]
                    M.gravar_config(cfg)
                    M.modelos("opencode", atualizar=True)  # lista atual dos modelos grátis
            except Exception:
                ok = False
            GLib.idle_add(self._gratis_pronto, ok)

        threading.Thread(target=worker, daemon=True).start()

    def _gratis_pronto(self, ok):
        self.spinner_gratis.stop()
        self.spinner_gratis.set_visible(False)
        self.btn_gratis.set_sensitive(True)
        self.lbl_btn_gratis.set_label(_t("Começar grátis"))
        if not ok:
            self._adicionar_sistema(_t("Não deu para preparar o modo grátis. Verifique a internet e tente de novo."))
            return False
        self._carregar_agentes()
        self.text_input.grab_focus()
        return False

    def _criar_composer(self):
        composer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        composer.add_css_class("composer-shell")
        composer.set_hexpand(True)
        composer.set_halign(Gtk.Align.FILL)
        self.composer_shell = composer

        # Anexos do próximo pedido (prints colados, imagens e arquivos)
        self.anexos_pendentes = []
        self.box_anexos = Gtk.FlowBox()
        self.box_anexos.set_selection_mode(Gtk.SelectionMode.NONE)
        self.box_anexos.set_max_children_per_line(30)
        self.box_anexos.set_column_spacing(8)
        self.box_anexos.set_row_spacing(8)
        self.box_anexos.set_homogeneous(False)
        self.box_anexos.add_css_class("anexos-faixa")
        self.box_anexos.set_visible(False)
        composer.append(self.box_anexos)

        self.scroll_txt = Gtk.ScrolledWindow()
        self.scroll_txt.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroll_txt.set_propagate_natural_height(True)
        self.scroll_txt.set_min_content_height(44)
        self.scroll_txt.set_max_content_height(170)
        self.scroll_txt.set_hexpand(True)

        self.text_input = Gtk.TextView()
        self.text_input.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_input.set_accepts_tab(False)
        self.text_input.set_top_margin(7)
        self.text_input.set_bottom_margin(7)
        self.text_input.set_left_margin(4)
        self.text_input.set_right_margin(4)
        self.text_input.add_css_class("composer-text")
        self.text_input_buf = self.text_input.get_buffer()
        self.text_input_buf.connect("changed", self._on_input_text_changed)
        self.scroll_txt.set_child(self.text_input)

        overlay_input = Gtk.Overlay()
        overlay_input.set_hexpand(True)
        overlay_input.set_child(self.scroll_txt)

        self.lbl_placeholder = Gtk.Label(label=_t("Pergunte algo ou dê uma tarefa…"))
        self.lbl_placeholder.set_halign(Gtk.Align.START)
        self.lbl_placeholder.set_valign(Gtk.Align.CENTER)
        self.lbl_placeholder.set_margin_start(10)
        self.lbl_placeholder.add_css_class("composer-placeholder")
        self.lbl_placeholder.set_can_target(False)
        overlay_input.add_overlay(self.lbl_placeholder)
        composer.append(overlay_input)

        rodape = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.btn_anexar = Gtk.Button(icon_name="mail-attachment-symbolic")
        self.btn_anexar.add_css_class("flat")
        self.btn_anexar.add_css_class("stop-button")
        self.btn_anexar.set_valign(Gtk.Align.CENTER)
        self.btn_anexar.set_tooltip_text(_t("Anexar imagens ou arquivos (ou cole um print com Ctrl+V)"))
        self.btn_anexar.connect("clicked", lambda _: self._escolher_anexos())
        rodape.append(self.btn_anexar)

        self.btn_capturar = Gtk.Button(icon_name="applets-screenshooter-symbolic")
        self.btn_capturar.add_css_class("flat")
        self.btn_capturar.add_css_class("stop-button")
        self.btn_capturar.set_valign(Gtk.Align.CENTER)
        self.btn_capturar.set_tooltip_text(_t("Capturar uma área da tela e anexar (Ctrl+Shift+S)"))
        self.btn_capturar.connect("clicked", lambda _: self._capturar_tela())
        rodape.append(self.btn_capturar)

        self.btn_pasta = Gtk.Button()
        self.btn_pasta.add_css_class("flat")
        self.btn_pasta.add_css_class("chip")
        self.btn_pasta.set_valign(Gtk.Align.CENTER)
        self.btn_pasta.connect("clicked", self._escolher_pasta)
        conteudo_pasta = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        conteudo_pasta.append(Gtk.Image.new_from_icon_name("folder-symbolic"))
        self.lbl_pasta = Gtk.Label(label="")
        self.lbl_pasta.set_max_width_chars(18)
        self.lbl_pasta.set_ellipsize(Pango.EllipsizeMode.END)
        conteudo_pasta.append(self.lbl_pasta)
        self.btn_pasta.set_child(conteudo_pasta)
        rodape.append(self.btn_pasta)

        # Modelo do agente selecionado, direto no rodapé (como o seletor do Claude/ChatGPT)
        self.modelo_opcoes = []
        self.modelo_dropdown = Seletor(lambda: self.modelo_opcoes, self._on_modelo_selecionado,
                                       cabecalho=_t("Modelo"), classe="model-chip", mostrar_icone=False)
        self.modelo_dropdown.set_valign(Gtk.Align.CENTER)
        self.modelo_dropdown.set_visible(False)
        rodape.append(self.modelo_dropdown)

        # Modo somente leitura: os agentes podem ler e responder, mas não editam
        # arquivos nem executam comandos que precisariam de aprovação.
        self.btn_seguro = Gtk.ToggleButton()
        self.btn_seguro.add_css_class("flat")
        self.btn_seguro.add_css_class("chip")
        self.btn_seguro.set_valign(Gtk.Align.CENTER)
        conteudo_seguro = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.ico_seguro = Gtk.Image.new_from_icon_name("changes-allow-symbolic")
        conteudo_seguro.append(self.ico_seguro)
        self.lbl_seguro = Gtk.Label(label=_t("Livre"))
        conteudo_seguro.append(self.lbl_seguro)
        self.btn_seguro.set_child(conteudo_seguro)
        self.btn_seguro.set_active(bool(M.ler_config(verificar=False).get("seguro")))
        self._atualizar_seguro_ui()
        self.btn_seguro.connect("toggled", self._on_seguro_alterado)
        rodape.append(self.btn_seguro)

        # Uso do limite do agente (como no Claude): anel + porcentagem; clicado, abre as
        # barras da sessão de 5 h e da semana com quanto falta para zerar.
        self.lbl_uso = Gtk.MenuButton()
        self.lbl_uso.add_css_class("flat")
        self.lbl_uso.add_css_class("uso-chip")
        self.lbl_uso.set_valign(Gtk.Align.CENTER)
        conteudo_uso = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.anel_uso = AnelUso()
        conteudo_uso.append(self.anel_uso)
        self.lbl_uso_pct = Gtk.Label()
        conteudo_uso.append(self.lbl_uso_pct)
        self.lbl_uso.set_child(conteudo_uso)
        self.pop_uso = Gtk.Popover()
        self.pop_uso.add_css_class("uso-pop")
        self.pop_uso.connect("show", lambda *_: self._montar_pop_uso())
        self.lbl_uso.set_popover(self.pop_uso)
        self.lbl_uso.set_visible(False)
        self.uso_dados = None
        rodape.append(self.lbl_uso)

        self.lbl_dica = Gtk.Label(label=_t("Enter envia · Shift+Enter quebra linha · Ctrl+V cola prints"))
        self.lbl_dica.add_css_class("composer-hint")
        self.lbl_dica.set_hexpand(True)
        self.lbl_dica.set_halign(Gtk.Align.START)
        self.lbl_dica.set_ellipsize(Pango.EllipsizeMode.END)
        rodape.append(self.lbl_dica)
        espaco_rodape = Gtk.Box()
        espaco_rodape.set_hexpand(True)
        rodape.append(espaco_rodape)   # mic e enviar à direita mesmo sem a dica

        # Ditado por voz (mesma transcrição do Draco)
        self.btn_mic = Gtk.Button(icon_name="audio-input-microphone-symbolic")
        self.btn_mic.add_css_class("flat")
        self.btn_mic.add_css_class("stop-button")
        self.btn_mic.set_valign(Gtk.Align.CENTER)
        self.btn_mic.set_tooltip_text(_t("Ditar por voz (Ctrl+M)"))
        self.btn_mic.set_visible(self.gravador is not None)
        self.btn_mic.connect("clicked", lambda _: self._alternar_ditado())
        rodape.append(self.btn_mic)

        self.btn_parar = Gtk.Button(icon_name="process-stop-symbolic")
        self.btn_parar.add_css_class("flat")
        self.btn_parar.add_css_class("stop-button")
        self.btn_parar.set_valign(Gtk.Align.CENTER)
        self.btn_parar.set_visible(False)
        self.btn_parar.set_tooltip_text(_t("Interromper (Esc)"))
        self.btn_parar.connect("clicked", lambda _: self._interromper())
        rodape.append(self.btn_parar)

        self.btn_enviar = Gtk.Button(icon_name="go-up-symbolic")
        self.btn_enviar.add_css_class("send-button")
        self.btn_enviar.set_valign(Gtk.Align.CENTER)
        self.btn_enviar.set_tooltip_text(_t("Enviar (Enter)"))
        self.btn_enviar.connect("clicked", lambda _: self._on_enviar())
        rodape.append(self.btn_enviar)

        composer.append(rodape)

        # Destaca a moldura do composer enquanto o campo de texto tem foco
        foco = Gtk.EventControllerFocus()
        foco.connect("enter", lambda *_: composer.add_css_class("focado"))
        foco.connect("leave", lambda *_: composer.remove_css_class("focado"))
        self.text_input.add_controller(foco)

        return composer

    # ── navegador embutido ─────────────────────────────────────────────────
    def _on_alternar_navegador(self, botao):
        if botao.get_active():
            self.navegador.mostrar()
        else:
            self._esconder_navegador()

    def _abrir_lateral(self, fracao=0.4):
        if not self.lateral.get_visible():
            self.lateral.set_visible(True)
            largura = self.get_width() or 1400
            # conversa à esquerda com ~40 % da janela, painel com o resto
            self.divisao.set_position(max(420, int(largura * fracao)))

    def _fechar_lateral_se_vazia(self):
        nav = self.navegador is not None and self.navegador.get_visible()
        if not nav and not self.painel_codigo.get_visible():
            self.lateral.set_visible(False)

    def _mostrar_navegador(self):
        if self.painel_codigo.get_visible():
            self.painel_codigo.set_visible(False)
        if not self.navegador.get_visible():
            self.navegador.set_visible(True)
            self._abrir_lateral(0.4)
        self.lateral.set_visible(True)
        if not self.btn_navegador.get_active():
            self.btn_navegador.set_active(True)

    def _esconder_navegador(self):
        self.navegador.set_visible(False)
        self._fechar_lateral_se_vazia()
        if self.btn_navegador.get_active():
            self.btn_navegador.set_active(False)
        # a conversa volta a ser o foco: cursor na caixa de mensagem
        self.text_input.grab_focus()

    # ── painel de código (como os Artifacts do Claude / Canvas do ChatGPT) ──
    def _preparar_painel_codigo(self):
        if self.navegador is not None and self.navegador.get_visible():
            self.navegador.set_visible(False)
            if self.btn_navegador.get_active():
                self.btn_navegador.set_active(False)
        self.painel_codigo.set_visible(True)
        self._abrir_lateral(0.5)
        self.lateral.set_visible(True)

    def _mostrar_codigo_lateral(self, lang, texto, titulo=""):
        self._preparar_painel_codigo()
        self.painel_codigo.mostrar_codigo(texto, lang, titulo)

    def _mostrar_arquivo_lateral(self, caminho, linha=None):
        erro = self.painel_codigo.mostrar_arquivo(caminho, linha)
        if erro is None:
            self._preparar_painel_codigo()
        return erro

    def _painel_codigo_fechado(self):
        self._fechar_lateral_se_vazia()
        self.text_input.grab_focus()

    # ── simba-chat: pedidos dos agentes ──────────────────────────────────────
    def _tratar_integracao(self, pedido, responder):
        cmd = pedido.get("cmd")
        if cmd == "estado":
            responder({"ok": True, "respondendo": self._rodando(), "pasta": str(self.work_dir),
                       "painel": self.painel_codigo.get_visible()})
        elif cmd == "mostrar":
            erro = self._mostrar_arquivo_lateral(pedido.get("arquivo", ""), pedido.get("linha"))
            responder({"ok": erro is None, "erro": erro} if erro else
                      {"ok": True, "msg": f"aberto no painel: {pedido.get('arquivo')}"})
        elif cmd == "codigo":
            self._mostrar_codigo_lateral(pedido.get("lang", ""), pedido.get("texto", ""), pedido.get("titulo", ""))
            responder({"ok": True, "msg": "mostrado no painel"})
        elif cmd == "fechar":
            if self.painel_codigo.get_visible():
                self.painel_codigo.fechar()
            responder({"ok": True})
        elif cmd == "notificar":
            texto = str(pedido.get("texto") or "").strip()[:400]
            if not texto:
                responder({"ok": False, "erro": "texto vazio"})
                return
            self._adicionar_sistema(f"🔔 {texto}", registro=False)
            if not self.is_active():
                try:
                    subprocess.Popen(["notify-send", "-a", _t("Agentes de IA"), "-i", "simba-agente",
                                      _t("Agentes de IA"), texto], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, start_new_session=True)
                except OSError:
                    pass
            responder({"ok": True})
        elif cmd == "perguntar":
            self._adicionar_pergunta(str(pedido.get("pergunta") or "").strip(),
                                     [str(o) for o in (pedido.get("opcoes") or []) if str(o).strip()][:8],
                                     responder)
        else:
            responder({"ok": False, "erro": f"comando desconhecido: {cmd}"})

    def _adicionar_pergunta(self, pergunta, opcoes, responder):
        """Cartão com a pergunta do agente e botões; a escolha volta para o simba-chat."""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card.add_css_class("pergunta-card")
        rot = Gtk.Label(label=_t("O agente precisa da sua decisão"), xalign=0)
        rot.add_css_class("pergunta-rotulo")
        card.append(rot)
        titulo = Gtk.Label(label=pergunta or _t("Como continuar?"), xalign=0, wrap=True, selectable=True)
        titulo.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        titulo.add_css_class("pergunta-titulo")
        card.append(titulo)
        botoes = Gtk.FlowBox()
        botoes.set_selection_mode(Gtk.SelectionMode.NONE)
        botoes.set_max_children_per_line(4)
        botoes.set_column_spacing(8)
        botoes.set_row_spacing(8)
        card.append(botoes)
        livre = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        entrada = Gtk.Entry()
        entrada.set_hexpand(True)
        entrada.set_placeholder_text(_t("Ou escreva outra resposta…") if opcoes else _t("Sua resposta…"))
        livre.append(entrada)
        enviar = Gtk.Button(icon_name="go-up-symbolic")
        enviar.add_css_class("send-button")
        enviar.set_tooltip_text(_t("Responder"))
        livre.append(enviar)
        card.append(livre)
        estado = {"feito": False}

        def concluir(resposta, cancelada=False):
            if estado["feito"]:
                return
            estado["feito"] = True
            if p in self.perguntas:
                self.perguntas.remove(p)
            card.add_css_class("respondida")
            botoes.set_sensitive(False)
            livre.set_visible(False)
            if cancelada:
                rot.set_label(_t("Pergunta cancelada (a resposta terminou)"))
                responder({"ok": False, "erro": "a resposta do agente terminou antes da escolha"})
                return
            rot.set_label(f"{_t('Você respondeu')}: {resposta}")
            self.conversa_mensagens.append({"tipo": "sistema", "quando": time.time(),
                                            "texto": f"{pergunta} → {resposta}"})
            self._agendar_salvamento()
            responder({"ok": True, "resposta": resposta})
            self.ultimo_sinal = time.monotonic()

        for o in opcoes:
            b = Gtk.Button(label=o)
            b.add_css_class("pergunta-opcao")
            b.add_css_class("pill")
            b.connect("clicked", lambda _b, o=o: concluir(o))
            botoes.append(b)
        botoes.set_visible(bool(opcoes))

        def livre_enviar(*_a):
            t = entrada.get_text().strip()
            if t:
                concluir(t)
        entrada.connect("activate", livre_enviar)
        enviar.connect("clicked", livre_enviar)
        p = {"card": card, "concluir": concluir}
        self.perguntas.append(p)
        self.box_mensagens.append(card)
        self._scroll_para_fim(forcar=True)
        if not self.is_active():
            self._trazer_janela()
        GLib.idle_add(lambda: ((botoes.get_child_at_index(0) or entrada).grab_focus(), False)[1])

    def _cancelar_perguntas(self):
        for p in list(self.perguntas):
            p["concluir"](None, cancelada=True)

    def _usar_sugestao(self, texto):
        self.text_input_buf.set_text(texto)
        fim = self.text_input_buf.get_end_iter()
        self.text_input_buf.place_cursor(fim)
        self.text_input.grab_focus()
        self._on_input_text_changed(self.text_input_buf)

    # ── Seletor de agente com logos ──────────────────────────────────────────
    def _icone_item(self, aid):
        if not aid or aid == "auto":
            return marcas.GENERICO
        return marcas.icone_agente(aid, M.modelo_escolhido(aid, M.ler_config(verificar=False)))

    def _atualizar_icone_seletor(self):
        self.dropdown.atualizar()

    # ── Anexos (prints colados, imagens e arquivos) ──────────────────────────
    def _on_colar(self, view):
        """Ctrl+V: imagem na área de transferência vira anexo; texto cola normal."""
        clip = view.get_clipboard()
        formatos = clip.get_formats()
        mimes = formatos.get_mime_types() or []
        gtypes = formatos.get_gtypes() or []
        # Arquivos copiados no gerenciador de arquivos (Nautilus etc.)
        if formatos.contain_gtype(Gdk.FileList) or "text/uri-list" in mimes:
            view.stop_emission_by_name("paste-clipboard")
            clip.read_value_async(Gdk.FileList, GLib.PRIORITY_DEFAULT, None, self._colar_arquivos)
            return
        # Texto tem prioridade: LibreOffice, editores etc. copiam texto junto com
        # uma imagem do trecho; print de tela e "copiar imagem" só trazem imagem.
        tem_texto = (any(m.startswith("text/plain") or m in ("UTF8_STRING", "STRING", "TEXT") for m in mimes)
                     or any(GObject.type_is_a(t, GObject.TYPE_STRING) for t in gtypes))
        if tem_texto:
            return
        tem_textura = any(GObject.type_is_a(t, Gdk.Texture) for t in gtypes)
        if tem_textura or any(m.startswith("image/") for m in mimes):
            view.stop_emission_by_name("paste-clipboard")
            clip.read_texture_async(None, self._colar_textura)

    def _colar_textura(self, clip, resultado):
        try:
            textura = clip.read_texture_finish(resultado)
        except GLib.Error as e:
            self._adicionar_sistema(f"{_t('Não foi possível colar a imagem:')} {e.message}", registro=False)
            return
        if textura is not None:
            self._anexar_textura(textura)

    def _colar_arquivos(self, clip, resultado):
        try:
            lista = clip.read_value_finish(resultado)
        except GLib.Error:
            lista = None
        caminhos = [f.get_path() for f in lista.get_files() if f.get_path()] if lista else []
        for c in caminhos:
            self._adicionar_anexo(c)
        if not caminhos:  # links da web etc.: cola como texto
            clip.read_text_async(None, self._colar_texto)

    def _colar_texto(self, clip, resultado):
        try:
            texto = clip.read_text_finish(resultado)
        except GLib.Error:
            return
        if texto:
            self.text_input_buf.delete_selection(True, True)
            self.text_input_buf.insert_at_cursor(texto)

    def _anexar_textura(self, textura):
        try:
            caminho = anexos.salvar_textura(textura)
        except (OSError, GLib.Error) as e:
            self._adicionar_sistema(f"{_t('Não foi possível guardar a imagem:')} {e}", registro=False)
            return
        self._adicionar_anexo(str(caminho))

    def _capturar_tela(self):
        """Esconde o chat, deixa escolher uma área (ou janela) e anexa o print."""
        if getattr(self, "capturando", False):
            return
        self.capturando = True
        self.estava_maximizada = self.is_maximized()
        self.set_visible(False)
        # espera o compositor tirar a janela da tela antes de congelar a imagem
        GLib.timeout_add(350, lambda: threading.Thread(target=self._capturar_thread, daemon=True).start() and False)

    def _capturar_thread(self):
        destino = anexos.novo_caminho("png")
        caminho, erro = None, None
        script = shutil.which("simba-capture-screenshot") or "/usr/share/simba/bin/simba-capture-screenshot"
        try:
            if Path(script).exists():
                env = dict(os.environ, SIMBA_SCREENSHOT_DIR=str(destino.parent))
                r = subprocess.run([script, "smart", "save"], env=env, stdin=subprocess.DEVNULL,
                                   capture_output=True, text=True, timeout=300)
                linhas = [l.strip() for l in r.stdout.splitlines() if l.strip().endswith(".png")]
                caminho = linhas[-1] if linhas else None
            elif shutil.which("grim") and shutil.which("slurp"):
                area = subprocess.run(["slurp"], capture_output=True, text=True, timeout=300).stdout.strip()
                if area and subprocess.run(["grim", "-g", area, str(destino)], timeout=30).returncode == 0:
                    caminho = str(destino)
            else:
                erro = _t("Ferramenta de captura não encontrada (grim e slurp).")
        except (OSError, subprocess.TimeoutExpired) as e:
            erro = str(e)
        GLib.idle_add(self._captura_pronta, caminho, erro)

    def _captura_pronta(self, caminho, erro):
        self.capturando = False
        self.set_visible(True)
        if getattr(self, "estava_maximizada", True):
            self.maximize()
        self.present()
        if caminho and Path(caminho).is_file():
            os.chmod(caminho, 0o600)
            self._adicionar_anexo(caminho)
        elif erro:
            self._adicionar_sistema(f"{_t('Não foi possível capturar a tela:')} {erro}", registro=False)
        self.text_input.grab_focus()
        return False

    def _escolher_anexos(self):
        dialog = Gtk.FileDialog(title=_t("Anexar imagens ou arquivos"))
        dialog.set_initial_folder(Gio.File.new_for_path(str(self.work_dir)))
        filtros = Gio.ListStore.new(Gtk.FileFilter)
        f_img = Gtk.FileFilter()
        f_img.set_name(_t("Imagens"))
        f_img.add_mime_type("image/*")
        f_todos = Gtk.FileFilter()
        f_todos.set_name(_t("Todos os arquivos"))
        f_todos.add_pattern("*")
        filtros.append(f_todos)
        filtros.append(f_img)
        dialog.set_filters(filtros)
        dialog.open_multiple(self, None, self._anexos_escolhidos)

    def _anexos_escolhidos(self, dialog, resultado):
        try:
            lista = dialog.open_multiple_finish(resultado)
        except GLib.Error:
            return
        for i in range(lista.get_n_items()):
            caminho = lista.get_item(i).get_path()
            if caminho:
                self._adicionar_anexo(caminho)

    def _adicionar_anexo(self, caminho):
        caminho = str(caminho)
        if caminho in self.anexos_pendentes:
            return
        self.anexos_pendentes.append(caminho)
        self.box_anexos.append(self._chip_anexo(caminho, removivel=True))
        self.box_anexos.set_visible(True)
        self._atualizar_botao_enviar()
        self.text_input.grab_focus()

    def _remover_anexo(self, caminho, chip):
        if caminho in self.anexos_pendentes:
            self.anexos_pendentes.remove(caminho)
        filho = chip.get_parent()  # FlowBoxChild
        if filho is not None and filho.get_parent() is self.box_anexos:
            self.box_anexos.remove(filho)
        self.box_anexos.set_visible(bool(self.anexos_pendentes))
        self._atualizar_botao_enviar()

    def _limpar_anexos(self):
        self.anexos_pendentes = []
        self.box_anexos.remove_all()
        self.box_anexos.set_visible(False)
        self._atualizar_botao_enviar()

    def _chip_anexo(self, caminho, removivel=False):
        """Miniatura (imagem) ou nome (arquivo); clicar abre no aplicativo padrão."""
        caixa = Gtk.Overlay()
        caixa.add_css_class("anexo")
        existe = Path(caminho).exists()
        miniatura = anexos.miniatura(caminho, 132, 92) if existe and anexos.eh_imagem(caminho) else None
        if miniatura is not None:
            foto = Gtk.Picture.new_for_paintable(miniatura)
            foto.set_can_shrink(False)
            foto.add_css_class("anexo-foto")
            conteudo = foto
        else:
            conteudo = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            conteudo.add_css_class("anexo-arquivo")
            icone = "image-x-generic-symbolic" if anexos.eh_imagem(caminho) else "text-x-generic-symbolic"
            conteudo.append(Gtk.Image.new_from_icon_name(icone))
            nome = Gtk.Label(label=Path(caminho).name)
            nome.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            nome.set_max_width_chars(24)
            conteudo.append(nome)
        botao = Gtk.Button()
        botao.add_css_class("flat")
        botao.add_css_class("anexo-botao")
        botao.set_child(conteudo)
        botao.set_tooltip_text(caminho if existe else f"{caminho} ({_t('arquivo não existe mais')})")
        botao.connect("clicked", lambda _b: self._abrir_arquivo(caminho))
        caixa.set_child(botao)
        if removivel:
            fechar = Gtk.Button(icon_name="window-close-symbolic")
            fechar.add_css_class("anexo-remover")
            fechar.add_css_class("circular")
            fechar.set_halign(Gtk.Align.END)
            fechar.set_valign(Gtk.Align.START)
            fechar.set_tooltip_text(_t("Remover anexo"))
            fechar.connect("clicked", lambda _b: self._remover_anexo(caminho, caixa))
            caixa.add_overlay(fechar)
        return caixa

    def _abrir_arquivo(self, caminho):
        if not Path(caminho).exists():
            return
        Gtk.FileLauncher.new(Gio.File.new_for_path(caminho)).launch(self, None, None)

    def _atualizar_pasta_ui(self):
        nome = self.work_dir.name or str(self.work_dir)
        if hasattr(self, "lbl_pasta"):
            self.lbl_pasta.set_text(nome)
        if hasattr(self, "btn_pasta"):
            self.btn_pasta.set_tooltip_text(f"{_t('Pasta de trabalho:')} {self.work_dir}")
        if hasattr(self, "btn_dir"):
            self.btn_dir.set_tooltip_text(f"{_t('Pasta de trabalho:')} {self.work_dir}")

    def _atualizar_botao_enviar(self):
        if not hasattr(self, "btn_enviar"):
            return
        inicio, fim = self.text_input_buf.get_bounds()
        tem_texto = bool(self.text_input_buf.get_text(inicio, fim, True).strip())
        self.btn_enviar.set_sensitive(tem_texto or bool(getattr(self, "anexos_pendentes", None)))

    def _carregar_agentes(self):
        cfg = M.ler_config(verificar=False)
        self.candidatos = M.candidatos(cfg, verificar=False, seguro=bool(cfg.get("seguro")))

        # Preserva a escolha do usuário ao recarregar (ex.: depois de trocar o modelo)
        anterior = self.dropdown.atual().get("id") if self.dropdown_items else None

        itens = [{"id": "auto", "nome": _t("Automático (Cascata)"), "curto": _t("Automático"),
                  "sub": _t("Usa o primeiro disponível e troca sozinho quando o limite acaba")}]
        for i, a in enumerate(self.candidatos):
            nome = M.AGENTES.get(a, {}).get("nome", a)
            modelo = M.modelo_escolhido(a, cfg)
            ate = M.esgotado_ate(a)
            it = {"id": a, "nome": nome, "curto": nome,
                  "sub": modelo or _t("Modelo padrão do agente")}
            if ate:
                it["aviso"] = f"{_t('volta')} {M.hora(ate)}"
            if i == 0:
                it["separar"] = True
            itens.append(it)
        self.dropdown_items = itens
        self.dropdown.atualizar(itens)
        if not self.dropdown.selecionar_id(anterior):
            self.dropdown.set_selected(0)

        if not self._rodando():
            aid = self.dropdown.atual().get("id")
            self.agente_atual = None if aid in (None, "auto") else aid
        self._atualizar_modelo_dropdown()
        self._atualizar_uso_ui()
        self._atualizar_estado_gratis()

    def _on_agente_selecionado(self, _i, item):
        # Durante uma resposta, agente_atual é quem está respondendo
        if not self._rodando():
            escolhido = item.get("id")
            self.agente_atual = None if escolhido == "auto" else escolhido
        self._atualizar_modelo_dropdown()
        self._atualizar_uso_ui()

    def _atualizar_modelo_dropdown(self):
        if not hasattr(self, "modelo_dropdown"):
            return
        agente = self.dropdown.atual().get("id")
        if not agente or agente == "auto" or agente not in M.AGENTES:
            self.modelo_dropdown.set_visible(False)
            return

        cfg = M.ler_config(verificar=False)
        atual = M.modelo_escolhido(agente, cfg)
        nome = M.AGENTES.get(agente, {}).get("nome", agente)
        opcoes = [{"id": "", "valor": "", "nome": _t("Padrão do agente"), "curto": _t("Modelo padrão"),
                   "sub": _t("O que o %1 escolher", nome)}]
        vistos = {""}
        for o in M.modelos(agente):
            valor = str(o.get("valor", "")).strip()
            if valor and valor not in vistos:
                vistos.add(valor)
                rot = o.get("rotulo") or valor
                opcoes.append({"id": valor, "valor": valor, "nome": rot, "curto": rot,
                               "sub": valor if valor != rot else ""})
        if atual and atual not in vistos:
            opcoes.append({"id": atual, "valor": atual, "nome": atual, "curto": atual})

        self.modelo_opcoes = opcoes
        self.modelo_dropdown.atualizar(opcoes)
        if not self.modelo_dropdown.selecionar_id(atual or ""):
            self.modelo_dropdown.set_selected(0)
        self.modelo_dropdown.set_visible(len(opcoes) > 1)

    def _on_modelo_selecionado(self, _i, item):
        agente = self.dropdown.atual().get("id")
        if not agente or agente == "auto":
            return
        self._definir_modelo(agente, item.get("valor", ""))

    def _definir_modelo(self, agente, valor):
        cfg = M.ler_config(verificar=False)
        atual = M.modelo_escolhido(agente, cfg)
        if (valor or "") == (atual or ""):
            return False
        mods = cfg.get("modelos")
        if not isinstance(mods, dict):
            mods = {}
            cfg["modelos"] = mods
        if valor:
            mods[agente] = valor
        else:
            mods.pop(agente, None)
        M.gravar_config(cfg)
        self._carregar_agentes()
        # Conversa em andamento: o modelo novo relê tudo no próximo pedido (sem o cache
        # do anterior) e pode ter de resumir a conversa — avisa, para a demora não parecer travamento.
        if self.sessoes.get(agente) and agente in self.conversas_iniciadas:
            nome = M.AGENTES.get(agente, {}).get("nome", agente)
            self._adicionar_sistema(
                f"{nome}: {_t('modelo trocado para')} {valor or _t('o padrão do agente')}. "
                + _t("Ele vai reler a conversa inteira no próximo pedido; a primeira resposta pode demorar mais."),
                registro=False)
        return False

    def _escolher_pasta(self, _btn):
        dialog = Gtk.FileDialog(title=_t("Selecionar Pasta de Trabalho"))
        dialog.set_initial_folder(Gio.File.new_for_path(str(self.work_dir)))
        dialog.select_folder(self, None, self._on_pasta_selecionada)

    def _on_pasta_selecionada(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                self._mudar_pasta(Path(folder.get_path()))
                self._adicionar_sistema(f"{_t('Pasta alterada para:')} {self.work_dir}")
        except Exception:
            pass

    def _mudar_pasta(self, caminho):
        if caminho != self.work_dir:
            # As sessões dos agentes são da pasta (o Claude procura a sessão pelo
            # projeto): em outra pasta, quem continuar recebe o histórico no pedido.
            self.sessoes.clear()
            self.conversas_iniciadas.clear()
        self.work_dir = caminho
        self._atualizar_pasta_ui()


    def _limpar_chat(self, descartar=False):
        if descartar:
            self.conversa_id = None
            self.conversa_criada = None
            self.conversa_mensagens = []
            self.ativo_registro = None
        self.fila = []
        self._interromper()
        self._salvar_conversa()
        while True:
            child = self.box_mensagens.get_first_child()
            if not child:
                break
            self.box_mensagens.remove(child)
        self.empty_state.set_visible(True)
        self.usados.clear()
        self.conversas_iniciadas.clear()
        self.sessoes = {}
        self.fila = []
        self.interrompido = False
        self.ativo_texto = ""
        self.anterior_passagem = None
        self.agente_atual = None
        self.ativo_mensagem = None
        self.ativo_bloco = None
        self.ativo_digitando = None
        self.ativo_modelo = None
        self.ativo_parser = None
        self.ativo_renderizado = False
        self.ativo_registro = None
        self.conversa_id = None
        self.conversa_criada = None
        self.conversa_mensagens = []
        self.precisa_contexto = False
        if self.salvar_fonte:
            try:
                GLib.source_remove(self.salvar_fonte)
            except Exception:
                pass
            self.salvar_fonte = 0
        self.btn_historico.set_sensitive(True)
        self.text_input_buf.set_text("")
        self._limpar_anexos()
        self.text_input.grab_focus()

    def _on_input_text_changed(self, buf):
        if hasattr(self, "lbl_placeholder"):
            self.lbl_placeholder.set_visible(buf.get_char_count() == 0)
        self._atualizar_botao_enviar()

    def _on_key_pressed(self, _controller, keyval, _keycode, state):
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if not (state & Gdk.ModifierType.SHIFT_MASK):
                self._on_enviar()
                return True
        elif keyval == Gdk.KEY_Escape:
            if self._rodando() or (self.gravador and self.gravador.gravando):
                self._interromper()
                return True
        elif keyval in (Gdk.KEY_m, Gdk.KEY_M) and (state & Gdk.ModifierType.CONTROL_MASK):
            if self.gravador:
                self._alternar_ditado()
                return True
        elif keyval == Gdk.KEY_Up:
            if self.text_input_buf.get_char_count() == 0:
                for msg in reversed(self.conversa_mensagens):
                    if msg.get("tipo") == "user" and msg.get("texto"):
                        self.text_input_buf.set_text(msg["texto"])
                        end_iter = self.text_input_buf.get_end_iter()
                        self.text_input_buf.place_cursor(end_iter)
                        return True
        elif keyval == Gdk.KEY_l and (state & Gdk.ModifierType.CONTROL_MASK):
            self._limpar_chat()
            return True
        elif (
            keyval in (Gdk.KEY_h, Gdk.KEY_H)
            and (state & Gdk.ModifierType.CONTROL_MASK)
            and (state & Gdk.ModifierType.SHIFT_MASK)
        ):
            # Histórico removido; atalho inativo
            return True
        elif (
            keyval in (Gdk.KEY_a, Gdk.KEY_A)
            and (state & Gdk.ModifierType.CONTROL_MASK)
            and (state & Gdk.ModifierType.SHIFT_MASK)
        ):
            self._abrir_central()
            return True
        return False

    def _on_window_key_pressed(self, _controller, keyval, _keycode, state):
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        foco = self.get_focus()
        no_texto = isinstance(foco, (Gtk.Text, Gtk.TextView)) and foco.get_editable()
        if ctrl and not shift and keyval in (Gdk.KEY_l, Gdk.KEY_L):
            self._limpar_chat()
            return True
        if ctrl and shift and keyval in (Gdk.KEY_a, Gdk.KEY_A):
            self._abrir_central()
            return True
        if ctrl and shift and keyval in (Gdk.KEY_b, Gdk.KEY_B) and self.navegador:
            self.btn_navegador.set_active(not self.btn_navegador.get_active())
            return True
        if ctrl and not shift and keyval in (Gdk.KEY_f, Gdk.KEY_F):
            self._abrir_busca()
            return True
        if ctrl and shift and keyval in (Gdk.KEY_s, Gdk.KEY_S):
            self._capturar_tela()
            return True
        if ctrl and not shift and keyval in (Gdk.KEY_o, Gdk.KEY_O):
            self._escolher_anexos()
            return True
        if ctrl and not shift and keyval in (Gdk.KEY_v, Gdk.KEY_V) and not no_texto:
            # Ctrl+V com o foco fora da caixa de texto (ex.: depois de clicar numa
            # resposta): cola na caixa do chat, imagem ou texto.
            self.text_input.grab_focus()
            self.text_input.emit("paste-clipboard")
            return True
        if keyval == Gdk.KEY_Escape:
            if self._rodando() or (self.gravador and self.gravador.gravando):
                self._interromper()
                return True
        elif keyval in (Gdk.KEY_m, Gdk.KEY_M) and (state & Gdk.ModifierType.CONTROL_MASK):
            if self.gravador:
                self._alternar_ditado()
                return True
        return False

    def _on_file_drop(self, _target, value, _x, _y):
        if isinstance(value, Gdk.FileList):
            caminhos = [f.get_path() for f in value.get_files() if f.get_path()]
            for c in caminhos:
                self._adicionar_anexo(c)
            return bool(caminhos)
        return False

    def _on_textura_drop(self, _target, value, _x, _y):
        if isinstance(value, Gdk.Texture):
            self._anexar_textura(value)
            return True
        return False


    # ── Envio, fila e execução ───────────────────────────────────────────────
    def _rodando(self):
        return self.proc is not None and not self.finalizado

    def _on_enviar(self):
        start, end = self.text_input_buf.get_bounds()
        texto = self.text_input_buf.get_text(start, end, True).strip()
        arquivos = list(self.anexos_pendentes)
        if not texto and not arquivos:
            return
        self.text_input_buf.set_text("")
        self._limpar_anexos()
        self.empty_state.set_visible(False)
        item = {"texto": texto, "anexos": arquivos}

        # O agente ainda está respondendo: a mensagem espera a vez dela. (Antes
        # ela era escrita no pty, mas no modo print os agentes não leem a
        # entrada e a mensagem se perdia.)
        if self._rodando():
            item["widgets"] = self._adicionar_bolha_usuario(texto, registro=False, na_fila=True, anexos=arquivos)
            self.fila.append(item)
            return
        self._enviar_pedido([item])

    def _enviar_pedido(self, itens):
        """itens: [{"texto", "anexos", "widgets" (bolha já mostrada na fila)}]."""
        partes = []
        for item in itens:
            texto, arquivos = item["texto"], item.get("anexos") or []
            if item.get("widgets"):
                item["widgets"]["fila"].set_visible(False)
                self._registrar_usuario(texto, arquivos)
            else:
                self._adicionar_bolha_usuario(texto, anexos=arquivos)
            partes.append(anexos.texto_para_agente(texto, arquivos))
        pedido = "\n\n".join(partes)
        if self.interrompido:
            quem = ("cancelada automaticamente pelo chat (" + self.interrompido + ")"
                    if isinstance(self.interrompido, str) else "interrompida pelo usuário")
            pedido = (
                f"(A sua resposta anterior foi {quem} antes de terminar. "
                "Considere o que já tinha sido feito e siga com o pedido abaixo.)\n\n" + pedido
            )
            self.interrompido = False
        self._iniciar_execucao(pedido)

    def _proximo_da_fila(self):
        if not self.fila:
            return
        itens, self.fila = self.fila, []
        self._enviar_pedido(itens)

    def _devolver_fila(self):
        """Interrompido: as mensagens da fila (e anexos) voltam para a caixa de texto."""
        if not self.fila:
            return
        textos = [i["texto"] for i in self.fila if i["texto"]]
        for item in self.fila:
            linha = item["widgets"].get("linha")
            if linha is not None and linha.get_parent() is self.box_mensagens:
                self.box_mensagens.remove(linha)
            for caminho in item.get("anexos") or []:
                self._adicionar_anexo(caminho)
        self.fila = []
        inicio, fim = self.text_input_buf.get_bounds()
        atual = self.text_input_buf.get_text(inicio, fim, True).strip()
        self.text_input_buf.set_text("\n\n".join(textos + ([atual] if atual else [])))
        self.text_input_buf.place_cursor(self.text_input_buf.get_end_iter())

    def _agente_escolhido(self):
        aid = self.dropdown.atual().get("id")
        return None if aid in (None, "auto") else aid

    def _iniciar_execucao(self, pedido, agente_forcado=None, arq_passagem=None):
        cfg = M.ler_config(verificar=False)
        seguro = bool(cfg.get("seguro"))
        agente = agente_forcado or self._agente_escolhido()
        if agente and not agente_forcado and seguro and not M.suporta_seguro(agente):
            nome = M.AGENTES.get(agente, {}).get("nome", agente)
            self._adicionar_sistema(
                f"{nome} {_t('não tem modo somente leitura. Desligue o modo ou escolha outro agente.')}"
            )
            self._proximo_da_fila()
            return
        if not agente:
            cands = [a for a in M.candidatos(cfg, pular=self.usados, verificar=False, seguro=seguro)
                     if not M.esgotado_ate(a)]
            if not cands:
                cands = M.candidatos(cfg, verificar=False, seguro=seguro)
            if not cands:
                self._adicionar_sistema(
                    _t("Nenhum agente com modo somente leitura disponível.") if seguro else
                    _t("Nenhum agente disponível no momento. Abra as Configurações para conectar suas contas.")
                )
                return
            agente = cands[0]

        info = M.AGENTES[agente]
        sessao = self.sessoes.get(agente) if info.get("retomar") else None
        continuar = (not sessao and not info.get("retomar") and agente in self.conversas_iniciadas
                     and bool(info.get("continue")))
        # Agente que ainda não participou desta conversa (ou cuja sessão não
        # pôde ser retomada) recebe o histórico junto com o pedido.
        if not agente_forcado and not sessao and not continuar:
            pedido = self._pedido_com_contexto(pedido)
        # sessão nova de um agente: ele fica sabendo do navegador embutido
        if not sessao and not continuar:
            extras = []
            if self.navegador and self.navegador.socket:
                extras.append(navegador.INSTRUCAO_AGENTE)
            if getattr(self, "integracoes", None) and self.integracoes.socket:
                extras.append(integracoes.INSTRUCAO_AGENTE)
            if not seguro:
                extras.append(integracoes.INSTRUCAO_LIVRE)
            if extras:
                pedido = "\n\n".join(extras) + "\n\n" + pedido
        self.precisa_contexto = False

        cmd = M.montar_comando(agente, pedido, cfg, sessao=sessao, continuar=continuar, seguro=seguro)
        # OpenCode: na cascata, o arquivo de passagem vai anexado com --file
        # (leitura mais confiável do que o caminho no meio do texto).
        if arq_passagem and agente == "opencode":
            curto = (
                "Você vai continuar um trabalho que outro agente de IA começou e não terminou "
                "porque o limite de uso dele acabou. O contexto completo está no arquivo anexo. "
                "Leia-o inteiro, depois confira o que já foi feito no disco e continue exatamente "
                "de onde parou, sem pedir para o usuário repetir nada."
            )
            cmd = M.montar_comando(agente, curto, cfg, seguro=seguro)
            cmd = cmd[:-1] + ["--file", str(arq_passagem), cmd[-1]]

        self.agente_atual = agente
        self.usados.add(agente)
        self.conversas_iniciadas.add(agente)
        self.inicio_agente = time.time()
        self.exec_seq += 1
        eid = self.exec_seq
        self.exec_atual = eid
        self.finalizado = False
        self.ativo_texto = ""

        self.btn_historico.set_sensitive(False)
        self._adicionar_bolha_assistente(agente)
        if seguro and self.ativo_registro is not None:
            self.ativo_registro["seguro"] = True

        mestre, escravo = pty.openpty()
        definir_tamanho_pty(escravo, 60, 240)
        env = dict(os.environ)
        env.update(AGENTES_ATUAL=agente, PYTHONUNBUFFERED="1", TERM="xterm-256color",
                   COLUMNS="240", LINES="60")
        if self.navegador and self.navegador.socket:
            env["SIMBA_NAVEGADOR"] = self.navegador.socket
        if getattr(self, "integracoes", None) and self.integracoes.socket:
            env["SIMBA_CHAT"] = self.integracoes.socket
        try:
            proc = subprocess.Popen(
                cmd, stdin=escravo, stdout=escravo, stderr=escravo, cwd=str(self.work_dir),
                env=env, start_new_session=True, close_fds=True,
            )
        except Exception as e:  # noqa: BLE001
            os.close(escravo)
            os.close(mestre)
            self.ativo_texto = f"⚠ {_t('Erro ao iniciar')} {info['nome']}: {e}"
            self._finalizar_resposta(notificar=False)
            return
        os.close(escravo)
        self.proc = proc

        def na_gui(fn, *args):
            def chamar():
                if self.exec_atual == eid:
                    fn(*args)
                return False
            GLib.idle_add(chamar)

        parser = AgentStreamParser(
            on_status=lambda s: na_gui(self._atualizar_status_ativo, s),
            on_text=lambda t: na_gui(self._anexar_texto_ativo, t),
            on_done=lambda _d: None,
            agente=agente,
            on_meta=lambda m: na_gui(self._meta_recebida, agente, m),
            on_evento=lambda e: na_gui(self._evento_ativo, e),
        )
        self.ativo_parser = parser

        self.btn_parar.set_visible(True)
        self.btn_enviar.set_visible(True)
        self._atualizar_uso_ui()
        self.ultimo_sinal = time.monotonic()
        self.vigia_cfg = cfg
        GLib.timeout_add_seconds(VIGIA_PASSO, self._vigiar, eid)
        threading.Thread(target=self._loop_leitura, args=(mestre, proc, eid, parser, cfg),
                         daemon=True).start()

    # ── vigia: nenhuma execução fica presa para sempre ───────────────────────
    # O processo do agente pode continuar vivo depois da resposta (subagentes e
    # comandos em segundo plano) — isso é trabalho, e o status mostra. Travado é:
    # ficar sem dar NENHUM sinal por muito tempo, repetir a mesma ação sem parar,
    # ou não sair depois de responder. Nesses casos o chat cancela sozinho.
    def _vigiar(self, eid):
        if self.exec_atual != eid or self.finalizado or self.proc is None:
            return False
        parser, cfg = self.ativo_parser, self.vigia_cfg or {}
        if self.perguntas:
            self.ultimo_sinal = time.monotonic()   # esperando a pessoa responder não é travamento
        parado = time.monotonic() - self.ultimo_sinal
        pendentes = parser.tarefas_pendentes() if parser else []
        comandos = [d for d in pendentes if d not in parser.tarefas_pendentes("local_agent")] if parser else []
        if parser and parser.fim_rodada and not pendentes and parado >= VIGIA_SAIDA:
            self._encerrar_execucao()  # já respondeu; só o processo não saiu
            self._finalizar_resposta()
            self._proximo_da_fila()
            return False
        if parser and parser.repeticoes >= VIGIA_REPETICOES:
            self._cancelar_sozinho(_t("repetiu a mesma ação %1 vezes seguidas", parser.repeticoes))
            return False
        # um comando em segundo plano (compilação, download) pode ficar calado por muito tempo
        minutos = cfg.get("semSinalFundoMin", 150) if comandos else cfg.get("semSinalMin", 20)
        try:
            limite = max(VIGIA_MINIMO, float(minutos) * 60)
        except (TypeError, ValueError):
            limite = 20 * 60
        if parado >= limite:
            self._cancelar_sozinho(_t("ficou %1 min sem dar nenhum sinal", int(parado // 60)))
            return False
        if parado >= VIGIA_AVISO and self.ativo_bloco is not None:
            falta = max(1, int((limite - parado) // 60))
            self.ativo_bloco.aviso(
                _t("sem novidade há %1 min (cancela sozinho em %2 min)", int(parado // 60), falta))
        return True

    def _encerrar_execucao(self):
        """Solta a execução atual e encerra o processo dela em segundo plano."""
        proc, self.proc = self.proc, None
        self.exec_atual = 0  # eventos atrasados desta execução passam a ser ignorados
        if proc is not None:
            threading.Thread(target=self._encerrar_proc, args=(proc,), daemon=True).start()

    def _cancelar_sozinho(self, motivo):
        nome = M.AGENTES.get(self.agente_atual, {}).get("nome", _t("Agente de IA"))
        self._encerrar_execucao()
        self.interrompido = motivo
        self._finalizar_resposta(interrompida=True, motivo=f"{_t('Cancelado automaticamente:')} {nome} {motivo}")
        self._devolver_fila()
        if not self.is_active():
            try:
                subprocess.Popen(["notify-send", "-a", _t("Agentes de IA"), "-i", "simba-agente",
                                  _t("Resposta cancelada automaticamente"), f"{nome} {motivo}"],
                                 stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass

    def _loop_leitura(self, mestre, proc, eid, parser, cfg):
        """Lê o pty até o processo acabar (e esvazia o que sobrou). Roda numa thread.

        A thread é a única dona do fd `mestre` e o fecha sempre, inclusive na troca
        de agente e quando o usuário interrompe.
        """
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        tela = bytearray()
        trocar = False
        while self.exec_atual == eid:
            try:
                prontos, _, _ = select.select([mestre], [], [], 0.15)
            except (OSError, ValueError):
                break
            if prontos:
                try:
                    dados = os.read(mestre, 65536)
                except OSError:  # EIO: o processo fechou o terminal
                    break
                if not dados:
                    break
                self.ultimo_sinal = time.monotonic()
                tela += dados
                if len(tela) > 400000:
                    del tela[:100000]
                parser.feed(decoder.decode(dados))
                # Limite informado de forma estruturada (ex.: rate_limit_event
                # "rejected" do Claude): troca na hora, sem esperar o fim.
                if parser.limite and cfg.get("trocaAutomatica", True):
                    trocar = True
                    break
            elif proc.poll() is not None:
                break
        try:
            os.close(mestre)
        except OSError:
            pass
        if self.exec_atual != eid:  # interrompido: quem interrompeu já encerrou
            return
        if trocar:
            self._encerrar_proc(proc)
        else:
            parser.feed(decoder.decode(b"", final=True))
            parser.finish()
        try:
            rc = proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._encerrar_proc(proc)
            rc = None
        GLib.idle_add(self._fim_execucao, eid, parser, rc, bytes(tela), cfg)

    @staticmethod
    def _encerrar_proc(proc):
        """SIGINT → SIGTERM → SIGKILL no grupo do processo, esperando entre um e outro."""
        import signal
        for sig, espera in ((signal.SIGINT, 2), (signal.SIGTERM, 2), (signal.SIGKILL, 2)):
            if proc.poll() is not None:
                return
            try:
                os.killpg(proc.pid, sig)
            except OSError:
                try:
                    proc.send_signal(sig)
                except OSError:
                    return
            try:
                proc.wait(timeout=espera)
                return
            except subprocess.TimeoutExpired:
                continue

    def _limite_atingido(self, parser, rc):
        """Decide se a execução terminou por falta de limite do agente.

        Primeiro os sinais estruturados; o texto só é examinado quando a execução
        falhou ou quase não respondeu — assim uma resposta que *fala* sobre
        limites (ex.: rate limit de uma API) não troca de agente.
        """
        if parser.limite:
            return True
        resposta = parser.texto.strip()
        if parser.agente in ("claude", "codex", "opencode"):
            suspeito = bool(parser.erro) or rc not in (0, None) or not resposta
        else:
            suspeito = rc not in (0, None) or bool(parser.erro) or len(resposta) < 300
        return suspeito and M.detectar_limite(parser.texto_detectavel)

    def _fim_execucao(self, eid, parser, rc, tela, cfg):
        if eid != self.exec_atual or self.finalizado:
            return False
        self.proc = None
        agente = self.agente_atual
        if cfg.get("trocaAutomatica", True) and self._limite_atingido(parser, rc):
            self._executar_troca_transparente(agente, cfg, tela, parser)
            return False
        if parser.erro and not parser.has_text:
            self.ativo_texto = f"⚠ {parser.erro.strip()}"
        elif not parser.has_text and rc not in (0, None):
            linhas = [l for l in M.tela_limpa(tela) if l.strip()][-8:]
            if linhas:
                self.ativo_texto = "⚠ " + _t("O agente terminou com erro:") + "\n\n```\n" + "\n".join(linhas) + "\n```"
        self._finalizar_resposta()
        self._proximo_da_fila()
        return False

    def _meta_recebida(self, agente, meta):
        if meta.get("sessao"):
            self.sessoes[agente] = meta["sessao"]
            self._agendar_salvamento()
        if meta.get("modelo") and self.ativo_registro is not None:
            if not M.modelo_escolhido(agente, M.ler_config(verificar=False)):
                self.ativo_registro["modelo"] = meta["modelo"]
                if getattr(self, "ativo_modelo", None):
                    self.ativo_modelo(meta["modelo"])
        if meta.get("voltas"):
            self.janelas_volta[agente] = meta["voltas"]
        if meta.get("janelas"):
            self.janelas_uso[agente] = meta["janelas"]
            self._atualizar_uso_ui()

    def _dados_uso(self):
        """(agente, {"5h": fração, "7d": fração}, {"5h": epoch de quando zera, ...})."""
        agente = (self.agente_atual if self._rodando() else None) or self._agente_escolhido()
        if not agente:
            # Automático: o limite que importa é o de quem vai responder agora
            agente = next((a for a in getattr(self, "candidatos", []) if not M.esgotado_ate(a)), None)
        if not agente:
            return None, {}, {}
        janelas = dict(self.janelas_uso.get(agente) or {})
        voltas = dict(self.janelas_volta.get(agente) or {})
        agora = time.time()
        # janela que já zerou: a porcentagem informada é velha
        for k in [k for k, t in voltas.items() if t <= agora]:
            janelas.pop(k, None)
            voltas.pop(k, None)
        if not janelas:
            # Do widget de uso, só janelas que ainda não reiniciaram (dado velho engana)
            u = M.uso(agente)
            for chave, rotulo in (("sessao", "5h"), ("semana", "7d")):
                volta = M._futuro(u.get(f"{chave}Volta") or "")
                if chave in u and volta:
                    janelas[rotulo] = u[chave]
                    voltas[rotulo] = _epoch_iso(volta)
        return agente, janelas, voltas

    def _atualizar_uso_ui(self):
        if not hasattr(self, "lbl_uso"):
            return
        agente, janelas, voltas = self._dados_uso()
        self.uso_dados = (agente, janelas, voltas)
        if not janelas:
            self.lbl_uso.set_visible(False)
            return
        agora = time.time()
        nome = M.AGENTES.get(agente, {}).get("nome", agente)
        nomes_jan = {"5h": _t("Sessão atual (5 h)"), "7d": _t("Semana (7 dias)")}
        dicas = []
        for k in ("5h", "7d"):
            if k in janelas:
                d = f"{nomes_jan[k]}: {round(janelas[k] * 100)}% {_t('usado')}"
                if voltas.get(k):
                    d += f" · {_t('zera em')} {_falta(voltas[k] - agora)}"
                dicas.append(d)
        # o anel mostra a janela mais apertada
        maior = max(janelas.values())
        chave = max(janelas, key=janelas.get)
        self.anel_uso.definir(maior)
        texto = f"{round(maior * 100)}% {_t('usado')}"
        if voltas.get(chave) and maior >= 0.5:
            texto += f" · {_t('zera em')} {_falta(voltas[chave] - agora)}"
        self.lbl_uso_pct.set_label(texto)
        self.lbl_uso.set_tooltip_text(f"{_t('Limite de uso de')} {nome}\n" + "\n".join(dicas))
        for c in ("uso-alto", "uso-critico"):
            self.lbl_uso.remove_css_class(c)
        if maior >= 0.9:
            self.lbl_uso.add_css_class("uso-critico")
        elif maior >= 0.75:
            self.lbl_uso.add_css_class("uso-alto")
        self.lbl_uso.set_visible(True)

    def _montar_pop_uso(self):
        """Popover estilo Claude › Configurações › Uso: uma barra por janela, com contagem."""
        agente, janelas, voltas = self._dados_uso()
        agora = time.time()
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        caixa.set_size_request(320, -1)
        nome = M.AGENTES.get(agente, {}).get("nome", agente or "")
        cab = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        if agente:
            cab.append(marcas.imagem(self._icone_item(agente), 20))
        t = Gtk.Label(label=f"{_t('Limites de uso')} · {nome}", xalign=0)
        t.add_css_class("uso-pop-titulo")
        cab.append(t)
        caixa.append(cab)
        titulos = {"5h": _t("Sessão atual"), "7d": _t("Limite semanal")}
        subs = {"5h": _t("janela de 5 horas"), "7d": _t("todos os modelos · 7 dias")}
        for k in ("5h", "7d"):
            if k not in janelas:
                continue
            frac = max(0.0, min(1.0, float(janelas[k])))
            linha = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
            topo = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            tt = Gtk.Label(label=titulos[k], xalign=0)
            tt.add_css_class("uso-pop-linha-titulo")
            topo.append(tt)
            st = Gtk.Label(label=subs[k], xalign=0, hexpand=True)
            st.add_css_class("uso-pop-sub")
            topo.append(st)
            pct = Gtk.Label(label=f"{round(frac * 100)}% {_t('usado')}")
            pct.add_css_class("uso-pop-pct")
            topo.append(pct)
            linha.append(topo)
            barra = Gtk.LevelBar(min_value=0, max_value=1, value=frac)
            barra.set_mode(Gtk.LevelBarMode.CONTINUOUS)
            for nome_off in ("low", "high", "full"):
                barra.remove_offset_value(nome_off)
            barra.add_css_class("uso-medidor")
            barra.add_offset_value("uso-ok", 0.75)
            barra.add_offset_value("uso-alto", 0.9)
            barra.add_offset_value("uso-critico", 1.0)
            linha.append(barra)
            if voltas.get(k):
                nota = Gtk.Label(label=f"{_t('Zera em')} {_falta(voltas[k] - agora)} · {_quando(voltas[k], longo=True)}",
                                 xalign=0)
            else:
                nota = Gtk.Label(label=_t("Começa a contar no próximo pedido"), xalign=0)
            nota.add_css_class("uso-pop-nota")
            linha.append(nota)
            caixa.append(linha)
        if not janelas:
            vazio = Gtk.Label(label=_t("Este agente ainda não informou os limites."), xalign=0)
            vazio.add_css_class("uso-pop-sub")
            caixa.append(vazio)
        btn = Gtk.Button(label=_t("Ver uso e custo detalhados"))
        btn.add_css_class("flat")
        btn.add_css_class("uso-pop-link")
        btn.connect("clicked", lambda _b: (self.pop_uso.popdown(), self._abrir_painel_uso()))
        caixa.append(btn)
        self.pop_uso.set_child(caixa)

    def _atualizar_seguro_ui(self):
        ativo = self.btn_seguro.get_active()
        self.lbl_seguro.set_label(_t("Somente leitura") if ativo else _t("Livre"))
        self.ico_seguro.set_from_icon_name("changes-prevent-symbolic" if ativo else "changes-allow-symbolic")
        self.btn_seguro.set_tooltip_text(
            _t("Somente leitura: os agentes leem e respondem, mas não editam arquivos nem executam comandos. Clique para liberar.")
            if ativo else
            _t("Livre: os agentes editam arquivos e executam comandos sem perguntar. Clique para somente leitura.")
        )
        if ativo:
            self.btn_seguro.add_css_class("seguro-ativo")
        else:
            self.btn_seguro.remove_css_class("seguro-ativo")

    def _on_seguro_alterado(self, _btn):
        cfg = M.ler_config(verificar=False)
        cfg["seguro"] = self.btn_seguro.get_active()
        M.gravar_config(cfg)
        self._atualizar_seguro_ui()
        self._carregar_agentes()

    def _atualizar_status_ativo(self, status_texto):
        """Status em texto do agente: vira o passo atual no cabeçalho do bloco "Pensando"."""
        bloco = self.ativo_bloco
        if bloco is None or not status_texto or not status_texto.strip():
            return
        bloco.status(status_texto)
        if self.ativo_digitando is not None and self.ativo_digitando.get_visible():
            self.ativo_digitando.mostrar(bloco.status_atual())
        self._agendar_salvamento()
        self._scroll_para_fim()

    def _evento_ativo(self, ev):
        """Evento estruturado do parser: passo (com entrada, saída, estado) ou raciocínio."""
        bloco = self.ativo_bloco
        if bloco is None:
            return
        if ev.get("ev") == "raciocinio":
            bloco.raciocinar(ev.get("texto"))
        elif ev.get("ev") == "passo":
            bloco.passo(ev)
            if bloco.aberto():
                self._scroll_para_fim()
        self._agendar_salvamento()

    def _anexar_texto_ativo(self, texto):
        self.ativo_texto += texto
        # Markdown durante a resposta: atualiza a mensagem a cada ~120 ms. Só o
        # último bloco muda (MensagemView), então o custo não cresce com o tamanho.
        if not self.render_fonte:
            self.render_fonte = GLib.timeout_add(120, self._render_parcial)

    def _render_parcial(self):
        self.render_fonte = 0
        if self.finalizado or self.ativo_mensagem is None:
            return False
        self.ativo_mensagem.definir(self.ativo_texto, ao_vivo=self.seguir_fim)
        # com texto na tela o cabeçalho do bloco sobe com a conversa: o indicador de
        # digitação, no fim, continua dizendo o que o agente faz
        if self.ativo_digitando is not None and not self.ativo_digitando.get_visible():
            self.ativo_digitando.mostrar(self.ativo_bloco.status_atual() if self.ativo_bloco else "")
        self._scroll_para_fim()
        return False

    def _concluir_status_ativo(self, interrompida=False):
        if self.ativo_digitando is not None:
            self.ativo_digitando.parar()
        if self.ativo_bloco is not None:
            self.ativo_bloco.concluir(
                segundos=(time.time() - self.inicio_agente) if self.inicio_agente > 0 else None,
                interrompida=interrompida)
        self._agendar_salvamento(400)
        self._scroll_para_fim()

    def _executar_troca_transparente(self, agente_antigo, cfg, tela, parser=None):
        nome_antigo = M.AGENTES[agente_antigo]["nome"]
        ate = None
        if parser is not None and parser.limite_ate:
            try:
                ate = datetime.fromtimestamp(float(parser.limite_ate)).astimezone().isoformat()
            except (TypeError, ValueError, OSError):
                ate = None
        M.marcar_esgotado(agente_antigo, ate)
        arq = M.passagem(agente_antigo, self.work_dir, self.inicio_agente, tela, self.anterior_passagem)
        self.anterior_passagem = arq
        if not self.ativo_texto.strip():
            self.ativo_texto = f"_{_t('Limite de uso atingido. O trabalho continua no próximo agente.')}_"
        self._finalizar_resposta(notificar=False)

        seguro = bool(cfg.get("seguro"))
        seguintes = [a for a in M.candidatos(cfg, pular=self.usados, verificar=False, seguro=seguro)
                     if not M.esgotado_ate(a)]
        # Modo grátis: o mesmo agente segue com o próximo modelo grátis.
        if not seguintes and M.modo_gratis(agente_antigo) and not M.esgotado_ate(agente_antigo):
            seguintes = [agente_antigo]
        if not seguintes:
            self._adicionar_sistema(
                f"⚡ {_t('Limite de uso atingido para')} {nome_antigo}. "
                f"{_t('Todos os agentes configurados estão sem limite no momento. Contexto salvo em:')} {arq.name}"
            )
            self._devolver_fila()
            return

        proximo = seguintes[0]
        nome_proximo = M.AGENTES[proximo]["nome"]
        self._adicionar_aviso_handover(nome_antigo, nome_proximo)
        subprocess.Popen([
            "notify-send", "-a", _t("Agentes de IA"), "-i", "dialog-information",
            f"{_t('Continuando com')} {nome_proximo}",
            f"{_t('O limite de uso do')} {nome_antigo} {_t('acabou. O trabalho continua automaticamente.')}"
        ], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        novo_pedido = (
            f"Você vai continuar um trabalho que outro agente de IA ({nome_antigo}) começou e não terminou "
            f"porque o limite de uso dele acabou. Leia primeiro, por inteiro, o arquivo {arq} (pedido do usuário, conversa, comandos e estado do Git). "
            f"Depois confira o que já foi feito e continue exatamente de onde parou, sem pedir para o usuário repetir nada."
        )
        self._iniciar_execucao(novo_pedido, agente_forcado=proximo, arq_passagem=arq)

    def _interromper(self):
        if self.gravador and self.gravador.gravando:
            self.gravador.cancelar()
            self._ditado_ui("parado")
        if not self._rodando():
            return
        self._encerrar_execucao()
        self.interrompido = True
        self._finalizar_resposta(interrompida=True)
        self._devolver_fila()

    def _finalizar_resposta(self, interrompida=False, notificar=True, motivo=None):
        if self.finalizado:
            return
        self.finalizado = True
        if self.render_fonte:
            GLib.source_remove(self.render_fonte)
            self.render_fonte = 0
        self._cancelar_perguntas()
        self._concluir_status_ativo(interrompida)

        tempo_fmt = None
        if self.inicio_agente > 0:
            duracao = time.time() - self.inicio_agente
            if duracao >= 60:
                tempo_fmt = f"{int(duracao // 60)}m {int(duracao % 60)}s"
            elif duracao >= 1.0:
                tempo_fmt = f"{duracao:.1f}s"
            else:
                tempo_fmt = "< 1s"

        parser = self.ativo_parser
        uso = dict(parser.uso) if parser is not None and parser.uso else {}
        if parser is not None and parser.uso_tarefas:
            uso["subagentes"] = sum(parser.uso_tarefas.values())
        rotulo = f"⏱ {tempo_fmt}" if tempo_fmt else ""
        extra = formatar_uso(uso)
        if extra:
            rotulo = f"{rotulo} · {extra}" if rotulo else extra
        if self.ativo_duracao_lbl and rotulo:
            self.ativo_duracao_lbl.set_label(rotulo)
            self.ativo_duracao_lbl.set_visible(True)

        texto = self.ativo_texto
        if not texto.strip():
            if parser is not None and parser.last_response:
                texto = parser.last_response
            elif not interrompida:
                texto = _t("(Concluído sem texto adicional)")
        if interrompida:
            texto = texto.rstrip() + ("\n\n" if texto.strip() else "") + f"_⏹ {motivo or _t('Interrompido pelo usuário')}_"
        self.ativo_texto = texto

        if self.ativo_registro is not None:
            self.ativo_registro["texto"] = texto
            if tempo_fmt:
                self.ativo_registro["duracao"] = tempo_fmt
            if uso:
                self.ativo_registro["uso"] = uso
            if interrompida:
                self.ativo_registro["interrompida"] = True
        if self.ativo_mensagem is not None:
            self.ativo_mensagem.definir(texto)
            self.ativo_mensagem.concluir(recolher=self.seguir_fim)
            self.ativo_renderizado = True

        if notificar and not interrompida and not self.is_active():
            nome = M.AGENTES.get(self.agente_atual, {}).get("nome", _t("Agente de IA"))
            self._notificar_conclusao(nome)

        card = getattr(self, "ativo_card", None)
        if card is not None:
            card.remove_css_class("ativo")
            card.acoes.set_visible(True)
            if self.ativo_bloco is not None:
                card.atualizar_acoes(self.ativo_bloco.passos)

        self.proc = None
        self._salvar_conversa()
        self._atualizar_uso_ui()
        self.btn_historico.set_sensitive(True)
        self.btn_parar.set_visible(False)
        self.btn_enviar.set_visible(True)
        self._focar_composer()
        self._scroll_para_fim()

    def _focar_composer(self):
        """Volta o foco para a caixa de texto, sem roubar de quem está digitando em outro lugar."""
        if getattr(self, "barra_busca", None) is not None and self._busca_ativa():
            return
        foco = self.get_focus()
        if isinstance(foco, (Gtk.Text, Gtk.TextView)) and foco.get_editable() and foco is not self.text_input:
            return
        self.text_input.grab_focus()

    def _notificar_conclusao(self, nome):
        """Notificação com ação: clicar traz a janela do chat de volta."""
        def esperar():
            try:
                r = subprocess.run(
                    ["notify-send", "-a", _t("Agentes de IA"), "-i", "simba-agente",
                     "-A", f"default={_t('Abrir o chat')}",
                     f"{nome} {_t('concluiu a resposta')}", _t("Clique para voltar ao chat e ver a resposta.")],
                    stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=3600,
                )
            except (OSError, subprocess.TimeoutExpired):
                return
            # clicar no cartão dispara a ação "default" (Service.qml do simba-shell)
            if r.stdout.strip() == "default":
                GLib.idle_add(self._trazer_janela)
        threading.Thread(target=esperar, daemon=True).start()

    def _trazer_janela(self):
        # simba-agentes sem argumentos traz a janela para a área de trabalho atual
        try:
            subprocess.Popen(["simba-agentes"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            self.present()
        return False

    # ── Ditado por voz ───────────────────────────────────────────────────────
    def _alternar_ditado(self):
        if not self.gravador:
            return
        if self.gravador.gravando:
            self.gravador.parar()
            self._ditado_ui("transcrevendo")
            threading.Thread(target=self._transcrever_ditado, daemon=True).start()
            return
        if getattr(self, "transcrevendo", False):
            return
        try:
            self.gravador.iniciar()
        except OSError as e:
            self._adicionar_sistema(f"{_t('Não foi possível usar o microfone:')} {e}")
            return
        self._ditado_ui("gravando")

    def _transcrever_ditado(self):
        try:
            texto = self.gravador.transcrever()
            erro = None
        except Exception as e:  # noqa: BLE001
            texto, erro = None, str(e)
        GLib.idle_add(self._ditado_pronto, texto, erro)

    def _ditado_pronto(self, texto, erro):
        self._ditado_ui("parado")
        if texto:
            inicio, fim = self.text_input_buf.get_bounds()
            atual = self.text_input_buf.get_text(inicio, fim, True)
            sep = " " if atual and not atual.endswith((" ", "\n")) else ""
            self.text_input_buf.insert(self.text_input_buf.get_end_iter(), sep + texto)
            self.text_input.grab_focus()
        elif erro not in ("curto", "vazio"):
            self._adicionar_sistema(f"{_t('Não foi possível transcrever o áudio.')} ({erro})", registro=False)
        return False

    def _ditado_ui(self, estado):
        self.transcrevendo = estado == "transcrevendo"
        self.btn_mic.remove_css_class("gravando")
        self.btn_mic.set_sensitive(estado != "transcrevendo")
        if estado == "gravando":
            self.btn_mic.add_css_class("gravando")
            self.btn_mic.set_icon_name("media-record-symbolic")
            self.btn_mic.set_tooltip_text(_t("Gravando… clique (ou Ctrl+M) para parar"))
        elif estado == "transcrevendo":
            self.btn_mic.set_icon_name("content-loading-symbolic")
            self.btn_mic.set_tooltip_text(_t("Transcrevendo…"))
        else:
            self.btn_mic.set_icon_name("audio-input-microphone-symbolic")
            self.btn_mic.set_tooltip_text(_t("Ditar por voz (Ctrl+M)"))

    # ── Construtores de Mensagens e Cards ────────────────────────────────────
    def _registrar_usuario(self, texto, arquivos=None):
        msg = {"tipo": "user", "texto": texto, "quando": time.time()}
        if arquivos:
            msg["anexos"] = list(arquivos)
        self.conversa_mensagens.append(msg)
        self._salvar_conversa()

    def _adicionar_bolha_usuario(self, texto, registro=True, na_fila=False, anexos=None):
        if registro:
            self._registrar_usuario(texto, anexos)

        box_linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box_linha.set_halign(Gtk.Align.END)
        box_linha.add_css_class("msg-user-row")

        bubble = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        bubble.add_css_class("user-bubble")

        if anexos:
            fotos = Gtk.FlowBox()
            fotos.set_selection_mode(Gtk.SelectionMode.NONE)
            fotos.set_max_children_per_line(6)
            fotos.set_column_spacing(6)
            fotos.set_row_spacing(6)
            fotos.set_halign(Gtk.Align.END)
            for caminho in anexos:
                fotos.append(self._chip_anexo(caminho))
            bubble.append(fotos)

        lbl = Gtk.Label(label=texto, wrap=True, selectable=True, xalign=0)
        lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        lbl.set_max_width_chars(110)
        lbl.set_visible(bool(texto))
        bubble.append(lbl)

        lbl_fila = Gtk.Label(label=f"⏳ {_t('Na fila: vai quando a resposta atual terminar')}", xalign=1)
        lbl_fila.add_css_class("fila-label")
        lbl_fila.set_visible(na_fila)
        bubble.append(lbl_fila)

        coluna = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        coluna.set_halign(Gtk.Align.END)
        coluna.append(bubble)
        # Ações ao passar o mouse: copiar e editar (volta o texto para a caixa)
        acoes = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        acoes.add_css_class("msg-user-acoes")
        acoes.set_halign(Gtk.Align.END)
        b_copiar = Gtk.Button(icon_name="edit-copy-symbolic")
        b_copiar.add_css_class("flat")
        b_copiar.add_css_class("action-button")
        b_copiar.set_tooltip_text(_t("Copiar"))
        b_copiar.connect("clicked", lambda b: self._copiar_icone(texto, b))
        acoes.append(b_copiar)
        b_editar = Gtk.Button(icon_name="document-edit-symbolic")
        b_editar.add_css_class("flat")
        b_editar.add_css_class("action-button")
        b_editar.set_tooltip_text(_t("Editar e enviar de novo"))
        b_editar.connect("clicked", lambda _b: self._usar_sugestao(texto))
        acoes.append(b_editar)
        acoes.set_visible(bool(texto))
        coluna.append(acoes)
        box_linha.append(coluna)
        self.box_mensagens.append(box_linha)
        if registro or na_fila:
            self._animar_entrada(box_linha)
        self._scroll_para_fim(forcar=True)
        return {"linha": box_linha, "fila": lbl_fila}

    def _adicionar_bolha_assistente(
        self, agente, registro=True, ativo=True, modelo=None, hora=None, duracao=None
    ):
        info = M.AGENTES.get(agente, {})
        nome = info.get("nome", agente)
        if modelo is None:
            modelo = M.modelo_escolhido(agente, M.ler_config(verificar=False)) or info.get("modelo", "")

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("assistant-card")
        card.set_hexpand(True)

        # Cabeçalho: avatar, nome, modelo e horário
        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        # Logo da empresa do agente, centrado num círculo de tamanho fixo
        # (antes era uma Gtk.Box, que encostava o ícone à esquerda).
        img_icone = marcas.imagem(marcas.icone_agente(agente, modelo), 18)
        img_icone.add_css_class("assistant-avatar")
        img_icone.set_size_request(30, 30)
        img_icone.set_halign(Gtk.Align.CENTER)
        img_icone.set_valign(Gtk.Align.CENTER)
        empresa = marcas.NOMES.get(marcas.marca_agente(agente, modelo))
        if empresa:
            img_icone.set_tooltip_text(empresa)
        header_row.append(img_icone)

        lbl_nome = Gtk.Label(label=nome)
        lbl_nome.add_css_class("assistant-name")
        lbl_nome.set_valign(Gtk.Align.CENTER)
        header_row.append(lbl_nome)

        # Selo do modelo; quando o provedor é outra empresa (ex.: OpenCode
        # usando OpenRouter ou Grok), o logo dele aparece dentro do selo.
        selo = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        selo.add_css_class("model-badge")
        selo.set_valign(Gtk.Align.CENTER)
        ico_mod = marcas.imagem(None, 12)
        selo.append(ico_mod)
        lbl_mod = Gtk.Label(label=modelo or "")
        lbl_mod.set_ellipsize(Pango.EllipsizeMode.END)
        lbl_mod.set_max_width_chars(40)
        selo.append(lbl_mod)
        header_row.append(selo)

        def mostrar_modelo(valor):
            valor = valor or ""
            lbl_mod.set_label(valor)
            prov = marcas.marca_modelo(valor)
            icone = marcas.nome_icone(prov) if prov and prov != marcas.AGENTE_MARCA.get(agente) else None
            if icone:
                ico_mod.set_from_icon_name(icone)
                selo.set_tooltip_text(f"{valor} · {marcas.NOMES.get(prov, prov)}")
            else:
                selo.set_tooltip_text(valor)
            ico_mod.set_visible(bool(icone))
            selo.set_visible(bool(valor))
            if agente not in marcas.AGENTE_MARCA:  # Crush, Pi: o logo vem do modelo
                img_icone.set_from_icon_name(marcas.icone_agente(agente, valor))
        mostrar_modelo(modelo)

        lbl_duracao = Gtk.Label(label=f"⏱ {duracao}" if duracao else "")
        lbl_duracao.add_css_class("duration-badge")
        lbl_duracao.set_valign(Gtk.Align.CENTER)
        lbl_duracao.set_visible(bool(duracao))

        # Modo livre: quantos comandos a IA rodou sozinha no computador (e se usou root)
        lbl_acoes = Gtk.Label()
        lbl_acoes.add_css_class("acoes-pc")
        lbl_acoes.set_valign(Gtk.Align.CENTER)
        lbl_acoes.set_visible(False)
        header_row.append(lbl_acoes)

        def atualizar_acoes(passos):
            cmds = [p for p in passos or [] if p.get("tipo") == "comando" and p.get("estado") != "negado"
                    and not p.get("simples")]
            edits = [p for p in passos or [] if p.get("tipo") == "edicao" and p.get("estado") != "negado"
                     and not p.get("simples")]
            root = any(re.search(r"(^|[\s;&|(])(sudo|pkexec|doas)\s", str((p.get("entrada") or {}).get("comando", "")))
                       for p in cmds)
            partes = []
            if cmds:
                partes.append(f"{len(cmds)} {_t('comando') if len(cmds) == 1 else _t('comandos')}")
            if edits:
                partes.append(f"{len(edits)} {_t('edição') if len(edits) == 1 else _t('edições')}")
            if not partes:
                lbl_acoes.set_visible(False)
                return
            lbl_acoes.set_label(("⚡ " if root else "⌘ ") + " · ".join(partes))
            lbl_acoes.set_tooltip_text(
                (_t("Inclui comando de administrador (root). ") if root else "")
                + _t("Ações que a IA executou no computador. Abra o bloco Pensando para ver cada uma."))
            (lbl_acoes.add_css_class if root else lbl_acoes.remove_css_class)("root")
            lbl_acoes.set_visible(True)

        espaco = Gtk.Box()
        espaco.set_hexpand(True)
        header_row.append(espaco)

        lbl_hora = Gtk.Label(label=hora or datetime.now().strftime("%H:%M"))
        lbl_hora.add_css_class("msg-time")
        lbl_hora.set_valign(Gtk.Align.CENTER)
        header_row.append(lbl_hora)
        card.append(header_row)

        # Bloco "Pensando": passo atual + cronômetro; clicado, abre a linha do tempo
        # (raciocínio, passos, cartões de comando). Fica acima do texto, como um resumo
        # do trabalho; o indicador de digitação fica DEPOIS do texto, no fim da conversa.
        seguro = bool(M.ler_config(verificar=False).get("seguro")) if ativo else False
        bloco = atividade.BlocoPensando(seguro=seguro, vivo=ativo,
                                        ao_abrir=lambda: GLib.idle_add(self._do_scroll) if self.seguir_fim else None)
        bloco.set_visible(ativo)
        card.append(bloco)

        # Corpo da resposta: blocos de texto, código e tabela (markdown.MensagemView)
        mensagem = self._criar_mensagem()
        card.append(mensagem)

        digitando = atividade.Digitando()
        card.append(digitando)

        # Ações da resposta (aparecem por inteiro ao passar o mouse): copiar, tentar de novo
        act_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        act_row.add_css_class("msg-actions")
        btn_copiar = Gtk.Button(icon_name="edit-copy-symbolic")
        btn_copiar.add_css_class("flat")
        btn_copiar.add_css_class("action-button")
        btn_copiar.set_tooltip_text(_t("Copiar resposta"))
        btn_copiar.connect("clicked", lambda b: self._copiar_icone(mensagem.texto, b))
        act_row.append(btn_copiar)
        pedido_ant = next((m for m in reversed(self.conversa_mensagens) if m.get("tipo") == "user"), None)
        if pedido_ant is not None:
            btn_repetir = Gtk.Button(icon_name="view-refresh-symbolic")
            btn_repetir.add_css_class("flat")
            btn_repetir.add_css_class("action-button")
            btn_repetir.set_tooltip_text(_t("Tentar de novo (reenvia o mesmo pedido)"))
            btn_repetir.connect("clicked", lambda _b, m=pedido_ant: self._repetir_pedido(m))
            act_row.append(btn_repetir)
        act_row.append(lbl_duracao)
        card.append(act_row)
        card.atualizar_acoes = atualizar_acoes
        card.acoes = act_row
        act_row.set_visible(not ativo)   # copiar/tentar de novo só depois que a resposta termina

        self.box_mensagens.append(card)
        if ativo:
            card.add_css_class("ativo")
            self._animar_entrada(card)

        if registro:
            novo = {
                "tipo": "assistant",
                "agente": agente,
                "modelo": modelo,
                "hora": lbl_hora.get_label(),
                "quando": time.time(),
                "texto": "",
                "passos": [],
            }
            self.conversa_mensagens.append(novo)
            if ativo:
                self.ativo_registro = novo
                # os passos são guardados na própria conversa, à medida que chegam
                bloco.registro = novo
                novo["passos"] = bloco.passos

        if ativo:
            self.ativo_mensagem = mensagem
            self.ativo_bloco = bloco
            self.ativo_digitando = digitando
            self.ativo_modelo = mostrar_modelo
            self.ativo_duracao_lbl = lbl_duracao
            self.ativo_card = card
            self.ativo_renderizado = False

        if registro:
            self._salvar_conversa()

        self._scroll_para_fim(forcar=True)
        return {
            "card": card,
            "mensagem": mensagem,
            "bloco": bloco,
            "digitando": digitando,
            "duracao_lbl": lbl_duracao,
        }

    def _animar_entrada(self, widget):
        """Entrada suave de uma mensagem nova (não nas conversas reabertas)."""
        if not atividade.animacoes():
            return
        widget.add_css_class("msg-entrada")
        GLib.timeout_add(450, lambda: (widget.remove_css_class("msg-entrada"), False)[1])

    def _adicionar_aviso_handover(self, nome_antigo, nome_proximo, registro=True):
        if registro:
            self.conversa_mensagens.append(
                {
                    "tipo": "handover",
                    "antigo": nome_antigo,
                    "proximo": nome_proximo,
                    "quando": time.time(),
                }
            )
            self._salvar_conversa()

        box_linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box_linha.set_halign(Gtk.Align.CENTER)
        box_linha.set_margin_top(6)
        box_linha.set_margin_bottom(6)

        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        card.add_css_class("handover-pill")

        icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        icon.set_pixel_size(14)
        lbl = Gtk.Label(
            label=f"{_t('Limite atingido no')} {nome_antigo} · {_t('Continuando com')} {nome_proximo}"
        )
        lbl.set_wrap(True)
        lbl.set_justify(Gtk.Justification.CENTER)
        lbl.set_max_width_chars(70)
        card.append(icon)
        card.append(lbl)

        box_linha.append(card)
        self.box_mensagens.append(box_linha)
        self._scroll_para_fim(forcar=True)

    def _adicionar_sistema(self, texto, registro=True):
        if registro:
            self.conversa_mensagens.append(
                {"tipo": "sistema", "texto": texto, "quando": time.time()}
            )
            self._salvar_conversa()

        box_linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box_linha.set_halign(Gtk.Align.CENTER)
        box_linha.set_margin_top(4)
        box_linha.set_margin_bottom(4)

        lbl = Gtk.Label(label=texto)
        lbl.set_wrap(True)
        lbl.set_justify(Gtk.Justification.CENTER)
        lbl.set_max_width_chars(76)
        lbl.set_selectable(True)
        lbl.add_css_class("system-pill")

        box_linha.append(lbl)
        self.box_mensagens.append(box_linha)
        self._scroll_para_fim(forcar=True)


    def _copiar_icone(self, texto, btn):
        """Copiar com botão só de ícone: vira um ✓ verde por 2 s."""
        if not texto:
            return
        Gdk.Display.get_default().get_clipboard().set(texto)
        btn.set_icon_name("object-select-symbolic")
        btn.add_css_class("copiado")

        def voltar():
            btn.set_icon_name("edit-copy-symbolic")
            btn.remove_css_class("copiado")
            return False
        GLib.timeout_add_seconds(2, voltar)

    def _repetir_pedido(self, msg):
        """Reenvia um pedido anterior (botão "Tentar de novo" de uma resposta)."""
        if self._rodando():
            self._adicionar_sistema(_t("Espere a resposta atual terminar (ou pare com Esc) para tentar de novo."),
                                    registro=False)
            return
        anexos_ok = [a for a in (msg.get("anexos") or []) if Path(a).exists()]
        self._enviar_pedido([{"texto": msg.get("texto", ""), "anexos": anexos_ok}])

    def _copiar_texto(self, texto, btn):
        if texto:
            Gdk.Display.get_default().get_clipboard().set(texto)
            self._feedback_botao(btn, "emblem-ok-symbolic", _t("Copiado!"), "edit-copy-symbolic", _t("Copiar"))

    def _rolagem_mudou(self, adj):
        if getattr(self, "_rolando_sozinho", False):
            return
        self.seguir_fim = adj.get_value() >= adj.get_upper() - adj.get_page_size() - 96

    def _scroll_para_fim(self, forcar=False):
        if forcar:
            self.seguir_fim = True
        if self.seguir_fim:
            GLib.idle_add(self._do_scroll)

    def _do_scroll(self):
        adj = self.scroller.get_vadjustment()
        self._rolando_sozinho = True
        adj.set_value(adj.get_upper() - adj.get_page_size())
        self._rolando_sozinho = False
        return False


class App(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )

    def do_command_line(self, cl):
        args = list(cl.get_arguments())
        pasta = None
        prompt = None
        i = 1
        while i < len(args):
            arg = args[i]
            if arg in ("--pasta", "--dir", "-d") and i + 1 < len(args):
                pasta = args[i + 1]
                i += 2
            elif arg in ("--prompt", "-p") and i + 1 < len(args):
                prompt = args[i + 1]
                i += 2
            else:
                i += 1
        win = self.props.active_window
        if not win:
            win = MainWindow(self, pasta=pasta, prompt_inicial=prompt)
        else:
            if pasta:
                win.definir_pasta(pasta)
            if prompt:
                win.definir_prompt(prompt)
        win.present()
        win.maximize()
        return 0

    def do_startup(self):
        Adw.Application.do_startup(self)
        css_prov = Gtk.CssProvider()
        css_prov.load_from_data(CSS.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), css_prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        marcas.registrar()
        threading.Thread(target=anexos.limpar_antigos, daemon=True).start()
        _vigiar_interface()

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = MainWindow(self)
        win.present()
        # O chat abre sempre maximizado: ocupa a área útil da tela, mas mantém a
        # barra de tarefas visível (tela cheia de verdade esconderia a barra).
        win.maximize()


def main():
    app = App()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
