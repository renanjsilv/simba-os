import QtQuick
import Quickshell
import qs.Comum

// Compacto: trilho de atalhos à esquerda (usuário, pastas, configurações,
// energia), lista de apps com "Mais usados" no meio e blocos fixados à direita.
Item {
  id: e
  property var menu

  // ── trilho ─────────────────────────────────────────────────────────────
  Rectangle {
    id: trilho
    anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
    width: 52
    color: Tema.alfa(Tema.texto, Tema.escuro ? 0.035 : 0.03)
    topLeftRadius: e.menu.cantos; bottomLeftRadius: e.menu.cantos
    Rectangle { anchors.right: parent.right; width: 1; height: parent.height; color: Tema.linha }
    Column {
      anchors { bottom: parent.bottom; bottomMargin: 10; horizontalCenter: parent.horizontalCenter }
      spacing: 4
      Repeater {
        model: [
          { id: "conta", g: "", dica: I18n.t("Conta") },
          { id: "documentos", g: Icones.fileDocument, dica: I18n.t("Documentos") },
          { id: "imagens", g: Icones.image, dica: I18n.t("Imagens") },
          { id: "arquivos", g: Icones.folder, dica: I18n.t("Arquivos") },
          { id: "config", g: Icones.cog, dica: I18n.t("Configurações") },
          { id: "energia", g: Icones.power, dica: I18n.t("Energia") }
        ]
        delegate: Rectangle {
          id: bt
          required property var modelData
          width: 40; height: 40; radius: 6
          color: ab.pressed ? Tema.pressionado : (ab.containsMouse ? Tema.hover : "transparent")
          Glifo { anchors.centerIn: parent; visible: !!bt.modelData.g; g: bt.modelData.g; tamanho: 17 }
          Avatar { anchors.centerIn: parent; visible: bt.modelData.id === "conta"; width: 28; height: 28; redondo: true; nome: e.menu.nomeUsuario }
          MouseArea {
            id: ab
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
              var h = Quickshell.env("HOME")
              switch (bt.modelData.id) {
              case "conta": e.menu.abrirConfig("contas"); break
              case "documentos": e.menu.abrirArquivo(h + "/Documents"); break
              case "imagens": e.menu.abrirArquivo(h + "/Pictures"); break
              case "arquivos": e.menu.abrirArquivo(h); break
              case "config": e.menu.abrirConfig("inicio"); break
              case "energia": e.menu.abrirEnergia(bt, false); break
              }
            }
          }
        }
      }
    }
  }

  // ── lista ──────────────────────────────────────────────────────────────
  Item {
    id: meio
    anchors { left: trilho.right; top: parent.top; bottom: parent.bottom; leftMargin: 12; topMargin: 16; bottomMargin: 12 }
    width: e.menu.texto ? parent.width - trilho.width - 24 : 270
    CampoBusca { id: busca; menu: e.menu; width: parent.width; height: 36; dica: I18n.t("Pesquisar") }
    Resultados { anchors { left: parent.left; right: parent.right; top: busca.bottom; bottom: parent.bottom; topMargin: 12 } visible: !!e.menu.texto; menu: e.menu }
    ListaTodos {
      anchors { left: parent.left; right: parent.right; top: busca.bottom; bottom: parent.bottom; topMargin: 10 }
      visible: !e.menu.texto
      menu: e.menu
      mostrarMaisUsados: e.menu.mostrarMaisUsados
    }
  }

  // ── blocos fixados ─────────────────────────────────────────────────────
  Item {
    visible: !e.menu.texto
    anchors { left: meio.right; right: parent.right; top: parent.top; bottom: parent.bottom; leftMargin: 14; rightMargin: 14; topMargin: 18; bottomMargin: 12 }
    Texto { id: tFix; text: I18n.t("Fixado"); font.pixelSize: Tema.tSubtitulo; font.weight: Font.DemiBold; height: 28 }
    GridView {
      id: blocos
      anchors { top: tFix.bottom; topMargin: 6; left: parent.left; right: parent.right; bottom: parent.bottom }
      cellWidth: Math.floor(width / 3)
      cellHeight: cellWidth
      clip: true
      boundsBehavior: Flickable.StopAtBounds
      model: e.menu.fixados
      delegate: Bloco {
        required property string modelData
        menu: e.menu; entrada: e.menu.app(modelData)
        width: blocos.cellWidth; height: blocos.cellHeight
        quadrado: true; icone: 36
      }
    }
  }
}
