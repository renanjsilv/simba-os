# Simba OS 0.1.3: instalações pela ISO ficavam sem o canto "mostrar a área de trabalho", o
# encaixe de janelas (Super+Z) e o aviso de atualizações (serviços não ligados no 1º login).
for u in botoes-janela.service simba-atualizar-avisar.timer; do
  systemctl --user cat "$u" >/dev/null 2>&1 && systemctl --user enable --now "$u" >/dev/null 2>&1 || true
done
