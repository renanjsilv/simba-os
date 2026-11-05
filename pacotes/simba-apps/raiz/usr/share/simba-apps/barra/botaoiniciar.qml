import QtQuick 6.11
import QtQuick.Shapes
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
  // Símbolo do Simba OS (/usr/share/simba-apps/simba-simbolo.svg) em vetor, na cor do tema
  Item {
    id: simbolo
    anchors.centerIn: parent
    readonly property real lado: Math.round(root.barSize * 0.62)
    width: lado; height: lado
    scale: area.pressed ? 0.85 : (area.containsMouse ? 1.06 : 1)
    Behavior on scale { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }
    Shape {
      width: 100; height: 100
      transform: Scale { xScale: simbolo.lado / 100; yScale: simbolo.lado / 100 }
      preferredRendererType: Shape.CurveRenderer
      ShapePath {
        fillColor: root.fg
        strokeWidth: -1
        fillRule: ShapePath.OddEvenFill
        PathSvg {
          path: "M50 92C27 92 12 78 12 58C12 47 15 38 19.5 30.5L17 9.5C16.8 7.6 18.7 6.4 20.3 7.4L37.5 19.6C41.5 18.6 45.7 18 50 18C54.3 18 58.5 18.6 62.5 19.6L79.7 7.4C81.3 6.4 83.2 7.6 83 9.5L80.5 30.5C85 38 88 47 88 58C88 78 73 92 50 92Z "
              + "M26.5 54C31 50.2 38.5 50.4 43.5 56.5C39.5 62.5 31.5 62.8 26.5 54Z M73.5 54C69 50.2 61.5 50.4 56.5 56.5C60.5 62.5 68.5 62.8 73.5 54Z "
              + "M46.8 70H53.2C54.2 70 54.6 71.1 53.9 71.8L50.8 74.6C50.3 75 49.7 75 49.2 74.6L46.1 71.8C45.4 71.1 45.8 70 46.8 70Z"
        }
      }
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
