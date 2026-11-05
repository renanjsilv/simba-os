// Draco overlay: smartphone-style voice assistant UI.
//
// Full-screen orb while you talk and while Draco works out what to do; once
// it has acted (or has an answer) the orb collapses into a small voice line at
// the bottom so you can see the result, and the reply plays as a caption.
//
// Driven by /usr/bin/draco and wake.py through $XDG_RUNTIME_DIR/draco/orb.cmd: one JSON
// line per command, {"s": "<ns timestamp>", "c": "<command>", "a": [args]}, appended; the
// file is watched (inotify), so the orb reacts in milliseconds, where each
// `qs ipc call` costs ~260 ms just to start. Same commands over IPC still work:
//   qs -c draco ipc call draco listening
//   qs -c draco ipc call draco transcribe
//   qs -c draco ipc call draco think  "<what you said>"
//   qs -c draco ipc call draco action "<what it is doing>"
//   qs -c draco ipc call draco acted
//   qs -c draco ipc call draco speak  "<reply>" "<levels file>"
//   qs -c draco ipc call draco done
//   qs -c draco ipc call draco fail   "<message>"
//   qs -c draco ipc call draco hide
import "idiomas"
import QtQuick
import Quickshell
import Quickshell.Io
import Quickshell.Wayland
import Quickshell.Hyprland

ShellRoot {
  id: shell

  // hidden | listening | transcribing | thinking | background | speaking | done | error
  // ── theme: follow the system (black or white); the orb keeps its own colors ──
  property color themeBg: "#000000"
  property color themeFg: "#ffffff"
  readonly property bool themeDark: (0.2126 * themeBg.r + 0.7152 * themeBg.g + 0.0722 * themeBg.b) < 0.5
  // scrim / caption box: tinted toward the theme's background
  function scrim(a) { return themeDark ? Qt.rgba(0.02, 0.02, 0.05, a) : Qt.rgba(0.97, 0.97, 0.98, a * 0.92) }
  function ink(a) { return Qt.rgba(themeFg.r, themeFg.g, themeFg.b, a) }
  FileView {
    id: themeColors
    path: Quickshell.env("HOME") + "/.local/state/simba/current/theme/colors.toml"
    printErrors: false
    onLoaded: {
      var bgm = text().match(/^\s*background\s*=\s*["']?(#[0-9A-Fa-f]{6})/m)
      var fgm = text().match(/^\s*foreground\s*=\s*["']?(#[0-9A-Fa-f]{6})/m)
      if (bgm) shell.themeBg = bgm[1]
      if (fgm) shell.themeFg = fgm[1]
    }
  }
  FileView {
    path: Quickshell.env("HOME") + "/.local/state/simba/current/theme.name"
    watchChanges: true
    printErrors: false
    onFileChanged: { reload(); themeColors.reload() }
  }

  property string phase: "hidden"
  property string heard: ""
  property string actionText: ""
  property string reply: ""
  property string message: ""
  property string levelsPath: ""
  property int speechMs: 0
  property real speechStart: -1 // shell.time when the audio started
  property real revealed: 0 // words of the reply already spoken
  // When each word starts (ms into the audio), sent by neural voices ("w <ms>"): the
  // caption follows the real speech, pauses included; otherwise it's paced evenly.
  property var wordTimes: []

  property real time: 0
  property real spin: 0 // orb lights' phase: advances faster while thinking/talking
  property real levelTarget: 0
  property real level: 0

  readonly property bool active: phase !== "hidden"
  // After the action: small voice line at the bottom instead of the big orb.
  readonly property bool minimal: phase === "background" || phase === "speaking" || phase === "done"
  readonly property bool big: active && !minimal
  readonly property string levelScript: Qt.resolvedUrl("level.py").toString().replace("file://", "")
  readonly property var words: reply.split(/\s+/).filter(w => w.length > 0)

  // Long replies don't fit the 3-line caption: split them into pages of up to ~3 lines
  // (breaking at the end of a sentence when possible) and show the page being spoken.
  readonly property int pageChars: 190
  readonly property var pages: {
    var out = [], start = 0, len = 0
    for (var i = 0; i < words.length; i++) {
      len += words[i].length + 1
      var sentenceEnd = /[.!?…:;]["”»)]*$/.test(words[i])
      var next = i + 1 < words.length ? words[i + 1].length + 1 : 0
      if (i + 1 === words.length || (sentenceEnd && len >= pageChars * 0.45) || len + next > pageChars) {
        out.push([start, i + 1])
        start = i + 1
        len = 0
      }
    }
    return out
  }
  readonly property int page: {
    var n = Math.ceil(revealed)
    for (var i = 0; i < pages.length; i++)
      if (n < pages[i][1] || i === pages.length - 1) return i
    return 0
  }

  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
  }

  // orb.cmd: run the lines newer than the last one seen (writers append; it may be truncated)
  property string lastSeq: ""
  property bool cmdPrimed: false
  function runCommands(t) {
    var lines = t.split("\n")
    for (var i = 0; i < lines.length; i++) {
      if (lines[i] === "") continue
      var m
      try { m = JSON.parse(lines[i]) } catch (e) { continue }
      var seq = String(m.s)
      if (seq.length < lastSeq.length || (seq.length === lastSeq.length && seq <= lastSeq)) continue
      lastSeq = seq
      if (cmdPrimed) dispatch(m.c, m.a || [])
    }
    cmdPrimed = true // whatever was in the file when the orb started is old news
  }
  function dispatch(c, a) {
    switch (c) {
      case "listening": ipc.listening(); break
      case "transcribe": ipc.transcribe(); break
      case "think": ipc.think(a[0] || ""); break
      case "action": ipc.action(a[0] || ""); break
      case "acted": ipc.acted(); break
      case "speak": ipc.speak(a[0] || "", a[1] || ""); break
      case "done": ipc.done(); break
      case "fail": ipc.fail(a[0] || ""); break
      case "hide": ipc.hide(); break
    }
  }

  FileView {
    path: Quickshell.env("XDG_RUNTIME_DIR") + "/draco/orb.cmd"
    watchChanges: true
    printErrors: false
    onFileChanged: reload()
    onLoaded: shell.runCommands(text())
    onLoadFailed: shell.cmdPrimed = true
  }

  function setPhase(next) {
    hideTimer.stop()
    phase = next
    micMeter.running = next === "listening"
    if (next !== "speaking" && next !== "done") speechMeter.running = false
  }

  IpcHandler {
    id: ipc
    target: "draco"

    function listening(): void {
      if (shell.phase === "hidden") { shell.time = 0; shell.spin = 0 } // keep floats small
      shell.heard = ""
      shell.actionText = ""
      shell.reply = ""
      shell.message = ""
      shell.revealed = 0
      shell.setPhase("listening")
    }
    function transcribe(): void { shell.setPhase("transcribing") }
    function think(text: string): void {
      shell.heard = text
      shell.setPhase("thinking")
    }
    function action(text: string): void { shell.actionText = text }
    function acted(): void { shell.setPhase("background") }
    function speak(text: string, levels: string): void {
      shell.reply = text
      shell.levelsPath = levels
      shell.revealed = 0
      shell.wordTimes = []
      shell.speechStart = -1
      shell.setPhase("speaking")
      speechMeter.running = false
      speechMeter.running = levels !== ""
    }
    function done(): void {
      shell.speechStart = -1
      shell.revealed = shell.words.length
      shell.setPhase("done")
      hideTimer.interval = 2500 + shell.words.length * 90
      hideTimer.restart()
    }
    function fail(text: string): void {
      shell.message = text
      shell.setPhase("error")
      hideTimer.interval = 3200
      hideTimer.restart()
    }
    function hide(): void { shell.setPhase("hidden") }
  }

  Timer {
    id: hideTimer
    onTriggered: shell.setPhase("hidden")
  }

  // Live microphone loudness while you talk.
  Process {
    id: micMeter
    command: ["python3", "-u", shell.levelScript]
    stdout: SplitParser { onRead: data => shell.levelTarget = parseFloat(data) || 0 }
  }

  // Draco' own voice: the speech server writes "d <ms>" then loudness values.
  Process {
    id: speechMeter
    command: ["tail", "-n", "+1", "-F", shell.levelsPath]
    stdout: SplitParser {
      onRead: data => {
        if (data.startsWith("w ")) {
          shell.wordTimes.push(parseInt(data.slice(2)) || 0)
        } else if (data.startsWith("d ")) {
          // first "d" = estimate when playback starts; a later one corrects the length
          shell.speechMs = Math.max(parseInt(data.slice(2)) || 0, 300)
          if (shell.speechStart < 0) shell.speechStart = shell.time
        } else {
          shell.levelTarget = parseFloat(data) || 0
        }
      }
    }
  }

  Process {
    id: cancelProc
    command: ["/usr/bin/draco", "cancel"]
  }

  FrameAnimation {
    running: window.visible
    onTriggered: {
      shell.time += frameTime
      // integrate the speed (time * speed would jump whenever the speed changes)
      shell.spin += frameTime * (1.0 + 0.5 * orb.think + 0.5 * shell.level)
      var target = shell.levelTarget
      if (shell.phase === "transcribing" || shell.phase === "thinking")
        target = 0.12 + 0.08 * Math.sin(shell.time * 3.0)
      else if (shell.phase === "background")
        target = 0.05 + 0.04 * Math.sin(shell.time * 2.2)
      else if (shell.phase === "done" || shell.phase === "error" || shell.phase === "hidden")
        target = 0
      var k = target > shell.level ? 0.35 : 0.10
      shell.level += (target - shell.level) * k
      if (shell.speechStart >= 0) {
        var elapsed = (shell.time - shell.speechStart) * 1000 - 80 // ~player latency
        if (shell.wordTimes.length > 0) {
          var n = 0
          while (n < shell.wordTimes.length && shell.wordTimes[n] <= elapsed) n++
          shell.revealed = Math.min(shell.words.length, n)
        } else {
          shell.revealed = Math.min(shell.words.length, shell.words.length * elapsed / shell.speechMs)
        }
      }
    }
  }

  PanelWindow {
    id: window

    // Stay mapped until every fade-out has finished.
    visible: shell.active || bigStage.opacity > 0.01 || minimalStage.opacity > 0.01
    screen: Quickshell.screens.find(s => s.name === Hyprland.focusedMonitor?.name) ?? Quickshell.screens[0]
    color: "transparent"
    anchors { top: true; bottom: true; left: true; right: true }
    exclusionMode: ExclusionMode.Ignore
    WlrLayershell.layer: WlrLayer.Overlay
    WlrLayershell.namespace: "draco"
    WlrLayershell.keyboardFocus: WlrKeyboardFocus.None

    // Clicks pass through everything except the caption (click it to stop Draco).
    mask: Region { item: shell.minimal ? caption : null }

    Item {
      id: root
      anchors.fill: parent

      readonly property real h: height
      readonly property real w: width
      readonly property real lineY: h - 46

      // ── Full-screen stage: dim, edge glow, status ───────────────────────
      Item {
        id: bigStage
        anchors.fill: parent
        opacity: shell.big ? 1 : 0
        visible: opacity > 0.01
        Behavior on opacity { NumberAnimation { duration: shell.big ? 220 : 480; easing.type: Easing.OutCubic } }

        Rectangle {
          anchors.fill: parent
          gradient: Gradient {
            GradientStop { position: 0.0; color: shell.scrim(0.34) }
            GradientStop { position: 0.55; color: shell.scrim(0.46) }
            GradientStop { position: 1.0; color: shell.scrim(0.64) }
          }
        }

        // Glow running around the screen edges while the mic is open.
        ShaderEffect {
          anchors.fill: parent
          opacity: shell.phase === "listening" ? 1 : 0
          visible: opacity > 0.01
          Behavior on opacity { NumberAnimation { duration: 450; easing.type: Easing.OutCubic } }
          property real time: shell.time
          property real level: shell.level
          property real aspect: width / Math.max(height, 1)
          fragmentShader: Qt.resolvedUrl("shaders/edge.frag.qsb")
        }

        // What you said, floating above the orb while Draco thinks.
        Text {
          width: Math.min(root.w - 80, 720)
          anchors.horizontalCenter: parent.horizontalCenter
          y: root.h * 0.45 - orb.size * 0.30 - height - 18
          opacity: shell.phase === "thinking" && shell.heard !== "" ? 1 : 0
          visible: opacity > 0.01
          Behavior on opacity { NumberAnimation { duration: 380; easing.type: Easing.OutCubic } }
          text: "“" + shell.heard + "”"
          color: shell.ink(0.97)
          font.family: "Adwaita Sans"
          font.pixelSize: 24
          font.weight: Font.Medium
          horizontalAlignment: Text.AlignHCenter
          wrapMode: Text.WordWrap
          maximumLineCount: 3
          elide: Text.ElideRight
        }

        // Status under the orb: Ouvindo / Entendendo / Pensando / current action / error.
        Item {
          id: status
          anchors.horizontalCenter: parent.horizontalCenter
          y: root.h * 0.45 + orb.size * 0.33 + 14
          width: statusText.implicitWidth + 40
          height: 34
          readonly property bool isError: shell.phase === "error"
          readonly property string label: {
            switch (shell.phase) {
              case "listening": return I18n.t("Ouvindo")
              case "transcribing": return I18n.t("Entendendo")
              case "thinking": return shell.actionText !== "" ? shell.actionText : I18n.t("Pensando")
              case "error": return shell.message
              default: return ""
            }
          }
          property string shownLabel: ""
          onLabelChanged: if (label !== "") shownLabel = label
          opacity: label !== "" ? 1 : 0
          visible: opacity > 0.01
          Behavior on opacity { NumberAnimation { duration: 260 } }

          Text {
            id: statusText
            anchors.centerIn: parent
            text: status.shownLabel + (status.isError ? "" : dots.text)
            color: status.isError ? (shell.themeDark ? "#ffb4c0" : "#b3261e") : shell.ink(0.92)
            font.family: "Adwaita Sans"
            font.pixelSize: 17
            font.weight: Font.Medium
            font.letterSpacing: 0.4

            SequentialAnimation on opacity {
              running: status.visible && !status.isError
              loops: Animation.Infinite
              NumberAnimation { to: 0.55; duration: 900; easing.type: Easing.InOutSine }
              NumberAnimation { to: 1.0; duration: 900; easing.type: Easing.InOutSine }
            }
          }

          Text {
            id: dots
            visible: false
            property int n: 0
            text: ["", ".", "..", "..."][n]
            Timer {
              interval: 380
              repeat: true
              running: status.visible
              onTriggered: dots.n = (dots.n + 1) % 4
            }
          }
        }

        Text {
          anchors.horizontalCenter: parent.horizontalCenter
          anchors.bottom: parent.bottom
          anchors.bottomMargin: 26
          text: I18n.t("Esc para cancelar")
          color: shell.ink(0.45)
          font.family: "Adwaita Sans"
          font.pixelSize: 12
          font.letterSpacing: 0.6
        }
      }

      // The orb. It lives outside bigStage so it can fly down and melt into the line.
      ShaderEffect {
        id: orb

        readonly property real size: {
          switch (shell.phase) {
            case "listening": return Math.min(root.h * 0.62, 460)
            case "transcribing":
            case "thinking": return Math.min(root.h * 0.50, 380)
            case "error": return Math.min(root.h * 0.40, 300)
            case "hidden": return Math.min(root.h * 0.30, 220)
            default: return 70 // collapsing into the voice line
          }
        }
        readonly property real centerY: shell.minimal ? root.lineY : root.h * 0.45

        width: size
        height: size
        x: (root.w - width) / 2
        y: centerY - height / 2
        opacity: shell.big ? 1 : 0
        visible: opacity > 0.01
        Behavior on opacity { NumberAnimation { duration: shell.big ? 220 : 520; easing.type: Easing.InCubic } }
        Behavior on width { SpringAnimation { spring: 2.6; damping: 0.24; epsilon: 0.5 } }
        Behavior on height { SpringAnimation { spring: 2.6; damping: 0.24; epsilon: 0.5 } }
        Behavior on y { NumberAnimation { duration: 520; easing.type: Easing.InOutCubic } }

        property real time: shell.time
        property real level: shell.level
        property real think: shell.phase === "transcribing" || shell.phase === "thinking" ? 1 : 0
        property real speak: 0
        property real spin: shell.spin
        Behavior on think { NumberAnimation { duration: 600; easing.type: Easing.InOutSine } }
        fragmentShader: Qt.resolvedUrl("shaders/orb.frag.qsb")
      }

      // ── Minimal stage: voice line + caption at the bottom ───────────────
      Item {
        id: minimalStage
        anchors.fill: parent
        opacity: shell.minimal ? 1 : 0
        visible: opacity > 0.01
        Behavior on opacity { NumberAnimation { duration: shell.minimal ? 380 : 700; easing.type: Easing.OutCubic } }

        // Soft shade behind the bottom so the line and text read on any window.
        Rectangle {
          anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
          height: 150
          gradient: Gradient {
            GradientStop { position: 0.0; color: "transparent" }
            GradientStop { position: 1.0; color: shell.scrim(0.40) }
          }
        }

        ShaderEffect {
          id: wave
          width: Math.min(root.w * 0.42, 460)
          height: 56
          anchors.horizontalCenter: parent.horizontalCenter
          y: root.lineY - height / 2
          property real time: shell.time
          property real level: shell.level
          property real spread: shell.minimal && shell.phase !== "done" ? 1 : (shell.minimal ? 0.35 : 0)
          Behavior on spread { NumberAnimation { duration: 700; easing.type: Easing.OutCubic } }
          fragmentShader: Qt.resolvedUrl("shaders/wave.frag.qsb")
        }

        // Caption: current action, then the reply with words lighting up as spoken.
        Rectangle {
          id: caption

          readonly property string plain: shell.reply !== "" ? shell.reply : shell.actionText
          readonly property bool hasText: plain !== ""

          width: Math.min(captionText.implicitWidth + 36, Math.min(root.w - 48, 620))
          readonly property bool paged: shell.reply !== "" && shell.pages.length > 1
          height: captionText.height + 20 + (paged ? 10 : 0)
          anchors.horizontalCenter: parent.horizontalCenter
          y: root.lineY - wave.height / 2 - height - 2
          Behavior on width { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }
          Behavior on height { NumberAnimation { duration: 260; easing.type: Easing.OutCubic } }

          opacity: hasText ? 1 : 0
          Behavior on opacity { NumberAnimation { duration: 300 } }
          radius: 18
          color: shell.themeDark ? Qt.rgba(0.07, 0.07, 0.11, 0.80) : Qt.rgba(1, 1, 1, 0.88)
          border.width: 1
          border.color: shell.ink(0.09)

          MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: {
              cancelProc.running = false
              cancelProc.running = true
              shell.setPhase("hidden")
            }
          }

          // Page dots: which part of a long reply is on screen
          Row {
            visible: caption.paged
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 7
            spacing: 5
            Repeater {
              model: caption.paged ? shell.pages.length : 0
              Rectangle {
                required property int index
                width: 5; height: 5; radius: 2.5
                color: index === shell.page ? shell.ink(0.8) : shell.ink(0.22)
              }
            }
          }

          Text {
            id: captionText
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: 10
            width: Math.min(implicitWidth, Math.min(root.w - 48, 620) - 36)
            horizontalAlignment: Text.AlignHCenter
            textFormat: Text.StyledText
            wrapMode: Text.WordWrap
            maximumLineCount: 3
            elide: Text.ElideRight
            font.family: "Adwaita Sans"
            font.pixelSize: 15
            font.weight: Font.Medium
            color: shell.ink(0.95)
            property int shownPage: shell.page
            onShownPageChanged: pageFade.restart()
            NumberAnimation { id: pageFade; target: captionText; property: "opacity"; from: 0.25; to: 1; duration: 220; easing.type: Easing.OutCubic }
            text: {
              if (shell.reply === "")
                return "<font color='#a9a9be'>" + shell.escapeHtml(shell.actionText) + "…</font>"
              var pg = shell.pages[shell.page] || [0, shell.words.length]
              var n = Math.min(Math.max(Math.ceil(shell.revealed), pg[0]), pg[1])
              var spoken = shell.escapeHtml(shell.words.slice(pg[0], n).join(" "))
              var rest = shell.escapeHtml(shell.words.slice(n, pg[1]).join(" "))
              return spoken + (rest ? (spoken ? " " : "") + "<font color='#5c5c72'>" + rest + "</font>" : "")
            }
          }
        }
      }
    }
  }
}
