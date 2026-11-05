# First-party plugins

These plugins ship with Simba and are discovered by the shell at startup.
They use the same `manifest.json` contract as third-party plugins; the
only difference is that the shell flags them with `__isFirstParty: true`.
First-party non-bar plugins are enabled unless listed in `disabledPlugins[]`;
`simba.bar` is the default bar option and becomes inactive only while another
`kind: "bar"` plugin is selected. Services and keep-loaded panels are mounted
at startup; other panels, overlays, and menus are loaded on demand.

User-installed plugins live alongside these conceptually but on disk under
`~/.config/simba/plugins/<plugin-id>/` rather than in this directory.

| Plugin        | id                        | kinds                   | entry point                           |
|---------------|---------------------------|-------------------------|---------------------------------------|
| Bar           | `simba.bar`             | `bar`                   | `bar/Bar.qml`                         |
| Image picker  | `simba.image-picker`    | `overlay`               | `image-picker/ImagePicker.qml`        |
| Emojis        | `simba.emojis`          | `overlay`               | `emojis/Emojis.qml`                   |
| Clipboard mgr | `simba.clipboard`       | `overlay`               | `clipboard/Clipboard.qml`             |
| Reminders     | `simba.reminders`       | `overlay`               | `reminders/ReminderFlow.qml`          |
| Simba menu  | `simba.menu`            | `menu`, `bar-widget`    | `menu/Menu.qml`, `menu/BarWidget.qml` |
| Notifications | `simba.notifications`   | `service`               | `notifications/Service.qml`           |
| Audio         | `simba.audio`           | `bar-widget`            | `panels/audio/Panel.qml`              |
| Bluetooth     | `simba.bluetooth`       | `bar-widget`            | `panels/bluetooth/Panel.qml`          |
| Clock         | `simba.clock`           | `bar-widget`            | `panels/clock/BarWidget.qml`          |
| Monitor       | `simba.monitor`         | `bar-widget`            | `panels/monitor/Panel.qml`            |
| Network       | `simba.network`         | `bar-widget`            | `panels/network/Panel.qml`            |
| Power         | `simba.power`           | `bar-widget`            | `panels/power/Panel.qml`              |
| Tailscale     | `simba.tailscale`       | `bar-widget`            | `panels/tailscale/Panel.qml`          |
| Agents   | `simba.agents`     | `bar-widget`            | `agents/Panel.qml`               |
| Weather       | `simba.weather`         | `bar-widget`            | `panels/weather/BarWidget.qml`        |
| Media         | `simba.media`           | `service`, `bar-widget` | `services/media/Service.qml`, `services/media/BarWidget.qml` |
| Battery       | `simba.battery`         | `service`               | `services/battery/Service.qml`        |
| Idle          | `simba.idle`            | `service`               | `services/idle/Service.qml`           |
| Night light   | `simba.nightlight`      | `service`               | `services/nightlight/Service.qml`     |
| Lock screen   | `simba.lock`            | `service`               | `lock/Service.qml`                    |
| OSD           | `simba.osd`             | `panel`                 | `osd/Osd.qml`                         |
| Polkit agent  | `simba.polkit`          | `service`               | `polkit/PolkitAgent.qml`              |

First-party bar-only widgets also carry manifests next to their QML files,
e.g. `bar/widgets/Workspaces.manifest.json`. Rich popup widgets live in their
own plugin directories, each with its own `manifest.json`.

## Bar

The built-in status bar and default full-bar option. Layout lives in the
top-level `bar:` subtree of `~/.config/simba/shell.json` (with the shell
providing [`config/simba/shell.json`](../../config/simba/shell.json) when
the user has no file). See [`bar/README.md`](bar/README.md) for the widget catalogue
and customization schema.

## Image picker

Fullscreen image-grid selector overlay. Used by `simba-menu-images`
(wallpaper picker) and `simba-theme-switcher` (theme picker) and any
other caller that wants to present a directory of images with previews.

Two ways to drive it:

- Shell-level summon: `simba-shell shell summon simba.image-picker '<jsonPayload>'`.
  The payload can carry `imageDirs`, `imageRows`, `selectedImage`,
  `selectionFile`, `doneFile`, `showLabels`, `filterable`. Best for
  in-shell callers that already speak JSON.
- Direct IPC target: `simba-shell image-selector open <imageDirs> <imageRowsB64> <selectedImage> <selectionFile> <doneFile> <showLabels> <filterable>`.
  Positional args; `imageRowsB64` is base64-encoded so embedded newlines /
  tabs survive the bash argv handoff. This is what `simba-menu-images`
  uses. Colors come from the central shell theme singleton; there is no
  per-call override surface.

The selection round-trip remains file-based: callers create a
`selection_file` and `done_file` (both `mktemp`), pass the paths, and
poll `done_file` for existence. The plugin writes the chosen path into
`selection_file` and touches `done_file` when it's done. `cancel` IPC
clears it without writing a selection.

The plugin has `keepLoaded: true` so the layer-shell window survives
between summons within a single shell session.

## Lock screen

Session-lock surface using Quickshell's native `WlSessionLock` and two
separate PAM services: `simba-lock-password` for password auth and,
only when fingerprints are enrolled, `simba-lock-fingerprint` for
fingerprint auth. It mirrors the previous lock screen field dimensions,
colors, blurred wallpaper, placeholder, and Hyprland-driven corners.
The plugin sets `keepLoaded: true` so a plugin hot-reload (for example
an installed bar widget changing on disk) does not destroy the lock
client while Hyprland still holds the session lock.

## Polkit agent

Theme-aware authentication dialog for privileged actions. It uses
Quickshell's native `Quickshell.Services.Polkit.PolkitAgent` backend and
runs inside the long-lived `simba-shell` process, replacing the old
`polkit-gnome-authentication-agent-1` autostart.

## Simba menu

Quickshell-powered Simba command menu.
The menu UI lives in `menu/Menu.qml` as a first-party `menu` plugin and is
summoned through the shell (`simba-shell shell summon simba.menu ...`),
so it shares the long-running `simba-shell` process instead of starting a
second Quickshell instance.

The menu definition lives outside the shell host code:

- defaults: `default/simba/simba-menu.jsonc`
- user extensions: `~/.config/simba/extensions/simba-menu.jsonc`

The shell parses both JSONC files at startup (with `watchChanges: true`
so edits take effect without a restart), evaluates `when:` / `checked:`
bash expressions in a single batched subprocess, and executes the
selected `action:` string directly via `Quickshell.execDetached`. The
long-running shell process keeps the parsed menu in memory, so the
keybind → IPC → visible path costs ~30ms cold.

## Coming soon

- `simba.theme-switcher` — folds theme switching into the shell.
