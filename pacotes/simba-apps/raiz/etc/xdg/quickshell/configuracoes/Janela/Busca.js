.pragma library

// Global search index: every setting row in the app, with extra words people
// might type. `chave` matches the Linha.chave on the page, which scrolls into
// view and pulses when a result is opened.
var itens = [
  // Personalização
  ["personalizacao", "tema", "Tema", "Cores do sistema inteiro: claro, escuro, paleta", "aparencia cor cores modo escuro claro dark light preto branco paleta skin estilo loja baixar instalar mais temas comunidade github remover"],
  ["personalizacao", "papel", "Papel de parede", "Imagem de fundo da área de trabalho", "fundo wallpaper plano imagem foto background tela"],
  ["personalizacao", "papelProximo", "Próximo papel de parede", "Troca para o próximo fundo do tema", "wallpaper fundo seguinte trocar"],
  ["personalizacao", "papelEscolher", "Escolher imagem para o fundo", "Usar qualquer imagem do computador", "wallpaper arquivo foto procurar"],
  ["personalizacao", "icones", "Tema de ícones", "Fluent, Tela, Papirus, Colloid, WhiteSur, Yaru…", "icones icone tema pacote fluent tela papirus colloid whitesur qogir yaru breeze aparencia"],
  ["personalizacao", "iconesCor", "Cor dos ícones", "Combina com o tema ou escolha uma", "icones cor pasta pastas azul verde"],
  ["personalizacao", "iconesBarra", "Ícones na barra de tarefas", "Monocromáticos ou coloridos", "icones barra tarefas colorido monocromatico"],
  ["personalizacao", "iconesModo", "Ícones claros ou escuros", "Variante do tema de ícones", "icones claro escuro variante"],
  ["personalizacao", "iniciarEstilo", "Estilo do menu Iniciar", "Windows 11, Windows 11 (2025), Compacto ou Tela cheia", "menu iniciar start super espaco launcher lancador aplicativos estilo windows"],
  ["personalizacao", "iniciarMaterial", "Fundo do menu Iniciar", "Sólido, acrílico ou transparente", "menu iniciar transparente translucido acrilico vidro fundo desfoque blur opaco"],
  ["personalizacao", "iniciarTransparencia", "Transparência do menu Iniciar", "Quanto do que está atrás aparece", "menu iniciar transparencia opacidade translucido"],
  ["personalizacao", "iniciarIntensidade", "Desfoque do menu Iniciar", "Intensidade do acrílico", "menu iniciar desfoque blur acrilico"],
  ["personalizacao", "iniciarTom", "Cor do menu Iniciar", "Do tema ou cor de destaque", "menu iniciar cor tonalidade destaque"],
  ["personalizacao", "iniciarCantos", "Cantos do menu Iniciar", "Arredondamento", "menu iniciar cantos arredondados raio"],
  ["personalizacao", "iniciarPosicao", "Posição do menu Iniciar", "Esquerda ou centro", "menu iniciar centro centralizado esquerda start"],
  ["personalizacao", "iniciarRecentes", "Arquivos recentes no Iniciar", "Recomendado", "recomendado recentes arquivos menu iniciar"],
  ["personalizacao", "iniciarFixados", "Apps fixados no Iniciar", "Restaurar fixados de fábrica", "fixar fixados pin menu iniciar"],
  ["personalizacao", "fonte", "Fonte do sistema", "Tipografia da barra, menus e terminais", "fonte letra tipografia font monospace"],
  ["personalizacao", "textoTamanho", "Tamanho do texto", "Escala do texto no shell, apps GTK e terminais", "zoom aumentar diminuir fonte grande pequena acessibilidade"],
  ["contas", "conta", "Conta Google", "Backup do sistema no Google Drive", "conta google drive backup login entrar sincronizar nuvem"],
  ["contas", "contaEntrar", "Entrar com o Google", "Conectar o Google Drive para backup", "login entrar conta google drive"],
  ["contas", "contaCripto", "Criptografar o backup", "Proteger o backup do Drive com senha", "criptografia senha backup seguranca"],
  ["contas", "contaItens", "O que é salvo no backup", "Configurações, imagens, histórico, documentos, programas", "backup categorias historico wallpaper papel de parede configuracoes programas pacotes"],
  ["contas", "contaAuto", "Backup automático", "Sincronizar com o Drive a cada 2 horas", "automatico sincronizar backup agendado"],
  ["contas", "contaRestaurar", "Restaurar desta conta", "Trazer tudo do Google Drive para este computador", "restaurar formatar formatada recuperar backup"],
  ["agentes", "agentesAbrir", "Abrir o agente de IA", "Super+Shift+Ctrl+A", "agente ia claude codex gemini opencode copilot abrir terminal"],
  ["agentes", "agentesOrdem", "Ordem dos agentes de IA", "Qual agente usar primeiro e qual vem depois", "agentes ordem prioridade claude codex gemini limite tokens"],
  ["agentes", "agentesTroca", "Trocar de agente quando o limite acabar", "Continua com o contexto em outro agente", "limite tokens acabou trocar agente automatico contexto failover"],
  ["agentes", "agentesEsperar", "Tempo antes de trocar de agente", "Contagem para cancelar com Esc", "esperar contagem trocar agente"],
  ["contas", "contaBoasVindas", "Oferecer entrar com o Google no primeiro boot", "Boas-vindas da conta nas instalações pela ISO", "primeira inicializacao boas vindas primeiro boot iso google opcional"],
  ["contas", "contaFormatada", "Restaurar numa máquina formatada", "Restaurar-Simba.sh", "formatar reinstalar maquina nova restaurar"],
  ["personalizacao", "temaBoot", "Tela de inicialização estilo Windows 11", "Escuro, claro, vidro (transparente), bloom e aurora", "plymouth boot inicializacao ligar desligar reiniciar windows 11 tema escuro claro transparente vidro bloom aurora spinner"],
  ["personalizacao", "desbloqueio", "Cores do tema Simba original (boot)", "Recolore a tela de senha do disco do Simba", "plymouth boot inicializacao desbloqueio senha disco cores"],
  // Janelas
  ["janelas", "gapsIn", "Espaço entre janelas", "Distância entre janelas lado a lado", "gaps gap espacamento margem interna gaps_in"],
  ["janelas", "gapsOut", "Margem da tela", "Distância entre as janelas e a borda da tela", "gaps gaps_out externa borda"],
  ["janelas", "borda", "Espessura da borda", "Moldura colorida da janela", "border borda contorno moldura"],
  ["janelas", "arredondamento", "Cantos arredondados", "Raio dos cantos das janelas (e deste app)", "rounding raio canto curva redondo quadrado"],
  ["janelas", "curvatura", "Suavidade dos cantos", "Formato da curva dos cantos", "rounding power squircle"],
  ["janelas", "opacidadeAtiva", "Opacidade da janela ativa", "Transparência da janela em foco", "transparencia opacidade vidro"],
  ["janelas", "opacidadeInativa", "Opacidade das janelas inativas", "Transparência das janelas fora de foco", "transparencia opacidade"],
  ["janelas", "escurecer", "Escurecer janelas inativas", "Destaca a janela em foco", "dim escurecer foco inativa"],
  ["janelas", "desfoque", "Desfoque (blur)", "Vidro fosco atrás de janelas transparentes", "blur desfoque vidro fosco acrilico"],
  ["janelas", "sombras", "Sombras", "Sombra suave sob as janelas", "shadow sombra profundidade"],
  ["janelas", "animacoes", "Animações", "Movimento ao abrir, fechar e mover janelas", "animacao efeitos movimento transicao"],
  ["janelas", "velocidade", "Velocidade das animações", "Mais rápidas ou mais suaves", "animacao rapida lenta velocidade"],
  ["janelas", "layout", "Organização das janelas", "Dwindle, mestre ou rolagem lateral", "layout dwindle master scrolling niri tiling mosaico"],
  ["janelas", "redimensionarBorda", "Redimensionar pelas bordas", "Arrastar a borda da janela com o mouse", "resize redimensionar borda"],
  ["janelas", "focoAtivar", "Focar janelas que pedem atenção", "Apps que se ativam roubam o foco", "focus foco ativar atencao"],
  ["janelas", "cursorDigitar", "Ocultar cursor ao digitar", "", "cursor mouse esconder digitar"],
  ["janelas", "botoesJanela", "Botões de janela (minimizar, maximizar, fechar)", "Minimizar, maximizar e fechar no canto das janelas", "minimizar maximizar fechar botoes titulo barra de titulo janela x"],
  ["janelas", "cursorParado", "Ocultar cursor parado", "Esconde o ponteiro após alguns segundos", "cursor mouse esconder inativo timeout"],
  // Tela
  ["tela", "organizacao", "Organizar telas", "Arraste as telas para posicioná-las", "monitor posicao arrastar layout organizar arranjo"],
  ["tela", "modoProjecao", "Modo de projeção", "Somente notebook, duplicar, estender ou somente segunda tela", "projetar duplicar espelhar estender mirror super p segunda tela externa hdmi"],
  ["tela", "resolucao", "Resolução", "", "resolucao tamanho pixels modo video"],
  ["tela", "taxa", "Taxa de atualização", "", "hz frequencia refresh taxa"],
  ["tela", "escala", "Escala", "Tamanho de tudo na tela", "escala zoom dpi hidpi"],
  ["tela", "rotacao", "Orientação", "Paisagem, retrato, invertido", "rotacao girar retrato paisagem transform"],
  ["tela", "telaAtiva", "Usar esta tela", "Ativar ou desativar a tela", "desativar desligar monitor tela"],
  ["tela", "perguntarTela", "Perguntar ao conectar uma tela nova", "Telas conhecidas lembram o modo", "monitor conectar novo hdmi lembrar conhecidas projetor"],
  ["tela", "principal", "Tela principal", "Onde ficam os ícones e o cursor inicial", "principal primaria primary"],
  ["tela", "brilho", "Brilho", "Brilho da tela do notebook", "brilho luminosidade backlight"],
  ["tela", "luzNoturna", "Luz noturna", "Tons mais quentes para descansar os olhos", "luz noturna azul filtro hyprsunset quente noite"],
  ["tela", "luzTemperatura", "Intensidade da luz noturna", "Temperatura de cor", "temperatura kelvin quente"],
  ["tela", "luzAgenda", "Programar luz noturna", "Liga e desliga sozinha em horários", "agendar horario programar automatico por do sol"],
  // Barra
  ["barra", "barraMostrar", "Mostrar a barra", "", "barra topo esconder mostrar painel waybar"],
  ["barra", "barraPosicao", "Posição da barra", "Topo, base, esquerda ou direita", "barra posicao topo base lateral"],
  ["barra", "barraTransparente", "Transparência da barra", "Quanto do papel de parede aparece atrás da barra", "barra transparencia transparente fundo opacidade nivel"],
  ["barra", "barraCentro", "Ícones do centro da barra", "Ocultar ou mostrar", "centro meio ocultar esconder icones indicadores clima teclado atualizacoes"],
  ["barra", "barraBandeja", "Seta de ícones ocultos", "Bandeja estilo Windows 11", "seta bandeja ocultos esconder icones tray overflow windows"],
  ["barra", "barraItens", "Itens da barra", "Mostrar, ocultar e reordenar widgets", "widgets itens relogio bateria rede bluetooth audio bandeja tray clima"],
  ["barra", "relogioFormato", "Formato do relógio", "", "relogio hora data formato 24h"],
  ["barra", "barraTamanho", "Tamanho da barra", "Compacta, normal, confortável ou grande", "barra altura tamanho grossura grande pequena"],
  ["barra", "areasEstilo", "Áreas de trabalho na barra", "Números, pontos, só ocupadas ou ocultar", "areas de trabalho workspaces 12345 numeros pontos ocultar esconder espacos"],
  ["barra", "tarefasIcones", "Estilo dos ícones da barra de tarefas", "Do tema (monocromáticos) ou coloridos", "icones tema monocromatico coloridos cor taskbar"],
  ["barra", "relogioHora", "Formato da hora", "24 ou 12 horas", "hora 12h 24h am pm relogio"],
  ["barra", "relogioSegundos", "Segundos no relógio", "", "segundos relogio hora"],
  ["barra", "relogioPosicao", "Posição do relógio", "Centro ou canto", "relogio posicao canto centro direita"],
  ["barra", "tarefasAtiva", "Barra de tarefas", "Apps fixados e abertos na barra", "barra de tarefas taskbar dock apps fixar fixados programas icones"],
  ["barra", "tarefasFixados", "Apps fixados na barra de tarefas", "Fixar, desafixar e reordenar", "fixar desafixar apps programas taskbar dock"],
  ["barra", "tarefasRotulos", "Nome dos apps na barra de tarefas", "", "rotulo nome titulo taskbar"],
  ["barra", "tarefasTamanho", "Tamanho dos ícones da barra de tarefas", "", "icones tamanho taskbar"],
  // Área de trabalho
  ["area", "areaIcones", "Mostrar ícones da área de trabalho", "", "icones area de trabalho desktop arquivos"],
  ["area", "areaTamanho", "Tamanho dos ícones", "Pequenos, médios ou grandes", "icones grandes pequenos medios"],
  ["area", "areaOrdenar", "Classificar ícones por", "Nome, tamanho, tipo ou data", "ordenar classificar"],
  ["area", "areaAuto", "Organizar ícones automaticamente", "", "auto organizar arranjar"],
  ["area", "areaGrade", "Alinhar ícones à grade", "", "grade alinhar"],
  ["area", "areaOcultos", "Mostrar arquivos ocultos", "", "ocultos escondidos ponto"],
  ["area", "areaPasta", "Pasta da área de trabalho", "", "pasta desktop diretorio"],
  ["area", "areaTela", "Tela com os ícones", "", "monitor tela icones"],
  ["area", "menuContexto", "Menu do botão direito", "Atualizar, novo, colar, papel de parede…", "clique direito menu contexto"],
  // Bloqueio
  ["bloqueio", "protecao", "Proteção de tela após", "Tempo parado até a proteção de tela", "protetor screensaver inatividade tempo ocioso"],
  ["bloqueio", "bloquearApos", "Bloquear após", "Tempo parado até bloquear com senha", "bloqueio lock senha tempo inatividade"],
  ["bloqueio", "manterAcordado", "Manter acordado", "Nunca entrar em inatividade", "cafeina acordado inibir idle"],
  ["bloqueio", "protecaoAtiva", "Proteção de tela", "Permitir a proteção de tela", "screensaver protetor ativar"],
  ["bloqueio", "bloquearAgora", "Bloquear agora", "", "lock bloquear tela senha"],
  ["bloqueio", "previaBloqueio", "Visualizar a tela de bloqueio", "", "preview previa bloqueio aparencia"],
  ["bloqueio", "protecaoAgora", "Iniciar a proteção de tela", "", "screensaver iniciar"],
  ["bloqueio", "protecaoTexto", "Texto da proteção de tela", "", "branding texto ascii screensaver"],
  // Entrada
  ["entrada", "kbLayout", "Layout do teclado", "", "teclado idioma layout abnt br us"],
  ["entrada", "kbVariante", "Variante do layout", "", "variante teclado intl dead keys"],
  ["entrada", "capsLock", "Tecla Caps Lock", "Maiúsculas ou tecla Compose", "caps lock maiusculas compose"],
  ["entrada", "repeticaoTaxa", "Velocidade de repetição", "", "repeticao tecla rapida repeat rate"],
  ["entrada", "repeticaoAtraso", "Atraso antes de repetir", "", "repeticao atraso delay"],
  ["entrada", "numlock", "Num Lock ligado ao iniciar", "", "numlock numerico"],
  ["entrada", "testeTeclado", "Testar o teclado", "", "teste digitar"],
  ["entrada", "mouseSensibilidade", "Velocidade do ponteiro", "", "mouse sensibilidade velocidade ponteiro cursor"],
  ["entrada", "mouseAceleracao", "Aceleração do ponteiro", "", "mouse aceleracao flat adaptive precisao"],
  ["entrada", "mouseNatural", "Rolagem natural do mouse", "", "mouse rolagem invertida natural scroll"],
  ["entrada", "mouseRolagem", "Velocidade da rolagem do mouse", "", "mouse rolagem scroll roda"],
  ["entrada", "canhoto", "Modo canhoto", "Troca os botões do mouse", "canhoto esquerdo botoes"],
  ["entrada", "focoMouse", "Foco segue o mouse", "", "foco follow mouse hover"],
  ["entrada", "touchpadAtivo", "Touchpad", "Ligar ou desligar o touchpad", "touchpad trackpad desligar"],
  ["entrada", "touchpadNatural", "Rolagem natural (touchpad)", "", "touchpad rolagem natural invertida"],
  ["entrada", "toqueClique", "Tocar para clicar", "", "touchpad toque tap clique"],
  ["entrada", "cliqueDedos", "Clique com dois dedos", "Botão direito com dois dedos", "touchpad clickfinger botao direito"],
  ["entrada", "digitandoDesativa", "Desativar touchpad ao digitar", "", "touchpad digitando palma"],
  ["entrada", "touchpadRolagem", "Velocidade da rolagem (touchpad)", "", "touchpad rolagem velocidade scroll"],
  ["entrada", "arrastar3", "Arrastar com três dedos", "", "touchpad arrastar tres dedos drag"],
  ["entrada", "gestos", "Gestos de áreas de trabalho", "Deslize três dedos para trocar", "gestos swipe deslizar workspace"],
  // Som
  ["som", "saida", "Dispositivo de saída", "Alto-falantes, fones, HDMI", "alto falante fone saida hdmi audio som"],
  ["som", "volume", "Volume", "", "volume som alto baixo"],
  ["som", "entradaDisp", "Microfone", "Dispositivo de entrada", "microfone entrada gravar mic"],
  ["som", "volumeMic", "Volume do microfone", "", "microfone ganho volume entrada"],
  ["som", "appsVolume", "Volume por aplicativo", "Mixer de volume", "mixer aplicativo volume programas"],
  ["som", "reiniciarAudio", "Reiniciar o áudio", "Quando o som some", "pipewire reiniciar som problema"],
  // Rede
  ["rede", "wifi", "Wi-Fi", "", "wifi wireless rede sem fio internet"],
  ["rede", "redes", "Redes disponíveis", "", "wifi conectar rede senha"],
  ["rede", "dns", "DNS", "Cloudflare, Google ou automático", "dns cloudflare google dhcp"],
  ["rede", "qrWifi", "Compartilhar Wi-Fi por QR Code", "", "qr code compartilhar senha wifi"],
  ["rede", "velocidadeRede", "Teste de velocidade", "", "speedtest velocidade internet download"],
  ["rede", "painelRede", "Painel de rede da barra", "", "painel rede barra"],
  // Bluetooth
  ["bluetooth", "btAtivo", "Bluetooth", "", "bluetooth ligar desligar"],
  ["bluetooth", "btDispositivos", "Dispositivos Bluetooth", "", "bluetooth parear conectar fone mouse teclado"],
  // Energia
  ["energia", "perfil", "Modo de energia", "Desempenho, equilibrado ou economia", "energia desempenho economia bateria perfil performance"],
  ["energia", "bateria", "Bateria", "", "bateria carga carregando tempo"],
  ["energia", "saudeBateria", "Saúde da bateria", "", "saude bateria capacidade desgaste"],
  ["energia", "suspenderMenu", "Mostrar Suspender no menu", "", "suspender dormir menu"],
  ["energia", "acoesEnergia", "Desligar, reiniciar e suspender", "", "desligar reiniciar suspender sair"],
  // Notificações
  ["notificacoes", "naoPerturbe", "Não perturbe", "Silencia as notificações", "nao perturbe silencio dnd notificacao"],
  ["notificacoes", "historico", "Histórico de notificações", "", "historico notificacoes antigas"],
  ["notificacoes", "limparNotif", "Limpar notificações", "", "limpar apagar notificacoes"],
  ["notificacoes", "testeNotif", "Enviar notificação de teste", "", "teste notificacao"],
  // Atalhos
  ["atalhos", "listaAtalhos", "Todos os atalhos de teclado", "", "atalhos teclas keybindings super"],
  ["atalhos", "superP", "Super + P: modo de projeção", "", "projetar super p atalho"],
  // Apps padrão
  ["apps", "navegador", "Navegador padrão", "", "navegador browser internet chrome firefox brave"],
  ["apps", "terminal", "Terminal padrão", "", "terminal console alacritty foot kitty ghostty"],
  ["apps", "editor", "Editor padrão", "", "editor texto codigo nvim vscode"],
  ["apps", "agente", "Agente de IA padrão", "", "agente ia claude codex gemini"],
  // Impressoras
  ["impressoras", "adicionarImpressora", "Adicionar impressora", "", "impressora imprimir printer adicionar instalar cups"],
  ["impressoras", "digitalizar", "Digitalizar documento", "Scanner", "scanner digitalizar escanear documento"],
  ["impressoras", "gerenciarImpressoras", "Gerenciar impressoras", "", "impressora fila remover padrao"],
  // Restauração
  ["restauracao", "pontoCriar", "Criar ponto de restauração", "", "restauracao ponto backup snapshot criar"],
  ["restauracao", "restaurar", "Restaurar o sistema", "Voltar para um ponto de restauração", "restaurar voltar desfazer snapshot recuperar quebrou"],
  ["restauracao", "pontosAuto", "Pontos de restauração automáticos", "", "automatico diario snapshot backup"],
  // Rede: firewall
  ["rede", "firewall", "Firewall", "Bloqueia conexões de entrada", "firewall seguranca ufw proteger bloquear"],
  // Sistema
  ["sistema", "sobre", "Sobre este computador", "Processador, memória, disco, sistema", "sobre hardware processador memoria ram disco versao especificacoes"],
  ["sistema", "atualizar", "Atualizar o sistema", "", "atualizacao update pacotes"],
  ["sistema", "idioma", "Idioma do sistema", "", "idioma lingua portugues ingles locale"],
  ["sistema", "fuso", "Fuso horário", "", "fuso horario hora relogio timezone"],
  ["sistema", "limpar", "Liberar espaço", "Caches de apps, AUR e programação, lixeira e pacotes antigos", "limpar espaco disco cache lixeira liberar armazenamento cheio"],
  ["sistema", "reiniciarShell", "Reiniciar a barra e as notificações", "", "reiniciar shell barra travou"],
  ["sistema", "sobreApp", "Sobre o app Configurações", "", "app configuracoes versao"]
]

function normalizar(s) {
  return String(s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
}

function paginaDe(chave) {
  for (var i = 0; i < itens.length; i++) if (itens[i][1] === chave) return itens[i][0]
  return ""
}

// tr: função de tradução (I18n.t). Busca no texto traduzido E no português, para que
// os dois idiomas achem a mesma configuração; mostra o traduzido.
function buscar(texto, paginas, tr) {
  tr = tr || function(x) { return x }
  var termos = normalizar(texto).split(/\s+/).filter(function(t) { return t.length > 0 })
  if (!termos.length) return []
  var info = {}
  for (var p = 0; p < paginas.length; p++) if (paginas[p].id) info[paginas[p].id] = paginas[p]
  var out = []
  for (var i = 0; i < itens.length; i++) {
    var it = itens[i]
    var pg = info[it[0]] || { titulo: it[0], glifo: "" }
    var tit = tr(it[2]), desc = tr(it[3]), chaves = it[4] ? tr(it[4]) : ""
    var titulo = normalizar(tit)
    var tudo = titulo + " " + normalizar(it[2]) + " " + normalizar(desc) + " " + normalizar(it[3]) + " " +
               normalizar(chaves) + " " + normalizar(it[4]) + " " + normalizar(pg.titulo)
    var ok = true, pontos = 0
    for (var t = 0; t < termos.length; t++) {
      var termo = termos[t]
      if (tudo.indexOf(termo) < 0) { ok = false; break }
      if (titulo.indexOf(termo) === 0) pontos += 6
      else if (titulo.indexOf(" " + termo) >= 0 || titulo.indexOf(termo) >= 0) pontos += 4
      else if (normalizar(chaves + " " + it[4]).indexOf(termo) >= 0) pontos += 2
      else pontos += 1
    }
    if (ok) out.push({ pagina: it[0], chave: it[1], titulo: tit, caminho: pg.titulo + (desc ? " · " + desc : ""), glifo: pg.glifo, pontos: pontos, ordem: i })
  }
  out.sort(function(a, b) { return b.pontos - a.pontos || a.ordem - b.ordem })
  return out
}
