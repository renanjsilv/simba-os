//@ pragma AppId com.simba.Draco
// Draco settings window (Super+F10, or `draco config`; opens by itself when F10 is
// pressed and no AI is configured yet).
//
// Two faces:
//   - first use (no AI chosen yet): a welcome with one big path ("Começar grátis", when
//     config.py offers a brain with semConta) and a secondary one (account or key);
//   - afterwards: a clean panel. Essentials on top (AI, voice, how to call it), the rest
//     (model, transcription, timings, wake word sensitivity) folded under "Avançado".
// Everything shown comes from `config.py status`: nothing about the providers is fixed here.
//
// Everything goes through /usr/share/draco/lib/config.py:
//   status (JSON), set <KEY> <value>, chave <provider> ($DRACO_CHAVE), testar <provider>, login,
//   modelos <provider> [--atualizar], modelo <provider> <id>
//   qs -c draco-config ipc call config show "<why it opened>"
//   qs -c draco-config ipc call config aba ia|geral|avancado
//   qs -c draco-config ipc call config modelos <provider>
import "idiomas"
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Effects
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

ShellRoot {
  id: shell

  readonly property string home: Quickshell.env("HOME")
  readonly property string configPy: "/usr/share/draco/lib/config.py"
  readonly property string draco: "/usr/bin/draco"

  property var st: null                    // config.py status
  property string reason: Quickshell.env("DRACO_CONFIG_MOTIVO") || ""
  property var results: ({})              // provider id -> {busy, ok, msg}
  property string openPicker: ""          // ipc: open this provider's model list

  // ── what is on screen ───────────────────────────────────────────────────
  property bool skipWelcome: false        // "Usar minha conta ou chave" was clicked
  property string onboarding: ""          // "" | "busy" | "error"  (the one-click start)
  property string onboardingMsg: ""
  property bool chooserOpen: false        // the list of AIs, inside the AI card
  property bool advancedOpen: false
  property bool celebrate: false          // just became ready: "Tudo pronto" banner
  property bool wasReady: true

  readonly property bool loading: st === null
  readonly property var brains: st ? st.cerebros : []
  readonly property var brain: st ? (brains.find(p => p.id === st.cerebro.id) || null) : null
  readonly property var freeBrain: brains.find(p => p.semConta === true) || null
  readonly property bool welcome: st !== null && (onboarding !== ""
      || (!skipWelcome && !st.cerebro.ok && (st.cerebro.id || "") === ""))

  // ── colors: follow the system theme (~/.local/state/simba/current/theme) ──
  // Same tokens as Configurações (Comum/Tema.qml): black themes stay black,
  // white themes go white; a grey accent falls back to the foreground.
  property color base: "#000000"
  property color ink: "#ffffff"
  property color themeAccent: "#8d8d8d"
  property var pal: ({})
  function lum(c) {
    function ch(v) { return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
    return 0.2126 * ch(c.r) + 0.7152 * ch(c.g) + 0.0722 * ch(c.b)
  }
  function contrast(a, b) { var la = lum(a), lb = lum(b); return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05) }
  function mix(a, b, k) { return Qt.rgba(a.r + (b.r - a.r) * k, a.g + (b.g - a.g) * k, a.b + (b.b - a.b) * k, 1) }
  function sat(c) { var mx = Math.max(c.r, c.g, c.b), mn = Math.min(c.r, c.g, c.b); return mx === 0 ? 0 : (mx - mn) / mx }
  readonly property bool dark: lum(base) < 0.45
  readonly property bool chromatic: sat(themeAccent) > 0.18 && contrast(themeAccent, base) > 2.2

  readonly property color bg: base
  readonly property color surface: mix(base, ink, dark ? 0.045 : 0.035)
  readonly property color surfaceHi: mix(base, ink, dark ? 0.075 : 0.06)
  readonly property color surfaceMax: mix(base, ink, dark ? 0.12 : 0.10)
  readonly property color line: tint(dark ? 0.09 : 0.11)
  readonly property color lineStrong: tint(dark ? 0.18 : 0.22)
  readonly property color fg: ink
  readonly property color text2: mix(ink, base, 0.32)
  readonly property color muted: mix(ink, base, dark ? 0.50 : 0.44)   // >= 4.5:1 on white
  readonly property color accent: chromatic ? themeAccent : ink
  readonly property color inkOnAccent: contrast(base, accent) >= contrast(ink, accent) ? base : ink
  readonly property color accentText: chromatic ? themeAccent : ink
  readonly property color good: pal.green || (dark ? "#6ee7a8" : "#1f8a4c")
  readonly property color warn: pal.yellow || (dark ? "#ffc46b" : "#9a6200")
  readonly property color bad: pal.red || (dark ? "#ff8fa3" : "#b3261e")
  function tint(a) { return Qt.rgba(ink.r, ink.g, ink.b, a) }
  function acc(a) { return Qt.rgba(accent.r, accent.g, accent.b, a) }
  function alpha(c, a) { return Qt.rgba(c.r, c.g, c.b, a) }

  // Shape, type and motion follow the system too (like Configurações): rounding from
  // Hyprland's decoration:rounding (0 = Simba's crisp look), the Simba font, and
  // animations only when Hyprland has them on.
  property string font: "JetBrainsMono Nerd Font"
  property int rounding: 0
  property bool animations: true
  readonly property int r: Math.min(rounding, 14)
  readonly property int rs: Math.round(r * 0.6)
  readonly property int rl: Math.min(Math.round(r * 1.4), 20)
  readonly property int fast: animations ? 120 : 0
  readonly property int mid: animations ? 180 : 0

  function loadColors(raw) {
    var p = {}
    String(raw || "").split("\n").forEach(function(l) {
      var m = l.match(/^\s*([A-Za-z0-9_-]+)\s*=\s*["']?(#[0-9A-Fa-f]{6})/)
      if (m) p[m[1]] = m[2]
    })
    pal = p
    base = p.background || p.color0 || "#000000"
    ink = p.foreground || p.color7 || "#ffffff"
    themeAccent = p.accent || p.color4 || ink
  }
  FileView {
    id: colorsFile
    path: shell.home + "/.local/state/simba/current/theme/colors.toml"
    printErrors: false
    onLoaded: shell.loadColors(text())
  }
  FileView {
    path: shell.home + "/.local/state/simba/current/theme.name"
    watchChanges: true
    printErrors: false
    onFileChanged: { reload(); colorsFile.reload() }
  }
  Process {
    command: ["fc-match", "-f", "%{family[0]}", "monospace"]
    running: true
    stdout: StdioCollector { onStreamFinished: { var f = text.trim(); if (f.length) shell.font = f } }
  }
  Process {
    command: ["sh", "-c", "hyprctl -j getoption decoration:rounding; echo @@; hyprctl -j getoption animations:enabled"]
    running: true
    stdout: StdioCollector {
      onStreamFinished: {
        var parts = text.split("@@")
        try { shell.rounding = JSON.parse(parts[0]).int || 0 } catch (e) {}
        try { shell.animations = JSON.parse(parts[1]).bool !== false } catch (e) {}
      }
    }
  }

  // Wake word threshold: config.py status doesn't report it yet, so read config.env
  // (read only; writes go through `config.py set LIMIAR`).
  property string limiarRaw: ""
  FileView {
    path: shell.home + "/.config/draco/config.env"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: {
      var m = text().match(/^LIMIAR=['"]?([0-9.]*)/m)
      shell.limiarRaw = m ? m[1] : ""
    }
  }
  readonly property string limiar: st && st.limiar !== undefined ? String(st.limiar || "") : limiarRaw

  // ── backend ─────────────────────────────────────────────────────────────
  function refresh() { statusProc.running = false; statusProc.running = true }

  function setResult(id, value) {
    var x = Object.assign({}, results)
    x[id] = value
    results = x
  }

  // Run config.py (or draco) and get its output back.
  function run(args, env, done) {
    var p = procComponent.createObject(shell, { command: args, environment: env || {} })
    p.done = done || null
    p.running = true
  }
  function config(args, env, done) { run(["python3", configPy].concat(args), env, done) }

  // Pick a provider. Only test right away when there is something to test (a key saved,
  // nothing needed at all): "falta a chave" before the person even pasted one is noise.
  function choose(kind, id) {
    var list = st ? (kind === "cerebro" ? st.cerebros : st.transcricoes) : []
    var p = list.find(x => x.id === id) || {}
    config(["set", kind === "cerebro" ? "CEREBRO" : "TRANSCRICAO", id], null, () => {
      refresh()
      if (!(p.precisa_chave && !p.tem_chave) && !p.login) test(id)
    })
  }
  function test(id, done) {
    setResult(id, { busy: true, ok: false, msg: "" })
    config(["testar", id], null, out => {
      var x = { ok: false, msg: "falhou" }
      try { x = JSON.parse(out) } catch (e) {}
      setResult(id, { busy: false, ok: x.ok, msg: x.msg })
      refresh()
      if (done) done(x)
    })
  }
  function saveKey(id, key) {
    config(["chave", id], { DRACO_CHAVE: key }, () => test(id))
  }
  function login(id) {
    setResult(id, { busy: true, ok: false, msg: "termine o login no navegador…" })
    config(["login"], null, () => test(id))
  }

  // The one-click start: choose the free brain and check it (the first time config.py
  // installs OpenCode, so this can take a minute).
  function startFree() {
    if (!freeBrain || onboarding === "busy") return
    var id = freeBrain.id
    onboarding = "busy"
    onboardingMsg = ""
    config(["set", "CEREBRO", id], null, () => {
      test(id, x => {
        if (x.ok) { onboarding = ""; celebrate = true }
        else { onboarding = "error"; onboardingMsg = x.msg || "falhou" }
      })
    })
  }
  function leaveWelcome() {
    onboarding = ""
    skipWelcome = true
    chooserOpen = true
  }

  // What fixes the current AI when it isn't working.
  function fixBrain() {
    var p = brain
    if (!p) { chooserOpen = true; return }
    if (p.login) login(p.id)
    else if (p.precisa_chave) { chooserOpen = true; Qt.callLater(() => scrollTo(aiCard)) }
    else test(p.id)
  }

  // Backend texts are Portuguese; show them through the catalog, first letter up.
  function say(s) {
    s = I18n.t(String(s || ""))
    return s.length ? s.charAt(0).toUpperCase() + s.slice(1) : s
  }

  Component {
    id: procComponent
    Process {
      property var done: null
      stdout: StdioCollector { id: out }
      onExited: {
        if (done) done(out.text)
        destroy()
      }
    }
  }

  Process {
    id: statusProc
    command: ["python3", shell.configPy, "status"]
    running: true
    stdout: StdioCollector {
      onStreamFinished: {
        var next = null
        try { next = JSON.parse(text) } catch (e) { console.warn("config status:", e); return }
        if (shell.st !== null && !shell.wasReady && next.pronto && shell.onboarding === "") shell.celebrate = true
        shell.wasReady = next.pronto
        shell.st = next
      }
    }
  }

  IpcHandler {
    target: "config"
    function show(why: string): void {
      if (why !== "") shell.reason = why
      shell.refresh()
      win.visible = true
    }
    // ia: the list of AIs; geral/avancado: the folded settings
    function aba(name: string): void {
      if (name === "ia") { shell.skipWelcome = true; shell.chooserOpen = true; Qt.callLater(() => shell.scrollTo(aiCard)) }
      else { shell.skipWelcome = true; shell.advancedOpen = true; Qt.callLater(() => shell.scrollTo(advancedHeader)) }
    }
    // the welcome's "Começar grátis" (tests: no synthetic clicks)
    function gratis(): void { shell.startFree() }
    // opens a provider's model list (tests: no synthetic clicks)
    function modelos(id: string): void {
      shell.skipWelcome = true
      shell.advancedOpen = true
      shell.openPicker = id
      Qt.callLater(() => shell.scrollTo(advancedHeader))
    }
  }

  // ── small building blocks ───────────────────────────────────────────────
  component Glyph: Text {
    property string g: ""
    property int size: 16
    Layout.maximumWidth: implicitWidth   // a centered Text otherwise soaks up a RowLayout's spare room
    text: g
    color: shell.fg
    font.family: shell.font
    font.pixelSize: size
    textFormat: Text.PlainText
    horizontalAlignment: Text.AlignHCenter
    verticalAlignment: Text.AlignVCenter
  }

  component Label: Text {
    color: shell.fg
    font.family: shell.font
    font.pixelSize: 13
    textFormat: Text.PlainText
    wrapMode: Text.WordWrap
    Behavior on color { ColorAnimation { duration: shell.mid } }
  }

  // Three breathing dots (busy).
  component Dots: Row {
    property color color: shell.fg
    spacing: 4
    Repeater {
      model: 3
      Rectangle {
        required property int index
        width: 5; height: 5; radius: 2.5
        color: parent.color
        opacity: 0.25
        SequentialAnimation on opacity {
          running: true
          loops: Animation.Infinite
          PauseAnimation { duration: index * 140 }
          NumberAnimation { to: 1; duration: 320; easing.type: Easing.InOutSine }
          NumberAnimation { to: 0.25; duration: 320; easing.type: Easing.InOutSine }
          PauseAnimation { duration: (2 - index) * 140 }
        }
      }
    }
  }

  // Soft shadow under a card (light themes mostly; black themes get a faint one).
  component Shadow: Item {
    id: sh
    property Item target: parent
    property real strength: 1
    anchors.fill: target
    z: -1
    // opaque in the page color: MultiEffect also paints the source, and it shows through translucent borders
    Rectangle { id: shape; anchors.fill: parent; radius: sh.target ? sh.target.radius : 0; color: shell.bg; visible: false }
    MultiEffect {
      source: shape
      anchors.fill: shape
      autoPaddingEnabled: true
      shadowEnabled: true
      shadowColor: shell.dark ? Qt.rgba(0, 0, 0, 0.6) : Qt.rgba(0, 0, 0, 0.10)
      shadowBlur: 0.8
      shadowOpacity: sh.strength
      shadowVerticalOffset: 4
      blurMax: 32
    }
  }

  // kind: "primary" | "normal" | "ghost"
  component Btn: Rectangle {
    id: b
    property string text: ""
    property string glyph: ""
    property string kind: "normal"
    property bool active: true
    property bool busy: false
    property bool compact: false
    signal clicked()
    readonly property color ink: kind === "primary" ? shell.inkOnAccent : shell.fg
    implicitHeight: compact ? 30 : 36
    implicitWidth: Math.max(implicitHeight, row.implicitWidth + (text !== "" ? (compact ? 24 : 32) : 0))
    radius: shell.rs
    opacity: active ? 1 : 0.4
    activeFocusOnTab: active
    Keys.onReturnPressed: if (active && !busy) clicked()
    Keys.onSpacePressed: if (active && !busy) clicked()
    color: kind === "primary" ? (ma.pressed ? shell.mix(shell.accent, shell.bg, 0.22) : ma.containsMouse ? shell.mix(shell.accent, shell.bg, 0.12) : shell.accent)
         : kind === "ghost" ? (ma.pressed ? shell.tint(0.10) : ma.containsMouse ? shell.tint(0.06) : "transparent")
         : (ma.pressed ? shell.mix(shell.surfaceMax, shell.fg, 0.05) : ma.containsMouse ? shell.surfaceMax : shell.surfaceHi)
    border.width: kind === "normal" ? 1 : 0
    border.color: shell.line
    scale: ma.pressed ? 0.97 : 1
    Behavior on scale { NumberAnimation { duration: shell.fast; easing.type: Easing.OutQuad } }
    Behavior on color { ColorAnimation { duration: shell.fast } }
    Row {
      id: row
      anchors.centerIn: parent
      spacing: 8
      opacity: b.busy ? 0 : 1
      Glyph { visible: b.glyph !== ""; g: b.glyph; size: b.compact ? 14 : 16; color: b.ink; anchors.verticalCenter: parent.verticalCenter }
      Text {
        visible: b.text !== ""
        text: b.text
        color: b.ink
        font.family: shell.font
        font.pixelSize: b.compact ? 12 : 13
        font.weight: b.kind === "primary" ? Font.DemiBold : Font.Medium
        anchors.verticalCenter: parent.verticalCenter
      }
    }
    Dots { anchors.centerIn: parent; visible: b.busy; color: b.ink }
    Rectangle { // keyboard focus ring
      anchors.fill: parent; anchors.margins: -3
      radius: b.radius > 0 ? b.radius + 3 : 0
      color: "transparent"; border.width: 1.5; border.color: shell.accent
      opacity: b.activeFocus ? 0.6 : 0
    }
    MouseArea {
      id: ma
      anchors.fill: parent
      hoverEnabled: true
      enabled: b.active && !b.busy
      cursorShape: Qt.PointingHandCursor
      onClicked: b.clicked()
    }
  }

  // Small label chip: tone "accent" | "good" | "neutral"
  component Tag: Rectangle {
    id: tg
    property string text: ""
    property string tone: "accent"
    implicitWidth: tagLabel.implicitWidth + 14
    implicitHeight: 20
    radius: shell.r > 0 ? 10 : 2
    color: tone === "good" ? shell.alpha(shell.good, 0.14) : tone === "neutral" ? shell.tint(0.08) : shell.acc(0.14)
    Text {
      id: tagLabel
      anchors.centerIn: parent
      text: tg.text
      font.family: shell.font
      font.pixelSize: 11
      font.weight: Font.Medium
      color: tg.tone === "good" ? shell.good : tg.tone === "neutral" ? shell.text2 : shell.accentText
    }
  }

  // One line of state: icon + text. tone: "busy" | "ok" | "bad" | "warn" | "info"
  component StateLine: RowLayout {
    id: sl
    property string tone: "info"
    property string text: ""
    spacing: 8
    readonly property color c: tone === "ok" ? shell.good : tone === "bad" ? shell.bad : tone === "warn" ? shell.warn : shell.muted
    Item {
      Layout.alignment: Qt.AlignTop
      implicitWidth: 16; implicitHeight: 18
      Glyph {
        anchors.centerIn: parent
        visible: sl.tone !== "busy"
        size: 15
        color: sl.c
        g: sl.tone === "ok" ? "\u{f05e0}" : sl.tone === "bad" ? "\u{f0159}" : sl.tone === "warn" ? "\u{f0026}" : "\u{f02fd}"
      }
      Dots { anchors.centerIn: parent; visible: sl.tone === "busy"; color: shell.muted; scale: 0.8 }
    }
    Label {
      text: sl.text
      color: sl.tone === "info" || sl.tone === "busy" ? shell.muted : sl.c
      font.pixelSize: 12
      Layout.fillWidth: true
    }
  }

  component Field: TextField {
    implicitHeight: 36
    color: shell.fg
    placeholderTextColor: shell.muted
    selectionColor: shell.accent
    selectedTextColor: shell.inkOnAccent
    font.family: shell.font
    font.pixelSize: 13
    leftPadding: 12
    background: Rectangle {
      radius: shell.rs
      color: shell.bg
      border.width: parent.activeFocus ? 1.5 : 1
      border.color: parent.activeFocus ? shell.accent : shell.lineStrong
      Behavior on border.color { ColorAnimation { duration: shell.fast } }
    }
  }

  // A card that groups rows.
  component Card: Rectangle {
    id: cd
    default property alias content: cardCol.data
    property int pad: 20
    Layout.fillWidth: true
    implicitHeight: cardCol.implicitHeight + pad * 2
    radius: shell.rl
    color: shell.surface
    border.width: 1
    border.color: shell.line
    Shadow { strength: shell.dark ? 0.5 : 1 }
    ColumnLayout {
      id: cardCol
      x: cd.pad; y: cd.pad
      width: cd.width - cd.pad * 2
      spacing: 16
    }
  }

  component SectionLabel: Text {
    color: shell.muted
    font.family: shell.font
    font.pixelSize: 11
    font.weight: Font.DemiBold
    font.letterSpacing: 1.2
    font.capitalization: Font.AllUppercase
    Layout.topMargin: 8
    Layout.leftMargin: 4
  }

  component Divider: Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: shell.line }

  // Folds its content open/closed with a short height animation.
  component Fold: Item {
    id: fd
    property bool open: false
    default property alias content: foldCol.data
    property int spacing: 12
    Layout.fillWidth: true
    clip: true
    implicitHeight: open ? foldCol.implicitHeight : 0
    visible: implicitHeight > 0.5
    Behavior on implicitHeight { NumberAnimation { duration: shell.mid; easing.type: Easing.OutCubic } }
    ColumnLayout {
      id: foldCol
      width: fd.width
      spacing: fd.spacing
      opacity: fd.open ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: shell.mid } }
    }
  }

  component Toggle: Item {
    id: tg
    property bool on: false
    property bool busy: false
    signal toggled()
    implicitWidth: 46; implicitHeight: 26
    activeFocusOnTab: true
    Keys.onSpacePressed: toggled()
    Keys.onReturnPressed: toggled()
    Rectangle {
      anchors.fill: parent
      radius: shell.r > 0 ? height / 2 : 3
      color: tg.on ? shell.accent : (tgMouse.containsMouse ? shell.tint(0.06) : "transparent")
      border.width: tg.on ? 0 : 1.5
      border.color: tgMouse.containsMouse ? shell.muted : shell.lineStrong
      Behavior on color { ColorAnimation { duration: shell.mid } }
    }
    Rectangle {
      id: knob
      width: tgMouse.pressed ? 22 : 16; height: 16; y: 5
      radius: shell.r > 0 ? 8 : 2
      x: tg.on ? tg.width - width - 5 : 5
      color: tg.on ? shell.inkOnAccent : shell.text2
      Behavior on x { NumberAnimation { duration: shell.mid; easing.type: Easing.OutBack; easing.overshoot: 1.4 } }
      Behavior on width { NumberAnimation { duration: shell.fast } }
      SequentialAnimation on opacity {
        running: tg.busy
        loops: Animation.Infinite
        onRunningChanged: if (!running) knob.opacity = 1
        NumberAnimation { to: 0.35; duration: 420 }
        NumberAnimation { to: 1; duration: 420 }
      }
    }
    Rectangle {
      anchors.fill: parent; anchors.margins: -3
      radius: shell.r > 0 ? height / 2 : 3
      color: "transparent"; border.width: 1.5; border.color: shell.accent
      opacity: tg.activeFocus ? 0.6 : 0
    }
    MouseArea { id: tgMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: tg.toggled() }
  }

  // A row of a card: title + hint on the left, a control on the right.
  component SettingRow: RowLayout {
    id: srow
    property string title: ""
    property string hint: ""
    default property alias control: ctrl.data
    Layout.fillWidth: true
    spacing: 16
    ColumnLayout {
      spacing: 4
      Layout.fillWidth: true
      Label { text: srow.title; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true }
      Label { visible: srow.hint !== ""; text: srow.hint; color: shell.muted; font.pixelSize: 12; Layout.fillWidth: true }
    }
    Item { id: ctrl; implicitWidth: childrenRect.width; implicitHeight: childrenRect.height; Layout.alignment: Qt.AlignVCenter }
  }

  // Model list of one provider: comes live from the provider (config.py modelos), searchable.
  component ModelPicker: ColumnLayout {
    id: picker
    property var p: ({})
    property string title: I18n.t("Modelo")
    Layout.fillWidth: true
    spacing: 8
    property bool open: false
    property bool loading: false
    property var info: null              // {modelos, fonte, erro, atual}
    property string query: ""
    Connections {
      target: shell
      function onOpenPickerChanged() {
        if (shell.openPicker === picker.p.id) { picker.open = true; if (!picker.info) picker.load(false); shell.openPicker = "" }
      }
    }
    readonly property var shown: {
      if (!info) return []
      var q = query.toLowerCase()
      return info.modelos.filter(m => q === "" || (m.nome + " " + m.id).toLowerCase().indexOf(q) >= 0)
    }
    readonly property string currentName: {
      var id = p.modelo || ""
      if (info) for (var i = 0; i < info.modelos.length; i++) if (info.modelos[i].id === id) return I18n.t(info.modelos[i].nome)
      return id !== "" ? id : I18n.t("Automático")
    }
    function load(refresh) {
      loading = true
      shell.config(["modelos", p.id].concat(refresh ? ["--atualizar"] : []), null, out => {
        try { info = JSON.parse(out) } catch (e) { info = { modelos: [], erro: "não consegui buscar os modelos", fonte: "" } }
        loading = false
      })
    }
    function choose(id) {
      shell.config(["modelo", p.id, id], null, () => {
        open = false
        query = ""
        shell.refresh()
        shell.test(p.id)
      })
    }

    SettingRow {
      title: picker.title
      hint: picker.open ? "" : picker.currentName
      Btn {
        text: picker.open ? I18n.t("Fechar") : I18n.t("Trocar")
        compact: true
        onClicked: { picker.open = !picker.open; if (picker.open && !picker.info) picker.load(false) }
      }
    }

    Fold {
      open: picker.open
      spacing: 8
      RowLayout {
        Layout.fillWidth: true
        spacing: 8
        Field {
          Layout.fillWidth: true
          placeholderText: I18n.t("Buscar modelo…")
          text: picker.query
          onTextChanged: picker.query = text
        }
        Btn { glyph: "\u{f0450}"; onClicked: picker.load(true); busy: picker.loading }
      }
      StateLine {
        Layout.fillWidth: true
        tone: picker.loading ? "busy" : picker.info && picker.info.erro ? "warn" : "info"
        text: picker.loading ? I18n.t("Buscando os modelos disponíveis…")
            : !picker.info ? ""
            : (I18n.f("%1 modelos", picker.info.modelos.length) + (picker.info.fonte ? " · " + I18n.t(picker.info.fonte) : "")
               + (picker.info.erro ? " · " + I18n.t(picker.info.erro) : ""))
      }
      Rectangle {
        Layout.fillWidth: true
        implicitHeight: Math.min(Math.max(picker.shown.length, 1) * 44 + 8, 264)
        radius: shell.rs
        color: shell.bg
        border.width: 1; border.color: shell.line
        ListView {
          id: modelList
          anchors.fill: parent
          anchors.margins: 4
          clip: true
          model: picker.shown
          boundsBehavior: Flickable.StopAtBounds
          ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
          delegate: Rectangle {
            id: row
            required property var modelData
            readonly property bool current: modelData.id === (picker.p.modelo || "")
            width: modelList.width - 8
            height: 44
            radius: Math.max(shell.rs - 2, 0)
            color: current ? shell.acc(0.12) : (rowMouse.containsMouse ? shell.tint(0.05) : "transparent")
            Behavior on color { ColorAnimation { duration: shell.fast } }
            MouseArea {
              id: rowMouse
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: picker.choose(row.modelData.id)
            }
            Column {
              anchors.verticalCenter: parent.verticalCenter
              x: 12
              width: parent.width - tagRow.width - 30
              Text { text: I18n.t(row.modelData.nome); color: shell.fg; font.family: shell.font; font.pixelSize: 13; elide: Text.ElideRight; width: parent.width }
              Text {
                visible: row.modelData.id !== "" && row.modelData.nome !== row.modelData.id
                text: row.modelData.id; color: shell.muted; font.family: shell.font; font.pixelSize: 10; elide: Text.ElideRight; width: parent.width
              }
            }
            Row {
              id: tagRow
              anchors.verticalCenter: parent.verticalCenter
              anchors.right: parent.right
              anchors.rightMargin: 12
              spacing: 4
              Repeater {
                model: (row.current ? ["em uso"] : []).concat(row.modelData.tags || [])
                Tag {
                  required property string modelData
                  text: I18n.t(modelData)
                  tone: modelData === "grátis" ? "good" : modelData === "em uso" ? "neutral" : "accent"
                }
              }
            }
          }
        }
        Label {
          anchors.centerIn: parent
          visible: !picker.loading && picker.info !== null && picker.shown.length === 0
          text: I18n.t("Nenhum modelo encontrado")
          color: shell.muted; font.pixelSize: 12
        }
      }
    }
  }

  // One provider in a list: pick it; the chosen one shows what it needs (key, sign in).
  component ProviderRow: Rectangle {
    id: card
    property var p: ({})
    property string selectedId: ""
    property var provState: null   // st.cerebro / st.transcricao
    property bool showModel: false
    readonly property bool selected: p.id === selectedId
    readonly property var result: shell.results[p.id]
    readonly property bool needsKey: p.precisa_chave === true
    readonly property bool busy: result !== undefined && result.busy === true

    Layout.fillWidth: true
    implicitHeight: body.implicitHeight + 28
    radius: shell.rs + 2
    color: selected ? shell.bg : (cardMouse.containsMouse ? shell.tint(0.04) : "transparent")
    border.width: 1
    border.color: selected ? shell.acc(0.7) : (cardMouse.containsMouse ? shell.lineStrong : shell.line)
    Behavior on color { ColorAnimation { duration: shell.fast } }
    Behavior on border.color { ColorAnimation { duration: shell.fast } }

    MouseArea {
      id: cardMouse
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: card.selected ? Qt.ArrowCursor : Qt.PointingHandCursor
      onClicked: if (!card.selected) shell.choose(card.p.tipo, card.p.id)
    }

    ColumnLayout {
      id: body
      anchors { left: parent.left; right: parent.right; top: parent.top; margins: 14; leftMargin: 16; rightMargin: 16 }
      spacing: 10

      RowLayout {
        spacing: 12
        Layout.fillWidth: true
        Rectangle { // radio
          Layout.alignment: Qt.AlignTop
          Layout.topMargin: 1
          width: 18; height: 18; radius: 9
          color: "transparent"
          border.width: card.selected ? 5 : 1.5
          border.color: card.selected ? shell.accent : shell.lineStrong
          Behavior on border.width { NumberAnimation { duration: shell.fast } }
        }
        ColumnLayout {
          spacing: 4
          Layout.fillWidth: true
          RowLayout {
            spacing: 8
            Label { text: I18n.t(card.p.nome || ""); font.pixelSize: 14; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
            Tag { visible: card.p.recomendado === true; text: I18n.t("recomendado") }
            Tag { visible: card.p.gratis === true; text: I18n.t("grátis"); tone: "good" }
            Item { Layout.fillWidth: true }
          }
          Label { text: I18n.t(card.p.desc || ""); color: shell.muted; font.pixelSize: 12; Layout.fillWidth: true }
        }
      }

      ColumnLayout {
        visible: card.selected
        Layout.leftMargin: 30
        Layout.fillWidth: true
        spacing: 10

        // API key
        RowLayout {
          visible: card.needsKey
          Layout.fillWidth: true
          spacing: 8
          Field {
            id: keyField
            Layout.fillWidth: true
            echoMode: TextInput.Password
            placeholderText: card.p.tem_chave ? I18n.t("Chave salva. Cole outra para trocar") : I18n.t("Cole a chave aqui")
            onAccepted: saveBtn.clicked()
          }
          Btn {
            id: saveBtn
            text: keyField.text !== "" ? I18n.t("Salvar e testar") : I18n.t("Testar")
            kind: keyField.text !== "" ? "primary" : "normal"
            active: keyField.text !== "" || card.p.tem_chave
            busy: card.busy
            onClicked: {
              if (keyField.text !== "") { shell.saveKey(card.p.id, keyField.text); keyField.text = "" }
              else shell.test(card.p.id)
            }
          }
        }
        RowLayout {
          visible: card.needsKey && (card.p.url_chave || "") !== ""
          spacing: 6
          Label { text: I18n.t("Não tem uma chave?"); color: shell.muted; font.pixelSize: 12; wrapMode: Text.NoWrap }
          Text {
            text: I18n.t("Criar no site") + " ↗"
            color: shell.accentText
            font.family: shell.font
            font.pixelSize: 12
            font.weight: Font.DemiBold
            font.underline: linkMouse.containsMouse
            MouseArea { id: linkMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: Qt.openUrlExternally(card.p.url_chave) }
          }
        }

        // Claude subscription: sign in
        RowLayout {
          visible: card.p.login === true
          spacing: 8
          Btn {
            text: card.provState && card.provState.ok ? I18n.t("Entrar com outra conta") : I18n.t("Entrar na conta")
            glyph: "\u{f0009}"
            kind: card.provState && card.provState.ok ? "normal" : "primary"
            busy: card.busy
            onClicked: shell.login(card.p.id)
          }
          Btn { text: I18n.t("Verificar"); kind: "ghost"; active: !card.busy; onClicked: shell.test(card.p.id) }
        }

        // No account, no key: just check it
        RowLayout {
          visible: !card.needsKey && card.p.login !== true && card.p.tipo !== "cerebro"
          Btn { text: I18n.t("Testar"); busy: card.busy; onClicked: shell.test(card.p.id) }
        }

        StateLine {
          Layout.fillWidth: true
          visible: text !== ""
          tone: card.busy ? "busy" : card.result ? (card.result.ok ? "ok" : "bad")
              : card.provState ? (card.provState.ok ? "ok" : "warn") : "info"
          text: card.busy ? (card.result.msg ? shell.say(card.result.msg) : I18n.t("Testando…"))
              : card.result ? shell.say(card.result.msg)
              : card.provState ? shell.say(card.provState.msg) : ""
        }

        ModelPicker {
          visible: card.showModel && card.p.tem_modelos === true
          p: card.p
        }
      }
    }
  }

  component SliderRow: ColumnLayout {
    id: sr
    property string title: ""
    property string hint: ""
    property string key: ""
    property real from: 0
    property real to: 10
    property real step: 1
    property real value: 0
    property string unit: "s"
    property string display: (slider.value % 1 === 0 ? slider.value : slider.value.toFixed(1).replace(".", I18n.decimal)) + " " + unit
    property string leftLabel: ""
    property string rightLabel: ""
    signal released(real v)
    Layout.fillWidth: true
    spacing: 6
    RowLayout {
      Layout.fillWidth: true
      Label { text: sr.title; font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true }
      Label { text: sr.display; color: shell.accentText; font.pixelSize: 13; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
    }
    Label { text: sr.hint; color: shell.muted; font.pixelSize: 12; Layout.fillWidth: true; visible: text !== "" }
    Slider {
      id: slider
      Layout.fillWidth: true
      from: sr.from; to: sr.to; stepSize: sr.step; snapMode: Slider.SnapAlways
      value: sr.value
      onPressedChanged: if (!pressed) {
        if (sr.key !== "") shell.config(["set", sr.key, String(value)], null, () => shell.refresh())
        sr.released(value)
      }
      background: Rectangle {
        x: slider.leftPadding; y: slider.topPadding + slider.availableHeight / 2 - height / 2
        width: slider.availableWidth; height: 4; radius: 2
        color: shell.tint(0.12)
        Rectangle { width: slider.visualPosition * parent.width; height: parent.height; radius: 2; color: shell.accent }
      }
      handle: Rectangle {
        x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
        y: slider.topPadding + slider.availableHeight / 2 - height / 2
        width: 18; height: 18; radius: 9
        color: shell.bg
        border.width: 2; border.color: slider.pressed || slider.hovered ? shell.accent : shell.lineStrong
        scale: slider.pressed ? 1.12 : 1
        Behavior on scale { NumberAnimation { duration: shell.fast } }
      }
    }
    RowLayout {
      visible: sr.leftLabel !== ""
      Layout.fillWidth: true
      Label { text: sr.leftLabel; color: shell.muted; font.pixelSize: 11; wrapMode: Text.NoWrap }
      Item { Layout.fillWidth: true }
      Label { text: sr.rightLabel; color: shell.muted; font.pixelSize: 11; wrapMode: Text.NoWrap }
    }
  }

  component Keycap: Rectangle {
    property string text: ""
    implicitWidth: Math.max(kc.implicitWidth + 16, 28)
    implicitHeight: 26
    radius: Math.max(shell.rs - 1, 0)
    color: shell.bg
    border.width: 1; border.color: shell.lineStrong
    Rectangle { anchors { left: parent.left; right: parent.right; bottom: parent.bottom } height: 2; color: shell.line } // key depth
    Text { id: kc; anchors.centerIn: parent; text: parent.text; color: shell.fg; font.family: shell.font; font.pixelSize: 12; font.weight: Font.DemiBold }
  }

  function scrollTo(item) {
    if (!item || !item.visible) return
    var y = item.mapToItem(content, 0, 0).y - 40
    scrollAnim.to = Math.max(0, Math.min(y, flick.contentHeight - flick.height))
    scrollAnim.restart()
  }

  // ── the window ──────────────────────────────────────────────────────────
  FloatingWindow {
    id: win
    title: I18n.t("Draco: configurações")   // config.py login finds the window by this title
    visible: true
    implicitWidth: 760
    implicitHeight: 640
    minimumSize: Qt.size(560, 440)
    color: shell.bg
    onVisibleChanged: if (!visible) Qt.quit()

    Shortcut { sequence: "Escape"; onActivated: Qt.quit() }

    // Loading
    Column {
      anchors.centerIn: parent
      spacing: 16
      visible: shell.loading
      Image {
        anchors.horizontalCenter: parent.horizontalCenter
        width: 56; height: 56
        sourceSize: Qt.size(112, 112)
        source: "file:///usr/share/icons/hicolor/scalable/apps/com.simba.Draco.svg"
        opacity: 0.85
      }
      Dots { anchors.horizontalCenter: parent.horizontalCenter; color: shell.muted }
    }

    // ── first use ─────────────────────────────────────────────────────────
    Flickable {
      id: welcomeView
      anchors.fill: parent
      visible: shell.welcome
      opacity: visible ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: shell.mid } }
      contentWidth: width
      contentHeight: Math.max(height, hero.implicitHeight + 64)
      boundsBehavior: Flickable.StopAtBounds
      clip: true
      ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }

      ColumnLayout {
        id: hero
        width: Math.min(welcomeView.width - 64, 520)
        x: (welcomeView.width - width) / 2
        y: Math.max(32, (welcomeView.contentHeight - implicitHeight) / 2 - 8)
        spacing: 0

        Image {
          Layout.alignment: Qt.AlignHCenter
          Layout.preferredWidth: 72; Layout.preferredHeight: 72
          sourceSize: Qt.size(144, 144)
          source: "file:///usr/share/icons/hicolor/scalable/apps/com.simba.Draco.svg"
        }
        Label {
          Layout.topMargin: 24
          Layout.fillWidth: true
          horizontalAlignment: Text.AlignHCenter
          text: I18n.t("Oi! Eu sou o Draco.")
          font.pixelSize: 26; font.weight: Font.Bold
        }
        Label {
          Layout.topMargin: 8
          Layout.fillWidth: true
          horizontalAlignment: Text.AlignHCenter
          text: I18n.t("Seu assistente de voz. Segure F10 ou diga “Draco” e peça: abrir um app, mudar o volume, tirar uma dúvida.")
          color: shell.text2
          font.pixelSize: 14
          lineHeight: 1.15
        }

        // Main path: one click
        Rectangle {
          id: freeTile
          visible: shell.freeBrain !== null
          readonly property bool busy: shell.onboarding === "busy"
          Layout.topMargin: 40
          Layout.fillWidth: true
          implicitHeight: 80
          radius: shell.rl
          color: freeMouse.pressed && !busy ? shell.mix(shell.accent, shell.bg, 0.2)
               : freeMouse.containsMouse && !busy ? shell.mix(shell.accent, shell.bg, 0.1) : shell.accent
          Behavior on color { ColorAnimation { duration: shell.fast } }
          scale: freeMouse.pressed && !busy ? 0.985 : 1
          Behavior on scale { NumberAnimation { duration: shell.fast } }
          activeFocusOnTab: true
          focus: shell.welcome
          Keys.onReturnPressed: shell.startFree()
          Keys.onSpacePressed: shell.startFree()
          Shadow { strength: freeMouse.containsMouse ? 1.4 : 1 }
          RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 20; anchors.rightMargin: 20
            spacing: 16
            Rectangle {
              implicitWidth: 44; implicitHeight: 44
              radius: shell.r > 0 ? 22 : shell.rs
              color: shell.alpha(shell.inkOnAccent, 0.14)
              Glyph { anchors.centerIn: parent; g: "\u{f14de}"; size: 22; color: shell.inkOnAccent }
            }
            ColumnLayout {
              spacing: 4
              Layout.fillWidth: true
              Text {
                text: freeTile.busy ? I18n.t("Preparando o Draco…") : I18n.t("Começar grátis")
                color: shell.inkOnAccent; font.family: shell.font; font.pixelSize: 17; font.weight: Font.Bold
              }
              Text {
                Layout.fillWidth: true
                text: freeTile.busy ? I18n.t("Na primeira vez pode levar um minuto.") : I18n.t("Pronto em 1 clique, sem conta nem chave.")
                color: shell.alpha(shell.inkOnAccent, 0.75); font.family: shell.font; font.pixelSize: 12
                elide: Text.ElideRight
              }
            }
            Item {
              implicitWidth: 24; implicitHeight: 24
              Glyph { anchors.centerIn: parent; visible: !freeTile.busy; g: "\u{f0054}"; size: 20; color: shell.inkOnAccent
                x: freeMouse.containsMouse ? 3 : 0
                Behavior on x { NumberAnimation { duration: shell.fast } } }
              Dots { anchors.centerIn: parent; visible: freeTile.busy; color: shell.inkOnAccent }
            }
          }
          Rectangle {
            anchors.fill: parent; anchors.margins: -4
            radius: shell.rl > 0 ? shell.rl + 4 : 0
            color: "transparent"; border.width: 1.5; border.color: shell.accent
            opacity: freeTile.activeFocus ? 0.5 : 0
          }
          MouseArea {
            id: freeMouse
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: freeTile.busy ? Qt.BusyCursor : Qt.PointingHandCursor
            onClicked: shell.startFree()
          }
        }

        // It didn't work: say why and offer the way out
        Rectangle {
          visible: shell.onboarding === "error"
          Layout.topMargin: 12
          Layout.fillWidth: true
          implicitHeight: errCol.implicitHeight + 24
          radius: shell.rs + 2
          color: shell.alpha(shell.bad, 0.08)
          border.width: 1; border.color: shell.alpha(shell.bad, 0.35)
          ColumnLayout {
            id: errCol
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 14 }
            spacing: 10
            StateLine { Layout.fillWidth: true; tone: "bad"; text: I18n.f("Não deu certo: %1", I18n.t(shell.onboardingMsg)) }
            RowLayout {
              Layout.leftMargin: 24
              spacing: 8
              Btn { text: I18n.t("Tentar de novo"); glyph: "\u{f0450}"; compact: true; onClicked: shell.startFree() }
              Btn { text: I18n.t("Escolher outra IA"); kind: "ghost"; compact: true; onClicked: shell.leaveWelcome() }
            }
          }
        }

        // Honest note about the free models
        RowLayout {
          visible: shell.freeBrain !== null
          Layout.topMargin: 12
          Layout.fillWidth: true
          Layout.leftMargin: 4; Layout.rightMargin: 4
          spacing: 8
          Glyph { Layout.alignment: Qt.AlignTop; g: "\u{f0498}"; size: 14; color: shell.muted }
          Label {
            Layout.fillWidth: true
            text: I18n.t(shell.freeBrain && shell.freeBrain.aviso ? shell.freeBrain.aviso
                  : "No modo grátis o provedor pode usar suas conversas para melhorar os modelos. Para privacidade, conecte sua conta.")
            color: shell.muted; font.pixelSize: 12
          }
        }

        // or
        RowLayout {
          visible: shell.freeBrain !== null
          Layout.topMargin: 24
          Layout.fillWidth: true
          spacing: 12
          Divider {}
          Label { text: I18n.t("ou"); color: shell.muted; font.pixelSize: 12; wrapMode: Text.NoWrap }
          Divider {}
        }

        // Secondary path (the main one when there is no free brain)
        Rectangle {
          id: ownTile
          readonly property bool main: shell.freeBrain === null
          Layout.topMargin: main ? 40 : 24
          Layout.fillWidth: true
          implicitHeight: main ? 80 : 64
          radius: shell.rl
          // without a free brain this is the main path: same weight as "Começar grátis"
          readonly property color ink: main ? shell.inkOnAccent : shell.fg
          color: main ? (ownMouse.containsMouse ? shell.mix(shell.accent, shell.bg, 0.1) : shell.accent)
               : (ownMouse.containsMouse ? shell.surfaceHi : shell.surface)
          border.width: main ? 0 : 1
          border.color: ownMouse.containsMouse ? shell.lineStrong : shell.line
          Behavior on color { ColorAnimation { duration: shell.fast } }
          activeFocusOnTab: true
          Keys.onReturnPressed: shell.leaveWelcome()
          Keys.onSpacePressed: shell.leaveWelcome()
          RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 20; anchors.rightMargin: 20
            spacing: 16
            Glyph { g: "\u{f0306}"; size: 20; color: ownTile.main ? ownTile.ink : shell.text2; Layout.preferredWidth: 44 }
            ColumnLayout {
              spacing: 2
              Layout.fillWidth: true
              Label {
                text: ownTile.main ? I18n.t("Escolher a IA") : I18n.t("Usar minha conta ou chave")
                color: ownTile.ink
                font.pixelSize: ownTile.main ? 17 : 14; font.weight: Font.DemiBold; wrapMode: Text.NoWrap
              }
              Label {
                Layout.fillWidth: true
                text: shell.brains.filter(p => p.semConta !== true).slice(0, 3).map(p => I18n.t(p.nome)).join(", ")
                      + (shell.brains.filter(p => p.semConta !== true).length > 3 ? " " + I18n.t("e outras") : "")
                color: ownTile.main ? shell.alpha(ownTile.ink, 0.75) : shell.muted
                font.pixelSize: 12; elide: Text.ElideRight; wrapMode: Text.NoWrap
              }
            }
            Glyph { g: "\u{f0142}"; size: 18; color: ownTile.main ? ownTile.ink : shell.muted }
          }
          Rectangle {
            anchors.fill: parent; anchors.margins: -4
            radius: shell.rl > 0 ? shell.rl + 4 : 0
            color: "transparent"; border.width: 1.5; border.color: shell.accent
            opacity: ownTile.activeFocus ? 0.5 : 0
          }
          MouseArea { id: ownMouse; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: shell.leaveWelcome() }
        }

        Label {
          Layout.topMargin: 32
          Layout.fillWidth: true
          horizontalAlignment: Text.AlignHCenter
          text: I18n.t("Dá para mudar tudo depois em Super + F10.")
          color: shell.muted; font.pixelSize: 11
        }
      }
    }

    // ── panel ─────────────────────────────────────────────────────────────
    Item {
      anchors.fill: parent
      visible: !shell.loading && !shell.welcome
      opacity: visible ? 1 : 0
      Behavior on opacity { NumberAnimation { duration: shell.mid } }

      // Header
      Rectangle {
        id: header
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 80
        color: shell.bg
        z: 2
        Rectangle { // hairline once the content scrolls under it
          anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
          height: 1; color: shell.line
          opacity: flick.contentY > 2 ? 1 : 0
          Behavior on opacity { NumberAnimation { duration: shell.fast } }
        }
        Row {
          x: (parent.width - content.width) / 2
          anchors.verticalCenter: parent.verticalCenter
          spacing: 16
          Image {
            width: 44; height: 44
            sourceSize: Qt.size(88, 88)
            source: "file:///usr/share/icons/hicolor/scalable/apps/com.simba.Draco.svg"
          }
          Column {
            anchors.verticalCenter: parent.verticalCenter
            spacing: 4
            Text { text: I18n.t("Draco"); color: shell.fg; font.family: shell.font; font.pixelSize: 20; font.weight: Font.Bold }
            Row {
              spacing: 8
              Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: 8; height: 8; radius: 4
                color: shell.st && shell.st.pronto ? shell.good : shell.warn
                SequentialAnimation on opacity { // a calm "alive" pulse when ready
                  running: shell.st !== null && shell.st.pronto && shell.animations
                  loops: Animation.Infinite
                  NumberAnimation { to: 0.35; duration: 1200; easing.type: Easing.InOutSine }
                  NumberAnimation { to: 1; duration: 1200; easing.type: Easing.InOutSine }
                }
              }
              Text {
                text: shell.st && shell.st.pronto ? I18n.t("Pronto para ouvir")
                    : shell.st && shell.st.cerebro.id ? I18n.t("A IA ainda não está pronta") : I18n.t("Falta escolher a IA")
                color: shell.text2; font.family: shell.font; font.pixelSize: 12
              }
            }
          }
        }
      }

      Flickable {
        id: flick
        anchors { left: parent.left; right: parent.right; top: header.bottom; bottom: footer.top }
        contentWidth: width
        contentHeight: content.implicitHeight + 32
        boundsBehavior: Flickable.StopAtBounds
        clip: true
        ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        NumberAnimation { id: scrollAnim; target: flick; property: "contentY"; duration: shell.mid * 1.5; easing.type: Easing.OutCubic }

        ColumnLayout {
          id: content
          width: Math.min(flick.width - 64, 640)
          x: (flick.width - width) / 2
          y: 8
          spacing: 12

          // Just got ready
          Rectangle {
            visible: shell.celebrate && shell.st !== null && shell.st.pronto
            Layout.fillWidth: true
            implicitHeight: 56
            radius: shell.rl
            color: shell.alpha(shell.good, 0.10)
            border.width: 1; border.color: shell.alpha(shell.good, 0.35)
            RowLayout {
              anchors.fill: parent
              anchors.leftMargin: 16; anchors.rightMargin: 8
              spacing: 12
              Glyph { g: "\u{f05e0}"; size: 20; color: shell.good }
              Label {
                Layout.fillWidth: true
                text: I18n.t("Tudo pronto! Segure F10 e fale, ou diga “Draco”.")
                font.pixelSize: 13; font.weight: Font.DemiBold
              }
              Btn { glyph: "\u{f0156}"; kind: "ghost"; compact: true; onClicked: shell.celebrate = false }
            }
          }

          // Why the window opened (e.g. F10 with nothing configured)
          Rectangle {
            visible: shell.reason !== "" && !(shell.st && shell.st.pronto)
            Layout.fillWidth: true
            implicitHeight: reasonLine.implicitHeight + 24
            radius: shell.rl
            color: shell.alpha(shell.warn, 0.08)
            border.width: 1; border.color: shell.alpha(shell.warn, 0.35)
            StateLine {
              id: reasonLine
              anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 16 }
              tone: "warn"
              text: I18n.t(shell.reason)
            }
          }

          // ── AI ──────────────────────────────────────────────────────────
          SectionLabel { text: I18n.t("Inteligência") }
          Card {
            id: aiCard
            readonly property var p: shell.brain
            readonly property var res: p ? shell.results[p.id] : undefined
            readonly property bool busy: res !== undefined && res.busy === true
            readonly property bool ok: shell.st !== null && shell.st.cerebro.ok && !(res && !res.busy && !res.ok)

            RowLayout {
              Layout.fillWidth: true
              spacing: 16
              Rectangle {
                implicitWidth: 44; implicitHeight: 44
                radius: shell.r > 0 ? 22 : shell.rs
                color: shell.acc(0.12)
                Glyph { anchors.centerIn: parent; g: "\u{f09d1}"; size: 22; color: shell.accentText }
              }
              ColumnLayout {
                spacing: 4
                Layout.fillWidth: true
                RowLayout {
                  spacing: 8
                  Label {
                    text: aiCard.p ? I18n.t(aiCard.p.nome) : I18n.t("Nenhuma IA escolhida")
                    font.pixelSize: 16; font.weight: Font.Bold; wrapMode: Text.NoWrap
                  }
                  Tag { visible: aiCard.p !== null && aiCard.p.gratis === true; text: I18n.t("grátis"); tone: "good" }
                }
                StateLine {
                  Layout.fillWidth: true
                  tone: aiCard.busy ? "busy" : !aiCard.p ? "warn" : aiCard.res ? (aiCard.res.ok ? "ok" : "bad") : (shell.st.cerebro.ok ? "ok" : "warn")
                  text: aiCard.busy ? (aiCard.res.msg ? shell.say(aiCard.res.msg) : I18n.t("Testando…"))
                      : !aiCard.p ? I18n.t("Escolha quem vai entender e responder seus pedidos.")
                      : aiCard.res ? shell.say(aiCard.res.msg) : shell.say(shell.st.cerebro.msg)
                }
              }
              Btn {
                visible: aiCard.p !== null
                text: I18n.t("Testar")
                busy: aiCard.busy
                onClicked: shell.test(aiCard.p.id)
              }
              Btn {
                text: shell.chooserOpen ? I18n.t("Fechar") : (aiCard.p ? I18n.t("Trocar") : I18n.t("Escolher"))
                kind: aiCard.p ? "ghost" : "primary"
                glyph: shell.chooserOpen ? "\u{f0143}" : "\u{f0140}"
                onClicked: shell.chooserOpen = !shell.chooserOpen
              }
            }

            // Not working: one clear fix
            Rectangle {
              visible: aiCard.p !== null && !aiCard.ok && !aiCard.busy && !shell.chooserOpen
              Layout.fillWidth: true
              implicitHeight: 52
              radius: shell.rs + 2
              color: shell.alpha(shell.warn, 0.08)
              border.width: 1; border.color: shell.alpha(shell.warn, 0.3)
              RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14; anchors.rightMargin: 8
                spacing: 12
                Label {
                  Layout.fillWidth: true
                  text: !aiCard.p ? "" : aiCard.p.login ? I18n.t("Entre na sua conta para o Draco poder responder.")
                      : aiCard.p.precisa_chave ? I18n.t("Falta a chave desse serviço.")
                      : I18n.t("A IA ainda não respondeu. Teste de novo.")
                  font.pixelSize: 12; color: shell.text2
                }
                Btn {
                  compact: true
                  kind: "primary"
                  text: !aiCard.p ? "" : aiCard.p.login ? I18n.t("Entrar na conta") : aiCard.p.precisa_chave ? I18n.t("Colar a chave") : I18n.t("Testar de novo")
                  onClicked: shell.fixBrain()
                }
              }
            }

            // Free mode: be honest about the data, and show the way up
            Rectangle {
              visible: aiCard.p !== null && aiCard.p.semConta === true && !shell.chooserOpen
              Layout.fillWidth: true
              implicitHeight: privRow.implicitHeight + 24
              radius: shell.rs + 2
              color: shell.tint(0.03)
              border.width: 1; border.color: shell.line
              RowLayout {
                id: privRow
                anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; leftMargin: 14; rightMargin: 8 }
                spacing: 12
                Glyph { Layout.alignment: Qt.AlignTop; g: "\u{f0498}"; size: 16; color: shell.muted }
                Label {
                  Layout.fillWidth: true
                  text: I18n.t(aiCard.p && aiCard.p.aviso ? aiCard.p.aviso
                        : "No modo grátis o provedor pode usar suas conversas para melhorar os modelos. Para privacidade, conecte sua conta.")
                  color: shell.text2; font.pixelSize: 12
                }
                Btn {
                  text: I18n.t("Melhorar")
                  glyph: "\u{f0ae2}"
                  compact: true
                  onClicked: { shell.chooserOpen = true; Qt.callLater(() => shell.scrollTo(chooser)) }
                }
              }
            }

            // The list of AIs, grouped by what they ask of you
            Fold {
              id: chooser
              open: shell.chooserOpen
              spacing: 8
              Divider { Layout.bottomMargin: 4 }
              Repeater {
                model: [
                  { titulo: I18n.t("Sem conta nem chave"), itens: shell.brains.filter(p => p.semConta === true) },
                  { titulo: I18n.t("Com a sua conta"), itens: shell.brains.filter(p => p.login === true && p.semConta !== true) },
                  { titulo: I18n.t("Com uma chave do serviço"), dica: I18n.t("Você cria a chave no site do serviço e cola aqui. Ela fica só neste computador."),
                    itens: shell.brains.filter(p => p.login !== true && p.semConta !== true) }
                ].filter(g => g.itens.length > 0)
                ColumnLayout {
                  required property var modelData
                  Layout.fillWidth: true
                  Layout.topMargin: 4
                  spacing: 8
                  Label { text: parent.modelData.titulo; color: shell.text2; font.pixelSize: 12; font.weight: Font.DemiBold; Layout.fillWidth: true }
                  Label { visible: parent.modelData.dica !== undefined; text: parent.modelData.dica || ""; color: shell.muted; font.pixelSize: 11; Layout.fillWidth: true }
                  Repeater {
                    model: parent.modelData.itens
                    ProviderRow {
                      required property var modelData
                      p: modelData
                      selectedId: shell.st.cerebro.id
                      provState: shell.st.cerebro
                    }
                  }
                }
              }
            }
          }

          // ── Voice ───────────────────────────────────────────────────────
          SectionLabel { text: I18n.t("Voz") }
          Card {
            SettingRow {
              title: I18n.t("Atender quando eu disser “Draco”")
              hint: I18n.t("Chame sem apertar nada. Desligado, o microfone só abre com o F10.")
              Toggle {
                id: wakeToggle
                on: shell.st ? shell.st.escuta : false
                onToggled: { busy = true; shell.run([shell.draco, "escuta", on ? "desliga" : "liga"], null, () => { busy = false; shell.refresh() }) }
              }
            }
            Divider {}
            RowLayout {
              Layout.fillWidth: true
              spacing: 16
              ColumnLayout {
                spacing: 4
                Layout.fillWidth: true
                Label { text: I18n.t("Voz do Draco"); font.pixelSize: 14; font.weight: Font.DemiBold }
                Label { text: I18n.t("Toque numa voz para ouvir como ela soa."); color: shell.muted; font.pixelSize: 12; Layout.fillWidth: true }
              }
              Btn { text: I18n.t("Ouvir"); glyph: "\u{f040a}"; compact: true; onClicked: shell.run([shell.draco, "say", I18n.t("Oi! Tô aqui, é só chamar.")]) }
            }
            Repeater {
              model: [{ tipo: "natural", titulo: I18n.t("Naturais"), dica: I18n.t("Soam como gente. Grátis, pela internet; começam a falar ~1 s depois. Sem internet, a voz do computador assume.") },
                      { tipo: "local", titulo: I18n.t("No computador"), dica: I18n.t("Instantâneas e sem internet, mas mais robóticas.") }]
              ColumnLayout {
                id: voiceGroup
                required property var modelData
                readonly property var voices: shell.st ? shell.st.vozes.filter(v => v.tipo === modelData.tipo) : []
                visible: voices.length > 0
                Layout.fillWidth: true
                spacing: 8
                RowLayout {
                  spacing: 8
                  Layout.fillWidth: true
                  Label { text: voiceGroup.modelData.titulo; color: shell.text2; font.pixelSize: 12; font.weight: Font.DemiBold; wrapMode: Text.NoWrap }
                  Label { text: voiceGroup.modelData.dica; color: shell.muted; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight; wrapMode: Text.NoWrap
                    ToolTip.visible: dicaMouse.containsMouse && truncated; ToolTip.text: text; ToolTip.delay: 400
                    MouseArea { id: dicaMouse; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.NoButton } }
                }
                Flow {
                  Layout.fillWidth: true
                  spacing: 8
                  Repeater {
                    model: voiceGroup.voices
                    Rectangle {
                      id: chip
                      required property var modelData
                      readonly property bool chosen: shell.st && shell.st.voz === modelData.id
                      width: chipRow.implicitWidth + 28; height: 48
                      radius: shell.rs + 2
                      color: chosen ? shell.acc(0.10) : (chipMouse.containsMouse ? shell.surfaceHi : shell.bg)
                      border.width: chosen ? 1.5 : 1
                      border.color: chosen ? shell.accent : (chipMouse.containsMouse ? shell.lineStrong : shell.line)
                      Behavior on color { ColorAnimation { duration: shell.fast } }
                      Row {
                        id: chipRow
                        anchors.centerIn: parent
                        spacing: 10
                        Glyph { anchors.verticalCenter: parent.verticalCenter; g: chip.chosen ? "\u{f05e0}" : "\u{f057e}"; size: 16; color: chip.chosen ? shell.accentText : shell.muted }
                        Column {
                          anchors.verticalCenter: parent.verticalCenter
                          spacing: 1
                          Text { text: chip.modelData.nome; color: shell.fg; font.family: shell.font; font.pixelSize: 13; font.weight: Font.DemiBold }
                          Text { visible: text !== ""; text: chip.modelData.desc; color: shell.muted; font.family: shell.font; font.pixelSize: 11 }
                        }
                      }
                      MouseArea {
                        id: chipMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: shell.config(["set", "VOZ", chip.modelData.id], null, () => {
                          shell.refresh()
                          shell.run([shell.draco, "say", I18n.t("Oi! Essa é a minha voz agora.")])
                        })
                      }
                    }
                  }
                }
              }
            }
          }

          // ── How to call it ──────────────────────────────────────────────
          SectionLabel { text: I18n.t("Como chamar") }
          Card {
            GridLayout {
              Layout.fillWidth: true
              columns: 1
              columnSpacing: 24
              rowSpacing: 12
              Repeater {
                model: [[["F10"], I18n.t("Segure enquanto fala e solte para enviar")],
                        [["“Draco”"], I18n.t("Diga o nome e depois o pedido")],
                        [[I18n.t("Esc")], I18n.t("Cancela o que ele estiver fazendo")],
                        [["Super", "F10"], I18n.t("Abre estas configurações")]]
                RowLayout {
                  required property var modelData
                  Layout.fillWidth: true
                  spacing: 12
                  Row {
                    Layout.preferredWidth: 120
                    spacing: 4
                    Repeater {
                      model: parent.parent.modelData[0]
                      Keycap { required property string modelData; text: modelData }
                    }
                  }
                  Label { text: parent.modelData[1]; color: shell.text2; font.pixelSize: 12; Layout.fillWidth: true }
                }
              }
            }
          }

          // ── Advanced ────────────────────────────────────────────────────
          Rectangle {
            id: advancedHeader
            Layout.fillWidth: true
            Layout.topMargin: 8
            implicitHeight: 52
            radius: shell.rl
            color: advMouse.containsMouse ? shell.tint(0.04) : "transparent"
            border.width: 1
            border.color: shell.line
            Behavior on color { ColorAnimation { duration: shell.fast } }
            readonly property bool sttProblem: shell.st !== null && !shell.st.transcricao.ok
            activeFocusOnTab: true
            Keys.onReturnPressed: shell.advancedOpen = !shell.advancedOpen
            Keys.onSpacePressed: shell.advancedOpen = !shell.advancedOpen
            RowLayout {
              anchors.fill: parent
              anchors.leftMargin: 16; anchors.rightMargin: 16
              spacing: 12
              Glyph { g: "\u{f062e}"; size: 18; color: shell.text2 }
              ColumnLayout {
                spacing: 2
                Layout.fillWidth: true
                Label { text: I18n.t("Avançado"); font.pixelSize: 14; font.weight: Font.DemiBold; Layout.fillWidth: true }
                Label {
                  visible: !shell.advancedOpen
                  text: I18n.t("Modelo, reconhecimento de voz, tempos e sensibilidade")
                  color: shell.muted; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight; wrapMode: Text.NoWrap
                }
              }
              Tag { visible: advancedHeader.sttProblem; text: I18n.t("precisa de atenção"); tone: "neutral" }
              Glyph {
                g: "\u{f0140}"; size: 18; color: shell.muted
                rotation: shell.advancedOpen ? 180 : 0
                Behavior on rotation { NumberAnimation { duration: shell.mid; easing.type: Easing.OutCubic } }
              }
            }
            Rectangle {
              anchors.fill: parent; anchors.margins: -3
              radius: shell.rl > 0 ? shell.rl + 3 : 0
              color: "transparent"; border.width: 1.5; border.color: shell.accent
              opacity: advancedHeader.activeFocus ? 0.5 : 0
            }
            MouseArea {
              id: advMouse
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: {
                shell.advancedOpen = !shell.advancedOpen
                if (shell.advancedOpen) Qt.callLater(() => shell.scrollTo(advancedHeader))
              }
            }
          }

          Fold {
            open: shell.advancedOpen
            spacing: 12

            // Model of the current AI
            Card {
              visible: shell.brain !== null && shell.brain.tem_modelos === true
              ModelPicker {
                p: shell.brain || ({})
                title: I18n.t("Modelo da IA")
              }
            }

            // Transcription
            Card {
              ColumnLayout {
                spacing: 4
                Layout.fillWidth: true
                Label { text: I18n.t("Reconhecimento de voz"); font.pixelSize: 14; font.weight: Font.DemiBold }
                Label { text: I18n.t("Transforma a sua fala em texto e confirma que você disse “Draco”."); color: shell.muted; font.pixelSize: 12; Layout.fillWidth: true }
              }
              ColumnLayout {
                Layout.fillWidth: true
                spacing: 8
                Repeater {
                  model: shell.st ? shell.st.transcricoes : []
                  ProviderRow {
                    required property var modelData
                    p: modelData
                    selectedId: shell.st.transcricao.id
                    provState: shell.st.transcricao
                    showModel: true
                  }
                }
              }
            }

            // Timings and sensitivity
            Card {
              SliderRow {
                title: I18n.t("Espera para você começar a falar")
                hint: I18n.t("Depois de “Draco”, quanto tempo ele aguarda o pedido antes de desistir.")
                key: "ESPERA"; from: 2; to: 15; step: 1
                value: shell.st ? shell.st.espera : 5
              }
              Divider {}
              SliderRow {
                title: I18n.t("Silêncio que encerra o pedido")
                hint: I18n.t("Pausa que ele entende como “terminei de falar”. Aumente se ele te corta no meio.")
                key: "SILENCIO"; from: 0.8; to: 5; step: 0.1
                value: shell.st ? shell.st.silencio : 2
              }
              Divider {}
              SliderRow {
                title: I18n.t("Memória da conversa")
                hint: I18n.t("Dentro desse tempo ele lembra do pedido anterior (“e agora aumenta o volume”). 0 = esquece sempre.")
                key: "MEMORIA"; from: 0; to: 60; step: 1; unit: "min"
                value: shell.st ? shell.st.memoria : 10
              }
              Divider {}
              // LIMIAR: wake word score needed (0.5–0.99, lower = more sensitive);
              // shown as sensitivity 0–100 %. Empty = the model's own.
              ColumnLayout {
                Layout.fillWidth: true
                spacing: 6
                SliderRow {
                  id: sens
                  title: I18n.t("Sensibilidade ao “Draco”")
                  hint: I18n.t("Mais sensível atende mesmo de longe, mas pode acordar por engano.")
                  from: 0; to: 100; step: 5; unit: "%"
                  value: shell.limiar !== "" ? Math.round((0.99 - parseFloat(shell.limiar)) / 0.49 * 100) : 50
                  display: shell.limiar !== "" ? Math.round(value) + " %" : I18n.t("Automática")
                  leftLabel: I18n.t("Menos sensível")
                  rightLabel: I18n.t("Mais sensível")
                  onReleased: v => {
                    var lim = (0.99 - v / 100 * 0.49).toFixed(2)
                    shell.limiarRaw = lim
                    shell.config(["set", "LIMIAR", lim], null, () => {
                      shell.refresh()
                    })
                  }
                }
                Btn {
                  visible: shell.limiar !== ""
                  text: I18n.t("Voltar para a automática")
                  kind: "ghost"; compact: true
                  onClicked: {
                    shell.limiarRaw = ""
                    shell.config(["set", "LIMIAR", ""], null, () => {
                      shell.refresh()
                    })
                  }
                }
              }
            }
          }
        }
      }

      // Footer
      Rectangle {
        id: footer
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 64
        color: shell.bg
        Rectangle { anchors { left: parent.left; right: parent.right; top: parent.top } height: 1; color: shell.line }
        RowLayout {
          width: content.width
          x: (parent.width - width) / 2
          anchors.verticalCenter: parent.verticalCenter
          spacing: 8
          Glyph { g: "\u{f033e}"; size: 13; color: shell.muted }
          Label { text: I18n.t("Suas chaves ficam só neste computador."); color: shell.muted; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight; wrapMode: Text.NoWrap }
          Btn { text: I18n.t("Concluído"); kind: shell.st && shell.st.pronto ? "primary" : "normal"; onClicked: Qt.quit() }
        }
      }
    }
  }
}
