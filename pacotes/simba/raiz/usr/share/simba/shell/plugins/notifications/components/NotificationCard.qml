// Notification card. Pure presentational — no service, Notification, or
// ListModel references. The popup container drives lifetime; the history
// panel drives static rendering. Both use the same component.
//
// Simba: `estilo` escolhe o visual (Configurações › Notificações):
//   normais: padrao (o antigo, quadrado), vidro, suave, windows, escuro, pilula
//   pixel art: rpg (padrão do sistema), balao, janela, conquista, portatil, vidro-pixel
// Os pixel art usam a fonte "Simba Pixel" (/usr/share/fonts/simba-pixel) e são
// desenhados num Canvas com pixels de P×P (PixelArte.js).

import QtQuick 6.11
import QtQuick.Layouts
import QtQuick.Effects
import Quickshell
import qs.Commons
import qs.Commons as Commons
import qs.Ui
import "../NotificationLogic.js" as NotificationLogic
import "PixelArte.js" as Px

BorderSurface {
  id: root

  property string app: ""
  property string appIcon: ""
  property string summary: ""
  property string body: ""
  property string image: ""
  // Nerd Font glyph rendered in the icon slot when no real icon is set.
  property string glyph: ""
  // NotificationUrgency: Low=0, Normal=1, Critical=2 (upstream).
  property int urgency: 1
  property double timestamp: 0
  property int cornerRadius: 0
  // System monospace font injected by the container.
  property string fontFamily: ""
  // Simba: visual escolhido e quanto falta para o cartão sumir (1 → 0).
  property string estilo: "rpg"
  property real progresso: 1.0

  readonly property bool hovered: hoverTracker.hovered

  signal closeRequested()
  signal cardClicked()

  readonly property string smallIconSource: image.length > 0 ? image : iconSource(appIcon)
  readonly property bool hasGlyph: glyph.length > 0
  readonly property bool compactGlyph: legado && NotificationLogic.shouldRenderCompactGlyph(glyph, smallIconSource, singleLineToast)
  readonly property bool hasSmallIcon: smallIconSource.length > 0
  readonly property bool summaryStartsWithGlyph: NotificationLogic.summaryStartsWithGlyph(summary)
  readonly property bool singleLineToast: sanitizedBody.length === 0
  readonly property bool collapseRedundantIcon: singleLineToast && !hasGlyph && summaryStartsWithGlyph
  readonly property string sanitizedBody: sanitizeBody(body)
  readonly property string styledBody: NotificationLogic.styledBody(body, app, appIcon)

  // ── estilo ────────────────────────────────────────────────────────────
  readonly property var estilosPixel: ["rpg", "balao", "janela", "conquista", "portatil", "vidro-pixel"]
  readonly property var estilosNormais: ["padrao", "vidro", "suave", "windows", "escuro", "pilula"]
  readonly property string est: estilosPixel.indexOf(estilo) >= 0 || estilosNormais.indexOf(estilo) >= 0 ? estilo : "rpg"
  readonly property bool legado: est === "padrao"
  readonly property bool pixel: estilosPixel.indexOf(est) >= 0
  readonly property int px: 2

  readonly property color corFundo: Commons.Color.notifications.background
  readonly property color corTexto: Commons.Color.notifications.text
  readonly property color corApagada: Qt.tint(corFundo, Qt.rgba(corTexto.r, corTexto.g, corTexto.b, 0.45))
  readonly property bool escuroTema: (corFundo.r + corFundo.g + corFundo.b) / 3 < 0.5

  readonly property color corTitulo: est === "conquista" || est === "escuro" ? "#ffffff"
                                   : est === "portatil" ? "#1b1b1b" : corTexto
  readonly property color corCorpo: est === "conquista" ? "#b0b0b0" : est === "escuro" ? "#c8c8c8"
                                  : est === "portatil" ? "#3d3d3d" : (legado ? bodyColor : Qt.tint(corTexto, Qt.rgba(corFundo.r, corFundo.g, corFundo.b, 0.25)))

  // margens do conteúdo [esquerda, topo, direita, baixo]
  readonly property var margens: ({
    padrao: [12, 10, 12, 10], rpg: [14, 12, 26, 12], balao: [44, 10, 14, 10], janela: [12, 32, 14, 12],
    conquista: [14, 12, 16, 20], portatil: [16, 14, 18, 14], "vidro-pixel": [14, 12, 30, 12],
    vidro: [16, 14, 34, 14], suave: [16, 14, 34, 20], windows: [14, 38, 34, 16], escuro: [16, 14, 34, 14],
    pilula: [10, 8, 26, 8]
  })[est]
  readonly property int tamIcone: pixel ? 24 : (est === "windows" ? 44 : (est === "pilula" ? 34 : 40))
  readonly property string fonteTexto: pixel ? "Simba Pixel" : (legado ? "Liberation Sans" : "Adwaita Sans")
  readonly property int tamTitulo: pixel ? 20 : (legado ? Style.font.title : 14)
  readonly property int tamCorpo: pixel ? 20 : (legado ? Style.font.title : 13)
  readonly property bool comFechar: ["vidro", "suave", "windows", "escuro", "vidro-pixel"].indexOf(est) >= 0
  readonly property int blocosAcesos: Math.ceil(Math.max(0, Math.min(1, progresso)) * 10)

  readonly property color dimColor: Qt.darker(Commons.Color.notifications.text, 1.4)
  readonly property color bodyColor: Qt.darker(Commons.Color.notifications.text, 1.15)
  readonly property color accentColor: urgency === 2 ? Commons.Color.urgent : (urgency === 0 ? dimColor : Commons.Color.notifications.countdown)
  readonly property var cardBorderSpec: Border.surfaceSpec("notifications", "border", Commons.Color.notifications.border, Math.max(1, Style.space(2)))

  function sanitizeBody(s) {
    return NotificationLogic.sanitizeBody(s, app, appIcon)
  }

  function iconSource(icon) {
    var value = String(icon || "")
    if (value.length === 0) return ""
    if (value.indexOf("file://") === 0 || value.indexOf("image://") === 0) return value
    if (value.charAt(0) === "/") return Util.fileUrl(value)
    return Quickshell.iconPath(value, true)
  }

  implicitWidth: legado ? Style.space(380) : (pixel ? 380 : 372)
  implicitHeight: legado ? mainColumn.implicitHeight + borderTop + borderBottom
                         : Math.max(conteudo.implicitHeight + margens[1] + margens[3], est === "balao" ? 40 : 0)
  radius: legado ? cornerRadius : 0
  color: legado ? Commons.Color.notifications.background : "transparent"
  borderSpec: legado ? cardBorderSpec : Border.none()
  clip: legado

  HoverHandler { id: hoverTracker }

  MouseArea {
    anchors.fill: parent
    cursorShape: Qt.PointingHandCursor
    acceptedButtons: Qt.LeftButton | Qt.RightButton
    onClicked: function(mouse) {
      if (mouse.button === Qt.RightButton) root.closeRequested()
      else root.cardClicked()
    }
  }

  // ── fundos normais (retângulo arredondado + sombra macia) ────────────────
  Rectangle {
    id: fundoNormal
    visible: false
    anchors.fill: parent
    readonly property bool claro: !root.escuroTema
    radius: ({ vidro: 18, suave: 14, windows: 10, escuro: 20, pilula: height / 2 })[root.est] || 0
    color: root.est === "escuro" ? Qt.rgba(0.11, 0.11, 0.12, 0.88)
         : root.est === "vidro" ? Qt.rgba(root.corFundo.r, root.corFundo.g, root.corFundo.b, 0.62)
         : root.est === "windows" ? Qt.rgba(root.corFundo.r, root.corFundo.g, root.corFundo.b, 0.94)
         : root.corFundo
    border.width: root.est === "suave" || root.est === "pilula" ? 0 : 1
    border.color: root.est === "vidro" ? (claro ? Qt.rgba(1, 1, 1, 0.75) : Qt.rgba(1, 1, 1, 0.14))
                : root.est === "escuro" ? Qt.rgba(1, 1, 1, 0.08)
                : Qt.rgba(root.corTexto.r, root.corTexto.g, root.corTexto.b, 0.10)
  }
  MultiEffect {
    visible: !root.legado && !root.pixel
    source: fundoNormal
    anchors.fill: fundoNormal
    autoPaddingEnabled: true
    shadowEnabled: true
    shadowBlur: 0.9
    shadowVerticalOffset: 8
    shadowColor: Qt.rgba(0, 0, 0, root.est === "escuro" ? 0.34 : 0.20)
  }
  // barrinha de tempo do "Cartão suave"
  Rectangle {
    visible: root.est === "suave"
    x: 16; height: 3; radius: 2
    anchors.bottom: parent.bottom; anchors.bottomMargin: 7
    width: parent.width - 32
    color: Qt.rgba(root.corTexto.r, root.corTexto.g, root.corTexto.b, 0.08)
    Rectangle { height: parent.height; radius: 2; color: root.corApagada; width: parent.width * Math.max(0, Math.min(1, root.progresso)) }
  }
  // cabeçalho do "Estilo Windows 11": ícone pequeno + nome do app
  Row {
    visible: root.est === "windows"
    x: 14; y: 11; spacing: 8
    Image {
      width: 16; height: 16; sourceSize.width: 32; sourceSize.height: 32
      source: root.smallIconSource; smooth: true; asynchronous: true
      visible: status === Image.Ready
    }
    Text {
      text: root.app || "Simba OS"
      font.family: root.fonteTexto; font.pixelSize: 12
      color: Qt.rgba(root.corTexto.r, root.corTexto.g, root.corTexto.b, 0.65)
    }
  }

  // ── pixel art ─────────────────────────────────────────────────────────
  Canvas {
    id: arte
    visible: root.pixel
    x: 0; y: 0
    width: root.width + 3 * root.px
    height: root.height + 3 * root.px
    antialiasing: false
    renderStrategy: Canvas.Cooperative
    property string chave: root.est + "|" + root.width + "x" + root.height + "|" + root.corFundo + root.corTexto
                           + "|" + (root.est === "conquista" ? root.blocosAcesos : 0) + "|" + root.app
    onChaveChanged: requestPaint()
    onPaint: {
      var c = getContext("2d")
      c.reset()
      if (!root.pixel) return
      var P = root.px, W = Math.floor(root.width / P), H = Math.floor(root.height / P)
      var fundo = String(root.corFundo), texto = String(root.corTexto), apagada = String(root.corApagada)
      switch (root.est) {
      case "rpg":
        Px.caixa(c, P, 0, 0, W, H, fundo, texto, 2)
        Px.caixa(c, P, 2, 2, W - 4, H - 4, fundo, apagada, 1)
        Px.sprite(c, P, Px.SETA, W - 10, H - 7, { k: texto })
        break
      case "balao":
        Px.caixa(c, P, 14, 0, W - 14, H, fundo, texto, 3)
        Px.sprite(c, P, Px.CAUDA, 11, H - 8, { k: texto, w: fundo })
        Px.rect(c, P, 14, H - 7, 1, 3, fundo)
        Px.sprite(c, P, Px.GATO, 0, H - 11, Px.GATO_CORES)
        break
      case "janela":
        Px.rect(c, P, 2, 2, W, H, "rgba(0,0,0,0.45)")
        Px.rect(c, P, 0, 0, W, H, texto)
        Px.rect(c, P, 1, 1, W - 2, H - 2, fundo)
        for (var j = 0; j < 9; j += 2) Px.rect(c, P, 2, 2 + j, W - 4, 1, texto)
        Px.rect(c, P, 5, 2, 9, 9, fundo)
        Px.rect(c, P, 6, 3, 7, 7, texto); Px.rect(c, P, 7, 4, 5, 5, fundo)
        var tw = Math.ceil((tituloJanela.implicitWidth + 16) / P)
        Px.rect(c, P, Math.floor((W - tw) / 2), 1, tw, 10, fundo)
        Px.rect(c, P, 1, 11, W - 2, 1, texto)
        break
      case "conquista":
        Px.rect(c, P, 2, 2, W, H, "#000000")
        Px.rect(c, P, 0, 0, W, H, "#d0d0d0")
        Px.rect(c, P, 1, 1, W - 2, H - 2, "#1e1e1e")
        Px.rect(c, P, 5, 4, 16, 16, "#d0d0d0"); Px.rect(c, P, 6, 5, 14, 14, "#2c2c2c")
        Px.pontilhado(c, P, 6, 5, 14, 14, "#383838")
        for (var b = 0; b < 10; b++) Px.rect(c, P, 26 + b * 9, H - 7, 7, 3, b < root.blocosAcesos ? "#e0e0e0" : "#4a4a4a")
        break
      case "portatil":
        Px.pontilhado(c, P, 3, 3, W, H, "#2b2b2b")
        Px.rect(c, P, 0, 0, W, H, "#2b2b2b")
        Px.rect(c, P, 2, 2, W - 4, H - 4, "#c9c9c9")
        Px.rect(c, P, 3, 3, W - 6, 1, "#e6e6e6")
        break
      case "vidro-pixel":
        Px.pontilhado(c, P, 1, H, W - 2, 2, "rgba(0,0,0,0.35)")
        var f = root.corFundo
        Px.forma(c, P, 0, 0, W, H, 3, Qt.rgba(f.r, f.g, f.b, 0.72).toString())
        Px.pontilhadoForma(c, P, 0, 0, W, H, 3, fundo)
        Px.forma(c, P, 3, 0, W - 6, 1, 0, root.escuroTema ? "#555555" : "#ffffff")
        break
      }
    }
  }
  // moldura do ícone e nome do app na barra de título (desenhados por cima do Canvas)
  Text {
    id: tituloJanela
    visible: root.est === "janela"
    y: 1
    anchors.horizontalCenter: parent.horizontalCenter
    text: root.app || "Simba OS"
    font.family: "Simba Pixel"; font.pixelSize: 20; font.bold: true
    color: root.corTexto
    renderType: Text.NativeRendering
  }
  // fechar (✕)
  Text {
    visible: root.comFechar
    anchors.top: parent.top; anchors.right: parent.right
    anchors.topMargin: root.est === "windows" ? 9 : 10
    anchors.rightMargin: 14
    text: root.est === "vidro-pixel" ? "×" : "✕"
    font.family: root.est === "vidro-pixel" ? "Simba Pixel" : "Adwaita Sans"
    font.pixelSize: root.est === "vidro-pixel" ? 20 : 12
    color: root.est === "escuro" ? "#9a9a9a" : Qt.rgba(root.corTexto.r, root.corTexto.g, root.corTexto.b, 0.5)
    MouseArea { anchors.fill: parent; anchors.margins: -6; cursorShape: Qt.PointingHandCursor; onClicked: root.closeRequested() }
  }

  // ── conteúdo dos estilos novos ─────────────────────────────────────────
  RowLayout {
    id: conteudo
    visible: !root.legado
    x: root.margens[0]; y: root.margens[1]
    width: root.width - root.margens[0] - root.margens[2]
    spacing: root.pixel ? 12 : 12

    Item {
      id: iconeNovo
      readonly property bool temImagem: root.hasSmallIcon && iconeImg.status !== Image.Error
      visible: temImagem || root.hasGlyph
      Layout.preferredWidth: root.tamIcone
      Layout.preferredHeight: root.tamIcone
      Layout.alignment: root.pixel ? Qt.AlignTop : Qt.AlignVCenter
      Layout.topMargin: root.pixel ? 2 : 0
      // fundo do ícone (Cartão suave, Escuro, Pílula)
      Rectangle {
        anchors.fill: parent
        anchors.margins: -4
        visible: ["suave", "escuro", "pilula"].indexOf(root.est) >= 0
        radius: root.est === "pilula" ? width / 2 : 12
        color: root.est === "escuro" ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(root.corTexto.r, root.corTexto.g, root.corTexto.b, 0.06)
      }
      Image {
        id: iconeImg
        anchors.fill: parent
        anchors.margins: root.est === "pilula" ? 4 : 0
        source: root.smallIconSource
        // pixel art: ícone pequeno ampliado sem suavizar
        sourceSize.width: root.pixel ? 12 : root.tamIcone * Screen.devicePixelRatio
        sourceSize.height: root.pixel ? 12 : root.tamIcone * Screen.devicePixelRatio
        fillMode: Image.PreserveAspectFit
        smooth: !root.pixel
        mipmap: false
        asynchronous: true
        visible: !root.hasGlyph || status === Image.Ready
      }
      Text {
        anchors.centerIn: parent
        visible: root.hasGlyph && iconeImg.status !== Image.Ready
        text: root.glyph
        color: root.corTitulo
        font.family: root.fontFamily
        font.pixelSize: root.pixel ? 20 : Style.font.displayLarge
      }
    }

    ColumnLayout {
      Layout.fillWidth: true
      Layout.alignment: Qt.AlignVCenter
      spacing: root.pixel ? 0 : 2

      Text {
        textFormat: Text.PlainText
        Layout.fillWidth: true
        visible: root.summary.length > 0
        text: root.summary
        font.family: root.fonteTexto
        font.pixelSize: root.tamTitulo
        font.bold: true
        color: root.corTitulo
        renderType: root.pixel ? Text.NativeRendering : Text.QtRendering
        wrapMode: Text.WordWrap
        elide: Text.ElideRight
        maximumLineCount: root.est === "pilula" ? 1 : 2
      }
      Text {
        Layout.fillWidth: true
        visible: root.sanitizedBody.length > 0
        text: root.styledBody
        textFormat: Text.StyledText
        font.family: root.fonteTexto
        font.pixelSize: root.tamCorpo
        color: root.corCorpo
        renderType: root.pixel ? Text.NativeRendering : Text.QtRendering
        wrapMode: root.est === "pilula" ? Text.NoWrap : Text.WordWrap
        elide: Text.ElideRight
        maximumLineCount: root.est === "pilula" ? 1 : 3
        lineHeight: root.pixel ? 0.95 : 1.0
      }
    }
  }

  // ── estilo antigo (padrao): exatamente como era ──────────────────────────
  ColumnLayout {
    id: mainColumn
    visible: root.legado
    anchors.top: parent.top
    anchors.left: parent.left
    anchors.right: parent.right
    anchors.topMargin: root.borderTop
    anchors.leftMargin: root.borderLeft
    anchors.rightMargin: root.borderRight
    spacing: 0

    RowLayout {
      Layout.fillWidth: true
      Layout.leftMargin: Style.space(12)
      Layout.rightMargin: Style.space(12)
      Layout.topMargin: root.singleLineToast ? Style.space(7) : Style.space(10)
      Layout.bottomMargin: root.singleLineToast ? Style.space(7) : Style.space(10)
      spacing: root.collapseRedundantIcon ? 0 : (root.compactGlyph ? Style.space(8) : Style.space(12))

      Item {
        id: smallIconSlot
        Layout.preferredWidth: visible ? Style.space(40) : 0
        Layout.preferredHeight: visible ? Style.space(40) : 0
        Layout.alignment: Qt.AlignVCenter
        visible: !root.collapseRedundantIcon && !root.compactGlyph && (root.hasSmallIcon || root.hasGlyph) && (root.hasGlyph || smallIconImage.status !== Image.Error)

        Image {
          id: smallIconImage
          anchors.fill: parent
          source: root.legado ? root.smallIconSource : ""
          sourceSize.width: smallIconSlot.width * Screen.devicePixelRatio
          sourceSize.height: smallIconSlot.height * Screen.devicePixelRatio
          fillMode: Image.PreserveAspectFit
          asynchronous: true
          smooth: true
          visible: !root.hasGlyph || smallIconImage.status === Image.Ready
        }
        Text {
          textFormat: Text.PlainText
          anchors.centerIn: parent
          visible: root.hasGlyph && smallIconImage.status !== Image.Ready
          text: root.glyph
          color: Commons.Color.notifications.text
          font.family: root.fontFamily
          font.pixelSize: Style.font.displayLarge
        }
      }

      Text {
        textFormat: Text.PlainText
        Layout.alignment: Qt.AlignVCenter
        visible: root.compactGlyph
        text: root.glyph
        color: Commons.Color.notifications.text
        font.family: root.fontFamily
        font.pixelSize: Style.font.icon
      }

      ColumnLayout {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignVCenter
        spacing: Style.space(2)

        Text {
          textFormat: Text.PlainText
          Layout.fillWidth: true
          visible: root.summary.length > 0
          text: root.summary
          font.family: "Liberation Sans"
          color: Commons.Color.notifications.text
          font.pixelSize: Style.font.title
          font.bold: true
          wrapMode: Text.WordWrap
          elide: Text.ElideRight
          maximumLineCount: 2
        }
        Text {
          Layout.fillWidth: true
          Layout.topMargin: Style.space(2)
          visible: root.sanitizedBody.length > 0
          text: root.styledBody
          textFormat: Text.StyledText
          font.family: "Liberation Sans"
          color: root.bodyColor
          font.pixelSize: Style.font.title
          wrapMode: Text.WordWrap
          elide: Text.ElideRight
          maximumLineCount: 3
        }
      }
    }
  }
}
