import QtQuick
import Quickshell
import Quickshell.Wayland
import qs.Comum

// "Identificar": a big number on every screen for a moment (numbers follow the
// left-to-right order used in Configurações › Tela).
Scope {
  id: id_
  property bool ativo: false
  property var ordem: []   // output names, left to right
  function mostrar(nomes) {
    ordem = nomes && nomes.length ? nomes : Quickshell.screens.slice().sort(function(a, b) { return a.x - b.x || a.y - b.y }).map(function(s) { return s.name })
    ativo = true
    fim.restart()
  }
  Timer { id: fim; interval: 2600; onTriggered: id_.ativo = false }

  Variants {
    model: id_.ativo ? Quickshell.screens : []
    delegate: PanelWindow {
      required property var modelData
      screen: modelData
      anchors { left: true; bottom: true }
      margins { left: 40; bottom: 40 }
      implicitWidth: 220
      implicitHeight: 200
      color: "transparent"
      exclusionMode: ExclusionMode.Ignore
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.namespace: "configuracoes-identificar"
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.None
      Rectangle {
        anchors.fill: parent
        radius: Tema.raioGrande + 6
        color: Tema.alfa(Tema.janela, 0.92)
        border.width: 2
        border.color: Tema.realce
        scale: 0.6; opacity: 0
        Component.onCompleted: { scale = 1; opacity = 1 }
        Behavior on scale { NumberAnimation { duration: Tema.lento; easing.type: Easing.OutBack } }
        Behavior on opacity { NumberAnimation { duration: Tema.medio } }
        Texto {
          anchors.centerIn: parent
          anchors.verticalCenterOffset: -12
          text: String(Math.max(1, id_.ordem.indexOf(modelData.name) + 1))
          font.pixelSize: 110
          font.weight: Font.Black
        }
        Texto {
          anchors.bottom: parent.bottom
          anchors.bottomMargin: 16
          anchors.horizontalCenter: parent.horizontalCenter
          text: modelData.name + " · " + modelData.width + "×" + modelData.height
          color: Tema.texto2
          font.pixelSize: Tema.tLegenda + 1
        }
      }
    }
  }
}
