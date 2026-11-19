# Simba OS: identidade em pixel art — o único gato é o retrato da marca.
# Refaz a lista de papéis de parede (os ilustrados antigos saíram) e troca o logo do terminal.
command -v simba-papeis >/dev/null && simba-papeis >/dev/null 2>&1
# papel atual apontando para um arquivo que não existe mais → o primeiro da lista do tema
bg="$HOME/.local/state/simba/current/background"
if [[ -L $bg && ! -e $bg ]] && command -v simba-theme-bg-next >/dev/null; then
  simba-theme-bg-next >/dev/null 2>&1
fi
# logo do fastfetch/terminal: só troca se ainda for o desenho padrão antigo (não mexe no da pessoa)
a="$HOME/.config/simba/branding/about.txt"
case $(md5sum < "$a" 2>/dev/null | cut -d' ' -f1) in
  d1472bfb13b154d79783a2087d86f0ea|9b01cbee5295f0e046033d73fa3f20f8) antigo=1 ;; *) antigo=0 ;;
esac
if [[ $antigo = 1 ]]; then
  cp /etc/skel/.config/simba/branding/about.txt "$a"
fi
true
