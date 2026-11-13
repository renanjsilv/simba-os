# Simba OS 0.1.3: a escuta do "Draco" era só iniciada (nunca habilitada) e parava a cada
# reinício numa instalação nova. Quem já preparou o Draco e não desligou a escuta: habilita.
d=~/.local/share/draco
[[ -x $d/venv/bin/python && ! -f $d/wake.disabled ]] || exit 0
systemctl --user enable --now draco-wake.service draco-aquecer.service >/dev/null 2>&1 || true
