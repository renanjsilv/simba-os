import QtQuick
import QtQuick.Layouts
import qs.Comum
import qs.Janela

Pagina {
  id: pg
  titulo: I18n.t("Atalhos de teclado")
  subtitulo: I18n.t("Todos os atalhos ativos agora (do sistema e os seus). Para mudar, edite ~/.config/hypr/bindings.lua.")

  property var atalhos: []
  property string filtro: ""
  Component.onCompleted: Sistema.json([Sistema.ajudante, "atalhos"], function(v) { if (v) pg.atalhos = v })

  function norm(s) { return String(s).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "") }
  readonly property var filtrados: {
    var f = norm(filtro).trim()
    var lista = atalhos.filter(function(a) { return a.acao && a.acao.length })
    if (!f) return lista
    return lista.filter(function(a) { return norm(a.teclas + " " + a.acao).indexOf(f) >= 0 })
  }
  function teclas(t) {
    // "SUPER SHIFT + LEFT" -> ["Super", "Shift", "←"]
    var partes = String(t).split("+")
    var mods = partes[0].trim().split(/\s+/).filter(function(x) { return x })
    var tecla = partes.slice(1).join("+").trim()
    var nomes = { SUPER: I18n.t("Super"), SHIFT: I18n.t("Shift"), CTRL: I18n.t("Ctrl"), CONTROL: I18n.t("Ctrl"), ALT: I18n.t("Alt"), RETURN: I18n.t("Enter"), SPACE: I18n.t("Espaço"),
                  LEFT: "←", RIGHT: "→", UP: "↑", DOWN: "↓", ESCAPE: I18n.t("Esc"), PRINT: I18n.t("PrtSc"), TAB: I18n.t("Tab"), BACKSPACE: "⌫",
                  DELETE: I18n.t("Del"), COMMA: ",", PERIOD: ".", SLASH: "/", MINUS: "−", EQUAL: "=", GRAVE: "`", APOSTROPHE: "'",
                  BRACKETLEFT: "[", BRACKETRIGHT: "]", SEMICOLON: ";", BACKSLASH: "\\", MOUSE_DOWN: I18n.t("Rolar ↓"), MOUSE_UP: I18n.t("Rolar ↑"),
                  "MOUSE:272": I18n.t("Clique esq."), "MOUSE:273": I18n.t("Clique dir.") }
    var out = mods.map(function(m) { return nomes[m] || (m.charAt(0) + m.slice(1).toLowerCase()) })
    if (tecla) out.push(nomes[tecla.toUpperCase()] || (tecla.length > 1 && tecla.indexOf("XF86") !== 0 ? tecla.charAt(0) + tecla.slice(1).toLowerCase() : tecla.replace("XF86", "")))
    return out
  }

  component Tecla: Rectangle {
    property string t: ""
    implicitWidth: Math.max(26, rot.implicitWidth + 14)
    implicitHeight: 26
    radius: Tema.raioPequeno + 1
    color: Tema.superficieAlta
    border.width: 1
    border.color: Tema.linhaForte
    Rectangle { anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right; anchors.margins: 1; height: 2; radius: 1; color: Tema.linhaForte }
    Texto { id: rot; anchors.centerIn: parent; anchors.verticalCenterOffset: -1; text: parent.t; font.pixelSize: Tema.tLegenda + 1; font.weight: Font.DemiBold }
  }

  Cartao {
    Linha {
      chave: "superP"; glifo: Icones.monitorMultiple
      titulo: I18n.t("Projetar (modo de exibição)")
      descricao: I18n.t("Novo: substitui “Pseudo-janela”, que era o padrão do sistema nesta tecla")
      Row { spacing: 4; Tecla { t: I18n.t("Super") } Texto { text: "+"; color: Tema.texto3; anchors.verticalCenter: parent.verticalCenter } Tecla { t: "P" } }
    }
    Linha {
      glifo: Icones.cog
      titulo: I18n.t("Configurações")
      descricao: I18n.t("Pelo menu de aplicativos (Super+Espaço) ou clique direito na área de trabalho")
      Row { spacing: 4; Tecla { t: I18n.t("Super") } Texto { text: "+"; color: Tema.texto3; anchors.verticalCenter: parent.verticalCenter } Tecla { t: I18n.t("Espaço") } }
    }
  }

  RowLayout {
    Layout.fillWidth: true
    Layout.topMargin: 18
    Secao { titulo: I18n.t("Todos os atalhos"); detalhe: pg.filtrados.length + " de " + pg.atalhos.length; Layout.topMargin: 0 }
    Ancora { chave: "listaAtalhos"; Layout.preferredWidth: 0 }
    Campo { Layout.preferredWidth: 280; glifo: Icones.magnify; dica: I18n.t("Filtrar: terminal, captura, Super+…"); onTextChanged: pg.filtro = text }
  }

  Cartao {
    Repeater {
      model: pg.filtrados
      delegate: Item {
        id: at
        required property var modelData
        required property int index
        Layout.fillWidth: true
        implicitHeight: 44
        Rectangle { visible: at.index > 0; anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 16; anchors.rightMargin: 16; height: 1; color: Tema.linha }
        RowLayout {
          anchors.fill: parent
          anchors.leftMargin: 16
          anchors.rightMargin: 16
          spacing: 12
          Texto { text: at.modelData.acao; elide: Text.ElideRight; Layout.fillWidth: true }
          Row {
            spacing: 4
            Repeater {
              model: pg.teclas(at.modelData.teclas)
              delegate: Row {
                required property string modelData
                required property int index
                spacing: 4
                Texto { visible: index > 0; text: "+"; color: Tema.texto3; anchors.verticalCenter: parent.verticalCenter }
                Tecla { t: modelData }
              }
            }
          }
        }
      }
    }
  }
}
