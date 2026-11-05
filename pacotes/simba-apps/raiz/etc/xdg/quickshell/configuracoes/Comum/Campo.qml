import QtQuick
import QtQuick.Controls.Basic as C
import qs.Comum

// Text field with optional leading glyph and a clear button.
C.TextField {
  id: r
  property string glifo: ""
  property string dica: ""
  implicitHeight: 34
  implicitWidth: 220
  color: Tema.texto
  placeholderText: dica
  placeholderTextColor: Tema.texto3
  selectionColor: Tema.alfa(Tema.realce, 0.4)
  selectedTextColor: Tema.texto
  font.family: Tema.fonte
  font.pixelSize: Tema.tCorpo
  leftPadding: glifo ? 34 : 12
  rightPadding: text.length ? 30 : 12
  verticalAlignment: TextInput.AlignVCenter
  Keys.onEscapePressed: function(e) { if (text.length) { text = ""; e.accepted = true } else e.accepted = false }
  background: Rectangle {
    radius: Tema.raioPequeno + 1
    color: r.activeFocus ? Tema.superficie : Tema.superficieAlta
    border.width: 1
    border.color: r.activeFocus ? Tema.realce : (hov.hovered ? Tema.linhaForte : Tema.linha)
    Behavior on border.color { ColorAnimation { duration: Tema.rapido } }
    Rectangle {
      visible: r.activeFocus
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      anchors.margins: 1
      height: 2
      color: Tema.realce
    }
    HoverHandler { id: hov }
  }
  Glifo {
    visible: r.glifo !== ""
    g: r.glifo
    tamanho: 15
    color: r.activeFocus ? Tema.texto : Tema.texto3
    x: 9
    anchors.verticalCenter: parent.verticalCenter
  }
  Glifo {
    visible: r.text.length > 0
    g: Icones.close
    tamanho: 13
    color: limpar.containsMouse ? Tema.texto : Tema.texto3
    anchors.right: parent.right
    anchors.rightMargin: 6
    anchors.verticalCenter: parent.verticalCenter
    MouseArea { id: limpar; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: { r.text = ""; r.forceActiveFocus() } }
  }
}
