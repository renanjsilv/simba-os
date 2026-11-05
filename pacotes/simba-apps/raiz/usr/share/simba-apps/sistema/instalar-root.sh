#!/bin/bash
# instalar-root.sh — parte do Simba OS que precisa de root. Idempotente: pode rodar de novo.
#   pkexec ~/.local/share/simba/sistema/instalar-root.sh <usuario>
# 1. remove LibreOffice e os vídeos de intro do Simba
# 2. papéis de parede do Simba em /usr/share/backgrounds/simba; tira os do Simba
# 3. pacman não extrai mais: fundos do Simba, documentação, traduções fora pt/en
# 4. suíte Craft (Word/Grid/Deck/PdfCraft) + atualizador diário verificado
# 5. Loja (Flatpak + Flathub + Bazaar) + atualização automática diária dos apps
# 6. nome "Simba OS" no sistema (os-release, issue) mantido depois de cada update
# 7. limpa o cache de pacotes antigos
set -uo pipefail
U=${1:?usuário}
D="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
H=$(getent passwd "$U" | cut -d: -f6)
passo() { printf '\n\e[1;34m==>\e[0m \e[1m%s\e[0m\n' "$*"; }
[ "$(id -u)" = 0 ] || { echo "rode com pkexec/sudo"; exit 1; }

passo "Removendo LibreOffice e as intros do Simba"
# simba-themes-intros é dependência do pacote simba: o pacote fica (vazio); os
# vídeos saem pelo NoExtract + limpeza dos fundos logo abaixo.
mapfile -t rem < <(pacman -Qq | grep -E '^libreoffice')
[ ${#rem[@]} -gt 0 ] && pacman -Rns --noconfirm "${rem[@]}"

passo "Configurando o pacman para não extrair arquivos desnecessários"
if ! grep -q '^# simba-noextract' /etc/pacman.conf; then
  cp -n /etc/pacman.conf /etc/pacman.conf.bak-simba
  python3 - <<'PY'
p = "/etc/pacman.conf"
s = open(p).read()
bloco = """# simba-noextract (Simba OS): fundos do Simba, documentação e traduções fora pt/en
NoExtract = usr/share/simba/themes/*/backgrounds/*
NoExtract = usr/share/doc/* usr/share/gtk-doc/*
NoExtract = usr/share/help/* !usr/share/help/C/* !usr/share/help/pt_BR/* !usr/share/help/pt/*
NoExtract = usr/share/locale/* !usr/share/locale/pt_BR/* !usr/share/locale/pt/* !usr/share/locale/en/* !usr/share/locale/en_US/* !usr/share/locale/en_GB/* !usr/share/locale/locale.alias
"""
i = s.index("[options]") + len("[options]\n")
s = s[:i] + bloco + s[i:]
open(p, "w").write(s)
PY
fi
pacman-conf >/dev/null || { echo "pacman.conf inválido — restaurando"; cp /etc/pacman.conf.bak-simba /etc/pacman.conf; }
find /usr/share/simba/themes -path '*/backgrounds/*' -type f -delete
find /usr/share/simba/themes -depth -path '*/backgrounds/*' -type d -empty -delete
rm -rf /usr/share/doc/* /usr/share/gtk-doc/*
find /usr/share/help -mindepth 1 -maxdepth 1 ! -name C ! -name pt_BR ! -name pt -exec rm -rf {} +
find /usr/share/locale -mindepth 1 -maxdepth 1 ! -name pt_BR ! -name pt ! -name en ! -name en_US ! -name en_GB ! -name locale.alias -exec rm -rf {} +

passo "Papéis de parede do Simba OS"
install -d /usr/share/backgrounds/simba
install -m644 "$D"/papeis/*.jpg /usr/share/backgrounds/simba/

runuser -u "$U" -- /usr/bin/simba-papeis || true

passo "Suíte de escritório Craft"
install -Dm755 "$D/simba-craft-atualizar" /usr/local/bin/simba-craft-atualizar
pacman -S --needed --noconfirm vulkan-icd-loader libxkbcommon-x11 >/dev/null
# pacotes já baixados e conferidos (sha256 da release) pelo usuário; senão, baixa agora
shopt -s nullglob
pk=("$H"/.local/share/simba/craft-cache/*.pkg.tar.zst)
if [ ${#pk[@]} -gt 0 ]; then
  ok=1
  while read -r url dig; do
    f="$H/.local/share/simba/craft-cache/$(basename "$url")"
    echo "${dig#sha256:}  $f" | sha256sum -c --status || { echo "sha256 não confere: $f"; ok=0; }
  done < "$H/.local/share/simba/craft-cache/lista.txt"
  [ $ok = 1 ] && pacman -U --noconfirm --needed "${pk[@]}"
fi
/usr/local/bin/simba-craft-atualizar || true
cat > /etc/systemd/system/simba-craft-atualizar.service <<'EOF'
[Unit]
Description=Simba OS: atualiza WordCraft, GridCraft, DeckCraft e PdfCraft
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/simba-craft-atualizar
Nice=10
IOSchedulingClass=idle
EOF
cat > /etc/systemd/system/simba-craft-atualizar.timer <<'EOF'
[Unit]
Description=Simba OS: atualização diária da suíte Craft

[Timer]
OnBootSec=15min
OnUnitActiveSec=1d
RandomizedDelaySec=30min
Persistent=true

[Install]
WantedBy=timers.target
EOF

passo "Loja de apps (Flatpak + Flathub + Bazaar)"
pacman -S --needed --noconfirm flatpak >/dev/null
flatpak remote-add --if-not-exists --system flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --system -y --noninteractive flathub io.github.kolunmi.Bazaar
install -Dm755 "$D/simba-loja" /usr/local/bin/simba-loja
cat > /etc/systemd/system/simba-flatpak-atualizar.service <<'EOF'
[Unit]
Description=Simba OS: atualiza os apps da Loja (Flatpak)
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/flatpak update --system -y --noninteractive
ExecStartPost=/usr/bin/flatpak uninstall --system -y --noninteractive --unused
Nice=10
IOSchedulingClass=idle
EOF
cat > /etc/systemd/system/simba-flatpak-atualizar.timer <<'EOF'
[Unit]
Description=Simba OS: atualização diária dos apps da Loja

[Timer]
OnBootSec=10min
OnUnitActiveSec=1d
RandomizedDelaySec=30min
Persistent=true

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now simba-craft-atualizar.timer simba-flatpak-atualizar.timer

passo "Nome do sistema: Simba OS"
install -Dm755 /dev/stdin /usr/local/bin/simba-marca <<'EOF'
#!/bin/bash
# Mantém o nome "Simba OS" no os-release e no /etc/issue (gancho do pacman).
f=/etc/os-release
[ -L $f ] && { cp --remove-destination "$(readlink -f $f)" $f; }
sed -i -e 's/^NAME=.*/NAME="Simba OS"/' -e 's/^PRETTY_NAME=.*/PRETTY_NAME="Simba OS"/' $f
grep -q '^VARIANT=' $f || echo 'VARIANT="baseado no Simba (Arch Linux)"' >> $f
printf 'Simba OS \\r (\\l)\n\n' > /etc/issue
EOF
install -Dm644 /dev/stdin /etc/pacman.d/hooks/zz-simba-marca.hook <<'EOF'
[Trigger]
Operation = Install
Operation = Upgrade
Type = Package
Target = *

[Action]
Description = Mantendo a identidade do Simba OS...
When = PostTransaction
Exec = /usr/local/bin/simba-marca
EOF
/usr/local/bin/simba-marca

passo "Limpando o cache de pacotes antigos"
paccache -rk1 -q || true
paccache -ruk0 -q || true

passo "Pronto"
df -h / | tail -1
