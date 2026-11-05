import QtQuick 6.11
import Quickshell
import Quickshell.Io
import qs.Commons

// Aviso de atualizações (simba-atualizar): só aparece quando há algo a atualizar.
// Clique: "Atualizar tudo" · botão direito: Configurações › Sistema.
Item {
  id: root
  property var bar
  property string moduleName
  property var settings: ({})
  readonly property bool vertical: bar ? bar.vertical : false
  readonly property int barSize: bar ? bar.barSize : 26
  readonly property color fg: bar ? bar.barForeground : Color.foreground
  property var dados: ({ total: 0 })
  readonly property int total: dados && dados.total ? dados.total : 0

  visible: total > 0
  implicitWidth: visible ? (vertical ? barSize : barSize + 4) : 0
  implicitHeight: visible ? (vertical ? barSize : barSize) : 0

  FileView {
    path: Quickshell.env("HOME") + "/.cache/simba/atualizacoes.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: { try { root.dados = JSON.parse(text()) } catch (e) { root.dados = { total: 0 } } }
  }

  Rectangle {
    anchors.fill: parent; anchors.margins: 3; radius: 6
    color: root.fg
    opacity: area.pressed ? 0.16 : (area.containsMouse ? 0.09 : 0)
    Behavior on opacity { NumberAnimation { duration: 100 } }
  }
  Text {
    anchors.centerIn: parent
    text: "\u{F06B0}"   // seta de atualização (Nerd Font)
    color: Color.accent
    font.family: root.bar ? root.bar.fontFamily : "monospace"
    font.pixelSize: Math.round(root.barSize * 0.55)
  }
  Rectangle {
    visible: root.total > 0
    anchors { right: parent.right; top: parent.top; rightMargin: 2; topMargin: 2 }
    width: Math.max(13, conta.implicitWidth + 6); height: 13; radius: 7
    color: Color.urgent
    Text { id: conta; anchors.centerIn: parent; text: root.total > 99 ? "99+" : root.total; color: "white"; font.pixelSize: 9; font.bold: true }
  }
  MouseArea {
    id: area
    anchors.fill: parent
    hoverEnabled: true
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    cursorShape: Qt.PointingHandCursor
    onClicked: function(m) {
      if (m.button === Qt.RightButton) Quickshell.execDetached(["/usr/bin/configuracoes", "sistema"])
      else Quickshell.execDetached(["simba-atualizar", "aplicar"])
    }
  }
}
