# Simba OS 0.1: os apps com.renan.* viram com.simba.* e o plugin da tela de bloqueio
# renan.lock vira simbaos.bloqueio. Atualiza a configuração da pessoa (fixados da barra e
# do Menu Iniciar, regras de janela do Hyprland, apps padrão) para os nomes novos.
ids='s/com\.renan\.\(Configuracoes\|Explorador\|GerenciadorTarefas\|Transcrever\|GerarIso\)/com.simba.\1/g'
for f in ~/.config/hypr/*.lua ~/.config/configuracoes/*.json ~/.config/mimeapps.list \
         ~/.local/share/applications/mimeapps.list ~/.config/simba/shell.json \
         ~/.config/simba/extensions/simba-menu.jsonc ~/.local/state/configuracoes/*.json; do
  [[ -f $f && ! -L $f ]] || continue
  grep -q 'com\.renan\.\|renan\.lock' "$f" || continue
  sed -i -e "$ids" -e 's/"renan\.lock"/"simbaos.bloqueio"/g' "$f"
done
plugins=~/.config/simba/plugins
rm -f "$plugins/renan.lock"
if [[ -d /usr/share/simba-apps/bloqueio ]]; then
  mkdir -p "$plugins"
  ln -sfn /usr/share/simba-apps/bloqueio "$plugins/simbaos.bloqueio"
fi

# Atalhos web herdados do Omarchy que o Simba não usa (só os originais; um atalho
# editado pela pessoa fica)
for app in Basecamp HEY Docker; do
  f=~/.local/share/applications/$app.desktop
  [[ -f $f ]] && grep -qE 'basecamp\.com|37signals\.com|app\.hey\.com|simba-webapp-handler-hey|simba-launch-docker' "$f" && rm -f "$f"
done
# e-mail padrão era o HEY
[[ -f ~/.config/mimeapps.list ]] && sed -i '/^x-scheme-handler\/mailto=HEY\.desktop$/d' ~/.config/mimeapps.list
true
