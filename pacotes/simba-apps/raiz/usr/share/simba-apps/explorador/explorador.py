#!/usr/bin/env python3
"""Explorador de Arquivos — gerenciador de arquivos no estilo do Windows 11 (GTK4/libadwaita).

    explorador [pasta|arquivo|URI ...]   abre (arquivo: abre a pasta com ele selecionado)

Abas, barra de comandos, endereço com caminho clicável, pesquisa, Início (acesso
rápido, favoritos, recentes), Galeria, Este Computador, Nuvem (rclone: Google Drive,
OneDrive, Dropbox…), Lixeira, painel de detalhes/visualização e os atalhos do Windows.
Também atende org.freedesktop.FileManager1 ("Mostrar na pasta" dos navegadores).
"""
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path
import sys as _sys, os as _os  # noqa: E401
_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))
from simba_i18n import t as _t, n as _n  # noqa: E402  (traduções: /usr/share/simba-apps/idiomas)

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

import nuvem  # noqa: E402
import utilidades as u  # noqa: E402
from abas import barra_titulo  # noqa: E402
from estilo import Estilo  # noqa: E402
from operacoes import Operacoes, modo_texto  # noqa: E402
from paginas import Computador, Detalhes, Inicio, Lateral, PaginaNuvem  # noqa: E402
from vista import NOMES_VISAO, ORDENS, VISOES, Vista, normalizar  # noqa: E402

APP_ID = "com.simba.Explorador"
ESPECIAIS = {"inicio": (_t("Início"), "user-home"), "galeria": (_t("Galeria"), "folder-pictures"),
             "computador": (_t("Este Computador"), "computer"), "nuvem": (_t("Nuvem"), "folder-remote"),
             "busca": (_t("Pesquisa"), "system-search")}
ARQUIVOS_COMPACTADOS = ("application/zip", "application/x-tar", "application/x-compressed-tar", "application/x-bzip-compressed-tar",
                        "application/x-xz-compressed-tar", "application/x-7z-compressed", "application/vnd.rar",
                        "application/x-rar", "application/gzip", "application/x-zstd-compressed-tar", "application/x-cd-image",
                        "application/zstd", "application/x-xz", "application/x-bzip2", "application/java-archive")


# ── uma aba ─────────────────────────────────────────────────────────────────
class Aba(Gtk.Box):
    def __init__(self, janela):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, css_classes=["conteudo"])
        self.janela = janela
        self.local = None          # Gio.File ou nome especial
        self.historia, self.pos = [], -1
        self.vista = None
        self.pagina = None
        self.busca = None          # (pasta, texto) da pesquisa em subpastas
        self._cancelar = threading.Event()

    def ir(self, local, registrar=True, selecionar=None):
        self._cancelar.set()
        self._cancelar = threading.Event()
        if registrar:
            self.historia = self.historia[:self.pos + 1] + [local]
            self.pos = len(self.historia) - 1
        self.local = local
        if self.pagina is not None:
            self.remove(self.pagina)
        self.vista = None
        if isinstance(local, str):
            if local == "inicio":
                self.pagina = Inicio(self.janela)
            elif local == "computador":
                self.pagina = Computador(self.janela)
            elif local == "nuvem":
                self.pagina = PaginaNuvem(self.janela)
            elif local == "galeria":
                self.vista = Vista(self.janela, lista=self._galeria(), mostrar_local=True)
                self.vista.definir_visao("grande") if self.vista.visao in ("lista", "detalhes") else None
                self.pagina = self.vista
            elif local == "busca":
                pasta, texto = self.busca
                self.vista = Vista(self.janela, lista=self._pesquisar(pasta, texto), mostrar_local=True)
                self.vista.definir_visao("detalhes")
                self.pagina = self.vista
        else:
            self.vista = Vista(self.janela, gfile=local)
            self.pagina = self.vista
        if self.vista is not None:
            v = self.vista
            v.connect("abrir", lambda v, info, nova: self.janela.abrir_info(info, nova))
            v.connect("selecao", lambda v: self.janela.selecao_mudou(self))
            v.connect("contagem", lambda v: self.janela.selecao_mudou(self))
            v.connect("menu", lambda v, x, y, item: self.janela.menu_contexto(x, y, item))
            v.connect("soltar", lambda v, cam, dest, copiar: self.janela.soltar(cam, dest, copiar))
            if selecionar:
                v.selecionar_quando_aparecer(selecionar)
        self.append(self.pagina)
        self.pagina.set_vexpand(True)
        self.janela.local_mudou(self)
        if self.vista is not None:
            GLib.idle_add(lambda: (self.vista and self.vista.focar(), False)[1])

    def titulo(self):
        if isinstance(self.local, str):
            if self.local == "busca" and self.busca:
                return _t("Pesquisa: %1", self.busca[1])
            return ESPECIAIS[self.local][0]
        return nome_local(self.local)

    def icone(self):
        if isinstance(self.local, str):
            return Gio.ThemedIcon.new(ESPECIAIS[self.local][1])
        p = self.local.get_path()
        if p in u.ICONE_PASTA:
            return Gio.ThemedIcon.new(u.ICONE_PASTA[p])
        if self.local.get_uri_scheme() == "trash":
            return Gio.ThemedIcon.new("user-trash")
        return Gio.ThemedIcon.new("folder")

    def _galeria(self):
        """Fotos e vídeos de Imagens (e subpastas), os mais novos primeiro."""
        loja = Gio.ListStore(item_type=Gio.FileInfo)
        cancelar = self._cancelar
        raizes = [str(p) for i, _, _, p in u.PASTAS if i in ("imagens", "videos") and p.is_dir()]

        def varrer():
            achados = []
            for raiz in raizes:
                for d, pastas, arqs in os.walk(raiz):
                    pastas[:] = [p for p in pastas if not p.startswith(".")]
                    for a in arqs:
                        if a.lower().rsplit(".", 1)[-1] in ("jpg", "jpeg", "png", "webp", "gif", "heic", "avif", "bmp",
                                                            "mp4", "mkv", "webm", "mov", "avi"):
                            p = os.path.join(d, a)
                            try:
                                achados.append((os.stat(p).st_mtime, p))
                            except OSError:
                                pass
                    if cancelar.is_set() or len(achados) > 5000:
                        break
            achados.sort(reverse=True)
            lote = []
            for _, p in achados[:3000]:
                if cancelar.is_set():
                    return
                i = u.info_de(Gio.File.new_for_path(p))
                if i:
                    lote.append(i)
                if len(lote) >= 120:
                    GLib.idle_add(loja.splice, loja.get_n_items(), 0, lote)
                    lote = []
            if lote:
                GLib.idle_add(loja.splice, loja.get_n_items(), 0, lote)
        threading.Thread(target=varrer, daemon=True).start()
        return loja

    def _pesquisar(self, pasta, texto):
        loja = Gio.ListStore(item_type=Gio.FileInfo)
        cancelar = self._cancelar
        termo = normalizar(texto)
        ocultos = self.janela.cfg["ocultos"]

        def varrer():
            lote, n = [], 0
            for d, pastas, arqs in os.walk(pasta):
                if not ocultos:
                    pastas[:] = [p for p in pastas if not p.startswith(".")]
                for nome in pastas + arqs:
                    if (ocultos or not nome.startswith(".")) and termo in normalizar(nome):
                        i = u.info_de(Gio.File.new_for_path(os.path.join(d, nome)))
                        if i:
                            lote.append(i)
                            n += 1
                if lote and (len(lote) >= 50):
                    GLib.idle_add(loja.splice, loja.get_n_items(), 0, lote)
                    lote = []
                if cancelar.is_set() or n >= 3000:
                    break
            if lote:
                GLib.idle_add(loja.splice, loja.get_n_items(), 0, lote)
            GLib.idle_add(self.janela.pesquisa_terminou, self, n)
        threading.Thread(target=varrer, daemon=True).start()
        return loja

    def voltar(self):
        if self.pos > 0:
            self.pos -= 1
            self.ir(self.historia[self.pos], False)

    def avancar(self):
        if self.pos < len(self.historia) - 1:
            self.pos += 1
            self.ir(self.historia[self.pos], False)

    def acima(self):
        if isinstance(self.local, Gio.File):
            pai = self.local.get_parent()
            if pai is not None:
                self.ir(pai, selecionar=self.local.get_basename())
            else:
                self.ir("computador")


def nome_local(gfile):
    p = gfile.get_path()
    if p in u.NOME_PASTA:
        return u.NOME_PASTA[p]
    if gfile.get_uri_scheme() == "trash":
        return _t("Lixeira")
    if gfile.get_uri() == "network:///":
        return _t("Rede")
    if p == "/":
        return _t("Disco local (/)")
    return gfile.get_basename() or gfile.get_uri()


# ── janela ──────────────────────────────────────────────────────────────────
class Janela(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_t("Explorador de Arquivos"), default_width=1240, default_height=780,
                         icon_name=APP_ID, css_classes=["explorador"])
        self.app = app
        self.cfg = u.ler_config()
        self.recortados = set()
        self.fechadas = []           # abas fechadas (Ctrl+Shift+T)
        self.ops = app.ops
        self._acoes()

        self.raiz = Adw.ToolbarView(top_bar_style=Adw.ToolbarStyle.FLAT, bottom_bar_style=Adw.ToolbarStyle.FLAT)
        self.toast = Adw.ToastOverlay(child=self.raiz)
        self.set_content(self.toast)

        # abas na barra de título
        self.abas = Adw.TabView()
        self.abas.connect("notify::selected-page", lambda *a: self._aba_trocada())
        self.abas.connect("close-page", self._fechando_aba)
        self.abas.connect("create-window", lambda *a: Janela(self.app).present_and_return())
        # abas na barra de título, como no Windows 11 (abas.py)
        cab, self.faixa_abas = barra_titulo(self.abas, lambda: self.nova_aba(None), self)
        self.raiz.add_top_bar(cab)
        self._sinal_estilo = self.app.estilo.ouvir(lambda: self.faixa_abas.queue_draw())
        self.raiz.add_top_bar(self._barra_endereco())
        self.raiz.add_top_bar(self._barra_comandos())

        # corpo: lateral | abas | detalhes
        self.lateral = Lateral(self)
        self.detalhes = Detalhes(self)
        meio = Gtk.Box()
        meio.append(self.abas)
        self.abas.set_hexpand(True)
        meio.append(self.detalhes)
        self.paned = Gtk.Paned(start_child=self.lateral, end_child=meio, position=self.cfg.get("lateral", 240),
                               shrink_start_child=False, resize_start_child=False)
        self.paned.connect("notify::position", self._lateral_largura)
        self.raiz.set_content(self.paned)
        self.raiz.add_bottom_bar(self._barra_status())
        self._painel(self.cfg.get("painel", ""))

        self._sinais_ops = [self.ops.connect("progresso", self._progresso), self.ops.connect("terminou", self._terminou)]
        self.connect("close-request", self._fechar_janela)
        vm = Gio.VolumeMonitor.get()
        self._sinais_vm = [vm.connect(s, lambda *a: GLib.timeout_add(600, self._mudou_montagem))
                           for s in ("mount-added", "mount-removed", "volume-added", "volume-removed")]

    @property
    def cores_abas(self):
        v = self.app.estilo.valores
        return {"cor-aba-sel": v.get("VISTA"), "cor-aba-hover": v.get("HOVERABA"), "cor-aba-div": v.get("LINHA")}

    def present_and_return(self):
        self.present()
        return self.abas

    # ── barras ─────────────────────────────────────────────────────────────
    def _barra_endereco(self):
        b = Gtk.Box(spacing=4, css_classes=["barra-endereco"])
        for icone, acao, dica in (("go-previous-symbolic", "win.voltar", _t("Voltar (Alt+←)")),
                                  ("go-next-symbolic", "win.avancar", _t("Avançar (Alt+→)")),
                                  ("go-up-symbolic", "win.acima", _t("Subir um nível (Alt+↑)")),
                                  ("view-refresh-symbolic", "win.atualizar", _t("Atualizar (F5)"))):
            b.append(Gtk.Button(icon_name=icone, action_name=acao, tooltip_text=dica, css_classes=["flat"]))
        # caminho: botões (migalhas) ou campo de texto
        self.caminho_pilha = Gtk.Stack(hexpand=True, transition_type=Gtk.StackTransitionType.CROSSFADE,
                                       transition_duration=100)
        self.migalhas = Gtk.Box(hexpand=True)
        # Caminho comprido não alarga a janela: rola e mostra sempre o final
        self.migalhas_rol = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.EXTERNAL,
                                               vscrollbar_policy=Gtk.PolicyType.NEVER, hexpand=True,
                                               css_classes=["caminho"])
        self.migalhas_rol.set_child(self.migalhas)
        self.migalhas_rol.get_hadjustment().connect("changed", lambda adj: adj.set_value(adj.get_upper() - adj.get_page_size()))
        self.caminho_entrada = Gtk.Entry(hexpand=True, css_classes=["caminho"])
        self.caminho_entrada.connect("activate", self._caminho_digitado)
        esc = Gtk.EventControllerKey()
        esc.connect("key-pressed", lambda c, k, *a: (self._caminho_modo(False), True)[1] if k == Gdk.KEY_Escape else False)
        self.caminho_entrada.add_controller(esc)
        foco = Gtk.EventControllerFocus()
        foco.connect("leave", lambda *a: GLib.timeout_add(150, lambda: (self._caminho_modo(False), False)[1]))
        self.caminho_entrada.add_controller(foco)
        self.caminho_pilha.add_named(self.migalhas_rol, "migalhas")
        self.caminho_pilha.add_named(self.caminho_entrada, "entrada")
        g = Gtk.GestureClick()
        g.connect("released", lambda g, n, x, y: self._caminho_clicado(x, y))
        self.migalhas_rol.add_controller(g)
        b.append(self.caminho_pilha)
        self.pesquisa = Gtk.SearchEntry(width_chars=28, css_classes=["pesquisa"], placeholder_text=_t("Pesquisar"))
        self.pesquisa.connect("search-changed", self._pesquisa_mudou)
        self.pesquisa.connect("activate", self._pesquisa_enter)
        self.pesquisa.connect("stop-search", lambda *a: (self.pesquisa.set_text(""), self._vista() and self._vista().focar()))
        b.append(self.pesquisa)
        return b

    def _botao(self, rotulo, icone, acao, dica, so_icone=False, classes=()):
        bt = Gtk.Button(action_name=acao, tooltip_text=dica, css_classes=["flat", *classes])
        c = Gtk.Box(spacing=6)
        c.append(Gtk.Image(icon_name=icone))
        if not so_icone:
            c.append(Gtk.Label(label=rotulo))
        bt.set_child(c)
        if so_icone:
            bt.add_css_class("so-icone")
        return bt

    def _menu_botao(self, rotulo, icone, menu, dica, classes=()):
        mb = Gtk.MenuButton(menu_model=menu, tooltip_text=dica, css_classes=["flat", *classes], always_show_arrow=True)
        c = Gtk.Box(spacing=6)
        c.append(Gtk.Image(icon_name=icone))
        if rotulo:
            c.append(Gtk.Label(label=rotulo))
        mb.set_child(c)
        return mb

    def _barra_comandos(self):
        b = Gtk.Box(spacing=2, css_classes=["barra-comandos"])
        self.menu_novo = Gio.Menu()
        b.append(self._menu_botao(_t("Novo"), "list-add-symbolic", self.menu_novo, _t("Novo item (Ctrl+Shift+N: pasta)"),
                                  ("botao-novo",)))
        b.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        for rot, ic, ac, dica in ((_t("Recortar"), "edit-cut-symbolic", "win.recortar", _t("Recortar (Ctrl+X)")),
                                  (_t("Copiar"), "edit-copy-symbolic", "win.copiar", _t("Copiar (Ctrl+C)")),
                                  (_t("Colar"), "edit-paste-symbolic", "win.colar", _t("Colar (Ctrl+V)")),
                                  (_t("Renomear"), "document-edit-symbolic", "win.renomear", _t("Renomear (F2)")),
                                  (_t("Compartilhar"), "emblem-shared-symbolic", "win.compartilhar", _t("Compartilhar")),
                                  (_t("Excluir"), "user-trash-symbolic", "win.excluir", _t("Excluir (Del) · Shift+Del exclui de vez"))):
            b.append(self._botao(rot, ic, ac, dica, so_icone=True))
        b.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        b.append(self._menu_botao(_t("Classificar"), "view-sort-ascending-symbolic", self._menu_classificar(), _t("Classificar")))
        b.append(self._menu_botao(_t("Exibir"), "view-grid-symbolic", self._menu_exibir(), _t("Exibir")))
        self.botao_restaurar = self._botao(_t("Restaurar"), "edit-undo-symbolic", "win.restaurar", _t("Restaurar da Lixeira"))
        self.botao_esvaziar = self._botao(_t("Esvaziar Lixeira"), "user-trash-full-symbolic", "win.esvaziar-lixeira",
                                          _t("Excluir tudo da Lixeira"))
        b.append(self.botao_restaurar)
        b.append(self.botao_esvaziar)
        b.append(self._menu_botao("", "view-more-symbolic", self._menu_mais(), _t("Ver mais")))
        b.append(Gtk.Box(hexpand=True))
        self.botao_detalhes = Gtk.ToggleButton(css_classes=["flat"], tooltip_text=_t("Painel de detalhes (Alt+Shift+P)"))
        c = Gtk.Box(spacing=6)
        c.append(Gtk.Image(icon_name="sidebar-show-right-symbolic"))
        c.append(Gtk.Label(label=_t("Detalhes")))
        self.botao_detalhes.set_child(c)
        self.botao_detalhes.connect("toggled", lambda bt: self._painel("detalhes" if bt.get_active() else "")
                                    if (self.cfg.get("painel") != "") != bt.get_active() else None)
        b.append(self.botao_detalhes)
        return b

    def _menu_classificar(self):
        m = Gio.Menu()
        s = Gio.Menu()
        for k, n in ORDENS.items():
            s.append(n, f"win.ordem::{k}")
        m.append_section(None, s)
        s2 = Gio.Menu()
        s2.append(_t("Crescente"), "win.desc::nao")
        s2.append(_t("Decrescente"), "win.desc::sim")
        m.append_section(None, s2)
        return m

    def _menu_exibir(self):
        m = Gio.Menu()
        s = Gio.Menu()
        for v in VISOES:
            s.append(NOMES_VISAO[v], f"win.visao::{v}")
        m.append_section(None, s)
        s2 = Gio.Menu()
        s2.append(_t("Painel de detalhes"), "win.painel::detalhes")
        s2.append(_t("Painel de visualização"), "win.painel::visualizar")
        s2.append(_t("Sem painel"), "win.painel::")
        m.append_section(None, s2)
        s3 = Gio.Menu()
        s3.append(_t("Itens ocultos"), "win.ocultos")
        s3.append(_t("Extensões de nomes de arquivos"), "win.extensoes")
        s3.append(_t("Abrir com um clique"), "win.clique-unico")
        m.append_section(_t("Mostrar"), s3)
        return m

    def _menu_mais(self):
        m = Gio.Menu()
        s = Gio.Menu()
        s.append(_t("Desfazer"), "win.desfazer")
        s.append(_t("Selecionar tudo"), "win.selecionar-tudo")
        s.append(_t("Desmarcar tudo"), "win.desmarcar")
        s.append(_t("Inverter seleção"), "win.inverter")
        m.append_section(None, s)
        s2 = Gio.Menu()
        s2.append(_t("Copiar caminho"), "win.copiar-caminho")
        s2.append(_t("Abrir no Terminal"), "win.terminal")
        s2.append(_t("Fixar no Acesso rápido"), "win.fixar")
        s2.append(_t("Propriedades"), "win.propriedades")
        m.append_section(None, s2)
        s3 = Gio.Menu()
        s3.append(_t("Nova janela"), "win.nova-janela")
        s3.append(_t("Ícones mais bonitos (Configurações)"), "win.icones")
        s3.append(_t("Atalhos de teclado"), "win.atalhos")
        s3.append(_t("Sobre o Explorador"), "win.sobre")
        m.append_section(None, s3)
        return m

    def _barra_status(self):
        b = Gtk.Box(spacing=8, css_classes=["barra-status"])
        self.status = Gtk.Label(xalign=0, hexpand=True)
        b.append(self.status)
        # progresso de operação (copiar/mover/...)
        self.prog_caixa = Gtk.Box(spacing=8, visible=False)
        self.prog_rotulo = Gtk.Label(ellipsize=Pango.EllipsizeMode.MIDDLE, max_width_chars=60, css_classes=["legenda"])
        self.prog_barra = Gtk.ProgressBar(valign=Gtk.Align.CENTER, width_request=180)
        cancelar = Gtk.Button(icon_name="process-stop-symbolic", css_classes=["flat"], tooltip_text=_t("Cancelar"))
        cancelar.connect("clicked", lambda *a: self.ops.cancelar.set())
        for w in (self.prog_rotulo, self.prog_barra, cancelar):
            self.prog_caixa.append(w)
        b.append(self.prog_caixa)
        for v, ic, dica in (("detalhes", "view-list-symbolic", _t("Detalhes (Ctrl+Shift+6)")),
                            ("grande", "view-grid-symbolic", _t("Ícones grandes (Ctrl+Shift+2)"))):
            bt = Gtk.Button(icon_name=ic, css_classes=["flat"], tooltip_text=dica, action_name="win.visao",
                            action_target=GLib.Variant.new_string(v))
            b.append(bt)
        return b

    # ── ações e atalhos ────────────────────────────────────────────────────
    def _acoes(self):
        def a(nome, fn, param=None):
            ac = Gio.SimpleAction.new(nome, GLib.VariantType.new(param) if param else None)
            ac.connect("activate", lambda ac, v: fn(v.unpack() if v is not None else None) if param else fn())
            self.add_action(ac)
            return ac

        def estado(nome, inicial, fn):
            ac = Gio.SimpleAction.new_stateful(nome, GLib.VariantType.new("s") if isinstance(inicial, str) else None,
                                               GLib.Variant.new_string(inicial) if isinstance(inicial, str)
                                               else GLib.Variant.new_boolean(inicial))
            ac.connect("change-state", lambda ac, v: (ac.set_state(v), fn(v.unpack())))
            self.add_action(ac)
            return ac
        a("voltar", lambda: self.aba() and self.aba().voltar())
        a("avancar", lambda: self.aba() and self.aba().avancar())
        a("acima", lambda: self.aba() and self.aba().acima())
        a("atualizar", self.atualizar)
        a("inicio", lambda: self.ir_especial("inicio"))
        a("endereco", lambda: self._caminho_modo(True))
        a("pesquisar", lambda: self.pesquisa.grab_focus())
        a("nova-aba", lambda: self.nova_aba(None))
        a("fechar-aba", self._fechar_aba_atual)
        a("reabrir-aba", self._reabrir_aba)
        a("proxima-aba", lambda: self._trocar_aba(1))
        a("aba-anterior", lambda: self._trocar_aba(-1))
        a("aba-n", lambda n: self._aba_n(n), "i")
        a("nova-janela", lambda: self.app.nova_janela(self.aba().local if self.aba() else None))
        a("abrir", self._abrir_selecao)
        a("abrir-nova-aba", lambda: [self.nova_aba(u.arquivo_de(i)) for i in self._selecao() if u.eh_pasta(i)])
        a("abrir-com", self._dialogo_abrir_com)
        a("abrir-com-app", self._abrir_com_app, "s")
        a("novo-pasta", self.nova_pasta)
        a("novo-texto", lambda: self.novo_arquivo(_t("Novo documento de texto.txt")))
        a("novo-vazio", lambda: self.novo_arquivo(_t("Novo arquivo")))
        a("novo-modelo", self._novo_modelo, "s")
        a("recortar", lambda: self._copiar_area(True))
        a("copiar", lambda: self._copiar_area(False))
        a("colar", self.colar)
        a("renomear", self.renomear)
        a("compartilhar", self._compartilhar)
        a("excluir", lambda: self.excluir(False))
        a("excluir-definitivo", lambda: self.excluir(True))
        a("desfazer", self.ops.desfazer)
        a("selecionar-tudo", lambda: self._vista() and self._vista().selecionar_tudo())
        a("desmarcar", lambda: self._vista() and self._vista().selecao.unselect_all())
        a("inverter", lambda: self._vista() and self._vista().inverter_selecao())
        a("copiar-caminho", self._copiar_caminho)
        a("terminal", self._terminal)
        a("propriedades", self.propriedades)
        a("fixar", self._fixar)
        a("favorito", self._favorito)
        a("compactar", self.compactar)
        a("extrair", self.extrair)
        a("papel-parede", self._papel_parede)
        a("enviar-celular", self._enviar_celular)
        a("restaurar", self._restaurar)
        a("esvaziar-lixeira", self._esvaziar)
        a("zoom-mais", lambda: self._vista() and self._vista().zoom(1))
        a("zoom-menos", lambda: self._vista() and self._vista().zoom(-1))
        a("tela-cheia", lambda: self.unfullscreen() if self.is_fullscreen() else self.fullscreen())
        a("atalhos", self._atalhos)
        a("icones", lambda: subprocess.Popen(["/usr/bin/configuracoes", "personalizacao", "icones"]))
        a("sobre", self._sobre)
        a("visao-n", lambda n: self.definir_visao(VISOES[n]), "i")
        a("painel-detalhes", lambda: self._painel("" if self.cfg.get("painel") == "detalhes" else "detalhes"))
        a("painel-visualizar", lambda: self._painel("" if self.cfg.get("painel") == "visualizar" else "visualizar"))
        a("menu-teclado", self._menu_teclado)
        self.ac_ordem = estado("ordem", self.cfg["ordem"], lambda v: self._vista() and self._vista().definir_ordem(v))
        self.ac_desc = estado("desc", "sim" if self.cfg["desc"] else "nao",
                              lambda v: self._vista() and self._vista().definir_ordem(desc=v == "sim"))
        self.ac_visao = estado("visao", self.cfg["visao"], self.definir_visao)
        self.ac_painel = estado("painel", self.cfg.get("painel", ""), self._painel)
        self.ac_ocultos = estado("ocultos", self.cfg["ocultos"], self._ocultos)
        self.ac_extensoes = estado("extensoes", self.cfg["extensoes"], self._extensoes)
        self.ac_clique = estado("clique-unico", self.cfg.get("cliqueUnico", False), self._clique_unico)

    # ── abas ───────────────────────────────────────────────────────────────
    def aba(self):
        p = self.abas.get_selected_page()
        return p.get_child() if p else None

    def _vista(self):
        a = self.aba()
        return a.vista if a else None

    def nova_aba(self, local, selecionar=None, fundo=False):
        aba = Aba(self)
        pag = self.abas.append(aba)
        if not fundo:
            self.abas.set_selected_page(pag)
        if local is None:
            local = "inicio" if self.cfg.get("abrirEm", "inicio") == "inicio" else Gio.File.new_for_path(str(u.HOME))
        aba.ir(local, selecionar=selecionar)
        return aba

    def _fechando_aba(self, view, pag):
        aba = pag.get_child()
        if aba.local is not None:
            self.fechadas.append(aba.local)
        view.close_page_finish(pag, True)
        if view.get_n_pages() == 0:
            self.close()
        return True

    def _fechar_aba_atual(self):
        p = self.abas.get_selected_page()
        if p:
            self.abas.close_page(p)

    def _reabrir_aba(self):
        if self.fechadas:
            self.nova_aba(self.fechadas.pop())

    def _trocar_aba(self, d):
        n = self.abas.get_n_pages()
        if n > 1:
            i = (self.abas.get_page_position(self.abas.get_selected_page()) + d) % n
            self.abas.set_selected_page(self.abas.get_nth_page(i))

    def _aba_n(self, n):
        total = self.abas.get_n_pages()
        if total:
            self.abas.set_selected_page(self.abas.get_nth_page(min(n, total) - 1 if n < 9 else total - 1))

    def _aba_trocada(self):
        a = self.aba()
        if a is not None and a.local is not None:
            self.local_mudou(a)

    # ── navegação ──────────────────────────────────────────────────────────
    def ir(self, local, selecionar=None):
        a = self.aba() or self.nova_aba(None)
        if not isinstance(local, str) and local.get_path() and not os.path.isdir(local.get_path()):
            # arquivo: abre a pasta dele com o arquivo selecionado
            selecionar, local = local.get_basename(), local.get_parent()
        a.ir(local, selecionar=selecionar)

    def ir_especial(self, nome):
        self.ir(nome)

    def local_mudou(self, aba):
        if aba is not self.aba():
            pag = self.abas.get_page(aba)
            pag.set_title(aba.titulo())
            pag.set_icon(aba.icone())
            return
        pag = self.abas.get_page(aba)
        pag.set_title(aba.titulo())
        pag.set_icon(aba.icone())
        self.set_title(_t("%1 — Explorador de Arquivos", aba.titulo()))
        self._migalhas(aba.local)
        marca = aba.local if aba.local != "busca" else None
        self.lateral.marcar(marca)
        # a lista seleciona a 1ª linha quando ganha o foco ao abrir: remarca depois
        GLib.timeout_add(250, lambda: (self.lateral.marcar(marca) if self.aba() is aba else None, False)[1])
        self.lookup_action("voltar").set_enabled(aba.pos > 0)
        self.lookup_action("avancar").set_enabled(aba.pos < len(aba.historia) - 1)
        self.lookup_action("acima").set_enabled(isinstance(aba.local, Gio.File))
        v = aba.vista
        lixeira = isinstance(aba.local, Gio.File) and aba.local.get_uri_scheme() == "trash"
        self.botao_restaurar.set_visible(lixeira)
        self.botao_esvaziar.set_visible(lixeira)
        if v is not None:
            self.ac_visao.set_state(GLib.Variant.new_string(v.visao))
            self.ac_ordem.set_state(GLib.Variant.new_string(v.ordem))
            self.ac_desc.set_state(GLib.Variant.new_string("sim" if v.desc else "nao"))
        nome = aba.titulo() if not isinstance(aba.local, str) else (_t("Início") if aba.local == "inicio" else aba.titulo())
        self.pesquisa.set_placeholder_text(_t("Pesquisar em %1", nome))
        if aba.local != "busca":
            self.pesquisa.set_text("")
        self._atualizar_novo()
        self.selecao_mudou(aba)

    def _migalhas(self, local):
        while (c := self.migalhas.get_first_child()) is not None:
            self.migalhas.remove(c)
        partes = []  # (rótulo, destino)
        if isinstance(local, str):
            if local == "busca":
                a = self.aba()
                partes = [(_t("Resultados da pesquisa em %1", nome_local(Gio.File.new_for_path(a.busca[0]))), "busca")]
            else:
                partes = [(ESPECIAIS[local][0], local)]
            ic = ESPECIAIS[local][1]
        else:
            ic = "folder"
            p = local.get_path()
            casa = str(u.HOME)
            if p and (p == casa or p.startswith(casa + "/")):
                partes.append((u.NOME_PASTA[casa], Gio.File.new_for_path(casa)))
                atual = casa
                for parte in Path(p).relative_to(casa).parts:
                    atual = os.path.join(atual, parte)
                    partes.append((u.NOME_PASTA.get(atual, parte), Gio.File.new_for_path(atual)))
                ic = "user-home"
            elif p:
                partes.append((_t("Este Computador"), "computador"))
                partes.append((_t("Disco local (/)"), Gio.File.new_for_path("/")))
                atual = "/"
                for parte in Path(p).parts[1:]:
                    atual = os.path.join(atual, parte)
                    partes.append((parte, Gio.File.new_for_path(atual)))
                ic = "computer"
            else:
                partes.append((nome_local(local), local))
                ic = "user-trash" if local.get_uri_scheme() == "trash" else "folder-remote"
        self.migalhas.append(Gtk.Image(icon_name=ic, margin_start=6, margin_end=2))
        for i, (rot, dest) in enumerate(partes):
            seta = Gtk.MenuButton(icon_name="go-next-symbolic", css_classes=["flat", "seta"], tooltip_text=_t("Subpastas"))
            if isinstance(dest, Gio.File) and dest.get_path():
                seta.set_create_popup_func(lambda mb, d=dest: self._popup_subpastas(mb, d))
            else:
                seta.set_sensitive(False)
            self.migalhas.append(seta)
            bt = Gtk.Button(label=rot, css_classes=["flat"])
            bt.connect("clicked", lambda b, d=dest: self.ir(d) if d != "busca" else None)
            if isinstance(dest, Gio.File) and dest.get_path():
                self.alvo_soltar_pasta(bt, dest.get_path())
            self.migalhas.append(bt)
        self.caminho_entrada.set_text(local.get_path() or local.get_uri() if isinstance(local, Gio.File) else ESPECIAIS[local][0])

    def _popup_subpastas(self, mb, pasta):
        pop = Gtk.Popover(has_arrow=False)
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        rol = Gtk.ScrolledWindow(max_content_height=420, propagate_natural_height=True, propagate_natural_width=True,
                                 hscrollbar_policy=Gtk.PolicyType.NEVER)
        rol.set_child(caixa)
        try:
            nomes = sorted((e.name for e in os.scandir(pasta.get_path())
                            if e.is_dir() and (self.cfg["ocultos"] or not e.name.startswith("."))),
                           key=lambda n: GLib.utf8_collate_key_for_filename(n, -1))[:300]
        except OSError:
            nomes = []
        for n in nomes:
            bt = Gtk.Button(css_classes=["flat"])
            c = Gtk.Box(spacing=8)
            c.append(Gtk.Image(icon_name=u.ICONE_PASTA.get(os.path.join(pasta.get_path(), n), "folder")))
            c.append(Gtk.Label(label=n, xalign=0))
            bt.set_child(c)
            bt.connect("clicked", lambda b, n=n: (pop.popdown(), self.ir(pasta.get_child(n))))
            caixa.append(bt)
        if not nomes:
            caixa.append(Gtk.Label(label=_t("Sem subpastas"), css_classes=["legenda"], margin_top=8, margin_bottom=8,
                                   margin_start=12, margin_end=12))
        pop.set_child(rol)
        mb.set_popover(pop)

    def _caminho_clicado(self, x, y):
        # clique no espaço vazio da barra de caminho: vira campo de texto
        w = self.migalhas_rol.pick(x, y, Gtk.PickFlags.DEFAULT)
        if w in (self.migalhas, self.migalhas_rol) or isinstance(w, Gtk.Viewport):
            self._caminho_modo(True)

    def _caminho_modo(self, editar):
        self.caminho_pilha.set_visible_child_name("entrada" if editar else "migalhas")
        if editar:
            self.caminho_entrada.grab_focus()
            self.caminho_entrada.select_region(0, -1)

    def _caminho_digitado(self, e):
        t = e.get_text().strip()
        self._caminho_modo(False)
        if not t:
            return
        especiais = {normalizar(v[0]): k for k, v in ESPECIAIS.items()}
        if normalizar(t) in especiais:
            self.ir(especiais[normalizar(t)])
            return
        if t.startswith("~"):
            t = os.path.expanduser(t)
        g = Gio.File.new_for_uri(t) if "://" in t else Gio.File.new_for_path(t)
        if g.get_path() and not os.path.exists(g.get_path()):
            # não é pasta: tenta como comando/app (como o Windows)
            self.aviso(_t("O Explorador não encontra “%1”. Verifique o nome e tente de novo.", t))
            return
        self.ir(g)

    # ── pesquisa ───────────────────────────────────────────────────────────
    def _pesquisa_mudou(self, e):
        v = self._vista()
        a = self.aba()
        if v is not None and a and a.local != "busca":
            v.filtrar_texto(e.get_text())

    def _pesquisa_enter(self, e):
        t = e.get_text().strip()
        a = self.aba()
        if not t or a is None:
            return
        if isinstance(a.local, Gio.File) and a.local.get_path():
            pasta = a.local.get_path()
        elif a.local == "busca":
            pasta = a.busca[0]
        else:
            pasta = str(u.HOME)
        a.busca = (pasta, t)
        a.ir("busca")
        self.status.set_label(_t("Pesquisando…"))

    def pesquisa_terminou(self, aba, n):
        if aba is self.aba():
            self.status.set_label(f"{n} {'resultado' if n == 1 else 'resultados'}" + (_t(" (limite atingido)") if n >= 3000 else ""))
        return False

    # ── seleção / status / detalhes ────────────────────────────────────────
    def _selecao(self):
        v = self._vista()
        return v.selecionados() if v else []

    def _caminhos(self):
        return [u.arquivo_de(i).get_path() for i in self._selecao() if u.arquivo_de(i) and u.arquivo_de(i).get_path()]

    def selecao_mudou(self, aba):
        if aba is not self.aba():
            return
        v = aba.vista
        sel = v.selecionados() if v else []
        tem = bool(sel)
        for nome in ("recortar", "copiar", "renomear", "excluir", "excluir-definitivo", "compartilhar", "abrir-com",
                     "compactar", "favorito", "copiar-caminho"):
            self.lookup_action(nome).set_enabled(tem)
        pasta_local = isinstance(aba.local, Gio.File) and bool(aba.local.get_path())
        for nome in ("colar", "novo-pasta", "novo-texto", "novo-vazio", "terminal"):
            self.lookup_action(nome).set_enabled(pasta_local)
        if v is None:
            self.status.set_label("")
        else:
            n = v.ordenado.get_n_items()
            txt = f"{n} {'item' if n == 1 else 'itens'}"
            if sel:
                txt += f"   |   {len(sel)} {'item selecionado' if len(sel) == 1 else 'itens selecionados'}"
                arqs = [i for i in sel if not u.eh_pasta(i)]
                if arqs:
                    txt += f"  {u.tamanho(sum(i.get_size() for i in arqs))}"
            self.status.set_label(txt)
        if self.detalhes.get_visible():
            pasta_info = u.info_de(aba.local) if isinstance(aba.local, Gio.File) else None
            self.detalhes.mostrar(sel, pasta_info)

    def _painel(self, modo):
        self.cfg["painel"] = modo
        self.detalhes.modo = modo or "detalhes"
        self.detalhes.set_visible(bool(modo))
        if hasattr(self, "ac_painel"):
            self.ac_painel.set_state(GLib.Variant.new_string(modo))
        if hasattr(self, "botao_detalhes") and self.botao_detalhes.get_active() != bool(modo):
            self.botao_detalhes.set_active(bool(modo))
        self.salvar_config()
        a = self.aba()
        if a is not None and modo:
            self.selecao_mudou(a)

    # ── preferências ───────────────────────────────────────────────────────
    def salvar_config(self):
        if getattr(self, "_salvar_pendente", False):
            return
        self._salvar_pendente = True

        def salvar():
            self._salvar_pendente = False
            u.gravar_config(self.cfg)
            return False
        GLib.timeout_add(400, salvar)

    def definir_visao(self, v):
        self.cfg["visao"] = v
        self.ac_visao.set_state(GLib.Variant.new_string(v))
        if self._vista():
            self._vista().definir_visao(v)
        self.salvar_config()

    def _ocultos(self, sim):
        self.cfg["ocultos"] = sim
        for i in range(self.abas.get_n_pages()):
            a = self.abas.get_nth_page(i).get_child()
            if a.vista:
                a.vista.definir_ocultos(sim)
        self.salvar_config()

    def _extensoes(self, sim):
        self.cfg["extensoes"] = sim
        self.salvar_config()
        self.atualizar()

    def _clique_unico(self, sim):
        self.cfg["cliqueUnico"] = sim
        self.salvar_config()
        if self._vista():
            self._vista().view.set_single_click_activate(sim)

    def _lateral_largura(self, *a):
        self.cfg["lateral"] = self.paned.get_position()
        self.salvar_config()

    def atualizar(self):
        a = self.aba()
        if a is None:
            return
        if a.vista and a.vista.dirlist:
            a.vista.recarregar()
        else:
            a.ir(a.local, registrar=False)
        self.lateral.montar()
        self.lateral.marcar(a.local)

    def atualizar_lateral(self):
        self.lateral.montar()
        a = self.aba()
        if a:
            self.lateral.marcar(a.local)
        return False

    def _mudou_montagem(self):
        self.atualizar_lateral()
        a = self.aba()
        if a and a.local == "computador":
            a.ir("computador", registrar=False)
        return False

    # ── abrir ──────────────────────────────────────────────────────────────
    def abrir_info(self, info, nova_aba=False):
        g = u.arquivo_de(info)
        if g is None:
            return
        if u.eh_pasta(info) or info.get_file_type() == Gio.FileType.SHORTCUT:
            alvo = g
            if info.get_file_type() == Gio.FileType.SHORTCUT and info.get_attribute_string("standard::target-uri"):
                alvo = Gio.File.new_for_uri(info.get_attribute_string("standard::target-uri"))
            if nova_aba:
                self.nova_aba(alvo, fundo=True)
            else:
                self.ir(alvo)
            return
        if g.get_uri_scheme() == "trash":
            self.aviso(_t("Restaure o item para abri-lo"))
            return
        ct = u.tipo(info) or ""
        app = Gio.AppInfo.get_default_for_type(ct, False) if ct else None
        if app is None and ct in ARQUIVOS_COMPACTADOS:
            self.extrair([g.get_path()])
            return
        Gtk.RecentManager.get_default().add_item(g.get_uri())
        if app is not None:
            try:
                app.launch([g], self.get_display().get_app_launch_context())
                return
            except GLib.Error:
                pass
        Gtk.FileLauncher.new(g).launch(self, None, None)

    def _abrir_selecao(self):
        sel = self._selecao()
        pastas = [i for i in sel if u.eh_pasta(i)]
        for i in sel:
            if not u.eh_pasta(i):
                self.abrir_info(i)
        if len(pastas) == 1:
            self.abrir_info(pastas[0])
        else:
            for i in pastas:
                self.nova_aba(u.arquivo_de(i), fundo=True)

    def _abrir_com_app(self, app_id):
        app = next((a for a in Gio.AppInfo.get_all() if a.get_id() == app_id), None)
        arqs = [u.arquivo_de(i) for i in self._selecao() if not u.eh_pasta(i)]
        if app and arqs:
            app.launch(arqs, self.get_display().get_app_launch_context())

    def _dialogo_abrir_com(self):
        sel = [i for i in self._selecao() if not u.eh_pasta(i)]
        if not sel:
            return
        ct = u.tipo(sel[0]) or "application/octet-stream"
        d = Adw.Dialog(title=_t("Como deseja abrir este arquivo?"), content_width=420, content_height=560)
        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_start=12, margin_end=12, margin_bottom=12)
        busca = Gtk.SearchEntry(placeholder_text=_t("Procurar um aplicativo"))
        caixa.append(busca)
        lista = Gtk.ListBox(css_classes=["boxed-list"])
        recomendados = {a.get_id() for a in Gio.AppInfo.get_all_for_type(ct)}
        apps = sorted([a for a in Gio.AppInfo.get_all() if a.should_show()],
                      key=lambda a: (a.get_id() not in recomendados, a.get_display_name().casefold()))
        for app in apps:
            r = Adw.ActionRow(title=app.get_display_name(), subtitle=_t("Recomendado") if app.get_id() in recomendados else "",
                              activatable=True)
            r.add_prefix(Gtk.Image(gicon=app.get_icon(), pixel_size=32))
            r._app = app
            lista.append(r)
        lista.set_filter_func(lambda r: normalizar(busca.get_text()) in normalizar(r._app.get_display_name()))
        busca.connect("search-changed", lambda *a: lista.invalidate_filter())
        rol = Gtk.ScrolledWindow(vexpand=True)
        rol.set_child(lista)
        caixa.append(rol)
        ext = (sel[0].get_display_name().rsplit(".", 1)[-1] if "." in sel[0].get_display_name() else "")
        sempre = Gtk.CheckButton(label=_t("Sempre usar este aplicativo para arquivos .%1", ext) if ext else
                                 _t("Sempre usar este aplicativo para este tipo de arquivo"))
        caixa.append(sempre)

        def escolhido(lb, r):
            if sempre.get_active():
                try:
                    r._app.set_as_default_for_type(ct)
                except GLib.Error:
                    pass
            r._app.launch([u.arquivo_de(i) for i in sel], self.get_display().get_app_launch_context())
            d.close()
        lista.connect("row-activated", escolhido)
        tv.set_content(caixa)
        d.set_child(tv)
        d.present(self)

    # ── área de transferência ──────────────────────────────────────────────
    def _copiar_area(self, recortar):
        arqs = [u.arquivo_de(i) for i in self._selecao() if u.arquivo_de(i)]
        if not arqs:
            return
        uris = [f.get_uri() for f in arqs]
        gnome = ("cut" if recortar else "copy") + "\n" + "\n".join(uris)
        prov = Gdk.ContentProvider.new_union([
            Gdk.ContentProvider.new_for_bytes("x-special/gnome-copied-files", GLib.Bytes.new(gnome.encode())),
            Gdk.ContentProvider.new_for_bytes("text/uri-list", GLib.Bytes.new(("\r\n".join(uris) + "\r\n").encode())),
            Gdk.ContentProvider.new_for_value(Gdk.FileList.new_from_list(arqs)),
            Gdk.ContentProvider.new_for_bytes("text/plain;charset=utf-8",
                                              GLib.Bytes.new("\n".join(f.get_path() or f.get_uri() for f in arqs).encode())),
        ])
        self.get_clipboard().set_content(prov)
        self.recortados = set(uris) if recortar else set()
        v = self._vista()
        if v:
            v.sorter.changed(Gtk.SorterChange.DIFFERENT)
        n = len(arqs)
        self.aviso(f"{n} {'item' if n == 1 else 'itens'} {'recortado' if recortar else 'copiado'}{'' if n == 1 else 's'}", 1)

    def colar(self, destino=None):
        a = self.aba()
        if destino is None:
            if not (a and isinstance(a.local, Gio.File) and a.local.get_path()):
                return
            destino = a.local.get_path()
        cb = self.get_clipboard()
        tipos = cb.get_formats().get_mime_types() or []
        mime = next((m for m in ("x-special/gnome-copied-files", "text/uri-list") if m in tipos), None)
        if mime is None:
            if "image/png" in tipos:
                self._colar_imagem(cb, destino)
            elif cb.get_formats().contain_gtype(Gdk.FileList):
                cb.read_value_async(Gdk.FileList, 0, None, lambda c, r: self._colar_lista(
                    "copy", [f.get_uri() for f in c.read_value_finish(r).get_files()], destino))
            return

        def processar(dados):
            linhas = [l.strip() for l in dados.decode("utf-8", "replace").splitlines() if l.strip()]
            modo = "copy"
            if mime == "x-special/gnome-copied-files" and linhas and linhas[0] in ("copy", "cut"):
                modo, linhas = linhas[0], linhas[1:]
            self._colar_lista(modo, [l for l in linhas if not l.startswith("#")], destino)

        def lido(c, res):
            try:
                stream, _ = c.read_finish(res)
            except GLib.Error as e:
                self.aviso(_t("Não foi possível colar: %1", e.message))
                return
            # Lê tudo sem bloquear (o próprio app pode ser quem fornece os dados)
            mem = Gio.MemoryOutputStream.new_resizable()

            def copiado(m, r):
                try:
                    m.splice_finish(r)
                except GLib.Error as e:
                    self.aviso(_t("Não foi possível colar: %1", e.message))
                    return
                processar(m.steal_as_bytes().get_data() or b"")
            mem.splice_async(stream, Gio.OutputStreamSpliceFlags.CLOSE_SOURCE | Gio.OutputStreamSpliceFlags.CLOSE_TARGET,
                             GLib.PRIORITY_DEFAULT, None, copiado)
        cb.read_async([mime], 0, None, lido)

    def _colar_lista(self, modo, uris, destino):
        caminhos = [Gio.File.new_for_uri(x).get_path() for x in uris]
        caminhos = [c for c in caminhos if c]
        if not caminhos:
            return
        if modo == "cut":
            self.ops.mover(caminhos, destino)
            self.recortados = set()
            self.get_clipboard().set_content(None)
        else:
            self.ops.copiar(caminhos, destino)

    def _colar_imagem(self, cb, destino):
        def lido(c, res):
            try:
                tex = c.read_texture_finish(res)
            except GLib.Error:
                return
            alvo = u.nome_livre(destino, "Imagem colada.png")
            tex.save_to_png(str(alvo))
            self._vista() and self._vista().selecionar_quando_aparecer(alvo.name)
        cb.read_texture_async(None, lido)

    def _copiar_caminho(self):
        cam = self._caminhos() or ([self.aba().local.get_path()] if self.aba() and isinstance(self.aba().local, Gio.File) else [])
        if cam:
            self.get_clipboard().set('\n'.join(f'"{c}"' if " " in c else c for c in cam))
            self.aviso(_t("Caminho copiado"), 1)

    # ── criar / renomear / excluir ─────────────────────────────────────────
    def _pasta_atual(self):
        a = self.aba()
        return a.local.get_path() if a and isinstance(a.local, Gio.File) and a.local.get_path() else None

    def _atualizar_novo(self):
        m = self.menu_novo
        m.remove_all()
        s = Gio.Menu()
        s.append(_t("Pasta"), "win.novo-pasta")
        m.append_section(None, s)
        s2 = Gio.Menu()
        s2.append(_t("Documento de texto"), "win.novo-texto")
        s2.append(_t("Arquivo vazio"), "win.novo-vazio")
        modelos = Path(GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_TEMPLATES) or "")
        if modelos.is_dir() and modelos != u.HOME:
            for f in sorted(modelos.iterdir())[:20]:
                if f.is_file():
                    it = Gio.MenuItem.new(f.stem, None)
                    it.set_action_and_target_value("win.novo-modelo", GLib.Variant.new_string(str(f)))
                    s2.append_item(it)
        m.append_section(None, s2)

    def nova_pasta(self):
        p = self._pasta_atual()
        if not p:
            return
        try:
            alvo = self.ops.nova_pasta(p)
        except OSError as e:
            self.aviso(_t("Não foi possível criar a pasta: %1", e.strerror or e))
            return
        self._renomear_quando_aparecer(alvo)

    def novo_arquivo(self, nome, conteudo=b""):
        p = self._pasta_atual()
        if not p:
            return
        try:
            alvo = self.ops.novo_arquivo(p, nome, conteudo)
        except OSError as e:
            self.aviso(_t("Não foi possível criar o arquivo: %1", e.strerror or e))
            return
        self._renomear_quando_aparecer(alvo)

    def _novo_modelo(self, caminho):
        try:
            self.novo_arquivo(os.path.basename(caminho), Path(caminho).read_bytes())
        except OSError:
            pass

    def _renomear_quando_aparecer(self, alvo):
        v = self._vista()
        nome = os.path.basename(alvo)
        tent = [30]

        def tentar():
            tent[0] -= 1
            if v and v.selecionar_nome(nome):
                self.renomear()
                return False
            return tent[0] > 0
        GLib.timeout_add(80, tentar)

    def renomear(self):
        sel = self._selecao()
        if not sel:
            return
        a = self.aba()
        if a and isinstance(a.local, Gio.File) and a.local.get_uri_scheme() == "trash":
            return
        primeiro = sel[0]
        nome = primeiro.get_display_name()
        d = Adw.AlertDialog(heading=_t("Renomear") if len(sel) == 1 else _t("Renomear %1 itens", len(sel)),
                            body="" if len(sel) == 1 else _t("Todos recebem este nome com um número: “Nome (1)”, “Nome (2)”…"))
        e = Gtk.Entry(text=nome if len(sel) == 1 else nome.rsplit(".", 1)[0], activates_default=True)
        d.set_extra_child(e)
        d.add_response("cancelar", _t("Cancelar"))
        d.add_response("ok", _t("Renomear"))
        d.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        d.set_default_response("ok")
        d.set_close_response("cancelar")

        def selecionar_base():
            e.grab_focus()
            fim = len(nome.rsplit(".", 1)[0]) if (len(sel) == 1 and "." in nome[1:] and not u.eh_pasta(primeiro)) else -1
            e.select_region(0, fim)
            return False

        def resp(d, r):
            if r != "ok":
                return
            novo = e.get_text().strip()
            if not novo or "/" in novo:
                self.aviso(_t("Nome inválido"))
                return
            try:
                if len(sel) == 1:
                    if novo != nome:
                        self.ops.renomear(u.arquivo_de(primeiro).get_path(), novo)
                        self._vista() and self._vista().selecionar_quando_aparecer(novo)
                else:
                    for n, i in enumerate(sel, 1):
                        orig = u.arquivo_de(i).get_path()
                        ext = os.path.splitext(orig)[1] if not u.eh_pasta(i) else ""
                        self.ops.renomear(orig, f"{novo} ({n}){ext}")
            except OSError as ex:
                self.aviso(_t("Não foi possível renomear: %1", ex.strerror or ex))
        d.connect("response", resp)
        d.present(self)
        GLib.timeout_add(120, selecionar_base)

    def excluir(self, definitivo):
        sel = self._selecao()
        if not sel:
            return
        a = self.aba()
        na_lixeira = a and isinstance(a.local, Gio.File) and a.local.get_uri_scheme() == "trash"
        if na_lixeira or definitivo or any(not i.get_attribute_boolean("access::can-trash") for i in sel):
            n = len(sel)
            d = Adw.AlertDialog(heading=_t("Excluir permanentemente?"),
                                body=(f"“{sel[0].get_display_name()}”" if n == 1 else f"{n} itens") +
                                _t(" vão ser apagados de vez — não vão para a Lixeira."))
            d.add_response("cancelar", _t("Cancelar"))
            d.add_response("excluir", _t("Excluir"))
            d.set_response_appearance("excluir", Adw.ResponseAppearance.DESTRUCTIVE)
            d.set_close_response("cancelar")
            alvos = [u.arquivo_de(i).get_uri() if na_lixeira else u.arquivo_de(i).get_path() for i in sel]
            d.connect("response", lambda d, r: self.ops.excluir(alvos) if r == "excluir" else None)
            d.present(self)
            return
        self.ops.lixeira([u.arquivo_de(i).get_path() for i in sel])

    def _restaurar(self):
        sel = self._selecao()
        a = self.aba()
        if a and isinstance(a.local, Gio.File) and a.local.get_uri_scheme() == "trash":
            if not sel:
                v = self._vista()
                sel = [v.ordenado.get_item(p) for p in range(v.ordenado.get_n_items())] if v else []
            self.ops.restaurar([u.arquivo_de(i).get_uri() for i in sel])

    def _esvaziar(self):
        d = Adw.AlertDialog(heading=_t("Esvaziar a Lixeira?"), body=_t("Todos os itens da Lixeira serão apagados de vez."))
        d.add_response("cancelar", _t("Cancelar"))
        d.add_response("sim", _t("Esvaziar"))
        d.set_response_appearance("sim", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_close_response("cancelar")
        d.connect("response", lambda d, r: self.ops.esvaziar_lixeira() if r == "sim" else None)
        d.present(self)

    def soltar(self, caminhos, destino, copiar):
        (self.ops.copiar if copiar else self.ops.mover)(caminhos, destino)

    def alvo_soltar_pasta(self, widget, pasta):
        alvo = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY | Gdk.DragAction.MOVE)

        def soltou(t, val, x, y):
            cams = [f.get_path() for f in val.get_files() if f.get_path()]
            if not cams or pasta in cams:
                return False
            st = t.get_current_event_state()
            if st & Gdk.ModifierType.CONTROL_MASK:
                copiar = True
            elif st & Gdk.ModifierType.SHIFT_MASK:
                copiar = False
            else:
                try:
                    copiar = os.stat(cams[0]).st_dev != os.stat(pasta).st_dev
                except OSError:
                    copiar = True
            self.soltar(cams, pasta, copiar)
            return True
        alvo.connect("drop", soltou)
        widget.add_controller(alvo)

    def compactar(self):
        cams = self._caminhos()
        if not cams:
            return
        base = os.path.basename(cams[0]) if len(cams) == 1 else os.path.basename(os.path.dirname(cams[0]))
        alvo = u.nome_livre(os.path.dirname(cams[0]), (base.rsplit(".", 1)[0] if os.path.isfile(cams[0]) else base) + ".zip")
        self.ops.compactar(cams, alvo)
        self._vista() and self._vista().selecionar_quando_aparecer(alvo.name, 100)

    def extrair(self, cams=None):
        cams = cams or self._caminhos()
        for c in cams[:1]:
            nome = os.path.basename(c)
            for ext in (".tar.gz", ".tar.xz", ".tar.bz2", ".tar.zst", ".tgz", ".zip", ".7z", ".rar", ".tar", ".iso", ".jar"):
                if nome.lower().endswith(ext):
                    nome = nome[:-len(ext)]
                    break
            alvo = u.nome_livre(os.path.dirname(c), nome)
            self.ops.extrair(c, alvo)

    # ── outros comandos ────────────────────────────────────────────────────
    def _terminal(self):
        sel = [i for i in self._selecao() if u.eh_pasta(i)]
        p = u.arquivo_de(sel[0]).get_path() if sel else self._pasta_atual()
        if p:
            u.abrir_terminal(p)

    def _fixar(self):
        sel = [i for i in self._selecao() if u.eh_pasta(i)]
        alvos = [u.arquivo_de(i).get_path() for i in sel] or ([self._pasta_atual()] if self._pasta_atual() else [])
        mudou = False
        for p in alvos:
            if p and p not in self.cfg["fixados"]:
                self.cfg["fixados"].append(p)
                mudou = True
        if mudou:
            self.salvar_config()
            self.app.atualizar_laterais()
            self.aviso(_t("Fixado no Acesso rápido"), 1)

    def desafixar(self, p):
        if p in self.cfg["fixados"]:
            self.cfg["fixados"].remove(p)
            self.salvar_config()
            self.app.atualizar_laterais()
            a = self.aba()
            if a and a.local == "inicio":
                a.ir("inicio", registrar=False)

    def _favorito(self):
        mudou = False
        for p in self._caminhos():
            if p in self.cfg["favoritos"]:
                self.cfg["favoritos"].remove(p)
            else:
                self.cfg["favoritos"].insert(0, p)
            mudou = True
        if mudou:
            self.salvar_config()
            self.aviso(_t("Favoritos atualizados"), 1)

    def _papel_parede(self):
        cams = self._caminhos()
        if cams:
            subprocess.Popen(["simba-theme-bg-set", cams[0]], start_new_session=True)
            self.aviso(_t("Papel de parede alterado"), 1)

    def _enviar_celular(self):
        cams = self._caminhos()
        if cams:
            subprocess.Popen(["localsend", *cams], start_new_session=True)

    def _compartilhar(self):
        cams = self._caminhos()
        if not cams:
            return
        m = Gio.Menu()
        m.append(_t("Enviar com o LocalSend (computadores e celulares por perto)"), "win.compartilhar-localsend")
        m.append(_t("Anexar num e-mail"), "win.compartilhar-email")
        m.append(_t("Copiar caminho"), "win.copiar-caminho")
        for nome, fn in (("compartilhar-localsend", lambda: subprocess.Popen(["localsend", *cams], start_new_session=True)),
                         ("compartilhar-email", lambda: subprocess.Popen(["xdg-email", *sum((["--attach", c] for c in cams), [])],
                                                                         start_new_session=True))):
            ac = Gio.SimpleAction.new(nome, None)
            ac.connect("activate", lambda *a, fn=fn: fn())
            self.add_action(ac)
        pop = Gtk.PopoverMenu.new_from_model(m)
        pop.set_parent(self.raiz)
        pop.set_has_arrow(False)
        pop.set_pointing_to(u.retangulo(self.get_width() // 2 - 100, 120))
        pop.connect("closed", lambda p: GLib.idle_add(p.unparent))
        pop.popup()

    def propriedades(self, infos=None):
        sel = infos or self._selecao()
        if not sel:
            a = self.aba()
            if a and isinstance(a.local, Gio.File):
                i = u.info_de(a.local)
                sel = [i] if i else []
        if not sel:
            return
        d = Adw.Dialog(title=_t("Propriedades"), content_width=440)
        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())
        pag = Adw.PreferencesPage()
        g = Adw.PreferencesGroup()
        info = sel[0]
        cab = Gtk.Box(spacing=14, margin_bottom=10)
        cab.append(Gtk.Image(gicon=info.get_icon(), pixel_size=56))
        cab.append(Gtk.Label(label=info.get_display_name() if len(sel) == 1 else f"{len(sel)} itens", wrap=True,
                             xalign=0, css_classes=["title-3"], hexpand=True))
        g.add(cab)
        pag.add(g)
        g2 = Adw.PreferencesGroup()

        def linha(t, v):
            r = Adw.ActionRow(title=t, subtitle=v, subtitle_selectable=True)
            r.add_css_class("property")
            g2.add(r)
            return r
        linha(_t("Tipo"), u.tipo_desc(info) if len(sel) == 1 else _t("Vários tipos"))
        gf = u.arquivo_de(info)
        pai = gf.get_parent()
        linha(_t("Local"), (pai.get_path() or pai.get_uri()) if pai else "")
        r_tam = linha(_t("Tamanho"), _t("Calculando…"))
        r_cont = linha(_t("Contém"), "…") if any(u.eh_pasta(i) for i in sel) else None
        if len(sel) == 1:
            linha(_t("Modificado"), u.data(info.get_modification_date_time()))
            if info.get_creation_date_time():
                linha(_t("Criado"), u.data(info.get_creation_date_time()))
            if info.get_access_date_time():
                linha(_t("Acessado"), u.data(info.get_access_date_time()))
            if info.has_attribute("owner::user"):
                linha(_t("Dono"), info.get_attribute_string("owner::user"))
        pag.add(g2)
        if len(sel) == 1 and gf.get_path():
            g3 = Adw.PreferencesGroup(title=_t("Atributos"))
            modo = info.get_attribute_uint32("unix::mode")
            linha_perm = Adw.ActionRow(title=_t("Permissões"), subtitle=modo_texto(modo))
            g3.add(linha_perm)
            so_leitura = Adw.SwitchRow(title=_t("Somente leitura"), active=not (modo & 0o200))
            executavel = Adw.SwitchRow(title=_t("Permitir executar como programa"), active=bool(modo & 0o100),
                                       visible=not u.eh_pasta(info))

            def mudar(*a):
                m = os.stat(gf.get_path()).st_mode
                m = (m & ~0o222) if so_leitura.get_active() else (m | 0o200)
                if not u.eh_pasta(info):
                    m = (m | 0o111) if executavel.get_active() else (m & ~0o111)
                try:
                    os.chmod(gf.get_path(), m)
                    linha_perm.set_subtitle(modo_texto(os.stat(gf.get_path()).st_mode))
                except OSError as e:
                    self.aviso(_t("Não foi possível mudar: %1", e.strerror))
            so_leitura.connect("notify::active", mudar)
            executavel.connect("notify::active", mudar)
            g3.add(so_leitura)
            g3.add(executavel)
            pag.add(g3)
        tv.set_content(pag)
        d.set_child(tv)
        d.present(self)

        def medir():
            total, arqs, pastas = 0, 0, 0
            for i in sel:
                p = u.arquivo_de(i).get_path()
                if not p:
                    total += i.get_size()
                    continue
                if os.path.isdir(p) and not os.path.islink(p):
                    for raiz, ds, fs in os.walk(p):
                        pastas += len(ds)
                        for f in fs:
                            arqs += 1
                            try:
                                total += os.lstat(os.path.join(raiz, f)).st_size
                            except OSError:
                                pass
                else:
                    arqs += 1
                    total += i.get_size()

            def mostrar():
                r_tam.set_subtitle(f"{u.tamanho(total)} ({total:,} bytes)".replace(f"({total:,}", "(" + f"{total:,}".replace(",", ".")))
                if r_cont:
                    r_cont.set_subtitle(_t("%1 arquivos, %2 pastas", arqs, pastas))
                return False
            GLib.idle_add(mostrar)
        threading.Thread(target=medir, daemon=True).start()

    # ── menus de contexto ──────────────────────────────────────────────────
    def _popover(self, menu, x, y, icones=None, parent=None):
        # submenus abrem ao lado (como no Windows), e o menu mede a altura certa
        pop = Gtk.PopoverMenu.new_from_model_full(menu, Gtk.PopoverMenuFlags.NESTED)
        pop.add_css_class("menu-win")
        parent = parent or self.raiz
        pop.set_parent(parent)
        pop.set_has_arrow(False)
        pop.set_pointing_to(u.retangulo(x, y))
        if icones:
            caixa = Gtk.Box(spacing=2, halign=Gtk.Align.CENTER, css_classes=["icones-topo"])
            for ic, ac, dica in icones:
                bt = Gtk.Button(icon_name=ic, action_name=ac, css_classes=["flat"], tooltip_text=dica)
                bt.connect("clicked", lambda b: pop.popdown())
                caixa.append(bt)
            pop.add_child(caixa, "icones")
        pop.connect("closed", lambda p: GLib.idle_add(lambda: (p.unparent(), False)[1]))
        # abre no próximo ciclo: já estilizado, o GTK mede a altura certa (senão cortava o último item)
        GLib.idle_add(lambda: (pop.popup(), False)[1])
        return pop

    def menu_contexto(self, x, y, em_item):
        a = self.aba()
        lixeira = a and isinstance(a.local, Gio.File) and a.local.get_uri_scheme() == "trash"
        sel = self._selecao()
        m = Gio.Menu()
        if lixeira:
            s = Gio.Menu()
            if em_item:
                s.append(_t("Restaurar"), "win.restaurar")
                s.append(_t("Excluir permanentemente"), "win.excluir")
                s.append(_t("Propriedades"), "win.propriedades")
            else:
                s.append(_t("Restaurar todos os itens"), "win.restaurar")
                s.append(_t("Esvaziar Lixeira"), "win.esvaziar-lixeira")
                s.append(_t("Atualizar"), "win.atualizar")
            m.append_section(None, s)
            self._popover(m, x, y)
            return
        if em_item and sel:
            topo = Gio.Menu()
            it = Gio.MenuItem.new(None, None)
            it.set_attribute_value("custom", GLib.Variant.new_string("icones"))
            topo.append_item(it)
            m.append_section(None, topo)
            s = Gio.Menu()
            s.append(_t("Abrir"), "win.abrir")
            pastas = [i for i in sel if u.eh_pasta(i)]
            arquivos = [i for i in sel if not u.eh_pasta(i)]
            if pastas:
                s.append(_t("Abrir em nova aba"), "win.abrir-nova-aba")
                s.append(_t("Abrir no Terminal"), "win.terminal")
            if arquivos:
                com = Gio.Menu()
                ct = u.tipo(arquivos[0]) or ""
                for app in Gio.AppInfo.get_all_for_type(ct)[:10] if ct else []:
                    item = Gio.MenuItem.new(app.get_display_name(), None)
                    item.set_action_and_target_value("win.abrir-com-app", GLib.Variant.new_string(app.get_id()))
                    item.set_icon(app.get_icon() or Gio.ThemedIcon.new("application-x-executable"))
                    com.append_item(item)
                outro = Gio.Menu()
                outro.append(_t("Escolher outro aplicativo…"), "win.abrir-com")
                com.append_section(None, outro)
                s.append_submenu(_t("Abrir com"), com)
            m.append_section(None, s)
            s2 = Gio.Menu()
            if pastas:
                fixado = all(u.arquivo_de(i).get_path() in self.cfg["fixados"] for i in pastas)
                if not fixado:
                    s2.append(_t("Fixar no Acesso rápido"), "win.fixar")
            s2.append(_t("Remover dos Favoritos") if all(p in self.cfg["favoritos"] for p in self._caminhos())
                      else _t("Adicionar aos Favoritos"), "win.favorito")
            s2.append(_t("Compactar para arquivo ZIP"), "win.compactar")
            if len(arquivos) == 1 and (u.tipo(arquivos[0]) or "") in ARQUIVOS_COMPACTADOS:
                s2.append(_t("Extrair tudo aqui"), "win.extrair")
            if len(arquivos) == 1 and (u.tipo(arquivos[0]) or "").startswith("image/"):
                s2.append(_t("Definir como papel de parede"), "win.papel-parede")
            if shutil.which("localsend"):
                s2.append(_t("Enviar com LocalSend (celular e PC)"), "win.enviar-celular")
            s2.append(_t("Copiar como caminho"), "win.copiar-caminho")
            m.append_section(None, s2)
            s3 = Gio.Menu()
            s3.append(_t("Excluir permanentemente"), "win.excluir-definitivo")
            s3.append(_t("Propriedades"), "win.propriedades")
            m.append_section(None, s3)
            self._popover(m, x, y, icones=[("edit-cut-symbolic", "win.recortar", _t("Recortar")),
                                           ("edit-copy-symbolic", "win.copiar", _t("Copiar")),
                                           ("document-edit-symbolic", "win.renomear", _t("Renomear")),
                                           ("emblem-shared-symbolic", "win.compartilhar", _t("Compartilhar")),
                                           ("user-trash-symbolic", "win.excluir", _t("Excluir"))])
            return
        # fundo da pasta
        s = Gio.Menu()
        s.append_submenu(_t("Exibir"), self._menu_exibir())
        s.append_submenu(_t("Classificar por"), self._menu_classificar())
        s.append(_t("Atualizar"), "win.atualizar")
        m.append_section(None, s)
        s2 = Gio.Menu()
        s2.append(_t("Colar"), "win.colar")
        s2.append(_t("Desfazer"), "win.desfazer")
        m.append_section(None, s2)
        s3 = Gio.Menu()
        s3.append_submenu(_t("Novo"), self.menu_novo)
        s3.append(_t("Abrir no Terminal"), "win.terminal")
        s3.append(_t("Selecionar tudo"), "win.selecionar-tudo")
        m.append_section(None, s3)
        s4 = Gio.Menu()
        s4.append(_t("Fixar no Acesso rápido"), "win.fixar")
        s4.append(_t("Propriedades"), "win.propriedades")
        m.append_section(None, s4)
        self._popover(m, x, y)

    def _menu_teclado(self):
        """Shift+F10 / tecla Menu: o menu de contexto da seleção."""
        v = self._vista()
        if v:
            self.menu_contexto(self.get_width() / 2, self.get_height() / 3, bool(v.selecionados()))

    def menu_fixado(self, w, caminho, x, y):
        m = Gio.Menu()
        ac = Gio.SimpleAction.new("desafixar-ctx", None)
        ac.connect("activate", lambda *a: self.desafixar(caminho))
        self.add_action(ac)
        ac2 = Gio.SimpleAction.new("abrir-ctx", None)
        ac2.connect("activate", lambda *a: self.nova_aba(Gio.File.new_for_path(caminho)))
        self.add_action(ac2)
        m.append(_t("Abrir em nova aba"), "win.abrir-ctx")
        m.append(_t("Desafixar do Acesso rápido"), "win.desafixar-ctx")
        jx, jy = u.coords(w, self.raiz, x, y)
        self._popover(m, jx, jy)

    def menu_lateral(self, lista, row, x, y):
        d = row._destino
        m = Gio.Menu()
        for nome in ("lat-aba", "lat-desafixar", "lat-fixar", "lat-prop", "lat-esvaziar", "lat-terminal"):
            if self.lookup_action(nome):
                self.remove_action(nome)

        def ac(nome, fn):
            a = Gio.SimpleAction.new(nome, None)
            a.connect("activate", lambda *x: fn())
            self.add_action(a)
        if not isinstance(d, str):
            ac("lat-aba", lambda: self.nova_aba(d))
            m.append(_t("Abrir em nova aba"), "win.lat-aba")
            if d.get_path():
                ac("lat-terminal", lambda: u.abrir_terminal(d.get_path()))
                m.append(_t("Abrir no Terminal"), "win.lat-terminal")
            if row._secao == "fixados":
                ac("lat-desafixar", lambda: self.desafixar(d.get_path()))
                m.append(_t("Desafixar do Acesso rápido"), "win.lat-desafixar")
            elif d.get_path() and d.get_path() not in self.cfg["fixados"]:
                ac("lat-fixar", lambda: (self.cfg["fixados"].append(d.get_path()), self.salvar_config(),
                                         self.app.atualizar_laterais()))
                m.append(_t("Fixar no Acesso rápido"), "win.lat-fixar")
            if d.get_uri_scheme() == "trash":
                m.append(_t("Esvaziar Lixeira"), "win.esvaziar-lixeira")
            ac("lat-prop", lambda: self.propriedades([u.info_de(d)] if u.info_de(d) else None))
            m.append(_t("Propriedades"), "win.lat-prop")
        else:
            return
        jx, jy = u.coords(lista, self.raiz, x, y)
        self._popover(m, jx, jy)

    def menu_arquivo_avulso(self, w, info, x, y):
        """Botão direito num item da página Início (recentes/favoritos)."""
        g = u.arquivo_de(info)
        for nome in ("av-abrir", "av-local", "av-fav", "av-prop"):
            if self.lookup_action(nome):
                self.remove_action(nome)

        def ac(nome, fn):
            a = Gio.SimpleAction.new(nome, None)
            a.connect("activate", lambda *x: fn())
            self.add_action(a)
        ac("av-abrir", lambda: self.abrir_info(info))
        ac("av-local", lambda: self.ir(g))
        ac("av-fav", lambda: (self.cfg["favoritos"].remove(g.get_path()) if g.get_path() in self.cfg["favoritos"]
                              else self.cfg["favoritos"].insert(0, g.get_path()), self.salvar_config(),
                              self.aba().ir("inicio", registrar=False)))
        ac("av-prop", lambda: self.propriedades([info]))
        m = Gio.Menu()
        m.append(_t("Abrir"), "win.av-abrir")
        m.append(_t("Abrir local do arquivo"), "win.av-local")
        m.append(_t("Remover dos Favoritos") if g.get_path() in self.cfg["favoritos"] else _t("Adicionar aos Favoritos"), "win.av-fav")
        m.append(_t("Propriedades"), "win.av-prop")
        jx, jy = u.coords(w, self.raiz, x, y)
        self._popover(m, jx, jy)

    # ── nuvem ──────────────────────────────────────────────────────────────
    def dialogo_nuvem(self, prov):
        d = Adw.Dialog(title=_t("Conectar %1", prov['nome']), content_width=440)
        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())
        pag = Adw.PreferencesPage()
        g = Adw.PreferencesGroup(description=_t("Abre o login no navegador; depois a nuvem aparece como uma pasta.")
                                 if prov["oauth"] else _t("Os dados ficam só neste computador, no rclone."))
        img = Gtk.Image(pixel_size=64, margin_bottom=8)
        img.set_from_file(nuvem.icone(prov["id"]))
        topo = Adw.PreferencesGroup()
        topo.add(img)
        pag.add(topo)
        pag.add(g)
        nome = Adw.EntryRow(title=_t("Nome da pasta"), text=prov["nome"])
        g.add(nome)
        campos = {}
        for chave, rotulo, segredo in prov.get("campos", []):
            r = Adw.PasswordEntryRow(title=rotulo) if segredo else Adw.EntryRow(title=rotulo)
            if segredo:
                # Campo de senha sem método de entrada: com fcitx5 no Wayland, o
                # campo travava depois do 1º caractere (mesma correção do simba-senha).
                texto = r.get_delegate()
                if texto is not None:
                    texto.set_property("im-module", "gtk-im-context-simple")
            g.add(r)
            campos[chave] = r
        estado = Gtk.Label(wrap=True, css_classes=["legenda"], margin_top=12, visible=False)
        link = Gtk.LinkButton(label=_t("Abrir a página de login"), visible=False)
        bt = Gtk.Button(label=_t("Conectar"), css_classes=["suggested-action", "pill"], halign=Gtk.Align.CENTER, margin_top=16)
        fim = Adw.PreferencesGroup()
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for w in (bt, estado, link):
            caixa.append(w)
        fim.add(caixa)
        pag.add(fim)

        def conectar(*a):
            titulo = nome.get_text().strip() or prov["nome"]
            valores = {k: r.get_text() for k, r in campos.items()}
            bt.set_sensitive(False)
            bt.set_label(_t("Conectando…"))
            estado.set_visible(True)
            estado.set_label(_t("Faça o login na janela do navegador que abriu…") if prov["oauth"] else _t("Conectando…"))

            def aviso_link(url):
                GLib.idle_add(lambda: (link.set_uri(url), link.set_visible(True), False)[2])

            def trabalho():
                try:
                    n = nuvem.conectar(prov["id"], titulo, valores, aviso_link)
                    erro = None
                except Exception as e:  # noqa: BLE001
                    n, erro = None, str(e)

                def pronto():
                    if erro:
                        bt.set_sensitive(True)
                        bt.set_label(_t("Tentar de novo"))
                        estado.set_label(_t("Não foi possível conectar: %1", erro[:300]))
                        return False
                    d.close()
                    self.app.atualizar_laterais()
                    self.aviso(f"{titulo} conectado", 2)
                    GLib.timeout_add(1500, lambda: (self.ir(Gio.File.new_for_path(str(nuvem.RAIZ / n))), False)[1])
                    return False
                GLib.idle_add(pronto)
            threading.Thread(target=trabalho, daemon=True).start()
        bt.connect("clicked", conectar)
        tv.set_content(pag)
        d.set_child(tv)
        d.present(self)

    def remover_nuvem(self, c):
        d = Adw.AlertDialog(heading=_t("Remover %1?", c['titulo']),
                            body=_t("A pasta some deste computador e o login é apagado. Os arquivos continuam na nuvem."))
        d.add_response("cancelar", _t("Cancelar"))
        d.add_response("sim", _t("Remover"))
        d.set_response_appearance("sim", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_close_response("cancelar")

        def resp(d, r):
            if r != "sim":
                return
            threading.Thread(target=lambda: (nuvem.desconectar(c["nome"]), GLib.idle_add(self.app.atualizar_laterais),
                                             GLib.idle_add(lambda: (self.aba() and self.aba().local == "nuvem"
                                                                    and self.aba().ir("nuvem", registrar=False), False)[1])),
                             daemon=True).start()
        d.connect("response", resp)
        d.present(self)

    # ── operações: progresso, fim, conflito ────────────────────────────────
    def _progresso(self, ops, texto, frac):
        self.prog_caixa.set_visible(True)
        self.prog_rotulo.set_label(texto)
        if frac < 0:
            self.prog_barra.pulse()
        else:
            self.prog_barra.set_fraction(frac)

    def _terminou(self, ops, msg, ok):
        self.prog_caixa.set_visible(False)
        if msg:
            self.aviso(msg, 2 if ok else 4)
        self.atualizar_lateral()
        a = self.aba()
        if a and a.vista and a.vista.dirlist is None and a.local not in ("galeria", "busca"):
            a.ir(a.local, registrar=False)

    def _conflito(self, nome, responder):
        d = Adw.AlertDialog(heading=_t("Substituir ou pular arquivos"),
                            body=_t("O destino já tem um item chamado “%1”.", nome))
        todos = Gtk.CheckButton(label=_t("Fazer isso para os próximos conflitos"))
        d.set_extra_child(todos)
        d.add_response("pular", _t("Pular"))
        d.add_response("ambos", _t("Manter ambos"))
        d.add_response("substituir", _t("Substituir"))
        d.set_response_appearance("substituir", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_default_response("ambos")
        d.set_close_response("pular")
        d.connect("response", lambda d, r: responder(r + ("-todos" if todos.get_active() else "")))
        d.present(self)

    def aviso(self, texto, segundos=3):
        self.toast.add_toast(Adw.Toast(title=texto, timeout=segundos))

    # ── diálogos ───────────────────────────────────────────────────────────
    def _atalhos(self):
        d = Adw.ShortcutsDialog()
        secoes = {
            _n("Navegação"): [(_t("Voltar"), "<Alt>Left"), (_t("Avançar"), "<Alt>Right"), (_t("Subir um nível"), "<Alt>Up"),
                          (_t("Início"), "<Alt>Home"), (_t("Ir para o endereço"), "<Control>l"), (_t("Pesquisar"), "<Control>f"),
                          (_t("Atualizar"), "F5"), (_t("Abrir seleção"), _t("Return")), (_t("Abrir em nova aba"), "<Control>Return")],
            _n("Abas e janelas"): [(_t("Nova aba"), "<Control>t"), (_t("Fechar aba"), "<Control>w"), (_t("Reabrir aba fechada"), "<Control><Shift>t"),
                               (_t("Próxima aba"), "<Control>Tab"), (_t("Aba anterior"), "<Control><Shift>Tab"),
                               (_t("Ir para a aba 1–9"), "<Control>1"), (_t("Nova janela"), "<Control>n"), (_t("Tela cheia"), "F11")],
            _n("Arquivos"): [(_t("Nova pasta"), "<Control><Shift>n"), (_t("Renomear"), "F2"), (_t("Recortar"), "<Control>x"),
                         (_t("Copiar"), "<Control>c"), (_t("Colar"), "<Control>v"), (_t("Desfazer"), "<Control>z"),
                         (_t("Mover para a Lixeira"), _t("Delete")), (_t("Excluir permanentemente"), "<Shift>Delete"),
                         (_t("Propriedades"), "<Alt>Return"), (_t("Copiar como caminho"), "<Control><Shift>c"),
                         (_t("Selecionar tudo"), "<Control>a"), (_t("Abrir no Terminal"), "<Control><Alt>t"),
                         (_t("Menu de contexto"), "<Shift>F10")],
            _n("Exibir"): [(_t("Ícones extragrandes … Detalhes"), "<Control><Shift>1"), (_t("Aumentar ícones"), "<Control>plus"),
                       (_t("Diminuir ícones"), "<Control>minus"), (_t("Itens ocultos"), "<Control>h"),
                       (_t("Painel de visualização"), "<Alt>p"), (_t("Painel de detalhes"), "<Alt><Shift>p"),
                       (_t("Atalhos de teclado"), "<Control>question")],
        }
        for titulo, itens in secoes.items():
            s = Adw.ShortcutsSection(title=_t(titulo))
            for t, acel in itens:
                s.add(Adw.ShortcutsItem(title=t, accelerator=acel))
            d.add(s)
        d.present(self)

    def _sobre(self):
        Adw.AboutDialog(application_name=_t("Explorador de Arquivos"), application_icon=APP_ID, version="1.0",
                        developer_name=_t("Renan"), comments=_t("Gerenciador de arquivos do Simba OS."),
                        license_type=Gtk.License.MIT_X11).present(self)

    def _fechar_janela(self, *a):
        u.gravar_config(self.cfg)
        self.app.estilo.esquecer(self._sinal_estilo)
        for s in self._sinais_ops:
            self.ops.disconnect(s)
        vm = Gio.VolumeMonitor.get()
        for s in self._sinais_vm:
            vm.disconnect(s)
        return False


# ── aplicativo ──────────────────────────────────────────────────────────────
DBUS_XML = _t("""<node><interface name="org.freedesktop.FileManager1">
<method name="ShowFolders"><arg type="as" name="URIs" direction="in"/><arg type="s" name="StartupId" direction="in"/></method>
<method name="ShowItems"><arg type="as" name="URIs" direction="in"/><arg type="s" name="StartupId" direction="in"/></method>
<method name="ShowItemProperties"><arg type="as" name="URIs" direction="in"/><arg type="s" name="StartupId" direction="in"/></method>
</interface></node>""")


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_OPEN)
        self.ops = Operacoes()
        # o copiador é um só para todas as janelas: a pergunta de conflito vai para a janela
        # ativa (antes ia para a última aberta, que podia estar atrás, em outra área de
        # trabalho ou fechada, e a cópia ficava esperando uma resposta que nunca vinha)
        self.ops.perguntar = self._conflito
        self.estilo = None
        self.servico = False     # iniciado pelo D-Bus (FileManager1): sem janela inicial

    def _conflito(self, nome, responder):
        jan = self.get_active_window() or next(iter(self.get_windows()), None)
        if jan is None:
            responder("pular")
            return
        jan.present()
        jan._conflito(nome, responder)

    def do_startup(self):
        Adw.Application.do_startup(self)
        self.estilo = Estilo()
        # contas de nuvem montadas com opções antigas: reaplica as rápidas (em segundo plano)
        threading.Thread(target=nuvem.atualizar_montagens, daemon=True).start()
        ac = {
            "win.voltar": ["<Alt>Left", _t("BackSpace"), _t("XF86Back")], "win.avancar": ["<Alt>Right", _t("XF86Forward")],
            "win.acima": ["<Alt>Up"], "win.atualizar": ["F5", "<Control>r"], "win.inicio": ["<Alt>Home"],
            "win.endereco": ["<Control>l", "<Alt>d", "F4"], "win.pesquisar": ["<Control>f", "<Control>e", "F3"],
            "win.nova-aba": ["<Control>t"], "win.fechar-aba": ["<Control>w", "<Control>F4"],
            "win.reabrir-aba": ["<Control><Shift>t"], "win.proxima-aba": ["<Control>Tab", "<Control>Page_Down"],
            "win.aba-anterior": ["<Control><Shift>Tab", "<Control>Page_Up"], "win.nova-janela": ["<Control>n"],
            "win.abrir-nova-aba": ["<Control>Return"], "win.novo-pasta": ["<Control><Shift>n"],
            "win.renomear": ["F2"], "win.recortar": ["<Control>x"], "win.copiar": ["<Control>c"], "win.colar": ["<Control>v"],
            "win.desfazer": ["<Control>z"], "win.excluir": [_t("Delete"), "<Control>d", _t("KP_Delete")],
            "win.excluir-definitivo": ["<Shift>Delete"], "win.propriedades": ["<Alt>Return"],
            "win.copiar-caminho": ["<Control><Shift>c"], "win.selecionar-tudo": ["<Control>a"],
            "win.terminal": ["<Control><Alt>t"], "win.zoom-mais": ["<Control>plus", "<Control>equal", "<Control>KP_Add"],
            "win.zoom-menos": ["<Control>minus", "<Control>KP_Subtract"], "win.tela-cheia": ["F11"],
            "win.atalhos": ["<Control>question", "F1"], "win.painel-visualizar": ["<Alt>p"],
            "win.painel-detalhes": ["<Alt><Shift>p"], "win.menu-teclado": ["<Shift>F10", _t("Menu")],
            "win.ocultos": ["<Control>h"], "win.abrir": ["<Alt>o"],
        }
        # Nuvem conectada/removida (aqui ou por fora): o rclone.conf muda → lateral atualiza
        conf = Gio.File.new_for_path(str(u.HOME / ".config/rclone/rclone.conf"))
        self._mon_rclone = conf.monitor_file(Gio.FileMonitorFlags.NONE, None)
        self._mon_rclone.connect("changed", lambda *a: GLib.timeout_add(1500, self.atualizar_laterais))
        for acao, teclas in ac.items():
            self.set_accels_for_action(acao, teclas)
        for n in range(1, 10):
            self.set_accels_for_action(f"win.aba-n({n})", [f"<Control>{n}", f"<Alt>{n}"])
        for n in range(7):
            self.set_accels_for_action(f"win.visao-n({n})", [f"<Control><Shift>{n + 1}"])
        # "Mostrar na pasta" dos navegadores e outros apps
        try:
            no = Gio.DBusNodeInfo.new_for_xml(DBUS_XML)
            self.get_dbus_connection().register_object("/org/freedesktop/FileManager1", no.interfaces[0],
                                                       self._dbus, None, None)
            Gio.bus_own_name_on_connection(self.get_dbus_connection(), "org.freedesktop.FileManager1",
                                           Gio.BusNameOwnerFlags.REPLACE, None, None)
        except Exception:  # noqa: BLE001
            pass

    def _dbus(self, con, remetente, caminho, iface, metodo, params, invocacao):
        uris, _ = params.unpack()
        arqs = [Gio.File.new_for_uri(x) for x in uris]
        if metodo == "ShowFolders":
            self.nova_janela_varios(arqs)
        elif metodo == "ShowItems":
            self.nova_janela_varios(arqs)
        elif metodo == "ShowItemProperties":
            j = self.nova_janela(arqs[0] if arqs else None)
            infos = [u.info_de(a) for a in arqs]
            GLib.timeout_add(400, lambda: (j.propriedades([i for i in infos if i]), False)[1])
        invocacao.return_value(None)

    def nova_janela(self, local=None):
        j = Janela(self)
        if isinstance(local, Gio.File) and local.get_path() and os.path.isfile(local.get_path()):
            j.nova_aba(local.get_parent(), selecionar=local.get_basename())
        else:
            j.nova_aba(local)
        j.present()
        return j

    def nova_janela_varios(self, arqs):
        j = Janela(self)
        for a in arqs or [None]:
            if isinstance(a, Gio.File) and a.get_path() and os.path.isfile(a.get_path()):
                j.nova_aba(a.get_parent(), selecionar=a.get_basename())
            else:
                j.nova_aba(a)
        j.present()
        return j

    def do_activate(self):
        if self.servico:
            # aberto pelo D-Bus: espera o pedido (ShowItems…) e sai se ninguém abrir janela
            self.servico = False
            self.hold()
            GLib.timeout_add_seconds(20, lambda: (self.release(), False)[1])
            return
        self.nova_janela(None)

    def do_open(self, arquivos, n, dica):
        self.nova_janela_varios(list(arquivos))

    def atualizar_laterais(self):
        for w in self.get_windows():
            if isinstance(w, Janela):
                w.atualizar_lateral()
        return False


if __name__ == "__main__":
    app = App()
    if "--servico" in sys.argv:
        sys.argv.remove("--servico")
        app.servico = True
    sys.exit(app.run(sys.argv))
