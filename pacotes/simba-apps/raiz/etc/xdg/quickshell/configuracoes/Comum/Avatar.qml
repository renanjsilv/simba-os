import QtQuick
import QtQuick.Effects
import Quickshell
import qs.Comum

// Foto do usuário (~/.face — a foto da conta Google, ligada por `conta foto`)
// ou, sem foto, a inicial do nome. Redonda quando o tema arredonda (ou
// `redondo: true`), quadrada no visual reto do Simba.
Item {
  id: a
  property string nome: ""
  property bool redondo: Tema.raio > 0
  property color cor: Tema.realce
  property color corTexto: Tema.sobreRealce
  readonly property bool temFoto: foto.status === Image.Ready
  implicitWidth: 48; implicitHeight: 48

  Rectangle {
    id: fundo
    anchors.fill: parent
    radius: a.redondo ? width / 2 : 0
    color: a.cor
    visible: !a.temFoto
    Texto {
      anchors.centerIn: parent
      text: a.nome.charAt(0).toUpperCase()
      color: a.corTexto
      font.pixelSize: parent.width * 0.44
      font.weight: Font.Bold
    }
  }

  Image {
    id: foto
    anchors.fill: parent
    readonly property string caminho: "file://" + Quickshell.env("HOME") + "/.face"
    source: caminho
    cache: false
    asynchronous: true
    fillMode: Image.PreserveAspectCrop
    sourceSize: Qt.size(a.width * 2, a.height * 2)
    visible: false
    // Nova foto: recarrega (mesmo caminho, outro conteúdo).
    Connections {
      target: Navegacao
      function onVersaoFotoChanged() { foto.source = ""; foto.source = foto.caminho }
    }
  }
  Rectangle {
    id: mascara
    anchors.fill: parent
    radius: a.redondo ? width / 2 : 0
    visible: false
    layer.enabled: true
  }
  MultiEffect {
    anchors.fill: parent
    visible: a.temFoto
    source: foto
    maskEnabled: true
    maskSource: mascara
    maskThresholdMin: 0.5
    maskSpreadAtMin: 1.0
  }
}
