import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import qs.Comum

// "Manter estas configurações de exibição?" — Windows-style safety net after
// any display change. Shown on every active screen; reverts by itself when the
// countdown ends. The revert does not depend on this UI: `tela modo`/`tela
// pendente` also arm a detached watchdog that undoes the change if nobody
// answers (e.g. the new mode left no visible screen).
Scope {
  id: c
  property bool aberta: false
  property int segundos: 15
  property int restante: segundos
  property string titulo: I18n.t("Manter estas configurações de exibição?")
  property var aoTerminar: null   // function(mantida)
  property real inicio: 0
  property real fracao: 1

  function iniciar(texto, terminar) {
    titulo = texto || I18n.t("Manter estas configurações de exibição?")
    aoTerminar = terminar || null
    restante = segundos
    fracao = 1
    inicio = Date.now()
    aberta = true
    relogio.restart()
  }

  function manter() {
    if (!aberta) return
    aberta = false
    relogio.stop()
    // Kept with an external screen connected: remember this mode for that screen.
    Sistema.rodar([Sistema.tela, "manter"], function() { Sistema.rodar([Sistema.tela, "lembrar"], function() { c.concluir(true) }) })
  }
  function reverter() {
    if (!aberta) return
    aberta = false
    relogio.stop()
    Sistema.rodar([Sistema.tela, "reverter"], function() {
      Sistema.notificar(I18n.t("Configurações de exibição revertidas"), "󰍹")
      c.concluir(false)
    })
  }
  function concluir(m) {
    var f = aoTerminar
    aoTerminar = null
    if (f) f(m)
  }

  Timer {
    id: relogio
    interval: 50
    repeat: true
    onTriggered: {
      var passado = (Date.now() - c.inicio) / 1000
      c.fracao = Math.max(0, 1 - passado / c.segundos)
      c.restante = Math.max(0, Math.ceil(c.segundos - passado))
      if (passado >= c.segundos) c.reverter()
    }
  }

  Variants {
    model: c.aberta ? Quickshell.screens : []
    delegate: PanelWindow {
      id: w
      required property var modelData
      screen: modelData
      readonly property bool principal: Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name === modelData.name : modelData === Quickshell.screens[0]
      anchors { top: true; bottom: true; left: true; right: true }
      color: "transparent"
      exclusionMode: ExclusionMode.Ignore
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.namespace: "configuracoes-confirmar"
      WlrLayershell.keyboardFocus: principal ? WlrKeyboardFocus.Exclusive : WlrKeyboardFocus.None

      Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.45)
        opacity: 0
        Component.onCompleted: opacity = 1
        Behavior on opacity { NumberAnimation { duration: Tema.medio } }
      }

      Rectangle {
        id: cartao
        width: Math.min(540, w.width - 40)
        height: col.implicitHeight + 48
        anchors.centerIn: parent
        radius: Tema.raioGrande + 4
        color: Tema.superficie
        border.width: 1
        border.color: Tema.linhaForte
        scale: 0.92
        opacity: 0
        Component.onCompleted: { scale = 1; opacity = 1; forceActiveFocus() }
        Behavior on scale { NumberAnimation { duration: Tema.lento; easing.type: Easing.OutBack; easing.overshoot: 1.2 } }
        Behavior on opacity { NumberAnimation { duration: Tema.medio } }
        Sombra { alvo: cartao; deslocamento: 18 }

        focus: true
        Keys.onReturnPressed: c.manter()
        Keys.onEnterPressed: c.manter()
        Keys.onEscapePressed: c.reverter()

        ColumnLayout {
          id: col
          anchors.left: parent.left
          anchors.right: parent.right
          anchors.top: parent.top
          anchors.margins: 24
          spacing: 14

          RowLayout {
            spacing: 18
            Item {
              Layout.preferredWidth: 64
              Layout.preferredHeight: 64
              Canvas {
                anchors.fill: parent
                property real f: c.fracao
                property color base: Tema.superficieMax
                property color cor: Tema.realce
                onFChanged: requestPaint()
                onPaint: {
                  var ctx = getContext("2d")
                  ctx.reset()
                  var r = width / 2 - 4
                  ctx.lineWidth = 4
                  ctx.strokeStyle = base
                  ctx.beginPath(); ctx.arc(width / 2, height / 2, r, 0, Math.PI * 2); ctx.stroke()
                  ctx.strokeStyle = cor
                  ctx.lineCap = Tema.raio > 0 ? "round" : "butt"
                  ctx.beginPath(); ctx.arc(width / 2, height / 2, r, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * f); ctx.stroke()
                }
              }
              Texto { anchors.centerIn: parent; text: c.restante; font.pixelSize: 22; font.weight: Font.Bold }
            }
            ColumnLayout {
              Layout.fillWidth: true
              spacing: 4
              Texto { text: c.titulo; font.pixelSize: Tema.tTitulo + 2; font.weight: Font.Bold; wrapMode: Text.WordWrap; Layout.fillWidth: true }
              Texto {
                text: I18n.t("Revertendo para as configurações anteriores em ") + c.restante + (c.restante === 1 ? " segundo." : " segundos.")
                color: Tema.texto2
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
              }
            }
          }

          RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 6
            spacing: 10
            Texto { text: I18n.t("Enter mantém · Esc reverte"); color: Tema.texto3; font.pixelSize: Tema.tLegenda + 1; Layout.fillWidth: true }
            Botao { texto: I18n.t("Reverter"); onClicado: c.reverter() }
            Botao { texto: I18n.t("Manter alterações"); tipo: "primario"; onClicado: c.manter() }
          }
        }
      }
    }
  }
}
