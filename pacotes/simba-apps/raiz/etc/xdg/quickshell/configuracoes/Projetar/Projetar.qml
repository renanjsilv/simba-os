import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import qs.Comum

// Super+P: "Projetar" — Windows-style display mode switcher.
//
// Opens on the focused screen over a frosted capture of that screen. Super+P
// again (or ←/→, Tab, 1-4) moves the selection, Enter or a click applies, Esc
// closes. Applying runs `tela modo <m>`, which persists the mode and arms an
// auto-revert; the Confirmacao dialog then asks to keep it.
Scope {
  id: p
  property var confirmacao: null
  property bool aberto: false
  property var estado: null
  property int selecionado: 2
  property bool aplicando: false
  property string telaNome: ""
  property string novaTela: ""     // friendly name when opened because a new screen was plugged in

  // ── hotplug: remembered modes per screen (bin/tela lembrar/conectado) ─────
  readonly property var nomesModo: ({ notebook: I18n.t("Somente tela do notebook"), duplicar: I18n.t("Duplicar"), estender: I18n.t("Estender"), segunda: I18n.t("Somente segunda tela") })
  function aoConectar(saida) {
    Sistema.json([Sistema.tela, "conectado", saida], function(r) {
      if (!r) return
      if (r.acao === "aplicado" || r.acao === "igual")
        Sistema.notificar(I18n.t("Tela ") + r.nome + I18n.t(": modo ") + (p.nomesModo[r.modo] || r.modo) + (r.acao === "aplicado" ? " aplicado" : "") + I18n.t(" · Super+P para mudar"), "󰍹")
      else if (r.acao === "novo" && Preferencias.obter("monitores.perguntar", true) && !(p.confirmacao && p.confirmacao.aberta))
        p.abrir(r.nome)
    })
  }
  Timer { id: aoConectarTimer; interval: 1500; property var fila: []
    onTriggered: { var f = fila; fila = []; f.forEach(function(s) { p.aoConectar(s) }) } }
  Timer { id: segurancaTimer; interval: 800; onTriggered: Sistema.rodar([Sistema.tela, "seguranca"]) }
  Connections {
    target: Hyprland
    function onRawEvent(ev) {
      if (ev.name === "monitoraddedv2") {
        var saida = String(ev.data).split(",")[1]
        if (saida && aoConectarTimer.fila.indexOf(saida) < 0) { aoConectarTimer.fila = aoConectarTimer.fila.concat([saida]); aoConectarTimer.restart() }
      } else if (ev.name === "monitorremovedv2") {
        segurancaTimer.restart()
        if (p.aberto && p.novaTela) p.fechar()
      }
    }
  }
  // At login: never start with the panel off and nothing else; re-apply the
  // remembered mode of a screen that was already connected.
  Component.onCompleted: inicio.start()
  Timer {
    id: inicio
    interval: 3000
    onTriggered: Sistema.rodar([Sistema.tela, "seguranca"], function() {
      Sistema.json([Sistema.tela, "estado"], function(v) {
        if (v) v.monitores.filter(function(m) { return m.name !== v.interna && !m.disabled }).forEach(function(m) { p.aoConectar(m.name) })
      })
    })
  }

  readonly property var modos: [
    { id: "notebook", titulo: I18n.t("Somente tela do notebook"), dica: I18n.t("Desliga a segunda tela") },
    { id: "duplicar", titulo: I18n.t("Duplicar"), dica: I18n.t("A mesma imagem nas duas") },
    { id: "estender", titulo: I18n.t("Estender"), dica: I18n.t("Uma área de trabalho maior") },
    { id: "segunda", titulo: I18n.t("Somente segunda tela"), dica: I18n.t("Desliga a tela do notebook") }
  ]
  readonly property bool soUma: estado !== null && estado.externas.length === 0
  readonly property string modoAtual: estado ? (estado.modo === "unico" ? "notebook" : estado.modo) : ""

  function indiceDe(m) { for (var i = 0; i < modos.length; i++) if (modos[i].id === m) return i; return -1 }
  function permitido(i) { return !soUma || modos[i].id === "notebook" }

  function abrir(nova) {
    if (aberto) return
    novaTela = nova || ""
    telaNome = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : ""
    Sistema.json([Sistema.tela, "estado"], function(v) {
      p.estado = v
      var i = v ? p.indiceDe(v.modo === "unico" ? "notebook" : v.modo) : -1
      p.selecionado = p.novaTela ? 2 : (i >= 0 ? i : 2)
      p.aberto = true
    })
  }
  function fechar() { aberto = false }
  function alternar() {
    if (!aberto) { abrir(); return }
    mover(1)
  }
  function mover(d) {
    var n = modos.length
    var i = selecionado
    for (var k = 0; k < n; k++) {
      i = (i + d + n) % n
      if (permitido(i)) break
    }
    selecionado = i
  }
  function selecionar(m) { var i = indiceDe(m); if (i >= 0) selecionado = i }
  function aplicar(m) {
    var i = m ? indiceDe(m) : selecionado
    if (i < 0 || !permitido(i)) return
    var modo = modos[i].id
    if (modo === modoAtual) {
      // Choosing the current mode for a new screen still means "remember this".
      if (novaTela) Sistema.rodar([Sistema.tela, "lembrar"], function() {
        Sistema.notificar(I18n.t("Tela ") + p.novaTela + ": " + p.modos[i].titulo + I18n.t(" lembrado · Super+P para mudar"), "󰍹")
      })
      fechar(); return
    }
    aplicando = true
    Sistema.rodar([Sistema.tela, "modo", modo, "15"], function(out, code, err) {
      p.aplicando = false
      p.aberto = false
      if (code !== 0) {
        Sistema.notificar(I18n.t("Não foi possível mudar o modo: ") + (err.trim() || out.trim()), "󰍹")
        return
      }
      if (p.confirmacao) p.confirmacao.iniciar(I18n.t("Manter “") + p.modos[i].titulo + "”?")
    })
  }

  Variants {
    model: p.aberto ? Quickshell.screens.filter(function(s) { return p.telaNome === "" ? s === Quickshell.screens[0] : s.name === p.telaNome }) : []
    delegate: PanelWindow {
      id: w
      required property var modelData
      screen: modelData
      anchors { top: true; bottom: true; left: true; right: true }
      color: "transparent"
      exclusionMode: ExclusionMode.Ignore
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.namespace: "configuracoes-projetar"
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

      // Frosted glass: a still capture of this screen, blurred and tinted.
      ScreencopyView {
        id: captura
        anchors.fill: parent
        captureSource: w.modelData
        live: false
        visible: false
      }
      MultiEffect {
        anchors.fill: parent
        source: captura
        visible: captura.hasContent
        blurEnabled: true
        blur: 1
        blurMax: 64
        saturation: -0.3
        brightness: Tema.escuro ? -0.25 : 0.05
        opacity: 0
        Component.onCompleted: opacity = 1
        Behavior on opacity { NumberAnimation { duration: Tema.lento } }
      }
      Rectangle {
        anchors.fill: parent
        color: Tema.alfa(Tema.janela, Tema.escuro ? 0.55 : 0.45)
        opacity: 0
        Component.onCompleted: opacity = 1
        Behavior on opacity { NumberAnimation { duration: Tema.medio } }
      }
      MouseArea { anchors.fill: parent; onClicked: p.fechar() }

      Item {
        id: conteudo
        anchors.fill: parent
        focus: true
        Component.onCompleted: forceActiveFocus()
        Keys.onPressed: function(e) {
          if (e.key === Qt.Key_Escape) p.fechar()
          else if (e.key === Qt.Key_Right || e.key === Qt.Key_Down || (e.key === Qt.Key_Tab && !(e.modifiers & Qt.ShiftModifier))) p.mover(1)
          else if (e.key === Qt.Key_Left || e.key === Qt.Key_Up || e.key === Qt.Key_Backtab) p.mover(-1)
          else if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.key === Qt.Key_Space) p.aplicar()
          else if (e.key >= Qt.Key_1 && e.key <= Qt.Key_4) { var i = e.key - Qt.Key_1; if (p.permitido(i)) { p.selecionado = i; p.aplicar() } }
          else if (e.key === Qt.Key_P) p.mover(1)
          else return
          e.accepted = true
        }

        ColumnLayout {
          id: painel
          anchors.centerIn: parent
          width: Math.min(900, w.width - 48)
          spacing: 22
          scale: 0.94
          opacity: 0
          Component.onCompleted: { scale = 1; opacity = 1 }
          Behavior on scale { NumberAnimation { duration: Tema.lento; easing.type: Easing.OutBack; easing.overshoot: 1.1 } }
          Behavior on opacity { NumberAnimation { duration: Tema.medio } }

          ColumnLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 6
            RowLayout {
              Layout.alignment: Qt.AlignHCenter
              spacing: 10
              Glifo { g: Icones.monitorMultiple; tamanho: 26; color: Tema.texto }
              Texto { text: p.novaTela ? I18n.t("Nova tela detectada") : I18n.t("Projetar"); font.pixelSize: 30; font.weight: Font.Bold; font.letterSpacing: -0.5 }
            }
            Texto {
              Layout.alignment: Qt.AlignHCenter
              text: p.novaTela ? "“" + p.novaTela + I18n.t("” — como usar esta tela? A escolha fica lembrada para ela.")
                    : p.soUma ? I18n.t("Só uma tela conectada. Conecte um monitor ou projetor para duplicar ou estender.")
                            : I18n.t("Super+P ou ← → escolhem · Enter aplica · Esc fecha")
              color: Tema.texto2
            }
          }

          RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 14
            Repeater {
              model: p.modos
              delegate: Rectangle {
                id: cartao
                required property var modelData
                required property int index
                readonly property bool sel: index === p.selecionado
                readonly property bool atual: modelData.id === p.modoAtual
                readonly property bool ok: p.permitido(index)
                Layout.preferredWidth: Math.min(200, (painel.width - 42) / 4)
                Layout.preferredHeight: 214
                radius: Tema.raioGrande + 4
                color: sel ? Tema.superficieAlta : Tema.alfa(Tema.superficie, 0.92)
                border.width: sel ? 2 : 1
                border.color: sel ? Tema.realce : Tema.linha
                opacity: ok ? 1 : 0.38
                scale: sel ? 1.045 : (mc.containsMouse && ok ? 1.02 : 1)
                Behavior on scale { NumberAnimation { duration: Tema.medio; easing.type: Easing.OutBack } }
                Behavior on color { ColorAnimation { duration: Tema.medio } }
                Sombra { alvo: cartao; intensidade: cartao.sel ? 1 : 0.35; deslocamento: cartao.sel ? 16 : 6 }

                // staggered entrance
                transform: Translate { id: sobe; y: 26 }
                Component.onCompleted: entrada.start()
                SequentialAnimation {
                  id: entrada
                  PauseAnimation { duration: Tema.animacoes ? 40 + cartao.index * 55 : 0 }
                  NumberAnimation { target: sobe; property: "y"; to: 0; duration: Tema.lento; easing.type: Easing.OutBack; easing.overshoot: 1.3 }
                }

                ColumnLayout {
                  anchors.fill: parent
                  anchors.margins: 16
                  spacing: 6
                  Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 96
                    Ilustracao { anchors.centerIn: parent; modo: cartao.modelData.id; destaque: cartao.sel }
                  }
                  Texto {
                    text: cartao.modelData.titulo
                    font.pixelSize: Tema.tSubtitulo
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                  }
                  Texto {
                    text: cartao.modelData.dica
                    color: Tema.texto3
                    font.pixelSize: Tema.tLegenda + 1
                    wrapMode: Text.WordWrap
                    horizontalAlignment: Text.AlignHCenter
                    Layout.fillWidth: true
                  }
                  Item { Layout.fillHeight: true }
                  Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    visible: cartao.atual
                    implicitWidth: rotuloAtual.implicitWidth + 16
                    implicitHeight: 20
                    radius: Tema.raio > 0 ? 10 : 0
                    color: Tema.alfa(Tema.realce, 0.16)
                    Texto { id: rotuloAtual; anchors.centerIn: parent; text: I18n.t("EM USO"); font.pixelSize: Tema.tLegenda - 1; font.weight: Font.Bold; font.letterSpacing: 1.2; color: Tema.realce }
                  }
                  Texto {
                    Layout.alignment: Qt.AlignHCenter
                    visible: !cartao.atual
                    text: String(cartao.index + 1)
                    color: Tema.texto3
                    font.pixelSize: Tema.tLegenda
                  }
                }

                // applying shimmer
                Rectangle {
                  anchors.fill: parent
                  radius: parent.radius
                  color: Tema.realce
                  opacity: cartao.sel && p.aplicando ? 0.12 : 0
                  Behavior on opacity { NumberAnimation { duration: Tema.rapido } }
                }

                MouseArea {
                  id: mc
                  anchors.fill: parent
                  hoverEnabled: true
                  enabled: cartao.ok
                  cursorShape: Qt.PointingHandCursor
                  onEntered: p.selecionado = cartao.index
                  onClicked: { p.selecionado = cartao.index; p.aplicar() }
                }
              }
            }
          }

          RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 8
            Botao {
              texto: I18n.t("Mais configurações de tela")
              glifo: Icones.cog
              tipo: "fantasma"
              onClicado: { p.fechar(); Navegacao.abrir("tela") }
            }
          }
        }
      }
    }
  }
}
