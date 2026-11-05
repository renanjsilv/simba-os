pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// App preferences: ~/.config/configuracoes/preferencias.json
//
// Holds what has no other home: desktop icon options and positions, the night
// light temperature/schedule, the animation speed and the Hyprland options the
// user changed in the app (regenerated into the managed blocks of
// ~/.config/hypr/looknfeel.lua and input.lua). Everything with a real config
// file elsewhere (shell.json, monitors.lua, hyprsunset.conf, ...) lives there.
Singleton {
  id: p

  readonly property string pasta: Quickshell.env("HOME") + "/.config/configuracoes"
  readonly property string caminho: pasta + "/preferencias.json"
  property bool pronto: false

  property var dados: ({})

  readonly property var padroes: ({
    area: {
      mostrarIcones: true,
      tamanho: "medio",        // pequeno | medio | grande
      ordenar: "nome",         // nome | tamanho | tipo | data
      automatico: false,       // organizar automaticamente
      grade: true,             // alinhar à grade
      ocultos: false,
      pasta: "",               // "" = XDG desktop dir
      tela: "",                // "" = the monitor at 0,0
      posicoes: {}
    },
    luzNoturna: { temperatura: 4000, agendar: false, inicio: "20:00", fim: "07:00" },
    animVelocidade: 1.0,
    hypr: {},
    gestos: false
  })

  function obter(caminhoChave, padrao) {
    var partes = caminhoChave.split(".")
    var v = dados
    for (var i = 0; i < partes.length; i++) {
      if (v === undefined || v === null || typeof v !== "object") { v = undefined; break }
      v = v[partes[i]]
    }
    if (v === undefined) {
      v = padroes
      for (var j = 0; j < partes.length; j++) {
        if (v === undefined || v === null) break
        v = v[partes[j]]
      }
    }
    return v === undefined ? padrao : v
  }

  function definir(caminhoChave, valor) {
    var copia = JSON.parse(JSON.stringify(dados || {}))
    var partes = caminhoChave.split(".")
    var alvo = copia
    for (var i = 0; i < partes.length - 1; i++) {
      if (typeof alvo[partes[i]] !== "object" || alvo[partes[i]] === null) alvo[partes[i]] = {}
      alvo = alvo[partes[i]]
    }
    if (valor === undefined) delete alvo[partes[partes.length - 1]]
    else alvo[partes[partes.length - 1]] = valor
    dados = copia
    salvar.restart()
  }

  property Timer salvar: Timer {
    interval: 350
    onTriggered: {
      arquivo.setText(JSON.stringify(p.dados, null, 2) + "\n")
    }
  }

  property FileView arquivo: FileView {
    path: p.caminho
    printErrors: false
    watchChanges: true
    atomicWrites: true
    onFileChanged: reload()
    onLoaded: {
      try { p.dados = JSON.parse(text()) || {} } catch (e) { p.dados = {} }
      p.pronto = true
    }
    onLoadFailed: {
      p.dados = {}
      p.pronto = true
      Quickshell.execDetached(["mkdir", "-p", p.pasta])
    }
  }
}
