#!/usr/bin/env python3
"""Gerenciador de Tarefas — inspirado no do Windows 11 (GTK4/libadwaita).

Páginas: Processos (apps com janela, segundo plano e sistema, agrupados),
Desempenho (CPU, memória, discos, rede com gráficos), Aplicativos de
inicialização, Detalhes (todos os processos) e Serviços (systemd).
Abre com Ctrl+Shift+Esc ou pelo menu do botão direito da barra de tarefas.
"""
import os
import re
import shlex
import signal
import subprocess
import sys
from collections import deque
from configparser import ConfigParser
from pathlib import Path

import gi
import sys as _sys, os as _os  # noqa: E401
_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))
from simba_i18n import t as _t, n as _n, DECIMAL as _DEC  # noqa: E402  (traduções: /usr/share/simba-apps/idiomas)

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Pango  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import coleta as C  # noqa: E402
import warnings  # noqa: E402
warnings.filterwarnings("ignore", category=DeprecationWarning)

APP_ID = "com.simba.GerenciadorTarefas"
HOME = Path.home()

CORES = {
    "cpu": (0.30, 0.66, 1.0),
    "mem": (0.69, 0.42, 0.88),
    "disco": (0.36, 0.72, 0.36),
    "rede": (0.86, 0.55, 0.22),
}

CSS = """
.navegacao { background: alpha(@window_fg_color, 0.03); padding: 6px 4px; }
.navegacao row { border-radius: 6px; margin: 2px 4px; padding: 0; min-height: 38px; }
.navegacao row:selected { background: alpha(@window_fg_color, 0.08); color: @window_fg_color; }
.navegacao row .pilula { min-width: 3px; min-height: 16px; border-radius: 2px; background: transparent; }
.navegacao row:selected .pilula { background: @accent_bg_color; }
.titulo-pagina { font-size: 20px; font-weight: 600; }
.barra-pagina { padding: 14px 18px 10px 18px; }
columnview { background: transparent; }
columnview > header > button { padding: 4px 8px; font-weight: 400; }
columnview row:selected { background: alpha(@accent_bg_color, 0.16); }
columnview row:selected:focus-within { background: alpha(@accent_bg_color, 0.22); }
.num { font-feature-settings: "tnum"; }
.calor { padding: 0 8px; min-height: 26px; }
.calor1 { background: alpha(#ffb900, 0.10); }
.calor2 { background: alpha(#ffb900, 0.20); }
.calor3 { background: alpha(#ffb900, 0.32); }
.calor4 { background: alpha(#ff8c00, 0.42); }
.calor5 { background: alpha(#e81123, 0.45); }
.grupo-titulo { font-weight: 700; }
.cartao-desempenho { border-radius: 8px; padding: 6px; }
.lista-desempenho row { border-radius: 8px; margin: 2px 6px; padding: 6px; }
.lista-desempenho row:selected { background: alpha(@window_fg_color, 0.08); color: @window_fg_color; }
.rotulo-fraco { opacity: 0.65; font-size: 12px; }
.valor-grande { font-size: 18px; font-weight: 400; }
.titulo-desempenho { font-size: 26px; font-weight: 600; }
.subtitulo-desempenho { font-size: 15px; opacity: 0.8; }
"""


# ── modelo ───────────────────────────────────────────────────────────────────
class Linha(GObject.Object):
    """Uma linha de tabela (grupo, app, processo ou serviço)."""
    __gsignals__ = {"mudou": (GObject.SignalFlags.RUN_FIRST, None, ())}

    def __init__(self, chave, tipo, expandivel=False):
        super().__init__()
        self.chave = chave
        self.tipo = tipo  # grupo | app | proc | servico | inicio
        self.nome = ""
        self.status = ""
        self.cpu = 0.0
        self.mem = 0.0
        self.disco = 0.0
        self.pid = 0
        self.pids = []
        self.icone = None
        self.rank = 0
        self.usuario = ""
        self.uid = C.MEU_UID
        self.cmd = ""
        self.threads = 0
        self.extra = {}
        self.filhos = Gio.ListStore(item_type=Linha) if expandivel else None


def item_de(list_item):
    it = list_item.get_item()
    if isinstance(it, Gtk.TreeListRow):
        it = it.get_item()
    return it


def sincronizar(store, itens):
    """Deixa o store com exatamente estes objetos (ordem fica para o sorter)."""
    quero = {id(x) for x in itens}
    for i in reversed(range(store.get_n_items())):
        if id(store.get_item(i)) not in quero:
            store.remove(i)
    tem = {id(store.get_item(i)) for i in range(store.get_n_items())}
    novos = [x for x in itens if id(x) not in tem]
    if novos:
        store.splice(store.get_n_items(), 0, novos)


def calor(v, limites):
    n = 0
    for i, lim in enumerate(limites):
        if v >= lim:
            n = i + 1
    return n


# ── colunas ──────────────────────────────────────────────────────────────────
def coluna_texto(titulo, texto, *, direita=False, expandir=False, largura=None, calor_de=None, sorter=None):
    fab = Gtk.SignalListItemFactory()

    def setup(_f, li):
        caixa = Gtk.Box()
        caixa.add_css_class("calor")
        rot = Gtk.Label(xalign=1 if direita else 0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
        if direita:
            rot.add_css_class("num")
        caixa.append(rot)
        li.set_child(caixa)
        caixa.rot = rot
        caixa.lig = None

    def atualizar(caixa, it):
        caixa.rot.set_text(texto(it))
        for i in range(1, 6):
            caixa.remove_css_class(f"calor{i}")
        if calor_de:
            n = calor_de(it)
            if n:
                caixa.add_css_class(f"calor{n}")

    def bind(_f, li):
        caixa, it = li.get_child(), item_de(li)
        if it is None:
            return
        atualizar(caixa, it)
        caixa.lig = (it, it.connect("mudou", lambda o: atualizar(caixa, o)))

    def unbind(_f, li):
        caixa = li.get_child()
        if caixa.lig:
            caixa.lig[0].disconnect(caixa.lig[1])
            caixa.lig = None

    fab.connect("setup", setup)
    fab.connect("bind", bind)
    fab.connect("unbind", unbind)
    col = Gtk.ColumnViewColumn(title=titulo, factory=fab)
    col.set_resizable(True)
    if expandir:
        col.set_expand(True)
    if largura:
        col.set_fixed_width(largura)
    if sorter:
        col.set_sorter(sorter)
    return col


def coluna_nome(arvore=True, sorter=None, largura=320):
    fab = Gtk.SignalListItemFactory()

    def setup(_f, li):
        caixa = Gtk.Box(spacing=8)
        caixa.add_css_class("calor")
        img = Gtk.Image(pixel_size=16)
        rot = Gtk.Label(xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
        caixa.append(img)
        caixa.append(rot)
        if arvore:
            exp = Gtk.TreeExpander()
            exp.set_child(caixa)
            exp.set_indent_for_icon(True)
            li.set_child(exp)
        else:
            li.set_child(caixa)
        caixa.img, caixa.rot, caixa.lig = img, rot, None

    def caixa_de(li):
        w = li.get_child()
        return w.get_child() if isinstance(w, Gtk.TreeExpander) else w

    def atualizar(caixa, it):
        caixa.rot.set_text(it.nome)
        if it.tipo == "grupo":
            caixa.rot.add_css_class("grupo-titulo")
            caixa.img.set_visible(False)
        else:
            caixa.rot.remove_css_class("grupo-titulo")
            caixa.img.set_visible(True)
            if it.icone:
                caixa.img.set_from_gicon(it.icone)
            else:
                caixa.img.set_from_icon_name("application-x-executable-symbolic")

    def bind(_f, li):
        if arvore:
            li.get_child().set_list_row(li.get_item())
        caixa, it = caixa_de(li), item_de(li)
        if it is None:
            return
        atualizar(caixa, it)
        caixa.lig = (it, it.connect("mudou", lambda o: atualizar(caixa, o)))

    def unbind(_f, li):
        caixa = caixa_de(li)
        if caixa.lig:
            caixa.lig[0].disconnect(caixa.lig[1])
            caixa.lig = None

    fab.connect("setup", setup)
    fab.connect("bind", bind)
    fab.connect("unbind", unbind)
    col = Gtk.ColumnViewColumn(title=_t("Nome"), factory=fab)
    col.set_resizable(True)
    col.set_fixed_width(largura)
    if sorter:
        col.set_sorter(sorter)
    return col


class Ordenador:
    """Sorters por coluna que mantêm os grupos (Aplicativos, Segundo plano,
    Sistema) na ordem fixa, independente da direção da ordenação."""

    def __init__(self):
        self.view = None

    def _desc(self):
        s = self.view.get_sorter() if self.view else None
        return bool(s) and s.get_primary_sort_order() == Gtk.SortType.DESCENDING

    def fazer(self, chave):
        def cmp(a, b, _d=None):
            if a.tipo == "grupo" and b.tipo == "grupo":
                r = (a.rank > b.rank) - (a.rank < b.rank)
                if self._desc():
                    r = -r
            else:
                va, vb = chave(a), chave(b)
                r = (va > vb) - (va < vb)
            return Gtk.Ordering.SMALLER if r < 0 else (Gtk.Ordering.LARGER if r > 0 else Gtk.Ordering.EQUAL)
        return Gtk.CustomSorter.new(cmp, None)


# ── nomes e ícones de apps ───────────────────────────────────────────────────
class Apps:
    def __init__(self):
        self.idx = {}
        self.por_url = []
        for a in Gio.AppInfo.get_all():
            if not isinstance(a, Gio.DesktopAppInfo):
                continue
            ident = (a.get_id() or "").removesuffix(".desktop").lower()
            for k in (ident, (a.get_startup_wm_class() or "").lower(),
                      os.path.basename((a.get_executable() or "")).lower()):
                if k and k not in self.idx:
                    self.idx[k] = a
            cl = a.get_commandline() or ""
            m = re.search(r"--app=https?://([^/\s\"']+)", cl)
            if m:
                self.por_url.append((m.group(1).lower(), a))

    def de_classe(self, classe):
        c = (classe or "").lower()
        if c in self.idx:
            return self.idx[c]
        # Web apps do Brave: brave-<host com __ no lugar de />-Default
        m = re.match(r"(?:brave|chrome|chromium)-(.+?)(?:__.*)?-default$", c)
        if m:
            host = m.group(1)
            for h, a in self.por_url:
                if h == host:
                    return a
        for k, a in self.idx.items():
            if c and (c.endswith("." + k) or k.endswith("." + c)):
                return a
        return None


# ── janela ───────────────────────────────────────────────────────────────────
class Janela(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_t("Gerenciador de Tarefas"))
        self.set_default_size(1060, 700)
        self.apps = Apps()
        self.coletor = C.Processos()
        self.procs = {}
        self.cache = {}
        self.cache_det = {}
        self.cache_srv = {}
        self.busca = ""
        self.desc_cache = {}

        caixa_raiz = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        cab = Adw.HeaderBar()
        titulo = Gtk.Box(spacing=8)
        ic = Gtk.Image.new_from_icon_name("com.simba.GerenciadorTarefas")
        ic.set_pixel_size(18)
        titulo.append(ic)
        titulo.append(Gtk.Label(label=_t("Gerenciador de Tarefas")))
        cab.pack_start(titulo)
        self.pesquisa = Gtk.SearchEntry(placeholder_text=_t("Digite um nome, editor ou PID para pesquisar"), width_chars=44)
        self.pesquisa.connect("search-changed", self._buscar)
        cab.set_title_widget(self.pesquisa)
        caixa_raiz.append(cab)

        corpo = Gtk.Box(vexpand=True)
        caixa_raiz.append(corpo)
        self.set_content(caixa_raiz)

        # Navegação lateral
        nav_caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        nav_caixa.add_css_class("navegacao")
        menu = Gtk.Button(icon_name="open-menu-symbolic", halign=Gtk.Align.START, margin_start=6, margin_bottom=4)
        menu.add_css_class("flat")
        menu.connect("clicked", self._alternar_nav)
        nav_caixa.append(menu)
        self.nav = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, vexpand=True)
        self.nav.add_css_class("navegacao")
        nav_caixa.append(self.nav)
        corpo.append(nav_caixa)
        corpo.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))

        self.stack = Gtk.Stack(hexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE, transition_duration=120)
        corpo.append(self.stack)

        self.rotulos_nav = []
        paginas = [
            ("processos", _t("Processos"), "view-grid-symbolic", self._pagina_processos()),
            ("desempenho", _t("Desempenho"), "power-profile-performance-symbolic", self._pagina_desempenho()),
            ("inicializacao", _t("Aplicativos de inicialização"), "system-reboot-symbolic", self._pagina_inicio()),
            ("detalhes", _t("Detalhes"), "view-list-bullet-symbolic", self._pagina_detalhes()),
            ("servicos", _t("Serviços"), "emblem-system-symbolic", self._pagina_servicos()),
        ]
        for nome, rotulo, icone, w in paginas:
            self.stack.add_named(w, nome)
            linha = Gtk.ListBoxRow()
            linha.nome = nome
            b = Gtk.Box(spacing=12)
            pil = Gtk.Box(valign=Gtk.Align.CENTER)
            pil.add_css_class("pilula")
            b.append(pil)
            b.append(Gtk.Image.new_from_icon_name(icone))
            r = Gtk.Label(label=rotulo, xalign=0, margin_end=12)
            self.rotulos_nav.append(r)
            b.append(r)
            linha.set_child(b)
            linha.set_tooltip_text(rotulo)
            self.nav.append(linha)
        # Seleciona antes de conectar: a 1ª coleta de processos fica para depois da
        # janela aparecer (abre ~100 ms mais rápido; a tabela enche no quadro seguinte).
        self.nav.select_row(self.nav.get_row_at_index(0))
        self.nav.connect("row-selected", self._trocar_pagina)

        # Atalhos
        tecla = Gtk.EventControllerKey()
        tecla.connect("key-pressed", self._tecla)
        self.add_controller(tecla)

        self._tick_desempenho()
        GLib.idle_add(lambda: (self._tick_processos(), False)[1])
        GLib.timeout_add(1000, self._tick_desempenho)
        GLib.timeout_add(1500, self._tick_processos)
        GLib.timeout_add(4000, self._tick_servicos)

    # ── geral ────────────────────────────────────────────────────────────────
    def _alternar_nav(self, _b):
        v = not self.rotulos_nav[0].get_visible()
        for r in self.rotulos_nav:
            r.set_visible(v)

    def _trocar_pagina(self, _lb, linha):
        if not linha:
            return
        self.stack.set_visible_child_name(linha.nome)
        self.pesquisa.set_sensitive(linha.nome in ("processos", "detalhes", "servicos", "inicializacao"))
        if linha.nome == "servicos":
            self._tick_servicos(forcar=True)
        elif linha.nome == "inicializacao":
            self._carregar_inicio()
        elif linha.nome in ("processos", "detalhes"):
            self._tick_processos()

    def _tecla(self, _c, kv, _code, mod):
        ctrl = mod & Gdk.ModifierType.CONTROL_MASK
        if ctrl and kv in (Gdk.KEY_f, Gdk.KEY_F):
            self.pesquisa.grab_focus()
            return True
        if kv == Gdk.KEY_Delete and not self.pesquisa.has_focus():
            pag = self.stack.get_visible_child_name()
            if pag == "processos":
                self._finalizar(self._sel_proc())
                return True
            if pag == "detalhes":
                self._finalizar(self._sel_det())
                return True
        if kv == Gdk.KEY_Escape and self.pesquisa.get_text():
            self.pesquisa.set_text("")
            return True
        return False

    def _buscar(self, e):
        self.busca = e.get_text().strip().lower()
        pag = self.stack.get_visible_child_name()
        if pag == "servicos":
            self._tick_servicos(forcar=True)
        elif pag == "inicializacao":
            self._carregar_inicio()
        else:
            self._tick_processos()

    def _bate(self, *textos):
        if not self.busca:
            return True
        return any(self.busca in str(t).lower() for t in textos if t)

    def _barra_pagina(self, titulo, botoes):
        b = Gtk.Box(spacing=6)
        b.add_css_class("barra-pagina")
        t = Gtk.Label(label=titulo, xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END)
        t.add_css_class("titulo-pagina")
        b.append(t)
        for w in botoes:
            b.append(w)
        return b

    @staticmethod
    def _botao(rotulo, icone, cb, sensivel=True):
        bt = Gtk.Button()
        c = Gtk.Box(spacing=6)
        c.append(Gtk.Image.new_from_icon_name(icone))
        c.append(Gtk.Label(label=rotulo))
        bt.set_child(c)
        bt.add_css_class("flat")
        bt.set_sensitive(sensivel)
        bt.connect("clicked", lambda *_: cb())
        return bt

    def _menu_contexto(self, view, itens):
        """Clique direito numa linha: seleciona e abre um menu com `itens`
        [(rótulo, função)] calculados na hora a partir da linha."""
        pop = Gtk.PopoverMenu()
        pop.set_parent(view)
        pop.set_has_arrow(False)
        pop.set_halign(Gtk.Align.START)
        grupo = Gio.SimpleActionGroup()
        view.insert_action_group("ctx", grupo)
        clique = Gtk.GestureClick(button=3)

        def pressionado(g, _n, x, y):
            alvo = view.pick(x, y, Gtk.PickFlags.DEFAULT)
            # sobe até a célula para descobrir a linha
            w = alvo
            while w is not None and w is not view and not hasattr(w, "lig"):
                w = w.get_parent()
            it = w.lig[0] if (w is not None and getattr(w, "lig", None)) else None
            if it is None:
                return
            self._selecionar_item(view, it)
            entradas = itens(it)
            if not entradas:
                return
            m = Gio.Menu()
            for i, (rot, fn) in enumerate(entradas):
                nome = f"a{i}"
                if grupo.lookup_action(nome):
                    grupo.remove_action(nome)
                acao = Gio.SimpleAction.new(nome, None)
                acao.connect("activate", lambda *_a, f=fn: f())
                grupo.add_action(acao)
                m.append(rot, f"ctx.{nome}")
            pop.set_menu_model(m)
            r = Gdk.Rectangle()
            r.x, r.y, r.width, r.height = int(x), int(y), 1, 1
            pop.set_pointing_to(r)
            pop.popup()
            g.set_state(Gtk.EventSequenceState.CLAIMED)

        clique.connect("pressed", pressionado)
        view.add_controller(clique)

    @staticmethod
    def _selecionar_item(view, it):
        sel = view.get_model()
        for i in range(sel.get_n_items()):
            x = sel.get_item(i)
            if isinstance(x, Gtk.TreeListRow):
                x = x.get_item()
            if x is it:
                sel.set_selected(i)
                return

    @staticmethod
    def _item_selecionado(view):
        x = view.get_model().get_selected_item()
        if isinstance(x, Gtk.TreeListRow):
            x = x.get_item()
        return x

    def _executar_nova(self):
        d = Adw.AlertDialog(heading=_t("Criar nova tarefa"),
                            body=_t("Digite o nome de um programa, pasta ou endereço para abrir."))
        e = Gtk.Entry(placeholder_text=_t("ex.: nautilus, firefox, ~/Downloads"), activates_default=True)
        d.set_extra_child(e)
        d.add_response("cancelar", _t("Cancelar"))
        d.add_response("ok", "OK")
        d.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        d.set_default_response("ok")

        def resp(_d, r):
            t = e.get_text().strip()
            if r != "ok" or not t:
                return
            alvo = os.path.expanduser(t)
            if os.path.exists(alvo) or re.match(r"^[a-z]+://", t):
                cmd = ["xdg-open", alvo]
            else:
                cmd = ["sh", "-c", t]
            subprocess.Popen(["uwsm-app", "--", *cmd], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        d.connect("response", resp)
        d.present(self)

    # ── finalizar ────────────────────────────────────────────────────────────
    def _finalizar(self, it, forcar=False):
        if not it or it.tipo == "grupo" or not it.pids:
            return
        procs = {p: self.procs[p] for p in it.pids if p in self.procs}
        if not procs:
            return
        alheios = [p for p, pr in procs.items() if pr.uid != C.MEU_UID]
        # Encerrar estes derruba a sessão inteira.
        criticos = [pr.nome for pr in procs.values()
                    if pr.nome.split(" ")[0] in ("systemd", "Hyprland", "start-hyprland", "uwsm", "Xwayland",
                                                 "dbus-broker", "dbus-daemon", "pipewire", "wireplumber",
                                                 "sddm", "sddm-helper", "quickshell")]

        def executar():
            sig = signal.SIGKILL if forcar else signal.SIGTERM
            negados = []
            for p in procs:
                try:
                    os.kill(p, sig)
                except PermissionError:
                    negados.append(p)
                except ProcessLookupError:
                    pass
            if negados:
                subprocess.Popen(["pkexec", "kill", f"-{int(sig)}", *map(str, negados)],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if not forcar:
                inicio = {p: pr.inicio for p, pr in procs.items()}
                GLib.timeout_add(3000, self._matar_restantes, inicio)
            GLib.timeout_add(300, self._tick_processos)

        if alheios or criticos:
            corpo = (_t("Este processo mantém a sua sessão funcionando (barra, janelas, som ou login). "
                     "Finalizá-lo pode fechar todos os seus aplicativos sem salvar.") if criticos else
                     _t("Este é um processo do sistema ou de outro usuário. Finalizá-lo pode deixar o sistema instável."))
            if alheios:
                corpo += _t(" Será pedida a senha de administrador.")
            d = Adw.AlertDialog(heading=_t("Deseja finalizar “%1”?", it.nome), body=corpo)
            d.add_response("cancelar", _t("Cancelar"))
            d.add_response("ok", _t("Finalizar processo"))
            d.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
            d.connect("response", lambda _d, r: executar() if r == "ok" else None)
            d.present(self)
        else:
            executar()

    def _matar_restantes(self, inicio):
        for p, ini in inicio.items():
            st = C._ler(f"/proc/{p}/stat")
            if st:
                campos = st[st.rfind(")") + 2:].split()
                if len(campos) > 19 and int(campos[19]) == ini:
                    try:
                        os.kill(p, signal.SIGKILL)
                    except OSError:
                        pass
        return False

    def _abrir_local(self, it):
        if not it or not it.pid:
            return
        try:
            exe = os.readlink(f"/proc/{it.pid}/exe")
        except OSError:
            return
        subprocess.Popen(["nautilus", "--select", exe], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # ── página Processos ─────────────────────────────────────────────────────
    def _pagina_processos(self):
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.bt_finalizar = self._botao(_t("Finalizar tarefa"), "process-stop-symbolic",
                                        lambda: self._finalizar(self._sel_proc()), False)
        caixa.append(self._barra_pagina(_t("Processos"), [
            self._botao(_t("Executar nova tarefa"), "document-new-symbolic", self._executar_nova),
            self.bt_finalizar,
        ]))

        self.raiz = Gio.ListStore(item_type=Linha)
        self.grupos = {}
        for rank, (k, nome) in enumerate((("apps", _t("Aplicativos")), ("bg", _t("Processos em segundo plano")),
                                          ("sys", _t("Processos do sistema")))):
            g = Linha("grupo:" + k, "grupo", expandivel=True)
            g.nome, g.rank, g.titulo = nome, rank, nome
            self.grupos[k] = g
            self.raiz.append(g)
        self.arvore = Gtk.TreeListModel.new(self.raiz, False, False, lambda it, *_: it.filhos)

        self.ord_proc = Ordenador()
        v = Gtk.ColumnView(show_row_separators=False, show_column_separators=True, reorderable=False)
        self.ord_proc.view = v
        self.col_nome = coluna_nome(True, self.ord_proc.fazer(lambda x: x.nome.lower()), 330)
        v.append_column(self.col_nome)
        v.append_column(coluna_texto(_t("Status"), lambda x: x.status, largura=110,
                                     sorter=self.ord_proc.fazer(lambda x: x.status)))
        self.col_cpu = coluna_texto("CPU", lambda x: "" if x.tipo == "grupo" else f"{x.cpu:.1f}%".replace(".", _DEC),
                                    direita=True, largura=90, sorter=self.ord_proc.fazer(lambda x: x.cpu),
                                    calor_de=lambda x: 0 if x.tipo == "grupo" else calor(x.cpu, (0.5, 5, 15, 40, 70)))
        self.col_mem = coluna_texto(_t("Memória"), lambda x: "" if x.tipo == "grupo" else C.fmt_mb(x.mem),
                                    direita=True, largura=120, sorter=self.ord_proc.fazer(lambda x: x.mem),
                                    calor_de=lambda x: 0 if x.tipo == "grupo" else calor(x.mem / 1048576, (50, 200, 500, 1000, 2000)))
        self.col_disco = coluna_texto(_t("Disco"), lambda x: "" if x.tipo == "grupo" else C.fmt_taxa(x.disco),
                                      direita=True, largura=100, sorter=self.ord_proc.fazer(lambda x: x.disco),
                                      calor_de=lambda x: 0 if x.tipo == "grupo" else calor(x.disco / 1048576, (0.1, 1, 5, 20, 80)))
        for c in (self.col_cpu, self.col_mem, self.col_disco):
            v.append_column(c)
        v.append_column(coluna_texto("", lambda x: "", expandir=True))

        ordem = Gtk.SortListModel.new(self.arvore, Gtk.TreeListRowSorter.new(v.get_sorter()))
        self.sel_proc = Gtk.SingleSelection(model=ordem, autoselect=False, can_unselect=True)
        self.sel_proc.connect("notify::selected", lambda *_: self.bt_finalizar.set_sensitive(
            (self._sel_proc() or Linha("", "grupo")).tipo != "grupo"))
        v.set_model(self.sel_proc)
        v.sort_by_column(self.col_mem, Gtk.SortType.DESCENDING)
        v.connect("activate", lambda _v, pos: self._ativar_linha(pos))
        self.view_proc = v
        self._menu_contexto(v, lambda it: [] if it.tipo == "grupo" else [
            (_t("Finalizar tarefa"), lambda: self._finalizar(it)),
            (_t("Forçar encerramento"), lambda: self._finalizar(it, True)),
            (_t("Abrir local do arquivo"), lambda: self._abrir_local(it)),
            (_t("Ir para detalhes"), lambda: self._ir_detalhes(it)),
        ])

        rol = Gtk.ScrolledWindow(vexpand=True, child=v)
        caixa.append(rol)
        self._expandido = False
        return caixa

    def _ativar_linha(self, pos):
        row = self.sel_proc.get_model().get_item(pos)
        if isinstance(row, Gtk.TreeListRow) and row.is_expandable():
            row.set_expanded(not row.get_expanded())

    def _ir_detalhes(self, it):
        self.nav.select_row(self.nav.get_row_at_index(3))
        GLib.idle_add(lambda: self._selecionar_item(self.view_det, self.cache_det.get(it.pid)) and False)

    def _sel_proc(self):
        return self._item_selecionado(self.view_proc)

    def _obter(self, cache, chave, tipo, expandivel=False):
        it = cache.get(chave)
        if it is None:
            it = Linha(chave, tipo, expandivel)
            cache[chave] = it
        return it

    def _linha_proc(self, cache, p, usados):
        it = self._obter(cache, f"p:{p.pid}:{p.inicio}", "proc")
        usados.add(it.chave)
        it.nome = p.nome
        it.pid = p.pid
        it.pids = [p.pid]
        it.cpu, it.mem, it.disco = p.cpu, p.mem, p.disco
        it.status = _t("Suspenso") if p.estado == "T" else ""
        it.uid = p.uid
        return it

    def _agrupado(self, cache, chave, nome, icone, membros, usados):
        exp = len(membros) > 1
        it = self._obter(cache, f"{chave}:{'+' if exp else '1'}", "app", exp)
        usados.add(it.chave)
        it.nome = nome + (f" ({len(membros)})" if exp else "")
        it.icone = icone
        it.pids = [m.pid for m in membros]
        it.pid = membros[0].pid
        it.cpu = sum(m.cpu for m in membros)
        it.mem = sum(m.mem for m in membros)
        it.disco = sum(m.disco for m in membros)
        it.uid = membros[0].uid
        it.status = _t("Suspenso") if all(m.estado == "T" for m in membros) else ""
        if exp:
            filhos = [self._linha_proc(cache, m, usados) for m in membros]
            sincronizar(it.filhos, filhos)
        return it

    def _tick_processos(self):
        pag = self.stack.get_visible_child_name() if hasattr(self, "stack") else "processos"
        if self.procs and (pag not in ("processos", "detalhes") or not self.is_visible() or self.is_suspended()):
            return True
        self.procs = procs = self.coletor.amostrar()
        if pag == "detalhes":
            self._atualizar_detalhes()
            return True
        usados = set()
        atribuido = set()
        apps = []
        # Uma linha por processo dono de janela (com seus descendentes).
        por_pid = {}
        for w in C.janelas_hyprland():
            pid = w.get("pid")
            if pid in procs:
                por_pid.setdefault(pid, []).append(w)
        for pid, ws in por_pid.items():
            membros = [procs[x] for x in C.descendentes(procs, pid) if x not in atribuido]
            if not membros:  # dono de janela já contado como filho de outro app
                continue
            atribuido.update(m.pid for m in membros)
            info = self.apps.de_classe(ws[0].get("class") or ws[0].get("initialClass"))
            nome = info.get_name() if info else (ws[0].get("class") or procs[pid].nome)
            if not self._bate(nome, *(m.nome for m in membros), *(str(m.pid) for m in membros),
                              *(w.get("title") for w in ws)):
                continue
            apps.append(self._agrupado(self.cache, f"app:{pid}", nome, info.get_icon() if info else None, membros, usados))

        bg, sis = {}, {}
        for p in procs.values():
            if p.pid in atribuido:
                continue
            if not self._bate(p.nome, str(p.pid)):
                continue
            (bg if p.uid == C.MEU_UID else sis).setdefault(p.nome, []).append(p)

        def linhas(dic, prefixo):
            out = []
            for nome, membros in dic.items():
                info = self.apps.idx.get(nome.lower())
                out.append(self._agrupado(self.cache, f"{prefixo}:{nome}", nome,
                                          info.get_icon() if info else None, membros, usados))
            return out

        grupos = {"apps": apps, "bg": linhas(bg, "bg"), "sys": linhas(sis, "sys")}
        sel = self._sel_proc()
        for k, g in self.grupos.items():
            sincronizar(g.filhos, grupos[k])
            g.nome = f"{g.titulo} ({len(grupos[k])})"
            g.emit("mudou")
        for k in [k for k in self.cache if k not in usados]:
            del self.cache[k]
        for k in usados:
            self.cache[k].emit("mudou")

        if not self._expandido:
            self._expandido = True
            i = 0
            while i < self.arvore.get_n_items():
                row = self.arvore.get_row(i)
                if row.get_depth() == 0 and row.get_item().rank < 2:
                    row.set_expanded(True)
                i += 1

        # Cabeçalhos com o total, como no Windows ("CPU 23%").
        uso_cpu = getattr(self, "ultimo_cpu", 0)
        mem = C.memoria()
        self.col_cpu.set_title(_t("CPU  %1%", format(uso_cpu, ".0f")))
        self.col_mem.set_title(_t("Memória  %1%", format(mem['usada'] / mem['total'] * 100, ".0f")))
        self.col_disco.set_title(_t("Disco  %1%", format(max(self.ultimo_disco or [0]), ".0f")) if hasattr(self, "ultimo_disco") else _t("Disco"))

        s = self.view_proc.get_sorter()
        col = s.get_primary_sort_column()
        if col in (self.col_cpu, self.col_mem, self.col_disco) and col.get_sorter():
            col.get_sorter().changed(Gtk.SorterChange.DIFFERENT)
            if sel is not None and sel.tipo != "grupo" and sel.chave in self.cache:
                self._selecionar_item(self.view_proc, sel)
        return True

    # ── página Detalhes ──────────────────────────────────────────────────────
    def _pagina_detalhes(self):
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.append(self._barra_pagina(_t("Detalhes"), [
            self._botao(_t("Executar nova tarefa"), "document-new-symbolic", self._executar_nova),
            self._botao(_t("Finalizar tarefa"), "process-stop-symbolic", lambda: self._finalizar(self._sel_det())),
        ]))
        self.store_det = Gio.ListStore(item_type=Linha)
        o = Ordenador()
        v = Gtk.ColumnView(show_column_separators=True)
        o.view = v
        v.append_column(coluna_nome(False, o.fazer(lambda x: x.nome.lower()), 220))
        v.append_column(coluna_texto("PID", lambda x: str(x.pid), direita=True, largura=80, sorter=o.fazer(lambda x: x.pid)))
        v.append_column(coluna_texto(_t("Status"), lambda x: x.status, largura=110, sorter=o.fazer(lambda x: x.status)))
        v.append_column(coluna_texto(_t("Usuário"), lambda x: x.usuario, largura=100, sorter=o.fazer(lambda x: x.usuario)))
        col_cpu = coluna_texto("CPU", lambda x: f"{x.cpu:.0f}", direita=True, largura=60, sorter=o.fazer(lambda x: x.cpu))
        v.append_column(col_cpu)
        self.col_mem_det = coluna_texto(_t("Memória (privada)"), lambda x: f"{x.mem / 1024:,.0f} K".replace(",", "."),
                                        direita=True, largura=140, sorter=o.fazer(lambda x: x.mem))
        v.append_column(self.col_mem_det)
        v.append_column(coluna_texto(_t("Threads"), lambda x: str(x.threads), direita=True, largura=70, sorter=o.fazer(lambda x: x.threads)))
        v.append_column(coluna_texto(_t("Linha de comando"), lambda x: x.cmd, expandir=True, sorter=o.fazer(lambda x: x.cmd)))
        self.sel_det = Gtk.SingleSelection(model=Gtk.SortListModel.new(self.store_det, v.get_sorter()),
                                           autoselect=False, can_unselect=True)
        v.set_model(self.sel_det)
        v.sort_by_column(self.col_mem_det, Gtk.SortType.DESCENDING)
        self.view_det = v
        self._menu_contexto(v, lambda it: [
            (_t("Finalizar tarefa"), lambda: self._finalizar(it)),
            (_t("Finalizar árvore de processos"), lambda: self._finalizar_arvore(it)),
            (_t("Forçar encerramento"), lambda: self._finalizar(it, True)),
            (_t("Abrir local do arquivo"), lambda: self._abrir_local(it)),
            (_t("Copiar linha de comando"), lambda: self.get_clipboard().set(it.cmd)),
        ])
        caixa.append(Gtk.ScrolledWindow(vexpand=True, child=v))
        return caixa

    def _finalizar_arvore(self, it):
        t = Linha("tmp", "proc")
        t.nome, t.pid = it.nome, it.pid
        t.pids = list(reversed(C.descendentes(self.procs, it.pid)))
        self._finalizar(t)

    def _sel_det(self):
        return self._item_selecionado(self.view_det)

    def _atualizar_detalhes(self):
        estados = {"R": _t("Em execução"), "S": _t("Em execução"), "D": _t("Aguardando E/S"), "T": _t("Suspenso"),
                   "t": _t("Rastreado"), "Z": _t("Zumbi"), "I": _t("Ocioso")}
        itens, usados = [], set()
        for p in self.procs.values():
            if not self._bate(p.nome, str(p.pid), p.cmd):
                continue
            it = self.cache_det.get(p.pid)
            if it is None or it.extra.get("inicio") != p.inicio:
                it = Linha(f"d:{p.pid}", "proc")
                it.extra["inicio"] = p.inicio
                info = self.apps.idx.get(p.nome.lower())
                it.icone = info.get_icon() if info else None
                self.cache_det[p.pid] = it
            usados.add(p.pid)
            it.nome, it.pid, it.pids = p.nome, p.pid, [p.pid]
            it.status = estados.get(p.estado, p.estado)
            it.usuario = C.nome_usuario(p.uid)
            it.uid = p.uid
            it.cpu, it.mem, it.threads, it.cmd = p.cpu, p.mem, p.threads, p.cmd
            itens.append(it)
        sel = self._sel_det()
        sincronizar(self.store_det, itens)
        for k in [k for k in self.cache_det if k not in usados]:
            del self.cache_det[k]
        for it in itens:
            it.emit("mudou")
        col = self.view_det.get_sorter().get_primary_sort_column()
        if col and col.get_sorter():
            col.get_sorter().changed(Gtk.SorterChange.DIFFERENT)
            if sel is not None and sel.pid in self.cache_det:
                self._selecionar_item(self.view_det, sel)

    # ── página Serviços ──────────────────────────────────────────────────────
    def _pagina_servicos(self):
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        caixa.append(self._barra_pagina(_t("Serviços"), [
            self._botao(_t("Iniciar"), "media-playback-start-symbolic", lambda: self._servico("start")),
            self._botao(_t("Parar"), "media-playback-stop-symbolic", lambda: self._servico("stop")),
            self._botao(_t("Reiniciar"), "view-refresh-symbolic", lambda: self._servico("restart")),
            self._botao(_t("Registros"), "view-list-bullet-symbolic", lambda: self._servico("log")),
        ]))
        self.store_srv = Gio.ListStore(item_type=Linha)
        o = Ordenador()
        v = Gtk.ColumnView(show_column_separators=True)
        o.view = v
        v.append_column(coluna_texto(_t("Nome"), lambda x: x.nome, largura=200, sorter=o.fazer(lambda x: x.nome.lower())))
        v.append_column(coluna_texto("PID", lambda x: str(x.pid) if x.pid else "", direita=True, largura=64, sorter=o.fazer(lambda x: x.pid)))
        v.append_column(coluna_texto(_t("Descrição"), lambda x: x.cmd, largura=230, sorter=o.fazer(lambda x: x.cmd.lower())))
        v.append_column(coluna_texto(_t("Status"), lambda x: x.status, largura=110, sorter=o.fazer(lambda x: x.status)))
        col_mem = coluna_texto(_t("Memória"), lambda x: C.fmt_mb(x.mem) if x.mem else "", direita=True, largura=110,
                               sorter=o.fazer(lambda x: x.mem),
                               calor_de=lambda x: calor(x.mem / 1048576, (50, 200, 500, 1000, 2000)))
        v.append_column(col_mem)
        v.append_column(coluna_texto(_t("Grupo"), lambda x: x.usuario, expandir=True, sorter=o.fazer(lambda x: x.usuario)))
        self.sel_srv = Gtk.SingleSelection(model=Gtk.SortListModel.new(self.store_srv, v.get_sorter()),
                                           autoselect=False, can_unselect=True)
        v.set_model(self.sel_srv)
        v.sort_by_column(col_mem, Gtk.SortType.DESCENDING)
        self.view_srv = v
        self._menu_contexto(v, lambda it: [
            (_t("Iniciar"), lambda: self._servico("start", it)),
            (_t("Parar"), lambda: self._servico("stop", it)),
            (_t("Reiniciar"), lambda: self._servico("restart", it)),
            (_t("Ver registros"), lambda: self._servico("log", it)),
        ])
        caixa.append(Gtk.ScrolledWindow(vexpand=True, child=v))
        return caixa

    def _tick_servicos(self, forcar=False):
        if self.stack.get_visible_child_name() != "servicos" and not forcar:
            return True
        status = {"running": _t("Em execução"), "exited": _t("Concluído"), "dead": _t("Parado"), "failed": _t("Falhou"),
                  "auto-restart": _t("Reiniciando"), "start": _t("Iniciando"), "stop": _t("Parando")}
        itens, usados = [], set()
        for s in C.servicos():
            if not self._bate(s["unidade"], s["descricao"], str(s["pid"])):
                continue
            ch = s["escopo"] + ":" + s["unidade"]
            it = self.cache_srv.get(ch) or Linha(ch, "servico")
            self.cache_srv[ch] = it
            usados.add(ch)
            it.nome = s["unidade"].removesuffix(".service")
            it.extra = s
            it.pid = s["pid"]
            it.cmd = s["descricao"]
            it.status = _t("Falhou") if s["ativo"] == "failed" else status.get(s["sub"], s["sub"])
            it.mem = s["memoria"]
            it.usuario = s["escopo"]
            itens.append(it)
        sel = self._item_selecionado(self.view_srv)
        sincronizar(self.store_srv, itens)
        for k in [k for k in self.cache_srv if k not in usados]:
            del self.cache_srv[k]
        for it in itens:
            it.emit("mudou")
        col = self.view_srv.get_sorter().get_primary_sort_column()
        if col and col.get_sorter():
            col.get_sorter().changed(Gtk.SorterChange.DIFFERENT)
            if sel is not None and sel.chave in self.cache_srv:
                self._selecionar_item(self.view_srv, sel)
        return True

    def _servico(self, acao, it=None):
        it = it or self._item_selecionado(self.view_srv)
        if not it:
            return
        s = it.extra
        usuario = s["escopo"] == _t("Usuário")
        if acao == "log":
            cmd = ["journalctl", "--user-unit" if usuario else "-u", s["unidade"], "-e", "-n", "500"]
            subprocess.Popen(["xdg-terminal-exec", "--", *cmd], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        base = ["systemctl", "--user"] if usuario else ["pkexec", "systemctl"]
        subprocess.Popen([*base, acao, s["unidade"]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        GLib.timeout_add(1500, lambda: self._tick_servicos(forcar=True) and False)

    # ── página Aplicativos de inicialização ──────────────────────────────────
    def _pagina_inicio(self):
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.bt_ativar = self._botao(_t("Ativar"), "media-playback-start-symbolic", lambda: self._inicio(True))
        self.bt_desativar = self._botao(_t("Desativar"), "media-playback-stop-symbolic", lambda: self._inicio(False))
        caixa.append(self._barra_pagina(_t("Aplicativos de inicialização"), [self.bt_ativar, self.bt_desativar]))
        self.store_ini = Gio.ListStore(item_type=Linha)
        o = Ordenador()
        v = Gtk.ColumnView(show_column_separators=True)
        o.view = v
        v.append_column(coluna_nome(False, o.fazer(lambda x: x.nome.lower()), 260))
        v.append_column(coluna_texto(_t("Origem"), lambda x: x.usuario, largura=170, sorter=o.fazer(lambda x: x.usuario)))
        v.append_column(coluna_texto(_t("Status"), lambda x: x.status, largura=110, sorter=o.fazer(lambda x: x.status)))
        v.append_column(coluna_texto(_t("Comando"), lambda x: x.cmd, expandir=True))
        self.sel_ini = Gtk.SingleSelection(model=Gtk.SortListModel.new(self.store_ini, v.get_sorter()),
                                           autoselect=False, can_unselect=True)
        v.set_model(self.sel_ini)
        self.view_ini = v
        self._menu_contexto(v, lambda it: [] if it.extra.get("so_leitura") else [
            (_t("Ativar") if it.status == _t("Desativado") else _t("Desativar"),
             lambda: self._inicio(it.status == _t("Desativado"), it)),
        ] + ([(_t("Abrir arquivo"), lambda: Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(it.extra["arquivo"]).get_uri(), None))]
             if it.extra.get("arquivo") else []))
        caixa.append(Gtk.ScrolledWindow(vexpand=True, child=v))
        nota = Gtk.Label(label="Itens “Hyprland” vêm de ~/.config/hypr/autostart.lua e só podem ser alterados no arquivo; "
                               "serviços do sistema (som, pastas do usuário…) não são alterados por aqui.",
                         xalign=0, margin_start=18, margin_bottom=8, margin_top=6)
        nota.add_css_class("rotulo-fraco")
        caixa.append(nota)
        return caixa

    def _carregar_inicio(self):
        itens = []
        # XDG autostart (usuário sobrescreve o do sistema com o mesmo nome)
        arquivos = {}
        for d in ("/etc/xdg/autostart", str(HOME / ".config/autostart")):
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.endswith(".desktop"):
                        arquivos[f] = os.path.join(d, f)
        for f, caminho in sorted(arquivos.items()):
            cp = ConfigParser(interpolation=None, strict=False)
            cp.optionxform = str
            try:
                # o do sistema primeiro: o do usuário (às vezes só "Hidden=true") sobrepõe chave a chave
                sistema = os.path.join("/etc/xdg/autostart", f)
                cp.read([x for x in (sistema, caminho) if os.path.exists(x)], encoding="utf-8")
                e = cp["Desktop Entry"]
            except Exception:
                continue
            ativo = e.get("Hidden", "false").lower() != "true" and \
                e.get("X-GNOME-Autostart-enabled", "true").lower() != "false"
            it = Linha("x:" + f, "inicio")
            it.nome = e.get("Name[pt_BR]") or e.get("Name") or f
            ic = e.get("Icon")
            it.icone = Gio.ThemedIcon.new(ic) if ic and not ic.startswith("/") else (Gio.FileIcon.new(Gio.File.new_for_path(ic)) if ic else None)
            it.usuario = _t("Autostart (XDG)")
            it.status = _t("Ativado") if ativo else _t("Desativado")
            it.cmd = e.get("Exec", "")
            it.extra = {"tipo": "xdg", "arquivo": caminho, "nome": f}
            itens.append(it)
        # Serviços do usuário que sobem com a sessão
        try:
            import json
            out = subprocess.run(["systemctl", "--user", "list-unit-files", "--type=service", "-o", "json", "--no-pager"],
                                 capture_output=True, text=True, timeout=5).stdout
            for u in json.loads(out or "[]"):
                if u.get("state") not in ("enabled", "disabled"):
                    continue
                caminho = HOME / ".config/systemd/user" / u["unit_file"]
                if u.get("state") == "disabled" and not caminho.exists():
                    continue
                it = Linha("s:" + u["unit_file"], "inicio")
                it.nome = u["unit_file"].removesuffix(".service")
                it.usuario = _t("Serviço do usuário")
                it.status = _t("Ativado") if u["state"] == "enabled" else _t("Desativado")
                if u["unit_file"] not in self.desc_cache:
                    self.desc_cache[u["unit_file"]] = subprocess.run(
                        ["systemctl", "--user", "show", "-P", "Description", u["unit_file"]],
                        capture_output=True, text=True, timeout=2).stdout.strip()
                desc = self.desc_cache[u["unit_file"]]
                it.cmd = desc
                it.icone = Gio.ThemedIcon.new("emblem-system-symbolic")
                proprio = caminho.exists()
                if not proprio:
                    it.usuario = _t("Serviço do sistema (usuário)")
                it.extra = {"tipo": "systemd", "unidade": u["unit_file"], "so_leitura": not proprio,
                            "arquivo": str(caminho) if proprio else ""}
                itens.append(it)
        except Exception:
            pass
        # Hyprland autostart.lua (só leitura)
        auto = HOME / ".config/hypr/autostart.lua"
        if auto.exists():
            for n, linha in enumerate(auto.read_text().splitlines()):
                s = linha.strip()
                if s.startswith("--"):
                    continue
                m = re.search(r"""exec[_a-z]*\(\s*["'](.+?)["']\s*[,)]""", s) or re.search(r"""\[\[(.+?)\]\]""", s)
                if not m:
                    continue
                cmd = m.group(1)
                it = Linha(f"h:{n}", "inicio")
                try:
                    partes = shlex.split(cmd)
                except ValueError:
                    partes = cmd.split()
                prog = next((p for p in partes if not p.startswith("-") and "=" not in p and p not in ("uwsm-app", "uwsm", "app", "--", "sh", "bash")), partes[0] if partes else cmd)
                it.nome = os.path.basename(prog)
                it.usuario = _t("Hyprland")
                it.status = _t("Ativado")
                it.cmd = cmd
                it.icone = Gio.ThemedIcon.new("application-x-executable-symbolic")
                it.extra = {"tipo": "hypr", "so_leitura": True, "arquivo": str(auto)}
                itens.append(it)
        itens = [i for i in itens if self._bate(i.nome, i.cmd, i.usuario)]
        self.store_ini.remove_all()
        self.store_ini.splice(0, 0, itens)

    def _inicio(self, ativar, it=None):
        it = it or self._item_selecionado(self.view_ini)
        if not it or it.extra.get("so_leitura"):
            return
        e = it.extra
        if e["tipo"] == "systemd":
            subprocess.run(["systemctl", "--user", "enable" if ativar else "disable", e["unidade"]],
                           capture_output=True, timeout=10)
        elif e["tipo"] == "xdg":
            destino = HOME / ".config/autostart" / e["nome"]
            destino.parent.mkdir(parents=True, exist_ok=True)
            sistema = Path("/etc/xdg/autostart") / e["nome"]
            texto = Path(e["arquivo"]).read_text(encoding="utf-8", errors="replace")
            texto = re.sub(r"(?m)^(Hidden|X-GNOME-Autostart-enabled)=.*\n?", "", texto)
            if ativar:
                sem_exec = not re.search(r"(?m)^Exec=", texto)
                if sistema.exists() and str(destino) == e["arquivo"] and (sem_exec or
                        texto.strip() == sistema.read_text(encoding="utf-8", errors="replace").strip()):
                    destino.unlink()  # só desativava o do sistema: volta a usar o do sistema
                else:
                    destino.write_text(texto, encoding="utf-8")
            else:
                if not texto.endswith("\n"):
                    texto += "\n"
                destino.write_text(texto + "Hidden=true\n", encoding="utf-8")
        self._carregar_inicio()

    # ── página Desempenho ────────────────────────────────────────────────────
    def _pagina_desempenho(self):
        self.cpu = C.Cpu()
        self.discos = [C.Disco(n) for n in C.discos()]
        self.redes = [C.Rede(n) for n in C.interfaces()]
        self.hist = {}
        self.recursos = []  # (id, tipo, titulo, cor)
        self.recursos.append(("cpu", "cpu", "CPU"))
        self.recursos.append(("mem", "mem", _t("Memória")))
        for i, d in enumerate(self.discos):
            self.recursos.append((f"disco{i}", "disco", _t("Disco %1 (%2)", i, d.nome)))
        for r in self.redes:
            self.recursos.append((f"rede:{r.nome}", "rede", _t("Wi-Fi") if r.wifi else _t("Ethernet")))
        for rid, *_ in self.recursos:
            self.hist[rid] = deque([0.0] * 60, maxlen=60)
            self.hist[rid + ":2"] = deque([0.0] * 60, maxlen=60)

        caixa = Gtk.Box()
        lista = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        lista.add_css_class("lista-desempenho")
        lista.add_css_class("navigation-sidebar")
        rol = Gtk.ScrolledWindow(child=lista, hscrollbar_policy=Gtk.PolicyType.NEVER, width_request=250)
        caixa.append(rol)
        caixa.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.stack_des = Gtk.Stack(hexpand=True)
        caixa.append(self.stack_des)
        self.mini = {}
        self.detalhe = {}

        for rid, tipo, titulo in self.recursos:
            linha = Gtk.ListBoxRow()
            linha.rid = rid
            b = Gtk.Box(spacing=10)
            graf = Gtk.DrawingArea(content_width=64, content_height=44)
            graf.set_draw_func(self._desenhar, (rid, tipo, True))
            b.append(graf)
            tx = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
            t = Gtk.Label(label=titulo, xalign=0)
            t.add_css_class("heading")
            sub = Gtk.Label(xalign=0)
            sub.add_css_class("rotulo-fraco")
            sub2 = Gtk.Label(xalign=0, visible=tipo == "disco")
            sub2.add_css_class("rotulo-fraco")
            tx.append(t)
            tx.append(sub)
            tx.append(sub2)
            b.append(tx)
            linha.set_child(b)
            lista.append(linha)
            self.mini[rid] = (graf, sub, sub2)
            self.stack_des.add_named(self._detalhe_recurso(rid, tipo, titulo), rid)

        lista.connect("row-selected", lambda _l, r: r and self.stack_des.set_visible_child_name(r.rid))
        lista.select_row(lista.get_row_at_index(0))
        return caixa

    def _detalhe_recurso(self, rid, tipo, titulo):
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, margin_start=22, margin_end=22, margin_top=16, margin_bottom=16)
        topo = Gtk.Box()
        t = Gtk.Label(label=titulo.split(" (")[0], xalign=0, hexpand=True)
        t.add_css_class("titulo-desempenho")
        topo.append(t)
        modelo = {"cpu": re.sub(r"\(R\)|\(TM\)| CPU| @.*", "", self.cpu.modelo).strip(), "mem": C.fmt_bytes(C.memoria()["total"])}.get(tipo, "")
        if tipo == "disco":
            d = self.discos[int(rid[5:])]
            modelo = d.modelo
        elif tipo == "rede":
            modelo = rid.split(":", 1)[1]
        m = Gtk.Label(label=modelo, xalign=1, valign=Gtk.Align.END)
        m.add_css_class("subtitulo-desempenho")
        topo.append(m)
        caixa.append(topo)
        legenda = {"cpu": _t("% de utilização"), "mem": _t("Uso da memória"), "disco": _t("Tempo ativo"), "rede": _t("Taxa de transferência")}[tipo]
        cab = Gtk.Box()
        cab.append(Gtk.Label(label=legenda, xalign=0, hexpand=True, css_classes=["rotulo-fraco"]))
        escala = Gtk.Label(label="100%" if tipo != "rede" else "", xalign=1, css_classes=["rotulo-fraco"])
        cab.append(escala)
        caixa.append(cab)
        graf = Gtk.DrawingArea(vexpand=True, content_height=260)
        graf.set_draw_func(self._desenhar, (rid, tipo, False))
        caixa.append(graf)
        rod = Gtk.Box()
        rod.append(Gtk.Label(label=_t("60 segundos"), xalign=0, hexpand=True, css_classes=["rotulo-fraco"]))
        rod.append(Gtk.Label(label="0", xalign=1, css_classes=["rotulo-fraco"]))
        caixa.append(rod)

        grade = Gtk.Grid(column_spacing=36, row_spacing=4, margin_top=14)
        caixa.append(grade)
        valores = {}

        def campo(col, lin, rotulo, grande=True):
            g = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            g.append(Gtk.Label(label=_t(rotulo), xalign=0, css_classes=["rotulo-fraco"]))
            v = Gtk.Label(label="—", xalign=0, css_classes=["valor-grande" if grande else "num"])
            g.append(v)
            grade.attach(g, col, lin, 1, 1)
            valores[rotulo] = v

        if tipo == "cpu":
            for i, r in enumerate((_n("Utilização"), _n("Velocidade"), _n("Processos"), _n("Threads"), _n("Tempo de atividade"))):
                campo(i % 3, i // 3, r)
            info = Gtk.Grid(column_spacing=12, row_spacing=2, margin_top=10)
            for i, (k, v) in enumerate(((_t("Velocidade base:"), f"{self.cpu.vel_base:.2f} GHz".replace(".", _DEC)),
                                        (_t("Núcleos:"), str(self.cpu.nucleos)),
                                        (_t("Processadores lógicos:"), str(C.NCPU)))):
                info.attach(Gtk.Label(label=k, xalign=0, css_classes=["rotulo-fraco"]), 0, i, 1, 1)
                info.attach(Gtk.Label(label=v, xalign=0), 1, i, 1, 1)
            caixa.append(info)
        elif tipo == "mem":
            for i, r in enumerate((_n("Em uso"), _n("Disponível"), _n("Em cache"), _n("Confirmada"), _n("Swap em uso"))):
                campo(i % 3, i // 3, r)
        elif tipo == "disco":
            for i, r in enumerate((_n("Tempo ativo"), _n("Velocidade de leitura"), _n("Velocidade de gravação"), _n("Capacidade"), _n("Tipo"))):
                campo(i % 3, i // 3, r)
        else:
            for i, r in enumerate((_n("Enviar"), _n("Receber"), _n("Endereço IPv4"))):
                campo(i % 3, i // 3, r)
        self.detalhe[rid] = (graf, valores, escala)
        return caixa

    def _desenhar(self, area, cr, w, h, dados):
        rid, tipo, mini = dados
        r, g, b = CORES[tipo]
        cr.set_source_rgba(r, g, b, 0.06)
        cr.rectangle(0, 0, w, h)
        cr.fill()
        if not mini:
            cr.set_source_rgba(r, g, b, 0.18)
            cr.set_line_width(1)
            for i in range(1, 10):
                x = round(w * i / 10) + 0.5
                cr.move_to(x, 0)
                cr.line_to(x, h)
            for i in range(1, 6):
                y = round(h * i / 6) + 0.5
                cr.move_to(0, y)
                cr.line_to(w, y)
            cr.stroke()
        series = [self.hist[rid]]
        if tipo == "rede":
            series.append(self.hist[rid + ":2"])
            topo = max(max(series[0]), max(series[1]), 1024 * 8)
        else:
            topo = 100.0
        for n, s in enumerate(series):
            pts = list(s)
            passo = w / (len(pts) - 1)
            cr.move_to(0, h)
            for i, v in enumerate(pts):
                cr.line_to(i * passo, h - min(1, v / topo) * (h - 1))
            cr.line_to(w, h)
            cr.close_path()
            if n == 0:
                cr.set_source_rgba(r, g, b, 0.18)
                cr.fill_preserve()
            else:
                cr.new_path()
                cr.move_to(0, h)
                for i, v in enumerate(pts):
                    cr.line_to(i * passo, h - min(1, v / topo) * (h - 1))
                cr.set_dash([4, 3])
            cr.set_source_rgba(r, g, b, 1)
            cr.set_line_width(1.2 if mini else 1.5)
            cr.stroke()
            cr.set_dash([])
        cr.set_source_rgba(r, g, b, 0.9)
        cr.set_line_width(1)
        cr.rectangle(0.5, 0.5, w - 1, h - 1)
        cr.stroke()

    def _tick_desempenho(self):
        cpu = self.cpu.amostrar()
        self.ultimo_cpu = cpu
        self.hist["cpu"].append(cpu)
        vel = self.cpu.velocidade()
        mem = C.memoria()
        pm = mem["usada"] / mem["total"] * 100
        self.hist["mem"].append(pm)
        self._atualizar_mini("cpu", f"{cpu:.0f}%  {vel:.2f} GHz".replace(".", _DEC))
        self._atualizar_mini("mem", f"{C.fmt_bytes(mem['usada'])}/{C.fmt_bytes(mem['total'])} ({pm:.0f}%)")
        if self.stack.get_visible_child_name() == "desempenho":
            _, v, _ = self.detalhe["cpu"]
            v["Utilização"].set_text(f"{cpu:.0f}%")
            v["Velocidade"].set_text(f"{vel:.2f} GHz".replace(".", _DEC))
            n, th = C.contar_processos()
            v["Processos"].set_text(str(n))
            v["Threads"].set_text(str(th))
            v["Tempo de atividade"].set_text(C.tempo_atividade())
            _, v, _ = self.detalhe["mem"]
            v["Em uso"].set_text(C.fmt_bytes(mem["usada"]))
            v["Disponível"].set_text(C.fmt_bytes(mem["disponivel"]))
            v["Em cache"].set_text(C.fmt_bytes(mem["cache"]))
            v["Confirmada"].set_text(f"{C.fmt_bytes(mem['comprometida'])}/{C.fmt_bytes(mem['limite'])}")
            v["Swap em uso"].set_text(f"{C.fmt_bytes(mem['swap_usada'])}/{C.fmt_bytes(mem['swap_total'])}")
        self.ultimo_disco = []
        for i, d in enumerate(self.discos):
            rid = f"disco{i}"
            ativo, le, gr = d.amostrar()
            self.ultimo_disco.append(ativo)
            self.hist[rid].append(ativo)
            self._atualizar_mini(rid, f"{d.tipo}", f"{ativo:.0f}%")
            _, v, _ = self.detalhe[rid]
            v["Tempo ativo"].set_text(f"{ativo:.0f}%")
            v["Velocidade de leitura"].set_text(C.fmt_bytes(le) + "/s")
            v["Velocidade de gravação"].set_text(C.fmt_bytes(gr) + "/s")
            v["Capacidade"].set_text(C.fmt_bytes(d.capacidade))
            v["Tipo"].set_text(d.tipo)
        for r in self.redes:
            rid = f"rede:{r.nome}"
            rx, tx = r.amostrar()
            self.hist[rid].append(rx)
            self.hist[rid + ":2"].append(tx)
            self._atualizar_mini(rid, f"E: {C.fmt_bits(tx)}  R: {C.fmt_bits(rx)}")
            _, v, esc = self.detalhe[rid]
            v["Enviar"].set_text(C.fmt_bits(tx))
            v["Receber"].set_text(C.fmt_bits(rx))
            if v["Endereço IPv4"].get_text() == "—":
                v["Endereço IPv4"].set_text(r.ip())
            esc.set_text(C.fmt_bits(max(max(self.hist[rid]), max(self.hist[rid + ":2"]), 1024 * 8)))
        for rid, (graf, _s, _s2) in self.mini.items():
            graf.queue_draw()
            if self.stack.get_visible_child_name() == "desempenho":
                self.detalhe[rid][0].queue_draw()
        return True

    def _atualizar_mini(self, rid, texto, texto2=None):
        _g, s, s2 = self.mini[rid]
        s.set_text(texto)
        if texto2 is not None:
            s2.set_text(texto2)


# ── tema do sistema (mesmas regras do Explorador e da Configurações) ─────────
TEMA = HOME / ".local/state/simba/current/theme"


def _hex(c, padrao):
    c = str(c or "").strip().strip('"').lstrip("#")
    return "#" + c[:6] if len(c) >= 6 else padrao


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, k):
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * k) for x, y in zip(_rgb(a), _rgb(b)))


def _lum(h):
    r, g, b = (x / 255 for x in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def css_tema():
    """Paleta do tema atual em variáveis do libadwaita; "" se não houver tema."""
    try:
        import tomllib
        d = tomllib.loads((TEMA / "colors.toml").read_text())
    except Exception:  # noqa: BLE001
        return "", None
    f = _hex(d.get("background"), "#1c1c1c")
    t = _hex(d.get("foreground"), "#ffffff")
    a = _hex(d.get("accent", d.get("color4")), "#4cc2ff")
    e = _lum(f) < 0.45 and not (TEMA / "light.mode").exists()
    r, g, b = _rgb(a)
    if (max(r, g, b) - min(r, g, b)) / max(1, max(r, g, b)) < 0.18:
        a = t  # destaque cinza (temas monocromáticos): usa o texto
    sobre = "#000000" if _lum(a) > 0.5 else "#ffffff"
    fundo = _mix(f, t, 0.03 if e else 0.02)
    v = {
        "window-bg-color": fundo, "window-fg-color": t,
        "view-bg-color": fundo, "view-fg-color": t,
        "headerbar-bg-color": _mix(f, t, 0.025 if e else 0.06), "headerbar-fg-color": t,
        "headerbar-backdrop-color": _mix(f, t, 0.025 if e else 0.06),
        "sidebar-bg-color": fundo, "sidebar-fg-color": t,
        "card-bg-color": _mix(f, t, 0.075 if e else 0.03),
        "popover-bg-color": _mix(f, t, 0.10 if e else 0.01), "popover-fg-color": t,
        "dialog-bg-color": _mix(f, t, 0.10 if e else 0.01), "dialog-fg-color": t,
        "accent-bg-color": a, "accent-color": a, "accent-fg-color": sobre,
    }
    nomes = "".join(f"@define-color {k.replace('-color', '').replace('-', '_')}_color {x};\n"
                    for k, x in v.items() if k.startswith(("accent", "window", "view")))
    return nomes + _t(":root { ") + " ".join(f"--{k}: {x};" for k, x in v.items()) + " }", e


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.janela = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        css = Gtk.CssProvider()
        css.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        # Cores do tema atual (vantablack, white…) e troca ao vivo: theme.name é escrito por último
        self.css_tema = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css_tema,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self._aplicar_tema()
        self.mon_tema = Gio.File.new_for_path(str(TEMA.parent / "theme.name")).monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.mon_tema.connect("changed", lambda *_: self._aplicar_tema())
        # O tema de ícones configurado pode não existir (ex.: Yaru-gray): usa o Adwaita para os símbolos.
        tema = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        if not tema.has_icon("document-new-symbolic"):
            Gtk.Settings.get_default().set_property("gtk-icon-theme-name", "Adwaita")
        q = Gio.SimpleAction.new("sair", None)
        q.connect("activate", lambda *_: self.quit())
        self.add_action(q)
        self.set_accels_for_action("app.sair", ["<Ctrl>q", "<Ctrl>w"])

    def _aplicar_tema(self):
        texto, escuro = css_tema()
        if escuro is not None:
            Adw.StyleManager.get_default().set_color_scheme(
                Adw.ColorScheme.FORCE_DARK if escuro else Adw.ColorScheme.FORCE_LIGHT)
        self.css_tema.load_from_string(texto)

    def do_command_line(self, linha):
        args = linha.get_arguments()[1:]
        if self.janela is None:
            self.janela = Janela(self)
        if args and args[0] in ("processos", "desempenho", "inicializacao", "detalhes", "servicos"):
            ordem = ["processos", "desempenho", "inicializacao", "detalhes", "servicos"]
            self.janela.nav.select_row(self.janela.nav.get_row_at_index(ordem.index(args[0])))
        self.janela.present()
        return 0


if __name__ == "__main__":
    sys.exit(App().run(sys.argv))
