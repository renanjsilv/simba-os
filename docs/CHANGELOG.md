# Histórico de versões do Simba OS

Cada versão é uma ISO de instalação. Quem já tem o Simba OS instalado recebe tudo pelo
**Atualizar tudo**, sem reinstalar.

## 1.0 — 22 de novembro de 2026

A primeira versão estável.

**Conta Google e sincronização**
- Pastas iguais em todos os computadores: Documentos, Imagens, Área de trabalho e as pastas
  extras ficam idênticas em todas as máquinas da conta. Na primeira vez, o conteúdo de cada
  máquina é mesclado ao do Drive, sem perder nada. Depois disso, criar, alterar ou apagar um
  arquivo numa máquina vale para todas. Se o mesmo arquivo mudar em duas, fica a versão mais
  nova e a outra é guardada ao lado como `nome.conflito1`.
- A lista de pastas sincronizadas é da conta: marcar ou desmarcar numa máquina vale para todas.
- Acesso próprio do Simba OS ao Google Drive (o acesso compartilhado do rclone está sendo
  desativado pelo Google). O login mostra "Simba OS", sem aviso de app não verificado.
- Login do Google numa janela própria, na frente das boas-vindas. Antes abria escondido atrás
  delas e parecia lento.
- O login é detectado em cerca de 1 segundo e a janela fecha sozinha ao terminar.
- Painel da nuvem com o envio real: cada arquivo aparece com o próprio percentual, mais o total,
  o que está na fila e o histórico do que já foi sincronizado.
- "Abrir pasta" abre a nova pasta **Simba Conta**, com atalhos para tudo o que é sincronizado
  (como a do OneDrive).
- Papel de parede entre máquinas corrigido: a máquina parada não recebia a troca feita na outra.
- Interruptores de Configurações › Contas não travam mais durante um backup.
- Boas-vindas: interruptores respondem na hora, o cartão inteiro é clicável e "Começar a
  sincronizar" sempre salva a escolha.
- Sincronização a cada 5 minutos (as configurações vão para o backup a cada 30).

**Tela de bloqueio**
- Super+L bloqueia de novo (o bloqueio não carregava).
- Visual novo: papel de parede com hora e data; qualquer tecla mostra a foto da conta Google
  (ou o gato do Simba), o nome e a senha sobre o fundo desfocado; menu de energia no canto.

**Instalação e inicialização**
- "Entrar sem senha ao ligar" agora também dispensa a senha do disco em computadores sem TPM.
  Para máquinas já instaladas: `sudo simba-disco-sem-senha ligar`.
- Tela de ligar, desligar e reiniciar preta com o gato e o nome Simba OS, igual à do pendrive
  (tema "Simba OS", o novo padrão).

**Segurança**
- O registro do login do Google não guarda mais o token legível por outros usuários.

## 0.2.0 — 19 a 21 de novembro de 2026

- Identidade visual em pixel art: retrato do gato, papéis de parede e o mini game do instalador
  (gato tigrado, 3 vidas, pombos e buracos no telhado).
- Secure Boot sem desligar nada: shim da Microsoft e chave própria do Simba OS.
- Sincronização com visual do OneDrive: ícone na bandeja, situação no Explorador e na área de
  trabalho, escolha de pastas e programas nas boas-vindas.

## 0.1.9 — 18 de novembro de 2026

- Explorador de Arquivos residente: abre em cerca de 0,15 s e não vaza mais memória.
- Configurações mais rápidas (páginas carregadas em segundo plano).
- Fotos abrem com setas para a próxima da pasta.
- Central de notificações no relógio, no estilo do Windows 11, com 12 estilos de aviso.
- Troca de tema claro/escuro em cerca de 1 segundo, com transição suave.

## 0.1.8 — 16 de novembro de 2026

- Tema escuro como padrão, boot preto e logo de alto contraste.
- Papel de parede igual entre as máquinas na hora.
- Draco grátis por padrão, com diagnóstico.
- Agentes de IA com modo automático e Skills.
- Configurações na ordem do Windows 11; propriedades de rede completas (IP manual, DNS, rede
  limitada, MAC aleatório); Bluetooth e Wi-Fi em páginas próprias na Central.

## 0.1.6 — 16 de novembro de 2026

- Teste completo da ISO passa a conferir mais 8 funções (OpenCode, botões de janela,
  restauração de fábrica, papel de parede entre máquinas, som do volume e outras).

## 0.1.5 — 15 de novembro de 2026

- Draco: só F10 para falar, transcrição local (Parakeet) e IA grátis por padrão.
- Restauração de fábrica nas Configurações (ponto de fábrica criado na instalação).
- Desinstalar apps pelo Menu Iniciar; Central com 65% menos uso de CPU.
- Wi-Fi mais confiável nas boas-vindas e na Central.

## 0.1.4 — 13 de novembro de 2026

- Programas do Windows (.exe) abrem pelo Wine, com atalhos depois de instalar.
- GPU híbrida, seletor de microfone, codecs Bluetooth de alta qualidade e cuidados com a bateria.
- Conta Google: favoritos do Brave, modo viagem, resolução de conflitos e sincronização seletiva.
- Botão "Programa de testes (versões beta)" em Configurações › Sistema.

## 0.1.3 — 12 de novembro de 2026

- Boas-vindas com Wi-Fi e conta Google de verdade; boot direto; ISO mais rápida.
- AnyDesk funcionando; Lixeira na área de trabalho; Central com o que está tocando.

## 0.1.2 — 11 de novembro de 2026

- Correções do teste numa instalação nova: barra com ícones, botões de janela únicos, primeira
  tela do instalador alinhada.

## 0.1.1 — 11 de novembro de 2026

- Correções do teste em outra máquina: barra, boas-vindas, Loja, Draco e boot.
- Canal de teste para as atualizações.

## 0.1.0 — 10 de novembro de 2026

- Primeira ISO pública (beta): Hyprland com barra de tarefas, Menu Iniciar, Configurações,
  Explorador de Arquivos, Gerenciador de Tarefas, Agentes de IA, Draco e conta Google, tudo em
  português.
