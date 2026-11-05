import QtQuick
import QtQuick.Controls.Basic as C
import Quickshell
import Quickshell.Wayland
import qs.Comum

// Inline rename (F2 / "Renomear"): a field drawn exactly over the icon label on
// a transparent overlay that takes the keyboard only while renaming. Enter or a
// click elsewhere commits, Esc cancels. The extension is kept out of the
// initial selection, like Windows.
Scope {
  id: r
  property var area: null
  property var item: null
  property bool aberto: false

  function abrir(it) { item = it; aberto = true }
  function concluir(salvar, texto) {
    if (!aberto) return
    aberto = false
    var it = item
    if (salvar && it && texto.trim() && texto.trim() !== it.nome)
      area.run(["renomear", it.caminho, texto.trim()], "", function(res) { if (res && res.caminho) area.selecao = [res.caminho] })
  }

  Variants {
    model: r.aberto && r.item ? Quickshell.screens.filter(function(s) {
      var g = r.area.geometria[r.item.caminho]
      return g ? s.name === g.tela : s === Quickshell.screens[0]
    }) : []
    delegate: PanelWindow {
      id: w
      required property var modelData
      screen: modelData
      anchors { top: true; bottom: true; left: true; right: true }
      exclusionMode: ExclusionMode.Ignore
      color: "transparent"
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.namespace: "configuracoes-renomear"
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

      readonly property var g: r.area.geometria[r.item.caminho] || { x: w.width / 2 - 60, y: w.height / 2 - 40, w: 120, h: 100 }

      MouseArea { anchors.fill: parent; onPressed: r.concluir(true, campo.text) }

      C.TextField {
        id: campo
        x: Math.max(4, Math.min(w.g.x + w.g.w / 2 - width / 2, w.width - width - 4))
        y: w.g.y + r.area.celula.i + 8
        width: Math.max(w.g.w + 40, Math.min(320, contentWidth + 28))
        height: 30
        text: r.item.nome
        color: Tema.texto
        selectionColor: Tema.alfa(Tema.realce, 0.45)
        selectedTextColor: Tema.texto
        font.family: Tema.fonte
        font.pixelSize: 12
        horizontalAlignment: TextInput.AlignHCenter
        background: Rectangle {
          radius: Math.max(4, Tema.raioPequeno)
          color: Tema.superficieAlta
          border.width: 1.5
          border.color: Tema.realce
          Sombra { alvo: parent; deslocamento: 4; intensidade: 0.7 }
        }
        Component.onCompleted: {
          forceActiveFocus()
          var n = r.item.nome
          var p = r.item.pasta ? -1 : n.lastIndexOf(".")
          select(0, p > 0 ? p : n.length)
        }
        Keys.onReturnPressed: r.concluir(true, text)
        Keys.onEnterPressed: r.concluir(true, text)
        Keys.onEscapePressed: r.concluir(false, "")
      }
    }
  }
}
