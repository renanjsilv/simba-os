pragma Singleton
import QtQuick
import Quickshell
import Quickshell.Io

// Tradução dos componentes próprios do Simba OS (ver ../LEIA-ME.md).
// I18n.t("Texto em português") → texto no idioma da sessão (ou o próprio texto).
Singleton {
  id: i
  readonly property string pasta: "/usr/share/simba-apps/idiomas"
  // en_US.UTF-8 → ["en_US", "en"]; pt_* → [] (o código já está em português)
  readonly property string idioma: {
    var l = Quickshell.env("SIMBA_IDIOMA") || Quickshell.env("LC_ALL") || Quickshell.env("LC_MESSAGES") || Quickshell.env("LANG") || "pt_BR"
    l = String(l).split(".")[0].split("@")[0]
    return l === "C" || l === "POSIX" ? "en" : l
  }
  // separador decimal do idioma (1,5 GB / 1.5 GB)
  readonly property string decimal: portugues ? "," : "."
  readonly property bool portugues: idioma === "" || idioma.indexOf("pt") === 0
  // en_US.json (variante) por cima de en.json (língua)
  readonly property var mapa: {
    if (portugues) return ({})
    var r = ({}), fontes = [lingua.text(), variante.text()]
    for (var k = 0; k < fontes.length; k++) {
      if (!fontes[k]) continue
      try { var o = JSON.parse(fontes[k]); for (var c in o) r[c] = o[c] } catch (e) { }
    }
    return r
  }
  FileView { id: lingua; blockLoading: true; printErrors: false; path: i.portugues ? "" : i.pasta + "/" + i.idioma.split("_")[0] + ".json" }
  FileView { id: variante; blockLoading: true; printErrors: false; path: i.portugues || i.idioma.indexOf("_") < 0 ? "" : i.pasta + "/" + i.idioma + ".json" }

  function t(s) {
    if (s === undefined || s === null) return ""
    s = String(s)
    var m = i.mapa
    if (i.portugues || !s) return s
    var v = m[s]
    if (v !== undefined) return v
    var p = /^(\s*)([\s\S]*?)(\s*)$/.exec(s)
    v = m[p[2]]
    return v !== undefined ? p[1] + v + p[3] : s
  }
  // t com argumentos: I18n.f("%1 de %2", a, b)
  function f(s) {
    var r = t(s)
    for (var k = 1; k < arguments.length; k++) r = r.split("%" + k).join(String(arguments[k]))
    return r
  }
}
