"""Vista de arquivos do Explorador: grade (ícones de vários tamanhos e blocos), lista e
detalhes, sobre o mesmo modelo (DirectoryList ou uma lista pronta, como pesquisa e
galeria), com miniaturas, arrastar e soltar, digitar para achar e Ctrl+roda."""
import unicodedata

from gi.repository import Gdk, Gio, GLib, GObject, Gtk, Pango

import utilidades as u
import sys as _sys, os as _os  # noqa: E401
_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))
from simba_i18n import t as _t  # noqa: E402  (traduções: /usr/share/simba-apps/idiomas)

# visão → (tamanho do ícone, largura do item) da grade
GRADE = {
    "extragrande": (176, 200), "grande": (96, 124), "media": (64, 100), "pequena": (32, 86),
}
VISOES = ["extragrande", "grande", "media", "pequena", "blocos", "lista", "detalhes"]
NOMES_VISAO = {"extragrande": _t("Ícones extragrandes"), "grande": _t("Ícones grandes"), "media": _t("Ícones médios"),
               "pequena": _t("Ícones pequenos"), "blocos": _t("Blocos"), "lista": _t("Lista"), "detalhes": _t("Detalhes")}
ORDENS = {"nome": _t("Nome"), "data": _t("Data de modificação"), "tipo": _t("Tipo"), "tamanho": _t("Tamanho")}


def normalizar(s):
    s = unicodedata.normalize("NFD", s or "").casefold()
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


class Vista(Gtk.Overlay):
    __gsignals__ = {
        "abrir": (GObject.SignalFlags.RUN_FIRST, None, (object, bool)),   # info, nova aba
        "selecao": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "menu": (GObject.SignalFlags.RUN_FIRST, None, (float, float, bool)),  # x, y (na janela), em item
        "soltar": (GObject.SignalFlags.RUN_FIRST, None, (object, str, bool)),  # [caminhos], destino, copiar
        "contagem": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, janela, gfile=None, lista=None, mostrar_local=False):
        super().__init__()
        self.janela = janela
        self.gfile = gfile
        self.mostrar_local = mostrar_local
        cfg = janela.cfg
        self.ocultos = cfg["ocultos"]
        self.texto = ""
        chave = gfile.get_uri() if gfile else ""
        por_pasta = cfg.get("visaoPorPasta", {}).get(chave, {})
        self.visao = por_pasta.get("visao", cfg["visao"])
        self.ordem = por_pasta.get("ordem", cfg["ordem"])
        self.desc = por_pasta.get("desc", cfg["desc"])
        self._busca_tecla, self._busca_tempo = "", 0

        if lista is not None:
            self.fonte = lista
            self.dirlist = None
        else:
            self.dirlist = Gtk.DirectoryList.new(u.ATRIBUTOS, gfile)
            self.dirlist.set_monitored(True)
            self.dirlist.set_io_priority(GLib.PRIORITY_DEFAULT)
            self.fonte = self.dirlist
            self.dirlist.connect("notify::loading", lambda *a: self._atualizar_vazio())
            self.dirlist.connect("notify::error", lambda *a: self._atualizar_vazio())

        self.filtro = Gtk.CustomFilter.new(self._filtrar)
        self.filtrado = Gtk.FilterListModel.new(self.fonte, self.filtro)
        self.sorter = Gtk.CustomSorter.new(self._comparar)
        self.ordenado = Gtk.SortListModel.new(self.filtrado, self.sorter)
        self.selecao = Gtk.MultiSelection.new(self.ordenado)
        self.selecao.connect("selection-changed", lambda *a: self.emit("selecao"))
        self.ordenado.connect("items-changed", self._mudou)

        self.rolagem = Gtk.ScrolledWindow(hexpand=True, vexpand=True)
        self.set_child(self.rolagem)
        self.vazio = Gtk.Label(css_classes=["vazio"], valign=Gtk.Align.START, margin_top=60, visible=False)
        self.add_overlay(self.vazio)
        self.carregando = Gtk.Spinner(spinning=True, valign=Gtk.Align.START, halign=Gtk.Align.CENTER, margin_top=40,
                                      width_request=28, height_request=28, visible=False)
        self.add_overlay(self.carregando)

        self._montar_view()
        self._controles()

    # ── modelo ─────────────────────────────────────────────────────────────
    def _filtrar(self, info, *_):
        nome = info.get_display_name() or ""
        if not self.ocultos and (info.get_is_hidden() or info.get_is_backup() or nome.startswith(".")):
            return False
        if self.texto and self.texto not in normalizar(nome):
            return False
        return True

    def _chave_nome(self, info):
        return GLib.utf8_collate_key_for_filename(info.get_display_name() or "", -1)

    def _comparar(self, a, b, *_):
        pa, pb = u.eh_pasta(a), u.eh_pasta(b)
        if pa != pb:
            return -1 if pa else 1
        if self.ordem == "data":
            va, vb = a.get_attribute_uint64("time::modified"), b.get_attribute_uint64("time::modified")
        elif self.ordem == "tamanho":
            va, vb = a.get_size(), b.get_size()
        elif self.ordem == "tipo":
            va, vb = u.tipo_desc(a), u.tipo_desc(b)
        else:
            va, vb = self._chave_nome(a), self._chave_nome(b)
        if va == vb and self.ordem != "nome":
            va, vb = self._chave_nome(a), self._chave_nome(b)
        r = (va > vb) - (va < vb)
        return -r if self.desc else r

    def definir_ordem(self, ordem=None, desc=None):
        if ordem is not None:
            self.ordem = ordem
        if desc is not None:
            self.desc = desc
        self.sorter.changed(Gtk.SorterChange.DIFFERENT)
        self._lembrar()

    def definir_ocultos(self, sim):
        self.ocultos = sim
        self.filtro.changed(Gtk.FilterChange.DIFFERENT)

    def filtrar_texto(self, t):
        self.texto = normalizar(t.strip())
        self.filtro.changed(Gtk.FilterChange.DIFFERENT)

    def _mudou(self, *a):
        self._atualizar_vazio()
        self.emit("contagem")

    def _atualizar_vazio(self):
        carregando = bool(self.dirlist and self.dirlist.is_loading())
        self.carregando.set_visible(carregando and self.ordenado.get_n_items() == 0)
        erro = self.dirlist.get_error() if self.dirlist else None
        if erro:
            self.vazio.set_label(_t("Não foi possível abrir esta pasta.\n") + erro.message)
            self.vazio.set_visible(True)
        elif not carregando and self.ordenado.get_n_items() == 0:
            self.vazio.set_label(_t("Nenhum item corresponde à pesquisa.") if self.texto else _t("Esta pasta está vazia."))
            self.vazio.set_visible(True)
        else:
            self.vazio.set_visible(False)

    def recarregar(self):
        if self.dirlist:
            self.dirlist.set_file(None)
            self.dirlist.set_file(self.gfile)

    # ── views ──────────────────────────────────────────────────────────────
    def _montar_view(self):
        v = self.visao
        if v == "detalhes":
            self.view = self._columnview()
        elif v == "lista":
            self.view = Gtk.ListView(model=self.selecao, factory=self._fabrica(self._item_lista, self._ligar_lista),
                                     css_classes=["arquivos"], enable_rubberband=True)
        else:
            self.view = Gtk.GridView(model=self.selecao, max_columns=64, min_columns=1, enable_rubberband=True,
                                     css_classes=["arquivos"],
                                     factory=self._fabrica(self._item_bloco if v == "blocos" else self._item_grade,
                                                           self._ligar_bloco if v == "blocos" else self._ligar_grade))
        self.view.set_single_click_activate(self.janela.cfg.get("cliqueUnico", False))
        self.view.connect("activate", self._ativado)
        self.rolagem.set_child(self.view)

    def definir_visao(self, v):
        if v == self.visao:
            return
        self.visao = v
        sel = self.posicoes()
        self._montar_view()
        for p in sel:
            self.selecao.select_item(p, False)
        self._lembrar()

    def _lembrar(self):
        """Visão e ordem por pasta, como o Windows."""
        if not self.gfile:
            return
        cfg = self.janela.cfg
        d = cfg.setdefault("visaoPorPasta", {})
        d[self.gfile.get_uri()] = {"visao": self.visao, "ordem": self.ordem, "desc": self.desc}
        if len(d) > 400:
            for k in list(d)[:100]:
                d.pop(k)
        self.janela.salvar_config()

    def _fabrica(self, criar, ligar):
        f = Gtk.SignalListItemFactory()
        f.connect("setup", lambda _f, li: criar(li))
        f.connect("bind", lambda _f, li: ligar(li))
        return f

    def _ativado(self, view, pos):
        info = self.ordenado.get_item(pos)
        if info:
            self.emit("abrir", info, False)

    # ícone ou miniatura
    def _icone(self, info, img, pic, tam, grande_mini=False):
        img.set_from_gicon(info.get_icon() or Gio.ThemedIcon.new("text-x-generic"))
        img.set_pixel_size(tam)
        img.set_visible(True)
        pic.set_visible(False)
        gfile = u.arquivo_de(info)
        caminho = gfile.get_path() if gfile else None
        if u.eh_pasta(info) and caminho in u.ICONE_PASTA:
            img.set_from_icon_name(u.ICONE_PASTA[caminho])
        if tam >= 24 and u.miniaturavel(u.tipo(info)):
            token = object()
            img._token = token

            def pronto(path):
                if getattr(img, "_token", None) is token:
                    pic.set_filename(path)
                    pic.set_visible(True)
                    img.set_visible(False)
                return False
            u.pedir_miniatura(info, tam > 128, pronto)
        else:
            img._token = None

    def _arrastavel(self, w):
        src = Gtk.DragSource(actions=Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        src.connect("prepare", self._preparar_arrasto, w)
        w.add_controller(src)

    def _alvo_soltar(self, w):
        alvo = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        alvo.connect("drop", lambda t, val, x, y: self._soltar_em(val, getattr(w, "_info", None), t))
        w.add_controller(alvo)

    def _item_grade(self, li):
        tam, larg = GRADE[self.visao]
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, width_request=larg)
        quadro = Gtk.Box(halign=Gtk.Align.CENTER, height_request=tam, width_request=tam)
        img = Gtk.Image(halign=Gtk.Align.CENTER, valign=Gtk.Align.END, hexpand=True)
        pic = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, can_shrink=True, width_request=tam, height_request=tam,
                          visible=False)
        quadro.append(img)
        quadro.append(pic)
        rot = Gtk.Label(wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, lines=2, ellipsize=Pango.EllipsizeMode.END,
                        justify=Gtk.Justification.CENTER, max_width_chars=1, css_classes=["nome-arquivo"],
                        width_request=larg - 8)
        caixa.append(quadro)
        caixa.append(rot)
        caixa._img, caixa._pic, caixa._rot = img, pic, rot
        self._arrastavel(caixa)
        self._alvo_soltar(caixa)
        li.set_child(caixa)

    def _ligar_grade(self, li):
        caixa, info = li.get_child(), li.get_item()
        caixa._info, caixa._pos = info, li.get_position()
        tam = GRADE[self.visao][0]
        self._icone(info, caixa._img, caixa._pic, tam)
        caixa._rot.set_label(self._nome(info))
        caixa.set_tooltip_text(self._dica(info))
        self._estilo(caixa, info)

    def _item_bloco(self, li):
        caixa = Gtk.Box(spacing=10, width_request=270, margin_top=2, margin_bottom=2)
        img = Gtk.Image(pixel_size=48)
        pic = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, width_request=48, height_request=48, visible=False)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER, spacing=1)
        rot = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END, max_width_chars=26)
        tipo = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END, css_classes=["legenda"], max_width_chars=28)
        tam = Gtk.Label(xalign=0, css_classes=["legenda"])
        for w in (rot, tipo, tam):
            txt.append(w)
        caixa.append(img)
        caixa.append(pic)
        caixa.append(txt)
        caixa._img, caixa._pic, caixa._rot, caixa._tipo, caixa._tam = img, pic, rot, tipo, tam
        self._arrastavel(caixa)
        self._alvo_soltar(caixa)
        li.set_child(caixa)

    def _ligar_bloco(self, li):
        caixa, info = li.get_child(), li.get_item()
        caixa._info, caixa._pos = info, li.get_position()
        self._icone(info, caixa._img, caixa._pic, 48)
        caixa._rot.set_label(self._nome(info))
        caixa._tipo.set_label(u.tipo_desc(info))
        caixa._tam.set_label("" if u.eh_pasta(info) else u.tamanho(info.get_size()))
        caixa.set_tooltip_text(self._dica(info))
        self._estilo(caixa, info)

    def _item_lista(self, li):
        caixa = Gtk.Box(spacing=10)
        img = Gtk.Image(pixel_size=20)
        rot = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.MIDDLE, hexpand=True)
        caixa.append(img)
        caixa.append(rot)
        caixa._img, caixa._rot = img, rot
        self._arrastavel(caixa)
        self._alvo_soltar(caixa)
        li.set_child(caixa)

    def _ligar_lista(self, li):
        caixa, info = li.get_child(), li.get_item()
        caixa._info, caixa._pos = info, li.get_position()
        caixa._img.set_from_gicon(info.get_icon() or Gio.ThemedIcon.new("text-x-generic"))
        gfile = u.arquivo_de(info)
        if u.eh_pasta(info) and gfile and gfile.get_path() in u.ICONE_PASTA:
            caixa._img.set_from_icon_name(u.ICONE_PASTA[gfile.get_path()])
        u.mini_no_icone(info, caixa._img)
        caixa._rot.set_label(self._nome(info))
        caixa.set_tooltip_text(self._dica(info))
        self._estilo(caixa, info)

    def _columnview(self):
        cv = Gtk.ColumnView(model=self.selecao, css_classes=["arquivos"], enable_rubberband=True,
                            show_column_separators=False, reorderable=True)
        colunas = [("nome", _t("Nome"), True), ("data", _t("Data de modificação"), False), ("tipo", _t("Tipo"), False),
                   ("tamanho", _t("Tamanho"), False)]
        if self.mostrar_local:
            colunas.insert(1, ("local", _t("Local"), False))
        if self.gfile and self.gfile.get_uri_scheme() == "trash":
            colunas = [("nome", _t("Nome"), True), ("origem", _t("Local original"), False), ("excluido", _t("Data da exclusão"), False),
                       ("tamanho", _t("Tamanho"), False)]
        self._colunas = {}
        for chave, titulo, expande in colunas:
            f = Gtk.SignalListItemFactory()
            f.connect("setup", self._cel_setup, chave)
            f.connect("bind", self._cel_bind, chave)
            col = Gtk.ColumnViewColumn(title=titulo, factory=f, expand=expande, resizable=True)
            if chave in ORDENS:
                col.set_sorter(Gtk.CustomSorter.new(lambda a, b, *_: 0))
            if not expande:
                col.set_fixed_width({"data": 170, "tipo": 190, "tamanho": 100, "local": 260,
                                     "origem": 260, "excluido": 170}.get(chave, 140))
            cv.append_column(col)
            self._colunas[chave] = col
        # Cabeçalho clicado: vira a ordem da vista (pastas sempre primeiro)
        col = self._colunas.get(self.ordem)
        if col:
            cv.sort_by_column(col, Gtk.SortType.DESCENDING if self.desc else Gtk.SortType.ASCENDING)
        cv.get_sorter().connect("changed", self._cabecalho_ordem)
        return cv

    def _cabecalho_ordem(self, sorter, *_):
        col = sorter.get_primary_sort_column()
        if not col:
            return
        chave = next((k for k, c in self._colunas.items() if c == col), None)
        if chave in ORDENS:
            desc = sorter.get_primary_sort_order() == Gtk.SortType.DESCENDING
            if chave != self.ordem or desc != self.desc:
                self.definir_ordem(chave, desc)

    def _cel_setup(self, f, li, chave):
        if chave == "nome":
            caixa = Gtk.Box(spacing=8)
            img = Gtk.Image(pixel_size=20)
            rot = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END)
            caixa.append(img)
            caixa.append(rot)
            caixa._img, caixa._rot = img, rot
            self._arrastavel(caixa)
            self._alvo_soltar(caixa)
            li.set_child(caixa)
        else:
            rot = Gtk.Label(xalign=0, ellipsize=Pango.EllipsizeMode.END, css_classes=["secundario"])
            if chave == "tamanho":
                rot.set_xalign(1)
            li.set_child(rot)

    def _cel_bind(self, f, li, chave):
        info, w = li.get_item(), li.get_child()
        w._info, w._pos = info, li.get_position()
        if chave == "nome":
            w._img.set_from_gicon(info.get_icon() or Gio.ThemedIcon.new("text-x-generic"))
            gfile = u.arquivo_de(info)
            if u.eh_pasta(info) and gfile and gfile.get_path() in u.ICONE_PASTA:
                w._img.set_from_icon_name(u.ICONE_PASTA[gfile.get_path()])
            u.mini_no_icone(info, w._img)
            w._rot.set_label(self._nome(info))
            w.set_tooltip_text(self._dica(info))
            self._estilo(w, info)
        elif chave == "data":
            w.set_label(u.data(info.get_modification_date_time()))
        elif chave == "tipo":
            w.set_label(u.tipo_desc(info))
        elif chave == "tamanho":
            w.set_label("" if u.eh_pasta(info) else u.tamanho(info.get_size()))
        elif chave == "local":
            g = u.arquivo_de(info)
            p = g.get_parent().get_path() if g and g.get_parent() else ""
            w.set_label((p or "").replace(str(u.HOME), "~", 1))
        elif chave == "origem":
            o = info.get_attribute_byte_string("trash::orig-path") or ""
            w.set_label(GLib.path_get_dirname(o).replace(str(u.HOME), "~", 1) if o else "")
        elif chave == "excluido":
            d = info.get_deletion_date()
            w.set_label(u.data(d) if d else "")

    def _nome(self, info):
        n = info.get_display_name() or info.get_name() or ""
        if not self.janela.cfg.get("extensoes", True) and not u.eh_pasta(info) and "." in n[1:]:
            n = n.rsplit(".", 1)[0]
        return n

    def _dica(self, info):
        partes = [info.get_display_name() or "", _t("Tipo: ") + u.tipo_desc(info)]
        if not u.eh_pasta(info):
            partes.append(_t("Tamanho: ") + u.tamanho(info.get_size()))
        partes.append(_t("Modificado: ") + u.data(info.get_modification_date_time()))
        return "\n".join(partes)

    def _estilo(self, w, info):
        n = info.get_display_name() or ""
        if info.get_is_hidden() or n.startswith("."):
            w.add_css_class("oculto")
        else:
            w.remove_css_class("oculto")
        g = u.arquivo_de(info)
        if g and g.get_uri() in self.janela.recortados:
            w.add_css_class("recortado")
        else:
            w.remove_css_class("recortado")

    # ── seleção ────────────────────────────────────────────────────────────
    def posicoes(self):
        bits = self.selecao.get_selection()
        out = []
        ok, it, p = Gtk.BitsetIter.init_first(bits)
        while ok:
            out.append(p)
            ok, p = it.next()
        return out

    def selecionados(self):
        return [self.ordenado.get_item(p) for p in self.posicoes()]

    def selecionar_tudo(self):
        self.selecao.select_all()

    def inverter_selecao(self):
        n = self.ordenado.get_n_items()
        sel = set(self.posicoes())
        self.selecao.unselect_all()
        for p in range(n):
            if p not in sel:
                self.selecao.select_item(p, False)

    def selecionar_nome(self, nome):
        for p in range(self.ordenado.get_n_items()):
            if self.ordenado.get_item(p).get_name() == nome:
                self.selecao.select_item(p, True)
                self.rolar_ate(p)
                return True
        return False

    def selecionar_quando_aparecer(self, nome, tentativas=40):
        """Arquivo recém-criado: seleciona quando o monitor da pasta trouxer."""
        def tentar():
            nonlocal tentativas
            tentativas -= 1
            return not self.selecionar_nome(nome) and tentativas > 0
        GLib.timeout_add(100, tentar)

    def rolar_ate(self, p):
        try:
            self.view.scroll_to(p, Gtk.ListScrollFlags.FOCUS, None)
        except Exception:  # noqa: BLE001
            pass

    def focar(self):
        self.view.grab_focus()

    # ── controles: botão direito, meio, digitar, Ctrl+roda, soltar ─────────
    def _controles(self):
        dir_ = Gtk.GestureClick(button=3)
        dir_.connect("pressed", self._clique_direito)
        self.rolagem.add_controller(dir_)
        meio = Gtk.GestureClick(button=2)
        meio.connect("pressed", self._clique_meio)
        self.rolagem.add_controller(meio)
        teclas = Gtk.EventControllerKey()
        teclas.connect("key-pressed", self._tecla)
        self.add_controller(teclas)
        roda = Gtk.EventControllerScroll(flags=Gtk.EventControllerScrollFlags.VERTICAL)
        roda.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        roda.connect("scroll", self._roda)
        self.add_controller(roda)
        alvo = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        alvo.connect("drop", lambda t, val, x, y: self._soltar_em(val, None, t))
        self.rolagem.add_controller(alvo)

    def _item_em(self, x, y):
        w = self.rolagem.pick(x, y, Gtk.PickFlags.DEFAULT)
        while w is not None and w is not self.rolagem:
            if hasattr(w, "_pos") and hasattr(w, "_info"):
                return w
            w = w.get_parent()
        return None

    def _clique_direito(self, g, n, x, y):
        w = self._item_em(x, y)
        if w is not None:
            if not self.selecao.is_selected(w._pos):
                self.selecao.select_item(w._pos, True)
        else:
            self.selecao.unselect_all()
        jx, jy = u.coords(self.rolagem, self.janela.raiz, x, y)
        self.emit("menu", jx, jy, w is not None)
        g.set_state(Gtk.EventSequenceState.CLAIMED)

    def _clique_meio(self, g, n, x, y):
        w = self._item_em(x, y)
        if w is not None and u.eh_pasta(w._info):
            self.emit("abrir", w._info, True)

    def _tecla(self, ctl, keyval, code, estado):
        if estado & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK | Gdk.ModifierType.SUPER_MASK):
            return False
        ch = Gdk.keyval_to_unicode(keyval)
        if not ch or ch < 32 or keyval in (Gdk.KEY_space,) and not self._busca_tecla:
            return False
        agora = u.tempo()
        if agora - self._busca_tempo > 1.0:
            self._busca_tecla = ""
        self._busca_tempo = agora
        self._busca_tecla += normalizar(chr(ch))
        for p in range(self.ordenado.get_n_items()):
            if normalizar(self.ordenado.get_item(p).get_display_name()).startswith(self._busca_tecla):
                self.selecao.select_item(p, True)
                self.rolar_ate(p)
                break
        return True

    def _roda(self, ctl, dx, dy):
        if not (ctl.get_current_event_state() & Gdk.ModifierType.CONTROL_MASK):
            return False
        self.zoom(-1 if dy > 0 else 1)
        return True

    def zoom(self, d):
        ordem = ["detalhes", "lista", "pequena", "media", "grande", "extragrande"]
        atual = ordem.index(self.visao) if self.visao in ordem else 3
        nova = ordem[max(0, min(len(ordem) - 1, atual + d))]
        self.janela.definir_visao(nova)

    def _preparar_arrasto(self, src, x, y, w):
        info = getattr(w, "_info", None)
        if info is None:
            return None
        if not self.selecao.is_selected(w._pos):
            self.selecao.select_item(w._pos, True)
        arquivos = [u.arquivo_de(i) for i in self.selecionados() if u.arquivo_de(i)]
        paint = Gtk.WidgetPaintable.new(getattr(w, "_img", w))
        src.set_icon(paint, 16, 16)
        return Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_list(arquivos))

    def _soltar_em(self, valor, info_alvo, alvo):
        arquivos = valor.get_files() if valor else []
        if info_alvo is not None and u.eh_pasta(info_alvo):
            destino = u.arquivo_de(info_alvo).get_path()
        elif self.gfile and self.gfile.get_path():
            destino = self.gfile.get_path()
        else:
            return False
        caminhos = [f.get_path() for f in arquivos if f.get_path()]
        if not caminhos or not destino or destino in caminhos:
            return False
        estado = alvo.get_current_event_state()
        if estado & Gdk.ModifierType.CONTROL_MASK:
            copiar = True
        elif estado & Gdk.ModifierType.SHIFT_MASK:
            copiar = False
        else:  # mesmo disco: move; outro disco: copia (como o Windows)
            import os
            try:
                copiar = os.stat(caminhos[0]).st_dev != os.stat(destino).st_dev
            except OSError:
                copiar = True
        self.emit("soltar", caminhos, destino, copiar)
        return True
