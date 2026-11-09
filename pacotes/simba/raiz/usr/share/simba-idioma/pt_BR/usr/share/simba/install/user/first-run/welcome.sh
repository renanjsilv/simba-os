# Quebras de linha de verdade, não um \n literal: o cartão mostra o texto como chega e
# corta depois de três linhas.
simba-notification-send -u critical -g  "Atalhos de teclado" \
  $'Super + K mostra todos os atalhos.\nSuper + Espaço abre o Menu Iniciar.' \
  --exec simba-menu-keybindings
