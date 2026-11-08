import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import Quickshell
import qs.Comum
import qs.Janela

Pagina {
  id: pg
  titulo: I18n.t("Personalização")
  subtitulo: I18n.t("Tema, papel de parede e tipografia. Tudo é aplicado na hora, no sistema inteiro.")

  property var temas: []
  property var fundos: ({ atual: "", grupos: [] })
  property var fontes: []
  property string fonteAtual: Tema.fonte
  property int textoTamanho: 12
  property string aplicandoTema: ""
  property string aplicandoFundo: ""
  property string filtro: "todos"
  // Temas de inicialização (Plymouth) estilo Windows 11 — /usr/bin/tema-boot
  property var temasBoot: []
  // ── ícones (bin/icones) ──
  property var icones: null                 // catálogo: famílias, prévias, tema ativo
  property string instalandoIcones: ""
  property var confirmarIcones: null        // família a instalar (pede confirmação)
  readonly property var escolhaIcones: Preferencias.obter("icones", { tema: "simba", cor: "auto", modo: "auto" })
  readonly property var familiaIcones: {
    if (!icones) return null
    var t = escolhaIcones.tema || "simba"
    return icones.familias.filter(function(f) { return f.id === t })[0] || null
  }
  // Amostras das cores dos temas de ícones (só para os botões de cor).
  readonly property var corAmostra: ({ standard: Tema.acento, black: "#2b2b2b", blue: "#3d8fe5", brown: "#9c6b4e", dracula: "#9b7ad8",
    green: "#4caf50", grey: "#8a8a8a", manjaro: "#26a269", nord: "#81a1c1", orange: "#f08a24", pink: "#e66da5",
    purple: "#8e5bd8", red: "#e5484d", ubuntu: "#e95420", yellow: "#e7b416", teal: "#1fa59a", magenta: "#b34cb3",
    olive: "#7b8a2c", prussiangreen: "#2a7f7a", sage: "#7a9a7e", wartybrown: "#9b7b56" })
  readonly property var nomeCor: ({ standard: I18n.t("Padrão"), black: I18n.t("Preto"), blue: I18n.t("Azul"), brown: I18n.t("Marrom"), dracula: I18n.t("Dracula"), green: I18n.t("Verde"),
    grey: I18n.t("Cinza"), manjaro: I18n.t("Manjaro"), nord: I18n.t("Nord"), orange: I18n.t("Laranja"), pink: I18n.t("Rosa"), purple: I18n.t("Roxo"), red: I18n.t("Vermelho"),
    ubuntu: I18n.t("Ubuntu"), yellow: I18n.t("Amarelo"), teal: I18n.t("Verde-água"), magenta: I18n.t("Magenta"), olive: I18n.t("Oliva"), prussiangreen: I18n.t("Verde-prússia"),
    sage: I18n.t("Sálvia"), wartybrown: I18n.t("Marrom Warty") })
  property string estiloBarra: "tema"
  function carregarIcones() {
    Sistema.json([Sistema.bin + "/icones", "catalogo"], function(v) { if (v) pg.icones = v })
    Sistema.json(["barra-tarefas", "estado"], function(v) { if (v && v.opcoes) pg.estiloBarra = v.opcoes.estiloIcones || "tema" })
  }
  function escolherIcones(mudanca) {
    var e = Object.assign({ tema: "simba", cor: "auto", modo: "auto" }, escolhaIcones, mudanca)
    Preferencias.definir("icones", e)
    Sistema.rodar([Sistema.bin + "/icones", "aplicar", JSON.stringify(e)], function(o) {
      pg.carregarIcones()
      Navegacao.confirmar(I18n.t("Ícones: ") + o.trim(), Icones.shapeOutline)
    })
  }
  function instalarIcones(f) {
    instalandoIcones = f.id
    Sistema.rodar([Sistema.bin + "/icones", "instalar", f.id], function(o, code) {
      if (f.fonte !== "oficial") {
        // AUR: o terminal fica aberto; confere de novo daqui a pouco
        Navegacao.confirmar(I18n.t("Instale no terminal que abriu (pede a senha)"), Icones.terminal)
        reverIcones.restart()
        return
      }
      pg.instalandoIcones = ""
      pg.carregarIcones()
      if (code === 0) pg.escolherIcones({ tema: f.id })
      else Navegacao.confirmar(I18n.t("Instalação cancelada"), Icones.alert)
    })
  }
  // Depois de mandar instalar do AUR: confere a cada 10 s, por até 10 min.
  Timer {
    id: reverIcones; interval: 10000; repeat: true
    property int voltas: 0
    onTriggered: {
      if (++voltas > 60 || !pg.instalandoIcones) { stop(); voltas = 0; pg.instalandoIcones = ""; return }
      Sistema.json([Sistema.bin + "/icones", "catalogo"], function(v) {
        if (!v) return
        pg.icones = v
        var f = v.familias.filter(function(x) { return x.id === pg.instalandoIcones })[0]
        if (f && f.instalado) { var id = f.id; pg.instalandoIcones = ""; reverIcones.stop(); pg.escolherIcones({ tema: id }) }
      })
    }
  }
  property string aplicandoBoot: ""
  property int previasBoot: 0
  property var confirmarBoot: null
  readonly property string cacheBoot: Quickshell.env("HOME") + "/.cache/temas-boot"

  function carregar() {
    Sistema.json([Sistema.ajudante, "temas"], function(v) { if (v) pg.temas = v })
    carregarFundos()
    Sistema.json([Sistema.ajudante, "fontes"], function(v) { if (v) pg.fontes = v })
    Sistema.sh("simba-font-current", function(o) { if (o.trim()) pg.fonteAtual = o.trim() })
    Sistema.sh("simba-display-text-size", function(o) {
      var m = o.match(/Text size:\s*(\d+)/i)
      if (m) pg.textoTamanho = Number(m[1])
    })
  }
  function carregarFundos() {
    Sistema.json([Sistema.ajudante, "fundos"], function(v) {
      if (v && JSON.stringify(v) !== JSON.stringify(pg.fundos)) pg.fundos = v
    })
  }
  Component.onCompleted: { carregar(); carregarBoot(); carregarIcones() }
  function carregarBoot() {
    Sistema.sh("tema-boot listar", function(o) {
      pg.temasBoot = o.trim().split("\n").filter(function(l) { return l }).map(function(l) {
        var c = l.split("|"); return { id: c[0], titulo: c[1], ativo: c[2] === "1" }
      })
    })
    // Prévias: geradas uma vez; a "Vidro" sempre (usa o papel de parede atual).
    // Refaz a prévia se faltar ou se o modelo do tema mudou; a "Vidro" vem depois (é mais lenta).
    var gerar = I18n.t("d=\"$HOME/.cache/temas-boot\"; m=\"$HOME/.local/share/temas-boot/tema.script\"; mkdir -p \"$d\"; ")
    Sistema.sh(gerar + "for i in $(tema-boot listar | cut -d'|' -f1); do [[ $i == win11-vidro ]] && continue; [[ -f $d/$i.png && $d/$i.png -nt $m ]] || tema-boot previa $i \"$d/$i.png\"; done", function() {
      pg.previasBoot++
      Sistema.sh(gerar + "tema-boot previa win11-vidro \"$d/win11-vidro.png\"", function() { pg.previasBoot++ })
    })
  }
  function aplicarBoot(id, titulo) {
    if (aplicandoBoot) return
    aplicandoBoot = id
    Sistema.rodar(["tema-boot", "aplicar", id], function(o, code) {
      pg.aplicandoBoot = ""
      pg.carregarBoot()
      if (code === 0) Navegacao.confirmar(I18n.t("Tela de inicialização: ") + titulo, Icones.monitorLock)
      else Navegacao.confirmar(I18n.t("Não foi possível aplicar (senha cancelada?)"), Icones.alert)
    })
  }
  Connections {
    target: Tema
    function onTemaTrocado() { recarregarTudo.restart() }
  }
  Timer { id: recarregarTudo; interval: 900; onTriggered: { pg.aplicandoTema = ""; pg.carregar() } }
  Timer { interval: 3000; running: true; repeat: true; onTriggered: pg.carregarFundos() }

  function aplicarTema(slug, nome) {
    if (aplicandoTema) return
    aplicandoTema = slug
    Sistema.rodar(["simba-theme-set", slug], function(o, code) {
      pg.aplicandoTema = ""
      if (code === 0) Navegacao.confirmar(I18n.t("Tema ") + nome + " aplicado", Icones.palette)
      else Navegacao.confirmar(I18n.t("Não foi possível aplicar o tema"), Icones.alert)
    })
  }
  function aplicarFundo(caminho) {
    aplicandoFundo = caminho
    Sistema.rodar(["simba-theme-bg-set", caminho], function(o, code) {
      pg.aplicandoFundo = ""
      pg.carregarFundos()
      if (code === 0) Navegacao.confirmar(I18n.t("Papel de parede alterado"), Icones.wallpaper)
    })
  }
  function escolherImagem() {
    Sistema.rodar(["simba-file-select", "--title", I18n.t("Escolher papel de parede"), "--extensions", "png jpg jpeg webp bmp gif"], function(o, code) {
      var p = o.trim().split("\n")[0]
      if (code === 0 && p) pg.aplicarFundo(decodeURIComponent(p.replace(/^file:\/\//, "")))
    })
  }

  readonly property var temaAtual: {
    for (var i = 0; i < temas.length; i++) if (temas[i].slug === Tema.nome) return temas[i]
    return null
  }
  readonly property var temasFiltrados: temas.filter(function(t) {
    return filtro === "todos" || (filtro === "escuros" ? t.modo !== "light" : t.modo === "light")
  })

  // ── grades responsivas: colunas pela largura, nunca pelo número de itens ──
  readonly property int vao: 12
  function colunas(larg, minimo, gap) { return Math.max(1, Math.floor((larg + gap) / (minimo + gap))) }
  function largura(larg, minimo, gap) { var c = colunas(larg, minimo, gap); return Math.floor((larg - (c - 1) * gap) / c) }

  // ── remoções (tema da pessoa, papel de parede) ──
  property var confirmarRemoverTema: null
  property var confirmarRemoverFundo: null
  function removerTema(t) {
    Sistema.json([Sistema.bin + "/loja-temas", "remover", t.slug], function(v, code) {
      if (code === 0) Navegacao.confirmar(I18n.t("Tema removido: ") + t.nome, Icones.deleteOutline)
      else Navegacao.confirmar(v && v.erro ? v.erro : I18n.t("Não foi possível remover"), Icones.alert)
      pg.carregar()
      if (pg.lojaAberta) pg.carregarLoja(false)
    })
  }
  function removerFundo(f) {
    Sistema.rodar([Sistema.bin + "/fundos", "remover", f.caminho], function(o, code, err) {
      if (code === 0) Navegacao.confirmar(o.trim() || I18n.t("Papel de parede excluído"), Icones.deleteOutline)
      else Navegacao.confirmar((err || "").trim() || I18n.t("Não foi possível excluir"), Icones.alert)
      pg.carregarFundos()
    })
  }

  // ── loja: temas da comunidade (bin/loja-temas) ──
  property bool lojaAberta: false
  property var loja: null                  // { temas: [...] }
  property string lojaErro: ""
  property bool lojaCarregando: false
  property string lojaBusca: ""
  property string lojaFiltro: "todos"
  property int lojaLimite: 24
  property var lojaPrevias: ({})            // repo → caminho local ("" = sem prévia)
  property string instalandoLoja: ""
  readonly property var lojaFiltrados: {
    if (!loja) return []
    var b = lojaBusca.trim().toLowerCase()
    return loja.temas.filter(function(t) {
      if (lojaFiltro === "escuros" && t.modo === "light") return false
      if (lojaFiltro === "claros" && t.modo !== "light") return false
      return !b || t.nome.toLowerCase().indexOf(b) >= 0 || t.autor.toLowerCase().indexOf(b) >= 0
    })
  }
  readonly property var lojaVisiveis: lojaFiltrados.slice(0, lojaLimite)
  onLojaVisiveisChanged: pedirPrevias()
  function carregarLoja(renovar) {
    lojaCarregando = true
    lojaErro = ""
    Sistema.json([Sistema.bin + "/loja-temas", "catalogo"].concat(renovar ? ["--renovar"] : []), function(v, code) {
      pg.lojaCarregando = false
      if (v && v.temas) pg.loja = v
      else pg.lojaErro = v && v.erro ? v.erro : I18n.t("Não foi possível carregar a lista de temas")
    })
  }
  function pedirPrevias() {
    var faltam = lojaVisiveis.filter(function(t) { return !(t.repo in pg.lojaPrevias) })
    if (!faltam.length) return
    var m = Object.assign({}, lojaPrevias)
    faltam.forEach(function(t) { m[t.repo] = null })     // pedido em andamento
    lojaPrevias = m
    Sistema.json([Sistema.bin + "/loja-temas", "previas"].concat(faltam.map(function(t) { return t.repo + "@" + t.ramo })), function(v) {
      var n = Object.assign({}, pg.lojaPrevias)
      faltam.forEach(function(t) { n[t.repo] = v && (t.repo in v) ? v[t.repo] : "" })
      pg.lojaPrevias = n
    })
  }
  function instalarDaLoja(t) {
    if (instalandoLoja) return
    if (t.instalado) { if (t.instalado !== Tema.nome) aplicarTema(t.instalado, t.nome); return }
    instalandoLoja = t.repo
    Sistema.json([Sistema.bin + "/loja-temas", "instalar", t.repo], function(v, code) {
      pg.instalandoLoja = ""
      if (code === 0 && v && v.slug) {
        pg.carregar()
        pg.carregarLoja(false)
        pg.aplicarTema(v.slug, t.nome)
      } else Navegacao.confirmar(v && v.erro ? v.erro : I18n.t("Não foi possível instalar"), Icones.alert)
    })
  }

  // ── topo: miniatura viva da área de trabalho ─────────────────────────────
  Rectangle {
    id: hero
    readonly property bool estreito: width < 640
    Layout.fillWidth: true
    Layout.preferredHeight: heroGrade.implicitHeight + 32
    radius: Tema.raioGrande
    color: Tema.superficie
    border.width: 1
    border.color: Tema.linha

    GridLayout {
      id: heroGrade
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.margins: 16
      columns: hero.estreito ? 1 : 2
      columnSpacing: 22
      rowSpacing: 14

      Item {
        Layout.fillWidth: hero.estreito
        Layout.preferredWidth: hero.estreito ? -1 : Math.min(340, hero.width * 0.4)
        Layout.preferredHeight: hero.estreito ? Math.round(width * 0.5) : 196
        Rectangle {
          anchors.fill: parent
          radius: Tema.raio + 2
          color: Tema.fundo
          clip: true
          border.width: 1
          border.color: Tema.linha
          Image {
            anchors.fill: parent
            source: pg.fundos.atual ? "file://" + pg.fundos.atual : ""
            fillMode: Image.PreserveAspectCrop
            sourceSize.width: 640
            asynchronous: true
            opacity: status === Image.Ready ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 500 } }
          }
          Rectangle {
            width: parent.width; height: 12
            color: Tema.alfa(Tema.fundo, 0.92)
            Row {
              x: 6; anchors.verticalCenter: parent.verticalCenter; spacing: 3
              Repeater { model: 4; Rectangle { required property int index; width: 5; height: 5; radius: Tema.raio > 0 ? 2.5 : 0; color: index === 0 ? Tema.texto : Tema.texto3 } }
            }
            Texto { anchors.centerIn: parent; text: Qt.formatTime(new Date(), "HH:mm"); font.pixelSize: 7; color: Tema.texto }
          }
          Rectangle {
            x: 8; y: 20; width: parent.width * 0.55 - 12; height: parent.height - 28
            radius: Math.min(Hypr.valor("decoration:rounding", 0), 10) * 0.5
            color: Tema.alfa(Tema.fundo, Hypr.valor("decoration:active_opacity", 1))
            border.width: Math.max(1, Hypr.valor("general:border_size", 2) * 0.6)
            border.color: Tema.acento
            Column {
              x: 8; y: 8; spacing: 4
              Repeater { model: 6; Rectangle { required property int index; width: [60, 90, 44, 70, 30, 80][index]; height: 4; radius: 2; color: [Tema.cor("green", Tema.texto), Tema.texto2, Tema.cor("blue", Tema.texto3), Tema.texto3, Tema.cor("yellow", Tema.texto2), Tema.texto3][index] } }
            }
          }
          Rectangle {
            x: parent.width * 0.55; y: 20; width: parent.width * 0.45 - 8; height: parent.height - 28
            radius: Math.min(Hypr.valor("decoration:rounding", 0), 10) * 0.5
            color: Tema.alfa(Tema.fundo, Hypr.valor("decoration:inactive_opacity", 1))
            border.width: Math.max(1, Hypr.valor("general:border_size", 2) * 0.6)
            border.color: Tema.alfa(Tema.texto, 0.25)
            Rectangle { x: 8; y: 8; width: parent.width - 16; height: parent.height * 0.4; radius: 2; color: Tema.superficieAlta }
            Rectangle { x: 8; y: parent.height * 0.4 + 14; width: parent.width * 0.6; height: 4; radius: 2; color: Tema.texto3 }
          }
        }
      }

      ColumnLayout {
        Layout.fillWidth: true
        Layout.fillHeight: true
        spacing: 6
        Texto { text: I18n.t("TEMA ATUAL"); color: Tema.texto3; font.pixelSize: Tema.tLegenda; font.letterSpacing: 1.5; font.weight: Font.DemiBold }
        Texto {
          text: pg.temaAtual ? pg.temaAtual.nome : Tema.nome
          font.pixelSize: Tema.tDisplay
          font.weight: Font.Bold
          font.letterSpacing: -1
          Layout.fillWidth: true
          elide: Text.ElideRight
        }
        Texto { text: (Tema.escuro ? I18n.t("Escuro") : I18n.t("Claro")) + " · " + Tema.fonte; color: Tema.texto2; Layout.fillWidth: true; elide: Text.ElideRight }
        Flow {
          Layout.topMargin: 6
          Layout.fillWidth: true
          spacing: 6
          Repeater {
            model: ["background", "foreground", "accent", "red", "green", "yellow", "blue", "magenta", "cyan"]
            Rectangle {
              required property string modelData
              required property int index
              width: 22; height: 22
              radius: Tema.raio > 0 ? 11 : 0
              color: Tema.cor(modelData, "transparent")
              border.width: 1
              border.color: Tema.linhaForte
              scale: 0
              Component.onCompleted: crescer.start()
              NumberAnimation on scale { id: crescer; running: false; from: 0; to: 1; duration: 420 + index * 55; easing.type: Easing.OutBack }
            }
          }
        }
        Item { Layout.fillHeight: true; Layout.minimumHeight: 8 }
        Flow {
          Layout.fillWidth: true
          spacing: 8
          Botao {
            glifo: Icones.wallpaper; texto: I18n.t("Próximo papel de parede"); tipo: "primario"
            onClicado: Sistema.rodar(["simba-theme-bg-next"], function() { pg.carregarFundos() })
          }
          Botao { glifo: Icones.folderOpen; texto: I18n.t("Escolher imagem…"); onClicado: pg.escolherImagem() }
        }
      }
    }
  }

  // ── temas instalados ─────────────────────────────────────────────────────
  Secao {
    titulo: I18n.t("Tema")
    detalhe: pg.temas.length + I18n.t(" temas instalados. Muda cores do shell, terminais, navegador, editor e bordas.")
  }
  Ancora { chave: "tema" }
  Flow {
    Layout.fillWidth: true
    spacing: 8
    Segmentado {
      opcoes: [{ valor: "todos", rotulo: I18n.t("Todos") }, { valor: "escuros", rotulo: I18n.t("Escuros"), glifo: Icones.weatherNight }, { valor: "claros", rotulo: I18n.t("Claros"), glifo: Icones.whiteBalanceSunny }]
      atual: pg.filtro
      onEscolhido: function(v) { pg.filtro = v }
    }
    Botao {
      glifo: Icones.storefrontOutline
      texto: pg.lojaAberta ? I18n.t("Fechar a loja") : I18n.t("Mais temas…")
      tipo: pg.lojaAberta ? "normal" : "primario"
      onClicado: { pg.lojaAberta = !pg.lojaAberta; if (pg.lojaAberta && !pg.loja) pg.carregarLoja(false) }
    }
  }

  Flow {
    id: gradeTemas
    Layout.fillWidth: true
    Layout.topMargin: 4
    spacing: pg.vao
    readonly property int larguraItem: pg.largura(width, 200, pg.vao)
    Repeater {
      model: pg.temasFiltrados
      delegate: Item {
        id: cart
        required property var modelData
        readonly property bool atual: modelData.slug === Tema.nome
        readonly property bool aplicando: pg.aplicandoTema === modelData.slug
        width: gradeTemas.larguraItem
        height: Math.round((width - 10) * 0.625) + 46
        scale: ma.pressed ? 0.97 : (ma.containsMouse ? 1.015 : 1)
        z: ma.containsMouse ? 2 : 1
        Behavior on scale { NumberAnimation { duration: Tema.medio; easing.type: Easing.OutBack } }

        Rectangle {
          id: caixa
          anchors.fill: parent
          radius: Tema.raioGrande
          color: Tema.superficie
          border.width: cart.atual ? 2 : 1
          border.color: cart.atual ? Tema.realce : (ma.containsMouse ? Tema.linhaForte : Tema.linha)
          Sombra { alvo: caixa; intensidade: ma.containsMouse ? 0.9 : 0; deslocamento: 8; Behavior on intensidade { NumberAnimation { duration: Tema.medio } } }

          Item {
            x: 5; y: 5
            width: parent.width - 10
            height: parent.height - 46
            Image {
              id: img
              anchors.fill: parent
              source: cart.modelData.preview ? "file://" + cart.modelData.preview : ""
              sourceSize.width: 480
              fillMode: Image.PreserveAspectCrop
              asynchronous: true
              visible: false
            }
            Rectangle { id: mascara; anchors.fill: parent; radius: Math.max(0, Tema.raioGrande - 4); visible: false; layer.enabled: true }
            MultiEffect {
              anchors.fill: parent
              source: img
              maskEnabled: true
              maskSource: mascara
              opacity: img.status === Image.Ready ? 1 : 0
              Behavior on opacity { NumberAnimation { duration: 400 } }
            }
            Rectangle {
              anchors.fill: parent
              radius: Math.max(0, Tema.raioGrande - 4)
              color: cart.modelData.cores.background || "#000"
              visible: img.status !== Image.Ready
            }
            Rectangle {
              anchors.fill: parent
              radius: Math.max(0, Tema.raioGrande - 4)
              color: Tema.alfa(Tema.janela, 0.7)
              visible: cart.aplicando
              Texto { anchors.centerIn: parent; text: I18n.t("Aplicando…"); font.weight: Font.DemiBold }
            }
          }

          RowLayout {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: 10
            anchors.bottomMargin: 9
            height: 26
            spacing: 6
            Texto {
              text: cart.modelData.nome
              font.weight: cart.atual ? Font.DemiBold : Font.Medium
              elide: Text.ElideRight
              Layout.fillWidth: true
            }
            Row {
              spacing: -4
              Repeater {
                model: ["background", "accent", "red", "green", "blue"]
                Rectangle {
                  required property string modelData
                  width: 14; height: 14; radius: Tema.raio > 0 ? 7 : 0
                  color: cart.modelData.cores[modelData] || "transparent"
                  border.width: 1
                  border.color: Tema.superficie
                }
              }
            }
            Glifo { visible: cart.atual; g: Icones.checkboxMarkedCircle; tamanho: 15; color: Tema.realce }
          }
        }
        MouseArea {
          id: ma
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: if (!cart.atual) pg.aplicarTema(cart.modelData.slug, cart.modelData.nome)
        }
        // lixeira: só temas que a pessoa instalou, e não o que está em uso
        Rectangle {
          visible: cart.modelData.usuario && !cart.atual && (ma.containsMouse || lixo.containsMouse)
          anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 11
          width: 28; height: 28; radius: Tema.raio > 0 ? 14 : 0
          color: lixo.containsMouse ? Tema.perigo : Tema.alfa(Tema.janela, 0.85)
          Glifo { anchors.centerIn: parent; g: Icones.deleteOutline; tamanho: 15; color: lixo.containsMouse ? "#ffffff" : Tema.texto }
          MouseArea { id: lixo; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pg.confirmarRemoverTema = cart.modelData }
        }
      }
    }
  }
  Cartao {
    visible: !!pg.confirmarRemoverTema
    Linha {
      glifo: Icones.deleteOutline
      titulo: pg.confirmarRemoverTema ? I18n.t("Remover o tema “") + pg.confirmarRemoverTema.nome + "”?" : ""
      descricao: I18n.t("Apaga a pasta do tema em ~/.config/simba/themes. Dá para instalar de novo pela loja.")
      Botao { texto: I18n.t("Cancelar"); tipo: "fantasma"; onClicado: pg.confirmarRemoverTema = null }
      Botao { texto: I18n.t("Remover"); tipo: "perigo"; onClicado: { var t = pg.confirmarRemoverTema; pg.confirmarRemoverTema = null; pg.removerTema(t) } }
    }
  }

  // ── loja de temas da comunidade ──────────────────────────────────────────
  Rectangle {
    id: lojaCaixa
    visible: pg.lojaAberta
    Layout.fillWidth: true
    Layout.topMargin: 10
    Layout.preferredHeight: lojaCol.implicitHeight + 32
    radius: Tema.raioGrande
    color: Tema.superficie
    border.width: 1
    border.color: Tema.linha

    ColumnLayout {
      id: lojaCol
      anchors.left: parent.left
      anchors.right: parent.right
      anchors.top: parent.top
      anchors.margins: 16
      spacing: 12

      RowLayout {
        Layout.fillWidth: true
        spacing: 12
        Glifo { g: Icones.storefrontOutline; tamanho: 26; color: Tema.realce; Layout.alignment: Qt.AlignTop }
        ColumnLayout {
          Layout.fillWidth: true
          spacing: 2
          Texto { text: I18n.t("Temas da comunidade"); font.pixelSize: Tema.tSubtitulo; font.weight: Font.DemiBold }
          Texto {
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
            color: Tema.texto3
            font.pixelSize: Tema.tLegenda + 1
            text: (pg.loja ? pg.loja.temas.length + I18n.t(" temas feitos por outras pessoas e publicados no GitHub. ") : "")
                  + I18n.t("Clique para instalar e aplicar; o tema fica em ~/.config/simba/themes.")
          }
        }
        Botao {
          compacto: true; tipo: "fantasma"; glifo: Icones.refresh
          Layout.alignment: Qt.AlignTop
          habilitado: !pg.lojaCarregando
          onClicado: pg.carregarLoja(true)
        }
      }

      Flow {
        Layout.fillWidth: true
        spacing: 8
        Campo {
          width: Math.min(320, lojaCol.width)
          glifo: Icones.magnify
          dica: I18n.t("Buscar por nome ou autor")
          onTextChanged: { pg.lojaBusca = text; pg.lojaLimite = 24 }
        }
        Segmentado {
          opcoes: [{ valor: "todos", rotulo: I18n.t("Todos") }, { valor: "escuros", rotulo: I18n.t("Escuros"), glifo: Icones.weatherNight }, { valor: "claros", rotulo: I18n.t("Claros"), glifo: Icones.whiteBalanceSunny }]
          atual: pg.lojaFiltro
          onEscolhido: function(v) { pg.lojaFiltro = v; pg.lojaLimite = 24 }
        }
      }

      Texto {
        visible: pg.lojaCarregando || pg.lojaErro !== "" || (!!pg.loja && pg.lojaFiltrados.length === 0)
        Layout.fillWidth: true
        Layout.topMargin: 8
        Layout.bottomMargin: 8
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
        color: pg.lojaErro ? Tema.perigo : Tema.texto3
        text: pg.lojaCarregando ? I18n.t("Procurando temas no GitHub… (a primeira vez leva uns 15 segundos)")
              : pg.lojaErro ? pg.lojaErro : I18n.t("Nenhum tema encontrado")
      }

      Flow {
        id: gradeLoja
        visible: !pg.lojaCarregando
        Layout.fillWidth: true
        spacing: pg.vao
        readonly property int larguraItem: pg.largura(width, 200, pg.vao)
        Repeater {
          model: pg.lojaVisiveis
          delegate: Item {
            id: lt
            required property var modelData
            readonly property string previa: pg.lojaPrevias[modelData.repo] || ""
            readonly property bool instalando: pg.instalandoLoja === modelData.repo
            readonly property bool emUso: !!modelData.instalado && modelData.instalado === Tema.nome
            width: gradeLoja.larguraItem
            height: Math.round((width - 10) * 0.625) + 62
            scale: ml.pressed ? 0.97 : (ml.containsMouse ? 1.015 : 1)
            z: ml.containsMouse ? 2 : 1
            Behavior on scale { NumberAnimation { duration: Tema.medio; easing.type: Easing.OutBack } }

            Rectangle {
              id: lcaixa
              anchors.fill: parent
              radius: Tema.raioGrande
              color: Tema.superficieAlta
              border.width: lt.emUso ? 2 : 1
              border.color: lt.emUso ? Tema.realce : (ml.containsMouse ? Tema.linhaForte : Tema.linha)

              Item {
                id: lprev
                x: 5; y: 5
                width: parent.width - 10
                height: parent.height - 62
                Image {
                  id: limg
                  anchors.fill: parent
                  source: lt.previa ? "file://" + lt.previa : ""
                  sourceSize.width: 480
                  fillMode: Image.PreserveAspectCrop
                  asynchronous: true
                  visible: false
                }
                Rectangle { id: lmasc; anchors.fill: parent; radius: Math.max(0, Tema.raioGrande - 4); visible: false; layer.enabled: true }
                // sem prévia: um desenho com as cores do tema
                Rectangle {
                  anchors.fill: parent
                  radius: Math.max(0, Tema.raioGrande - 4)
                  color: lt.modelData.cores.background || "#000"
                  visible: limg.status !== Image.Ready
                  clip: true
                  Column {
                    x: 12; y: 12; spacing: 6
                    visible: pg.lojaPrevias[lt.modelData.repo] === ""
                    Repeater {
                      model: ["accent", "foreground", "green", "blue", "yellow", "red", "magenta"]
                      Rectangle {
                        required property string modelData
                        required property int index
                        width: [70, 110, 50, 90, 40, 80, 60][index] * lprev.width / 240; height: 5; radius: 2.5
                        color: lt.modelData.cores[modelData] || lt.modelData.cores.foreground || "#888"
                      }
                    }
                  }
                  Texto {
                    anchors.centerIn: parent
                    visible: pg.lojaPrevias[lt.modelData.repo] === null || pg.lojaPrevias[lt.modelData.repo] === undefined
                    text: I18n.t("Carregando prévia…")
                    color: lt.modelData.cores.foreground || Tema.texto3
                    opacity: 0.6
                    font.pixelSize: Tema.tLegenda
                  }
                }
                MultiEffect {
                  anchors.fill: parent
                  source: limg
                  maskEnabled: true
                  maskSource: lmasc
                  opacity: limg.status === Image.Ready ? 1 : 0
                  Behavior on opacity { NumberAnimation { duration: 400 } }
                }
                Rectangle {
                  anchors.fill: parent
                  radius: Math.max(0, Tema.raioGrande - 4)
                  color: Tema.alfa(Tema.janela, 0.75)
                  visible: lt.instalando
                  Texto { anchors.centerIn: parent; text: I18n.t("Instalando…"); font.weight: Font.DemiBold }
                }
                // selo "instalado"
                Rectangle {
                  visible: !!lt.modelData.instalado && !lt.instalando
                  anchors.left: parent.left; anchors.top: parent.top; anchors.margins: 6
                  width: selo.implicitWidth + 16; height: 22; radius: Tema.raio > 0 ? 11 : 0
                  color: Tema.realce
                  Texto { id: selo; anchors.centerIn: parent; text: lt.emUso ? I18n.t("Em uso") : I18n.t("Instalado"); color: Tema.sobreRealce; font.pixelSize: Tema.tLegenda; font.weight: Font.DemiBold }
                }
              }

              ColumnLayout {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 10
                anchors.bottomMargin: 8
                spacing: 1
                RowLayout {
                  Layout.fillWidth: true
                  spacing: 6
                  Texto { text: lt.modelData.nome; font.weight: Font.Medium; elide: Text.ElideRight; Layout.fillWidth: true }
                  Row {
                    spacing: -4
                    Repeater {
                      model: ["background", "accent", "red", "green", "blue"]
                      Rectangle {
                        required property string modelData
                        width: 14; height: 14; radius: Tema.raio > 0 ? 7 : 0
                        color: lt.modelData.cores[modelData] || "transparent"
                        border.width: 1
                        border.color: Tema.superficieAlta
                      }
                    }
                  }
                }
                RowLayout {
                  Layout.fillWidth: true
                  spacing: 4
                  Texto { text: I18n.t("por ") + lt.modelData.autor; color: Tema.texto3; font.pixelSize: Tema.tLegenda; elide: Text.ElideRight; Layout.fillWidth: true }
                  Glifo { g: Icones.starOutline; tamanho: 12; color: Tema.texto3 }
                  Texto { text: lt.modelData.estrelas; color: Tema.texto3; font.pixelSize: Tema.tLegenda }
                }
              }
            }
            MouseArea {
              id: ml
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: pg.instalarDaLoja(lt.modelData)
            }
            // abrir a página do repositório
            Rectangle {
              visible: ml.containsMouse || gh.containsMouse
              anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 11
              width: 28; height: 28; radius: Tema.raio > 0 ? 14 : 0
              color: gh.containsMouse ? Tema.realce : Tema.alfa(Tema.janela, 0.85)
              Glifo { anchors.centerIn: parent; g: Icones.github; tamanho: 15; color: gh.containsMouse ? Tema.sobreRealce : Tema.texto }
              MouseArea { id: gh; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: Sistema.solto(["xdg-open", "https://github.com/" + lt.modelData.repo]) }
            }
          }
        }
      }

      Botao {
        visible: !pg.lojaCarregando && pg.lojaFiltrados.length > pg.lojaLimite
        Layout.alignment: Qt.AlignHCenter
        texto: I18n.t("Mostrar mais (") + (pg.lojaFiltrados.length - pg.lojaLimite) + I18n.t(" restantes)")
        onClicado: pg.lojaLimite += 24
      }
    }
  }

  // ── papéis de parede ─────────────────────────────────────────────────────
  Secao {
    titulo: I18n.t("Papel de parede")
    detalhe: I18n.t("Clique numa imagem para usá-la; passe o mouse para excluir. Os do tema mudam junto quando você troca de tema.")
  }
  Ancora { chave: "papel" }

  Repeater {
    model: pg.fundos.grupos
    delegate: ColumnLayout {
      id: grupo
      required property var modelData
      Layout.fillWidth: true
      spacing: 8
      Texto { text: grupo.modelData.titulo; color: Tema.texto2; font.pixelSize: Tema.tLegenda + 1; Layout.topMargin: 4 }
      Flow {
        id: gradeFundos
        Layout.fillWidth: true
        spacing: 8
        readonly property int larguraItem: pg.largura(width, 150, 8)
        Repeater {
          model: grupo.modelData.itens
          delegate: Item {
            id: fundo
            required property var modelData
            readonly property bool atual: modelData.real === pg.fundos.atual || modelData.caminho === pg.fundos.atual
            width: gradeFundos.larguraItem
            height: Math.round(width * 0.625)
            scale: mf.pressed ? 0.96 : (mf.containsMouse ? 1.04 : 1)
            z: mf.containsMouse ? 2 : 1
            Behavior on scale { NumberAnimation { duration: Tema.medio; easing.type: Easing.OutBack } }
            Image {
              id: fImg
              anchors.fill: parent
              anchors.margins: 3
              source: "file://" + fundo.modelData.caminho
              sourceSize.width: 360
              fillMode: Image.PreserveAspectCrop
              asynchronous: true
              visible: false
            }
            Rectangle { id: fm; anchors.fill: fImg; radius: Tema.raio; visible: false; layer.enabled: true }
            MultiEffect {
              anchors.fill: fImg; source: fImg; maskEnabled: true; maskSource: fm
              opacity: fImg.status === Image.Ready ? 1 : 0
              Behavior on opacity { NumberAnimation { duration: 350 } }
            }
            Rectangle {
              anchors.fill: parent
              radius: Tema.raio + 3
              color: "transparent"
              border.width: fundo.atual ? 2 : (mf.containsMouse ? 1 : 0)
              border.color: fundo.atual ? Tema.realce : Tema.linhaForte
            }
            Rectangle {
              visible: fundo.atual || pg.aplicandoFundo === fundo.modelData.caminho
              anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 8
              width: 22; height: 22; radius: Tema.raio > 0 ? 11 : 0
              color: Tema.realce
              Glifo { anchors.centerIn: parent; g: pg.aplicandoFundo === fundo.modelData.caminho ? Icones.timer : Icones.check; tamanho: 13; color: Tema.sobreRealce }
            }
            MouseArea { id: mf; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: if (!fundo.atual) pg.aplicarFundo(fundo.modelData.caminho) }
            Rectangle {
              visible: fundo.modelData.removivel && !fundo.atual && (mf.containsMouse || lixoF.containsMouse)
              anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 8
              width: 26; height: 26; radius: Tema.raio > 0 ? 13 : 0
              color: lixoF.containsMouse ? Tema.perigo : Tema.alfa(Tema.janela, 0.85)
              Glifo { anchors.centerIn: parent; g: Icones.deleteOutline; tamanho: 14; color: lixoF.containsMouse ? "#ffffff" : Tema.texto }
              MouseArea { id: lixoF; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pg.confirmarRemoverFundo = fundo.modelData }
            }
          }
        }
      }
    }
  }
  Cartao {
    visible: !!pg.confirmarRemoverFundo
    Linha {
      glifo: Icones.deleteOutline
      titulo: I18n.t("Excluir este papel de parede?")
      descricao: !pg.confirmarRemoverFundo ? ""
                 : /\/usr\/share\/backgrounds\/simba\/|\/simba\/sistema\/papeis\//.test(pg.confirmarRemoverFundo.real)
                 ? I18n.t("É um papel do Simba: some de todos os temas e não volta quando o tema muda.")
                 : I18n.t("A imagem vai para a lixeira (dá para recuperar).")
      Botao { texto: I18n.t("Cancelar"); tipo: "fantasma"; onClicado: pg.confirmarRemoverFundo = null }
      Botao { texto: I18n.t("Excluir"); tipo: "perigo"; onClicado: { var f = pg.confirmarRemoverFundo; pg.confirmarRemoverFundo = null; pg.removerFundo(f) } }
    }
  }

  Cartao {
    Layout.topMargin: 6
    Linha {
      chave: "papelProximo"
      glifo: Icones.imageMultiple
      titulo: I18n.t("Próximo papel de parede")
      descricao: I18n.t("Também pelo clique direito na área de trabalho")
      Botao { texto: I18n.t("Trocar"); onClicado: Sistema.rodar(["simba-theme-bg-next"], function() { pg.carregarFundos() }) }
    }
    Linha {
      chave: "papelEscolher"
      glifo: Icones.folderOpen
      titulo: I18n.t("Escolher imagem do computador")
      descricao: I18n.t("Qualquer imagem PNG, JPG ou WebP")
      Botao { texto: I18n.t("Procurar…"); onClicado: pg.escolherImagem() }
    }
  }

  // ── typography ───────────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Tipografia") }
  Cartao {
    Linha {
      chave: "fonte"
      glifo: Icones.formatFont
      titulo: I18n.t("Fonte do sistema")
      descricao: I18n.t("Barra, menus, notificações, terminais e este app")
      Selecao {
        width: 250
        opcoes: pg.fontes.map(function(f) { return { valor: f, rotulo: f } })
        atual: pg.fonteAtual
        onEscolhido: function(v) {
          pg.fonteAtual = v
          Sistema.rodar(["simba-font-set", v], function(o, code) {
            Tema.recarregar()
            if (code === 0) Navegacao.confirmar(I18n.t("Fonte alterada para ") + v, Icones.formatFont)
          })
        }
      }
    }
    Item {
      Layout.fillWidth: true
      Layout.preferredHeight: 76
      Rectangle { anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 16; anchors.rightMargin: 16; height: 1; color: Tema.linha }
      Column {
        anchors.verticalCenter: parent.verticalCenter
        x: 64
        spacing: 2
        Texto { text: I18n.t("Aa Bb Cc Çç 0123 → ≠ ≥ {}"); font.family: pg.fonteAtual; font.pixelSize: 22 }
        Texto { text: I18n.t("O rápido jabuti xereta viu a dúzia de pôneis felizes."); font.family: pg.fonteAtual; color: Tema.texto2 }
      }
    }
    Linha {
      chave: "textoTamanho"
      glifo: Icones.formatSize
      titulo: I18n.t("Tamanho do texto")
      descricao: I18n.t("Shell, apps GTK e terminais juntos · padrão 12 px")
      Botao {
        compacto: true; tipo: "fantasma"; glifo: Icones.undo
        visible: pg.textoTamanho !== 12
        onClicado: Sistema.rodar(["simba-display-text-size", "reset"], function() { pg.textoTamanho = 12 })
      }
      Deslizante {
        width: 220
        de: 9; ate: 20; passo: 1
        valor: pg.textoTamanho
        sufixo: " px"
        onSolto: function(v) {
          Sistema.rodar(["simba-display-text-size", String(v)], function(o, code) {
            pg.textoTamanho = v
            if (code === 0) Navegacao.confirmar(I18n.t("Texto em ") + v + " px", Icones.formatSize)
          })
        }
      }
    }
  }

  // ── ícones ───────────────────────────────────────────────────────────────
  Secao {
    titulo: I18n.t("Ícones")
    detalhe: I18n.t("Barra de tarefas, menu Iniciar, Arquivos e apps. “Do tema” segue o tema atual; os outros guardam a sua escolha quando o tema muda.")
  }
  Ancora { chave: "icones" }
  Flow {
    Layout.fillWidth: true
    spacing: 10
    Repeater {
      model: pg.icones ? [{ id: "simba", nome: I18n.t("Do tema"), desc: I18n.t("O do tema atual"), instalado: true,
                            previa: pg.icones.doTema.previa, variante: pg.icones.doTema.variante, fonte: "" }].concat(pg.icones.familias) : []
      delegate: Item {
        id: fi
        required property var modelData
        readonly property bool ativo: (pg.escolhaIcones.tema || "simba") === modelData.id
        readonly property bool instalando: pg.instalandoIcones === modelData.id
        width: 196; height: 136
        scale: mi.pressed ? 0.96 : (mi.containsMouse ? 1.03 : 1)
        z: mi.containsMouse ? 2 : 1
        Behavior on scale { NumberAnimation { duration: Tema.medio; easing.type: Easing.OutBack } }
        Rectangle {
          x: 3; y: 3; width: parent.width - 6; height: 106
          radius: Tema.raio
          color: Tema.superficieAlta
          Grid {
            anchors.centerIn: parent
            visible: fi.modelData.instalado
            columns: 4; spacing: 10
            Repeater {
              model: fi.modelData.previa
              delegate: Image {
                required property string modelData
                width: 30; height: 30
                source: "file://" + modelData
                sourceSize: Qt.size(60, 60)
                asynchronous: true
                smooth: true; mipmap: true
              }
            }
          }
          Column {
            anchors.centerIn: parent
            visible: !fi.modelData.instalado
            spacing: 6
            Glifo { anchors.horizontalCenter: parent.horizontalCenter; g: fi.instalando ? Icones.timer : Icones.update; tamanho: 22; color: Tema.texto2 }
            Texto {
              anchors.horizontalCenter: parent.horizontalCenter
              text: fi.instalando ? I18n.t("Instalando…") : I18n.t("Instalar · ") + (fi.modelData.fonte === "oficial" ? "oficial" : "AUR")
              color: Tema.texto2; font.pixelSize: Tema.tLegenda
            }
            Texto {
              anchors.horizontalCenter: parent.horizontalCenter
              width: 170; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
              text: fi.modelData.desc; color: Tema.texto3; font.pixelSize: Tema.tLegenda - 1
            }
          }
        }
        Rectangle {
          x: 0; y: 0; width: parent.width; height: 112
          radius: Tema.raio + 3
          color: "transparent"
          border.width: fi.ativo ? 2 : (mi.containsMouse ? 1 : 0)
          border.color: fi.ativo ? Tema.realce : Tema.linhaForte
        }
        Rectangle {
          visible: fi.ativo
          x: parent.width - 30; y: 82
          width: 22; height: 22; radius: Tema.raio > 0 ? 11 : 0
          color: Tema.realce
          Glifo { anchors.centerIn: parent; g: Icones.check; tamanho: 13; color: Tema.sobreRealce }
        }
        Texto { x: 4; y: 116; width: parent.width - 8; text: fi.modelData.nome + (fi.modelData.instalado && fi.modelData.id !== "simba" ? "" : ""); color: fi.ativo ? Tema.texto : Tema.texto2; elide: Text.ElideRight }
        MouseArea {
          id: mi
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: {
            if (fi.instalando) return
            if (fi.modelData.instalado) pg.escolherIcones({ tema: fi.modelData.id, cor: "auto" })
            else pg.confirmarIcones = fi.modelData
          }
        }
      }
    }
  }
  Cartao {
    visible: !!pg.confirmarIcones
    Linha {
      glifo: Icones.update
      titulo: pg.confirmarIcones ? I18n.t("Instalar os ícones “") + pg.confirmarIcones.nome + "”?" : ""
      descricao: pg.confirmarIcones ? (pg.confirmarIcones.fonte === "oficial"
                 ? I18n.t("Do repositório oficial (") + pg.confirmarIcones.pacote + I18n.t("). Pede a senha de administrador.")
                 : I18n.t("Do AUR (") + pg.confirmarIcones.pacote + I18n.t("): abre um terminal, compila e pede a senha. Leva alguns minutos.")) : ""
      Botao { texto: I18n.t("Cancelar"); tipo: "fantasma"; onClicado: pg.confirmarIcones = null }
      Botao { texto: I18n.t("Instalar"); tipo: "primario"; onClicado: { var f = pg.confirmarIcones; pg.confirmarIcones = null; pg.instalarIcones(f) } }
    }
  }
  Cartao {
    visible: !!pg.icones
    Linha {
      chave: "iconesCor"
      visible: !!pg.familiaIcones && pg.familiaIcones.cores.length > 0
      glifo: Icones.palette
      titulo: I18n.t("Cor dos ícones")
      descricao: (pg.escolhaIcones.cor || "auto") === "auto" && pg.familiaIcones
                 ? I18n.t("Automática: ") + (pg.nomeCor[pg.familiaIcones.corAuto] || pg.familiaIcones.corAuto) + I18n.t(", a mais perto da cor do tema")
                 : I18n.t("Escolhida por você")
      Flow {
        width: 330
        spacing: 6
        layoutDirection: Qt.RightToLeft
        Repeater {
          model: pg.familiaIcones ? ["auto"].concat(pg.familiaIcones.cores) : []
          delegate: Rectangle {
            required property string modelData
            readonly property bool sel: (pg.escolhaIcones.cor || "auto") === modelData
            width: modelData === "auto" ? 64 : 24; height: 24
            radius: 12
            color: modelData === "auto" ? Tema.superficieAlta : (pg.corAmostra[modelData] || Tema.acento)
            border.width: sel ? 2 : 1
            border.color: sel ? Tema.texto : Tema.linhaForte
            Texto { anchors.centerIn: parent; visible: modelData === "auto"; text: I18n.t("Auto"); font.pixelSize: Tema.tLegenda }
            Glifo { anchors.centerIn: parent; visible: sel && modelData !== "auto"; g: Icones.check; tamanho: 12; color: "#ffffff" }
            MouseArea {
              anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
              onClicked: pg.escolherIcones({ cor: modelData })
              onContainsMouseChanged: if (containsMouse && modelData !== "auto") Navegacao.confirmar(pg.nomeCor[modelData] || modelData, "")
            }
          }
        }
      }
    }
    Linha {
      chave: "iconesModo"
      visible: (pg.escolhaIcones.tema || "simba") === "simba" || (!!pg.familiaIcones && pg.familiaIcones.modos)
      glifo: Icones.themeLightDark
      titulo: I18n.t("Variante clara ou escura")
      descricao: I18n.t("Automática acompanha o tema (agora ") + (pg.icones && pg.icones.escuro ? "escuro" : "claro") + ")"
      Segmentado {
        atual: pg.escolhaIcones.modo || "auto"
        opcoes: [{ valor: "auto", rotulo: I18n.t("Automática") }, { valor: "claro", rotulo: I18n.t("Clara") }, { valor: "escuro", rotulo: I18n.t("Escura") }]
        onEscolhido: function(v) { pg.escolherIcones({ modo: v }) }
      }
    }
    Linha {
      chave: "iconesBarra"
      glifo: Icones.dockBottom
      titulo: I18n.t("Ícones na barra de tarefas")
      descricao: pg.estiloBarra === "coloridos" ? I18n.t("Os do tema de ícones escolhido acima") : I18n.t("Silhuetas na cor do tema (ignoram o tema de ícones)")
      Segmentado {
        atual: pg.estiloBarra
        opcoes: [{ valor: "tema", rotulo: I18n.t("Monocromáticos") }, { valor: "coloridos", rotulo: I18n.t("Coloridos") }]
        onEscolhido: function(v) {
          pg.estiloBarra = v
          Sistema.rodar(["barra-tarefas", "opcao", "estiloIcones", JSON.stringify(v)])
        }
      }
    }
    Linha {
      chave: "iconesAtivo"
      glifo: Icones.informationOutline
      titulo: I18n.t("Tema de ícones em uso")
      descricao: pg.icones ? pg.icones.ativo + (pg.icones.simba && pg.icones.simba !== pg.icones.doTema.variante && (pg.escolhaIcones.tema || "simba") === "simba"
                 ? I18n.t(" (o tema do Simba pede “") + pg.icones.simba + I18n.t("”, que não está instalado; usando o mais parecido)") : "") : ""
    }
  }

  // ── menu Iniciar ─────────────────────────────────────────────────────────
  Secao {
    titulo: I18n.t("Iniciar")
    detalhe: I18n.t("O menu do Super+Espaço e do botão Iniciar da barra. As cores seguem o tema (claro ou escuro).")
  }
  Ancora { chave: "iniciarEstilo" }
  Flow {
    Layout.fillWidth: true
    spacing: 10
    Repeater {
      model: [
        { id: "classico", titulo: I18n.t("Windows 11") },
        { id: "moderno", titulo: I18n.t("Windows 11 (2025)") },
        { id: "compacto", titulo: I18n.t("Compacto") },
        { id: "telaCheia", titulo: I18n.t("Tela cheia") }
      ]
      delegate: Item {
        id: est
        required property var modelData
        readonly property bool ativo: Preferencias.obter("iniciar.estilo", "classico") === modelData.id
        readonly property color c1: Tema.alfa(Tema.texto, 0.18)
        readonly property color c2: Tema.alfa(Tema.texto, 0.32)
        width: 196; height: 136
        scale: me.pressed ? 0.96 : (me.containsMouse ? 1.03 : 1)
        z: me.containsMouse ? 2 : 1
        Behavior on scale { NumberAnimation { duration: Tema.medio; easing.type: Easing.OutBack } }
        // tela em miniatura
        Rectangle {
          id: tela
          x: 3; y: 3; width: parent.width - 6; height: 106
          radius: Tema.raio
          color: Tema.mistura(Tema.fundo, Tema.texto, 0.10)
          clip: true
          Rectangle { anchors.bottom: parent.bottom; width: parent.width; height: 8; color: Tema.alfa(Tema.texto, 0.10) }
          // cartão do menu
          Rectangle {
            id: menuMini
            visible: est.modelData.id !== "telaCheia"
            x: 8; y: 8
            width: est.modelData.id === "moderno" ? 104 : (est.modelData.id === "compacto" ? 100 : 84)
            height: parent.height - 22
            radius: 4
            color: Tema.mistura(Tema.fundo, Tema.texto, Tema.escuro ? 0.05 : 0.0)
            border.width: 1; border.color: Tema.linha
            // pesquisa
            Rectangle {
              visible: est.modelData.id !== "compacto"
              x: 6; y: 5; width: parent.width - 12; height: 6; radius: 3; color: est.c1
            }
            // grade de fixados
            Grid {
              visible: est.modelData.id !== "compacto"
              x: 7; y: 16
              columns: est.modelData.id === "moderno" ? 8 : 6
              spacing: 3
              Repeater {
                model: est.modelData.id === "moderno" ? 8 : 12
                delegate: Rectangle { width: 9; height: 9; radius: 2; color: est.c2 }
              }
            }
            // recomendados / categorias
            Grid {
              visible: est.modelData.id === "classico"
              x: 7; y: 46; columns: 2; spacing: 4
              Repeater { model: 4; delegate: Rectangle { width: 32; height: 5; radius: 2; color: est.c1 } }
            }
            Grid {
              visible: est.modelData.id === "moderno"
              x: 7; y: 32; columns: 3; spacing: 4
              Repeater { model: 3; delegate: Rectangle { width: 27; height: 5; radius: 2; color: est.c1 } }
            }
            Grid {
              visible: est.modelData.id === "moderno"
              x: 7; y: 44; columns: 3; spacing: 4
              Repeater { model: 3; delegate: Rectangle { width: 27; height: 20; radius: 3; color: est.c1 } }
            }
            // compacto: trilho, lista e blocos
            Rectangle { visible: est.modelData.id === "compacto"; x: 0; y: 0; width: 10; height: parent.height; color: est.c1; radius: 4 }
            Column {
              visible: est.modelData.id === "compacto"
              x: 15; y: 6; spacing: 4
              Repeater { model: 9; delegate: Rectangle { width: 34; height: 4; radius: 2; color: est.c1 } }
            }
            Grid {
              visible: est.modelData.id === "compacto"
              x: 55; y: 6; columns: 3; spacing: 3
              Repeater { model: 9; delegate: Rectangle { width: 12; height: 12; radius: 2; color: est.c2 } }
            }
            // rodapé
            Rectangle { visible: est.modelData.id !== "compacto"; anchors.bottom: parent.bottom; width: parent.width; height: 9; color: est.c1; radius: 4 }
          }
          // tela cheia: grade grande
          Rectangle { visible: est.modelData.id === "telaCheia"; anchors.horizontalCenter: parent.horizontalCenter; y: 8; width: 70; height: 7; radius: 3; color: est.c1 }
          Grid {
            visible: est.modelData.id === "telaCheia"
            anchors.horizontalCenter: parent.horizontalCenter
            y: 22; columns: 8; spacing: 6
            Repeater { model: 32; delegate: Rectangle { width: 13; height: 13; radius: 3; color: est.c2 } }
          }
        }
        Rectangle {
          x: 0; y: 0; width: parent.width; height: 112
          radius: Tema.raio + 3
          color: "transparent"
          border.width: est.ativo ? 2 : (me.containsMouse ? 1 : 0)
          border.color: est.ativo ? Tema.realce : Tema.linhaForte
        }
        Rectangle {
          visible: est.ativo
          x: parent.width - 30; y: 82
          width: 22; height: 22; radius: Tema.raio > 0 ? 11 : 0
          color: Tema.realce
          Glifo { anchors.centerIn: parent; g: Icones.check; tamanho: 13; color: Tema.sobreRealce }
        }
        Texto { x: 4; y: 116; width: parent.width - 8; text: est.modelData.titulo; color: est.ativo ? Tema.texto : Tema.texto2; elide: Text.ElideRight }
        MouseArea {
          id: me
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: {
            Preferencias.definir("iniciar.estilo", est.modelData.id)
            Navegacao.confirmar(I18n.t("Menu Iniciar: ") + est.modelData.titulo, Icones.apps)
          }
        }
      }
    }
  }
  Cartao {
    Linha {
      chave: "iniciarAbrir"
      glifo: Icones.apps
      titulo: I18n.t("Ver o menu Iniciar")
      descricao: I18n.t("Super+Espaço ou o botão Iniciar da barra · botão direito num app fixa ou desafixa")
      Botao { texto: I18n.t("Abrir"); onClicado: Sistema.solto(["configuracoes", "menu-iniciar", "abrir"]) }
    }
    Linha {
      chave: "iniciarMaterial"
      glifo: Icones.blur
      titulo: I18n.t("Fundo do menu")
      descricao: I18n.t("Acrílico desfoca o que está atrás; Transparente só deixa ver")
      Segmentado {
        atual: Preferencias.obter("iniciar.material", "transparente")
        opcoes: [{ valor: "solido", rotulo: I18n.t("Sólido") }, { valor: "acrilico", rotulo: I18n.t("Acrílico") }, { valor: "transparente", rotulo: I18n.t("Transparente") }]
        onEscolhido: function(v) { Preferencias.definir("iniciar.material", v) }
      }
    }
    Linha {
      visible: Preferencias.obter("iniciar.material", "transparente") !== "solido"
      chave: "iniciarTransparencia"
      glifo: Icones.opacity
      titulo: I18n.t("Transparência")
      Deslizante { width: 220; de: 0; ate: 85; passo: 1; sufixo: " %"; valor: Preferencias.obter("iniciar.transparencia", 28); onSolto: function(v) { Preferencias.definir("iniciar.transparencia", v) } }
    }
    Linha {
      visible: Preferencias.obter("iniciar.material", "transparente") === "acrilico"
      chave: "iniciarIntensidade"
      glifo: Icones.blur
      titulo: I18n.t("Intensidade do desfoque")
      Deslizante { width: 220; de: 0; ate: 100; passo: 1; sufixo: " %"; valor: Preferencias.obter("iniciar.intensidade", 70); onSolto: function(v) { Preferencias.definir("iniciar.intensidade", v) } }
    }
    Linha {
      chave: "iniciarTom"
      glifo: Icones.palette
      titulo: I18n.t("Tonalidade")
      descricao: I18n.t("Cor do fundo do menu")
      Segmentado {
        atual: Preferencias.obter("iniciar.tom", "tema")
        opcoes: [{ valor: "tema", rotulo: I18n.t("Do tema") }, { valor: "destaque", rotulo: I18n.t("Cor de destaque") }]
        onEscolhido: function(v) { Preferencias.definir("iniciar.tom", v) }
      }
    }
    Linha {
      chave: "iniciarCantos"
      glifo: Icones.roundedCorner
      titulo: I18n.t("Cantos arredondados")
      Deslizante { width: 220; de: 0; ate: 24; passo: 1; sufixo: " px"; valor: Preferencias.obter("iniciar.cantos", 10); onSolto: function(v) { Preferencias.definir("iniciar.cantos", v) } }
    }
    Linha {
      chave: "iniciarBorda"
      glifo: Icones.borderAll
      titulo: I18n.t("Borda")
      Interruptor { ligado: Preferencias.obter("iniciar.borda", true); onAlternado: function(x) { Preferencias.definir("iniciar.borda", x) } }
    }
    Linha {
      chave: "iniciarPosicao"
      glifo: Icones.dockBottom
      titulo: I18n.t("Posição")
      descricao: I18n.t("Ao lado do botão Iniciar ou no meio da tela")
      Segmentado {
        atual: Preferencias.obter("iniciar.centro", false) ? "centro" : "esquerda"
        opcoes: [{ valor: "esquerda", rotulo: I18n.t("Esquerda") }, { valor: "centro", rotulo: I18n.t("Centro") }]
        onEscolhido: function(v) { Preferencias.definir("iniciar.centro", v === "centro") }
      }
    }
    Linha {
      chave: "iniciarRecentes"
      glifo: Icones.history
      titulo: I18n.t("Mostrar arquivos recentes")
      descricao: I18n.t("Em “Recomendado” e na pesquisa")
      Interruptor { ligado: Preferencias.obter("iniciar.recentes", true); onAlternado: function(x) { Preferencias.definir("iniciar.recentes", x) } }
    }
    Linha {
      chave: "iniciarMaisUsados"
      glifo: Icones.star
      titulo: I18n.t("Mostrar apps mais usados")
      descricao: I18n.t("No topo da lista do estilo Compacto")
      Interruptor { ligado: Preferencias.obter("iniciar.maisUsados", true); onAlternado: function(x) { Preferencias.definir("iniciar.maisUsados", x) } }
    }
    Linha {
      chave: "iniciarFixados"
      glifo: Icones.pin
      titulo: I18n.t("Apps fixados")
      descricao: I18n.t("Volta aos apps fixados de fábrica")
      Botao { texto: I18n.t("Restaurar"); tipo: "fantasma"; onClicado: { Preferencias.definir("iniciar.fixados", undefined); Navegacao.confirmar(I18n.t("Fixados restaurados"), Icones.pin) } }
    }
  }

  Secao {
    titulo: I18n.t("Inicialização")
    detalhe: I18n.t("Tela que aparece ao ligar, desligar e reiniciar, no estilo do Windows 11. Pede a senha de administrador e vale a partir do próximo boot. “Vidro” usa o papel de parede atual.")
  }
  Ancora { chave: "temaBoot" }
  Flow {
    Layout.fillWidth: true
    spacing: 10
    Repeater {
      model: pg.temasBoot
      delegate: Item {
        id: tb
        required property var modelData
        readonly property bool aplicando: pg.aplicandoBoot === modelData.id
        width: 196; height: 136
        scale: mb.pressed ? 0.96 : (mb.containsMouse ? 1.03 : 1)
        z: mb.containsMouse ? 2 : 1
        Behavior on scale { NumberAnimation { duration: Tema.medio; easing.type: Easing.OutBack } }
        Image {
          id: bi
          x: 3; y: 3; width: parent.width - 6; height: 106
          source: pg.previasBoot > 0 ? "file://" + pg.cacheBoot + "/" + tb.modelData.id + ".png?" + pg.previasBoot : ""
          sourceSize.width: 380
          fillMode: Image.PreserveAspectCrop
          cache: false
          asynchronous: true
          visible: false
        }
        Rectangle { id: bm; anchors.fill: bi; radius: Tema.raio; visible: false; layer.enabled: true }
        MultiEffect {
          anchors.fill: bi; source: bi; maskEnabled: true; maskSource: bm
          opacity: bi.status === Image.Ready ? 1 : 0
          Behavior on opacity { NumberAnimation { duration: 350 } }
        }
        Rectangle {
          x: 0; y: 0; width: parent.width; height: 112
          radius: Tema.raio + 3
          color: "transparent"
          border.width: tb.modelData.ativo ? 2 : (mb.containsMouse ? 1 : 0)
          border.color: tb.modelData.ativo ? Tema.realce : Tema.linhaForte
        }
        Rectangle {
          visible: tb.modelData.ativo || tb.aplicando
          x: parent.width - 30; y: 82
          width: 22; height: 22; radius: Tema.raio > 0 ? 11 : 0
          color: Tema.realce
          Glifo { anchors.centerIn: parent; g: tb.aplicando ? Icones.timer : Icones.check; tamanho: 13; color: Tema.sobreRealce }
        }
        Texto { x: 4; y: 116; width: parent.width - 8; text: tb.modelData.titulo; color: tb.modelData.ativo ? Tema.texto : Tema.texto2; elide: Text.ElideRight }
        MouseArea { id: mb; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: if (!tb.modelData.ativo && !pg.aplicandoBoot) pg.confirmarBoot = tb.modelData }
      }
    }
  }
  Cartao {
    visible: !!pg.confirmarBoot
    Linha {
      glifo: Icones.monitorLock
      titulo: pg.confirmarBoot ? I18n.t("Usar “") + pg.confirmarBoot.titulo + I18n.t("” ao iniciar?") : ""
      descricao: I18n.t("Pede a senha de administrador e leva cerca de 1 minuto (o sistema refaz a imagem de inicialização).")
      Botao { texto: I18n.t("Cancelar"); tipo: "fantasma"; onClicado: pg.confirmarBoot = null }
      Botao { texto: I18n.t("Aplicar"); tipo: "primario"; onClicado: { var t = pg.confirmarBoot; pg.confirmarBoot = null; pg.aplicarBoot(t.id, t.titulo) } }
    }
  }
  Cartao {
    Linha {
      chave: "desbloqueio"
      glifo: Icones.monitorLock
      titulo: I18n.t("Cores do tema de inicialização original")
      descricao: I18n.t("Recolore o tema “Simba (original)” com as cores de um tema do sistema.")
      Botao {
        texto: I18n.t("Escolher…")
        onClicado: Sistema.soltoSh("unlock=$(simba-plymouth-switcher); if [[ $unlock == default ]]; then simba-launch-floating-terminal-with-presentation simba-plymouth-reset; elif [[ -n $unlock ]]; then simba-launch-floating-terminal-with-presentation \"simba-plymouth-set-by-theme $(printf %q \"$unlock\")\"; fi")
      }
    }
  }
}
