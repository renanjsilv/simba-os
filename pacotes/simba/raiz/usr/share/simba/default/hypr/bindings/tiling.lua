o.bind("SUPER + W", "Fechar janela", hl.dsp.window.close())
o.bind("CTRL + ALT + DELETE", "Fechar todas as janelas", "simba-hyprland-window-close-all")

o.bind("SUPER + J", "Alternar divisão da janela", hl.dsp.layout("togglesplit"))
o.bind("SUPER + P", "Pseudo-janela", hl.dsp.window.pseudo())
o.bind("SUPER + T", "Alternar janela flutuante/lado a lado", hl.dsp.window.float({ action = "toggle" }))
o.bind("SUPER + F", "Tela cheia", hl.dsp.window.fullscreen({ mode = "fullscreen" }))
o.bind("SUPER + CTRL + F", "Tela cheia lado a lado", "simba-hyprland-window-tiled-fullscreen-toggle")
o.bind("SUPER + ALT + F", "Largura total", hl.dsp.window.fullscreen({ mode = "maximized" }))
o.bind("SUPER + O", "Destacar janela (flutuar e fixar)", "simba-hyprland-window-pop")
o.bind("SUPER + ALT + Home", "Salvar largura da janela", "simba-hyprland-window-width save")
o.bind("SUPER + Home", "Restaurar largura da janela", "simba-hyprland-window-width restore")
o.bind("SUPER + L", "Alternar layout da área de trabalho", "simba-hyprland-workspace-layout-toggle")

o.bind("SUPER + LEFT", "Focar janela à esquerda", hl.dsp.focus({ direction = "l" }))
o.bind("SUPER + RIGHT", "Focar janela à direita", hl.dsp.focus({ direction = "r" }))
o.bind("SUPER + UP", "Focar janela acima", hl.dsp.focus({ direction = "u" }))
o.bind("SUPER + DOWN", "Focar janela abaixo", hl.dsp.focus({ direction = "d" }))

for workspace = 1, 10 do
  local key = "code:" .. tostring(workspace + 9)
  o.bind("SUPER + " .. key, "Ir para a área de trabalho " .. workspace, hl.dsp.focus({ workspace = tostring(workspace) }))
  o.bind("SUPER + SHIFT + " .. key, "Mover janela para a área de trabalho " .. workspace, hl.dsp.window.move({ workspace = tostring(workspace) }))
  o.bind("SUPER + SHIFT + ALT + " .. key, "Mover janela (sem seguir) para a área de trabalho " .. workspace, hl.dsp.window.move({ workspace = tostring(workspace), follow = false }))
end

o.bind("SUPER + S", "Mostrar/ocultar rascunho", hl.dsp.workspace.toggle_special("scratchpad"))
o.bind("SUPER + ALT + S", "Mover janela para o rascunho", hl.dsp.window.move({ workspace = "special:scratchpad", follow = false }))

o.bind("SUPER + TAB", "Próxima área de trabalho", hl.dsp.focus({ workspace = "e+1" }))
o.bind("SUPER + SHIFT + TAB", "Área de trabalho anterior", hl.dsp.focus({ workspace = "e-1" }))
o.bind("SUPER + CTRL + TAB", "Última área de trabalho usada", hl.dsp.focus({ workspace = "previous" }))

o.bind("SUPER + SHIFT + ALT + LEFT", "Mover área de trabalho para o monitor à esquerda", hl.dsp.workspace.move({ monitor = "l" }))
o.bind("SUPER + SHIFT + ALT + RIGHT", "Mover área de trabalho para o monitor à direita", hl.dsp.workspace.move({ monitor = "r" }))
o.bind("SUPER + SHIFT + ALT + UP", "Mover área de trabalho para o monitor acima", hl.dsp.workspace.move({ monitor = "u" }))
o.bind("SUPER + SHIFT + ALT + DOWN", "Mover área de trabalho para o monitor abaixo", hl.dsp.workspace.move({ monitor = "d" }))

o.bind("SUPER + SHIFT + LEFT", "Trocar janela com a da esquerda", hl.dsp.window.swap({ direction = "l" }))
o.bind("SUPER + SHIFT + RIGHT", "Trocar janela com a da direita", hl.dsp.window.swap({ direction = "r" }))
o.bind("SUPER + SHIFT + UP", "Trocar janela com a de cima", hl.dsp.window.swap({ direction = "u" }))
o.bind("SUPER + SHIFT + DOWN", "Trocar janela com a de baixo", hl.dsp.window.swap({ direction = "d" }))

o.bind("ALT + TAB", "Focar próxima janela", hl.dsp.window.cycle_next())
o.bind("ALT + SHIFT + TAB", "Focar janela anterior", hl.dsp.window.cycle_next({ next = false }))
o.bind("ALT + TAB", "Trazer janela ativa para frente", hl.dsp.window.bring_to_top())
o.bind("ALT + SHIFT + TAB", "Trazer janela ativa para frente", hl.dsp.window.bring_to_top())

o.bind("CTRL + ALT + TAB", "Focar próximo monitor", hl.dsp.focus({ monitor = "+1" }))
o.bind("CTRL + ALT + SHIFT + TAB", "Focar monitor anterior", hl.dsp.focus({ monitor = "-1" }))

o.bind("SUPER + code:20", "Expandir janela para a esquerda", hl.dsp.window.resize({ x = -100, y = 0, relative = true }))
o.bind("SUPER + code:21", "Encolher janela para a esquerda", hl.dsp.window.resize({ x = 100, y = 0, relative = true }))
o.bind("SUPER + SHIFT + code:20", "Encolher janela para cima", hl.dsp.window.resize({ x = 0, y = -100, relative = true }))
o.bind("SUPER + SHIFT + code:21", "Expandir janela para baixo", hl.dsp.window.resize({ x = 0, y = 100, relative = true }))

o.bind("SUPER + ALT + code:20", "Expandir janela um pouco para a esquerda", hl.dsp.window.resize({ x = -25, y = 0, relative = true }))
o.bind("SUPER + ALT + code:21", "Encolher janela um pouco para a esquerda", hl.dsp.window.resize({ x = 25, y = 0, relative = true }))
o.bind("SUPER + SHIFT + ALT + code:20", "Encolher janela um pouco para cima", hl.dsp.window.resize({ x = 0, y = -25, relative = true }))
o.bind("SUPER + SHIFT + ALT + code:21", "Expandir janela um pouco para baixo", hl.dsp.window.resize({ x = 0, y = 25, relative = true }))

o.bind("SUPER + CTRL + code:20", "Expandir janela bastante para a esquerda", hl.dsp.window.resize({ x = -300, y = 0, relative = true }))
o.bind("SUPER + CTRL + code:21", "Encolher janela bastante para a esquerda", hl.dsp.window.resize({ x = 300, y = 0, relative = true }))
o.bind("SUPER + CTRL + SHIFT + code:20", "Encolher janela bastante para cima", hl.dsp.window.resize({ x = 0, y = -300, relative = true }))
o.bind("SUPER + CTRL + SHIFT + code:21", "Expandir janela bastante para baixo", hl.dsp.window.resize({ x = 0, y = 300, relative = true }))

o.bind("SUPER + mouse_down", "Rolar área de trabalho para frente", hl.dsp.focus({ workspace = "e+1" }))
o.bind("SUPER + mouse_up", "Rolar área de trabalho para trás", hl.dsp.focus({ workspace = "e-1" }))

o.bind("SUPER + mouse:272", "Mover janela", hl.dsp.window.drag(), { mouse = true })
o.bind("SUPER + mouse:273", "Redimensionar janela", hl.dsp.window.resize(), { mouse = true })

o.bind("SUPER + G", "Agrupar/desagrupar janelas", hl.dsp.group.toggle())
o.bind("SUPER + ALT + G", "Tirar janela ativa do grupo", hl.dsp.window.move({ out_of_group = true }))

o.bind("SUPER + ALT + LEFT", "Mover janela para o grupo à esquerda", hl.dsp.window.move({ into_group = "l" }))
o.bind("SUPER + ALT + RIGHT", "Mover janela para o grupo à direita", hl.dsp.window.move({ into_group = "r" }))
o.bind("SUPER + ALT + UP", "Mover janela para o grupo acima", hl.dsp.window.move({ into_group = "u" }))
o.bind("SUPER + ALT + DOWN", "Mover janela para o grupo abaixo", hl.dsp.window.move({ into_group = "d" }))

o.bind("SUPER + ALT + TAB", "Próxima janela do grupo", hl.dsp.group.next())
o.bind("SUPER + ALT + SHIFT + TAB", "Janela anterior do grupo", hl.dsp.group.prev())

o.bind("SUPER + CTRL + LEFT", "Mover foco no grupo para a esquerda", hl.dsp.group.prev())
o.bind("SUPER + CTRL + RIGHT", "Mover foco no grupo para a direita", hl.dsp.group.next())

o.bind("SUPER + ALT + mouse_down", "Próxima janela do grupo", hl.dsp.group.next())
o.bind("SUPER + ALT + mouse_up", "Janela anterior do grupo", hl.dsp.group.prev())

for index = 1, 5 do
  o.bind("SUPER + ALT + code:" .. tostring(index + 9), "Ir para a janela do grupo " .. index, hl.dsp.group.active({ index = index }))
end

o.bind("SUPER + SLASH", "Aumentar escala do monitor", "simba-hyprland-monitor-scaling up")
o.bind("SUPER + ALT + SLASH", "Diminuir escala do monitor", "simba-hyprland-monitor-scaling down")
