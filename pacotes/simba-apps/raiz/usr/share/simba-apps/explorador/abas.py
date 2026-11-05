"""Faixa de abas na barra de título, como a do Explorador do Windows 11.

Medidas do controle de abas do WinUI (TabView_themeresources.xaml, microsoft-ui-xaml):
faixa com 8 px livres em cima e abas de 32 px (barra de 40 px); abas de largura
igual entre 100 e 240 px; texto 12 px, ícone 16 px, botão fechar 24 px; botão "+"
de 32×24 logo depois da última aba; divisória de 1 px entre abas não selecionadas;
aba selecionada com cantos de 8 px em cima e "pés" curvos embaixo, na mesma cor da
barra de baixo (endereço/comandos), sem linha entre as duas. O resto da faixa é área
de arrastar a janela (no mínimo 120 px antes dos botões da janela).

Usa o Adw.TabView só como dono das páginas; a faixa é desenhada aqui.
"""
from gi.repository import Gdk, Gio, GLib, Graphene, Gsk, Gtk, Pango

import utilidades as u
import sys as _sys, os as _os  # noqa: E401
_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))
from simba_i18n import t as _t  # noqa: E402  (traduções: /usr/share/simba-apps/idiomas)

TOPO = 8           # espaço livre acima das abas
ALTURA = 32        # altura da aba
LARG_MAX = 240
LARG_MIN = 100
LARG_MINIMA = 44   # muitas abas: só o ícone
MAIS_L, MAIS_A = 32, 24
RAIO = 8
AREA_ARRASTAR = 120


class Aba(Gtk.Box):
    """Uma aba: ícone, título e X."""

    def __init__(self, faixa, pagina):
        super().__init__(spacing=8, css_classes=["aba-win"], valign=Gtk.Align.START)
        self.faixa, self.pagina = faixa, pagina
        self.set_size_request(-1, ALTURA)
        self.img = Gtk.Image(pixel_size=16, margin_start=10)
        self.rot = Gtk.Label(xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END, css_classes=["aba-titulo"])
        self.x = Gtk.Button(icon_name="window-close-symbolic", css_classes=["flat", "aba-fechar"], valign=Gtk.Align.CENTER,
                            tooltip_text=_t("Fechar aba (Ctrl+W)"), margin_end=4)
        self.x.connect("clicked", lambda b: self.faixa.view.close_page(self.pagina))
        for w in (self.img, self.rot, self.x):
            self.append(w)
        self._sinais = [pagina.connect("notify::title", lambda *a: self.atualizar()),
                        pagina.connect("notify::icon", lambda *a: self.atualizar())]
        self.atualizar()
        # clique seleciona; meio fecha; direito abre o menu
        g = Gtk.GestureClick(button=0)
        g.connect("pressed", self._clique)
        self.add_controller(g)
        # arrastar para reordenar
        d = Gtk.GestureDrag()
        # a aba fica com o gesto: senão a alça da barra de título arrasta a janela
        d.connect("drag-begin", lambda g, x, y: (g.set_state(Gtk.EventSequenceState.CLAIMED),
                                                 self.faixa.arrasto_inicio(self)))
        d.connect("drag-update", lambda g, dx, dy: self.faixa.arrasto_move(self, dx))
        d.connect("drag-end", lambda g, dx, dy: self.faixa.arrasto_fim(self))
        self.add_controller(d)
        mov = Gtk.EventControllerMotion()
        mov.connect("enter", lambda *a: (self.add_css_class("hover"), self.faixa.queue_draw()))
        mov.connect("leave", lambda *a: (self.remove_css_class("hover"), self.faixa.queue_draw()))
        self.add_controller(mov)

    def desligar(self):
        for s in self._sinais:
            self.pagina.disconnect(s)

    def atualizar(self):
        self.rot.set_label(self.pagina.get_title() or "")
        self.set_tooltip_text(self.pagina.get_title() or "")
        ic = self.pagina.get_icon()
        if ic:
            self.img.set_from_gicon(ic)

    def _clique(self, g, n, x, y):
        b = g.get_current_button()
        if b == 2:
            self.faixa.view.close_page(self.pagina)
            g.set_state(Gtk.EventSequenceState.CLAIMED)
        elif b == 3:
            self.faixa.menu(self, x, y)
            g.set_state(Gtk.EventSequenceState.CLAIMED)
        elif b == 1:
            self.faixa.view.set_selected_page(self.pagina)


class FaixaAbas(Gtk.Widget):
    """Layout próprio: abas de largura igual + "+", alinhados à esquerda."""

    def __init__(self, view, ao_nova_aba, janela):
        super().__init__(hexpand=True, css_classes=["faixa-abas"])
        self.view, self.janela = view, janela
        self.abas = []
        self.mais = Gtk.Button(icon_name="list-add-symbolic", css_classes=["flat", "aba-mais"],
                               tooltip_text=_t("Nova aba (Ctrl+T)"))
        self.mais.connect("clicked", lambda b: ao_nova_aba())
        self.mais.set_parent(self)
        self._larg = LARG_MAX
        self._arrasto = None
        view.connect("page-attached", lambda v, p, i: self._anexar(p, i))
        view.connect("page-detached", lambda v, p, i: self._remover(p))
        view.connect("page-reordered", lambda v, p, i: self._reordenar())
        view.connect("notify::selected-page", lambda *a: self._selecao())
        for i in range(view.get_n_pages()):
            self._anexar(view.get_nth_page(i), i)

    # ── páginas ────────────────────────────────────────────────────────────
    def _anexar(self, pagina, i):
        a = Aba(self, pagina)
        a.set_parent(self)
        self.abas.insert(i, a)
        self._selecao()
        self.queue_resize()

    def _remover(self, pagina):
        for a in list(self.abas):
            if a.pagina is pagina:
                a.desligar()
                a.unparent()
                self.abas.remove(a)
        self.queue_resize()

    def _reordenar(self):
        ordem = {self.view.get_nth_page(i): i for i in range(self.view.get_n_pages())}
        self.abas.sort(key=lambda a: ordem.get(a.pagina, 0))
        self.queue_allocate()

    def _selecao(self):
        sel = self.view.get_selected_page()
        for a in self.abas:
            if a.pagina is sel:
                a.add_css_class("selecionada")
            else:
                a.remove_css_class("selecionada")
        self.queue_draw()

    # ── layout ─────────────────────────────────────────────────────────────
    def do_measure(self, orientacao, para):
        if orientacao == Gtk.Orientation.HORIZONTAL:
            nat = len(self.abas) * LARG_MAX + MAIS_L + 8 + AREA_ARRASTAR
            return 0, nat, -1, -1
        return TOPO + ALTURA, TOPO + ALTURA, -1, -1

    def do_size_allocate(self, largura, altura, base):
        n = max(1, len(self.abas))
        disponivel = max(0, largura - AREA_ARRASTAR - MAIS_L - 8)
        self._larg = max(LARG_MINIMA, min(LARG_MAX, disponivel // n if self.abas else LARG_MAX))
        x = 0
        for a in self.abas:
            a.rot.set_visible(self._larg >= 76)
            mostrar_x = self._larg >= LARG_MIN or a.has_css_class("selecionada")
            a.x.set_visible(mostrar_x)
            if self._arrasto is not None and a is self._arrasto[0]:
                ax = int(max(0, min(x + self._arrasto[1], (len(self.abas) - 1) * self._larg)))
            else:
                ax = x
            t = Gsk.Transform().translate(Graphene.Point().init(ax, TOPO))
            a.allocate(self._larg, ALTURA, -1, t)
            a._x = ax
            x += self._larg
        t = Gsk.Transform().translate(Graphene.Point().init(x + 4, TOPO + (ALTURA - MAIS_A) // 2))
        self.mais.allocate(MAIS_L, MAIS_A, -1, t)

    # ── desenho: aba selecionada com cantos e "pés", divisórias ───────────
    def do_snapshot(self, snap):
        sel = self.view.get_selected_page()
        cor_sel = self._cor("cor-aba-sel")
        cor_hover = self._cor("cor-aba-hover")
        cor_div = self._cor("cor-aba-div")
        topo, base = TOPO, TOPO + ALTURA
        for i, a in enumerate(self.abas):
            x, w = getattr(a, "_x", i * self._larg), self._larg
            if a.pagina is sel:
                continue
            if a.has_css_class("hover"):
                self._retangulo(snap, x + 2, topo + 3, w - 4, ALTURA - 6, 6, cor_hover)
        # divisórias (não encostam na selecionada nem na que está sob o mouse)
        for i in range(1, len(self.abas)):
            esq, dir_ = self.abas[i - 1], self.abas[i]
            if sel in (esq.pagina, dir_.pagina) or esq.has_css_class("hover") or dir_.has_css_class("hover"):
                continue
            x = getattr(dir_, "_x", i * self._larg)
            r = Graphene.Rect().init(x, topo + 8, 1, ALTURA - 16)
            snap.append_color(cor_div, r)
        for a in self.abas:
            if a.pagina is sel:
                self._aba_sel(snap, getattr(a, "_x", 0), self._larg, topo, base, cor_sel)
        for a in self.abas + [self.mais]:
            self.snapshot_child(a, snap)

    def _aba_sel(self, snap, x, w, topo, base, cor):
        p = Gsk.PathBuilder.new()
        r, pe = RAIO, 6
        p.move_to(x - pe, base)
        p.quad_to(x, base, x, base - pe)                       # pé esquerdo
        p.line_to(x, topo + r)
        p.quad_to(x, topo, x + r, topo)                        # canto de cima
        p.line_to(x + w - r, topo)
        p.quad_to(x + w, topo, x + w, topo + r)
        p.line_to(x + w, base - pe)
        p.quad_to(x + w, base, x + w + pe, base)               # pé direito
        p.close()
        snap.append_fill(p.to_path(), Gsk.FillRule.WINDING, cor)

    def _retangulo(self, snap, x, y, w, h, raio, cor):
        r = Gsk.RoundedRect()
        r.init_from_rect(Graphene.Rect().init(x, y, w, h), raio)
        snap.push_rounded_clip(r)
        snap.append_color(cor, Graphene.Rect().init(x, y, w, h))
        snap.pop()

    def _cor(self, nome):
        c = getattr(self.janela, "cores_abas", {}).get(nome)
        rgba = Gdk.RGBA()
        rgba.parse(c or "#202020")
        return rgba

    # ── arrastar para reordenar ────────────────────────────────────────────
    def arrasto_inicio(self, aba):
        self._arrasto = None
        self._arrasto_dx = 0

    def arrasto_move(self, aba, dx):
        if self._arrasto is None and abs(dx) < 8:
            return
        self._arrasto = (aba, dx)
        i = self.abas.index(aba)
        destino = int(round((i * self._larg + dx) / max(1, self._larg)))
        destino = max(0, min(len(self.abas) - 1, destino))
        if destino != i:
            # troca no TabView; compensa o deslocamento para a aba seguir o mouse
            self.view.reorder_page(aba.pagina, destino)
            self._arrasto = (aba, dx - (destino - i) * self._larg)
            self._compensa = (destino - i) * self._larg
        self.queue_allocate()

    def arrasto_fim(self, aba):
        self._arrasto = None
        self.queue_allocate()

    # ── menu da aba ────────────────────────────────────────────────────────
    def menu(self, aba, x, y):
        j = self.janela
        for nome in ("aba-fechar", "aba-outras", "aba-direita", "aba-duplicar", "aba-janela"):
            if j.lookup_action(nome):
                j.remove_action(nome)

        def ac(nome, fn):
            a = Gio.SimpleAction.new(nome, None)
            a.connect("activate", lambda *x: fn())
            j.add_action(a)
        pag = aba.pagina
        ac("aba-fechar", lambda: self.view.close_page(pag))
        ac("aba-outras", lambda: self.view.close_other_pages(pag))
        ac("aba-direita", lambda: self.view.close_pages_after(pag))
        ac("aba-duplicar", lambda: j.nova_aba(pag.get_child().local))
        ac("aba-janela", lambda: j.app.nova_janela(pag.get_child().local))
        m = Gio.Menu()
        s = Gio.Menu()
        s.append(_t("Duplicar aba"), "win.aba-duplicar")
        s.append(_t("Abrir em nova janela"), "win.aba-janela")
        m.append_section(None, s)
        s2 = Gio.Menu()
        s2.append(_t("Fechar aba"), "win.aba-fechar")
        s2.append(_t("Fechar outras abas"), "win.aba-outras")
        s2.append(_t("Fechar abas à direita"), "win.aba-direita")
        m.append_section(None, s2)
        jx, jy = u.coords(aba, j.raiz, x, y)
        j._popover(m, jx, jy)


def barra_titulo(view, ao_nova_aba, janela):
    """Faixa de abas + área de arrastar + botões da janela, numa barra de 40 px."""
    alca = Gtk.WindowHandle(css_classes=["barra-titulo"])
    caixa = Gtk.Box()
    faixa = FaixaAbas(view, ao_nova_aba, janela)
    faixa.set_margin_start(8)
    caixa.append(faixa)
    botoes = Gtk.WindowControls(side=Gtk.PackType.END, valign=Gtk.Align.START, css_classes=["controles-janela"])
    caixa.append(botoes)
    alca.set_child(caixa)
    return alca, faixa
