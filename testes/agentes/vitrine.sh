#!/bin/bash
# Fotografa a janela do chat com uma resposta de exemplo, sem abrir nada na tela
# (GTK no backend Broadway). Variáveis: veja vitrine.py.
set -u
aqui=$(dirname "$(readlink -f "$0")")
n=$((40 + RANDOM % 50))
gtk4-broadwayd ":$n" >/dev/null 2>&1 & bw=$!
trap 'kill $bw 2>/dev/null' EXIT
sleep 0.4
GDK_BACKEND=broadway BROADWAY_DISPLAY=":$n" timeout 120 python3 "$aqui/vitrine.py" 2>&1 | grep -v "Gtk-WARNING\|Gdk-WARNING\|^$"
