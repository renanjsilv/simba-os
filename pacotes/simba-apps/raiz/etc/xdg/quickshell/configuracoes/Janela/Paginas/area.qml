import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.Comum
import qs.Janela

Pagina {
  id: pg
  titulo: I18n.t("Área de trabalho")
  subtitulo: I18n.t("Ícones sobre o papel de parede e o menu do botão direito, como no Windows. Os ícones nunca ficam por cima das janelas.")

  property string xdg: ""
  property var telas: Quickshell.screens.map(function(s) { return s.name })
  Component.onCompleted: Sistema.sh("xdg-user-dir DESKTOP", function(o) { pg.xdg = o.trim() })

  readonly property string pastaAtual: Preferencias.obter("area.pasta", "") || xdg
  function curto(p) { return String(p).replace(Sistema.home, "~") || "~" }

  // ── illustration ─────────────────────────────────────────────────────────
  Rectangle {
    Layout.fillWidth: true
    Layout.preferredHeight: 200
    radius: Tema.raioGrande
    color: Tema.superficie
    border.width: 1
    border.color: Tema.linha
    clip: true
    Rectangle {
      anchors.fill: parent
      anchors.margins: 14
      radius: Tema.raio
      clip: true
      color: Tema.fundo
      Image { anchors.fill: parent; source: "file://" + Tema.estadoSimba + "/background"; fillMode: Image.PreserveAspectCrop; sourceSize.width: 700; asynchronous: true; cache: false }
      Grid {
        visible: Preferencias.obter("area.mostrarIcones", true)
        x: 14; y: 14
        flow: Grid.TopToBottom
        rows: 3
        spacing: Preferencias.obter("area.tamanho", "medio") === "grande" ? 10 : 6
        Repeater {
          model: [Icones.folderHome, Icones.folder, Icones.fileDocumentOutline, Icones.fileImage, Icones.gamepadVariant]
          Column {
            required property string modelData
            readonly property int t: Preferencias.obter("area.tamanho", "medio") === "grande" ? 30 : (Preferencias.obter("area.tamanho", "medio") === "pequeno" ? 16 : 22)
            spacing: 2
            Glifo { anchors.horizontalCenter: parent.horizontalCenter; g: parent.modelData; tamanho: parent.t; color: "white" }
            Rectangle { anchors.horizontalCenter: parent.horizontalCenter; width: parent.t * 1.4; height: 3; radius: 1.5; color: Qt.rgba(1, 1, 1, 0.8) }
          }
        }
      }
      // a context menu sketch
      Rectangle {
        x: parent.width * 0.55; y: 26
        width: 150; height: menuCol.implicitHeight + 12
        radius: Tema.raio
        color: Tema.alfa(Tema.janela, 0.94)
        border.width: 1
        border.color: Tema.linhaForte
        Column {
          id: menuCol
          x: 6; y: 6
          width: parent.width - 12
          spacing: 2
          Repeater {
            model: [[Icones.viewGridOutline, I18n.t("Exibir")], [Icones.sortVariant, I18n.t("Classificar por")], [Icones.refresh, I18n.t("Atualizar")], [Icones.plusCircle, I18n.t("Novo")], [Icones.contentPaste, I18n.t("Colar")], [Icones.wallpaper, I18n.t("Papel de parede")]]
            Row {
              required property var modelData
              required property int index
              spacing: 6
              height: 18
              Glifo { g: modelData[0]; tamanho: 11; color: Tema.texto2; anchors.verticalCenter: parent.verticalCenter }
              Texto { text: modelData[1]; font.pixelSize: 10; anchors.verticalCenter: parent.verticalCenter; color: index === 2 ? Tema.texto : Tema.texto2 }
            }
          }
        }
      }
    }
  }

  Secao { titulo: I18n.t("Ícones") }
  Cartao {
    Linha {
      chave: "areaIcones"; glifo: Icones.viewGridOutline
      titulo: I18n.t("Mostrar ícones da área de trabalho")
      descricao: I18n.t("Arquivos e pastas de ") + pg.curto(pg.pastaAtual)
      Interruptor { ligado: Preferencias.obter("area.mostrarIcones", true); onAlternado: function(v) { Preferencias.definir("area.mostrarIcones", v) } }
    }
    Linha {
      chave: "areaLixeira"; glifo: Icones.lixeira
      titulo: I18n.t("Mostrar a Lixeira")
      descricao: I18n.t("Ícone da Lixeira no canto da área de trabalho")
      Interruptor { ligado: Preferencias.obter("area.lixeira", true); onAlternado: function(v) { Preferencias.definir("area.lixeira", v) } }
    }
    Linha {
      chave: "areaTamanho"; glifo: Icones.formatSize
      titulo: I18n.t("Tamanho dos ícones")
      Segmentado {
        opcoes: [{ valor: "pequeno", rotulo: I18n.t("Pequenos") }, { valor: "medio", rotulo: I18n.t("Médios") }, { valor: "grande", rotulo: I18n.t("Grandes") }]
        atual: Preferencias.obter("area.iconePx", 0) ? "" : Preferencias.obter("area.tamanho", "medio")
        onEscolhido: function(v) { Preferencias.definir("area.iconePx", undefined); Preferencias.definir("area.tamanho", v) }
      }
    }
    Linha {
      chave: "areaOrdenar"; glifo: Icones.sortVariant
      titulo: I18n.t("Classificar por")
      descricao: I18n.t("Pastas sempre primeiro")
      Selecao {
        width: 200
        opcoes: [{ valor: "nome", rotulo: I18n.t("Nome") }, { valor: "tamanho", rotulo: I18n.t("Tamanho") }, { valor: "tipo", rotulo: I18n.t("Tipo de item") }, { valor: "data", rotulo: I18n.t("Data de modificação") }]
        atual: Preferencias.obter("area.ordenar", "nome")
        onEscolhido: function(v) { Preferencias.definir("area.ordenar", v); Preferencias.definir("area.posicoes", {}) }
      }
    }
    Linha {
      chave: "areaAuto"; glifo: Icones.viewDashboard
      titulo: I18n.t("Organizar ícones automaticamente")
      descricao: I18n.t("Mantém tudo em colunas a partir do canto; desligado, você arrasta para onde quiser")
      Interruptor { ligado: Preferencias.obter("area.automatico", false); onAlternado: function(v) { Preferencias.definir("area.automatico", v); if (v) Preferencias.definir("area.posicoes", {}) } }
    }
    Linha {
      chave: "areaGrade"; glifo: Icones.borderAll
      titulo: I18n.t("Alinhar ícones à grade")
      Interruptor { ligado: Preferencias.obter("area.grade", true); onAlternado: function(v) { Preferencias.definir("area.grade", v) } }
    }
    Linha {
      chave: "areaOcultos"; glifo: Icones.eyeOutline
      titulo: I18n.t("Mostrar arquivos ocultos")
      descricao: I18n.t("Os que começam com ponto")
      Interruptor { ligado: Preferencias.obter("area.ocultos", false); onAlternado: function(v) { Preferencias.definir("area.ocultos", v) } }
    }
  }

  Secao { titulo: I18n.t("Onde ficam") }
  Cartao {
    Linha {
      chave: "areaPasta"; glifo: Icones.folderHome
      titulo: I18n.t("Pasta da área de trabalho")
      descricao: pg.curto(pg.pastaAtual) + (Preferencias.obter("area.pasta", "") ? "" : I18n.t(" · a pasta “Área de trabalho” do sistema (xdg-user-dir)"))
      Botao {
        texto: I18n.t("Escolher…")
        onClicado: Sistema.rodar(["simba-file-select", "--title", I18n.t("Pasta da área de trabalho"), "--directory"], function(o, code) {
          var p = o.trim().split("\n")[0]
          if (code === 0 && p) { Preferencias.definir("area.pasta", decodeURIComponent(p.replace(/^file:\/\//, ""))); Preferencias.definir("area.posicoes", {}) }
        })
      }
      Botao {
        visible: Preferencias.obter("area.pasta", "") !== ""
        tipo: "fantasma"; glifo: Icones.backupRestore
        onClicado: { Preferencias.definir("area.pasta", ""); Preferencias.definir("area.posicoes", {}) }
      }
      Botao { tipo: "fantasma"; glifo: Icones.openInNew; onClicado: Sistema.solto(["xdg-open", pg.pastaAtual]) }
    }
    Linha {
      chave: "areaTela"; glifo: Icones.monitor
      titulo: I18n.t("Tela com os ícones")
      descricao: I18n.t("O menu do botão direito funciona em todas")
      Selecao {
        width: 200
        opcoes: [{ valor: "", rotulo: I18n.t("Tela principal") }].concat(pg.telas.map(function(n) { return { valor: n, rotulo: n } })).concat([{ valor: "*", rotulo: I18n.t("Todas as telas") }])
        atual: Preferencias.obter("area.tela", "")
        onEscolhido: function(v) { Preferencias.definir("area.tela", v) }
      }
    }
  }

  Secao { titulo: I18n.t("Menu do botão direito") }
  Cartao {
    Linha {
      chave: "menuContexto"; glifo: Icones.cursorDefault
      titulo: I18n.t("Clique com o botão direito num espaço vazio da área de trabalho")
      descricao: I18n.t("Exibir, classificar, atualizar, novo, colar, abrir no terminal, trocar o papel de parede e abrir estas configurações. Num ícone: abrir, copiar, recortar, renomear, excluir e propriedades.")
      Botao { texto: I18n.t("Mostrar"); onClicado: Sistema.soltoSh("qs -c configuracoes ipc call configuracoes menu '' -1 -1") }
    }
  }
}
