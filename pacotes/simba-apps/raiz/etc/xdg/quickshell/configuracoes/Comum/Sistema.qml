pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// Process helpers shared by the desktop layer, Super+P and the settings window.
Singleton {
  id: s

  readonly property string home: Quickshell.env("HOME")
  readonly property string runtime: (Quickshell.env("XDG_RUNTIME_DIR") || "/tmp") + "/configuracoes"
  readonly property string bin: Quickshell.shellDir + "/bin"
  readonly property string tela: bin + "/tela"
  readonly property string bloco: bin + "/bloco"
  readonly property string ajudante: bin + "/ajudante"

  // Single-quote a value for bash.
  function q(v) { return "'" + String(v).replace(/'/g, "'\\''") + "'" }

  // Run argv; done(stdout, exitCode, stderr) when it finishes.
  function rodar(argv, done, stdin) {
    var p = processo.createObject(s, { command: argv, entrada: stdin === undefined ? null : String(stdin) })
    p.feito = done || null
    p.running = true
    return p
  }
  function sh(script, done, stdin) { return rodar(["bash", "-c", script], done, stdin) }
  function json(argv, done) {
    return rodar(argv, function(out, code) {
      var v = null
      try { v = JSON.parse(out) } catch (e) { v = null }
      if (done) done(v, code)
    })
  }
  function solto(argv) { Quickshell.execDetached(argv) }
  function soltoSh(script) { Quickshell.execDetached(["bash", "-c", script]) }

  // Live Hyprland change (persistence is written separately).
  function hypr(lua, done) { return rodar(["hyprctl", "eval", lua], done) }

  function notificar(texto, glifo) {
    soltoSh("simba-notification-send " + (glifo ? "-g " + q(glifo) + " " : "") + q(texto))
  }

  Component {
    id: processo
    Process {
      id: pr
      property var feito: null
      property var entrada: null
      stdinEnabled: entrada !== null
      stdout: StdioCollector { id: saida }
      stderr: StdioCollector { id: erro }
      onStarted: {
        if (entrada !== null) { write(entrada); stdinEnabled = false }
      }
      onExited: function(code) {
        var f = feito
        feito = null
        if (f) {
          try { f(saida.text, code, erro.text) } catch (e) {
            // A page closed before its command finished leaves its ids null:
            // nothing to update, not an error.
            if (!/is null|of null|is undefined/.test(String(e)))
              console.warn("configuracoes:", e, "\n", e.stack, "\n cmd:", JSON.stringify(command).slice(0, 160))
          }
        }
        destroy()
      }
    }
  }
}
