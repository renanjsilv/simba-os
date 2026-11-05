#!/bin/bash
# temas-e-logo.sh — Simba OS (root, idempotente):
#  1. deixa só o tema White em /usr/share/simba/themes; o preto é o "Black"
#     (cópia do Vantablack em ~/.config/simba/themes/black, do usuário)
#  2. troca o logo do Simba (/usr/share/simba/logo.txt, mostrado nos terminais de
#     atualização/instalação) pelo gato Simba
#  O pacman não extrai mais esses arquivos (NoExtract), então atualizações do Simba
#  não trazem os temas de volta nem restauram o logo.
#   sudo ~/.local/share/simba/sistema/temas-e-logo.sh <usuario>
set -uo pipefail
[ "$(id -u)" = 0 ] || { echo "rode com sudo/pkexec"; exit 1; }
U=${1:-${SUDO_USER:-${PKEXEC_UID:+$(id -nu "$PKEXEC_UID")}}}
[ -n "$U" ] || { echo "informe o usuário"; exit 1; }
H=$(getent passwd "$U" | cut -d: -f6)
FICA="white"
T=/usr/share/simba/themes

echo "==> pacman.conf"
if ! grep -qxF "NoExtract = usr/share/simba/themes/* $(printf '!usr/share/simba/themes/%s/* ' $FICA)usr/share/simba/logo.txt" /etc/pacman.conf; then
  cp -n /etc/pacman.conf /etc/pacman.conf.bak-temas; cp /etc/pacman.conf /etc/pacman.conf.antes-temas
  # versão anterior do bloco (com outros temas) sai antes de pôr a nova
  sed -i '/^# simba-temas/{N;d}' /etc/pacman.conf
  python3 - "$FICA" <<'PY'
import sys
p = "/etc/pacman.conf"
s = open(p).read()
fica = sys.argv[1].split()
linha = "NoExtract = usr/share/simba/themes/* " + " ".join(f"!usr/share/simba/themes/{t}/*" for t in fica) + " usr/share/simba/logo.txt"
bloco = "# simba-temas (Simba OS): só o tema White (o Black fica em ~/.config); logo do Simba = gato Simba\n" + linha + "\n"
# antes do bloco simba-noextract: no pacman vale a última regra que casa, e a dos
# fundos (themes/*/backgrounds/*) precisa continuar valendo para os temas que ficam
i = s.find("# simba-noextract")
if i < 0: i = s.index("[options]") + len("[options]\n")
open(p, "w").write(s[:i] + bloco + s[i:])
PY
fi
pacman-conf >/dev/null || { echo "pacman.conf inválido — restaurando"; cp /etc/pacman.conf.antes-temas /etc/pacman.conf; exit 1; }

# o Black do usuário nasce do Vantablack; se ainda não existir, copia antes de apagar
if [ ! -d "$H/.config/simba/themes/black" ] && [ -d "$T/vantablack" ]; then
  install -d -o "$U" -g "$(id -gn "$U")" "$H/.config/simba/themes"
  cp -r "$T/vantablack" "$H/.config/simba/themes/black"
  chown -R "$U:$(id -gn "$U")" "$H/.config/simba/themes/black"
fi

echo "==> temas"
for d in "$T"/*/; do
  n=$(basename "$d")
  [[ " $FICA " == *" $n "* ]] && continue
  rm -rf "$d" && echo "removido: $n"
  # fundos do Simba ligados a esse tema (só links; arquivos da pessoa ficam)
  b="$H/.config/simba/backgrounds/$n"
  if [ -d "$b" ]; then
    find "$b" -maxdepth 1 -type l -delete
    rmdir "$b" 2>/dev/null || true
  fi
done

echo "==> logo"
[ -f /usr/share/simba/logo.txt.bak-simba ] || cp /usr/share/simba/logo.txt /usr/share/simba/logo.txt.bak-simba
install -m644 "$H/.config/simba/branding/about.txt" /usr/share/simba/logo.txt

echo "Pronto. Temas: $(ls "$T" | tr '\n' ' ')"
