import "idiomas"
import QtQuick 6.11
import Quickshell
import Quickshell.Io
import qs.Commons

// Módulo da Nuvem (Simba Conta) para a barra:
// Mostra o status da sincronização com o Google Drive e anima durante envio/recebimento.
Item {
  id: root
  property var bar
  property string moduleName
  property var settings: ({})
  readonly property bool vertical: bar ? bar.vertical : false
  readonly property int barSize: bar ? bar.barSize : 26
  readonly property color fg: bar ? bar.barForeground : Color.foreground
  readonly property string fonte: bar && bar.fontFamily ? bar.fontFamily : "JetBrainsMono Nerd Font"
  readonly property int tamIcone: 16

  FileView {
    id: nuvemFile
    path: Quickshell.env("HOME") + "/.local/state/conta/estado.json"
    watchChanges: true
    printErrors: false
    property var dados: ({})
    readonly property bool conectado: dados && (dados.ultima || dados.remoto_meta || dados.conectado)
    readonly property bool sincronizando: dados && (dados.sincronizando || dados.rodando || (dados.progresso && dados.progresso !== ""))
    readonly property string erro: dados && dados.resultado === "erro" ? String(dados.erro || "") : ""
    onFileChanged: reload()
    onLoaded: { try { dados = JSON.parse(text()) } catch (e) { dados = {} } }
  }

  visible: nuvemFile.conectado
  implicitWidth: visible ? (vertical ? barSize : tamIcone + 12) : 0
  implicitHeight: visible ? (vertical ? tamIcone + 12 : barSize) : 0

  Rectangle {
    anchors.fill: parent; anchors.margins: 2; radius: Math.min(7, height / 2)
    color: root.fg
    opacity: area.containsMouse ? 0.08 : 0
  }

  Text {
    id: icone
    anchors.centerIn: parent
    text: nuvemFile.sincronizando ? "\u{F06B0}" : (nuvemFile.erro !== "" ? "\u{F0028}" : "\u{F01BE}")
    color: nuvemFile.erro !== "" ? Color.urgent : (nuvemFile.sincronizando ? Color.accent : root.fg)
    font.family: root.fonte
    font.pixelSize: root.tamIcone
    opacity: nuvemFile.sincronizando ? pulsoAnim.opacidade : 0.85

    RotationAnimation on rotation {
      running: nuvemFile.sincronizando
      from: 0; to: 360
      duration: 1200
      loops: Animation.Infinite
    }
  }

  SequentialAnimation {
    id: pulsoAnim
    property real opacidade: 1.0
    running: nuvemFile.sincronizando
    loops: Animation.Infinite
    NumberAnimation { target: pulsoAnim; property: "opacidade"; from: 0.4; to: 1.0; duration: 600; easing.type: Easing.InOutQuad }
    NumberAnimation { target: pulsoAnim; property: "opacidade"; from: 1.0; to: 0.4; duration: 600; easing.type: Easing.InOutQuad }
  }

  MouseArea {
    id: area
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    cursorShape: Qt.PointingHandCursor
    onClicked: function(m) {
      if (m.button === Qt.RightButton) {
        Quickshell.execDetached(["/usr/bin/conta", "puxar", "--forcar"])
      } else {
        Quickshell.execDetached(["/usr/bin/configuracoes", "contas"])
      }
    }
    onEntered: {
      if (root.bar) {
        var msg = I18n.t("Simba Conta")
        if (nuvemFile.sincronizando) msg += ": " + I18n.t("Sincronizando...")
        else if (nuvemFile.erro !== "") msg += ": " + I18n.t("Erro na sincronização")
        else msg += ": " + I18n.t("Sincronizado")
        msg += "\n" + I18n.t("Clique: Configurações · Botão direito: Sincronizar agora")
        root.bar.showTooltip(root, msg)
      }
    }
    onExited: if (root.bar) root.bar.hideTooltip(root)
  }
}
