import QtQuick
import qs.Comum

// Toggle switch. `ligado` is display state; the parent decides what a click
// means through `alternado` (so a failed command never shows a wrong state).
Item {
  id: r
  property bool ligado: false
  property bool habilitado: true
  property bool ocupado: false
  signal alternado(bool valor)

  implicitWidth: 46
  implicitHeight: 26
  opacity: habilitado ? 1 : 0.4
  activeFocusOnTab: habilitado
  Keys.onSpacePressed: if (habilitado) r.alternado(!r.ligado)
  Keys.onReturnPressed: if (habilitado) r.alternado(!r.ligado)

  readonly property real raioTrilho: Tema.raio > 0 ? height / 2 : 3

  Rectangle {
    id: trilho
    anchors.fill: parent
    radius: r.raioTrilho
    color: r.ligado ? Tema.realce : (area.containsMouse ? Tema.hover : "transparent")
    border.width: r.ligado ? 0 : 1.5
    border.color: area.containsMouse ? Tema.texto3 : Tema.linhaForte
    Behavior on color { ColorAnimation { duration: Tema.medio; easing.type: Tema.curva } }
  }

  Rectangle {
    id: botao
    readonly property real base: r.height - 10
    width: area.pressed ? base + 6 : base
    height: base
    radius: Tema.raio > 0 ? height / 2 : 2
    y: 5
    x: r.ligado ? r.width - width - 5 : 5
    color: r.ligado ? Tema.sobreRealce : Tema.texto2
    Behavior on x { NumberAnimation { duration: Tema.medio; easing.type: Easing.OutBack; easing.overshoot: 1.6 } }
    Behavior on width { NumberAnimation { duration: Tema.rapido; easing.type: Tema.curva } }
    Behavior on color { ColorAnimation { duration: Tema.medio } }

    // Busy: a subtle breathing while the backing command runs.
    SequentialAnimation on opacity {
      running: r.ocupado
      loops: Animation.Infinite
      onRunningChanged: if (!running) botao.opacity = 1
      NumberAnimation { to: 0.35; duration: 420; easing.type: Easing.InOutSine }
      NumberAnimation { to: 1; duration: 420; easing.type: Easing.InOutSine }
    }
  }

  Rectangle {
    anchors.fill: parent
    anchors.margins: -3
    radius: r.raioTrilho + 3
    color: "transparent"
    border.width: 1.5
    border.color: Tema.realce
    visible: r.activeFocus
    opacity: 0.6
  }

  MouseArea {
    id: area
    anchors.fill: parent
    anchors.margins: -4
    hoverEnabled: true
    cursorShape: r.habilitado ? Qt.PointingHandCursor : Qt.ArrowCursor
    onClicked: if (r.habilitado && !r.ocupado) r.alternado(!r.ligado)
  }
}
