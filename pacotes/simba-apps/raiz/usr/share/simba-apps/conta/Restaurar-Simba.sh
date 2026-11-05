#!/bin/bash
# Restaurar-Simba.sh — traz a sua conta (configurações, papéis de parede,
# histórico, documentos e programas) do Google Drive para um Simba recém-instalado.
#
# Como usar numa máquina formatada:
#   1. Instale o Simba e entre na área de trabalho.
#   2. Abra drive.google.com no navegador, entre na pasta "Simba Conta" e baixe este arquivo.
#   3. Abra um terminal e rode:  bash ~/Downloads/Restaurar-Simba.sh
#   4. Entre com a mesma conta Google na janela do navegador que abrir.
set -euo pipefail
echo "== Restaurar a conta do Google Drive =="
if ! command -v rclone >/dev/null; then
  echo "Instalando o rclone (pede a sua senha)…"
  sudo pacman -S --needed --noconfirm rclone
fi
if ! rclone listremotes | grep -qx 'conta-gdrive:'; then
  echo "Abrindo o login do Google no navegador…"
  echo "Se o navegador não abrir, copie o link http://127.0.0.1:53682/... que aparecer abaixo."
  rclone config create conta-gdrive drive scope=drive.file config_is_local=true
fi
mkdir -p "$HOME/.local/share/conta" "$HOME/.local/bin"
rclone copyto "conta-gdrive:Simba Conta/ferramenta/conta.py" "/usr/share/simba-apps/conta/conta.py"
printf '#!/bin/bash\nexec python3 "/usr/share/simba-apps/conta/conta.py" "$@"\n' > "/usr/bin/conta"
chmod +x "/usr/bin/conta"
if rclone cat "conta-gdrive:Simba Conta/meta.json" 2>/dev/null | grep -q '"cripto": true'; then
  python3 - <<'PY'
import json, pathlib
p = pathlib.Path.home() / ".config/conta/config.json"
p.parent.mkdir(parents=True, exist_ok=True)
c = json.loads(p.read_text()) if p.exists() else {}
c["cripto"] = True
p.write_text(json.dumps(c))
PY
  for t in 1 2 3; do
    read -rsp "Senha do backup criptografado: " senha; echo
    "/usr/bin/conta" senha "$senha" && break
    echo "Senha incorreta."
    [[ $t == 3 ]] && exit 1
  done
fi
"/usr/bin/conta" restaurar --sim
"/usr/bin/conta" auto liga || true
echo
echo "Pronto! Saia da sessão e entre de novo (ou reinicie) para tudo carregar."
