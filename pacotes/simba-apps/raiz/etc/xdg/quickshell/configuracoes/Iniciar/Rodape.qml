import QtQuick
import Quickshell
import qs.Comum

// Faixa de baixo: usuário (foto da conta Google / inicial) à esquerda; atalhos e
// o botão de energia à direita (menu.abrirEnergia).
Item {
  id: r
  property var menu
  property bool atalhos: true
  height: 64
  readonly property string nome: menu.nomeUsuario
  Rectangle {
    anchors.fill: parent
    color: Tema.alfa(Tema.texto, Tema.escuro ? 0.035 : 0.03)
    bottomLeftRadius: r.menu.cantos; bottomRightRadius: r.menu.cantos
    Rectangle { width: parent.width; height: 1; color: Tema.linha }
  }
  // usuário
  Rectangle {
    id: usuario
    x: 40; anchors.verticalCenter: parent.verticalCenter
    height: 44; width: linhaU.implicitWidth + 20; radius: 6
    color: au.containsMouse ? Tema.hover : "transparent"
    Row {
      id: linhaU
      anchors.verticalCenter: parent.verticalCenter
      x: 10; spacing: 12
      Avatar { width: 32; height: 32; redondo: true; nome: r.nome; anchors.verticalCenter: parent.verticalCenter }
      Texto { text: r.nome; anchors.verticalCenter: parent.verticalCenter }
    }
    MouseArea { id: au; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: r.menu.abrirConfig("contas") }
  }
  Row {
    anchors { right: parent.right; rightMargin: 36; verticalCenter: parent.verticalCenter }
    spacing: 4
    Repeater {
      model: [
        { id: "arquivos", g: Icones.folder, dica: I18n.t("Arquivos"), ver: r.atalhos },
        { id: "config", g: Icones.cog, dica: I18n.t("Configurações"), ver: r.atalhos },
        { id: "energia", g: Icones.power, dica: I18n.t("Energia"), ver: true }
      ].filter(function(b) { return b.ver })
      delegate: Rectangle {
        required property var modelData
        width: 40; height: 40; radius: 6
        color: ab.pressed ? Tema.pressionado : (ab.containsMouse || (modelData.id === "energia" && r.menu.energiaAberta) ? Tema.hover : "transparent")
        Glifo { anchors.centerIn: parent; g: modelData.g; tamanho: 18 }
        MouseArea {
          id: ab
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: {
            if (modelData.id === "energia") r.menu.abrirEnergia(ab, true)
            else if (modelData.id === "config") r.menu.abrirConfig("inicio")
            else { Quickshell.execDetached(["uwsm-app", "--", "xdg-open", Quickshell.env("HOME")]); r.menu.fechar() }
          }
        }
      }
    }
  }
}
