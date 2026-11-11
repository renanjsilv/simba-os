// Tela de login com a identidade da marca (mesmas cores e logo da tela de inicialização).
// Instalada pelo marca/aplicar em /usr/share/sddm/themes/simba-marca; cores em theme.conf.
import QtQuick 2.0
import SddmComponents 2.0

Rectangle {
  id: root
  width: 640
  height: 480
  color: config.fundo || "#f4f4f2"

  // Instalação nova: ninguém entrou ainda e lastUser vem vazio. Usa o primeiro usuário
  // da lista (NameRole = Qt.UserRole + 1); senão o login falha sempre.
  property string currentUser: {
    if (userModel.lastUser)
      return userModel.lastUser
    for (var i = 0; i < userModel.rowCount(); i++) {
      var n = userModel.data(userModel.index(i, 0), Qt.UserRole + 1)
      if (n)
        return n.toString()
    }
    return ""
  }
  property bool loginFailed: false
  property int sessionIndex: {
    for (var i = 0; i < sessionModel.rowCount(); i++) {
      var name = (sessionModel.data(sessionModel.index(i, 0), Qt.DisplayRole) || "").toString()
      if (name.indexOf("uwsm") !== -1)
        return i
    }
    return sessionModel.lastIndex
  }

  Connections {
    target: sddm
    function onLoginFailed() {
      root.loginFailed = true
      password.text = ""
      password.focus = true
    }
    function onLoginSucceeded() {
      root.loginFailed = false
    }
  }

  Column {
    anchors.centerIn: parent
    spacing: 36

    Image {
      source: "logo.png"
      // o logo é gerado com 600 px de largura: metade em 1080p, como no Plymouth
      width: Math.min(sourceSize.width, Math.round(root.height * 0.28 * sourceSize.width / Math.max(1, sourceSize.height)))
      height: sourceSize.width > 0 ? Math.round(width * sourceSize.height / sourceSize.width) : 0
      fillMode: Image.PreserveAspectFit
      smooth: true
      anchors.horizontalCenter: parent.horizontalCenter
    }

    Column {
      anchors.horizontalCenter: parent.horizontalCenter
      spacing: 10

      Text {
        anchors.horizontalCenter: parent.horizontalCenter
        text: root.loginFailed ? (config.textoErro || "Senha incorreta. Tente de novo.") : (config.textoEntrar || "Digite a senha para entrar")
        color: root.loginFailed ? (config.erro || "#c42b1c") : (config.texto || "#1b1b1b")
        font.family: "Cantarell"
        font.pixelSize: Math.max(14, Math.round(root.height / 60))
      }

      Rectangle {
        id: campo
        width: Math.max(280, Math.round(root.height * 0.36))
        height: Math.max(40, Math.round(root.height * 0.045))
        radius: height / 2
        color: config.campoFundo || "#ffffff"
        border.width: 2
        border.color: root.loginFailed ? (config.erro || "#c42b1c") : (config.campoBorda || "#b5b5b2")

        Row {
          anchors.centerIn: parent
          spacing: 8
          Repeater {
            model: Math.min(password.text.length, 18)
            Rectangle {
              width: 9; height: 9; radius: 4.5
              color: config.ponto || "#1b1b1b"
            }
          }
        }

        TextInput {
          id: password
          anchors.fill: parent
          anchors.leftMargin: 20
          anchors.rightMargin: 20
          verticalAlignment: TextInput.AlignVCenter
          echoMode: TextInput.Password
          color: "transparent"
          selectionColor: "transparent"
          selectedTextColor: "transparent"
          cursorDelegate: Item {}
          focus: true

          onTextChanged: root.loginFailed = false

          Keys.onPressed: {
            if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
              sddm.login(root.currentUser, password.text, root.sessionIndex)
              event.accepted = true
            }
          }
        }
      }
    }
  }

  Component.onCompleted: password.forceActiveFocus()
}
