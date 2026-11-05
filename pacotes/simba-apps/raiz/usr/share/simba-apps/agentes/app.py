#!/usr/bin/env python3
"""Agentes de IA do Simba OS — Frontend gráfico unificado de Chat (GTK4/libadwaita).

Permite interagir com todos os agentes de IA instalados (Claude Code, Antigravity,
Codex, Grok, Copilot, etc.) em uma interface centralizada de chat.
Quando o limite de uso de um agente é atingido, a conversa é continuada automaticamente
no próximo agente de forma transparente, sem fechar a janela ou quebrar o fluxo.
"""
import codecs
from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import pty
import re
import select
import shutil
import signal
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

APP_ID = "com.simba.Agentes"
HOME = Path.home()


# ── Parser Dinâmico de Eventos e Ferramentas ──────────────────────────────────
class AgentStreamParser:
    """Interpreta streams JSON (NDJSON) ou texto puro dos agentes de IA.

    Separa chamadas de ferramentas e spinners (direcionando para a pílula de status dinâmico)
    do texto real da resposta que preenche a conversa.
    """

    def __init__(self, on_status, on_text, on_done):
        self.on_status = on_status
        self.on_text = on_text
        self.on_done = on_done
        self.buffer = ""
        self.actions = []
        self.last_response = ""
        self.has_text = False

    def feed(self, chunk: str):
        self.buffer += chunk
        lines = self.buffer.split("\n")
        self.buffer = lines.pop()

        for line in lines:
            line_s = line.strip()
            if not line_s:
                continue

            # Tenta decodificar evento JSON
            if line_s.startswith("{") and line_s.endswith("}"):
                try:
                    data = json.loads(line_s)
                    self._handle_json(data)
                    continue
                except json.JSONDecodeError:
                    pass

            # Fallback para agentes que produzem texto puro / logs
            self._handle_plain_text(line_s)

    def _handle_json(self, data: dict):
        event = data.get("event")

        # Formato Antigravity CLI
        if event == "step_update":
            su = data.get("step_update", {})
            st = su.get("step_type")
            state = su.get("state")
            if st == "tool":
                tname = su.get("tool_name", "ferramenta")
                tinfo = su.get("tool_info", {})
                params = tinfo.get("parameters", {})
                desc = self._format_tool(tname, params)
                if state == "ACTIVE":
                    self.on_status(desc)
                elif state == "DONE":
                    if desc not in self.actions:
                        self.actions.append(desc)
                    self.on_status(_t("✦ Pensando na resposta..."))
            elif st == "agent_response":
                delta = su.get("text_delta")
                if delta:
                    self.has_text = True
                    self.on_text(delta)
        elif event == "result":
            res = data.get("result", {})
            resp = res.get("response", "")
            self.last_response = resp
            self.on_done(resp)

        # Formato Claude Code / stream-json
        elif "type" in data:
            t = data.get("type")
            if t == "tool_use":
                name = data.get("name", "ferramenta")
                inp = data.get("input", {})
                cmd = inp.get("command") or inp.get("path") or ""
                desc = f"Executando: {cmd[:40]}" if cmd else f"Executando {name}"
                if desc not in self.actions:
                    self.actions.append(desc)
                self.on_status(f"⚡ {desc}...")
            elif t == "content_block_delta":
                delta = data.get("delta", {}).get("text", "")
                if delta:
                    self.has_text = True
                    self.on_text(delta)
            elif t == "assistant":
                msg = data.get("message", {})
                for c in msg.get("content", []):
                    if c.get("type") == "text":
                        txt = c.get("text", "")
                        self.has_text = True
                        self.on_text(txt)
            elif t == "result":
                self.last_response = data.get("result", "")
                self.on_done(self.last_response)

    def _format_tool(self, tool_name: str, params: dict) -> str:
        if tool_name == "run_command":
            cmd = params.get("CommandLine", "")
            return f"⚡ {_t('Executando:')} {cmd[:42]}..."
        elif tool_name in ("read_file", "view_file"):
            p = Path(params.get("Path", "")).name or params.get("Path", "")
            return f"⚡ {_t('Lendo:')} {p}..."
        elif tool_name in ("write_to_file", "replace_file_content", "edit_file"):
            p = Path(params.get("Path", "")).name or params.get("Path", "")
            return f"⚡ {_t('Editando:')} {p}..."
        elif tool_name == "search_web":
            q = params.get("query", "")
            return f"⚡ {_t('Pesquisando na web:')} {q[:32]}..."
        elif tool_name == "list_dir":
            p = Path(params.get("Path", "")).name or params.get("Path", "")
            return f"⚡ {_t('Listando:')} {p or _t('arquivos')}..."
        return f"⚡ {tool_name}..."

    def _handle_plain_text(self, line: str):
        # Limpa caracteres de spinner braille
        clean = re.sub(r"[\u2800-\u28FF]+", "", line).strip()
        if not clean:
            return

        # Redireciona mensagens de comando para status
        m = re.match(r"^(?:Running command|Reading file|Editing file|Searching)\s*:?\s*(.*)", clean, re.I)
        if m:
            self.on_status(f"⚡ {clean[:50]}...")
            return

        # Descarta banners e indicadores de expansão de terminal
        if re.search(r"(?:Antigravity CLI|ctrl\+o to expand|\bcommands? \(\+\d+)", clean, re.I):
            self.on_status(_t("⚡ Executando ações..."))
            return

        self.has_text = True
        self.on_text(clean + "\n")

    def finish(self):
        if self.buffer.strip():
            self._handle_plain_text(self.buffer.strip())
        self.on_done(self.last_response)


def definir_tamanho_pty(fd, linhas=40, colunas=120):
    try:
        ws = struct.pack("HHHH", linhas, colunas, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, ws)
    except Exception:
        pass


# ── Design Moderno de Chat (UX/UI Especialista) ─────────────────────────────
CSS = """
window.background, .chat-window, .chat-bg, .chat-scroll {
  background-color: @window_bg_color;
}

/* Bolhas de mensagem do usuário (Alinhadas à direita com destaque visual) */
.msg-user-box {
  margin: 4px 14px 4px 80px;
}
.msg-user {
  background-color: @accent_bg_color;
  color: @accent_fg_color;
  border-radius: 18px 18px 4px 18px;
  padding: 12px 18px;
  box-shadow: 0 1px 3px alpha(#000, 0.15);
}
.msg-user label {
  color: @accent_fg_color;
  font-size: 14.5px;
  line-height: 1.45;
}

/* Cartão de resposta da IA (Ocupa 100% da largura útil sem cortes laterais) */
.msg-assistant-card {
  background-color: alpha(@window_fg_color, 0.04);
  border: 1px solid alpha(@window_fg_color, 0.09);
  border-radius: 16px;
  padding: 16px 20px;
  margin: 6px 14px;
}
.msg-assistant-header {
  font-size: 13.5px;
  font-weight: 700;
  opacity: 0.95;
}
.msg-assistant-model {
  font-size: 11px;
  opacity: 0.70;
  background-color: alpha(@window_fg_color, 0.08);
  border-radius: 10px;
  padding: 2px 8px;
  margin-left: 6px;
}

/* Indicador dinâmico de status da IA (Pílula interativa para ações e ferramentas) */
.status-pill {
  background-color: alpha(@accent_color, 0.12);
  border: 1px solid alpha(@accent_color, 0.28);
  color: @accent_color;
  border-radius: 12px;
  padding: 6px 14px;
  font-size: 12.5px;
  font-weight: 600;
  margin: 6px 0 10px 0;
}
.status-pill.done {
  background-color: alpha(@window_fg_color, 0.04);
  border-color: alpha(@window_fg_color, 0.08);
  color: alpha(@window_fg_color, 0.65);
  font-weight: 500;
}

/* Corpo do texto da resposta */
.msg-body {
  background-color: transparent;
  font-size: 14.5px;
  line-height: 1.6;
}

/* Barra de ação inferior da resposta */
.msg-action-bar {
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid alpha(@window_fg_color, 0.06);
}
.btn-copiar {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 8px;
}

/* Cartão de Entrada Flutuante */
.chat-input-card {
  background-color: alpha(@window_fg_color, 0.05);
  border: 1.5px solid alpha(@window_fg_color, 0.12);
  border-radius: 18px;
  padding: 6px 12px;
  box-shadow: 0 2px 8px alpha(#000, 0.10);
}
.chat-input-card:focus-within {
  border-color: @accent_color;
  box-shadow: 0 0 0 1px @accent_color;
}

/* Handover Banner */
.msg-handover {
  background-color: alpha(@warning_color, 0.15);
  border: 1px solid alpha(@warning_color, 0.40);
  color: @warning_color;
  border-radius: 20px;
  padding: 8px 20px;
  margin: 10px 14px;
  font-weight: 600;
  font-size: 13px;
}
"""


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_t("Agentes de IA"))
        self.set_default_size(880, 700)
        self.set_size_request(520, 500)
        self.add_css_class("chat-bg")

        # Estado da sessão
        self.work_dir = HOME / "Work" if (HOME / "Work").is_dir() else HOME
        self.proc = None
        self.mestre_fd = None
        self.agente_atual = None
        self.usados = set()
        self.conversas_iniciadas = set()
        self.anterior_passagem = None
        self.historico_tela = bytearray()
        self.inicio_agente = 0.0
        self.cauda_buffer = ""
        self.ignorar_limite_ate = 0.0

        # Elementos da bolha ativa
        self.ativo_assistente_view = None
        self.ativo_assistente_buf = None
        self.ativo_status_box = None
        self.ativo_status_icon = None
        self.ativo_status_lbl = None
        self.ativo_parser = None

        self._construir_ui()
        self._carregar_agentes()

    def _construir_ui(self):
        # Toolbar View
        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_css_class("chat-bg")
        self.set_content(toolbar_view)

        # Header Bar
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        # Seletor de Agente (Dropdown)
        self.dropdown_model = Gtk.StringList()
        self.dropdown = Gtk.DropDown(model=self.dropdown_model)
        self.dropdown.set_tooltip_text(_t("Agente de IA ativo"))
        self.dropdown.connect("notify::selected", self._on_agente_selecionado)
        header.pack_start(self.dropdown)

        # Botão Nova Conversa
        btn_novo = Gtk.Button(icon_name="document-new-symbolic")
        btn_novo.set_tooltip_text(_t("Nova conversa (limpar histórico)"))
        btn_novo.connect("clicked", lambda _: self._limpar_chat())
        header.pack_start(btn_novo)

        # Botão de Configurações
        btn_cfg = Gtk.Button(icon_name="preferences-system-symbolic")
        btn_cfg.set_tooltip_text(_t("Abrir Configurações › Agentes de IA"))
        btn_cfg.connect("clicked", lambda _: self._abrir_configuracoes())
        header.pack_end(btn_cfg)

        # Indicador de Pasta de Trabalho
        self.btn_dir = Gtk.Button(icon_name="folder-symbolic")
        self.btn_dir.set_tooltip_text(f"{_t('Pasta de trabalho:')} {self.work_dir}")
        self.btn_dir.connect("clicked", self._escolher_pasta)
        header.pack_end(self.btn_dir)

        # Área Central de Mensagens
        self.scroller = Gtk.ScrolledWindow()
        self.scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.scroller.set_vexpand(True)
        self.scroller.set_hexpand(True)
        self.scroller.add_css_class("chat-scroll")

        self.box_mensagens = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.box_mensagens.set_margin_top(14)
        self.box_mensagens.set_margin_bottom(14)
        self.scroller.set_child(self.box_mensagens)

        # Banner de Boas-Vindas
        self.status_page = Adw.StatusPage()
        self.status_page.set_icon_name("simba-agente")
        self.status_page.set_title(_t("Agentes de IA"))
        self.status_page.set_description(
            _t("Converse e delegue tarefas aos agentes com transparência total.\n"
               "Se a cota de um se esgotar, o próximo assume automaticamente com todo o contexto.")
        )
        self.box_mensagens.append(self.status_page)

        # Barra Inferior de Entrada
        box_inferior = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box_inferior.set_margin_start(14)
        box_inferior.set_margin_end(14)
        box_inferior.set_margin_bottom(14)
        box_inferior.set_margin_top(4)

        # Card de Entrada Flutuante
        card_input = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        card_input.add_css_class("chat-input-card")

        scroll_txt = Gtk.ScrolledWindow()
        scroll_txt.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_txt.set_propagate_natural_height(True)
        scroll_txt.set_min_content_height(38)
        scroll_txt.set_max_content_height(130)
        scroll_txt.set_hexpand(True)

        self.text_input = Gtk.TextView()
        self.text_input.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_input.set_accepts_tab(False)
        self.text_input.set_top_margin(4)
        self.text_input.set_bottom_margin(4)
        self.text_input.set_left_margin(4)
        self.text_input.set_right_margin(4)
        self.text_input_buf = self.text_input.get_buffer()
        scroll_txt.set_child(self.text_input)

        # Placeholder com Overlay
        overlay_input = Gtk.Overlay()
        overlay_input.set_hexpand(True)
        overlay_input.set_child(scroll_txt)

        self.lbl_placeholder = Gtk.Label(
            label=_t("Pergunte algo ou dê uma tarefa aos agentes... (Enter envia, Shift+Enter pula linha)")
        )
        self.lbl_placeholder.set_halign(Gtk.Align.START)
        self.lbl_placeholder.set_valign(Gtk.Align.CENTER)
        self.lbl_placeholder.set_margin_start(8)
        self.lbl_placeholder.add_css_class("dim-label")
        self.lbl_placeholder.set_can_target(False)
        overlay_input.add_overlay(self.lbl_placeholder)

        self.text_input_buf.connect("changed", self._on_input_text_changed)
        card_input.append(overlay_input)

        # Botão Interromper
        self.btn_parar = Gtk.Button(icon_name="process-stop-symbolic")
        self.btn_parar.add_css_class("destructive-action")
        self.btn_parar.add_css_class("circular")
        self.btn_parar.set_valign(Gtk.Align.END)
        self.btn_parar.set_visible(False)
        self.btn_parar.set_tooltip_text(_t("Interromper"))
        self.btn_parar.connect("clicked", lambda _: self._interromper())
        card_input.append(self.btn_parar)

        # Botão Enviar
        self.btn_enviar = Gtk.Button(icon_name="mail-send-symbolic")
        self.btn_enviar.add_css_class("suggested-action")
        self.btn_enviar.add_css_class("circular")
        self.btn_enviar.set_valign(Gtk.Align.END)
        self.btn_enviar.set_tooltip_text(_t("Enviar (Enter)"))
        self.btn_enviar.connect("clicked", lambda _: self._on_enviar())
        card_input.append(self.btn_enviar)

        box_inferior.append(card_input)

        # Atalho de teclado no TextView (Enter envia, Shift+Enter nova linha)
        key_ctrl = Gtk.EventControllerKey()
        key_ctrl.connect("key-pressed", self._on_key_pressed)
        self.text_input.add_controller(key_ctrl)

        # Layout principal
        box_principal = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box_principal.add_css_class("chat-bg")
        box_principal.append(self.scroller)
        box_principal.append(box_inferior)
        toolbar_view.set_content(box_principal)

    def _carregar_agentes(self):
        cfg = M.ler_config()
        self.candidatos = M.candidatos(cfg)
        self.dropdown_items = []

        # Opção Automático
        self.dropdown_items.append({"id": "auto", "nome": _t("Automático (Cascata)")})
        for a in self.candidatos:
            nome = M.AGENTES.get(a, {}).get("nome", a)
            ate = M.esgotado_ate(a)
            status = f" ({_t('sem limite até')} {M.hora(ate)})" if ate else ""
            self.dropdown_items.append({"id": a, "nome": f"{nome}{status}"})

        # Atualiza model do DropDown
        while self.dropdown_model.get_n_items() > 0:
            self.dropdown_model.remove(0)
        for it in self.dropdown_items:
            self.dropdown_model.append(it["nome"])
        self.dropdown.set_selected(0)

    def _on_agente_selecionado(self, dropdown, _param):
        idx = dropdown.get_selected()
        if 0 <= idx < len(self.dropdown_items):
            escolhido = self.dropdown_items[idx]["id"]
            if escolhido != "auto":
                self.agente_atual = escolhido

    def _escolher_pasta(self, _btn):
        dialog = Gtk.FileDialog(title=_t("Selecionar Pasta de Trabalho"))
        dialog.set_initial_folder(Gio.File.new_for_path(str(self.work_dir)))
        dialog.select_folder(self, None, self._on_pasta_selecionada)

    def _on_pasta_selecionada(self, dialog, result):
        try:
            folder = dialog.select_folder_finish(result)
            if folder:
                self.work_dir = Path(folder.get_path())
                self.btn_dir.set_tooltip_text(f"{_t('Pasta de trabalho:')} {self.work_dir}")
                self._adicionar_sistema(f"{_t('Pasta alterada para:')} {self.work_dir}")
        except Exception:
            pass

    def _abrir_configuracoes(self):
        subprocess.Popen(["configuracoes", "agentes"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

    def _limpar_chat(self):
        self._interromper()
        while True:
            child = self.box_mensagens.get_first_child()
            if not child:
                break
            self.box_mensagens.remove(child)
        self.status_page = Adw.StatusPage()
        self.status_page.set_icon_name("simba-agente")
        self.status_page.set_title(_t("Agentes de IA"))
        self.status_page.set_description(
            _t("Converse e delegue tarefas aos agentes com transparência total.\n"
               "Se a cota de um se esgotar, o próximo assume automaticamente com todo o contexto.")
        )
        self.box_mensagens.append(self.status_page)
        self.usados.clear()
        self.conversas_iniciadas.clear()
        self.anterior_passagem = None
        self.agente_atual = None
        self.ativo_assistente_view = None
        self.ativo_assistente_buf = None
        self.ativo_status_box = None
        self.ativo_status_icon = None
        self.ativo_status_lbl = None
        self.ativo_parser = None

    def _on_input_text_changed(self, buf):
        if hasattr(self, "lbl_placeholder"):
            self.lbl_placeholder.set_visible(buf.get_char_count() == 0)

    def _on_key_pressed(self, _controller, keyval, _keycode, state):
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            if not (state & Gdk.ModifierType.SHIFT_MASK):
                self._on_enviar()
                return True
        elif keyval == Gdk.KEY_Escape:
            if self.proc and self.proc.poll() is None:
                self._interromper()
                return True
        elif keyval == Gdk.KEY_l and (state & Gdk.ModifierType.CONTROL_MASK):
            self._limpar_chat()
            return True
        return False

    def _on_enviar(self):
        start, end = self.text_input_buf.get_bounds()
        texto = self.text_input_buf.get_text(start, end, True).strip()
        if not texto:
            return

        self.text_input_buf.set_text("")

        # Esconde tela de boas-vindas na primeira mensagem
        if self.status_page.get_parent() == self.box_mensagens:
            self.box_mensagens.remove(self.status_page)

        # Adiciona bolha do usuário
        self._adicionar_bolha_usuario(texto)

        # Se já existe um processo ativo e aguardando entrada do usuário via PTY:
        if self.proc and self.mestre_fd is not None and self.proc.poll() is None:
            try:
                os.write(self.mestre_fd, (texto + "\n").encode("utf-8"))
            except OSError:
                pass
            return

        # Inicia nova execução da IA
        self._iniciar_execucao(texto)

    def _iniciar_execucao(self, pedido, agente_forcado=None):
        cfg = M.ler_config()
        if agente_forcado:
            agente = agente_forcado
        else:
            sel_idx = self.dropdown.get_selected()
            if sel_idx > 0 and sel_idx < len(self.dropdown_items):
                agente = self.dropdown_items[sel_idx]["id"]
            else:
                cands = [a for a in M.candidatos(cfg, pular=self.usados) if not M.esgotado_ate(a)]
                if not cands:
                    cands = M.candidatos(cfg)
                if not cands:
                    self._adicionar_sistema(_t("Nenhum agente disponível no momento. Abra as Configurações para conectar suas contas."))
                    return
                agente = cands[0]

        self.agente_atual = agente
        self.usados.add(agente)
        self.inicio_agente = time.time()
        self.historico_tela.clear()
        self.cauda_buffer = ""
        self.ignorar_limite_ate = time.time() + 2.0

        # Cria a bolha de resposta da IA em largura completa
        self._adicionar_bolha_assistente(agente)

        # Prepara comando (modo print/turnos com histórico de sessão)
        info = M.AGENTES[agente]
        cmd = list(info["cmd"])
        continuar = (agente in self.conversas_iniciadas) and ("continue" in info)
        args_template = info.get("continue") if continuar else info.get("prompt")
        if pedido and args_template:
            cmd += [x.replace("{p}", pedido) for x in args_template]
        elif pedido:
            cmd += [pedido]

        self.conversas_iniciadas.add(agente)

        # PTY
        mestre, escravo = pty.openpty()
        definir_tamanho_pty(escravo, 40, 120)
        self.mestre_fd = mestre

        env = dict(os.environ)
        env["AGENTES_ATUAL"] = agente
        env["PYTHONUNBUFFERED"] = "1"
        env["TERM"] = "xterm-256color"
        env["COLUMNS"] = "120"
        env["LINES"] = "40"

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdin=escravo,
                stdout=escravo,
                stderr=escravo,
                cwd=str(self.work_dir),
                env=env,
                preexec_fn=os.setsid,
                close_fds=True
            )
            os.close(escravo)
        except Exception as e:
            os.close(mestre)
            self._adicionar_sistema(f"{_t('Erro ao iniciar')} {info['nome']}: {e}")
            return

        self.btn_parar.set_visible(True)
        self.btn_enviar.set_visible(True)

        threading.Thread(target=self._loop_leitura, args=(mestre, agente, pedido, cfg), daemon=True).start()

    def _loop_leitura(self, mestre, agente, pedido, cfg):
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        parser = AgentStreamParser(
            on_status=lambda s: GLib.idle_add(self._atualizar_status_ativo, s),
            on_text=lambda t: GLib.idle_add(self._anexar_texto_ativo, t),
            on_done=lambda d: GLib.idle_add(self._concluir_status_ativo, d),
        )
        self.ativo_parser = parser

        while self.proc and self.proc.poll() is None:
            try:
                r, _, _ = select.select([mestre], [], [], 0.1)
            except (InterruptedError, ValueError):
                break
            if mestre in r:
                try:
                    dados = os.read(mestre, 4096)
                except OSError:
                    break
                if not dados:
                    break

                self.historico_tela += dados
                if len(self.historico_tela) > 400000:
                    del self.historico_tela[:100000]

                texto = decoder.decode(dados)
                parser.feed(texto)

                # Detecção de limite de uso
                if cfg.get("trocaAutomatica", True) and time.time() >= self.ignorar_limite_ate:
                    ultimos = (self.cauda_buffer + texto)[-1200:]
                    self.cauda_buffer = ultimos
                    if M.detectar_limite(ultimos):
                        GLib.idle_add(self._executar_troca_transparente, agente, cfg)
                        return

        try:
            os.close(mestre)
        except OSError:
            pass

        parser.finish()
        GLib.idle_add(self._finalizar_resposta)

    def _atualizar_status_ativo(self, status_texto):
        if self.ativo_status_box and self.ativo_status_lbl:
            if status_texto:
                self.ativo_status_box.set_visible(True)
                self.ativo_status_box.remove_css_class("done")
                self.ativo_status_icon.set_from_icon_name("system-run-symbolic")
                self.ativo_status_lbl.set_text(status_texto)
            else:
                self.ativo_status_box.set_visible(False)
            self._scroll_para_fim()

    def _anexar_texto_ativo(self, texto):
        if self.ativo_assistente_buf:
            end = self.ativo_assistente_buf.get_end_iter()
            self.ativo_assistente_buf.insert(end, texto)
            self._scroll_para_fim()

    def _concluir_status_ativo(self, _resultado=None):
        if self.ativo_status_box and self.ativo_status_lbl:
            if self.ativo_parser and self.ativo_parser.actions:
                qtd = len(self.ativo_parser.actions)
                sufixo = _t("ações executadas") if qtd > 1 else _t("ação executada")
                resumo = ", ".join(self.ativo_parser.actions[:3])
                if len(self.ativo_parser.actions) > 3:
                    resumo += "..."
                self.ativo_status_box.add_css_class("done")
                self.ativo_status_icon.set_from_icon_name("emblem-ok-symbolic")
                self.ativo_status_lbl.set_text(f"✓ {qtd} {sufixo} ({resumo})")
                self.ativo_status_box.set_visible(True)
            else:
                self.ativo_status_box.set_visible(False)
            self._scroll_para_fim()

    def _executar_troca_transparente(self, agente_antigo, cfg):
        M.encerrar(self.proc.pid)
        self.proc = None
        self.mestre_fd = None

        M.marcar_esgotado(agente_antigo)
        arq = M.passagem(agente_antigo, self.work_dir, self.inicio_agente, bytes(self.historico_tela), self.anterior_passagem)
        self.anterior_passagem = arq

        seguintes = [a for a in M.candidatos(cfg, pular=self.usados) if not M.esgotado_ate(a)]
        nome_antigo = M.AGENTES[agente_antigo]["nome"]

        if not seguintes:
            self._adicionar_sistema(
                f"⚡ {_t('Limite de uso atingido para')} {nome_antigo}. "
                f"{_t('Todos os agentes configurados estão sem limite no momento. Contexto salvo em:')} {arq.name}"
            )
            self._finalizar_resposta()
            return

        proximo = seguintes[0]
        nome_proximo = M.AGENTES[proximo]["nome"]

        # Banner estilizado e transparente na conversa
        self._adicionar_aviso_handover(nome_antigo, nome_proximo)

        # Notificação do sistema
        subprocess.run([
            "notify-send", "-a", _t("Agentes de IA"), "-i", "dialog-information",
            f"{_t('Continuando com')} {nome_proximo}",
            f"{_t('O limite de uso do')} {nome_antigo} {_t('acabou. O trabalho continua automaticamente.')}"
        ], capture_output=True)

        novo_pedido = (
            f"Você vai continuar um trabalho que outro agente de IA ({nome_antigo}) começou e não terminou "
            f"porque o limite de uso dele acabou. Leia primeiro, por inteiro, o arquivo {arq} (pedido do usuário, conversa, comandos e estado do Git). "
            f"Depois confira o que já foi feito e continue exatamente de onde parou, sem pedir para o usuário repetir nada."
        )

        # Inicia imediatamente o próximo agente
        self._iniciar_execucao(novo_pedido, agente_forcado=proximo)

    def _interromper(self):
        if self.proc:
            try:
                M.encerrar(self.proc.pid)
            except Exception:
                pass
            self.proc = None
        if self.mestre_fd is not None:
            try:
                os.close(self.mestre_fd)
            except Exception:
                pass
            self.mestre_fd = None
        self._finalizar_resposta()

    def _finalizar_resposta(self):
        self._concluir_status_ativo()
        if self.ativo_assistente_buf and self.ativo_assistente_buf.get_char_count() == 0:
            if self.ativo_parser and self.ativo_parser.last_response:
                self.ativo_assistente_buf.set_text(self.ativo_parser.last_response)
            else:
                self.ativo_assistente_buf.set_text(_t("(Concluído sem texto adicional)"))
        self.btn_parar.set_visible(False)
        self.btn_enviar.set_visible(True)
        self.text_input.grab_focus()
        self._scroll_para_fim()

    # ── Construtores de Mensagens e Cards ────────────────────────────────────
    def _adicionar_bolha_usuario(self, texto):
        box_linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box_linha.set_halign(Gtk.Align.END)
        box_linha.add_css_class("msg-user-box")

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("msg-user")

        lbl = Gtk.Label(label=texto, wrap=True, selectable=True, xalign=0)
        lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        card.append(lbl)

        box_linha.append(card)
        self.box_mensagens.append(box_linha)
        self._scroll_para_fim()

    def _adicionar_bolha_assistente(self, agente):
        info = M.AGENTES.get(agente, {})
        nome = info.get("nome", agente)
        modelo = info.get("modelo", "")

        # Cartão da IA ocupa 100% da largura útil da janela
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("msg-assistant-card")
        card.set_hexpand(True)

        # Cabeçalho da IA
        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        img_icone = Gtk.Image.new_from_icon_name("simba-agente")
        lbl_nome = Gtk.Label(label=nome)
        lbl_nome.add_css_class("msg-assistant-header")
        header_row.append(img_icone)
        header_row.append(lbl_nome)

        if modelo:
            lbl_mod = Gtk.Label(label=modelo)
            lbl_mod.add_css_class("msg-assistant-model")
            header_row.append(lbl_mod)

        hora_str = datetime.now().strftime("%H:%M")
        lbl_hora = Gtk.Label(label=hora_str)
        lbl_hora.set_opacity(0.5)
        lbl_hora.add_css_class("caption")
        lbl_hora.set_hexpand(True)
        lbl_hora.set_halign(Gtk.Align.END)
        header_row.append(lbl_hora)

        card.append(header_row)

        # Pílula Dinâmica de Status / Ações
        pill_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        pill_box.add_css_class("status-pill")
        pill_box.set_halign(Gtk.Align.START)
        pill_ico = Gtk.Image.new_from_icon_name("system-run-symbolic")
        pill_lbl = Gtk.Label(label=_t("✦ Pensando na resposta..."))
        pill_box.append(pill_ico)
        pill_box.append(pill_lbl)
        card.append(pill_box)

        # Corpo da resposta (Gtk.TextView expansivo)
        tv = Gtk.TextView()
        tv.set_editable(False)
        tv.set_cursor_visible(False)
        tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        tv.set_hexpand(True)
        tv.add_css_class("msg-body")
        tv_buf = tv.get_buffer()
        tv_buf.set_text("")
        card.append(tv)

        # Barra inferior de ações
        act_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        act_row.add_css_class("msg-action-bar")
        btn_copiar = Gtk.Button(icon_name="edit-copy-symbolic", label=_t("Copiar resposta"))
        btn_copiar.add_css_class("flat")
        btn_copiar.add_css_class("btn-copiar")
        btn_copiar.set_halign(Gtk.Align.START)
        btn_copiar.connect("clicked", lambda b: self._copiar_buffer(tv_buf, b))
        act_row.append(btn_copiar)
        card.append(act_row)

        self.box_mensagens.append(card)

        self.ativo_assistente_view = tv
        self.ativo_assistente_buf = tv_buf
        self.ativo_status_box = pill_box
        self.ativo_status_icon = pill_ico
        self.ativo_status_lbl = pill_lbl
        self._scroll_para_fim()

    def _adicionar_aviso_handover(self, nome_antigo, nome_proximo):
        box_linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box_linha.set_halign(Gtk.Align.CENTER)

        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        card.add_css_class("msg-handover")

        icon = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
        lbl = Gtk.Label(
            label=f"⚡ {_t('Limite atingido no')} {nome_antigo} · {_t('Continuando conversa com')} {nome_proximo}..."
        )
        card.append(icon)
        card.append(lbl)

        box_linha.append(card)
        self.box_mensagens.append(box_linha)
        self._scroll_para_fim()

    def _adicionar_sistema(self, texto):
        box_linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box_linha.set_halign(Gtk.Align.CENTER)

        card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        card.add_css_class("dim-label")
        card.set_margin_top(4)
        card.set_margin_bottom(4)

        lbl = Gtk.Label(label=texto)
        card.append(lbl)

        box_linha.append(card)
        self.box_mensagens.append(box_linha)
        self._scroll_para_fim()

    def _copiar_buffer(self, buf, btn):
        start, end = buf.get_bounds()
        texto = buf.get_text(start, end, True)
        if texto:
            cb = Gdk.Display.get_default().get_clipboard()
            cb.set(texto)
            btn.set_label(_t("Copiado!"))
            btn.set_icon_name("emblem-ok-symbolic")
            GLib.timeout_add_seconds(2, lambda: (btn.set_label(_t("Copiar resposta")), btn.set_icon_name("edit-copy-symbolic")))

    def _scroll_para_fim(self):
        GLib.idle_add(self._do_scroll)

    def _do_scroll(self):
        adj = self.scroller.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)

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


def main():
    app = App()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
