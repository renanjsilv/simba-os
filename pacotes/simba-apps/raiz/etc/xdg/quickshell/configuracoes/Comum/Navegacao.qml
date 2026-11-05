pragma Singleton
import QtQuick
import Quickshell

// Which settings page is showing and which row a search result points at.
Singleton {
  property string pagina: "inicio"
  property string destaque: ""
  property int pulso: 0
  property bool janelaAberta: false
  property var confirmacao: null   // Projetar/Confirmacao (set by shell.qml)
  property var identificar: null
  property var paginaAtual: null   // the Pagina (Flickable) on screen, for tests
  property int versaoFoto: 0       // bumps when ~/.face changes (conta foto) — Avatar reloads
  signal pedirJanela()
  // Short confirmation pill at the bottom of the window ("Tema aplicado").
  signal aviso(string texto, string glifo)
  function confirmar(texto, glifo) { aviso(texto, glifo || "") }

  function ir(p, chave) {
    pagina = p || "inicio"
    destaque = chave || ""
    pulso++
  }
  function abrir(p, chave) {
    if (p) ir(p, chave)
    pedirJanela()
  }
}
