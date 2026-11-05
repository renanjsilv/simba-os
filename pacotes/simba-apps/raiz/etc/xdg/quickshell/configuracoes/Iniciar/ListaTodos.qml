import QtQuick
import qs.Comum

// Todos os apps em ordem alfabética, com a letra como cabeçalho de seção.
// `lista` padrão: todos; o estilo moderno passa os de uma categoria.
ListView {
  id: lv
  property var menu
  property var lista: menu.apps
  property bool mostrarMaisUsados: false
  clip: true
  spacing: 1
  boundsBehavior: Flickable.StopAtBounds
  model: lista
  function letra(n) {
    var c = (n || "#").charAt(0).toUpperCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
    return /[A-Z]/.test(c) ? c : "#"
  }
  header: Column {
    width: lv.width
    visible: lv.mostrarMaisUsados && lv.menu.maisUsados.length > 0
    height: visible ? implicitHeight + 8 : 0
    Texto { text: I18n.t("Mais usados"); color: Tema.texto2; font.pixelSize: Tema.tLegenda; height: 26; leftPadding: 12; verticalAlignment: Text.AlignVCenter }
    Repeater {
      model: lv.mostrarMaisUsados ? lv.menu.maisUsados : []
      delegate: LinhaApp {
        required property var modelData
        width: lv.width; menu: lv.menu
        titulo: modelData.name; fonte: lv.menu.iconeApp(modelData); idApp: modelData.id
        onAtivada: lv.menu.abrirApp(modelData.id)
      }
    }
  }
  // Letra como cabeçalho quando muda em relação ao app anterior.
  delegate: Column {
    id: item
    required property var modelData
    required property int index
    width: lv.width
    readonly property bool novaLetra: index === 0 || lv.letra(lv.lista[index - 1].name) !== lv.letra(modelData.name)
    Item {
      visible: item.novaLetra
      width: lv.width; height: visible ? 30 : 0
      Texto { x: 14; anchors.bottom: parent.bottom; anchors.bottomMargin: 4; text: lv.letra(item.modelData.name); font.weight: Font.DemiBold; color: Tema.texto2 }
    }
    LinhaApp {
      width: lv.width
      menu: lv.menu
      titulo: item.modelData.name
      fonte: lv.menu.iconeApp(item.modelData)
      idApp: item.modelData.id
      onAtivada: lv.menu.abrirApp(item.modelData.id)
    }
  }
}
