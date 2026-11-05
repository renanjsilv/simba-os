import QtQuick
import QtQuick.Effects
import Quickshell.Io
import qs.Comum

// "Mica": the current wallpaper, heavily blurred and tinted with the theme
// background, as the window material. Follows wallpaper changes.
Item {
  id: m
  property string papel: ""
  property real tinta: Tema.escuro ? 0.84 : 0.80

  Process {
    id: ler
    command: ["readlink", "-f", Tema.estadoSimba + "/background"]
    running: true
    stdout: StdioCollector { onStreamFinished: { var p = text.trim(); if (p && p !== m.papel) m.papel = p } }
  }
  Timer { interval: 2500; running: true; repeat: true; onTriggered: ler.running = true }
  Connections { target: Tema; function onTemaTrocado() { atraso.restart() } }
  Timer { id: atraso; interval: 1200; onTriggered: ler.running = true }

  Image {
    id: img
    anchors.fill: parent
    source: m.papel ? "file://" + m.papel : ""
    fillMode: Image.PreserveAspectCrop
    sourceSize.width: 480
    asynchronous: true
    cache: false
    visible: false
  }
  MultiEffect {
    id: efeito
    anchors.fill: parent
    source: img
    blurEnabled: true
    blur: 1.0
    blurMax: 64
    saturation: 0.15
    opacity: img.status === Image.Ready ? 1 : 0
    Behavior on opacity { NumberAnimation { duration: 600 } }
  }
  Rectangle {
    anchors.fill: parent
    color: Tema.alfa(Tema.janela, m.tinta)
    Behavior on color { ColorAnimation { duration: Tema.lento } }
  }
}
