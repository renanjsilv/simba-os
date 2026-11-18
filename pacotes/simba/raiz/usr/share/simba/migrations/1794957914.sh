# Simba OS: transição suave entre temas claro/escuro (foto da tela que se desfaz).
# A camada da "cortina" precisa aparecer sem a animação de entrada do Hyprland.
f="$HOME/.config/hypr/looknfeel.lua"
if [[ -f $f ]] && ! grep -q 'namespace = "simba-transicao-tema"' "$f"; then
  printf '%s\n' 'hl.layer_rule({ match = { namespace = "simba-transicao-tema" }, no_anim = true, animation = "none" })' >> "$f"
fi
true
