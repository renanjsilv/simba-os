import "idiomas"
import QtQuick 6.11
import QtQuick.Effects
import QtQuick.Layouts
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Widgets
import qs.Commons
import "tarefas-icones.js" as TI

// Barra de tarefas: apps fixados + apps abertos, estilo Windows.
//   esquerdo  = abre o app; se já aberto, foca (restaura se minimizado);
//               no app em foco alterna entre as janelas ou minimiza
//   meio      = nova janela
//   direito   = menu (janelas, nova janela, fixar/desafixar, fechar)
//   mouse parado num app aberto = prévia ao vivo das janelas (como no Windows 11)
// Opções na entrada { "id": "tarefas", "type": "qml", ... } do shell.json,
// editadas pelo /usr/bin/barra-tarefas e por Configurações › Barra.
Item {
  id: root

  property var bar
  property string moduleName
  property var settings: ({})

  function opcao(k, padrao) { var v = settings ? settings[k] : undefined; return v === undefined || v === null ? padrao : v }
  // Enquanto o shell.json não recarrega depois de arrastar, vale a ordem local.
  property var fixadosLocal: null
  onSettingsChanged: fixadosLocal = null
  readonly property var fixados: fixadosLocal || opcao("fixados", [])
  // Ordem dos apps abertos não fixados (só nesta sessão).
  property var ordemAbertos: []
  readonly property bool mostrarAbertos: opcao("abertos", true)
  readonly property bool rotulos: opcao("rotulos", false) && !vertical
  // O ícone nunca passa da altura da barra menos uma folga (~1/3), para não
  // encostar nas bordas; ao aumentar a barra (alça) a folga cresce junto.
  // "tamanho" = ícone na barra Normal (26 px); cresce/encolhe junto com a barra,
  // sempre na mesma proporção (sem regravar o shell.json a cada passo da alça)
  readonly property int tamIcone: Math.max(14, Math.min(barSize - 4, Math.round(barSize * Number(opcao("tamanho", 18)) / 26)))
  readonly property bool soEstaTela: opcao("soEstaTela", false)
  readonly property bool cliqueMinimiza: opcao("cliqueMinimiza", true)
  // "tema" = glifos monocromáticos na cor do tema · "coloridos" = tema de ícones do sistema
  readonly property bool monocromatico: opcao("estiloIcones", "tema") !== "coloridos"

  readonly property bool vertical: bar ? bar.vertical : false
  readonly property int barSize: bar ? bar.barSize : 26
  readonly property color fg: bar ? bar.barForeground : Color.foreground
  readonly property string especial: "special:minimizadas"
  readonly property string minhaTela: QsWindow.window && QsWindow.window.screen ? QsWindow.window.screen.name : ""

  implicitWidth: vertical ? barSize : grade.implicitWidth + 6
  implicitHeight: vertical ? grade.implicitHeight + 6 : barSize

  // ── apps ↔ janelas ────────────────────────────────────────────────────────
  // Índice classe-de-janela → desktop entry: id, StartupWMClass, binário do
  // Exec e, para web apps do Simba (Brave --app), o host da URL.
  property var indice: ({})
  function reindexar() {
    // Duas camadas: o id do atalho e o StartupWMClass mandam; o binário do Exec só vale
    // se nenhum atalho tiver aquele nome. Antes valia o primeiro lido, e os atalhos de jogo
    // da Steam (Exec=steam steam://rungameid/…) às vezes ganhavam a chave "steam": a
    // janela da Steam aparecia com o ícone de um jogo, trocando quando a lista era relida.
    var forte = {}, fraco = {}, classeDona = {}
    var apps = DesktopEntries.applications.values
    for (var i = 0; i < apps.length; i++) {
      var d = apps[i]
      if (!d || d.noDisplay) continue
      // StartupWMClass primeiro: um atalho que reivindica a classe (a Loja do Simba reivindica a
      // janela do Bazaar) ganha do atalho que só tem o mesmo id
      if (d.startupClass && classeDona[String(d.startupClass).toLowerCase()] === undefined)
        classeDona[String(d.startupClass).toLowerCase()] = d.id
      var chaves = [d.id, d.startupClass]
      var ex = String(d.execString || "")
      var m = ex.match(/simba-launch-webapp\s+["']?https?:\/\/(?:www\.)?([^\/\s"']+)/)
      if (m) chaves.push("web:" + m[1].toLowerCase())
      for (var k = 0; k < chaves.length; k++) {
        var c = String(chaves[k] || "").toLowerCase()
        if (c && forte[c] === undefined) forte[c] = d.id
      }
      if (!m) {
        var partes = ex.replace(/^(env\s+(\S+=\S+\s+)*)/, "").split(/\s+/)
        var bin = (partes[0] || "").split("/").pop().toLowerCase()
        // atalho que só abre um link do app (steam://, heroic://…) não é o app
        var link = /^[a-z][a-z0-9+.-]*:\/\//i.test(partes[1] || "")
        if (bin && !link && ["env", "xdg-terminal-exec", "uwsm-app", "gtk-launch", "flatpak"].indexOf(bin) < 0 && fraco[bin] === undefined)
          fraco[bin] = d.id
      }
    }
    for (var b in fraco) if (forte[b] === undefined) forte[b] = fraco[b]
    for (var cd in classeDona) forte[cd] = classeDona[cd]
    indice = forte
  }
  Connections { target: DesktopEntries; function onApplicationsChanged() { reindexarAdiado.restart(); if (!varrerIcones.running) varrerIcones.running = true } }
  Timer { id: reindexarAdiado; interval: 400; onTriggered: root.reindexar() }
  // Tema de ícones trocado (Configurações › Personalização › Ícones): varre de novo.
  FileView {
    path: Quickshell.env("HOME") + "/.local/state/configuracoes/icones-versao"
    watchChanges: true
    printErrors: false
    onFileChanged: { reload(); if (!varrerIcones.running) varrerIcones.running = true }
  }
  Component.onCompleted: {
    reindexar(); Hyprland.refreshToplevels()
    // A barra cobre cada módulo com um MouseArea que arrasta o módulo inteiro
    // e só repassa cliques. Subir o Loader acima dele deixa os botões receberem
    // o press para reordenar ícones; o vão nas bordas ainda move o módulo.
    if (parent) parent.z = 60
  }

  function idDaClasse(classe) {
    var c = String(classe || "").toLowerCase()
    if (!c) return ""
    if (indice[c] !== undefined) return indice[c]
    var w = c.match(/^(?:brave|chrome|chromium)-(?:www\.)?([^_]+?)(?:__.*)?-default$/)
    if (w && indice["web:" + w[1]] !== undefined) return indice["web:" + w[1]]
    var curto = c.split(".").pop()
    if (indice[curto] !== undefined) return indice[curto]
    var d = DesktopEntries.heuristicLookup(classe)
    return d ? d.id : ""
  }

  function classeDe(t) {
    var o = t.lastIpcObject || {}
    return String(o["class"] || o.initialClass || (t.wayland ? t.wayland.appId : "") || "")
  }
  function enderecoDe(t) { var a = String(t.address || ""); return a.indexOf("0x") === 0 ? a : "0x" + a }

  // Ordem de foco: o mais recente primeiro.
  property var focoRecente: ({})
  property int relogio: 0
  Connections {
    target: Hyprland
    function onActiveToplevelChanged() {
      var t = Hyprland.activeToplevel
      if (!t) return
      var f = Object.assign({}, root.focoRecente)
      f[root.enderecoDe(t)] = ++root.relogio
      root.focoRecente = f
    }
    function onRawEvent(ev) {
      if (["openwindow", "closewindow", "movewindow", "movewindowv2", "windowtitle", "windowtitlev2"].indexOf(ev.name) >= 0) atualizar.restart()
    }
  }
  Timer { id: atualizar; interval: 80; onTriggered: Hyprland.refreshToplevels() }

  readonly property var grupos: {
    var _f = focoRecente, _i = indice
    var lista = Hyprland.toplevels.values
    var porId = {}, ordem = []
    for (var i = 0; i < lista.length; i++) {
      var t = lista[i]
      var classe = classeDe(t)
      if (!classe) continue
      var ws = t.workspace ? String(t.workspace.name || "") : ""
      var minimizada = ws === especial
      if (ws.indexOf("special:") === 0 && !minimizada) continue
      if (soEstaTela && minhaTela && t.monitor && t.monitor.name !== minhaTela && !minimizada) continue
      var id = idDaClasse(classe) || ("classe:" + classe)
      if (!porId[id]) { porId[id] = []; ordem.push(id) }
      porId[id].push({ t: t, endereco: enderecoDe(t), titulo: String(t.title || classe), minimizada: minimizada, classe: classe })
    }
    var _o = ordemAbertos
    ordem = ordem.map(function(id, n) { return { id: id, n: n, p: _o.indexOf(id) } })
                 .sort(function(a, b) { return (a.p < 0 ? 1e6 + a.n : a.p) - (b.p < 0 ? 1e6 + b.n : b.p) })
                 .map(function(x) { return x.id })
    for (var k in porId) porId[k].sort(function(a, b) { return (_f[b.endereco] || 0) - (_f[a.endereco] || 0) })
    var itens = []
    for (var p = 0; p < fixados.length; p++) itens.push({ id: fixados[p], fixado: true, janelas: porId[fixados[p]] || [] })
    if (mostrarAbertos)
      for (var o = 0; o < ordem.length; o++)
        if (fixados.indexOf(ordem[o]) < 0) itens.push({ id: ordem[o], fixado: false, janelas: porId[ordem[o]] })
    return itens
  }

  // lê a lista para reavaliar quando o Quickshell relê os atalhos (troca o objeto dos duplicados)
  function entrada(id) { var _ = DesktopEntries.applications.values; return id.indexOf("classe:") === 0 ? null : DesktopEntries.byId(id) }
  function nomeDe(item) {
    var d = entrada(item.id)
    if (d && d.name) return d.name
    return item.janelas.length ? item.janelas[0].classe : item.id
  }
  function glifoDe(item) {
    var d = entrada(item.id)
    var classe = item.janelas.length ? item.janelas[0].classe : ""
    return TI.glifo(item.id, classe, d ? d.name : "", d ? d.categories : [])
  }
  function mascaraDe(item) {
    var d = entrada(item.id)
    return TI.mascara(item.id, item.janelas.length ? item.janelas[0].classe : "", d ? d.name : "")
  }
  function iconeDe(item) {
    var d = entrada(item.id)
    var n = d && d.icon ? String(d.icon) : (item.janelas.length ? item.janelas[0].classe : "")
    // Janelas de terminal do Simba (agente, TUIs) usam a classe org.simba.*.
    // O agente de IA tem ícone próprio (~/.local/share/icons/.../simba-agente.svg),
    // para não se confundir com o terminal.
    if (!d && n === "org.simba.agent" && icones["simba-agente"]) n = "simba-agente"
    if (!d && /^org\.simba\./.test(n) && !icones[n]) n = "foot"
    if (n.charAt(0) === "/") return "file://" + n
    var f = icones[n] || icones[n.toLowerCase()]
    if (f) return "file://" + f
    return Quickshell.iconPath(n, true) || Quickshell.iconPath(n.toLowerCase(), true) || (icones["application-x-executable"] ? "file://" + icones["application-x-executable"] : "")
  }

  // O tema de ícones do Qt não enxerga o hicolor de vários apps: índice
  // nome → arquivo (SVG antes de PNG, tamanhos maiores antes), como o AppLibrary.
  property var icones: ({})
  property var iconesNovos: ({})
  Process {
    id: varrerIcones
    running: true
    // Pastas do tema de ícones ativo e dos que ele herda (index.theme), na ordem de
    // busca — a mesma do menu Iniciar (configuracoes/bin/icones cadeia).
    command: ["bash", "-c", 'for b in $(/etc/xdg/quickshell/configuracoes/bin/icones cadeia || printf "/usr/share/icons/hicolor\\n") "$HOME/.local/share/icons"; do [[ -d $b ]] || continue; for ext in svg png; do find -L "$b" \\( -path "*/apps/*" -o -path "*/mimetypes/*" \\) -not -path "*symbolic*" -name "*.$ext" 2>/dev/null | sort -r -V; done; done; find /usr/share/pixmaps -maxdepth 1 \\( -name "*.svg" -o -name "*.png" \\) 2>/dev/null']
    stdout: SplitParser {
      onRead: function(l) {
        var nome = l.slice(l.lastIndexOf("/") + 1).replace(/\.(svg|png)$/, "")
        if (nome && root.iconesNovos[nome] === undefined) root.iconesNovos[nome] = l
      }
    }
    onStarted: root.iconesNovos = {}
    onExited: root.icones = root.iconesNovos
  }

  // ── ações ─────────────────────────────────────────────────────────────────
  function despachar(lua) { Hyprland.dispatch(lua) }
  function abrirNovo(item) {
    if (item.id.indexOf("classe:") === 0) return
    Quickshell.execDetached(["uwsm-app", "--", "gtk-launch", item.id + ".desktop"])
  }
  // foco.janela (hypr/foco.lua) foca sem levar o cursor ao centro da janela/outro monitor.
  function focoLua(endereco, ws) { return 'foco.janela("' + endereco + '"' + (ws ? ', "' + ws + '"' : '') + ')' }
  function focar(j) {
    if (j.minimizada) {
      // Volta na área de trabalho do monitor desta barra (não necessariamente o focado).
      var mon = root.QsWindow.window && root.QsWindow.window.screen ? Hyprland.monitorFor(root.QsWindow.window.screen) : null
      if (!mon || !mon.activeWorkspace) mon = Hyprland.focusedMonitor
      var ws = mon && mon.activeWorkspace ? mon.activeWorkspace.name : "1"
      despachar(focoLua(j.endereco, ws))
    } else {
      despachar(focoLua(j.endereco))
    }
    atualizar.restart()
  }
  function minimizar(j) {
    despachar('hl.dsp.window.move({ workspace = "' + especial + '", follow = false, window = "address:' + j.endereco + '" })')
    atualizar.restart()
  }
  function fechar(j) { despachar('hl.dsp.window.close({ window = "address:' + j.endereco + '" })') }
  function ativo(item) {
    var a = Hyprland.activeToplevel
    if (!a) return null
    var e = enderecoDe(a)
    for (var i = 0; i < item.janelas.length; i++) if (item.janelas[i].endereco === e && !item.janelas[i].minimizada) return item.janelas[i]
    return null
  }
  // Clique no ícone, como no Windows 11:
  //  - sem janela: abre o app;
  //  - uma janela: traz para a frente; se já é a janela ativa, minimiza;
  //  - várias janelas: abre (ou fecha) as miniaturas para escolher qual — não
  //    alterna sozinho entre elas.
  function clique(item, botao) {
    var js = item.janelas
    if (!js.length) { previa.fechar(true); abrirNovo(item); return }
    if (js.length > 1) { previa.alternar(botao); return }
    previa.fechar(true)
    var a = ativo(item)
    if (a && cliqueMinimiza) minimizar(a)
    else if (!a) focar(js[0])
  }
  function helper(args) { Quickshell.execDetached(["barra-tarefas"].concat(args)) }

  // ── arrastar para reordenar ───────────────────────────────────────────────
  // Fixados ficam primeiro (ordem gravada no shell.json); soltar um app
  // aberto no meio dos fixados fixa ele ali. Abertos se reordenam na sessão.
  property int arrastando: -1
  property int alvoArrasto: -1
  property real deslocArrasto: 0
  readonly property int nFixados: { var n = 0; for (var i = 0; i < grupos.length; i++) if (grupos[i].fixado) n++; return n }

  function tamDe(i) { var it = repetidor.itemAt(i); return it ? (vertical ? it.height + grade.rowSpacing : it.width + grade.columnSpacing) : 0 }
  function centroDe(i) { var it = repetidor.itemAt(i); return it ? (vertical ? it.y + it.height / 2 : it.x + it.width / 2) : 0 }
  function calcularAlvo() {
    var c = centroDe(arrastando) + deslocArrasto, alvo = 0
    for (var i = 0; i < grupos.length; i++) if (i !== arrastando && centroDe(i) < c) alvo++
    // Fixado não sai da área dos fixados.
    if (grupos[arrastando].fixado) alvo = Math.min(alvo, nFixados - 1)
    // Sem desktop entry não dá para fixar.
    else if (grupos[arrastando].id.indexOf("classe:") === 0) alvo = Math.max(alvo, nFixados)
    alvoArrasto = alvo
  }
  function deslocDe(i) {
    if (arrastando < 0) return 0
    if (i === arrastando) return deslocArrasto
    var t = tamDe(arrastando)
    if (arrastando < alvoArrasto && i > arrastando && i <= alvoArrasto) return -t
    if (alvoArrasto < arrastando && i >= alvoArrasto && i < arrastando) return t
    return 0
  }
  function soltar() {
    var de = arrastando, para = alvoArrasto
    arrastando = -1
    deslocArrasto = 0
    if (de < 0 || para < 0 || de === para) return
    var item = grupos[de]
    var fix = fixados.slice()
    if (item.fixado || para < nFixados) {
      var j = fix.indexOf(item.id)
      if (j >= 0) fix.splice(j, 1)
      fix.splice(para, 0, item.id)
      fixadosLocal = fix
      helper(["ordem"].concat(fix))
    } else {
      var ab = []
      for (var i = nFixados; i < grupos.length; i++) if (grupos[i].id !== item.id) ab.push(grupos[i].id)
      ab.splice(para - nFixados, 0, item.id)
      // Guarda também os que estão fechados agora, para voltarem no mesmo lugar.
      ordemAbertos = ab.concat(ordemAbertos.filter(function(x) { return ab.indexOf(x) < 0 }))
    }
  }

  // ── visual ────────────────────────────────────────────────────────────────
  GridLayout {
    id: grade
    anchors.centerIn: parent
    columns: root.vertical ? 1 : Math.max(1, root.grupos.length)
    rowSpacing: 2
    columnSpacing: 2

    Repeater {
      id: repetidor
      model: root.grupos
      delegate: Item {
        id: botao
        required property var modelData
        required property int index
        readonly property bool arrastado: root.arrastando === index
        z: arrastado ? 10 : 0
        transform: Translate {
          x: root.vertical ? 0 : root.deslocDe(botao.index)
          y: root.vertical ? root.deslocDe(botao.index) : 0
          Behavior on x { enabled: !botao.arrastado; NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
          Behavior on y { enabled: !botao.arrastado; NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
        }
        readonly property bool aberto: modelData.janelas.length > 0
        readonly property bool emFoco: root.ativo(modelData) !== null
        readonly property string nome: root.nomeDe(modelData)
        Layout.preferredWidth: root.vertical ? root.barSize : (root.rotulos ? Math.min(170, conteudo.implicitWidth + 14) : root.tamIcone + 16)
        Layout.preferredHeight: root.vertical ? root.tamIcone + 12 : root.barSize

        Rectangle {
          anchors.fill: parent
          anchors.leftMargin: 2; anchors.rightMargin: 2
          anchors.topMargin: root.vertical ? 2 : 3; anchors.bottomMargin: root.vertical ? 2 : 3
          radius: Math.min(7, height / 2)
          color: root.fg
          opacity: botao.emFoco ? 0.12 : (area.containsMouse ? 0.08 : 0)
          Behavior on opacity { NumberAnimation { duration: 120 } }
        }

        Row {
          id: conteudo
          anchors.centerIn: parent
          spacing: 6
          Item {
            id: icone
            visible: root.monocromatico
            anchors.verticalCenter: parent.verticalCenter
            width: root.tamIcone + 2
            height: root.tamIcone + 2
            readonly property string mascara: root.mascaraDe(botao.modelData)
            readonly property color cor: botao.emFoco ? Color.accent : root.fg
            opacity: botao.emFoco || area.containsMouse ? 1 : (botao.aberto ? 0.88 : 0.62)
            scale: area.pressed ? 0.86 : 1
            Behavior on scale { NumberAnimation { duration: 90 } }
            Behavior on opacity { NumberAnimation { duration: 140 } }

            // Os glifos da Nerd Font não ficam centrados na própria caixa
            // (passam do avanço e da linha): centra pelo desenho real.
            Text {
              id: glifo
              visible: !icone.mascara
              anchors.centerIn: parent
              anchors.horizontalCenterOffset: Math.round(width / 2 - (medida.tightBoundingRect.x + medida.tightBoundingRect.width / 2))
              anchors.verticalCenterOffset: Math.round(height / 2 - (metricas.ascent + medida.tightBoundingRect.y + medida.tightBoundingRect.height / 2))
              text: root.glifoDe(botao.modelData)
              color: icone.cor
              font.family: root.bar && root.bar.fontFamily ? root.bar.fontFamily : "JetBrainsMono Nerd Font"
              font.pixelSize: root.tamIcone
              Behavior on color { ColorAnimation { duration: 160 } }
              TextMetrics { id: medida; font: glifo.font; text: glifo.text }
              FontMetrics { id: metricas; font: glifo.font }
            }

            // Apps sem glifo (Brave): máscara branca pintada com a cor do tema.
            Image {
              id: mascaraImg
              visible: false
              anchors.centerIn: parent
              height: root.tamIcone
              width: root.tamIcone
              fillMode: Image.PreserveAspectFit
              source: icone.mascara ? Qt.resolvedUrl(icone.mascara) : ""
              sourceSize.height: root.tamIcone * 2
              smooth: true
              mipmap: true
            }
            MultiEffect {
              visible: !!icone.mascara
              anchors.fill: mascaraImg
              source: mascaraImg
              colorization: 1.0
              colorizationColor: icone.cor
              Behavior on colorizationColor { ColorAnimation { duration: 160 } }
            }
          }
          IconImage {
            visible: !root.monocromatico
            anchors.verticalCenter: parent.verticalCenter
            implicitSize: root.tamIcone
            source: root.monocromatico ? "" : root.iconeDe(botao.modelData)
            asynchronous: true
            scale: area.pressed ? 0.86 : 1
            Behavior on scale { NumberAnimation { duration: 90 } }
          }
          Text {
            visible: root.rotulos
            anchors.verticalCenter: parent.verticalCenter
            width: Math.min(implicitWidth, 110)
            elide: Text.ElideRight
            text: botao.modelData.janelas.length ? botao.modelData.janelas[0].titulo : botao.nome
            color: root.fg
            opacity: botao.emFoco ? 1 : 0.8
            font.family: root.bar ? root.bar.fontFamily : "monospace"
            font.pixelSize: 12
          }
        }

        // Indicador de janela aberta: traço na borda voltada para a área de trabalho.
        Rectangle {
          visible: botao.aberto
          readonly property bool vert: root.vertical
          readonly property bool lado: root.bar && (root.bar.position === "bottom" || root.bar.position === "right")
          width: vert ? 2 : (botao.emFoco ? 14 : 6)
          height: vert ? (botao.emFoco ? 14 : 6) : 2
          radius: 1
          color: botao.emFoco ? Color.accent : root.fg
          opacity: botao.emFoco ? 1 : 0.55
          x: vert ? (lado ? 2 : parent.width - 4) : (parent.width - width) / 2
          y: vert ? (parent.height - height) / 2 : (lado ? 2 : parent.height - 4)
          Behavior on width { NumberAnimation { duration: 150 } }
          Behavior on height { NumberAnimation { duration: 150 } }
        }

        MouseArea {
          id: area
          anchors.fill: parent
          hoverEnabled: true
          acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
          cursorShape: botao.arrastado ? Qt.ClosedHandCursor : Qt.PointingHandCursor
          preventStealing: true
          property real inicio: 0
          property bool arrastou: false
          function pos(m) { var p = mapToItem(grade, m.x, m.y); return root.vertical ? p.y : p.x }
          onPressed: function(m) { arrastou = false; inicio = pos(m) }
          onPositionChanged: function(m) {
            if (!(pressedButtons & Qt.LeftButton) || root.grupos.length < 2) return
            var d = pos(m) - inicio
            if (!arrastou && Math.abs(d) < 8) return
            if (!arrastou) {
              arrastou = true
              previa.fechar(true)
              if (root.bar) root.bar.hideTooltip(botao)
              root.alvoArrasto = botao.index
              root.arrastando = botao.index
            }
            // pos() é a posição do cursor na grade, não muda com o deslocamento do botão
            root.deslocArrasto += d
            inicio += d
            root.calcularAlvo()
          }
          onReleased: if (arrastou) root.soltar()
          onCanceled: if (arrastou) root.soltar()
          onClicked: function(m) {
            if (arrastou) return
            if (root.bar) root.bar.hideTooltip(botao)
            if (m.button === Qt.LeftButton) { root.clique(botao.modelData, botao); return }
            previa.fechar(true)
            if (m.button === Qt.MiddleButton) root.abrirNovo(botao.modelData)
            else menu.abrir(botao)
          }
          // App aberto: prévia das janelas; só fixado: dica com o nome.
          onEntered: {
            if (menu.visible || root.arrastando >= 0) return
            if (botao.aberto) previa.pedir(botao)
            else if (root.bar) root.bar.showTooltip(botao, botao.nome)
          }
          onExited: { if (root.bar) root.bar.hideTooltip(botao); previa.soltar(botao) }
        }
      }
    }
  }

  // ── botão direito numa parte vazia da barra ──────────────────────────────
  // Camada no fundo da janela da barra (abaixo de todos os módulos): só recebe
  // o clique direito que nenhum módulo tratou, como no Windows.
  Item {
    id: fundoBarra
    parent: root.QsWindow.window ? root.QsWindow.window.contentItem : null
    anchors.fill: parent
    z: -100
    Item { id: pontoMenu; width: 1; height: 1 }
    MouseArea {
      anchors.fill: parent
      acceptedButtons: Qt.RightButton
      onClicked: function(m) {
        pontoMenu.x = root.vertical ? (root.bar && root.bar.position === "right" ? 0 : fundoBarra.width) : m.x
        pontoMenu.y = root.vertical ? m.y : (root.bar && root.bar.position === "bottom" ? 0 : fundoBarra.height)
        menu.abrirBarra(pontoMenu)
      }
    }
  }

  // ── menu do botão direito ────────────────────────────────────────────────
  PopupWindow {
    id: menu
    property var alvo: null
    // modoBarra: aberto pelo botão direito numa parte vazia da barra (alvo = pontoMenu)
    property bool modoBarra: false
    property var item: alvo && !modoBarra ? alvo.modelData : null
    property var opcoes: []
    color: "transparent"
    visible: false
    implicitWidth: 330
    implicitHeight: caixa.implicitHeight + 12

    anchor.item: alvo
    anchor.rect.x: alvo ? (root.vertical ? (root.bar && root.bar.position === "right" ? -implicitWidth - 4 : alvo.width + 4) : alvo.width / 2 - implicitWidth / 2) : 0
    anchor.rect.y: alvo ? (root.vertical ? 0 : (root.bar && root.bar.position === "bottom" ? -implicitHeight - 4 : alvo.height + 4)) : 0

    function abrirBarra(p) {
      previa.fechar(true)
      modoBarra = true
      alvo = null  // força reancorar no novo ponto
      alvo = p
      opcoes = [
        { tipo: "gerenciador", rotulo: I18n.t("Gerenciador de tarefas"), glifo: "󰍛" },
        { tipo: "sep" },
        { tipo: "area", rotulo: I18n.t("Mostrar a área de trabalho"), glifo: "󰍹" },
        { tipo: "config", rotulo: I18n.t("Configurações da barra de tarefas"), glifo: "󰒓" }
      ]
      visible = true
    }
    function abrir(b) {
      previa.fechar(true)
      modoBarra = false
      alvo = b
      var it = b.modelData, o = []
      var d = root.entrada(it.id)
      if (it.janelas.length > 1)
        for (var i = 0; i < it.janelas.length; i++) o.push({ tipo: "janela", j: it.janelas[i], rotulo: it.janelas[i].titulo, glifo: it.janelas[i].minimizada ? "󰖰" : "󰖯" })
      if (it.janelas.length > 1) o.push({ tipo: "sep" })
      if (d) o.push({ tipo: "novo", rotulo: it.janelas.length ? I18n.t("Nova janela") : I18n.t("Abrir"), glifo: "󰐕" })
      if (d) o.push({ tipo: "fixar", rotulo: it.fixado ? I18n.t("Desafixar da barra de tarefas") : I18n.t("Fixar na barra de tarefas"), glifo: it.fixado ? "󰐄" : "󰐃" })
      if (it.janelas.length) o.push({ tipo: "fechar", rotulo: it.janelas.length > 1 ? I18n.t("Fechar todas as janelas") : I18n.t("Fechar janela"), glifo: "󰅖" })
      o.push({ tipo: "sep" })
      o.push({ tipo: "config", rotulo: I18n.t("Configurações da barra de tarefas"), glifo: "󰒓" })
      opcoes = o
      visible = true
    }
    function escolher(op) {
      var it = item
      visible = false
      if (op.tipo === "gerenciador") { Quickshell.execDetached(["gerenciador-tarefas"]); return }
      if (op.tipo === "area") { Quickshell.execDetached(["qs", "-c", "botoes-janela", "ipc", "call", "botoes", "mostrarArea"]); return }
      if (op.tipo === "config") { Quickshell.execDetached(["configuracoes", "barra"]); return }
      if (!it) return
      if (op.tipo === "janela") root.focar(op.j)
      else if (op.tipo === "novo") root.abrirNovo(it)
      else if (op.tipo === "fixar") root.helper([it.fixado ? "desafixar" : "fixar", it.id])
      else if (op.tipo === "fechar") for (var i = 0; i < it.janelas.length; i++) root.fechar(it.janelas[i])
      else if (op.tipo === "config") Quickshell.execDetached(["configuracoes", "barra"])
    }

    // O grab só pega depois que o popup está mapeado; ativado junto ele falha calado
    // e o menu não fechava ao clicar fora.
    property bool grabPronto: false
    onVisibleChanged: { grabPronto = false; if (visible) ativarGrab.restart() }
    Timer { id: ativarGrab; interval: 60; onTriggered: menu.grabPronto = menu.visible }
    HyprlandFocusGrab {
      id: grabMenu
      active: menu.grabPronto
      windows: [menu]
      onCleared: menu.visible = false
    }

    Rectangle {
      anchors.fill: parent
      anchors.margins: 4
      radius: 10
      color: Color.popups.background
      border.width: 1
      border.color: Color.popups.border

      Column {
        id: caixa
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 6
        spacing: 1

        Text {
          width: parent.width
          leftPadding: 8; topPadding: 4; bottomPadding: 6
          text: menu.modoBarra ? I18n.t("Barra de tarefas") : (menu.alvo ? menu.alvo.nome : "")
          color: Color.popups.text
          opacity: 0.6
          font.family: root.bar ? root.bar.fontFamily : "monospace"
          font.pixelSize: 11
          elide: Text.ElideRight
        }
        Repeater {
          model: menu.opcoes
          delegate: Item {
            id: linha
            required property var modelData
            width: caixa.width
            height: modelData.tipo === "sep" ? 9 : 30
            Rectangle {
              visible: linha.modelData.tipo === "sep"
              anchors.centerIn: parent
              width: parent.width - 12; height: 1
              color: Color.popups.text; opacity: 0.12
            }
            Rectangle {
              visible: linha.modelData.tipo !== "sep"
              anchors.fill: parent
              radius: 6
              color: Color.popups.text
              opacity: ml.containsMouse ? 0.10 : 0
            }
            Row {
              visible: linha.modelData.tipo !== "sep"
              anchors.verticalCenter: parent.verticalCenter
              x: 8
              spacing: 10
              Text { text: linha.modelData.glifo || ""; color: Color.popups.text; font.family: root.bar ? root.bar.fontFamily : "monospace"; font.pixelSize: 14; anchors.verticalCenter: parent.verticalCenter }
              Text {
                text: linha.modelData.rotulo || ""
                width: caixa.width - 46
                elide: Text.ElideRight
                color: Color.popups.text
                font.family: root.bar ? root.bar.fontFamily : "monospace"
                font.pixelSize: 12
                anchors.verticalCenter: parent.verticalCenter
              }
            }
            MouseArea {
              id: ml
              anchors.fill: parent
              enabled: linha.modelData.tipo !== "sep"
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: menu.escolher(linha.modelData)
            }
          }
        }
      }
    }
  }

  // ── prévia das janelas (mouse parado no ícone, como no Windows 11) ──────────
  PopupWindow {
    id: previa
    property var alvo: null
    property var pendente: null
    readonly property var janelas: alvo ? alvo.modelData.janelas : []
    // Lista estável de endereços: os grupos são recriados a cada troca de título
    // (ex.: indicador animado no título do terminal), e recriar os cartões reinicia a
    // captura — era o que fazia a prévia piscar.
    property var enderecos: []
    function dados(e) { for (var i = 0; i < janelas.length; i++) if (janelas[i].endereco === e) return janelas[i]; return null }
    readonly property bool sobre: dentroPrevia.hovered
    readonly property int largCartao: 220
    color: "transparent"
    visible: false
    implicitWidth: root.vertical ? largCartao + 16 : linhaPrevia.implicitWidth + 16
    implicitHeight: root.vertical ? linhaPrevia.implicitHeight + 16 : 172

    anchor.item: alvo
    anchor.rect.x: alvo ? (root.vertical ? (root.bar && root.bar.position === "right" ? -implicitWidth - 4 : alvo.width + 4) : alvo.width / 2 - implicitWidth / 2) : 0
    anchor.rect.y: alvo ? (root.vertical ? 0 : (root.bar && root.bar.position === "bottom" ? -implicitHeight - 4 : alvo.height + 4)) : 0

    function pedir(b) {
      fecharPrevia.stop()
      pendente = b
      // Já aberta: troca na hora, como o Windows ao deslizar pelos ícones.
      if (visible) { if (alvo !== b) porClique = false; alvo = b; return }
      abrirPrevia.restart()
    }
    function soltar(b) {
      if (pendente === b) { pendente = null; abrirPrevia.stop() }
      fecharPrevia.restart()
    }
    // Clique num ícone com várias janelas: mostra as miniaturas na hora (ou fecha,
    // se já estavam abertas para ele).
    property bool porClique: false
    function alternar(b) {
      abrirPrevia.stop(); fecharPrevia.stop()
      if (visible && alvo === b && porClique) { fechar(true); return }
      pendente = b
      alvo = b
      porClique = true
      visible = true
    }
    function fechar(agora) {
      abrirPrevia.stop(); fecharPrevia.stop()
      pendente = null
      porClique = false
      if (agora) { visible = false; alvo = null }
    }
    onJanelasChanged: {
      var novos = janelas.map(function(j) { return j.endereco })
      if (novos.join(",") !== enderecos.join(",")) enderecos = novos
      if (visible && janelas.length === 0) fechar(true)
    }
    onSobreChanged: if (sobre) fecharPrevia.stop(); else fecharPrevia.restart()

    Timer { id: abrirPrevia; interval: 400; onTriggered: if (previa.pendente) { previa.alvo = previa.pendente; previa.porClique = false; previa.visible = true } }
    Timer {
      id: fecharPrevia; interval: 300
      onTriggered: if (!previa.sobre && !previa.pendente) previa.fechar(true)
    }

    HoverHandler { id: dentroPrevia }

    Rectangle {
      anchors.fill: parent
      anchors.margins: 4
      radius: 10
      color: Color.popups.background
      border.width: 1
      border.color: Color.popups.border

      GridLayout {
        id: linhaPrevia
        anchors.centerIn: parent
        columns: root.vertical ? 1 : Math.max(1, previa.enderecos.length)
        rowSpacing: 6
        columnSpacing: 6

        Repeater {
          model: previa.visible ? previa.enderecos : []
          delegate: Item {
            id: cartao
            required property string modelData
            readonly property var j: previa.dados(modelData)
            readonly property bool emFoco: !!j && Hyprland.activeToplevel && root.enderecoDe(Hyprland.activeToplevel) === modelData && !j.minimizada
            Layout.preferredWidth: previa.largCartao
            Layout.preferredHeight: 156

            Rectangle {
              anchors.fill: parent
              radius: 8
              color: Color.popups.text
              opacity: mc.containsMouse ? 0.10 : (cartao.emFoco ? 0.06 : 0)
              Behavior on opacity { NumberAnimation { duration: 100 } }
            }

            Text {
              id: tituloPrevia
              anchors { left: parent.left; right: fecharJanela.left; top: parent.top; leftMargin: 8; rightMargin: 4; topMargin: 6 }
              text: cartao.j ? cartao.j.titulo : ""
              elide: Text.ElideRight
              color: Color.popups.text
              font.family: root.bar ? root.bar.fontFamily : "monospace"
              font.pixelSize: 11
            }

            // Captura ao vivo da janela (protocolo de exportação de toplevel do Hyprland).
            ScreencopyView {
              id: captura
              anchors { horizontalCenter: parent.horizontalCenter; top: tituloPrevia.bottom; topMargin: 6 }
              // Fixo enquanto o cartão existe: trocar a fonte reinicia a captura.
              property var fonte: null
              Component.onCompleted: fonte = cartao.j && cartao.j.t ? cartao.j.t.wayland : null
              captureSource: fonte
              live: previa.visible
              paintCursor: false
              constraintSize: Qt.size(previa.largCartao - 16, 118)
              opacity: cartao.j && cartao.j.minimizada ? 0.75 : 1
            }
            // Sem imagem (ainda capturando ou indisponível): o nome do app no lugar.
            Text {
              visible: !captura.hasContent
              anchors.centerIn: captura.hasContent ? undefined : parent
              text: previa.alvo ? previa.alvo.nome : ""
              color: Color.popups.text
              opacity: 0.5
              font.family: root.bar ? root.bar.fontFamily : "monospace"
              font.pixelSize: 12
            }

            MouseArea {
              id: mc
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              acceptedButtons: Qt.LeftButton | Qt.MiddleButton
              onClicked: function(m) {
                var j = cartao.j
                if (!j) return
                if (m.button === Qt.MiddleButton) { root.fechar(j); return }
                root.focar(j)
                previa.fechar(true)
              }
            }

            Rectangle {
              id: fecharJanela
              anchors { right: parent.right; top: parent.top; margins: 3 }
              width: 22; height: 20; radius: 5
              color: mf.containsMouse ? "#c42b1c" : "transparent"
              opacity: mc.containsMouse || mf.containsMouse ? 1 : 0
              Text { anchors.centerIn: parent; text: "󰅖"; color: mf.containsMouse ? "#ffffff" : Color.popups.text; font.family: root.bar ? root.bar.fontFamily : "monospace"; font.pixelSize: 12 }
              MouseArea { id: mf; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: if (cartao.j) root.fechar(cartao.j) }
            }
          }
        }
      }
    }
  }
}
