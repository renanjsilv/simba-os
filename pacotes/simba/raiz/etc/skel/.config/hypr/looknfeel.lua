-- Change the default Simba look'n'feel.

-- https://wiki.hypr.land/Configuring/Basics/Variables/#general
-- hl.config({
--   general = {
--     -- No gaps between windows or borders.
--     gaps_in = 0,
--     gaps_out = 0,
--     border_size = 0,
--
--     -- Change to niri-like side-scrolling layout.
--     layout = "scrolling",
--   },
-- })

-- https://wiki.hypr.land/Configuring/Basics/Variables/#decoration
-- hl.config({
--   decoration = {
--     -- Use round window corners.
--     rounding = 8,
--
--     -- Dim unfocused windows (0.0 = no dim, 1.0 = fully dimmed).
--     dim_inactive = true,
--     dim_strength = 0.15,
--   },
-- })

-- https://wiki.hypr.land/Configuring/Basics/Variables/#animations
-- hl.config({
--   animations = {
--     -- Disable all animations.
--     enabled = false,
--   },
-- })

-- https://wiki.hypr.land/Configuring/Basics/Variables/#layout
-- hl.config({
--   layout = {
--     -- Avoid overly wide single-window layouts on wide screens.
--     single_window_aspect_ratio = { 1, 1 },
--   },
-- })

-- https://wiki.hypr.land/Configuring/Layouts/Scrolling-Layout/
-- hl.config({
--   scrolling = {
--     -- See only one column per screen instead of two.
--     column_width = 0.97,
--   },
-- })

-- Draco voice assistant overlay (~/.config/quickshell/draco): it does
-- its own QML fades, so skip the compositor layer animation.
hl.layer_rule({ match = { namespace = "draco" }, no_anim = true, animation = "none" })
-- Botões de janela (~/.config/quickshell/botoes-janela): a pílula anima sozinha em QML.
hl.layer_rule({ match = { namespace = "botoes-janela.*" }, no_anim = true, animation = "none" })
-- Draco settings window (Super+F10, ~/.config/quickshell/draco-config): tiled like a normal app

-- Configurações (~/.config/quickshell/configuracoes): abre maximizada como um
-- app comum (janelas.lua); o botão restaurar a solta. Its layers animate themselves in QML.
-- Opaque: its "Mica" background is the blurred wallpaper, not what is behind it.
o.window("com.simba.Configuracoes", { tag = "-default-opacity" })
o.window("com.simba.Configuracoes", { opacity = "1 1" })
hl.layer_rule({ match = { namespace = "configuracoes-.*" }, no_anim = true, animation = "none" })
-- Menu Iniciar: fundo acrílico quando o desfoque (decoration.blur) estiver ligado.
hl.layer_rule({ match = { namespace = "configuracoes-iniciar" }, blur = true, ignore_alpha = 0.5 })

-- Gerenciador de Tarefas (~/.local/share/gerenciador-tarefas, Ctrl+Shift+Esc): janela flutuante opaca
o.window("com.simba.GerenciadorTarefas", { float = true })
o.window("com.simba.GerenciadorTarefas", { center = true })
o.window("com.simba.GerenciadorTarefas", { size = { 1060, 680 } })
o.window("com.simba.GerenciadorTarefas", { tag = "-default-opacity" })
o.window("com.simba.GerenciadorTarefas", { opacity = "1 1" })

-- Boas-vindas ao Simba OS (~/.local/share/boas-vindas): flutuante, centralizada, opaca
o.window("com.simba.BoasVindas", { float = true })
o.window("com.simba.BoasVindas", { center = true })
-- sem tamanho forçado: o GTK mede o conteúdo. Com 900×620 fixo, numa tela/fonte em que o
-- conteúdo pedia mais altura, a janela era desenhada maior que a área que recebe clique e a
-- metade de baixo dos botões Próximo/Voltar não respondia.
o.window("com.simba.BoasVindas", { tag = "-default-opacity" })
o.window("com.simba.BoasVindas", { opacity = "1 1" })

-- Agentes de IA do Simba: abre sempre maximizado (ocupa a área útil, barra de tarefas visível).
o.window("com.simba.Agentes", { tile = true, tag = "-default-opacity", opacity = "1 1" })

-- Janelas encostam nas bordas da tela (sem espaço nas laterais/topo/base).
hl.config({
  general = {
    gaps_out = 0,
    -- Janelas estilo Windows 11: cada uma abre maximizada; Super+setas ou o
    -- menu do botão maximizar encaixam lado a lado (~/.config/hypr/janelas.lua).
    layout = "lua:janelas",
  },
})

-- >>> Configurações: gerado pelo app Configurações (Super+Espaço › Configurações). Edite pelo app. >>>
hl.config({
  decoration = {
    blur = {
      enabled = true,
      passes = 3,
      size = 12,
    },
  },
})
-- <<< Configurações <<<

-- Explorador de Arquivos (~/.local/share/explorador): opaco, como o do Windows
o.window("com.simba.Explorador", { tag = "-default-opacity" })
o.window("com.simba.Explorador", { opacity = "1 1" })

-- Gerar ISO (~/.local/share/gerar-iso/app.py): opaco
o.window("com.simba.GerarIso", { tag = "-default-opacity" })
o.window("com.simba.GerarIso", { opacity = "1 1" })

-- Calculadora (substituta do Omacalc) flutuante, como era a do Simba
o.window("org.gnome.Calculator", { float = true })

-- Janelas maximizadas sem borda (janelas.lua põe a etiqueta janelas-max nelas).
o.window({ tag = "janelas-max" }, { border_size = 0 })
