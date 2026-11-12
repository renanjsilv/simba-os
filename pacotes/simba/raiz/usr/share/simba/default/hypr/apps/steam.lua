o.window("steam", { float = true, idle_inhibit = "fullscreen" })
o.window({ class = "steam", title = "Steam" }, { center = true, size = { 1100, 700 } })
o.window("steam.*", { tag = "-default-opacity", opacity = "1 1" })
o.window({ class = "steam", title = "Friends List" }, { size = { 460, 800 } })

-- Notificações da Steam ("Fulano iniciou…"): não roubam o foco. A posição (acima da barra de
-- tarefas) vale para todo app: janelas.lua › manter_na_area.
o.window({ class = "steam", title = "^notificationtoasts_.*" }, { no_focus = true, no_initial_focus = true })
