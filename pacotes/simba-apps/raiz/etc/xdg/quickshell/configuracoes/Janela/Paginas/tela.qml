import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.Comum
import qs.Janela
import qs.Projetar

Pagina {
  id: pg
  titulo: I18n.t("Tela")
  subtitulo: I18n.t("Monitores, resolução, escala, brilho e luz noturna. Mudanças de tela pedem confirmação e se desfazem sozinhas em 15 s.")

  property var estado: null
  property var rascunho: ({})       // name -> { modo, escala, giro, x, y }
  property string sel: ""
  property bool aplicando: false
  property int brilho: -1
  property var luz: ({ ativo: false, temperatura: null })
  property bool hyprsunsetAgenda: Preferencias.obter("luzNoturna.agendar", false)

  readonly property var ativos: estado ? estado.monitores.filter(function(m) { return !m.disabled }) : []
  readonly property var mon: {
    if (!estado) return null
    for (var i = 0; i < estado.monitores.length; i++) if (estado.monitores[i].name === sel) return estado.monitores[i]
    return ativos.length ? ativos[0] : null
  }
  readonly property var ordem: ativos.slice().sort(function(a, b) { return a.x - b.x || a.y - b.y }).map(function(m) { return m.name })
  function numero(nome) { return ordem.indexOf(nome) + 1 }

  function modoTexto(m) { return m.width + "x" + m.height + "@" + Number(m.refreshRate).toFixed(2) }
  function inicial(m) { return { modo: modoTexto(m), escala: Number(m.scale), giro: m.transform, x: m.x, y: m.y } }

  function carregar() {
    Sistema.json([Sistema.tela, "estado"], function(v) {
      if (!v) return
      pg.estado = v
      var r = {}
      v.monitores.forEach(function(m) { r[m.name] = pg.inicial(m) })
      pg.rascunho = r
      if (!pg.sel || !v.monitores.some(function(m) { return m.name === pg.sel })) {
        var f = v.monitores.filter(function(m) { return m.focused && !m.disabled })[0] || v.monitores.filter(function(m) { return !m.disabled })[0]
        pg.sel = f ? f.name : ""
      }
    })
    Sistema.sh("brightnessctl -m -c backlight 2>/dev/null | head -1 | cut -d, -f4 | tr -d '%'", function(o) { var n = parseInt(o); pg.brilho = isNaN(n) ? -1 : n })
    Sistema.json([Sistema.ajudante, "luz"], function(v) { if (v) pg.luz = v })
  }
  Component.onCompleted: { carregar(); carregarConhecidas() }

  readonly property bool alterado: {
    if (!estado) return false
    for (var i = 0; i < estado.monitores.length; i++) {
      var m = estado.monitores[i]
      if (m.disabled) continue
      var a = inicial(m), b = rascunho[m.name]
      if (!b) continue
      if (a.modo !== b.modo || Math.abs(a.escala - b.escala) > 0.001 || a.giro !== b.giro || a.x !== b.x || a.y !== b.y) return true
    }
    return false
  }

  function mudar(nome, campo, valor) {
    var r = JSON.parse(JSON.stringify(rascunho))
    r[nome][campo] = valor
    rascunho = r
  }

  // logical size of a monitor under its draft mode/scale/rotation
  function tamanhoLogico(nome) {
    var d = rascunho[nome]
    if (!d) return { w: 0, h: 0 }
    var p = d.modo.split("@")[0].split("x")
    var w = Number(p[0]) / d.escala, h = Number(p[1]) / d.escala
    if (d.giro % 2 === 1) { var t = w; w = h; h = t }
    return { w: Math.round(w), h: Math.round(h) }
  }

  // Snap `nome` next to the closest other monitor (left/right/above/below),
  // keeping overlap on the other axis; then shift everything to start at 0,0.
  function encaixar(nome, x, y) {
    var r = JSON.parse(JSON.stringify(rascunho))
    var eu = tamanhoLogico(nome)
    var melhor = null
    ativos.forEach(function(o) {
      if (o.name === nome) return
      var t = tamanhoLogico(o.name), ox = r[o.name].x, oy = r[o.name].y
      function lim(v, a, b) { return Math.max(a, Math.min(b, v)) }
      var cand = [
        { x: ox + t.w, y: lim(y, oy - eu.h + 40, oy + t.h - 40) },
        { x: ox - eu.w, y: lim(y, oy - eu.h + 40, oy + t.h - 40) },
        { x: lim(x, ox - eu.w + 40, ox + t.w - 40), y: oy - eu.h },
        { x: lim(x, ox - eu.w + 40, ox + t.w - 40), y: oy + t.h }
      ]
      cand.forEach(function(c) {
        // edge alignment magnet
        if (Math.abs(c.y - oy) < 60) c.y = oy
        if (Math.abs(c.y + eu.h - (oy + t.h)) < 60) c.y = oy + t.h - eu.h
        if (Math.abs(c.x - ox) < 60) c.x = ox
        var d = Math.hypot(c.x - x, c.y - y)
        if (!melhor || d < melhor.d) melhor = { x: Math.round(c.x), y: Math.round(c.y), d: d }
      })
    })
    if (melhor) { r[nome].x = melhor.x; r[nome].y = melhor.y }
    var mx = Infinity, my = Infinity
    ativos.forEach(function(m) { mx = Math.min(mx, r[m.name].x); my = Math.min(my, r[m.name].y) })
    ativos.forEach(function(m) { r[m.name].x -= mx; r[m.name].y -= my })
    rascunho = r
  }

  function blocoMonitores() {
    var linhas = ["-- Telas organizadas no app Configurações › Tela"]
    ativos.forEach(function(m) {
      var d = rascunho[m.name]
      linhas.push(I18n.t('hl.monitor({ output = "') + m.name + I18n.t('", mode = "') + d.modo + I18n.t('", position = "') + d.x + "x" + d.y +
                  I18n.t('", scale = ') + Number(d.escala.toFixed(3)) + (d.giro ? I18n.t(", transform = ") + d.giro : "") + " })")
    })
    return linhas.join("\n")
  }

  function aplicar() {
    aplicando = true
    var bloco = blocoMonitores()
    var arquivo = Sistema.home + "/.config/hypr/monitors.lua"
    Sistema.rodar([Sistema.tela, "snapshot"], function() {
      Sistema.rodar([Sistema.bloco, arquivo], function(o, code) {
        Sistema.sh("hyprctl reload >/dev/null; " + Sistema.q(Sistema.tela) + " pendente 15", function() {
          pg.aplicando = false
          pg.carregar()
          if (Navegacao.confirmacao) Navegacao.confirmacao.iniciar(I18n.t("Manter estas configurações de exibição?"), function() { pg.carregar() })
        })
      }, bloco)
    })
  }

  function aplicarModo(modo) {
    if (!estado || modo === (estado.modo === "unico" ? "notebook" : estado.modo)) return
    aplicando = true
    Sistema.rodar([Sistema.tela, "modo", modo, "15"], function(o, code, err) {
      pg.aplicando = false
      pg.carregar()
      if (code !== 0) { Navegacao.confirmar(err.trim() || I18n.t("Não foi possível mudar o modo"), Icones.alert); return }
      if (Navegacao.confirmacao) Navegacao.confirmacao.iniciar(I18n.t("Manter este modo de exibição?"), function() { pg.carregar() })
    })
  }

  // ── arrangement ──────────────────────────────────────────────────────────
  Ancora { chave: "organizacao" }
  Rectangle {
    id: palco
    Layout.fillWidth: true
    Layout.preferredHeight: 270
    radius: Tema.raioGrande
    color: Tema.superficie
    border.width: 1
    border.color: Tema.linha
    clip: true

    // dotted grid
    Canvas {
      anchors.fill: parent
      opacity: 0.5
      property color c: Tema.linhaForte
      onCChanged: requestPaint()
      onWidthChanged: requestPaint()
      onPaint: {
        var ctx = getContext("2d"); ctx.reset(); ctx.fillStyle = c
        for (var x = 12; x < width; x += 18) for (var y = 12; y < height; y += 18) ctx.fillRect(x, y, 1.2, 1.2)
      }
    }

    readonly property var caixa: {
      var minx = Infinity, miny = Infinity, maxx = -Infinity, maxy = -Infinity
      pg.ativos.forEach(function(m) {
        var d = pg.rascunho[m.name]; if (!d) return
        var t = pg.tamanhoLogico(m.name)
        minx = Math.min(minx, d.x); miny = Math.min(miny, d.y)
        maxx = Math.max(maxx, d.x + t.w); maxy = Math.max(maxy, d.y + t.h)
      })
      if (minx === Infinity) return { x: 0, y: 0, w: 1, h: 1 }
      return { x: minx, y: miny, w: maxx - minx, h: maxy - miny }
    }
    readonly property real fator: Math.min((width - 120) / Math.max(1, caixa.w + 600), (height - 70) / Math.max(1, caixa.h + 300))
    readonly property real ox: (width - caixa.w * fator) / 2 - caixa.x * fator
    readonly property real oy: (height - 30 - caixa.h * fator) / 2 - caixa.y * fator

    Repeater {
      model: pg.ativos
      delegate: Rectangle {
        id: caixaMon
        required property var modelData
        readonly property var d: pg.rascunho[modelData.name] || { x: 0, y: 0 }
        readonly property var t: pg.tamanhoLogico(modelData.name)
        readonly property bool selecionado: pg.sel === modelData.name
        readonly property bool espelho: modelData.mirrorOf && modelData.mirrorOf !== "none"
        x: arrasto.drag.active ? x : palco.ox + d.x * palco.fator
        y: arrasto.drag.active ? y : palco.oy + d.y * palco.fator
        width: t.w * palco.fator
        height: t.h * palco.fator
        z: arrasto.drag.active ? 10 : (selecionado ? 2 : 1)
        radius: Tema.raio
        color: selecionado ? Tema.realce : Tema.superficieMax
        border.width: selecionado ? 0 : 1
        border.color: Tema.linhaForte
        Behavior on x { enabled: !arrasto.drag.active; NumberAnimation { duration: Tema.lento; easing.type: Easing.OutBack; easing.overshoot: 0.8 } }
        Behavior on y { enabled: !arrasto.drag.active; NumberAnimation { duration: Tema.lento; easing.type: Easing.OutBack; easing.overshoot: 0.8 } }
        Behavior on width { NumberAnimation { duration: Tema.medio } }
        Behavior on height { NumberAnimation { duration: Tema.medio } }
        Behavior on color { ColorAnimation { duration: Tema.medio } }
        Sombra { alvo: caixaMon; intensidade: arrasto.drag.active ? 1 : 0.4; deslocamento: arrasto.drag.active ? 14 : 4 }
        scale: arrasto.drag.active ? 1.03 : 1
        Behavior on scale { NumberAnimation { duration: Tema.rapido } }

        Column {
          anchors.centerIn: parent
          spacing: 2
          Texto {
            anchors.horizontalCenter: parent.horizontalCenter
            text: caixaMon.espelho ? "1|2" : String(pg.numero(caixaMon.modelData.name))
            font.pixelSize: Math.max(18, Math.min(40, caixaMon.height * 0.35))
            font.weight: Font.Bold
            color: caixaMon.selecionado ? Tema.sobreRealce : Tema.texto
          }
          Texto {
            anchors.horizontalCenter: parent.horizontalCenter
            text: caixaMon.modelData.name
            font.pixelSize: Tema.tLegenda
            color: caixaMon.selecionado ? Tema.alfa(Tema.sobreRealce, 0.8) : Tema.texto2
          }
        }
        MouseArea {
          id: arrasto
          anchors.fill: parent
          cursorShape: pg.ativos.length > 1 ? (drag.active ? Qt.ClosedHandCursor : Qt.OpenHandCursor) : Qt.PointingHandCursor
          drag.target: pg.ativos.length > 1 ? caixaMon : null
          drag.threshold: 4
          onPressed: pg.sel = caixaMon.modelData.name
          onReleased: {
            if (!drag.active && Math.abs(caixaMon.x - (palco.ox + caixaMon.d.x * palco.fator)) < 2) return
            var lx = (caixaMon.x - palco.ox) / palco.fator
            var ly = (caixaMon.y - palco.oy) / palco.fator
            pg.encaixar(caixaMon.modelData.name, lx, ly)
          }
        }
      }
    }

    RowLayout {
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.bottom: parent.bottom
      anchors.margins: 12
      spacing: 8
      Texto {
        text: pg.ativos.length > 1 ? I18n.t("Arraste as telas para combinar com a posição real delas.") : I18n.t("Uma tela ativa.")
        color: Tema.texto3
        font.pixelSize: Tema.tLegenda + 1
        Layout.fillWidth: true
      }
      Botao { texto: I18n.t("Identificar"); glifo: Icones.monitorScreenshot; compacto: true; onClicado: if (Navegacao.identificar) Navegacao.identificar.mostrar(pg.ordem) }
      Botao { visible: pg.alterado; texto: I18n.t("Descartar"); compacto: true; onClicado: pg.carregar() }
      Botao { visible: pg.alterado; texto: I18n.t("Aplicar"); tipo: "primario"; compacto: true; ocupado: pg.aplicando; onClicado: pg.aplicar() }
    }
  }

  // ── projection mode ──────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Modo de projeção"); detalhe: I18n.t("O mesmo do atalho Super+P.") }
  Ancora { chave: "modoProjecao" }
  RowLayout {
    Layout.fillWidth: true
    spacing: 10
    Repeater {
      model: [
        { id: "notebook", titulo: I18n.t("Somente notebook") },
        { id: "duplicar", titulo: I18n.t("Duplicar") },
        { id: "estender", titulo: I18n.t("Estender") },
        { id: "segunda", titulo: I18n.t("Somente segunda") }
      ]
      delegate: Rectangle {
        id: cm
        required property var modelData
        readonly property string atual: pg.estado ? (pg.estado.modo === "unico" ? "notebook" : pg.estado.modo) : ""
        readonly property bool ativo: atual === modelData.id
        readonly property bool ok: pg.estado && (pg.estado.externas.length > 0 || modelData.id === "notebook")
        Layout.fillWidth: true
        Layout.preferredHeight: 132
        radius: Tema.raioGrande
        color: ativo ? Tema.superficieAlta : (mm.containsMouse && ok ? Tema.superficieAlta : Tema.superficie)
        border.width: ativo ? 2 : 1
        border.color: ativo ? Tema.realce : Tema.linha
        opacity: ok ? 1 : 0.4
        Behavior on color { ColorAnimation { duration: Tema.rapido } }
        ColumnLayout {
          anchors.fill: parent
          anchors.margins: 10
          spacing: 4
          Item { Layout.fillWidth: true; Layout.preferredHeight: 86; Ilustracao { anchors.centerIn: parent; modo: cm.modelData.id; destaque: cm.ativo; scale: 0.9 } }
          Texto { text: cm.modelData.titulo; font.weight: cm.ativo ? Font.DemiBold : Font.Normal; horizontalAlignment: Text.AlignHCenter; Layout.fillWidth: true; elide: Text.ElideRight }
        }
        MouseArea { id: mm; anchors.fill: parent; hoverEnabled: true; enabled: cm.ok && !cm.ativo && !pg.aplicando; cursorShape: Qt.PointingHandCursor; onClicked: pg.aplicarModo(cm.modelData.id) }
      }
    }
  }
  Texto {
    visible: pg.estado !== null && pg.estado.externas.length === 0
    text: I18n.t("Só a tela do notebook está conectada agora. Conecte um monitor para duplicar ou estender.")
    color: Tema.texto3
    font.pixelSize: Tema.tLegenda + 1
  }

  // ── remembered screens ───────────────────────────────────────────────────
  property var conhecidas: ({})
  function carregarConhecidas() { Sistema.json([Sistema.tela, "memoria"], function(v) { if (v) pg.conhecidas = v }) }
  Timer { interval: 4000; running: true; repeat: true; onTriggered: pg.carregarConhecidas() }
  readonly property var nomesModo: ({ notebook: I18n.t("Somente notebook"), duplicar: I18n.t("Duplicar"), estender: I18n.t("Estender"), segunda: I18n.t("Somente segunda tela") })
  function quando(iso) {
    var d = new Date(iso)
    if (isNaN(d)) return ""
    var s = (Date.now() - d.getTime()) / 1000
    if (s < 120) return "agora"
    if (s < 3600) return I18n.t("há ") + Math.round(s / 60) + " min"
    if (s < 86400) return I18n.t("há ") + Math.round(s / 3600) + " h"
    return d.toLocaleString(Qt.locale(), I18n.t("d 'de' MMM, HH:mm"))
  }

  Secao { titulo: I18n.t("Telas conhecidas"); detalhe: I18n.t("Cada monitor lembra o modo que você confirmou para ele e volta a usá-lo sozinho quando é conectado.") }
  Cartao {
    Linha {
      chave: "perguntarTela"; glifo: Icones.monitorMultiple
      titulo: I18n.t("Perguntar ao conectar uma tela nova")
      descricao: Preferencias.obter("monitores.perguntar", true) ? I18n.t("Abre o Projetar (Super+P) para você escolher") : I18n.t("Telas novas só estendem a área de trabalho")
      Interruptor { ligado: Preferencias.obter("monitores.perguntar", true); onAlternado: function(x) { Preferencias.definir("monitores.perguntar", x) } }
    }
    Repeater {
      model: Object.keys(pg.conhecidas).sort(function(a, b) { return String(pg.conhecidas[b].visto).localeCompare(String(pg.conhecidas[a].visto)) })
      delegate: Linha {
        required property string modelData
        readonly property var t: pg.conhecidas[modelData] || {}
        chave: ""
        glifo: Icones.monitor
        titulo: t.nome || modelData
        descricao: (pg.nomesModo[t.modo] || t.modo) + (t.video ? " · " + String(t.video).split("@")[0].replace("x", " × ") : "") + I18n.t(" · vista ") + pg.quando(t.visto) + (t.saida ? " em " + t.saida : "")
        Botao {
          texto: I18n.t("Esquecer"); compacto: true; tipo: "fantasma"; glifo: Icones.lixeira
          onClicado: Sistema.rodar([Sistema.tela, "esquecer", modelData], function() { pg.carregarConhecidas(); Navegacao.confirmar(I18n.t("Tela esquecida"), Icones.monitor) })
        }
      }
    }
  }
  Texto {
    visible: Object.keys(pg.conhecidas).length === 0
    text: I18n.t("Nenhuma tela lembrada ainda. Conecte um monitor e confirme um modo.")
    color: Tema.texto3
    font.pixelSize: Tema.tLegenda + 1
  }

  // ── selected monitor ─────────────────────────────────────────────────────
  Secao {
    titulo: pg.mon ? I18n.t("Tela ") + pg.numero(pg.mon.name) + " · " + (pg.mon.description || pg.mon.name) : I18n.t("Tela")
    detalhe: pg.mon ? pg.mon.name + (pg.mon.name.indexOf("eDP") === 0 ? I18n.t(" · tela do notebook") : I18n.t(" · monitor externo")) : ""
  }
  Row {
    visible: pg.ativos.length > 1
    spacing: 8
    Repeater {
      model: pg.ativos
      delegate: Botao {
        required property var modelData
        texto: pg.numero(modelData.name) + " · " + modelData.name
        compacto: true
        tipo: pg.sel === modelData.name ? "primario" : "normal"
        onClicado: pg.sel = modelData.name
      }
    }
  }
  Cartao {
    visible: pg.mon !== null && !pg.mon.disabled
    Linha {
      chave: "resolucao"; glifo: Icones.aspectRatio
      titulo: I18n.t("Resolução")
      descricao: pg.mon ? I18n.t("Recomendada: ") + (pg.mon.availableModes[0] || "").split("@")[0] : ""
      Selecao {
        width: 200
        readonly property var resolucoes: {
          if (!pg.mon) return []
          var vistos = {}, out = []
          pg.mon.availableModes.forEach(function(m, i) {
            var r = m.split("@")[0]
            if (vistos[r]) return
            vistos[r] = true
            var p = r.split("x")
            out.push({ valor: r, rotulo: p[0] + " × " + p[1], detalhe: i === 0 ? I18n.t("Recomendada") : "" })
          })
          return out
        }
        opcoes: resolucoes
        atual: pg.mon && pg.rascunho[pg.mon.name] ? pg.rascunho[pg.mon.name].modo.split("@")[0] : ""
        onEscolhido: function(v) {
          var taxas = pg.mon.availableModes.filter(function(m) { return m.split("@")[0] === v })
          var modo = taxas[0].replace("Hz", "")
          pg.mudar(pg.mon.name, "modo", modo)
        }
      }
    }
    Linha {
      chave: "taxa"; glifo: Icones.sineWave
      titulo: I18n.t("Taxa de atualização")
      descricao: I18n.t("Mais Hz deixa o movimento mais fluido")
      Selecao {
        width: 200
        readonly property string res: pg.mon && pg.rascunho[pg.mon.name] ? pg.rascunho[pg.mon.name].modo.split("@")[0] : ""
        opcoes: {
          if (!pg.mon) return []
          var vistos = {}, out = []
          pg.mon.availableModes.forEach(function(m) {
            if (m.split("@")[0] !== res) return
            var hz = m.split("@")[1].replace("Hz", "")
            if (vistos[hz]) return
            vistos[hz] = true
            out.push({ valor: res + "@" + hz, rotulo: Number(hz).toFixed(Number(hz) % 1 === 0 ? 0 : 2).replace(".", I18n.decimal) + I18n.t(" Hz") })
          })
          return out
        }
        atual: {
          if (!pg.mon || !pg.rascunho[pg.mon.name]) return ""
          var m = pg.rascunho[pg.mon.name].modo
          var hz = Number(m.split("@")[1])
          for (var i = 0; i < opcoes.length; i++) if (Math.abs(Number(opcoes[i].valor.split("@")[1]) - hz) < 0.05) return opcoes[i].valor
          return m
        }
        onEscolhido: function(v) { pg.mudar(pg.mon.name, "modo", v) }
      }
    }
    Linha {
      chave: "escala"; glifo: Icones.magnify
      titulo: I18n.t("Escala")
      descricao: I18n.t("Aumenta textos, apps e itens nesta tela")
      Selecao {
        width: 200
        opcoes: [1, 1.25, 1.333333, 1.5, 1.6, 1.666667, 1.75, 2, 2.5, 3].map(function(s) {
          return { valor: s, rotulo: Math.round(s * 100) + "%", detalhe: s === 1 ? I18n.t("Sem ampliação") : "" }
        })
        atual: {
          if (!pg.mon || !pg.rascunho[pg.mon.name]) return 1
          var e = pg.rascunho[pg.mon.name].escala
          for (var i = 0; i < opcoes.length; i++) if (Math.abs(opcoes[i].valor - e) < 0.01) return opcoes[i].valor
          return e
        }
        onEscolhido: function(v) { pg.mudar(pg.mon.name, "escala", v) }
      }
    }
    Linha {
      chave: "rotacao"; glifo: Icones.screenRotation
      titulo: I18n.t("Orientação")
      Selecao {
        width: 200
        opcoes: [{ valor: 0, rotulo: I18n.t("Paisagem") }, { valor: 1, rotulo: I18n.t("Retrato") }, { valor: 2, rotulo: I18n.t("Paisagem (invertida)") }, { valor: 3, rotulo: I18n.t("Retrato (invertido)") }]
        atual: pg.mon && pg.rascunho[pg.mon.name] ? pg.rascunho[pg.mon.name].giro : 0
        onEscolhido: function(v) { pg.mudar(pg.mon.name, "giro", v) }
      }
    }
    Linha {
      chave: "telaAtiva"; glifo: Icones.monitorOff
      titulo: I18n.t("Usar esta tela")
      descricao: pg.ativos.length < 2 ? I18n.t("É a única tela ativa") : I18n.t("Desligar muda o modo de projeção")
      Interruptor {
        ligado: true
        habilitado: pg.ativos.length > 1
        onAlternado: function(on) {
          if (!on && pg.mon) pg.aplicarModo(pg.mon.name === pg.estado.interna ? "segunda" : "notebook")
        }
      }
    }
    Linha {
      id: linhaPrincipal
      chave: "principal"; glifo: Icones.star
      titulo: I18n.t("Tela principal")
      descricao: I18n.t("Recebe os ícones da área de trabalho e o cursor ao entrar")
      readonly property string principal: Preferencias.obter("area.tela", "") || (pg.ordem[0] || "")
      Botao {
        visible: pg.mon && linhaPrincipal.principal !== pg.mon.name
        texto: I18n.t("Tornar principal")
        compacto: true
        onClicado: {
          Preferencias.definir("area.tela", pg.mon.name)
          Hypr.definir("cursor:default_monitor", pg.mon.name)
          Navegacao.confirmar(pg.mon.name + I18n.t(" é a tela principal"), Icones.star)
        }
      }
      Texto {
        visible: pg.mon && linhaPrincipal.principal === pg.mon.name
        text: I18n.t("É a principal")
        color: Tema.texto2
      }
    }
  }

  // ── brightness & night light ─────────────────────────────────────────────
  Secao { titulo: I18n.t("Brilho e cor") }
  Cartao {
    Linha {
      chave: "brilho"; glifo: Icones.brightness6
      visible: pg.brilho >= 0
      titulo: I18n.t("Brilho")
      descricao: I18n.t("Tela do notebook · também pelas teclas de brilho")
      Deslizante {
        width: 260
        de: 5; ate: 100; passo: 1
        valor: Math.max(5, pg.brilho)
        sufixo: "%"
        onMovido: function(v) { Sistema.rodar(["brightnessctl", "-q", "-c", "backlight", "set", v + "%"]) }
        onSolto: function(v) { pg.brilho = v }
      }
    }
    Linha {
      id: linhaLuz
      chave: "luzNoturna"; glifo: Icones.weatherNight
      titulo: I18n.t("Luz noturna")
      descricao: pg.luz.ativo && pg.luz.temperatura && pg.luz.temperatura < 6000 ? I18n.t("Ligada · ") + pg.luz.temperatura + " K" : I18n.t("Tons quentes à noite cansam menos a vista")
      readonly property bool ligada: !!(pg.luz.ativo && pg.luz.temperatura && pg.luz.temperatura < 6000)
      expandido: true
      Interruptor {
        ligado: linhaLuz.ligada
        onAlternado: function(on) {
          var t = on ? Preferencias.obter("luzNoturna.temperatura", 4000) : 6500
          Sistema.sh("pgrep -x hyprsunset >/dev/null || { setsid uwsm-app -- hyprsunset >/dev/null 2>&1 & sleep 1; }; hyprctl hyprsunset temperature " + t + " >/dev/null; simba-shell nightlight refresh >/dev/null 2>&1", function() {
            Sistema.json([Sistema.ajudante, "luz"], function(v) { if (v) pg.luz = v })
          })
        }
      }
      extra: [
        RowLayout {
          Layout.fillWidth: true; Layout.leftMargin: 48
          Ancora { chave: "luzTemperatura"; Layout.preferredWidth: 0 }
          Texto { text: I18n.t("Intensidade"); color: Tema.texto2; Layout.fillWidth: true }
          Texto { text: I18n.t("Suave"); color: Tema.texto3; font.pixelSize: Tema.tLegenda }
          Deslizante {
            Layout.preferredWidth: 220
            de: 2500; ate: 5500; passo: 100
            valor: 8000 - Preferencias.obter("luzNoturna.temperatura", 4000)
            formatar: function(v) { return (8000 - v) + " K" }
            onSolto: function(v) {
              var t = 8000 - v
              Preferencias.definir("luzNoturna.temperatura", t)
              if (pg.luz.ativo && pg.luz.temperatura < 6000) Sistema.sh("hyprctl hyprsunset temperature " + t + " >/dev/null; simba-shell nightlight refresh", function() {
                Sistema.json([Sistema.ajudante, "luz"], function(x) { if (x) pg.luz = x })
              })
            }
          }
          Texto { text: I18n.t("Forte"); color: Tema.texto3; font.pixelSize: Tema.tLegenda }
        },
        RowLayout {
          Layout.fillWidth: true; Layout.leftMargin: 48
          Ancora { chave: "luzAgenda"; Layout.preferredWidth: 0 }
          Texto { text: I18n.t("Programar"); color: Tema.texto2 }
          Item { Layout.fillWidth: true }
          Texto { text: I18n.t("das"); color: Tema.texto3; visible: pg.hyprsunsetAgenda }
          Selecao {
            visible: pg.hyprsunsetAgenda
            width: 96
            opcoes: ["18:00", "19:00", "20:00", "21:00", "22:00", "23:00"].map(function(h) { return { valor: h, rotulo: h } })
            atual: Preferencias.obter("luzNoturna.inicio", "20:00")
            onEscolhido: function(v) { Preferencias.definir("luzNoturna.inicio", v); agenda.restart() }
          }
          Texto { text: I18n.t("às"); color: Tema.texto3; visible: pg.hyprsunsetAgenda }
          Selecao {
            visible: pg.hyprsunsetAgenda
            width: 96
            opcoes: ["05:00", "06:00", "07:00", "08:00", "09:00"].map(function(h) { return { valor: h, rotulo: h } })
            atual: Preferencias.obter("luzNoturna.fim", "07:00")
            onEscolhido: function(v) { Preferencias.definir("luzNoturna.fim", v); agenda.restart() }
          }
          Interruptor {
            ligado: pg.hyprsunsetAgenda
            onAlternado: function(on) { Preferencias.definir("luzNoturna.agendar", on); pg.hyprsunsetAgenda = on; agenda.restart() }
          }
        }
      ]
    }
  }
  Timer {
    id: agenda
    interval: 500
    onTriggered: {
      var conf = Sistema.home + "/.config/hypr/hyprsunset.conf"
      var bloco = ""
      if (pg.hyprsunsetAgenda) {
        var t = Preferencias.obter("luzNoturna.temperatura", 4000)
        bloco = "# Luz noturna programada (app Configurações): liga às " + Preferencias.obter("luzNoturna.inicio", "20:00") +
                I18n.t(", desliga às ") + Preferencias.obter("luzNoturna.fim", "07:00") + ".\n" +
                I18n.t("profile {\n    time = ") + Preferencias.obter("luzNoturna.inicio", "20:00") + I18n.t("\n    temperature = ") + t + "\n}\n" +
                I18n.t("profile {\n    time = ") + Preferencias.obter("luzNoturna.fim", "07:00") + I18n.t("\n    identity = true\n}")
      }
      Sistema.rodar([Sistema.bin + "/luz-agenda", pg.hyprsunsetAgenda ? "ligar" : "desligar"], function() {
        Navegacao.confirmar(pg.hyprsunsetAgenda ? I18n.t("Luz noturna programada") : I18n.t("Programação desligada"), Icones.weatherNight)
        Sistema.json([Sistema.ajudante, "luz"], function(x) { if (x) pg.luz = x })
      }, bloco)
    }
  }
}
