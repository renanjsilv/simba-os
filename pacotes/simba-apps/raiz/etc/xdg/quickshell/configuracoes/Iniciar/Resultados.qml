import QtQuick
import qs.Comum

// Resultados da pesquisa: lista à esquerda e a "Melhor correspondência" em
// destaque à direita (quando cabe), como no Windows 11.
Item {
  id: r
  property var menu
  readonly property var lista: menu.resultados
  readonly property var melhor: lista.length ? lista[menu.sel] || lista[0] : null
  readonly property bool lado: width > 560

  Texto {
    anchors.centerIn: parent
    visible: !r.lista.length
    text: I18n.t("Nenhum resultado para “") + r.menu.texto + "”"
    color: Tema.texto3
  }
  ListView {
    id: lv
    anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
    width: r.lado ? parent.width * 0.52 : parent.width
    clip: true
    spacing: 2
    model: r.lista
    currentIndex: r.menu.sel
    boundsBehavior: Flickable.StopAtBounds
    header: Texto { visible: r.lista.length > 0; text: I18n.t("Melhor correspondência"); color: Tema.texto2; font.pixelSize: Tema.tLegenda; height: 26 }
    onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
    delegate: LinhaApp {
      required property var modelData
      required property int index
      width: lv.width
      menu: r.menu
      titulo: modelData.titulo
      sub: modelData.sub
      fonte: modelData.icone || ""
      glifo: modelData.glifo || ""
      idApp: modelData.tipo === "app" ? modelData.id : ""
      selecionada: index === r.menu.sel
      onAtivada: r.menu.abrirResultado(modelData)
    }
  }
  // destaque
  Rectangle {
    visible: r.lado && !!r.melhor
    anchors { left: lv.right; leftMargin: 12; right: parent.right; top: parent.top; topMargin: 26; bottom: parent.bottom }
    radius: 8
    color: Tema.alfa(Tema.texto, Tema.escuro ? 0.04 : 0.03)
    border.width: 1; border.color: Tema.linha
    Column {
      anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 36 }
      spacing: 10
      Icone {
        anchors.horizontalCenter: parent.horizontalCenter
        tamanho: 64
        fonte: r.melhor ? (r.melhor.icone || "") : ""
        glifo: r.melhor ? (r.melhor.glifo || "") : ""
      }
      Texto {
        width: parent.width - 24; anchors.horizontalCenter: parent.horizontalCenter
        horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
        text: r.melhor ? r.melhor.titulo : ""
        font.pixelSize: Tema.tTitulo; font.weight: Font.DemiBold
      }
      Texto {
        width: parent.width - 24; anchors.horizontalCenter: parent.horizontalCenter
        horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight
        text: r.melhor ? r.melhor.sub : ""
        color: Tema.texto3; font.pixelSize: Tema.tLegenda
      }
      Rectangle { width: parent.width - 32; height: 1; color: Tema.linha; anchors.horizontalCenter: parent.horizontalCenter }
      Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width - 32; height: 36; radius: 6
        color: ao.containsMouse ? Tema.hover : "transparent"
        Row {
          anchors.verticalCenter: parent.verticalCenter; x: 12; spacing: 10
          Glifo { g: Icones.openInNew; tamanho: 15; color: Tema.realce; anchors.verticalCenter: parent.verticalCenter }
          Texto { text: !r.melhor ? "" : r.melhor.tipo === "loja" ? I18n.t("Ver na Loja") : r.melhor.tipo === "draco" ? I18n.t("Perguntar") : I18n.t("Abrir"); anchors.verticalCenter: parent.verticalCenter }
        }
        MouseArea { id: ao; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: r.menu.abrirResultado(r.melhor) }
      }
      Rectangle {
        visible: !!r.melhor && r.melhor.tipo === "app"
        anchors.horizontalCenter: parent.horizontalCenter
        width: parent.width - 32; height: 36; radius: 6
        color: af.containsMouse ? Tema.hover : "transparent"
        Row {
          anchors.verticalCenter: parent.verticalCenter; x: 12; spacing: 10
          Glifo { g: Icones.pin; tamanho: 15; color: Tema.texto2; anchors.verticalCenter: parent.verticalCenter }
          Texto { text: r.melhor && r.menu.fixado(r.melhor.id) ? I18n.t("Desafixar de Iniciar") : I18n.t("Fixar em Iniciar"); anchors.verticalCenter: parent.verticalCenter }
        }
        MouseArea {
          id: af; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
          onClicked: if (r.menu.fixado(r.melhor.id)) r.menu.desafixar(r.melhor.id); else r.menu.fixar(r.melhor.id)
        }
      }
    }
  }
}
