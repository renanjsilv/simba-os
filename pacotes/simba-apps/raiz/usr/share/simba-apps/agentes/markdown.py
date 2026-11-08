"""Markdown das respostas, em blocos separados: texto, código e tabela.

A resposta vira uma coluna de widgets (MensagemView). Enquanto a IA gera, a
mesma coluna é atualizada a cada pedaço novo: os blocos que já estão prontos não
são refeitos; só o último muda. Assim o código aparece como bloco de código (com
cores) desde a primeira linha, e não como texto corrido até o fim da resposta.
"""
from html import escape
from pathlib import Path
import re
import shlex
import subprocess
import sys
import uuid

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, GLib, Gtk, Pango  # noqa: E402

sys.path.insert(0, "/usr/share/simba-apps/idiomas")
from simba_i18n import t as _t  # noqa: E402

try:
    gi.require_version("GtkSource", "5")
    from gi.repository import GtkSource  # noqa: E402
    HAS_GTKSOURCE = True
except Exception:
    HAS_GTKSOURCE = False

LANG_ALIASES = {
    "py": "python3", "python": "python3", "python2": "python",
    "bash": "sh", "zsh": "sh", "shell": "sh", "sh": "sh", "console": "sh", "shellsession": "sh",
    "javascript": "js", "js": "js", "jsx": "js",
    "typescript": "typescript", "ts": "typescript", "tsx": "typescript",
    "yaml": "yaml", "yml": "yaml",
    "html": "html", "css": "css", "scss": "css",
    "json": "json", "jsonc": "json",
    "lua": "lua", "rust": "rust", "rs": "rust",
    "c": "c", "cpp": "cpp", "c++": "cpp", "h": "c", "hpp": "cpp",
    "md": "markdown", "markdown": "markdown",
    "sql": "sql", "toml": "toml", "ini": "ini", "xml": "xml", "qml": "js",
    "dockerfile": "dockerfile", "docker": "dockerfile", "diff": "diff", "patch": "diff",
}
EXECUTAVEIS = ("bash", "sh", "zsh", "shell", "python", "py", "python3")

# Sequências ANSI (cores, cursor, limpeza de linha) que alguns CLIs ainda emitem
# mesmo no modo de impressão. Elas não podem chegar ao texto do chat.
ANSI_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\)|[@-_])")
CERCA = re.compile(r"^\s{0,3}(`{3,}|~{3,})\s*([\w+#.-]*)")
LINHA_TABELA = re.compile(r"^\s*\|.*\|\s*$")
SEPARADOR_TABELA = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
INLINE = re.compile(
    r"(\*\*[^*\n]+\*\*|__[^_\n]+__|`[^`\n]+`|~~[^~\n]+~~|\*[^*\n]+\*|(?<!\w)_[^_\n]+_(?!\w)"
    r"|\[[^\]\n]+\]\([^)\n]+\)|https?://[^\s<>()\]]+[^\s<>()\].,;:!?'\"])"
)


# ── Análise (sem GTK, testável) ─────────────────────────────────────────────
def parse_blocos(texto):
    """Divide o markdown em blocos {tipo: texto|codigo|tabela, conteudo, lang, aberto}.

    Um bloco de código ainda sem a cerca de fechamento (resposta sendo gerada)
    vem com aberto=True e já é tratado como código.
    """
    texto = ANSI_RE.sub("", texto.replace("\r\n", "\n").replace("\r", "\n"))
    linhas = texto.split("\n")
    blocos, texto_atual = [], []

    def fecha_texto():
        conteudo = "\n".join(texto_atual).strip("\n")
        texto_atual.clear()
        if conteudo.strip():
            blocos.append({"tipo": "texto", "conteudo": conteudo, "lang": "", "aberto": False})

    i = 0
    while i < len(linhas):
        linha = linhas[i]
        m = CERCA.match(linha)
        if m:
            fecha_texto()
            cerca, lang = m.group(1), m.group(2).lower()
            corpo, i, aberto = [], i + 1, True
            while i < len(linhas):
                if linhas[i].strip().startswith(cerca[0] * len(cerca)) and not linhas[i].strip().strip(cerca[0]):
                    aberto = False
                    i += 1
                    break
                corpo.append(linhas[i])
                i += 1
            blocos.append({"tipo": "codigo", "conteudo": "\n".join(corpo), "lang": lang, "aberto": aberto})
            continue
        if LINHA_TABELA.match(linha) and i + 1 < len(linhas) and SEPARADOR_TABELA.match(linhas[i + 1]):
            fecha_texto()
            tabela = [linha]
            i += 1
            while i < len(linhas) and LINHA_TABELA.match(linhas[i]):
                tabela.append(linhas[i])
                i += 1
            blocos.append({"tipo": "tabela", "conteudo": "\n".join(tabela), "lang": "", "aberto": False})
            continue
        texto_atual.append(linha)
        i += 1
    fecha_texto()
    return blocos


def _celulas(linha):
    s = linha.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", s)]


def parse_tabela(conteudo):
    """(cabeçalho, alinhamentos, linhas) de uma tabela markdown."""
    linhas = conteudo.split("\n")
    cab = _celulas(linhas[0])
    alinh = []
    for c in _celulas(linhas[1]) if len(linhas) > 1 else []:
        c = c.strip()
        alinh.append("centro" if c.startswith(":") and c.endswith(":") else "direita" if c.endswith(":") else "esquerda")
    corpo = [_celulas(l) for l in linhas[2:] if l.strip()]
    return cab, alinh, corpo


def inline_para_markup(texto):
    """Markdown de uma linha → markup do Pango (células de tabela)."""
    saida, pos = [], 0
    for m in INLINE.finditer(texto):
        saida.append(escape(texto[pos:m.start()], quote=False))
        tok = m.group(0)
        if tok.startswith(("**", "__")):
            saida.append(f"<b>{escape(tok[2:-2], quote=False)}</b>")
        elif tok.startswith("`"):
            saida.append(f"<tt>{escape(tok[1:-1], quote=False)}</tt>")
        elif tok.startswith("~~"):
            saida.append(f"<s>{escape(tok[2:-2], quote=False)}</s>")
        elif tok.startswith(("*", "_")):
            saida.append(f"<i>{escape(tok[1:-1], quote=False)}</i>")
        elif tok.startswith("["):
            lk = re.match(r"\[([^\]]+)\]\(([^)]+)\)", tok)
            saida.append(f'<a href="{escape(lk.group(2))}">{escape(lk.group(1), quote=False)}</a>')
        else:
            saida.append(f'<a href="{escape(tok)}">{escape(tok, quote=False)}</a>')
        pos = m.end()
    saida.append(escape(texto[pos:], quote=False))
    return "".join(saida)


def abrir_link(janela, url):
    if url.startswith(("http://", "https://", "mailto:")):
        Gtk.show_uri(janela, url, Gdk.CURRENT_TIME)
        return
    caminho = url[7:] if url.startswith("file://") else url
    if Path(caminho).expanduser().exists():
        subprocess.Popen(["xdg-open", str(Path(caminho).expanduser())], start_new_session=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        Gtk.show_uri(janela, url, Gdk.CURRENT_TIME)


# ── Mensagem em blocos ──────────────────────────────────────────────────────
class MensagemView(Gtk.Box):
    """Corpo de uma resposta: coluna de blocos atualizada de forma incremental."""

    def __init__(self, janela):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.janela = janela
        self.texto = ""
        self.itens = []  # [{"tipo", "lang", "conteudo", "widget"}]
        self.set_hexpand(True)
        self.add_css_class("msg-corpo")

    def definir(self, texto):
        if texto == self.texto:
            return
        self.texto = texto
        try:
            blocos = parse_blocos(texto)
            for i, b in enumerate(blocos):
                if i < len(self.itens):
                    it = self.itens[i]
                    if it["tipo"] == b["tipo"] and (b["tipo"] != "codigo" or it["lang"] == b["lang"]):
                        if it["conteudo"] != b["conteudo"]:
                            self._atualizar(it, b)
                        continue
                    self._remover_de(i)
                self._criar(b)
            self._remover_de(len(blocos))
        except Exception as exc:  # noqa: BLE001 — nunca deixa a resposta sumir
            sys.stderr.write(f"markdown: {exc}\n")
            self._remover_de(0)
            self._criar({"tipo": "texto", "conteudo": texto, "lang": "", "aberto": False}, cru=True)

    def _remover_de(self, i):
        for it in self.itens[i:]:
            self.remove(it["widget"])
        del self.itens[i:]

    def _criar(self, b, cru=False):
        j = self.janela
        if b["tipo"] == "codigo":
            w = j._criar_widget_codigo(b["lang"], b["conteudo"])
        elif b["tipo"] == "tabela":
            w = j._criar_tabela(b["conteudo"])
        else:
            w = j._criar_texto_view()
            if cru:
                w.get_buffer().set_text(b["conteudo"])
            else:
                j._render_texto(w.get_buffer(), b["conteudo"])
        self.append(w)
        self.itens.append({"tipo": b["tipo"], "lang": b["lang"], "conteudo": b["conteudo"], "widget": w})

    def _atualizar(self, it, b):
        w = it["widget"]
        if b["tipo"] == "codigo":
            w.definir_codigo(b["conteudo"])
        elif b["tipo"] == "tabela":
            novo = self.janela._criar_tabela(b["conteudo"])
            self.insert_child_after(novo, w)
            self.remove(w)
            it["widget"] = novo
        else:
            buf = w.get_buffer()
            buf.set_text("")
            self.janela._render_texto(buf, b["conteudo"])
        it["conteudo"] = b["conteudo"]


class MarkdownMixin:
    def _criar_mensagem(self):
        return MensagemView(self)

    # ── texto ────────────────────────────────────────────────────────────────
    def _tags_markdown(self, buf):
        tabela = buf.get_tag_table()

        def tag(nome, **props):
            existente = tabela.lookup(nome)
            if existente:
                return existente
            t = Gtk.TextTag(name=nome)
            for chave, valor in props.items():
                t.set_property(chave.replace("_", "-"), valor)
            tabela.add(t)
            return t

        neutro = Gdk.RGBA()
        neutro.parse("rgba(127,127,127,0.20)")
        cinza = Gdk.RGBA()
        cinza.parse("rgba(127,127,127,0.85)")
        accent = Gdk.RGBA()
        accent.parse("rgba(98,160,234,1)")

        return {
            "base": tag("md-base", pixels_below_lines=3, pixels_inside_wrap=3),
            "bold": tag("md-bold", weight=Pango.Weight.BOLD),
            "italic": tag("md-italic", style=Pango.Style.ITALIC),
            "strike": tag("md-strike", strikethrough=True),
            "code": tag("md-code", family="monospace", scale=0.92, background_rgba=neutro),
            "h1": tag("md-h1", weight=Pango.Weight.BOLD, scale=1.45, pixels_above_lines=10, pixels_below_lines=6),
            "h2": tag("md-h2", weight=Pango.Weight.BOLD, scale=1.25, pixels_above_lines=10, pixels_below_lines=4),
            "h3": tag("md-h3", weight=Pango.Weight.BOLD, scale=1.1, pixels_above_lines=8, pixels_below_lines=3),
            "lista0": tag("md-lista0", left_margin=26, indent=-18, pixels_below_lines=3),
            "lista1": tag("md-lista1", left_margin=50, indent=-18, pixels_below_lines=3),
            "lista2": tag("md-lista2", left_margin=74, indent=-18, pixels_below_lines=3),
            "marcador": tag("md-marcador", foreground_rgba=accent, weight=Pango.Weight.BOLD),
            "quote": tag("md-quote", left_margin=20, foreground_rgba=cinza, style=Pango.Style.ITALIC,
                         pixels_above_lines=2, pixels_below_lines=2),
            "link": tag("md-link", underline=Pango.Underline.SINGLE, foreground_rgba=accent),
            "dim": tag("md-dim", foreground_rgba=cinza),
        }

    def _inserir(self, buf, texto, tags):
        if texto:
            buf.insert_with_tags(buf.get_end_iter(), texto, *tags)

    def _inserir_inline(self, buf, texto, tags, extra=None):
        base = [tags["base"]] + list(extra or [])
        pos = 0
        for m in INLINE.finditer(texto):
            if m.start() > pos:
                self._inserir(buf, texto[pos:m.start()], base)
            tok = m.group(0)
            if tok.startswith(("**", "__")):
                inner = tok[2:-2]
                if "`" in inner:
                    self._inserir_inline(buf, inner, tags, extra=list(extra or []) + [tags["bold"]])
                else:
                    self._inserir(buf, inner, base + [tags["bold"]])
            elif tok.startswith("`"):
                self._inserir(buf, f" {tok[1:-1]} ", base + [tags["code"]])
            elif tok.startswith("~~"):
                self._inserir(buf, tok[2:-2], base + [tags["strike"]])
            elif tok.startswith(("*", "_")):
                self._inserir(buf, tok[1:-1], base + [tags["italic"]])
            else:
                lk = re.match(r"\[([^\]]+)\]\(([^)]+)\)", tok)
                rotulo, url = (lk.group(1), lk.group(2)) if lk else (tok, tok)
                tag_link = Gtk.TextTag(name=f"link-{uuid.uuid4().hex[:8]}")
                tag_link.set_property("underline", Pango.Underline.SINGLE)
                tag_link.set_property("foreground-rgba", tags["link"].get_property("foreground-rgba"))
                tag_link.url = url
                buf.get_tag_table().add(tag_link)
                self._inserir(buf, rotulo, base + [tag_link])
            pos = m.end()
        if pos < len(texto):
            self._inserir(buf, texto[pos:], base)

    def _render_texto(self, buf, texto):
        """Um bloco de texto (sem código nem tabela): títulos, listas, citações, parágrafos."""
        tags = self._tags_markdown(buf)
        primeiro = [True]

        def nova_linha(n=1):
            if not primeiro[0]:
                self._inserir(buf, "\n" * n, [tags["base"]])
            primeiro[0] = False

        paragrafo = []
        anterior = [None]  # tipo da última linha, para o espaçamento

        def flush():
            if not paragrafo:
                return
            p = "\n".join(x.strip() for x in paragrafo)
            paragrafo.clear()
            nova_linha(1 if primeiro[0] else 2)
            self._inserir_inline(buf, p, tags)
            anterior[0] = "par"

        for linha in texto.split("\n"):
            s = linha.strip()
            if not s:
                flush()
                if anterior[0] == "lista":
                    anterior[0] = "fim-lista"
                continue
            titulo = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", s)
            item = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", linha)
            if titulo:
                flush()
                nova_linha(1 if primeiro[0] else 2)
                n = len(titulo.group(1))
                self._inserir_inline(buf, titulo.group(2), tags, extra=[tags["h1" if n == 1 else "h2" if n == 2 else "h3"]])
                anterior[0] = "titulo"
            elif item and not re.match(r"^([-*_])\1{2,}$", s):
                flush()
                nivel = min(len(item.group(1).expandtabs(4)) // 2, 2)
                marca, conteudo = item.group(2), item.group(3)
                tarefa = re.match(r"^\[([ xX])\]\s+(.*)$", conteudo)
                if tarefa:
                    marca = "☑" if tarefa.group(1).lower() == "x" else "☐"
                    conteudo = tarefa.group(2)
                elif marca in "-*+":
                    marca = ("•", "◦", "▪")[nivel]
                nova_linha(1 if anterior[0] in ("lista", "titulo", None) else 2)
                lista = tags[f"lista{nivel}"]
                self._inserir(buf, f"{marca} ", [tags["base"], lista, tags["marcador"]])
                self._inserir_inline(buf, conteudo, tags, extra=[lista])
                anterior[0] = "lista"
            elif s.startswith(">"):
                flush()
                nova_linha(1 if anterior[0] == "quote" else 2 if not primeiro[0] else 1)
                self._inserir(buf, "▍ ", [tags["base"], tags["dim"]])
                self._inserir_inline(buf, s.lstrip(">").strip(), tags, extra=[tags["quote"]])
                anterior[0] = "quote"
            elif re.match(r"^([-*_])\s*(\1\s*){2,}$", s):
                flush()
                nova_linha(2)
                self._inserir(buf, "─" * 48, [tags["base"], tags["dim"]])
                anterior[0] = "hr"
            elif anterior[0] == "lista" and linha.startswith((" ", "\t")):
                # continuação de um item de lista
                self._inserir_inline(buf, " " + s, tags, extra=[tags["lista0"]])
            else:
                paragrafo.append(linha)
        flush()

    def _criar_texto_view(self):
        tv = Gtk.TextView()
        tv.set_editable(False)
        tv.set_cursor_visible(False)
        tv.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        tv.set_hexpand(True)
        tv.set_left_margin(2)
        tv.set_right_margin(2)
        tv.add_css_class("msg-body")

        def url_em(view, x, y):
            bx, by = view.window_to_buffer_coords(Gtk.TextWindowType.WIDGET, int(x), int(y))
            res = view.get_iter_at_location(bx, by)
            ok, it = (res[0], res[1]) if isinstance(res, tuple) else (True, res)
            if ok and it:
                for t in it.get_tags():
                    if getattr(t, "url", None):
                        return t.url
            return None

        clique = Gtk.GestureClick.new()

        def ao_clicar(gesto, n, x, y):
            url = url_em(tv, x, y) if n == 1 else None
            if url:
                abrir_link(self, url)
                gesto.set_state(Gtk.EventSequenceState.CLAIMED)
        clique.connect("released", ao_clicar)
        tv.add_controller(clique)

        movimento = Gtk.EventControllerMotion.new()
        movimento.connect("motion", lambda _c, x, y: tv.set_cursor_from_name("pointer" if url_em(tv, x, y) else "text"))
        tv.add_controller(movimento)
        return tv

    # ── tabela ───────────────────────────────────────────────────────────────
    def _criar_tabela(self, conteudo):
        cab, alinh, corpo = parse_tabela(conteudo)
        ncol = max([len(cab)] + [len(l) for l in corpo])
        grade = Gtk.Grid()
        grade.add_css_class("md-tabela")
        xalign = {"esquerda": 0.0, "centro": 0.5, "direita": 1.0}
        for r, linha in enumerate([cab] + corpo):
            for c in range(ncol):
                texto = linha[c] if c < len(linha) else ""
                lbl = Gtk.Label(xalign=xalign.get(alinh[c] if c < len(alinh) else "", 0.0))
                lbl.set_markup(inline_para_markup(texto))
                # quebra só nas células longas: com quebra, a Grid mede a altura na
                # largura mínima e a tabela ganhava um vão vazio embaixo
                if len(texto) > 40:
                    lbl.set_wrap(True)
                    lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
                    lbl.set_max_width_chars(42)
                    lbl.set_width_chars(24)
                lbl.set_selectable(True)
                lbl.set_hexpand(True)
                lbl.add_css_class("md-th" if r == 0 else "md-td")
                if r > 0 and r % 2 == 0:
                    lbl.add_css_class("md-par")
                lbl.connect("activate-link", lambda _l, url: (abrir_link(self, url), True)[1])
                grade.attach(lbl, c, r, 1, 1)
        # Sem rolagem: as células quebram linha, e um ScrolledWindow horizontal
        # mediria a altura na largura mínima (sobrava um vão enorme embaixo).
        moldura = Gtk.Box()
        moldura.add_css_class("md-tabela-moldura")
        moldura.set_overflow(Gtk.Overflow.HIDDEN)
        grade.set_hexpand(True)
        moldura.append(grade)
        return moldura

    # ── código ───────────────────────────────────────────────────────────────
    def _botao_codigo(self, icone, rotulo, dica):
        btn = Gtk.Button()
        btn.set_child(Adw.ButtonContent(icon_name=icone, label=rotulo))
        btn.add_css_class("flat")
        btn.add_css_class("code-copy-btn")
        btn.set_tooltip_text(dica)
        return btn

    def _feedback_botao(self, btn, icone, rotulo, icone_volta, rotulo_volta):
        btn.set_child(Adw.ButtonContent(icon_name=icone, label=rotulo))
        GLib.timeout_add_seconds(2, lambda: (btn.set_child(Adw.ButtonContent(icon_name=icone_volta,
                                                                             label=rotulo_volta)), False)[1])

    def _criar_widget_codigo(self, lang, codigo):
        lang = (lang or "").lower()
        code_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        code_box.add_css_class("code-block-box")
        code_box.set_hexpand(True)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        header.add_css_class("code-block-header")
        lbl_lang = Gtk.Label(label=lang or _t("código"))
        lbl_lang.add_css_class("code-block-lang")
        header.append(lbl_lang)
        espaco = Gtk.Box()
        espaco.set_hexpand(True)
        header.append(espaco)

        lang_real = LANG_ALIASES.get(lang, lang)
        if HAS_GTKSOURCE:
            lm = GtkSource.LanguageManager.get_default()
            language = lm.get_language(lang_real) if lang_real else None
            buf = GtkSource.Buffer.new_with_language(language) if language else GtkSource.Buffer()
            sm = GtkSource.StyleSchemeManager.get_default()
            escuro = Adw.StyleManager.get_default().get_dark()
            scheme = sm.get_scheme("Adwaita-dark" if escuro else "Adwaita") or sm.get_scheme("classic")
            if scheme:
                buf.set_style_scheme(scheme)
            view = GtkSource.View.new_with_buffer(buf)
        else:
            view = Gtk.TextView()
            buf = view.get_buffer()
        view.set_editable(False)
        view.set_cursor_visible(False)
        view.set_monospace(True)
        view.set_wrap_mode(Gtk.WrapMode.NONE)
        view.set_top_margin(10)
        view.set_bottom_margin(10)
        view.set_left_margin(14)
        view.set_right_margin(14)
        view.add_css_class("code-block-view")
        buf.set_text(codigo)

        def texto_atual():
            return buf.get_text(buf.get_start_iter(), buf.get_end_iter(), True)

        if lang in EXECUTAVEIS:
            btn_exec = self._botao_codigo("media-playback-start-symbolic", _t("Executar"),
                                          _t("Executar comando no terminal do Simba"))

            def _exec_codigo(_b, l=lang):
                c = texto_atual()
                pausa = f"echo; read -n1 -rsp '{_t('Pronto. Tecle algo para fechar.')}'"
                corpo = f"python3 -c {shlex.quote(c)}" if l in ("python", "py", "python3") else c
                subprocess.Popen(
                    ["simba-launch-tui", "--app-id=org.simba.agent", "bash", "-c",
                     f"cd {shlex.quote(str(self.work_dir))}; {corpo}; {pausa}"],
                    cwd=str(self.work_dir), start_new_session=True,
                )
            btn_exec.connect("clicked", _exec_codigo)
            header.append(btn_exec)

        btn_salvar = self._botao_codigo("document-save-symbolic", _t("Salvar"),
                                        _t("Salvar código em arquivo na pasta de trabalho"))

        def _salvar_bloco(_b, l=lang):
            c = texto_atual()
            exts = {"python": "py", "python3": "py", "py": "py", "sh": "sh", "bash": "sh", "shell": "sh",
                    "zsh": "sh", "js": "js", "javascript": "js", "ts": "ts", "typescript": "ts", "json": "json",
                    "yaml": "yaml", "yml": "yaml", "toml": "toml", "html": "html", "css": "css", "sql": "sql",
                    "rust": "rs", "lua": "lua", "qml": "qml", "diff": "diff"}
            primeira = c.strip().splitlines()[0] if c.strip() else ""
            m_nome = re.search(r"^(?:#|//|--|/\*)\s*(?:arquivo|file)?:\s*([a-zA-Z0-9_\-\./\\]+)", primeira, re.I)
            sugerido = m_nome.group(1).strip() if m_nome else f"snippet.{exts.get(l, 'txt')}"
            alerta = Adw.AlertDialog.new(_t("Salvar código"), _t("Nome do arquivo na pasta de trabalho:"))
            alerta.add_response("cancelar", _t("Cancelar"))
            alerta.add_response("salvar", _t("Salvar"))
            alerta.set_response_appearance("salvar", Adw.ResponseAppearance.SUGGESTED)
            alerta.set_default_response("salvar")
            alerta.set_close_response("cancelar")
            entry = Gtk.Entry()
            entry.set_text(sugerido)
            entry.set_margin_start(12)
            entry.set_margin_end(12)
            alerta.set_extra_child(entry)

            def _on_resposta(_d, resp):
                if resp != "salvar":
                    return
                destino = self.work_dir / (entry.get_text().strip() or sugerido)
                try:
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    destino.write_text(c, encoding="utf-8")
                    self._feedback_botao(btn_salvar, "emblem-ok-symbolic", _t("Salvo!"),
                                         "document-save-symbolic", _t("Salvar"))
                except Exception as err:  # noqa: BLE001
                    self._adicionar_sistema(f"{_t('Erro ao salvar:')} {err}", registro=False)
            alerta.connect("response", _on_resposta)
            alerta.present(self)
        btn_salvar.connect("clicked", _salvar_bloco)
        header.append(btn_salvar)

        btn_copiar = self._botao_codigo("edit-copy-symbolic", _t("Copiar"), _t("Copiar"))

        def _copiar_codigo(_b):
            Gdk.Display.get_default().get_clipboard().set(texto_atual())
            self._feedback_botao(btn_copiar, "emblem-ok-symbolic", _t("Copiado!"), "edit-copy-symbolic", _t("Copiar"))
        btn_copiar.connect("clicked", _copiar_codigo)
        header.append(btn_copiar)
        code_box.append(header)

        # Rolagem só na horizontal: linhas longas não são cortadas nem quebradas
        rolagem = Gtk.ScrolledWindow()
        rolagem.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
        rolagem.set_propagate_natural_height(True)
        rolagem.set_hexpand(True)
        rolagem.set_child(view)
        code_box.append(rolagem)

        code_box.definir_codigo = lambda novo: buf.set_text(novo)
        return code_box
