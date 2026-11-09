-- Keep only your personal keybinding overrides here. Add new bindings or
-- unbind defaults before replacing them.

-- See current bindings and descriptions:
--   simba menu keybindings --print

-- To disable every Simba default binding, set this in
-- ~/.config/hypr/hyprland.lua before require("default.hypr.simba"), then add
-- only the bindings you want below:
--   simba_default_bindings = false

-- To disable all preinstalled app/webapp bindings, set:
--   simba_preinstalled_bindings = false

-- Add a new binding.
-- o.bind("SUPER + SHIFT + R", "SSH", "alacritty -e ssh your-server")

-- Change an existing binding by unbinding it first, then binding the key again.
-- This example changes SUPER+SPACE from the launcher to the Simba root menu.
-- hl.unbind("SUPER + SPACE")
-- o.bind("SUPER + SPACE", "Simba menu", "simba-menu toggle root")

-- Disable a default binding without replacing it.
-- hl.unbind("SUPER + SHIFT + B")

-- Logitech MX Keys examples:
-- o.bind("SUPER + SHIFT + S", nil, "simba-capture-screenshot")
-- o.bind("SUPER + H", nil, "voxtype record toggle")
-- o.bind("SUPER + PERIOD", nil, "simba-shell shell toggle simba.emojis")

-- File manager on SUPER+E (like Windows), replacing the default SUPER+SHIFT+F
hl.unbind("SUPER + SHIFT + F")
o.bind("SUPER + E", "Explorador de Arquivos", "/usr/bin/explorador")
o.bind("SUPER + A", "Central de controle", "simba-shell -q central alternar")

-- Full screen on F11; SUPER+F becomes full width (keeps the top bar visible)
hl.unbind("SUPER + F")
o.bind("F11", "Tela cheia", hl.dsp.window.fullscreen({ mode = "fullscreen" }))
o.bind("SUPER + F", "Largura total", hl.dsp.window.fullscreen({ mode = "maximized" }))

-- Janelas estilo Windows 11 (~/.config/hypr/janelas.lua): SUPER+←/→ encaixa a janela
-- numa metade e põe a usada por último na outra; ↑ maximiza; ↓ restaura a maximizada
-- ou encaixada e minimiza a solta (como o Win+↓ do Windows).
-- O foco entre janelas fica em SUPER+SHIFT+setas.
for _, key in ipairs({ "LEFT", "RIGHT", "UP", "DOWN" }) do
  hl.unbind("SUPER + " .. key)
  hl.unbind("SUPER + SHIFT + " .. key)
end
o.bind("SUPER + LEFT", "Encaixar janela à esquerda", function() hl.dispatch(janelas.lado(nil, "esquerda")) end)
o.bind("SUPER + RIGHT", "Encaixar janela à direita", function() hl.dispatch(janelas.lado(nil, "direita")) end)
o.bind("SUPER + UP", "Maximizar janela", function() hl.dispatch(janelas.maximizar(nil)) end)
o.bind("SUPER + DOWN", "Restaurar ou minimizar janela", function() hl.dispatch(janelas.baixo(nil)) end)
o.bind("SUPER + Z", "Layouts de encaixe da janela", "qs -c botoes-janela ipc call botoes layouts")
o.bind("SUPER + SHIFT + LEFT", "Focar janela da esquerda", hl.dsp.focus({ direction = "l" }))
o.bind("SUPER + SHIFT + RIGHT", "Focar janela da direita", hl.dsp.focus({ direction = "r" }))
o.bind("SUPER + SHIFT + UP", "Focar janela de cima", hl.dsp.focus({ direction = "u" }))
o.bind("SUPER + SHIFT + DOWN", "Focar janela de baixo", hl.dsp.focus({ direction = "d" }))

-- Draco voice assistant: hold F10, speak, release (/usr/bin/draco)
o.bind("F10", "Draco (segurar para falar)", "/usr/bin/draco start")
o.bind("F10", "Draco: soltar", "/usr/bin/draco stop", { release = true })
o.bind("SUPER + F10", "Draco: configurações", "/usr/bin/draco config")
-- Esc cancels Draco; non_consuming so apps still get their Esc (no-op when Draco is idle)
o.bind("Escape", "Draco: cancelar", "/usr/bin/draco cancel", { non_consuming = true })

-- Super+P: Win+P-style display mode switcher (Configurações). Simba's default
-- here was "Pseudo-janela" (hl.dsp.window.pseudo), which no longer has a key.
hl.unbind("SUPER + P")
o.bind("SUPER + P", "Projetar (modo de exibição)", "/usr/bin/configuracoes projetar")

-- Gerenciador de Tarefas, como no Windows
o.bind("CTRL + SHIFT + ESCAPE", "Gerenciador de Tarefas", "/usr/bin/gerenciador-tarefas")

-- Menu Iniciar estilo Windows 11 (Configurações › Personalização › Iniciar).
-- O menu do Simba fica no Super+Alt+Espaço e no botão direito do botão Iniciar.
hl.unbind("SUPER + SPACE")
o.bind("SUPER + SPACE", "Menu Iniciar", "/usr/bin/configuracoes menu-iniciar")
hl.unbind("SUPER + ALT + SPACE")
o.bind("SUPER + ALT + SPACE", "Menu do Simba", "simba-menu toggle")

-- Super+L bloqueia a tela, como no Windows (o Simba usava para alternar o
-- layout da área de trabalho, que o janelas.lua já controla). Super+Ctrl+L continua.
hl.unbind("SUPER + L")
o.bind("SUPER + L", "Bloquear tela", "simba-system-lock")

-- Explorador de Arquivos (estilo Windows 11) no lugar do Nautilus.
hl.unbind("SUPER + SHIFT + F")
o.bind("SUPER + SHIFT + F", "Explorador de Arquivos", "/usr/bin/explorador")

-- Agentes de IA em sequência: quando o limite de um acaba, o próximo continua com o
-- contexto (/usr/bin/agentes; ordem em Configurações › Agentes de IA).
hl.unbind("SUPER + SHIFT + CTRL + A")
o.bind("SUPER + SHIFT + CTRL + A", "Agentes de IA", "/usr/bin/agentes abrir")

-- Apps "Oma" do Simba (Omacalc, Omawrite, Omacut) foram trocados por apps comuns:
-- os atalhos do Simba que apontavam para eles agora abrem os substitutos.
hl.unbind("SUPER + CTRL + Q")
hl.unbind("XF86Calculator")
hl.unbind("SUPER + SHIFT + W")
o.bind("SUPER + CTRL + Q", "Calculadora", "/usr/bin/calculadora")
o.bind("XF86Calculator", "Calculadora", "/usr/bin/calculadora")
o.bind("SUPER + SHIFT + W", "Editor de Texto", "uwsm-app -- gnome-text-editor")
