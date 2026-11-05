import QtQuick
import qs.Comum

// Button. tipo: "normal" | "primario" | "fantasma" | "perigo"
Rectangle {
  id: r
  property string texto: ""
  property string glifo: ""
  property string tipo: "normal"
  property bool habilitado: true
  property bool compacto: false
  property bool ocupado: false
  signal clicado()

  implicitHeight: compacto ? 28 : 34
  implicitWidth: Math.max(implicitHeight, conteudo.implicitWidth + (texto ? (compacto ? 20 : 28) : 0) + (texto ? 0 : 0))
  radius: Tema.raioPequeno + 1
  opacity: habilitado ? 1 : 0.4
  activeFocusOnTab: habilitado
  Keys.onReturnPressed: if (habilitado) r.clicado()
  Keys.onSpacePressed: if (habilitado) r.clicado()

  readonly property color corFundo: {
    if (tipo === "primario") return area.pressed ? Qt.darker(Tema.realce, Tema.escuro ? 1.12 : 1.18) : (area.containsMouse ? Qt.lighter(Tema.realce, Tema.escuro ? 1.08 : 1.15) : Tema.realce)
    if (tipo === "perigo") return area.pressed ? Tema.alfa(Tema.perigo, 0.36) : area.containsMouse ? Tema.alfa(Tema.perigo, 0.28) : Tema.alfa(Tema.perigo, 0.18)
    if (tipo === "fantasma") return area.pressed ? Tema.pressionado : (area.containsMouse ? Tema.hover : "transparent")
    return area.pressed ? Tema.mistura(Tema.superficieMax, Tema.texto, 0.06) : (area.containsMouse ? Tema.superficieMax : Tema.superficieAlta)
  }
  readonly property color corTexto: tipo === "primario" ? Tema.sobreRealce : (tipo === "perigo" ? Tema.perigo : Tema.texto)

  color: corFundo
  border.width: tipo === "normal" ? 1 : 0
  border.color: Tema.linha
  scale: area.pressed ? 0.965 : 1
  Behavior on scale { NumberAnimation { duration: Tema.rapido; easing.type: Easing.OutQuad } }
  Behavior on color { ColorAnimation { duration: Tema.rapido } }

  Row {
    id: conteudo
    anchors.centerIn: parent
    spacing: 7
    opacity: r.ocupado ? 0.35 : 1
    Glifo {
      visible: r.glifo !== ""
      g: r.glifo
      tamanho: r.compacto ? 14 : 15
      color: r.corTexto
      anchors.verticalCenter: parent.verticalCenter
    }
    Texto {
      visible: r.texto !== ""
      text: r.texto
      color: r.corTexto
      font.pixelSize: r.compacto ? Tema.tCorpo - 1 : Tema.tCorpo
      font.weight: r.tipo === "primario" ? Font.DemiBold : Font.Medium
      anchors.verticalCenter: parent.verticalCenter
    }
  }

  // Busy indicator: three dots
  Row {
    anchors.centerIn: parent
    spacing: 4
    visible: r.ocupado
    Repeater {
      model: 3
      Rectangle {
        required property int index
        width: 5; height: 5; radius: 2.5
        color: r.corTexto
        SequentialAnimation on opacity {
          running: r.ocupado
          loops: Animation.Infinite
          PauseAnimation { duration: index * 120 }
          NumberAnimation { from: 0.2; to: 1; duration: 300 }
          NumberAnimation { from: 1; to: 0.2; duration: 300 }
          PauseAnimation { duration: (2 - index) * 120 }
        }
      }
    }
  }

  Rectangle {
    anchors.fill: parent
    anchors.margins: -3
    radius: r.radius + 3
    color: "transparent"
    border.width: 1.5
    border.color: Tema.realce
    opacity: r.activeFocus ? 0.6 : 0
    Behavior on opacity { NumberAnimation { duration: Tema.rapido } }
  }

  MouseArea {
    id: area
    anchors.fill: parent
    hoverEnabled: true
    enabled: r.habilitado && !r.ocupado
    cursorShape: Qt.PointingHandCursor
    onClicked: r.clicado()
  }
}
