import QtQuick
import QtQuick.Layouts
import qs.Comum

// Inline notice. tipo: "info" | "aviso" | "perigo"
Rectangle {
  id: r
  property string texto: ""
  property string tipo: "info"
  property string glifo: tipo === "info" ? Icones.informationOutline : Icones.alert
  property alias acoes: acoesRow.data
  Layout.fillWidth: true
  implicitHeight: Math.max(44, corpo.implicitHeight + 22)
  radius: Tema.raio
  readonly property color tom: tipo === "perigo" ? Tema.perigo : (tipo === "aviso" ? Tema.aviso : Tema.realce)
  color: Tema.alfa(tom, 0.09)
  border.width: 1
  border.color: Tema.alfa(tom, 0.28)
  RowLayout {
    id: corpo
    anchors.fill: parent
    anchors.leftMargin: 12
    anchors.rightMargin: 10
    spacing: 10
    Glifo { g: r.glifo; tamanho: 16; color: r.tom; Layout.alignment: Qt.AlignVCenter }
    Texto {
      text: r.texto
      wrapMode: Text.WordWrap
      color: Tema.texto
      Layout.fillWidth: true
      Layout.alignment: Qt.AlignVCenter
    }
    Row { id: acoesRow; spacing: 6; Layout.alignment: Qt.AlignVCenter }
  }
}
