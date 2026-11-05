import QtQuick
import QtQuick.Effects
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland
import qs.Comum
import "../Janela/Busca.js" as BuscaConfig
import "Equivalentes.js" as Equivalentes

// Menu Iniciar (Super+Espaço e o botão Iniciar da barra), no estilo do Windows 11.
//
// Estilos (Configurações › Personalização › Iniciar; preferências "iniciar.*"):
//   classico   Windows 11 original: Fixado (grade com páginas) + Recomendado
//   moderno    Windows 11 2025: uma coluna rolável — Fixado, Recomendado e Todos
//              por categoria, grade ou lista
//   compacto   lista de apps com "Mais usados" e uma coluna de blocos fixados
//   telaCheia  todos os apps em grade ocupando a tela
// As cores vêm do tema do Simba (Tema): claro ou escuro, ao vivo.
//
// Abrir/fechar: `configuracoes menu-iniciar` (comando no arquivo de comandos).
// Digitar pesquisa apps, configurações (o mesmo índice da janela) e arquivos
// recentes; Enter abre o primeiro resultado, Esc volta/fecha.
Scope {
  id: m

  property bool aberto: false
  property string telaNome: ""
  property string pagina: "inicio"     // inicio | todos (classico/compacto)
  property string texto: ""
  property int sel: 0
  property var recentes: []
  property var uso: ({})
  property var contexto: null          // { tipo, id, x, y } — menu do botão direito
  property bool energiaAberta: false
  property var energiaPos: ({ x: 0, y: 0, direita: true })
  property var barraFixados: []
  property bool desfoque: false        // decoration:blur:enabled (fundo acrílico de verdade)
  property var iconesArq: ({})         // nome do ícone → arquivo (bin/iniciar icones), guardado entre aberturas
  property string nomeUsuario: Quickshell.env("USER") || ""

  // ── preferências ─────────────────────────────────────────────────────────
  readonly property string estilo: Preferencias.obter("iniciar.estilo", "classico")
  readonly property bool mostrarRecentes: Preferencias.obter("iniciar.recentes", true)
  readonly property bool mostrarMaisUsados: Preferencias.obter("iniciar.maisUsados", true)
  readonly property bool centralizado: Preferencias.obter("iniciar.centro", false)
  // Aparência (Personalização › Iniciar):
  //   material  solido | acrilico (captura da tela atrás, desfocada) | transparente
  readonly property string material: Preferencias.obter("iniciar.material", "acrilico")
  readonly property real transparencia: Preferencias.obter("iniciar.transparencia", 28) / 100   // 0 = opaco
  readonly property real intensidade: Preferencias.obter("iniciar.intensidade", 70) / 100       // desfoque
  readonly property string tom: Preferencias.obter("iniciar.tom", "tema")                       // tema | destaque
  readonly property int cantos: Preferencias.obter("iniciar.cantos", 10)
  readonly property bool borda: Preferencias.obter("iniciar.borda", true)
  readonly property color corFundo: {
    var base = Tema.mistura(Tema.fundo, Tema.texto, Tema.escuro ? 0.06 : 0.02)
    return tom === "destaque" ? Tema.mistura(base, Tema.acento, Tema.escuro ? 0.22 : 0.14) : base
  }
  readonly property real alfaFundo: material === "solido" ? 1 : Math.max(0.12, 1 - transparencia)
  readonly property string visaoTodos: Preferencias.obter("iniciar.visaoTodos", "categoria")  // moderno
  readonly property var fixadosPadrao: ["brave-browser", "com.renan.Explorador", "simba-loja", "com.renan.Configuracoes",
    "ai.storyteller.wordcraft", "ai.storyteller.gridcraft", "ai.storyteller.deckcraft", "com.simba.Draco",
    "foot", "WhatsApp", "spotify", "steam", "localsend", "org.gnome.TextEditor", "org.gnome.Calculator"]
  readonly property var fixados: {
    var l = Preferencias.obter("iniciar.fixados", fixadosPadrao) || []
    var _ = DesktopEntries.applications.values
    return l.filter(function(id) { return !!DesktopEntries.byId(id) })
  }
  function definirFixados(l) { Preferencias.definir("iniciar.fixados", l) }
  function fixado(id) { return fixados.indexOf(id) >= 0 }
  function fixar(id) { if (!fixado(id)) definirFixados(fixados.concat([id])) }
  function desafixar(id) { definirFixados(fixados.filter(function(x) { return x !== id })) }
  function paraInicio(id) { definirFixados([id].concat(fixados.filter(function(x) { return x !== id }))) }

  // ── apps ─────────────────────────────────────────────────────────────────
  readonly property var apps: {
    var l = DesktopEntries.applications.values.filter(function(e) { return e && !e.noDisplay && e.name })
    l.sort(function(a, b) { return a.name.localeCompare(b.name, "pt-BR", { sensitivity: "base" }) })
    return l
  }
  // Lê a lista de apps para que quem chama (os blocos fixados) volte a procurar quando o
  // Quickshell relê os atalhos: ele troca o objeto de um app com .desktop duplicado (pasta
  // pessoal + sistema: Brave, Foot…) e o antigo some — o bloco ficava engrenagem sem nome.
  // `aberturas` refaz a procura a cada abertura do menu, mesmo que a troca não avise.
  property int aberturas: 0
  function app(id) { var _ = DesktopEntries.applications.values, __ = aberturas; return DesktopEntries.byId(id) }

  function iconeApp(e) { return e ? caminhoIcone(e.icon) : caminhoIcone("") }
  function caminhoIcone(n) {
    if (n && n.charAt(0) === "/") return "file://" + n
    var arq = n ? iconesArq[n] : ""
    if (arq) return "file://" + arq
    var p = n ? Quickshell.iconPath(n, true) : ""
    return p || Quickshell.iconPath("application-x-executable", true) || ""
  }

  // Categorias no jeito do Windows 11 (estilo moderno).
  readonly property var categorias: [
    { id: "produtividade", titulo: I18n.t("Produtividade"), chaves: ["Office", "TextEditor", "WordProcessor", "Spreadsheet", "Presentation", "Calendar", "ContactManagement", "Viewer"] },
    { id: "internet", titulo: I18n.t("Internet e social"), chaves: ["Network", "WebBrowser", "Email", "Chat", "InstantMessaging", "FileTransfer", "RemoteAccess"] },
    { id: "criatividade", titulo: I18n.t("Criatividade e mídia"), chaves: ["Graphics", "Photography", "AudioVideo", "Audio", "Video", "Music", "Player", "Recorder"] },
    { id: "jogos", titulo: I18n.t("Jogos"), chaves: ["Game"] },
    { id: "desenvolvimento", titulo: I18n.t("Desenvolvimento"), chaves: ["Development", "IDE", "Building", "Debugger"] },
    { id: "utilitarios", titulo: I18n.t("Utilitários e ferramentas"), chaves: ["Utility", "Accessories", "FileManager", "Archiving", "Calculator", "Compression", "TerminalEmulator"] },
    { id: "sistema", titulo: I18n.t("Sistema"), chaves: ["Settings", "System", "Monitor", "PackageManager", "HardwareSettings", "Security"] },
    { id: "outros", titulo: I18n.t("Outros"), chaves: [] }
  ]
  function categoriaDe(e) {
    var cs = e.categories || []
    for (var i = 0; i < categorias.length - 1; i++)
      for (var k = 0; k < categorias[i].chaves.length; k++)
        if (cs.indexOf(categorias[i].chaves[k]) >= 0) return categorias[i].id
    return "outros"
  }
  readonly property var porCategoria: {
    var g = {}
    for (var i = 0; i < apps.length; i++) {
      var c = categoriaDe(apps[i])
      if (!g[c]) g[c] = []
      g[c].push(apps[i])
    }
    // Dentro de cada categoria, os mais usados primeiro (os 4 ícones do bloco).
    var u = uso
    for (var k in g) g[k].sort(function(a, b) { return ((u[b.id] || {}).n || 0) - ((u[a.id] || {}).n || 0) || a.name.localeCompare(b.name, "pt-BR") })
    return categorias.filter(function(c) { return g[c.id] && g[c.id].length }).map(function(c) { return { id: c.id, titulo: c.titulo, apps: g[c.id] } })
  }
  readonly property var maisUsados: {
    var u = uso
    return apps.filter(function(e) { return u[e.id] && u[e.id].n > 0 })
               .sort(function(a, b) { return u[b.id].n - u[a.id].n || u[b.id].ultimo - u[a.id].ultimo })
               .slice(0, 6)
  }

  // ── pesquisa ─────────────────────────────────────────────────────────────
  readonly property var titulosPaginas: [
    { id: "inicio", titulo: I18n.t("Início") }, { id: "contas", titulo: I18n.t("Contas") }, { id: "personalizacao", titulo: I18n.t("Personalização") },
    { id: "janelas", titulo: I18n.t("Janelas e animações") }, { id: "tela", titulo: I18n.t("Tela") }, { id: "barra", titulo: I18n.t("Barra") },
    { id: "area", titulo: I18n.t("Área de trabalho") }, { id: "bloqueio", titulo: I18n.t("Bloqueio e inatividade") },
    { id: "entrada", titulo: I18n.t("Teclado, mouse e touchpad") }, { id: "som", titulo: I18n.t("Som") }, { id: "rede", titulo: I18n.t("Rede e internet") },
    { id: "bluetooth", titulo: I18n.t("Bluetooth") }, { id: "energia", titulo: I18n.t("Energia e bateria") }, { id: "notificacoes", titulo: I18n.t("Notificações") },
    { id: "atalhos", titulo: I18n.t("Atalhos de teclado") }, { id: "apps", titulo: I18n.t("Aplicativos padrão") }, { id: "sistema", titulo: I18n.t("Sistema") }
  ]
  readonly property var resultados: {
    var t = BuscaConfig.normalizar(texto.trim())
    if (!t) return []
    var out = []
    for (var i = 0; i < apps.length; i++) {
      var e = apps[i]
      var nome = BuscaConfig.normalizar(e.name)
      var extra = BuscaConfig.normalizar([e.genericName || "", e.comment || "", (e.keywords || []).join(" "), e.id].join(" "))
      var p = 0
      if (nome.indexOf(t) === 0) p = 100
      else if (nome.indexOf(" " + t) >= 0) p = 80
      else if (nome.indexOf(t) >= 0) p = 60
      else if (extra.indexOf(t) >= 0) p = 12
      if (p) out.push({ tipo: "app", id: e.id, titulo: e.name, sub: I18n.t("Aplicativo"), icone: iconeApp(e), pontos: p + ((uso[e.id] || {}).n || 0) * 0.5 })
    }
    // "word" → WordCraft, "excel" → GridCraft…: programas do Windows que não existem no Linux
    // levam ao app que faz o mesmo papel (Equivalentes.js; vale o primeiro instalado)
    var eq = Equivalentes.buscar(t)
    for (var q0 = 0; q0 < eq.length; q0++) {
      var alvo = null
      for (var q1 = 0; q1 < eq[q0].ids.length && !alvo; q1++) {
        var en = app(eq[q0].ids[q1])
        if (en && !en.noDisplay) alvo = en
      }
      if (!alvo) continue
      var subEq = I18n.t("Alternativa para ") + I18n.t(eq[q0].de)
      var ptsEq = eq[q0].pontos + ((uso[alvo.id] || {}).n || 0) * 0.5
      var ja = out.filter(function(x) { return x.tipo === "app" && x.id === alvo.id })[0]
      if (ja) { if (ptsEq > ja.pontos) { ja.pontos = ptsEq; ja.sub = subEq } }
      else out.push({ tipo: "app", id: alvo.id, titulo: alvo.name, sub: subEq, icone: iconeApp(alvo), pontos: ptsEq })
    }
    var cfg = BuscaConfig.buscar(texto, titulosPaginas, I18n.t).slice(0, 6)
    for (var c = 0; c < cfg.length; c++)
      out.push({ tipo: "config", pagina: cfg[c].pagina, chave: cfg[c].chave, titulo: cfg[c].titulo, sub: I18n.t("Configurações › ") + cfg[c].caminho,
                 glifo: Icones.cog, pontos: 20 + cfg[c].pontos })
    for (var r = 0; r < recentes.length; r++) {
      var a = recentes[r]
      if (BuscaConfig.normalizar(a.nome).indexOf(t) >= 0)
        out.push({ tipo: "arquivo", caminho: a.caminho, titulo: a.nome, sub: a.pasta, icone: caminhoIcone(a.icone), pontos: 15 })
    }
    // arquivos da pasta pessoal (plocate), além dos recentes
    var vistos = {}
    for (var v = 0; v < out.length; v++) if (out[v].caminho) vistos[out[v].caminho] = 1
    for (var f = 0; f < buscaArquivos.length; f++) {
      var b = buscaArquivos[f]
      if (vistos[b.caminho]) continue
      out.push({ tipo: "arquivo", caminho: b.caminho, titulo: b.nome, sub: b.pasta, glifo: b.pastaSim ? Icones.folder : Icones.file, pontos: 11 })
    }
    // apps que ainda não estão instalados: "Instalar pela Loja"
    var temApp = out.some(function(x) { return x.tipo === "app" && x.pontos >= 60 })
    var nomesApps = {}
    for (var q = 0; q < apps.length; q++) nomesApps[BuscaConfig.normalizar(apps[q].name)] = 1
    for (var l = 0; l < buscaLoja.length; l++) {
      var a2 = buscaLoja[l]
      if (nomesApps[BuscaConfig.normalizar(a2.nome)]) continue   // já instalado (pacote do sistema)
      out.push({ tipo: "loja", id: a2.id, titulo: a2.nome, sub: I18n.t("Instalar pela Loja") + (a2.resumo ? " · " + a2.resumo : ""),
                 icone: a2.icone ? "file://" + a2.icone : iconeLoja, pontos: temApp ? 9 - l * 0.1 : 40 - l })
    }
    out.sort(function(x, y) { return y.pontos - x.pontos })
    out = out.slice(0, 13)
    // Draco: sempre a última linha; vira a primeira quando parece uma pergunta/pedido
    var bruto = texto.trim()
    if (bruto.length >= 3) {
      var pergunta = /[?]$/.test(bruto) || /^(o que|oque|como|qual|quais|quanto|quantos|quando|onde|quem|por que|porque|me |abra|abre|crie|cria|escreva|pesquise|procure|toque|coloque|mande|envie|lembre|traduza|resuma|explique)\b/i.test(bruto) || bruto.split(/\s+/).length >= 4
      var d = { tipo: "draco", texto: bruto, titulo: I18n.t("Perguntar ao Draco: “") + bruto + "”", sub: I18n.t("Assistente de IA · responde e faz por você"), icone: iconeDraco, pontos: 0 }
      if (pergunta) out.unshift(d); else out.push(d)
    }
    return out
  }
  readonly property string iconeDraco: "file://" + Quickshell.env("HOME") + "/.local/share/icons/hicolor/scalable/apps/com.simba.Draco.svg"
  readonly property string iconeLoja: "file://" + Quickshell.env("HOME") + "/.local/share/icons/hicolor/scalable/apps/simba-loja.svg"
  // resultados que vêm de fora (Loja e arquivos), buscados depois de uma pausa na digitação
  property var buscaLoja: []
  property var buscaArquivos: []
  property string buscaFeita: ""
  Timer {
    id: buscaExtra
    interval: 260
    onTriggered: {
      var t = m.texto.trim()
      if (t.length < 2) { m.buscaLoja = []; m.buscaArquivos = []; return }
      m.buscaFeita = t
      Sistema.json([Sistema.bin + "/iniciar", "loja", t], function(v) { if (m.buscaFeita === t) m.buscaLoja = v || [] })
      Sistema.json([Sistema.bin + "/iniciar", "arquivos", t], function(v) { if (m.buscaFeita === t) m.buscaArquivos = v || [] })
    }
  }
  onTextoChanged: { sel = 0; if (!texto.trim()) { buscaLoja = []; buscaArquivos = [] } buscaExtra.restart() }

  // ── ações ────────────────────────────────────────────────────────────────
  function abrir() {
    if (aberto) return
    telaNome = Hyprland.focusedMonitor ? Hyprland.focusedMonitor.name : ""
    Hyprland.refreshMonitors()
    texto = ""; pagina = "inicio"; contexto = null; energiaAberta = false
    aberturas++
    aberto = true
    Sistema.json([Sistema.bin + "/iniciar", "recentes", "12"], function(v) { if (v) { m.recentes = v; m.buscarIcones() } })
    buscarIcones()
    Sistema.rodar(["hyprctl", "getoption", "decoration:blur:enabled", "-j"], function(o) {
      try { var j = JSON.parse(o); m.desfoque = !!(j.int !== undefined ? j.int : j.bool) } catch (e) {}
    })
    // Nome da conta Google (Contas) ou o nome do usuário do sistema.
    Sistema.sh("jq -r '.nome // empty' ~/.config/conta/config.json 2>/dev/null || true; getent passwd \"$USER\" | cut -d: -f5 | cut -d, -f1", function(o) {
      var l = o.split("\n").map(function(x) { return x.trim() }).filter(function(x) { return x })
      var u = Quickshell.env("USER") || ""
      m.nomeUsuario = l[0] || (u.charAt(0).toUpperCase() + u.slice(1))
    })
    Sistema.json([Sistema.bin + "/iniciar", "uso"], function(v) { if (v) m.uso = v })
    Sistema.json(["barra-tarefas", "estado"], function(v) { if (v && v.fixados) m.barraFixados = v.fixados })
  }
  function fechar() { aberto = false; contexto = null; energiaAberta = false }
  // Resolve (uma vez) os ícones de apps e arquivos que ainda não estão no cache.
  function buscarIcones() {
    var faltam = {}
    apps.forEach(function(e) { if (e.icon && e.icon.charAt(0) !== "/" && !iconesArq[e.icon]) faltam[e.icon] = true })
    recentes.forEach(function(r) { if (r.icone && !iconesArq[r.icone]) faltam[r.icone] = true })
    var l = Object.keys(faltam).filter(function(n) { return !(n in tentados) })
    if (!l.length) return
    l.forEach(function(n) { tentados[n] = true })
    Sistema.json([Sistema.bin + "/iniciar", "icones"].concat(l), function(v) {
      if (v) m.iconesArq = Object.assign({}, m.iconesArq, v)
    })
  }
  property var tentados: ({})
  // Tema de ícones trocado (bin/icones aplicar grava este arquivo): esquece o cache.
  FileView {
    path: Sistema.home + "/.local/state/configuracoes/icones-versao"
    watchChanges: true
    printErrors: false
    onFileChanged: { reload(); m.iconesArq = ({}); m.tentados = ({}); if (m.aberto) m.buscarIcones() }
  }
  function alternar() { if (aberto) fechar(); else abrir() }

  function abrirApp(id) {
    Quickshell.execDetached(["uwsm-app", "--", "gtk-launch", id + ".desktop"])
    Sistema.solto([Sistema.bin + "/iniciar", "usar", id])
    fechar()
  }
  function abrirArquivo(caminho) { Quickshell.execDetached(["uwsm-app", "--", "xdg-open", caminho]); fechar() }
  function abrirConfig(pagina, chave) { fechar(); Navegacao.abrir(pagina, chave || "") }
  function abrirResultado(r) {
    if (!r) return
    if (r.tipo === "app") abrirApp(r.id)
    else if (r.tipo === "config") abrirConfig(r.pagina, r.chave)
    else if (r.tipo === "arquivo") abrirArquivo(r.caminho)
    else if (r.tipo === "loja") { Quickshell.execDetached(["simba-loja", "appstream://" + r.id]); fechar() }
    else if (r.tipo === "draco") { Quickshell.execDetached(["draco", "perguntar", r.texto]); fechar() }
  }
  function energia(acao) {
    fechar()
    var cmd = { bloquear: ["simba-system-lock"], suspender: ["systemctl", "suspend"], sair: ["simba-system-logout"],
                reiniciar: ["simba-system-reboot"], desligar: ["simba-system-shutdown"] }[acao]
    if (cmd) Quickshell.execDetached(cmd)
  }
  function fixarBarra(id, sim) {
    Sistema.rodar(["barra-tarefas", sim ? "fixar" : "desafixar", id], function() {
      Sistema.json(["barra-tarefas", "estado"], function(v) { if (v && v.fixados) m.barraFixados = v.fixados })
    })
  }
  // Menu de energia acima do botão (direita: alinhado à direita do botão).
  function abrirEnergia(item, direita) {
    if (energiaAberta) { energiaAberta = false; return }
    var p = item.mapToItem(null, direita ? item.width : 0, 0)
    energiaPos = { x: p.x, y: p.y, direita: !!direita }
    energiaAberta = true
  }
  function quando(iso) {
    if (!iso) return ""
    var min = Math.round((new Date() - new Date(iso)) / 60000)
    if (min < 1) return I18n.t("Agora mesmo")
    if (min < 60) return I18n.t("Há ") + min + " min"
    if (min < 1440) return I18n.t("Há ") + Math.round(min / 60) + " h"
    if (min < 2880) return I18n.t("Ontem")
    if (min < 10080) return I18n.t("Há ") + Math.round(min / 1440) + " dias"
    return new Date(iso).toLocaleDateString(Qt.locale(), I18n.t("d 'de' MMM"))
  }
  function menuApp(id, item, x, y) {
    var p = item.mapToItem(null, x, y)
    contexto = { id: id, x: p.x, y: p.y }
  }

  // Teclas comuns a todos os estilos (o campo de pesquisa recebe o foco).
  function tecla(ev) {
    if (ev.key === Qt.Key_Escape) {
      if (contexto || energiaAberta) { contexto = null; energiaAberta = false }
      else if (texto) texto = ""
      else if (pagina !== "inicio") pagina = "inicio"
      else fechar()
      ev.accepted = true
    } else if (texto && (ev.key === Qt.Key_Down || ev.key === Qt.Key_Tab)) {
      sel = Math.min(resultados.length - 1, sel + 1); ev.accepted = true
    } else if (texto && (ev.key === Qt.Key_Up || ev.key === Qt.Key_Backtab)) {
      sel = Math.max(0, sel - 1); ev.accepted = true
    } else if (ev.key === Qt.Key_Return || ev.key === Qt.Key_Enter) {
      if (texto) abrirResultado(resultados[sel])
      ev.accepted = true
    }
  }

  // ── janela ───────────────────────────────────────────────────────────────
  Variants {
    model: m.aberto ? Quickshell.screens.filter(function(s) { return m.telaNome === "" ? s === Quickshell.screens[0] : s.name === m.telaNome }) : []
    delegate: PanelWindow {
      id: w
      required property var modelData
      screen: modelData
      anchors { top: true; bottom: true; left: true; right: true }
      color: "transparent"
      exclusionMode: ExclusionMode.Ignore
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.namespace: "configuracoes-iniciar"
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

      // Área reservada pela barra (esquerda, cima, direita, baixo) neste monitor.
      readonly property var reservado: {
        var mon = Hyprland.monitorFor(modelData)
        var o = mon && mon.lastIpcObject
        return o && o.reserved ? o.reserved : [0, 0, 0, 26]
      }
      readonly property bool barraEmCima: reservado[1] > reservado[3]
      readonly property bool telaCheia: m.estilo === "telaCheia"
      readonly property real largCartao: ({ classico: 640, moderno: 780, compacto: 620 })[m.estilo] || 640
      readonly property real altCartao: Math.min(({ classico: 720, moderno: 820, compacto: 640 })[m.estilo] || 720,
                                                 height - reservado[1] - reservado[3] - 24)

      // Captura parada da tela, para o fundo acrílico (feita ao abrir, antes do menu aparecer).
      ScreencopyView {
        id: captura
        anchors.fill: parent
        captureSource: m.material === "acrilico" ? w.modelData : null
        live: false
        visible: false
      }

      // Clique fora fecha (como no Windows).
      MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
        onClicked: m.fechar()
      }
      // Tela cheia: a tela toda vira o fundo (acrílico/transparente/sólido).
      MultiEffect {
        anchors.fill: parent
        visible: w.telaCheia && m.material === "acrilico" && captura.hasContent
        source: captura
        blurEnabled: true; blur: m.intensidade; blurMax: 64
        saturation: 0.15
        opacity: cartao.p
      }
      Rectangle {
        anchors.fill: parent
        visible: w.telaCheia
        color: Tema.alfa(m.corFundo, m.material === "solido" ? 0.97 : m.alfaFundo)
        opacity: cartao.p
      }

      Item {
        id: cartao
        property real p: 0
        x: w.telaCheia ? 0 : (m.centralizado ? Math.round((w.width - width) / 2) : w.reservado[0] + 12)
        y: w.telaCheia ? 0 : (w.barraEmCima ? w.reservado[1] + 12 : w.height - w.reservado[3] - 12 - height) + (1 - p) * (w.barraEmCima ? -36 : 36)
        width: w.telaCheia ? w.width : w.largCartao
        height: w.telaCheia ? w.height : w.altCartao
        opacity: p
        NumberAnimation on p { id: entrada; from: 0; to: 1; duration: Tema.animacoes ? 260 : 0; easing.type: Easing.OutCubic; running: true }

        // Fundo: acrílico = o que está atrás do menu (captura), desfocado e com a
        // cor do tema por cima; transparente = só a cor translúcida (com o desfoque
        // do Hyprland, se estiver ligado); sólido = opaco.
        Item {
          id: vidro
          anchors.fill: parent
          visible: false
          layer.enabled: m.material === "acrilico" && !w.telaCheia
          clip: true
          MultiEffect {
            x: -cartao.x; y: -cartao.y
            width: w.width; height: w.height
            source: captura
            blurEnabled: true; blur: m.intensidade; blurMax: 64
            saturation: 0.15
          }
        }
        Rectangle { id: mascaraCartao; anchors.fill: parent; radius: m.cantos; visible: false; layer.enabled: true }
        MultiEffect {
          anchors.fill: parent
          visible: m.material === "acrilico" && !w.telaCheia && captura.hasContent
          source: vidro
          maskEnabled: true; maskSource: mascaraCartao
          maskThresholdMin: 0.5; maskSpreadAtMin: 1.0
        }
        Rectangle {
          anchors.fill: parent
          visible: !w.telaCheia
          radius: m.cantos
          color: Tema.alfa(m.corFundo, m.alfaFundo)
          border.width: m.borda ? 1 : 0
          border.color: Tema.alfa(Tema.texto, Tema.escuro ? 0.14 : 0.16)
        }
        // Engole os cliques do cartão (não fecha) e fecha menus abertos.
        MouseArea {
          anchors.fill: parent
          acceptedButtons: Qt.LeftButton | Qt.RightButton
          // Tela cheia: clicar no vazio fecha, como no Windows.
          onClicked: { if (m.contexto || m.energiaAberta) { m.contexto = null; m.energiaAberta = false } else if (w.telaCheia) m.fechar() }
        }

        Loader {
          anchors.fill: parent
          focus: true
          sourceComponent: ({ classico: classico, moderno: moderno, compacto: compacto, telaCheia: telaCheiaC })[m.estilo] || classico
        }
        Component { id: classico; EstiloClassico { menu: m } }
        Component { id: moderno; EstiloModerno { menu: m } }
        Component { id: compacto; EstiloCompacto { menu: m } }
        Component { id: telaCheiaC; EstiloTelaCheia { menu: m } }
      }

      // ── menu de energia ────────────────────────────────────────────────
      Rectangle {
        id: en
        visible: m.energiaAberta
        width: 210; height: colE.implicitHeight + 10
        x: Math.max(8, Math.min(m.energiaPos.direita ? m.energiaPos.x - width : m.energiaPos.x, w.width - width - 8))
        y: Math.max(8, m.energiaPos.y - height - 6)
        radius: 8
        color: Tema.mistura(Tema.fundo, Tema.texto, Tema.escuro ? 0.09 : 0.03)
        border.width: 1; border.color: Tema.linhaForte
        MouseArea { anchors.fill: parent }
        Column {
          id: colE
          anchors { left: parent.left; right: parent.right; top: parent.top; margins: 5 }
          Repeater {
            model: [
              { id: "bloquear", t: I18n.t("Bloquear"), g: Icones.lock },
              { id: "suspender", t: I18n.t("Suspender"), g: Icones.sleep },
              { id: "sair", t: I18n.t("Sair"), g: Icones.logout },
              { id: "reiniciar", t: I18n.t("Reiniciar"), g: Icones.restart },
              { id: "desligar", t: I18n.t("Desligar"), g: Icones.power }
            ]
            delegate: Rectangle {
              required property var modelData
              width: colE.width; height: 36; radius: 5
              color: me.containsMouse ? Tema.hover : "transparent"
              Row {
                anchors.verticalCenter: parent.verticalCenter
                x: 12; spacing: 12
                Glifo { g: modelData.g; tamanho: 15; color: Tema.texto2; anchors.verticalCenter: parent.verticalCenter }
                Texto { text: modelData.t; anchors.verticalCenter: parent.verticalCenter }
              }
              MouseArea { id: me; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: m.energia(modelData.id) }
            }
          }
        }
      }

      // ── menu do botão direito num app ──────────────────────────────────
      Rectangle {
        id: ctx
        visible: m.contexto !== null
        readonly property string idApp: m.contexto ? m.contexto.id : ""
        readonly property var opcoes: !m.contexto ? [] : [
          m.fixado(idApp) ? { id: "desafixar", t: I18n.t("Desafixar de Iniciar"), g: Icones.pin } : { id: "fixar", t: I18n.t("Fixar em Iniciar"), g: Icones.pin },
          m.fixado(idApp) ? { id: "inicio", t: I18n.t("Mover para o início"), g: Icones.arrowUp } : null,
          m.barraFixados.indexOf(idApp) >= 0 ? { id: "desbarra", t: I18n.t("Desafixar da barra de tarefas"), g: Icones.dockBottom }
                                              : { id: "barra", t: I18n.t("Fixar na barra de tarefas"), g: Icones.dockBottom },
          { id: "abrir", t: I18n.t("Abrir"), g: Icones.openInNew }
        ].filter(function(o) { return o !== null })
        x: m.contexto ? Math.min(m.contexto.x, w.width - width - 8) : 0
        y: m.contexto ? Math.min(m.contexto.y, w.height - height - 8) : 0
        width: 250
        height: colCtx.implicitHeight + 10
        radius: 8
        color: Tema.mistura(Tema.fundo, Tema.texto, Tema.escuro ? 0.09 : 0.03)
        border.width: 1
        border.color: Tema.linhaForte
        MouseArea { anchors.fill: parent }
        Column {
          id: colCtx
          anchors { left: parent.left; right: parent.right; top: parent.top; margins: 5 }
          Repeater {
            model: ctx.opcoes
            delegate: Rectangle {
              required property var modelData
              width: colCtx.width; height: 34; radius: 5
              color: mo.containsMouse ? Tema.hover : "transparent"
              Row {
                anchors.verticalCenter: parent.verticalCenter
                x: 10; spacing: 10
                Glifo { g: modelData.g; tamanho: 15; color: Tema.texto2; anchors.verticalCenter: parent.verticalCenter }
                Texto { text: modelData.t; anchors.verticalCenter: parent.verticalCenter }
              }
              MouseArea {
                id: mo
                anchors.fill: parent
                hoverEnabled: true
                onClicked: {
                  // lê tudo antes de fechar: fechar o menu destrói este item
                  var id = ctx.idApp, op = modelData.id, mm = m
                  mm.contexto = null
                  if (op === "fixar") mm.fixar(id)
                  else if (op === "desafixar") mm.desafixar(id)
                  else if (op === "inicio") mm.paraInicio(id)
                  else if (op === "barra") mm.fixarBarra(id, true)
                  else if (op === "desbarra") mm.fixarBarra(id, false)
                  else if (op === "abrir") mm.abrirApp(id)
                }
              }
            }
          }
        }
      }
    }
  }
}
