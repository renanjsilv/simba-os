//@ pragma AppId com.renan.Configuracoes
// Configurações: settings app, Win+P-style display switcher and desktop layer
// (right-click menu + icons) for Simba, in one long-running Quickshell.
//
//   qs -c configuracoes -n -d          started from ~/.config/hypr/autostart.lua
//   /usr/bin/configuracoes [página] open the settings window (launcher entry)
//   /usr/bin/configuracoes projetar Super+P
//   /usr/bin/configuracoes menu-iniciar  Super+Espaço / botão Iniciar (Iniciar/Iniciar.qml)
//
// Commands arrive through $XDG_RUNTIME_DIR/configuracoes/cmd (one JSON line per
// command, appended by /usr/bin/configuracoes; inotify makes it instant) or
// through IPC: qs -c configuracoes ipc call configuracoes <função> ...
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Hyprland
import qs.Comum
import qs.Desktop
import qs.Projetar
import qs.Janela
import qs.Iniciar

ShellRoot {
  id: raiz

  // ── commands ─────────────────────────────────────────────────────────────
  function executar(c, a) {
    switch (c) {
    case "abrir": Navegacao.abrir(a[0] || "", a[1] || ""); break
    case "fechar": janela.fechar(); break
    case "alternar": if (janela.aberta) janela.fechar(); else Navegacao.abrir(a[0] || ""); break
    case "projetar": projetar.alternar(); break
    case "tema": Tema.recarregar(); break
    case "menu": desktop.abrirMenuEm(a[0] || "", Number(a[1] || 0), Number(a[2] || 0)); break
    case "atualizar": desktop.atualizar(); break
    case "menu-iniciar": if (a[0] === "abrir") iniciar.abrir(); else if (a[0] === "fechar") iniciar.fechar(); else iniciar.alternar(); break
    }
  }

  property string ultimoSeq: ""
  property bool cmdPronto: false
  function lerComandos(t) {
    var linhas = t.split("\n")
    for (var i = 0; i < linhas.length; i++) {
      if (!linhas[i]) continue
      var m
      try { m = JSON.parse(linhas[i]) } catch (e) { continue }
      var seq = String(m.s)
      if (seq.length < ultimoSeq.length || (seq.length === ultimoSeq.length && seq <= ultimoSeq)) continue
      ultimoSeq = seq
      if (cmdPronto) executar(m.c, m.a || [])
    }
    cmdPronto = true
  }

  FileView {
    id: arquivoCmd
    path: Sistema.runtime + "/cmd"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: { raiz.lerComandos(text()); esperaCmd.stop() }
    // Sem o arquivo ainda (sistema recém-instalado): não há o que vigiar, então tenta de
    // novo até ele aparecer — senão o botão Iniciar e os outros comandos se perdem.
    onLoadFailed: { raiz.cmdPronto = true; esperaCmd.start() }
  }
  Timer { id: esperaCmd; interval: 500; repeat: true; onTriggered: arquivoCmd.reload() }

  FileView { id: pidArquivo; path: Sistema.runtime + "/pid"; printErrors: false }

  IpcHandler {
    target: "configuracoes"
    function abrir(pagina: string): void { Navegacao.abrir(pagina) }
    function buscar(chave: string): void {
      // Opens the page that holds a setting and highlights it (tests, links).
      var r = janela.paginaDaChave(chave)
      Navegacao.abrir(r, chave)
    }
    function fechar(): void { janela.fechar() }
    // Tests: open the Start menu already searching for a text.
    function iniciarBuscar(texto: string): void { iniciar.abrir(); iniciar.texto = texto }
    function projetar(): void { projetar.alternar() }
    function projetarFechar(): void { projetar.fechar() }
    function projetarSelecionar(modo: string): void { projetar.selecionar(modo) }
    function projetarAplicar(modo: string): void { projetar.aplicar(modo) }
    function manter(): void { confirmacao.manter() }
    // Tests: arm a no-op revertible change and show the keep/revert dialog.
    function confirmarTeste(): void {
      Sistema.sh(Sistema.q(Sistema.tela) + " snapshot; " + Sistema.q(Sistema.tela) + " pendente 15", function() { confirmacao.iniciar() })
    }
    function reverter(): void { confirmacao.reverter() }
    function menu(tela: string, x: int, y: int): void { desktop.abrirMenuEm(tela, x, y) }
    function menuIcone(tela: string, nome: string): void { desktop.abrirMenuIcone(tela, nome) }
    function menuFechar(): void { desktop.fecharMenu() }
    function atualizar(): void { desktop.atualizar() }
    function espiar(ms: int): void { desktop.espiar(ms) }
    function areaZoom(passos: int): void { desktop.zoom(passos) }
    function icone(nome: string): string { return Quickshell.iconPath(nome, true) }
    // Run a desktop-menu action by id (tests): atualizar, novaPasta, novoTexto, colar, …
    function areaAcao(id: string): void { desktop.acao(id) }
    function areaSelecionar(nome: string): void { desktop.selecionarNome(nome) }
    function renomearCancelar(): void { desktop.cancelarRenomear() }
    function renomearPara(texto: string): void { desktop.concluirRenomear(texto) }
    function propriedadesFechar(): void { desktop.fecharPropriedades() }
    // Tests: change / forget a Hyprland option exactly like the pages do.
    function hyprDefinir(chave: string, json: string): void { Hypr.definir(chave, JSON.parse(json)) }
    function hyprRestaurar(chave: string): void { Hypr.restaurar([chave]) }
    function preferencia(chave: string, json: string): void { Preferencias.definir(chave, json === "" ? undefined : JSON.parse(json)) }
    function estado(): string {
      return JSON.stringify({ janela: janela.aberta, pagina: Navegacao.pagina, tema: Tema.nome, escuro: Tema.escuro,
                              projetar: projetar.aberto, confirmacao: confirmacao.aberta, menu: desktop.menuAberto,
                              icones: desktop.totalIcones })
    }
    function tema(): void { Tema.recarregar() }
    // Testes: cores de outro tema só na memória (tema() volta ao real).
    function temaPrevia(fundo: string, texto: string, acento: string): void { Tema.fundo = fundo; Tema.texto = texto; Tema.acento = acento }
    // Menu Iniciar (testes): abrir/fechar, pesquisar, estado
    function iniciarAlternar(): void { iniciar.alternar() }
    function iniciarPesquisar(t: string): void { iniciar.texto = t }
    function iniciarPagina(p: string): void { iniciar.pagina = p }
    function iniciarEstado(): string {
      return JSON.stringify({ aberto: iniciar.aberto, estilo: iniciar.estilo, apps: iniciar.apps.length, fixados: iniciar.fixados,
                              resultados: iniciar.resultados.map(function(r) { return r.tipo + ":" + r.titulo }), recentes: iniciar.recentes.length,
                              uso: Object.keys(iniciar.uso), maisUsados: iniciar.maisUsados.map(function(e) { return e.id }) })
    }
    function identificar(): void { identificar.mostrar() }
    function rolagem(): string {
      var p = Navegacao.paginaAtual
      return p ? JSON.stringify({ y: p.contentY, altura: p.contentHeight, vista: p.height }) : "{}"
    }
    function rolar(y: int): void { if (Navegacao.paginaAtual) Navegacao.paginaAtual.contentY = y }
  }

  Component.onCompleted: {
    Quickshell.execDetached(["mkdir", "-p", Sistema.runtime, Preferencias.pasta])
    pidArquivo.setText(String(Quickshell.processId) + "\n")
    Navegacao.confirmacao = confirmacao
    Navegacao.identificar = identificar
  }

  // ── pieces ───────────────────────────────────────────────────────────────
  AreaDeTrabalho { id: desktop }
  Confirmacao { id: confirmacao }
  Identificar { id: identificar }
  Projetar { id: projetar; confirmacao: confirmacao }
  Janela { id: janela; confirmacao: confirmacao }
  Iniciar { id: iniciar }
}
