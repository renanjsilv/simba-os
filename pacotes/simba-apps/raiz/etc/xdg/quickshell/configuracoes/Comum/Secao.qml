import QtQuick
import QtQuick.Layouts
import qs.Comum

// Section heading above a card.
ColumnLayout {
  property string titulo: ""
  property string detalhe: ""
  Layout.fillWidth: true
  Layout.topMargin: 18
  Layout.bottomMargin: 2
  spacing: 2
  Texto {
    text: parent.titulo
    font.pixelSize: Tema.tSubtitulo
    font.weight: Font.DemiBold
    Layout.fillWidth: true
  }
  Texto {
    visible: text !== ""
    text: parent.detalhe
    color: Tema.texto3
    font.pixelSize: Tema.tLegenda + 1
    wrapMode: Text.WordWrap
    Layout.fillWidth: true
  }
}
