.pragma library
// Ícones monocromáticos (Nerd Font / Material Design) para a barra de tarefas.
// Pintados com a cor do tema, combinam com os glifos do resto da barra do
// Simba. Usado por tarefas.qml e por Configurações › Barra.

var G = {
  web: "\u{F059F}", chrome: "\u{F02AF}", firefox: "\u{F0239}", pasta: "\u{F024B}",
  terminal: "\u{F018D}", whatsapp: "\u{F05A3}", spotify: "\u{F04C7}", steam: "\u{F04D3}",
  discord: "\u{F066F}", youtube: "\u{F05C3}", caderno: "\u{F082E}", documento: "\u{F0219}",
  engrenagem: "\u{F0493}", vscode: "\u{F0A1E}", enviar: "\u{F048A}", imagem: "\u{F02E9}",
  imagens: "\u{F02F9}", mapa: "\u{F034D}", mensagem: "\u{F0361}", contatos: "\u{F06CB}",
  video: "\u{F0567}", twitter: "\u{F0544}", email: "\u{F01EE}", docker: "\u{F0868}",
  controle: "\u{F0297}", controle2: "\u{F02B4}", microfone: "\u{F036C}", disco: "\u{F0025}",
  dados: "\u{F01BC}", robo: "\u{F06A9}", monitor: "\u{F0379}", remoto: "\u{F08B9}",
  calculadora: "\u{F00EC}", editar: "\u{F0DC8}", grafico: "\u{F012A}", musica: "\u{F075A}",
  codigo: "\u{F0174}", pacote: "\u{F03D7}", app: "\u{F08C6}", fones: "\u{F02CB}",
  calendario: "\u{F00ED}", pdf: "\u{F0226}", conta: "\u{F0004}", cadeado: "\u{F033E}",
  baixar: "\u{F01DA}", camera: "\u{F0100}", lapis: "\u{F03EB}", github: "\u{F02A4}",
  google: "\u{F02AD}", noticias: "\u{F0395}"
}

// Primeira regra que casar com "id|classe|nome" (minúsculas) vence:
// específicas antes das genéricas.
var REGRAS = [
  [/org\.simba\.agent|claude|chatgpt|gemini|copilot|hermes|openclaw|\bai\b/, "robo"],
  [/org\.simba\.|foot|alacritty|ghostty|kitty|wezterm|konsole|terminal/, "terminal"],
  [/whatsapp/, "whatsapp"], [/spotify|spotifast/, "spotify"], [/steam/, "steam"],
  [/discord|vesktop|webcord/, "discord"], [/youtube/, "youtube"],
  [/google photos|photos\.google|google fotos/, "imagens"], [/google maps|maps\.google|\bmaps\b/, "mapa"],
  [/google messages|messages\.google|signal|element|slack/, "mensagem"], [/telegram/, "enviar"],
  [/contacts|contatos/, "contatos"], [/(^|\|)x(\||$)|twitter/, "twitter"],
  [/(^|\|)hey(\||$)|thunderbird|geary|evolution|e-?mail|gmail/, "email"],
  [/chromium|chrome/, "chrome"], [/firefox|librewolf|zen-browser|floorp/, "firefox"],
  [/brave|browser|navegador|epiphany|qutebrowser/, "web"],
  [/nautilus|thunar|dolphin|nemo|pcmanfm|files|arquivos/, "pasta"],
  [/obsidian|typora|notes|anota|joplin|logseq|basecamp/, "caderno"],
  [/libreoffice|writer|onlyoffice|wps/, "documento"],
  [/configuracoes|settings|preferences|control-center/, "engrenagem"],
  [/(^|\|)code(\||$)|vscode|vscodium|cursor|zed|neovim|nvim/, "vscode"],
  [/imv|loupe|eog|gthumb|shotwell|image viewer/, "imagem"],
  [/zoom|meet|mpv|vlc|celluloid|totem|video|kdenlive|obs/, "video"],
  [/docker|lazydocker|podman/, "docker"],
  [/hydra|heroic|lutris|bottles/, "controle"], [/duckstation|retroarch|pcsx|dolphin-emu|ppsspp|emulat/, "controle2"],
  [/transcrever|voxtype|draco|audacity|recorder/, "microfone"],
  [/gerar-iso|iso|brasero/, "disco"], [/disk usage|baobab|gnome-disks|gparted|discos/, "dados"],
  [/virt-manager|qemu|virtualbox|boxes|remmina/, "monitor"], [/anydesk|rustdesk|teamviewer/, "remoto"],
  [/calculator|calculadora|qalculate/, "calculadora"], [/text-editor|gedit|kate|mousepad|editor de texto/, "editar"],
  [/btop|htop|system monitor|monitor do sistema|resources|mission center/, "grafico"],
  [/pdf|evince|papers|okular|zathura/, "pdf"], [/1password|keepass|bitwarden|seahorse|senhas/, "cadeado"],
  [/localsend|transmission|qbittorrent|download/, "baixar"], [/camera|snapshot|cheese/, "camera"],
  [/pinta|gimp|krita|inkscape|drawing/, "lapis"], [/github/, "github"], [/calendar|calendário|agenda/, "calendario"],
  [/rhythmbox|lollypop|music|música|tidal|deezer/, "musica"], [/pavucontrol|wiremix|easyeffects|helvum/, "fones"]
]

var CATEGORIAS = [
  ["WebBrowser", "web"], ["FileManager", "pasta"], ["TerminalEmulator", "terminal"], ["Game", "controle2"],
  ["Music", "musica"], ["Audio", "fones"], ["Video", "video"], ["AudioVideo", "video"], ["Graphics", "imagem"],
  ["Office", "documento"], ["Development", "codigo"], ["Email", "email"], ["InstantMessaging", "mensagem"],
  ["Chat", "mensagem"], ["Network", "web"], ["Settings", "engrenagem"], ["System", "grafico"],
  ["Utility", "pacote"]
]

function chaveDe(id, classe, nome) {
  return [id, classe, nome].map(function(s) { return String(s || "").toLowerCase() }).join("|")
}

function glifo(id, classe, nome, categorias) {
  var chave = chaveDe(id, classe, nome)
  for (var i = 0; i < REGRAS.length; i++) if (REGRAS[i][0].test(chave)) return G[REGRAS[i][1]]
  var cats = categorias || []
  for (var c = 0; c < CATEGORIAS.length; c++) if (cats.indexOf(CATEGORIAS[c][0]) >= 0) return G[CATEGORIAS[c][1]]
  return G.app
}

// Apps sem glifo na Nerd Font: máscara PNG (branca, alfa = forma) em
// icones/, pintada com a cor do tema. Só vale para o navegador em si;
// web apps (brave-<site>-Default) continuam nas regras acima.
function mascara(id, classe, nome) {
  var chave = chaveDe(id, classe, nome)
  if (/(^|\|)brave(-browser)?(\||$)/.test(chave)) return "icones/brave.png"
  return ""
}
