#!/bin/bash
# Roda janela_integracao.py sem abrir nada na tela (GTK no backend Broadway).
set -u
aqui=$(dirname "$(readlink -f "$0")")
porta=$((20000 + RANDOM % 20000))
tela=":$((porta - 8080))"
gtk4-broadwayd --port "$porta" "$tela" >/dev/null 2>&1 &
broadway=$!
trap 'kill $broadway 2>/dev/null' EXIT
sleep 0.5
GDK_BACKEND=broadway BROADWAY_DISPLAY="$tela" timeout 180 python3 "$aqui/janela_integracao.py"
