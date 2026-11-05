import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import qs.Comum

// The desktop: a transparent layer on WlrLayer.Bottom on every screen (above
// Simba's wallpaper layer, below every window) that catches clicks on empty
// desktop, shows the desktop folder's icons on the chosen screen and opens the
// Windows 11-style context menu. It never takes keyboard focus; only the menu,
// rename field and properties card (Overlay layer) do, while they are open.
Scope {
  id: a

  // ── state ────────────────────────────────────────────────────────────────
  property var itens: []
  property var selecao: []           // paths
  property string xdg: ""
  readonly property bool menuAberto: menu.aberto
  readonly property int totalIcones: itens.length
  readonly property string pasta: Preferencias.obter("area.pasta", "") || xdg
  readonly property bool mostrar: Preferencias.obter("area.mostrarIcones", true)
  readonly property string tamanho: Preferencias.obter("area.tamanho", "medio")
  readonly property string ordenar: Preferencias.obter("area.ordenar", "nome")
  readonly property bool automatico: Preferencias.obter("area.automatico", false)
  readonly property bool grade: Preferencias.obter("area.grade", true)
  readonly property bool ocultos: Preferencias.obter("area.ocultos", false)
  property int versao: 0          // bumps on refresh (icons replay their entrance)
  property bool elevada: false
  function espiar(ms) { elevada = true; baixar.interval = Math.max(300, ms || 1500); baixar.restart() }
  Timer { id: baixar; onTriggered: a.elevada = false }

  readonly property var celula: tamanho === "grande" ? { w: 118, h: 128, i: 64 } : (tamanho === "pequeno" ? { w: 82, h: 86, i: 32 } : { w: 98, h: 106, i: 48 })

  // The screen that shows icons: preference, else the monitor at 0,0, else the first.
  readonly property string telaIcones: {
    var p = Preferencias.obter("area.tela", "")
    if (p === "*") return "*"
    var nomes = Quickshell.screens.map(function(s) { return s.name })
    if (p && nomes.indexOf(p) >= 0) return p
    var zero = Quickshell.screens.filter(function(s) { return s.x === 0 && s.y === 0 })[0]
    return zero ? zero.name : (nomes[0] || "")
  }

  Process {
    command: ["xdg-user-dir", "DESKTOP"]
    running: true
    stdout: StdioCollector { onStreamFinished: { a.xdg = text.trim() || Quickshell.env("HOME") } }
  }

  property string renomearPendente: ""
  function listar() {
    if (!pasta) return
    Sistema.json([Sistema.bin + "/area", "listar", pasta].concat(ocultos ? ["--ocultos"] : []), function(v) {
      if (!Array.isArray(v)) return
      a.itens = a.ordenados(v)
      var vivos = a.itens.map(function(x) { return x.caminho })
      a.selecao = a.selecao.filter(function(c) { return vivos.indexOf(c) >= 0 })
      if (a.renomearPendente && vivos.indexOf(a.renomearPendente) >= 0) {
        var alvo = a.renomearPendente
        a.renomearPendente = ""
        a.selecao = [alvo]
        Qt.callLater(function() { a.renomear(alvo) })
      }
    })
  }
  onPastaChanged: { selecao = []; listar() }
  onOcultosChanged: listar()
  onOrdenarChanged: itens = ordenados(itens)

  function ordenados(v) {
    var o = ordenar
    return v.slice().sort(function(x, y) {
      if (x.pasta !== y.pasta) return x.pasta ? -1 : 1
      var r = 0
      if (o === "tamanho") r = x.tamanho - y.tamanho
      else if (o === "tipo") r = String(x.mime).localeCompare(String(y.mime))
      else if (o === "data") r = y.mtime - x.mtime
      return r !== 0 ? r : String(x.rotulo).localeCompare(String(y.rotulo), "pt-BR", { sensitivity: "base", numeric: true })
    })
  }

  function atualizar() { versao++; listar() }

  // Desktop folder watcher (a directory FileView only reports changes).
  FileView {
    path: a.pasta
    watchChanges: a.pasta !== ""
    printErrors: false
    onFileChanged: relistar.restart()
  }
  Timer { id: relistar; interval: 250; onTriggered: a.listar() }
  // Backstop for changes the watcher can miss (e.g. a renamed mount).
  Timer { interval: 15000; running: true; repeat: true; onTriggered: a.listar() }

  // ── positions ────────────────────────────────────────────────────────────
  function posicoes() { return Preferencias.obter("area.posicoes", {}) || {} }
  function guardarPosicao(nome, pos) {
    var p = JSON.parse(JSON.stringify(posicoes()))
    p[nome] = pos
    Preferencias.definir("area.posicoes", p)
  }

  // ── actions ──────────────────────────────────────────────────────────────
  function run(argv, msgOk, depois) {
    Sistema.rodar([Sistema.bin + "/area"].concat(argv), function(out, code) {
      var r = null
      try { r = JSON.parse(out) } catch (e) {}
      if (code !== 0 || !r || r.erro) Sistema.notificar(r && r.erro ? r.erro : I18n.t("Não foi possível concluir"), "󰀦")
      else if (msgOk) Sistema.notificar(msgOk, "󰆏")
      if (depois) depois(r, code)
      a.listar()
    })
  }
  function abrirItem(caminho) { run(["abrir", caminho]) }
  function copiar(cortar) { if (selecao.length) run([cortar ? "recortar" : "copiar"].concat(selecao)) }
  function colar(atalho) { run([atalho ? "colar-atalho" : "colar", pasta]) }
  function excluir() {
    if (!selecao.length) return
    var n = selecao.length
    run(["lixeira"].concat(selecao), n === 1 ? I18n.t("Movido para a lixeira") : n + I18n.t(" itens movidos para a lixeira"))
    selecao = []
  }
  function novaPasta() { run(["nova-pasta", pasta], "", function(r) { if (r && r.caminho) a.renomearPendente = r.caminho }) }
  function novoTexto() { run(["novo-texto", pasta], "", function(r) { if (r && r.caminho) a.renomearPendente = r.caminho }) }
  function soltar(uris) { run(["soltar", pasta].concat(uris), "") }
  function definirFundo(caminho) { Sistema.rodar(["simba-theme-bg-set", caminho]) }

  function telaPorNome(n) {
    return Quickshell.screens.filter(function(q) { return q.name === n })[0] || null
  }
  function abrirMenuEm(tela, x, y) {
    if (x < 0 || y < 0 || !telaPorNome(tela)) {
      // From IPC / the settings app: open where the cursor is.
      Sistema.json(["hyprctl", "-j", "cursorpos"], function(c) {
        var s = Quickshell.screens.filter(function(q) { return c && c.x >= q.x && c.x < q.x + q.width && c.y >= q.y && c.y < q.y + q.height })[0] || Quickshell.screens[0]
        a.selecao = []
        menu.abrir(s.name, c ? c.x - s.x : s.width / 2, c ? c.y - s.y : s.height / 2, "area")
      })
      return
    }
    selecao = []
    menu.abrir(tela, x, y, "area")
  }
  function abrirMenuItem(tela, x, y) { menu.abrir(tela, x, y, "icone") }
  // IPC/tests: open the menu of an icon by file name, next to the icon.
  function abrirMenuIcone(tela, nome) {
    var it = itens.filter(function(i) { return i.nome === nome })[0]
    if (!it) return
    selecao = [it.caminho]
    var g = geometria[it.caminho]
    var s = telaPorNome(g ? g.tela : tela) || Quickshell.screens[0]
    menu.abrir(s.name, g ? g.x + g.w * 0.7 : s.width / 2, g ? g.y + g.h * 0.5 : s.height / 2, "icone")
  }
  function fecharMenu() { menu.fechar() }
  function acao(id) { menu.executar(id) }
  function selecionarNome(nome) { selecao = itens.filter(function(i) { return i.nome === nome }).map(function(i) { return i.caminho }) }
  function renomear(caminho) {
    var it = itens.filter(function(i) { return i.caminho === caminho })[0]
    if (it) renomeador.abrir(it)
  }
  function propriedades(caminho) { propriedadesJanela.abrir(caminho) }
  function cancelarRenomear() { renomeador.concluir(false, "") }
  function concluirRenomear(t) { renomeador.concluir(true, t) }
  function fecharPropriedades() { propriedadesJanela.aberto = false }

  // Icon geometry (screen-local), filled by the icon delegates.
  property var geometria: ({})
  function registrar(caminho, tela, x, y, w, h) {
    var g = Object.assign({}, geometria)
    g[caminho] = { tela: tela, x: x, y: y, w: w, h: h }
    geometria = g
  }

  Component.onCompleted: listar()

  // ── surfaces ─────────────────────────────────────────────────────────────
  Variants {
    model: Quickshell.screens
    delegate: Superficie {
      required property var modelData
      screen: modelData
      area: a
      mostrarIcones: a.mostrar && (a.telaIcones === "*" || a.telaIcones === modelData.name)
    }
  }

  MenuContexto { id: menu; area: a }
  Renomear { id: renomeador; area: a }
  Propriedades { id: propriedadesJanela; area: a }

  // A night-light schedule saved in Configurações › Tela keeps working after
  // a reboot: this daemon is autostarted, hyprsunset is not.
  Timer { interval: 4000; running: true; onTriggered: Sistema.solto([Sistema.bin + "/luz-agenda", "garantir"]) }
}
