import QtQuick
import qs.Comum

// Segmented control with a sliding selection pill.
// opcoes: [{ valor, rotulo, glifo? }]
Rectangle {
  id: r
  property var opcoes: []
  property var atual
  property bool habilitado: true
  property int altura: 32
  signal escolhido(var valor)

  implicitHeight: altura
  implicitWidth: linha.implicitWidth + 8
  radius: Tema.raioPequeno + 2
  color: Tema.superficieAlta
  border.width: 1
  border.color: Tema.linha
  opacity: habilitado ? 1 : 0.45
  activeFocusOnTab: habilitado

  readonly property int indice: {
    for (var i = 0; i < opcoes.length; i++) if (opcoes[i].valor === atual) return i
    return -1
  }
  Keys.onLeftPressed: if (habilitado && indice > 0) escolhido(opcoes[indice - 1].valor)
  Keys.onRightPressed: if (habilitado && indice < opcoes.length - 1) escolhido(opcoes[indice + 1].valor)

  Rectangle {
    id: pilula
    readonly property Item alvo: r.indice >= 0 && repetidor.count > r.indice ? repetidor.itemAt(r.indice) : null
    visible: alvo !== null
    x: alvo ? alvo.x + linha.x : 0
    width: alvo ? alvo.width : 0
    y: 3
    height: r.height - 6
    radius: Tema.raioPequeno
    color: Tema.realce
    Behavior on x { NumberAnimation { duration: Tema.medio; easing.type: Easing.OutBack; easing.overshoot: 0.9 } }
    Behavior on width { NumberAnimation { duration: Tema.medio; easing.type: Tema.curva } }
  }

  Rectangle {
    anchors.fill: parent
    anchors.margins: -3
    radius: r.radius + 3
    color: "transparent"
    border.width: 1.5
    border.color: Tema.realce
    opacity: r.activeFocus ? 0.5 : 0
  }

  Row {
    id: linha
    x: 4
    height: parent.height
    Repeater {
      id: repetidor
      model: r.opcoes
      delegate: Item {
        id: opc
        required property var modelData
        required property int index
        readonly property bool sel: index === r.indice
        width: conteudo.implicitWidth + 24
        height: linha.height
        Row {
          id: conteudo
          anchors.centerIn: parent
          spacing: 6
          Glifo {
            visible: !!opc.modelData.glifo
            g: opc.modelData.glifo || ""
            tamanho: 14
            anchors.verticalCenter: parent.verticalCenter
            color: opc.sel ? Tema.sobreRealce : (ma.containsMouse ? Tema.texto : Tema.texto2)
          }
          Texto {
            text: opc.modelData.rotulo
            anchors.verticalCenter: parent.verticalCenter
            font.pixelSize: Tema.tCorpo - 1
            font.weight: opc.sel ? Font.DemiBold : Font.Normal
            color: opc.sel ? Tema.sobreRealce : (ma.containsMouse ? Tema.texto : Tema.texto2)
          }
        }
        MouseArea {
          id: ma
          anchors.fill: parent
          hoverEnabled: true
          enabled: r.habilitado
          cursorShape: Qt.PointingHandCursor
          onClicked: if (!opc.sel) r.escolhido(opc.modelData.valor)
        }
      }
    }
  }
}
