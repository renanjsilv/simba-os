import "idiomas"
import QtQuick 6.11
import QtQuick.Effects
import Quickshell
import Quickshell.Hyprland
import Quickshell.Wayland
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
  Component.onCompleted: {
    if (parent) parent.z = 60
    root.atualizarSync()
  }

  // ── Sincronização estilo OneDrive ────────────────────────────────────
  property var syncData: null

  FileView {
    id: fvConfig
    path: Quickshell.env("HOME") + "/.config/conta/config.json"
    watchChanges: true
    onFileChanged: reload()
    onLoaded: root.atualizarSync()
  }

  FileView {
    id: fvEstado
    path: Quickshell.env("HOME") + "/.local/state/conta/estado.json"
    watchChanges: true
    onFileChanged: reload()
    onLoaded: root.atualizarSync()
  }

  readonly property var syncCfg: {
    try { return JSON.parse(fvConfig.text()) || {} } catch (e) { return {} }
  }
  readonly property var syncEst: {
    try { return JSON.parse(fvEstado.text()) || {} } catch (e) { return {} }
  }

  readonly property string syncEmail: (syncData && syncData.email) || syncCfg.email || ""
  readonly property string syncNome: (syncData && syncData.nome) || syncCfg.nome || ""
  readonly property bool syncConectado: !!(syncEmail || (syncData && syncData.conectado))
  readonly property bool syncPrecisaDecidir: !!(syncData ? (syncData.conflito || syncData.precisa_decidir) : (syncEst.conflito || syncEst.precisa_decidir))
  readonly property bool syncPausado: !!(syncData ? syncData.pausado : syncEst.pausado_ate)
  readonly property bool syncRodando: !!(syncData ? (syncData.rodando || syncData.sincronizando) : syncEst.sincronizando)
  readonly property bool syncErro: !!((syncData && syncData.resultado === "erro" && !syncPrecisaDecidir) || (syncEst.resultado === "erro" && !syncPrecisaDecidir))

  readonly property string syncEstadoNome: {
    if (!syncConectado) return I18n.t("Não conectado")
    if (syncPrecisaDecidir) return I18n.t("Precisa de você")
    if (syncPausado) return I18n.t("Pausado")
    if (syncRodando) return I18n.t("Sincronizando…")
    if (syncErro) return I18n.t("Sem conexão")
    return I18n.t("Tudo em dia")
  }

  readonly property color syncCor: {
    if (!syncConectado) return "#77777e"
    if (syncPrecisaDecidir) return "#ea4335"
    if (syncPausado) return "#fbbc05"
    if (syncRodando) return "#4285f4"
    if (syncErro) return "#ea4335"
    return "#34a853"
  }

  readonly property string syncGlifo: {
    if (!syncConectado) return "\u{F0708}"
    if (syncPrecisaDecidir) return "\u{F0028}"
    if (syncPausado) return "\u{F03E4}"
    if (syncRodando) return "\u{F046A}"
    if (syncErro) return "\u{F0156}"
    return "\u{F012C}"
  }

  function extrairProgresso(str) {
    if (!str) return 0
    var m = String(str).match(/(\d+)%/)
    if (m) return parseInt(m[1], 10)
    return 0
  }

  // Painel aberto: status completo (arquivos recentes, cota). Fechado: o leve, só para o
  // ícone e o estado (sem varrer as pastas a cada poucos segundos).
  function atualizarSync() {
    if (procSyncStatus.running) return
    procSyncStatus.command = painelSync.visible ? ["conta", "status"] : ["conta", "status", "--rapido"]
    procSyncStatus.running = true
  }

  Process {
    id: procSyncStatus
    // `conta` do sistema (/usr/bin): ~/.local/bin/conta só existia nesta máquina de
    // desenvolvimento, e numa instalação nova o painel ficava sempre "Não conectado".
    command: ["conta", "status", "--rapido"]
    stdout: StdioCollector { id: syncCollector }
    onExited: function(code) {
      if (code === 0 && syncCollector.text) {
        try {
          root.syncData = JSON.parse(syncCollector.text)
        } catch (e) {}
      }
    }
  }

  Timer {
    interval: painelSync.visible ? 4000 : 15000
    repeat: true
    running: true
    triggeredOnStart: true
    onTriggered: {
      // os arquivos podem não existir no 1º login: sem isso o FileView nunca os relê
      if (fvConfig.loaded === false) fvConfig.reload()
      if (fvEstado.loaded === false) fvEstado.reload()
      root.atualizarSync()
    }
  }

  // simba-shell simbasync alternarSync|abrirSync|fecharSync
  IpcHandler {
    target: "simbasync"
    function alternarSync(): void {
      if (painelSync.visible) painelSync.fechar()
      else painelSync.abrir(seta)
    }
    function abrirSync(): void {
      painelSync.abrir(seta)
    }
    function fecharSync(): void {
      painelSync.fechar()
    }
  }

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
    var ehSync = it.id === "simba-sync-tray" || String(it.id).indexOf("sync-tray") >= 0
    if (ehSync) {
      if (painelSync.visible) {
        painelSync.fechar()
      } else {
        if (menu.visible) menu.visible = false
        var anc = ancora
        if (popup.visible) {
          anc = seta
          popup.fechar()
        }
        painelSync.abrir(anc)
      }
      return
    }

    var ehMenu = it.onlyMenu
    if (botao === Qt.MiddleButton) {
      it.secondaryActivate()
    } else if (botao === Qt.RightButton || ehMenu) {
      if (it.hasMenu) {
        if (menu.visible && menu.item === it) menu.visible = false
        else menu.abrir(it, ancora)
      } else {
        it.activate()
      }
    } else {
      it.activate()
    }
  }

  // ── ícones do Simba ocultos ───────────────────────────────────────────
  readonly property var widgets: ({
    // Abre a interface de chat dos Agentes de IA
    "simba.agents":          { nome: I18n.t("Agentes de IA"),     glifo: "\u{F06A9}", cmd: ["simba-agentes"] },
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
  // Camada transparente na tela inteira (acima de tudo, inclusive da barra):
  // a caixa é desenhada ao lado da seta e qualquer clique fora dela fecha a
  // bandeja. Antes era um PopupWindow + HyprlandFocusGrab, mas o grab não
  // dispara no Hyprland atual e a bandeja ficava presa aberta.
  PanelWindow {
    id: popup
    color: "transparent"
    visible: false
    screen: seta.QsWindow.window ? seta.QsWindow.window.screen : null
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "simba-bandeja"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand
    anchors { top: true; bottom: true; left: true; right: true }

    readonly property int celula: 38
    readonly property int colunas: Math.max(1, Math.min(5, root.totalNaSeta))
    property string dica: ""
    property bool arrastandoFora: false
    readonly property int larg: Math.max(colunas * celula + 20, 200)
    readonly property int alt: conteudo.implicitHeight + 20

    // posição da seta na tela, medida ao abrir
    property real setaX: 0
    property real setaY: 0
    readonly property real caixaX: {
      var x = root.vertical ? (root.posicao === "right" ? setaX - larg - 4 : setaX + seta.width + 4)
                            : setaX + seta.width / 2 - larg / 2
      return Math.max(0, Math.min(x, width - larg))
    }
    readonly property real caixaY: {
      var y = root.vertical ? setaY : (root.posicao === "bottom" ? setaY - alt - 4 : setaY + seta.height + 4)
      return Math.max(0, Math.min(y, height - alt))
    }

    function medir() {
      var w = seta.QsWindow.window
      var p = seta.mapToItem(null, 0, 0)
      var sw = w && w.screen ? w.screen.width : 0
      var sh = w && w.screen ? w.screen.height : 0
      // a barra ocupa a borda inteira da tela
      setaX = p.x + (w && root.posicao === "right" ? sw - w.width : 0)
      setaY = p.y + (w && root.posicao === "bottom" ? sh - w.height : 0)
    }
    function abrir() { dica = ""; medir(); visible = true; teclas.forceActiveFocus() }
    function fechar() { visible = false; menu.visible = false }

    MouseArea {
      anchors.fill: parent
      acceptedButtons: Qt.AllButtons
      onPressed: popup.fechar()
      onWheel: popup.fechar()
    }
    Item { id: teclas; focus: true; Keys.onEscapePressed: popup.fechar() }

    Item {
      x: popup.caixaX
      y: popup.caixaY
      width: popup.larg
      height: popup.alt

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

  // ── Painel estilo OneDrive para a Sincronização do Simba ────────────────
  PanelWindow {
    id: painelSync
    color: "transparent"
    visible: false
    screen: root.bar && root.bar.screen ? root.bar.screen : (seta.QsWindow.window ? seta.QsWindow.window.screen : null)
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.namespace: "simba-sync-painel"
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand
    anchors { top: true; bottom: true; left: true; right: true }

    readonly property int larg: 380
    readonly property int alt: Math.min(560, colSync.implicitHeight + 36)

    property real ancoraX: 0
    property real ancoraY: 0
    property real ancoraW: 0
    property real ancoraH: 0

    readonly property real caixaX: {
      var x = root.vertical ? (root.posicao === "right" ? ancoraX - larg - 8 : ancoraX + ancoraW + 8)
                            : ancoraX + ancoraW / 2 - larg / 2
      return Math.max(8, Math.min(x, width - larg - 8))
    }
    readonly property real caixaY: {
      var y = root.vertical ? Math.max(8, Math.min(ancoraY + ancoraH / 2 - alt / 2, height - alt - 8))
                            : (root.posicao === "bottom" ? ancoraY - alt - 8 : ancoraY + ancoraH + 8)
      return Math.max(8, Math.min(y, height - alt - 8))
    }

    function medir(anc) {
      if (!anc) return
      var w = anc.QsWindow.window
      var p = anc.mapToItem(null, 0, 0)
      var sw = w && w.screen ? w.screen.width : 0
      var sh = w && w.screen ? w.screen.height : 0
      ancoraX = p.x + (w && root.posicao === "right" ? sw - w.width : 0)
      ancoraY = p.y + (w && root.posicao === "bottom" ? sh - w.height : 0)
      ancoraW = anc.width
      ancoraH = anc.height
    }

    function abrir(anc) {
      medir(anc)
      visible = true
      procSyncStatus.running = false   // troca a consulta leve em andamento pela completa
      root.atualizarSync()
      teclasSync.forceActiveFocus()
    }

    function fechar() {
      visible = false
    }

    MouseArea {
      anchors.fill: parent
      acceptedButtons: Qt.AllButtons
      onPressed: painelSync.fechar()
    }

    Item {
      id: teclasSync
      focus: true
      Keys.onEscapePressed: painelSync.fechar()
    }

    Item {
      x: painelSync.caixaX
      y: painelSync.caixaY
      width: painelSync.larg
      height: painelSync.alt

      MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.AllButtons
        onClicked: {}
        onWheel: function(wheel) {
          if (listaRecentes.contentHeight > listaRecentes.height) {
            listaRecentes.contentY = Math.max(0, Math.min(listaRecentes.contentHeight - listaRecentes.height, listaRecentes.contentY - wheel.angleDelta.y))
          }
          wheel.accepted = true
        }
      }

      Rectangle {
        id: caixaSync
        anchors.fill: parent
        anchors.margins: 4
        radius: 12
        color: "#262629"
        border.width: 1
        border.color: Qt.rgba(0, 0, 0, 0.5)

        Rectangle {
          anchors.fill: parent
          anchors.margins: 1
          radius: 11
          color: "transparent"
          border.width: 1
          border.color: Qt.rgba(1, 1, 1, 0.08)
        }

        Column {
          id: colSync
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.top: parent.top
          anchors.margins: 16
          spacing: 12

          // 1. Cabeçalho (Avatar + Título + Email)
          Row {
            width: parent.width
            spacing: 10

            Rectangle {
              width: 32; height: 32; radius: 16
              color: "#4a4a50"
              clip: true
              anchors.verticalCenter: parent.verticalCenter

              Image {
                id: imgAvatar
                anchors.fill: parent
                source: (root.syncData && root.syncData.foto) ? ("file://" + root.syncData.foto) : ("file://" + Quickshell.env("HOME") + "/.local/state/conta/foto.jpg")
                fillMode: Image.PreserveAspectCrop
                visible: status === Image.Ready
              }

              Text {
                visible: !imgAvatar.visible
                anchors.centerIn: parent
                text: {
                  if (root.syncNome) return root.syncNome.charAt(0).toUpperCase()
                  if (root.syncEmail) return root.syncEmail.charAt(0).toUpperCase()
                  return "S"
                }
                color: "#e8e8ea"
                font.family: root.fonte
                font.pixelSize: 13
                font.weight: Font.DemiBold
              }
            }

            Column {
              anchors.verticalCenter: parent.verticalCenter
              width: parent.width - 42
              spacing: 1

              Text {
                text: I18n.t("Sincronização")
                color: "#ededee"
                font.family: root.fonte
                font.pixelSize: 14
                font.weight: Font.DemiBold
              }

              Text {
                text: root.syncEmail || I18n.t("Não conectado")
                color: "#77777e"
                font.family: root.fonte
                font.pixelSize: 12
                elide: Text.ElideRight
                width: parent.width
              }
            }
          }

          // 2. Card de Estado (com ícone colorido, status e barra de progresso)
          Rectangle {
            width: parent.width
            height: colEstado.implicitHeight + 24
            radius: 10
            color: Qt.rgba(1, 1, 1, 0.04)

            Column {
              id: colEstado
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.top: parent.top
              anchors.margins: 12
              spacing: 6

              Row {
                width: parent.width
                spacing: 8

                Text {
                  anchors.verticalCenter: parent.verticalCenter
                  text: root.syncGlifo
                  color: root.syncCor
                  font.family: root.fonte
                  font.pixelSize: 15

                  RotationAnimation on rotation {
                    running: root.syncRodando
                    from: 0
                    to: 360
                    duration: 1600
                    loops: Animation.Infinite
                  }
                }

                Text {
                  anchors.verticalCenter: parent.verticalCenter
                  text: root.syncEstadoNome
                  color: root.syncCor
                  font.family: root.fonte
                  font.pixelSize: 14
                  font.weight: Font.DemiBold
                }
              }

              Text {
                width: parent.width
                text: {
                  if (!root.syncConectado) return I18n.t("Conecte sua conta para sincronizar arquivos")
                  if (root.syncPrecisaDecidir) return (root.syncData && root.syncData.erro) || root.syncEst.erro || I18n.t("Há uma decisão a tomar")
                  if (root.syncPausado) return I18n.t("Sincronização pausada · clique em Retomar para voltar")
                  if (root.syncRodando) return (root.syncData && root.syncData.progresso) || root.syncEst.progresso || I18n.t("Enviando e recebendo alterações…")
                  if (root.syncErro) return (root.syncData && root.syncData.erro) || root.syncEst.erro || I18n.t("Sem conexão com o Drive")
                  return I18n.t("Arquivos sincronizados e protegidos")
                }
                color: "#77777e"
                font.family: root.fonte
                font.pixelSize: 12
                wrapMode: Text.WordWrap
              }

              Item {
                width: parent.width
                height: 6
                visible: root.syncRodando || root.syncConectado

                Rectangle {
                  anchors.fill: parent
                  radius: 3
                  color: Qt.rgba(1, 1, 1, 0.08)

                  Rectangle {
                    height: parent.height
                    radius: 3
                    color: root.syncCor
                    width: {
                      if (root.syncRodando) {
                        var progStr = (root.syncData && root.syncData.progresso) || root.syncEst.progresso || ""
                        var p = root.extrairProgresso(progStr)
                        return Math.max(12, parent.width * (p > 0 ? (p / 100) : 0.64))
                      }
                      return parent.width
                    }
                    Behavior on width { NumberAnimation { duration: 250 } }
                  }
                }
              }
            }
          }

          // 3. Seção "Recentes"
          Row {
            width: parent.width

            Text {
              text: I18n.t("Arquivos recentes")
              color: "#a7a7ad"
              font.family: root.fonte
              font.pixelSize: 12
              font.weight: Font.DemiBold
              leftPadding: 2
              anchors.verticalCenter: parent.verticalCenter
            }

            Item {
              width: Math.max(8, parent.width - 220)
              height: 1
            }

            Text {
              visible: root.syncData && root.syncData.recentes && root.syncData.recentes.length > 0
              text: String(root.syncData && root.syncData.recentes ? root.syncData.recentes.length : 0) + " " + I18n.t("itens")
              color: "#6e6e76"
              font.family: root.fonte
              font.pixelSize: 11
              anchors.verticalCenter: parent.verticalCenter
            }
          }

          Item {
            id: containerRecentes
            width: parent.width
            height: Math.min(240, Math.max(90, (root.syncData && root.syncData.recentes ? root.syncData.recentes.length : 0) * 46))
            clip: true

            ListView {
              id: listaRecentes
              anchors.fill: parent
              clip: true
              boundsBehavior: Flickable.StopAtBounds
              interactive: contentHeight > height
              model: (root.syncData && root.syncData.recentes && root.syncData.recentes.length > 0)
                     ? root.syncData.recentes
                     : []
              spacing: 2

              delegate: Item {
                id: itemRecente
                required property var modelData
                required property int index

                width: listaRecentes.width - (barraScroll.visible ? 8 : 0)
                height: (modelData.status === "sincronizando") ? 52 : 44

                Rectangle {
                  anchors.fill: parent
                  radius: 8
                  color: areaRecente.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent"
                  Behavior on color { ColorAnimation { duration: 100 } }
                }

                Row {
                  anchors.fill: parent
                  anchors.leftMargin: 6
                  anchors.rightMargin: 6
                  spacing: 10

                  // 1. Ícone de Status estilo OneDrive
                  Item {
                    id: caixaIconeStatus
                    width: 24
                    height: 24
                    anchors.verticalCenter: parent.verticalCenter

                    Rectangle {
                      anchors.centerIn: parent
                      width: 22
                      height: 22
                      radius: 11
                      color: {
                        var st = itemRecente.modelData.status || "ok"
                        if (st === "sincronizando") return "#4285F4"
                        if (st === "erro") return "#EA4335"
                        if (st === "pausado") return "#FBBC05"
                        if (st === "nuvem") return "#1a73e8"
                        return "#34A853" // ok / disponível offline
                      }

                      Text {
                        anchors.centerIn: parent
                        text: {
                          var st = itemRecente.modelData.status || "ok"
                          if (st === "sincronizando") return "\u{F046A}" // Setas circulares
                          if (st === "erro") return "\u{F0156}" // X
                          if (st === "pausado") return "\u{F03E4}" // Pausa
                          if (st === "nuvem") return "\u{F0708}" // Nuvem
                          return "\u{F012C}" // Check verde
                        }
                        color: (itemRecente.modelData.status === "pausado") ? "#1f1f1f" : "#ffffff"
                        font.family: root.fonte
                        font.pixelSize: 11

                        RotationAnimation on rotation {
                          running: itemRecente.modelData.status === "sincronizando"
                          from: 0
                          to: 360
                          duration: 1600
                          loops: Animation.Infinite
                        }
                      }
                    }
                  }

                  // 2. Nome, Pasta e Barra de Progresso
                  Column {
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - caixaIconeStatus.width - tagRecente.implicitWidth - 24
                    spacing: 2

                    Text {
                      width: parent.width
                      text: itemRecente.modelData.nome || ""
                      color: "#ededee"
                      font.family: root.fonte
                      font.pixelSize: 13
                      font.weight: Font.Medium
                      elide: Text.ElideRight
                    }

                    Text {
                      width: parent.width
                      text: {
                        var p = itemRecente.modelData.pasta || ""
                        if (itemRecente.modelData.status === "sincronizando") {
                          return (p ? p + " · " : "") + I18n.t("Enviando alterações…")
                        }
                        return p
                      }
                      color: (itemRecente.modelData.status === "sincronizando") ? "#8fb4e8" : "#77777e"
                      font.family: root.fonte
                      font.pixelSize: 11
                      elide: Text.ElideRight
                    }

                    // Barra de progresso para itens que estão fazendo upload
                    Item {
                      width: parent.width
                      height: 3
                      visible: itemRecente.modelData.status === "sincronizando"

                      Rectangle {
                        anchors.fill: parent
                        radius: 1.5
                        color: Qt.rgba(1, 1, 1, 0.1)

                        Rectangle {
                          height: parent.height
                          radius: 1.5
                          color: "#4285F4"
                          width: Math.max(8, parent.width * Math.min(1.0, (itemRecente.modelData.progresso_pct || 65) / 100))
                          Behavior on width { NumberAnimation { duration: 250 } }
                        }
                      }
                    }
                  }

                  // 3. Rótulo de Estado
                  Text {
                    id: tagRecente
                    anchors.verticalCenter: parent.verticalCenter
                    text: itemRecente.modelData.estado || ""
                    color: {
                      var st = itemRecente.modelData.status || "ok"
                      if (st === "sincronizando") return "#4285F4"
                      if (st === "erro") return "#EA4335"
                      if (st === "pausado") return "#FBBC05"
                      return "#77777e"
                    }
                    font.family: root.fonte
                    font.pixelSize: 11
                    horizontalAlignment: Text.AlignRight
                  }
                }

                MouseArea {
                  id: areaRecente
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: {
                    if (itemRecente.modelData.caminho) {
                      Quickshell.execDetached(["xdg-open", itemRecente.modelData.caminho])
                      painelSync.fechar()
                    }
                  }
                  onWheel: function(wheel) {
                    if (listaRecentes.contentHeight > listaRecentes.height) {
                      listaRecentes.contentY = Math.max(0, Math.min(listaRecentes.contentHeight - listaRecentes.height, listaRecentes.contentY - wheel.angleDelta.y))
                    }
                    wheel.accepted = true
                  }
                }
              }
            }

            // Scrollbar vertical suave
            Rectangle {
              id: barraScroll
              anchors.right: parent.right
              anchors.top: parent.top
              anchors.bottom: parent.bottom
              anchors.rightMargin: 1
              width: 3
              radius: 1.5
              color: "transparent"
              visible: listaRecentes.contentHeight > listaRecentes.height

              Rectangle {
                width: 3
                radius: 1.5
                color: Qt.rgba(1, 1, 1, 0.28)
                y: Math.max(0, Math.min(barraScroll.height - height, listaRecentes.visibleArea.yPosition * barraScroll.height))
                height: Math.max(20, listaRecentes.visibleArea.heightRatio * barraScroll.height)
              }
            }

            Text {
              visible: !root.syncData || !root.syncData.recentes || root.syncData.recentes.length === 0
              anchors.centerIn: parent
              text: I18n.t("Nenhum arquivo recente")
              color: "#77777e"
              font.family: root.fonte
              font.pixelSize: 12
            }
          }

          // 4. Botões de Ação ("Abrir pasta" e "Ver no Drive")
          Row {
            width: parent.width
            spacing: 8

            Rectangle {
              width: (parent.width - 8) / 2
              height: 34
              radius: 8
              color: areaBtnPasta.pressed ? Qt.rgba(1, 1, 1, 0.05) : (areaBtnPasta.containsMouse ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(1, 1, 1, 0.08))
              Behavior on color { ColorAnimation { duration: 100 } }

              Text {
                anchors.centerIn: parent
                text: I18n.t("Abrir pasta")
                color: "#ededee"
                font.family: root.fonte
                font.pixelSize: 13
                font.weight: Font.DemiBold
              }

              MouseArea {
                id: areaBtnPasta
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                  // ~/Simba Conta: atalhos para tudo o que é sincronizado (como a pasta do OneDrive)
                  Quickshell.execDetached(["conta", "abrir-pasta"])
                  painelSync.fechar()
                }
              }
            }

            Rectangle {
              width: (parent.width - 8) / 2
              height: 34
              radius: 8
              color: areaBtnDrive.pressed ? Qt.rgba(1, 1, 1, 0.05) : (areaBtnDrive.containsMouse ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(1, 1, 1, 0.08))
              Behavior on color { ColorAnimation { duration: 100 } }

              Text {
                anchors.centerIn: parent
                text: I18n.t("Ver no Drive")
                color: "#ededee"
                font.family: root.fonte
                font.pixelSize: 13
                font.weight: Font.DemiBold
              }

              MouseArea {
                id: areaBtnDrive
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                  Quickshell.execDetached(["xdg-open", "https://drive.google.com/drive/search?q=%22Simba%20Conta%22"])
                  painelSync.fechar()
                }
              }
            }
          }

          // 5. Rodapé ("Pausar" / "Retomar" e "Configurações")
          Item {
            width: parent.width
            height: 36

            Rectangle {
              anchors.top: parent.top
              anchors.left: parent.left
              anchors.right: parent.right
              height: 1
              color: Qt.rgba(1, 1, 1, 0.07)
            }

            Rectangle {
              anchors.left: parent.left
              anchors.verticalCenter: parent.verticalCenter
              anchors.verticalCenterOffset: 2
              height: 28
              width: txtPausar.implicitWidth + 14
              radius: 6
              color: areaBtnPausar.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent"

              Text {
                id: txtPausar
                anchors.centerIn: parent
                text: root.syncPausado ? I18n.t("Retomar") : I18n.t("Pausar")
                color: areaBtnPausar.containsMouse ? "#ededee" : "#a7a7ad"
                font.family: root.fonte
                font.pixelSize: 13
                font.weight: Font.Medium
              }

              MouseArea {
                id: areaBtnPausar
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                  if (root.syncPausado) {
                    Quickshell.execDetached(["conta", "retomar"])
                  } else {
                    Quickshell.execDetached(["conta", "pausar", "24"])
                  }
                  root.atualizarSync()
                }
              }
            }

            Rectangle {
              anchors.right: parent.right
              anchors.verticalCenter: parent.verticalCenter
              anchors.verticalCenterOffset: 2
              height: 28
              width: txtCfg.implicitWidth + 14
              radius: 6
              color: areaBtnCfg.containsMouse ? Qt.rgba(1, 1, 1, 0.06) : "transparent"

              Text {
                id: txtCfg
                anchors.centerIn: parent
                text: I18n.t("Configurações")
                color: areaBtnCfg.containsMouse ? "#ededee" : "#a7a7ad"
                font.family: root.fonte
                font.pixelSize: 13
                font.weight: Font.Medium
              }

              MouseArea {
                id: areaBtnCfg
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                  Quickshell.execDetached(["configuracoes", "contas"])
                  painelSync.fechar()
                }
              }
            }
          }
        }
      }
    }
  }
}
