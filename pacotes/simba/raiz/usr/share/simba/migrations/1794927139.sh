# Simba OS: estilos de notificação (Configurações › Notificações). Os estilos translúcidos
# (Vidro, Escuro, Vidro pixelado) desfocam o fundo: regra de desfoque para a camada das
# notificações. ignore_alpha 0.5 = só desfoca atrás do cartão (a camada ocupa a tela toda).
f="$HOME/.config/hypr/looknfeel.lua"
if [ -f "$f" ] && ! grep -q 'namespace = "simba-notifications"' "$f"; then
  printf '%s\n' 'hl.layer_rule({ match = { namespace = "simba-notifications" }, blur = true, ignore_alpha = 0.5 })' >> "$f"
fi
fc-cache -f >/dev/null 2>&1 || true
true
