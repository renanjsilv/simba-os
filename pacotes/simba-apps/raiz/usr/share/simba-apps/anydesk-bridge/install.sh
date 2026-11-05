#!/bin/bash
# Instala a ponte AnyDesk ↔ Hyprland.
#   Uso:      sudo /usr/share/simba-apps/anydesk-bridge/install.sh
#   Remover:  sudo /usr/share/simba-apps/anydesk-bridge/install.sh --uninstall
#
# Mudanças no sistema (todas aditivas e reversíveis):
#   /usr/local/lib/anydesk-bridge/libanydesk-bridge-shim.so
#   /etc/systemd/system/anydesk.service.d/hyprland-bridge.conf  (LD_PRELOAD só no serviço do AnyDesk)
#   ~/.config/systemd/user/anydesk-bridge.service               (serviço de usuário)
set -euo pipefail

[ "$(id -u)" = 0 ] || { echo "Rode com sudo." >&2; exit 1; }
USER_NAME="${SUDO_USER:?rode via sudo a partir do seu usuário}"
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
USER_UID="$(id -u "$USER_NAME")"
SRC="$USER_HOME/.local/share/anydesk-bridge"
LIBDIR=/usr/local/lib/anydesk-bridge
DROPIN=/etc/systemd/system/anydesk.service.d/hyprland-bridge.conf
as_user() { sudo -u "$USER_NAME" XDG_RUNTIME_DIR="/run/user/$USER_UID" "$@"; }

if [ "${1:-}" = "--uninstall" ]; then
  as_user systemctl --user disable --now anydesk-bridge.service 2>/dev/null || true
  rm -f "$USER_HOME/.config/systemd/user/anydesk-bridge.service"
  rm -f "$DROPIN"; rmdir --ignore-fail-on-non-empty "$(dirname "$DROPIN")" 2>/dev/null || true
  rm -rf "$LIBDIR"
  systemctl daemon-reload
  systemctl restart anydesk
  echo "Ponte removida; AnyDesk de volta ao original."
  exit 0
fi

# 1) Compila o shim como root a partir do fonte revisado
install -d -m 755 "$LIBDIR"
gcc -O2 -Wall -fPIC -shared -o "$LIBDIR/libanydesk-bridge-shim.so" "$SRC/shim.c" \
  $(pkg-config --cflags --libs gio-2.0 gio-unix-2.0) -ldl
chmod 644 "$LIBDIR/libanydesk-bridge-shim.so"

# 2) Drop-in: carrega o shim apenas no serviço do AnyDesk
install -d -m 755 "$(dirname "$DROPIN")"
cat > "$DROPIN" <<EOF
[Service]
Environment=LD_PRELOAD=$LIBDIR/libanydesk-bridge-shim.so
EOF
install -m 644 /dev/null /var/log/anydesk-bridge-shim.log

# 3) Serviço de usuário da ponte
install -d -o "$USER_NAME" -g "$(id -gn "$USER_NAME")" "$USER_HOME/.config/systemd/user"
install -m 644 -o "$USER_NAME" -g "$(id -gn "$USER_NAME")" \
  "$SRC/anydesk-bridge.service" "$USER_HOME/.config/systemd/user/anydesk-bridge.service"
chmod 755 "$SRC/anydesk-bridge"
as_user systemctl --user daemon-reload
as_user systemctl --user enable --now anydesk-bridge.service

# 4) Reinicia o AnyDesk com o shim
systemctl daemon-reload
systemctl restart anydesk
echo "Ponte instalada. Log do shim: /var/log/anydesk-bridge-shim.log"
