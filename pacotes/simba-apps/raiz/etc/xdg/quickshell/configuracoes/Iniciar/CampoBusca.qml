import QtQuick
import qs.Comum

// Caixa de pesquisa (pílula) ligada a menu.texto; recebe o foco ao abrir e as teclas do menu.
Rectangle {
  id: c
  property var menu
  property string dica: I18n.t("Pesquisar aplicativos, configurações e arquivos")
  property alias entrada: campo
  height: 40
  radius: height / 2
  color: Tema.escuro ? Tema.alfa(Tema.fundo, 0.55) : Qt.rgba(1, 1, 1, 0.9)
  border.width: 1
  border.color: campo.activeFocus ? Tema.alfa(Tema.realce, 0.7) : Tema.linhaForte
  Rectangle {
    // traço de destaque embaixo, como o campo do Windows 11
    visible: campo.activeFocus
    anchors { bottom: parent.bottom; horizontalCenter: parent.horizontalCenter }
    width: parent.width - parent.radius * 2; height: 2; radius: 1
    color: Tema.realce
  }
  Glifo { id: lupa; x: 14; anchors.verticalCenter: parent.verticalCenter; g: Icones.magnify; tamanho: 17; color: Tema.texto2 }
  TextInput {
    id: campo
    anchors { left: lupa.right; leftMargin: 8; right: parent.right; rightMargin: 16; verticalCenter: parent.verticalCenter }
    text: c.menu.texto
    onTextEdited: c.menu.texto = text
    color: Tema.texto
    selectionColor: Tema.alfa(Tema.realce, 0.4)
    font.family: Tema.fonte
    font.pixelSize: Tema.tCorpo + 1
    clip: true
    focus: true
    Component.onCompleted: forceActiveFocus()
    Keys.onPressed: function(ev) { c.menu.tecla(ev) }
    Texto {
      anchors.verticalCenter: parent.verticalCenter
      visible: !campo.text
      text: c.dica
      color: Tema.texto3
      font.pixelSize: Tema.tCorpo + 1
      elide: Text.ElideRight
      width: parent.width
    }
  }
}
