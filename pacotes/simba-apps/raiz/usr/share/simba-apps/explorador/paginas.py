"""Páginas especiais do Explorador (Início, Este Computador, Nuvem), a barra lateral e
o painel de detalhes/visualização."""
import os
import threading

from gi.repository import Gdk, Gio, GLib, Gtk, Pango

import nuvem
import utilidades as u
import sys as _sys, os as _os  # noqa: E401
_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))
from simba_i18n import t as _t, n as _n  # noqa: E402  (traduções: /usr/share/simba-apps/idiomas)


def titulo(texto):
    return Gtk.Label(label=texto, xalign=0, css_classes=["titulo-pagina"])


def rolagem(filho):
    r = Gtk.ScrolledWindow(hexpand=True, vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
    r.set_child(filho)
    return r


def clique(w, fn, botao=1):
    g = Gtk.GestureClick(button=botao)
    g.connect("released" if botao == 1 else "pressed", lambda g, n, x, y: fn(n, x, y))
    w.add_controller(g)


def icone_de(caminho, padrao="folder"):
    return u.ICONE_PASTA.get(caminho, padrao)


# ── Início ──────────────────────────────────────────────────────────────────
class Inicio(Gtk.Box):
    def __init__(self, janela):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.janela = janela
        self.corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_bottom=24)
        self.append(rolagem(self.corpo))
        self.montar()
        # recentes mudam enquanto a página está aberta
        self._sinal = Gtk.RecentManager.get_default().connect("changed", lambda *a: GLib.idle_add(self.montar))

    def do_unroot(self):
        Gtk.RecentManager.get_default().disconnect(self._sinal)
        Gtk.Box.do_unroot(self)

    def montar(self):
        while (c := self.corpo.get_first_child()) is not None:
            self.corpo.remove(c)
        cfg = self.janela.cfg
        self.corpo.append(titulo(_t("Acesso rápido")))
        fluxo = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6, min_children_per_line=1,
                            row_spacing=8, column_spacing=8, margin_start=24, margin_end=24, homogeneous=True)
        for p in cfg["fixados"]:
            if not os.path.isdir(p):
                continue
            fluxo.append(self._bloco(p))
        self.corpo.append(fluxo)

        self.corpo.append(titulo(_t("Favoritos")))
        favs = [p for p in cfg["favoritos"] if os.path.exists(p)]
        if favs:
            self.corpo.append(self._lista([(Gio.File.new_for_path(p), None) for p in favs]))
        else:
            self.corpo.append(Gtk.Label(label=_t("Clique com o botão direito num arquivo e escolha “Adicionar aos Favoritos”."),
                                        xalign=0, margin_start=24, css_classes=["legenda"]))

        self.corpo.append(titulo(_t("Recentes")))
        itens = []
        for r in Gtk.RecentManager.get_default().get_items():
            uri = r.get_uri()
            if not uri.startswith("file://") or not r.exists():
                continue
            caminho = Gio.File.new_for_uri(uri).get_path() or ""
            if "/." in caminho:
                continue
            itens.append((r.get_modified().to_unix(), Gio.File.new_for_uri(uri), r.get_modified()))
        itens.sort(key=lambda x: -x[0])
        if itens:
            self.corpo.append(self._lista([(f, d) for _, f, d in itens[:40]]))
        else:
            self.corpo.append(Gtk.Label(label=_t("Os arquivos que você abrir vão aparecer aqui."), xalign=0, margin_start=24,
                                        css_classes=["legenda"]))

    def _bloco(self, caminho):
        b = Gtk.Box(spacing=12, css_classes=["bloco"], width_request=200)
        b.append(Gtk.Image(icon_name=icone_de(caminho), pixel_size=40))
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, valign=Gtk.Align.CENTER)
        txt.append(Gtk.Label(label=u.NOME_PASTA.get(caminho, os.path.basename(caminho)), xalign=0,
                             ellipsize=Pango.EllipsizeMode.END, max_width_chars=18))
        local = os.path.dirname(caminho).replace(str(u.HOME), "Pessoal", 1) or "/"
        legenda = Gtk.Label(xalign=0, css_classes=["legenda"], ellipsize=Pango.EllipsizeMode.END, max_width_chars=20)
        legenda.set_label(local)
        txt.append(legenda)
        b.append(txt)
        b.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        clique(b, lambda n, x, y: self.janela.ir(Gio.File.new_for_path(caminho)))
        clique(b, lambda n, x, y: self.janela.menu_fixado(b, caminho, x, y), 3)
        clique(b, lambda n, x, y: self.janela.nova_aba(Gio.File.new_for_path(caminho)), 2)
        self.janela.alvo_soltar_pasta(b, caminho)
        return b

    def _lista(self, itens):
        lb = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, margin_start=18, margin_end=18,
                         css_classes=["boxed-list-separate"])
        lb.set_activate_on_single_click(False)
        for gfile, quando in itens:
            info = u.info_de(gfile)
            if info is None:
                continue
            linha = Gtk.Box(spacing=12, margin_top=4, margin_bottom=4, margin_start=6, margin_end=6)
            ic = Gtk.Image(gicon=info.get_icon(), pixel_size=24)
            u.mini_no_icone(info, ic)
            linha.append(ic)
            linha.append(Gtk.Label(label=info.get_display_name(), xalign=0, hexpand=True, ellipsize=Pango.EllipsizeMode.END))
            linha.append(Gtk.Label(label=u.data(quando or info.get_modification_date_time()), xalign=0,
                                   width_request=150, css_classes=["secundario"]))
            pai = gfile.get_parent()
            linha.append(Gtk.Label(label=(pai.get_path() if pai else "").replace(str(u.HOME), "Pessoal", 1), xalign=0,
                                   width_request=260, width_chars=34, max_width_chars=34, ellipsize=Pango.EllipsizeMode.START,
                                   css_classes=["secundario"]))
            row = Gtk.ListBoxRow(child=linha)
            row._gfile, row._info = gfile, info
            lb.append(row)
        lb.connect("row-activated", lambda lb, row: self.janela.abrir_info(row._info))
        clique(lb, lambda n, x, y: self._menu_linha(lb, x, y), 3)
        return lb

    def _menu_linha(self, lb, x, y):
        row = lb.get_row_at_y(int(y))
        if row is not None:
            self.janela.menu_arquivo_avulso(lb, row._info, x, y)


# ── Este Computador ─────────────────────────────────────────────────────────
TIPOS_REAIS = {"ext4", "ext3", "btrfs", "xfs", "vfat", "exfat", "ntfs", "ntfs3", "fuseblk", "f2fs", "zfs",
               "fuse.rclone", "nfs", "nfs4", "cifs", "smb3", "iso9660", "udf"}
OCULTAR = ("/boot", "/efi", "/var", "/run/user", "/snap", "/.snapshots", "/srv", "/opt", "/root", "/tmp", "/usr", "/nix")


def discos():
    """[(ponto, nome, ícone, tipo)] — um por dispositivo, sem os internos do sistema."""
    vistos, out = {}, []
    try:
        linhas = open("/proc/self/mounts").read().splitlines()
    except OSError:
        linhas = []
    for l in linhas:
        dev, ponto, tipo = l.split()[:3]
        ponto = ponto.encode().decode("unicode_escape")
        if tipo not in TIPOS_REAIS:
            continue
        if ponto != "/" and any(ponto == o or ponto.startswith(o + "/") for o in OCULTAR):
            continue
        if ponto.startswith(str(u.HOME / _t("Nuvem"))):
            continue
        chave = dev if tipo != "fuse.rclone" else ponto
        if chave in vistos and len(vistos[chave]) <= len(ponto):
            continue
        vistos[chave] = ponto
    for dev, ponto in vistos.items():
        if ponto == "/":
            nome, ic = _t("Disco local (Sistema)"), "drive-harddisk-system"
        elif ponto == str(u.HOME):
            nome, ic = _t("Pasta pessoal (/home)"), "drive-harddisk"
        elif ponto.startswith(("/run/media", "/media")):
            nome, ic = os.path.basename(ponto), "drive-removable-media"
        else:
            nome, ic = f"{os.path.basename(ponto) or ponto} ({ponto})", "drive-harddisk"
        out.append((ponto, nome, ic))
    out.sort(key=lambda x: (x[0] != "/", x[0]))
    return out


class Computador(Gtk.Box):
    def __init__(self, janela):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.janela = janela
        corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_bottom=24)
        self.append(rolagem(corpo))
        corpo.append(titulo(_t("Pastas")))
        f1 = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=6, row_spacing=8,
                         column_spacing=8, margin_start=24, margin_end=24, homogeneous=True)
        for _, nome, ic, p in u.PASTAS:
            if p.is_dir():
                f1.append(self._pasta(str(p), nome, ic))
        corpo.append(f1)
        corpo.append(titulo(_t("Dispositivos e unidades")))
        self.f2 = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=4, row_spacing=10,
                              column_spacing=10, margin_start=24, margin_end=24, homogeneous=True)
        corpo.append(self.f2)
        for ponto, nome, ic in discos():
            self.f2.append(self._disco(ponto, nome, ic))
        # volumes ainda não montados (pendrives, partições)
        vm = Gio.VolumeMonitor.get()
        for vol in vm.get_volumes():
            if vol.get_mount() is None and vol.can_mount():
                self.f2.append(self._volume(vol))
        nuvens = [n for n in nuvem.listar() if n["ativo"]]
        if nuvens:
            corpo.append(titulo(_t("Nuvem")))
            f3 = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=4, row_spacing=10,
                             column_spacing=10, margin_start=24, margin_end=24, homogeneous=True)
            for n in nuvens:
                f3.append(self._disco(n["pasta"], n["titulo"], nuvem.icone(n["provedor"]) or "folder-remote", nuvem_=n["nome"]))
            corpo.append(f3)

    def _pasta(self, caminho, nome, ic):
        b = Gtk.Box(spacing=12, css_classes=["bloco"])
        b.append(Gtk.Image(icon_name=ic, pixel_size=40))
        b.append(Gtk.Label(label=nome, xalign=0))
        b.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        clique(b, lambda n, x, y: self.janela.ir(Gio.File.new_for_path(caminho)))
        self.janela.alvo_soltar_pasta(b, caminho)
        return b

    def _disco(self, ponto, nome, ic, nuvem_=None):
        b = Gtk.Box(spacing=14, css_classes=["disco"], width_request=280)
        img = Gtk.Image(pixel_size=48)
        if ic.startswith("/"):
            img.set_from_file(ic)
        else:
            img.set_from_icon_name(ic)
        b.append(img)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5, hexpand=True, valign=Gtk.Align.CENTER)
        txt.append(Gtk.Label(label=nome, xalign=0, ellipsize=Pango.EllipsizeMode.END))
        barra = Gtk.LevelBar(min_value=0, max_value=1, css_classes=["uso"])
        legenda = Gtk.Label(xalign=0, css_classes=["legenda"], label="…", wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                            max_width_chars=30)
        txt.append(barra)
        txt.append(legenda)
        b.append(txt)

        def medir():
            r = None
            if nuvem_:
                r = nuvem.espaco(nuvem_)
            else:
                try:
                    s = os.statvfs(ponto)
                    total = s.f_blocks * s.f_frsize
                    if s.f_flag & os.ST_RDONLY and s.f_bavail == 0:
                        r = ("so-leitura", total)   # ISO gravada, CD/DVD: "cheio" é normal, não alerta
                    else:
                        r = (total - s.f_bavail * s.f_frsize, total)
                except OSError:
                    r = None
            GLib.idle_add(mostrar, r)

        def mostrar(r):
            if r and r[1]:
                if r[0] == "so-leitura":
                    barra.set_visible(False)
                    legenda.set_label(_t("Somente leitura · %1", u.tamanho(r[1])))
                else:
                    u.mostrar_uso(barra, legenda, r[0], r[1], curto=True)
            else:
                barra.set_visible(False)
                legenda.set_label(ponto.replace(str(u.HOME), "~", 1))
            return False
        threading.Thread(target=medir, daemon=True).start()
        b.set_cursor(Gdk.Cursor.new_from_name("pointer"))
        clique(b, lambda n, x, y: self.janela.ir(Gio.File.new_for_path(ponto)))
        return b

    def _volume(self, vol):
        b = Gtk.Box(spacing=14, css_classes=["disco"], width_request=280)
        b.append(Gtk.Image(gicon=vol.get_icon(), pixel_size=48))
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.CENTER)
        txt.append(Gtk.Label(label=vol.get_name(), xalign=0))
        txt.append(Gtk.Label(label=_t("Clique para montar"), xalign=0, css_classes=["legenda"]))
        b.append(txt)
        b.set_cursor(Gdk.Cursor.new_from_name("pointer"))

        def montar(*a):
            op = Gtk.MountOperation.new(self.janela)

            def pronto(v, res):
                try:
                    v.mount_finish(res)
                    m = v.get_mount()
                    if m:
                        self.janela.ir(m.get_root())
                except GLib.Error as e:
                    self.janela.aviso(_t("Não foi possível montar: %1", e.message))
            vol.mount(Gio.MountMountFlags.NONE, op, None, pronto)
        clique(b, montar)
        return b


# ── Nuvem ───────────────────────────────────────────────────────────────────
class PaginaNuvem(Gtk.Box):
    def __init__(self, janela):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.janela = janela
        self.corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, margin_bottom=24)
        self.append(rolagem(self.corpo))
        self.montar()

    def montar(self):
        while (c := self.corpo.get_first_child()) is not None:
            self.corpo.remove(c)
        contas = nuvem.listar()
        self.corpo.append(titulo(_t("Suas nuvens")))
        if contas:
            f = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=3, row_spacing=10,
                            column_spacing=10, margin_start=24, margin_end=24, homogeneous=True)
            for c in contas:
                f.append(self._conta(c))
            self.corpo.append(f)
        else:
            self.corpo.append(Gtk.Label(label=_t("Nenhuma nuvem conectada ainda. Escolha uma abaixo — ela aparece como uma pasta, "
                                              "em Nuvem na barra lateral e em ~/Nuvem."),
                                        xalign=0, wrap=True, margin_start=24, margin_end=24, css_classes=["legenda"]))
        self.corpo.append(titulo(_t("Adicionar uma conta")))
        f = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, max_children_per_line=5, row_spacing=10,
                        column_spacing=10, margin_start=24, margin_end=24, homogeneous=True)
        for p in nuvem.PROVEDORES:
            b = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["nuvem-cartao"], width_request=150)
            img = Gtk.Image(pixel_size=48)
            img.set_from_file(nuvem.icone(p["id"]))
            b.append(img)
            b.append(Gtk.Label(label=p["nome"], wrap=True, justify=Gtk.Justification.CENTER))
            b.set_cursor(Gdk.Cursor.new_from_name("pointer"))
            clique(b, lambda n, x, y, p=p: self.janela.dialogo_nuvem(p))
            f.append(b)
        self.corpo.append(f)
        self.corpo.append(Gtk.Label(label=_t("O login abre no navegador (Google, Microsoft, Dropbox, Box, pCloud). "
                                          "Os arquivos ficam na nuvem e são baixados quando você abre; o que você salva "
                                          "na pasta sobe sozinho. Usa o rclone."),
                                    xalign=0, wrap=True, margin_start=24, margin_end=24, margin_top=16, css_classes=["legenda"]))

    def _conta(self, c):
        b = Gtk.Box(spacing=14, css_classes=["nuvem-cartao"])
        img = Gtk.Image(pixel_size=48)
        img.set_from_file(nuvem.icone(c["provedor"]) or "")
        b.append(img)
        txt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True, valign=Gtk.Align.CENTER)
        txt.append(Gtk.Label(label=c["titulo"], xalign=0, ellipsize=Pango.EllipsizeMode.END))
        est = Gtk.Label(xalign=0, css_classes=["legenda"], label=_t("Conectada") if c["ativo"] else _t("Desconectada"),
                        wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR)
        barra = Gtk.LevelBar(min_value=0, max_value=1, css_classes=["uso"], visible=False)
        txt.append(barra)
        txt.append(est)
        b.append(txt)
        caixa_bt = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, valign=Gtk.Align.CENTER)
        abrir = Gtk.Button(label=_t("Abrir") if c["ativo"] else _t("Montar"), css_classes=["suggested-action"])
        sair = Gtk.Button(label=_t("Remover"), css_classes=["flat"])
        caixa_bt.append(abrir)
        caixa_bt.append(sair)
        b.append(caixa_bt)

        def abrir_(*a):
            if c["ativo"]:
                self.janela.ir(Gio.File.new_for_path(c["pasta"]))
            else:
                threading.Thread(target=lambda: (nuvem.montar(c["nome"]), GLib.idle_add(self.janela.atualizar_lateral),
                                                 GLib.idle_add(self.montar)), daemon=True).start()
        abrir.connect("clicked", abrir_)
        sair.connect("clicked", lambda *a: self.janela.remover_nuvem(c))

        def medir():
            r = nuvem.espaco(c["nome"]) if c["ativo"] else None
            GLib.idle_add(mostrar, r)

        def mostrar(r):
            if r:
                u.mostrar_uso(barra, est, r[0], r[1])
            return False
        threading.Thread(target=medir, daemon=True).start()
        return b


# ── barra lateral ───────────────────────────────────────────────────────────
class Lateral(Gtk.Box):
    def __init__(self, janela):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, css_classes=["lateral"])
        self.janela = janela
        self.lista = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE, focus_on_click=False)
        self.lista.connect("row-activated", self._ativada)
        self.lista.set_header_func(self._cabecalho)
        self.append(rolagem(self.lista))
        clique(self.lista, self._menu, 3)
        clique(self.lista, self._meio, 2)
        teclas = Gtk.EventControllerKey()
        teclas.connect("key-pressed", self._tecla)
        self.lista.add_controller(teclas)
        self.montar()

    def _linha(self, nome, icone, destino, secao, recuo=0, pasta=None, seta=None):
        caixa = Gtk.Box(spacing=4, margin_start=2 + recuo)
        caixa.append(Gtk.Box(css_classes=["marca"]))
        # setinha de expandir à esquerda do ícone (como no Windows 11); quem não tem
        # filhos ganha o mesmo espaço vazio, para os ícones ficarem alinhados
        frente = Gtk.Box(spacing=2, margin_end=4)
        if seta:
            b = Gtk.Button(icon_name="pan-end-symbolic", css_classes=["seta-expandir"], valign=Gtk.Align.CENTER,
                           focus_on_click=False, can_focus=False)
            b.connect("clicked", lambda *_: seta())
            frente.append(b)
        else:
            frente.append(Gtk.Box(css_classes=["seta-vazia"]))
        img = Gtk.Image(pixel_size=20)
        if icone.startswith("/"):
            img.set_from_file(icone)
        else:
            img.set_from_icon_name(icone)
        frente.append(img)
        caixa.append(frente)
        caixa.append(Gtk.Label(label=nome, xalign=0, ellipsize=Pango.EllipsizeMode.END, hexpand=True))
        row = Gtk.ListBoxRow(child=caixa, tooltip_text=nome)
        row._destino, row._secao, row._pasta = destino, secao, pasta
        row._seta = b if seta else None
        if pasta:
            self.janela.alvo_soltar_pasta(row, pasta)
        self.lista.append(row)
        return row

    def montar(self):
        self.lista.remove_all()
        self.linhas = []
        L = self.linhas.append
        L(self._linha(_t("Início"), "user-home", "inicio", "inicio"))
        L(self._linha(_t("Galeria"), "folder-pictures", "galeria", "inicio"))
        for c in nuvem.listar():
            if c["ativo"]:
                L(self._linha(c["titulo"], nuvem.icone(c["provedor"]) or "folder-remote",
                              Gio.File.new_for_path(c["pasta"]), "nuvem-topo", pasta=c["pasta"]))
        for p in self.janela.cfg["fixados"]:
            if os.path.isdir(p):
                L(self._linha(u.NOME_PASTA.get(p, os.path.basename(p)), icone_de(p), Gio.File.new_for_path(p),
                              "fixados", pasta=p))
        self.linha_pc = self._linha(_t("Este Computador"), "computer", "computador", "pc", seta=self.alternar_pc)
        L(self.linha_pc)
        self.linhas_discos = []
        for ponto, nome, ic in discos():
            r = self._linha(nome, ic, Gio.File.new_for_path(ponto), "pc", recuo=16, pasta=ponto)
            self.linhas_discos.append(r)
            L(r)
        self._mostrar_discos()
        L(self._linha(_t("Nuvem"), "folder-remote", "nuvem", "pc"))
        L(self._linha(_t("Rede"), "network-workgroup", Gio.File.new_for_uri("network:///"), "pc"))
        cheia = False
        try:
            lix = Gio.File.new_for_uri("trash:///").query_info("trash::item-count", Gio.FileQueryInfoFlags.NONE, None)
            cheia = lix.get_attribute_uint32("trash::item-count") > 0
        except GLib.Error:
            pass
        L(self._linha(_t("Lixeira"), "user-trash-full" if cheia else "user-trash", Gio.File.new_for_uri("trash:///"), "lixo"))

    # ── Este Computador: expandir / recolher os discos ──────────────────────
    def _pc_aberto(self):
        return self.janela.cfg.get("pcExpandido", True)

    def _mostrar_discos(self):
        aberto = self._pc_aberto()
        for r in self.linhas_discos:
            r.set_visible(aberto)
        s = self.linha_pc._seta
        if aberto:
            s.add_css_class("aberto")
        else:
            s.remove_css_class("aberto")
        s.set_tooltip_text(_t("Recolher") if aberto else _t("Mostrar os discos"))

    def alternar_pc(self, aberto=None):
        aberto = (not self._pc_aberto()) if aberto is None else aberto
        if aberto == self._pc_aberto():
            return
        sel = self.lista.get_selected_row()
        self.janela.cfg["pcExpandido"] = aberto
        self.janela.salvar_config()
        self._mostrar_discos()
        # disco selecionado sumiu: a seleção sobe para o Este Computador (como no Windows)
        if not aberto and sel in self.linhas_discos:
            self.lista.select_row(self.linha_pc)

    def _tecla(self, ctl, tecla, cod, mods):
        # → expande e ← recolhe, com o foco no Este Computador
        row = self.lista.get_focus_child() or self.lista.get_selected_row()
        if row is not getattr(self, "linha_pc", None):
            return False
        if tecla == Gdk.KEY_Right:
            self.alternar_pc(True)
            return True
        if tecla == Gdk.KEY_Left:
            self.alternar_pc(False)
            return True
        return False

    def _cabecalho(self, row, antes):
        if antes is not None and antes._secao != row._secao:
            row.set_header(Gtk.Separator(margin_top=6, margin_bottom=6, margin_start=12, margin_end=12))
        else:
            row.set_header(None)

    def _ativada(self, lista, row):
        d = row._destino
        if isinstance(d, str):
            self.janela.ir_especial(d)
        else:
            self.janela.ir(d)

    def marcar(self, local):
        """Destaca a linha do lugar atual (pasta exata ou página especial)."""
        alvo = None
        for row in self.linhas:
            d = row._destino
            if isinstance(local, str) and d == local:
                alvo = row
            elif not isinstance(local, str) and not isinstance(d, str) and local is not None and d.equal(local):
                alvo = row
        if alvo is not None and not alvo.get_visible():
            alvo = self.linha_pc   # disco dentro do Este Computador recolhido
        if alvo:
            self.lista.select_row(alvo)
        else:
            self.lista.unselect_all()

    def _row_em(self, y):
        return self.lista.get_row_at_y(int(y))

    def _menu(self, n, x, y):
        row = self._row_em(y)
        if row is None:
            return
        self.janela.menu_lateral(self.lista, row, x, y)

    def _meio(self, n, x, y):
        row = self._row_em(y)
        if row is not None and not isinstance(row._destino, str):
            self.janela.nova_aba(row._destino)


# ── painel de detalhes / visualização ───────────────────────────────────────
class Detalhes(Gtk.Box):
    def __init__(self, janela):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, css_classes=["painel-detalhes"], width_request=300)
        self.janela = janela
        self.modo = "detalhes"
        self.corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_start=16, margin_end=16,
                             margin_top=16, margin_bottom=16)
        self.append(rolagem(self.corpo))

    def limpar(self):
        while (c := self.corpo.get_first_child()) is not None:
            self.corpo.remove(c)

    def mostrar(self, infos, pasta_info=None):
        self.limpar()
        if not infos:
            if pasta_info is not None:
                infos = [pasta_info]
            else:
                self.corpo.append(Gtk.Label(label=_t("Selecione um arquivo para ver os detalhes."), wrap=True,
                                            css_classes=["vazio"], margin_top=40))
                return
        if len(infos) > 1:
            self.corpo.append(Gtk.Image(icon_name="edit-select-all", pixel_size=96, margin_top=20))
            total = sum(i.get_size() for i in infos if not u.eh_pasta(i))
            self.corpo.append(Gtk.Label(label=_t("%1 itens selecionados", len(infos)), css_classes=["title-3"]))
            self.corpo.append(Gtk.Label(label=_t("Tamanho total: %1", u.tamanho(total)), css_classes=["secundario"]))
            return
        info = infos[0]
        gfile = u.arquivo_de(info)
        ct = u.tipo(info) or ""
        topo = Gtk.Box(halign=Gtk.Align.CENTER, height_request=200, margin_bottom=6)
        img = Gtk.Image(gicon=info.get_icon(), pixel_size=128)
        pic = Gtk.Picture(content_fit=Gtk.ContentFit.CONTAIN, width_request=260, height_request=200, visible=False)
        topo.append(img)
        topo.append(pic)
        self.corpo.append(topo)
        if u.miniaturavel(ct):
            def pronto(p):
                pic.set_filename(p)
                pic.set_visible(True)
                img.set_visible(False)
                return False
            u.pedir_miniatura(info, True, pronto)
        self.corpo.append(Gtk.Label(label=info.get_display_name(), wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                                    css_classes=["title-4"], justify=Gtk.Justification.CENTER))
        self.corpo.append(Gtk.Label(label=u.tipo_desc(info), css_classes=["secundario"]))
        # texto: começo do arquivo (visualização)
        if self.modo == "visualizar" and (ct.startswith("text/") or ct in ("application/json", "application/x-shellscript",
                                                                             "application/xml", "application/javascript")):
            try:
                with open(gfile.get_path(), "rb") as f:
                    txt = f.read(24000).decode("utf-8", "replace")
                tv = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=8,
                                  left_margin=8, right_margin=8, bottom_margin=8, css_classes=["card"])
                tv.get_buffer().set_text(txt)
                self.corpo.append(tv)
            except (OSError, TypeError):
                pass
        grade = Gtk.Grid(column_spacing=12, row_spacing=6, margin_top=12)
        linhas = []
        if u.eh_pasta(info):
            linhas.append((_n("Itens"), "…"))
        else:
            linhas.append((_n("Tamanho"), u.tamanho(info.get_size())))
        linhas += [(_n("Modificado"), u.data(info.get_modification_date_time())),
                   (_n("Criado"), u.data(info.get_creation_date_time()) if info.get_creation_date_time() else "—"),
                   (_n("Acessado"), u.data(info.get_access_date_time()) if info.get_access_date_time() else "—")]
        pai = gfile.get_parent() if gfile else None
        linhas.append((_n("Local"), (pai.get_path() or pai.get_uri()) if pai else ""))
        rotulos = {}
        for n, (k, v) in enumerate(linhas):
            grade.attach(Gtk.Label(label=_t(k), xalign=0, css_classes=["secundario"], valign=Gtk.Align.START), 0, n, 1, 1)
            lv = Gtk.Label(label=v, xalign=0, wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR, selectable=True, hexpand=True)
            grade.attach(lv, 1, n, 1, 1)
            rotulos[k] = lv
        self.corpo.append(grade)
        if u.eh_pasta(info) and gfile and gfile.get_path():
            def contar():
                try:
                    n = len(os.listdir(gfile.get_path()))
                except OSError:
                    n = None
                GLib.idle_add(lambda: (rotulos["Itens"].set_label("—" if n is None else f"{n}"), False)[1])
            threading.Thread(target=contar, daemon=True).start()
