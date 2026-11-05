import QtQuick 6.11
import qs.Ui

BarWidget {
  id: root
  moduleName: "simba.menu"

  implicitWidth: button.implicitWidth
  implicitHeight: button.implicitHeight

  WidgetButton {
    id: button
    anchors.fill: parent
    bar: root.bar
    text: "\ue900"
    fontFamily: "simba"
    horizontalMargin: 7.5
    onPressed: function(button) {
      if (!root.bar) return
      if (button === Qt.RightButton) root.bar.run("xdg-terminal-exec")
      else root.bar.run("simba-shell shell toggle simba.menu '{\"menu\":\"root\"}'")
    }
  }
}
