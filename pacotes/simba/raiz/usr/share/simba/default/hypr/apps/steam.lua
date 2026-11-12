o.window("steam", { float = true, idle_inhibit = "fullscreen" })
o.window({ class = "steam", title = "Steam" }, { center = true, size = { 1100, 700 } })
o.window("steam.*", { tag = "-default-opacity", opacity = "1 1" })
o.window({ class = "steam", title = "Friends List" }, { size = { 460, 800 } })

-- Notificações da Steam ("Fulano iniciou…"): a Steam põe no canto da tela sem saber da barra
-- de tarefas, e elas ficavam atrás dela. Sobe para cima da barra e não rouba o foco.
o.window({ class = "steam", title = "^notificationtoasts_.*" }, {
  move = { "(monitor_w-window_w-12)", "(monitor_h-window_h-60)" },
  no_focus = true,
  no_initial_focus = true,
})
