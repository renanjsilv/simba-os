# Simba OS 0.1.2: janelas.lua novo (janela solta que abre atrás da barra de tarefas — ex.: as
# notificações da Steam — é trazida para a área útil). O arquivo mora na ~/.config do usuário;
# a versão anterior fica em janelas.lua.bak-0.1.2.
f=~/.config/hypr/janelas.lua
[[ -f /etc/skel/.config/hypr/janelas.lua ]] || exit 0
if [[ -f $f ]] && ! grep -q manter_na_area "$f"; then
  cp "$f" "$f.bak-0.1.2"
  cp /etc/skel/.config/hypr/janelas.lua "$f"
  hyprctl reload >/dev/null 2>&1 || true
fi
