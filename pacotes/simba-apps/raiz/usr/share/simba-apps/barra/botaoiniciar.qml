import QtQuick 6.11
import QtQuick.Window
import Quickshell
import qs.Commons

// Botão Iniciar (no lugar do botão do menu do Simba).
//   clique          menu Iniciar estilo Windows 11 (Configurações › Personalização › Iniciar)
//   botão direito   menu do Simba (como o Win+X do Windows)
// Super+Espaço abre o mesmo menu (hypr/bindings.lua).
Item {
  id: root
  property var bar
  property string moduleName
  property var settings: ({})

  readonly property bool vertical: bar ? bar.vertical : false
  readonly property int barSize: bar ? bar.barSize : 26
  readonly property color fg: bar ? bar.barForeground : Color.foreground

  implicitWidth: vertical ? barSize : barSize + 10
  implicitHeight: vertical ? barSize + 6 : barSize

  Rectangle {
    anchors.fill: parent
    anchors.margins: 2
    radius: 5
    color: fg
    opacity: area.pressed ? 0.16 : (area.containsMouse ? 0.09 : 0)
    Behavior on opacity { NumberAnimation { duration: 100 } }
  }
  // Retrato do Simba OS em pixel art (/usr/share/simba-apps/marca-pixel)
  Item {
    id: simbolo
    anchors.centerIn: parent
    readonly property real lado: Math.round(root.barSize * 0.74)
    width: lado; height: lado
    scale: area.pressed ? 0.85 : (area.containsMouse ? 1.06 : 1)
    Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
    Image {
      anchors.fill: parent
      source: "file:///usr/share/simba-apps/marca-pixel/retrato-144.png"
      fillMode: Image.PreserveAspectFit
      smooth: true
      mipmap: true
    }
  }
  // Lei de Fitts: o clique vale até o canto da tela (como no Windows). A área
  // de clique se estende para fora do botão até as bordas da janela da barra.
  property point origem: Qt.point(0, 0)
  function medir() {
    var p = root.mapToItem(null, 0, 0)
    origem = Qt.point(Math.max(0, p.x), Math.max(0, p.y))
  }
  Component.onCompleted: {
    if (parent) parent.z = 60 // acima do MouseArea de arrastar módulos da barra
    Qt.callLater(medir)
  }
  // a posição final só existe depois do layout da barra: confere de tempos em tempos
  Timer { interval: 400; running: true; repeat: true; onTriggered: { root.medir(); if (++n > 10) interval = 3000 } property int n: 0 }
  onXChanged: Qt.callLater(medir)
  onWidthChanged: Qt.callLater(medir)
  Connections {
    target: root.Window.window
    function onWidthChanged() { Qt.callLater(root.medir) }
    function onHeightChanged() { Qt.callLater(root.medir) }
  }

  // Filho do conteúdo da janela da barra (fora dos limites do módulo o Qt não entrega
  // eventos a filhos): cobre do canto da tela até a borda direita do botão.
  MouseArea {
    id: area
    parent: root.Window.window ? root.Window.window.contentItem : root
    z: 1000
    x: parent === root ? 0 : 0
    y: parent === root ? 0 : 0
    width: parent === root ? root.width : root.origem.x + root.width
    height: parent === root ? root.height : Math.max(root.origem.y + root.height, parent.height)
    hoverEnabled: true
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    onClicked: function(m) {
      if (m.button === Qt.RightButton)
        Quickshell.execDetached(["simba-shell", "shell", "toggle", "simba.menu", '{"menu":"root"}'])
      else
        Quickshell.execDetached(["/usr/bin/configuracoes", "menu-iniciar"])
    }
  }
}
