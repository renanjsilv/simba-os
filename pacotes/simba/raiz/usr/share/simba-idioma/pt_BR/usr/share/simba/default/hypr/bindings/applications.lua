-- Essential application bindings.
o.bind("SUPER + RETURN", "Terminal", { simba = "terminal" })
o.bind("SUPER + SHIFT + RETURN", "Navegador", { simba = "browser" })
o.bind("SUPER + SHIFT + F", "Gerenciador de arquivos", { simba = "nautilus" })
o.bind("SUPER + ALT + SHIFT + F", "Gerenciador de arquivos (pasta atual)", { simba = "nautilus-cwd" })
o.bind("SUPER + SHIFT + B", "Navegador", { simba = "browser" })
o.bind("SUPER + SHIFT + ALT + B", "Navegador (privado)", { simba = "browser --private" })
o.bind("SUPER + SHIFT + N", "Editor", { simba = "editor" })

if o.preinstalled_bindings_enabled() then
  -- Bindings for preinstalled Simba applications, TUIs, and web apps.
  o.bind("SUPER + ALT + RETURN", "Tmux", { simba = "terminal-tmux" })
  o.bind("SUPER + CTRL + RETURN", "Herdr", { simba = "terminal-herdr" })
  o.bind("SUPER + SHIFT + M", "Música", { simba = "spotify" })
  o.bind("SUPER + SHIFT + ALT + M", "Música (terminal)", { tui = "cliamp", focus = true })
  o.bind("SUPER + SHIFT + D", "Docker", { tui = "simba-launch-docker-tui" })
  o.bind("SUPER + SHIFT + G", "Signal", { simba = "signal" })
  o.bind("SUPER + SHIFT + O", "Obsidian", { launch = "obsidian", focus = "^obsidian$" })
  o.bind("SUPER + SHIFT + W", "Omawrite", { launch = "omawrite" })
  o.bind("SUPER + SHIFT + SLASH", "Senhas", { simba = "1password" })

  o.bind("SUPER + SHIFT + A", "ChatGPT", { webapp = "https://chatgpt.com" })
  o.bind("SUPER + SHIFT + ALT + A", "Grok", { webapp = "https://grok.com" })
  o.bind("SUPER + SHIFT + C", "Calendário", { webapp = "https://app.hey.com/calendar/weeks/" })
  o.bind("SUPER + SHIFT + E", "E-mail", { webapp = "https://app.hey.com" })
  o.bind("SUPER + SHIFT + ALT + E", "Novo e-mail", { webapp = "https://app.hey.com/messages/new?display=standalone&new_window=true" })
  o.bind("SUPER + SHIFT + Y", "YouTube", { webapp = "https://youtube.com/" })
  o.bind("SUPER + SHIFT + ALT + G", "WhatsApp", { webapp = "https://web.whatsapp.com/", focus = true })
  o.bind( "SUPER + SHIFT + CTRL + G", "Google Mensagens", { webapp = "https://messages.google.com/web/conversations", focus = true })
  o.bind("SUPER + SHIFT + P", "Google Fotos", { webapp = "https://photos.google.com/", focus = true })
  o.bind("SUPER + SHIFT + S", "Google Maps", { webapp = "https://maps.google.com/", focus = true })
  o.bind("SUPER + SHIFT + X", "X", { webapp = "https://x.com/" })
  o.bind("SUPER + SHIFT + ALT + X", "Publicar no X", { webapp = "https://x.com/compose/post" })
end
