-- Janelas estilo Windows 11.
--
-- Toda janela de app é flutuante, como no Windows: assim existe uma única ordem
-- de empilhamento, a mesma para desenhar e para o clique. (Com janelas lado a
-- lado sobrepostas o Hyprland desenha numa ordem e entrega o clique na ordem
-- inversa — clicar na janela de cima focava uma escondida atrás dela.)
--
-- Estados (por janela):
--   "max"   ocupa a área útil do monitor (janela nova abre assim);
--   "zona"  encaixada numa fração da área útil (metade, terço, quarto...);
--   nil     solta/restaurada, onde o usuário deixar.
-- Encaixar põe a janela numa zona e preenche as outras zonas do mesmo arranjo com
-- os apps usados/abertos por último, como o Windows 11 — inclusive minimizados.
-- A janela em foco vem para a frente de todas.
--
-- Usado pelos atalhos Super+setas (hypr/bindings.lua) e pelos botões de janela
-- (~/.config/quickshell/botoes-janela), que chamam pelo hyprctl dispatch:
--   janelas.encaixar("<endereço>", "<x y l a;x y l a;...>", <n>)   frações da área útil
--   janelas.lado("<endereço>"|nil, "esquerda"|"direita")
--   janelas.maximizar("<endereço>")      volta a ocupar a área toda
--   janelas.alternar("<endereço>")       maximizada/encaixada ⇄ solta
--   janelas.minimizar("<endereço>")
--   janelas.pedido("<endereço>", "minimizar"|"maximizar"|"restaurar"|"alternar"|"fechar"|"soltar")
-- Cada função devolve um dispatcher, então serve direto no `hyprctl dispatch`.
--
-- janelas.pedido é a porta de entrada do plugin janelas-nativo (~/.local/share/janelas-nativo):
-- botões da barra de título que o Hyprland desenha e os botões/atalhos do próprio app
-- (xdg_toplevel set_minimized/set_maximized, X11 WM_CHANGE_STATE). O estado de cada janela
-- volta para o plugin (hl.plugin.janelas.estado), que avisa o app se está maximizado.

janelas = janelas or {}

local LAYOUT = "lua:janelas"
local MINIMIZADAS = "special:minimizadas"
-- Marca das janelas de app gerenciadas aqui (as outras flutuantes são diálogos,
-- janelas com regra própria etc.). Lida também pelos botões de janela.
local APP = "janelas-app"
-- Maximizadas ficam sem borda (regra em looknfeel.lua pela etiqueta).
local MAX = "janelas-max"

-- endereço → { modo = "max" } | { modo = "zona", x, y, w, h (frações) }
local estado = {}
-- endereço → {x, y, w, h} px: onde a janela estava solta (volta ao restaurar)
local solta = {}
-- endereço → {x, y, w, h} px: onde foi colocada por último (detecta se o usuário
-- arrastou/redimensionou — aí ela passa a ser solta)
local colocada = {}

-- ── estado em arquivo ───────────────────────────────────────────────────────
-- O reload do Hyprland recria o Lua: o estado fica num arquivo da sessão.
local ARQUIVO = os.getenv("JANELAS_ESTADO") or ((os.getenv("XDG_RUNTIME_DIR") or "/tmp") .. "/hypr-janelas.estado")

-- Plugin janelas-nativo (se carregado): sabe o estado para desenhar ☐/❐ e avisar o app.
local informados = {}
local function plugin() return hl.plugin and hl.plugin.janelas end

local function sincronizar()
  local P = plugin()
  if not P or not P.estado then return end
  local vistos = {}
  for a, e in pairs(estado) do
    vistos[a] = true
    if informados[a] ~= e.modo then pcall(P.estado, a, e.modo); informados[a] = e.modo end
  end
  for a, m in pairs(informados) do
    if not vistos[a] then
      if hl.get_window("address:" .. a) then pcall(P.estado, a, "solta") end
      informados[a] = nil
    end
  end
end

local function gravar()
  sincronizar()
  local f = io.open(ARQUIVO, "w")
  if not f then return end
  local function linha(nome, a, g) f:write(string.format("%s %s %s %s %s %s\n", nome, a, g.x, g.y, g.w, g.h)) end
  for a, e in pairs(estado) do
    if e.modo == "max" then f:write("max " .. a .. "\n") else linha("zona", a, e) end
  end
  for a, g in pairs(solta) do linha("solta", a, g) end
  for a, g in pairs(colocada) do linha("colocada", a, g) end
  f:close()
end

local function ler()
  local f = io.open(ARQUIVO, "r")
  if not f then return end
  for l in f:lines() do
    local nome, a, resto = l:match("^(%S+) (%S+)%s*(.*)$")
    if nome and hl.get_window("address:" .. a) then
      local x, y, w, h = resto:match("^(%S+) (%S+) (%S+) (%S+)$")
      local g = x and { x = tonumber(x), y = tonumber(y), w = tonumber(w), h = tonumber(h) }
      if nome == "max" then estado[a] = { modo = "max" }
      elseif nome == "zona" and g then g.modo = "zona"; estado[a] = g
      elseif nome == "solta" and g then solta[a] = g
      elseif nome == "colocada" and g then colocada[a] = g end
    end
  end
  f:close()
end

-- ── geometria ───────────────────────────────────────────────────────────────
local function sel(w) return "address:" .. w.address end

local function janela(addr)
  if addr and addr ~= "" then return hl.get_window("address:" .. addr) end
  return hl.get_active_window()
end

local function no_layout(w)
  return w and w.workspace and not w.workspace.special and w.workspace.tiled_layout == LAYOUT
end

local function tem_tag(w, tag)
  for _, t in ipairs(w.tags or {}) do
    if t == tag or t == tag .. "*" then return true end
  end
  return false
end

local function geometria(w)
  local a, t = w.at or {}, w.size or {}
  return { x = a.x or a[1], y = a.y or a[2], w = t.x or t[1], h = t.y or t[2] }
end

local function lados(v)
  if type(v) == "table" then return v.left or 0, v.top or 0, v.right or 0, v.bottom or 0 end
  v = tonumber(v) or 0
  return v, v, v, v
end

-- Área útil do monitor (sem barras e sem gaps_out), em pixels lógicos.
local function area_de(m)
  local rl, rt, rr, rb = lados(m.reserved)
  local gl, gt, gr, gb = lados(hl.get_config("general.gaps_out"))
  return {
    x = m.x + rl + gl, y = m.y + rt + gt,
    w = math.floor(m.width / m.scale + 0.5) - rl - rr - gl - gr,
    h = math.floor(m.height / m.scale + 0.5) - rt - rb - gt - gb,
  }
end

-- Caixa da janela (sem a borda) para a zona z da área — igual ao que o layout
-- lado a lado fazia: borda em volta e gaps_in só nos lados internos.
local function caixa(area, z, sem_borda)
  local x, y, x2, y2 = area.x, area.y, area.x + area.w, area.y + area.h
  if z then
    x = math.floor(area.x + area.w * z.x + 0.5)
    y = math.floor(area.y + area.h * z.y + 0.5)
    x2 = math.floor(area.x + area.w * (z.x + z.w) + 0.5)
    y2 = math.floor(area.y + area.h * (z.y + z.h) + 0.5)
  end
  local b = sem_borda and 0 or (tonumber(hl.get_config("general.border_size")) or 0)
  local il, it, ir, ib = lados(hl.get_config("general.gaps_in"))
  if x <= area.x + 1 then il = 0 end
  if y <= area.y + 1 then it = 0 end
  if x2 >= area.x + area.w - 1 then ir = 0 end
  if y2 >= area.y + area.h - 1 then ib = 0 end
  return { x = x + b + il, y = y + b + it, w = x2 - x - 2 * b - il - ir, h = y2 - y - 2 * b - it - ib }
end

local function perto(a, b)
  return a and b and math.abs(a.x - b.x) <= 3 and math.abs(a.y - b.y) <= 3
     and math.abs(a.w - b.w) <= 3 and math.abs(a.h - b.h) <= 3
end

-- Altura da barra de título que o Hyprland desenha em cima da janela (plugin janelas-nativo);
-- 0 se o app desenha a própria ou o plugin não está carregado.
local function barra(w)
  local P = plugin()
  if not P or not P.barra then return 0 end
  local ok, h = pcall(P.barra, w.address)
  return ok and tonumber(h) or 0
end

-- Etiqueta MAX = sem borda: só enquanto a janela está maximizada.
local function marcar_max(w)
  local e = estado[w.address]
  local quer = e ~= nil and e.modo == "max"
  if quer ~= tem_tag(w, MAX) then
    hl.dispatch(hl.dsp.window.tag({ tag = (quer and "+" or "-") .. MAX, window = sel(w) }))
  end
end

-- g = caixa externa (barra de título incluída) ou, com `interna`, a caixa do conteúdo do
-- app (o que o Hyprland informa em at/size; a barra fica acima dela).
local function colocar(w, g, interna)
  if not w.floating then hl.dispatch(hl.dsp.window.float({ action = "set", window = sel(w) })) end
  if w.fullscreen > 0 then hl.dispatch(hl.dsp.window.fullscreen_state({ internal = 0, client = 0, window = sel(w) })) end
  if not tem_tag(w, APP) then hl.dispatch(hl.dsp.window.tag({ tag = "+" .. APP, window = sel(w) })) end
  marcar_max(w)
  if not interna then
    local hb = barra(w)
    if hb > 0 then g = { x = g.x, y = g.y + hb, w = g.w, h = g.h - hb } end
  end
  hl.dispatch(hl.dsp.window.resize({ x = g.w, y = g.h, window = sel(w) }))
  hl.dispatch(hl.dsp.window.move({ x = g.x, y = g.y, window = sel(w) }))
  colocada[w.address] = g
end

-- Põe a janela onde o estado dela manda, no monitor em que está agora.
local function posicionar(w)
  local e = estado[w.address]
  if not e or not w.monitor then return end
  colocar(w, caixa(area_de(w.monitor), e.modo == "zona" and e or nil, e.modo == "max"))
end

-- Ocupa (quase) a área útil inteira: é uma janela maximizada, mesmo que tenha aberto
-- flutuante com o tamanho que lembrava (Brave, Electron...).
local function cobre_area(w)
  local a = w.monitor and area_de(w.monitor)
  if not a then return false end
  local g, hb = geometria(w), barra(w)
  return g.w >= a.w * 0.95 and g.h + hb >= a.h * 0.95
end

-- Guarda a posição de solta antes de maximizar/encaixar (para restaurar depois).
local function lembrar_solta(w)
  if not estado[w.address] and w.floating and w.fullscreen == 0 then solta[w.address] = geometria(w) end
end

-- Candidatas a preencher as outras zonas: apps da mesma área de trabalho e os
-- minimizados, do usado/aberto mais recentemente para o mais antigo.
local function vizinhas(w)
  local lista = {}
  local function juntar(ws)
    for _, v in ipairs(hl.get_workspace_windows(ws) or {}) do
      if v.address ~= w.address and v.mapped and v.fullscreen == 0 and tem_tag(v, APP) then
        table.insert(lista, v)
      end
    end
  end
  juntar(w.workspace.name)
  juntar(MINIMIZADAS)
  table.sort(lista, function(a, b) return a.focus_history_id < b.focus_history_id end)
  return lista
end

local function zonas_de(texto)
  local zonas = {}
  for parte in tostring(texto):gmatch("[^;]+") do
    local x, y, l, a = parte:match("^%s*(%S+)%s+(%S+)%s+(%S+)%s+(%S+)%s*$")
    x, y, l, a = tonumber(x), tonumber(y), tonumber(l), tonumber(a)
    if x and y and l and a then table.insert(zonas, { x = x, y = y, w = l, h = a }) end
  end
  return zonas
end

-- ── ações ───────────────────────────────────────────────────────────────────
function janelas.encaixar(addr, texto, n)
  local w = janela(addr)
  local zonas = zonas_de(texto)
  n = tonumber(n) or 1
  if not no_layout(w) or not zonas[n] then return hl.dsp.no_op() end
  local outras = vizinhas(w)
  lembrar_solta(w)
  local z = zonas[n]; z.modo = "zona"
  estado[w.address] = z
  posicionar(w)
  local extras, i = {}, 1
  for k, zk in ipairs(zonas) do
    if k ~= n and outras[i] then
      local v = outras[i]
      if v.workspace.name ~= w.workspace.name then
        hl.dispatch(hl.dsp.window.move({ workspace = w.workspace.name, follow = false, window = sel(v) }))
        v = hl.get_window(sel(v)) or v
      end
      lembrar_solta(v)
      zk.modo = "zona"
      estado[v.address] = zk
      posicionar(v)
      table.insert(extras, v)
      i = i + 1
    end
  end
  -- Traz para a frente as encaixadas e termina com o foco na principal.
  for k = #extras, 1, -1 do hl.dispatch(hl.dsp.window.alter_zorder({ mode = "top", window = sel(extras[k]) })) end
  hl.dispatch(hl.dsp.focus({ window = sel(w) }))
  hl.dispatch(hl.dsp.window.alter_zorder({ mode = "top", window = sel(w) }))
  gravar()
  return hl.dsp.no_op()
end

local METADES = "0 0 0.5 1;0.5 0 0.5 1"

-- Monitor vizinho na direção (o mais próximo cujo lado encosta neste).
local function monitor_ao_lado(m, lado)
  local melhor, dist = nil, math.huge
  local mx2 = m.x + m.width / m.scale
  for _, o in ipairs(hl.get_monitors() or {}) do
    if o.name ~= m.name and not o.is_mirror then
      local ox2 = o.x + o.width / o.scale
      local d = lado == "direita" and (o.x - mx2) or (m.x - ox2)
      if d >= -1 and d < dist then melhor, dist = o, d end
    end
  end
  return melhor
end

function janelas.lado(addr, lado)
  local w = janela(addr)
  -- Já encaixada nesse lado e há outro monitor para lá: vai para ele, encaixada
  -- no lado de entrada (Super+→ duas vezes leva o app para a tela da direita).
  local e = w and estado[w.address]
  if e and e.modo == "zona" and e.w < 0.999 and w.monitor
      and ((lado == "esquerda" and e.x <= 0.001) or (lado == "direita" and e.x + e.w >= 0.999)) then
    local m = monitor_ao_lado(w.monitor, lado)
    if m and m.active_workspace then
      local z = zonas_de(METADES)[lado == "esquerda" and 2 or 1]
      z.modo = "zona"
      estado[w.address] = z
      hl.dispatch(hl.dsp.window.move({ workspace = m.active_workspace.name, follow = false, window = sel(w) }))
      w = hl.get_window(sel(w)) or w
      posicionar(w)
      hl.dispatch(hl.dsp.focus({ window = sel(w) }))
      hl.dispatch(hl.dsp.window.alter_zorder({ mode = "top", window = sel(w) }))
      gravar()
      return hl.dsp.no_op()
    end
  end
  return janelas.encaixar(addr, METADES, lado == "esquerda" and 1 or 2)
end

function janelas.maximizar(addr)
  local w = janela(addr)
  if not no_layout(w) then return hl.dsp.no_op() end
  lembrar_solta(w)
  estado[w.address] = { modo = "max" }
  posicionar(w)
  hl.dispatch(hl.dsp.focus({ window = sel(w) }))
  hl.dispatch(hl.dsp.window.alter_zorder({ mode = "top", window = sel(w) }))
  gravar()
  return hl.dsp.no_op()
end

-- Botão maximizar: maximizada/encaixada → solta (onde estava antes, ou 70% da
-- tela no centro); solta → maximizada.
function janelas.alternar(addr)
  local w = janela(addr)
  if not w then return hl.dsp.no_op() end
  -- Fora do layout janelas (área com outro layout): maximizar do Hyprland.
  if not no_layout(w) then return hl.dsp.window.fullscreen({ mode = "maximized", window = sel(w) }) end
  -- solta do tamanho da tela (maximizar não mudaria nada): restaura para 70% no centro
  if not estado[w.address] and w.fullscreen == 0 and w.floating and not cobre_area(w) then return janelas.maximizar(addr) end
  estado[w.address] = nil
  local a = w.monitor and area_de(w.monitor)
  local g = solta[w.address]
  local hb = barra(w)
  local interna = true
  -- sem lugar de solta, fora da área ou do tamanho da tela toda (restaurar não mudaria
  -- nada): 70% da área no centro, como o Windows faz
  local cheia = g and g.w >= a.w * 0.95 and g.h + hb >= a.h * 0.95
  if a and (not g or cheia or g.x < a.x or g.y - hb < a.y or g.x + g.w > a.x + a.w or g.y + g.h > a.y + a.h) then
    local lw, la = math.floor(a.w * 0.7), math.floor(a.h * 0.7)
    g = { x = a.x + math.floor((a.w - lw) / 2), y = a.y + math.floor((a.h - la) / 2), w = lw, h = la }
    interna = false
  end
  if g then colocar(w, g, interna) end
  colocada[w.address] = nil
  hl.dispatch(hl.dsp.focus({ window = sel(w) }))
  gravar()
  return hl.dsp.no_op()
end

function janelas.minimizar(addr)
  local w = janela(addr)
  if not w then return hl.dsp.no_op() end
  return hl.dsp.window.move({ workspace = MINIMIZADAS, follow = false, window = sel(w) })
end

-- Restaurar (botão restaurar, Super+↓ numa maximizada, app pediu unset_maximized).
function janelas.restaurar(addr)
  local w = janela(addr)
  if not w then return hl.dsp.no_op() end
  if not no_layout(w) then return hl.dsp.window.fullscreen_state({ internal = 0, client = 0, window = sel(w) }) end
  if not estado[w.address] then return hl.dsp.no_op() end
  return janelas.alternar(w.address)
end

-- Super+↓ como no Windows: maximizada/encaixada → restaura; solta → minimiza.
function janelas.baixo(addr)
  local w = janela(addr)
  if not w then return hl.dsp.no_op() end
  if no_layout(w) and estado[w.address] then return janelas.restaurar(w.address) end
  return janelas.minimizar(w.address)
end

-- Arrastar a barra de título de uma maximizada/encaixada: volta ao tamanho de solta com o
-- cursor no mesmo ponto relativo da barra (fx = fração da largura, fy = px do topo da barra),
-- e o plugin começa o arrasto. Como no Windows 11.
function janelas.soltar(addr, fx, fy)
  local w = janela(addr)
  if not no_layout(w) or not estado[w.address] then return hl.dsp.no_op() end
  local a = w.monitor and area_de(w.monitor)
  if not a then return hl.dsp.no_op() end
  local g = solta[w.address]
  local lw, la = math.floor(a.w * 0.7), math.floor(a.h * 0.7)
  if g then lw, la = math.min(g.w, a.w), math.min(g.h, a.h) end
  local c = hl.get_cursor_pos and hl.get_cursor_pos() or nil
  local cx, cy = c and (c.x or c[1]), c and (c.y or c[2])
  if not cx then local gw = geometria(w); cx, cy = gw.x + gw.w / 2, gw.y end
  fx, fy = tonumber(fx) or 0.5, tonumber(fy) or 16
  local hb = barra(w)
  local x = math.floor(cx - lw * fx + 0.5)
  local y = math.floor(cy - fy + hb + 0.5)
  x = math.max(a.x, math.min(x, a.x + a.w - lw))
  y = math.max(a.y + hb, math.min(y, a.y + a.h - la))
  estado[w.address] = nil
  colocar(w, { x = x, y = y, w = lw, h = la }, true)
  colocada[w.address] = nil
  gravar()
  return hl.dsp.no_op()
end

-- O plugin janelas-nativo pôs ou tirou a barra de título de uma janela: maximizada ou
-- encaixada refaz a caixa; solta com a barra fora da área útil desce (e encolhe) para caber.
function janelas.barra_mudou(addr)
  local ok, erro = pcall(function()
    local w = janela(addr)
    if not w or not no_layout(w) or w.fullscreen > 0 then return end
    if not estado[w.address] and cobre_area(w) then estado[w.address] = { modo = "max" } end
    if estado[w.address] then posicionar(w); gravar(); return end
    local a = w.monitor and area_de(w.monitor)
    if not a then return end
    local g, hb = geometria(w), barra(w)
    local b = tonumber(hl.get_config("general.border_size")) or 0
    if g.y - hb - b >= a.y then return end
    local y = a.y + hb + b
    local h = math.min(g.h, a.y + a.h - y - b)
    colocar(w, { x = g.x, y = y, w = g.w, h = h }, true)
    colocada[w.address] = nil
    gravar()
  end)
  if not ok then
    local log = io.open(ARQUIVO .. ".erro", "a")
    if log then log:write(os.date("%H:%M:%S ") .. tostring(erro) .. "\n"); log:close() end
  end
  return hl.dsp.no_op()
end

-- Diagnóstico: hyprctl eval 'error(janelas.estado_de("0x..."))'
function janelas.estado_de(addr)
  local e = estado[addr]
  return (e and e.modo or "solta") .. (solta[addr] and " (lembra solta)" or "")
end

-- Plugin (re)carregado: manda o estado de todas as janelas de novo.
function janelas.sincronizar()
  informados = {}
  sincronizar()
  return hl.dsp.no_op()
end

-- Porta de entrada do plugin janelas-nativo (barra de título e pedidos do próprio app).
-- Roda com cursor.no_warps ligado: clicar num botão não pode puxar o mouse para o meio
-- de outra janela (o foco do Hyprland leva o cursor junto).
local pedido_real
function janelas.pedido(addr, acao, extra)
  local antes = hl.get_config("cursor.no_warps")
  hl.config({ cursor = { no_warps = true } })
  local ok, erro = pcall(function() hl.dispatch(pedido_real(addr, acao, extra)) end)
  hl.config({ cursor = { no_warps = antes and true or false } })
  if not ok then error(erro) end
  return hl.dsp.no_op()
end

pedido_real = function(addr, acao, extra)
  local w = janela(addr)
  if not w then return hl.dsp.no_op() end
  if acao == "minimizar" then return janelas.minimizar(w.address) end
  if acao == "fechar" then return hl.dsp.window.close({ window = sel(w) }) end
  if acao == "alternar" then return janelas.alternar(w.address) end
  if acao == "restaurar" then return janelas.restaurar(w.address) end
  if acao == "maximizar" then
    if no_layout(w) then return janelas.maximizar(w.address) end
    return hl.dsp.window.fullscreen_state({ internal = 1, client = 1, window = sel(w) })
  end
  if acao == "soltar" then
    local fx, fy = tostring(extra or ""):match("^([%d.]+),([%d.]+)$")
    return janelas.soltar(w.address, fx, fy)
  end
  return hl.dsp.no_op()
end

-- ── eventos ─────────────────────────────────────────────────────────────────
local ocupado = false
local function protegido(f)
  if ocupado then return end
  ocupado = true
  local ok, erro = pcall(f)
  ocupado = false
  if not ok then
    local log = io.open(ARQUIVO .. ".erro", "a")
    if log then log:write(os.date("%H:%M:%S ") .. tostring(erro) .. "\n"); log:close() end
  end
end

-- Janela que ia ficar lado a lado: vira flutuante maximizada (ou volta ao estado
-- que tinha, se o arquivo lembrar). Se o usuário arrastou/redimensionou uma
-- maximizada/encaixada, ela passa a ser solta onde ele deixou.
-- Geometria diferente da colocada E ainda no mesmo monitor = o usuário arrastou ou
-- redimensionou. (Mudar de monitor também muda a geometria, mas não é arrasto.)
local function arrastada(w)
  local c = colocada[w.address]
  if not c or perto(geometria(w), c) or not w.monitor then return false end
  local m = w.monitor
  local cx, cy = c.x + c.w / 2, c.y + c.h / 2
  return cx >= m.x and cx < m.x + m.width / m.scale and cy >= m.y and cy < m.y + m.height / m.scale
end

local function ajustar(w)
  if not no_layout(w) or w.fullscreen > 0 or w.pinned then return end
  local e = estado[w.address]
  if not w.floating then
    if not e then estado[w.address] = { modo = "max" } end
    posicionar(w)
    gravar()
  elseif e and arrastada(w) then
    estado[w.address] = nil
    colocada[w.address] = nil
    marcar_max(w)
    gravar()
  end
end

local function ajustar_todas()
  for _, w in ipairs(hl.get_windows() or {}) do
    if w.mapped and no_layout(w) then
      if estado[w.address] and w.floating and not arrastada(w) then
        posicionar(w)  -- área útil mudou (monitor, barra): acompanha
      else
        ajustar(w)
      end
    end
  end
  gravar()
end

hl.on("window.open", function(w)
  if not w or not w.address then return end
  estado[w.address], solta[w.address], colocada[w.address] = nil, nil, nil
  informados[w.address] = nil
  protegido(function()
    w = hl.get_window(sel(w))
    if not w then return end
    if not w.floating or w.class == "com.simba.Agentes" then
      ajustar(w)
    elseif no_layout(w) and w.fullscreen == 0 and not w.pinned and cobre_area(w) then
      -- abriu flutuante do tamanho da tela: vira maximizada de verdade (botão restaurar
      -- funciona e a caixa respeita a barra de título)
      estado[w.address] = { modo = "max" }
      posicionar(w)
      gravar()
    end
  end)
end)

hl.on("window.close", function(w)
  if not w or not w.address then return end
  estado[w.address], solta[w.address], colocada[w.address] = nil, nil, nil
  gravar()
end)

-- Foco no clique (input.follow_mouse ≠ 1): a janela ativada vem para a frente.
hl.on("window.active", function(w)
  if not w or not w.address then return end
  protegido(function()
    w = hl.get_window(sel(w))
    if not w then return end
    ajustar(w)
    if w.floating and hl.get_config("input.follow_mouse") ~= 1 then
      hl.dispatch(hl.dsp.window.alter_zorder({ mode = "top", window = sel(w) }))
    end
  end)
end)

-- Voltou de minimizada ou mudou de monitor: maximizada/encaixada ocupa a área
-- útil de onde está agora (arrastada pelo usuário para outro lugar: fica solta).
hl.on("window.move_to_workspace", function(w)
  if not w or not w.address then return end
  local addr = w.address
  -- O evento chega antes de o Hyprland atualizar monitor/posição: ajusta logo depois.
  hl.timer(function()
    protegido(function()
      local v = hl.get_window("address:" .. addr)
      if not v or not no_layout(v) or not estado[addr] or not v.monitor then return end
      -- Mesmo monitor e geometria diferente: o usuário arrastou → fica solta.
      if arrastada(v) then estado[addr] = nil; colocada[addr] = nil; marcar_max(v); gravar(); return end
      posicionar(v)
      gravar()
    end)
  end, { timeout = 200, type = "oneshot" })
end)

-- A barra mudou de tamanho (alça / barra-tarefas altura): a área útil mudou,
-- maximizadas e encaixadas acompanham.
function janelas.reajustar() protegido(ajustar_todas) end

for _, ev in ipairs({ "monitor.added", "monitor.removed", "monitor.layout_changed" }) do
  hl.on(ev, function() protegido(ajustar_todas) end)
end

-- Janelas que ainda estiverem lado a lado (instantes antes de virarem
-- flutuantes): área útil inteira.
hl.layout.register("janelas", {
  recalculate = function(ctx)
    for _, t in ipairs(ctx.targets) do
      t:place({ x = ctx.area.x, y = ctx.area.y, w = ctx.area.w, h = ctx.area.h })
    end
  end,
  layout_msg = function(_, msg)
    if msg == "atualizar" then return true end
    return "janelas: mensagem desconhecida: " .. msg
  end,
})

ler()
-- Recarregou a configuração com janelas abertas (ou veio do modelo antigo, lado
-- a lado): converte as que estiverem no layout — um pouco depois do reload, que
-- ainda informa o layout anterior nas áreas de trabalho.
hl.on("config.reloaded", function()
  hl.timer(function() protegido(ajustar_todas) end, { timeout = 300, type = "oneshot" })
end)
