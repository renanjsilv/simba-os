// Complementos dos botões de janela (estilo Windows 11, ~/.config/hypr/janelas.lua):
// menu de layouts de encaixe (mouse parado no maximizar, Super+Z) e "Mostrar área de
// trabalho" no canto da tela.
//
// Os botões minimizar · maximizar · fechar de cada janela são do próprio Hyprland desde
// 2026-11-04: plugin janelas-nativo (~/.local/share/janelas-nativo) desenha a barra de título
// nos apps que pedem decoração do servidor e faz funcionar os botões nativos dos apps que
// desenham os seus (GTK, Chromium, Electron). As camadas por cima das janelas e o detector
// bin/decorado saíram (backup shell.qml.bak-nativo).
//
// Roda como serviço: systemctl --user restart botoes-janela
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland

ShellRoot {
  id: root

  readonly property string especial: "special:minimizadas"
  readonly property string home: Quickshell.env("HOME")

  // ---------- tema (cores do Simba, recarregadas ao trocar de tema) ----------
  property var cores: ({})
  readonly property color fundo: cores.background || "#000000"
  readonly property color frente: cores.foreground || "#ffffff"
  readonly property color realce: cores.accent || "#8d8d8d"
  readonly property color perigo: cores.red || "#e06c75"
  readonly property bool claro: (cores.mode || "dark") === "light"

  FileView {
    id: arquivoCores
    path: root.home + "/.local/state/simba/current/theme/colors.toml"
    watchChanges: true
    onFileChanged: reload()
    onLoadFailed: novaLeitura.restart()
    onLoaded: {
      const c = {}
      for (const linha of text().split("\n")) {
        const m = linha.match(/^\s*([a-z_]+)\s*=\s*"([^"]*)"/)
        if (m) c[m[1]] = m[2]
      }
      root.cores = c
    }
  }

  // simba-theme-set reescreve theme.name por último, depois de trocar a pasta do tema
  FileView {
    path: root.home + "/.local/state/simba/current/theme.name"
    watchChanges: true
    onFileChanged: { reload(); arquivoCores.reload() }
  }
  Timer { id: novaLeitura; interval: 500; onTriggered: arquivoCores.reload() }

  // ---------- regras por classe ----------
  property var regras: ({ mostrar: [], ocultar: ocultarPadrao })
  // Apps do Simba que desenham os próprios botões de janela: nunca ganham os daqui
  // (valem mesmo sem config.json, ex. numa instalação nova).
  readonly property var ocultarPadrao: ["^com\\.simba\\.Configuracoes$"]
  FileView {
    path: root.home + "/.config/botoes-janela/config.json"
    watchChanges: true
    onFileChanged: reload()
    onLoaded: {
      try {
        const j = JSON.parse(text())
        root.regras = { mostrar: j.mostrar || [], ocultar: root.ocultarPadrao.concat(j.ocultar || []) }
      } catch (e) {
        root.regras = { mostrar: [], ocultar: root.ocultarPadrao }
      }
      root.recalcular()
    }
  }

  function casa(lista, classe) {
    for (const r of lista) {
      try { if (new RegExp(r).test(classe)) return true } catch (e) {}
    }
    return false
  }

  // ---------- janelas ----------
  property var janelas: ({})      // address → {x, y, w, h, monitor, ...} das janelas que ganham botões
  property var enderecos: []      // chaves de janelas, estáveis para o Variants
  property var minimizadas: []    // [{address, classe, titulo}]

  function recalcular() {
    const ativos = {}             // nomes das workspaces visíveis
    for (const m of Hyprland.monitors.values) {
      const o = m.lastIpcObject || {}
      if (o.specialWorkspace && o.specialWorkspace.name) ativos[o.specialWorkspace.name] = m.name
      else if (o.activeWorkspace) ativos[o.activeWorkspace.name] = m.name
    }

    const mins = []
    const novas = {}
    for (const t of Hyprland.toplevels.values) {
      const o = t.lastIpcObject
      if (!o || !o.workspace || !o.mapped) continue
      if (o.workspace.name === root.especial) {
        mins.push({ address: o.address, classe: o.class || "", titulo: o.title || o.class || "Janela" })
        continue
      }
      if (!(o.workspace.name in ativos) || o.hidden || o.fullscreen === 2) continue
      const classe = o.class || ""
      const tags = (o.tags || []).map(t => t.replace(/\*$/, ""))
      novas[o.address] = {
        x: o.at[0], y: o.at[1], w: o.size[0], h: o.size[1],
        monitor: ativos[o.workspace.name], ativa: o.focusHistoryID === 0, classe: classe,
        // barra de título desenhada pelo Hyprland (plugin janelas-nativo marca a janela)
        barra: tags.indexOf("janelas-barra") >= 0,
      }
    }
    root.janelas = novas
    const lista = Object.keys(novas).sort()
    if (JSON.stringify(lista) !== JSON.stringify(root.enderecos)) root.enderecos = lista
    root.minimizadas = mins
  }

  // Centro do botão maximizar de cada janela (âncora do menu de layouts no Super+Z):
  // barra do Hyprland = 46 px por botão, o maximizar é o do meio; apps com botões
  // próprios (GTK, Chromium...) ficam mais ou menos no mesmo lugar.
  function pontoMaximizar(j) {
    if (j.barra) return { x: j.x + j.w - 69, y: j.y }
    return { x: j.x + j.w - 60, y: j.y + 40 }
  }


  function despachar(cmd) { Hyprland.dispatch(cmd) }

  function minimizar(addr) {
    despachar(`hl.dsp.window.move({ workspace = "${root.especial}", follow = false, window = "address:${addr}" })`)
    atualizarLogo()
  }
  function maximizar(addr) {
    despachar(`janelas.alternar("${addr}")`)
    atualizarLogo()
  }
  function encaixar(addr, zonas, n) {
    despachar(`janelas.encaixar("${addr}", "${zonas.map(z => z.join(" ")).join(";")}", ${n})`)
    // Com follow_mouse, ao sumir o menu o cursor cai em outra janela e leva o foco: devolve.
    focoAdiado.endereco = addr
    focoAdiado.interval = 180
    focoAdiado.restart()
    atualizarLogo()
  }
  function fechar(addr) {
    despachar(`hl.dsp.window.close({ window = "address:${addr}" })`)
    atualizarLogo()
  }
  function restaurar(addr) {
    const ws = Hyprland.focusedMonitor && Hyprland.focusedMonitor.activeWorkspace
      ? Hyprland.focusedMonitor.activeWorkspace.name : "1"
    despachar(`hl.dsp.window.move({ workspace = "${ws}", follow = false, window = "address:${addr}" })`)
    focoAdiado.endereco = addr
    focoAdiado.restart()
    atualizarLogo()
  }

  // O foco só pega depois que a janela chegou na workspace.
  Timer {
    id: focoAdiado
    property string endereco: ""
    interval: 120
    onTriggered: { root.despachar(`foco.janela("${endereco}")`); interval = 120 }
  }

  function atualizarLogo() { atraso.restart() }

  Timer {
    id: atraso
    interval: 60
    onTriggered: { Hyprland.refreshToplevels(); Hyprland.refreshMonitors() }
  }
  // O Hyprland não emite evento ao redimensionar janelas flutuantes: um pulso leve cobre isso.
  Timer {
    interval: 900; running: true; repeat: true
    onTriggered: { Hyprland.refreshToplevels(); Hyprland.refreshMonitors() }
  }

  Connections {
    target: Hyprland
    function onRawEvent(ev) {
      switch (ev.name) {
        case "openwindow": case "closewindow": case "movewindowv2": case "changefloatingmode":
        case "fullscreen": case "workspacev2": case "focusedmonv2": case "activespecialv2":
        case "activewindowv2": case "monitoraddedv2": case "monitorremovedv2":
          root.atualizarLogo()
      }
    }
  }
  // Os objetos IPC chegam depois do refresh: recalcula quando qualquer um muda.
  Instantiator {
    model: Hyprland.toplevels
    delegate: Connections {
      required property var modelData
      target: modelData
      function onLastIpcObjectChanged() { recalculo.restart() }
    }
  }
  Instantiator {
    model: Hyprland.monitors
    delegate: Connections {
      required property var modelData
      target: modelData
      function onLastIpcObjectChanged() { recalculo.restart() }
    }
  }
  Timer { id: recalculo; interval: 16; onTriggered: root.recalcular() }

  function tela(nome) {
    for (const s of Quickshell.screens) if (s.name === nome) return s
    return null
  }

  // Os botões de cada janela agora são do próprio Hyprland (plugin janelas-nativo,
  // ~/.local/share/janelas-nativo): barra de título nos apps sem decoração própria e os
  // botões nativos dos apps (GTK, Chromium...) funcionando pelo protocolo.

  component Botao: Rectangle {
    id: botao
    property string dica
    property bool perigoso: false
    property bool invisivel: false       // sobre botão nativo: só o realce, translúcido
    readonly property bool sobre: alvo.containsMouse
    readonly property color tinta: alvo.containsMouse && perigoso
      ? (root.claro ? "#ffffff" : root.frente) : root.frente
    signal acionado()

    width: 26; height: 20; radius: 10
    color: alvo.pressed ? Qt.rgba(root.frente.r, root.frente.g, root.frente.b, invisivel ? 0.18 : 0.22)
      : alvo.containsMouse ? (perigoso ? Qt.rgba(root.perigo.r, root.perigo.g, root.perigo.b, invisivel ? 0.55 : 1)
                                       : Qt.rgba(root.frente.r, root.frente.g, root.frente.b, invisivel ? 0.10 : 0.12))
      : "transparent"
    Behavior on color { ColorAnimation { duration: 110 } }

    MouseArea {
      id: alvo
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      onClicked: botao.acionado()
    }
  }

  // ---------- layouts de encaixe (mouse parado no maximizar, como no Windows 11) ----------
  // Cada layout é uma lista de zonas [x, y, largura, altura] em frações da área útil.
  // Clicar numa zona põe a janela nela; as outras zonas recebem as janelas usadas por último.
  readonly property var layouts: [
    [[0, 0, 0.5, 1], [0.5, 0, 0.5, 1]],
    [[0, 0, 0.6667, 1], [0.6667, 0, 0.3333, 1]],
    [[0, 0, 0.3333, 1], [0.3333, 0, 0.3334, 1], [0.6667, 0, 0.3333, 1]],
    [[0, 0, 0.5, 1], [0.5, 0, 0.5, 0.5], [0.5, 0.5, 0.5, 0.5]],
    [[0, 0, 0.5, 0.5], [0.5, 0, 0.5, 0.5], [0, 0.5, 0.5, 0.5], [0.5, 0.5, 0.5, 0.5]],
  ]

  property string snapEndereco: ""
  property var snapPonto: ({ x: 0, y: 0 })
  property string snapMonitor: ""
  property bool snapAberto: false
  property bool sobreBotaoMax: false

  // Prévia do encaixe: zona sob o mouse (layout, zona) e quem vai para as outras —
  // mesma ordem do janelas.lua: apps da mesma área (marca janelas-app) e
  // minimizados, do usado/aberto por último para o mais antigo.
  property int snapLayout: -1
  property int snapZona: -1
  readonly property var snapCandidatas: {
    if (!snapAberto) return []
    const alvo = Hyprland.toplevels.values.find(t => enderecoDe(t) === snapEndereco)
    const ws = alvo && alvo.lastIpcObject && alvo.lastIpcObject.workspace ? alvo.lastIpcObject.workspace.name : ""
    return Hyprland.toplevels.values.map(t => t.lastIpcObject)
      .filter(o => o && o.workspace && o.address !== snapEndereco && o.mapped && o.fullscreen === 0
        && (o.workspace.name === ws || o.workspace.name === especial)
        && (o.tags || []).some(t => t.replace(/\*$/, "") === "janelas-app"))
      .sort((a, b) => a.focusHistoryID - b.focusHistoryID)
      .map(o => o.class || "")
  }
  function classeSnap() {
    const j = root.janelas[root.snapEndereco]
    return j ? j.classe : ""
  }
  // classe do app que cai na zona z do layout l, com a zona `escolhida` para a janela
  function quemVai(l, z, escolhida) {
    if (z === escolhida) return classeSnap()
    let i = 0
    for (let k = 0; k < z; k++) if (k !== escolhida) i++
    return i < snapCandidatas.length ? snapCandidatas[i] : ""
  }
  function iconeDe(classe) {
    if (!classe) return ""
    const e = DesktopEntries.heuristicLookup(classe)
    return e && e.icon ? Quickshell.iconPath(e.icon, true) : ""
  }

  function sobreMaximizar(addr, sobre, ponto, monitor) {
    if (sobre) {
      root.sobreBotaoMax = true
      if (root.snapAberto && root.snapEndereco === addr) { fecharSnap.stop(); return }
      root.snapEndereco = addr
      root.snapPonto = ponto
      root.snapMonitor = monitor
      abrirSnap.restart()
    } else {
      root.sobreBotaoMax = false
      abrirSnap.stop()
      fecharSnap.restart()
    }
  }
  Timer { id: abrirSnap; interval: 450; onTriggered: { root.snapAberto = true; fecharSnap.stop() } }
  onSnapAbertoChanged: if (!snapAberto) fecharSnap.interval = 350
  Timer {
    id: fecharSnap; interval: 350
    onTriggered: if (!root.sobreBotaoMax && !menuSnap.sobre) root.snapAberto = false
  }
  onJanelasChanged: if (root.snapAberto && !(root.snapEndereco in root.janelas)) root.snapAberto = false

  PanelWindow {
    id: menuSnap
    readonly property var mon: Hyprland.monitors.values.find(m => m.name === root.snapMonitor) || null
    readonly property var mo: mon ? mon.lastIpcObject : null
    readonly property real largTela: mo && mo.width ? mo.width / mo.scale : 1366
    readonly property bool sobre: dentroMenu.hovered

    visible: root.snapAberto && mon !== null
    screen: mon ? root.tela(mon.name) : null
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "botoes-janela-snap"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    anchors { top: true; left: true }
    implicitWidth: cartao.width
    implicitHeight: cartao.height + 6
    margins {
      left: mon ? Math.max(6, Math.min(largTela - implicitWidth - 6, root.snapPonto.x - mon.x - implicitWidth / 2)) : 0
      top: mon ? root.snapPonto.y - mon.y + 2 : 0
    }
    onSobreChanged: if (!sobre) fecharSnap.restart()

    HoverHandler { id: dentroMenu }

    Rectangle {
      id: cartao
      y: 6
      width: linha.implicitWidth + 20
      height: linha.implicitHeight + 20
      radius: 12
      color: Qt.rgba(root.fundo.r, root.fundo.g, root.fundo.b, 0.97)
      border.width: 1
      border.color: Qt.rgba(root.frente.r, root.frente.g, root.frente.b, 0.14)

      Row {
        id: linha
        anchors.centerIn: parent
        spacing: 10

        Repeater {
          model: root.layouts
          Item {
            id: miniatura
            required property var modelData
            required property int index
            width: 78; height: 50

            Repeater {
              model: miniatura.modelData
              Rectangle {
                id: zona
                required property var modelData
                required property int index
                x: modelData[0] * miniatura.width + 2
                y: modelData[1] * miniatura.height + 2
                width: modelData[2] * miniatura.width - 4
                height: modelData[3] * miniatura.height - 4
                radius: 4
                readonly property bool mesmoLayout: root.snapLayout === miniatura.index && root.snapZona >= 0
                readonly property string vai: mesmoLayout ? root.quemVai(miniatura.index, index, root.snapZona) : ""
                color: alvoZona.containsMouse ? root.realce
                  : vai !== "" ? Qt.rgba(root.realce.r, root.realce.g, root.realce.b, 0.35)
                  : Qt.rgba(root.frente.r, root.frente.g, root.frente.b, 0.16)
                border.width: 1
                border.color: alvoZona.containsMouse ? root.realce : Qt.rgba(root.frente.r, root.frente.g, root.frente.b, 0.28)
                Behavior on color { ColorAnimation { duration: 90 } }
                Image {
                  anchors.centerIn: parent
                  readonly property int lado: Math.min(18, parent.width - 6, parent.height - 6)
                  width: lado; height: lado
                  sourceSize: Qt.size(36, 36)
                  visible: source != ""
                  source: root.iconeDe(zona.vai)
                }
                MouseArea {
                  id: alvoZona
                  anchors.fill: parent
                  hoverEnabled: true
                  onContainsMouseChanged: {
                    if (containsMouse) { root.snapLayout = miniatura.index; root.snapZona = zona.index }
                    else if (root.snapLayout === miniatura.index && root.snapZona === zona.index) { root.snapLayout = -1; root.snapZona = -1 }
                  }
                  cursorShape: Qt.PointingHandCursor
                  onClicked: {
                    root.snapAberto = false
                    root.encaixar(root.snapEndereco, miniatura.modelData, zona.index + 1)
                  }
                }
              }
            }
          }
        }
      }
    }
  }

  // ---------- chip "N minimizadas" + lista para restaurar ----------
  PanelWindow {
    id: chip
    property bool listaAberta: false
    readonly property var mon: Hyprland.focusedMonitor

    // Desligado: a barra de tarefas já mostra e restaura as minimizadas.
    visible: false
    screen: mon ? root.tela(mon.name) : null
    color: "transparent"
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Top
    WlrLayershell.namespace: "botoes-janela-chip"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
    anchors { bottom: true }
    margins.bottom: 6
    implicitWidth: 360
    implicitHeight: 34 + (listaAberta ? lista.implicitHeight + 8 : 0)
    mask: Region { item: chip.listaAberta ? caixa : botaoChip }
    onVisibleChanged: if (!visible) listaAberta = false

    Item {
      id: caixa
      anchors.fill: parent

      Rectangle {
        id: fundoLista
        visible: chip.listaAberta
        anchors { bottom: botaoChip.top; bottomMargin: 6; horizontalCenter: parent.horizontalCenter }
        width: 340
        height: lista.implicitHeight + 8
        radius: 14
        color: Qt.rgba(root.fundo.r, root.fundo.g, root.fundo.b, 0.96)
        border.width: 1
        border.color: Qt.rgba(root.frente.r, root.frente.g, root.frente.b, 0.12)

        Column {
          id: lista
          anchors { left: parent.left; right: parent.right; top: parent.top; margins: 4 }
          Repeater {
            model: root.minimizadas
            Rectangle {
              id: item
              required property var modelData
              width: lista.width; height: 36; radius: 10
              color: alvoItem.containsMouse ? Qt.rgba(root.frente.r, root.frente.g, root.frente.b, 0.10) : "transparent"
              Image {
                id: icone
                anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
                width: 18; height: 18
                sourceSize: Qt.size(36, 36)
                readonly property var entrada: DesktopEntries.heuristicLookup(item.modelData.classe)
                source: entrada && entrada.icon ? Quickshell.iconPath(entrada.icon, true) : ""
              }
              Text {
                anchors { left: icone.right; leftMargin: 10; right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
                text: item.modelData.titulo
                elide: Text.ElideRight
                color: root.frente
                font.pixelSize: 13
              }
              MouseArea {
                id: alvoItem
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                  root.restaurar(item.modelData.address)
                  if (root.minimizadas.length <= 1) chip.listaAberta = false
                }
              }
            }
          }
        }
      }

      Rectangle {
        id: botaoChip
        anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter }
        height: 26
        width: rotulo.implicitWidth + 30
        radius: 13
        color: Qt.rgba(root.fundo.r, root.fundo.g, root.fundo.b, alvoChip.containsMouse || chip.listaAberta ? 0.94 : 0.6)
        border.width: 1
        border.color: Qt.rgba(root.frente.r, root.frente.g, root.frente.b, 0.12)
        opacity: alvoChip.containsMouse || chip.listaAberta ? 1 : 0.7
        Behavior on color { ColorAnimation { duration: 140 } }
        Behavior on opacity { NumberAnimation { duration: 140 } }

        Text {
          id: rotulo
          anchors.centerIn: parent
          text: root.minimizadas.length === 1 ? "1 janela minimizada" : root.minimizadas.length + " janelas minimizadas"
          color: root.frente
          font.pixelSize: 12
        }
        MouseArea {
          id: alvoChip
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          acceptedButtons: Qt.LeftButton | Qt.MiddleButton
          onClicked: mouse => {
            if (mouse.button === Qt.MiddleButton || root.minimizadas.length === 1) {
              for (const m of root.minimizadas) root.restaurar(m.address)
              chip.listaAberta = false
            } else {
              chip.listaAberta = !chip.listaAberta
            }
          }
        }
      }
    }
  }

  // ---------- "Mostrar área de trabalho" (canto inferior direito, como no Windows 11) ----------
  // Mostrar área de trabalho = Win+D do Windows 11: 1º clique minimiza (manda para
  // special:minimizadas, igual ao botão minimizar) todas as janelas visíveis, sem
  // trocar de workspace; 2º clique devolve as mesmas janelas para onde estavam.
  // As que forem restauradas uma a uma pela barra de tarefas saem da lista.
  // A lista fica em disco para sobreviver a um reinício do serviço.
  property var areaJanelas: []    // [{ address, ws, flutuante, x, y }] na ordem de devolução
  property string areaFoco: ""     // janela que estava em foco
  FileView {
    id: areaEstado
    path: (Quickshell.env("XDG_RUNTIME_DIR") || "/tmp") + "/botoes-janela-area.json"
    printErrors: false
    onLoaded: {
      try { const e = JSON.parse(text()); root.areaJanelas = e.janelas || []; root.areaFoco = e.foco || "" } catch (err) {}
    }
  }
  function guardarArea() { areaEstado.setText(JSON.stringify({ janelas: root.areaJanelas, foco: root.areaFoco })) }

  function enderecoDe(t) { const a = String(t.address || ""); return a.startsWith("0x") ? a : "0x" + a }

  function alternarArea() {
    Hyprland.refreshToplevels()
    const ativas = Hyprland.monitors.values
      .filter(m => m.activeWorkspace && !(m.lastIpcObject && m.lastIpcObject.disabled))
      .map(m => m.activeWorkspace.name)
    const visiveis = Hyprland.toplevels.values.filter(t => {
      const o = t.lastIpcObject
      return o && o.workspace && ativas.indexOf(o.workspace.name) >= 0 && o.mapped !== false
    })

    if (visiveis.length > 0) {
      const ativa = Hyprland.activeToplevel
      if (ativa) root.areaFoco = enderecoDe(ativa)
      // Ordem de devolução: o dwindle divide a janela em foco, então devolver da
      // esquerda para a direita e de cima para baixo refaz o mesmo arranjo.
      const novas = visiveis.map(t => {
        const o = t.lastIpcObject
        return { address: enderecoDe(t), ws: o.workspace.name, flutuante: !!o.floating,
                 x: o.at ? o.at[0] : 0, y: o.at ? o.at[1] : 0 }
      }).sort((a, b) => (a.flutuante - b.flutuante) || (a.x - b.x) || (a.y - b.y))
      const ja = root.areaJanelas.filter(j => !novas.some(n => n.address === j.address))
      root.areaJanelas = ja.concat(novas)
      for (const j of novas) despachar(`hl.dsp.window.move({ workspace = "${root.especial}", follow = false, window = "address:${j.address}" })`)
    } else if (root.areaJanelas.length > 0) {
      const minimizadas = Hyprland.toplevels.values
        .filter(t => t.lastIpcObject && t.lastIpcObject.workspace && t.lastIpcObject.workspace.name === root.especial)
        .map(t => enderecoDe(t))
      for (const j of root.areaJanelas) {
        if (minimizadas.indexOf(j.address) < 0) continue
        despachar(`hl.dsp.window.move({ workspace = "${j.ws}", follow = false, window = "address:${j.address}" })`)
        despachar(`foco.janela("${j.address}")`)
      }
      if (root.areaFoco && minimizadas.indexOf(root.areaFoco) >= 0) despachar(`foco.janela("${root.areaFoco}")`)
      root.areaJanelas = []
      root.areaFoco = ""
    }
    guardarArea()
    atualizarLogo()
  }

  Variants {
    model: Quickshell.screens

    PanelWindow {
      id: canto
      required property var modelData
      screen: modelData
      color: "transparent"
      exclusionMode: ExclusionMode.Ignore
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.namespace: "botoes-janela-area"
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      anchors { bottom: true; right: true }
      // canto do tamanho da barra inteira (antes 7×26: mais baixo que a barra de 35–48 px, o clique
      // no canto alto da barra caía nela e nada acontecia)
      implicitWidth: 12
      implicitHeight: 40

      // linha fina que aparece ao passar o mouse, como o separador do Windows 11
      Rectangle {
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom; topMargin: 5; bottomMargin: 5 }
        width: 1
        color: root.frente
        opacity: alvoCanto.containsMouse ? 0.55 : 0
        Behavior on opacity { NumberAnimation { duration: 120 } }
      }
      MouseArea {
        id: alvoCanto
        anchors.fill: parent
        hoverEnabled: true
        onClicked: root.alternarArea()
      }
    }
  }

  IpcHandler {
    target: "botoes"
    function mostrarArea(): void { root.alternarArea() }
    function atualizar(): void { root.atualizarLogo() }
    // Super+Z: menu de layouts da janela em foco, ancorado no botão maximizar dela
    function layouts(): void {
      const a = Hyprland.activeToplevel
      const addr = a ? root.enderecoDe(a) : ""
      const j = root.janelas[addr]
      if (!j) return
      root.snapEndereco = addr
      root.snapMonitor = j.monitor
      root.snapPonto = root.pontoMaximizar(j)
      root.snapAberto = true
      fecharSnap.interval = 4000
      fecharSnap.restart()
    }
    // Mouse entrou/saiu do botão maximizar da barra do Hyprland (plugin janelas-nativo):
    // parado ali 450 ms abre os layouts de encaixe, como no Windows 11. x, y = centro de
    // baixo do botão, em coordenadas globais.
    function sobreMaximizar(addr: string, sobre: string, x: int, y: int, monitor: string): void {
      if (!(addr in root.janelas) && sobre === "true") return   // janela de outra sessão (teste)
      root.sobreMaximizar(addr, sobre === "true", { x: x, y: y }, monitor !== "-" ? monitor : (root.janelas[addr] || {}).monitor || "")
    }
    function restaurarTodas(): void { for (const m of root.minimizadas) root.restaurar(m.address) }
    function estado(): string {
      return JSON.stringify({ janelas: root.janelas, minimizadas: root.minimizadas,
                              toplevels: Hyprland.toplevels.values.length })
    }
  }
}
