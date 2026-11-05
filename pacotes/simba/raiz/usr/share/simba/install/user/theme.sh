# Setup user theme folder and seed the default only when no theme exists yet.
mkdir -p ~/.config/simba/themes

if [[ ! -s $HOME/.local/state/simba/current/theme.name ]]; then
  # iso-chroot and provision-owner both run without a live session to notify.
  if [[ ${SIMBA_SETUP_CONTEXT:-runtime} != "runtime" ]]; then
    SIMBA_THEME_HEADLESS=1 simba-theme-set "Tokyo Night"
    rm -f ~/.config/chromium/SingletonLock # otherwise archiso owns the Chromium singleton
  else
    simba-theme-set "Tokyo Night"
  fi
fi
simba-theme-set-pi --activate

mkdir -p ~/.config/btop/themes
ln -snf "$HOME/.local/state/simba/current/theme/btop.theme" ~/.config/btop/themes/current.theme
