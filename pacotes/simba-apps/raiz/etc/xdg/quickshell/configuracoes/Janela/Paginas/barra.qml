import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Comum
import qs.Janela
import "tarefas-icones.js" as TI

Pagina {
  id: pg
  titulo: I18n.t("Barra")
  subtitulo: I18n.t("Aparência, apps, áreas de trabalho e relógio da barra. Tudo aparece na barra na hora.")

  // ── estado ───────────────────────────────────────────────────────────────
  property var b: null          // ajudante barra (layout, catálogo, oculta, transparente…)
  // transparência mostrada na mini barra: a do arrasto enquanto o controle se move
  property real transparenciaArrasto: -1
  readonly property real transparencia: transparenciaArrasto >= 0 ? transparenciaArrasto : (b ? b.transparencia : 0)
  property var t: null          // barra-tarefas estado
  property var icones: ({})     // desktop-id → arquivo (modo colorido)
  property bool ocupado: false

  readonly property var nomes: ({
    "simba.active-window": I18n.t("Janela ativa"), "simba.agents": I18n.t("Agentes de IA"), "simba.audio": I18n.t("Áudio"),
    "simba.bluetooth": I18n.t("Bluetooth"), "simba.clock": I18n.t("Relógio"), "simba.dropbox": I18n.t("Dropbox"),
    "simba.indicators": I18n.t("Indicadores"), "simba.keyboard-layout": I18n.t("Layout do teclado"), "simba.media": I18n.t("Mídia"),
    "simba.menu": I18n.t("Menu do Simba"), "simba.microphone": I18n.t("Microfone"), "simba.monitor": I18n.t("Tela"),
    "simba.network": I18n.t("Rede"), "simba.power": I18n.t("Energia e bateria"), "simba.spacer": I18n.t("Espaçador"),
    "simba.system-update": I18n.t("Atualizações"), "simba.tailscale": I18n.t("Tailscale"), "simba.tray": I18n.t("Bandeja do sistema"),
    "simba.weather": I18n.t("Clima"), "simba.workspaces": I18n.t("Áreas de trabalho"), "tarefas": I18n.t("Barra de tarefas"),
    "areas": I18n.t("Áreas de trabalho"), "bandeja": I18n.t("Seta de ícones ocultos")
  })
  readonly property var glifos: ({
    "simba.active-window": Icones.dockWindow, "simba.agents": Icones.robot, "simba.audio": Icones.volumeHigh,
    "simba.bluetooth": Icones.bluetooth, "simba.clock": Icones.clockOutline, "simba.dropbox": Icones.folderOpen,
    "simba.indicators": Icones.bellRing, "simba.keyboard-layout": Icones.keyboard, "simba.media": Icones.music,
    "simba.menu": Icones.menu, "simba.microphone": Icones.microphone, "simba.monitor": Icones.monitor,
    "simba.network": Icones.wifi, "simba.power": Icones.battery, "simba.spacer": Icones.dotsHorizontal,
    "simba.system-update": Icones.update, "simba.tailscale": Icones.lan, "simba.tray": Icones.apps,
    "simba.weather": Icones.weatherSunny, "simba.workspaces": Icones.viewGridOutline, "tarefas": Icones.apps,
    "areas": Icones.viewGridOutline, "bandeja": Icones.chevronUp
  })
  function nome(id) {
    if (nomes[id]) return nomes[id]
    var c = b ? b.catalogo.filter(function(x) { return x.id === id })[0] : null
    return c ? c.nome : id
  }

  function carregar() {
    Sistema.json([Sistema.ajudante, "barra"], function(v) { if (v) pg.b = v })
    Sistema.json(["barra-tarefas", "estado"], function(v) {
      if (!v) return
      pg.t = v
      Sistema.json(["barra-tarefas", "icones"].concat(v.fixados), function(m) { if (m) pg.icones = m })
    })
  }
  Component.onCompleted: carregar()

  function cmd(argv, msg, glifoMsg) {
    ocupado = true
    Sistema.rodar(argv, function(o, code, err) {
      pg.ocupado = false
      pg.carregar()
      if (code === 0 && msg) Navegacao.confirmar(msg, glifoMsg || Icones.dockBottom)
      else if (code !== 0) Navegacao.confirmar((err || o).trim().split("\n").pop() || I18n.t("Não deu certo"), Icones.alert)
    })
  }
  function tarefas(args, msg) { cmd(["barra-tarefas"].concat(args), msg) }
  function app(id) { return DesktopEntries.byId(id) }
  function glifoApp(id) { var d = app(id); return TI.glifo(id, "", d ? d.name : "", d ? d.categories : []) }

  readonly property bool tarefasAtiva: t ? t.ativa : false
  readonly property string posicao: t ? t.posicao : "top"
  readonly property bool vertical: posicao === "left" || posicao === "right"
  readonly property bool monocromatico: !t || t.opcoes.estiloIcones !== "coloridos"
  readonly property string estiloAreas: t ? t.areas : "numeros"
  readonly property string tamanhoBarra: t ? t.tamanho : "normal"
  // altura em px (22–60); enquanto o controle é arrastado, a mini barra mostra a prévia
  property int alturaArrasto: -1
  readonly property int alturaBarra: alturaArrasto > 0 ? alturaArrasto : (t && t.altura ? t.altura : 26)
  function nomeAltura(v) {
    if (v <= 23) return I18n.t("Compacta")
    if (v <= 28) return I18n.t("Normal")
    if (v <= 35) return I18n.t("Confortável")
    if (v <= 44) return I18n.t("Grande")
    return I18n.t("Enorme")
  }

  readonly property var todosNaBarra: b ? b.layout.left.concat(b.layout.center).concat(b.layout.right) : []
  readonly property var disponiveis: b ? b.catalogo.filter(function(c) { return pg.todosNaBarra.indexOf(c.id) < 0 && c.id !== "simba.workspaces" }) : []
  readonly property var appsDisponiveis: {
    var fix = t ? t.fixados : []
    return DesktopEntries.applications.values
      .filter(function(d) { return d && !d.noDisplay && fix.indexOf(d.id) < 0 })
      .map(function(d) { return { valor: d.id, rotulo: d.name, detalhe: d.genericName || "" } })
      .sort(function(x, y) { return String(x.rotulo).localeCompare(String(y.rotulo), "pt-BR", { sensitivity: "base" }) })
  }

  // ── relógio ──────────────────────────────────────────────────────────────
  property date agora: new Date()
  Timer { interval: 1000; running: true; repeat: true; onTriggered: pg.agora = new Date() }
  function fmt(f, d) { return Qt.locale().toString(d || agora, f) }
  readonly property var datas: [
    { valor: "", rotulo: I18n.t("Sem data") },
    { valor: "ddd", rotulo: I18n.t("Dia da semana") },
    { valor: "dd/MM", rotulo: I18n.t("Dia e mês") },
    { valor: "ddd, d MMM", rotulo: I18n.t("Curta") },
    { valor: "d 'de' MMMM", rotulo: I18n.t("Por extenso") },
    { valor: "dddd, d 'de' MMMM", rotulo: I18n.t("Completa") },
    { valor: "dd/MM/yyyy", rotulo: I18n.t("Numérica") },
    { valor: "yyyy-MM-dd", rotulo: I18n.t("ISO") }
  ]
  readonly property var partes: {
    var p = t && t.relogio ? t.relogio.partes : null
    if (p) return p
    var f = t && t.relogio ? String(t.relogio.formato) : "yyyy-MM-dd HH:mm"
    var d = ""
    for (var i = datas.length - 1; i > 0; i--) if (f.indexOf(datas[i].valor) >= 0) { d = datas[i].valor; break }
    return { data: d, h12: /AP|ap/.test(f), segundos: f.indexOf("ss") >= 0 }
  }
  function compor(p) {
    var hora = p.h12 ? "h:mm" + (p.segundos ? ":ss" : "") + " AP" : "HH:mm" + (p.segundos ? ":ss" : "")
    return p.data ? p.data + "  " + hora : hora
  }
  function relogio(mudar, msg) {
    var p = Object.assign({}, partes, mudar)
    cmd(["barra-tarefas", "relogio", compor(p), JSON.stringify(p)], msg || I18n.t("Relógio atualizado"), Icones.clockOutline)
  }
  readonly property string textoRelogio: fmt(compor(partes))

  // ── pré-visualização ─────────────────────────────────────────────────────
  property string papel: ""
  Process {
    command: ["readlink", "-f", Tema.estadoSimba + "/background"]
    running: true
    stdout: StdioCollector { onStreamFinished: pg.papel = text.trim() }
  }

  // Mini barra desenhada com os mesmos glifos e opções da barra real.
  component MiniBarra: Rectangle {
    id: mb
    property real escala: 1
    property bool vert: false
    readonly property int grossura: Math.round(pg.alturaBarra * escala)
    readonly property color frente: pg.transparencia >= 50 ? "#ffffff" : Tema.texto
    color: Qt.rgba(Tema.fundo.r, Tema.fundo.g, Tema.fundo.b, 1 - pg.transparencia / 100)
    Behavior on color { ColorAnimation { duration: Tema.medio } }

    Grid {
      id: esq
      columns: mb.vert ? 1 : 40
      spacing: Math.round(9 * mb.escala)
      x: mb.vert ? (mb.width - width) / 2 : Math.round(10 * mb.escala)
      y: mb.vert ? Math.round(10 * mb.escala) : (mb.height - height) / 2
      verticalItemAlignment: Grid.AlignVCenter
      horizontalItemAlignment: Grid.AlignHCenter

      Text { text: Icones.menu; color: mb.frente; font.family: Tema.fonte; font.pixelSize: Math.round(12 * mb.escala) }

      // áreas de trabalho
      Grid {
        visible: pg.estiloAreas !== "ocultar"
        columns: mb.vert ? 1 : 10
        spacing: Math.round((pg.estiloAreas === "pontos" ? 4 : 6) * mb.escala)
        verticalItemAlignment: Grid.AlignVCenter
        horizontalItemAlignment: Grid.AlignHCenter
        Repeater {
          model: pg.estiloAreas === "ocupadas" ? [1] : [1, 2, 3, 4, 5]
          delegate: Item {
            required property int modelData
            readonly property bool foco: modelData === 1
            width: pg.estiloAreas === "pontos" ? (foco && !mb.vert ? 16 : 6) * mb.escala : numero.implicitWidth
            height: pg.estiloAreas === "pontos" ? (foco && mb.vert ? 16 : 6) * mb.escala : numero.implicitHeight
            Behavior on width { NumberAnimation { duration: Tema.medio; easing.type: Tema.curva } }
            Rectangle {
              visible: pg.estiloAreas === "pontos"
              anchors.fill: parent
              radius: Math.min(width, height) / 2
              color: parent.foco ? Tema.realce : mb.frente
              opacity: parent.foco ? 1 : (parent.modelData === 2 ? 0.85 : 0.3)
            }
            Text {
              id: numero
              visible: pg.estiloAreas !== "pontos"
              text: pg.estiloAreas === "numeros" && parent.foco ? "󱓻" : String(parent.modelData)
              color: pg.estiloAreas === "ocupadas" ? Tema.realce : mb.frente
              opacity: parent.foco || parent.modelData === 2 ? 1 : 0.5
              font.family: Tema.fonte
              font.pixelSize: Math.round(11 * mb.escala)
              font.weight: pg.estiloAreas === "ocupadas" ? Font.Bold : Font.Normal
            }
          }
        }
      }

      // apps
      Grid {
        visible: pg.tarefasAtiva
        columns: mb.vert ? 1 : 20
        spacing: Math.round(10 * mb.escala)
        verticalItemAlignment: Grid.AlignVCenter
        horizontalItemAlignment: Grid.AlignHCenter
        Repeater {
          model: pg.t ? pg.t.fixados.slice(0, mb.vert ? 4 : 8) : []
          delegate: Item {
            required property string modelData
            required property int index
            readonly property int lado: Math.round((pg.t ? pg.t.opcoes.tamanho : 18) * mb.escala)
            width: lado + 2
            height: lado + 2
            Text {
              visible: pg.monocromatico
              anchors.centerIn: parent
              text: pg.glifoApp(parent.modelData)
              color: parent.index === 1 ? Tema.realce : mb.frente
              opacity: parent.index <= 2 ? 1 : 0.65
              font.family: Tema.fonte
              font.pixelSize: parent.lado
            }
            Image {
              visible: !pg.monocromatico
              anchors.fill: parent
              source: pg.icones[parent.modelData] ? "file://" + pg.icones[parent.modelData] : ""
              sourceSize.width: 64
              sourceSize.height: 64
              smooth: true
              asynchronous: true
            }
            // indicador de app aberto (os dois primeiros), do lado voltado para a tela
            Rectangle {
              visible: parent.index <= 1
              readonly property bool dentro: pg.posicao === "bottom" || pg.posicao === "right"
              width: mb.vert ? 2 : (parent.index === 1 ? 10 : 4) * mb.escala
              height: mb.vert ? (parent.index === 1 ? 10 : 4) * mb.escala : 2
              radius: 1
              color: parent.index === 1 ? Tema.realce : mb.frente
              x: mb.vert ? (dentro ? -Math.round(4 * mb.escala) : parent.width + Math.round(2 * mb.escala)) : (parent.width - width) / 2
              y: mb.vert ? (parent.height - height) / 2 : (dentro ? -Math.round(5 * mb.escala) : parent.height + Math.round(3 * mb.escala))
            }
          }
        }
      }
    }

    // relógio
    Text {
      id: rel
      readonly property bool centro: !pg.t || pg.t.relogio.secao !== "right"
      text: mb.vert ? pg.fmt(I18n.t("HH\nmm")) : pg.textoRelogio
      horizontalAlignment: Text.AlignHCenter
      color: mb.frente
      font.family: Tema.fonte
      font.pixelSize: Math.round(11 * mb.escala)
      x: mb.vert ? (mb.width - width) / 2 : (centro ? (mb.width - width) / 2 : dir.x - width - Math.round(12 * mb.escala))
      y: mb.vert ? (centro ? (mb.height - height) / 2 : dir.y - height - Math.round(12 * mb.escala)) : (mb.height - height) / 2
      Behavior on x { NumberAnimation { duration: Tema.medio; easing.type: Tema.curva } }
    }

    // status
    Grid {
      id: dir
      columns: mb.vert ? 1 : 4
      spacing: Math.round(10 * mb.escala)
      x: mb.vert ? (mb.width - width) / 2 : mb.width - width - Math.round(10 * mb.escala)
      y: mb.vert ? mb.height - height - Math.round(10 * mb.escala) : (mb.height - height) / 2
      Repeater {
        model: [Icones.wifi, Icones.volumeHigh, Icones.bluetooth, Icones.battery]
        delegate: Text { required property string modelData; text: modelData; color: mb.frente; font.family: Tema.fonte; font.pixelSize: Math.round(11 * mb.escala) }
      }
    }
  }

  // Bloco de escolha visual (tile) para áreas de trabalho e estilo de ícones.
  component Escolha: Rectangle {
    id: es
    property bool selecionado: false
    property string rotulo: ""
    property string detalhe: ""
    default property alias desenho: palco.data
    signal escolher()
    Layout.fillWidth: true
    Layout.preferredHeight: 116
    radius: Tema.raioGrande
    color: selecionado ? Tema.selecao : (ma.containsMouse ? Tema.superficieAlta : Tema.superficie)
    border.width: selecionado ? 2 : 1
    border.color: selecionado ? Tema.realce : Tema.linha
    Behavior on color { ColorAnimation { duration: Tema.rapido } }
    Behavior on border.color { ColorAnimation { duration: Tema.rapido } }
    scale: ma.pressed ? 0.98 : 1
    Behavior on scale { NumberAnimation { duration: Tema.rapido } }

    Rectangle {
      id: palcoFundo
      x: 10; y: 10
      width: parent.width - 20
      height: 52
      radius: Math.max(4, Tema.raio - 2)
      color: Tema.fundo
      border.width: 1
      border.color: Tema.linha
      clip: true
      Item { id: palco; anchors.fill: parent }
    }
    Column {
      x: 12
      anchors.top: palcoFundo.bottom
      anchors.topMargin: 9
      width: parent.width - 24
      spacing: 1
      Texto { text: es.rotulo; font.weight: Font.DemiBold; width: parent.width; elide: Text.ElideRight }
      Texto { visible: es.detalhe !== ""; text: es.detalhe; color: Tema.texto3; font.pixelSize: Tema.tLegenda; width: parent.width; elide: Text.ElideRight }
    }
    Rectangle {
      visible: es.selecionado
      anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 5
      width: 18; height: 18; radius: 9
      color: Tema.realce
      Glifo { anchors.centerIn: parent; g: Icones.check; tamanho: 11; color: Tema.sobreRealce }
    }
    MouseArea { id: ma; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: if (!pg.ocupado && !es.selecionado) es.escolher() }
  }

  Rectangle {
    id: previa
    Layout.fillWidth: true
    Layout.preferredHeight: 230
    Layout.topMargin: 4
    radius: Tema.raioGrande
    color: Tema.superficie
    border.width: 1
    border.color: Tema.linha
    clip: true

    Image {
      anchors.fill: parent
      source: pg.papel ? "file://" + pg.papel : ""
      fillMode: Image.PreserveAspectCrop
      sourceSize.width: 1100
      asynchronous: true
    }
    Rectangle { anchors.fill: parent; color: Tema.fundo; opacity: 0.15 }

    // uma janela de exemplo, para dar escala
    Rectangle {
      readonly property int g: Math.round(pg.alturaBarra * 0.9)
      x: pg.posicao === "left" ? g + 26 : 26
      y: pg.posicao === "top" ? g + 22 : 22
      width: parent.width - 52 - (pg.vertical ? g : 0)
      height: parent.height - 44 - (pg.vertical ? 0 : g)
      radius: Math.max(6, Tema.raio)
      color: Tema.alfa(Tema.fundo, 0.82)
      border.width: 1
      border.color: Tema.alfa(Tema.texto, 0.12)
      Behavior on x { NumberAnimation { duration: Tema.medio; easing.type: Tema.curva } }
      Behavior on y { NumberAnimation { duration: Tema.medio; easing.type: Tema.curva } }
      Column {
        x: 18; y: 18
        spacing: 8
        Repeater {
          model: [0.42, 0.7, 0.58, 0.33]
          delegate: Rectangle { required property real modelData; width: 260 * modelData; height: 7; radius: 3.5; color: Tema.texto; opacity: 0.12 }
        }
      }
    }

    MiniBarra {
      escala: 0.9
      vert: pg.vertical
      visible: !pg.b || !pg.b.oculta
      width: vert ? grossura : parent.width
      height: vert ? parent.height : grossura
      x: pg.posicao === "right" ? parent.width - width : 0
      y: pg.posicao === "bottom" ? parent.height - height : 0
    }

    Rectangle {
      visible: pg.b ? pg.b.oculta : false
      anchors.centerIn: parent
      width: aviso.implicitWidth + 28; height: 34; radius: 17
      color: Tema.alfa(Tema.fundo, 0.85)
      Texto { id: aviso; anchors.centerIn: parent; text: I18n.t("Barra oculta · Super+Shift+Espaço mostra de novo"); color: Tema.texto2 }
    }
  }

  // ── aparência ────────────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Aparência") }
  Cartao {
    Linha {
      chave: "barraMostrar"; glifo: Icones.dockBottom
      titulo: I18n.t("Mostrar a barra")
      descricao: I18n.t("Também com Super+Shift+Espaço")
      Interruptor { ligado: pg.b ? !pg.b.oculta : true; onAlternado: function(on) { pg.cmd(["simba-toggle-bar", on ? "off" : "on"], on ? I18n.t("Barra visível") : I18n.t("Barra oculta")) } }
    }
    Linha {
      chave: "barraPosicao"; glifo: Icones.dockBottom
      titulo: I18n.t("Posição")
      Segmentado {
        opcoes: [{ valor: "top", rotulo: I18n.t("Topo"), glifo: Icones.dockTop }, { valor: "bottom", rotulo: I18n.t("Base"), glifo: Icones.dockBottom },
                 { valor: "left", rotulo: I18n.t("Esquerda"), glifo: Icones.dockLeft }, { valor: "right", rotulo: I18n.t("Direita"), glifo: Icones.dockRight }]
        atual: pg.posicao
        onEscolhido: function(v) { pg.cmd(["simba-bar", "position", v], I18n.t("Barra movida")) }
      }
    }
    Linha {
      chave: "barraTamanho"; glifo: Icones.formatSize
      titulo: I18n.t("Tamanho da barra")
      descricao: I18n.t("Altura da barra (ou largura, na lateral) · padrão 26 px")
      Deslizante {
        width: 240; de: 22; ate: 60; passo: 2
        valor: pg.t && pg.t.altura ? pg.t.altura : 26
        formatar: function(v) { return Math.round(v) + " px · " + pg.nomeAltura(v) }
        onMovido: function(v) { pg.alturaArrasto = Math.round(v) }
        onSolto: function(v) {
          pg.alturaArrasto = -1
          pg.tarefas(["altura", String(Math.round(v))], I18n.t("Tamanho da barra ajustado"))
        }
      }
    }
    Linha {
      chave: "barraTransparente"; glifo: Icones.opacity
      titulo: I18n.t("Transparência do fundo")
      descricao: I18n.t("Quanto do papel de parede aparece atrás da barra · 0 % = sólida")
      Deslizante {
        width: 240; de: 0; ate: 100; passo: 5; sufixo: " %"
        valor: pg.b ? pg.b.transparencia : 0
        onMovido: function(v) { pg.transparenciaArrasto = v }
        onSolto: function(v) {
          pg.transparenciaArrasto = -1
          pg.cmd(["simba-bar", "transparency", String(Math.round(v))],
                 v <= 0 ? I18n.t("Barra sólida") : (v >= 100 ? I18n.t("Barra transparente") : I18n.t("Transparência da barra ajustada")))
        }
      }
    }
    Linha {
      chave: "barraCentro"; glifo: Icones.eyeOutline
      titulo: I18n.t("Ícones do centro")
      descricao: I18n.t("Indicadores, teclado, clima e atualizações no meio da barra. O relógio continua, se estiver lá.")
      Interruptor { ligado: pg.t ? !pg.t.centroOculto : true; onAlternado: function(on) { pg.tarefas(["centro", on ? "mostrar" : "ocultar"], on ? I18n.t("Ícones do centro visíveis") : I18n.t("Ícones do centro ocultos")) } }
    }
    Linha {
      chave: "barraBandeja"; glifo: Icones.chevronUp
      titulo: I18n.t("Seta de ícones ocultos")
      descricao: I18n.t("Como no Windows 11: arraste ícones para a seta para escondê-los, e de dentro dela para fora para mostrar de novo.")
      Interruptor { ligado: pg.t ? pg.t.bandeja.ativa : false; onAlternado: function(on) { pg.tarefas(["bandeja", on ? "ativar" : "desativar"], on ? I18n.t("Seta de ícones ocultos ativada") : I18n.t("Seta desativada, ícones de volta na barra")) } }
    }
  }

  // ── áreas de trabalho ────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Áreas de trabalho"); detalhe: I18n.t("Como as áreas aparecem na barra. Super + número continua levando a qualquer uma, mesmo ocultas.") }
  Ancora { chave: "areasEstilo" }
  GridLayout {
    Layout.fillWidth: true
    columns: 4
    columnSpacing: 10
    Escolha {
      rotulo: I18n.t("Números"); detalhe: I18n.t("Padrão do Simba")
      selecionado: pg.estiloAreas === "numeros"
      onEscolher: pg.tarefas(["areas", "numeros"], I18n.t("Áreas de trabalho: números"))
      Row {
        anchors.centerIn: parent; spacing: 9
        Repeater { model: ["󱓻", "2", "3", "4", "5"]; delegate: Texto { required property string modelData; required property int index; text: modelData; opacity: index <= 1 ? 1 : 0.45 } }
      }
    }
    Escolha {
      rotulo: I18n.t("Pontos"); detalhe: I18n.t("A atual em destaque")
      selecionado: pg.estiloAreas === "pontos"
      onEscolher: pg.tarefas(["areas", "pontos"], I18n.t("Áreas de trabalho: pontos"))
      Row {
        anchors.centerIn: parent; spacing: 5
        Repeater {
          model: 5
          delegate: Rectangle {
            required property int index
            width: index === 0 ? 18 : 6; height: 6; radius: 3
            color: index === 0 ? Tema.realce : Tema.texto
            opacity: index === 0 ? 1 : (index === 1 ? 0.85 : 0.28)
          }
        }
      }
    }
    Escolha {
      rotulo: I18n.t("Só as ocupadas"); detalhe: I18n.t("Com janelas abertas")
      selecionado: pg.estiloAreas === "ocupadas"
      onEscolher: pg.tarefas(["areas", "ocupadas"], I18n.t("Áreas de trabalho: só as ocupadas"))
      Row {
        anchors.centerIn: parent; spacing: 4
        Rectangle { width: 22; height: 20; radius: 6; color: Tema.alfa(Tema.texto, 0.12); Texto { anchors.centerIn: parent; text: "1"; color: Tema.realce; font.weight: Font.Bold } }
        Item { width: 22; height: 20; Texto { anchors.centerIn: parent; text: "3"; opacity: 0.7 } }
      }
    }
    Escolha {
      rotulo: I18n.t("Ocultar"); detalhe: I18n.t("Use Super + número")
      selecionado: pg.estiloAreas === "ocultar"
      onEscolher: pg.tarefas(["areas", "ocultar"], I18n.t("Áreas de trabalho ocultas"))
      Row {
        anchors.centerIn: parent; spacing: 6
        Repeater {
          model: [I18n.t("Super"), "+", "1…9"]
          delegate: Rectangle {
            required property string modelData
            width: tecla.implicitWidth + (modelData === "+" ? 0 : 14); height: 22; radius: 5
            color: modelData === "+" ? "transparent" : Tema.superficieAlta
            border.width: modelData === "+" ? 0 : 1
            border.color: Tema.linhaForte
            Texto { id: tecla; anchors.centerIn: parent; text: parent.modelData; font.pixelSize: Tema.tLegenda; color: Tema.texto2 }
          }
        }
      }
    }
  }

  // ── barra de tarefas ─────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Barra de tarefas"); detalhe: I18n.t("Seus apps na barra: clique abre ou alterna, clique do meio abre outra janela, botão direito fixa, desafixa ou fecha.") }
  Ancora { chave: "tarefas" }
  Cartao {
    Linha {
      chave: "tarefasAtiva"; glifo: Icones.apps
      titulo: I18n.t("Mostrar apps na barra")
      descricao: I18n.t("Desligue para deixar a barra como o Simba vem (seus apps fixados ficam guardados)")
      Interruptor { ligado: pg.tarefasAtiva; onAlternado: function(on) { pg.tarefas([on ? "ativar" : "desativar"], on ? I18n.t("Barra de tarefas ativada") : I18n.t("Barra de tarefas desativada")) } }
    }
  }

  Ancora { chave: "tarefasIcones"; visible: pg.tarefasAtiva }
  GridLayout {
    visible: pg.tarefasAtiva
    Layout.fillWidth: true
    Layout.topMargin: 10
    columns: 2
    columnSpacing: 10
    Escolha {
      rotulo: I18n.t("Ícones do tema"); detalhe: I18n.t("Monocromáticos, mudam de cor junto com o tema")
      selecionado: pg.monocromatico
      onEscolher: pg.tarefas(["opcao", "estiloIcones", "\"tema\""], I18n.t("Ícones do tema"))
      Row {
        anchors.centerIn: parent; spacing: 16
        Repeater {
          model: pg.t ? pg.t.fixados.slice(0, 6) : []
          delegate: Texto { required property string modelData; required property int index; text: pg.glifoApp(modelData); font.pixelSize: 20; color: index === 1 ? Tema.realce : Tema.texto; opacity: index <= 1 ? 1 : 0.7 }
        }
      }
    }
    Escolha {
      rotulo: I18n.t("Coloridos"); detalhe: I18n.t("Ícones originais dos apps (tema de ícones do sistema)")
      selecionado: !pg.monocromatico
      onEscolher: pg.tarefas(["opcao", "estiloIcones", "\"coloridos\""], I18n.t("Ícones coloridos"))
      Row {
        anchors.centerIn: parent; spacing: 14
        Repeater {
          model: pg.t ? pg.t.fixados.slice(0, 6) : []
          delegate: Image {
            required property string modelData
            width: 22; height: 22
            source: pg.icones[modelData] ? "file://" + pg.icones[modelData] : ""
            sourceSize.width: 64; sourceSize.height: 64
            asynchronous: true; smooth: true
          }
        }
      }
    }
  }

  Cartao {
    visible: pg.tarefasAtiva
    Layout.topMargin: 10
    Linha {
      chave: "tarefasSecao"; glifo: Icones.dockBottom
      titulo: I18n.t("Onde ficam os apps")
      Segmentado {
        opcoes: [{ valor: "left", rotulo: I18n.t("Esquerda") }, { valor: "center", rotulo: I18n.t("Centro") }, { valor: "right", rotulo: I18n.t("Direita") }]
        atual: pg.t ? pg.t.secao : "left"
        onEscolhido: function(v) { pg.tarefas(["secao", v], I18n.t("Apps movidos")) }
      }
    }
    Linha {
      chave: "tarefasTamanho"; glifo: Icones.relativeScale
      titulo: I18n.t("Tamanho dos ícones")
      Segmentado {
        opcoes: [{ valor: 14, rotulo: I18n.t("Pequeno") }, { valor: 18, rotulo: I18n.t("Médio") }, { valor: 22, rotulo: I18n.t("Grande") }]
        atual: pg.t ? pg.t.opcoes.tamanho : 18
        onEscolhido: function(v) { pg.tarefas(["opcao", "tamanho", String(v)]) }
      }
    }
    Linha {
      chave: "tarefasAbertos"; glifo: Icones.dockWindow
      titulo: I18n.t("Mostrar apps abertos")
      descricao: I18n.t("Além dos fixados, mostra todo app com janela aberta")
      Interruptor { ligado: pg.t ? pg.t.opcoes.abertos : true; onAlternado: function(on) { pg.tarefas(["opcao", "abertos", on ? "true" : "false"]) } }
    }
    Linha {
      chave: "tarefasRotulos"; glifo: Icones.formatText
      titulo: I18n.t("Nome ao lado do ícone")
      descricao: I18n.t("Título da janela ou nome do app; ocupa espaço, combina com poucos apps fixados")
      Interruptor { ligado: pg.t ? pg.t.opcoes.rotulos : false; onAlternado: function(on) { pg.tarefas(["opcao", "rotulos", on ? "true" : "false"]) } }
    }
    Linha {
      chave: "tarefasMinimiza"; glifo: Icones.minus
      titulo: I18n.t("Clicar no app em foco minimiza")
      descricao: I18n.t("Clique de novo para trazer a janela de volta")
      Interruptor { ligado: pg.t ? pg.t.opcoes.cliqueMinimiza : true; onAlternado: function(on) { pg.tarefas(["opcao", "cliqueMinimiza", on ? "true" : "false"]) } }
    }
    Linha {
      chave: "tarefasTela"; glifo: Icones.monitorMultiple
      titulo: I18n.t("Só janelas desta tela")
      descricao: I18n.t("Com mais de um monitor, cada barra mostra só as janelas abertas nele")
      Interruptor { ligado: pg.t ? pg.t.opcoes.soEstaTela : false; onAlternado: function(on) { pg.tarefas(["opcao", "soEstaTela", on ? "true" : "false"]) } }
    }
  }

  Secao { visible: pg.tarefasAtiva; titulo: I18n.t("Apps fixados"); detalhe: I18n.t("Na ordem em que aparecem na barra.") }
  Ancora { chave: "tarefasFixados"; visible: pg.tarefasAtiva }
  Cartao {
    visible: pg.tarefasAtiva
    Repeater {
      model: pg.t ? pg.t.fixados : []
      delegate: Linha {
        id: fixo
        required property string modelData
        required property int index
        glifo: pg.glifoApp(modelData)
        titulo: pg.app(modelData) ? pg.app(modelData).name : modelData
        descricao: pg.app(modelData) ? (pg.app(modelData).genericName || "") : I18n.t("App não encontrado")
        Row {
          spacing: 0
          Botao { compacto: true; tipo: "fantasma"; glifo: Icones.chevronUp; habilitado: fixo.index > 0 && !pg.ocupado; onClicado: pg.tarefas(["mover", fixo.modelData, "-1"]) }
          Botao { compacto: true; tipo: "fantasma"; glifo: Icones.chevronDown; habilitado: pg.t && fixo.index < pg.t.fixados.length - 1 && !pg.ocupado; onClicado: pg.tarefas(["mover", fixo.modelData, "1"]) }
          Botao { compacto: true; tipo: "fantasma"; glifo: Icones.close; habilitado: !pg.ocupado; onClicado: pg.tarefas(["desafixar", fixo.modelData], I18n.t("Desafixado")) }
        }
      }
    }
    Linha {
      glifo: Icones.plus
      titulo: I18n.t("Fixar um app")
      descricao: I18n.t("Ou clique com o botão direito num app aberto na barra")
      Selecao {
        width: 260
        vazio: I18n.t("Escolher app…")
        opcoes: pg.appsDisponiveis
        onEscolhido: function(v) { pg.tarefas(["fixar", v], I18n.t("App fixado na barra")) }
      }
    }
  }

  // ── data e hora ──────────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Data e hora"); detalhe: I18n.t("Clique no relógio da barra para ver o calendário e a data completa.") }
  Ancora { chave: "relogio" }
  Cartao {
    Item {
      Layout.fillWidth: true
      Layout.preferredHeight: 96
      Column {
        anchors.centerIn: parent
        spacing: 4
        Texto {
          anchors.horizontalCenter: parent.horizontalCenter
          text: pg.textoRelogio
          font.pixelSize: Tema.tTitulao
          font.weight: Font.Light
        }
        Texto {
          anchors.horizontalCenter: parent.horizontalCenter
          text: I18n.t("Ao clicar: ") + pg.fmt(I18n.t("dddd, d 'de' MMMM 'de' yyyy"))
          color: Tema.texto3
          font.pixelSize: Tema.tLegenda + 1
        }
      }
      Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 1; color: Tema.linha }
    }
    Linha {
      chave: "relogioHora"; glifo: Icones.clockOutline
      titulo: I18n.t("Formato da hora")
      Segmentado {
        opcoes: [{ valor: false, rotulo: I18n.t("24 horas") }, { valor: true, rotulo: I18n.t("12 horas") }]
        atual: pg.partes.h12 === true
        onEscolhido: function(v) { pg.relogio({ h12: v }) }
      }
    }
    Linha {
      chave: "relogioSegundos"; glifo: Icones.timer
      titulo: I18n.t("Mostrar segundos")
      Interruptor { ligado: pg.partes.segundos === true; onAlternado: function(on) { pg.relogio({ segundos: on }) } }
    }
    Linha {
      chave: "relogioFormato"; glifo: Icones.calendar
      titulo: I18n.t("Data")
      descricao: I18n.t("Junto da hora, na barra")
      Selecao {
        width: 260
        opcoes: pg.datas.map(function(d) { return { valor: d.valor, rotulo: d.valor ? pg.fmt(d.valor) : d.rotulo, detalhe: d.valor ? d.rotulo : "" } })
        atual: pg.partes.data
        onEscolhido: function(v) { pg.relogio({ data: v }) }
      }
    }
    Linha {
      chave: "relogioPosicao"; glifo: Icones.swapHorizontal
      titulo: I18n.t("Posição do relógio")
      descricao: I18n.t("No centro, como no Simba, ou no canto, como no Windows")
      Segmentado {
        opcoes: [{ valor: "center", rotulo: I18n.t("Centro") }, { valor: "right", rotulo: I18n.t("Canto") }]
        atual: pg.t && pg.t.relogio.secao === "right" ? "right" : "center"
        onEscolhido: function(v) { pg.tarefas(["relogio-secao", v], v === "right" ? I18n.t("Relógio no canto") : I18n.t("Relógio no centro")) }
      }
    }
  }

  // ── itens (avançado) ─────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Itens da barra"); detalhe: I18n.t("Reordene com as setas, mude de seção ou tire da barra.") }
  Ancora { chave: "barraItens" }
  RowLayout {
    Layout.fillWidth: true
    spacing: 10
    Repeater {
      model: [{ id: "left", titulo: I18n.t("Esquerda") }, { id: "center", titulo: I18n.t("Centro") }, { id: "right", titulo: I18n.t("Direita") }]
      delegate: Rectangle {
        id: secao
        required property var modelData
        readonly property var itens: pg.b ? pg.b.layout[modelData.id] : []
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignTop
        Layout.preferredHeight: colSec.implicitHeight + 20
        radius: Tema.raioGrande
        color: Tema.superficie
        border.width: 1
        border.color: Tema.linha
        ColumnLayout {
          id: colSec
          x: 10; y: 10
          width: parent.width - 20
          spacing: 4
          Texto { text: secao.modelData.titulo.toUpperCase(); color: Tema.texto3; font.pixelSize: Tema.tLegenda; font.letterSpacing: 1.4; font.weight: Font.DemiBold; Layout.bottomMargin: 4; Layout.leftMargin: 4 }
          Repeater {
            model: secao.itens
            delegate: Rectangle {
              id: it
              required property string modelData
              required property int index
              Layout.fillWidth: true
              Layout.preferredHeight: 38
              radius: Tema.raio
              color: mi.containsMouse ? Tema.superficieAlta : "transparent"
              Behavior on color { ColorAnimation { duration: Tema.rapido } }
              RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 4
                spacing: 6
                Glifo { g: pg.glifos[it.modelData] || Icones.widgets; tamanho: 15; color: Tema.texto2 }
                Texto { text: pg.nome(it.modelData); elide: Text.ElideRight; Layout.fillWidth: true }
                Row {
                  spacing: 0
                  visible: mi.containsMouse
                  Botao { compacto: true; tipo: "fantasma"; glifo: Icones.chevronUp; habilitado: it.index > 0 && !pg.ocupado
                    onClicado: pg.cmd(["simba-bar", "move", it.modelData, "--section", secao.modelData.id, "--index", String(it.index - 1)]) }
                  Botao { compacto: true; tipo: "fantasma"; glifo: Icones.chevronDown; habilitado: it.index < secao.itens.length - 1 && !pg.ocupado
                    onClicado: pg.cmd(["simba-bar", "move", it.modelData, "--section", secao.modelData.id, "--index", String(it.index + 1)]) }
                  Botao { compacto: true; tipo: "fantasma"; glifo: secao.modelData.id === "right" ? Icones.chevronLeft : Icones.chevronRight; habilitado: !pg.ocupado
                    onClicado: { var dest = secao.modelData.id === "left" ? "center" : (secao.modelData.id === "center" ? "right" : "center"); pg.cmd(["simba-bar", "move", it.modelData, "--section", dest]) } }
                  Botao { compacto: true; tipo: "fantasma"; glifo: Icones.eyeOff; habilitado: !pg.ocupado && it.modelData !== "simba.menu"
                    onClicado: {
                      var m = it.modelData
                      var argv = m === "tarefas" ? ["barra-tarefas", "desativar"]
                        : (m === "areas" || m === "simba.workspaces") ? ["barra-tarefas", "areas", "ocultar"]
                        : ["simba-plugin-disable", m]
                      pg.cmd(argv, pg.nome(m) + I18n.t(" removido da barra"))
                    } }
                }
              }
              MouseArea { id: mi; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton }
            }
          }
          Texto { visible: secao.itens.length === 0; text: I18n.t("Vazia"); color: Tema.texto3; Layout.leftMargin: 4 }
        }
      }
    }
  }

  Secao { titulo: I18n.t("Adicionar à barra"); visible: pg.disponiveis.length > 0 }
  Flow {
    Layout.fillWidth: true
    spacing: 8
    visible: pg.disponiveis.length > 0
    Repeater {
      model: pg.disponiveis
      delegate: Botao {
        required property var modelData
        glifo: Icones.plus
        texto: pg.nome(modelData.id)
        habilitado: !pg.ocupado
        onClicado: pg.cmd(["simba-plugin-enable", modelData.id], pg.nome(modelData.id) + " adicionado")
      }
    }
  }

  RowLayout {
    Layout.fillWidth: true
    Layout.topMargin: 16
    spacing: 8
    Texto { text: I18n.t("A barra é o simba-shell; a configuração fica em ~/.config/simba/shell.json e shell.toml."); color: Tema.texto3; font.pixelSize: Tema.tLegenda + 1; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    Botao { glifo: Icones.backupRestore; texto: I18n.t("Padrões da barra de tarefas"); visible: pg.tarefasAtiva; onClicado: pg.tarefas(["padroes"], I18n.t("Barra de tarefas restaurada")) }
    Botao { glifo: Icones.backupRestore; texto: I18n.t("Itens padrão"); onClicado: pg.cmd(["simba-bar", "defaults"], I18n.t("Itens padrão restaurados")) }
  }
}
