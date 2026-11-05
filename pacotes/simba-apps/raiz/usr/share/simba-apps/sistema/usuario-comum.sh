#!/bin/bash
# usuario-comum.sh — Simba OS para o usuário comum (rodar como o usuário, NÃO como root;
# pede a senha do sudo uma vez). Idempotente.
#   1 editor de texto · 2 compactados · 3 vídeos · 4 codecs · 5 NTFS · 7 corretor pt-BR
#   8 pontos de restauração · 9 firmware · 10 firewall · 12 impressoras/scanner
set -uo pipefail
[ "$(id -u)" != 0 ] || { echo "rode como o seu usuário (sem sudo)"; exit 1; }
D="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
passo() { printf '\n\e[1;34m==>\e[0m \e[1m%s\e[0m\n' "$*"; }
sudo -v || exit 1

passo "Apps e codecs"
sudo pacman -S --needed --noconfirm gnome-text-editor file-roller celluloid \
  gst-libav gst-plugins-ugly ntfs-3g fwupd simple-scan sane

passo "Corretor ortográfico em português (AUR)"
yay -S --needed --noconfirm --answerclean None --answerdiff None hunspell-pt-br || echo "(não instalou o corretor — tente de novo depois)"

passo "Ajudante de administrador das Configurações"
sudo install -Dm755 "$D/simba-sistema" /usr/local/bin/simba-sistema
sudo tee /etc/systemd/system/simba-menu-volta.service >/dev/null <<'UNIT'
[Unit]
Description=Simba OS: esconde de novo o menu de inicialização depois de usado uma vez
RequiresMountsFor=/boot
ConditionPathExists=/boot/simba-menu-uma-vez

[Service]
Type=oneshot
ExecStart=/usr/local/bin/simba-sistema menu-volta

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable simba-menu-volta.service

passo "Pontos de restauração"
# grupo wheel lista e cria pontos sem senha (restaurar continua pedindo)
sudo snapper -c root set-config ALLOW_GROUPS=wheel SYNC_ACL=yes TIMELINE_CREATE=yes \
  TIMELINE_LIMIT_HOURLY=0 TIMELINE_LIMIT_DAILY=5 TIMELINE_LIMIT_WEEKLY=2 \
  TIMELINE_LIMIT_MONTHLY=0 TIMELINE_LIMIT_QUARTERLY=0 TIMELINE_LIMIT_YEARLY=0
sudo systemctl enable --now snapper-timeline.timer snapper-cleanup.timer

passo "Firmware (fwupd)"
sudo systemctl enable --now fwupd-refresh.timer 2>/dev/null || true

passo "Impressoras"
sudo systemctl enable --now cups.socket avahi-daemon.service 2>/dev/null || true

passo "Apps padrão (texto, compactados, vídeo)"
for m in text/plain text/markdown text/x-log application/x-shellscript application/json application/xml text/x-python; do
  xdg-mime default org.gnome.TextEditor.desktop "$m"; done
for m in application/zip application/x-7z-compressed application/x-rar application/vnd.rar application/x-tar \
  application/x-compressed-tar application/x-bzip2-compressed-tar application/x-xz-compressed-tar \
  application/zstd application/x-zstd-compressed-tar application/gzip application/x-gzip; do
  xdg-mime default org.gnome.FileRoller.desktop "$m"; done
for m in video/mp4 video/x-matroska video/webm video/quicktime video/x-msvideo video/mpeg video/ogg \
  video/x-flv video/3gpp video/x-ms-wmv; do
  xdg-mime default io.github.celluloid_player.Celluloid.desktop "$m"; done

printf '\n\e[1;32mPronto!\e[0m\n'
