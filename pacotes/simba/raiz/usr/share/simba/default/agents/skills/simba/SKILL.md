---
name: simba
description: >
  REQUIRED for end-user customization of Linux desktop, window manager, or system config.
  Use when editing ~/.config/hypr/, ~/.config/simba/,
  ~/.config/alacritty/, ~/.config/foot/, ~/.config/kitty/, or ~/.config/ghostty/.
  Triggers: Hyprland, window rules, animations, keybindings, monitors, gaps, borders,
  blur, opacity, simba-shell, bar, terminal config, themes, background,
  night light, idle, lock screen, screenshots, reminders, layer rules, workspace
  settings, display config, and user-facing simba commands. Excludes Simba
  source development through `simba dev link` workflows.
---

# Simba Skill

Manage Simba OS systems (Arch Linux + Hyprland).

This skill is for end-user customization on installed systems.
It is not for contributing to Simba source code.

## When This Skill MUST Be Used

**ALWAYS invoke this skill for end-user requests involving ANY of these:**

- Editing ANY file in `~/.config/hypr/` (window rules, animations, keybindings, monitors, etc.)
- Editing `~/.config/simba/shell.json` (status bar layout, widgets)
- Editing terminal configs (alacritty, foot, kitty, ghostty)
- Editing ANY file in `~/.config/simba/`
- Window behavior, animations, opacity, blur, gaps, borders
- Layer rules, workspace settings, display/monitor configuration
- Themes, backgrounds, fonts, appearance changes
- User-facing `simba` commands (`simba theme ...`, `simba refresh ...`, `simba restart ...`, etc.)
- Screenshots, screen recording, reminders, night light, idle behavior, lock screen

**If you're about to edit a config file in ~/.config/ on this system, STOP and use this skill first.**

**Do NOT use this skill for Simba development tasks** (editing the Simba source tree, creating migrations, or running `simba dev ...` workflows).

## Topic Guides

Deeper instructions for common areas live next to this file. Read the
matching guide before starting:

- [`hyprland.md`](hyprland.md) - keybindings, monitors, window rules, and other Hyprland config
- [`plugins.md`](plugins.md) - the Simba shell: bar layout, widgets, plugins, idle behavior
- [`theming.md`](theming.md) - themes, backgrounds, and fonts
- [`hooks.md`](hooks.md) - automation hooks that run on system events
- [`capture.md`](capture.md) - screenshots, screen recordings, OCR text capture, and file sharing
- [`contributing.md`](contributing.md) - reporting Simba bugs and submitting fixes upstream

## Critical Safety Rules

For privileged commands, follow the Privilege Escalation rules below: `sudo` when a terminal is available for the password prompt, `pkexec` when it is not. Do not wrap commands that already manage privilege elevation themselves.

**For end-user customization tasks, NEVER modify anything in `/usr/share/simba/`** - but READING is safe and encouraged.

This directory is owned by the simba package. Any local changes will be
overwritten on the next `simba update`.

```
/usr/share/simba/     # READ-ONLY - NEVER EDIT (reading is OK)
├── bin/                    # Command source (packaged binaries are on PATH)
├── config/                 # Default config templates
├── themes/                 # Stock themes
├── default/                # System defaults
├── shell/                  # Simba shell source and defaults
├── migrations/             # Update migrations
└── install/                # Installation scripts
```

**Reading `/usr/share/simba/` is SAFE and useful** - do it freely to:
- Understand how simba commands work: `simba theme set --help` or `cat $(which simba-theme-set)`
- See default configs before customizing: `cat "$SIMBA_PATH/config/simba/shell.json"`
- Check stock theme files to copy for customization
- Reference default hyprland settings: `cat /usr/share/simba/default/hypr/*`

**Always use these safe locations instead:**
- `~/.config/` - User configuration (safe to edit)
- `~/.config/simba/themes/<custom-name>/` - Custom themes
- `~/.config/simba/hooks/` - Custom automation hooks

If the request is to develop Simba itself, this skill is out of scope. Follow repository development instructions instead of this skill.

## Privilege Escalation

For an interactive script or command run in a visible terminal, use `sudo` for
privileged work. Simba may grant passwordless `sudo` access to particular
commands, and the terminal is the appropriate place to request a password
when one is needed.

Use `pkexec` only when the caller cannot interact with a terminal or cannot
enter a password there, such as a command launched by an agent or a graphical
background process. Do not replace `sudo` with `pkexec` merely because a
command changes system state.

## System Architecture

Simba is built on:

| Component | Purpose | Config Location |
|-----------|---------|-----------------|
| **Arch Linux** | Base OS | `/etc/`, `~/.config/` |
| **Hyprland** | Wayland compositor/WM | `~/.config/hypr/` |
| **Simba shell** | Status bar + notifications (Quickshell) | `~/.config/simba/shell.json` |
| **Launcher/menus** | Quickshell menu | `~/.config/simba/extensions/simba-menu.jsonc` |
| **Alacritty/Foot/Kitty/Ghostty** | Terminals | `~/.config/<terminal>/` |
| **Simba OSD** | On-screen display | Quickshell plugin |

## Command Discovery

Simba ships a single `simba` CLI that dispatches to all `simba-*` binaries via `simba <group> <action>`. Always prefer this form — it is self-documenting and stable. The underlying `simba-*` binaries still exist on `PATH` and remain safe to read for source.

```bash
# List every documented command and its summary (--all includes hidden commands)
simba commands

# Show the commands inside a group
simba theme --help
simba refresh --help
simba restart --help

# Show help for a specific command (does not execute it)
simba theme set --help

# Machine-readable listing (binary, route, summary, args, aliases)
simba commands --json

# Read a command's source to understand it
cat $(which simba-theme-set)
```

### Command Groups

Run `simba --help` for the full list. The most common groups:

| Group | Purpose | Example |
|-------|---------|---------|
| `simba refresh` | Reset config to defaults (backs up first) | `simba refresh shell` |
| `simba restart` | Restart a service/app | `simba restart shell` |
| `simba toggle` | Toggle feature on/off | `simba toggle nightlight` |
| `simba theme` | Theme management | `simba theme set <name>` |
| `simba bar` | Bar layout and widgets | `simba bar move simba.clock --section right` |
| `simba plugin` | Manage/clone shell plugins | `simba plugin clone simba.clock` |
| `simba hook` | Install automation hooks | `simba hook install theme-set <script>` |
| `simba install` | Install optional software / packages | `simba install docker dbs` |
| `simba launch` | Launch apps | `simba launch browser` |
| `simba capture` | Screenshots and recordings | `simba capture screenshot` |
| `simba reminder` | Desktop notification reminders | `simba reminder 15 "Pickup Jack"` |
| `simba pkg` | Package management | `simba pkg add <pkg>` |
| `simba setup` | Interactive setup wizards | `simba setup security fingerprint` |
| `simba update` | System updates | `simba update` |

## Configuration Locations

Hyprland config lives in `~/.config/hypr/` — see [`hyprland.md`](hyprland.md).
The Simba shell (bar, notifications, plugins, idle) is configured in
`~/.config/simba/shell.json` — see [`plugins.md`](plugins.md).

### Terminals

```
~/.config/alacritty/alacritty.toml
~/.config/foot/foot.ini
~/.config/kitty/kitty.conf
~/.config/ghostty/config
```

**Command:** `simba restart terminal`

### Other Configs

| App | Location |
|-----|----------|
| btop | `~/.config/btop/btop.conf` |
| fastfetch | `/etc/fastfetch/config.jsonc` default; `~/.config/fastfetch/config.jsonc` user override |
| lazygit | `~/.config/lazygit/config.yml` |
| starship | `~/.config/starship.toml` |
| git | `~/.config/git/config` |

## Safe Customization Patterns

### Edit User Config Directly

For simple changes, edit files in `~/.config/`:

```bash
# 1. Read current config
cat ~/.config/hypr/bindings.lua

# 2. Backup before changes
cp ~/.config/hypr/bindings.lua ~/.config/hypr/bindings.lua.bak.$(date +%s)

# 3. Make changes with Edit tool

# 4. Apply changes
# - Hyprland: auto-reloads on save, but MUST validate with `hyprctl reload` and `hyprctl configerrors`
# - Simba shell: shell.json and user plugin code under ~/.config/simba/plugins/ hot-reload on save
# - Menus/launcher: ~/.config/simba/extensions/simba-menu.jsonc hot-reloads on save
# - Terminals: apply with `simba restart terminal` (reloads running terminals; foot picks changes up in new windows)
```

### Reset to Defaults -- ALWAYS SEEK USER CONFIRMATION BEFORE RUNNING

When customizations go wrong:

```bash
# Reset specific config (creates backup automatically)
simba refresh shell
simba refresh hyprland

# The refresh command:
# 1. Backs up current config with timestamp
# 2. Copies default from $SIMBA_PATH/config/
# 3. Restarts the component where the refresh needs it (e.g. `refresh shell`)
```

## System Commands

```bash
simba update                  # Full system update
simba version                 # Show Simba version
simba debug --no-sudo --print # Debug info (ALWAYS use these flags)
simba system lock             # Lock screen
simba system shutdown         # Shutdown
simba system reboot           # Reboot
```

**IMPORTANT:** Always run `simba debug` with `--no-sudo --print` flags to avoid interactive sudo prompts that will hang the terminal.

## Troubleshooting

```bash
# Get debug information (ALWAYS use these flags to avoid interactive prompts)
simba debug --no-sudo --print

# Reset specific config to defaults
simba refresh <app>

# Refresh specific config file
# config-file path is relative to ~/.config/
# eg. `simba refresh config hypr/hyprland.lua` will refresh ~/.config/hypr/hyprland.lua
simba refresh config <config-file>

# Full reinstall of configs (nuclear option)
simba reinstall
```

## Decision Framework

When user requests system changes:

1. **Is it a stock simba command?** Use it directly
2. **Is it a config edit?** Edit in `~/.config/`, never `/usr/share/simba/`
3. **Is it a theme customization?** Follow [`theming.md`](theming.md); create a NEW custom theme directory
4. **Is it automation?** Follow [`hooks.md`](hooks.md); use `simba hook install` and the hook `.d` directories
5. **Is it a package install?** Use `simba pkg add <pkgs...>` (or `simba pkg aur add <pkgs...>` for AUR-only packages)
6. **Is it built-in shell/plugin code?** Follow [`plugins.md`](plugins.md); clone it with `simba plugin clone`, never edit the packaged copy
7. **Unsure if command exists?** Run `simba commands` (or `simba <group> --help` for one group)

### Reminder Requests

When the user asks to set a reminder, use `simba reminder <minutes> [message]` directly. Convert natural language durations to minutes and title-case short reminder labels when appropriate.

```bash
simba reminder 15 "Pickup Jack"
simba reminder 60 "Check laundry"
simba reminder show
simba reminder clear
```

## Out of Scope

This skill intentionally does not cover Simba source development. Do not use this skill for:
- Editing files in `/usr/share/simba/` (`bin/`, `config/`, `default/`, `shell/`, `themes/`, `migrations/`, etc.)
- Creating or editing migrations
- Running `simba dev ...` commands

## Example Requests

- "Change my theme to catppuccin" -> `simba theme set catppuccin`
- "Add a keybinding for Super+E to open file manager" -> Check existing bindings first, call `hl.unbind` if needed, then `o.bind` in `~/.config/hypr/bindings.lua`
- "Configure my external monitor" -> Edit `~/.config/hypr/monitors.lua`
- "Make the window gaps smaller" -> Edit `~/.config/hypr/looknfeel.lua`
- "Turn on night light" -> `simba toggle nightlight` (for time-based schedules, edit `~/.config/hypr/hyprsunset.conf` profiles, then `simba restart hyprsunset`)
- "Set a reminder to pickup jack in 15 minutes" -> `simba reminder 15 "Pickup Jack"`
- "Show my reminders" -> `simba reminder show`
- "Clear all reminders" -> `simba reminder clear`
- "Customize the catppuccin theme colors" -> Overlay: put an edited `colors.toml` in `~/.config/simba/themes/catppuccin/`, then re-apply the theme (see `theming.md`)
- "Run a script every time I change themes" -> Install it with `simba hook install theme-set <script>`
- "Change how workspace labels are rendered" -> Clone `simba.workspaces`, which switches the bar to `<username>.workspaces`, then edit the clone
- "Lock after ten minutes" -> Set `idle.lock` to `600` in `~/.config/simba/shell.json`
- "Reset shell/bar to defaults" -> `simba refresh shell`
- "Record my screen" -> `simba screenrecord --fullscreen`, then `simba screenrecord --stop-recording` (see `capture.md`)
- "Report this bug to Simba" -> Gather diagnostics and a capture of the problem, then file it (see `contributing.md`)
