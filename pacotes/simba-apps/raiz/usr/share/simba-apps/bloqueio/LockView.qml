import "idiomas"
import QtQuick 6.11
import QtQuick.Effects
import Quickshell
import Quickshell.Io

// Tela de bloqueio do Simba OS, no jeito do Windows:
//  1. Cortina: o papel de parede nítido, com a hora e a data grandes no canto inferior esquerdo.
//  2. Qualquer tecla, clique ou rolagem levanta a cortina: o fundo desfoca e aparecem a foto
//     da conta Google (ou o gato do Simba, sem conta), o nome e o campo de senha.
//  3. Esc ou 30 s sem mexer voltam para a cortina. Canto inferior direito: energia.
Item {
  id: root

  // ── interface usada pelo Service.qml (não mudar os nomes) ──
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

  signal submitPassword(string password)
  signal passwordTextEdited(string password)
  signal clearFailureRequested()
  signal wakeRequested()

  // ── estado próprio ──
  property bool mostrarLogin: false          // false = cortina com o relógio
  property bool menuEnergia: false
  property date agora: new Date()
  readonly property string fonte: "Adwaita Sans"
  readonly property bool errorState: failureMessage.length > 0

  readonly property var contaCfg: {
    try { return JSON.parse(cfgConta.text()) || {} } catch (e) { return {} }
  }
  readonly property string nomeExibido: {
    if (contaCfg.nome) return contaCfg.nome
    var g = String(gecos.text || "").trim()
    if (g) return g
    var u = Quickshell.env("USER") || ""
    return u.charAt(0).toUpperCase() + u.slice(1)
  }

  function fileUrl(path) {
    if (!path) return ""
    var encoded = String(path).split("/").map(encodeURIComponent).join("/")
    return "file://" + encoded + "?v=" + backgroundVersion
  }

  function forcePasswordFocus() { passwordInput.forceActiveFocus() }
  function clearPassword() { passwordTextEdited("") }

  function levantar() {
    if (!mostrarLogin) mostrarLogin = true
    ocioso.restart()
    wakeRequested()
    forcePasswordFocus()
  }

  function baixar() {
    mostrarLogin = false
    menuEnergia = false
    passwordTextEdited("")
    forcePasswordFocus()      // continua recebendo as teclas para levantar de novo
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
    else mostrarLogin = false
  }
  // senha errada: fica no login, mostrando o aviso
  onFailureMessageChanged: if (failureMessage.length > 0) { mostrarLogin = true; ocioso.restart() }
  Component.onCompleted: {
    syncPasswordText()
    if (inputEnabled) Qt.callLater(forcePasswordFocus)
  }

  Timer { interval: 1000; running: true; repeat: true; onTriggered: root.agora = new Date() }

  // 30 s parado no login, sem nada digitado: volta para a cortina (como no Windows)
  Timer {
    id: ocioso
    interval: 30000
    running: root.mostrarLogin && passwordInput.text.length === 0 && !root.authenticatingPassword
    onTriggered: root.baixar()
  }

  FileView {
    id: cfgConta
    path: Quickshell.env("HOME") + "/.config/conta/config.json"
    printErrors: false
    watchChanges: true
    onFileChanged: reload()
  }
  Process {
    id: procGecos
    running: true
    command: ["sh", "-c", "getent passwd \"$USER\" | cut -d: -f5 | cut -d, -f1"]
    stdout: StdioCollector { id: gecos }
  }

  Rectangle {
    anchors.fill: parent
    color: "#101418"

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

    // fundo desfocado do login (aparece por cima do nítido ao levantar a cortina)
    MultiEffect {
      anchors.fill: wallpaper
      source: wallpaper
      autoPaddingEnabled: false
      visible: opacity > 0
      opacity: root.mostrarLogin ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } }
      // desfoque como o do Windows: a imagem continua reconhecível (cores e formas), sem
      // escurecer — com o desfoque máximo e -12% de brilho um papel escuro virava preto
      blurEnabled: wallpaper.status === Image.Ready
      blur: 0.55
      blurMax: 48
      blurMultiplier: 0.6
      brightness: 0.04
    }

    MouseArea {
      anchors.fill: parent
      hoverEnabled: true
      acceptedButtons: Qt.LeftButton | Qt.RightButton
      onClicked: { root.menuEnergia = false; root.levantar() }
      onPositionChanged: { root.wakeRequested(); if (root.mostrarLogin) ocioso.restart() }
      onWheel: function(w) { root.levantar() }
    }

    // ── 1. Cortina: hora e data ──
    Item {
      id: cortina
      anchors.fill: parent
      opacity: root.mostrarLogin ? 0 : 1
      visible: opacity > 0
      // sobe e some, como a cortina do Windows
      transform: Translate { y: root.mostrarLogin ? -cortina.height * 0.06 : 0; Behavior on y { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } } }
      Behavior on opacity { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }

      Column {
        id: relogio
        anchors { left: parent.left; bottom: parent.bottom; leftMargin: Math.round(parent.width * 0.026); bottomMargin: Math.round(parent.height * 0.1) }
        spacing: -Math.round(cortina.height * 0.005)
        Text {
          text: Qt.formatTime(root.agora, "HH:mm")
          color: "white"
          font.family: root.fonte
          font.pixelSize: Math.round(Math.max(72, Math.min(160, cortina.height * 0.125)))
          font.weight: Font.Light
        }
        Text {
          leftPadding: Math.round(cortina.height * 0.004)
          text: Qt.locale().toString(root.agora, I18n.t("dddd, d 'de' MMMM"))
          color: "white"
          font.family: root.fonte
          font.pixelSize: Math.round(Math.max(26, Math.min(52, cortina.height * 0.042)))
          font.weight: Font.Light
        }
        layer.enabled: true
        layer.effect: MultiEffect { shadowEnabled: true; shadowColor: Qt.rgba(0, 0, 0, 0.5); shadowBlur: 0.7; shadowVerticalOffset: 1 }
      }
    }

    // ── 2. Login: foto, nome e senha ──
    Item {
      id: login
      anchors.fill: parent
      opacity: root.mostrarLogin ? 1 : 0
      visible: opacity > 0
      Behavior on opacity { NumberAnimation { duration: 300; easing.type: Easing.OutCubic } }

      Column {
        id: coluna
        anchors.centerIn: parent
        anchors.verticalCenterOffset: -Math.round(parent.height * 0.03)
        spacing: 0
        transform: Translate { y: root.mostrarLogin ? 0 : 30; Behavior on y { NumberAnimation { duration: 350; easing.type: Easing.OutCubic } } }

        // avatar: foto da conta Google; sem conta, o gato do Simba
        Item {
          id: avatar
          anchors.horizontalCenter: parent.horizontalCenter
          readonly property int tam: Math.round(Math.max(140, Math.min(200, login.height * 0.18)))
          width: tam; height: tam

          Image {
            id: foto
            anchors.fill: parent
            source: "file://" + Quickshell.env("HOME") + "/.local/state/conta/foto.jpg"
            cache: false
            asynchronous: true
            fillMode: Image.PreserveAspectCrop
            sourceSize: Qt.size(400, 400)
            visible: false
          }
          Rectangle { id: mascara; anchors.fill: parent; radius: width / 2; visible: false; layer.enabled: true }
          MultiEffect {
            anchors.fill: parent
            visible: foto.status === Image.Ready
            source: foto
            maskEnabled: true
            maskSource: mascara
            maskThresholdMin: 0.5
            maskSpreadAtMin: 1.0
          }
          Rectangle {
            anchors.fill: parent
            visible: foto.status !== Image.Ready
            radius: width / 2
            color: Qt.rgba(1, 1, 1, 0.16)
            SimbaSimbolo { anchors.centerIn: parent; width: Math.round(avatar.tam * 0.58); height: width }
          }
        }

        Item { width: 1; height: Math.round(login.height * 0.028) }

        Text {
          anchors.horizontalCenter: parent.horizontalCenter
          text: root.nomeExibido
          color: "white"
          font.family: root.fonte
          font.pixelSize: Math.round(Math.max(28, Math.min(40, login.height * 0.035)))
          font.weight: Font.Normal
          layer.enabled: true
          layer.effect: MultiEffect { shadowEnabled: true; shadowColor: Qt.rgba(0, 0, 0, 0.45); shadowBlur: 0.5 }
        }

        Item { width: 1; height: Math.round(login.height * 0.03) }

        // campo de senha com a seta de entrar (como o do Windows)
        Rectangle {
          id: campo
          anchors.horizontalCenter: parent.horizontalCenter
          width: Math.round(Math.max(280, Math.min(340, login.width * 0.2)))
          height: 36
          radius: 4
          color: passwordInput.activeFocus ? Qt.rgba(1, 1, 1, 0.92) : Qt.rgba(1, 1, 1, 0.75)
          border.width: 1
          border.color: root.errorState ? "#ff99a4" : Qt.rgba(1, 1, 1, 0.9)
          clip: true

          TextInput {
            id: passwordInput
            anchors { left: parent.left; right: botaoEntrar.left; verticalCenter: parent.verticalCenter; leftMargin: 10; rightMargin: 6 }
            activeFocusOnPress: true
            clip: true
            enabled: root.inputEnabled && !root.authenticatingPassword
            readOnly: root.authenticatingPassword
            echoMode: TextInput.Password
            passwordCharacter: "●"
            passwordMaskDelay: 0
            color: "#1b1b1b"
            selectionColor: "#0067c0"
            selectedTextColor: "white"
            font.family: root.fonte
            font.pixelSize: 15
            cursorVisible: activeFocus && root.mostrarLogin && !root.authenticatingPassword
            cursorDelegate: Rectangle { width: 1; color: "#1b1b1b"; visible: passwordInput.cursorVisible }

            onTextChanged: {
              if (!root.syncingPasswordText) root.passwordTextEdited(text)
              if (text.length > 0) {
                if (!root.mostrarLogin) root.mostrarLogin = true
                ocioso.restart()
                root.wakeRequested()
              }
              if (text.length > 0 && root.failureMessage.length > 0) root.clearFailureRequested()
            }

            onAccepted: {
              if (!root.mostrarLogin) { root.levantar(); return }
              var submitted = root.passwordText
              root.passwordTextEdited("")
              if (submitted.length > 0) root.submitPassword(submitted)
            }

            Keys.onPressed: function(event) {
              root.wakeRequested()
              if (!root.mostrarLogin) {
                // na cortina: qualquer tecla levanta; letras já entram na senha
                root.levantar()
                if (event.text.length === 0 || event.key === Qt.Key_Space || event.key === Qt.Key_Return
                    || event.key === Qt.Key_Enter || event.key === Qt.Key_Escape) event.accepted = true
                return
              }
              ocioso.restart()
              if (event.key === Qt.Key_Escape) {
                if (root.menuEnergia) root.menuEnergia = false
                else if (passwordInput.text.length > 0) root.passwordTextEdited("")
                else root.baixar()
                event.accepted = true
              } else if (event.modifiers & Qt.ControlModifier && event.key === Qt.Key_U) {
                root.passwordTextEdited("")
                event.accepted = true
              }
            }
          }

          Text {
            anchors.fill: passwordInput
            verticalAlignment: Text.AlignVCenter
            visible: passwordInput.text.length === 0
            text: root.authenticatingPassword ? I18n.t("Verificando…") : I18n.t("Senha")
            color: "#5f5f5f"
            font.family: root.fonte
            font.pixelSize: 15
            elide: Text.ElideRight
          }

          // impressão digital cadastrada: dica dentro do campo
          Text {
            anchors { right: botaoEntrar.left; rightMargin: 6; verticalCenter: parent.verticalCenter }
            visible: root.fingerprintConfigured && passwordInput.text.length === 0
            text: "󰈷"
            color: "#5f5f5f"
            font.family: "JetBrainsMono Nerd Font"
            font.pixelSize: 18
          }

          Rectangle {
            id: botaoEntrar
            anchors { right: parent.right; top: parent.top; bottom: parent.bottom; margins: 1 }
            width: height
            radius: 3
            color: areaEntrar.pressed ? "#d0d0d0" : (areaEntrar.containsMouse ? "#e6e6e6" : "transparent")
            Text {
              anchors.centerIn: parent
              text: root.authenticatingPassword ? "󰔟" : "󰁔"      // ampulheta / seta →
              color: "#1b1b1b"
              font.family: "JetBrainsMono Nerd Font"
              font.pixelSize: 18
            }
            MouseArea {
              id: areaEntrar
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: passwordInput.accepted()
            }
          }
        }

        Item { width: 1; height: 14 }

        Text {
          anchors.horizontalCenter: parent.horizontalCenter
          width: campo.width + 80
          horizontalAlignment: Text.AlignHCenter
          wrapMode: Text.WordWrap
          visible: root.errorState
          text: I18n.t("A senha está incorreta. Tente novamente.")
          color: "white"
          font.family: root.fonte
          font.pixelSize: 15
          layer.enabled: true
          layer.effect: MultiEffect { shadowEnabled: true; shadowColor: Qt.rgba(0, 0, 0, 0.6); shadowBlur: 0.5 }
        }
      }
    }

    // ── 3. Energia (canto inferior direito, nas duas telas) ──
    Row {
      id: cantos
      anchors { right: parent.right; bottom: parent.bottom; rightMargin: 28; bottomMargin: 26 }
      spacing: 18
      opacity: root.mostrarLogin ? 1 : 0.85

      Rectangle {
        id: botaoEnergia
        width: 44; height: 44; radius: 6
        visible: root.mostrarLogin
        color: areaEnergia.containsMouse || root.menuEnergia ? Qt.rgba(1, 1, 1, 0.15) : "transparent"
        Text {
          anchors.centerIn: parent
          text: "󰐥"
          color: "white"
          font.family: "JetBrainsMono Nerd Font"
          font.pixelSize: 24
        }
        MouseArea {
          id: areaEnergia
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: { root.menuEnergia = !root.menuEnergia; ocioso.restart() }
        }
      }
    }

    Rectangle {
      id: menu
      visible: root.menuEnergia && root.mostrarLogin
      anchors { right: parent.right; bottom: cantos.top; rightMargin: 20; bottomMargin: 8 }
      width: 190
      height: opcoes.implicitHeight + 12
      radius: 8
      color: Qt.rgba(0.13, 0.13, 0.13, 0.96)
      border.width: 1
      border.color: Qt.rgba(1, 1, 1, 0.12)

      Column {
        id: opcoes
        anchors { left: parent.left; right: parent.right; top: parent.top; margins: 6 }
        Repeater {
          model: [
            { rotulo: I18n.t("Suspender"), glifo: "󰒲", cmd: ["systemctl", "suspend"] },
            { rotulo: I18n.t("Desligar"), glifo: "󰐥", cmd: ["systemctl", "poweroff"] },
            { rotulo: I18n.t("Reiniciar"), glifo: "󰜉", cmd: ["systemctl", "reboot"] }
          ]
          delegate: Rectangle {
            required property var modelData
            width: opcoes.width
            height: 38
            radius: 5
            color: areaOpcao.containsMouse ? Qt.rgba(1, 1, 1, 0.1) : "transparent"
            Row {
              anchors { left: parent.left; leftMargin: 12; verticalCenter: parent.verticalCenter }
              spacing: 12
              Text { text: modelData.glifo; color: "white"; font.family: "JetBrainsMono Nerd Font"; font.pixelSize: 16; anchors.verticalCenter: parent.verticalCenter }
              Text { text: modelData.rotulo; color: "white"; font.family: root.fonte; font.pixelSize: 14; anchors.verticalCenter: parent.verticalCenter }
            }
            MouseArea {
              id: areaOpcao
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: {
                root.menuEnergia = false
                if (root.inputEnabled) Quickshell.execDetached(modelData.cmd)
              }
            }
          }
        }
      }
    }
  }
}
