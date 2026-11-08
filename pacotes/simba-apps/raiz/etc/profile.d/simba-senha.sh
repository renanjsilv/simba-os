# sudo sem terminal pede a senha numa janela do Simba (veja /usr/bin/simba-senha).
[ -x /usr/bin/simba-senha ] && export SUDO_ASKPASS=/usr/bin/simba-senha
