import "idiomas"
import QtQuick 6.11
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import Quickshell.Services.Mpris
import qs.Commons

// Central de controle do Simba OS (como a do Windows 11 / macOS).
// Na barra: ícones de rede, som e bateria num botão só.
//   clique   abre a central (Wi-Fi, Bluetooth, Não perturbe, Modo escuro,
//            Luz noturna, Economia de energia, volume, brilho, bateria)
//   rolar    muda o volume
// Em cima, como no Windows 11: o que está tocando (MPRIS: capa, nome, anterior/tocar/próxima)
// e, numa chamada pelo navegador (Meet, Teams…), o aviso com o mudo do microfone dela.
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
                      economia: false, volume: 50, mudo: false, brilho: 100, bateria: null, carregando: false,
                      saidas_audio: [] })
  property bool mostrarSaidas: false
  readonly property var saidasAudio: st.saidas_audio || []
  readonly property var saidaAtual: {
    for (var i = 0; i < saidasAudio.length; i++) {
      if (saidasAudio[i].padrao) return saidasAudio[i]
    }
    return saidasAudio.length > 0 ? saidasAudio[0] : null
  }
  function gTipoSaida(tipo) {
    if (tipo === "bluetooth") return "\u{F0970}"
    if (tipo === "headphones") return "\u{F02CB}"
    if (tipo === "hdmi") return "\u{F0A24}"
    return "\u{F04C3}"
  }
  readonly property string gSaidaAtual: saidaAtual ? gTipoSaida(saidaAtual.tipo) : "\u{F0142}"

  function trocarSaidaAudio(disp) {
    if (st.saidas_audio) {
      var arr = st.saidas_audio.map(function(s) {
        return Object.assign({}, s, { padrao: s.id === disp.id || (s.nome && s.nome === disp.nome) })
      })
      st = Object.assign({}, st, { saidas_audio: arr })
    }
    acao(["saida-audio", String(disp.id), disp.nome || ""])
  }

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

  // ── chamada no navegador (simba-central chamada) ─────────────────────────
  property var chamada: ({ ativa: false })
  Process {
    id: lerChamada
    command: [root.ajudante, "chamada"]
    stdout: StdioCollector { onStreamFinished: { try { root.chamada = JSON.parse(text) } catch (e) {} } }
  }
  Timer {
    interval: 1500; running: painel.visible; repeat: true; triggeredOnStart: true
    onTriggered: if (!lerChamada.running) lerChamada.running = true
  }
  function alternarMudoChamada() {
    root.chamada = Object.assign({}, root.chamada, { mudo: !root.chamada.mudo })
    Quickshell.execDetached([root.ajudante, "chamada-mudo"])
  }

  // ── mídia (MPRIS) ────────────────────────────────────────────────────────
  // o que está tocando; senão o último com música carregada
  readonly property var player: {
    var ps = Mpris.players.values.filter(function(p) { return p && p.trackTitle })
    var tocando = ps.filter(function(p) { return p.isPlaying })
    return tocando.length ? tocando[0] : (ps.length ? ps[ps.length - 1] : null)
  }

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
    implicitHeight: caixa.implicitHeight + 8 * 2 + 14 * 2   // margem da moldura (8) + do conteúdo (14), em cima e embaixo
    anchor.item: root
    anchor.rect.x: root.vertical ? (root.bar && root.bar.position === "right" ? -implicitWidth - 6 : root.width + 6) : root.width - implicitWidth + 4
    anchor.rect.y: root.vertical ? root.height - implicitHeight : (root.bar && root.bar.position === "bottom" ? -implicitHeight - 6 : root.height + 6)

    property bool grabPronto: false
    onVisibleChanged: { grabPronto = false; if (!visible) mostrarSaidas = false; if (visible) ativarGrab.restart() }
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

        // chamada de vídeo no navegador
        Rectangle {
          visible: root.chamada.ativa === true
          width: parent.width; height: visible ? 60 : 0
          radius: 12
          color: root.alfa(root.texto, root.escuro ? 0.06 : 0.05)
          border.width: 1; border.color: root.alfa(root.texto, 0.08)
          Row {
            // vai até os botões da direita (antes a largura era fixa e o texto passava por baixo deles)
            anchors { left: parent.left; leftMargin: 12; right: botoesChamada.left; rightMargin: 8; verticalCenter: parent.verticalCenter }
            spacing: 10
            Rectangle {
              id: iconeChamada
              width: 36; height: 36; radius: 18; anchors.verticalCenter: parent.verticalCenter
              color: "#c42b1c"
              Text { anchors.centerIn: parent; text: "\u{F0567}"; color: "white"; font.family: root.fonte; font.pixelSize: 18 }
              SequentialAnimation on opacity { running: painel.visible && root.chamada.ativa === true; loops: Animation.Infinite
                NumberAnimation { to: 0.55; duration: 900 } NumberAnimation { to: 1; duration: 900 } }
            }
            Column {
              anchors.verticalCenter: parent.verticalCenter
              width: parent.width - iconeChamada.width - parent.spacing
              Text { width: parent.width; text: I18n.t("Chamada em andamento"); color: root.texto; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight }
              Text {
                width: parent.width; elide: Text.ElideRight; color: root.texto; opacity: 0.72; font.pixelSize: 10
                text: (root.chamada.plataforma || I18n.t("No navegador")) + (root.chamada.mudo ? I18n.t(" · mudo") : I18n.t(" · microfone ligado"))
              }
            }
          }
          Row {
            id: botoesChamada
            anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
            spacing: 6
            Rectangle {
              width: 36; height: 36; radius: 18
              color: root.chamada.mudo ? "#c42b1c" : (mMic.containsMouse ? root.alfa(root.texto, 0.14) : root.alfa(root.texto, 0.08))
              Text { anchors.centerIn: parent; text: root.chamada.mudo ? "\u{F036D}" : "\u{F036C}"; color: root.chamada.mudo ? "white" : root.texto; font.family: root.fonte; font.pixelSize: 17 }
              // sem fluxo do microfone (desligado na própria chamada) não há o que ligar daqui: abre a chamada
              MouseArea { id: mMic; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: { if (root.chamada.controle) root.alternarMudoChamada(); else { painel.visible = false; Quickshell.execDetached([root.ajudante, "chamada-abrir"]) } } }
            }
            Rectangle {
              visible: !!root.chamada.janela
              width: 36; height: 36; radius: 18
              color: mIr.containsMouse ? root.alfa(root.texto, 0.14) : root.alfa(root.texto, 0.08)
              Text { anchors.centerIn: parent; text: "\u{F03CC}"; color: root.texto; font.family: root.fonte; font.pixelSize: 16 }
              MouseArea { id: mIr; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: { painel.visible = false; Quickshell.execDetached([root.ajudante, "chamada-abrir"]) } }
            }
          }
        }

        // tocando agora (MPRIS)
        Rectangle {
          id: midia
          readonly property var p: root.player
          visible: p !== null
          width: parent.width; height: visible ? 76 : 0
          radius: 12
          color: root.alfa(root.texto, root.escuro ? 0.06 : 0.05)
          border.width: 1; border.color: root.alfa(root.texto, 0.08)
          clip: true
          Rectangle {
            id: capa
            anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
            width: 56; height: 56; radius: 8
            color: root.alfa(root.texto, 0.10)
            clip: true
            Text { anchors.centerIn: parent; visible: arte.status !== Image.Ready; text: "\u{F075A}"; color: root.texto; opacity: 0.6; font.family: root.fonte; font.pixelSize: 24 }
            Image {
              id: arte
              anchors.fill: parent
              source: midia.p && midia.p.trackArtUrl ? midia.p.trackArtUrl : ""
              fillMode: Image.PreserveAspectCrop
              asynchronous: true; smooth: true
              sourceSize: Qt.size(112, 112)
            }
          }
          Column {
            anchors { left: capa.right; leftMargin: 10; right: controles.left; rightMargin: 6; verticalCenter: parent.verticalCenter }
            spacing: 2
            Text { width: parent.width; text: midia.p ? midia.p.trackTitle : ""; color: root.texto; font.pixelSize: 12; font.weight: Font.DemiBold; elide: Text.ElideRight }
            Text {
              width: parent.width; elide: Text.ElideRight; color: root.texto; opacity: 0.72; font.pixelSize: 10
              text: midia.p ? (midia.p.trackArtist || midia.p.trackAlbum || "") : ""
              visible: text !== ""
            }
            Text { width: parent.width; text: midia.p ? midia.p.identity : ""; color: root.texto; opacity: 0.5; font.pixelSize: 9; elide: Text.ElideRight }
          }
          Row {
            id: controles
            anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
            spacing: 2
            Repeater {
              model: [
                { g: "\u{F04AE}", pode: midia.p && midia.p.canGoPrevious, fazer: function() { midia.p.previous() } },
                { g: midia.p && midia.p.isPlaying ? "\u{F03E4}" : "\u{F040A}", pode: midia.p && midia.p.canTogglePlaying, fazer: function() { midia.p.togglePlaying() }, grande: true },
                { g: "\u{F04AD}", pode: midia.p && midia.p.canGoNext, fazer: function() { midia.p.next() } }
              ]
              delegate: Rectangle {
                required property var modelData
                width: modelData.grande ? 36 : 30; height: width; radius: width / 2
                anchors.verticalCenter: parent.verticalCenter
                opacity: modelData.pode ? 1 : 0.35
                color: modelData.grande ? root.realce : (mc.containsMouse && modelData.pode ? root.alfa(root.texto, 0.12) : "transparent")
                Text { anchors.centerIn: parent; text: parent.modelData.g; color: parent.modelData.grande ? root.sobreRealce : root.texto; font.family: root.fonte; font.pixelSize: parent.modelData.grande ? 18 : 16 }
                MouseArea { id: mc; anchors.fill: parent; hoverEnabled: true; enabled: !!parent.modelData.pode; cursorShape: Qt.PointingHandCursor; onClicked: parent.modelData.fazer() }
              }
            }
          }
        }

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
          property bool temAcaoDireita: false
          property string glifoDireita: ""
          property bool ativaDireita: false
          signal mudou(int v)
          signal clicouGlifo()
          signal clicouDireita()
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
            anchors { right: d.temAcaoDireita ? btnExtra.left : parent.right; rightMargin: d.temAcaoDireita ? 6 : 0; verticalCenter: parent.verticalCenter }
            width: 30; horizontalAlignment: Text.AlignRight
            text: d.valor; color: root.texto; opacity: 0.7; font.pixelSize: 12
          }
          Rectangle {
            id: btnExtra
            visible: d.temAcaoDireita
            anchors { right: parent.right; verticalCenter: parent.verticalCenter }
            width: 28; height: 28; radius: 14
            color: d.ativaDireita ? root.realce : (me.containsMouse ? root.alfa(root.texto, 0.14) : root.alfa(root.texto, 0.07))
            scale: me.pressed ? 0.92 : 1
            Behavior on scale { NumberAnimation { duration: 80 } }
            Behavior on color { ColorAnimation { duration: 100 } }
            Text {
              anchors.centerIn: parent
              text: d.glifoDireita
              color: d.ativaDireita ? root.sobreRealce : root.texto
              font.family: root.fonte
              font.pixelSize: 15
            }
            MouseArea {
              id: me
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: d.clicouDireita()
            }
          }
        }
        // aplica no máximo a cada 60 ms enquanto arrasta
        Timer { id: aplicaVol; interval: 60; onTriggered: root.acao(["volume", String(root.st.volume)]) }
        Timer { id: aplicaBri; interval: 60; onTriggered: root.acao(["brilho", String(root.st.brilho)]) }

        Deslizante {
          glifo: root.gVol
          valor: root.st.mudo ? 0 : root.st.volume
          temAcaoDireita: true
          glifoDireita: root.mostrarSaidas ? "\u{F0140}" : root.gSaidaAtual
          ativaDireita: root.mostrarSaidas
          onMudou: function(v) { root.st = Object.assign({}, root.st, { volume: v, mudo: false }); if (!aplicaVol.running) aplicaVol.start() }
          onClicouGlifo: { root.acao(["mudo"]); root.st = Object.assign({}, root.st, { mudo: !root.st.mudo }) }
          onClicouDireita: { root.mostrarSaidas = !root.mostrarSaidas }
        }

        // seletor de saída de áudio (fone, bluetooth, alto-falante)
        Rectangle {
          id: painelSaidas
          visible: root.mostrarSaidas && root.saidasAudio.length > 0
          width: parent.width
          height: visible ? colSaidas.implicitHeight + 16 : 0
          radius: 12
          color: root.alfa(root.texto, root.escuro ? 0.08 : 0.05)
          border.width: 1; border.color: root.alfa(root.texto, 0.10)
          clip: true

          Column {
            id: colSaidas
            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 8 }
            spacing: 4

            Row {
              width: parent.width
              spacing: 6
              Text {
                text: I18n.t("Saída de som")
                color: root.texto; opacity: 0.65; font.pixelSize: 11; font.weight: Font.DemiBold
              }
            }

            Repeater {
              model: root.saidasAudio
              delegate: Rectangle {
                id: itemSaida
                required property var modelData
                width: colSaidas.width; height: 36; radius: 8
                color: itemSaida.modelData.padrao ? root.alfa(root.realce, 0.20) : (ms.containsMouse ? root.alfa(root.texto, 0.08) : "transparent")
                border.width: itemSaida.modelData.padrao ? 1 : 0
                border.color: root.realce

                Row {
                  anchors { left: parent.left; leftMargin: 10; right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
                  spacing: 10

                  Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.gTipoSaida(itemSaida.modelData.tipo)
                    color: itemSaida.modelData.padrao ? root.realce : root.texto
                    font.family: root.fonte; font.pixelSize: 16
                  }

                  Text {
                    anchors.verticalCenter: parent.verticalCenter
                    width: parent.width - 60
                    text: itemSaida.modelData.descricao || itemSaida.modelData.nome
                    color: root.texto
                    font.pixelSize: 12
                    font.weight: itemSaida.modelData.padrao ? Font.DemiBold : Font.Normal
                    elide: Text.ElideRight
                  }

                  Text {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: itemSaida.modelData.padrao
                    text: "\u{F012C}"
                    color: root.realce
                    font.family: root.fonte; font.pixelSize: 14
                  }
                }

                MouseArea {
                  id: ms
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: {
                    root.trocarSaidaAudio(itemSaida.modelData)
                  }
                }
              }
            }

            Rectangle {
              width: colSaidas.width; height: 26; radius: 6
              color: mCfgSom.containsMouse ? root.alfa(root.texto, 0.08) : "transparent"
              Row {
                anchors.centerIn: parent; spacing: 6
                Text { text: "\u{F0493}"; color: root.texto; opacity: 0.6; font.family: root.fonte; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
                Text { text: I18n.t("Mais configurações de som"); color: root.texto; opacity: 0.7; font.pixelSize: 11; anchors.verticalCenter: parent.verticalCenter }
              }
              MouseArea {
                id: mCfgSom; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                onClicked: { painel.visible = false; Quickshell.execDetached(["/usr/bin/configuracoes", "som"]) }
              }
            }
          }
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
