"""Busca na conversa (Ctrl+F): destaca as ocorrências e navega entre elas.

Procura em todos os textos da conversa: respostas (texto e blocos de código),
mensagens do usuário, tabelas e avisos. Sem diferenciar maiúsculas nem acentos.
"""
import sys
from pathlib import Path
import unicodedata

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import GLib, Graphene, Gtk, Pango  # noqa: E402

sys.path.insert(0, "/usr/share/simba-apps/idiomas")
from simba_i18n import t as _t  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))

TAG = "simba-busca"
TAG_ATUAL = "simba-busca-atual"


def normalizar(texto):
    """Minúsculas e sem acento, mantendo o mesmo número de caracteres."""
    saida = []
    for c in texto:
        base = unicodedata.normalize("NFD", c)[0]
        saida.append(base.casefold()[:1] or c)
    return "".join(saida)


def ocorrencias(texto, termo):
    """Posições (início, fim) de `termo` em `texto`, em caracteres."""
    if not termo:
        return []
    alvo, t = normalizar(texto), normalizar(termo)
    out, i = [], alvo.find(t)
    while i != -1:
        out.append((i, i + len(t)))
        i = alvo.find(t, i + max(1, len(t)))
    return out


class BuscaMixin:
    def _criar_barra_busca(self):
        self.busca_resultados = []
        self.busca_indice = -1
        self.busca_buffers = set()
        self.busca_rotulos = {}  # Label → atributos originais (para desfazer o destaque)

        # Barra simples (não Gtk.SearchBar): a animação do SearchBar deixava o
        # campo fora da tela no instante do Ctrl+F e o GTK devolvia o foco à caixa
        # de texto do chat, então o que a pessoa digitava ia para o lugar errado.
        self.barra_busca = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self.barra_busca.add_css_class("barra-busca")
        self.barra_busca.set_visible(False)
        caixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        caixa.set_hexpand(True)
        caixa.set_halign(Gtk.Align.CENTER)

        self.busca_entrada = Gtk.SearchEntry()
        self.busca_entrada.set_placeholder_text(_t("Buscar na conversa"))
        self.busca_entrada.set_size_request(320, -1)
        self.busca_entrada.connect("search-changed", lambda *_: self._buscar())
        self.busca_entrada.connect("activate", lambda *_: self._busca_ir(1))
        self.busca_entrada.connect("next-match", lambda *_: self._busca_ir(1))
        self.busca_entrada.connect("previous-match", lambda *_: self._busca_ir(-1))
        self.busca_entrada.connect("stop-search", lambda *_: self._fechar_busca())
        tecla = Gtk.EventControllerKey()
        tecla.connect("key-pressed", self._busca_tecla)
        self.busca_entrada.add_controller(tecla)
        caixa.append(self.busca_entrada)

        self.busca_contagem = Gtk.Label(label="")
        self.busca_contagem.add_css_class("composer-hint")
        self.busca_contagem.set_width_chars(10)
        caixa.append(self.busca_contagem)

        for icone, passo, dica in (("go-up-symbolic", -1, _t("Anterior (Shift+Enter)")),
                                   ("go-down-symbolic", 1, _t("Próxima (Enter)"))):
            b = Gtk.Button(icon_name=icone)
            b.add_css_class("flat")
            b.add_css_class("circular")
            b.set_tooltip_text(dica)
            b.connect("clicked", lambda _b, p=passo: self._busca_ir(p))
            caixa.append(b)

        self.barra_busca.append(caixa)
        fechar = Gtk.Button(icon_name="window-close-symbolic")
        fechar.add_css_class("flat")
        fechar.add_css_class("circular")
        fechar.set_valign(Gtk.Align.CENTER)
        fechar.set_tooltip_text(_t("Fechar a busca (Esc)"))
        fechar.connect("clicked", lambda _b: self._fechar_busca())
        self.barra_busca.append(fechar)
        return self.barra_busca

    def _busca_ativa(self):
        return self.barra_busca.get_visible()

    def _abrir_busca(self):
        selecao = self._texto_selecionado()  # antes de o foco sair da resposta
        self.barra_busca.set_visible(True)
        if selecao:
            self.busca_entrada.set_text(selecao)
        self.busca_entrada.grab_focus()
        self.busca_entrada.select_region(0, -1)

    def _fechar_busca(self):
        if not self.barra_busca.get_visible():
            return
        self.barra_busca.set_visible(False)
        self._limpar_destaques()
        self.busca_resultados = []
        self.busca_contagem.set_label("")
        self.text_input.grab_focus()

    def _busca_tecla(self, _c, keyval, _code, estado):
        from gi.repository import Gdk
        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and estado & Gdk.ModifierType.SHIFT_MASK:
            self._busca_ir(-1)
            return True
        return False

    def _texto_selecionado(self):
        foco = self.get_focus()
        if isinstance(foco, Gtk.TextView):
            buf = foco.get_buffer()
            if buf.get_has_selection():
                a, b = buf.get_selection_bounds()
                texto = buf.get_text(a, b, False)
                if "\n" not in texto and len(texto) < 80:
                    return texto
        return ""

    # ── procurar ─────────────────────────────────────────────────────────────
    def _alvos(self, widget):
        """TextViews e Labels da conversa, na ordem em que aparecem."""
        filho = widget.get_first_child()
        while filho is not None:
            if isinstance(filho, Gtk.TextView):
                if not filho.get_editable():
                    yield filho
            elif isinstance(filho, Gtk.Label):
                if filho.get_selectable() or filho.has_css_class("md-celula"):
                    yield filho
            else:
                yield from self._alvos(filho)
            filho = filho.get_next_sibling()

    def _buscar(self):
        self._limpar_destaques()
        termo = self.busca_entrada.get_text().strip()
        self.busca_resultados = []
        self.busca_indice = -1
        if not termo:
            self.busca_contagem.set_label("")
            return
        for alvo in self._alvos(self.box_mensagens):
            if not alvo.get_mapped() and not self._visivel_na_conversa(alvo):
                continue
            if isinstance(alvo, Gtk.TextView):
                buf = alvo.get_buffer()
                texto = buf.get_text(buf.get_start_iter(), buf.get_end_iter(), False)
                achados = ocorrencias(texto, termo)
                if achados:
                    self._tags_busca(buf)
                    self.busca_buffers.add(buf)
                for ini, fim in achados:
                    buf.apply_tag_by_name(TAG, buf.get_iter_at_offset(ini), buf.get_iter_at_offset(fim))
                    self.busca_resultados.append((alvo, ini, fim))
            else:
                achados = ocorrencias(alvo.get_text(), termo)
                for ini, fim in achados:
                    self.busca_resultados.append((alvo, ini, fim))
                if achados:
                    self.busca_rotulos[alvo] = alvo.get_attributes()
                    self._destacar_rotulo(alvo, achados, None)
        if self.busca_resultados:
            self.busca_indice = len(self.busca_resultados) - 1  # a mais recente primeiro
            self._busca_mostrar()
        else:
            self.busca_contagem.set_label(_t("Nada encontrado"))

    def _visivel_na_conversa(self, w):
        """Ignora o que está dentro de painéis recolhidos (ex.: Detalhes fechado)."""
        while w is not None and w is not self.box_mensagens:
            if not w.get_visible():
                return False
            if isinstance(w, Gtk.Revealer) and not w.get_reveal_child():
                return False
            w = w.get_parent()
        return True

    def _busca_ir(self, passo):
        if not self.busca_resultados:
            self._buscar()
            return
        self.busca_indice = (self.busca_indice + passo) % len(self.busca_resultados)
        self._busca_mostrar()

    def _busca_mostrar(self):
        total = len(self.busca_resultados)
        alvo, ini, fim = self.busca_resultados[self.busca_indice]
        self.busca_contagem.set_label(_t("%1 de %2").replace("%1", str(self.busca_indice + 1)).replace("%2", str(total)))
        for buf in self.busca_buffers:
            buf.remove_tag_by_name(TAG_ATUAL, buf.get_start_iter(), buf.get_end_iter())
        for rotulo in self.busca_rotulos:
            achados = [(i, f) for (a, i, f) in self.busca_resultados if a is rotulo]
            self._destacar_rotulo(rotulo, achados, (ini, fim) if rotulo is alvo else None)
        y = 0.0
        if isinstance(alvo, Gtk.TextView):
            buf = alvo.get_buffer()
            a, b = buf.get_iter_at_offset(ini), buf.get_iter_at_offset(fim)
            buf.apply_tag_by_name(TAG_ATUAL, a, b)
            ret = alvo.get_iter_location(a)
            _wx, y = alvo.buffer_to_window_coords(Gtk.TextWindowType.WIDGET, ret.x, ret.y)
        else:
            layout = alvo.get_layout()
            idx = len(alvo.get_text()[:ini].encode("utf-8"))
            pos = layout.index_to_pos(idx)
            _lx, ly = alvo.get_layout_offsets()
            y = ly + pos.y / Pango.SCALE
        ok, ponto = alvo.compute_point(self.box_mensagens, Graphene.Point().init(0, y))
        if ok:
            self.seguir_fim = False
            adj = self.scroller.get_vadjustment()
            destino = ponto.y + self.box_mensagens.get_margin_top() - adj.get_page_size() / 3
            GLib.idle_add(lambda: adj.set_value(max(0.0, min(destino, adj.get_upper() - adj.get_page_size()))) and False)

    def _tags_busca(self, buf):
        tabela = buf.get_tag_table()
        if tabela.lookup(TAG) is None:
            buf.create_tag(TAG, background="rgba(246, 211, 45, 0.35)")
        if tabela.lookup(TAG_ATUAL) is None:
            buf.create_tag(TAG_ATUAL, background="rgba(255, 120, 0, 0.85)", foreground="#000000")

    def _limpar_destaques(self):
        for buf in self.busca_buffers:
            ini, fim = buf.get_start_iter(), buf.get_end_iter()
            buf.remove_tag_by_name(TAG, ini, fim)
            buf.remove_tag_by_name(TAG_ATUAL, ini, fim)
        self.busca_buffers = set()
        for rotulo, originais in self.busca_rotulos.items():
            rotulo.set_attributes(originais)
        self.busca_rotulos = {}

    def _destacar_rotulo(self, rotulo, achados, atual):
        """Fundo amarelo nas ocorrências (laranja na atual), por cima dos atributos do rótulo."""
        base = self.busca_rotulos.get(rotulo)
        attrs = base.copy() if base is not None else Pango.AttrList()
        texto = rotulo.get_text()
        for ini, fim in achados:
            a = len(texto[:ini].encode("utf-8"))
            b = len(texto[:fim].encode("utf-8"))
            eh_atual = atual == (ini, fim)
            cor = (0xFFFF, 0x7800, 0x0000) if eh_atual else (0xF600, 0xD300, 0x2D00)
            fundo = Pango.attr_background_new(*cor)
            fundo.start_index, fundo.end_index = a, b
            attrs.insert(fundo)
            alfa = Pango.attr_background_alpha_new(0xD999 if eh_atual else 0x5999)
            alfa.start_index, alfa.end_index = a, b
            attrs.insert(alfa)
            if eh_atual:
                frente = Pango.attr_foreground_new(0, 0, 0)
                frente.start_index, frente.end_index = a, b
                attrs.insert(frente)
        rotulo.set_attributes(attrs)
