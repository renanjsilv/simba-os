import "idiomas"
import QtQuick 6.11
import QtQuick.Effects
import Quickshell
import qs.Commons
import qs.Commons as Commons
import qs.Ui

Item {
  id: root

  property string backgroundPath: ""
  property int backgroundVersion: 0
  property bool fingerprintConfigured: false
  property bool authenticatingPassword: false
  property string failureMessage: ""
  property int failedAttempts: 0
  property bool inputEnabled: true
  property bool loadBackground: true
  property string passwordText: ""
  property bool syncingPasswordText: false

  readonly property string placeholderText: I18n.t("Digite a senha")
  readonly property int fieldWidth: 381
  readonly property int fieldHeight: 67
  readonly property int outlineThickness: 3
  readonly property int fieldFontSize: Math.round(Style.font.heading * 1.125)
  readonly property int passwordDotFontSize: Math.round(Style.font.heading * 1.33)
  readonly property int passwordDotLetterSpacing: Math.round(Style.font.heading * 0.19)
  // Space to keep clear on each side of the field for the fingerprint icon
  // (icon width plus a gap) so the centered dots never run under it.
  readonly property real fingerprintReserve: fingerprintConfigured ? Math.round(fingerprintIcon.implicitWidth + 12) : 0
  // Shrink the dots to fit once the password outgrows the field, so every
  // keystroke stays visible — otherwise long passwords clip with no feedback.
  readonly property real passwordDotScale: dotMetrics.advanceWidth > 0
    ? Math.min(1, (passwordInput.width - 4) / dotMetrics.advanceWidth)
    : 1
  readonly property bool showPasswordCursor: inputEnabled && !authenticatingPassword && failureMessage.length === 0
  readonly property bool errorState: failureMessage.length > 0
  readonly property var inputBorderSpec: errorState
    ? Border.surfaceSpec("lock", "border-error", Commons.Color.lock.borderError, root.outlineThickness, "border-alpha")
    : Border.surfaceSpec("lock", "border-active", Commons.Color.lock.borderActive, root.outlineThickness, "border-alpha")

  signal submitPassword(string password)
  signal passwordTextEdited(string password)
  signal clearFailureRequested()
  signal wakeRequested()

  // Cache-busts the lock background by appending `?v=`. Adding a query
  // string keeps Image's loader happy while forcing it to reload when the
  // user picks a new background mid-session.
  function fileUrl(path) {
    if (!path) return ""
    var encoded = String(path).split("/").map(encodeURIComponent).join("/")
    return "file://" + encoded + "?v=" + backgroundVersion
  }

  function forcePasswordFocus() {
    passwordInput.forceActiveFocus()
  }

  function clearPassword() {
    passwordTextEdited("")
  }

  function syncPasswordText() {
    if (passwordInput.text === passwordText) return
    syncingPasswordText = true
    passwordInput.text = passwordText
    syncingPasswordText = false
  }

  onPasswordTextChanged: syncPasswordText()
  onInputEnabledChanged: {
    if (inputEnabled) Qt.callLater(forcePasswordFocus)
  }
  Component.onCompleted: {
    syncPasswordText()
    if (inputEnabled) Qt.callLater(forcePasswordFocus)
  }

  // Measures the masked password at full size; passwordDotScale compares this
  // against the field width to decide how far the dots must shrink to fit.
  TextMetrics {
    id: dotMetrics
    font.family: Style.font.family
    font.pixelSize: root.passwordDotFontSize
    font.letterSpacing: root.passwordDotLetterSpacing
    text: "●".repeat(passwordInput.text.length)
  }

  Rectangle {
    anchors.fill: parent
    color: Commons.Color.background

    Image {
      id: wallpaper
      anchors.fill: parent
      source: root.loadBackground ? root.fileUrl(root.backgroundPath) : ""
      fillMode: Image.PreserveAspectCrop
      asynchronous: true
      cache: false
      sourceSize.width: width
      sourceSize.height: height
    }

    MultiEffect {
      anchors.fill: wallpaper
      source: wallpaper
      autoPaddingEnabled: false
      blurEnabled: root.loadBackground && wallpaper.status === Image.Ready
      blur: 1.0
      blurMax: 128
      blurMultiplier: 1.25
      contrast: -0.08
    }

    MouseArea {
      anchors.fill: parent
      hoverEnabled: true
      onClicked: { root.wakeRequested(); root.forcePasswordFocus() }
      onPositionChanged: root.wakeRequested()
    }

    // ── Simba OS: relógio e data no canto inferior esquerdo (como no Windows) ──
    Item {
      id: relogioLock
      property date agora: new Date()
      Timer { interval: 1000; running: true; repeat: true; onTriggered: relogioLock.agora = new Date() }
      anchors { left: parent.left; bottom: parent.bottom; leftMargin: Math.round(parent.width * 0.035); bottomMargin: Math.round(parent.height * 0.06) }
      width: colunaRelogio.width; height: colunaRelogio.height
      Column {
        id: colunaRelogio
        spacing: 2
        Text {
          text: Qt.formatTime(relogioLock.agora, "HH:mm")
          color: "white"
          font.family: "Adwaita Sans"
          font.pixelSize: Math.round(Math.min(96, relogioLock.parent.height * 0.1))
          font.weight: Font.DemiBold
          font.letterSpacing: -2
        }
        Text {
          leftPadding: 4
          text: { var t = Qt.locale().toString(relogioLock.agora, I18n.t("dddd, d 'de' MMMM")); return t.charAt(0).toUpperCase() + t.slice(1) }
          color: Qt.rgba(1, 1, 1, 0.9)
          font.family: "Adwaita Sans"
          font.pixelSize: 22
          font.weight: Font.Medium
        }
      }
      layer.enabled: true
      layer.effect: MultiEffect { shadowEnabled: true; shadowColor: Qt.rgba(0, 0, 0, 0.45); shadowBlur: 0.6; shadowVerticalOffset: 2 }
    }

    // Sem foto da conta: avatar redondo com o gato do Simba
    Rectangle {
      visible: foto.status !== Image.Ready
      width: 132; height: 132; radius: 66
      anchors { horizontalCenter: inputField.horizontalCenter; bottom: inputField.top; bottomMargin: 68 }
      color: Qt.rgba(1, 1, 1, 0.14)
      border.width: 2
      border.color: Qt.rgba(1, 1, 1, 0.35)
      SimbaSimbolo { anchors.centerIn: parent; width: 70; height: 70; cor: "white" }
    }
    // nome de quem está usando, entre o avatar e a senha
    Text {
      anchors { horizontalCenter: inputField.horizontalCenter; bottom: inputField.top; bottomMargin: 30 }
      text: { var u = Quickshell.env("USER") || ""; return u.charAt(0).toUpperCase() + u.slice(1) }
      color: "white"
      font.family: "Adwaita Sans"
      font.pixelSize: 22
      font.weight: Font.DemiBold
      layer.enabled: true
      layer.effect: MultiEffect { shadowEnabled: true; shadowColor: Qt.rgba(0, 0, 0, 0.5); shadowBlur: 0.5 }
    }

    // marca discreta no rodapé
    Row {
      anchors { right: parent.right; bottom: parent.bottom; rightMargin: Math.round(parent.width * 0.035); bottomMargin: Math.round(parent.height * 0.06) + 6 }
      spacing: 8
      opacity: 0.75
      SimbaSimbolo { width: 20; height: 20; cor: "white"; anchors.verticalCenter: parent.verticalCenter }
      Text { text: I18n.t("Simba OS"); color: "white"; font.family: "Adwaita Sans"; font.pixelSize: 14; font.weight: Font.DemiBold; anchors.verticalCenter: parent.verticalCenter }
    }

    // Foto da conta Google conectada (Configurações › Contas; `conta foto`
    // a baixa e `conta sair` a apaga). Sem conta: a tela fica como a original.
    Item {
      id: fotoConta
      readonly property string arquivo: "file://" + Quickshell.env("HOME") + "/.local/state/conta/foto.jpg"
      visible: foto.status === Image.Ready
      width: 132; height: 132
      anchors { horizontalCenter: inputField.horizontalCenter; bottom: inputField.top; bottomMargin: 68 }
      Image {
        id: foto
        anchors.fill: parent
        source: fotoConta.arquivo
        cache: false
        asynchronous: true
        fillMode: Image.PreserveAspectCrop
        sourceSize: Qt.size(264, 264)
        visible: false
      }
      Rectangle { id: mascaraFoto; anchors.fill: parent; radius: width / 2; visible: false; layer.enabled: true }
      MultiEffect {
        anchors.fill: parent
        source: foto
        maskEnabled: true
        maskSource: mascaraFoto
        maskThresholdMin: 0.5
        maskSpreadAtMin: 1.0
      }
      Rectangle {
        anchors.fill: parent
        radius: width / 2
        color: "transparent"
        border.width: 2
        border.color: Qt.rgba(1, 1, 1, 0.35)
      }
    }

    BorderSurface {
      id: inputField
      width: root.fieldWidth
      height: root.fieldHeight
      anchors.centerIn: parent
      // um pouco abaixo do centro: mais respiro entre a foto/nome e a senha
      anchors.verticalCenterOffset: 34
      color: Commons.Color.lock.background
      borderSpec: root.inputBorderSpec
      radius: 16
      clip: true

      TextInput {
        id: passwordInput
        anchors.fill: parent
        anchors.topMargin: inputField.borderTop
        // Reserve the fingerprint icon's width on both sides so the centered
        // dots stay symmetric and never slide under the icon as they grow.
        anchors.rightMargin: inputField.borderRight + 18 + root.fingerprintReserve
        anchors.bottomMargin: inputField.borderBottom
        anchors.leftMargin: inputField.borderLeft + 18 + root.fingerprintReserve
        verticalAlignment: TextInput.AlignVCenter
        horizontalAlignment: TextInput.AlignHCenter
        activeFocusOnPress: true
        clip: true
        enabled: root.inputEnabled && !root.authenticatingPassword
        readOnly: root.authenticatingPassword
        echoMode: TextInput.Password
        passwordCharacter: "\u25CF"
        passwordMaskDelay: 0
        color: Commons.Color.lock.text
        selectionColor: Commons.Color.lock.selection
        selectedTextColor: Commons.Color.lock.text
        font.family: Style.font.family
        font.pixelSize: text.length > 0 ? Math.max(1, Math.floor(root.passwordDotFontSize * root.passwordDotScale)) : root.fieldFontSize
        font.letterSpacing: text.length > 0 ? root.passwordDotLetterSpacing * root.passwordDotScale : 0
        cursorVisible: activeFocus && root.showPasswordCursor && text.length > 0
        cursorDelegate: Rectangle {
          width: 2
          color: Commons.Color.lock.text
          visible: passwordInput.cursorVisible
        }

        onTextChanged: {
          if (!root.syncingPasswordText) root.passwordTextEdited(text)
          if (text.length > 0) {
            root.wakeRequested()
          }
          if (text.length > 0 && root.failureMessage.length > 0) root.clearFailureRequested()
        }

        onAccepted: {
          var submitted = root.passwordText
          root.passwordTextEdited("")
          if (submitted.length > 0) root.submitPassword(submitted)
        }

        Keys.onPressed: function(event) {
          root.wakeRequested()
          if (event.key === Qt.Key_Escape || (event.modifiers & Qt.ControlModifier && event.key === Qt.Key_U)) {
            root.passwordTextEdited("")
            event.accepted = true
          }
        }
      }

      Text {
        textFormat: Text.PlainText
        anchors.fill: passwordInput
        text: root.authenticatingPassword ? I18n.t("Verificando…") : (root.failureMessage.length > 0 ? root.failureMessage : root.placeholderText)
        visible: passwordInput.text.length === 0
        color: root.authenticatingPassword ? Commons.Color.lock.text : (root.failureMessage.length > 0 ? Commons.Color.lock.textError : Commons.Color.lock.placeholder)
        font.family: Style.font.family
        font.pixelSize: root.fieldFontSize
        font.italic: !root.authenticatingPassword && root.failureMessage.length > 0
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
      }

      // Fingerprint hint pinned inside the field's right edge when a sensor is
      // enrolled, so the user knows they can touch to unlock instead of typing.
      // Matches hyprlock, which draws its fingerprint icon in the same spot.
      Text {
        id: fingerprintIcon
        objectName: "fingerprintIndicator"
        anchors.right: parent.right
        anchors.rightMargin: inputField.borderRight + 18
        anchors.verticalCenter: parent.verticalCenter
        visible: root.fingerprintConfigured
        text: "󰈷"
        color: Commons.Color.lock.placeholder
        font.family: Style.font.family
        font.pixelSize: Math.round(root.fieldFontSize * 1.1)
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
      }
    }
  }
}
