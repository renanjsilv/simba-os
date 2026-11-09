pragma Singleton
import QtQuick
import Quickshell
import qs.Comum

// Hyprland options the app edits.
//
// Reading: `hyprctl getoption` (live truth, whatever file set it).
// Changing: applied at once with `hyprctl eval hl.config{...}`, remembered in
// Preferencias.hypr, and written as a managed block (see bin/bloco) at the end of
//   ~/.config/hypr/looknfeel.lua   general / decoration / animations / cursor
//   ~/.config/hypr/input.lua       input (+ touchpad gestures)
// so it survives reloads and reboots. The user's own lines in those files are
// never touched; the block comes last, so the app's choice wins.
Singleton {
  id: h

  property var valores: ({})
  property bool carregado: false
  property string erro: ""

  readonly property var looknfeel: [
    "general:gaps_in", "general:gaps_out", "general:border_size", "general:layout", "general:resize_on_border",
    "decoration:rounding", "decoration:rounding_power", "decoration:active_opacity", "decoration:inactive_opacity",
    "decoration:dim_inactive", "decoration:dim_strength",
    "decoration:blur:enabled", "decoration:blur:size", "decoration:blur:passes", "decoration:blur:vibrancy",
    "decoration:shadow:enabled", "decoration:shadow:range", "decoration:shadow:render_power",
    "animations:enabled", "cursor:hide_on_key_press", "cursor:inactive_timeout", "misc:focus_on_activate",
    "cursor:default_monitor"
  ]
  readonly property var entrada: [
    "input:kb_layout", "input:kb_variant", "input:kb_options", "input:repeat_rate", "input:repeat_delay",
    "input:numlock_by_default", "input:sensitivity", "input:accel_profile", "input:natural_scroll",
    "input:follow_mouse", "input:scroll_factor", "input:left_handed",
    "input:touchpad:natural_scroll", "input:touchpad:tap-to-click", "input:touchpad:clickfinger_behavior",
    "input:touchpad:disable_while_typing", "input:touchpad:scroll_factor", "input:touchpad:drag_3fg"
  ]

  // Simba's default animation leaves (default/hypr/looknfeel.lua); the speed
  // preference rewrites them scaled (Hyprland speed is duration: bigger = slower).
  readonly property var folhas: [
    ["global", 10, "default", ""], ["border", 5.39, "easeOutQuint", ""], ["windows", 3.79, "easeOutQuint", ""],
    ["windowsIn", 4.1, "easeOutQuint", I18n.t("popin 87%")], ["windowsOut", 1.49, "linear", I18n.t("popin 87%")],
    ["fadeIn", 1.73, "almostLinear", ""], ["fadeOut", 1.46, "almostLinear", ""], ["fade", 3.03, "quick", ""],
    ["layers", 3.81, "easeOutQuint", ""], ["layersIn", 4, "easeOutQuint", "fade"], ["layersOut", 1.5, "linear", "fade"],
    ["fadeLayersIn", 1.79, "almostLinear", ""], ["fadeLayersOut", 1.39, "almostLinear", ""],
    ["specialWorkspace", 3, "easeOutQuint", "slidevert"]
  ]

  function valor(chave, padrao) {
    var v = valores[chave]
    return v === undefined || v === null ? padrao : v
  }

  function recarregar(done) {
    Sistema.json([Sistema.ajudante, "opcoes"].concat(looknfeel).concat(entrada), function(v) {
      if (v) { valores = v; carregado = true }
      if (done) done()
    })
  }

  function caminhoLua(chave) { return chave.split(":").map(function(p) { return p.replace(/-/g, "_") }) }

  function literal(v) {
    if (typeof v === "boolean") return v ? "true" : "false"
    if (typeof v === "number") return String(Number(v.toFixed(4)))
    return '"' + String(v).replace(/\\/g, "\\\\").replace(/"/g, '\\"') + '"'
  }

  // {"a:b:c": v, ...} -> "{ a = { b = { c = v } } }" (pretty, sorted)
  function tabelaLua(mapa, recuo) {
    var arvore = {}
    Object.keys(mapa).sort().forEach(function(k) {
      var partes = caminhoLua(k)
      var no = arvore
      for (var i = 0; i < partes.length - 1; i++) {
        if (typeof no[partes[i]] !== "object") no[partes[i]] = {}
        no = no[partes[i]]
      }
      no[partes[partes.length - 1]] = { __v: mapa[k] }
    })
    function emitir(no, nivel) {
      var pad = "  ".repeat(nivel)
      var linhas = []
      Object.keys(no).sort().forEach(function(k) {
        var v = no[k]
        if (v && v.__v !== undefined) linhas.push(pad + k + " = " + literal(v.__v) + ",")
        else {
          linhas.push(pad + k + " = {")
          linhas = linhas.concat(emitir(v, nivel + 1))
          linhas.push(pad + "},")
        }
      })
      return linhas
    }
    return ["{"].concat(emitir(arvore, (recuo || 0) + 1)).concat(["  ".repeat(recuo || 0) + "}"]).join("\n")
  }

  function separar(over) {
    var a = {}, b = {}
    Object.keys(over).forEach(function(k) {
      if (k.indexOf("input:") === 0) b[k] = over[k]
      else a[k] = over[k]
    })
    return [a, b]
  }

  function blocoLooknfeel() {
    var over = separar(Preferencias.obter("hypr", {}))[0]
    var linhas = []
    if (Object.keys(over).length) linhas.push("hl.config(" + tabelaLua(over, 0) + ")")
    if (Preferencias.obter("barraDesfoque", false)) {
      // Vidro fosco atrás da barra: o desfoque cobre a barra inteira e a
      // transparência da barra (simba-bar transparency) define o quanto da cor
      // do tema fica por cima. Só a barra: os fantasmas de arrasto têm outro nome.
      linhas.push("-- Barra com desfoque (Configurações › Personalização › Barra)")
      linhas.push('hl.layer_rule({ match = { namespace = "^simba-bar$" }, blur = true })')
    }
    var k = Number(Preferencias.obter("animVelocidade", 1.0))
    if (k > 0 && Math.abs(k - 1) > 0.001) {
      linhas.push("-- Velocidade das animações: " + k + I18n.t("× a duração padrão do Simba"))
      folhas.forEach(function(f) {
        linhas.push(I18n.t('hl.animation({ leaf = "') + f[0] + I18n.t('", enabled = true, speed = ') + Number((f[1] * k).toFixed(2)) +
                    I18n.t(', bezier = "') + f[2] + '"' + (f[3] ? I18n.t(', style = "') + f[3] + '"' : "") + " })")
      })
    }
    return linhas.join("\n")
  }

  function blocoEntrada() {
    var over = separar(Preferencias.obter("hypr", {}))[1]
    var linhas = []
    if (Object.keys(over).length) linhas.push("hl.config(" + tabelaLua(over, 0) + ")")
    if (Preferencias.obter("gestos", false)) {
      linhas.push("-- Gesto: deslizar com 3 dedos troca de área de trabalho")
      linhas.push(I18n.t('hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })'))
    }
    return linhas.join("\n")
  }

  // Change one option: live, remembered, persisted.
  function definir(chave, v) {
    var over = JSON.parse(JSON.stringify(Preferencias.obter("hypr", {})))
    over[chave] = v
    Preferencias.definir("hypr", over)
    var novo = Object.assign({}, valores)
    novo[chave] = v
    valores = novo
    var m = {}
    m[chave] = v
    Sistema.hypr("hl.config(" + tabelaLua(m, 0).replace(/\n\s*/g, " ") + ")", function(out) {
      if (out.indexOf("error") >= 0) h.erro = out.trim()
    })
    if (chave === "decoration:rounding") Tema.arredondamento = Number(v)
    if (chave === "animations:enabled") Tema.animacoes = !!v
    gravar.restart()
  }

  // Forget the app's value for an option: the user's/Simba's value returns.
  function restaurar(chaves) {
    var over = JSON.parse(JSON.stringify(Preferencias.obter("hypr", {})))
    chaves.forEach(function(c) { delete over[c] })
    Preferencias.definir("hypr", over)
    gravar.restart()
    recarregarDepois.restart()
  }
  function personalizado(chave) { return Preferencias.obter("hypr", {})[chave] !== undefined }

  function definirVelocidade(k) {
    Preferencias.definir("animVelocidade", k)
    gravar.restart()
    recarregarDepois.restart()
  }
  function definirDesfoqueBarra(on) {
    Preferencias.definir("barraDesfoque", on)
    gravar.restart()
  }
  function definirGestos(on) {
    Preferencias.definir("gestos", on)
    gravar.restart()
  }

  property Timer gravar: Timer {
    interval: 700
    onTriggered: {
      var home = Quickshell.env("HOME")
      Sistema.rodar([Sistema.bloco, home + "/.config/hypr/looknfeel.lua"], function() {
        Sistema.rodar([Sistema.bloco, home + "/.config/hypr/input.lua"], function() {
          Sistema.sh("hyprctl reload config-only >/dev/null; sleep 0.3; hyprctl configerrors", function(out) {
            var e = out.trim()
            h.erro = e.length > 0 && e !== "no errors" ? e : ""
            Tema.recarregar()
          })
        }, h.blocoEntrada())
      }, h.blocoLooknfeel())
    }
  }
  property Timer recarregarDepois: Timer { interval: 1600; onTriggered: h.recarregar() }
}
