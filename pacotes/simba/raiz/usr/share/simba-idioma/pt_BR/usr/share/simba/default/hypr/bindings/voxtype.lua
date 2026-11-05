if o.cmd_present("voxtype") then
  o.bind("SUPER + CTRL + X", "Ativar/desativar ditado", "voxtype record toggle")
  o.bind("F9", "Iniciar ditado (segurar para falar)", "voxtype record start")
  o.bind("F9", "Parar ditado (segurar para falar)", "voxtype record stop", { release = true })
end
