function createMenus() {
  chrome.contextMenus.removeAll(() => {
  chrome.contextMenus.create({
    id: "set-wallpaper",
    title: "Definir como plano de fundo",
    contexts: ["image"],
  });
  // No Google Fotos as miniaturas não são <img>: mostra o item em qualquer ponto da página
  chrome.contextMenus.create({
    id: "set-wallpaper-photos",
    title: "Definir como plano de fundo",
    contexts: ["page", "link", "frame", "selection"],
    documentUrlPatterns: ["https://photos.google.com/*"],
  });
  });
}
// recria sempre: onInstalled nem sempre dispara em extensão descompactada
chrome.runtime.onInstalled.addListener(createMenus);
chrome.runtime.onStartup.addListener(createMenus);
createMenus();

function send(msg, tabId) {
  if (typeof msg === "string") msg = { url: msg };
  if (!(msg && (msg.url || msg.data))) return;
  chrome.runtime.sendNativeMessage("com.draco.wallpaper", msg, (res) => {
    // avisa a página (Google Fotos) para trocar o "Definindo…" pelo resultado
    if (tabId != null) chrome.tabs.sendMessage(tabId, { wallpaperResult: !!(res && res.ok) }, () => chrome.runtime.lastError);
  });
}

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "set-wallpaper" && info.srcUrl && !/photos\.google\.com/.test(info.pageUrl || "")) {
    send(info.srcUrl);
    return;
  }
  // Google Fotos: pergunta à página qual imagem estava sob o clique
  chrome.tabs.sendMessage(tab.id, "last-image", (url) => send(url || info.srcUrl, tab.id));
});
