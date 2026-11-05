import QtQuick
import qs.Comum

// Slider with a value bubble. `movido` fires while dragging (live preview),
// `solto` once on release / key / wheel (commit).
Item {
  id: r
  property real de: 0
  property real ate: 100
  property real passo: 1
  property real valor: 0
  property int casas: 0
  property string sufixo: ""
  property var formatar: null
  property bool habilitado: true
  property bool mostrarValor: true
  signal movido(real v)
  signal solto(real v)

  implicitWidth: 240
  implicitHeight: 32
  opacity: habilitado ? 1 : 0.4
  activeFocusOnTab: habilitado

  property real _arrasto: valor
  property bool _arrastando: false
  // After a commit, keep showing the chosen value until the backing value
  // catches up (the parent re-reads the real config), so the knob never snaps back.
  property bool _pendente: false
  onValorChanged: _pendente = false
  Timer { id: soltarPendente; interval: 2500; onTriggered: r._pendente = false }
  readonly property real atual: (_arrastando || _pendente) ? _arrasto : valor
  readonly property real fracao: ate === de ? 0 : Math.max(0, Math.min(1, (atual - de) / (ate - de)))

  function texto(v) {
    if (formatar) return formatar(v)
    return Number(v).toFixed(casas).replace(".", I18n.decimal) + sufixo
  }
  function ajustar(v) {
    var n = Math.round((v - de) / passo) * passo + de
    n = Math.max(de, Math.min(ate, n))
    return Number(n.toFixed(4))
  }
  function deX(px) { return ajustar(de + Math.max(0, Math.min(1, (px - pega.width / 2) / (trilho.width - pega.width))) * (ate - de)) }
  function passoTeclado(d) {
    if (!habilitado) return
    var v = ajustar(atual + d * passo)
    if (v !== atual) { _arrasto = v; _pendente = true; soltarPendente.restart(); r.movido(v); r.solto(v) }
  }

  Keys.onLeftPressed: passoTeclado(-1)
  Keys.onRightPressed: passoTeclado(1)
  Keys.onDownPressed: passoTeclado(-1)
  Keys.onUpPressed: passoTeclado(1)

  Item {
    id: trilho
    anchors.verticalCenter: parent.verticalCenter
    width: parent.width
    height: 18

    Rectangle {
      anchors.verticalCenter: parent.verticalCenter
      width: parent.width
      height: area.containsMouse || r._arrastando ? 6 : 4
      radius: Tema.raio > 0 ? height / 2 : 1
      color: Tema.superficieMax
      Behavior on height { NumberAnimation { duration: Tema.rapido } }

      Rectangle {
        height: parent.height
        radius: parent.radius
        width: pega.x + pega.width / 2
        color: Tema.realce
        Behavior on color { ColorAnimation { duration: Tema.medio } }
      }
    }

    Rectangle {
      id: pega
      width: r._arrastando ? 20 : 16
      height: width
      radius: Tema.raio > 0 ? width / 2 : 3
      anchors.verticalCenter: parent.verticalCenter
      x: r.fracao * (trilho.width - 16) - (width - 16) / 2
      color: Tema.realce
      border.width: 3
      border.color: Tema.janela
      Behavior on width { NumberAnimation { duration: Tema.rapido; easing.type: Easing.OutBack } }
      Behavior on x { enabled: !r._arrastando; NumberAnimation { duration: Tema.medio; easing.type: Tema.curva } }

      Rectangle {
        anchors.centerIn: parent
        width: parent.width + 8
        height: width
        radius: Tema.raio > 0 ? width / 2 : 4
        color: "transparent"
        border.width: 1.5
        border.color: Tema.realce
        opacity: r.activeFocus ? 0.55 : 0
      }
    }

    // Value bubble
    Rectangle {
      id: bolha
      visible: r.mostrarValor
      opacity: r._arrastando || r.activeFocus || area.containsMouse ? 1 : 0
      scale: opacity > 0 ? 1 : 0.8
      Behavior on opacity { NumberAnimation { duration: Tema.rapido } }
      Behavior on scale { NumberAnimation { duration: Tema.medio; easing.type: Easing.OutBack } }
      width: Math.max(34, rotuloBolha.implicitWidth + 14)
      height: 22
      radius: Tema.raioPequeno
      color: Tema.texto
      x: Math.max(-6, Math.min(trilho.width - width + 6, pega.x + pega.width / 2 - width / 2))
      y: -height - 6
      z: 5
      Texto {
        id: rotuloBolha
        anchors.centerIn: parent
        text: r.texto(r.atual)
        color: Tema.janela
        font.pixelSize: Tema.tLegenda
        font.weight: Font.DemiBold
      }
    }
  }

  MouseArea {
    id: area
    anchors.fill: parent
    anchors.topMargin: -4
    anchors.bottomMargin: -4
    hoverEnabled: true
    enabled: r.habilitado
    cursorShape: Qt.PointingHandCursor
    preventStealing: true
    onPressed: function(m) {
      r.forceActiveFocus()
      r._arrasto = r.deX(m.x)
      r._arrastando = true
      r.movido(r._arrasto)
    }
    onPositionChanged: function(m) {
      if (!pressed) return
      var v = r.deX(m.x)
      if (v !== r._arrasto) { r._arrasto = v; r.movido(v) }
    }
    onReleased: {
      var v = r._arrasto
      r._pendente = true
      soltarPendente.restart()
      r._arrastando = false
      r.solto(v)
    }
    onWheel: function(w) {
      r.passoTeclado(w.angleDelta.y > 0 ? 1 : -1)
    }
  }
}
