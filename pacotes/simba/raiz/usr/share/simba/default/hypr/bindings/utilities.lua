o.bind("SUPER + SPACE", "Menu do Simba", "simba-menu toggle")
o.bind("SUPER + ALT + SPACE", "Menu de aplicativos", "simba-menu toggle apps")
o.bind("SUPER + CTRL + E", "Emojis", "simba-shell shell toggle simba.emojis")
o.bind("SUPER + CTRL + C", "Menu de captura", "simba-menu toggle capture")
o.bind("SUPER + CTRL + O", "Abrir/fechar menu", "simba-menu toggle toggle")
o.bind("SUPER + CTRL + H", "Menu de hardware", "simba-menu toggle hardware")
o.bind("SUPER + SHIFT + code:201", "Menu do Simba", "simba-menu toggle root")
o.bind("SUPER + ESCAPE", "Menu do sistema", "simba-menu toggle system")
o.bind("XF86PowerOff", "Menu de energia", "simba-menu toggle system", { locked = true })
o.bind("SUPER + K", "Atalhos de teclado", "simba-menu-keybindings")
o.bind("SUPER + ALT + K", "Atalhos do Tmux", "simba-menu-tmux-keybindings")
o.bind("SUPER + CTRL + K", "Atalhos do Herdr", "simba-menu-herdr-keybindings")
o.bind("SUPER + CTRL + Q", "Calculadora", "omacalc")
o.bind("XF86Calculator", "Calculadora", "omacalc")

o.bind_toggle("SUPER + SHIFT + SPACE", "Mostrar/ocultar barra superior", "bar")
o.bind("SUPER + CTRL + SPACE", "Trocar plano de fundo", "simba-menu toggle background")
o.bind("SUPER + SHIFT + CTRL + SPACE", "Menu de temas", "simba-menu toggle theme")
o.bind("SUPER + BACKSPACE", "Ativar/desativar transparência da janela", "simba-hyprland-window-transparency-toggle")
o.bind("SUPER + SHIFT + BACKSPACE", "Ativar/desativar espaçamento entre janelas", "simba-hyprland-window-gaps-toggle")
o.bind("SUPER + CTRL + BACKSPACE", "Alternar proporção quadrada (janela única)", "simba-hyprland-window-single-square-aspect-toggle")

-- xkbcommon names the comma keysym "comma"; the upper-case "COMMA" does not match.
o.bind("SUPER + comma", "Dispensar última notificação", "simba-shell notifications dismissOne")
o.bind("SUPER + SHIFT + comma", "Dispensar todas as notificações", "simba-shell notifications dismissAll")
o.bind_toggle("SUPER + CTRL + comma", "Silenciar/reativar notificações", "notification-silencing")
o.bind("SUPER + ALT + comma", "Abrir última notificação", "simba-shell notifications invokeLast")
o.bind("SUPER + SHIFT + ALT + comma", "Abrir histórico de notificações", "simba-shell notifications showHistory")

o.bind_toggle("SUPER + CTRL + I", "Ativar/desativar bloqueio por inatividade", "idle")
o.bind_toggle("SUPER + CTRL + N", "Ativar/desativar luz noturna", "nightlight")
o.bind("SUPER + CTRL + Delete", "Ligar/desligar tela do notebook", "simba-hyprland-monitor-internal toggle")
o.bind("SUPER + CTRL + ALT + Delete", "Ativar/desativar espelhamento da tela do notebook", "simba-hyprland-monitor-internal-mirror toggle")
o.bind("switch:on:Lid Switch", nil, "simba-system-lid-close", { locked = true })
o.bind("switch:off:Lid Switch", nil, "simba-hyprland-monitor-clamshell", { locked = true })

o.bind("PRINT", "Captura de tela", "simba-capture-screenshot")
o.bind("ALT + PRINT", "Gravação de tela", "simba-capture-screenrecording --stop-recording || simba-menu toggle trigger.capture.screenrecord")
o.bind("SUPER + ALT + code:34", "Diminuir sobreposição da webcam", "simba-capture-webcam-resize smaller")
o.bind("SUPER + ALT + code:35", "Aumentar sobreposição da webcam", "simba-capture-webcam-resize larger")
o.bind("SUPER + PRINT", "Seletor de cores", "pkill hyprpicker || hyprpicker -a")
o.bind("SUPER + CTRL + PRINT", "Extrair texto (OCR) de captura de tela", "simba-capture-text")

-- Keyboard control for the slurp region picker (see simba-capture-region).
-- The binds live exactly as long as a selection layer is on screen (slurp
-- opens one per monitor), so they cannot leak or get stuck.
-- Unbinding by key would take a same-key binding out of the user's own config
-- with it, so each handle is kept and removed individually.
local selection_layers = 0
local selection_binds = {}

hl.on("layer.opened", function(layer)
  if layer.namespace == "selection" then
    selection_layers = selection_layers + 1
    if selection_layers == 1 then
      selection_binds = {
        hl.bind("RETURN", hl.dsp.exec_cmd("simba-capture-region --take-window"), { description = "Capturar janela destacada" }),
        hl.bind("CTRL + RETURN", hl.dsp.exec_cmd("simba-capture-region --take-fullscreen"), { description = "Capturar a tela inteira" }),
        hl.bind("TAB", hl.dsp.exec_cmd("simba-capture-region --select-window next"), { description = "Selecionar próxima janela para capturar" }),
        hl.bind("CTRL + TAB", hl.dsp.exec_cmd("simba-capture-region --select-window prev"), { description = "Selecionar janela anterior para capturar" }),
      }
      for _, direction in ipairs({ "left", "right", "up", "down" }) do
        table.insert(
          selection_binds,
          hl.bind(direction:upper(), hl.dsp.exec_cmd("simba-capture-region --select-window " .. direction), { description = "Selecionar janela para capturar" })
        )
      end
    end
  end
end)

hl.on("layer.closed", function(layer)
  if layer.namespace == "selection" and selection_layers > 0 then
    selection_layers = selection_layers - 1
    if selection_layers == 0 then
      for _, keybind in ipairs(selection_binds) do
        keybind:unbind()
      end
      selection_binds = {}
    end
  end
end)

o.bind("SUPER + CTRL + S", "Compartilhar", "simba-menu toggle share")

o.bind("SUPER + CTRL + PERIOD", "Converter mídia", "simba-transcode")

o.bind("SUPER + CTRL + R", "Criar lembrete", "simba-menu toggle reminder-set")
o.bind("SUPER + CTRL + ALT + R", "Mostrar lembretes", "simba-reminder show")
o.bind("SUPER + SHIFT + CTRL + R", "Limpar lembretes", "simba-reminder clear")

o.bind("SUPER + CTRL + ALT + T", "Mostrar hora", "simba-notification-time")
o.bind("SUPER + CTRL + ALT + B", "Mostrar bateria restante", "simba-notification-battery")
o.bind("SUPER + CTRL + ALT + W", "Mostrar/ocultar clima", "simba-notification-weather")

o.bind("SUPER + SHIFT + CTRL + A", "Agentes de IA (mostrar/ocultar)", "simba-agentes --toggle")
o.bind("SUPER + CTRL + A", "Áudio", "simba-shell shell toggle simba.audio")
o.bind("SUPER + CTRL + B", "Bluetooth", "simba-shell shell toggle simba.bluetooth")
o.bind("SUPER + CTRL + D", "Tela", "simba-shell shell toggle simba.monitor")
o.bind("SUPER + CTRL + ALT + D", "Calendário", "simba-shell shell toggle simba.clock")
o.bind("SUPER + CTRL + W", "Rede", "simba-shell shell toggle simba.network")
o.bind("SUPER + CTRL + P", "Energia", "simba-shell shell toggle simba.power")
o.bind("SUPER + CTRL + T", "Atividade", { tui = "btop" })

-- The letters above name a panel; the numbers count them. 1 is the leftmost
-- panel in the bar's right section, and a widget with no panel of its own (the
-- tray) is not counted, so the number matches the icon a user would point at.
-- A bar with fewer panels than this leaves the tail of the range doing nothing.
for panel = 1, 9 do
  o.bind(
    "SUPER + CTRL + code:" .. tostring(panel + 9),
    "Painel da barra " .. panel,
    "simba-shell -q shell togglePanelAt right " .. panel
  )
end

o.bind("SUPER + CTRL + Z", "Aumentar zoom", function()
  local zoom = hl.get_config("cursor.zoom_factor") or 1
  hl.config({ cursor = { zoom_factor = zoom + 1 } })
end)

o.bind("SUPER + CTRL + ALT + Z", "Redefinir zoom", function()
  hl.config({ cursor = { zoom_factor = 1 } })
end)

o.bind("SUPER + CTRL + L", "Bloquear sistema", "simba-system-lock")
