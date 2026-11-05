// Google Fotos: as miniaturas costumam ser divs com background-image, não <img>.
// Guarda a URL da imagem sob o último clique direito para o menu usar.
let lastImage = null;

function imageUrlOf(el) {
  if (el.tagName === "IMG" && el.src) return el.src;
  const bg = getComputedStyle(el).backgroundImage;
  const m = bg && bg.match(/url\("?(.*?)"?\)/);
  return m ? m[1] : null;
}

function findImage(target) {
  for (let el = target; el && el !== document.body; el = el.parentElement) {
    const url = imageUrlOf(el);
    if (url && /googleusercontent\.com|usercontent\.google\.com/.test(url)) return url;
    // o clique pode cair numa camada por cima da miniatura: procura dentro do bloco
    for (const child of el.querySelectorAll("img, [style*='background-image']")) {
      const u = imageUrlOf(child);
      if (u && /googleusercontent\.com|usercontent\.google\.com/.test(u)) return u;
    }
  }
  return null;
}

// O Google Fotos bloqueia o menu do navegador nas miniaturas: captura antes dele (na window)
// e impede que a página cancele o menu.
window.addEventListener("contextmenu", (e) => {
  lastImage = findImage(e.target);
  if (lastImage) e.stopImmediatePropagation();
}, true);

// As fotos novas (photos.fife.usercontent.google.com) só baixam com o login do navegador:
// baixa aqui mesmo, em tamanho máximo, e devolve em base64 para o host.
async function fetchFull(url) {
  const base = url.replace(/\?.*$/, "").replace(/=[^/=]*$/, "");
  const r = await fetch(base + "=s0", { credentials: "include" });
  if (!r.ok) throw new Error(r.status);
  const buf = new Uint8Array(await r.arrayBuffer());
  let bin = "";
  for (let i = 0; i < buf.length; i += 0x8000) bin += String.fromCharCode(...buf.subarray(i, i + 0x8000));
  return btoa(bin);
}

// Aviso no topo da página enquanto define o papel de parede
let toast = null, toastTimer = null;
function showToast(text, done) {
  if (!toast) {
    toast = document.createElement("div");
    toast.style.cssText = "position:fixed;top:16px;left:50%;transform:translateX(-50%);z-index:2147483647;" +
      "padding:10px 20px;border-radius:20px;background:#202124;color:#fff;font:500 14px system-ui,sans-serif;" +
      "box-shadow:0 2px 10px rgba(0,0,0,.4);transition:opacity .3s;pointer-events:none";
  }
  if (!toast.isConnected) document.documentElement.appendChild(toast);
  toast.textContent = text;
  toast.style.opacity = "1";
  clearTimeout(toastTimer);
  if (done) toastTimer = setTimeout(() => { toast.style.opacity = "0"; setTimeout(() => toast.remove(), 300); }, 2500);
}

chrome.runtime.onMessage.addListener((msg, _sender, reply) => {
  if (msg && msg.wallpaperResult !== undefined) {
    showToast(msg.wallpaperResult ? "✓ Papel de parede definido!" : "Não consegui definir o papel de parede", true);
    return;
  }
  if (msg !== "last-image") return;
  if (!lastImage) { reply(null); return; }
  showToast("Definindo foto de fundo…");
  fetchFull(lastImage)
    .then((data) => reply({ url: lastImage, data }))
    .catch(() => reply({ url: lastImage }));
  return true;
});
