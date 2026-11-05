import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import qs.Comum

// "Propriedades" card for a desktop item (Esc or click outside closes).
Scope {
  id: p
  property var area: null
  property var info: null
  property bool aberto: false
  property string tela: ""

  function abrir(caminho) {
    tela = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : ""
    info = null
    aberto = true
    Sistema.json([Sistema.bin + "/area", "info", caminho], function(v) { p.info = v })
  }
  function tamanho(b) {
    if (b === undefined || b === null) return ""
    var u = ["bytes", "KB", "MB", "GB", "TB"], i = 0, v = b
    while (v >= 1024 && i < u.length - 1) { v /= 1024; i++ }
    return (i === 0 ? v : v.toFixed(v < 10 ? 2 : 1)).toString().replace(".", I18n.decimal) + " " + u[i] + (i > 0 ? " (" + b.toLocaleString(Qt.locale(), "f", 0) + " bytes)" : "")
  }
  function data(s) { return s ? new Date(s * 1000).toLocaleString(Qt.locale(), I18n.t("dddd, d 'de' MMMM 'de' yyyy, HH:mm")) : "" }
  function perm(o) {
    if (!o) return ""
    var n = parseInt(o, 8), q = function(b) { return (b & 4 ? "ler" : "") + (b & 2 ? (b & 4 ? ", " : "") + "escrever" : "") + (b & 1 ? ((b & 6) ? ", " : "") + "executar" : "") || "nada" }
    return I18n.t("Você: ") + q(n >> 6) + I18n.t(" · Grupo: ") + q((n >> 3) & 7) + I18n.t(" · Outros: ") + q(n & 7)
  }

  Variants {
    model: p.aberto ? Quickshell.screens.filter(function(s) { return p.tela ? s.name === p.tela : s === Quickshell.screens[0] }) : []
    delegate: PanelWindow {
      id: w
      required property var modelData
      screen: modelData
      anchors { top: true; bottom: true; left: true; right: true }
      exclusionMode: ExclusionMode.Ignore
      color: "transparent"
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.namespace: "configuracoes-propriedades"
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

      Rectangle { anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.35) }
      MouseArea { anchors.fill: parent; onPressed: p.aberto = false }

      Rectangle {
        id: cartao
        anchors.centerIn: parent
        width: Math.min(480, w.width - 40)
        height: col.implicitHeight + 44
        radius: Tema.raioGrande + 4
        color: Tema.superficie
        border.width: 1
        border.color: Tema.linhaForte
        focus: true
        Component.onCompleted: { forceActiveFocus(); scale = 1; opacity = 1 }
        scale: 0.94; opacity: 0
        Behavior on scale { NumberAnimation { duration: Tema.medio; easing.type: Easing.OutBack } }
        Behavior on opacity { NumberAnimation { duration: Tema.rapido } }
        Keys.onEscapePressed: p.aberto = false
        Keys.onReturnPressed: p.aberto = false
        Sombra { alvo: cartao; deslocamento: 16 }
        MouseArea { anchors.fill: parent }

        ColumnLayout {
          id: col
          x: 22; y: 22
          width: parent.width - 44
          spacing: 12
          RowLayout {
            spacing: 14
            Glifo { g: p.info && p.info.pasta ? Icones.folder : Icones.fileDocumentOutline; tamanho: 34 }
            ColumnLayout {
              Layout.fillWidth: true
              spacing: 2
              Texto { text: p.info ? p.info.rotulo : I18n.t("Carregando…"); font.pixelSize: Tema.tTitulo + 2; font.weight: Font.Bold; elide: Text.ElideMiddle; Layout.fillWidth: true }
              Texto { text: p.info ? (p.info.tipoDescricao || p.info.mime) : ""; color: Tema.texto2; Layout.fillWidth: true; elide: Text.ElideRight }
            }
          }
          Rectangle { Layout.fillWidth: true; height: 1; color: Tema.linha }
          GridLayout {
            columns: 2
            columnSpacing: 16
            rowSpacing: 8
            Layout.fillWidth: true
            Repeater {
              model: !p.info ? [] : [
                [I18n.t("Nome"), p.info.nome],
                [I18n.t("Local"), String(p.info.local).replace(Sistema.home, "~")],
                [p.info.pasta ? I18n.t("Tamanho") : I18n.t("Tamanho"), p.tamanho(p.info.tamanho) + (p.info.pasta ? " · " + p.info.arquivos + " arquivos" + (p.info.parcial ? I18n.t(" (contagem parcial)") : "") : "")],
                [I18n.t("Modificado"), p.data(p.info.mtime)],
                [I18n.t("Acessado"), p.data(p.info.acesso)],
                [I18n.t("Permissões"), p.perm(p.info.permissoes)]
              ].concat(p.info.destino ? [[I18n.t("Aponta para"), p.info.destino]] : [])
              delegate: Repeater {
                required property var modelData
                model: [modelData[0], modelData[1]]
                delegate: Texto {
                  required property var modelData
                  required property int index
                  text: modelData
                  color: index === 0 ? Tema.texto3 : Tema.texto
                  wrapMode: index === 0 ? Text.NoWrap : Text.WrapAnywhere
                  Layout.fillWidth: index === 1
                  Layout.alignment: Qt.AlignTop
                }
              }
            }
          }
          RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: 6
            Item { Layout.fillWidth: true }
            Botao { texto: I18n.t("Abrir local"); onClicado: { p.aberto = false; Sistema.solto(["uwsm-app", "--", "nautilus", "--new-window", "--select", p.info.caminho]) } }
            Botao { texto: I18n.t("OK"); tipo: "primario"; onClicado: p.aberto = false }
          }
        }
      }
    }
  }
}
