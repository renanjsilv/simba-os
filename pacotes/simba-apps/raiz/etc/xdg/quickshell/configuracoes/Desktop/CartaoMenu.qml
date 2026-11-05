import QtQuick
import QtQuick.Layouts
import qs.Comum

// One menu card (root or submenu). Rows: { id, rotulo, glifo, tecla, sub,
// marcado, radio, negrito, habilitado, separador }; `acoes` is the optional
// quick-action strip shown above the rows (icon menu).
Rectangle {
  id: c
  property var itens: []
  property var acoes: []
  property int atual: -1
  property int subAberto: -1
  property real origemX: 0
  property real origemY: 0
  readonly property bool containsMouse: hover.hovered
  signal passou(int i)
  signal escolheu(int i)
  signal acao(string id)

  width: Math.max(250, Math.min(340, largura + 32))
  height: col.implicitHeight + 10
  radius: Math.max(6, Tema.raioGrande)
  color: Tema.superficieAlta
  border.width: 1
  border.color: Tema.linhaForte
  HoverHandler { id: hover }

  property real largura: 0
  Sombra { alvo: c; deslocamento: 10; intensidade: 0.9 }

  // reveal from the click point
  transform: Scale { id: escala; origin.x: c.origemX; origin.y: c.origemY; xScale: 0.92 + 0.08 * c.rev; yScale: 0.9 + 0.1 * c.rev }
  property real rev: 0
  opacity: rev
  Component.onCompleted: revelar.start()
  onVisibleChanged: if (visible) { rev = 0; revelar.restart() }
  NumberAnimation { id: revelar; target: c; property: "rev"; from: 0; to: 1; duration: Tema.animacoes ? 190 : 0; easing.type: Easing.OutCubic }

  function posicaoLinha(i) {
    var r = repetidor.itemAt(i)
    return r ? r.y + col.y : 0
  }

  Column {
    id: col
    x: 5; y: 5
    width: parent.width - 10
    spacing: 0

    // quick actions (Win11 icon menu)
    Row {
      visible: c.acoes.length > 0
      height: visible ? 46 : 0
      spacing: 2
      leftPadding: 4
      Repeater {
        model: c.acoes
        delegate: Rectangle {
          id: ac
          required property var modelData
          readonly property bool ok: modelData.habilitado !== false
          width: 44; height: 40
          y: 3
          radius: Math.max(4, Tema.raioPequeno)
          color: ma.containsMouse && ok ? Tema.hover : "transparent"
          opacity: ok ? 1 : 0.35
          Glifo { anchors.centerIn: parent; g: ac.modelData.glifo; tamanho: 18 }
          MouseArea {
            id: ma
            anchors.fill: parent
            hoverEnabled: true
            enabled: ac.ok
            cursorShape: Qt.PointingHandCursor
            onClicked: c.acao(ac.modelData.id)
          }
          // tooltip
          Rectangle {
            visible: ma.containsMouse
            y: -30
            anchors.horizontalCenter: parent.horizontalCenter
            width: dica.implicitWidth + 14; height: 24
            radius: Math.max(4, Tema.raioPequeno)
            color: Tema.texto
            z: 10
            Texto { id: dica; anchors.centerIn: parent; text: ac.modelData.rotulo; color: Tema.janela; font.pixelSize: Tema.tLegenda }
          }
        }
      }
    }
    Rectangle { visible: c.acoes.length > 0; width: parent.width; height: 1; color: Tema.linha }
    Item { visible: c.acoes.length > 0; width: 1; height: 4 }

    Repeater {
      id: repetidor
      model: c.itens
      delegate: Item {
        id: linha
        required property var modelData
        required property int index
        readonly property bool sep: !!modelData.separador
        readonly property bool ok: modelData.habilitado !== false
        readonly property bool ativo: index === c.atual
        width: col.width
        height: sep ? 9 : 34
        Rectangle { visible: linha.sep; anchors.verticalCenter: parent.verticalCenter; x: 8; width: parent.width - 16; height: 1; color: Tema.linha }
        Rectangle {
          visible: !linha.sep
          anchors.fill: parent
          radius: Math.max(4, Tema.raioPequeno)
          color: linha.ativo && linha.ok ? Tema.hover : "transparent"
          Behavior on color { ColorAnimation { duration: 70 } }
          Rectangle {
            visible: linha.ativo && linha.ok
            x: 0; width: 3; height: 16
            anchors.verticalCenter: parent.verticalCenter
            radius: 1.5
            color: Tema.realce
          }
        }
        RowLayout {
          visible: !linha.sep
          anchors.fill: parent
          anchors.leftMargin: 12
          anchors.rightMargin: 10
          spacing: 12
          opacity: linha.ok ? 1 : 0.4
          Item {
            Layout.preferredWidth: 18; Layout.preferredHeight: 18
            Glifo {
              anchors.centerIn: parent
              g: linha.modelData.marcado ? Icones.check : (linha.modelData.radio ? Icones.radioboxMarked : (linha.modelData.glifo || ""))
              tamanho: 16
              color: linha.modelData.marcado || linha.modelData.radio ? Tema.realce : Tema.texto
              visible: g !== "" && (linha.modelData.marcado !== false || linha.modelData.glifo)
              opacity: linha.modelData.marcado === false ? 0 : 1
            }
          }
          Texto {
            text: linha.modelData.rotulo || ""
            font.weight: linha.modelData.negrito ? Font.DemiBold : Font.Normal
            elide: Text.ElideRight
            Layout.fillWidth: true
            Component.onCompleted: c.largura = Math.max(c.largura, implicitWidth + 60 + (linha.modelData.tecla ? 60 : 0))
          }
          Texto { visible: !!linha.modelData.tecla; text: linha.modelData.tecla || ""; color: Tema.texto3; font.pixelSize: Tema.tLegenda }
          Glifo { visible: !!linha.modelData.sub; g: Icones.chevronRight; tamanho: 14; color: Tema.texto2 }
        }
        MouseArea {
          anchors.fill: parent
          enabled: !linha.sep && linha.ok
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onEntered: c.passou(linha.index)
          onClicked: c.escolheu(linha.index)
        }
      }
    }
  }
}
