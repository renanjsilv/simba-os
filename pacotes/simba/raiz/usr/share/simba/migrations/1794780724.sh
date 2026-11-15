# Simba OS: a extensão "definir como papel de parede" do Google Fotos (Draco) parou quando o
# Draco virou pacote: o manifesto do navegador apontava para ~/.local/share/draco/bin.
# Regrava o manifesto com /usr/share/draco e garante a extensão no brave-flags.conf.
if [ -x /usr/share/draco/bin/draco-registrar-navegador ]; then
  /usr/share/draco/bin/draco-registrar-navegador
fi
true
