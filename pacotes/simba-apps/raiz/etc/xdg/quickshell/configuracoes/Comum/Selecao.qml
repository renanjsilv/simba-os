import QtQuick
import QtQuick.Controls.Basic as C
import qs.Comum

// Dropdown. opcoes: [{ valor, rotulo, detalhe? }]. Long lists get a filter field.
Rectangle {
  id: r
  property var opcoes: []
  property var atual
  property string vazio: I18n.t("Escolher…")
  property bool habilitado: true
  property int larguraLista: Math.max(width, 260)
  signal escolhido(var valor)

  implicitWidth: 220
  implicitHeight: 34
  radius: Tema.raioPequeno + 1
  color: area.containsMouse || lista.opened ? Tema.superficieMax : Tema.superficieAlta
  border.width: 1
  border.color: lista.opened ? Tema.realce : Tema.linha
  opacity: habilitado ? 1 : 0.45
  activeFocusOnTab: habilitado
  Keys.onReturnPressed: abrir()
  Keys.onSpacePressed: abrir()
  Behavior on color { ColorAnimation { duration: Tema.rapido } }

  readonly property var selecionada: {
    for (var i = 0; i < opcoes.length; i++) if (opcoes[i].valor === atual) return opcoes[i]
    return null
  }

  function abrir() {
    if (!habilitado) return
    filtro.text = ""
    lista.open()
  }

  Texto {
    anchors.left: parent.left
    anchors.leftMargin: 12
    anchors.right: seta.left
    anchors.rightMargin: 6
    anchors.verticalCenter: parent.verticalCenter
    text: r.selecionada ? r.selecionada.rotulo : (r.atual !== undefined && r.atual !== "" ? String(r.atual) : r.vazio)
    elide: Text.ElideRight
    color: r.selecionada || r.atual ? Tema.texto : Tema.texto3
  }
  Glifo {
    id: seta
    anchors.right: parent.right
    anchors.rightMargin: 8
    anchors.verticalCenter: parent.verticalCenter
    g: Icones.chevronDown
    tamanho: 14
    color: Tema.texto2
    rotation: lista.opened ? 180 : 0
    Behavior on rotation { NumberAnimation { duration: Tema.medio; easing.type: Tema.curva } }
  }

  Rectangle {
    anchors.fill: parent
    anchors.margins: -3
    radius: r.radius + 3
    color: "transparent"
    border.width: 1.5
    border.color: Tema.realce
    opacity: r.activeFocus && !lista.opened ? 0.55 : 0
  }

  MouseArea {
    id: area
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: r.abrir()
  }

  readonly property var filtradas: {
    var f = filtro.text.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
    if (!f) return opcoes
    return opcoes.filter(function(o) {
      var s = (String(o.rotulo) + " " + (o.detalhe || "") + " " + String(o.valor)).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
      return s.indexOf(f) >= 0
    })
  }

  C.Popup {
    id: lista
    y: r.height + 6
    x: Math.min(0, r.width - r.larguraLista)
    width: r.larguraLista
    height: Math.min(conteudo.implicitHeight + 12, 360)
    padding: 6
    focus: true
    closePolicy: C.Popup.CloseOnEscape | C.Popup.CloseOnPressOutside
    onOpened: {
      var i = Math.max(0, r.filtradas.indexOf(r.selecionada))
      vista.currentIndex = i
      vista.positionViewAtIndex(i, ListView.Center)
      if (filtro.visible) filtro.forceActiveFocus(); else vista.forceActiveFocus()
    }
    onClosed: r.forceActiveFocus()

    enter: Transition {
      NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Tema.rapido }
      NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: Tema.medio; easing.type: Easing.OutBack }
    }
    exit: Transition {
      NumberAnimation { property: "opacity"; to: 0; duration: Tema.rapido }
    }

    background: Rectangle {
      radius: Tema.raio + 2
      color: Tema.superficieAlta
      border.width: 1
      border.color: Tema.linhaForte
      Sombra { alvo: parent }
    }

    contentItem: Column {
      id: conteudo
      spacing: 4
      Campo {
        id: filtro
        visible: r.opcoes.length > 10
        width: parent.width
        glifo: Icones.magnify
        dica: I18n.t("Filtrar…")
        Keys.onDownPressed: { vista.forceActiveFocus(); vista.currentIndex = 0 }
        Keys.onReturnPressed: if (r.filtradas.length) { r.escolhido(r.filtradas[0].valor); lista.close() }
      }
      ListView {
        id: vista
        width: parent.width
        height: Math.min(contentHeight, 360 - (filtro.visible ? 44 : 0) - 12)
        clip: true
        model: r.filtradas
        boundsBehavior: Flickable.StopAtBounds
        keyNavigationEnabled: true
        highlightMoveDuration: 0
        Keys.onReturnPressed: if (currentIndex >= 0) { r.escolhido(r.filtradas[currentIndex].valor); lista.close() }
        C.ScrollBar.vertical: C.ScrollBar { policy: vista.contentHeight > vista.height ? C.ScrollBar.AlwaysOn : C.ScrollBar.AlwaysOff; width: 6 }
        delegate: Rectangle {
          id: item
          required property var modelData
          required property int index
          readonly property bool sel: modelData.valor === r.atual
          width: vista.width - 8
          height: modelData.detalhe ? 44 : 32
          radius: Tema.raioPequeno
          color: ma.containsMouse || vista.currentIndex === index ? Tema.hover : "transparent"
          Rectangle {
            visible: item.sel
            width: 3; height: parent.height - 14
            radius: 1.5
            anchors.verticalCenter: parent.verticalCenter
            x: 2
            color: Tema.realce
          }
          Column {
            anchors.verticalCenter: parent.verticalCenter
            x: 14
            width: parent.width - 48
            Texto {
              width: parent.width
              text: item.modelData.rotulo
              elide: Text.ElideRight
              font.weight: item.sel ? Font.DemiBold : Font.Normal
            }
            Texto {
              visible: !!item.modelData.detalhe
              width: parent.width
              text: item.modelData.detalhe || ""
              color: Tema.texto3
              font.pixelSize: Tema.tLegenda
              elide: Text.ElideRight
            }
          }
          Glifo {
            visible: item.sel
            anchors.right: parent.right
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            g: Icones.check
            tamanho: 14
            color: Tema.realce
          }
          MouseArea {
            id: ma
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: { r.escolhido(item.modelData.valor); lista.close() }
          }
        }
      }
    }
  }
}
