# Simba OS: Draco e botões de janela agora rodam dentro do Quickshell das Configurações
# (um processo em vez de três, ~170 MB a menos). Os comandos antigos apontavam para os
# processos separados.
h=~/.config/hypr
[[ -f $h/bindings.lua ]] && sed -i 's/qs -c botoes-janela ipc call botoes/qs -c configuracoes ipc call botoes/g' "$h/bindings.lua"
[[ -f $h/autostart.lua ]] && sed -i '/^o\.launch_on_start("qs -c draco -n")$/d' "$h/autostart.lua"
# O serviço botoes-janela virou só uma marca de "ligado" (não abre mais um Quickshell).
systemctl --user daemon-reload >/dev/null 2>&1 || true
true
