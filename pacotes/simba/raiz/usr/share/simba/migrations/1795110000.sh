# Simba OS: atalhos preguiçosos do mise (~/.local/bin/<programa> que baixa na 1ª execução) de
# programas que já vêm instalados no sistema (ex.: /usr/bin/opencode da ISO) saem: eles vinham
# antes de /usr/bin no PATH e faziam o Draco e os Agentes acharem que o OpenCode não existia.
for w in "$HOME"/.local/bin/*; do
  [ -f "$w" ] || continue
  grep -q 'exec mise x' "$w" 2>/dev/null || continue
  n=$(basename "$w")
  PATH=/usr/local/bin:/usr/bin:/bin command -v "$n" >/dev/null 2>&1 && rm -f "$w"
done
# O comando `agentes` do terminal gravava o OpenCode (grátis, sem conta) como desligado no 1º uso:
# religa uma vez (depois disso vale o que a pessoa escolher em Configurações › Agentes de IA).
python3 - <<'PY' 2>/dev/null || true
import json, pathlib
p = pathlib.Path.home() / ".config/agentes/config.json"
try:
    c = json.loads(p.read_text())
except (OSError, ValueError):
    raise SystemExit
if isinstance(c, dict) and not c.get("gratis_revisto"):
    if "opencode" in c.get("inativos", []):
        c["inativos"].remove("opencode")
    if "opencode" in c.get("ordem", []):
        c["ordem"].remove("opencode"); c["ordem"].insert(0, "opencode")
    c["gratis_revisto"] = True
    p.write_text(json.dumps(c, ensure_ascii=False, indent=1))
PY
true
