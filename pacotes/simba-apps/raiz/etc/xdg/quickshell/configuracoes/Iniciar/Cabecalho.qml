import QtQuick
import qs.Comum

// Título de seção ("Fixado", "Recomendado") com botão à direita ("Todos ›").
Item {
  id: h
  property string titulo: ""
  property string botao: ""
  property bool voltar: false        // botão "‹ Voltar" (seta à esquerda)
  signal clicado()
  height: 32
  Texto { anchors.verticalCenter: parent.verticalCenter; text: h.titulo; font.pixelSize: Tema.tSubtitulo; font.weight: Font.DemiBold }
  Rectangle {
    visible: !!h.botao
    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
    height: 26; width: rot.implicitWidth + 30; radius: 5
    color: ab.pressed ? Tema.pressionado : (ab.containsMouse ? Tema.superficieMax : Tema.alfa(Tema.texto, Tema.escuro ? 0.07 : 0.05))
    border.width: 1; border.color: Tema.linha
    Row {
      anchors.centerIn: parent
      spacing: 4
      Glifo { visible: h.voltar; g: Icones.chevronLeft; tamanho: 12; anchors.verticalCenter: parent.verticalCenter }
      Texto { id: rot; text: h.botao; font.pixelSize: Tema.tLegenda + 1; anchors.verticalCenter: parent.verticalCenter }
      Glifo { visible: !h.voltar; g: Icones.chevronRight; tamanho: 12; anchors.verticalCenter: parent.verticalCenter }
    }
    MouseArea { id: ab; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: h.clicado() }
  }
}
