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

ANSI_CSI = re.compile(r"\x1b\[([0-9;?]*)([a-zA-Z])")
ANSI_OSC = re.compile(r"\x1b\][^\x07\x1b]*(\x07|\x1b\\)")
ANSI_OTHER = re.compile(r"\x1b[()][0-9A-B]|\x1b[=>78]")


class TerminalCleaner:
    """Processa saídas de terminal VT100/ANSI, tratando spinners, cursores e rewrites."""
    def __init__(self):
        self._lock = threading.Lock()
        self.linhas = []
        self.atual = ""
        self.resto = ""

    def feed(self, texto: str):
        texto = self.resto + texto
        self.resto = ""

        # Preserva sequência de escape incompleta que tenha sido cortada no final do buffer
        m = re.search(r"\x1b(\[[0-9;?]*[ -/]?)?$", texto)
        if m:
            self.resto = m.group(0)
            texto = texto[:m.start()]

        texto = ANSI_OSC.sub("", texto)
        texto = ANSI_OTHER.sub("", texto)

        with self._lock:
            i = 0
            n = len(texto)
            while i < n:
                if texto[i:i+2] == "\x1b[":
                    m = ANSI_CSI.match(texto, i)
                    if m:
                        args, cmd = m.group(1), m.group(2)
                        if cmd == "K":
                            self.atual = ""
                        elif cmd == "A":
                            count = int(args) if args.isdigit() else 1
                            for _ in range(count):
                                if self.linhas:
                                    self.atual = self.linhas.pop()
                        elif cmd == "D":
                            count = int(args) if args.isdigit() else 1
                            self.atual = self.atual[:-count]
                        elif cmd == "G":
                            self.atual = ""
                        i = m.end()
                        continue
                ch = texto[i]
                if ch == "\r":
                    self.atual = ""
                elif ch == "\n":
                    self.linhas.append(self.atual)
                    self.atual = ""
                elif ch == "\b":
                    self.atual = self.atual[:-1]
                else:
                    self.atual += ch
                i += 1

    def get_text(self) -> str:
        with self._lock:
            res = self.linhas + ([self.atual] if self.atual else [])
            return "\n".join(res)


def definir_tamanho_pty(fd, linhas=40, colunas=100):
    try:
        ws = struct.pack("HHHH", linhas, colunas, 0, 0)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, ws)
    except Exception:
        pass


CSS = """
window.background, .chat-window, .chat-bg, .chat-scroll {
  background-color: @window_bg_color;
}
.msg-user {
  background-color: @accent_bg_color;
  color: @accent_fg_color;
  border-radius: 18px 18px 4px 18px;
  padding: 10px 16px;
  margin-left: 80px;
  box-shadow: 0 1px 3px alpha(#000, 0.12);
}
.msg-user label {
  color: @accent_fg_color;
  font-size: 14px;
  line-height: 1.4;
}
.msg-assistant {
  background-color: alpha(@window_fg_color, 0.05);
  border: 1px solid alpha(@window_fg_color, 0.10);
  border-radius: 18px 18px 18px 4px;
  padding: 14px 18px;
  margin-right: 64px;
}
.msg-assistant-header {
  font-size: 13px;
  font-weight: 700;
  opacity: 0.9;
}
.msg-body {
  background-color: transparent;
  font-size: 14px;
  line-height: 1.45;
}
.msg-handover {
  background-color: alpha(@warning_color, 0.15);
  border: 1px solid alpha(@warning_color, 0.40);
  color: @warning_color;
  border-radius: 20px;
  padding: 8px 20px;
  margin: 10px 0;
  font-weight: 600;
  font-size: 13px;
}
.chat-input-card {
  background-color: alpha(@window_fg_color, 0.05);
  border: 1px solid alpha(@window_fg_color, 0.14);
  border-radius: 24px;
  padding: 4px 8px 4px 10px;
}
.chat-input-card:focus-within {
  border-color: @accent_bg_color;
  box-shadow: 0 0 0 1px @accent_bg_color;
}
.btn-copiar {
  font-size: 12px;
  padding: 3px 10px;
  min-height: 28px;
  margin-top: 4px;
}
.dir-pill {
  font-size: 12px;
  opacity: 0.7;
}
"""


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_t("Agentes de IA"))
        self.set_default_size(860, 680)
        self.set_size_request(480, 500)
        self.add_css_class("chat-window")
        self.add_css_class("chat-bg")

        # Estado da sessão
        self.work_dir = HOME / "Work" if (HOME / "Work").is_dir() else HOME
        self.proc = None
        self.mestre_fd = None
        self.agente_atual = None
        self.usados = set()
        self.anterior_passagem = None
        self.historico_tela = bytearray()
        self.inicio_agente = 0.0
        self.ativo_assistente_view = None
        self.ativo_assistente_buf = None
        self.ativo_cleaner = None
        self.atualizacao_pendente = False
        self.ignorar_limite_ate = 0.0

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

        self.box_mensagens = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        self.box_mensagens.set_margin_start(20)
        self.box_mensagens.set_margin_end(20)
        self.box_mensagens.set_margin_top(20)
        self.box_mensagens.set_margin_bottom(20)
        self.scroller.set_child(self.box_mensagens)

        # Banner de Boas-Vindas
        self.status_page = Adw.StatusPage()
        self.status_page.set_icon_name("simba-agente")
        self.status_page.set_title(_t("Agentes de IA"))
        self.status_page.set_description(
            _t("Controle e alterne entre todos os agentes em uma única tela.\n"
               "Se o limite de um acabar, o trabalho continua automaticamente no próximo com todo o contexto.")
        )
        self.box_mensagens.append(self.status_page)

        # Barra Inferior de Entrada
        box_inferior = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box_inferior.set_margin_start(20)
        box_inferior.set_margin_end(20)
        box_inferior.set_margin_bottom(16)
        box_inferior.set_margin_top(6)

        # Card de Entrada
        card_input = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        card_input.add_css_class("chat-input-card")

        scroll_txt = Gtk.ScrolledWindow()
        scroll_txt.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll_txt.set_propagate_natural_height(True)
        scroll_txt.set_min_content_height(36)
        scroll_txt.set_max_content_height(130)
        scroll_txt.set_hexpand(True)
        scroll_txt.set_valign(Gtk.Align.CENTER)

        self.text_input = Gtk.TextView()
        self.text_input.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.text_input.set_accepts_tab(False)
        self.text_input.set_top_margin(6)
        self.text_input.set_bottom_margin(6)
        self.text_input.set_left_margin(8)
        self.text_input.set_right_margin(8)
        self.text_input_buf = self.text_input.get_buffer()
        scroll_txt.set_child(self.text_input)

        # Placeholder com Overlay
        overlay_input = Gtk.Overlay()
        overlay_input.set_hexpand(True)
        overlay_input.set_child(scroll_txt)

        self.lbl_placeholder = Gtk.Label(label=_t("Escreva uma mensagem ou comando... (Enter envia, Shift+Enter quebra)"))
        self.lbl_placeholder.set_halign(Gtk.Align.START)
        self.lbl_placeholder.set_valign(Gtk.Align.CENTER)
        self.lbl_placeholder.set_margin_start(12)
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
            _t("Controle e alterne entre todos os agentes em uma única tela.\n"
               "Se o limite de um acabar, o trabalho continua automaticamente no próximo com todo o contexto.")
        )
        self.box_mensagens.append(self.status_page)
        self.usados.clear()
        self.anterior_passagem = None
        self.agente_atual = None
        self.ativo_assistente_view = None
        self.ativo_assistente_buf = None
        self.ativo_cleaner = None

    def _on_input_text_changed(self, buf):
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

        # Se já existe um processo ativo e aguardando entrada do usuário:
        if self.proc and self.mestre_fd is not None and self.proc.poll() is None:
            self.ativo_cleaner = TerminalCleaner()
            self._adicionar_bolha_assistente(self.agente_atual or "auto")
            self.btn_parar.set_visible(True)
            self.btn_enviar.set_visible(True)
            try:
                os.write(self.mestre_fd, (texto + "\n").encode("utf-8"))
            except OSError:
                pass
            return

        # Caso contrário, inicia nova execução
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
        self.ignorar_limite_ate = time.time() + 2.0
        self.ativo_cleaner = TerminalCleaner()

        # Cria a bolha de resposta do agente
        self._adicionar_bolha_assistente(agente)

        # Prepara comando
        info = M.AGENTES[agente]
        cmd = list(info["cmd"])
        if pedido:
            if info["prompt"]:
                cmd += [x.replace("{p}", pedido) for x in info["prompt"]]
            elif agente == "crush":
                cmd = ["crush", "run", pedido]

        # PTY
        mestre, escravo = pty.openpty()
        definir_tamanho_pty(escravo, 40, 100)
        self.mestre_fd = mestre

        env = dict(os.environ)
        env["AGENTES_ATUAL"] = agente
        env["PYTHONUNBUFFERED"] = "1"
        env["TERM"] = "xterm-256color"
        env["COLUMNS"] = "100"
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
        while self.proc and self.proc.poll() is None:
            try:
                r, _, _ = select.select([mestre], [], [], 0.15)
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
                if self.ativo_cleaner:
                    self.ativo_cleaner.feed(texto)
                    self._agendar_atualizacao_texto()

                # Detecção de limite de uso
                if cfg.get("trocaAutomatica", True) and time.time() >= self.ignorar_limite_ate:
                    if self.ativo_cleaner:
                        texto_recente = self.ativo_cleaner.get_text()[-1200:]
                        if M.detectar_limite(texto_recente):
                            GLib.idle_add(self._executar_troca_transparente, agente, cfg)
                            return

        try:
            os.close(mestre)
        except OSError:
            pass

        GLib.idle_add(self._finalizar_resposta)

    def _agendar_atualizacao_texto(self):
        if not self.atualizacao_pendente:
            self.atualizacao_pendente = True
            GLib.idle_add(self._aplicar_atualizacao_texto)

    def _aplicar_atualizacao_texto(self):
        self.atualizacao_pendente = False
        if self.ativo_assistente_buf and self.ativo_cleaner:
            self.ativo_assistente_buf.set_text(self.ativo_cleaner.get_text())
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
        if self.ativo_assistente_buf and self.ativo_cleaner:
            self.ativo_assistente_buf.set_text(self.ativo_cleaner.get_text())
            self._scroll_para_fim()
        self.btn_parar.set_visible(False)
        self.btn_enviar.set_visible(True)
        self.text_input.grab_focus()

    # ── Construtores de Bolhas no Chat ───────────────────────────────────────
    def _adicionar_bolha_usuario(self, texto):
        box_linha = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box_linha.set_halign(Gtk.Align.END)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        card.add_css_class("msg-user")

        lbl = Gtk.Label(label=texto, wrap=True, selectable=True, xalign=0)
        lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        card.append(lbl)

        box_linha.append(card)
        self.box_mensagens.append(box_linha)
        self._scroll_para_fim()

    def _adicionar_bolha_assistente(self, agente):
        nome = M.AGENTES.get(agente, {}).get("nome", agente)

        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        card.add_css_class("msg-assistant")
        card.set_hexpand(True)
        card.set_margin_end(64)

        # Cabeçalho da mensagem
        header_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        img_icone = Gtk.Image.new_from_icon_name("simba-agente")
        lbl_nome = Gtk.Label(label=nome)
        lbl_nome.add_css_class("msg-assistant-header")
        header_row.append(img_icone)
        header_row.append(lbl_nome)

        hora_str = datetime.now().strftime("%H:%M")
        lbl_hora = Gtk.Label(label=hora_str)
        lbl_hora.set_opacity(0.5)
        lbl_hora.add_css_class("caption")
        lbl_hora.set_hexpand(True)
        lbl_hora.set_halign(Gtk.Align.END)
        header_row.append(lbl_hora)

        card.append(header_row)

        # TextView para a resposta com seleção nativa e context menu de copiar
        tv = Gtk.TextView()
        tv.set_editable(False)
        tv.set_cursor_visible(False)
        tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        tv.set_hexpand(True)
        tv.add_css_class("msg-body")
        tv_buf = tv.get_buffer()

        card.append(tv)

        # Botão inferior para copiar a resposta inteira
        btn_copiar = Gtk.Button(icon_name="edit-copy-symbolic", label=_t("Copiar resposta"))
        btn_copiar.add_css_class("flat")
        btn_copiar.add_css_class("btn-copiar")
        btn_copiar.set_halign(Gtk.Align.START)
        btn_copiar.connect("clicked", lambda b: self._copiar_buffer(tv_buf, b))
        card.append(btn_copiar)

        self.box_mensagens.append(card)

        self.ativo_assistente_view = tv
        self.ativo_assistente_buf = tv_buf
        self.ativo_cleaner = TerminalCleaner()
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
