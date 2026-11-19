# Simba OS: atalhos preguiçosos do mise (~/.local/bin/<programa> que baixa na 1ª execução) de
# programas que já vêm instalados no sistema (ex.: /usr/bin/opencode da ISO) saem: eles vinham
# antes de /usr/bin no PATH e faziam o Draco e os Agentes acharem que o OpenCode não existia.
for w in "$HOME"/.local/bin/*; do
  [ -f "$w" ] || continue
  grep -q 'exec mise x' "$w" 2>/dev/null || continue
  n=$(basename "$w")
  PATH=/usr/local/bin:/usr/bin:/bin command -v "$n" >/dev/null 2>&1 && rm -f "$w"
done
true
