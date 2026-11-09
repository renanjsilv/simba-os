-- Super sozinho abre o Iniciar, como no Windows: apertar e soltar a tecla Super
-- sem nenhuma outra tecla no meio. Super+qualquer tecla continua como sempre.
-- (Atalho "release" no SUPER_L não dispara no Hyprland 0.56; por isso o evento
-- de tecla.) Segurar o Super por mais de 0,9 s não abre — evita abrir o menu
-- depois de arrastar/redimensionar janela com Super+mouse, que não gera tecla.
local SUPER = { [133] = true, [134] = true }   -- Super esquerdo / direito (código físico)
local armado, vez = false, 0

hl.on("input.keyboard.key", function(codigo, _, apertada)
  if SUPER[codigo] then
    if apertada == 1 then
      armado = true
      vez = vez + 1
      local esta = vez
      hl.timer(function() if vez == esta then armado = false end end, { timeout = 900, type = "oneshot" })
    elseif armado then
      armado = false
      hl.dispatch(hl.dsp.exec_cmd("/usr/bin/configuracoes menu-iniciar"))
    end
  elseif apertada == 1 then
    armado = false
  end
end)
