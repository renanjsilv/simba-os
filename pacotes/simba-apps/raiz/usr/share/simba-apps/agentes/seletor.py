"""Seletor em popover (agente e modelo), no estilo do seletor de modelo do Claude/ChatGPT.

Substitui o Gtk.DropDown: a lista do DropDown era alterada (rótulos com o modelo, "sem
limite até…") enquanto o menu ainda fechava, e trocar o modelo podia congelar a janela.
Aqui a lista só é montada quando o popover abre, nada a altera enquanto ele está aberto,
e a escolha é aplicada depois que ele fecha (idle). Uma busca aparece em listas longas.

API compatível com o que o resto do chat usava do DropDown: get_selected(),
set_selected(i) (sem disparar a escolha) e a lista `itens` [{id, nome, ...}].
"""
import sys

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

sys.path.insert(0, "/usr/share/simba-apps/idiomas")
from simba_i18n import t as _t  # noqa: E402

BUSCA_A_PARTIR = 9   # itens a partir dos quais aparece o campo de busca


class Seletor(Gtk.MenuButton):
    """Botão + popover com uma lista de itens {id, nome, sub, icone, aviso}.

    `itens_fn()` devolve a lista atual (chamada ao abrir); `ao_escolher(i, item)` roda
    depois que o popover fecha. `cabecalho` é um título opcional no topo da lista.
    """

    def __init__(self, itens_fn, ao_escolher, cabecalho="", classe="seletor", icone_fn=None,
                 largura=340, mostrar_icone=True):
        super().__init__()
        self.itens_fn = itens_fn
        self.ao_escolher = ao_escolher
        self.icone_fn = icone_fn
        self.itens = []
        self._sel = 0
        self._pendente = None
        self.add_css_class(classe)
        self.set_always_show_arrow(False)

        conteudo = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
        self.icone = Gtk.Image()
        self.icone.set_pixel_size(18)
        self.icone.set_visible(mostrar_icone)
        conteudo.append(self.icone)
        self.rotulo = Gtk.Label(xalign=0)
        self.rotulo.set_ellipsize(Pango.EllipsizeMode.END)
        self.rotulo.set_max_width_chars(30)
        conteudo.append(self.rotulo)
        seta = Gtk.Image.new_from_icon_name("pan-down-symbolic")
        seta.set_pixel_size(12)
        seta.add_css_class("seletor-seta")
        conteudo.append(seta)
        self.set_child(conteudo)

        self.pop = Gtk.Popover()
        self.pop.add_css_class("seletor-pop")
        self.pop.set_has_arrow(False)
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        caixa.set_size_request(largura, -1)
        if cabecalho:
            titulo = Gtk.Label(label=cabecalho, xalign=0)
            titulo.add_css_class("seletor-titulo")
            caixa.append(titulo)
        self.busca = Gtk.SearchEntry()
        self.busca.set_placeholder_text(_t("Buscar…"))
        self.busca.add_css_class("seletor-busca")
        self.busca.connect("search-changed", lambda *_: self.lista.invalidate_filter())
        self.busca.connect("activate", self._ativar_primeiro)
        caixa.append(self.busca)
        self.rolagem = Gtk.ScrolledWindow()
        self.rolagem.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.rolagem.set_propagate_natural_height(True)
        self.rolagem.set_max_content_height(420)
        self.lista = Gtk.ListBox()
        self.lista.add_css_class("seletor-lista")
        self.lista.set_selection_mode(Gtk.SelectionMode.NONE)
        self.lista.set_activate_on_single_click(True)
        self.lista.connect("row-activated", self._linha_ativada)
        self.lista.set_filter_func(self._filtro)
        self.rolagem.set_child(self.lista)
        caixa.append(self.rolagem)
        self.pop.set_child(caixa)
        self.set_popover(self.pop)
        self.pop.connect("show", lambda *_: self._montar())
        self.pop.connect("closed", lambda *_: self._aplicar_pendente())

    # ── estado ────────────────────────────────────────────────────────────────
    def atualizar(self, itens=None):
        """Relê os itens (sem abrir) e atualiza o botão. Não mexe no popover aberto."""
        if self.pop.get_visible():
            return
        self.itens = list(itens if itens is not None else self.itens_fn())
        if not (0 <= self._sel < len(self.itens)):
            self._sel = 0
        self._mostrar_atual()

    def get_selected(self):
        return self._sel

    def set_selected(self, i):
        """Marca o item i (como o DropDown, sem chamar ao_escolher)."""
        if 0 <= i < len(self.itens):
            self._sel = i
            self._mostrar_atual()

    def selecionar_id(self, iid):
        for i, it in enumerate(self.itens):
            if it.get("id") == iid:
                self.set_selected(i)
                return True
        return False

    def escolher(self, i):
        """Escolhe o item i como se a pessoa tivesse clicado (usado pelos testes)."""
        if 0 <= i < len(self.itens):
            self._sel = i
            self._mostrar_atual()
            self.ao_escolher(i, self.itens[i])

    def atual(self):
        return self.itens[self._sel] if 0 <= self._sel < len(self.itens) else {}

    def _mostrar_atual(self):
        it = self.atual()
        self.rotulo.set_label(it.get("curto") or it.get("nome") or "")
        icone = it.get("icone") or (self.icone_fn(it) if self.icone_fn else None)
        if icone:
            self.icone.set_from_icon_name(icone)
        dica = it.get("nome", "")
        if it.get("sub"):
            dica += f"\n{it['sub']}"
        self.set_tooltip_text(dica or None)

    # ── popover ───────────────────────────────────────────────────────────────
    def _montar(self):
        self.itens = list(self.itens_fn())
        if not (0 <= self._sel < len(self.itens)):
            self._sel = 0
        filho = self.lista.get_first_child()
        while filho is not None:
            self.lista.remove(filho)
            filho = self.lista.get_first_child()
        for i, it in enumerate(self.itens):
            self.lista.append(self._linha(i, it))
        longa = len(self.itens) >= BUSCA_A_PARTIR
        self.busca.set_visible(longa)
        self.busca.set_text("")
        if longa:
            GLib.idle_add(lambda: (self.busca.grab_focus(), False)[1])
        linha = self.lista.get_row_at_index(self._sel)
        if linha is not None and not longa:
            GLib.idle_add(lambda: (linha.grab_focus(), False)[1])

    def _linha(self, i, it):
        linha = Gtk.ListBoxRow()
        linha.add_css_class("seletor-linha")
        linha.indice = i
        linha.busca = f"{it.get('nome', '')} {it.get('sub', '')} {it.get('id', '')}".lower()
        if it.get("separar"):
            linha.add_css_class("separar")
        caixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        icone = it.get("icone") or (self.icone_fn(it) if self.icone_fn else None)
        if icone:
            img = Gtk.Image.new_from_icon_name(icone)
            img.set_pixel_size(20)
            img.set_valign(Gtk.Align.CENTER)
            img.add_css_class("seletor-linha-icone")
            caixa.append(img)
        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        textos.set_hexpand(True)
        nome = Gtk.Label(label=it.get("nome", ""), xalign=0)
        nome.set_ellipsize(Pango.EllipsizeMode.END)
        nome.add_css_class("seletor-nome")
        textos.append(nome)
        if it.get("sub"):
            sub = Gtk.Label(label=it["sub"], xalign=0)
            sub.set_wrap(True)
            sub.set_lines(2)
            sub.set_max_width_chars(38)
            sub.set_ellipsize(Pango.EllipsizeMode.END)
            sub.add_css_class("seletor-sub")
            textos.append(sub)
        caixa.append(textos)
        if it.get("aviso"):
            av = Gtk.Label(label=it["aviso"])
            av.add_css_class("seletor-aviso")
            av.set_valign(Gtk.Align.CENTER)
            caixa.append(av)
        marca = Gtk.Image.new_from_icon_name("object-select-symbolic")
        marca.set_pixel_size(14)
        marca.add_css_class("seletor-marca")
        marca.set_valign(Gtk.Align.CENTER)
        marca.set_opacity(1.0 if i == self._sel else 0.0)
        caixa.append(marca)
        linha.set_child(caixa)
        if i == self._sel:
            linha.add_css_class("atual")
        return linha

    def _filtro(self, linha):
        termo = self.busca.get_text().strip().lower() if self.busca.get_visible() else ""
        return not termo or all(p in linha.busca for p in termo.split())

    def _ativar_primeiro(self, _e):
        i = 0
        while True:
            linha = self.lista.get_row_at_index(i)
            if linha is None:
                return
            if linha.get_child_visible() and self._filtro(linha):
                self._linha_ativada(self.lista, linha)
                return
            i += 1

    def _linha_ativada(self, _lista, linha):
        self._pendente = linha.indice
        self.pop.popdown()

    def _aplicar_pendente(self):
        i, self._pendente = self._pendente, None
        if i is None or not (0 <= i < len(self.itens)):
            return

        def aplicar():
            self._sel = i
            self._mostrar_atual()
            self.ao_escolher(i, self.itens[i])
            return False
        # depois que o popover terminou de fechar: nada muda com o menu na tela
        GLib.idle_add(aplicar)
