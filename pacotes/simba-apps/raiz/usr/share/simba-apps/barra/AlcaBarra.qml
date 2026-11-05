import "idiomas"
import QtQuick 6.11
import Quickshell
import qs.Commons

// Alça de tamanho da barra (como a borda da barra de tarefas do Windows).
//   mouse na borda interna da barra → a borda acende e aparece o controle − / +
//   arrastar a borda              → prévia do novo tamanho; aplica ao soltar
//   duplo clique na borda         → volta ao tamanho padrão
// Quem aplica é `barra-tarefas altura <px>` (barra + ícones das tarefas juntos).
Item {
  id: alca

  property var barra            // o módulo tarefas (bar, vertical, barSize, fg)
  property var janela           // janela da barra (QsWindow)
  readonly property var bar: barra ? barra.bar : null
  readonly property bool vertical: barra ? barra.vertical : false
  readonly property string posicao: bar && bar.position ? bar.position : "bottom"
  readonly property int atual: barra ? barra.barSize : 26
  readonly property int minimo: 22
  readonly property int maximo: 60
  readonly property int padrao: 26
  readonly property int passo: 4

  // tamanho em edição (prévia); -1 = nenhum
  property int alvo: -1
  readonly property int mostrado: alvo > 0 ? alvo : atual

  function limitar(v) { return Math.max(minimo, Math.min(maximo, Math.round(v))) }
  function nomeTamanho(v) {
    if (v <= 23) return I18n.t("Compacta")
    if (v <= 28) return I18n.t("Normal")
    if (v <= 35) return I18n.t("Confortável")
    if (v <= 44) return I18n.t("Grande")
    return I18n.t("Enorme")
  }
  // cliques seguidos em − / + só mudam a prévia; o tamanho é gravado uma vez,
  // quando a pessoa para de clicar (antes, cada clique recarregava a barra no
  // meio do próximo e o tamanho "se perdia")
  function aplicar(v) {
    alvo = limitar(v)
    soltarPrevia.stop()
    enviar.restart()
  }
  function aplicarJa(v) { alvo = limitar(v); enviar.stop(); enviar.triggered() }
  Timer {
    id: enviar; interval: 450
    onTriggered: {
      if (alca.alvo > 0 && alca.alvo !== alca.atual) Quickshell.execDetached(["barra-tarefas", "altura", String(alca.alvo)])
      soltarPrevia.restart()
    }
  }
  // a barra recarrega com o tamanho novo; até lá a prévia segura o número
  Timer { id: soltarPrevia; interval: 2500; onTriggered: alca.alvo = -1 }
  onAtualChanged: if (alvo === atual) alvo = -1

  parent: janela ? janela.contentItem : null
  z: 1000
  // faixa sensível na borda que dá para a tela (bottom → em cima; top → embaixo...)
  readonly property int espessura: 5
  x: vertical ? (posicao === "left" ? (parent ? parent.width - espessura : 0) : 0) : 0
  y: vertical ? 0 : (posicao === "top" ? (parent ? parent.height - espessura : 0) : 0)
  width: vertical ? espessura : (parent ? parent.width : 0)
  height: vertical ? (parent ? parent.height : 0) : espessura

  // linha que acende na borda
  Rectangle {
    anchors.fill: parent
    anchors.topMargin: !alca.vertical && alca.posicao === "bottom" ? 0 : 3
    anchors.bottomMargin: !alca.vertical && alca.posicao === "top" ? 0 : 3
    anchors.leftMargin: alca.vertical && alca.posicao === "right" ? 0 : (alca.vertical ? 3 : 0)
    anchors.rightMargin: alca.vertical && alca.posicao === "left" ? 0 : (alca.vertical ? 3 : 0)
    color: Color.accent
    opacity: zona.pressed ? 0.95 : (zona.containsMouse || controle.visible ? 0.55 : 0)
    Behavior on opacity { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
  }

  Item { id: pontoMouse; width: 1; height: 1 }

  MouseArea {
    id: zona
    anchors.fill: parent
    anchors.margins: -1
    hoverEnabled: true
    cursorShape: alca.vertical ? Qt.SizeHorCursor : Qt.SizeVerCursor
    acceptedButtons: Qt.LeftButton
    preventStealing: true
    property real inicio: 0
    property int base: 0
    function deslocamento(m) {
      var p = mapToItem(null, m.x, m.y)
      var d = alca.vertical ? p.x - inicio : p.y - inicio
      // afastar-se da borda da tela aumenta
      return (alca.posicao === "bottom" || alca.posicao === "right") ? -d : d
    }
    onEntered: { esconder.stop(); mostrar.restart() }
    onExited: { mostrar.stop(); if (!pressed) esconder.restart() }
    onPositionChanged: function(m) {
      if (!pressed) {
        pontoMouse.x = alca.vertical ? 0 : m.x
        pontoMouse.y = alca.vertical ? m.y : 0
        return
      }
      alca.alvo = alca.limitar(base + deslocamento(m))
      soltarPrevia.stop()
    }
    onPressed: function(m) {
      var p = mapToItem(null, m.x, m.y)
      inicio = alca.vertical ? p.x : p.y
      enviar.stop()
      base = alca.mostrado
      alca.alvo = base
      soltarPrevia.stop()
      controle.visible = true
    }
    onReleased: function(m) {
      if (alca.alvo > 0) alca.aplicarJa(alca.alvo)
      if (!containsMouse) esconder.restart()
    }
    onDoubleClicked: alca.aplicarJa(alca.padrao)
  }

  Timer { id: mostrar; interval: 260; onTriggered: { controle.alvoAncora = pontoMouse; controle.visible = true } }
  Timer {
    id: esconder; interval: 700
    onTriggered: if (!zona.containsMouse && !zona.pressed && !caixaHover.hovered) controle.visible = false
  }

  // ── prévia do tamanho novo enquanto arrasta ─────────────────────────────
  PopupWindow {
    id: fantasma
    color: "transparent"
    visible: zona.pressed && alca.alvo > 0 && alca.alvo !== alca.atual
    readonly property int novo: Math.max(alca.alvo, 1)
    implicitWidth: alca.vertical ? novo : (alca.parent ? alca.parent.width : 100)
    implicitHeight: alca.vertical ? (alca.parent ? alca.parent.height : 100) : novo
    anchor.item: alca.parent
    anchor.rect.x: alca.vertical && alca.posicao === "right" ? alca.atual - novo : 0
    anchor.rect.y: !alca.vertical && alca.posicao === "bottom" ? alca.atual - novo : 0
    Rectangle {
      anchors.fill: parent
      color: Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.10)
      border.width: 2
      border.color: Qt.rgba(Color.accent.r, Color.accent.g, Color.accent.b, 0.75)
      radius: 4
    }
  }

  // ── controle flutuante: − tamanho + ─────────────────────────────────────
  PopupWindow {
    id: controle
    property var alvoAncora: pontoMouse
    color: "transparent"
    visible: false
    implicitWidth: caixa.implicitWidth + 16
    implicitHeight: caixa.implicitHeight + 16
    anchor.item: alvoAncora
    anchor.rect.x: alca.vertical ? (alca.posicao === "right" ? -implicitWidth - 6 : alca.atual + 6) : -implicitWidth / 2
    anchor.rect.y: alca.vertical ? -implicitHeight / 2 : (alca.posicao === "bottom" ? -implicitHeight - 8 - Math.max(0, alca.mostrado - alca.atual) : alca.atual + 8)

    HoverHandler {
      id: caixaHover
      onHoveredChanged: hovered ? esconder.stop() : esconder.restart()
    }

    Rectangle {
      id: fundo
      anchors.fill: parent
      anchors.margins: 4
      radius: 12
      color: Color.popups.background
      border.width: 1
      border.color: Qt.rgba(Color.popups.text.r, Color.popups.text.g, Color.popups.text.b, 0.14)
      opacity: controle.visible ? 1 : 0
      scale: controle.visible ? 1 : 0.96
      Behavior on opacity { NumberAnimation { duration: 140 } }
      Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutCubic } }

      Row {
        id: caixa
        anchors.centerIn: parent
        spacing: 6
        padding: 4

        component BotaoRedondo: Rectangle {
          id: b
          property string glifo: ""
          property string dica: ""
          property bool ativo: true
          signal clicado()
          width: 30; height: 30; radius: 15
          color: !ativo ? "transparent" : (m.pressed ? Qt.rgba(Color.popups.text.r, Color.popups.text.g, Color.popups.text.b, 0.20)
                 : (m.containsMouse ? Qt.rgba(Color.popups.text.r, Color.popups.text.g, Color.popups.text.b, 0.10) : "transparent"))
          opacity: ativo ? 1 : 0.35
          Behavior on color { ColorAnimation { duration: 100 } }
          Text {
            anchors.centerIn: parent
            text: b.glifo
            color: Color.popups.text
            font.family: alca.bar ? alca.bar.fontFamily : "monospace"
            font.pixelSize: 16
          }
          MouseArea {
            id: m
            anchors.fill: parent
            hoverEnabled: true
            enabled: b.ativo
            cursorShape: Qt.PointingHandCursor
            onClicked: b.clicado()
          }
        }

        BotaoRedondo {
          glifo: "󰍴"
          ativo: alca.mostrado > alca.minimo
          onClicado: alca.aplicar(alca.mostrado - alca.passo)
        }
        Column {
          anchors.verticalCenter: parent.verticalCenter
          width: 116
          spacing: 1
          Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: alca.nomeTamanho(alca.mostrado)
            color: Color.popups.text
            font.family: alca.bar ? alca.bar.fontFamily : "monospace"
            font.pixelSize: 12
            font.weight: Font.DemiBold
          }
          // trilho com a posição atual entre o mínimo e o máximo
          Item {
            width: parent.width; height: 8
            Rectangle {
              anchors.verticalCenter: parent.verticalCenter
              width: parent.width; height: 3; radius: 2
              color: Qt.rgba(Color.popups.text.r, Color.popups.text.g, Color.popups.text.b, 0.15)
            }
            Rectangle {
              anchors.verticalCenter: parent.verticalCenter
              width: Math.max(6, parent.width * (alca.mostrado - alca.minimo) / (alca.maximo - alca.minimo)); height: 3; radius: 2
              color: Color.accent
              Behavior on width { NumberAnimation { duration: 120 } }
            }
          }
          Text {
            width: parent.width
            horizontalAlignment: Text.AlignHCenter
            text: zona.pressed ? alca.mostrado + " px" : I18n.t("arraste a borda")
            color: Color.popups.text
            opacity: 0.55
            font.family: alca.bar ? alca.bar.fontFamily : "monospace"
            font.pixelSize: 10
          }
        }
        BotaoRedondo {
          glifo: "󰐕"
          ativo: alca.mostrado < alca.maximo
          onClicado: alca.aplicar(alca.mostrado + alca.passo)
        }
        BotaoRedondo {
          glifo: "󰑓"
          ativo: alca.mostrado !== alca.padrao
          onClicado: alca.aplicar(alca.padrao)
        }
      }
    }
  }
}
