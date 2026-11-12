# Simba OS 0.1.3: liga direto no sistema, sem o menu do Limine ("Simba OS > Linux").
# Segurar Shift no boot ainda abre o menu.
f=/boot/limine.conf
[[ -f $f ]] || exit 0
grep -qx 'timeout: 0' "$f" && grep -qx 'quiet: yes' "$f" && exit 0
echo "Ajustando o boot para ligar direto (pede a senha de administrador)"
sudo sed -i -e '/^#\{0,1\}timeout:/d' -e '/^#\{0,1\}quiet:/d' "$f"
sudo sed -i '1i timeout: 0\nquiet: yes' "$f"
