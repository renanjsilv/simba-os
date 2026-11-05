import QtQuick
import QtQuick.Layouts
import qs.Comum

// One setting: icon tile, title, description and a control on the right.
// `chave` is the search-index id; when a search result points here the row
// scrolls into view and pulses.
Item {
  id: r
  property string chave: ""
  property string glifo: ""
  property string titulo: ""
  property string descricao: ""
  property bool navegavel: false
  property bool habilitado: true
  property bool expandido: false
  default property alias controle: slot.data
  property alias extra: extraCol.data
  signal clicado()

  Layout.fillWidth: true
  implicitHeight: topo.height + (expandido ? extraCol.implicitHeight + 16 : 0)
  clip: true
  Behavior on implicitHeight { NumberAnimation { duration: Tema.medio; easing.type: Tema.curva } }

  readonly property bool emDestaque: chave !== "" && Navegacao.destaque === chave

  function rolarAteMim() {
    var f = r.parent
    while (f && !(f.contentY !== undefined && f.contentHeight !== undefined)) f = f.parent
    if (!f) return
    var p = r.mapToItem(f.contentItem, 0, 0)
    var alvo = Math.max(0, Math.min(p.y - f.height / 3, f.contentHeight - f.height))
    f.contentY = alvo
  }
  Connections {
    target: Navegacao
    function onPulsoChanged() { if (r.emDestaque) atraso.restart() }
  }
  Component.onCompleted: if (emDestaque) atraso.restart()
  Timer { id: atraso; interval: 260; onTriggered: { r.rolarAteMim(); pulsar.restart() } }

  Rectangle {
    id: fundoPulso
    anchors.fill: parent
    anchors.margins: 1
    radius: Tema.raioGrande
    color: Tema.realce
    opacity: 0
    SequentialAnimation {
      id: pulsar
      NumberAnimation { target: fundoPulso; property: "opacity"; to: 0.16; duration: 200 }
      NumberAnimation { target: fundoPulso; property: "opacity"; to: 0.03; duration: 450 }
      NumberAnimation { target: fundoPulso; property: "opacity"; to: 0.14; duration: 300 }
      NumberAnimation { target: fundoPulso; property: "opacity"; to: 0; duration: 900; easing.type: Easing.InOutSine }
    }
  }

  Rectangle {
    visible: r.y > 0
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.leftMargin: 16
    anchors.rightMargin: 16
    height: 1
    color: Tema.linha
  }

  Item {
    id: topo
    width: parent.width
    height: Math.max(60, textos.implicitHeight + 26)

    Rectangle {
      anchors.fill: parent
      anchors.margins: 2
      radius: Tema.raio
      color: r.navegavel && areaLinha.containsMouse ? Tema.hover : "transparent"
      Behavior on color { ColorAnimation { duration: Tema.rapido } }
    }

    RowLayout {
      anchors.fill: parent
      anchors.leftMargin: 16
      anchors.rightMargin: 16
      spacing: 14
      opacity: r.habilitado ? 1 : 0.45

      Rectangle {
        visible: r.glifo !== ""
        Layout.preferredWidth: 34
        Layout.preferredHeight: 34
        Layout.alignment: Qt.AlignVCenter
        radius: Tema.raioPequeno + 1
        color: Tema.superficieAlta
        border.width: 1
        border.color: Tema.linha
        Glifo { anchors.centerIn: parent; g: r.glifo; tamanho: 17; color: Tema.texto }
      }

      ColumnLayout {
        id: textos
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignVCenter
        spacing: 2
        Texto {
          text: r.titulo
          font.pixelSize: Tema.tCorpo + 1
          font.weight: Font.Medium
          Layout.fillWidth: true
          elide: Text.ElideRight
        }
        Texto {
          visible: r.descricao !== ""
          text: r.descricao
          color: Tema.texto3
          font.pixelSize: Tema.tLegenda + 1
          wrapMode: Text.WordWrap
          Layout.fillWidth: true
          maximumLineCount: 3
          elide: Text.ElideRight
        }
      }

      Row {
        id: slot
        spacing: 8
        Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
      }

      Glifo {
        visible: r.navegavel
        g: r.extra.length ? (r.expandido ? Icones.chevronUp : Icones.chevronDown) : Icones.chevronRight
        tamanho: 16
        color: Tema.texto3
        Layout.alignment: Qt.AlignVCenter
      }
    }

    MouseArea {
      id: areaLinha
      anchors.fill: parent
      z: -1
      enabled: r.navegavel && r.habilitado
      hoverEnabled: true
      cursorShape: r.navegavel ? Qt.PointingHandCursor : Qt.ArrowCursor
      onClicked: r.clicado()
    }
  }

  ColumnLayout {
    id: extraCol
    y: topo.height
    x: 16
    width: parent.width - 32
    spacing: 10
    opacity: r.expandido ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: Tema.medio } }
  }
}
