//@ pragma AppId com.simba.Draco
// Draco settings window (Super+F10, or `draco config`; opens by itself when F10 is
// pressed and no AI is configured yet).
//
// Everything goes through /usr/share/draco/lib/config.py:
//   status (JSON), set <KEY> <value>, chave <provider> ($DRACO_CHAVE), testar <provider>, login
//   qs -c draco-config ipc call config show "<why it opened>"
//   qs -c draco-config ipc call config aba ia|geral
import "idiomas"
import QtQuick
import QtQuick.Controls.Basic
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
  property string tab: "ia"
  property var results: ({})              // provider id -> {busy, ok, msg}
  property string openPicker: ""          // ipc: open this provider's model list

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
  readonly property color panel: mix(base, ink, dark ? 0.045 : 0.04)
  readonly property color panelHi: mix(base, ink, dark ? 0.085 : 0.075)
  readonly property color panelHover: mix(base, ink, dark ? 0.065 : 0.055)
  readonly property color line: tint(dark ? 0.09 : 0.12)
  readonly property color fg: ink
  readonly property color muted: mix(ink, base, dark ? 0.38 : 0.36)
  readonly property color accent: chromatic ? themeAccent : ink
  readonly property color accent2: accent
  readonly property color onAccent: contrast(base, accent) >= contrast(ink, accent) ? base : ink
  readonly property color accentText: chromatic ? themeAccent : muted
  readonly property color good: pal.green || (dark ? "#6ee7a8" : "#1f8a4c")
  readonly property color warn: pal.yellow || (dark ? "#ffc46b" : "#9a6200")
  readonly property color bad: pal.red || (dark ? "#ff8fa3" : "#b3261e")
  function tint(a) { return Qt.rgba(ink.r, ink.g, ink.b, a) }
  function well(a) { return dark ? Qt.rgba(0, 0, 0, a) : Qt.rgba(ink.r, ink.g, ink.b, a * 0.12) }
  function acc(a) { return Qt.rgba(accent.r, accent.g, accent.b, a) }

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

  function refresh() { statusProc.running = false; statusProc.running = true }

  function setResult(id, value) {
    var r = Object.assign({}, results)
    r[id] = value
    results = r
  }

  // Run config.py (or draco) and get its output back.
  function run(args, env, done) {
    var p = procComponent.createObject(shell, { command: args, environment: env || {} })
    p.done = done || null
    p.running = true
  }
  function config(args, env, done) { run(["python3", configPy].concat(args), env, done) }

  function choose(kind, id) {
    config(["set", kind === "cerebro" ? "CEREBRO" : "TRANSCRICAO", id], null, () => {
      refresh()
      test(id)
    })
  }
  function test(id) {
    setResult(id, { busy: true, ok: false, msg: "testando…" })
    config(["testar", id], null, out => {
      var r = { ok: false, msg: "falhou" }
      try { r = JSON.parse(out) } catch (e) {}
      setResult(id, { busy: false, ok: r.ok, msg: r.msg })
      refresh()
    })
  }
  function saveKey(id, key) {
    config(["chave", id], { DRACO_CHAVE: key }, () => test(id))
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
        try { shell.st = JSON.parse(text) } catch (e) { console.warn("config status:", e) }
      }
    }
  }

  IpcHandler {
    target: "config"
    function show(why: string): void {
      if (why !== "") shell.reason = why
      shell.tab = "ia"
      shell.refresh()
      win.visible = true
    }
    function aba(name: string): void { shell.tab = name === "geral" ? "geral" : "ia" }
    // opens the model list of a provider's card (tests: no synthetic clicks)
    function modelos(id: string): void { shell.tab = "ia"; shell.openPicker = id }
  }

  // ── small building blocks ───────────────────────────────────────────────
  component Btn: Rectangle {
    id: btn
    property string text: ""
    property bool primary: false
    property bool active: true
    signal clicked()
    implicitWidth: btnLabel.implicitWidth + 28
    implicitHeight: 34
    radius: 10
    opacity: active ? 1 : 0.45
    gradient: primary ? grad : null
    color: primary ? "transparent" : (btnMouse.containsMouse ? shell.tint(0.10) : shell.tint(0.06))
    border.width: primary ? 0 : 1
    border.color: shell.line
    Gradient {
      id: grad
      orientation: Gradient.Horizontal
      GradientStop { position: 0; color: btnMouse.containsMouse ? shell.mix(shell.accent, shell.bg, 0.12) : shell.accent }
      GradientStop { position: 1; color: btnMouse.containsMouse ? shell.mix(shell.accent2, shell.bg, 0.12) : shell.accent2 }
    }
    Text {
      id: btnLabel
      anchors.centerIn: parent
      text: btn.text
      color: btn.primary ? shell.onAccent : shell.fg
      font.pixelSize: 13
      font.weight: Font.DemiBold
    }
    MouseArea {
      id: btnMouse
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: btn.active ? Qt.PointingHandCursor : Qt.ArrowCursor
      onClicked: if (btn.active) btn.clicked()
    }
  }

  component Link: Text {
    property string url: ""
    text: I18n.t("Pegar a chave ↗")
    color: shell.accent
    font.pixelSize: 13
    font.underline: linkMouse.containsMouse
    MouseArea {
      id: linkMouse
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: Qt.PointingHandCursor
      onClicked: Qt.openUrlExternally(parent.url)
    }
  }

  component Field: TextField {
    implicitHeight: 34
    color: shell.fg
    placeholderTextColor: shell.tint(0.35)
    selectionColor: shell.accent
    font.pixelSize: 13
    leftPadding: 12
    background: Rectangle {
      radius: 10
      color: shell.well(0.35)
      border.width: 1
      border.color: parent.activeFocus ? shell.accent : shell.line
    }
  }

  component SectionTitle: ColumnLayout {
    property string title: ""
    property string hint: ""
    spacing: 2
    Layout.fillWidth: true
    Layout.topMargin: 6
    Text { text: parent.title; color: shell.fg; font.pixelSize: 15; font.weight: Font.Bold }
    Text {
      text: parent.hint; color: shell.muted; font.pixelSize: 12
      visible: text !== ""; wrapMode: Text.WordWrap; Layout.fillWidth: true
    }
  }

  // One provider: pick it, then key / login / model / test right there.
  component ProviderCard: Rectangle {
    id: card
    property var p: ({})
    property string selectedId: ""
    property var provState: null   // st.cerebro / st.transcricao
    readonly property bool selected: p.id === selectedId
    readonly property var result: shell.results[p.id]
    readonly property bool needsKey: p.precisa_chave === true

    Layout.fillWidth: true
    implicitHeight: body.implicitHeight + 26
    radius: 14
    color: selected ? shell.panelHi : (cardMouse.containsMouse ? shell.panelHover : shell.panel)
    border.width: 1
    border.color: selected ? shell.acc(0.55) : shell.line
    Behavior on color { ColorAnimation { duration: 120 } }

    MouseArea {
      id: cardMouse
      anchors.fill: parent
      hoverEnabled: true
      cursorShape: card.selected ? Qt.ArrowCursor : Qt.PointingHandCursor
      onClicked: if (!card.selected) shell.choose(card.p.tipo, card.p.id)
    }

    ColumnLayout {
      id: body
      anchors { left: parent.left; right: parent.right; top: parent.top; margins: 13; leftMargin: 16; rightMargin: 16 }
      spacing: 8

      RowLayout {
        spacing: 10
        Layout.fillWidth: true
        Rectangle { // radio
          width: 16; height: 16; radius: 8
          color: "transparent"
          border.width: 2
          border.color: card.selected ? shell.accent : shell.tint(0.3)
          Rectangle { anchors.centerIn: parent; width: 8; height: 8; radius: 4; color: shell.accent; visible: card.selected }
        }
        Text { text: card.p.nome || ""; color: shell.fg; font.pixelSize: 14; font.weight: Font.DemiBold }
        Rectangle {
          visible: card.p.recomendado === true
          implicitWidth: recText.implicitWidth + 14; implicitHeight: 20; radius: 10
          color: shell.acc(0.16)
          Text { id: recText; anchors.centerIn: parent; text: I18n.t("recomendado"); color: shell.accentText; font.pixelSize: 11 }
        }
        Item { Layout.fillWidth: true }
        Text { // status of the chosen one
          visible: card.selected && card.provState !== null && !(card.result && card.result.busy)
          text: card.provState ? (card.provState.ok ? "● " + card.provState.msg : "● " + card.provState.msg) : ""
          color: card.provState && card.provState.ok ? shell.good : shell.warn
          font.pixelSize: 12
          elide: Text.ElideRight
          Layout.maximumWidth: 260
        }
      }

      Text {
        text: card.p.desc || ""
        color: shell.muted
        font.pixelSize: 12
        Layout.leftMargin: 26
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
      }

      // API key
      RowLayout {
        visible: card.selected && card.needsKey
        Layout.leftMargin: 26
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
          primary: keyField.text !== ""
          active: keyField.text !== "" || card.p.tem_chave
          onClicked: {
            if (keyField.text !== "") { shell.saveKey(card.p.id, keyField.text); keyField.text = "" }
            else shell.test(card.p.id)
          }
        }
        Link { url: card.p.url_chave || ""; visible: url !== "" }
      }

      // Claude subscription: sign in
      RowLayout {
        visible: card.selected && card.p.login === true
        Layout.leftMargin: 26
        spacing: 8
        Btn {
          text: I18n.t("Entrar na conta")
          primary: !(card.provState && card.provState.ok)
          onClicked: { shell.setResult(card.p.id, { busy: true, ok: false, msg: I18n.t("termine o login no navegador…") }); shell.config(["login"], null, () => shell.test(card.p.id)) }
        }
        Btn { text: I18n.t("Verificar"); onClicked: shell.test(card.p.id) }
      }

      // Model: the list comes live from the provider (config.py modelos), searchable
      ColumnLayout {
        id: picker
        visible: card.selected && card.p.tem_modelos === true
        Layout.leftMargin: 26
        Layout.fillWidth: true
        spacing: 6
        property bool open: false
        property bool loading: false
        Connections {
          target: shell
          function onOpenPickerChanged() {
            if (shell.openPicker === card.p.id) { picker.open = true; if (!picker.info) picker.load(false); shell.openPicker = "" }
          }
        }
        property var info: null              // {modelos, fonte, erro, atual}
        property string query: ""
        readonly property var shown: {
          if (!info) return []
          var q = query.toLowerCase()
          return info.modelos.filter(m => q === "" || (m.nome + " " + m.id).toLowerCase().indexOf(q) >= 0)
        }
        readonly property string currentName: {
          var id = card.p.modelo || ""
          if (info) for (var i = 0; i < info.modelos.length; i++) if (info.modelos[i].id === id) return info.modelos[i].nome
          return id !== "" ? id : "padrão do provedor"
        }
        function load(refresh) {
          loading = true
          shell.config(["modelos", card.p.id].concat(refresh ? ["--atualizar"] : []), null, out => {
            try { info = JSON.parse(out) } catch (e) { info = { modelos: [], erro: I18n.t("não consegui buscar os modelos"), fonte: "" } }
            loading = false
          })
        }
        function choose(id) {
          shell.config(["modelo", card.p.id, id], null, () => {
            open = false
            query = ""
            shell.refresh()
            shell.test(card.p.id)
          })
        }

        RowLayout {
          spacing: 8
          Layout.fillWidth: true
          Text { text: I18n.t("Modelo"); color: shell.muted; font.pixelSize: 12 }
          Rectangle {
            implicitWidth: Math.min(curText.implicitWidth + 20, 330); implicitHeight: 28; radius: 8
            color: shell.well(0.3); border.width: 1; border.color: shell.line
            Text {
              id: curText
              anchors.verticalCenter: parent.verticalCenter
              x: 10; width: parent.width - 20
              text: picker.currentName
              color: shell.fg; font.pixelSize: 13; elide: Text.ElideRight
            }
          }
          Btn {
            text: picker.open ? I18n.t("Fechar") : I18n.t("Trocar")
            implicitHeight: 28
            onClicked: { picker.open = !picker.open; if (picker.open && !picker.info) picker.load(false) }
          }
          Item { Layout.fillWidth: true }
        }

        ColumnLayout {
          visible: picker.open
          Layout.fillWidth: true
          spacing: 6
          RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Field {
              Layout.fillWidth: true
              placeholderText: I18n.t("Buscar modelo…")
              text: picker.query
              onTextChanged: picker.query = text
            }
            Btn { text: I18n.t("↻ Atualizar"); onClicked: picker.load(true) }
          }
          Text {
            text: picker.loading ? I18n.t("Buscando os modelos disponíveis…")
                : !picker.info ? ""
                : (picker.info.modelos.length + " modelos" + (picker.info.fonte ? " · " + picker.info.fonte : "")
                   + (picker.info.erro ? " · " + picker.info.erro : ""))
            color: picker.info && picker.info.erro ? shell.warn : shell.muted
            font.pixelSize: 11
            Layout.fillWidth: true
            wrapMode: Text.WordWrap
          }
          Rectangle {
            Layout.fillWidth: true
            implicitHeight: Math.min(Math.max(picker.shown.length, 1) * 40 + 8, 248)
            radius: 10
            color: shell.well(0.28)
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
                readonly property bool current: modelData.id === (card.p.modelo || "")
                width: modelList.width - 8
                height: 40
                radius: 8
                color: current ? shell.acc(0.22) : (rowMouse.containsMouse ? shell.tint(0.06) : "transparent")
                MouseArea {
                  id: rowMouse
                  anchors.fill: parent
                  hoverEnabled: true
                  cursorShape: Qt.PointingHandCursor
                  onClicked: picker.choose(row.modelData.id)
                }
                Column {
                  anchors.verticalCenter: parent.verticalCenter
                  x: 10
                  width: parent.width - tagRow.width - 26
                  Text { text: row.modelData.nome; color: shell.fg; font.pixelSize: 13; elide: Text.ElideRight; width: parent.width }
                  Text {
                    visible: row.modelData.nome !== row.modelData.id
                    text: row.modelData.id; color: shell.muted; font.pixelSize: 10; elide: Text.ElideRight; width: parent.width
                  }
                }
                Row {
                  id: tagRow
                  anchors.verticalCenter: parent.verticalCenter
                  anchors.right: parent.right
                  anchors.rightMargin: 10
                  spacing: 4
                  Repeater {
                    model: (row.current ? [I18n.t("em uso")] : []).concat(row.modelData.tags || [])
                    Rectangle {
                      required property string modelData
                      width: tagText.implicitWidth + 12; height: 18; radius: 9
                      color: modelData === "grátis" ? Qt.rgba(0.43, 0.91, 0.66, 0.16)
                           : modelData === "em uso" ? shell.tint(0.12) : shell.acc(0.16)
                      Text {
                        id: tagText
                        anchors.centerIn: parent
                        text: parent.modelData
                        color: parent.modelData === "grátis" ? shell.good : parent.modelData === "em uso" ? shell.fg : shell.accentText
                        font.pixelSize: 10
                      }
                    }
                  }
                }
              }
            }
            Text {
              anchors.centerIn: parent
              visible: !picker.loading && picker.info !== null && picker.shown.length === 0
              text: I18n.t("Nenhum modelo encontrado")
              color: shell.muted; font.pixelSize: 12
            }
          }
        }
      }

      Text {
        visible: card.selected && card.result !== undefined && card.result.msg !== ""
        text: card.result ? (card.result.busy ? I18n.t("Testando…") : (card.result.ok ? "✓ " : "✕ ") + card.result.msg) : ""
        color: card.result && card.result.busy ? shell.muted : (card.result && card.result.ok ? shell.good : shell.bad)
        font.pixelSize: 12
        Layout.leftMargin: 26
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
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
    Layout.fillWidth: true
    spacing: 4
    RowLayout {
      Layout.fillWidth: true
      Text { text: sr.title; color: shell.fg; font.pixelSize: 14; font.weight: Font.DemiBold }
      Item { Layout.fillWidth: true }
      Text {
        text: (slider.value % 1 === 0 ? slider.value : slider.value.toFixed(1)) + " " + sr.unit
        color: shell.accent; font.pixelSize: 14; font.weight: Font.DemiBold
      }
    }
    Text { text: sr.hint; color: shell.muted; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true }
    Slider {
      id: slider
      Layout.fillWidth: true
      from: sr.from; to: sr.to; stepSize: sr.step; snapMode: Slider.SnapAlways
      value: sr.value
      onPressedChanged: if (!pressed) shell.config(["set", sr.key, String(value)], null, () => shell.refresh())
      background: Rectangle {
        x: slider.leftPadding; y: slider.topPadding + slider.availableHeight / 2 - height / 2
        width: slider.availableWidth; height: 4; radius: 2
        color: shell.tint(0.12)
        Rectangle {
          width: slider.visualPosition * parent.width; height: parent.height; radius: 2
          gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0; color: shell.accent }
            GradientStop { position: 1; color: shell.accent2 }
          }
        }
      }
      handle: Rectangle {
        x: slider.leftPadding + slider.visualPosition * (slider.availableWidth - width)
        y: slider.topPadding + slider.availableHeight / 2 - height / 2
        width: 18; height: 18; radius: 9
        color: slider.pressed ? shell.fg : shell.mix(shell.fg, shell.bg, 0.1)
        border.width: 1; border.color: shell.line
      }
    }
  }

  // ── the window ──────────────────────────────────────────────────────────
  FloatingWindow {
    id: win
    title: I18n.t("Draco: configurações")
    visible: true
    implicitWidth: 760
    implicitHeight: 620
    minimumSize: Qt.size(560, 420)
    color: shell.bg
    onVisibleChanged: if (!visible) Qt.quit()

    Shortcut { sequence: "Escape"; onActivated: Qt.quit() }

    ColumnLayout {
      anchors.fill: parent
      anchors.margins: 22
      spacing: 14

      // Header
      RowLayout {
        spacing: 14
        Layout.fillWidth: true
        // mesmo ícone do Menu Iniciar e da barra de tarefas
        Image {
          Layout.preferredWidth: 44; Layout.preferredHeight: 44
          sourceSize: Qt.size(88, 88)
          source: "file:///usr/share/icons/hicolor/scalable/apps/com.simba.Draco.svg"
        }
        ColumnLayout {
          spacing: 0
          Text { text: I18n.t("Draco"); color: shell.fg; font.pixelSize: 22; font.weight: Font.Bold }
          Text {
            text: !shell.st ? "carregando…"
                : shell.st.pronto ? I18n.t("Pronto para ouvir: segure F10 ou diga “Draco”.")
                : I18n.t("Ainda não configurado: escolha qual IA vai responder.")
            color: shell.st && shell.st.pronto ? shell.good : shell.warn
            font.pixelSize: 13
          }
        }
        Item { Layout.fillWidth: true }
        // Tabs
        Rectangle {
          implicitWidth: tabs.implicitWidth + 8; implicitHeight: 38; radius: 12
          color: shell.panel; border.width: 1; border.color: shell.line
          Row {
            id: tabs
            anchors.centerIn: parent
            spacing: 4
            Repeater {
              model: [{ id: "ia", label: I18n.t("IA e voz") }, { id: "geral", label: I18n.t("Configurações") }]
              Rectangle {
                required property var modelData
                width: tabText.implicitWidth + 26; height: 30; radius: 9
                color: shell.tab === modelData.id ? shell.acc(0.22) : "transparent"
                Text {
                  id: tabText
                  anchors.centerIn: parent
                  text: parent.modelData.label
                  color: shell.tab === parent.modelData.id ? shell.fg : shell.muted
                  font.pixelSize: 13; font.weight: Font.DemiBold
                }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: shell.tab = parent.modelData.id }
              }
            }
          }
        }
      }

      // Why the window opened (e.g. F10 with nothing configured)
      Rectangle {
        visible: shell.reason !== ""
        Layout.fillWidth: true
        implicitHeight: reasonText.implicitHeight + 20
        radius: 12
        color: Qt.rgba(1, 0.77, 0.42, 0.10)
        border.width: 1; border.color: Qt.rgba(1, 0.77, 0.42, 0.35)
        Text {
          id: reasonText
          anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 14 }
          text: shell.reason
          color: shell.warn; font.pixelSize: 13; wrapMode: Text.WordWrap
        }
      }

      // ── Tab: AI and transcription providers ─────────────────────────────
      ScrollView {
        visible: shell.tab === "ia"
        Layout.fillWidth: true
        Layout.fillHeight: true
        contentWidth: availableWidth
        clip: true

        ColumnLayout {
          width: parent.width
          spacing: 8

          SectionTitle { title: I18n.t("Quem responde"); hint: I18n.t("A IA que entende o pedido e mexe no computador (o Draco usa o Claude Code por baixo).") }
          Repeater {
            model: shell.st ? shell.st.cerebros : []
            ProviderCard {
              required property var modelData
              p: modelData
              selectedId: shell.st.cerebro.id
              provState: shell.st.cerebro
            }
          }

          SectionTitle { title: I18n.t("Quem transcreve sua voz"); hint: I18n.t("Transforma a fala em texto e confirma que você disse “Draco”.") }
          Repeater {
            model: shell.st ? shell.st.transcricoes : []
            ProviderCard {
              required property var modelData
              p: modelData
              selectedId: shell.st.transcricao.id
              provState: shell.st.transcricao
            }
          }
          Item { implicitHeight: 6 }
        }
      }

      // ── Tab: general settings ───────────────────────────────────────────
      ScrollView {
        visible: shell.tab === "geral"
        Layout.fillWidth: true
        Layout.fillHeight: true
        contentWidth: availableWidth
        clip: true

        ColumnLayout {
          width: parent.width
          spacing: 18

          // Wake word on/off
          RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
              spacing: 2
              Layout.fillWidth: true
              Text { text: I18n.t("Escutar “Draco”"); color: shell.fg; font.pixelSize: 14; font.weight: Font.DemiBold }
              Text {
                text: I18n.t("Chamar sem apertar nada. Desligado, o microfone só abre com o F10.")
                color: shell.muted; font.pixelSize: 12; wrapMode: Text.WordWrap; Layout.fillWidth: true
              }
            }
            Rectangle {
              id: toggle
              readonly property bool on: shell.st ? shell.st.escuta : false
              width: 46; height: 26; radius: 13
              color: on ? shell.accent : shell.tint(0.15)
              Behavior on color { ColorAnimation { duration: 150 } }
              Rectangle {
                width: 20; height: 20; radius: 10; y: 3
                x: toggle.on ? 23 : 3
                Behavior on x { NumberAnimation { duration: 150 } }
                color: toggle.on ? shell.onAccent : shell.fg
              }
              MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: shell.run([shell.draco, "escuta", toggle.on ? "desliga" : "liga"], null, () => shell.refresh())
              }
            }
          }

          // Voice: natural (online, Microsoft) or on this computer (Piper)
          ColumnLayout {
            Layout.fillWidth: true
            spacing: 8
            RowLayout {
              Layout.fillWidth: true
              Text { text: I18n.t("Voz"); color: shell.fg; font.pixelSize: 14; font.weight: Font.DemiBold }
              Item { Layout.fillWidth: true }
              Btn { text: I18n.t("▶ Ouvir"); implicitHeight: 28; onClicked: shell.run([shell.draco, "say", I18n.t("Oi! Tô aqui, é só chamar.")]) }
            }
            Repeater {
              model: [{ tipo: "natural", titulo: I18n.t("Naturais"), dica: I18n.t("Soam como gente. Grátis, pela internet; começam a falar ~1 s depois. Sem internet, a voz do computador assume.") },
                      { tipo: "local", titulo: I18n.t("No computador"), dica: I18n.t("Instantâneas e sem internet, mas mais robóticas.") }]
              ColumnLayout {
                required property var modelData
                Layout.fillWidth: true
                spacing: 6
                Text { text: parent.modelData.titulo; color: shell.muted; font.pixelSize: 12; font.weight: Font.DemiBold }
                Text { text: parent.modelData.dica; color: shell.tint(0.4); font.pixelSize: 11; wrapMode: Text.WordWrap; Layout.fillWidth: true }
                Flow {
                  Layout.fillWidth: true
                  spacing: 8
                  Repeater {
                    model: shell.st ? shell.st.vozes.filter(v => v.tipo === parent.parent.modelData.tipo) : []
                    Rectangle {
                      required property var modelData
                      readonly property bool chosen: shell.st && shell.st.voz === modelData.id
                      width: voiceCol.implicitWidth + 28; height: voiceCol.implicitHeight + 14; radius: 10
                      color: chosen ? shell.acc(0.22) : shell.panel
                      border.width: 1; border.color: chosen ? shell.acc(0.6) : shell.line
                      Column {
                        id: voiceCol
                        anchors.centerIn: parent
                        spacing: 1
                        Text { text: parent.parent.modelData.nome; color: shell.fg; font.pixelSize: 13; font.weight: Font.DemiBold }
                        Text {
                          visible: text !== ""
                          text: parent.parent.modelData.desc
                          color: shell.muted; font.pixelSize: 10
                        }
                      }
                      MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: shell.config(["set", "VOZ", parent.modelData.id], null, () => {
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

          SliderRow {
            title: I18n.t("Espera para você começar a falar")
            hint: I18n.t("Depois de “Draco”, quanto tempo ele aguarda o pedido antes de desistir.")
            key: "ESPERA"; from: 2; to: 15; step: 1
            value: shell.st ? shell.st.espera : 5
          }
          SliderRow {
            title: I18n.t("Silêncio que encerra o pedido")
            hint: I18n.t("Pausa que ele entende como “terminei de falar”. Aumente se ele te corta no meio.")
            key: "SILENCIO"; from: 0.8; to: 5; step: 0.1
            value: shell.st ? shell.st.silencio : 2
          }
          SliderRow {
            title: I18n.t("Memória da conversa")
            hint: I18n.t("Dentro desse tempo ele lembra do pedido anterior (“e agora aumenta o volume”). 0 = esquece sempre.")
            key: "MEMORIA"; from: 0; to: 60; step: 1; unit: "min"
            value: shell.st ? shell.st.memoria : 10
          }

          // Shortcuts
          ColumnLayout {
            Layout.fillWidth: true
            spacing: 6
            Text { text: I18n.t("Atalhos"); color: shell.fg; font.pixelSize: 14; font.weight: Font.DemiBold }
            Repeater {
              model: [["F10", I18n.t("segure enquanto fala, solte para enviar")],
                      ["“Draco”", I18n.t("diga o nome e depois o pedido")],
                      [I18n.t("Esc"), I18n.t("cancela o que ele estiver fazendo")],
                      [I18n.t("Super + F10"), I18n.t("abre estas configurações")]]
              RowLayout {
                required property var modelData
                spacing: 10
                Rectangle {
                  implicitWidth: Math.max(keyText.implicitWidth + 16, 92); implicitHeight: 26; radius: 7
                  color: shell.panel; border.width: 1; border.color: shell.line
                  Text { id: keyText; anchors.centerIn: parent; text: parent.parent.modelData[0]; color: shell.fg; font.pixelSize: 12; font.weight: Font.DemiBold }
                }
                Text { text: parent.modelData[1]; color: shell.muted; font.pixelSize: 13 }
              }
            }
          }
          Item { implicitHeight: 4 }
        }
      }

      // Footer
      RowLayout {
        Layout.fillWidth: true
        Text {
          text: I18n.t("As chaves ficam só neste computador (~/.config/draco).")
          color: shell.tint(0.35); font.pixelSize: 11
        }
        Item { Layout.fillWidth: true }
        Btn { text: I18n.t("Fechar"); onClicked: Qt.quit() }
      }
    }
  }
}
