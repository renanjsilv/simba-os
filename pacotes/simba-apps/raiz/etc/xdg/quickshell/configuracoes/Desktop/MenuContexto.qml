import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Wayland
import qs.Comum

// Windows 11-style context menu for the desktop and its icons.
// Icon menu: a row of quick actions (cut, copy, rename, delete) on top, then
// the list. Submenus open on hover or →; ↑↓ move, Enter runs, ← / Esc go back.
Scope {
  id: m
  property var area: null
  property bool aberto: false
  property string tela: ""
  property real px: 0
  property real py: 0
  property string tipo: "area"   // "area" | "icone"
  property int indice: -1
  property int sub: -1            // index of the row whose submenu is open
  property int indiceSub: -1

  function abrir(t, x, y, k) {
    tela = t; px = x; py = y; tipo = k
    indice = -1; sub = -1; indiceSub = -1
    aberto = true
  }
  function fechar() { aberto = false; sub = -1 }

  readonly property var sel: area ? area.selecao : []
  readonly property var itemSel: {
    if (!area || sel.length !== 1) return null
    return area.itens.filter(function(i) { return i.caminho === sel[0] })[0] || null
  }

  function marca(v) { return v ? "check" : "" }
  readonly property var itensArea: [
    { id: "exibir", rotulo: I18n.t("Exibir"), glifo: Icones.viewGridOutline, sub: [
      { id: "grande", rotulo: I18n.t("Ícones grandes"), glifo: Icones.viewGrid, radio: area && area.tamanhoNome === "grande" },
      { id: "medio", rotulo: I18n.t("Ícones médios"), glifo: Icones.viewGridOutline, radio: area && area.tamanhoNome === "medio" },
      { id: "pequeno", rotulo: I18n.t("Ícones pequenos"), glifo: Icones.dotsHorizontal, radio: area && area.tamanhoNome === "pequeno" },
      { separador: true },
      { id: "auto", rotulo: I18n.t("Organizar ícones automaticamente"), marcado: area && area.automatico },
      { id: "grade", rotulo: I18n.t("Alinhar ícones à grade"), marcado: area && area.grade },
      { separador: true },
      { id: "mostrar", rotulo: I18n.t("Mostrar ícones da área de trabalho"), marcado: area && area.mostrar },
      { id: "mostrarLixeira", rotulo: I18n.t("Mostrar a Lixeira"), marcado: area && area.lixeira }
    ] },
    { id: "classificar", rotulo: I18n.t("Classificar por"), glifo: Icones.sortVariant, sub: [
      { id: "nome", rotulo: I18n.t("Nome"), radio: area && area.ordenar === "nome" },
      { id: "tamanho", rotulo: I18n.t("Tamanho"), radio: area && area.ordenar === "tamanho" },
      { id: "tipo", rotulo: I18n.t("Tipo de item"), radio: area && area.ordenar === "tipo" },
      { id: "data", rotulo: I18n.t("Data de modificação"), radio: area && area.ordenar === "data" }
    ] },
    { id: "atualizar", rotulo: I18n.t("Atualizar"), glifo: Icones.refresh, tecla: "F5" },
    { separador: true },
    { id: "novo", rotulo: I18n.t("Novo"), glifo: Icones.plusCircle, sub: [
      { id: "novaPasta", rotulo: I18n.t("Pasta"), glifo: Icones.folderPlus },
      { id: "novoTexto", rotulo: I18n.t("Documento de texto"), glifo: Icones.textBoxPlusOutline }
    ] },
    { separador: true },
    { id: "colar", rotulo: I18n.t("Colar"), glifo: Icones.contentPaste, tecla: I18n.t("Ctrl+V") },
    { id: "colarAtalho", rotulo: I18n.t("Colar atalho"), glifo: Icones.linkVariant },
    { separador: true },
    { id: "mostrarArea", rotulo: I18n.t("Mostrar a área de trabalho"), glifo: Icones.monitor },
    { separador: true },
    { id: "terminal", rotulo: I18n.t("Abrir no Terminal"), glifo: Icones.terminal },
    { id: "pasta", rotulo: I18n.t("Abrir a pasta da área de trabalho"), glifo: Icones.folderOpen },
    { separador: true },
    { id: "proximoFundo", rotulo: I18n.t("Próximo papel de parede"), glifo: Icones.imageMultiple },
    { id: "fundo", rotulo: I18n.t("Alterar papel de parede…"), glifo: Icones.wallpaper },
    { separador: true },
    { id: "exibicao", rotulo: I18n.t("Configurações de exibição"), glifo: Icones.monitor },
    { id: "personalizar", rotulo: I18n.t("Personalizar"), glifo: Icones.palette },
    { id: "config", rotulo: I18n.t("Configurações"), glifo: Icones.cog, tecla: "" }
  ]
  readonly property var acoesIcone: [
    { id: "recortar", rotulo: I18n.t("Recortar"), glifo: Icones.contentCut },
    { id: "copiar", rotulo: I18n.t("Copiar"), glifo: Icones.contentCopy },
    { id: "renomear", rotulo: I18n.t("Renomear"), glifo: Icones.renameBox, habilitado: sel.length === 1 },
    { id: "excluir", rotulo: I18n.t("Excluir"), glifo: Icones.lixeira }
  ]
  readonly property var itensLixeira: [
    { id: "abrir", rotulo: I18n.t("Abrir"), glifo: Icones.openInNew, tecla: I18n.t("Enter"), negrito: true },
    { id: "esvaziarLixeira", rotulo: I18n.t("Esvaziar Lixeira"), glifo: Icones.lixeira, habilitado: !!(itemSel && itemSel.cheia) },
    { separador: true },
    { id: "ocultarLixeira", rotulo: I18n.t("Ocultar a Lixeira da área de trabalho"), glifo: Icones.eyeOff }
  ]
  readonly property var itensIcone: {
    var it = itemSel
    if (it && it.especial === "lixeira") return itensLixeira
    var l = [{ id: "abrir", rotulo: sel.length > 1 ? I18n.t("Abrir ") + sel.length + " itens" : I18n.t("Abrir"), glifo: Icones.openInNew, tecla: I18n.t("Enter"), negrito: true }]
    if (it && it.pasta) l.push({ id: "terminalItem", rotulo: I18n.t("Abrir no Terminal"), glifo: Icones.terminal })
    if (it && it.imagem) l.push({ id: "definirFundo", rotulo: I18n.t("Definir como papel de parede"), glifo: Icones.wallpaper })
    l.push({ separador: true })
    l.push({ id: "copiarCaminho", rotulo: sel.length > 1 ? I18n.t("Copiar caminhos") : I18n.t("Copiar como caminho"), glifo: Icones.linkVariant })
    l.push({ id: "revelar", rotulo: I18n.t("Mostrar no Arquivos"), glifo: Icones.folderOpen })
    l.push({ id: "enviarLocalSend", rotulo: I18n.t("Enviar com LocalSend (celular e PC)"), glifo: Icones.cellphoneLink })
    l.push({ separador: true })
    l.push({ id: "propriedades", rotulo: I18n.t("Propriedades"), glifo: Icones.informationOutline, tecla: I18n.t("Alt+Enter"), habilitado: sel.length === 1 })
    return l
  }
  readonly property var itens: tipo === "icone" ? itensIcone : itensArea

  function executar(id) {
    var a = area
    var abrirCfg = function(p) { Navegacao.abrir(p) }
    switch (id) {
    case "grande": case "medio": case "pequeno": area.definirTamanho(id); break
    case "auto": Preferencias.definir("area.automatico", !a.automatico); if (!a.automatico) Preferencias.definir("area.posicoes", {}); break
    case "grade": Preferencias.definir("area.grade", !a.grade); break
    case "mostrar": Preferencias.definir("area.mostrarIcones", !a.mostrar); break
    case "mostrarLixeira": Preferencias.definir("area.lixeira", !a.lixeira); break
    case "ocultarLixeira": Preferencias.definir("area.lixeira", false); a.selecao = []
      Sistema.notificar(I18n.t("Lixeira oculta. Para mostrar de novo: botão direito na área de trabalho › Exibir › Mostrar a Lixeira"), "󰩹"); break
    case "esvaziarLixeira": a.esvaziarLixeira(); break
    case "nome": case "tamanho": case "tipo": case "data": Preferencias.definir("area.ordenar", id); Preferencias.definir("area.posicoes", {}); break
    case "atualizar": a.atualizar(); break
    case "novaPasta": a.novaPasta(); break
    case "novoTexto": a.novoTexto(); break
    case "colar": a.colar(false); break
    case "colarAtalho": a.colar(true); break
    case "mostrarArea": Sistema.solto(["qs", "-c", "botoes-janela", "ipc", "call", "botoes", "mostrarArea"]); break
    case "terminal": Sistema.solto(["uwsm-app", "--", "xdg-terminal-exec", "--dir=" + a.pasta]); break
    case "pasta": Sistema.solto(["uwsm-app", "--", "nautilus", "--new-window", a.pasta]); break
    case "proximoFundo": Sistema.solto(["simba-theme-bg-next"]); break
    case "fundo": abrirCfg("personalizacao"); Navegacao.ir("personalizacao", "papel"); break
    case "exibicao": abrirCfg("tela"); break
    case "personalizar": abrirCfg("personalizacao"); break
    case "config": abrirCfg("inicio"); break
    // icon menu
    case "abrir": a.selecao.forEach(function(c) { a.abrirItem(c) }); break
    case "terminalItem": if (m.itemSel) Sistema.solto(["uwsm-app", "--", "xdg-terminal-exec", "--dir=" + m.itemSel.caminho]); break
    case "definirFundo": if (m.itemSel) a.definirFundo(m.itemSel.caminho); break
    case "copiarCaminho": Sistema.rodar(["wl-copy", a.selecao.join("\n")]); break
    case "revelar": Sistema.solto(["uwsm-app", "--", "nautilus", "--new-window", "--select", a.selecao[0]]); break
    case "enviarLocalSend": if (a.selecao && a.selecao.length > 0) Sistema.solto(["localsend"].concat(a.selecao)); break
    case "propriedades": if (m.itemSel) a.propriedades(m.itemSel.caminho); break
    case "recortar": a.copiar(true); break
    case "copiar": a.copiar(false); break
    case "renomear": if (m.itemSel) a.renomear(m.itemSel.caminho); break
    case "excluir": a.excluir(); break
    }
  }
  function ativar(item) {
    if (!item || item.separador || item.habilitado === false) return
    if (item.sub) return
    fechar()
    executar(item.id)
  }

  function proximo(lista, i, d) {
    var n = lista.length
    for (var k = 0; k < n; k++) {
      i = (i + d + n) % n
      if (!lista[i].separador && lista[i].habilitado !== false) return i
    }
    return -1
  }

  Variants {
    model: m.aberto ? Quickshell.screens.filter(function(s) { return s.name === m.tela }) : []
    delegate: PanelWindow {
      id: w
      required property var modelData
      screen: modelData
      anchors { top: true; bottom: true; left: true; right: true }
      exclusionMode: ExclusionMode.Ignore
      color: "transparent"
      WlrLayershell.layer: WlrLayer.Overlay
      WlrLayershell.namespace: "configuracoes-menu"
      WlrLayershell.keyboardFocus: WlrKeyboardFocus.Exclusive

      MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onPressed: m.fechar()
      }

      Item {
        id: teclado
        anchors.fill: parent
        focus: true
        Component.onCompleted: forceActiveFocus()
        Keys.onPressed: function(e) {
          var lista = m.itens
          if (m.sub >= 0) {
            var sl = lista[m.sub].sub
            if (e.key === Qt.Key_Down) m.indiceSub = m.proximo(sl, m.indiceSub, 1)
            else if (e.key === Qt.Key_Up) m.indiceSub = m.proximo(sl, m.indiceSub < 0 ? 0 : m.indiceSub, -1)
            else if (e.key === Qt.Key_Left || e.key === Qt.Key_Escape) { m.sub = -1; m.indiceSub = -1 }
            else if (e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.key === Qt.Key_Space) m.ativar(sl[m.indiceSub])
            e.accepted = true
            return
          }
          if (e.key === Qt.Key_Escape) m.fechar()
          else if (e.key === Qt.Key_Down) m.indice = m.proximo(lista, m.indice, 1)
          else if (e.key === Qt.Key_Up) m.indice = m.proximo(lista, m.indice < 0 ? 0 : m.indice, -1)
          else if ((e.key === Qt.Key_Right || e.key === Qt.Key_Return || e.key === Qt.Key_Enter) && m.indice >= 0 && lista[m.indice].sub) { m.sub = m.indice; m.indiceSub = m.proximo(lista[m.indice].sub, -1, 1) }
          else if ((e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.key === Qt.Key_Space) && m.indice >= 0) m.ativar(lista[m.indice])
          else if (e.key === Qt.Key_F5) { m.fechar(); m.area.atualizar() }
          else if (e.key === Qt.Key_Delete && m.tipo === "icone") { m.fechar(); m.area.excluir() }
          else if (e.key === Qt.Key_F2 && m.tipo === "icone" && m.itemSel) { m.fechar(); m.area.renomear(m.itemSel.caminho) }
          else if ((e.modifiers & Qt.ControlModifier) && e.key === Qt.Key_C && m.tipo === "icone") { m.fechar(); m.area.copiar(false) }
          else if ((e.modifiers & Qt.ControlModifier) && e.key === Qt.Key_X && m.tipo === "icone") { m.fechar(); m.area.copiar(true) }
          else if ((e.modifiers & Qt.ControlModifier) && e.key === Qt.Key_V) { m.fechar(); m.area.colar(false) }
          e.accepted = true
        }
      }

      CartaoMenu {
        id: principal
        itens: m.itens
        acoes: m.tipo === "icone" ? m.acoesIcone : []
        atual: m.sub >= 0 ? m.sub : m.indice
        subAberto: m.sub
        x: Math.max(6, Math.min(m.px + 2, w.width - width - 6))
        y: Math.max(6, Math.min(m.py + 2, w.height - height - 6))
        origemX: m.px - x
        origemY: m.py - y
        onPassou: function(i) {
          m.indice = i
          if (m.itens[i] && m.itens[i].sub) { abrirSub.alvo = i; abrirSub.restart() }
          else { abrirSub.stop(); if (m.sub >= 0) fecharSub.restart() }
        }
        onEscolheu: function(i) {
          var it = m.itens[i]
          if (it.sub) { m.sub = i; m.indiceSub = -1 }
          else m.ativar(it)
        }
        onAcao: function(id) { m.fechar(); m.executar(id) }
      }
      Timer { id: abrirSub; property int alvo: -1; interval: 180; onTriggered: { fecharSub.stop(); m.sub = alvo; m.indiceSub = -1 } }
      Timer { id: fecharSub; interval: 260; onTriggered: if (!secundario.containsMouse) { m.sub = -1; m.indiceSub = -1 } }

      CartaoMenu {
        id: secundario
        visible: m.sub >= 0 && !!m.itens[m.sub] && !!m.itens[m.sub].sub
        itens: visible ? m.itens[m.sub].sub : []
        atual: m.indiceSub
        readonly property var linha: m.sub >= 0 ? principal.posicaoLinha(m.sub) : 0
        readonly property bool aDireita: principal.x + principal.width + width + 4 < w.width
        x: aDireita ? principal.x + principal.width - 4 : principal.x - width + 4
        y: Math.max(6, Math.min(principal.y + linha - 6, w.height - height - 6))
        origemX: aDireita ? 0 : width
        origemY: 16
        onPassou: function(i) { m.indiceSub = i; fecharSub.stop() }
        onEscolheu: function(i) { m.ativar(m.itens[m.sub].sub[i]) }
        onContainsMouseChanged: if (containsMouse) fecharSub.stop()
      }
    }
  }
}
