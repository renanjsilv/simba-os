import QtQuick 6.11
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Commons
import qs.Commons as Commons
import "../../notifications/components/PixelArte.js" as Px

// Central de notificações do Simba (cartão superior flutuante, estilo Windows 11).
// Lista as últimas notificações do histórico (~/.local/state/simba/notifications/history),
// cada uma removível (×) e clicável: executa a ação dela (simba-exec-argv), abre a página
// certa das Configurações para os avisos do próprio sistema, ou foca a janela do app.
//
// Temas (~/.config/simba/notificacoes.json → "central"):
// 1. escuro: Windows 11 Dark Mica (padrão)
// 2. fluent: Windows 11 Fluent Fiel (acrílico/vidro suave)
// 3. pixel-rpg: Simba Pixel Art Retrô
// 4. minimal: Simba Minimal Moderno
Item {
  id: root

  property bool ativo: false              // o painel está aberto
  property color fg: Commons.Color.foreground
  property color bg: Commons.Color.popups.background
  property string fonteSistema: "Adwaita Sans"
  signal acionado()                       // pede para fechar o painel depois de um clique

  readonly property string home: Quickshell.env("HOME")
  readonly property string pastaHistorico: home + "/.local/state/simba/notifications/history/"
  readonly property string simbaPath: Quickshell.env("SIMBA_PATH") || "/usr/share/simba"

  // ── preferências ────────────────────────────────────────────────────────
  property string estiloAviso: "rpg"
  property string temaEscolhido: "escuro"  // PADRÃO DO SISTEMA: Opção 4 (Windows 11 Dark Mica)
  property string temaForcado: ""          // prévias (Configurações)
  readonly property string tema: {
    var t = temaForcado || temaEscolhido
    if (t === "win11-fluent") return "fluent"
    if (t === "win11-dark" || t === "dark") return "escuro"
    if (t === "pixel") return "pixel-rpg"
    if (["fluent", "minimal", "escuro", "pixel-rpg", "pixel-portatil", "pixel-noturno"].indexOf(t) >= 0) return t
    return "escuro"
  }
  readonly property bool pixel: tema.indexOf("pixel") === 0
  readonly property int px: 2
  readonly property int raio: pixel ? 0 : (tema === "minimal" ? 8 : 12)

  // Detecção dinâmica de tema escuro ou claro do sistema
  readonly property bool darkTheme: {
    var b = Commons.Color.background
    return (b.r * 0.299 + b.g * 0.587 + b.b * 0.114) < 0.5
  }

  // ── Cores adaptativas por tema (funcionam em tema branco e tema preto) ───────
  readonly property color cFundo: {
    if (tema === "escuro") return darkTheme ? Qt.rgba(0.11, 0.11, 0.13, 0.88) : Qt.rgba(0.96, 0.96, 0.97, 0.88)
    if (tema === "fluent") return darkTheme ? Qt.rgba(0.14, 0.14, 0.17, 0.85) : Qt.rgba(0.96, 0.97, 0.98, 0.82)
    if (tema === "minimal") return darkTheme ? "#181a1f" : "#ffffff"
    if (pixel) return darkTheme ? "#111111" : "#ffffff"
    return darkTheme ? Qt.rgba(0.11, 0.11, 0.13, 0.88) : Qt.rgba(0.96, 0.96, 0.97, 0.88)
  }

  readonly property color cBorda: {
    if (tema === "escuro") return darkTheme ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(0, 0, 0, 0.10)
    if (tema === "fluent") return darkTheme ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(0, 0, 0, 0.08)
    if (tema === "minimal") return darkTheme ? "#2d3139" : "#e5e7eb"
    if (pixel) return darkTheme ? "#b8b8b8" : "#111111"
    return darkTheme ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(0, 0, 0, 0.10)
  }

  readonly property color cTexto: {
    if (tema === "escuro") return darkTheme ? "#ffffff" : "#111827"
    if (tema === "fluent") return darkTheme ? "#f3f4f6" : "#111827"
    if (tema === "minimal") return darkTheme ? "#f3f4f6" : "#111827"
    if (pixel) return darkTheme ? "#f2f2f2" : "#111111"
    return darkTheme ? "#ffffff" : "#111827"
  }

  readonly property color cTextoSec: {
    if (tema === "escuro") return darkTheme ? "#d1d5db" : "#4b5563"
    if (tema === "fluent") return darkTheme ? "#d1d5db" : "#4b5563"
    if (tema === "minimal") return darkTheme ? "#d1d5db" : "#4b5563"
    if (pixel) return darkTheme ? "#cccccc" : "#333333"
    return darkTheme ? "#d1d5db" : "#4b5563"
  }

  readonly property color cApagado: {
    if (tema === "escuro") return darkTheme ? "#9ca3af" : "#6b7280"
    if (tema === "fluent") return darkTheme ? "#9ca3af" : "#6b7280"
    if (tema === "minimal") return darkTheme ? "#8b949e" : "#9ca3af"
    if (pixel) return darkTheme ? "#888888" : "#666666"
    return darkTheme ? "#9ca3af" : "#6b7280"
  }

  readonly property color cItem: {
    if (tema === "escuro") return darkTheme ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.85)
    if (tema === "fluent") return darkTheme ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.85)
    if (tema === "minimal") return darkTheme ? "#22252b" : "#fafafa"
    if (pixel) return darkTheme ? "#1a1a1a" : "#f8f8f8"
    return darkTheme ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.85)
  }

  readonly property color cBordaItem: {
    if (tema === "escuro") return darkTheme ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.06)
    if (tema === "fluent") return darkTheme ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(0, 0, 0, 0.05)
    if (tema === "minimal") return darkTheme ? "#2d3139" : "#f0f0f0"
    if (pixel) return darkTheme ? "#7a7a7a" : "#111111"
    return darkTheme ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.06)
  }

  readonly property color cHover: {
    if (tema === "escuro") return darkTheme ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(0, 0, 0, 0.05)
    if (tema === "fluent") return darkTheme ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(0, 0, 0, 0.05)
    if (tema === "minimal") return darkTheme ? "#2a2e36" : "#f3f4f6"
    if (pixel) return darkTheme ? "#2c2c2c" : "#e0e0e0"
    return darkTheme ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(0, 0, 0, 0.05)
  }

  readonly property color destaque: {
    if (tema === "escuro") return darkTheme ? "#0078d4" : "#0067c0"
    if (tema === "fluent") return darkTheme ? "#38bdf8" : "#0067c0"
    if (tema === "minimal") return darkTheme ? "#e5e7eb" : "#1f2937"
    if (pixel) return darkTheme ? "#ffffff" : "#111111"
    return darkTheme ? "#0078d4" : "#0067c0"
  }

  readonly property string fonteTitulo: pixel ? "Simba Pixel" : fonteSistema

  FileView {
    path: root.home + "/.config/simba/notificacoes.json"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      try {
        var v = JSON.parse(text() || "{}")
        root.estiloAviso = v.estilo || "rpg"
        root.temaEscolhido = v.central || "escuro"
      } catch (e) { root.estiloAviso = "rpg"; root.temaEscolhido = "escuro" }
    }
    onLoadFailed: { root.estiloAviso = "rpg"; root.temaEscolhido = "escuro" }
  }

  // ── dados ───────────────────────────────────────────────────────────────
  property var itens: exemplo || []
  property var exemplo: null                // prévias: lista fixa, não lê o histórico
  property bool dnd: false
  // hora atual pelo SystemClock
  SystemClock { id: relogio; precision: SystemClock.Minutes }
  readonly property double agora: relogio.date.getTime()

  function ler() { if (exemplo || limpando) return; leitor.running = true; dndProc.running = true }

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
        // só troca a lista se mudou: trocar recria os itens e cortaria uma animação de saída
        if (root.limpando) return
        var chaveNova = lista.map(function(x) { return x.arquivo }).join("|")
        var chaveAtual = root.itens.map(function(x) { return x.arquivo }).join("|")
        if (chaveNova !== chaveAtual) root.itens = lista
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

  // "Limpar tudo": cada item sai em cascata (30 ms entre um e outro) e só no fim
  // o histórico é apagado de verdade.
  property bool limpando: false
  readonly property int passoCascata: 30
  readonly property int duracaoSaida: 300      // deslizar (160) + encolher (140)
  // O histórico só é apagado quando o último item termina de sair (contagem em saidos);
  // o Timer é só a rede de segurança caso alguma animação não chegue ao fim.
  property int saidos: 0
  function limparTudo() {
    if (root.limpando || root.itens.length === 0) return
    root.saidos = 0
    root.limpando = true
    fimLimpeza.interval = (root.itens.length - 1) * root.passoCascata + root.duracaoSaida + 2000
    fimLimpeza.restart()
  }
  function itemSaiu() {
    root.saidos++
    if (root.saidos >= root.itens.length) concluirLimpeza()
  }
  function concluirLimpeza() {
    if (!root.limpando) return
    fimLimpeza.stop()
    if (!root.exemplo) {   // prévias/testes nunca apagam o histórico de verdade
      acao.command = ["simba-shell", "notifications", "clear"]
      acao.running = true
    }
    root.itens = []
    root.limpando = false
  }
  Timer {
    id: fimLimpeza
    repeat: false
    onTriggered: root.concluirLimpeza()
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

  // ── Fundo do cartão superior flutuante ─────────────────────────────────────
  Rectangle {
    anchors.fill: parent
    visible: !root.pixel
    radius: root.raio
    color: root.cFundo
    border.width: 1
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
      var f = String(root.cFundo), t = String(root.cBorda)
      Px.caixa(c, P, 0, 0, W, H, f, t, 2)
      Px.caixa(c, P, 2, 2, W - 4, H - 4, f, String(root.cBordaItem), 1)
    }
  }

  ColumnLayout {
    id: coluna
    anchors.fill: parent
    spacing: 0

    // ── 1. Cabeçalho de Notificações ──
    RowLayout {
      Layout.fillWidth: true
      Layout.leftMargin: root.pixel ? 12 : 14
      Layout.rightMargin: root.pixel ? 12 : 14
      Layout.topMargin: root.pixel ? 8 : 10
      Layout.bottomMargin: 6
      Layout.preferredHeight: 30
      spacing: 6

      Text {
        text: "Notificações"
        font.family: root.fonteTitulo
        font.pixelSize: root.pixel ? 16 : 13.5
        font.bold: true
        font.capitalization: root.tema === "minimal" ? Font.AllUppercase : Font.MixedCase
        font.letterSpacing: root.tema === "minimal" ? 0.5 : 0
        color: root.cTexto
        renderType: root.pixel ? Text.NativeRendering : Text.QtRendering
      }

      // Contador de notificações
      Rectangle {
        visible: root.itens.length > 0
        implicitWidth: Math.max(16, contador.implicitWidth + 8)
        implicitHeight: 16
        radius: root.pixel ? 0 : 8
        color: root.pixel ? root.cTexto : root.cItem
        border.width: root.pixel ? 1 : (root.tema === "minimal" ? 1 : 0)
        border.color: root.cBorda
        Text {
          id: contador
          anchors.centerIn: parent
          text: root.itens.length
          font.family: root.pixel ? "Simba Pixel" : root.fonteSistema
          font.pixelSize: root.pixel ? 10 : 10
          font.bold: true
          color: root.pixel ? root.cFundo : root.cTexto
          renderType: root.pixel ? Text.NativeRendering : Text.QtRendering
        }
      }

      Item { Layout.fillWidth: true }

      // Botão Não Perturbe
      Rectangle {
        implicitWidth: 26; implicitHeight: 26
        radius: root.pixel ? 0 : 6
        color: root.dnd ? root.destaque : (dndMouse.containsMouse ? root.cHover : "transparent")
        border.width: root.pixel ? 1 : 0
        border.color: root.cBorda
        Text {
          anchors.centerIn: parent
          text: root.dnd ? "󰂛" : "󰂚"
          font.family: "JetBrainsMono Nerd Font"
          font.pixelSize: 13
          color: root.dnd ? "#ffffff" : root.cTexto
        }
        MouseArea {
          id: dndMouse
          anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
          onClicked: root.alternarDnd()
        }
        ToolTipSimples {
          visivel: dndMouse.containsMouse
          texto: root.dnd ? "Não perturbe: ligado" : "Não perturbe: desligado"
        }
      }

      // Botão Limpar tudo (estilo pill do Windows 11)
      Rectangle {
        visible: root.itens.length > 0
        implicitWidth: txtLimpar.implicitWidth + 14
        implicitHeight: 24
        radius: root.pixel ? 0 : 5
        color: limparMouse.containsMouse ? root.cHover : "transparent"
        border.width: 1
        border.color: root.cBordaItem

        Text {
          id: txtLimpar
          anchors.centerIn: parent
          text: "Limpar tudo"
          font.family: root.fonteTitulo
          font.pixelSize: root.pixel ? 13 : 11
          font.bold: true
          color: root.cTexto
          renderType: root.pixel ? Text.NativeRendering : Text.QtRendering
        }
        MouseArea {
          id: limparMouse
          anchors.fill: parent
          hoverEnabled: true; cursorShape: Qt.PointingHandCursor
          onClicked: root.limparTudo()
        }
      }
    }

    // ── 2. Lista de Notificações ──
    Item {
      id: containerRolagem
      visible: root.itens.length > 0
      Layout.fillWidth: true
      Layout.fillHeight: visible
      Layout.preferredHeight: visible ? -1 : 0
      Layout.leftMargin: root.pixel ? 10 : 12
      Layout.rightMargin: root.pixel ? 10 : 12
      Layout.topMargin: 2
      Layout.bottomMargin: root.pixel ? 10 : 12

      Flickable {
        id: rolagem
        anchors.fill: parent
        anchors.rightMargin: (contentHeight > height) ? 7 : 0
        contentHeight: lista.implicitHeight
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        interactive: contentHeight > height
        flickDeceleration: 4000

      Column {
        id: lista
        width: rolagem.width
        spacing: root.tema === "minimal" ? 2 : 6

        Repeater {
          model: root.itens
          delegate: Item {
            id: it
            required property var modelData
            required property int index
            width: lista.width
            // fator encolhe a altura no fim da saída, para os de baixo subirem suavemente
            property real fator: 1
            height: (corpoItem.implicitHeight + 14) * fator
            clip: fator < 1
            readonly property bool urgente: modelData.urgency === 2
            property bool individual: false
            Connections {
              target: root
              function onLimpandoChanged() {
                if (root.limpando && !saida.running) {
                  it.individual = false
                  atrasoSaida.duration = it.index * root.passoCascata
                  saida.start()
                }
              }
            }
            readonly property bool sobre: mItem.containsMouse || mFechar.containsMouse
            opacity: 1

            // Fundo do cartão individual de notificação
            Rectangle {
              anchors.fill: parent
              visible: !root.pixel
              radius: root.tema === "minimal" ? 4 : 8
              color: it.sobre ? root.cHover : root.cItem
              border.width: 1
              border.color: root.cBordaItem
              Behavior on color { ColorAnimation { duration: 100 } }

              // Faixa de destaque para notificações urgentes
              Rectangle {
                visible: it.urgente
                width: 3; height: parent.height - 8; y: 4; radius: 1.5; color: root.destaque
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
                Px.caixa(c, P, 0, 0, W, H, String(root.cItem), String(root.cBordaItem), 1)
                if (it.sobre) Px.pontilhadoForma(c, P, 1, 1, W - 2, H - 2, 0, String(root.cHover))
                if (it.urgente) Px.rect(c, P, 2, 2, 2, H - 4, String(root.cTexto))
              }
            }

            ColumnLayout {
              id: corpoItem
              x: it.urgente ? 14 : 10
              y: 7
              width: parent.width - x - 28
              spacing: 2

              // Linha do App e Horário
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
                  font.family: root.fonteSistema; font.pixelSize: 10
                  font.bold: true
                  color: root.cApagado
                  elide: Text.ElideRight
                  Layout.fillWidth: true
                }
              }

              // Título
              Text {
                Layout.fillWidth: true
                visible: text.length > 0
                text: (it.urgente ? "! " : "") + (it.modelData.summary || "")
                font.family: root.fonteTitulo
                font.pixelSize: root.pixel ? 10 : 12.5
                font.bold: true
                color: root.cTexto
                wrapMode: Text.WordWrap
                elide: Text.ElideRight
                maximumLineCount: 2
                renderType: root.pixel ? Text.NativeRendering : Text.QtRendering
              }

              // Mensagem / Detalhes
              Text {
                Layout.fillWidth: true
                visible: text.length > 0
                text: String(it.modelData.body || "").replace(/<[^>]+>/g, "")
                textFormat: Text.PlainText
                font.family: root.fonteSistema; font.pixelSize: 11
                color: root.cTextoSec
                wrapMode: Text.WordWrap
                elide: Text.ElideRight
                maximumLineCount: 2
                lineHeight: 1.2
              }
            }

            // Área de clique da notificação inteira
            MouseArea {
              id: mItem
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: root.temAcao(it.modelData) ? Qt.PointingHandCursor : Qt.ArrowCursor
              onClicked: root.acionar(it.modelData)
            }

            // Botão Fechar (×)
            Rectangle {
              anchors.top: parent.top; anchors.right: parent.right
              anchors.topMargin: 5; anchors.rightMargin: 5
              width: 20; height: 20
              radius: root.pixel ? 0 : 4
              opacity: it.sobre ? 1 : 0
              Behavior on opacity { NumberAnimation { duration: 120 } }
              color: mFechar.containsMouse ? root.cHover : "transparent"
              Text {
                anchors.centerIn: parent
                text: root.pixel ? "×" : "✕"
                font.family: root.pixel ? "Simba Pixel" : root.fonteSistema
                font.pixelSize: root.pixel ? 14 : 10
                color: root.cTexto
              }
              MouseArea {
                id: mFechar
                anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: { it.individual = true; atrasoSaida.duration = 0; saida.start() }
              }
            }

            // Animação de remoção suave
            // desliza para a direita e some, depois encolhe (os de baixo sobem)
            SequentialAnimation {
              id: saida
              PauseAnimation { id: atrasoSaida; duration: 0 }
              ParallelAnimation {
                NumberAnimation { target: it; property: "opacity"; to: 0; duration: 160; easing.type: Easing.OutQuad }
                NumberAnimation { target: it; property: "x"; to: Math.round(it.width * 0.35); duration: 160; easing.type: Easing.InCubic }
              }
              NumberAnimation { target: it; property: "fator"; to: 0; duration: 140; easing.type: Easing.InOutQuad }
              onFinished: {
                if (it.individual) root.remover(it.modelData)
                else if (root.limpando) root.itemSaiu()
              }
            }
          }
        }
      }
    }

    // Barra de rolagem discreta estilo Win11
      Rectangle {
        id: barraRolagem
        visible: rolagem.contentHeight > rolagem.height
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        width: 3
        color: "transparent"

        Rectangle {
          y: rolagem.visibleArea.yPosition * parent.height
          width: 3
          height: Math.max(20, rolagem.visibleArea.heightRatio * parent.height)
          radius: 1.5
          color: root.cApagado
          opacity: 0.5
        }
      }
    }

    // ── 3. Estado Vazio ──
    Item {
      id: vazio
      visible: root.itens.length === 0
      Layout.fillWidth: true
      Layout.fillHeight: visible
      Layout.preferredHeight: visible ? -1 : 0
      implicitHeight: 64

      Column {
        anchors.centerIn: parent
        spacing: 3

        Canvas {   // Simba cochilando (temas pixel)
          visible: root.pixel
          anchors.horizontalCenter: parent.horizontalCenter
          width: 36; height: 20
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
              ".kkkkkkkkkkkkkk."], 0, 3, Px.GATO_CORES)
            var cor = String(root.cApagado)
            for (var k = 0; k <= quadro; k++) Px.rect(c, 2, 17 + k * 2, 2 - k * 2, 2, 1, cor)
          }
        }

        Text {
          visible: !root.pixel
          anchors.horizontalCenter: parent.horizontalCenter
          text: "󰂚"; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 20
          color: root.cApagado
        }
        Text {
          anchors.horizontalCenter: parent.horizontalCenter
          text: root.pixel ? "Nada por aqui…" : "Nenhuma notificação nova"
          font.family: root.fonteTitulo; font.pixelSize: root.pixel ? 16 : 12; font.bold: true
          color: root.cTexto
          renderType: root.pixel ? Text.NativeRendering : Text.QtRendering
        }
        Text {
          anchors.horizontalCenter: parent.horizontalCenter
          text: root.pixel ? "o Simba está cochilando." : "Tudo em dia."
          font.family: root.fonteSistema; font.pixelSize: 10
          color: root.cApagado
        }
      }
    }
  }

  // Dica simples (tooltip)
  component ToolTipSimples: Rectangle {
    property bool visivel: false
    property string texto: ""
    visible: visivel
    z: 10
    anchors.top: parent.bottom; anchors.topMargin: 4
    anchors.right: parent.right
    width: dica.implicitWidth + 14; height: dica.implicitHeight + 8
    radius: root.pixel ? 0 : 4
    color: root.cItem
    border.width: 1
    border.color: root.cBorda
    Text { id: dica; anchors.centerIn: parent; text: parent.texto; font.family: root.fonteSistema; font.pixelSize: 11; color: root.cTexto }
  }
}
