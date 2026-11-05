pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// Visual tokens derived live from the active Simba theme.
//
// Same sources the Simba shell reads (shell/Commons/Color.qml):
//   ~/.local/state/simba/current/theme/colors.toml   palette
//   ~/.local/state/simba/current/theme.name          written last by simba-theme-set,
//                                                      so watching it catches every switch
//   fc-match monospace                                 the Simba font (simba font set)
//   hyprctl getoption decoration:rounding              the UI rounds exactly like the windows
//   hyprctl getoption animations:enabled               motion follows the compositor setting
Singleton {
  id: t

  readonly property string home: Quickshell.env("HOME")
  readonly property string estadoSimba: home + "/.local/state/simba/current"

  // ── raw palette ──────────────────────────────────────────────────────────
  property string nome: ""
  property var paleta: ({})
  property color fundo: "#000000"
  property color texto: "#ffffff"
  property color acento: "#8d8d8d"
  property color urgente: "#a4a4a4"
  property color mudoBase: "#7a7a7a"
  property string fonte: "JetBrainsMono Nerd Font"
  property int arredondamento: 0          // Hyprland decoration:rounding
  property bool animacoes: true           // Hyprland animations:enabled
  property int versao: 0                  // bumps on every theme reload (for cache-busting)

  // ── derived ──────────────────────────────────────────────────────────────
  readonly property bool escuro: luminancia(fundo) < 0.45

  function luminancia(c) {
    function ch(v) { return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
    return 0.2126 * ch(c.r) + 0.7152 * ch(c.g) + 0.0722 * ch(c.b)
  }
  function contraste(a, b) {
    var la = luminancia(a), lb = luminancia(b)
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
  }
  function mistura(a, b, k) {
    return Qt.rgba(a.r + (b.r - a.r) * k, a.g + (b.g - a.g) * k, a.b + (b.b - a.b) * k, 1)
  }
  function alfa(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }
  function saturacao(c) {
    var mx = Math.max(c.r, c.g, c.b), mn = Math.min(c.r, c.g, c.b)
    return mx === 0 ? 0 : (mx - mn) / mx
  }

  // Monochrome themes (Vantablack, White, Matte Black) have a grey accent; a
  // grey "primary" button reads as disabled, so the highlight falls back to the
  // foreground and the UI becomes a pure black-and-white composition.
  readonly property bool acentoCromatico: saturacao(acento) > 0.18 && contraste(acento, fundo) > 2.2
  readonly property color realce: acentoCromatico ? acento : texto
  readonly property color sobreRealce: contraste(fundo, realce) >= contraste(texto, realce) ? fundo : texto

  readonly property color janela: fundo
  readonly property color lateral: mistura(fundo, texto, escuro ? 0.025 : 0.035)
  readonly property color superficie: mistura(fundo, texto, escuro ? 0.045 : 0.04)
  readonly property color superficieAlta: mistura(fundo, texto, escuro ? 0.075 : 0.065)
  readonly property color superficieMax: mistura(fundo, texto, escuro ? 0.12 : 0.10)
  readonly property color linha: alfa(texto, escuro ? 0.09 : 0.12)
  readonly property color linhaForte: alfa(texto, escuro ? 0.18 : 0.22)
  readonly property color texto2: mistura(texto, fundo, 0.32)
  // claro: 0.44 mantém o texto terciário acima de 4.5:1 (WCAG AA) sobre o branco
  readonly property color texto3: mistura(texto, fundo, escuro ? 0.52 : 0.44)
  readonly property color hover: alfa(texto, escuro ? 0.06 : 0.06)
  readonly property color pressionado: alfa(texto, escuro ? 0.11 : 0.10)
  readonly property color selecao: alfa(realce, 0.16)
  readonly property color sombra: escuro ? Qt.rgba(0, 0, 0, 0.65) : Qt.rgba(0, 0, 0, 0.22)
  readonly property color perigo: cor("red", urgente)
  readonly property color sucesso: cor("green", realce)
  readonly property color aviso: cor("yellow", realce)

  function cor(chave, padrao) {
    var v = paleta[chave]
    return v ? v : padrao
  }

  // Radii follow Hyprland's window rounding, so changing "Arredondamento" in the
  // app reshapes the app itself. 0 keeps Simba's crisp square look.
  readonly property int raio: Math.min(arredondamento, 18)
  readonly property int raioPequeno: Math.round(raio * 0.6)
  readonly property int raioGrande: Math.min(Math.round(raio * 1.4), 24)

  // ── type scale ───────────────────────────────────────────────────────────
  readonly property int tLegenda: 11
  readonly property int tCorpo: 13
  readonly property int tSubtitulo: 14
  readonly property int tTitulo: 16
  readonly property int tTitulao: 26
  readonly property int tDisplay: 34

  // ── motion ───────────────────────────────────────────────────────────────
  readonly property int rapido: animacoes ? 120 : 0
  readonly property int medio: animacoes ? 220 : 0
  readonly property int lento: animacoes ? 380 : 0
  readonly property int curva: Easing.OutCubic
  readonly property int curvaEnfase: Easing.OutQuint

  // ── loading ──────────────────────────────────────────────────────────────
  function carregarCores(raw) {
    var p = {}
    var linhas = String(raw || "").split("\n")
    for (var i = 0; i < linhas.length; i++) {
      var m = linhas[i].match(/^\s*([A-Za-z0-9_-]+)\s*=\s*["']?(#[0-9A-Fa-f]{6})/)
      if (m) p[m[1]] = m[2]
    }
    paleta = p
    fundo = p.background || p.color0 || "#000000"
    texto = p.foreground || p.color7 || "#ffffff"
    acento = p.accent || p.color4 || p.blue || texto
    urgente = p.red || p.color1 || "#cc5555"
    mudoBase = p.muted || p.color8 || texto
    versao++
  }

  function recarregar() {
    coresArquivo.reload()
    nomeArquivo.reload()
    fonteProc.running = false
    fonteProc.running = true
    hyprProc.running = false
    hyprProc.running = true
  }

  property FileView coresArquivo: FileView {
    path: t.estadoSimba + "/theme/colors.toml"
    printErrors: false
    onLoaded: t.carregarCores(text())
  }

  // simba-theme-set rewrites theme.name after swapping the theme directory.
  property FileView nomeArquivo: FileView {
    path: t.estadoSimba + "/theme.name"
    watchChanges: true
    printErrors: false
    onFileChanged: { reload(); t.coresArquivo.reload(); t.temaTrocado() }
    onLoaded: t.nome = text().trim()
  }

  signal temaTrocado()

  property Process fonteProc: Process {
    command: ["fc-match", "-f", "%{family[0]}", "monospace"]
    running: true
    stdout: StdioCollector {
      onStreamFinished: { var f = text.trim(); if (f.length) t.fonte = f }
    }
  }

  property Process hyprProc: Process {
    command: ["bash", "-c", "hyprctl -j getoption decoration:rounding; echo @@; hyprctl -j getoption animations:enabled"]
    running: true
    stdout: StdioCollector {
      onStreamFinished: {
        var partes = text.split("@@")
        try { t.arredondamento = JSON.parse(partes[0]).int || 0 } catch (e) {}
        try { t.animacoes = JSON.parse(partes[1]).bool !== false } catch (e) {}
      }
    }
  }
}
