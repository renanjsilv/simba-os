#!/bin/bash
# Configurações app: re-read the Simba font/theme right away (font-set/theme-set hook).
f="${XDG_RUNTIME_DIR:-/tmp}/configuracoes/cmd"
[[ -d ${f%/*} ]] && jq -cn --arg s "$(date +%s%N)" '{s: $s, c: "tema", a: []}' >>"$f"
exit 0
