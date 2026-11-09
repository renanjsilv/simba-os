#!/bin/bash
# Simba OS: garante os papéis de parede do Simba na pasta de fundos do tema novo.
exec /usr/bin/simba-papeis "${1:-$(cat "$HOME/.local/state/simba/current/theme.name" 2>/dev/null)}" >/dev/null 2>&1
