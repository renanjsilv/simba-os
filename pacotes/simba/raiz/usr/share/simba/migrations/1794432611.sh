# Simba OS 0.1.1: quem instalou pela ISO 0.1.0 não tem as regras dos botões de janela
# (o plugin janelas-nativo lê ~/.config/botoes-janela/config.json) e as Configurações
# ficavam com dois conjuntos de botões. Cria o arquivo padrão; não mexe num existente.
b=~/.config/botoes-janela/config.json
[[ -e $b ]] && exit 0
mkdir -p "${b%/*}"
cp /etc/skel/.config/botoes-janela/config.json "$b"
hyprctl janelas recarregar >/dev/null 2>&1 || true
