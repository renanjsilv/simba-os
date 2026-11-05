import QtQuick
import qs.Comum

// Bloco de app de grade (ícone em cima, nome embaixo), como os fixados do Windows 11.
Item {
  id: b
  property var menu
  property var entrada: null          // DesktopEntry
  property int icone: 32
  property bool quadrado: false       // estilo bloco (compacto): fundo sempre visível
  width: 96; height: 86
  Rectangle {
    anchors.fill: parent
    anchors.margins: 2
    radius: 6
    color: area.pressed ? Tema.pressionado : (area.containsMouse ? Tema.hover : (b.quadrado ? Tema.alfa(Tema.texto, 0.04) : "transparent"))
    border.width: b.quadrado ? 1 : 0
    border.color: Tema.linha
    Behavior on color { ColorAnimation { duration: 90 } }
  }
  Icone {
    id: ic
    anchors.horizontalCenter: parent.horizontalCenter
    y: b.quadrado ? (b.height - b.icone) / 2 - 8 : Math.max(6, (b.height - b.icone - 34) / 2)
    tamanho: b.icone
    fonte: b.menu.iconeApp(b.entrada)
    scale: area.pressed ? 0.9 : 1
    Behavior on scale { NumberAnimation { duration: 90 } }
  }
  Texto {
    anchors { top: ic.bottom; topMargin: 6; left: parent.left; right: parent.right; leftMargin: 4; rightMargin: 4 }
    text: b.entrada ? b.entrada.name : ""
    horizontalAlignment: Text.AlignHCenter
    elide: Text.ElideRight
    // Quebra só entre palavras; uma palavra comprida demais vira "Configuraç…".
    maximumLineCount: b.quadrado || text.indexOf(" ") < 0 ? 1 : 2
    wrapMode: b.quadrado || text.indexOf(" ") < 0 ? Text.NoWrap : Text.WordWrap
    font.pixelSize: Tema.tLegenda
    lineHeight: 0.95
  }
  MouseArea {
    id: area
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    cursorShape: Qt.PointingHandCursor
    onClicked: function(ev) {
      if (!b.entrada) return
      if (ev.button === Qt.RightButton) b.menu.menuApp(b.entrada.id, area, ev.x, ev.y)
      else b.menu.abrirApp(b.entrada.id)
    }
  }
}
