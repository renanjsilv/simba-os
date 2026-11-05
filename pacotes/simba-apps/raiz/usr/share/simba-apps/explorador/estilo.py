"""Visual do Explorador: cores do tema do Simba + toques do Windows 11 (CSS)."""
import tomllib
from pathlib import Path

from gi.repository import Adw, Gdk, Gio, GLib, Gtk

TEMA = Path.home() / ".local/state/simba/current/theme"


def _hex(c, padrao):
    c = str(c or "").strip().strip('"').lstrip("#")
    return "#" + c[:6] if len(c) >= 6 else padrao


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _mix(a, b, k):
    ra, rb = _rgb(a), _rgb(b)
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * k) for x, y in zip(ra, rb))


def _lum(h):
    r, g, b = (x / 255 for x in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def cores():
    try:
        d = tomllib.loads((TEMA / "colors.toml").read_text())
    except Exception:  # noqa: BLE001
        d = {}
    fundo = _hex(d.get("background"), "#1c1c1c")
    texto = _hex(d.get("foreground"), "#ffffff")
    acento = _hex(d.get("accent", d.get("color4")), "#4cc2ff")
    modo = str(d.get("mode", "")).lower()
    escuro = modo != "light" if modo else _lum(fundo) < 0.45
    if (TEMA / "light.mode").exists():
        escuro = False
    # Destaque cinza (temas monocromáticos): usa o texto, como o resto do sistema
    r, g, b = _rgb(acento)
    sat = (max(r, g, b) - min(r, g, b)) / max(1, max(r, g, b))
    if sat < 0.18:
        acento = texto
    return {"fundo": fundo, "texto": texto, "acento": acento, "escuro": escuro}


CSS = """
:root {
  --window-bg-color: @FUNDO@;
  --window-fg-color: @TEXTO@;
  --view-bg-color: @VISTA@;
  --view-fg-color: @TEXTO@;
  --headerbar-bg-color: @BARRA@;
  --headerbar-fg-color: @TEXTO@;
  --headerbar-backdrop-color: @BARRA@;
  --sidebar-bg-color: @LATERAL@;
  --sidebar-fg-color: @TEXTO@;
  --card-bg-color: @CARTAO@;
  --popover-bg-color: @POPOVER@;
  --popover-fg-color: @TEXTO@;
  --dialog-bg-color: @POPOVER@;
  --dialog-fg-color: @TEXTO@;
  --accent-bg-color: @ACENTO@;
  --accent-color: @ACENTO@;
  --accent-fg-color: @SOBREACENTO@;
}
window.explorador { background: @FUNDO@; }
/* a cor do texto não segue --window-fg-color nesta versão do libadwaita: no tema
   claro as barras de cima/baixo ficavam com texto branco em fundo branco */
window, dialog, popover > contents, popover > arrow { color: @TEXTO@; }
/* barra de título com abas (medidas do TabView do WinUI: 40 px, abas de 32) */
.barra-titulo { background: @BARRA@; min-height: 40px; }
.faixa-abas { min-height: 40px; }
.aba-win { background: transparent; }
.aba-titulo { font-size: 12px; }
.aba-win.selecionada .aba-titulo { font-weight: normal; }
.aba-win:not(.selecionada) .aba-titulo { opacity: 0.85; }
.aba-fechar { min-width: 24px; min-height: 24px; padding: 0; border-radius: 4px; }
.aba-fechar image { -gtk-icon-size: 12px; }
.aba-mais { min-width: 32px; min-height: 24px; padding: 0; border-radius: 4px; }
.aba-mais image { -gtk-icon-size: 14px; }
.controles-janela { margin: 0; }
.controles-janela button { min-width: 46px; min-height: 32px; padding: 0; margin: 0; border-radius: 0;
  background: transparent; box-shadow: none; }
.controles-janela button image { -gtk-icon-size: 12px; background: none; box-shadow: none; padding: 0; }
.controles-janela button:hover { background: @HOVER@; }
.controles-janela button.close:hover { background: #c42b1c; color: #ffffff; }
.barra-comandos { background: @VISTA@; padding: 4px 8px 4px 8px; border-bottom: 1px solid @LINHA@; }
.barra-comandos button { min-height: 32px; padding: 0 8px; border-radius: 4px; }
.barra-comandos label { font-size: 13px; }
.barra-comandos button.so-icone { padding: 0 8px; }
.barra-comandos button label { font-weight: normal; }
.barra-comandos separator { margin: 6px 4px; background: @LINHA@; }
.botao-novo { background: @ACENTO@; color: @SOBREACENTO@; }
.botao-novo:hover { background: @ACENTOHOVER@; }
.botao-novo:active { opacity: 0.85; }
.barra-endereco { background: @VISTA@; padding: 4px 8px 4px 8px; }
.barra-endereco > button.flat { min-width: 32px; min-height: 32px; padding: 0; margin: 0 1px; border-radius: 4px; }
.barra-endereco button.flat image { -gtk-icon-size: 14px; }
.caminho { background: @CAMPO@; border: 1px solid @LINHA@; border-radius: 4px; min-height: 30px; padding: 0 4px; }
.caminho button { padding: 0 6px; min-height: 24px; border-radius: 4px; font-weight: normal; font-size: 13px; }
.caminho entry, entry.caminho { font-size: 13px; }
.caminho .seta { padding: 0 2px; min-width: 14px; opacity: 0.7; }
.pesquisa { background: @CAMPO@; border: 1px solid @LINHA@; border-radius: 4px; min-height: 30px; font-size: 13px; }
.lateral { background: @LATERAL@; }
.lateral list { background: transparent; }
.lateral row { border-radius: 6px; margin: 1px 6px; min-height: 34px; }
.lateral row:selected { background: @SELECAO@; color: @TEXTO@; }
.lateral row:selected .marca { background: @ACENTO@; }
.lateral .marca { min-width: 3px; border-radius: 2px; margin: 9px 0; background: transparent; }
.lateral .seta-expandir { min-width: 14px; min-height: 18px; padding: 0; margin: 0; border-radius: 4px;
  background: transparent; box-shadow: none; opacity: 0.5; transition: opacity 120ms, background 120ms; }
.lateral .seta-expandir image { -gtk-icon-size: 12px; transition: -gtk-icon-transform 160ms ease-out; }
.lateral:hover .seta-expandir { opacity: 0.85; }
.lateral .seta-expandir:hover { background: @HOVER@; opacity: 1; }
.lateral .seta-expandir.aberto image { -gtk-icon-transform: rotate(90deg); }
.lateral .seta-vazia { min-width: 14px; }
.lateral .titulo-secao { font-size: 0.8em; opacity: 0.65; margin: 12px 18px 4px 18px; }
.conteudo { background: @CONTEUDO@; }
gridview.arquivos { background: transparent; padding: 8px; }
gridview.arquivos > child { border-radius: 8px; padding: 6px 4px; margin: 2px; }
gridview.arquivos > child:hover { background: @HOVER@; }
gridview.arquivos > child:selected { background: @SELECAO@; outline: 1px solid @SELECAOBORDA@; outline-offset: -1px; }
listview.arquivos > row { border-radius: 6px; margin: 0 6px; padding: 2px 6px; }
listview.arquivos > row:hover { background: @HOVER@; }
listview.arquivos > row:selected { background: @SELECAO@; }
columnview.arquivos { background: transparent; }
columnview.arquivos > listview > row { border-radius: 6px; margin: 0 4px; }
columnview.arquivos > listview > row:hover { background: @HOVER@; }
columnview.arquivos > listview > row:selected { background: @SELECAO@; }
columnview.arquivos > header > button { font-weight: normal; opacity: 0.8; }
.nome-arquivo { font-size: 0.95em; }
.oculto { opacity: 0.55; }
.recortado { opacity: 0.45; }
.barra-status { background: @CONTEUDO@; border-top: 1px solid @LINHA@; padding: 2px 12px; font-size: 0.9em; min-height: 28px; }
.barra-status button { min-height: 24px; min-width: 28px; padding: 0 4px; border-radius: 4px; }
.titulo-pagina { font-size: 1.15em; font-weight: 600; margin: 18px 24px 8px 24px; }
.bloco { background: @CARTAO@; border-radius: 8px; padding: 10px; border: 1px solid @LINHA@; }
.bloco, .disco, .nuvem-cartao { transition: background-color 120ms ease-out; }
.bloco:hover { background: @HOVER2@; }
.bloco:active, .disco:active, .nuvem-cartao:active { background: @PRESSIONADO@; }
.disco { background: @CARTAO@; border-radius: 8px; padding: 12px; border: 1px solid @LINHA@; }
.disco:hover { background: @HOVER2@; }
levelbar.uso block.filled { background: @ACENTO@; border-radius: 3px; }
levelbar.uso.cheio block.filled { background: #e5484d; }
.legenda.perigo { color: #e5484d; opacity: 1; }
levelbar.uso block.empty { background: @LINHA@; border-radius: 3px; }
levelbar.uso trough { min-height: 6px; padding: 0; background: transparent; border: none; }
.painel-detalhes { background: @LATERAL@; border-left: 1px solid @LINHA@; }
.secundario { opacity: 0.7; }
.legenda { font-size: 0.85em; opacity: 0.7; }
/* .menu-win sem padding próprio: o GTK cortava o último item */
.menu-win .icones-topo button { min-width: 38px; min-height: 38px; border-radius: 6px; }
.menu-win .item { min-height: 34px; border-radius: 6px; padding: 0 10px; font-weight: normal; }
.menu-win .item:hover { background: @HOVER@; }
.progresso-op { background: @CARTAO@; border-top: 1px solid @LINHA@; padding: 8px 14px; }
.vazio { opacity: 0.6; }
.nuvem-cartao { background: @CARTAO@; border-radius: 10px; padding: 14px; border: 1px solid @LINHA@; }
.nuvem-cartao:hover { background: @HOVER2@; }
"""


class Estilo:
    def __init__(self):
        self.valores = {}
        self._ouvintes = {}
        self._n = 0
        self.prov = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), self.prov,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self.aplicar()
        # Troca de tema do Simba: theme.name é escrito por último
        self.mon = Gio.File.new_for_path(str(TEMA.parent / "theme.name")).monitor_file(Gio.FileMonitorFlags.NONE, None)
        self.mon.connect("changed", lambda *a: self._tema_mudou())
        self._adiado = 0

    def _tema_mudou(self):
        # A troca de tema gera vários eventos e os arquivos do tema novo ainda estão
        # sendo trocados no primeiro: aplicar ali misturava as cores dos dois temas
        # (texto claro em fundo claro). Espera assentar e confere de novo depois.
        if self._adiado:
            GLib.source_remove(self._adiado)

        def agora():
            self._adiado = 0
            self.aplicar()
            GLib.timeout_add(1500, lambda: (self.aplicar(), False)[1])
            return False
        self._adiado = GLib.timeout_add(400, agora)

    def aplicar(self):
        c = cores()
        f, t, a, e = c["fundo"], c["texto"], c["acento"], c["escuro"]
        Adw.StyleManager.get_default().set_color_scheme(
            Adw.ColorScheme.FORCE_DARK if e else Adw.ColorScheme.FORCE_LIGHT)
        sobre = "#000000" if _lum(a) > 0.5 else "#ffffff"
        v = {
            "FUNDO": _mix(f, t, 0.03 if e else 0.02), "TEXTO": t,
            # Como no Windows 11: faixa das abas (Mica) mais escura; aba ativa, endereço
            # e comandos numa camada mais clara; conteúdo igual a ela.
            "VISTA": _mix(f, t, 0.085 if e else 0.0),
            "BARRA": _mix(f, t, 0.025 if e else 0.06),
            "CONTEUDO": _mix(f, t, 0.035 if e else 0.0),     # lateral e arquivos
            "LATERAL": _mix(f, t, 0.035 if e else 0.0),
            "CARTAO": _mix(f, t, 0.075 if e else 0.03),
            "POPOVER": _mix(f, t, 0.10 if e else 0.01),
            "CAMPO": _mix(f, t, 0.035 if e else 0.025),
            "ACENTO": a, "SOBREACENTO": sobre, "ACENTOHOVER": _mix(a, t if not e else f, 0.15),
            "LINHA": _mix(f, t, 0.12 if e else 0.12),
            "HOVER": _mix(f, t, 0.085 if e else 0.06),
            "HOVER2": _mix(f, t, 0.11 if e else 0.06),
            "PRESSIONADO": _mix(f, t, 0.14 if e else 0.10),
            "SELECAO": _mix(_mix(f, t, 0.035 if e else 0.0), a, 0.22 if e else 0.18),
            "SELECAOBORDA": _mix(f, a, 0.55),
        }
        v["HOVERABA"] = _mix(v["BARRA"], t, 0.07 if e else 0.06)
        self.valores = v
        css = CSS
        for k, val in v.items():
            css = css.replace(f"@{k}@", val)
        self.prov.load_from_string(css)
        for fn in list(self._ouvintes.values()):
            fn()

    def ouvir(self, fn):
        """fn() a cada troca de tema; devolve um id para esquecer()."""
        self._n += 1
        self._ouvintes[self._n] = fn
        return self._n

    def esquecer(self, n):
        self._ouvintes.pop(n, None)
