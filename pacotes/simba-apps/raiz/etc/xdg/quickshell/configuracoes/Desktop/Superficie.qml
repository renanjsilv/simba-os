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
  Connections { target: Hyprland; function onRawEvent(ev) { if (ev.name === "monitoradded" || ev.name === "monitorremoved" || ev.name === "configreloaded") Hyprland.refreshMonitors() } }

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
      if (p && p.c !== undefined && p.c < colunas && p.r < linhas && !ocupado[p.c + "," + p.r]) {
        ocupado[p.c + "," + p.r] = true
        res[it.caminho] = { x: x0 + p.c * cel.w, y: y0 + p.r * cel.h }
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
  // Drop an icon: snap to the nearest free cell (or keep the free position).
  function soltarIcone(it, px, py) {
    if (area.automatico) return
    if (!area.grade) { area.guardarPosicao(it.nome, { x: Math.round(px), y: Math.round(py) }); return }
    var alvo = celulaEm(px, py)
    var livres = {}
    for (var k in lugares) {
      if (k === it.caminho) continue
      var l = lugares[k]
      livres[Math.round((l.x - x0) / cel.w) + "," + Math.round((l.y - y0) / cel.h)] = true
    }
    var melhor = null
    for (var raio = 0; raio < Math.max(colunas, linhas) && !melhor; raio++) {
      for (var dc = -raio; dc <= raio; dc++) for (var dr = -raio; dr <= raio; dr++) {
        var c = alvo.c + dc, r = alvo.r + dr
        if (c < 0 || r < 0 || c >= colunas || r >= linhas || livres[c + "," + r]) continue
        var d = Math.hypot(dc, dr)
        if (!melhor || d < melhor.d) melhor = { c: c, r: r, d: d }
      }
    }
    if (melhor) area.guardarPosicao(it.nome, { c: melhor.c, r: melhor.r })
  }

  Item {
    id: raiz
    anchors.fill: parent
    focus: true

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
