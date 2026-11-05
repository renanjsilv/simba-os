import "idiomas"
import QtQuick 6.11
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import qs.Commons

// Central de controle do Simba OS (como a do Windows 11 / macOS).
// Na barra: ícones de rede, som e bateria num botão só.
//   clique   abre a central (Wi-Fi, Bluetooth, Não perturbe, Modo escuro,
//            Luz noturna, Economia de energia, volume, brilho, bateria)
//   rolar    muda o volume
// Estado e ações: /usr/bin/simba-central.
Item {
  id: root
  property var bar
  property string moduleName
  property var settings: ({})

  readonly property bool vertical: bar ? bar.vertical : false
  readonly property int barSize: bar ? bar.barSize : 26
  readonly property color fg: bar ? bar.barForeground : Color.foreground
  readonly property string fonte: bar ? bar.fontFamily : "monospace"
  readonly property string ajudante: "/usr/bin/simba-central"

  property var st: ({ wifi: true, ssid: "", bluetooth: false, naoperturbe: false, claro: false, luznoturna: false,
                      economia: false, volume: 50, mudo: false, brilho: 100, bateria: null, carregando: false })

  // ── cores do painel (segue o tema; destaque cinza vira o texto, como na Configurações) ──
  function lum(c) { return 0.2126 * c.r + 0.7152 * c.g + 0.0722 * c.b }
  function sat(c) { var mx = Math.max(c.r, c.g, c.b), mn = Math.min(c.r, c.g, c.b); return mx === 0 ? 0 : (mx - mn) / mx }
  readonly property color fundo: Color.popups.background
  readonly property color texto: Color.popups.text
  readonly property bool escuro: lum(fundo) < 0.5
  readonly property color realce: sat(Color.accent) > 0.18 ? Color.accent : texto
  readonly property color sobreRealce: Math.abs(lum(realce) - lum(fundo)) > Math.abs(lum(realce) - lum(texto)) ? fundo : texto
  function alfa(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

  // ── ícones de estado ─────────────────────────────────────────────────────
  readonly property string gWifi: !st.wifi ? "\u{F092D}" : (st.ssid ? "\u{F0928}" : "\u{F092F}")
  readonly property string gVol: st.mudo || st.volume === 0 ? "\u{F075F}" : (st.volume < 34 ? "\u{F057F}" : (st.volume < 67 ? "\u{F0580}" : "\u{F057E}"))
  function gBat(p, c) {
    if (p === null || p === undefined) return "\u{F06A5}"
    var i = Math.max(0, Math.min(10, Math.round(p / 10)))
    if (c) return ["\u{F089F}", "\u{F089C}", "\u{F0086}", "\u{F0087}", "\u{F0088}", "\u{F089D}", "\u{F0089}", "\u{F089E}", "\u{F008A}", "\u{F008B}", "\u{F0085}"][i]
    return ["\u{F008E}", "\u{F007A}", "\u{F007B}", "\u{F007C}", "\u{F007D}", "\u{F007E}", "\u{F007F}", "\u{F0080}", "\u{F0081}", "\u{F0082}", "\u{F0079}"][i]
  }

  implicitWidth: vertical ? barSize : linha.implicitWidth + 16
  implicitHeight: vertical ? coluna.implicitHeight + 10 : barSize

  // ── leitura do estado ────────────────────────────────────────────────────
  Process {
    id: ler
    command: [root.ajudante, "estado"]
    stdout: StdioCollector {
      onStreamFinished: { try { var v = JSON.parse(text); if (!root.arrastando) root.st = v; else root.stPendente = v } catch (e) {} }
    }
  }
  property bool arrastando: false
  property var stPendente: null
  onArrastandoChanged: if (!arrastando && stPendente) { st = stPendente; stPendente = null }
  function atualizar() { if (!ler.running) ler.running = true }
  Timer { interval: painel.visible ? 1500 : 6000; running: true; repeat: true; triggeredOnStart: true; onTriggered: root.atualizar() }
  function acao(args, depois) {
    Quickshell.execDetached([root.ajudante].concat(args))
    reler.restart()
  }
  Timer { id: reler; interval: 450; onTriggered: root.atualizar() }

  // ── botão na barra ───────────────────────────────────────────────────────
  Rectangle {
    anchors.fill: parent; anchors.margins: 3; radius: 8
    color: root.fg
    opacity: area.pressed ? 0.16 : (area.containsMouse || painel.visible ? 0.09 : 0)
    Behavior on opacity { NumberAnimation { duration: 100 } }
  }
  Row {
    id: linha
    visible: !root.vertical
    anchors.centerIn: parent
    spacing: 10
    Repeater {
      model: [root.gWifi, root.gVol, root.gBat(root.st.bateria, root.st.carregando)]
      Text {
        required property var modelData
        text: modelData; color: root.fg
        font.family: root.fonte; font.pixelSize: Math.round(root.barSize * 0.5)
        anchors.verticalCenter: parent.verticalCenter
      }
    }
  }
  Column {
    id: coluna
    visible: root.vertical
    anchors.centerIn: parent
    spacing: 6
    Repeater {
      model: [root.gWifi, root.gVol, root.gBat(root.st.bateria, root.st.carregando)]
      Text { required property var modelData; text: modelData; color: root.fg; font.family: root.fonte; font.pixelSize: Math.round(root.barSize * 0.5) }
    }
  }
  MouseArea {
    id: area
    anchors.fill: parent
    hoverEnabled: true
    cursorShape: Qt.PointingHandCursor
    onClicked: { if (painel.visible) painel.visible = false; else { root.atualizar(); painel.visible = true } }
    onWheel: function(w) {
      var v = Math.max(0, Math.min(100, root.st.volume + (w.angleDelta.y > 0 ? 5 : -5)))
      root.st = Object.assign({}, root.st, { volume: v, mudo: false })
      root.acao(["volume", String(v)])
    }
  }

  // simba-shell central alternar|abrir|fechar  (Super+A, como no Windows 11)
  IpcHandler {
    target: "central"
    function alternar(): void { if (painel.visible) painel.visible = false; else { root.atualizar(); painel.visible = true } }
    function abrir(): void { root.atualizar(); painel.visible = true }
    function fechar(): void { painel.visible = false }
  }

  // ── a central ────────────────────────────────────────────────────────────
  PopupWindow {
    id: painel
    visible: false
    color: "transparent"
    implicitWidth: 372
    implicitHeight: caixa.implicitHeight + 24
    anchor.item: root
    anchor.rect.x: root.vertical ? (root.bar && root.bar.position === "right" ? -implicitWidth - 6 : root.width + 6) : root.width - implicitWidth + 4
    anchor.rect.y: root.vertical ? root.height - implicitHeight : (root.bar && root.bar.position === "bottom" ? -implicitHeight - 6 : root.height + 6)

    property bool grabPronto: false
    onVisibleChanged: { grabPronto = false; if (visible) ativarGrab.restart() }
    Timer { id: ativarGrab; interval: 60; onTriggered: painel.grabPronto = painel.visible }
    HyprlandFocusGrab { active: painel.grabPronto; windows: [painel]; onCleared: painel.visible = false }

    Rectangle {
      id: fundoPainel
      anchors.fill: parent; anchors.margins: 8
      radius: 16
      color: root.fundo
      border.width: 1; border.color: root.alfa(root.texto, root.escuro ? 0.12 : 0.14)
      opacity: painel.visible ? 1 : 0
      transform: Translate { y: painel.visible ? 0 : 8; Behavior on y { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } } }
      Behavior on opacity { NumberAnimation { duration: 140 } }

      Column {
        id: caixa
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14 }
        spacing: 14

        // botões rápidos (3 × 2)
        Grid {
          id: grade
          columns: 3; spacing: 10
          width: parent.width
          Repeater {
            model: [
              { id: "wifi", g: root.gWifi, t: I18n.t("Wi-Fi"), s: root.st.wifi ? (root.st.ssid || I18n.t("Sem conexão")) : I18n.t("Desligado"), on: root.st.wifi, cfg: "rede" },
              { id: "bluetooth", g: "\u{F00AF}", t: I18n.t("Bluetooth"), s: root.st.bluetooth ? I18n.t("Ligado") : I18n.t("Desligado"), on: root.st.bluetooth, cfg: "bluetooth" },
              { id: "naoperturbe", g: "\u{F009B}", t: I18n.t("Não perturbe"), s: root.st.naoperturbe ? I18n.t("Ligado") : I18n.t("Desligado"), on: root.st.naoperturbe, cfg: "notificacoes" },
              { id: "escuro", g: root.st.claro ? "\u{F0599}" : "\u{F0594}", t: root.st.claro ? I18n.t("Modo claro") : I18n.t("Modo escuro"), s: I18n.t("Tema do sistema"), on: !root.st.claro, cfg: "personalizacao" },
              { id: "luznoturna", g: "\u{F06E8}", t: I18n.t("Luz noturna"), s: root.st.luznoturna ? I18n.t("Ligada") : I18n.t("Desligada"), on: root.st.luznoturna, cfg: "tela" },
              { id: "economia", g: "\u{F032A}", t: I18n.t("Economia"), s: root.st.economia ? I18n.t("Ligada") : I18n.t("Desempenho"), on: root.st.economia, cfg: "energia" }
            ]
            delegate: Rectangle {
              id: bloco
              required property var modelData
              width: (grade.width - grade.spacing * 2) / 3
              height: 76
              radius: 12
              color: modelData.on ? root.realce : (m.containsMouse ? root.alfa(root.texto, 0.10) : root.alfa(root.texto, root.escuro ? 0.06 : 0.05))
              border.width: modelData.on ? 0 : 1
              border.color: root.alfa(root.texto, 0.08)
              scale: m.pressed ? 0.96 : 1
              Behavior on color { ColorAnimation { duration: 140 } }
              Behavior on scale { NumberAnimation { duration: 90 } }
              readonly property color cor: modelData.on ? root.sobreRealce : root.texto
              Column {
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 10; rightMargin: 8 }
                spacing: 2
                Text { text: bloco.modelData.g; color: bloco.cor; font.family: root.fonte; font.pixelSize: 19 }
                Text { width: parent.width; text: bloco.modelData.t; color: bloco.cor; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight }
                Text { width: parent.width; text: bloco.modelData.s; color: bloco.cor; opacity: 0.72; font.pixelSize: 10; elide: Text.ElideRight }
              }
              MouseArea {
                id: m
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                cursorShape: Qt.PointingHandCursor
                onClicked: function(e) {
                  if (e.button === Qt.RightButton) {   // botão direito: as configurações daquilo
                    painel.visible = false
                    Quickshell.execDetached(["/usr/bin/configuracoes", bloco.modelData.cfg])
                    return
                  }
                  // a ação vai primeiro: trocar root.st recria este botão (o modelo
                  // depende dele) e, depois disso, "root" já não existe neste handler
                  var r = root, k = bloco.modelData.id, o = {}
                  r.acao([k])
                  o[k === "escuro" ? "claro" : k] = k === "escuro" ? !r.st.claro : !r.st[k]
                  r.st = Object.assign({}, r.st, o)   // responde na hora; o estado real vem logo depois
                }
              }
            }
          }
        }

        // controles deslizantes
        component Deslizante: Item {
          id: d
          property string glifo: ""
          property int valor: 0
          property int minimo: 0
          signal mudou(int v)
          signal clicouGlifo()
          width: parent.width; height: 34
          Text {
            id: ig
            anchors { left: parent.left; verticalCenter: parent.verticalCenter }
            width: 26
            text: d.glifo; color: root.texto; font.family: root.fonte; font.pixelSize: 17
            MouseArea { anchors.fill: parent; anchors.margins: -6; cursorShape: Qt.PointingHandCursor; onClicked: d.clicouGlifo() }
          }
          Item {
            id: trilho
            anchors { left: ig.right; leftMargin: 8; right: num.left; rightMargin: 10; verticalCenter: parent.verticalCenter }
            height: 22
            readonly property real k: Math.max(0, Math.min(1, d.valor / 100))
            Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 6; radius: 3; color: root.alfa(root.texto, 0.14) }
            Rectangle { anchors.verticalCenter: parent.verticalCenter; width: Math.max(6, parent.width * trilho.k); height: 6; radius: 3; color: root.realce }
            Rectangle {
              x: (parent.width - width) * trilho.k; anchors.verticalCenter: parent.verticalCenter
              width: 18; height: 18; radius: 9
              color: root.escuro ? "white" : root.fundo
              border.width: root.escuro ? 0 : 1; border.color: root.alfa(root.texto, 0.25)
              scale: arr.pressed ? 1.15 : 1
              Behavior on scale { NumberAnimation { duration: 90 } }
            }
            MouseArea {
              id: arr
              anchors.fill: parent; anchors.margins: -6
              cursorShape: Qt.PointingHandCursor
              preventStealing: true
              function valorEm(x) { return Math.round(Math.max(d.minimo, Math.min(100, (x - 6) / (trilho.width) * 100))) }
              onPressed: function(e) { root.arrastando = true; d.mudou(valorEm(e.x)) }
              onPositionChanged: function(e) { if (pressed) d.mudou(valorEm(e.x)) }
              onReleased: root.arrastando = false
              onWheel: function(w) { d.mudou(Math.max(d.minimo, Math.min(100, d.valor + (w.angleDelta.y > 0 ? 5 : -5)))) }
            }
          }
          Text {
            id: num
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            width: 30; horizontalAlignment: Text.AlignRight
            text: d.valor; color: root.texto; opacity: 0.7; font.pixelSize: 12
          }
        }
        // aplica no máximo a cada 60 ms enquanto arrasta
        Timer { id: aplicaVol; interval: 60; onTriggered: root.acao(["volume", String(root.st.volume)]) }
        Timer { id: aplicaBri; interval: 60; onTriggered: root.acao(["brilho", String(root.st.brilho)]) }

        Deslizante {
          glifo: root.gVol
          valor: root.st.mudo ? 0 : root.st.volume
          onMudou: function(v) { root.st = Object.assign({}, root.st, { volume: v, mudo: false }); if (!aplicaVol.running) aplicaVol.start() }
          onClicouGlifo: { root.acao(["mudo"]); root.st = Object.assign({}, root.st, { mudo: !root.st.mudo }) }
        }
        Deslizante {
          glifo: "\u{F00E0}"
          minimo: 1
          valor: root.st.brilho
          onMudou: function(v) { root.st = Object.assign({}, root.st, { brilho: v }); if (!aplicaBri.running) aplicaBri.start() }
        }

        // rodapé: bateria e atalhos
        Rectangle { width: parent.width; height: 1; color: root.alfa(root.texto, 0.10) }
        Item {
          width: parent.width; height: 30
          Row {
            anchors { left: parent.left; verticalCenter: parent.verticalCenter }
            spacing: 8
            Text { text: root.gBat(root.st.bateria, root.st.carregando); color: root.texto; font.family: root.fonte; font.pixelSize: 16; anchors.verticalCenter: parent.verticalCenter }
            Text {
              anchors.verticalCenter: parent.verticalCenter
              text: root.st.bateria === null || root.st.bateria === undefined ? I18n.t("Na tomada") : root.st.bateria + "%" + (root.st.carregando ? I18n.t(" · carregando") : "")
              color: root.texto; font.pixelSize: 12
            }
          }
          Row {
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            spacing: 4
            Repeater {
              model: [{ g: "\u{F0493}", dica: I18n.t("Configurações"), cmd: ["/usr/bin/configuracoes"] },
                      { g: "\u{F0425}", dica: I18n.t("Energia"), cmd: ["simba-shell", "shell", "toggle", "simba.menu", '{"menu":"system"}'] }]
              delegate: Rectangle {
                required property var modelData
                width: 30; height: 30; radius: 15
                color: mb.containsMouse ? root.alfa(root.texto, 0.10) : "transparent"
                Text { anchors.centerIn: parent; text: parent.modelData.g; color: root.texto; font.family: root.fonte; font.pixelSize: 16 }
                MouseArea { id: mb; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: { painel.visible = false; Quickshell.execDetached(parent.modelData.cmd) } }
              }
            }
          }
        }
      }
    }
  }
}
