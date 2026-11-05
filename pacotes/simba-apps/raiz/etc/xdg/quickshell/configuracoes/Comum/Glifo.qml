import QtQuick
import qs.Comum

// One Nerd Font glyph (see Icones.qml), centered in a square box so rows of
// icons line up regardless of each glyph's advance width.
Item {
  id: r
  property string g: ""
  property int tamanho: 16
  property color color: Tema.texto
  implicitWidth: tamanho + 4
  implicitHeight: tamanho + 4
  Behavior on color { ColorAnimation { duration: Tema.medio; easing.type: Tema.curva } }
  Text {
    anchors.centerIn: parent
    text: r.g
    color: r.color
    font.family: Tema.fonte
    font.pixelSize: r.tamanho
    textFormat: Text.PlainText
  }
}
