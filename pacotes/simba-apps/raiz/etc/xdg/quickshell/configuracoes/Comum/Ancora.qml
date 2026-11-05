import QtQuick
import QtQuick.Layouts
import qs.Comum

// Search target for things that are not a single row (theme grid, wallpaper
// gallery): scrolls into view and sweeps an accent line when opened from search.
Item {
  id: a
  property string chave: ""
  Layout.fillWidth: true
  implicitHeight: 2
  readonly property bool emDestaque: chave !== "" && Navegacao.destaque === chave
  function rolar() {
    var f = a.parent
    while (f && !(f.contentY !== undefined && f.contentHeight !== undefined)) f = f.parent
    if (!f) return
    var p = a.mapToItem(f.contentItem, 0, 0)
    f.contentY = Math.max(0, Math.min(p.y - 90, f.contentHeight - f.height))
  }
  Connections { target: Navegacao; function onPulsoChanged() { if (a.emDestaque) atraso.restart() } }
  Component.onCompleted: if (emDestaque) atraso.restart()
  Timer { id: atraso; interval: 260; onTriggered: { a.rolar(); varrer.restart() } }
  Rectangle {
    id: barra
    height: 2
    radius: 1
    color: Tema.realce
    width: 0
    opacity: 0
    SequentialAnimation {
      id: varrer
      PropertyAction { target: barra; property: "opacity"; value: 1 }
      NumberAnimation { target: barra; property: "width"; from: 0; to: a.width; duration: 650; easing.type: Easing.OutCubic }
      PauseAnimation { duration: 900 }
      NumberAnimation { target: barra; property: "opacity"; to: 0; duration: 600 }
    }
  }
}
