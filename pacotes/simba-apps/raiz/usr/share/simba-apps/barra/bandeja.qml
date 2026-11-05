import "idiomas"
import QtQuick 6.11
import QtQuick.Effects
import Quickshell
import Quickshell.Hyprland
import Quickshell.Io
import Quickshell.Widgets
import Quickshell.Services.SystemTray
import qs.Commons

// Bandeja estilo Windows 11: seta ^ no início da direita da barra.
//   • Ícones de apps em segundo plano (bandeja do sistema) ficam ao lado da
//     seta; arrastar um para cima da seta oculta, arrastar de dentro da seta
//     para fora devolve.
//   • Ícones do Simba: arrastar (pela própria barra) e soltar em cima da seta
//     oculta. Na seta eles viram atalhos que abrem a página das Configurações.
// Estado na entrada { "id": "bandeja", "type": "qml", "apps": [...], "ocultos": [...] }
// do shell.json, alterada pelo /usr/bin/barra-tarefas bandeja ….
Item {
  id: root

  property var bar
  property string moduleName
  property var settings: ({})

  readonly property var appsOcultos: settings && settings.apps instanceof Array ? settings.apps : []
  readonly property var widgetsOcultos: settings && settings.ocultos instanceof Array ? settings.ocultos : []

  readonly property bool vertical: bar ? bar.vertical : false
  readonly property int barSize: bar ? bar.barSize : 26
  readonly property color fg: bar ? bar.barForeground : Color.foreground
  readonly property string fonte: bar && bar.fontFamily ? bar.fontFamily : "JetBrainsMono Nerd Font"
  readonly property string posicao: bar && bar.position ? bar.position : "bottom"
  readonly property int tamIcone: 16

  implicitWidth: vertical ? barSize : linha.implicitWidth + 4
  implicitHeight: vertical ? linha.implicitHeight + 4 : barSize

  // A barra cobre cada módulo com um MouseArea que arrasta o módulo inteiro;
  // subir o Loader deixa os ícones receberem o press (como em tarefas.qml).
  Component.onCompleted: if (parent) parent.z = 60

  // ── ícones do Simba arrastados pela barra até a seta ──────────────────
  // A barra decide "antes/depois" pela borda mais próxima, o que numa seta
  // estreita quase sempre dá "depois" (não oculta). Então, durante o arrasto
  // da barra, olhamos o cursor no MouseArea do módulo arrastado: se ele for
  // solto em cima da seta, o ajudante manda o ícone para cá (depois da barra
  // gravar a própria mudança).
  readonly property var meuSlot: parent ? parent.parent : null
  property var slots: []
  property int tique: 0
  property var origem: null        // slot sendo arrastado pela barra
  property bool origemSobreSeta: false
  readonly property bool alvoBarra: origem !== null && origemSobreSeta
  readonly property var naoOcultaveis: ["tarefas", "areas", "bandeja", "simba.workspaces", "simba.menu", "simba.spacer"]

  function acharSlots() {
    var raiz = root
    while (raiz.parent) raiz = raiz.parent
    var achados = []
    function varrer(it) {
      if (!it || !it.children) return
      for (var i = 0; i < it.children.length; i++) {
        var c = it.children[i]
        if (c !== root.meuSlot && c.dragSource !== undefined && c.moduleName !== undefined) achados.push(c)
        else varrer(c)
      }
    }
    varrer(raiz)
    slots = achados
  }
  function ponteiroDe(slot) {
    for (var i = 0; i < slot.children.length; i++) {
      var c = slot.children[i]
      if (c.dragging !== undefined && c.mouseX !== undefined && c.pressed !== undefined) return c
    }
    return null
  }
  Timer {
    interval: 50
    repeat: true
    running: true
    onTriggered: {
      if (!root.slots.length || (++root.tique % 40 === 0 && !root.origem)) root.acharSlots()
      var arrastado = null
      for (var i = 0; i < root.slots.length; i++) if (root.slots[i] && root.slots[i].dragSource) { arrastado = root.slots[i]; break }
      if (arrastado) {
        var mp = root.ponteiroDe(arrastado)
        var sobre = false
        if (mp && root.naoOcultaveis.indexOf(String(arrastado.moduleName)) < 0) {
          var p = mp.mapToItem(seta, mp.mouseX, mp.mouseY)
          // um pouco de folga em volta da seta
          sobre = p.x >= -6 && p.y >= -6 && p.x <= seta.width + 6 && p.y <= seta.height + 6
        }
        root.origem = arrastado
        root.origemSobreSeta = sobre
      } else if (root.origem) {
        var nome = String(root.origem.moduleName || "")
        var ocultar = root.origemSobreSeta
        root.origem = null
        root.origemSobreSeta = false
        if (ocultar && nome) { ocultarAdiado.nome = nome; ocultarAdiado.restart() }
      }
    }
  }
  // Slots são recriados quando o layout muda.
  onSettingsChanged: slots = []
  Connections { target: root.meuSlot ? root.meuSlot.parent : null; function onChildrenChanged() { root.slots = [] } }
  Timer { id: ocultarAdiado; property string nome: ""; interval: 450; onTriggered: root.helper(["ocultar", nome]) }

  // ── apps (StatusNotifierItem) ───────────────────────────────────────────
  // Chrome/Electron trocam o id a cada execução: para eles vale o título.
  function chaveApp(it) {
    var id = String(it.id || "")
    if (!id || /^(chrome_status_icon|StatusIcon|tray_icon)/i.test(id)) return String(it.title || it.tooltipTitle || id)
    return id
  }
  function nomeApp(it) { return String(it.tooltipTitle || it.title || it.id || "") }
  readonly property var todosApps: SystemTray.items.values
  readonly property var appsVisiveis: todosApps.filter(function(it) { return root.appsOcultos.indexOf(root.chaveApp(it)) < 0 })
  readonly property var appsNaSeta: todosApps.filter(function(it) { return root.appsOcultos.indexOf(root.chaveApp(it)) >= 0 })

  function cliqueApp(it, botao, ancora, m) {
    if (botao === Qt.MiddleButton) it.secondaryActivate()
    else if (botao === Qt.RightButton || it.onlyMenu) { if (it.hasMenu) menu.abrir(it, ancora); else it.activate() }
    else it.activate()
  }

  // ── ícones do Simba ocultos ───────────────────────────────────────────
  readonly property var widgets: ({
    // Abre Configurações › Agentes de IA (cascata: quando um agente esgota, /usr/bin/agentes passa ao próximo)
    "simba.agents":          { nome: I18n.t("Agentes de IA"),     glifo: "\u{F06A9}", cmd: ["configuracoes", "agentes"] },
    "simba.bluetooth":       { nome: I18n.t("Bluetooth"),         glifo: "\u{F00AF}", cmd: ["configuracoes", "bluetooth"] },
    "simba.network":         { nome: I18n.t("Rede"),              glifo: "\u{F05A9}", cmd: ["configuracoes", "rede"] },
    "simba.audio":           { nome: I18n.t("Som"),               glifo: "\u{F057E}", cmd: ["configuracoes", "som"] },
    "simba.microphone":      { nome: I18n.t("Microfone"),         glifo: "\u{F036C}", cmd: ["configuracoes", "som"] },
    "simba.monitor":         { nome: I18n.t("Tela"),              glifo: "\u{F0379}", cmd: ["configuracoes", "tela"] },
    "simba.power":           { nome: I18n.t("Energia e bateria"), glifo: "\u{F0079}", cmd: ["configuracoes", "energia"] },
    "simba.indicators":      { nome: I18n.t("Indicadores"),       glifo: "\u{F009E}", cmd: ["configuracoes", "notificacoes"] },
    "simba.keyboard-layout": { nome: I18n.t("Layout do teclado"), glifo: "\u{F030C}", cmd: ["configuracoes", "entrada"] },
    "simba.weather":         { nome: I18n.t("Clima"),             glifo: "\u{F0599}", cmd: ["simba", "notification", "weather"] },
    "simba.system-update":   { nome: I18n.t("Atualizações"),      glifo: "\u{F06B0}", cmd: ["simba-atualizar", "aplicar"] },
    "simba.clock":           { nome: I18n.t("Relógio"),           glifo: "\u{F0150}", cmd: ["configuracoes", "barra"] },
    "simba.media":           { nome: I18n.t("Mídia"),             glifo: "\u{F075A}", cmd: ["configuracoes", "som"] },
    "simba.tailscale":       { nome: I18n.t("Tailscale"),         glifo: "\u{F0317}", cmd: ["configuracoes", "rede"] },
    "simba.dropbox":         { nome: I18n.t("Dropbox"),           glifo: "\u{F0770}", cmd: ["configuracoes", "barra"] },
    "simba.tray":            { nome: I18n.t("Bandeja do sistema"), glifo: "\u{F003B}", cmd: ["configuracoes", "barra"] },
    "simba.active-window":   { nome: I18n.t("Janela ativa"),      glifo: "\u{F10AC}", cmd: ["configuracoes", "barra"] }
  })
  function idWidget(e) { return typeof e === "string" ? e : String(e && e.id || "") }
  function infoWidget(e) {
    var id = idWidget(e)
    return widgets[id] || { nome: id, glifo: "\u{F003B}", cmd: ["configuracoes", "barra"] }
  }

  readonly property int totalNaSeta: appsNaSeta.length + widgetsOcultos.length

  function helper(args) { Quickshell.execDetached(["barra-tarefas", "bandeja"].concat(args)) }

  // Ícone do Simba solto em cima da seta pelo arrasto da própria barra: ele
  // cai antes da bandeja no layout; o ajudante tira dali e guarda na seta.
  FileView {
    path: Quickshell.env("HOME") + "/.config/simba/shell.json"
    watchChanges: true
    onFileChanged: reload()
    onLoaded: {
      try {
        var lay = JSON.parse(text()).bar.layout
        var fixos = ["tarefas", "areas", "bandeja", "simba.workspaces", "simba.menu", "simba.spacer"]
        for (var s of ["left", "center", "right"]) {
          var l = lay[s] || []
          var i = l.findIndex(function(x) { return root.idWidget(x) === "bandeja" })
          if (i < 0) continue
          for (var k = 0; k < i; k++) if (fixos.indexOf(root.idWidget(l[k])) < 0) { root.helper(["recolher"]); return }
        }
      } catch (e) {}
    }
  }

  // ── barra: seta + apps visíveis ─────────────────────────────────────────
  Grid {
    id: linha
    anchors.centerIn: parent
    columns: root.vertical ? 1 : 1 + root.appsVisiveis.length
    spacing: 0

    Item {
      id: seta
      width: root.vertical ? root.barSize : root.tamIcone + 12
      height: root.vertical ? root.tamIcone + 12 : root.barSize
      readonly property bool alvo: (root.arrastandoApp >= 0 && root.sobreSeta) || root.alvoBarra

      Rectangle {
        anchors.fill: parent
        anchors.margins: 2
        radius: Math.min(7, height / 2)
        color: root.fg
        opacity: seta.alvo ? 0.22 : (popup.visible ? 0.12 : (setaArea.containsMouse ? 0.08 : 0))
        Behavior on opacity { NumberAnimation { duration: 120 } }
      }
      Text {
        anchors.centerIn: parent
        // Aponta para onde a bandeja abre.
        text: root.posicao === "top" ? "\u{F0140}" : root.posicao === "left" ? "\u{F0142}" : root.posicao === "right" ? "\u{F0141}" : "\u{F0143}"
        color: root.fg
        opacity: root.totalNaSeta > 0 || setaArea.containsMouse || popup.visible ? 0.9 : 0.45
        font.family: root.fonte
        font.pixelSize: root.tamIcone
        rotation: popup.visible ? 180 : 0
        Behavior on rotation { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }
      }
      MouseArea {
        id: setaArea
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: { if (root.bar) root.bar.hideTooltip(seta); popup.visible ? popup.fechar() : popup.abrir() }
        onEntered: if (root.bar && !popup.visible) root.bar.showTooltip(seta, root.totalNaSeta > 0
                     ? I18n.t("Mostrar ícones ocultos (") + root.totalNaSeta + ")" : I18n.t("Ícones ocultos: arraste ícones para cá"))
        onExited: if (root.bar) root.bar.hideTooltip(seta)
      }
    }

    Repeater {
      model: root.appsVisiveis
      delegate: Item {
        id: app
        required property var modelData
        required property int index
        width: root.vertical ? root.barSize : root.tamIcone + 12
        height: root.vertical ? root.tamIcone + 12 : root.barSize
        z: root.arrastandoApp === index ? 10 : 0
        transform: Translate { x: root.arrastandoApp === app.index && !root.vertical ? root.deslocApp : 0; y: root.arrastandoApp === app.index && root.vertical ? root.deslocApp : 0 }

        Rectangle {
          anchors.fill: parent
          anchors.margins: 2
          radius: Math.min(7, height / 2)
          color: root.fg
          opacity: appArea.containsMouse ? 0.08 : 0
        }
        IconImage {
          anchors.centerIn: parent
          implicitSize: root.tamIcone
          source: String(app.modelData.icon || "")
          asynchronous: true
          opacity: app.modelData.status === Status.Passive ? 0.6 : 1
          scale: appArea.pressed ? 0.86 : 1
          Behavior on scale { NumberAnimation { duration: 90 } }
        }
        Rectangle {
          // pede atenção
          visible: app.modelData.status === Status.NeedsAttention
          width: 5; height: 5; radius: 2.5
          color: Color.accent
          anchors { right: parent.right; top: parent.top; margins: 4 }
        }
        MouseArea {
          id: appArea
          anchors.fill: parent
          hoverEnabled: true
          preventStealing: true
          acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
          cursorShape: root.arrastandoApp === app.index ? Qt.ClosedHandCursor : Qt.PointingHandCursor
          property real inicio: 0
          property bool arrastou: false
          function pos(m) { var p = mapToItem(linha, m.x, m.y); return root.vertical ? p.y : p.x }
          onPressed: function(m) { arrastou = false; inicio = pos(m) }
          onPositionChanged: function(m) {
            if (!(pressedButtons & Qt.LeftButton)) return
            var d = pos(m) - inicio
            if (!arrastou && Math.abs(d) < 8) return
            if (!arrastou) { arrastou = true; if (root.bar) root.bar.hideTooltip(app); root.arrastandoApp = app.index }
            root.deslocApp = d
            var p = mapToItem(seta, m.x, m.y)
            root.sobreSeta = root.vertical ? p.y < seta.height + 4 : p.x < seta.width + 4
          }
          onReleased: {
            if (!arrastou) return
            if (root.sobreSeta) root.helper(["app-ocultar", root.chaveApp(app.modelData)])
            root.arrastandoApp = -1; root.deslocApp = 0; root.sobreSeta = false
          }
          onCanceled: { root.arrastandoApp = -1; root.deslocApp = 0; root.sobreSeta = false }
          onClicked: function(m) { if (!arrastou) root.cliqueApp(app.modelData, m.button, app, m) }
          onWheel: function(w) { app.modelData.scroll(w.angleDelta.y !== 0 ? w.angleDelta.y : w.angleDelta.x, w.angleDelta.y === 0) }
          onEntered: if (root.bar && root.arrastandoApp < 0) root.bar.showTooltip(app, root.nomeApp(app.modelData))
          onExited: if (root.bar) root.bar.hideTooltip(app)
        }
      }
    }
  }
  property int arrastandoApp: -1
  property real deslocApp: 0
  property bool sobreSeta: false

  // ── a bandeja (seta aberta) ─────────────────────────────────────────────
  PopupWindow {
    id: popup
    color: "transparent"
    visible: false
    readonly property int celula: 38
    readonly property int colunas: Math.max(1, Math.min(5, root.totalNaSeta))
    property string dica: ""
    property bool arrastandoFora: false
    implicitWidth: Math.max(colunas * celula + 20, 200)
    implicitHeight: conteudo.implicitHeight + 20

    anchor.item: seta
    anchor.rect.x: root.vertical ? (root.posicao === "right" ? -implicitWidth - 4 : seta.width + 4) : seta.width / 2 - implicitWidth / 2
    anchor.rect.y: root.vertical ? 0 : (root.posicao === "bottom" ? -implicitHeight - 4 : seta.height + 4)

    function abrir() { dica = ""; visible = true }
    function fechar() { visible = false; menu.visible = false }

    HyprlandFocusGrab {
      active: popup.visible && !menu.visible
      windows: [popup]
      onCleared: popup.fechar()
    }

    Rectangle {
      id: caixa
      anchors.fill: parent
      anchors.margins: 4
      radius: 10
      color: Color.popups.background
      border.width: 1
      border.color: Color.popups.border

      Column {
        id: conteudo
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 6
        spacing: 4

        Text {
          visible: root.totalNaSeta === 0
          width: parent.width
          padding: 8
          wrapMode: Text.WordWrap
          horizontalAlignment: Text.AlignHCenter
          text: I18n.t("Arraste ícones da barra para a seta para escondê-los aqui.")
          color: Color.popups.text
          opacity: 0.7
          font.family: root.fonte
          font.pixelSize: 11
        }

        Grid {
          id: grade
          anchors.horizontalCenter: parent.horizontalCenter
          columns: popup.colunas
          spacing: 0

          Repeater {
            // apps primeiro, depois os ícones do Simba
            model: root.appsNaSeta.map(function(it) { return { app: it } })
                    .concat(root.widgetsOcultos.map(function(w) { return { widget: w } }))
            delegate: Item {
              id: tile
              required property var modelData
              readonly property bool ehApp: !!modelData.app
              readonly property var info: ehApp ? null : root.infoWidget(modelData.widget)
              readonly property string nome: ehApp ? root.nomeApp(modelData.app) : info.nome
              width: popup.celula
              height: popup.celula
              z: tileArea.arrastou ? 10 : 0
              transform: Translate { x: tileArea.dx; y: tileArea.dy }

              Rectangle {
                anchors.fill: parent
                anchors.margins: 2
                radius: 7
                color: Color.popups.text
                opacity: tileArea.arrastou ? 0.16 : (tileArea.containsMouse ? 0.10 : 0)
              }
              IconImage {
                visible: tile.ehApp
                anchors.centerIn: parent
                implicitSize: 18
                source: tile.ehApp ? String(tile.modelData.app.icon || "") : ""
                asynchronous: true
              }
              Text {
                visible: !tile.ehApp
                anchors.centerIn: parent
                text: tile.info ? tile.info.glifo : ""
                color: Color.popups.text
                font.family: root.fonte
                font.pixelSize: 18
              }
              MouseArea {
                id: tileArea
                anchors.fill: parent
                hoverEnabled: true
                preventStealing: true
                acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
                cursorShape: arrastou ? Qt.ClosedHandCursor : Qt.PointingHandCursor
                property real x0: 0
                property real y0: 0
                property real dx: 0
                property real dy: 0
                property bool arrastou: false
                function fora(m) {
                  var p = mapToItem(caixa, m.x, m.y)
                  return p.x < 0 || p.y < 0 || p.x > caixa.width || p.y > caixa.height
                }
                onPressed: function(m) { arrastou = false; var p = mapToItem(caixa, m.x, m.y); x0 = p.x; y0 = p.y }
                onPositionChanged: function(m) {
                  if (!(pressedButtons & Qt.LeftButton)) return
                  var p = mapToItem(caixa, m.x, m.y)
                  if (!arrastou && Math.abs(p.x - x0) + Math.abs(p.y - y0) < 8) return
                  arrastou = true
                  dx = p.x - x0; dy = p.y - y0
                  popup.arrastandoFora = fora(m)
                }
                onReleased: function(m) {
                  if (!arrastou) return
                  if (fora(m)) {
                    if (tile.ehApp) root.helper(["app-mostrar", root.chaveApp(tile.modelData.app)])
                    else root.helper(["mostrar", root.idWidget(tile.modelData.widget)])
                  }
                  dx = 0; dy = 0; popup.arrastandoFora = false
                  Qt.callLater(function() { tileArea.arrastou = false })
                }
                onCanceled: { dx = 0; dy = 0; arrastou = false; popup.arrastandoFora = false }
                onClicked: function(m) {
                  if (arrastou) return
                  if (tile.ehApp) {
                    root.cliqueApp(tile.modelData.app, m.button, tile, m)
                    if (m.button === Qt.LeftButton && !tile.modelData.app.onlyMenu) popup.fechar()
                  } else {
                    Quickshell.execDetached(tile.info.cmd)
                    popup.fechar()
                  }
                }
                onEntered: popup.dica = tile.nome
                onExited: if (popup.dica === tile.nome) popup.dica = ""
              }
            }
          }
        }

        Text {
          visible: root.totalNaSeta > 0
          width: parent.width
          leftPadding: 4; rightPadding: 4
          elide: Text.ElideRight
          horizontalAlignment: Text.AlignHCenter
          text: popup.arrastandoFora ? I18n.t("Solte para mostrar na barra") : (popup.dica || I18n.t("Arraste para fora para mostrar na barra"))
          color: Color.popups.text
          opacity: popup.dica || popup.arrastandoFora ? 0.85 : 0.5
          font.family: root.fonte
          font.pixelSize: 11
        }
      }
    }
  }

  // ── menu do app (botão direito) ─────────────────────────────────────────
  // QsMenuEntry.display() precisa do Quickshell em modo QApplication, que o
  // simba-shell não usa: o menu é desenhado aqui, com submenus em pilha.
  PopupWindow {
    id: menu
    color: "transparent"
    visible: false
    property var item: null
    property var ancora: null
    property var pilha: []
    readonly property var entradas: pilha.length ? pilha[pilha.length - 1].children.values : abridor.children.values
    implicitWidth: 240
    implicitHeight: menuCol.implicitHeight + 20

    anchor.item: ancora
    anchor.rect.x: ancora ? ancora.width / 2 - implicitWidth / 2 : 0
    anchor.rect.y: ancora ? (root.posicao === "bottom" ? -implicitHeight - 4 : ancora.height + 4) : 0

    function limpar() { for (var i = pilha.length - 1; i >= 0; i--) pilha[i].destroy(); pilha = [] }
    function abrir(it, anc) { limpar(); item = it; ancora = anc; visible = true }
    function entrar(e) { var o = submenu.createObject(menu, { menu: e }); if (o) pilha = pilha.concat([o]) }
    function voltar() { var p = pilha.slice(); var o = p.pop(); pilha = p; if (o) o.destroy() }
    onVisibleChanged: if (!visible) limpar()

    QsMenuOpener { id: abridor; menu: menu.item ? menu.item.menu : null }
    Component { id: submenu; QsMenuOpener {} }

    HyprlandFocusGrab {
      active: menu.visible
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
        id: menuCol
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 6
        spacing: 1

        Item {
          visible: menu.pilha.length > 0
          width: parent.width; height: 28
          Rectangle { anchors.fill: parent; radius: 6; color: Color.popups.text; opacity: voltarArea.containsMouse ? 0.10 : 0 }
          Text { x: 8; anchors.verticalCenter: parent.verticalCenter; text: "\u{F0141}  Voltar"; color: Color.popups.text; font.family: root.fonte; font.pixelSize: 12 }
          MouseArea { id: voltarArea; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: menu.voltar() }
        }

        Repeater {
          model: menu.entradas
          delegate: Item {
            id: linhaMenu
            required property var modelData
            width: menuCol.width
            height: modelData.isSeparator ? 9 : 28
            opacity: modelData.enabled ? 1 : 0.45
            Rectangle {
              visible: linhaMenu.modelData.isSeparator
              anchors.centerIn: parent
              width: parent.width - 12; height: 1
              color: Color.popups.text; opacity: 0.12
            }
            Rectangle {
              visible: !linhaMenu.modelData.isSeparator
              anchors.fill: parent
              radius: 6
              color: Color.popups.text
              opacity: mla.containsMouse && linhaMenu.modelData.enabled ? 0.10 : 0
            }
            Row {
              visible: !linhaMenu.modelData.isSeparator
              x: 8
              anchors.verticalCenter: parent.verticalCenter
              spacing: 8
              Text {
                width: 14
                text: linhaMenu.modelData.checkState === Qt.Checked ? "\u{F012C}" : ""
                color: Color.popups.text; font.family: root.fonte; font.pixelSize: 12
                anchors.verticalCenter: parent.verticalCenter
              }
              Text {
                width: menuCol.width - 56
                elide: Text.ElideRight
                text: String(linhaMenu.modelData.text || "").replace(/_(?!_)/g, "")
                color: Color.popups.text; font.family: root.fonte; font.pixelSize: 12
                anchors.verticalCenter: parent.verticalCenter
              }
              Text {
                visible: linhaMenu.modelData.hasChildren
                text: "\u{F0142}"
                color: Color.popups.text; font.family: root.fonte; font.pixelSize: 12
                anchors.verticalCenter: parent.verticalCenter
              }
            }
            MouseArea {
              id: mla
              anchors.fill: parent
              enabled: !linhaMenu.modelData.isSeparator && linhaMenu.modelData.enabled
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: {
                if (linhaMenu.modelData.hasChildren) { menu.entrar(linhaMenu.modelData); return }
                linhaMenu.modelData.triggered()
                menu.visible = false
                popup.fechar()
              }
            }
          }
        }
      }
    }
  }
}
