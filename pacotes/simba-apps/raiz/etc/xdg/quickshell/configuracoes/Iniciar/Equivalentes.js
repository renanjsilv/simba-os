.pragma library
// Programas famosos do Windows → o que faz o mesmo papel no Simba.
//
// Quem procura "word" no Menu Iniciar vê o WordCraft como primeiro resultado, com
// "Alternativa para Microsoft Word". Cada linha: nome do programa do Windows, os termos que
// as pessoas digitam e os apps (ids de .desktop) em ordem de preferência — vale o primeiro
// que estiver instalado, então a mesma tabela serve numa máquina com LibreOffice ou GIMP.
// Termos sem acento e em minúsculas (a busca normaliza o que é digitado).

var TABELA = [
  ["Microsoft Word", ["word", "microsoft word", "ms word", "winword", "office word", "documento word"],
   ["ai.storyteller.wordcraft", "libreoffice-writer", "org.onlyoffice.desktopeditors"]],
  ["Microsoft Excel", ["excel", "microsoft excel", "ms excel", "planilha excel"],
   ["ai.storyteller.gridcraft", "libreoffice-calc", "org.onlyoffice.desktopeditors"]],
  ["Microsoft PowerPoint", ["powerpoint", "power point", "ppt", "microsoft powerpoint", "ms powerpoint"],
   ["ai.storyteller.deckcraft", "libreoffice-impress", "org.onlyoffice.desktopeditors"]],
  ["Microsoft Office", ["office", "microsoft office", "office 365", "microsoft 365", "pacote office"],
   ["ai.storyteller.wordcraft", "libreoffice-startcenter", "org.onlyoffice.desktopeditors"]],
  ["Adobe Acrobat", ["acrobat", "adobe acrobat", "acrobat reader", "adobe reader", "adobe pdf", "foxit", "leitor de pdf", "pdf reader"],
   ["ai.storyteller.pdfcraft", "org.gnome.Papers", "org.gnome.Evince", "okularApplication_pdf"]],
  ["Paint", ["paint", "mspaint", "ms paint", "paint 3d"],
   ["com.github.PintaProject.Pinta", "org.kde.kolourpaint", "org.gimp.GIMP"]],
  ["Adobe Photoshop", ["photoshop", "adobe photoshop", "photoshop express", "lightroom"],
   ["org.gimp.GIMP", "org.kde.krita", "com.github.PintaProject.Pinta"]],
  ["Bloco de Notas", ["bloco de notas", "notepad", "notepad++", "wordpad"],
   ["org.gnome.TextEditor", "org.gnome.gedit", "org.kde.kate"]],
  ["Microsoft OneNote", ["onenote", "one note", "microsoft onenote"],
   ["com.github.xournalpp.xournalpp", "obsidian"]],
  ["Evernote", ["evernote", "notion"], ["obsidian"]],
  ["Windows Media Player", ["windows media player", "media player", "wmp", "vlc", "filmes e tv", "player de video"],
   ["io.github.celluloid_player.Celluloid", "vlc", "mpv"]],
  ["Adobe Premiere", ["premiere", "adobe premiere", "premiere pro", "vegas", "sony vegas", "capcut", "clipchamp",
                      "filmora", "movie maker", "editor de video", "after effects"],
   ["org.kde.kdenlive", "org.shotcut.Shotcut", "org.openshot.OpenShot"]],
  ["Camtasia", ["camtasia", "bandicam", "xbox game bar", "game bar", "gravador de tela", "screen recorder", "gravar tela"],
   ["com.obsproject.Studio"]],
  ["Explorador de Arquivos", ["explorador de arquivos", "windows explorer", "explorer", "meu computador", "este computador",
                              "my computer", "this pc"],
   ["com.renan.Explorador", "org.gnome.Nautilus"]],
  ["Gerenciador de Tarefas", ["task manager", "taskmgr", "ctrl alt del"],
   ["com.renan.GerenciadorTarefas"]],
  ["Calculadora do Windows", ["calc", "calculator", "calculadora do windows"],
   ["com.simba.Calculadora", "org.gnome.Calculator", "org.kde.kcalc"]],
  ["Painel de Controle", ["painel de controle", "control panel", "configuracoes do windows", "windows settings"],
   ["com.renan.Configuracoes"]],
  ["Microsoft Store", ["microsoft store", "windows store", "loja do windows", "play store", "loja de aplicativos"],
   ["simba-loja", "io.github.kolunmi.Bazaar"]],
  ["Google Chrome", ["chrome", "google chrome", "edge", "microsoft edge", "internet explorer", "navegador de internet"],
   ["brave-browser", "chromium", "firefox"]],
  ["TeamViewer", ["teamviewer", "team viewer", "acesso remoto"], ["anydesk"]],
  ["Área de Trabalho Remota", ["area de trabalho remota", "remote desktop", "mstsc", "rdp", "conexao remota"],
   ["vncviewer", "org.remmina.Remmina", "anydesk"]],
  ["WinRAR", ["winrar", "win rar", "7zip", "7-zip", "winzip", "descompactar", "extrair zip", "extrair rar"],
   ["org.gnome.FileRoller", "org.kde.ark"]],
  ["VirtualBox", ["hyper-v", "hyperv", "virtualbox", "vmware", "maquina virtual"],
   ["virt-manager", "virtualbox"]],
  ["Gerenciamento de Disco", ["gerenciamento de disco", "disk management", "diskmgmt", "particionar", "formatar pendrive"],
   ["org.gnome.DiskUtility", "gparted"]],
  ["Rufus", ["rufus", "balena etcher", "etcher", "pendrive bootavel", "gravar iso"],
   ["io.gitlab.adhami3310.Impression", "gnome-disk-image-writer"]],
  ["Compartilhamento por Proximidade", ["compartilhamento por proximidade", "nearby share", "quick share", "airdrop"],
   ["localsend"]],
  ["Fax e Scanner do Windows", ["fax e scanner", "windows fax and scan", "scanner", "digitalizar"],
   ["org.gnome.SimpleScan"]],
  ["Visualizador de Fotos do Windows", ["visualizador de fotos", "windows photo viewer", "photo viewer"],
   ["imv", "org.gnome.Loupe", "org.gnome.eog"]],
  ["Prompt de Comando", ["cmd", "prompt de comando", "powershell", "windows terminal", "terminal do windows"],
   ["foot", "org.gnome.Console", "org.kde.konsole"]],
  ["Xbox", ["xbox", "xbox app"], ["steam"]]
]

function _compacto(s) { return String(s).replace(/[\s\-_.]+/g, "") }

// [{ ids, de, pontos }] para o texto já normalizado (minúsculas, sem acento).
// Termo exato = 95; o que foi digitado é o começo de um termo = 85 (pelo menos 3 letras,
// ou o termo inteiro se ele for menor — "ppt", "rdp").
function buscar(t) {
  var tc = _compacto(t)
  if (tc.length < 2) return []
  var out = []
  for (var i = 0; i < TABELA.length; i++) {
    var melhor = 0
    var termos = TABELA[i][1]
    for (var k = 0; k < termos.length; k++) {
      var ac = _compacto(termos[k])
      if (ac === tc) { melhor = 95; break }
      if (ac.indexOf(tc) === 0 && tc.length >= Math.min(3, ac.length)) melhor = Math.max(melhor, 85)
    }
    if (melhor) out.push({ de: TABELA[i][0], ids: TABELA[i][2], pontos: melhor })
  }
  return out
}
