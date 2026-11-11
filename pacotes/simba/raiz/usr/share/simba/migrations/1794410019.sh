# Simba OS 0.1.1: a barra ficou travada (arrastar o meio dela mudava a borda e a barra de
# tarefas se perdia na lateral). Quem ficou com a barra na esquerda/direita volta para baixo.
# Regra dos botões de janela ainda com o nome antigo das Configurações (botões duplicados).
b=~/.config/botoes-janela/config.json
[[ -f $b && ! -L $b ]] && sed -i 's/com\(\\*\)\.renan\(\\*\)\./com\1.simba\2./g' "$b"

f=~/.config/simba/shell.json
[[ -f $f && ! -L $f ]] || exit 0
python3 - "$f" <<'PY'
import json, sys
p = sys.argv[1]
with open(p, encoding="utf-8") as fh:
    cfg = json.load(fh)
bar = cfg.get("bar")
if isinstance(bar, dict) and bar.get("position") in ("left", "right") and not bar.get("movable"):
    bar["position"] = "bottom"
    with open(p + ".tmp-migracao", "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    import os
    os.replace(p + ".tmp-migracao", p)
PY
true
