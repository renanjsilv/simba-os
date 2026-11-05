import QtQuick
import QtQuick.Effects
import Quickshell
import qs.Comum

// One desktop icon: themed file icon (or a thumbnail for images), a label that
// stays legible on any wallpaper, Windows-like hover/selection, drag to move,
// double-click to open, right-click for the icon menu.
Item {
  id: ic
  property var item: ({})
  property var superficie: null
  property int ordem: 0
  property var lugar: ({ x: 0, y: 0 })
  readonly property var area: superficie.area
  readonly property var cel: superficie.cel
  readonly property bool selecionado: area.selecao.indexOf(item.caminho) >= 0
  readonly property bool cortado: false

  width: cel.w - 4
  height: cel.h - 4
  x: arrasto.drag.active ? x : lugar.x
  y: arrasto.drag.active ? y : lugar.y
  z: arrasto.drag.active ? 100 : (selecionado ? 2 : 1)
  Behavior on x { enabled: !arrasto.drag.active; NumberAnimation { duration: Tema.lento; easing.type: Easing.OutCubic } }
  Behavior on y { enabled: !arrasto.drag.active; NumberAnimation { duration: Tema.lento; easing.type: Easing.OutCubic } }

  onXChanged: registrar.restart()
  onYChanged: registrar.restart()
  Timer { id: registrar; interval: 400; onTriggered: ic.area.registrar(ic.item.caminho, ic.superficie.nome, ic.lugar.x, ic.lugar.y, ic.width, ic.height) }
  Component.onCompleted: { registrar.restart(); entrada.restart() }

  // Entrance: icons pop in one after another (and again on "Atualizar").
  property real revelado: 0
  opacity: revelado * (arrasto.drag.active ? 0.85 : 1)
  scale: 0.85 + 0.15 * revelado
  SequentialAnimation {
    id: entrada
    PropertyAction { target: ic; property: "revelado"; value: 0 }
    PauseAnimation { duration: Tema.animacoes ? Math.min(ic.ordem, 24) * 18 : 0 }
    NumberAnimation { target: ic; property: "revelado"; to: 1; duration: Tema.animacoes ? 260 : 0; easing.type: Easing.OutBack }
  }
  Connections { target: ic.area; function onVersaoChanged() { entrada.restart() } }

  function fonte() {
    var it = item
    if (it.imagem) return "file://" + it.imagem
    if (it.arquivoIcone) return "file://" + it.arquivoIcone
    var nomes = it.icones || []
    for (var i = 0; i < nomes.length; i++) {
      var n = nomes[i]
      if (!n) continue
      if (n.charAt(0) === "/") return "file://" + n
      var p = Quickshell.iconPath(n, true)
      if (p) return p
    }
    return ""
  }
  readonly property string caminhoIcone: fonte()

  Rectangle {
    id: fundoSel
    anchors.fill: parent
    radius: Math.max(4, Tema.raioPequeno)
    color: ic.selecionado ? Qt.rgba(1, 1, 1, 0.22) : (mouse.containsMouse ? Qt.rgba(1, 1, 1, 0.12) : "transparent")
    border.width: ic.selecionado ? 1 : 0
    border.color: Qt.rgba(1, 1, 1, 0.35)
    Behavior on color { ColorAnimation { duration: 90 } }
  }

  Item {
    id: figura
    width: ic.cel.i
    height: ic.cel.i
    anchors.horizontalCenter: parent.horizontalCenter
    y: 6
    Image {
      id: img
      anchors.fill: parent
      source: ic.caminhoIcone
      sourceSize.width: ic.cel.i * 2
      sourceSize.height: ic.cel.i * 2
      fillMode: Image.PreserveAspectFit
      asynchronous: true
      smooth: true
      mipmap: true
      visible: false
    }
    MultiEffect {
      anchors.fill: img
      source: img
      visible: img.status === Image.Ready
      shadowEnabled: true
      shadowColor: "#000000"
      shadowOpacity: 0.45
      shadowBlur: 0.5
      shadowVerticalOffset: 2
      autoPaddingEnabled: true
    }
    // image thumbnails get a thin photo frame
    Rectangle {
      visible: !!ic.item.imagem && img.status === Image.Ready
      x: (parent.width - img.paintedWidth) / 2 - 1
      y: (parent.height - img.paintedHeight) / 2 - 1
      width: img.paintedWidth + 2
      height: img.paintedHeight + 2
      color: "transparent"
      border.width: 1
      border.color: Qt.rgba(1, 1, 1, 0.7)
    }
    Glifo {
      anchors.centerIn: parent
      visible: img.status !== Image.Ready
      g: ic.item.pasta ? Icones.folder : (ic.item.atalho ? Icones.application : Icones.fileDocumentOutline)
      tamanho: ic.cel.i * 0.8
      color: "white"
    }
    Glifo {
      visible: !!ic.item.link
      anchors.left: parent.left
      anchors.bottom: parent.bottom
      g: Icones.arrowTopRight
      tamanho: Math.max(10, ic.cel.i * 0.28)
      color: "white"
      Rectangle { anchors.fill: parent; z: -1; radius: 2; color: Qt.rgba(0, 0, 0, 0.55) }
    }
  }

  // Label: white with a dark halo (legible on any wallpaper, like Windows).
  Item {
    id: rotulo
    anchors.top: figura.bottom
    anchors.topMargin: 4
    anchors.horizontalCenter: parent.horizontalCenter
    width: parent.width - 6
    height: texto.height
    Text {
      id: sombraTexto
      x: 1; y: 1
      width: parent.width
      text: texto.text
      font: texto.font
      color: Qt.rgba(0, 0, 0, 0.85)
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.Wrap
      maximumLineCount: texto.maximumLineCount
      elide: Text.ElideRight
    }
    Text {
      id: texto
      width: parent.width
      text: ic.item.rotulo || ic.item.nome || ""
      color: "white"
      font.family: Tema.fonte
      font.pixelSize: ic.cel.i >= 64 ? 13 : (ic.cel.i <= 32 ? 11 : 12)
      horizontalAlignment: Text.AlignHCenter
      wrapMode: Text.Wrap
      maximumLineCount: ic.selecionado ? 4 : 2
      elide: Text.ElideRight
      style: Text.Outline
      styleColor: Qt.rgba(0, 0, 0, 0.35)
    }
  }

  MouseArea {
    id: mouse
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    cursorShape: Qt.PointingHandCursor
    property bool moveu: false

    MouseArea {
      id: arrasto
      anchors.fill: parent
      acceptedButtons: Qt.LeftButton
      drag.target: ic.area.automatico ? null : ic
      drag.threshold: 6
      propagateComposedEvents: true
      onPressed: function(m) {
        if (m.modifiers & Qt.ControlModifier) {
          var s = ic.area.selecao.slice()
          var i = s.indexOf(ic.item.caminho)
          if (i >= 0) s.splice(i, 1); else s.push(ic.item.caminho)
          ic.area.selecao = s
        } else if (!ic.selecionado) ic.area.selecao = [ic.item.caminho]
      }
      onReleased: {
        if (drag.active || Math.abs(ic.x - ic.lugar.x) > 3 || Math.abs(ic.y - ic.lugar.y) > 3) {
          ic.superficie.soltarIcone(ic.item, ic.x, ic.y)
          // snap back visually until the new position arrives
          ic.x = Qt.binding(function() { return arrasto.drag.active ? ic.x : ic.lugar.x })
          ic.y = Qt.binding(function() { return arrasto.drag.active ? ic.y : ic.lugar.y })
        }
      }
      onDoubleClicked: ic.area.abrirItem(ic.item.caminho)
    }
    onClicked: function(m) {
      if (m.button !== Qt.RightButton) return
      if (!ic.selecionado) ic.area.selecao = [ic.item.caminho]
      var p = ic.mapToItem(null, m.x, m.y)
      ic.area.abrirMenuItem(ic.superficie.nome, p.x, p.y)
    }
  }
}
