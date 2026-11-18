#!/usr/bin/env python3
"""Boas-vindas ao Simba OS — tela da primeira inicialização.

  boas-vindas                 abre sempre (para rever pelo menu)
  boas-vindas --primeira-vez  só abre se ~/.local/state/simba/boas-vindas-vista não existe

O marcador é criado ao terminar, pular ou fechar a janela. A ISO nunca o leva
(.local/state/simba está em gerar-iso/excluir-home.txt), então cada instalação nova
mostra a tela uma vez.
"""
import json
import os
import pwd
import shutil
import subprocess
import sys
import threading
import time

import gi
import sys as _sys, os as _os  # noqa: E401
_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))
from simba_i18n import t as _t  # noqa: E402  (traduções: /usr/share/simba-apps/idiomas)

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

APP_ID = "com.simba.BoasVindas"
HOME = os.path.expanduser("~")
AQUI = os.path.dirname(os.path.abspath(__file__))
MARCADOR = os.path.join(HOME, ".local/state/simba/boas-vindas-vista")
ESTADO_TEMA = os.path.join(HOME, ".local/state/simba/current")
BIN = os.path.join(HOME, ".local/bin")
os.environ["PATH"] = BIN + ":" + os.environ.get("PATH", "")


# ───────────────────────────────────────────────────────────── utilidades
def marcar_visto():
    os.makedirs(os.path.dirname(MARCADOR), exist_ok=True)
    open(MARCADOR, "a").close()


def rodar(cmd):
    """Dispara um comando solto (não espera, não herda a sessão do app)."""
    try:
        subprocess.Popen(cmd, start_new_session=True, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except OSError:
        return False


def em_segundo_plano(func, pronto):
    """func() numa thread; pronto(resultado) no thread da interface."""
    def alvo():
        try:
            r = func()
        except Exception:  # noqa: BLE001
            r = None
        GLib.idle_add(pronto, r)
    threading.Thread(target=alvo, daemon=True).start()


def primeiro_nome():
    try:
        nome = pwd.getpwuid(os.getuid()).pw_gecos.split(",")[0].strip()
    except KeyError:
        nome = ""
    nome = nome or os.environ.get("USER", "")
    return nome.split()[0].capitalize() if nome else ""


def ler_cores():
    cores = {}
    try:
        with open(os.path.join(ESTADO_TEMA, "theme/colors.toml")) as f:
            for linha in f:
                if "=" in linha:
                    k, v = linha.split("=", 1)
                    cores[k.strip()] = v.strip().strip("\"'")
    except OSError:
        pass
    return cores


def tema_atual():
    try:
        with open(os.path.join(ESTADO_TEMA, "theme.name")) as f:
            return f.read().strip()
    except OSError:
        return ""


def rgb(hexa):
    hexa = (hexa or "#000000").lstrip("#")
    return tuple(int(hexa[i:i + 2], 16) / 255 for i in (0, 2, 4))


def luminancia(hexa):
    def c(v):
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(hexa)
    return 0.2126 * c(r) + 0.7152 * c(g) + 0.0722 * c(b)


def saturacao(hexa):
    r, g, b = rgb(hexa)
    mx, mn = max(r, g, b), min(r, g, b)
    return 0 if mx == 0 else (mx - mn) / mx


def achar_desktop(*nomes):
    """Primeiro .desktop cujo nome de arquivo contém um dos nomes (sem diferenciar maiúsculas)."""
    dirs = [os.path.join(HOME, ".local/share")] + os.environ.get(
        "XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
    dirs += [os.path.join(HOME, ".local/share/flatpak/exports/share"), "/var/lib/flatpak/exports/share"]
    for d in dirs:
        apps = os.path.join(d, "applications")
        try:
            arquivos = sorted(os.listdir(apps))
        except OSError:
            continue
        for n in nomes:
            for a in arquivos:
                if a.endswith(".desktop") and n in a.lower():
                    return a[:-len(".desktop")]
    return None


# ───────────────────────────────────────────────────────────── ilustrações
# SVGs próprios, desenhados com as cores do tema (fg = texto, bg = fundo, ac = realce).
def svg_conta(fg, bg, ac):
    return _t("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 240 200\">\n  <defs><linearGradient id=\"n\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\">\n    <stop offset=\"0\" stop-color=\"%1\" stop-opacity=\".16\"/><stop offset=\"1\" stop-color=\"%2\" stop-opacity=\".05\"/></linearGradient></defs>\n  <path d=\"M62 132a34 34 0 0 1 6-67 46 46 0 0 1 88-8 38 38 0 0 1 22 75z\" fill=\"url(#n)\" stroke=\"%3\" stroke-opacity=\".55\" stroke-width=\"3\" stroke-linejoin=\"round\"/>\n  <g fill=\"none\" stroke=\"%4\" stroke-width=\"7\" stroke-linecap=\"round\" stroke-linejoin=\"round\">\n    <path d=\"M94 104a26 26 0 0 1 44-14\"/><path d=\"M134 76v15h-15\"/>\n    <path d=\"M146 112a26 26 0 0 1-44 14\"/><path d=\"M106 140v-15h15\"/>\n  </g>\n  <rect x=\"36\" y=\"150\" width=\"70\" height=\"40\" rx=\"7\" fill=\"%5\" stroke=\"%6\" stroke-opacity=\".5\" stroke-width=\"3\"/>\n  <rect x=\"44\" y=\"158\" width=\"54\" height=\"24\" rx=\"3\" fill=\"%7\" fill-opacity=\".12\"/>\n  <rect x=\"146\" y=\"146\" width=\"30\" height=\"48\" rx=\"7\" fill=\"%8\" stroke=\"%9\" stroke-opacity=\".5\" stroke-width=\"3\"/>\n  <circle cx=\"161\" cy=\"186\" r=\"2.6\" fill=\"%10\" fill-opacity=\".6\"/>\n  <rect x=\"184\" y=\"152\" width=\"34\" height=\"38\" rx=\"5\" fill=\"%11\" stroke=\"%12\" stroke-opacity=\".5\" stroke-width=\"3\"/>\n  <path d=\"M192 166h18M192 175h12\" stroke=\"%13\" stroke-opacity=\".45\" stroke-width=\"3\" stroke-linecap=\"round\"/>\n</svg>", fg, fg, fg, ac, bg, fg, fg, bg, fg, fg, bg, fg, fg)


def svg_draco(fg, bg, ac):
    barras = "".join(
        f'<rect x="{x - 4}" y="{100 - h / 2}" width="8" height="{h}" rx="4" fill="{bg}" fill-opacity=".92"/>'
        for x, h in zip(range(84, 160, 14), (18, 34, 52, 64, 46, 28)))
    return _t("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 240 200\">\n  <defs>\n    <radialGradient id=\"o\" cx=\".38\" cy=\".32\" r=\".8\">\n      <stop offset=\"0\" stop-color=\"%1\"/><stop offset=\".6\" stop-color=\"%2\" stop-opacity=\".78\"/>\n      <stop offset=\"1\" stop-color=\"%3\" stop-opacity=\".45\"/></radialGradient>\n    <radialGradient id=\"h\" cx=\".5\" cy=\".5\" r=\".5\">\n      <stop offset=\".55\" stop-color=\"%4\" stop-opacity=\".16\"/><stop offset=\"1\" stop-color=\"%5\" stop-opacity=\"0\"/></radialGradient>\n  </defs>\n  <circle cx=\"120\" cy=\"100\" r=\"98\" fill=\"url(#h)\"/>\n  <circle cx=\"120\" cy=\"100\" r=\"78\" fill=\"none\" stroke=\"%6\" stroke-opacity=\".14\" stroke-width=\"2\"/>\n  <circle cx=\"120\" cy=\"100\" r=\"62\" fill=\"url(#o)\"/>\n  %7\n  <ellipse cx=\"100\" cy=\"66\" rx=\"20\" ry=\"9\" fill=\"%8\" fill-opacity=\".18\" transform=\"rotate(-24 100 66)\"/>\n</svg>", fg, fg, fg, fg, fg, fg, barras, bg)


def svg_agentes(fg, bg, ac):
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 200">'
            f'<circle cx="120" cy="100" r="96" fill="{fg}" fill-opacity=".06"/>'
            f'<rect x="48" y="52" width="122" height="82" rx="22" fill="{fg}" fill-opacity=".92"/>'
            f'<path d="M74 132 l-6 26 l28 -24 z" fill="{fg}" fill-opacity=".92"/>'
            f'<rect x="68" y="76" width="66" height="9" rx="4.5" fill="{bg}" fill-opacity=".85"/>'
            f'<rect x="68" y="94" width="82" height="9" rx="4.5" fill="{bg}" fill-opacity=".6"/>'
            f'<rect x="68" y="112" width="48" height="9" rx="4.5" fill="{bg}" fill-opacity=".4"/>'
            f'<path d="M182 46 q4 18 22 22 q-18 4 -22 22 q-4 -18 -22 -22 q18 -4 22 -22 z" fill="{ac}"/>'
            f'<path d="M196 104 q2 9 11 11 q-9 2 -11 11 q-2 -9 -11 -11 q9 -2 11 -11 z" fill="{ac}" fill-opacity=".7"/>'
            '</svg>')


def svg_loja(fg, bg, ac):
    tiles = ""
    for i, (x, y) in enumerate(((84, 92), (122, 92), (84, 130), (122, 130))):
        op = (".9", ".55", ".55", ".3")[i]
        tiles += _t("<rect x=\"%1\" y=\"%2\" width=\"32\" height=\"32\" rx=\"9\" fill=\"%3\" fill-opacity=\"%4\"/>", x, y, bg, op)
    return _t("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 240 200\">\n  <path d=\"M92 64v-6a28 28 0 0 1 56 0v6\" fill=\"none\" stroke=\"%1\" stroke-opacity=\".7\" stroke-width=\"7\" stroke-linecap=\"round\"/>\n  <path d=\"M60 64h120l-8 116a10 10 0 0 1-10 9H78a10 10 0 0 1-10-9z\" fill=\"%2\"/>\n  %3\n  <circle cx=\"188\" cy=\"58\" r=\"20\" fill=\"%4\"/>\n  <path d=\"M188 47v22M177 58h22\" stroke=\"%5\" stroke-width=\"5\" stroke-linecap=\"round\"/>\n</svg>", fg, fg, tiles, ac, bg)


def svg_escritorio(fg, bg, ac):
    def doc(x, rot, cor, letra):
        return _t("<g transform=\"rotate(%1 %2 140)\">\n      <path d=\"M%3 70h48l20 20v86a6 6 0 0 1-6 6H%4a6 6 0 0 1-6-6V76a6 6 0 0 1 6-6z\" fill=\"%5\" stroke=\"%6\" stroke-opacity=\".55\" stroke-width=\"3\"/>\n      <path d=\"M%7 70v20h20\" fill=\"none\" stroke=\"%8\" stroke-opacity=\".55\" stroke-width=\"3\"/>\n      <rect x=\"%9\" y=\"104\" width=\"48\" height=\"30\" rx=\"6\" fill=\"%10\"/>\n      <text x=\"%11\" y=\"125\" font-family=\"sans-serif\" font-weight=\"800\" font-size=\"18\" text-anchor=\"middle\" fill=\"#fff\">%12</text>\n      <path d=\"M%13 146h48M%14 158h34\" stroke=\"%15\" stroke-opacity=\".3\" stroke-width=\"4\" stroke-linecap=\"round\"/>\n    </g>", rot, x + 34, x, x + 6, bg, fg, x + 48, fg, x + 10, cor, x + 34, letra, x + 10, x + 10, fg)
    return _t("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 240 200\">\n  %1%2%3%4\n</svg>", doc(6, -12, "#2b6be3", "W"), doc(58, -4, "#1f9d57", "X"), doc(108, 4, "#e2672b", "P"), doc(158, 12, "#d6333f", "PDF"))


def svg_wifi(fg, bg, ac):
    return ("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 240 200\">"
            f"<circle cx=\"120\" cy=\"104\" r=\"84\" fill=\"{fg}\" fill-opacity=\".06\"/>"
            f"<path d=\"M50 92a100 100 0 0 1 140 0\" fill=\"none\" stroke=\"{fg}\" stroke-opacity=\".35\" stroke-width=\"14\" stroke-linecap=\"round\"/>"
            f"<path d=\"M74 118a66 66 0 0 1 92 0\" fill=\"none\" stroke=\"{fg}\" stroke-opacity=\".6\" stroke-width=\"14\" stroke-linecap=\"round\"/>"
            f"<path d=\"M98 144a32 32 0 0 1 44 0\" fill=\"none\" stroke=\"{fg}\" stroke-width=\"14\" stroke-linecap=\"round\"/>"
            f"<circle cx=\"120\" cy=\"166\" r=\"9\" fill=\"{fg}\"/></svg>")


def nmcli(*args, timeout=20):
    return subprocess.run(["nmcli", *args], capture_output=True, text=True, timeout=timeout)


def internet_ok():
    try:
        return nmcli("-t", "networking", "connectivity", "check", timeout=10).stdout.strip() == "full"
    except (OSError, subprocess.SubprocessError):
        return False


def redes_wifi():
    """[(ssid, sinal, protegida, em_uso)] — uma por nome, a de sinal mais forte."""
    try:
        out = nmcli("-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY", "device", "wifi", "list", "--rescan", "auto").stdout
    except (OSError, subprocess.SubprocessError):
        return []
    vistas = {}
    for linha in out.splitlines():
        partes = linha.replace("\\:", "\0").split(":")
        if len(partes) < 4:
            continue
        uso, ssid, sinal, seg = [x.replace("\0", ":") for x in partes[:4]]
        if not ssid:
            continue
        sinal = int(sinal or 0)
        if ssid not in vistas or sinal > vistas[ssid][1]:
            vistas[ssid] = (ssid, sinal, bool(seg and seg != "--"), uso == "*")
    return sorted(vistas.values(), key=lambda r: (not r[3], -r[1]))


def svg_pronto(fg, bg, ac):
    return _t("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 240 200\">\n  <circle cx=\"120\" cy=\"100\" r=\"84\" fill=\"%1\" fill-opacity=\".06\"/>\n  <circle cx=\"120\" cy=\"100\" r=\"64\" fill=\"%2\"/>\n  <path d=\"M90 101l20 20 42-44\" fill=\"none\" stroke=\"%3\" stroke-width=\"12\" stroke-linecap=\"round\" stroke-linejoin=\"round\"/>\n  <g fill=\"%4\" fill-opacity=\".5\"><circle cx=\"34\" cy=\"52\" r=\"5\"/><circle cx=\"206\" cy=\"40\" r=\"4\"/>\n  <circle cx=\"214\" cy=\"150\" r=\"6\"/><circle cx=\"26\" cy=\"150\" r=\"3.5\"/><circle cx=\"64\" cy=\"22\" r=\"3\"/></g>\n</svg>", fg, fg, bg, fg)


def svg_previa(claro):
    """Miniatura de área de trabalho para os cartões de tema."""
    fundo, texto = ("#f4f4f4", "#1b1b1b") if claro else ("#050505", "#f2f2f2")
    jan = "#ffffff" if claro else "#141414"
    borda = "#d6d6d6" if claro else "#2a2a2a"
    return _t("<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 320 190\">\n  <rect width=\"320\" height=\"190\" rx=\"12\" fill=\"%1\"/>\n  <circle cx=\"250\" cy=\"150\" r=\"70\" fill=\"%2\" fill-opacity=\".05\"/><circle cx=\"60\" cy=\"40\" r=\"50\" fill=\"%3\" fill-opacity=\".04\"/>\n  <rect x=\"0\" y=\"0\" width=\"320\" height=\"18\" fill=\"%4\" opacity=\".9\"/>\n  <circle cx=\"14\" cy=\"9\" r=\"4\" fill=\"%5\" fill-opacity=\".7\"/>\n  <rect x=\"140\" y=\"6\" width=\"40\" height=\"6\" rx=\"3\" fill=\"%6\" fill-opacity=\".45\"/>\n  <rect x=\"268\" y=\"6\" width=\"40\" height=\"6\" rx=\"3\" fill=\"%7\" fill-opacity=\".3\"/>\n  <rect x=\"40\" y=\"38\" width=\"180\" height=\"120\" rx=\"8\" fill=\"%8\" stroke=\"%9\"/>\n  <rect x=\"40\" y=\"38\" width=\"48\" height=\"120\" rx=\"8\" fill=\"%10\" fill-opacity=\".05\"/>\n  <rect x=\"100\" y=\"54\" width=\"90\" height=\"8\" rx=\"4\" fill=\"%11\" fill-opacity=\".75\"/>\n  <rect x=\"100\" y=\"70\" width=\"104\" height=\"6\" rx=\"3\" fill=\"%12\" fill-opacity=\".25\"/>\n  <rect x=\"100\" y=\"82\" width=\"80\" height=\"6\" rx=\"3\" fill=\"%13\" fill-opacity=\".25\"/>\n  <rect x=\"100\" y=\"128\" width=\"46\" height=\"16\" rx=\"8\" fill=\"%14\"/>\n  <rect x=\"190\" y=\"88\" width=\"110\" height=\"80\" rx=\"8\" fill=\"%15\" stroke=\"%16\"/>\n  <rect x=\"202\" y=\"102\" width=\"40\" height=\"40\" rx=\"20\" fill=\"%17\" fill-opacity=\".12\"/>\n  <rect x=\"250\" y=\"108\" width=\"40\" height=\"6\" rx=\"3\" fill=\"%18\" fill-opacity=\".5\"/>\n  <rect x=\"250\" y=\"120\" width=\"30\" height=\"6\" rx=\"3\" fill=\"%19\" fill-opacity=\".25\"/>\n</svg>", fundo, texto, texto, jan, texto, texto, texto, jan, borda, texto, texto, texto, texto, texto, jan, borda, texto, texto, texto)


def textura_svg(svg, escala=2):
    """SVG → textura nítida: renderiza em `escala`× o viewBox (a imagem é reduzida na tela)."""
    vb = svg.split('viewBox="', 1)[1].split('"', 1)[0].split()
    w, h = float(vb[2]) * escala, float(vb[3]) * escala
    svg = svg.replace("<svg ", f'<svg width="{w:g}" height="{h:g}" ', 1)
    return Gdk.Texture.new_from_bytes(GLib.Bytes.new(svg.encode()))


# ───────────────────────────────────────────────────────────── janela
class Janela(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_t("Boas-vindas ao Simba OS"))
        self.set_default_size(900, 620)
        self.set_resizable(False)
        self.ilustracoes = []  # (Gtk.Picture, função svg)
        self.cartoes_tema = {}
        self.desktop_office = {}
        self.css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(), self.css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)

        self.toasts = Adw.ToastOverlay()
        vista = Adw.ToolbarView()
        topo = Adw.HeaderBar(show_title=False)
        topo.add_css_class("flat")
        self.pular = Gtk.Button(label=_t("Pular"))
        self.pular.add_css_class("flat")
        self.pular.set_tooltip_text(_t("Pular a apresentação (dá para rever pelo menu Iniciar)"))
        self.pular.connect("clicked", lambda *_: self.concluir())
        topo.pack_start(self.pular)
        vista.add_top_bar(topo)

        self.carrossel = Adw.Carousel(allow_scroll_wheel=False, spacing=0, hexpand=True, vexpand=True)
        self.carrossel.connect("page-changed", self.pagina_mudou)
        for montar in (self.p_inicio, self.p_wifi, self.p_conta, self.p_draco, self.p_agentes, self.p_aparencia,
                       self.p_loja, self.p_escritorio, self.p_atalhos, self.p_pronto):
            self.carrossel.append(montar())
        vista.set_content(self.carrossel)

        base = Gtk.CenterBox(margin_start=28, margin_end=28, margin_top=10, margin_bottom=22)
        self.voltar = Gtk.Button(label=_t("Voltar"))
        self.voltar.add_css_class("pill")
        self.voltar.connect("clicked", lambda *_: self.ir(-1))
        self.proximo = Gtk.Button(label=_t("Próximo"))
        self.proximo.add_css_class("pill")
        self.proximo.add_css_class("suggested-action")
        self.proximo.connect("clicked", lambda *_: self.ir(1))
        base.set_start_widget(self.voltar)
        base.set_center_widget(Adw.CarouselIndicatorDots(carousel=self.carrossel))
        base.set_end_widget(self.proximo)
        vista.add_bottom_bar(base)

        self.toasts.set_child(vista)
        self.set_content(self.toasts)

        teclas = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        teclas.connect("key-pressed", self.tecla)
        self.add_controller(teclas)
        self.connect("close-request", lambda *_: (marcar_visto(), False)[1])

        # Acompanha trocas de tema (feitas aqui ou em outro lugar) para recolorir tudo.
        self.monitor_tema = Gio.File.new_for_path(os.path.join(ESTADO_TEMA, "theme.name")).monitor_file(
            Gio.FileMonitorFlags.NONE, None)
        self.monitor_tema.connect("changed", lambda *_: GLib.timeout_add(250, self.aplicar_tema))
        self.aplicar_tema()
        self.pagina_mudou(self.carrossel, 0)
        inicio = int(os.environ.get("BOAS_VINDAS_PAGINA", "0") or 0)  # para testes/capturas
        if 0 < inicio < self.carrossel.get_n_pages():
            GLib.timeout_add(200, lambda: (self.carrossel.scroll_to(self.carrossel.get_nth_page(inicio), False), False)[1])
        captura = os.environ.get("BOAS_VINDAS_CAPTURA")  # testes: salva a janela em PNG e fecha
        if captura:
            GLib.timeout_add(1500, self._capturar, captura)

    def _capturar(self, caminho):
        w, h = self.get_width(), self.get_height()
        snap = Gtk.Snapshot()
        Gtk.WidgetPaintable.new(self).snapshot(snap, w, h)
        no = snap.to_node()
        if no is not None:
            self.get_renderer().render_texture(no, None).save_to_png(caminho)
        self.get_application().quit()
        return False
        self.atualizar_conta()

    # ── estrutura de página ───────────────────────────────────────────
    def pagina(self, titulo, texto, ilustracao=None, extra=None, tamanho=200):
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0, valign=Gtk.Align.CENTER,
                        halign=Gtk.Align.CENTER, hexpand=True, vexpand=True, margin_start=48, margin_end=48)
        caixa.add_css_class("pagina")
        if ilustracao is not None:
            if callable(ilustracao):
                img = Gtk.Image()
                self.ilustracoes.append((img, ilustracao))
            else:
                img = ilustracao
            img.set_pixel_size(tamanho)
            img.set_halign(Gtk.Align.CENTER)
            img.set_margin_bottom(26)
            caixa.append(img)
        t = Gtk.Label(label=titulo, wrap=True, justify=Gtk.Justification.CENTER)
        t.add_css_class("titulo")
        caixa.append(t)
        d = Gtk.Label(label=texto, wrap=True, justify=Gtk.Justification.CENTER, max_width_chars=58,
                      margin_top=10)
        d.add_css_class("descricao")
        caixa.append(d)
        if extra is not None:
            extra.set_margin_top(26)
            extra.set_halign(Gtk.Align.CENTER)
            caixa.append(extra)
        return caixa

    def botao(self, rotulo, acao, principal=False, icone=None):
        b = Gtk.Button()
        if icone:
            b.set_child(Adw.ButtonContent(label=rotulo, icon_name=icone))
        else:
            b.set_label(rotulo)
        b.add_css_class("pill")
        b.add_css_class("acao")
        b.set_halign(Gtk.Align.CENTER)
        if principal:
            b.add_css_class("suggested-action")
        b.connect("clicked", lambda *_: acao())
        return b

    # ── páginas ───────────────────────────────────────────────────────
    def p_inicio(self):
        self.mascote = Gtk.Image()
        nome = primeiro_nome()
        return self.pagina(_t("Olá%1! Bem-vindo ao Simba OS", ', ' + nome if nome else ''),
                           _t("Rápido, bonito e feito para o seu dia a dia. Em menos de um minuto "
                           "mostramos o que dá para fazer por aqui."),
                           self.mascote, tamanho=180)

    def p_wifi(self):
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, width_request=440)
        self.wifi_estado = Gtk.Label(label=_t("Procurando redes…"))
        self.wifi_estado.add_css_class("estado")
        self.wifi_lista = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.wifi_lista.add_css_class("boxed-list")
        self.wifi_lista.connect("row-activated", lambda _l, linha: self.wifi_escolher(linha.ssid, linha.protegida))
        rolagem = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, min_content_height=150,
                                     max_content_height=170, propagate_natural_height=True)
        rolagem.set_child(self.wifi_lista)
        self.wifi_rolagem = rolagem
        atualizar = Gtk.Button(label=_t("Procurar de novo"), halign=Gtk.Align.CENTER)
        atualizar.add_css_class("flat")
        atualizar.connect("clicked", lambda *_: self.wifi_atualizar())
        caixa.append(self.wifi_estado)
        caixa.append(rolagem)
        caixa.append(atualizar)
        GLib.timeout_add(400, lambda: (self.wifi_atualizar(), False)[1])
        return self.pagina(_t("Conecte-se à internet"),
                           _t("Escolha a sua rede Wi-Fi. Com internet, o próximo passo já traz a sua conta Google."),
                           svg_wifi, caixa, tamanho=130)

    def wifi_atualizar(self, manter_aviso=False):
        # manter_aviso: depois de uma falha a lista se atualiza, mas a mensagem de erro fica
        # (antes era trocada por "Escolha a sua rede:" em 1,5 s e a pessoa nunca via o motivo)
        if not manter_aviso:
            self.wifi_estado.set_label(_t("Procurando redes…"))

        def ler():
            return internet_ok(), redes_wifi()

        def pronto(r):
            if not r:
                return
            ok, redes = r
            while (linha := self.wifi_lista.get_row_at_index(0)) is not None:
                self.wifi_lista.remove(linha)
            for ssid, sinal, protegida, uso in redes[:12]:
                linha = Adw.ActionRow(title=GLib.markup_escape_text(ssid), activatable=not uso)
                linha.ssid, linha.protegida = ssid, protegida
                barras = "network-wireless-signal-" + ("excellent" if sinal > 75 else "good" if sinal > 50 else "ok" if sinal > 25 else "weak") + "-symbolic"
                linha.add_prefix(Gtk.Image(icon_name=barras))
                if uso:
                    linha.set_subtitle(_t("Conectado"))
                    linha.add_suffix(Gtk.Image(icon_name="object-select-symbolic"))
                elif protegida:
                    linha.add_suffix(Gtk.Image(icon_name="system-lock-screen-symbolic"))
                self.wifi_lista.append(linha)
            self.wifi_rolagem.set_visible(bool(redes))
            if ok:
                self.wifi_estado.set_label(_t("✓  Você está conectado à internet. Pode seguir."))
            elif manter_aviso:
                pass
            elif not redes:
                self.wifi_estado.set_label(_t("Nenhuma rede Wi-Fi encontrada. Use um cabo de rede ou procure de novo."))
            else:
                self.wifi_estado.set_label(_t("Escolha a sua rede:"))
        em_segundo_plano(ler, pronto)

    def wifi_escolher(self, ssid, protegida):
        if not protegida:
            self.wifi_conectar(ssid, "")
            return
        d = Adw.AlertDialog(heading=_t("Senha do Wi-Fi"), body=ssid)
        campo = Gtk.PasswordEntry(show_peek_icon=True, activates_default=True)
        d.set_extra_child(campo)
        d.add_response("cancelar", _t("Cancelar"))
        d.add_response("conectar", _t("Conectar"))
        d.set_response_appearance("conectar", Adw.ResponseAppearance.SUGGESTED)
        d.set_default_response("conectar")
        d.set_close_response("cancelar")
        d.connect("response", lambda _d, r: r == "conectar" and self.wifi_conectar(ssid, campo.get_text()))
        d.present(self)
        # uma vez só: grab_focus devolve True e o GLib repetia sem parar, selecionando o texto
        # inteiro a cada volta — cada tecla substituía a anterior (só ficava 1 caractere)
        GLib.idle_add(lambda: (campo.grab_focus(), False)[1])

    def wifi_conectar(self, ssid, senha):
        self.wifi_estado.set_label(_t("Conectando a %1…", ssid))

        def ligar():
            args = ["device", "wifi", "connect", ssid] + (["password", senha] if senha else [])
            try:
                r = nmcli(*args, timeout=45)
            except subprocess.TimeoutExpired:
                subprocess.run(["nmcli", "connection", "down", "id", ssid], capture_output=True, timeout=15)
                return ("tempo", "")
            if r.returncode != 0:
                return ("erro", (r.stderr or "") + (r.stdout or ""))
            # conectado: sem IPv4 não há internet (roteador que aceita a senha mas não entrega endereço)
            for _ in range(8):
                ip = subprocess.run(["ip", "-4", "-o", "addr", "show", "scope", "global"], capture_output=True, text=True)
                if "inet " in ip.stdout:
                    return ("ok", "")
                time.sleep(1.5)
            return ("sem-ip", "")

        def pronto(r):
            tipo, erro = r if r else ("erro", "")
            e = erro.lower()
            if tipo == "ok":
                self.toast(_t("Conectado a %1", ssid))
            elif tipo == "sem-ip":
                self.wifi_estado.set_label(_t("Conectado a %1, mas o roteador não entregou um endereço: sem internet. "
                                              "Tente de novo; se repetir, reinicie o roteador.", ssid))
            elif tipo == "tempo":
                self.wifi_estado.set_label(_t("%1 não respondeu em 45 segundos. A senha pode estar certa, mas o roteador "
                                              "não liberou a conexão. Tente de novo ou reinicie o roteador.", ssid))
            elif "secrets" in e or "psk" in e or "password" in e or "senha" in e or "authentication" in e:
                self.wifi_estado.set_label(_t("Senha incorreta. Confira (maiúsculas contam) e tente de novo."))
            elif "no network with ssid" in e or "nenhuma rede" in e or "not found" in e:
                self.wifi_estado.set_label(_t("%1 está fora de alcance. Chegue mais perto do roteador.", ssid))
            elif "ip configuration" in e or "configuração ip" in e or "dhcp" in e:
                self.wifi_estado.set_label(_t("A senha está certa, mas o roteador não entregou um endereço (DHCP). "
                                              "Tente de novo; se repetir, reinicie o roteador."))
            else:
                self.wifi_estado.set_label(_t("Não deu para conectar a %1. Tente de novo.", ssid))
            GLib.timeout_add(1500, lambda: (self.wifi_atualizar(manter_aviso=tipo != "ok"), False)[1])
        em_segundo_plano(ligar, pronto)
        return True

    def p_conta(self):
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.conta_botao = self.botao(_t("Entrar com Google"), self.entrar_google, True, "avatar-default-symbolic")
        self.conta_estado = Gtk.Label(visible=False)
        self.conta_estado.add_css_class("estado")
        caixa.append(self.conta_botao)
        caixa.append(self.conta_estado)
        caixa.append(self._montar_escolha())
        self.conta_texto = (_t("Entre com sua conta Google e o Simba OS guarda no seu Drive as configurações, "
                            "o papel de parede e os documentos. Formatou ou trocou de computador? "
                            "É só entrar de novo e tudo volta.") + " " +
                            _t("Depois do login você escolhe o que sincronizar."))
        pagina = self.pagina(_t("Sua conta, em todo lugar"), self.conta_texto, svg_conta, caixa)
        self.conta_ilustracao = pagina.get_first_child()
        return pagina

    # Escolha do que sincronizar (aparece logo depois do 1º login; nada é enviado antes).
    ESCOLHAS = [
        ("config", "Configurações e aplicativos"),
        ("imagens", "Papéis de parede e imagens"),
        ("historico", "Histórico do navegador e do terminal"),
        ("documentos", "Documentos e área de trabalho"),
        ("pacotes", "Lista de programas instalados"),
        ("fundo", "Papel de parede igual nos outros computadores"),
    ]

    def _montar_escolha(self):
        self.escolha_caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10, visible=False)
        rotulo = Gtk.Label(label=_t("O que você quer sincronizar?"))
        rotulo.add_css_class("heading")
        self.escolha_caixa.append(rotulo)
        grade = Gtk.Grid(column_spacing=24, row_spacing=4, halign=Gtk.Align.CENTER)
        self.escolha_opcoes = {}
        for i, (chave, texto) in enumerate(self.ESCOLHAS):
            cb = Gtk.CheckButton(label=_t(texto), active=True)
            self.escolha_opcoes[chave] = cb
            grade.attach(cb, i % 2, i // 2, 1, 1)
        self.escolha_caixa.append(grade)
        self.escolha_botao = self.botao(_t("Começar a sincronizar"), self.confirmar_escolha, True)
        self.escolha_caixa.append(self.escolha_botao)
        return self.escolha_caixa

    def _mostrar_escolha(self, mostrar):
        self.escolha_caixa.set_visible(mostrar)
        # sem a ilustração a lista cabe na janela (que não muda de tamanho)
        if getattr(self, "conta_ilustracao", None) is not None:
            self.conta_ilustracao.set_visible(not mostrar)
        self.conta_botao.set_visible(not mostrar)

    def confirmar_escolha(self):
        cats = [k for k, _ in self.ESCOLHAS if k != "fundo" and self.escolha_opcoes[k].get_active()]
        fundo = "liga" if self.escolha_opcoes["fundo"].get_active() else "desliga"
        self.escolha_botao.set_sensitive(False)

        def escolher():
            return subprocess.run(["conta", "escolher", "--categorias", ",".join(cats), "--fundo", fundo],
                                  capture_output=True, timeout=60).returncode

        def pronto(rc):
            self.escolha_botao.set_sensitive(True)
            if rc != 0:
                self.toast(_t("Não foi possível salvar a escolha."))
                return
            self._sincronizou_inicial = True   # `conta escolher` já ligou e sincronizou
            self._mostrar_escolha(False)
            self.toast(_t("Sincronização iniciada") if cats else _t("Escolha salva"))
            self.atualizar_conta()
        em_segundo_plano(escolher, pronto)

    def p_draco(self):
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        dicas = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        for exemplo in (_t("“Que horas são?”"), _t("“Abre o Spotify”"), _t("“Me lembra às 15h”")):
            c = Gtk.Label(label=exemplo)
            c.add_css_class("chip")
            dicas.append(c)
        caixa.append(dicas)
        caixa.append(self.botao(_t("Configurar o Draco"), lambda: self.abrir(["draco", "config"]), True,
                                "audio-input-microphone-symbolic"))
        return self.pagina(_t("Conheça o Draco, seu assistente de voz"),
                           _t("Segure F10, peça o que quiser e solte. Ele abre apps, "
                           "pesquisa na web, controla a música, manda mensagens e cria lembretes."),
                           svg_draco, caixa, tamanho=170)

    def p_agentes(self):
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        dicas = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        for exemplo in (_t("“Cria um site para minha loja”"), _t("“Organiza meus arquivos”"),
                        _t("“Por que o Wi-Fi caiu?”")):
            c = Gtk.Label(label=exemplo)
            c.add_css_class("chip")
            dicas.append(c)
        caixa.append(dicas)
        # OpenCode já vem instalado: aqui a pessoa confere se há versão nova (1ª inicialização)
        self.oc_status = Gtk.Label(label=_t("Conferindo o OpenCode…"), wrap=True, justify=Gtk.Justification.CENTER)
        self.oc_status.add_css_class("dim-label")
        caixa.append(self.oc_status)
        botoes = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        self.oc_atualizar = self.botao(_t("Atualizar o OpenCode"), self.opencode_atualizar, False,
                                       "software-update-available-symbolic")
        self.oc_atualizar.set_visible(False)
        botoes.append(self.oc_atualizar)
        botoes.append(self.botao(_t("Abrir os Agentes"), lambda: self.abrir(["simba-agentes"]), True,
                                 "user-available-symbolic"))
        caixa.append(botoes)
        return self.pagina(_t("Agentes de IA: peça, eles fazem"),
                           _t("Converse com o Claude, o Codex, o OpenCode e outros: eles programam, criam "
                              "documentos, pesquisam na web e resolvem problemas do computador por você. "
                              "O OpenCode já vem instalado e dá para usar de graça, sem conta."),
                           svg_agentes, caixa, tamanho=150)

    def opencode_conferir(self):
        if getattr(self, "oc_conferindo", False):
            return
        self.oc_conferindo = True

        def ler():
            r = subprocess.run(["/usr/bin/agentes", "versao", "opencode"], capture_output=True, text=True, timeout=60)
            return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None

        def pronto(info):
            self.oc_conferindo = False
            if not info:                       # consulta falhou (sem internet etc.): não afirma nada
                self.oc_status.set_label("")
                self.oc_atualizar.set_visible(False)
                return False
            if not info.get("instalado"):
                self.oc_status.set_label(_t("O OpenCode não está instalado: abra os Agentes para instalar."))
                self.oc_atualizar.set_visible(False)
            elif info.get("pendente"):
                self.oc_status.set_label(_t("OpenCode %1 instalado · versão nova disponível: %2",
                                            info.get("versao_atual", ""), info.get("versao_nova", "")))
                self.oc_atualizar.set_visible(True)
            else:
                v = info.get("versao_atual", "")
                self.oc_status.set_label(_t("OpenCode %1 instalado e em dia", v) if v else _t("OpenCode instalado"))
                self.oc_atualizar.set_visible(False)
            return False
        em_segundo_plano(ler, pronto)

    def opencode_atualizar(self):
        self.oc_atualizar.set_sensitive(False)
        self.oc_status.set_label(_t("Atualizando o OpenCode… pode seguir, avisamos quando terminar."))

        def atualizar():
            return subprocess.run(["/usr/bin/agentes", "atualizar", "opencode"], capture_output=True,
                                  timeout=900).returncode

        def pronto(rc):
            self.oc_atualizar.set_sensitive(True)
            if rc == 0:
                self.oc_atualizar.set_visible(False)
            self.opencode_conferir()
            return False
        em_segundo_plano(atualizar, pronto)

    def p_aparencia(self):
        linha = Gtk.Box(spacing=22, halign=Gtk.Align.CENTER)
        for tema, rotulo, claro in (("black", _t("Escuro"), False), ("white", _t("Claro"), True)):
            b = Gtk.Button()
            b.add_css_class("cartao-tema")
            corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            img = Gtk.Picture.new_for_paintable(textura_svg(svg_previa(claro)))
            img.set_can_shrink(True)
            img.set_content_fit(Gtk.ContentFit.CONTAIN)
            img.set_size_request(240, 142)
            img.add_css_class("previa")
            corpo.append(img)
            rot = Gtk.Box(spacing=8, halign=Gtk.Align.CENTER)
            marca = Gtk.Image.new_from_icon_name("object-select-symbolic")
            marca.add_css_class("marca")
            rot.append(marca)
            rot.append(Gtk.Label(label=rotulo))
            corpo.append(rot)
            b.set_child(corpo)
            b.connect("clicked", lambda _b, t=tema: self.trocar_tema(t))
            self.cartoes_tema[tema] = (b, marca)
            linha.append(b)
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        caixa.append(linha)
        mais = Gtk.Button(label=_t("Mais temas e papéis de parede"), halign=Gtk.Align.CENTER)
        mais.add_css_class("flat")
        mais.add_css_class("link-acao")
        mais.connect("clicked", lambda *_: self.abrir(["configuracoes", "personalizacao"]))
        caixa.append(mais)
        return self.pagina(_t("Do seu jeito: claro ou escuro"),
                           _t("Escolha a aparência — dá para mudar quando quiser, junto com cores, ícones, "
                           "papel de parede e a tela de inicialização."), None, caixa)

    def p_loja(self):
        return self.pagina(_t("Milhares de apps a um clique"),
                           _t("A Loja reúne apps verificados do Flathub — navegadores, jogos, edição de "
                           "fotos e vídeo, estudo e muito mais. Eles se atualizam sozinhos, sem você "
                           "precisar fazer nada."),
                           svg_loja, self.botao(_t("Abrir a Loja"), self.abrir_loja, True, "system-software-install-symbolic"))

    def p_escritorio(self):
        caixa = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER)
        self.caixa_office = caixa
        for chave, rotulo, icone in (("wordcraft", _t("WordCraft"), "x-office-document-symbolic"),
                                     ("gridcraft", _t("GridCraft"), "x-office-spreadsheet-symbolic"),
                                     ("deckcraft", _t("DeckCraft"), "x-office-presentation-symbolic"),
                                     ("pdfcraft", _t("PdfCraft"), "x-office-document-symbolic")):
            b = self.botao(rotulo, lambda c=chave: self.abrir_office(c), icone=icone)
            self.desktop_office[chave] = b
            caixa.append(b)
        self.office_aviso = Gtk.Label(label=_t("Os apps de escritório ainda estão sendo instalados."), visible=False)
        self.office_aviso.add_css_class("estado")
        fora = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        fora.append(caixa)
        fora.append(self.office_aviso)
        return self.pagina(_t("Escritório completo, já instalado"),
                           _t("Textos, planilhas, apresentações e PDFs — abre e salva arquivos do Word, "
                           "Excel e PowerPoint. Gratuito, leve e sem precisar de conta."),
                           svg_escritorio, fora, tamanho=170)

    def p_atalhos(self):
        grade = Gtk.Grid(column_spacing=48, row_spacing=14, halign=Gtk.Align.CENTER)
        atalhos = (
            ([_t("Super")], _t("Menu Iniciar")),
            ([_t("Super"), "E"], _t("Explorador de Arquivos")),
            ([_t("Ctrl"), _t("Shift"), _t("Esc")], _t("Gerenciador de Tarefas")),
            ([_t("Super"), "←", "→"], _t("Encaixar janela nos lados")),
            ([_t("Super"), "↑"], _t("Maximizar janela")),
            ([_t("Super"), "L"], _t("Bloquear a tela")),
            ([_t("Super"), "P"], _t("Projetar em outra tela")),
            (["F10"], _t("Falar com o Draco")),
        )
        for i, (teclas, descricao) in enumerate(atalhos):
            linha = Gtk.Box(spacing=12)
            tecs = Gtk.Box(spacing=5)
            tecs.set_size_request(160, -1)
            for t in teclas:
                k = Gtk.Label(label=t)
                k.add_css_class("tecla")
                tecs.append(k)
            linha.append(tecs)
            d = Gtk.Label(label=descricao, xalign=0)
            d.add_css_class("atalho")
            linha.append(d)
            grade.attach(linha, i % 2, i // 2, 1, 1)
        caixa = self.pagina(_t("Atalhos que valem ouro"),
                            _t("Tudo também funciona com o mouse, mas estes atalhos deixam o dia bem mais rápido."),
                            None, grade)
        return caixa

    def p_pronto(self):
        return self.pagina(_t("Tudo pronto!"),
                           _t("Aproveite o Simba OS. Para rever esta apresentação, procure "
                           "“Boas-vindas” no menu Iniciar."),
                           svg_pronto, None, tamanho=180)

    # ── navegação ─────────────────────────────────────────────────────
    def ir(self, passo):
        # Durante a animação conta a partir do DESTINO (a posição ainda está na página anterior e
        # um clique rápido "voltava"); fora dela, a partir da página REAL. Antes o destino valia
        # sempre: se a animação parava no meio (a lista do Wi-Fi mudando o tamanho da página),
        # um clique não avançava e o seguinte pulava duas páginas.
        n = self.carrossel.get_n_pages()
        animando = time.monotonic() - getattr(self, "ultimo_ir", 0) < 0.5
        base = self.destino if animando and hasattr(self, "destino") else round(self.carrossel.get_position())
        alvo = base + passo
        if alvo >= n:
            self.concluir()
            return
        if 0 <= alvo < n:
            self.destino = alvo
            self.ultimo_ir = time.monotonic()
            self.carrossel.scroll_to(self.carrossel.get_nth_page(alvo), True)
            if getattr(self, "conferir_id", 0):
                GLib.source_remove(self.conferir_id)
            self.conferir_id = GLib.timeout_add(700, self._conferir_pagina)

    def _conferir_pagina(self):
        """A animação foi interrompida no caminho: termina sem animar, na página pedida."""
        self.conferir_id = 0
        alvo = getattr(self, "destino", 0)
        if abs(self.carrossel.get_position() - alvo) > 0.01:
            self.carrossel.scroll_to(self.carrossel.get_nth_page(alvo), False)
        return False

    def pagina_mudou(self, carrossel, indice):
        self.destino = indice  # também quando a pessoa arrasta o carrossel
        n = carrossel.get_n_pages()
        ultima = indice >= n - 1
        self.voltar.set_sensitive(indice > 0)
        self.voltar.set_opacity(1 if indice > 0 else 0)
        self.proximo.set_label(_t("Começar a usar") if ultima else (_t("Vamos lá") if indice == 0 else _t("Próximo")))
        self.pular.set_visible(not ultima)
        # 0 início · 1 Wi-Fi · 2 conta · 3 Draco · 4 Agentes · 5 aparência · 6 Loja · 7 Escritório
        # 8 atalhos · 9 pronto
        if indice == 1:
            self.wifi_atualizar()
        if indice == 2:
            self.atualizar_conta()
        if indice == 4:
            self.opencode_conferir()
        if indice == 7:
            self.atualizar_office()
        self.proximo.grab_focus()

    def tecla(self, _c, keyval, _code, estado):
        if estado & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK):
            return False
        foco = self.get_focus()
        if isinstance(foco, Gtk.Editable) or isinstance(getattr(foco, "get_parent", lambda: None)(), Gtk.Editable):
            return False   # digitando (senha do Wi-Fi): as setas movem o cursor, não a página
        if keyval in (Gdk.KEY_Right, Gdk.KEY_Page_Down):
            self.ir(1)
            return True
        if keyval in (Gdk.KEY_Left, Gdk.KEY_Page_Up):
            self.ir(-1)
            return True
        return False

    def concluir(self):
        marcar_visto()
        self.close()

    # ── ações ─────────────────────────────────────────────────────────
    def toast(self, texto):
        self.toasts.add_toast(Adw.Toast(title=texto, timeout=3))

    def abrir(self, cmd):
        if not shutil.which(cmd[0]) or not rodar(cmd):
            self.toast(_t("Não foi possível abrir agora."))

    def entrar_google(self):
        # Já conectado: o botão vira "Gerenciar a conta" e leva às Configurações.
        if getattr(self, "conectado", False) or not shutil.which("conta"):
            self.abrir(["configuracoes", "contas"])
            return
        # Abre o login do Google direto no navegador (o próprio `conta entrar` faz isso)
        if not rodar(["conta", "entrar"]):
            self.toast(_t("Não foi possível abrir agora."))
            return
        self.conta_estado.set_label(_t("Termine o login na janela do navegador…"))
        self.conta_estado.set_visible(True)
        # acompanha o login até terminar (até 2 minutos)
        self.tentativas_conta = 40
        GLib.timeout_add_seconds(3, self._vigiar_conta)

    def _vigiar_conta(self):
        self.tentativas_conta -= 1
        self.atualizar_conta()
        return self.tentativas_conta > 0 and not getattr(self, "conectado", False)

    def atualizar_conta(self):
        if not shutil.which("conta"):
            return

        def ler():
            r = subprocess.run(["conta", "status"], capture_output=True, text=True, timeout=15)
            return json.loads(r.stdout)

        def pronto(st):
            if not st:
                return
            self.conectado = bool(st.get("conectado"))
            if self.conectado:
                quem = st.get("email") or st.get("nome") or _t("sua conta Google")
                self.conta_estado.set_label(_t("✓  Conectado como %1", quem))
                self.conta_estado.set_visible(True)
                self.conta_botao.set_child(Adw.ButtonContent(label=_t("Gerenciar a conta"),
                                                             icon_name="avatar-default-symbolic"))
                self.conta_botao.remove_css_class("suggested-action")
                if st.get("precisa_escolher"):
                    # `conta escolher` liga o backup/papel conforme a escolha e já sincroniza
                    self._mostrar_escolha(True)
                    self.conta_estado.set_label(_t("✓  Conectado como %1", quem) + " — " +
                                                _t("escolha abaixo o que sincronizar"))
                elif not getattr(self, "_sincronizou_inicial", False):
                    self._sincronizou_inicial = True
                    def sincronizar_inicial():
                        subprocess.run(["systemctl", "--user", "enable", "--now", "conta-fundo.service"],
                                       capture_output=True, timeout=10)
                        subprocess.run(["conta", "fundo", "puxar"], capture_output=True, timeout=30)
                        subprocess.run(["conta", "fundo", "enviar"], capture_output=True, timeout=30)
                        subprocess.run(["conta", "sincronizar", "--silencioso"], capture_output=True, timeout=120)
                    em_segundo_plano(sincronizar_inicial, lambda _: None)
            elif st.get("erro") and not st.get("entrando") and getattr(self, "tentativas_conta", 0):
                # ex.: backup criptografado pede a senha — isso é feito em Contas
                self.conta_estado.set_label(st["erro"])
                self.conta_estado.set_visible(True)
            elif st.get("boas_vindas"):
                self.conta_estado.set_label(_t("Tem um backup no Drive? Entre para trazer tudo de volta."))
                self.conta_estado.set_visible(True)

        em_segundo_plano(ler, pronto)

    def trocar_tema(self, tema):
        if tema == tema_atual():
            return
        for b, _m in self.cartoes_tema.values():
            b.set_sensitive(False)

        def trocar():
            return subprocess.run(["simba-theme-set", tema], capture_output=True, timeout=60).returncode

        def pronto(rc):
            for b, _m in self.cartoes_tema.values():
                b.set_sensitive(True)
            if rc != 0:
                self.toast(_t("Não foi possível trocar o tema."))
            self.aplicar_tema()

        em_segundo_plano(trocar, pronto)

    def abrir_loja(self):
        if shutil.which("simba-loja") and rodar(["simba-loja"]):
            return
        self.toast(_t("Não foi possível abrir a Loja."))

    def atualizar_office(self):
        algum = False
        for chave, b in self.desktop_office.items():
            ident = achar_desktop(chave)
            b.ident = ident
            b.set_visible(bool(ident))
            algum = algum or bool(ident)
        self.office_aviso.set_visible(not algum)

    def abrir_office(self, chave):
        ident = getattr(self.desktop_office[chave], "ident", None) or achar_desktop(chave)
        if not ident or not rodar(["gtk-launch", ident]):
            self.toast(_t("Este app ainda não está instalado."))

    # ── tema ──────────────────────────────────────────────────────────
    def aplicar_tema(self):
        cores = ler_cores()
        fundo = cores.get("background", "#000000")
        texto = cores.get("foreground", "#ffffff")
        acento = cores.get("accent", texto)
        escuro = luminancia(fundo) < 0.45
        # Temas monocromáticos (black/white): acento cinza parece desabilitado,
        # então o destaque vira a própria cor do texto (preto-e-branco puro).
        lf, la = luminancia(fundo), luminancia(acento)
        contraste = (max(lf, la) + 0.05) / (min(lf, la) + 0.05)
        realce = acento if saturacao(acento) > 0.18 and contraste > 2.2 else texto
        sobre = fundo if luminancia(realce) > 0.45 else "#ffffff"
        if luminancia(realce) <= 0.45 and not escuro:
            sobre = "#ffffff"
        Adw.StyleManager.get_default().set_color_scheme(
            Adw.ColorScheme.FORCE_DARK if escuro else Adw.ColorScheme.FORCE_LIGHT)

        def mix(a, b, k):
            ra, rb = rgb(a), rgb(b)
            return "#" + "".join(f"{round((x + (y - x) * k) * 255):02x}" for x, y in zip(ra, rb))

        superficie = mix(fundo, texto, 0.06 if escuro else 0.045)
        superficie2 = mix(fundo, texto, 0.11 if escuro else 0.09)
        linha = mix(fundo, texto, 0.16 if escuro else 0.14)
        texto2 = mix(texto, fundo, 0.32)
        self.css.load_from_string(f"""
          window, window.background {{ background-color: {fundo}; color: {texto}; }}
          headerbar {{ background: transparent; box-shadow: none; }}
          .titulo {{ font-size: 28px; font-weight: 800; letter-spacing: -0.4px; }}
          .descricao {{ font-size: 15px; color: {texto2}; line-height: 1.35; }}
          .estado {{ font-size: 13px; color: {texto2}; }}
          button.pill {{ padding: 10px 26px; font-weight: 600; }}
          button.suggested-action {{ background-color: {realce}; color: {sobre}; }}
          button.suggested-action:hover {{ background-color: {mix(realce, fundo, 0.08)}; }}
          button.acao:not(.suggested-action) {{ background-color: {superficie}; border: 1px solid {linha}; }}
          button.acao:not(.suggested-action):hover {{ background-color: {superficie2}; }}
          .chip {{ padding: 7px 14px; border-radius: 999px; background-color: {superficie};
                   border: 1px solid {linha}; color: {texto2}; font-size: 13px; }}
          .tecla {{ padding: 4px 10px; min-width: 18px; border-radius: 8px; font-weight: 700; font-size: 13px;
                    background-color: {superficie2}; border: 1px solid {linha};
                    box-shadow: inset 0 -3px 0 {linha}; }}
          .atalho {{ font-size: 14px; }}
          button.cartao-tema {{ padding: 10px; border-radius: 18px; background-color: {superficie};
                                border: 2px solid {linha}; font-weight: 700; font-size: 15px; }}
          button.cartao-tema:hover {{ background-color: {superficie2}; }}
          button.cartao-tema.ativo {{ border-color: {realce}; }}
          button.cartao-tema .marca {{ opacity: 0; }}
          button.cartao-tema.ativo .marca {{ opacity: 1; color: {realce}; }}
          .previa {{ border-radius: 12px; }}
          .link-acao {{ color: {texto2}; font-weight: 600; }}
          .link-acao:hover {{ color: {texto}; }}
          carouselindicatordots {{ color: {texto}; }}
        """)
        self.mascote.set_from_file("/usr/share/simba-apps/marca-pixel/retrato-1152.png")  # retrato em pixel art (claro e escuro)
        for img, func in self.ilustracoes:
            img.set_from_paintable(textura_svg(func(texto, fundo, realce)))
        atual = tema_atual()
        for tema, (b, _m) in self.cartoes_tema.items():
            (b.add_css_class if tema == atual else b.remove_css_class)("ativo")
        return False


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)

    def do_activate(self):
        win = self.get_active_window() or Janela(self)
        win.present()


def main():
    if "--primeira-vez" in sys.argv:
        if os.path.exists(MARCADOR):
            return 0
        sys.argv.remove("--primeira-vez")
    return App().run(sys.argv[:1])


if __name__ == "__main__":
    sys.exit(main())
