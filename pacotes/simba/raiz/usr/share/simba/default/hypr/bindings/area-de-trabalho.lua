-- Ctrl + roda do mouse sobre a área de trabalho = ícones maiores/menores (como no Windows).
-- A área de trabalho não recebe o estado do Ctrl (o teclado fica com a janela em foco),
-- então o Hyprland avisa; ela só age se o cursor estiver sobre ela. non_consuming: a
-- rolagem continua chegando aos apps (Ctrl+roda no navegador segue dando zoom).
o.bind("CTRL + mouse_up", "Ícones da área de trabalho maiores",
  "qs -c configuracoes ipc call configuracoes areaRoda 1", { non_consuming = true })
o.bind("CTRL + mouse_down", "Ícones da área de trabalho menores",
  "qs -c configuracoes ipc call configuracoes areaRoda -1", { non_consuming = true })
