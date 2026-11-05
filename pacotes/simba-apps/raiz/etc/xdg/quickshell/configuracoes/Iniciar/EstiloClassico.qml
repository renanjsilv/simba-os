import QtQuick
import qs.Comum

// Windows 11 original: pesquisa, "Fixado" em grade de 6 × 3 com páginas (rolar
// ou os pontos à direita), "Recomendado" (arquivos recentes) e a faixa do usuário.
// "Todos" troca para a lista alfabética.
Item {
  id: e
  property var menu
  readonly property int colunas: 6
  readonly property int linhas: 3

  CampoBusca { id: busca; menu: e.menu; x: 32; y: 28; width: parent.width - 64 }

  Item {
    id: conteudo
    anchors { left: parent.left; right: parent.right; top: busca.bottom; bottom: rodape.top; leftMargin: 32; rightMargin: 32; topMargin: 20; bottomMargin: 8 }

    Resultados { anchors.fill: parent; visible: !!e.menu.texto; menu: e.menu }

    // ── início ─────────────────────────────────────────────────────────
    Item {
      anchors.fill: parent
      visible: !e.menu.texto && e.menu.pagina === "inicio"

      Cabecalho { id: hFix; width: parent.width; titulo: I18n.t("Fixado"); botao: I18n.t("Todos"); onClicado: e.menu.pagina = "todos" }
      GridView {
        id: grade
        anchors { top: hFix.bottom; topMargin: 6; left: parent.left; right: parent.right; rightMargin: pontos.visible ? 16 : 0 }
        height: e.linhas * cellHeight
        cellWidth: Math.floor(width / e.colunas)
        cellHeight: 88
        clip: true
        interactive: count > e.colunas * e.linhas
        boundsBehavior: Flickable.StopAtBounds
        snapMode: GridView.SnapToRow
        model: e.menu.fixados
        readonly property int paginas: Math.max(1, Math.ceil(count / (e.colunas * e.linhas)))
        readonly property int paginaAtual: Math.round(contentY / height)
        delegate: Bloco { required property string modelData; menu: e.menu; entrada: e.menu.app(modelData); width: grade.cellWidth; height: grade.cellHeight }
        Behavior on contentY { enabled: !grade.moving; NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }
        // roda do mouse = uma página
        WheelHandler {
          onWheel: function(ev) {
            var p = Math.max(0, Math.min(grade.paginas - 1, grade.paginaAtual + (ev.angleDelta.y < 0 ? 1 : -1)))
            grade.contentY = p * grade.height
          }
        }
        Texto {
          anchors.centerIn: parent
          visible: grade.count === 0
          text: I18n.t("Clique com o botão direito num app em “Todos” para fixá-lo aqui")
          color: Tema.texto3; font.pixelSize: Tema.tLegenda
        }
      }
      Column {
        id: pontos
        visible: grade.paginas > 1
        anchors { right: parent.right; verticalCenter: grade.verticalCenter }
        spacing: 8
        Repeater {
          model: grade.paginas
          delegate: Rectangle {
            required property int index
            width: 6; height: index === grade.paginaAtual ? 14 : 6; radius: 3
            color: index === grade.paginaAtual ? Tema.texto : Tema.texto3
            Behavior on height { NumberAnimation { duration: 150 } }
            MouseArea { anchors.fill: parent; anchors.margins: -4; onClicked: grade.contentY = index * grade.height }
          }
        }
      }

      Cabecalho {
        id: hRec
        visible: e.menu.mostrarRecentes
        anchors { top: grade.bottom; topMargin: 18 }
        width: parent.width
        titulo: I18n.t("Recomendado")
        botao: e.menu.recentes.length > 6 ? I18n.t("Mais") : ""
        onClicado: e.menu.pagina = "recomendado"
      }
      Grid {
        id: recs
        visible: e.menu.mostrarRecentes
        anchors { top: hRec.bottom; topMargin: 6; left: parent.left; right: parent.right }
        columns: 2
        columnSpacing: 8
        rowSpacing: 2
        Repeater {
          model: e.menu.recentes.slice(0, 6)
          delegate: LinhaApp {
            required property var modelData
            width: (recs.width - 8) / 2
            menu: e.menu
            titulo: modelData.nome
            sub: e.menu.quando(modelData.quando)
            fonte: e.menu.caminhoIcone(modelData.icone)
            onAtivada: e.menu.abrirArquivo(modelData.caminho)
          }
        }
      }
      Texto {
        visible: e.menu.mostrarRecentes && e.menu.recentes.length === 0
        anchors { top: hRec.bottom; topMargin: 24; horizontalCenter: parent.horizontalCenter }
        text: I18n.t("Os arquivos que você abrir vão aparecer aqui.")
        color: Tema.texto3; font.pixelSize: Tema.tLegenda
      }
    }

    // ── todos os apps ──────────────────────────────────────────────────
    Item {
      anchors.fill: parent
      visible: !e.menu.texto && e.menu.pagina === "todos"
      Cabecalho { id: hTodos; width: parent.width; titulo: I18n.t("Todos"); botao: I18n.t("Voltar"); voltar: true; onClicado: e.menu.pagina = "inicio" }
      ListaTodos { anchors { top: hTodos.bottom; topMargin: 6; left: parent.left; right: parent.right; bottom: parent.bottom } menu: e.menu }
    }

    // ── recomendados (todos) ───────────────────────────────────────────
    Item {
      anchors.fill: parent
      visible: !e.menu.texto && e.menu.pagina === "recomendado"
      Cabecalho { id: hRec2; width: parent.width; titulo: I18n.t("Recomendado"); botao: I18n.t("Voltar"); voltar: true; onClicado: e.menu.pagina = "inicio" }
      ListView {
        anchors { top: hRec2.bottom; topMargin: 6; left: parent.left; right: parent.right; bottom: parent.bottom }
        clip: true; spacing: 2
        model: e.menu.recentes
        delegate: LinhaApp {
          required property var modelData
          width: ListView.view.width
          menu: e.menu
          titulo: modelData.nome
          sub: e.menu.quando(modelData.quando) + " · " + modelData.pasta
          fonte: e.menu.caminhoIcone(modelData.icone)
          onAtivada: e.menu.abrirArquivo(modelData.caminho)
        }
      }
    }
  }

  Rodape { id: rodape; menu: e.menu; anchors { left: parent.left; right: parent.right; bottom: parent.bottom } }
}
