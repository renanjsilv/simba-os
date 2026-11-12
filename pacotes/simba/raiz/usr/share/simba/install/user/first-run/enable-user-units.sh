#!/bin/bash

# Enable AND start the user systemd units we ship. Runs at first-run rather
# than at finalize-user time because the user manager isn't live during the
# ISO chroot — by first-run, the Hyprland/uwsm session is up and
# `systemctl --user enable --now` both writes the correct .wants symlinks
# (based on each unit's [Install]/WantedBy) and starts the services so the
# first session has bluetooth pairing, sleep lock, etc. live immediately
# instead of waiting for the next login. ConditionPath* in the unit files
# keep the enabled units inert on hardware they don't apply to.

set -euo pipefail

systemctl --user daemon-reload
systemctl --user enable --now \
  bt-agent.service \
  simba-recover-internal-monitor.service \
  simba-sleep-lock.service \
  simba-migrate-notify.service \
  simba-fcitx5.service \
  simba-crash-watch.service
# do simba-apps: canto "mostrar a área de trabalho", encaixe de janelas (Super+Z) e o aviso de
# atualizações — sem eles, instalação nova ficava sem o canto e sem avisos
for u in botoes-janela.service simba-atualizar-avisar.timer; do
  systemctl --user cat "$u" >/dev/null 2>&1 && systemctl --user enable --now "$u" || true
done
