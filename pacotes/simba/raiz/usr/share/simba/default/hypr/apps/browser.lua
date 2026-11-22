-- Browser tags and styling.
o.window("((google-)?[cC]hrom(e|ium)|[bB]rave-browser|[mM]icrosoft-edge|Vivaldi-stable|helium)", { tag = "+chromium-based-browser" })
o.window("([fF]irefox|zen|librewolf)", { tag = "+firefox-based-browser" })
o.window({ tag = "chromium-based-browser" }, { tag = "-default-opacity", tile = true, opacity = "1.0 0.985" })
o.window({ tag = "firefox-based-browser" }, { tag = "-default-opacity", opacity = "1.0 0.985" })

-- Video apps: remove chromium browser tag so they don't get opacity applied.
o.window("(^.+-youtube\\.com__.*$|^.+-app\\.zoom\\.us__wc_home.*$)", { tag = "-chromium-based-browser" })
o.window("(^.+-youtube\\.com__.*$|^.+-app\\.zoom\\.us__wc_home.*$)", { tag = "-default-opacity" })

-- Hide screen sharing notification windows.
o.window({ title = ".*is sharing.*" }, { workspace = "special silent" })

-- Login do Google da Conta (`conta entrar`): janela de app do navegador para o 127.0.0.1 do
-- rclone, flutuante e no centro — lado a lado ela abria escondida atrás das boas-vindas.
o.window("^(brave|chrome|chromium|google-chrome|microsoft-edge|vivaldi|helium)-127\\.0\\.0\\.1__.*$", { tag = "-chromium-based-browser" })
o.window("^(brave|chrome|chromium|google-chrome|microsoft-edge|vivaldi|helium)-127\\.0\\.0\\.1__.*$", { float = true, center = true, size = { 560, 690 } })
