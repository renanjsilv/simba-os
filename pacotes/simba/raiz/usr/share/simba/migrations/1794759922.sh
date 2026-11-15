# Simba OS: a palavra de ativação "Draco" saiu (o Draco agora é só segurar F10).
# Desliga o serviço de escuta que ficou habilitado/rodando e tira as marcas e o modelo
# do detector. As gravações de treino (~/.local/share/draco/wake-train) não são apagadas
# aqui: são gravações da própria pessoa.
d=~/.local/share/draco
systemctl --user disable --now draco-wake.service >/dev/null 2>&1 || true
rm -f ~/.config/systemd/user/graphical-session.target.wants/draco-wake.service
rm -f "$d/wake.disabled" "$d"/models/draco_wake.npz*
systemctl --user daemon-reload >/dev/null 2>&1 || true
true
