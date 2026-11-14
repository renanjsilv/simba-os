"""Painel lateral de código (como os Artifacts do Claude e o Canvas do ChatGPT).

Mostra um código ou arquivo ao lado da conversa, com números de linha e realce: a
pessoa abre pelo botão "Abrir ao lado" de um bloco de código, e o agente pelo
`simba-chat mostrar <arquivo>` (o painel acompanha o arquivo enquanto ele muda).
Guarda os últimos documentos abertos numa lista, para voltar a eles.
"""
from pathlib import Path
import subprocess
import sys

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

try:
    gi.require_version("GtkSource", "5")
    from gi.repository import GtkSource  # noqa: E402
except (ImportError, ValueError):
    GtkSource = None

sys.path.insert(0, "/usr/share/simba-apps/idiomas")
from simba_i18n import t as _t  # noqa: E402

MAX_BYTES = 2_000_000
MAX_DOCS = 12
EXTENSOES = {".py": "python3", ".sh": "sh", ".js": "js", ".ts": "typescript", ".json": "json", ".md": "markdown",
             ".html": "html", ".css": "css", ".qml": "qml", ".lua": "lua", ".rs": "rust", ".c": "c", ".h": "c",
             ".cpp": "cpp", ".toml": "toml", ".yaml": "yaml", ".yml": "yaml", ".sql": "sql", ".go": "go",
             ".java": "java", ".xml": "xml", ".diff": "diff", ".patch": "diff", ".ini": "ini", ".conf": "ini"}
APELIDOS = {"python": "python3", "py": "python3", "bash": "sh", "shell": "sh", "zsh": "sh",
            "javascript": "js", "ts": "typescript", "yml": "yaml", "c++": "cpp"}


class PainelCodigo(Gtk.Box):
    def __init__(self, ao_fechar=None, pasta=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("painel-codigo")
        self.ao_fechar = ao_fechar or (lambda: None)
        self.pasta = pasta or (lambda: Path.home())
        self.docs = []          # [{"titulo", "lang", "texto", "arquivo"}]
        self.atual = None
        self.monitor = None

        barra = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        barra.add_css_class("painel-codigo-barra")
        icone = Gtk.Image.new_from_icon_name("text-x-script-symbolic")
        icone.set_pixel_size(18)
        barra.append(icone)
        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        textos.set_hexpand(True)
        self.titulo = Gtk.Label(xalign=0)
        self.titulo.add_css_class("painel-codigo-titulo")
        self.titulo.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        textos.append(self.titulo)
        self.sub = Gtk.Label(xalign=0)
        self.sub.add_css_class("painel-codigo-sub")
        self.sub.set_ellipsize(Pango.EllipsizeMode.START)
        textos.append(self.sub)
        barra.append(textos)

        # documentos anteriores
        self.btn_docs = Gtk.MenuButton(icon_name="view-list-symbolic")
        self.btn_docs.add_css_class("flat")
        self.btn_docs.set_tooltip_text(_t("Documentos abertos"))
        self.pop_docs = Gtk.Popover()
        self.lista_docs = Gtk.ListBox()
        self.lista_docs.set_selection_mode(Gtk.SelectionMode.NONE)
        self.lista_docs.connect("row-activated", self._doc_escolhido)
        self.pop_docs.set_child(self.lista_docs)
        self.pop_docs.connect("show", lambda *_: self._montar_docs())
        self.btn_docs.set_popover(self.pop_docs)
        barra.append(self.btn_docs)

        def botao(icone, dica, acao):
            b = Gtk.Button(icon_name=icone)
            b.add_css_class("flat")
            b.set_tooltip_text(dica)
            b.connect("clicked", lambda _b: acao(b))
            barra.append(b)
            return b
        self.btn_copiar = botao("edit-copy-symbolic", _t("Copiar tudo"), self._copiar)
        self.btn_salvar = botao("document-save-symbolic", _t("Salvar na pasta de trabalho"), self._salvar)
        self.btn_abrir = botao("document-open-symbolic", _t("Abrir no editor"), self._abrir_editor)
        botao("window-close-symbolic", _t("Fechar painel"), lambda _b: self.fechar())
        self.append(barra)

        if GtkSource is not None:
            self.buf = GtkSource.Buffer()
            self.view = GtkSource.View.new_with_buffer(self.buf)
            self.view.set_show_line_numbers(True)
            self.view.set_highlight_current_line(False)
            sm = GtkSource.StyleSchemeManager.get_default()
            esquema = sm.get_scheme("Adwaita-dark")   # igual aos blocos de código da conversa
            Adw.StyleManager.get_default().connect("notify::dark", lambda *_: self._tema())
            if esquema:
                self.buf.set_style_scheme(esquema)
        else:
            self.view = Gtk.TextView()
            self.buf = self.view.get_buffer()
        self.view.set_editable(False)
        self.view.set_monospace(True)
        self.view.set_top_margin(10)
        self.view.set_bottom_margin(10)
        self.view.set_left_margin(8)
        self.view.add_css_class("painel-codigo-view")
        rolagem = Gtk.ScrolledWindow()
        rolagem.set_vexpand(True)
        rolagem.set_child(self.view)
        self.rolagem = rolagem
        self.append(rolagem)

    def _tema(self):
        if GtkSource is None:
            return
        sm = GtkSource.StyleSchemeManager.get_default()
        esquema = sm.get_scheme("Adwaita-dark")
        if esquema:
            self.buf.set_style_scheme(esquema)

    # ── abrir ─────────────────────────────────────────────────────────────────
    def mostrar_codigo(self, texto, lang="", titulo=""):
        doc = {"titulo": titulo or (lang and f"{_t('Código')} {lang}") or _t("Código"),
               "lang": lang or "", "texto": texto, "arquivo": None}
        self._abrir_doc(doc)

    def mostrar_arquivo(self, caminho, linha=None):
        """Abre um arquivo; devolve None se deu certo, ou o texto do erro."""
        p = Path(caminho).expanduser()
        if not p.is_absolute():
            p = Path(self.pasta()) / p
        try:
            if p.stat().st_size > MAX_BYTES:
                return _t("arquivo grande demais para o painel")
            texto = p.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            return str(e)
        existente = next((d for d in self.docs if d.get("arquivo") == str(p)), None)
        doc = existente or {"titulo": p.name, "lang": "", "arquivo": str(p)}
        doc["texto"] = texto
        self._abrir_doc(doc, linha=linha)
        return None

    def _abrir_doc(self, doc, linha=None):
        if doc in self.docs:
            self.docs.remove(doc)
        self.docs.insert(0, doc)
        del self.docs[MAX_DOCS:]
        self.atual = doc
        self.titulo.set_label(doc["titulo"])
        if doc.get("arquivo"):
            self.sub.set_label(doc["arquivo"].replace(str(Path.home()), "~", 1))
        else:
            self.sub.set_label(_t("trecho da conversa") + (f" · {doc['lang']}" if doc.get("lang") else ""))
        self.btn_abrir.set_visible(bool(doc.get("arquivo")))
        self.btn_docs.set_visible(len(self.docs) > 1)
        self._linguagem(doc)
        self.buf.set_text(doc["texto"])
        self._vigiar(doc)
        if linha:
            GLib.idle_add(self._ir_para, int(linha))
        else:
            self.rolagem.get_vadjustment().set_value(0)

    def _linguagem(self, doc):
        if GtkSource is None:
            return
        lm = GtkSource.LanguageManager.get_default()
        lang = None
        if doc.get("arquivo"):
            lang = lm.guess_language(doc["arquivo"], None)
            if lang is None:
                ext = EXTENSOES.get(Path(doc["arquivo"]).suffix.lower())
                lang = lm.get_language(ext) if ext else None
        elif doc.get("lang"):
            nome = doc["lang"].lower()
            lang = lm.get_language(APELIDOS.get(nome, nome))
        self.buf.set_language(lang)

    def _ir_para(self, linha):
        res = self.buf.get_iter_at_line(max(0, linha - 1))
        ok, it = res if isinstance(res, tuple) else (True, res)
        if not ok:
            return False
        self.buf.place_cursor(it)
        self.view.scroll_to_iter(it, 0.2, True, 0, 0.3)
        return False

    # acompanha o arquivo enquanto o agente o altera
    def _vigiar(self, doc):
        if self.monitor is not None:
            self.monitor.cancel()
            self.monitor = None
        if not doc.get("arquivo"):
            return
        try:
            self.monitor = Gio.File.new_for_path(doc["arquivo"]).monitor_file(Gio.FileMonitorFlags.NONE, None)
            self.monitor.set_rate_limit(400)
            self.monitor.connect("changed", self._arquivo_mudou)
        except GLib.Error:
            self.monitor = None

    def _arquivo_mudou(self, _m, _f, _o, evento):
        if evento not in (Gio.FileMonitorEvent.CHANGES_DONE_HINT, Gio.FileMonitorEvent.CREATED,
                          Gio.FileMonitorEvent.CHANGED):
            return
        doc = self.atual
        if not doc or not doc.get("arquivo"):
            return
        try:
            texto = Path(doc["arquivo"]).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return
        if texto != doc.get("texto"):
            adj = self.rolagem.get_vadjustment()
            pos = adj.get_value()
            doc["texto"] = texto
            self.buf.set_text(texto)
            GLib.idle_add(lambda: (adj.set_value(pos), False)[1])

    # ── lista de documentos ─────────────────────────────────────────────────
    def _montar_docs(self):
        f = self.lista_docs.get_first_child()
        while f is not None:
            self.lista_docs.remove(f)
            f = self.lista_docs.get_first_child()
        for d in self.docs:
            linha = Gtk.ListBoxRow()
            linha.doc = d
            lbl = Gtk.Label(label=d["titulo"], xalign=0)
            lbl.set_margin_start(8)
            lbl.set_margin_end(8)
            lbl.set_margin_top(6)
            lbl.set_margin_bottom(6)
            linha.set_child(lbl)
            self.lista_docs.append(linha)

    def _doc_escolhido(self, _l, linha):
        self.pop_docs.popdown()
        doc = linha.doc
        GLib.idle_add(lambda: (self.mostrar_arquivo(doc["arquivo"]) if doc.get("arquivo")
                               else self._abrir_doc(doc), False)[1])

    # ── ações ─────────────────────────────────────────────────────────────────
    def texto(self):
        return self.atual.get("texto", "") if self.atual else ""

    def _feedback(self, b, icone):
        b.set_icon_name("object-select-symbolic")
        GLib.timeout_add_seconds(2, lambda: (b.set_icon_name(icone), False)[1])

    def _copiar(self, b):
        Gdk.Display.get_default().get_clipboard().set(self.texto())
        self._feedback(b, "edit-copy-symbolic")

    def _salvar(self, b):
        if not self.atual:
            return
        dialogo = Gtk.FileDialog(title=_t("Salvar código"))
        nome = Path(self.atual["arquivo"]).name if self.atual.get("arquivo") else "codigo.txt"
        dialogo.set_initial_name(nome)
        dialogo.set_initial_folder(Gio.File.new_for_path(str(self.pasta())))

        def fim(d, res):
            try:
                f = d.save_finish(res)
            except GLib.Error:
                return
            if f is not None:
                Path(f.get_path()).write_text(self.texto(), encoding="utf-8")
                self._feedback(b, "document-save-symbolic")
        dialogo.save(self.get_root(), None, fim)

    def _abrir_editor(self, _b):
        if self.atual and self.atual.get("arquivo"):
            subprocess.Popen(["xdg-open", self.atual["arquivo"]], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def fechar(self):
        if self.monitor is not None:
            self.monitor.cancel()
            self.monitor = None
        self.set_visible(False)
        self.ao_fechar()
