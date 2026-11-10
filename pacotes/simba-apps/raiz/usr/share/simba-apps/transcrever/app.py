#!/usr/bin/env python3
"""Transcrever — interface GTK4/libadwaita para transcrever vídeos e áudios com Whisper, um de cada vez.

A interface roda no Python do sistema (PyGObject); a transcrição roda em worker.py, no venv do faster-whisper,
que conversa com a interface por linhas JSON no stdout.
"""
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import gi
import sys as _sys, os as _os  # noqa: E401
_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))
from simba_i18n import t as _t, DECIMAL as _DEC  # noqa: E402  (traduções: /usr/share/simba-apps/idiomas)

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

APP_ID = "com.simba.Transcrever"
BASE = Path(__file__).resolve().parent
WORKER = BASE / "worker.py"
PYTHON = Path.home() / ".local/share/whisper-venv/bin/python"
CONFIG = Path(GLib.get_user_config_dir()) / "transcrever" / "config.json"
LOG = Path(GLib.get_user_cache_dir()) / "transcrever" / "worker.log"
EXTENSOES = {".mp4", ".mkv", ".mov", ".webm", ".avi", ".m4v", ".mp3", ".m4a", ".wav", ".ogg", ".opus", ".flac", ".aac"}

CSS = """
.linha { padding: 14px 16px; }
.linha progressbar trough, .linha progressbar progress { min-height: 6px; border-radius: 3px; }
.porcentagem { font-feature-settings: "tnum"; font-weight: 700; min-width: 3.5em; }
.texto-vivo { padding: 16px 18px; line-height: 1.5; }
actionbar > revealer > box { padding: 8px 14px; }
"""


def ts(s: float) -> str:
    s = int(s)
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def humano(s: float) -> str:
    s = int(s)
    if s < 60:
        return f"{s} s"
    h, m = s // 3600, s % 3600 // 60
    return _t("%1 h %2 min", h, format(m, "02d")) if h else f"{m} min"


def duracao(path: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=20,
        ).stdout
        return float(out)
    except (ValueError, subprocess.SubprocessError):
        return 0.0


def carregar_config() -> dict:
    try:
        return json.loads(CONFIG.read_text())
    except (OSError, ValueError):
        return {}


def salvar_config(cfg: dict) -> None:
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))


class Item:
    """Um arquivo na fila e a linha que o representa."""

    def __init__(self, path: Path):
        self.path = path
        self.destino = path.parent / _t("Transcrições") / f"{path.stem}.txt"
        self.parcial = self.destino.with_suffix(".parcial")
        self.total = duracao(path)
        self.pos = 0.0
        self.estado = "fila"  # fila · preparando · rodando · pausado · concluido · erro
        self.detalhe = ""
        self.t_ini = None
        self.pos_ini = 0.0
        self.gasto = 0.0
        if self.destino.exists():
            self.estado, self.pos = "concluido", self.total
            self.detalhe = _t("Já transcrito")
        elif self.parcial.exists():
            self.pos = self._pos_parcial()
            self.estado = "pausado"

    def _pos_parcial(self) -> float:
        try:
            texto = self.parcial.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return 0.0
        marcas = [l for l in texto.splitlines() if l.startswith("[") and l[9:10] == "]"]
        if not marcas:
            return 0.0
        h, m, s = map(int, marcas[-1][1:9].split(":"))
        return h * 3600 + m * 60 + s

    @property
    def fracao(self) -> float:
        return min(1.0, self.pos / self.total) if self.total else 0.0


class LinhaArquivo(Gtk.ListBoxRow):
    def __init__(self, item: Item, janela: _t("Janela")):
        super().__init__(activatable=False, selectable=False)
        self.item, self.janela = item, janela

        caixa = Gtk.Box(spacing=14, css_classes=["linha"])
        self.icone = Gtk.Image(pixel_size=24, valign=Gtk.Align.CENTER)
        caixa.append(self.icone)

        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True, valign=Gtk.Align.CENTER)
        self.titulo = Gtk.Label(label=item.path.name, xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE,
                                css_classes=["heading"])
        self.subtitulo = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END, css_classes=["dim-label", "caption"])
        self.barra = Gtk.ProgressBar(margin_top=6)
        textos.append(self.titulo)
        textos.append(self.subtitulo)
        textos.append(self.barra)
        caixa.append(textos)

        self.porcento = Gtk.Label(css_classes=["porcentagem", "title-4"], xalign=1, valign=Gtk.Align.CENTER)
        caixa.append(self.porcento)

        self.botoes = Gtk.Box(spacing=6, valign=Gtk.Align.CENTER)
        self.b_abrir = Gtk.Button(icon_name="text-x-generic-symbolic", tooltip_text=_t("Abrir transcrição"),
                                  css_classes=["flat", "circular"])
        self.b_abrir.connect("clicked", lambda *_: self.janela.abrir_arquivo(self.item.destino))
        self.b_pasta = Gtk.Button(icon_name="folder-symbolic", tooltip_text=_t("Mostrar na pasta"),
                                  css_classes=["flat", "circular"])
        self.b_pasta.connect("clicked", lambda *_: self.janela.mostrar_na_pasta(self.item.destino))
        self.b_remover = Gtk.Button(icon_name="window-close-symbolic", tooltip_text=_t("Tirar da lista"),
                                    css_classes=["flat", "circular"])
        self.b_remover.connect("clicked", lambda *_: self.janela.remover(self))
        for b in (self.b_abrir, self.b_pasta, self.b_remover):
            self.botoes.append(b)
        caixa.append(self.botoes)
        self.set_child(caixa)
        self.atualizar()

    def atualizar(self) -> None:
        it = self.item
        icones = {
            "fila": "document-open-recent-symbolic", "preparando": "process-working-symbolic",
            "rodando": "media-record-symbolic", "pausado": "media-playback-pause-symbolic",
            "concluido": "object-select-symbolic", "erro": "dialog-warning-symbolic",
        }
        self.icone.set_from_icon_name(icones[it.estado])
        for c in ("success", "error", "accent", "dim-label"):
            self.icone.remove_css_class(c)
        self.icone.add_css_class({"concluido": "success", "erro": "error", "rodando": "accent"}.get(it.estado, "dim-label"))

        total = ts(it.total) if it.total else _t("duração desconhecida")
        if it.estado == "fila":
            sub = _t("Na fila · %1", total)
        elif it.estado == "preparando":
            sub = it.detalhe or _t("Preparando…")
        elif it.estado == "rodando":
            sub = f"{ts(it.pos)} de {total}"
            if it.t_ini and it.pos - it.pos_ini > 30:
                dec = time.monotonic() - it.t_ini
                vel = (it.pos - it.pos_ini) / dec
                sub += f" · faltam ~{humano((it.total - it.pos) / vel)} · {vel:.1f}×".replace(".", _DEC)
            else:
                sub += _t(" · calculando tempo restante…")
        elif it.estado == "pausado":
            sub = _t("Pausado em %1 de %2 · continua de onde parou", ts(it.pos), total) if it.pos else _t("Pausado · %1", total)
        elif it.estado == "concluido":
            sub = it.detalhe or _t("Concluído em %1", humano(it.gasto))
        else:
            sub = it.detalhe or _t("Erro")
        self.subtitulo.set_label(sub)
        self.subtitulo.set_tooltip_text(sub)

        if it.estado == "preparando":
            self.barra.pulse()
        else:
            self.barra.set_fraction(it.fracao)
        self.barra.set_visible(it.estado != "fila" or it.pos > 0)
        self.porcento.set_label(f"{int(it.fracao * 100)}%" if it.estado != "fila" or it.pos else "")

        pronto = it.estado == "concluido"
        self.b_abrir.set_visible(pronto)
        self.b_pasta.set_visible(pronto)
        self.b_remover.set_visible(it.estado not in ("rodando", "preparando"))


class Janela(Adw.ApplicationWindow):
    def __init__(self, app: _t("App")):
        super().__init__(application=app, title=_t("Transcrever"), default_width=820, default_height=700)
        self.app = app
        self.linhas: list[LinhaArquivo] = []
        self.atual: LinhaArquivo | None = None
        self.proc: Gio.Subprocess | None = None
        self.parando = False
        self.fechar_depois = False
        self.cfg = carregar_config()
        self.inibicao = 0

        self.toasts = Adw.ToastOverlay()
        vista = Adw.ToolbarView()
        self.toasts.set_child(vista)
        self.set_content(self.toasts)

        cabecalho = Adw.HeaderBar()
        cabecalho.set_title_widget(Adw.WindowTitle(title=_t("Transcrever"), subtitle=_t("Whisper large-v3-turbo · 100% local")))
        b_add = Gtk.Button(child=Adw.ButtonContent(icon_name="list-add-symbolic", label=_t("Adicionar")),
                           tooltip_text=_t("Adicionar vídeos ou áudios"))
        b_add.connect("clicked", lambda *_: self.escolher_arquivos())
        cabecalho.pack_start(b_add)

        menu = Gio.Menu()
        qual = Gio.Menu()
        qual.append(_t("Qualidade máxima (recomendado)"), "win.qualidade::maxima")
        qual.append(_t("Rápida (≈1,5× mais veloz)"), "win.qualidade::rapida")
        menu.append_section(_t("Qualidade"), qual)
        outros = Gio.Menu()
        outros.append(_t("Limpar concluídos"), "win.limpar")
        outros.append(_t("Sobre o Transcrever"), "win.sobre")
        menu.append_section(None, outros)
        cabecalho.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu, tooltip_text=_t("Menu")))
        vista.add_top_bar(cabecalho)

        acao_q = Gio.SimpleAction.new_stateful("qualidade", GLib.VariantType.new("s"),
                                                GLib.Variant("s", self.cfg.get("qualidade", "maxima")))
        acao_q.connect("change-state", self._mudar_qualidade)
        self.add_action(acao_q)
        for nome, fn in (("limpar", self.limpar_concluidos), ("sobre", self.sobre), ("adicionar", self.escolher_arquivos)):
            a = Gio.SimpleAction.new(nome, None)
            a.connect("activate", lambda *_, f=fn: f())
            self.add_action(a)

        # Estado vazio
        self.pilha = Gtk.Stack(transition_type=Gtk.StackTransitionType.CROSSFADE)
        vazio = Adw.StatusPage(
            icon_name=APP_ID, title=_t("Transcreva suas aulas"),
            description=_t("Selecione ou arraste vídeos e áudios para cá.\n"
                        "Eles são transcritos um de cada vez, e nada sai do seu computador."),
        )
        b_sel = Gtk.Button(label=_t("Selecionar arquivos"), halign=Gtk.Align.CENTER, css_classes=["pill", "suggested-action"])
        b_sel.connect("clicked", lambda *_: self.escolher_arquivos())
        vazio.set_child(b_sel)
        self.pilha.add_named(vazio, "vazio")

        # Lista + texto ao vivo
        conteudo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24, margin_top=24, margin_bottom=24,
                           margin_start=16, margin_end=16)
        self.lista = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["boxed-list"])
        conteudo.append(self.lista)

        self.grupo_vivo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, visible=False)
        cab_vivo = Gtk.Box(spacing=8)
        self.titulo_vivo = Gtk.Label(label=_t("Texto ao vivo"), xalign=0, hexpand=True, css_classes=["heading"])
        cab_vivo.append(self.titulo_vivo)
        self.grupo_vivo.append(cab_vivo)
        self.texto_vivo = Gtk.Label(xalign=0, yalign=0, wrap=True, selectable=True, css_classes=["texto-vivo"],
                                    wrap_mode=Pango.WrapMode.WORD_CHAR)
        cartao = Gtk.Frame(css_classes=["card"], child=self.texto_vivo)
        self.grupo_vivo.append(cartao)
        conteudo.append(self.grupo_vivo)

        self.rolagem = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True,
                                          child=Adw.Clamp(maximum_size=820, child=conteudo))
        self.pilha.add_named(self.rolagem, "lista")
        vista.set_content(self.pilha)

        # Barra inferior
        barra = Gtk.ActionBar()
        self.resumo = Gtk.Label(css_classes=["dim-label"])
        barra.pack_start(self.resumo)
        self.b_principal = Gtk.Button(css_classes=["pill", "suggested-action"])
        self.b_principal.connect("clicked", lambda *_: self.alternar())
        barra.pack_end(self.b_principal)
        self.barra_inferior = barra
        vista.add_bottom_bar(barra)

        alvo = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        alvo.connect("drop", self._soltou)
        self.add_controller(alvo)

        self.connect("close-request", self._ao_fechar)
        GLib.timeout_add(500, self._tique)
        self.atualizar_geral()

    # ---------- arquivos ----------
    def escolher_arquivos(self) -> None:
        filtro = Gtk.FileFilter(name=_t("Vídeos e áudios"))
        filtro.add_mime_type("video/*")
        filtro.add_mime_type("audio/*")
        filtros = Gio.ListStore.new(Gtk.FileFilter)
        filtros.append(filtro)
        dlg = Gtk.FileDialog(title=_t("Escolha os vídeos para transcrever"), filters=filtros, default_filter=filtro)
        pasta = self.cfg.get("ultima_pasta")
        if pasta and Path(pasta).is_dir():
            dlg.set_initial_folder(Gio.File.new_for_path(pasta))

        def pronto(d, res):
            try:
                arquivos = d.open_multiple_finish(res)
            except GLib.Error:
                return
            self.adicionar([arquivos.get_item(i).get_path() for i in range(arquivos.get_n_items())])

        dlg.open_multiple(self, None, pronto)

    def _soltou(self, _alvo, valor, *_):
        self.adicionar([f.get_path() for f in valor.get_files()])
        return True

    def adicionar(self, caminhos) -> None:
        novos = 0
        ja = {l.item.path for l in self.linhas}
        for c in caminhos:
            if not c:
                continue
            p = Path(c).resolve()
            if p.is_dir():
                self.adicionar(sorted(str(x) for x in p.iterdir() if x.suffix.lower() in EXTENSOES))
                continue
            if p in ja or not p.is_file():
                continue
            linha = LinhaArquivo(Item(p), self)
            self.linhas.append(linha)
            self.lista.append(linha)
            ja.add(p)
            novos += 1
            self.cfg["ultima_pasta"] = str(p.parent)
        if novos:
            salvar_config(self.cfg)
            self.toasts.add_toast(Adw.Toast(title=_t("%1 arquivo(s) adicionado(s)", novos), timeout=2))
            if self.proc is None and not self.cfg.get("nao_iniciar_sozinho"):
                self.iniciar()
        self.atualizar_geral()

    def remover(self, linha: LinhaArquivo) -> None:
        self.linhas.remove(linha)
        self.lista.remove(linha)
        self.atualizar_geral()

    def limpar_concluidos(self) -> None:
        for l in [l for l in self.linhas if l.item.estado == "concluido"]:
            self.remover(l)

    def abrir_arquivo(self, path: Path) -> None:
        Gtk.FileLauncher(file=Gio.File.new_for_path(str(path))).launch(self, None, None)

    def mostrar_na_pasta(self, path: Path) -> None:
        Gtk.FileLauncher(file=Gio.File.new_for_path(str(path))).open_containing_folder(self, None, None)

    # ---------- fila ----------
    def pendentes(self):
        return [l for l in self.linhas if l.item.estado in ("fila", "pausado", "erro")]

    def alternar(self) -> None:
        if self.proc:
            self.pausar()
        else:
            for l in self.linhas:  # "Tentar de novo" também reenfileira os que deram erro
                if l.item.estado == "erro":
                    l.item.estado = "fila"
                    l.atualizar()
            self.iniciar()

    def iniciar(self) -> None:
        prox = next((l for l in self.linhas if l.item.estado in ("fila", "pausado")), None)
        if prox is None:
            self.atualizar_geral()
            return
        it = prox.item
        it.estado, it.detalhe, it.t_ini = "preparando", _t("Preparando…"), None
        self.atual, self.parando = prox, False
        args = [str(PYTHON), str(WORKER), str(it.path)]
        if self.cfg.get("qualidade") == "rapida":
            args.append("--rapido")
        LOG.parent.mkdir(parents=True, exist_ok=True)
        lanc = Gio.SubprocessLauncher.new(Gio.SubprocessFlags.STDOUT_PIPE)
        lanc.set_stderr_file_path(str(LOG))
        self.proc = lanc.spawnv(args)
        self._ler(Gio.DataInputStream.new(self.proc.get_stdout_pipe()), prox)
        self.texto_vivo.set_label("")
        self.titulo_vivo.set_label(_t("Texto ao vivo — %1", it.path.stem))
        self._inibir(True)
        prox.atualizar()
        self.atualizar_geral()

    def pausar(self) -> None:
        if self.proc:
            self.parando = True
            self.proc.send_signal(signal.SIGTERM)

    def _ler(self, stream: Gio.DataInputStream, linha: LinhaArquivo) -> None:
        def chegou(s, res):
            try:
                texto, _ = s.read_line_finish_utf8(res)
            except GLib.Error:
                texto = None
            if texto is None:
                self.proc.wait_async(None, lambda p, r: self._terminou(p, r, linha))
                return
            try:
                self._evento(linha, json.loads(texto))
            except ValueError:
                pass
            s.read_line_async(GLib.PRIORITY_DEFAULT, None, chegou)

        stream.read_line_async(GLib.PRIORITY_DEFAULT, None, chegou)

    def _evento(self, linha: LinhaArquivo, e: dict) -> None:
        it, ev = linha.item, e["ev"]
        if ev == "preparando":
            it.detalhe = _t("Lendo o arquivo…")
        elif ev == "modelo":
            it.detalhe = _t("Carregando o modelo Whisper…")
        elif ev == "audio":
            it.detalhe = _t("Extraindo o áudio do vídeo…")
        elif ev == "transcrevendo":
            it.estado, it.t_ini, it.pos_ini = "rodando", time.monotonic(), e["pos"]
        elif ev == "progresso":
            it.total = e.get("total") or it.total
            it.pos = e["pos"]
            if e.get("texto"):
                self._acrescentar_texto(e["texto"])
        elif ev == "concluido":
            it.estado, it.pos = "concluido", it.total
            it.gasto = e.get("segundos", 0)
            it.detalhe = _t("Já transcrito") if e.get("existente") else ""
        elif ev == "erro":
            it.estado, it.detalhe = "erro", e.get("mensagem", _t("Erro"))
        linha.atualizar()

    def _acrescentar_texto(self, paragrafo: str) -> None:
        atuais = [p for p in self.texto_vivo.get_label().split("\n\n") if p]
        atuais.append(paragrafo)
        self.texto_vivo.set_label("\n\n".join(atuais[-4:]))
        self.grupo_vivo.set_visible(True)

    def _terminou(self, proc, res, linha: LinhaArquivo) -> None:
        try:
            proc.wait_finish(res)
        except GLib.Error:
            pass
        it = linha.item
        if it.estado != "concluido" and it.estado != "erro":
            if self.parando:
                it.estado = "pausado"
            else:
                it.estado = "erro"
                it.detalhe = _t("O processo parou inesperadamente (veja %1)", LOG)
        elif it.estado == "concluido" and not it.detalhe:
            self._notificar(f"{it.path.name} transcrito", _t("Pronto em %1.", humano(it.gasto)))
        self.proc, self.atual = None, None
        self._inibir(False)
        linha.atualizar()
        if self.fechar_depois:
            self.destroy()
            return
        if not self.parando and any(l.item.estado == "fila" for l in self.linhas):
            self.iniciar()
        elif not self.parando and not self.pendentes() and self.linhas:
            self._notificar(_t("Transcrições concluídas"), _t("Todos os arquivos da lista foram transcritos."))
        self.atualizar_geral()

    def _tique(self) -> bool:
        if self.atual:
            self.atual.atualizar()
        return True

    def _inibir(self, ligar: bool) -> None:
        if ligar and not self.inibicao:
            self.inibicao = self.app.inhibit(self, Gtk.ApplicationInhibitFlags.SUSPEND | Gtk.ApplicationInhibitFlags.IDLE,
                                             _t("Transcrevendo"))
        elif not ligar and self.inibicao:
            self.app.uninhibit(self.inibicao)
            self.inibicao = 0

    def _notificar(self, titulo: str, corpo: str) -> None:
        if self.is_active():
            self.toasts.add_toast(Adw.Toast(title=titulo, timeout=4))
            return
        n = Gio.Notification.new(titulo)
        n.set_body(corpo)
        self.app.send_notification(None, n)

    def atualizar_geral(self) -> None:
        self.pilha.set_visible_child_name("lista" if self.linhas else "vazio")
        self.barra_inferior.set_revealed(bool(self.linhas))
        feitos = sum(l.item.estado == "concluido" for l in self.linhas)
        n = len(self.linhas)
        self.resumo.set_label(_t("%1 de %2 concluído", feitos, n) + ("s" if n != 1 else ""))
        b = self.b_principal
        if self.proc:
            b.set_child(Adw.ButtonContent(icon_name="media-playback-pause-symbolic", label=_t("Pausar")))
            b.remove_css_class("suggested-action")
            b.set_sensitive(True)
        else:
            b.add_css_class("suggested-action")
            pend = self.pendentes()
            retomar = any(l.item.estado == "pausado" for l in pend)
            erro = any(l.item.estado == "erro" for l in pend)
            rotulo = _t("Continuar") if retomar else _t("Tentar de novo") if erro and len(pend) == sum(
                l.item.estado == "erro" for l in pend) else _t("Iniciar")
            b.set_child(Adw.ButtonContent(icon_name="media-playback-start-symbolic", label=rotulo))
            b.set_sensitive(bool(pend))

    # ---------- outros ----------
    def _mudar_qualidade(self, acao, valor) -> None:
        acao.set_state(valor)
        self.cfg["qualidade"] = valor.get_string()
        salvar_config(self.cfg)
        if self.proc:
            self.toasts.add_toast(Adw.Toast(title=_t("A nova qualidade vale a partir do próximo arquivo"), timeout=3))

    def sobre(self) -> None:
        Adw.AboutDialog(
            application_name=_t("Transcrever"), application_icon=APP_ID, version="1.0", developer_name=_t("Renan"),
            comments=_t("Transcreve vídeos e áudios em português com o Whisper large-v3-turbo "
                     "(faster-whisper), localmente. As transcrições ficam na pasta “Transcrições”, "
                     "ao lado de cada vídeo, prontas para o NotebookLM."),
        ).present(self)

    def _ao_fechar(self, *_):
        if not self.proc:
            return False
        dlg = Adw.AlertDialog(
            heading=_t("Transcrição em andamento"),
            body=_t("Se você fechar agora, a transcrição é pausada. Ao abrir de novo e adicionar o mesmo arquivo, "
                 "ela continua de onde parou."),
        )
        dlg.add_response("cancelar", _t("Continuar transcrevendo"))
        dlg.add_response("fechar", _t("Pausar e fechar"))
        dlg.set_response_appearance("fechar", Adw.ResponseAppearance.DESTRUCTIVE)
        dlg.set_default_response("cancelar")

        def resposta(_d, r):
            if r == "fechar":
                self.fechar_depois = True
                self.pausar()

        dlg.connect("response", resposta)
        dlg.present(self)
        return True


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.janela = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        css = Gtk.CssProvider()
        css.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        sair = Gio.SimpleAction.new("sair", None)
        sair.connect("activate", lambda *_: self.janela and self.janela.close())
        self.add_action(sair)
        self.set_accels_for_action("app.sair", ["<Control>q"])
        self.set_accels_for_action("win.adicionar", ["<Control>o"])

    def _janela(self) -> Janela:
        if self.janela is None:
            self.janela = Janela(self)
        return self.janela

    def do_activate(self):
        self._janela().present()

    def do_open(self, files, _n, _hint):
        j = self._janela()
        j.present()
        j.adicionar([f.get_path() for f in files])


if __name__ == "__main__":
    sys.exit(App().run(sys.argv))
