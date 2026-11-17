// Desenho em pixel art para os estilos de notificação do Simba (Canvas 2D).
// Tudo em "pixels da grade": cada um vira P×P pixels da tela (P = 2).
.pragma library

function rect(c, P, x, y, w, h, cor) {
  if (w <= 0 || h <= 0) return
  c.fillStyle = cor
  c.fillRect(x * P, y * P, w * P, h * P)
}

// Retângulo com cantos em degrau (r = tamanho do degrau)
function forma(c, P, x, y, w, h, r, cor) {
  for (var j = 0; j < h; j++) {
    var ins = 0
    if (j < r) ins = r - j
    else if (j >= h - r) ins = j - (h - r) + 1
    rect(c, P, x + ins, y + j, w - 2 * ins, 1, cor)
  }
}

function caixa(c, P, x, y, w, h, fundo, borda, r) {
  if (borda) {
    forma(c, P, x, y, w, h, r, borda)
    forma(c, P, x + 1, y + 1, w - 2, h - 2, Math.max(0, r - 1), fundo)
  } else {
    forma(c, P, x, y, w, h, r, fundo)
  }
}

// Xadrez de pixels (translucidez e sombra "pontilhada" dos jogos antigos)
function pontilhado(c, P, x, y, w, h, cor, fase) {
  c.fillStyle = cor
  for (var j = 0; j < h; j++)
    for (var i = 0; i < w; i++)
      if ((i + j + (fase || 0)) % 2 === 0) c.fillRect((x + i) * P, (y + j) * P, P, P)
}

// Pontilhado só dentro da forma em degrau
function pontilhadoForma(c, P, x, y, w, h, r, cor) {
  c.fillStyle = cor
  for (var j = 0; j < h; j++) {
    var ins = 0
    if (j < r) ins = r - j
    else if (j >= h - r) ins = j - (h - r) + 1
    for (var i = ins; i < w - ins; i++)
      if ((i + j) % 2 === 0) c.fillRect((x + i) * P, (y + j) * P, P, P)
  }
}

// sprite: lista de strings; '.' = vazio; letras → cores do mapa
function sprite(c, P, sp, x, y, mapa) {
  for (var j = 0; j < sp.length; j++)
    for (var i = 0; i < sp[j].length; i++) {
      var ch = sp[j][i]
      if (ch === "." || !mapa[ch]) continue
      c.fillStyle = mapa[ch]
      c.fillRect((x + i) * P, (y + j) * P, P, P)
    }
}

// O Simba: gatinho cinza (nunca laranja)
var GATO = [
  "k.........k",
  "kk.......kk",
  "kgk.....kgk",
  "kggkkkkkggk",
  "kgggggggggk",
  "kgwkgggkwgk",
  "kgkkgggkkgk",
  "kgggglggggk",
  "kggggkggggk",
  ".kgggggggk.",
  "..kkkkkkk.."]
var GATO_CORES = { k: "#111111", g: "#7a7a7a", l: "#b8b8b8", w: "#ffffff" }
var SETA = ["kkkkk", ".kkk.", "..k.."]
var CAUDA = ["...k", "..kw", ".kww", "kkkk"]
