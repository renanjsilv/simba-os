-- Foco sem puxar o mouse: o Hyprland leva o cursor para o centro da janela ao
-- focar (e para outro monitor, se ela estiver lá). A barra de tarefas, a
-- prévia e os botões de janela chamam foco.janela(), que foca com
-- cursor.no_warps ligado só durante o foco — o cursor não se mexe.
-- Uso: hyprctl dispatch 'foco.janela("0xabc")'  ou  foco.janela("0xabc", "2")
--      (com área de trabalho: traz a janela para ela antes, ex. minimizada).
foco = foco or {}

function foco.janela(addr, ws)
  local sel = "address:" .. addr
  if not hl.get_window(sel) then return hl.dsp.no_op() end
  if ws and ws ~= "" then
    hl.dispatch(hl.dsp.window.move({ workspace = ws, follow = false, window = sel }))
  end
  local antes = hl.get_config("cursor.no_warps")
  hl.config({ cursor = { no_warps = true } })
  -- pcall: se o foco falhar, no_warps não pode ficar ligado para sempre
  local ok, erro = pcall(function()
    hl.dispatch(hl.dsp.focus({ window = sel }))
    hl.dispatch(hl.dsp.window.bring_to_top())
  end)
  hl.config({ cursor = { no_warps = antes and true or false } })
  if not ok then error(erro) end
  return hl.dsp.no_op()
end
