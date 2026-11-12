import QtQuick
import Quickshell
import Quickshell.Wayland
import Quickshell.Hyprland
import qs.Comum

// One screen's desktop surface (WlrLayer.Bottom, full screen). Keyboard focus is
// on demand: Hyprland hands it over only when the desktop is clicked (a click on
// a window takes it back), so Delete & co. act on the selected icons like on
// Windows and never steal keys from apps.
PanelWindow {
  id: sup
  property var area: null
  property bool mostrarIcones: false
  readonly property bool sobCursor: sobre.hovered
  readonly property string nome: screen ? screen.name : ""

  anchors { top: true; bottom: true; left: true; right: true }
  exclusionMode: ExclusionMode.Ignore
  color: "transparent"
  // `area.elevada` lifts the desktop above windows for a moment (IPC "espiar",
  // used to preview/screenshot the icons without minimizing anything).
  WlrLayershell.layer: area.elevada ? WlrLayer.Top : WlrLayer.Bottom
  WlrLayershell.namespace: "configuracoes-area"
  WlrLayershell.keyboardFocus: WlrKeyboardFocus.OnDemand

  // Space taken by the bar (Hyprland "reserved" = left, top, right, bottom).
  readonly property var monitorH: Hyprland.monitorFor(screen)
  readonly property var reservado: {
    var r = monitorH && monitorH.lastIpcObject ? monitorH.lastIpcObject.reserved : null
    return r && r.length === 4 ? r : [0, 26, 0, 0]
  }
  // The reserved area changes when the bar restarts, moves or is resized, which Hyprland
  // only signals as layer open/close: refresh on those too (debounced), plus a slow
  // backstop. A stale value kept icons from being placed where the bar used to be.
  Connections {
    target: Hyprland
    function onRawEvent(ev) {
      if (["monitoradded", "monitoraddedv2", "monitorremoved", "monitorremovedv2", "configreloaded", "openlayer", "closelayer"].indexOf(ev.name) >= 0)
        releReserva.restart()
    }
  }
  Timer { id: releReserva; interval: 400; onTriggered: Hyprland.refreshMonitors() }
  Timer { interval: 20000; running: true; repeat: true; onTriggered: Hyprland.refreshMonitors() }
  Component.onCompleted: Hyprland.refreshMonitors()

  readonly property real x0: reservado[0] + 10
  readonly property real y0: reservado[1] + 10
  readonly property var cel: area.celula
  readonly property int linhas: Math.max(1, Math.floor((height - y0 - reservado[3] - 10) / cel.h))
  readonly property int colunas: Math.max(1, Math.floor((width - x0 - reservado[2] - 10) / cel.w))

  // path -> {x, y} for every icon on this surface
  readonly property var lugares: {
    var res = {}
    if (!mostrarIcones) return res
    var pos = area.automatico ? {} : area.posicoes()
    var ocupado = {}
    var resto = []
    area.itens.forEach(function(it) {
      var p = pos[it.nome]
      // a cell beyond the grid (bigger icons, smaller screen) sticks to the nearest edge
      var pc = p && p.c !== undefined ? Math.min(p.c, colunas - 1) : -1
      var pr = p && p.c !== undefined ? Math.min(p.r, linhas - 1) : -1
      if (pc >= 0 && !ocupado[pc + "," + pr]) {
        ocupado[pc + "," + pr] = true
        res[it.caminho] = { x: x0 + pc * cel.w, y: y0 + pr * cel.h }
      } else if (p && p.x !== undefined && !area.grade && p.x < width - 20 && p.y < height - 20) {
        res[it.caminho] = { x: p.x, y: p.y }
      } else resto.push(it)
    })
    var k = 0
    resto.forEach(function(it) {
      while (ocupado[Math.floor(k / linhas) + "," + (k % linhas)]) k++
      var c = Math.floor(k / linhas), r = k % linhas
      ocupado[c + "," + r] = true
      res[it.caminho] = { x: x0 + c * cel.w, y: y0 + r * cel.h }
      k++
    })
    return res
  }

  function celulaEm(px, py) {
    var c = Math.max(0, Math.min(colunas - 1, Math.round((px - x0) / cel.w)))
    var r = Math.max(0, Math.min(linhas - 1, Math.round((py - y0) / cel.h)))
    return { c: c, r: r }
  }
  // Solta o ícone arrastado e, se ele fazia parte da seleção, todos os selecionados juntos
  // (mesmo deslocamento; cada um na célula livre mais perto, sem dois na mesma).
  function celulaDe(l) { return { c: Math.round((l.x - x0) / cel.w), r: Math.round((l.y - y0) / cel.h) } }
  function livreMaisPerto(alvo, ocupadas) {
    var melhor = null
    for (var raio = 0; raio < Math.max(colunas, linhas) && !melhor; raio++) {
      for (var dc = -raio; dc <= raio; dc++) for (var dr = -raio; dr <= raio; dr++) {
        var c = alvo.c + dc, r = alvo.r + dr
        if (c < 0 || r < 0 || c >= colunas || r >= linhas || ocupadas[c + "," + r]) continue
        var d = Math.hypot(dc, dr)
        if (!melhor || d < melhor.d) melhor = { c: c, r: r, d: d }
      }
    }
    return melhor
  }
  function soltarIcone(it, px, py) {
    // largado em cima da Lixeira: vai para a lixeira (a seleção inteira, como no Windows)
    var lx = lugares["trash:///"]
    if (lx && !area.ehLixeira(it.caminho) && Math.abs(px - lx.x) < cel.w / 2 && Math.abs(py - lx.y) < cel.h / 2) {
      area.largarNaLixeira()
      return
    }
    if (area.automatico) return
    var sel = area.selecao.indexOf(it.caminho) >= 0 ? area.selecao : [it.caminho]
    var l0 = lugares[it.caminho] || { x: px, y: py }
    var dx = px - l0.x, dy = py - l0.y
    var grupo = area.itens.filter(function(i) { return sel.indexOf(i.caminho) >= 0 })
    grupo.sort(function(a, b) { return (a.caminho === it.caminho ? 0 : 1) - (b.caminho === it.caminho ? 0 : 1) })
    var novas = {}
    if (!area.grade) {
      grupo.forEach(function(i) {
        var l = lugares[i.caminho]
        if (l) novas[i.nome] = { x: Math.round(l.x + dx), y: Math.round(l.y + dy) }
      })
    } else {
      var ocupadas = {}
      for (var k in lugares) {
        if (sel.indexOf(k) >= 0) continue
        var ck = celulaDe(lugares[k])
        ocupadas[ck.c + "," + ck.r] = true
      }
      grupo.forEach(function(i) {
        var l = lugares[i.caminho]
        if (!l) return
        var m = livreMaisPerto(celulaEm(l.x + dx, l.y + dy), ocupadas)
        if (!m) return
        ocupadas[m.c + "," + m.r] = true
        novas[i.nome] = { c: m.c, r: m.r }
      })
    }
    area.guardarPosicoes(novas)
  }

  Item {
    id: raiz
    anchors.fill: parent
    focus: true

    // Pointer over this desktop (icons included; a window on top takes it away).
    // Ctrl + scroll resizes the icons only while this is true (see AreaDeTrabalho.rodaCtrl).
    HoverHandler { id: sobre }

    // Delete = lixeira · F2 = renomear · Enter = abrir · Ctrl+A/C/X/V · Esc = limpar seleção
    Keys.onPressed: function(e) {
      var a = sup.area, ctrl = e.modifiers & Qt.ControlModifier
      if (e.key === Qt.Key_Delete) a.excluir()
      else if (e.key === Qt.Key_F2 && a.selecao.length === 1) a.renomear(a.selecao[0])
      else if ((e.key === Qt.Key_Return || e.key === Qt.Key_Enter) && a.selecao.length) a.selecao.forEach(function(c) { a.abrirItem(c) })
      else if (e.key === Qt.Key_Escape) a.selecao = []
      else if (ctrl && e.key === Qt.Key_A) a.selecao = sup.mostrarIcones ? a.itens.map(function(i) { return i.caminho }) : []
      else if (ctrl && e.key === Qt.Key_C) a.copiar(false)
      else if (ctrl && e.key === Qt.Key_X) a.copiar(true)
      else if (ctrl && e.key === Qt.Key_V) a.colar(false)
      else if (e.key === Qt.Key_F5) a.atualizar()
      else return
      e.accepted = true
    }

    // ── empty desktop: right click menu, rubber band selection ────────────
    MouseArea {
      id: fundo
      anchors.fill: parent
      acceptedButtons: Qt.LeftButton | Qt.RightButton
      property point inicio
      property bool laco: false
      onPressed: function(m) {
        if (m.button === Qt.RightButton) return
        inicio = Qt.point(m.x, m.y)
        laco = false
        if (!(m.modifiers & Qt.ControlModifier)) sup.area.selecao = []
      }
      onPositionChanged: function(m) {
        if (!(m.buttons & Qt.LeftButton) || !sup.mostrarIcones) return
        if (!laco && Math.hypot(m.x - inicio.x, m.y - inicio.y) > 6) laco = true
        if (!laco) return
        var x1 = Math.min(inicio.x, m.x), y1 = Math.min(inicio.y, m.y)
        var x2 = Math.max(inicio.x, m.x), y2 = Math.max(inicio.y, m.y)
        banda.x = x1; banda.y = y1; banda.width = x2 - x1; banda.height = y2 - y1
        var sel = []
        for (var k in sup.lugares) {
          var l = sup.lugares[k]
          var lx2 = l.x + sup.cel.w - 6, ly2 = l.y + sup.cel.h - 6
          if (l.x + 6 < x2 && lx2 > x1 && l.y + 4 < y2 && ly2 > y1) sel.push(k)
        }
        sup.area.selecao = sel
      }
      onReleased: function(m) { laco = false }
      onClicked: function(m) {
        if (m.button === Qt.RightButton) sup.area.abrirMenuEm(sup.nome, m.x, m.y)
      }
    }

    Rectangle {
      id: banda
      visible: fundo.laco
      color: Tema.alfa(Tema.realce, 0.18)
      border.width: 1
      border.color: Tema.alfa(Tema.realce, 0.75)
      radius: Math.min(Tema.raioPequeno, 4)
    }

    // ── drops from the file manager ───────────────────────────────────────
    DropArea {
      anchors.fill: parent
      keys: ["text/uri-list"]
      onDropped: function(d) {
        if (d.hasUrls) {
          sup.area.soltar(d.urls.map(function(u) { return u.toString() }))
          d.acceptProposedAction()
        }
      }
    }

    // ── icons ─────────────────────────────────────────────────────────────
    Repeater {
      model: sup.mostrarIcones ? sup.area.itens : []
      delegate: Icone {
        required property var modelData
        required property int index
        item: modelData
        ordem: index
        superficie: sup
        lugar: sup.lugares[modelData.caminho] || { x: sup.x0, y: sup.y0 }
      }
    }
  }
}
