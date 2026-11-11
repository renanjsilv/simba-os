# Simba OS 0.1.2 — correções para quem instalou pela 0.1.0 / 0.1.1:
# 1. regras dos botões de janela (o plugin janelas-nativo lê ~/.config/botoes-janela/config.json;
#    sem ele as Configurações ficavam com dois conjuntos de botões). Não mexe num existente.
b=~/.config/botoes-janela/config.json
if [[ ! -e $b ]]; then
  mkdir -p "${b%/*}"
  cp /etc/skel/.config/botoes-janela/config.json "$b"
  hyprctl janelas recarregar >/dev/null 2>&1 || true
fi
# 2. o primeiro login forçava o GTK no modo escuro (Loja escura no tema claro)
simba-theme-set-gnome >/dev/null 2>&1 || true
