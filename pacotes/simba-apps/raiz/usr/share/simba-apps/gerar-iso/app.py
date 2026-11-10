#!/usr/bin/env python3
"""Gerar ISO — clona este sistema numa ISO instalável e grava em pendrive.

Interface para /usr/share/simba-apps/gerar-iso/gerar-iso-build (que faz o trabalho, com root,
via gerar-iso-root + pkexec). Mostra as etapas, a porcentagem, o tempo e o registro;
depois grava a ISO (ou qualquer outra imagem .iso/.img) num pendrive, com verificação.
"""
import json
import os
import re
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
from gi.repository import Adw, Gio, GLib, Gtk, Pango  # noqa: E402

APP_ID = "com.simba.GerarIso"
BASE = Path(__file__).resolve().parent
ROOT = BASE / "gerar-iso-root"
RUN = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "gerar-iso"
LOG_ARQ = Path.home() / ".cache/gerar-iso/ultimo.log"


def novo_log(titulo):
    try:
        LOG_ARQ.parent.mkdir(parents=True, exist_ok=True)
        LOG_ARQ.write_text(f"== {titulo} — {GLib.DateTime.new_now_local().format('%F %T')}\n", encoding="utf-8")
    except OSError:
        pass

# etapas do gerar-iso-build: (id, título, peso no total)
ETAPAS = [
    ("deps", _t("Verificar dependências"), 2),
    ("snapshots", _t("Tirar snapshots do sistema"), 1),
    ("sistema", _t("Compactar o sistema"), 42),
    ("pessoal", _t("Compactar as pastas pessoais"), 14),
    ("boot", _t("Copiar a partição de boot"), 1),
    ("marca", _t("Preparar a identidade visual"), 1),
    ("live", _t("Montar o sistema de instalação"), 30),
    ("embutir", _t("Embutir o clone na ISO"), 10),
]
PESO_TOTAL = sum(p for _, _, p in ETAPAS)


def destino():
    return Path("/mnt/dados/gerar-iso") if os.path.ismount("/mnt/dados") else Path("/var/tmp/gerar-iso")


def tamanho(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return (f"{n:.1f} {u}" if u not in ("B",) else f"{n} {u}").replace(".", _DEC)
        n /= 1024


def duracao(s):
    s = int(s)
    if s < 60:
        return f"{s} s"
    if s < 3600:
        return _t("%1 min %2 s", s // 60, format(s % 60, "02d"))
    return _t("%1 h %2 min", s // 3600, format((s % 3600) // 60, "02d"))


def pendrives():
    """Discos USB/removíveis (nunca o do sistema)."""
    if os.environ.get("GERAR_ISO_FALSO"):
        return [{"path": "/dev/sdz", "nome": _t("SanDisk Ultra (teste)"), "tamanho": 32 * 1024 ** 3, "rotulos": ["PENDRIVE"],
                 "montado": False}]
    try:
        d = json.loads(subprocess.run(["lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,MODEL,VENDOR,TRAN,RM,TYPE,LABEL,MOUNTPOINTS"],
                                      capture_output=True, text=True, timeout=5).stdout)
    except Exception:  # noqa: BLE001
        return []
    out = []
    for b in d.get("blockdevices", []):
        if b.get("type") != "disk" or not (b.get("tran") == "usb" or b.get("rm") in (True, "1", 1)):
            continue
        if not b.get("size"):
            continue
        rotulos = [c.get("label") for c in b.get("children", []) if c.get("label")]
        montado = any(m for c in [b] + b.get("children", []) for m in (c.get("mountpoints") or []) if m)
        nome = " ".join(x for x in ((b.get("vendor") or "").strip(), (b.get("model") or "").strip()) if x) or b["path"]
        out.append({"path": b["path"], "nome": nome, "tamanho": int(b["size"]), "rotulos": rotulos, "montado": montado})
    return out


# ── processo com root (pkexec), lido linha a linha ──────────────────────────
class Processo:
    def __init__(self, argv, ao_ler, ao_fim):
        RUN.mkdir(parents=True, exist_ok=True)
        self.cancelar_arq = RUN / _t("cancelar-%1-%2", os.getpid(), int(time.time()))
        self.cancelar_arq.unlink(missing_ok=True)
        argv = [a if a != "{CANCELAR}" else str(self.cancelar_arq) for a in argv]
        # sem dormir/suspender enquanto trabalha
        falso = os.environ.get("GERAR_ISO_FALSO")   # testes da interface: script que imita o root
        prefixo = [falso] if falso else ["systemd-inhibit", "--what=sleep:idle:handle-lid-switch", "--who=Gerar ISO",
                                         "--why=Gerando a ISO / gravando o pendrive", "pkexec"]
        if falso:
            argv = argv[1:]
        self.p = Gio.Subprocess.new([*prefixo, *argv],
                                    Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE)
        self.ao_ler, self.ao_fim = ao_ler, ao_fim
        self.resto = ""
        self.stream = self.p.get_stdout_pipe()
        self._ler()
        self.p.wait_async(None, self._terminou)

    def _ler(self):
        self.stream.read_bytes_async(65536, GLib.PRIORITY_DEFAULT, None, self._lido)

    def _lido(self, s, res):
        try:
            b = s.read_bytes_finish(res).get_data()
        except GLib.Error:
            return
        if not b:
            if self.resto:
                self.ao_ler(self.resto, True)
            return
        texto = self.resto + b.decode("utf-8", "replace")
        partes = re.split(r"(\r|\n)", texto)
        self.resto = partes.pop() if partes else ""
        linha = ""
        for p in partes:
            if p in ("\r", "\n"):
                self.ao_ler(linha, p == "\n")
                linha = ""
            else:
                linha += p
        self.resto = linha + self.resto
        self._ler()

    def _terminou(self, p, res):
        try:
            p.wait_finish(res)
        except GLib.Error:
            pass
        rc = p.get_exit_status() if p.get_if_exited() else 1
        GLib.timeout_add(150, lambda: (self.ao_fim(rc), False)[1])

    def cancelar(self):
        self.cancelar_arq.touch()


# ── janela ──────────────────────────────────────────────────────────────────
class Janela(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_t("Gerar ISO"), default_width=820, default_height=720)
        self.nav = Adw.NavigationView()
        self.toast = Adw.ToastOverlay(child=self.nav)
        self.set_content(self.toast)
        self.proc = None
        self.iso_pronta = None
        self.nav.add(self._pagina_inicio())
        self.connect("close-request", self._fechar)

    def aviso(self, t, s=3):
        self.toast.add_toast(Adw.Toast(title=t, timeout=s))

    def _pagina(self, titulo, conteudo, tag):
        tv = Adw.ToolbarView()
        tv.add_top_bar(Adw.HeaderBar())
        tv.set_content(conteudo)
        return Adw.NavigationPage(title=titulo, child=tv, tag=tag)

    # ── início ─────────────────────────────────────────────────────────────
    def _pagina_inicio(self):
        pag = Adw.PreferencesPage()
        topo = Adw.PreferencesGroup()
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, margin_top=8, margin_bottom=8)
        caixa.append(Gtk.Image(icon_name="media-optical", pixel_size=88))
        caixa.append(Gtk.Label(label=_t("Clonar este sistema numa ISO"), css_classes=["title-1"]))
        caixa.append(Gtk.Label(label=_t("Uma ISO instalável com tudo como está agora: programas, tradução, atalhos, "
                                     "temas e configurações. Depois é só gravar num pendrive e instalar em outra máquina."),
                               wrap=True, justify=Gtk.Justification.CENTER, css_classes=["dim-label"], max_width_chars=60))
        bt = Gtk.Button(label=_t("Gerar ISO"), css_classes=["suggested-action", "pill"], halign=Gtk.Align.CENTER, margin_top=12)
        bt.connect("clicked", lambda b: self._confirmar_gerar())
        caixa.append(bt)
        topo.add(caixa)
        pag.add(topo)

        # ── tipo de ISO ──
        self.modo, self.logins = "sistema", False
        gt = Adw.PreferencesGroup(title=_t("Tipo de ISO"))
        self.radios = {}
        primeiro = None
        for modo, titulo, sub in (
                ("sistema", _t("Sistema e configurações"),
                 _t("Seu usuário e sua senha, sem arquivos pessoais — para reinstalar nos seus computadores")),
                ("pessoal", _t("Com arquivos pessoais (backup completo)"),
                 _t("Leva também Documentos, Downloads, Imagens, Área de trabalho… · calculando o tamanho…")),
                ("distribuivel", _t("Distribuível — para outras pessoas"),
                 _t("Nada pessoal, sem logins e sem a sua senha: quem instalar cria a própria conta"))):
            r = Adw.ActionRow(title=titulo, subtitle=sub, activatable=True)
            rb = Gtk.CheckButton(valign=Gtk.Align.CENTER, active=modo == "sistema")
            if primeiro:
                rb.set_group(primeiro)
            primeiro = primeiro or rb
            rb.connect("toggled", lambda b, m=modo: self._mudar_modo(m) if b.get_active() else None)
            r.add_prefix(rb)
            r.set_activatable_widget(rb)
            gt.add(r)
            self.radios[modo] = r
        self.sw_logins = Adw.SwitchRow(title=_t("Incluir senhas e logins"),
                                       subtitle=_t("Navegadores já logados, chaves SSH, Wi-Fi, chaveiro, conta do Google Drive, "
                                                "chaves de API — guarde o pendrive em lugar seguro"), visible=False)
        self.sw_logins.connect("notify::active", lambda *a: self._mudar_modo(self.modo))
        gt.add(self.sw_logins)
        self.nome_sistema = Adw.EntryRow(title=_t("Nome do sistema (aparece no instalador e no nome da ISO)"), text=_t("Simba OS"),
                                         visible=False)
        gt.add(self.nome_sistema)
        pag.add(gt)
        self._medir_pessoal()

        self.grupo_vai = Adw.PreferencesGroup(title=_t("O que vai na ISO"))
        self.grupo_fora = Adw.PreferencesGroup(title=_t("Fica de fora"))
        self._linhas_desc = []
        pag.add(self.grupo_vai)
        pag.add(self.grupo_fora)
        self._descrever()

        g3 = Adw.PreferencesGroup(title=_t("Onde fica"))
        dest = destino()
        livre = 0
        try:
            st = os.statvfs(dest if dest.exists() else dest.parent)
            livre = st.f_bavail * st.f_frsize
        except OSError:
            pass
        usado = 0
        try:
            s = os.statvfs("/")
            usado = (s.f_blocks - s.f_bfree) * s.f_frsize
        except OSError:
            pass
        precisa = usado + 10 * 1024 ** 3
        r = Adw.ActionRow(title=str(dest), subtitle=_t("%1 livres · precisa de ~%2 durante a geração · a ISO tem ~9–11 GB · leva de 20 a 60 minutos", tamanho(livre), tamanho(precisa)))
        r.add_prefix(Gtk.Image(icon_name="folder-symbolic"))
        if livre and livre < precisa:
            r.add_suffix(Gtk.Label(label=_t("Espaço insuficiente"), css_classes=["error"]))
        g3.add(r)
        pag.add(g3)

        self.grupo_isos = Adw.PreferencesGroup(title=_t("Gravar num pendrive"),
                                               description=_t("ISOs já geradas — ou qualquer outra imagem .iso/.img, como o Rufus."))
        outra = Gtk.Button(label=_t("Escolher imagem…"), css_classes=["flat"], valign=Gtk.Align.CENTER)
        outra.connect("clicked", lambda b: self._escolher_imagem())
        self.grupo_isos.set_header_suffix(outra)
        pag.add(self.grupo_isos)
        self._listar_isos()
        return self._pagina(_t("Gerar ISO"), pag, "inicio")

    PASTAS_PESSOAIS = (_t("Documents"), _t("Downloads"), _t("Music"), _t("Pictures"), _t("Videos"), _t("Projects"), _t("Work"), _t("Desktop"),
                       _t("Área de trabalho"), _t("Wallpapers"))

    def _medir_pessoal(self):
        import threading

        def medir():
            total = 0
            for n in self.PASTAS_PESSOAIS:
                for raiz, _, arqs in os.walk(Path.home() / n):
                    for a in arqs:
                        try:
                            total += os.lstat(os.path.join(raiz, a)).st_size
                        except OSError:
                            pass
            GLib.idle_add(lambda: (self.radios["pessoal"].set_subtitle(
                _t("Leva também Documentos, Downloads, Imagens, Área de trabalho… (+%1)", tamanho(total))), False)[1])
        threading.Thread(target=medir, daemon=True).start()

    def _mudar_modo(self, modo):
        self.modo = modo
        self.sw_logins.set_visible(modo == "pessoal")
        self.nome_sistema.set_visible(modo == "distribuivel")
        self.logins = modo == "pessoal" and self.sw_logins.get_active()
        self._descrever()

    def _descrever(self):
        for g, r in self._linhas_desc:
            g.remove(r)
        self._linhas_desc = []
        vai = [(_t("Sistema e programas"), _t("Todos os pacotes instalados e o sistema traduzido")),
               (_t("Configurações"), _t("Hyprland, barra, menu Iniciar, Configurações, Explorador, temas, scripts e apps próprios")),
               (_t("Instalador automático"), _t("Ao dar boot pelo pendrive, o instalador abre sozinho (disco criptografado, TPM)"))]
        fora = []
        if self.modo == "sistema":
            vai.insert(2, (_t("Seu usuário"), _t("Mesmo nome de usuário e mesma senha de login")))
            fora = [(_t("Arquivos pessoais"), _t("Documentos, Downloads, Imagens, Músicas, Vídeos, Área de trabalho, papéis de parede")),
                    (_t("Senhas e logins"), _t("Navegadores, chaves SSH, Wi-Fi, chaveiro, Google Drive, chaves de API"))]
        elif self.modo == "pessoal":
            vai.insert(2, (_t("Seu usuário"), _t("Mesmo nome de usuário e mesma senha de login")))
            vai.insert(3, (_t("Arquivos pessoais"), _t("Documentos, Downloads, Imagens, Músicas, Vídeos, Área de trabalho, "
                                                "papéis de parede e históricos")))
            if self.logins:
                vai.insert(4, (_t("Senhas e logins"), _t("Navegadores logados, chaves SSH, Wi-Fi, chaveiro, Google Drive, chaves de API")))
            else:
                fora = [(_t("Senhas e logins"), _t("Navegadores, chaves SSH, Wi-Fi, chaveiro, Google Drive, chaves de API"))]
        else:
            vai.insert(2, (_t("Conta de quem instalar"), _t("O instalador pede nome, usuário e senha — a ISO não traz a sua senha")))
            fora = [(_t("Tudo o que identifica você"), _t("Arquivos pessoais, históricos, senhas e logins, sua senha, nome do "
                                                  "computador, Git, favoritos, foto da conta, outros usuários deste PC"))]
        fora.append((_t("Histórico do Claude Code"), _t("Nunca vai, em nenhum tipo de ISO")))
        fora.append((_t("Identidade desta máquina"), _t("ID do AnyDesk, chaves do SSH do sistema, TPM, machine-id")))
        for g, itens, ic in ((self.grupo_vai, vai, "emblem-ok-symbolic"), (self.grupo_fora, fora, "action-unavailable-symbolic")):
            for t, sub in itens:
                r = Adw.ActionRow(title=t, subtitle=sub)
                r.add_prefix(Gtk.Image(icon_name=ic))
                g.add(r)
                self._linhas_desc.append((g, r))

    def _listar_isos(self):
        if hasattr(self, "_linhas_iso"):
            for r in self._linhas_iso:
                self.grupo_isos.remove(r)
        self._linhas_iso = []
        dest = destino()
        isos = sorted(dest.glob("*.iso"), key=lambda p: p.stat().st_mtime, reverse=True) if dest.is_dir() else []
        if not isos:
            r = Adw.ActionRow(title=_t("Nenhuma ISO gerada ainda"))
            self.grupo_isos.add(r)
            self._linhas_iso.append(r)
        for iso in isos[:6]:
            st = iso.stat()
            r = Adw.ActionRow(title=iso.name, subtitle=f"{tamanho(st.st_size)} · {time.strftime('%d/%m/%Y %H:%M', time.localtime(st.st_mtime))}")
            r.add_prefix(Gtk.Image(icon_name="media-optical-symbolic"))
            b = Gtk.Button(label=_t("Gravar no pendrive"), valign=Gtk.Align.CENTER)
            b.connect("clicked", lambda b, i=iso: self.ir_pendrive(i))
            r.add_suffix(b)
            m = Gtk.MenuButton(icon_name="view-more-symbolic", css_classes=["flat"], valign=Gtk.Align.CENTER)
            menu = Gio.Menu()
            menu.append(_t("Abrir a pasta"), f"app.abrir-pasta::{iso}")
            menu.append(_t("Excluir esta ISO"), f"app.excluir-iso::{iso}")
            m.set_menu_model(menu)
            r.add_suffix(m)
            self.grupo_isos.add(r)
            self._linhas_iso.append(r)

    def _escolher_imagem(self):
        d = Gtk.FileDialog(title=_t("Escolher imagem de disco"))
        f = Gtk.FileFilter()
        f.set_name(_t("Imagens de disco (.iso, .img)"))
        for pad in ("*.iso", "*.img", "*.ISO", "*.IMG"):
            f.add_pattern(pad)
        lista = Gio.ListStore(item_type=Gtk.FileFilter)
        lista.append(f)
        d.set_filters(lista)
        d.set_default_filter(f)

        def pronto(d, res):
            try:
                arq = d.open_finish(res)
            except GLib.Error:
                return
            if arq and arq.get_path():
                self.ir_pendrive(Path(arq.get_path()))
        d.open(self, None, pronto)

    # ── gerar ──────────────────────────────────────────────────────────────
    def _confirmar_gerar(self):
        tipo = {"sistema": _t("Sistema e configurações"), "pessoal": _t("Com arquivos pessoais") + (_t(" e senhas") if self.logins else ""),
                "distribuivel": _t("Distribuível — “%1”", self.nome_sistema.get_text().strip() or 'Simba OS')}[self.modo]
        extra = ("\n\n" + _t("Atenção: a ISO vai ter as suas senhas e logins. Não compartilhe e guarde o pendrive em lugar seguro.")
                 if self.logins else "")
        extra += self._checar_idiomas()
        d = Adw.AlertDialog(heading=_t("Gerar a ISO agora?"),
                            body=_t("Tipo: %1.\n\nLeva de 20 a 60 minutos e usa bastante o processador. Dá para continuar usando o computador. Vai pedir a senha de administrador.%2", tipo, extra))
        d.add_response("cancelar", _t("Cancelar"))
        d.add_response("gerar", _t("Gerar ISO"))
        d.set_response_appearance("gerar", Adw.ResponseAppearance.SUGGESTED)
        d.set_close_response("cancelar")
        d.connect("response", lambda d, r: self._gerar() if r == "gerar" else None)
        d.present(self)

    def _checar_idiomas(self):
        """Frases dos apps próprios ainda sem tradução, por idioma (ferramentas de /usr/share/simba-apps/idiomas)."""
        pasta = Path("/usr/share/simba-apps/idiomas")
        faltas = []
        for cat in sorted(pasta.glob("*.json")):
            try:
                r = subprocess.run([str(pasta / "ferramentas/extrair.py"), "--faltando", cat.stem],
                                   capture_output=True, text=True, timeout=30)
                n = len([l for l in r.stdout.splitlines() if l.strip()])
            except Exception:
                continue
            if n:
                faltas.append(f"{cat.stem}: {n}")
        if not faltas:
            return ""
        return "\n\n" + _t("Idiomas: há frases sem tradução (%1). Nesses idiomas elas aparecem em português. Para ver quais: /usr/share/simba-apps/idiomas/ferramentas/extrair.py --faltando <idioma>", ", ".join(faltas))

    def _gerar(self):
        self.inicio_t = time.monotonic()
        self.etapa_atual = None
        self.frac_etapa = 0.0
        self.iso_pronta = None
        self.ultimo_erro = ""
        self.nav.push(self._pagina_progresso())
        novo_log("construir " + self.modo)
        self.proc = Processo([str(ROOT), "construir", "{CANCELAR}", self.modo, "1" if self.logins else "0",
                              self.nome_sistema.get_text().strip() or _t("Simba OS")], self._linha_gerar, self._fim_gerar)
        self._relogio = GLib.timeout_add_seconds(1, self._tique)

    def _pagina_progresso(self):
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin_start=28, margin_end=28,
                        margin_top=20, margin_bottom=20)
        self.titulo_prog = Gtk.Label(label=_t("Preparando…"), css_classes=["title-2"], xalign=0)
        caixa.append(self.titulo_prog)
        self.barra = Gtk.ProgressBar(show_text=True, text="0%", css_classes=["barra-grande"])
        caixa.append(self.barra)
        linha = Gtk.Box(spacing=12)
        self.rot_tempo = Gtk.Label(xalign=0, hexpand=True, css_classes=["dim-label"], label=_t("Aguardando a senha de administrador…"))
        self.rot_resta = Gtk.Label(xalign=1, css_classes=["dim-label"])
        linha.append(self.rot_tempo)
        linha.append(self.rot_resta)
        caixa.append(linha)
        lista = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        self.linhas_etapa = {}
        for eid, titulo, _ in ETAPAS:
            r = Adw.ActionRow(title=titulo)
            ic = Gtk.Image(icon_name="content-loading-symbolic", css_classes=["dim-label"])
            sp = Adw.Spinner(visible=False)
            pct = Gtk.Label(css_classes=["dim-label", "numeric"])
            r.add_prefix(ic)
            r.add_prefix(sp)
            r.add_suffix(pct)
            lista.append(r)
            self.linhas_etapa[eid] = (r, ic, sp, pct)
        caixa.append(lista)
        exp = Gtk.Expander(label=_t("Detalhes"))
        self.log = Gtk.TextView(editable=False, monospace=True, wrap_mode=Gtk.WrapMode.WORD_CHAR, top_margin=8,
                                bottom_margin=8, left_margin=8, right_margin=8, css_classes=["card"])
        rol = Gtk.ScrolledWindow(min_content_height=180, max_content_height=260, child=self.log)
        self.log_rol = rol
        exp.set_child(rol)
        caixa.append(exp)
        self.bt_cancelar = Gtk.Button(label=_t("Cancelar"), css_classes=["destructive-action", "pill"], halign=Gtk.Align.CENTER)
        self.bt_cancelar.connect("clicked", lambda b: self._confirmar_cancelar())
        caixa.append(self.bt_cancelar)
        rolagem = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, child=caixa)
        pag = self._pagina(_t("Gerando a ISO"), rolagem, "progresso")
        pag.set_can_pop(False)
        return pag

    def _log(self, texto):
        # cópia em arquivo: se der errado dá para ver depois (~/.cache/gerar-iso/ultimo.log)
        try:
            with open(LOG_ARQ, "a", encoding="utf-8") as f:
                f.write(texto.rstrip("\n") + "\n")
        except OSError:
            pass
        buf = self.log.get_buffer()
        buf.insert(buf.get_end_iter(), texto + "\n")
        if buf.get_line_count() > 3000:
            ini = buf.get_start_iter()
            fim = buf.get_iter_at_line(buf.get_line_count() - 2500)[1]
            buf.delete(ini, fim)
        adj = self.log_rol.get_vadjustment()
        GLib.idle_add(lambda: (adj.set_value(adj.get_upper()), False)[1])

    def _linha_gerar(self, linha, completa):
        limpa = re.sub(r"\x1b\[[0-9;]*m", "", linha).strip()
        if not limpa:
            return
        if limpa.startswith("@@ETAPA "):
            _, eid, *resto = limpa.split(" ", 2)
            self._entrar_etapa(eid)
            return
        if limpa.startswith("@@ISO "):
            self.iso_pronta = Path(limpa[6:].strip())
            return
        if limpa.startswith("@@FIM") or limpa.startswith("@@CANCELANDO"):
            if limpa.startswith("@@CANCELANDO"):
                self.titulo_prog.set_label(_t("Cancelando e limpando…"))
            return
        if self.etapa_atual is None:
            self.rot_tempo.set_label(_t("Iniciando…"))
        e = self.etapa_atual
        pct = None
        m = re.search(r"(\d{1,3})%\s*$", limpa)
        if e in ("sistema", "pessoal") and m:
            pct = int(m.group(1)) / 100
        elif e == "live":
            m2 = re.search(r"\(\s*(\d+)/(\d+)\)\s+(installing|instalando)", limpa)
            if "Installing packages" in limpa or "Instalando pacotes" in limpa:
                pct = 0.05
            elif m2:
                pct = 0.08 + 0.5 * int(m2.group(1)) / max(1, int(m2.group(2)))
            elif "Creating SquashFS" in limpa or "Creating an erofs" in limpa:
                pct = 0.62
            elif m and self.frac_etapa >= 0.62:
                pct = 0.62 + 0.3 * int(m.group(1)) / 100
            elif "Creating ISO image" in limpa:
                pct = 0.94
        elif e == "embutir":
            m3 = re.search(r"([\d.]+)%\s+done", limpa)
            if m3:
                pct = float(m3.group(1)) / 100
        if pct is not None:
            self.frac_etapa = max(self.frac_etapa, min(1.0, pct))
            self._atualizar_barra()
        # o log só recebe linhas completas (as de progresso com \r ficam de fora)
        if completa and not re.search(r"^\[[=\\|/\- ]*\]", limpa):
            self._log(limpa)
            if "ERRO" in limpa or "error" in limpa.lower():
                self.ultimo_erro = limpa

    def _entrar_etapa(self, eid):
        ids = [e for e, _, _ in ETAPAS]
        if self.etapa_atual in ids:
            self._marcar(self.etapa_atual, "ok")
        for anterior in ids[:ids.index(eid)] if eid in ids else []:
            self._marcar(anterior, "ok")
        self.etapa_atual = eid
        self.frac_etapa = 0.0
        self._marcar(eid, "rodando")
        self.titulo_prog.set_label(dict((e, t) for e, t, _ in ETAPAS).get(eid, eid) + "…")
        self._atualizar_barra()

    def _marcar(self, eid, estado):
        if eid not in self.linhas_etapa:
            return
        r, ic, sp, pct = self.linhas_etapa[eid]
        sp.set_visible(estado == "rodando")
        ic.set_visible(estado != "rodando")
        if estado == "ok":
            ic.set_from_icon_name("emblem-ok-symbolic")
            ic.remove_css_class("dim-label")
            ic.add_css_class("success")
            pct.set_label("")
        elif estado == "erro":
            ic.set_from_icon_name("dialog-error-symbolic")
            ic.add_css_class("error")

    def _fracao_total(self):
        feito = 0
        for eid, _, peso in ETAPAS:
            if eid == self.etapa_atual:
                feito += peso * self.frac_etapa
                break
            feito += peso
        else:
            feito = 0 if self.etapa_atual is None else PESO_TOTAL
        return min(1.0, feito / PESO_TOTAL)

    def _atualizar_barra(self):
        f = self._fracao_total()
        self.barra.set_fraction(f)
        self.barra.set_text(f"{int(f * 100)}%")
        if self.etapa_atual in self.linhas_etapa and self.frac_etapa > 0:
            self.linhas_etapa[self.etapa_atual][3].set_label(f"{int(self.frac_etapa * 100)}%")

    def _tique(self):
        if not self.proc:
            return False
        dec = time.monotonic() - self.inicio_t
        if self.etapa_atual is not None:
            self.rot_tempo.set_label(_t("Tempo decorrido: %1", duracao(dec)))
            f = self._fracao_total()
            if f > 0.04:
                self.rot_resta.set_label(_t("Falta cerca de %1", duracao(dec / f - dec)))
        return True

    def _confirmar_cancelar(self):
        d = Adw.AlertDialog(heading=_t("Cancelar a geração?"), body=_t("O que já foi feito é descartado."))
        d.add_response("nao", _t("Continuar gerando"))
        d.add_response("sim", _t("Cancelar"))
        d.set_response_appearance("sim", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_close_response("nao")

        def resp(d, r):
            if r == "sim" and self.proc:
                self.proc.cancelar()
                self.bt_cancelar.set_sensitive(False)
                self.titulo_prog.set_label(_t("Cancelando e limpando…"))
        d.connect("response", resp)
        d.present(self)

    def _fim_gerar(self, rc):
        cancelado = self.proc and self.proc.cancelar_arq.exists()
        if self.proc:
            self.proc.cancelar_arq.unlink(missing_ok=True)
        self.proc = None
        if rc == 0 and self.iso_pronta:
            for eid, _, _ in ETAPAS:
                self._marcar(eid, "ok")
            self.barra.set_fraction(1)
            self.barra.set_text("100%")
            dec = time.monotonic() - self.inicio_t
            self.nav.replace([self.nav.find_page("inicio"), self._pagina_pronta(self.iso_pronta, dec)])
            self._notificar(_t("ISO pronta"), self.iso_pronta.name)
            self._listar_isos()
            return
        if rc in (126, 127) and self.etapa_atual is None:
            self.nav.pop_to_tag("inicio")
            self.aviso(_t("Senha cancelada — a ISO não foi gerada"))
            return
        if cancelado or rc == 130:
            self.nav.pop_to_tag("inicio")
            self.aviso(_t("Geração cancelada"))
            return
        if self.etapa_atual:
            self._marcar(self.etapa_atual, "erro")
        self.titulo_prog.set_label(_t("Não foi possível gerar a ISO"))
        self.rot_tempo.set_label(self.ultimo_erro or _t("O gerador saiu com o código %1. Veja os detalhes.", rc))
        self.bt_cancelar.set_label(_t("Voltar"))
        self.bt_cancelar.set_sensitive(True)
        novo = Gtk.Button(label=_t("Voltar"), css_classes=["pill"], halign=Gtk.Align.CENTER)
        novo.connect("clicked", lambda b: self.nav.pop_to_tag("inicio"))
        pai = self.bt_cancelar.get_parent()
        pai.remove(self.bt_cancelar)
        pai.append(novo)
        self._notificar(_t("A ISO não foi gerada"), _t("Abra o Gerar ISO para ver o motivo"), erro=True)

    def _pagina_pronta(self, iso, dec):
        st = Adw.StatusPage(icon_name="emblem-ok-symbolic", title=_t("ISO pronta"), css_classes=["ok"],
                            description=_t("%1\n%2 · gerada em %3", iso.name, tamanho(iso.stat().st_size), duracao(dec)))
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, halign=Gtk.Align.CENTER)
        b1 = Gtk.Button(label=_t("Gravar no pendrive"), css_classes=["suggested-action", "pill"])
        b1.connect("clicked", lambda b: self.ir_pendrive(iso))
        b2 = Gtk.Button(label=_t("Abrir a pasta"), css_classes=["pill"])
        b2.connect("clicked", lambda b: Gio.AppInfo.launch_default_for_uri(iso.parent.as_uri(), None))
        b3 = Gtk.Button(label=_t("Concluir"), css_classes=["flat"])
        b3.connect("clicked", lambda b: self.nav.pop_to_tag("inicio"))
        for b in (b1, b2, b3):
            caixa.append(b)
        st.set_child(caixa)
        return self._pagina(_t("Pronto"), st, "pronta")

    # ── pendrive ───────────────────────────────────────────────────────────
    def ir_pendrive(self, iso):
        self.iso_gravar = Path(iso)
        self.nav.push(self._pagina_pendrive())

    def _pagina_pendrive(self):
        pag = Adw.PreferencesPage()
        g = Adw.PreferencesGroup(title=_t("Imagem"))
        try:
            tam = self.iso_gravar.stat().st_size
        except OSError:
            tam = 0
        r = Adw.ActionRow(title=self.iso_gravar.name, subtitle=f"{tamanho(tam)} · {self.iso_gravar.parent}")
        r.add_prefix(Gtk.Image(icon_name="media-optical-symbolic"))
        g.add(r)
        pag.add(g)
        self.grupo_usb = Adw.PreferencesGroup(title=_t("Pendrive"),
                                              description=_t("Conecte o pendrive. Tudo o que estiver nele será apagado."))
        pag.add(self.grupo_usb)
        g3 = Adw.PreferencesGroup()
        self.sw_verificar = Adw.SwitchRow(title=_t("Verificar depois de gravar"),
                                          subtitle=_t("Lê o pendrive de volta e compara com a imagem (leva mais alguns minutos)"),
                                          active=True)
        g3.add(self.sw_verificar)
        pag.add(g3)
        g4 = Adw.PreferencesGroup()
        self.bt_gravar = Gtk.Button(label=_t("Gravar"), css_classes=["destructive-action", "pill"], halign=Gtk.Align.CENTER,
                                    sensitive=False)
        self.bt_gravar.connect("clicked", lambda b: self._confirmar_gravar())
        g4.add(self.bt_gravar)
        pag.add(g4)
        self.usb_escolhido = None
        self._linhas_usb = []
        self._usb_assinatura = None
        self._atualizar_usb()
        self._timer_usb = GLib.timeout_add_seconds(2, self._atualizar_usb)
        nav = self._pagina(_t("Gravar no pendrive"), pag, "pendrive")
        nav.connect("hidden", lambda *a: GLib.source_remove(self._timer_usb) if self._timer_usb else None)
        return nav

    def _atualizar_usb(self):
        lista = pendrives()
        assinatura = json.dumps(lista, sort_keys=True)
        if assinatura == self._usb_assinatura:
            return True
        self._usb_assinatura = assinatura
        for r in self._linhas_usb:
            self.grupo_usb.remove(r)
        self._linhas_usb = []
        try:
            tam_iso = self.iso_gravar.stat().st_size
        except OSError:
            tam_iso = 0
        grupo_radio = None
        caminhos = [d["path"] for d in lista]
        if self.usb_escolhido not in caminhos:
            self.usb_escolhido = None
        if not lista:
            r = Adw.ActionRow(title=_t("Nenhum pendrive conectado"), subtitle=_t("Conecte um pendrive — ele aparece aqui sozinho"))
            r.add_prefix(Adw.Spinner())
            self.grupo_usb.add(r)
            self._linhas_usb.append(r)
        for d in lista:
            pequeno = d["tamanho"] <= tam_iso
            sub = f"{tamanho(d['tamanho'])} · {d['path']}"
            if d["rotulos"]:
                sub += " · " + ", ".join(d["rotulos"])
            if pequeno:
                sub += _t(" · pequeno demais para esta imagem")
            r = Adw.ActionRow(title=d["nome"], subtitle=sub, activatable=not pequeno, sensitive=not pequeno)
            radio = Gtk.CheckButton(valign=Gtk.Align.CENTER)
            if grupo_radio:
                radio.set_group(grupo_radio)
            grupo_radio = grupo_radio or radio
            radio.connect("toggled", lambda b, p=d["path"]: self._escolher_usb(p) if b.get_active() else None)
            r.add_prefix(radio)
            r.set_activatable_widget(radio)
            r.add_suffix(Gtk.Image(icon_name="drive-removable-media-symbolic"))
            if d["path"] == self.usb_escolhido or (self.usb_escolhido is None and not pequeno and len(lista) == 1):
                radio.set_active(True)
            self.grupo_usb.add(r)
            self._linhas_usb.append(r)
        self.bt_gravar.set_sensitive(self.usb_escolhido is not None)
        return True

    def _escolher_usb(self, p):
        self.usb_escolhido = p
        self.bt_gravar.set_sensitive(True)

    def _confirmar_gravar(self):
        d = next((x for x in pendrives() if x["path"] == self.usb_escolhido), None)
        if not d:
            self.aviso(_t("O pendrive foi removido"))
            return
        a = Adw.AlertDialog(heading=_t("Apagar tudo em “%1”?", d['nome']),
                            body=_t("%1 (%2). Todos os arquivos do pendrive serão apagados e substituídos pela imagem. Vai pedir a senha de administrador.", tamanho(d['tamanho']), d['path']))
        a.add_response("cancelar", _t("Cancelar"))
        a.add_response("gravar", _t("Apagar e gravar"))
        a.set_response_appearance("gravar", Adw.ResponseAppearance.DESTRUCTIVE)
        a.set_close_response("cancelar")
        a.connect("response", lambda a, r: self._gravar(d) if r == "gravar" else None)
        a.present(self)

    def _gravar(self, d):
        self.total = max(1, self.iso_gravar.stat().st_size)
        self.inicio_t = time.monotonic()
        self.fase = "senha"
        self.erro_gravar = ""
        self.nav.push(self._pagina_gravando(d))
        novo_log("gravar " + str(self.iso_gravar))
        self.proc = Processo([str(ROOT), "gravar", str(self.iso_gravar), d["path"],
                              "1" if self.sw_verificar.get_active() else "0", "{CANCELAR}"],
                             self._linha_gravar, self._fim_gravar)

    def _pagina_gravando(self, d):
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14, margin_start=28, margin_end=28,
                        margin_top=40, margin_bottom=20, valign=Gtk.Align.START)
        caixa.append(Gtk.Image(icon_name="drive-removable-media", pixel_size=72))
        self.g_titulo = Gtk.Label(label=_t("Aguardando a senha de administrador…"), css_classes=["title-2"])
        caixa.append(self.g_titulo)
        caixa.append(Gtk.Label(label=f"{self.iso_gravar.name} → {d['nome']} ({d['path']})", css_classes=["dim-label"],
                               ellipsize=Pango.EllipsizeMode.MIDDLE))
        self.g_barra = Gtk.ProgressBar(show_text=True, text="0%", margin_top=10, css_classes=["barra-grande"])
        caixa.append(self.g_barra)
        self.g_info = Gtk.Label(css_classes=["dim-label"])
        caixa.append(self.g_info)
        self.g_cancelar = Gtk.Button(label=_t("Cancelar"), css_classes=["destructive-action", "pill"], halign=Gtk.Align.CENTER,
                                     margin_top=10)
        self.g_cancelar.connect("clicked", lambda b: (self.proc and self.proc.cancelar(), b.set_sensitive(False)))
        caixa.append(self.g_cancelar)
        pag = self._pagina(_t("Gravando"), caixa, "gravando")
        pag.set_can_pop(False)
        return pag

    def _linha_gravar(self, linha, completa):
        l = linha.strip()
        if not l:
            return
        if completa:
            try:
                with open(LOG_ARQ, "a", encoding="utf-8") as f:
                    f.write(l + "\n")
            except OSError:
                pass
        if l.startswith("@@FASE "):
            self.fase = l.split(" ", 1)[1]
            self.g_titulo.set_label({"gravando": _t("Gravando…"), "sincronizando": _t("Terminando de gravar…"),
                                     "verificando": _t("Verificando…")}.get(self.fase, self.fase))
            if self.fase != "gravando":
                self.g_barra.set_fraction(1)
                self.g_barra.set_text("100%")
                self.g_info.set_label(_t("Isso pode levar alguns minutos — não remova o pendrive"))
                self.g_cancelar.set_sensitive(False)
                self._pulsar = GLib.timeout_add(120, lambda: (self.g_barra.pulse(), self.fase in ("sincronizando", "verificando"))[1])
            return
        if l.startswith("@@ERRO "):
            self.erro_gravar = l[7:]
            return
        if l.startswith("@@"):
            return
        m = re.match(r"(\d+) bytes", l)
        if m and self.fase == "gravando":
            feito = int(m.group(1))
            f = min(1.0, feito / self.total)
            dec = max(0.1, time.monotonic() - self.inicio_t)
            vel = feito / dec
            resta = (self.total - feito) / vel if vel > 0 else 0
            self.g_barra.set_fraction(f)
            self.g_barra.set_text(f"{int(f * 100)}%")
            self.g_info.set_label(_t("%1 de %2 · %3/s · falta %4", tamanho(feito), tamanho(self.total), tamanho(vel), duracao(resta)))

    def _fim_gravar(self, rc):
        cancelado = self.proc and self.proc.cancelar_arq.exists()
        if self.proc:
            self.proc.cancelar_arq.unlink(missing_ok=True)
        self.proc = None
        self.fase = "fim"
        if rc == 0:
            clone = self.iso_gravar.name.startswith(("simba-clone", "simba-backup", "simba-clone", "simba-backup")) or \
                (self.iso_pronta is not None and self.iso_gravar == self.iso_pronta)
            st = Adw.StatusPage(icon_name="emblem-ok-symbolic", title=_t("Pendrive pronto"), css_classes=["ok"],
                                description=_t("Na outra máquina, ligue pelo pendrive (menu de boot, em modo UEFI). ") +
                                            (_t("O instalador abre sozinho.") if clone else _t("Já pode remover o pendrive.")))
            b = Gtk.Button(label=_t("Concluir"), css_classes=["suggested-action", "pill"], halign=Gtk.Align.CENTER)
            b.connect("clicked", lambda b: self.nav.pop_to_tag("inicio"))
            st.set_child(b)
            self.nav.replace([self.nav.find_page("inicio"), self._pagina(_t("Pronto"), st, "gravado")])
            self._notificar(_t("Pendrive pronto"), self.iso_gravar.name)
            return
        if rc in (126, 127) and self.fase in ("senha", "fim") and not self.erro_gravar:
            self.nav.pop_to_tag("pendrive")
            self.aviso(_t("Senha cancelada — nada foi gravado"))
            return
        if cancelado or rc == 130:
            self.nav.pop_to_tag("pendrive")
            self.aviso(_t("Gravação cancelada — o pendrive ficou incompleto; grave de novo antes de usar"), 5)
            return
        self.g_titulo.set_label(_t("A gravação falhou"))
        self.g_info.set_label(self.erro_gravar or _t("Saiu com o código %1", rc))
        self.g_cancelar.set_label(_t("Voltar"))
        self.g_cancelar.set_sensitive(True)
        self.g_cancelar.connect("clicked", lambda b: self.nav.pop_to_tag("pendrive"))

    # ── outros ─────────────────────────────────────────────────────────────
    def _notificar(self, titulo, corpo, erro=False):
        if self.is_active():
            return
        n = Gio.Notification.new(titulo)
        n.set_body(corpo)
        if erro:
            n.set_priority(Gio.NotificationPriority.HIGH)
        self.get_application().send_notification(None, n)

    def _fechar(self, *a):
        if self.proc is None:
            return False
        d = Adw.AlertDialog(heading=_t("Ainda está trabalhando"),
                            body=_t("Fechar agora cancela a operação. A ISO ou o pendrive ficam incompletos."))
        d.add_response("nao", _t("Continuar"))
        d.add_response("sim", _t("Cancelar e fechar"))
        d.set_response_appearance("sim", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_close_response("nao")

        def resp(d, r):
            if r == "sim" and self.proc:
                self.proc.cancelar()
                p = self.proc
                p.ao_fim = lambda rc: self.destroy()
        d.connect("response", resp)
        d.present(self)
        return True


CSS = """
progressbar.barra-grande trough, progressbar.barra-grande progress { min-height: 10px; border-radius: 5px; }
progressbar.barra-grande text { font-size: 1.05em; font-weight: 600; margin-bottom: 4px; }
statuspage.ok image { color: @success_color; }
"""


_tema_simba = Path.home() / ".local/state/simba/current/theme"
TEMA = _tema_simba if _tema_simba.exists() else (Path.home() / ".local/state/simba/current/theme")


def css_tema():
    """(css, escuro) com a paleta do tema atual — as mesmas regras do Explorador e da Configurações."""
    def rgb(h):
        return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))

    def mix(a, b, k):
        return "#%02x%02x%02x" % tuple(round(x + (y - x) * k) for x, y in zip(rgb(a), rgb(b)))

    def lum(h):
        r, g, b = (x / 255 for x in rgb(h))
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    def cor(v, padrao):
        v = str(v or "").strip().strip('"').lstrip("#")
        return "#" + v[:6] if len(v) >= 6 else padrao
    try:
        import tomllib
        d = tomllib.loads((TEMA / "colors.toml").read_text())
    except Exception:  # noqa: BLE001
        return "", None
    f, t = cor(d.get("background"), "#1c1c1c"), cor(d.get("foreground"), "#ffffff")
    a = cor(d.get("accent", d.get("color4")), "#4cc2ff")
    e = lum(f) < 0.45 and not (TEMA / "light.mode").exists()
    r, g, b = rgb(a)
    if (max(r, g, b) - min(r, g, b)) / max(1, max(r, g, b)) < 0.18:
        a = t  # destaque cinza (temas monocromáticos): usa o texto
    # no claro, cartões brancos sobre um fundo levemente cinza (como o libadwaita); no escuro, o inverso
    fundo = mix(f, t, 0.03 if e else 0.045)
    v = {"window-bg-color": fundo, "window-fg-color": t, "view-bg-color": fundo, "view-fg-color": t,
         "headerbar-bg-color": fundo, "headerbar-fg-color": t, "headerbar-backdrop-color": fundo,
         "card-bg-color": mix(f, t, 0.075) if e else f,
         "popover-bg-color": mix(f, t, 0.10 if e else 0.01), "popover-fg-color": t,
         "dialog-bg-color": mix(f, t, 0.10 if e else 0.01), "dialog-fg-color": t,
         "accent-bg-color": a, "accent-color": a, "accent-fg-color": "#000000" if lum(a) > 0.5 else "#ffffff"}
    nomes = "".join(f"@define-color {k[:-6].replace('-', '_')}_color {x};\n"
                    for k, x in v.items() if k.startswith(("accent", "window", "view")))
    return nomes + _t(":root { ") + " ".join(f"--{k}: {x};" for k, x in v.items()) + " }", e


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_startup(self):
        Adw.Application.do_startup(self)
        from gi.repository import Gdk
        prov = Gtk.CssProvider()
        prov.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        # Segue o tema do sistema (vantablack, white…), também ao trocar com o app aberto
        self.css_tema = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.css_tema,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self._aplicar_tema()
        self.mon_tema = Gio.File.new_for_path(str(TEMA.parent / "theme.name")).monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.mon_tema.connect("changed", lambda *_: self._aplicar_tema())
        for nome, fn in (("abrir-pasta", lambda p: Gio.AppInfo.launch_default_for_uri(Path(p).parent.as_uri(), None)),
                         ("excluir-iso", self._excluir)):
            a = Gio.SimpleAction.new(nome, GLib.VariantType.new("s"))
            a.connect("activate", lambda a, v, fn=fn: fn(v.unpack()))
            self.add_action(a)

    def _aplicar_tema(self):
        texto, escuro = css_tema()
        Adw.StyleManager.get_default().set_color_scheme(
            Adw.ColorScheme.PREFER_DARK if escuro is None else
            (Adw.ColorScheme.FORCE_DARK if escuro else Adw.ColorScheme.FORCE_LIGHT))
        self.css_tema.load_from_string(texto)

    def _excluir(self, p):
        j = self.get_active_window()
        d = Adw.AlertDialog(heading=_t("Excluir esta ISO?"), body=Path(p).name)
        d.add_response("cancelar", _t("Cancelar"))
        d.add_response("excluir", _t("Excluir"))
        d.set_response_appearance("excluir", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_close_response("cancelar")

        def resp(d, r):
            if r == "excluir":
                try:
                    Path(p).unlink()
                except OSError as e:
                    j.aviso(_t("Não foi possível excluir: %1", e.strerror))
                j._listar_isos()
        d.connect("response", resp)
        d.present(j)

    def do_activate(self):
        j = self.get_active_window() or Janela(self)
        j.present()


if __name__ == "__main__":
    sys.exit(App().run(sys.argv))
