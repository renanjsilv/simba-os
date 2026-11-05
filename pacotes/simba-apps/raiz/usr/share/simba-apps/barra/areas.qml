import "idiomas"
import QtQuick 6.11
import Quickshell
import Quickshell.Hyprland
import qs.Commons

// Áreas de trabalho em estilos mais discretos que o padrão do Simba.
//   estilo "pontos"   = um ponto por área; a atual vira uma pílula na cor de destaque
//   estilo "ocupadas" = só os números das áreas com janelas (e a atual)
// Clique vai para a área; a roda do mouse passa para a anterior/próxima.
// Configurado em Configurações › Barra (barra-tarefas areas <estilo>).
Item {
  id: root

  property var bar
  property string moduleName
  property var settings: ({})

  function opcao(k, padrao) { var v = settings ? settings[k] : undefined; return v === undefined || v === null ? padrao : v }
  readonly property string estilo: opcao("estilo", "pontos")
  readonly property int minimo: Number(opcao("quantidade", 5))

  readonly property bool vertical: bar ? bar.vertical : false
  readonly property int barSize: bar ? bar.barSize : 26
  readonly property color fg: bar ? bar.barForeground : Color.foreground
  readonly property int atual: Hyprland.focusedWorkspace ? Hyprland.focusedWorkspace.id : 1

  function ocupada(id) {
    var ws = Hyprland.workspaces.values
    for (var i = 0; i < ws.length; i++) if (ws[i].id === id) return ws[i].toplevels.values.length > 0
    return false
  }
  readonly property var ids: {
    var _ = Hyprland.workspaces.values.length, set = {}
    var ws = Hyprland.workspaces.values
    if (estilo !== "ocupadas") for (var n = 1; n <= minimo; n++) set[n] = true
    for (var i = 0; i < ws.length; i++) {
      var id = ws[i].id
      if (id < 1 || id > 10) continue
      if (estilo !== "ocupadas" || ws[i].toplevels.values.length > 0) set[id] = true
    }
    if (atual >= 1 && atual <= 10) set[atual] = true
    return Object.keys(set).map(Number).sort(function(a, b) { return a - b })
  }

  function ir(id) { Hyprland.dispatch('hl.dsp.focus({ workspace = "' + id + '" })') }

  implicitWidth: vertical ? barSize : linha.implicitWidth + 12
  implicitHeight: vertical ? linha.implicitHeight + 12 : barSize

  WheelHandler {
    onWheel: function(e) {
      var i = root.ids.indexOf(root.atual)
      var j = e.angleDelta.y < 0 ? Math.min(root.ids.length - 1, i + 1) : Math.max(0, i - 1)
      if (j !== i && j >= 0) root.ir(root.ids[j])
    }
  }

  Grid {
    id: linha
    anchors.centerIn: parent
    columns: root.vertical ? 1 : root.ids.length
    spacing: root.estilo === "pontos" ? 4 : 2

    Repeater {
      model: root.ids
      delegate: Item {
        id: cel
        required property int modelData
        readonly property bool foco: modelData === root.atual
        readonly property bool cheia: root.ocupada(modelData)
        readonly property bool pontos: root.estilo === "pontos"
        width: pontos ? (root.vertical ? 14 : (foco ? 22 : 12)) : 22
        height: pontos ? (root.vertical ? (foco ? 22 : 12) : 14) : 20
        Behavior on width { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
        Behavior on height { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }

        // pontos
        Rectangle {
          visible: cel.pontos
          anchors.centerIn: parent
          width: root.vertical ? 6 : (cel.foco ? 18 : 6)
          height: root.vertical ? (cel.foco ? 18 : 6) : 6
          radius: 3
          color: cel.foco ? Color.accent : root.fg
          opacity: cel.foco ? 1 : (cel.cheia ? 0.85 : (toque.containsMouse ? 0.55 : 0.28))
          Behavior on width { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
          Behavior on height { NumberAnimation { duration: 200; easing.type: Easing.OutCubic } }
          Behavior on color { ColorAnimation { duration: 200 } }
          Behavior on opacity { NumberAnimation { duration: 160 } }
        }

        // só ocupadas: números, a atual com fundo suave e traço de destaque
        Rectangle {
          visible: !cel.pontos
          anchors.fill: parent
          radius: 6
          color: root.fg
          opacity: cel.foco ? 0.12 : (toque.containsMouse ? 0.07 : 0)
          Behavior on opacity { NumberAnimation { duration: 140 } }
        }
        Text {
          visible: !cel.pontos
          anchors.centerIn: parent
          text: cel.modelData === 10 ? "0" : String(cel.modelData)
          color: cel.foco ? Color.accent : root.fg
          opacity: cel.foco || toque.containsMouse ? 1 : 0.7
          font.family: root.bar && root.bar.fontFamily ? root.bar.fontFamily : "monospace"
          font.pixelSize: 12
          font.weight: cel.foco ? Font.Bold : Font.Normal
        }

        MouseArea {
          id: toque
          anchors.fill: parent
          anchors.margins: -2
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: root.ir(cel.modelData)
          onEntered: if (root.bar) root.bar.showTooltip(cel, I18n.t("Área de trabalho ") + cel.modelData + I18n.t(" · Super+") + (cel.modelData === 10 ? 0 : cel.modelData))
          onExited: if (root.bar) root.bar.hideTooltip(cel)
        }
      }
    }
  }
}
