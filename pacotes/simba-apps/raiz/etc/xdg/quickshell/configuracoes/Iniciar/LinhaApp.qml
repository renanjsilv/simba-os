import QtQuick
import qs.Comum

// Linha de lista: ícone + título (+ subtítulo). Serve para apps, arquivos e resultados.
Item {
  id: l
  property var menu
  property string titulo: ""
  property string sub: ""
  property string fonte: ""
  property string glifo: ""
  property string idApp: ""          // app: botão direito abre o menu do app
  property bool selecionada: false
  property int icone: sub ? 32 : 24
  signal ativada()
  height: sub ? 52 : 40
  Rectangle {
    anchors.fill: parent
    radius: 6
    color: area.pressed ? Tema.pressionado : (l.selecionada ? Tema.alfa(Tema.realce, Tema.escuro ? 0.16 : 0.12) : (area.containsMouse ? Tema.hover : "transparent"))
    Rectangle {
      visible: l.selecionada
      width: 3; height: parent.height * 0.45; radius: 2
      anchors.verticalCenter: parent.verticalCenter
      color: Tema.realce
    }
  }
  Icone {
    id: ic
    x: 12
    anchors.verticalCenter: parent.verticalCenter
    tamanho: l.icone
    fonte: l.fonte
    glifo: l.glifo
  }
  Column {
    anchors { left: ic.right; leftMargin: 12; right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
    spacing: 2
    Texto { width: parent.width; text: l.titulo; elide: Text.ElideRight }
    Texto { width: parent.width; visible: !!l.sub; text: l.sub; elide: Text.ElideRight; color: Tema.texto3; font.pixelSize: Tema.tLegenda }
  }
  MouseArea {
    id: area
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    cursorShape: Qt.PointingHandCursor
    onClicked: function(ev) {
      if (ev.button === Qt.RightButton) { if (l.idApp) l.menu.menuApp(l.idApp, area, ev.x, ev.y) }
      else l.ativada()
    }
  }
}
