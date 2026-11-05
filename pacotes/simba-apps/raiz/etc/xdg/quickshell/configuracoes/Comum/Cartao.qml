import QtQuick
import QtQuick.Layouts
import qs.Comum

// Card that groups setting rows (rows draw their own dividers).
Rectangle {
  id: r
  default property alias conteudo: coluna.data
  property int preenchimento: 0
  Layout.fillWidth: true
  implicitHeight: coluna.implicitHeight + preenchimento * 2
  radius: Tema.raioGrande
  color: Tema.superficie
  border.width: 1
  border.color: Tema.linha
  clip: false
  Behavior on color { ColorAnimation { duration: Tema.lento } }
  ColumnLayout {
    id: coluna
    x: r.preenchimento
    y: r.preenchimento
    width: r.width - r.preenchimento * 2
    spacing: 0
  }
}
