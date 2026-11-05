import QtQuick
import Quickshell
import qs.Comum

// Tela cheia: pesquisa no alto e todos os apps em grade grande (fixados primeiro).
// Clicar no vazio ou Esc fecha.
Item {
  id: e
  property var menu
  readonly property int celula: 132
  readonly property int colunas: Math.max(4, Math.min(9, Math.floor((width - 160) / celula)))

  CampoBusca { id: busca; menu: e.menu; width: Math.min(620, parent.width - 80); anchors.horizontalCenter: parent.horizontalCenter; y: 48; height: 44 }

  Resultados {
    visible: !!e.menu.texto
    width: Math.min(980, parent.width - 80)
    anchors { horizontalCenter: parent.horizontalCenter; top: busca.bottom; topMargin: 28; bottom: parent.bottom; bottomMargin: 90 }
    menu: e.menu
  }

  Flickable {
    id: rol
    visible: !e.menu.texto
    width: e.colunas * e.celula
    anchors { horizontalCenter: parent.horizontalCenter; top: busca.bottom; topMargin: 28; bottom: parent.bottom; bottomMargin: 80 }
    clip: true
    contentHeight: col.implicitHeight
    boundsBehavior: Flickable.StopAtBounds
    Column {
      id: col
      width: rol.width
      spacing: 8
      Texto { text: I18n.t("Fixado"); font.pixelSize: Tema.tTitulo; font.weight: Font.DemiBold; visible: e.menu.fixados.length > 0 }
      Grid {
        columns: e.colunas
        Repeater {
          model: e.menu.fixados
          delegate: Bloco { required property string modelData; menu: e.menu; entrada: e.menu.app(modelData); width: e.celula; height: 118; icone: 56 }
        }
      }
      Item { width: 1; height: 12 }
      Texto { text: I18n.t("Todos os aplicativos"); font.pixelSize: Tema.tTitulo; font.weight: Font.DemiBold }
      Grid {
        columns: e.colunas
        Repeater {
          model: e.menu.apps
          delegate: Bloco { required property var modelData; menu: e.menu; entrada: modelData; width: e.celula; height: 118; icone: 56 }
        }
      }
    }
  }

  // usuário e energia, no canto de baixo
  Row {
    anchors { right: parent.right; bottom: parent.bottom; margins: 28 }
    spacing: 8
    Rectangle {
      height: 44; width: linhaU.implicitWidth + 20; radius: 8
      color: au.containsMouse ? Tema.hover : "transparent"
      Row {
        id: linhaU
        anchors.verticalCenter: parent.verticalCenter; x: 10; spacing: 10
        Avatar { width: 30; height: 30; redondo: true; nome: e.menu.nomeUsuario; anchors.verticalCenter: parent.verticalCenter }
        Texto { text: e.menu.nomeUsuario; anchors.verticalCenter: parent.verticalCenter }
      }
      MouseArea { id: au; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: e.menu.abrirConfig("contas") }
    }
    Rectangle {
      id: bEn
      width: 44; height: 44; radius: 8
      color: ae.containsMouse ? Tema.hover : "transparent"
      Glifo { anchors.centerIn: parent; g: Icones.power; tamanho: 19 }
      MouseArea { id: ae; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: e.menu.abrirEnergia(bEn, true) }
    }
  }
}
