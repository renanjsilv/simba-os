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
import select
import struct
import subprocess
import sys
import termios
import threading
import time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

sys.path.insert(0, "/usr/share/simba-apps/idiomas")
from simba_i18n import t as _t  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motor as M  # noqa: E402
from central import CentralMixin  # noqa: E402
from estilo import CSS  # noqa: E402
from historico import HistoricoMixin  # noqa: E402
from markdown import MarkdownMixin  # noqa: E402
from parser import AgentStreamParser  # noqa: E402
import voz  # noqa: E402

# AGENTES_DEV=1 abre uma instância separada (para testar sem mexer na janela aberta).
APP_ID = "com.simba.AgentesDev" if os.environ.get("AGENTES_DEV") else "com.simba.Agentes"
HOME = Path.home()


def formatar_uso(uso):
    """'12,3 mil tokens · US$ 0,004' a partir do uso informado pelo agente."""
    if not uso:
        return ""
    partes = []
    total = int(uso.get("entrada", 0) or 0) + int(uso.get("saida", 0) or 0)
    if total:
        partes.append(f"{total / 1000:.1f}k tokens" if total >= 1000 else f"{total} tokens")
    custo = uso.get("custo")
    if custo:
        partes.append(f"US$ {custo:.3f}")
    return " · ".join(partes)


def definir_tamanho_pty(fd, linhas=40, colunas=120):
    try:
        ws = struct.pack("HHHH", linhas, colunas, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, ws)
    except Exception:
        pass




class MainWindow(CentralMixin, HistoricoMixin, MarkdownMixin, Adw.ApplicationWindow):
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
        self.ativo_status_box = None
        self.ativo_status_spinner = None
        self.ativo_status_check = None
        self.ativo_status_lbl = None
        self.ativo_status_toggle = None
        self.ativo_status_revealer = None
        self.ativo_status_log_buf = None
        self.ativo_status_historico = []
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

        self._construir_ui()
        self._carregar_agentes()
        self.connect("close-request", self._ao_fechar)

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

        # Seletor de Agente: ícone + dropdown em uma pílula compacta
        seletor = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        seletor.add_css_class("agent-pill")
        icone_agente = Gtk.Image.new_from_icon_name("simba-agente")
        icone_agente.set_pixel_size(18)
        seletor.append(icone_agente)

        self.dropdown_model = Gtk.StringList()
        self.dropdown = Gtk.DropDown(model=self.dropdown_model)
        self.dropdown.add_css_class("agent-dropdown")
        self.dropdown.set_tooltip_text(_t("Agente de IA ativo"))
        self.dropdown.connect("notify::selected", self._on_agente_selecionado)
        seletor.append(self.dropdown)
        header.pack_start(seletor)

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

        # Central de agentes: tudo o que existe em Configurações, sem sair do chat
        btn_central = Gtk.Button(icon_name="simba-agente")
        btn_central.add_css_class("flat")
        btn_central.add_css_class("icon-button")
        btn_central.set_tooltip_text(f"{_t('Central de agentes')} (Ctrl+Shift+A)")
        btn_central.connect("clicked", lambda _: self._abrir_central())
        acoes.append(btn_central)

        self.btn_dir = Gtk.Button(icon_name="folder-symbolic")
        self.btn_dir.add_css_class("flat")
        self.btn_dir.add_css_class("icon-button")
        self.btn_dir.set_tooltip_text(f"{_t('Pasta de trabalho:')} {self.work_dir}")
        self.btn_dir.connect("clicked", self._escolher_pasta)
        acoes.append(self.btn_dir)

        # Exportar conversa para arquivo Markdown
        self.btn_exportar = Gtk.Button(icon_name="document-save-as-symbolic")
        self.btn_exportar.add_css_class("flat")
        self.btn_exportar.add_css_class("icon-button")
        self.btn_exportar.set_tooltip_text(_t("Exportar conversa para Markdown (.md)"))
        self.btn_exportar.connect("clicked", lambda _: self._exportar_conversa())
        acoes.append(self.btn_exportar)

        header.pack_end(acoes)

        # Área Central de Mensagens: coluna central ergonômica para leitura agradável
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.set_vexpand(True)
        self.scroller.set_hexpand(True)
        self.scroller.add_css_class("chat-scroll")

        self.box_mensagens = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.box_mensagens.set_hexpand(True)
        self.box_mensagens.set_halign(Gtk.Align.FILL)
        self.box_mensagens.set_margin_top(16)
        self.box_mensagens.set_margin_bottom(16)
        self.box_mensagens.set_margin_start(16)
        self.box_mensagens.set_margin_end(16)

        self.clamp_mensagens = Adw.Clamp()
        self.clamp_mensagens.set_maximum_size(920)
        self.clamp_mensagens.set_tightening_threshold(720)
        self.clamp_mensagens.set_child(self.box_mensagens)

        self.scroller.set_child(self.clamp_mensagens)
        # Seguir o fim: enquanto a pessoa está no fim da conversa, a rolagem
        # acompanha o texto novo; se ela rolar para cima para ler, para de seguir.
        self.seguir_fim = True
        adj = self.scroller.get_vadjustment()
        adj.connect("value-changed", self._rolagem_mudou)
        adj.connect("notify::upper", lambda *_: self.seguir_fim and GLib.idle_add(self._do_scroll))

        # O estado vazio fica sobreposto à área de rolagem para centralizar de verdade
        self.empty_state = self._criar_estado_vazio()
        self.overlay = Gtk.Overlay()
        self.overlay.set_vexpand(True)
        self.overlay.set_child(self.scroller)
        self.overlay.add_overlay(self.empty_state)

        # Barra Inferior de Entrada (alinhada à coluna de leitura do chat)
        box_inferior = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box_inferior.set_margin_start(16)
        box_inferior.set_margin_end(16)
        box_inferior.set_margin_bottom(12)
        box_inferior.set_margin_top(4)

        clamp_composer = Adw.Clamp()
        clamp_composer.set_maximum_size(920)
        clamp_composer.set_tightening_threshold(720)
        clamp_composer.set_child(self._criar_composer())
        box_inferior.append(clamp_composer)

        # Atalho de teclado no TextView (Enter envia, Shift+Enter nova linha)
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.text_input.add_controller(key_ctrl)

        # Arrastar e soltar arquivos na caixa de entrada
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("drop", self._on_file_drop)
        self.text_input.add_controller(drop_target)

        # Layout principal
        box_principal = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box_principal.add_css_class("chat-bg")
        box_principal.append(self.overlay)
        box_principal.append(box_inferior)
        toolbar_view.set_content(box_principal)

        self._atualizar_pasta_ui()
        self._atualizar_botao_enviar()
        GLib.idle_add(self.text_input.grab_focus)

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
        return box

    def _criar_composer(self):
        composer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        composer.add_css_class("composer-shell")
        composer.set_hexpand(True)
        composer.set_halign(Gtk.Align.FILL)
        self.composer_shell = composer

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

        # Modelo do agente selecionado, direto no rodapé (estilo OpenCode)
        self.modelo_lista = Gtk.StringList()
        self.modelo_dropdown = Gtk.DropDown(model=self.modelo_lista)
        self.modelo_dropdown.add_css_class("model-chip")
        self.modelo_dropdown.set_tooltip_text(_t("Modelo usado pela IA"))
        self.modelo_dropdown.set_size_request(150, -1)
        self.modelo_dropdown.set_visible(False)
        self.modelo_handler_id = self.modelo_dropdown.connect(
            "notify::selected", self._on_modelo_selecionado
        )
        self.modelo_opcoes = []
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

        # Uso do limite do agente (janelas de 5 h / 7 dias) e da última resposta
        self.lbl_uso = Gtk.Label(label="")
        self.lbl_uso.add_css_class("composer-hint")
        self.lbl_uso.set_valign(Gtk.Align.CENTER)
        self.lbl_uso.set_visible(False)
        rodape.append(self.lbl_uso)

        self.lbl_dica = Gtk.Label(label=_t("Enter envia · Shift+Enter quebra linha"))
        self.lbl_dica.add_css_class("composer-hint")
        self.lbl_dica.set_hexpand(True)
        self.lbl_dica.set_halign(Gtk.Align.START)
        self.lbl_dica.set_ellipsize(Pango.EllipsizeMode.END)
        rodape.append(self.lbl_dica)

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

    def _usar_sugestao(self, texto):
        self.text_input_buf.set_text(texto)
        fim = self.text_input_buf.get_end_iter()
        self.text_input_buf.place_cursor(fim)
        self.text_input.grab_focus()
        self._on_input_text_changed(self.text_input_buf)

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
        self.btn_enviar.set_sensitive(tem_texto)

    def _carregar_agentes(self):
        cfg = M.ler_config()
        self.candidatos = M.candidatos(cfg, verificar=False, seguro=bool(cfg.get("seguro")))

        # Preserva a escolha do usuário ao recarregar (ex.: depois de trocar o modelo)
        anterior = None
        idx = self.dropdown.get_selected()
        if 0 <= idx < len(self.dropdown_items):
            anterior = self.dropdown_items[idx]["id"]

        self.dropdown_items = []
        self.dropdown_items.append({"id": "auto", "nome": _t("Automático (Cascata)")})
        for a in self.candidatos:
            nome = M.AGENTES.get(a, {}).get("nome", a)
            modelo = M.modelo_escolhido(a, cfg)
            if modelo:
                nome += f" · {modelo}"
            ate = M.esgotado_ate(a)
            status = f" ({_t('sem limite até')} {M.hora(ate)})" if ate else ""
            self.dropdown_items.append({"id": a, "nome": f"{nome}{status}"})

        # Atualiza model do DropDown
        while self.dropdown_model.get_n_items() > 0:
            self.dropdown_model.remove(0)
        for it in self.dropdown_items:
            self.dropdown_model.append(it["nome"])

        selecionado = 0
        for i, it in enumerate(self.dropdown_items):
            if it["id"] == anterior:
                selecionado = i
                break
        self.dropdown.set_selected(selecionado)
        if selecionado == 0:
            self.agente_atual = None
        self._atualizar_modelo_dropdown()

    def _on_agente_selecionado(self, dropdown, _param):
        idx = dropdown.get_selected()
        if 0 <= idx < len(self.dropdown_items):
            escolhido = self.dropdown_items[idx]["id"]
            self.agente_atual = None if escolhido == "auto" else escolhido
        self._atualizar_modelo_dropdown()
        self._atualizar_uso_ui()

    def _atualizar_modelo_dropdown(self):
        if not hasattr(self, "modelo_dropdown"):
            return
        idx = self.dropdown.get_selected()
        if not (0 <= idx < len(self.dropdown_items)):
            self.modelo_dropdown.set_visible(False)
            return
        agente = self.dropdown_items[idx]["id"]
        if agente == "auto" or agente not in M.AGENTES:
            self.modelo_dropdown.set_visible(False)
            return

        cfg = M.ler_config()
        atual = M.modelo_escolhido(agente, cfg)
        opcoes = [{"valor": "", "rotulo": _t("Padrão do agente")}]
        vistos = {""}
        for o in M.modelos(agente):
            valor = str(o.get("valor", "")).strip()
            if valor and valor not in vistos:
                vistos.add(valor)
                opcoes.append({"valor": valor, "rotulo": o.get("rotulo") or valor})
        if atual and atual not in vistos:
            opcoes.append({"valor": atual, "rotulo": atual})

        self.modelo_opcoes = opcoes
        self.modelo_dropdown.handler_block(self.modelo_handler_id)
        while self.modelo_lista.get_n_items() > 0:
            self.modelo_lista.remove(0)
        selecionado = 0
        for i, o in enumerate(opcoes):
            self.modelo_lista.append(o["rotulo"])
            if o["valor"] == atual:
                selecionado = i
        self.modelo_dropdown.set_selected(selecionado)
        self.modelo_dropdown.handler_unblock(self.modelo_handler_id)
        self.modelo_dropdown.set_visible(len(opcoes) > 1)
        nome = M.AGENTES.get(agente, {}).get("nome", agente)
        self.modelo_dropdown.set_tooltip_text(f"{_t('Modelo de')} {nome}")

    def _on_modelo_selecionado(self, dropdown, _param):
        idx = dropdown.get_selected()
        if not (0 <= idx < len(self.modelo_opcoes)):
            return
        selec = self.dropdown.get_selected()
        if not (0 <= selec < len(self.dropdown_items)):
            return
        agente = self.dropdown_items[selec]["id"]
        if agente == "auto":
            return
        self._definir_modelo(agente, self.modelo_opcoes[idx]["valor"])

    def _definir_modelo(self, agente, valor):
        cfg = M.ler_config()
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
        self.ativo_status_box = None
        self.ativo_status_spinner = None
        self.ativo_status_check = None
        self.ativo_status_lbl = None
        self.ativo_modelo_lbl = None
        self.ativo_status_toggle = None
        self.ativo_status_revealer = None
        self.ativo_status_log_buf = None
        self.ativo_status_historico = []
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
            if caminhos:
                texto_arquivos = " ".join(f'"{c}"' for c in caminhos)
                start, end = self.text_input_buf.get_bounds()
                atual = self.text_input_buf.get_text(start, end, True)
                sep = " " if atual and not atual.endswith(" ") else ""
                self.text_input_buf.insert(end, sep + texto_arquivos)
                self.text_input.grab_focus()
                return True
        return False


    # ── Envio, fila e execução ───────────────────────────────────────────────
    def _rodando(self):
        return self.proc is not None and not self.finalizado

    def _on_enviar(self):
        start, end = self.text_input_buf.get_bounds()
        texto = self.text_input_buf.get_text(start, end, True).strip()
        if not texto:
            return
        self.text_input_buf.set_text("")
        self.empty_state.set_visible(False)

        # O agente ainda está respondendo: a mensagem espera a vez dela. (Antes
        # ela era escrita no pty, mas no modo print os agentes não leem a
        # entrada e a mensagem se perdia.)
        if self._rodando():
            widgets = self._adicionar_bolha_usuario(texto, registro=False, na_fila=True)
            self.fila.append({"texto": texto, "widgets": widgets})
            return
        self._enviar_pedido([texto])

    def _enviar_pedido(self, textos, bolhas=None):
        for i, texto in enumerate(textos):
            if bolhas and bolhas[i]:
                bolhas[i]["fila"].set_visible(False)
                self._registrar_usuario(texto)
            else:
                self._adicionar_bolha_usuario(texto)
        pedido = "\n\n".join(textos)
        if self.interrompido:
            pedido = (
                "(A sua resposta anterior foi interrompida pelo usuário antes de terminar. "
                "Considere o que já tinha sido feito e siga com o pedido abaixo.)\n\n" + pedido
            )
            self.interrompido = False
        self._iniciar_execucao(pedido)

    def _proximo_da_fila(self):
        if not self.fila:
            return
        itens, self.fila = self.fila, []
        self._enviar_pedido([i["texto"] for i in itens], [i["widgets"] for i in itens])

    def _devolver_fila(self):
        """Interrompido: as mensagens da fila voltam para a caixa de texto."""
        if not self.fila:
            return
        textos = [i["texto"] for i in self.fila]
        for item in self.fila:
            linha = item["widgets"].get("linha")
            if linha is not None and linha.get_parent() is self.box_mensagens:
                self.box_mensagens.remove(linha)
        self.fila = []
        inicio, fim = self.text_input_buf.get_bounds()
        atual = self.text_input_buf.get_text(inicio, fim, True).strip()
        self.text_input_buf.set_text("\n\n".join(textos + ([atual] if atual else [])))
        self.text_input_buf.place_cursor(self.text_input_buf.get_end_iter())

    def _agente_escolhido(self):
        idx = self.dropdown.get_selected()
        if 0 < idx < len(self.dropdown_items):
            return self.dropdown_items[idx]["id"]
        return None

    def _iniciar_execucao(self, pedido, agente_forcado=None, arq_passagem=None):
        cfg = M.ler_config()
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
        )
        self.ativo_parser = parser

        self.btn_parar.set_visible(True)
        self.btn_enviar.set_visible(True)
        self._atualizar_uso_ui()
        threading.Thread(target=self._loop_leitura, args=(mestre, proc, eid, parser, cfg),
                         daemon=True).start()

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
                if getattr(self, "ativo_modelo_lbl", None):
                    self.ativo_modelo_lbl.set_label(meta["modelo"])
                    self.ativo_modelo_lbl.set_visible(True)
        if meta.get("janelas"):
            self.janelas_uso[agente] = meta["janelas"]
            self._atualizar_uso_ui()

    def _atualizar_uso_ui(self):
        if not hasattr(self, "lbl_uso"):
            return
        agente = (self.agente_atual if self._rodando() else None) or self._agente_escolhido()
        if not agente:
            self.lbl_uso.set_visible(False)
            return
        janelas = dict(self.janelas_uso.get(agente) or {})
        if not janelas:
            # Do widget de uso, só janelas que ainda não reiniciaram (dado velho engana)
            u = M.uso(agente)
            for chave, rotulo in (("sessao", "5h"), ("semana", "7d")):
                if chave in u and M._futuro(u.get(f"{chave}Volta") or ""):
                    janelas[rotulo] = u[chave]
        if not janelas:
            self.lbl_uso.set_visible(False)
            return
        partes = [f"{k} {round(v * 100)}%" for k, v in janelas.items() if k in ("5h", "7d")]
        self.lbl_uso.set_label("◔ " + " · ".join(partes))
        nome = M.AGENTES.get(agente, {}).get("nome", agente)
        self.lbl_uso.set_tooltip_text(
            f"{_t('Limite usado de')} {nome}: 5h = {_t('sessão de 5 horas')}, 7d = {_t('semana')}"
        )
        alto = max(janelas.values()) >= 0.8
        if alto:
            self.lbl_uso.add_css_class("uso-alto")
        else:
            self.lbl_uso.remove_css_class("uso-alto")
        self.lbl_uso.set_visible(bool(partes))

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
        if not self.ativo_status_box:
            return
        if status_texto:
            status_texto = status_texto.strip()
            historico = self.ativo_status_historico
            if status_texto and (not historico or historico[-1] != status_texto):
                historico.append(status_texto)
                if self.ativo_status_log_buf:
                    self.ativo_status_log_buf.set_text("\n".join(historico))
                if self.ativo_registro is not None:
                    atividade = self.ativo_registro.setdefault("atividade", [])
                    if not atividade or atividade[-1] != status_texto:
                        atividade.append(status_texto)
                self._agendar_salvamento()
            if getattr(self, "ativo_status_lbl", None):
                self.ativo_status_lbl.set_label(status_texto)
                self.ativo_status_lbl.set_visible(True)
            self.ativo_status_box.set_visible(True)
            if self.ativo_status_spinner:
                self.ativo_status_spinner.set_visible(True)
                self.ativo_status_spinner.start()
            if self.ativo_status_toggle:
                self.ativo_status_toggle.set_visible(True)
        else:
            self.ativo_status_box.set_visible(False)
        self._scroll_para_fim()

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
        self.ativo_mensagem.definir(self.ativo_texto)
        self._scroll_para_fim()
        return False

    def _concluir_status_ativo(self, _resultado=None):
        if self.ativo_status_box and self.ativo_status_spinner:
            self.ativo_status_spinner.stop()
            self.ativo_status_spinner.set_visible(False)
        if getattr(self, "ativo_status_lbl", None):
            self.ativo_status_lbl.set_visible(False)
        # O botão continua disponível para consultar o histórico em paz.
        if self.ativo_status_box and self.ativo_status_historico:
            self.ativo_status_box.set_visible(True)
            if self.ativo_status_toggle:
                self.ativo_status_toggle.set_visible(True)
        elif self.ativo_status_box:
            self.ativo_status_box.set_visible(False)
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
        proc, self.proc = self.proc, None
        self.exec_atual = 0  # eventos atrasados desta execução passam a ser ignorados
        threading.Thread(target=self._encerrar_proc, args=(proc,), daemon=True).start()
        self.interrompido = True
        self._finalizar_resposta(interrompida=True)
        self._devolver_fila()

    def _finalizar_resposta(self, interrompida=False, notificar=True):
        if self.finalizado:
            return
        self.finalizado = True
        if self.render_fonte:
            GLib.source_remove(self.render_fonte)
            self.render_fonte = 0
        self._concluir_status_ativo()

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
            texto = texto.rstrip() + ("\n\n" if texto.strip() else "") + f"_⏹ {_t('Interrompido pelo usuário')}_"
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
            self.ativo_renderizado = True

        if notificar and not interrompida and not self.is_active():
            nome = M.AGENTES.get(self.agente_atual, {}).get("nome", _t("Agente de IA"))
            self._notificar_conclusao(nome)

        self.proc = None
        self._salvar_conversa()
        self._atualizar_uso_ui()
        self.btn_historico.set_sensitive(True)
        self.btn_parar.set_visible(False)
        self.btn_enviar.set_visible(True)
        self.text_input.grab_focus()
        self._scroll_para_fim()

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
    def _registrar_usuario(self, texto):
        self.conversa_mensagens.append({"tipo": "user", "texto": texto, "quando": time.time()})
        self._salvar_conversa()

    def _adicionar_bolha_usuario(self, texto, registro=True, na_fila=False):
        if registro:
            self._registrar_usuario(texto)

        box_linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box_linha.set_halign(Gtk.Align.END)
        box_linha.add_css_class("msg-user-row")

        bubble = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        bubble.add_css_class("user-bubble")

        lbl = Gtk.Label(label=texto, wrap=True, selectable=True, xalign=0)
        lbl.set_wrap_mode(Pango.WrapMode.WORD)
        lbl.set_max_width_chars(75)
        bubble.append(lbl)

        lbl_fila = Gtk.Label(label=f"⏳ {_t('Na fila: vai quando a resposta atual terminar')}", xalign=1)
        lbl_fila.add_css_class("fila-label")
        lbl_fila.set_visible(na_fila)
        bubble.append(lbl_fila)

        box_linha.append(bubble)
        self.box_mensagens.append(box_linha)
        self._scroll_para_fim(forcar=True)
        return {"linha": box_linha, "fila": lbl_fila}

    def _adicionar_bolha_assistente(
        self, agente, registro=True, ativo=True, modelo=None, hora=None, duracao=None
    ):
        info = M.AGENTES.get(agente, {})
        nome = info.get("nome", agente)
        if modelo is None:
            modelo = M.modelo_escolhido(agente, M.ler_config()) or info.get("modelo", "")

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("assistant-card")
        card.set_hexpand(True)

        # Cabeçalho: avatar, nome, modelo e horário
        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        avatar = Gtk.Box()
        avatar.add_css_class("assistant-avatar")
        avatar.set_valign(Gtk.Align.CENTER)
        img_icone = Gtk.Image.new_from_icon_name("simba-agente")
        img_icone.set_pixel_size(16)
        avatar.append(img_icone)
        header_row.append(avatar)

        lbl_nome = Gtk.Label(label=nome)
        lbl_nome.add_css_class("assistant-name")
        lbl_nome.set_valign(Gtk.Align.CENTER)
        header_row.append(lbl_nome)

        lbl_mod = Gtk.Label(label=modelo or "")
        lbl_mod.add_css_class("model-badge")
        lbl_mod.set_valign(Gtk.Align.CENTER)
        lbl_mod.set_ellipsize(Pango.EllipsizeMode.END)
        lbl_mod.set_max_width_chars(34)
        lbl_mod.set_visible(bool(modelo))
        header_row.append(lbl_mod)

        lbl_duracao = Gtk.Label(label=f"⏱ {duracao}" if duracao else "")
        lbl_duracao.add_css_class("duration-badge")
        lbl_duracao.set_valign(Gtk.Align.CENTER)
        lbl_duracao.set_visible(bool(duracao))
        header_row.append(lbl_duracao)

        espaco = Gtk.Box()
        espaco.set_hexpand(True)
        header_row.append(espaco)

        lbl_hora = Gtk.Label(label=hora or datetime.now().strftime("%H:%M"))
        lbl_hora.add_css_class("msg-time")
        lbl_hora.set_valign(Gtk.Align.CENTER)
        header_row.append(lbl_hora)
        card.append(header_row)

        # Atividade discreta: spinner minúsculo e botão para ver os detalhes
        status_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        status_row.add_css_class("activity-row")
        status_row.set_halign(Gtk.Align.START)
        status_row.set_visible(False)

        spinner = Gtk.Spinner()
        spinner.set_size_request(12, 12)
        spinner.set_valign(Gtk.Align.CENTER)
        spinner.start()
        status_row.append(spinner)

        # O que a IA está fazendo agora (ferramenta, comando, arquivo)
        lbl_status = Gtk.Label(label="", xalign=0)
        lbl_status.add_css_class("activity-now")
        lbl_status.set_ellipsize(Pango.EllipsizeMode.END)
        lbl_status.set_max_width_chars(70)
        lbl_status.set_visible(False)
        status_row.append(lbl_status)

        espaco_status = Gtk.Box()
        espaco_status.set_hexpand(True)
        status_row.append(espaco_status)

        btn_detalhes = Gtk.ToggleButton()
        btn_detalhes.add_css_class("flat")
        btn_detalhes.add_css_class("activity-toggle")
        btn_detalhes.set_valign(Gtk.Align.CENTER)
        btn_detalhes.set_tooltip_text(_t("Ver o que a IA pensou e executou"))
        btn_detalhes.set_visible(False)
        conteudo_detalhes = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        icone_detalhes = Gtk.Image.new_from_icon_name("pan-end-symbolic")
        icone_detalhes.set_pixel_size(10)
        rotulo_detalhes = Gtk.Label(label=_t("Detalhes"))
        conteudo_detalhes.append(icone_detalhes)
        conteudo_detalhes.append(rotulo_detalhes)
        btn_detalhes.set_child(conteudo_detalhes)
        status_row.append(btn_detalhes)
        card.append(status_row)

        # Painel expansível com o histórico de pensamento/ações (oculto por padrão)
        revealer = Gtk.Revealer()
        revealer.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        revealer.set_transition_duration(180)
        revealer.set_reveal_child(False)
        log_view = Gtk.TextView()
        log_view.set_editable(False)
        log_view.set_cursor_visible(False)
        log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        log_view.set_top_margin(2)
        log_view.set_bottom_margin(2)
        log_view.set_left_margin(2)
        log_view.set_right_margin(2)
        log_view.add_css_class("activity-log")
        log_buf = log_view.get_buffer()
        revealer.set_child(log_view)
        card.append(revealer)

        # Corpo da resposta: blocos de texto, código e tabela (markdown.MensagemView)
        mensagem = self._criar_mensagem()
        card.append(mensagem)

        # Ações da resposta
        act_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        act_row.add_css_class("msg-actions")
        btn_copiar = Gtk.Button()
        btn_copiar.set_child(Adw.ButtonContent(icon_name="edit-copy-symbolic", label=_t("Copiar")))
        btn_copiar.add_css_class("flat")
        btn_copiar.add_css_class("action-button")
        btn_copiar.set_halign(Gtk.Align.START)
        btn_copiar.connect("clicked", lambda b: self._copiar_texto(mensagem.texto, b))
        act_row.append(btn_copiar)
        card.append(act_row)

        self.box_mensagens.append(card)

        btn_detalhes.connect(
            "toggled",
            lambda b, rev=revealer, ico=icone_detalhes: self._alternar_detalhes(b, rev, ico),
        )

        if registro:
            novo = {
                "tipo": "assistant",
                "agente": agente,
                "modelo": modelo,
                "hora": lbl_hora.get_label(),
                "quando": time.time(),
                "texto": "",
                "atividade": [],
            }
            self.conversa_mensagens.append(novo)
            if ativo:
                self.ativo_registro = novo

        if ativo:
            self.ativo_mensagem = mensagem
            self.ativo_status_box = status_row
            self.ativo_status_spinner = spinner
            self.ativo_status_lbl = lbl_status
            self.ativo_modelo_lbl = lbl_mod
            self.ativo_status_check = None
            self.ativo_status_toggle = btn_detalhes
            self.ativo_status_revealer = revealer
            self.ativo_status_log_buf = log_buf
            self.ativo_status_historico = []
            self.ativo_duracao_lbl = lbl_duracao
            self.ativo_renderizado = False

        if registro:
            self._salvar_conversa()

        self._scroll_para_fim(forcar=True)
        return {
            "card": card,
            "mensagem": mensagem,
            "status_row": status_row,
            "spinner": spinner,
            "toggle": btn_detalhes,
            "revealer": revealer,
            "log_buf": log_buf,
            "icone": icone_detalhes,
            "duracao_lbl": lbl_duracao,
        }

    def _alternar_detalhes(self, btn, revealer=None, icone=None):
        revealer = revealer or self.ativo_status_revealer
        if not revealer:
            return
        aberto = btn.get_active()
        revealer.set_reveal_child(aberto)
        alvo = icone or btn
        alvo.set_from_icon_name("pan-down-symbolic" if aberto else "pan-end-symbolic")
        if aberto:
            GLib.idle_add(self._do_scroll)

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
