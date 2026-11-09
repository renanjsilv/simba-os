-- Keep only your personal input overrides here. Uncommented settings below
-- replace Simba's defaults.

-- Keyboard layout and options.
-- See https://wiki.hypr.land/Configuring/Basics/Variables/#input
-- hl.config({
--   input = {
--     -- Use multiple keyboard layouts and switch between them with Left Alt + Right Alt.
--     kb_layout = "us,dk,eu",
--     kb_options = "compose:caps,shift:both_capslock_cancel,grp:alts_toggle",
--
--     -- Use a specific keyboard variant if needed (e.g. intl for international keyboards).
--     kb_variant = "intl",
--
--     -- Change speed of keyboard repeat.
--     repeat_rate = 40,
--     repeat_delay = 250,
--
--     -- Start with numlock on by default.
--     numlock_by_default = true,
--
--     -- Increase sensitivity for mouse/trackpad (default: 0).
--     sensitivity = 0.35,
--
--     -- Turn off mouse acceleration (default: adaptive).
--     accel_profile = "flat",
--
--     touchpad = {
--       -- Use natural (inverse) scrolling.
--       natural_scroll = true,
--
--       -- Use two-finger clicks for right-click instead of lower-right corner.
--       clickfinger_behavior = true,
--
--       -- Control the speed of your scrolling.
--       scroll_factor = 0.4,
--
--       -- Enable the touchpad while typing.
--       disable_while_typing = false,
--
--       -- Left-click-and-drag with three fingers.
--       drag_3fg = 1,
--     },
--   },
-- })

-- App-specific touchpad scroll speeds.
-- o.window("(Alacritty|kitty|foot)", { scroll_touchpad = 1.5 })
-- o.window("com.mitchellh.ghostty", { scroll_touchpad = 0.2 })

-- Enable touchpad gestures for changing workspaces.
-- See https://wiki.hypr.land/Configuring/Advanced-and-Cool/Gestures/
-- hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })

-- Enable touchpad gestures for moving focus (helpful on scrolling layout).
-- hl.gesture({ fingers = 3, direction = "left", action = function() hl.dispatch(hl.dsp.focus({ direction = "l" })) end })
-- hl.gesture({ fingers = 3, direction = "right", action = function() hl.dispatch(hl.dsp.focus({ direction = "r" })) end })

-- CapsLock normal (maiúsculas) em vez de tecla Compose.
hl.config({
  input = {
    kb_options = "",
    -- Foco segue o mouse só ao cruzar a borda de outra janela: ao clicar numa
    -- prévia da barra de tarefas, mexer o mouse não devolve o foco para a
    -- janela flutuante que estiver embaixo do cursor.
    mouse_refocus = false,
    -- Foco no clique, como no Windows 11: passar o mouse não troca a janela
    -- ativa (a rolagem continua indo para a janela sob o cursor). O
    -- empilhamento do janelas.lua depende disso.
    follow_mouse = 0,
  },
})

-- Keys typed by wtype (Draco automates apps with it) must not trigger
-- compositor shortcuts: wtype's first key lands on Esc's keycode and was
-- firing the Draco cancel bind mid-task.
hl.device({ name = "hl-virtual-keyboard-wtype", keybinds = false })

-- >>> Configurações: gerado pelo app Configurações (Super+Espaço › Configurações). Edite pelo app. >>>
hl.config({
  input = {
    touchpad = {
      scroll_factor = 0.7,
    },
  },
})
-- <<< Configurações <<<
