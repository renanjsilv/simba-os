import QtQuick
import qs.Comum

// Little drawing of a display mode: notebook on the left, monitor on the right.
Item {
  id: il
  property string modo: "estender"
  property bool destaque: false
  property bool desativado: false
  implicitWidth: 150
  implicitHeight: 84

  readonly property bool notebookLigado: modo !== "segunda"
  readonly property bool monitorLigado: modo !== "notebook"
  readonly property color corLigada: destaque ? Tema.realce : Tema.texto2
  readonly property color corTexto: destaque ? Tema.sobreRealce : Tema.janela

  // continuous band for "estender"
  property real fase: 0
  NumberAnimation on fase { from: 0; to: 1; duration: 2600; loops: Animation.Infinite; running: il.destaque && il.modo === "estender" && Tema.animacoes }

  // notebook
  Item {
    id: nb
    x: 4; y: 22
    width: 60; height: 52
    Rectangle {
      id: telaNb
      x: 6; width: 48; height: 32
      radius: Math.min(Tema.raioPequeno, 4)
      color: il.notebookLigado ? il.corLigada : "transparent"
      border.width: il.notebookLigado ? 0 : 1.5
      border.color: Tema.linhaForte
      Behavior on color { ColorAnimation { duration: Tema.medio } }
      Texto {
        anchors.centerIn: parent
        visible: il.notebookLigado
        text: il.modo === "duplicar" ? "1|2" : "1"
        color: il.corTexto
        font.pixelSize: 12
        font.weight: Font.Bold
      }
      Rectangle {
        visible: !il.notebookLigado
        anchors.centerIn: parent
        width: 2; height: parent.height * 0.9; rotation: 40
        color: Tema.linhaForte
      }
    }
    Rectangle { x: 0; y: 34; width: 60; height: 5; radius: 2; color: il.notebookLigado ? il.corLigada : Tema.linhaForte; opacity: 0.85 }
  }

  // monitor
  Item {
    id: mon
    x: 72; y: 4
    width: 74; height: 72
    Rectangle {
      id: telaMon
      width: 74; height: 48
      radius: Math.min(Tema.raioPequeno, 4)
      color: il.monitorLigado ? il.corLigada : "transparent"
      border.width: il.monitorLigado ? 0 : 1.5
      border.color: Tema.linhaForte
      Behavior on color { ColorAnimation { duration: Tema.medio } }
      Texto {
        anchors.centerIn: parent
        visible: il.monitorLigado
        text: il.modo === "duplicar" ? "1|2" : (il.modo === "segunda" ? "1" : "2")
        color: il.corTexto
        font.pixelSize: 14
        font.weight: Font.Bold
      }
      Rectangle {
        visible: !il.monitorLigado
        anchors.centerIn: parent
        width: 2; height: parent.height * 0.9; rotation: 50
        color: Tema.linhaForte
      }
    }
    Rectangle { x: 33; y: 48; width: 8; height: 12; color: il.monitorLigado ? il.corLigada : Tema.linhaForte; opacity: 0.85 }
    Rectangle { x: 22; y: 60; width: 30; height: 4; radius: 2; color: il.monitorLigado ? il.corLigada : Tema.linhaForte; opacity: 0.85 }
  }

  // extend: a light streak travelling across both screens
  Rectangle {
    visible: il.modo === "estender" && il.destaque
    x: nb.x + telaNb.x + (mon.x + telaMon.width - nb.x - telaNb.x) * il.fase - 10
    y: 26
    width: 20; height: 3; radius: 1.5
    color: il.corTexto
    opacity: 0.55
  }
  // duplicate: mirror arrows
  Texto {
    visible: il.modo === "duplicar"
    x: 58; y: 26
    text: "⇄"
    color: il.destaque ? Tema.realce : Tema.texto3
    font.pixelSize: 13
  }
}
