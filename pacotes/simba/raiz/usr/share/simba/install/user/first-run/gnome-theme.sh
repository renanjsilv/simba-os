# Claro ou escuro conforme o tema do Simba (o tema padrão, White, é claro): antes isto
# forçava o modo escuro e os apps GTK/libadwaita (Loja, Arquivos) abriam escuros no tema claro.
simba-theme-set-gnome || {
  gsettings set org.gnome.desktop.interface color-scheme "prefer-light"
  gsettings set org.gnome.desktop.interface gtk-theme "Adwaita"
  gsettings set org.gnome.desktop.interface icon-theme "Yaru-blue"
}
