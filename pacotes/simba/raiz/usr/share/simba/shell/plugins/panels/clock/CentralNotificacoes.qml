import QtQuick 6.11
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import "../../notifications/components/PixelArte.js" as Px

// Central de notificações do Simba (acima da data e do calendário, como no Windows 11).
// Lista as últimas notificações do histórico (~/.local/state/simba/notifications/history),
// cada uma removível (×) e clicável: executa a ação dela (simba-exec-argv), abre a página
// certa das Configurações para os avisos do próprio sistema, ou foca a janela do app.
//
// Temas (~/.config/simba/notificacoes.json → "central"): auto, fluent, minimal, escuro,
// pixel-rpg, pixel-portatil, pixel-noturno. "auto" acompanha o estilo dos avisos.
Item {
  id: root

  property bool ativo: false              // o painel está aberto
  property color fg: Commons.Color.foreground
  property color bg: Commons.Color.popups.background
  property color destaque: Commons.Color.accent
  property string fonteSistema: "Adwaita Sans"
  signal acionado()                       // pede para fechar o painel depois de um clique

  readonly property string home: Quickshell.env("HOME")
  readonly property string pastaHistorico: home + "/.local/state/simba/notifications/history/"
  readonly property string simbaPath: Quickshell.env("SIMBA_PATH") || "/usr/share/simba"

  // ── preferências ────────────────────────────────────────────────────────
  property string estiloAviso: "rpg"
  property string temaEscolhido: "auto"
  property string temaForcado: ""          // prévias (Configurações)
  readonly property string tema: {
    var t = temaForcado || temaEscolhido
    if (["fluent", "minimal", "escuro", "pixel-rpg", "pixel-portatil", "pixel-noturno"].indexOf(t) >= 0) return t
    return ({ vidro: "fluent", windows: "fluent", suave: "minimal", pilula: "minimal", padrao: "minimal",
              escuro: "escuro", rpg: "pixel-rpg", balao: "pixel-rpg", janela: "pixel-rpg",
              portatil: "pixel-portatil", conquista: "pixel-noturno", "vidro-pixel": "pixel-noturno" })[estiloAviso] || "pixel-rpg"
  }
  readonly property bool pixel: tema.indexOf("pixel") === 0
  readonly property int px: 2

  FileView {
    path: root.home + "/.config/simba/notificacoes.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      try {
        var v = JSON.parse(text() || "{}")
        root.estiloAviso = v.estilo || "rpg"
        root.temaEscolhido = v.central || "auto"
      } catch (e) { root.estiloAviso = "rpg"; root.temaEscolhido = "auto" }
    }
    onLoadFailed: { root.estiloAviso = "rpg"; root.temaEscolhido = "auto" }
  }

  // ── cores por tema (sempre a partir das cores do tema do sistema) ───────
  function mistura(a, b, t) { return Qt.rgba(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t, 1) }
  readonly property bool invertido: tema === "escuro" || tema === "pixel-noturno"
  readonly property color cFundo: tema === "escuro" ? Qt.rgba(0.11, 0.11, 0.12, 1)
                                 : tema === "pixel-noturno" ? Qt.rgba(0.09, 0.09, 0.10, 1)
                                 : tema === "pixel-portatil" ? mistura(bg, fg, 0.33) : bg
  readonly property color cTexto: invertido ? "#f2f2f2" : (tema === "pixel-portatil" ? fg : fg)
  readonly property color cApagado: invertido ? "#a8a8a8" : mistura(fg, bg, 0.45)
  readonly property color cItem: tema === "escuro" ? Qt.rgba(1, 1, 1, 0.07)
                                : tema === "pixel-noturno" ? Qt.rgba(1, 1, 1, 0.06)
                                : tema === "pixel-portatil" ? bg
                                : tema === "minimal" ? "transparent" : mistura(bg, fg, 0.045)
  readonly property color cHover: invertido ? Qt.rgba(1, 1, 1, 0.13) : mistura(bg, fg, 0.09)
  readonly property color cBorda: invertido ? Qt.rgba(1, 1, 1, 0.16) : mistura(bg, fg, 0.16)
  readonly property string fonteTitulo: pixel ? "Simba Pixel" : fonteSistema

  // ── dados ───────────────────────────────────────────────────────────────
  property var itens: exemplo || []
  property var exemplo: null                // prévias: lista fixa, não lê o histórico
  property bool dnd: false
  // hora atual pelo SystemClock (o construtor Date não está disponível neste contexto)
  SystemClock { id: relogio; precision: SystemClock.Minutes }
  readonly property double agora: relogio.date.getTime()

  function ler() { if (exemplo) return; leitor.running = true; dndProc.running = true }

  Process {
    id: leitor
    running: false
    command: ["bash", "-c", "cd \"$1\" 2>/dev/null || exit 0; for f in $(ls -1r -- *.json 2>/dev/null | head -n 10); do printf '%s\\t' \"$f\"; tr -d '\\n' < \"$f\"; echo; done", "--", root.pastaHistorico]
    stdout: StdioCollector {
      waitForEnd: true
      onStreamFinished: {
        var lista = []
        var linhas = String(text || "").split("\n")
        for (var i = 0; i < linhas.length; i++) {
          var tab = linhas[i].indexOf("\t")
          if (tab < 0) continue
          try {
            var v = JSON.parse(linhas[i].slice(tab + 1))
            v.arquivo = linhas[i].slice(0, tab)
            lista.push(v)
          } catch (e) {}
        }
        // urgentes fixados no topo; o resto do mais novo para o mais antigo
        lista.sort(function(a, b) {
          var ua = a.urgency === 2 ? 1 : 0, ub = b.urgency === 2 ? 1 : 0
          if (ua !== ub) return ub - ua
          return (b.timestamp || 0) - (a.timestamp || 0)
        })
        root.itens = lista
      }
    }
  }
  Process {
    id: dndProc
    running: false
    command: ["simba-shell", "notifications", "isDnd"]
    stdout: StdioCollector { waitForEnd: true; onStreamFinished: root.dnd = String(text).trim() === "on" }
  }
  Process { id: acao; running: false }

  onAtivoChanged: if (ativo) ler()
  Timer { interval: 3000; repeat: true; running: root.ativo; onTriggered: root.ler() }

  function quando(ms) {
    var d = (root.agora - ms) / 1000
    if (d < 60) return "agora"
    if (d < 3600) return "há " + Math.round(d / 60) + " min"
    if (d < 86400) return "há " + Math.round(d / 3600) + " h"
    if (d < 172800) return "ontem"
    return "há " + Math.round(d / 86400) + " dias"
  }

  function remover(item) {
    acao.command = ["bash", "-c", "rm -f -- \"$1$2\" \"$1../images/${2%.json}\"-* 2>/dev/null; true", "--", root.pastaHistorico, item.arquivo]
    acao.running = true
    root.itens = root.itens.filter(function(x) { return x.arquivo !== item.arquivo })
  }

  function limparTudo() {
    acao.command = ["simba-shell", "notifications", "clear"]
    acao.running = true
    root.itens = []
  }

  function alternarDnd() {
    acao.command = ["simba-shell", "notifications", "toggleDnd"]
    acao.running = true
    root.dnd = !root.dnd
  }

  // Para onde levar cada aviso do próprio sistema (quando ele não trouxe ação).
  function destinoPorApp(app, titulo) {
    var a = String(app || "").toLowerCase(), t = String(titulo || "").toLowerCase()
    if (a === "conta" || a === "simba conta" || t.indexOf("backup") >= 0) return ["configuracoes", "contas"]
    if (a === "configurações" || a === "configuracoes") return ["configuracoes", "notificacoes"]
    if (t.indexOf("atualiza") >= 0) return ["configuracoes", "sistema"]
    if (a.indexOf("bluetooth") >= 0) return ["configuracoes", "bluetooth"]
    if (a.indexOf("wi-fi") >= 0 || a.indexOf("rede") >= 0 || a === "networkmanager") return ["configuracoes", "rede"]
    return null
  }

  function temAcao(item) { return !!(item.execArgv || destinoPorApp(item.app, item.summary) || item.app) }

  function acionar(item) {
    var argv = null
    try { var p = JSON.parse(item.execArgv || ""); if (Array.isArray(p) && p.length) argv = p } catch (e) {}
    if (!argv) argv = destinoPorApp(item.app, item.summary)
    if (!argv && item.app) argv = [root.simbaPath + "/bin/simba-hyprland-focus-app", String(item.app)]
    if (!argv) return
    Quickshell.execDetached(argv)
    remover(item)
    root.acionado()
  }

  implicitHeight: coluna.implicitHeight

  // ── fundo da seção (moldura do tema) ─────────────────────────────────────
  Rectangle {
    anchors.fill: parent
    visible: !root.pixel && root.tema !== "minimal"
    radius: root.tema === "escuro" ? 10 : 8
    color: root.tema === "escuro" ? root.cFundo : "transparent"
    border.width: root.tema === "fluent" ? 1 : 0
    border.color: root.cBorda
  }
  Canvas {
    id: moldura
    anchors.fill: parent
    visible: root.pixel
    antialiasing: false
    property string chave: root.tema + root.width + "x" + root.height + root.fg + root.bg
    onChaveChanged: requestPaint()
    onPaint: {
      var c = getContext("2d"); c.reset()
      if (!root.pixel) return
      var P = root.px, W = Math.floor(width / P), H = Math.floor(height / P)
      var f = String(root.cFundo), t = String(root.tema === "pixel-noturno" ? root.cApagado : root.fg)
      if (root.tema === "pixel-rpg") {
        Px.caixa(c, P, 0, 0, W, H, f, t, 2)
        Px.caixa(c, P, 2, 2, W - 4, H - 4, f, String(root.cBorda), 1)
      } else if (root.tema === "pixel-portatil") {
        Px.rect(c, P, 0, 0, W, H, String(root.fg))
        Px.rect(c, P, 1, 1, W - 2, H - 2, f)
      } else {
        Px.caixa(c, P, 0, 0, W, H, f, t, 2)
        Px.pontilhado(c, P, 2, 2, W - 4, 8, String(Qt.rgba(root.destaque.r, root.destaque.g, root.destaque.b, 0.35)))
      }
    }
  }

  ColumnLayout {
    id: coluna
    width: parent.width
    spacing: 0

    // ── cabeçalho ──
    RowLayout {
      Layout.fillWidth: true
      Layout.leftMargin: root.pixel ? 14 : 12
      Layout.rightMargin: root.pixel ? 18 : 10
      Layout.topMargin: root.pixel ? 10 : 8
      Layout.preferredHeight: 36
      spacing: 8
      Text {
        text: "Notificações"
        font.family: root.fonteTitulo
        font.pixelSize: root.pixel ? 20 : 14
        font.bold: true
        font.capitalization: root.tema === "minimal" ? Font.AllUppercase : Font.MixedCase
        font.letterSpacing: root.tema === "minimal" ? 0.5 : 0
        color: root.cTexto
        renderType: root.pixel ? Text.NativeRendering : Text.QtRendering
      }
      Rectangle {
        visible: root.itens.length > 0
        implicitWidth: Math.max(18, contador.implicitWidth + 10)
        implicitHeight: 18
        radius: root.pixel ? 0 : 9
        color: root.pixel ? root.cTexto : root.cItem
        border.width: root.tema === "minimal" ? 1 : 0
        border.color: root.cBorda
        Text {
          id: contador
          anchors.centerIn: parent
          text: root.itens.length
          font.family: root.pixel ? "Simba Pixel" : root.fonteSistema
          font.pixelSize: root.pixel ? 10 : 11
          font.bold: true
          color: root.pixel ? root.cFundo : root.cTexto
          renderType: root.pixel ? Text.NativeRendering : Text.QtRendering
        }
      }
      Item { Layout.fillWidth: true }
      // Não perturbe
      Rectangle {
        implicitWidth: 28; implicitHeight: 28
        radius: root.pixel ? 0 : 6
        color: root.dnd ? root.destaque : (dndMouse.containsMouse ? root.cHover : "transparent")
        Text {
          anchors.centerIn: parent
          text: root.dnd ? "󰂛" : "󰂚"
          font.family: "JetBrainsMono Nerd Font"
          font.pixelSize: 15
          color: root.dnd ? root.cFundo : root.cTexto
        }
        MouseArea {
          id: dndMouse
          anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
          onClicked: root.alternarDnd()
        }
        ToolTipSimples { visivel: dndMouse.containsMouse; texto: root.dnd ? "Não perturbe: ligado — avisos vão só para a central" : "Não perturbe: desligado — clique para silenciar avisos" }
      }
      // Limpar tudo
      Text {
        visible: root.itens.length > 0
        text: "Limpar tudo"
        font.family: root.pixel ? "Simba Pixel" : root.fonteSistema
        font.pixelSize: root.pixel ? 20 : 12
        font.underline: limparMouse.containsMouse && !root.pixel
        color: limparMouse.containsMouse ? root.cTexto : root.cApagado
        renderType: root.pixel ? Text.NativeRendering : Text.QtRendering
        MouseArea {
          id: limparMouse
          anchors.fill: parent; anchors.margins: -6
          hoverEnabled: true; cursorShape: Qt.PointingHandCursor
          onClicked: root.limparTudo()
        }
      }
    }

    // ── lista ──
    Flickable {
      id: rolagem
      Layout.fillWidth: true
      Layout.leftMargin: root.pixel ? 10 : 8
      Layout.rightMargin: root.pixel ? 10 : 8
      Layout.topMargin: 4
      Layout.bottomMargin: root.pixel ? 12 : 8
      Layout.preferredHeight: root.itens.length === 0 ? vazio.implicitHeight : Math.min(lista.implicitHeight, 272)
      contentHeight: lista.implicitHeight
      clip: true
      boundsBehavior: Flickable.StopAtBounds
      interactive: contentHeight > height
      flickDeceleration: 4000

      Column {
        id: lista
        width: rolagem.width
        spacing: root.tema === "minimal" ? 0 : 6

        Repeater {
          model: root.itens
          delegate: Item {
            id: it
            required property var modelData
            required property int index
            width: lista.width
            height: corpoItem.implicitHeight + 20
            readonly property bool urgente: modelData.urgency === 2
            readonly property bool sobre: mItem.containsMouse || mFechar.containsMouse
            opacity: 1

            // fundo do item
            Rectangle {
              anchors.fill: parent
              visible: !root.pixel
              radius: root.tema === "minimal" ? 0 : 6
              color: it.sobre ? root.cHover : root.cItem
              Behavior on color { ColorAnimation { duration: 100 } }
              Rectangle {   // linha separadora (Minimal)
                visible: root.tema === "minimal" && it.index < root.itens.length - 1
                anchors.bottom: parent.bottom; width: parent.width; height: 1; color: root.cBorda
              }
              Rectangle {   // faixa de urgente
                visible: it.urgente
                width: 3; height: parent.height - 12; y: 6; radius: 1.5; color: root.cTexto
              }
            }
            Canvas {
              anchors.fill: parent
              visible: root.pixel
              antialiasing: false
              property string chave: root.tema + width + "x" + height + it.sobre + it.urgente + root.fg + root.bg
              onChaveChanged: requestPaint()
              onPaint: {
                var c = getContext("2d"); c.reset()
                if (!root.pixel) return
                var P = root.px, W = Math.floor(width / P), H = Math.floor(height / P)
                var borda = root.tema === "pixel-portatil" ? String(mistura(root.bg, root.fg, 0.66)) : String(root.cBorda)
                Px.caixa(c, P, 0, 0, W, H, String(root.tema === "pixel-portatil" ? root.bg : (root.tema === "pixel-noturno" ? Qt.rgba(0.14, 0.14, 0.15, 1) : root.bg)), borda, 1)
                if (it.sobre) Px.pontilhadoForma(c, P, 1, 1, W - 2, H - 2, 0, String(root.cHover))
                if (it.urgente) Px.rect(c, P, 2, 3, 2, H - 6, String(root.cTexto))
              }
            }

            ColumnLayout {
              id: corpoItem
              x: it.urgente ? 16 : 12
              y: 10
              width: parent.width - x - 36
              spacing: 2
              RowLayout {
                spacing: 6
                Image {
                  Layout.preferredWidth: 16; Layout.preferredHeight: 16
                  source: {
                    var i = String(it.modelData.appIcon || it.modelData.image || "")
                    if (!i) return ""
                    if (i.indexOf("/") === 0) return "file://" + i
                    if (i.indexOf("file://") === 0 || i.indexOf("image://") === 0) return i
                    return Quickshell.iconPath(i, true)
                  }
                  sourceSize.width: root.pixel ? 16 : 32; sourceSize.height: root.pixel ? 16 : 32
                  smooth: !root.pixel
                  visible: status === Image.Ready
                }
                Text {
                  text: (it.modelData.app || "Sistema") + " · " + root.quando(it.modelData.timestamp || 0)
                  font.family: root.fonteSistema; font.pixelSize: 11
                  color: root.cApagado
                  elide: Text.ElideRight
                  Layout.fillWidth: true
                }
              }
              Text {
                Layout.fillWidth: true
                visible: text.length > 0
                text: (it.urgente ? "! " : "") + (it.modelData.summary || "")
                font.family: root.fonteTitulo
                font.pixelSize: root.pixel ? 20 : 13
                font.bold: true
                color: root.cTexto
                elide: Text.ElideRight
                maximumLineCount: 1
                renderType: root.pixel ? Text.NativeRendering : Text.QtRendering
              }
              Text {
                Layout.fillWidth: true
                visible: text.length > 0
                text: String(it.modelData.body || "").replace(/<[^>]+>/g, "")
                textFormat: Text.PlainText
                font.family: root.fonteSistema; font.pixelSize: 12
                color: root.cTexto
                opacity: 0.8
                wrapMode: Text.WordWrap
                elide: Text.ElideRight
                maximumLineCount: 2
              }
            }

            MouseArea {
              id: mItem
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: root.temAcao(it.modelData) ? Qt.PointingHandCursor : Qt.ArrowCursor
              onClicked: root.acionar(it.modelData)
            }
            // remover (×)
            Rectangle {
              anchors.top: parent.top; anchors.right: parent.right
              anchors.topMargin: 6; anchors.rightMargin: 6
              width: 24; height: 24
              radius: root.pixel ? 0 : 5
              opacity: it.sobre ? 1 : 0
              Behavior on opacity { NumberAnimation { duration: 120 } }
              color: mFechar.containsMouse ? root.cHover : "transparent"
              Text {
                anchors.centerIn: parent
                text: root.pixel ? "×" : "✕"
                font.family: root.pixel ? "Simba Pixel" : root.fonteSistema
                font.pixelSize: root.pixel ? 20 : 11
                color: root.cTexto
              }
              MouseArea {
                id: mFechar
                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: saida.start()
              }
            }
            // desliza para a direita e some, depois sai do histórico
            ParallelAnimation {
              id: saida
              NumberAnimation { target: it; property: "opacity"; to: 0; duration: 160 }
              NumberAnimation { target: it; property: "x"; to: 24; duration: 160; easing.type: Easing.OutCubic }
              onFinished: root.remover(it.modelData)
            }
          }
        }
      }
    }

    // ── estado vazio ──
    Item {
      id: vazio
      visible: root.itens.length === 0
      Layout.fillWidth: true
      Layout.preferredHeight: visible ? implicitHeight : 0
      implicitHeight: 104
      Column {
        anchors.centerIn: parent
        spacing: 6
        Canvas {   // Simba cochilando (temas pixel)
          visible: root.pixel
          anchors.horizontalCenter: parent.horizontalCenter
          width: 48; height: 30
          antialiasing: false
          property int quadro: 0
          Timer { interval: 500; repeat: true; running: root.ativo && root.pixel && vazio.visible; onTriggered: parent.quadro = (parent.quadro + 1) % 3 }
          onQuadroChanged: requestPaint()
          onPaint: {
            var c = getContext("2d"); c.reset()
            Px.sprite(c, 2, [
              "..........k...k.",
              ".........kgk.kgk",
              "..kkkkkkkkgggggk",
              ".kgggggggggkgkgk",
              "kgggggggggggglgk",
              "kggggggggggggggk",
              ".kkkkkkkkkkkkkk."], 4, 8, Px.GATO_CORES)
            var cor = String(root.cApagado)
            // "z" subindo: um, dois, três pontinhos
            for (var k = 0; k <= quadro; k++) Px.rect(c, 2, 20 + k * 2, 5 - k * 2, 2, 1, cor)
          }
        }
        Text {
          visible: !root.pixel
          anchors.horizontalCenter: parent.horizontalCenter
          text: "󰂚"; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 30
          color: root.cApagado
        }
        Text {
          anchors.horizontalCenter: parent.horizontalCenter
          text: root.pixel ? "Nada por aqui…" : "Nenhuma notificação nova"
          font.family: root.fonteTitulo; font.pixelSize: root.pixel ? 20 : 13; font.bold: root.pixel
          color: root.cTexto
          renderType: root.pixel ? Text.NativeRendering : Text.QtRendering
        }
        Text {
          anchors.horizontalCenter: parent.horizontalCenter
          text: root.pixel ? "o Simba está cochilando." : "Tudo em dia."
          font.family: root.fonteSistema; font.pixelSize: 11
          color: root.cApagado
        }
      }
    }
  }

  // dica simples (sem depender dos componentes do painel)
  component ToolTipSimples: Rectangle {
    property bool visivel: false
    property string texto: ""
    visible: visivel
    z: 10
    anchors.top: parent.bottom; anchors.topMargin: 4
    anchors.right: parent.right
    width: dica.implicitWidth + 14; height: dica.implicitHeight + 8
    radius: root.pixel ? 0 : 4
    color: root.invertido ? "#2a2a2a" : root.fg
    Text { id: dica; anchors.centerIn: parent; text: parent.texto; font.family: root.fonteSistema; font.pixelSize: 11; color: root.invertido ? "#f2f2f2" : root.bg }
  }
}
