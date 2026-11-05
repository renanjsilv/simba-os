import QtQuick
import qs.Comum

// Windows 11 (2025): uma coluna rolável — Fixado (2 linhas, "Mostrar tudo"),
// Recomendado e Todos, por Categoria, Grade ou Lista.
Item {
  id: e
  property var menu
  readonly property int colunas: 8
  property bool fixadosTodos: false
  property bool recomendadosMais: false
  property string categoriaAberta: ""

  CampoBusca { id: busca; menu: e.menu; x: 32; y: 28; width: parent.width - 64 }

  Resultados {
    anchors { left: parent.left; right: parent.right; top: busca.bottom; bottom: rodape.top; margins: 32; topMargin: 20; bottomMargin: 8 }
    visible: !!e.menu.texto
    menu: e.menu
  }

  Flickable {
    id: rol
    visible: !e.menu.texto
    anchors { left: parent.left; right: parent.right; top: busca.bottom; bottom: rodape.top; topMargin: 12 }
    clip: true
    contentHeight: col.implicitHeight + 24
    boundsBehavior: Flickable.StopAtBounds
    Behavior on contentY { enabled: !rol.moving; NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

    Column {
      id: col
      x: 32; width: rol.width - 64
      spacing: 6

      // ── fixado ───────────────────────────────────────────────────────
      Cabecalho {
        width: parent.width
        titulo: I18n.t("Fixado")
        botao: e.menu.fixados.length > e.colunas * 2 ? (e.fixadosTodos ? I18n.t("Mostrar menos") : I18n.t("Mostrar tudo")) : ""
        onClicado: e.fixadosTodos = !e.fixadosTodos
      }
      Grid {
        id: gFix
        columns: e.colunas
        width: parent.width
        Repeater {
          model: e.fixadosTodos ? e.menu.fixados : e.menu.fixados.slice(0, e.colunas * 2)
          delegate: Bloco { required property string modelData; menu: e.menu; entrada: e.menu.app(modelData); width: gFix.width / e.colunas; height: 88 }
        }
      }

      // ── recomendado ──────────────────────────────────────────────────
      Item { width: 1; height: 8; visible: e.menu.mostrarRecentes && e.menu.recentes.length > 0 }
      Cabecalho {
        visible: e.menu.mostrarRecentes && e.menu.recentes.length > 0
        width: parent.width
        titulo: I18n.t("Recomendado")
        botao: e.menu.recentes.length > 3 ? (e.recomendadosMais ? I18n.t("Mostrar menos") : I18n.t("Mostrar mais")) : ""
        onClicado: e.recomendadosMais = !e.recomendadosMais
      }
      Grid {
        id: gRec
        visible: e.menu.mostrarRecentes
        columns: 3
        columnSpacing: 6
        rowSpacing: 2
        width: parent.width
        Repeater {
          model: e.menu.recentes.slice(0, e.recomendadosMais ? 9 : 3)
          delegate: LinhaApp {
            required property var modelData
            width: (gRec.width - 12) / 3
            menu: e.menu
            titulo: modelData.nome
            sub: e.menu.quando(modelData.quando)
            fonte: e.menu.caminhoIcone(modelData.icone)
            onAtivada: e.menu.abrirArquivo(modelData.caminho)
          }
        }
      }

      // ── todos ────────────────────────────────────────────────────────
      Item { width: 1; height: 10 }
      Item {
        width: parent.width; height: 32
        Texto { anchors.verticalCenter: parent.verticalCenter; text: e.categoriaAberta ? "" : I18n.t("Todos"); font.pixelSize: Tema.tSubtitulo; font.weight: Font.DemiBold }
        Cabecalho {
          visible: !!e.categoriaAberta
          width: 300
          titulo: ""
          botao: I18n.t("Todas as categorias")
          voltar: true
          anchors.left: parent.left
          // botão à esquerda: reposiciona o retângulo do Cabecalho
          LayoutMirroring.enabled: true
          LayoutMirroring.childrenInherit: false
          onClicado: e.categoriaAberta = ""
        }
        Segmentado {
          anchors { right: parent.right; verticalCenter: parent.verticalCenter }
          altura: 28
          atual: e.menu.visaoTodos
          opcoes: [{ valor: "categoria", rotulo: I18n.t("Categoria") }, { valor: "grade", rotulo: I18n.t("Grade") }, { valor: "lista", rotulo: I18n.t("Lista") }]
          onEscolhido: function(v) { e.categoriaAberta = ""; Preferencias.definir("iniciar.visaoTodos", v) }
        }
      }

      // por categoria: blocos com os 4 apps mais usados; clicar abre a categoria
      Grid {
        id: gCat
        visible: e.menu.visaoTodos === "categoria" && !e.categoriaAberta
        columns: 3
        columnSpacing: 10
        rowSpacing: 10
        width: parent.width
        Repeater {
          model: gCat.visible ? e.menu.porCategoria : []
          delegate: Item {
            id: cat
            required property var modelData
            width: (gCat.width - 20) / 3
            height: 152
            Rectangle {
              id: fundoCat
              anchors { left: parent.left; right: parent.right; top: parent.top }
              height: 118
              radius: 8
              color: ac.containsMouse ? Tema.superficieMax : Tema.alfa(Tema.texto, Tema.escuro ? 0.05 : 0.04)
              border.width: 1; border.color: Tema.linha
              MouseArea { id: ac; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: e.categoriaAberta = cat.modelData.id }
              Grid {
                anchors.centerIn: parent
                columns: 2; spacing: 10
                Repeater {
                  model: cat.modelData.apps.slice(0, cat.modelData.apps.length > 4 ? 3 : 4)
                  delegate: Item {
                    required property var modelData
                    width: 44; height: 44
                    Rectangle { anchors.fill: parent; radius: 6; color: ai.containsMouse ? Tema.hover : "transparent" }
                    Icone { anchors.centerIn: parent; tamanho: 32; fonte: e.menu.iconeApp(parent.modelData) }
                    MouseArea { id: ai; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: e.menu.abrirApp(parent.modelData.id) }
                  }
                }
                // 4º espaço: mini-grade com os demais (abre a categoria)
                Item {
                  visible: cat.modelData.apps.length > 4
                  width: 44; height: 44
                  Grid {
                    anchors.centerIn: parent
                    columns: 2; spacing: 3
                    Repeater {
                      model: cat.modelData.apps.slice(3, 7)
                      delegate: Icone { required property var modelData; tamanho: 16; fonte: e.menu.iconeApp(modelData) }
                    }
                  }
                }
              }
            }
            Texto {
              anchors { top: fundoCat.bottom; topMargin: 8; horizontalCenter: parent.horizontalCenter }
              text: cat.modelData.titulo
              font.pixelSize: Tema.tLegenda + 1
            }
          }
        }
      }
      // categoria aberta / lista: linhas
      Repeater {
        model: (e.menu.visaoTodos === "lista" || e.categoriaAberta) ? e.listaAtual : []
        delegate: Column {
          id: li
          required property var modelData
          required property int index
          width: col.width
          readonly property bool novaLetra: !e.categoriaAberta && (index === 0 || e.letra(e.listaAtual[index - 1].name) !== e.letra(modelData.name))
          Item {
            visible: li.novaLetra
            width: parent.width; height: visible ? 30 : 0
            Texto { x: 14; anchors.bottom: parent.bottom; anchors.bottomMargin: 4; text: e.letra(li.modelData.name); font.weight: Font.DemiBold; color: Tema.texto2 }
          }
          LinhaApp {
            width: parent.width
            menu: e.menu
            titulo: li.modelData.name
            fonte: e.menu.iconeApp(li.modelData)
            idApp: li.modelData.id
            onAtivada: e.menu.abrirApp(li.modelData.id)
          }
        }
      }
      // grade
      Grid {
        id: gTodos
        visible: e.menu.visaoTodos === "grade" && !e.categoriaAberta
        columns: e.colunas
        width: parent.width
        Repeater {
          model: gTodos.visible ? e.menu.apps : []
          delegate: Bloco { required property var modelData; menu: e.menu; entrada: modelData; width: gTodos.width / e.colunas; height: 88 }
        }
      }
    }
  }

  readonly property var listaAtual: {
    if (categoriaAberta) {
      var c = menu.porCategoria.filter(function(x) { return x.id === categoriaAberta })[0]
      return c ? c.apps.slice().sort(function(a, b) { return a.name.localeCompare(b.name, "pt-BR") }) : []
    }
    return menu.apps
  }
  function letra(n) {
    var c = (n || "#").charAt(0).toUpperCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
    return /[A-Z]/.test(c) ? c : "#"
  }

  Rodape { id: rodape; menu: e.menu; anchors { left: parent.left; right: parent.right; bottom: parent.bottom } }
}
