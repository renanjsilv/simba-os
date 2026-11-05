-- Volume, brightness, keyboard backlight, and touchpad controls.
o.bind("XF86AudioRaiseVolume", "Aumentar volume", "simba-audio-output-volume raise", { locked = true, repeating = true })
o.bind("XF86AudioLowerVolume", "Diminuir volume", "simba-audio-output-volume lower", { locked = true, repeating = true })
o.bind("XF86AudioMute", "Silenciar", "simba-audio-output-volume mute-toggle", { locked = true })
o.bind("XF86AudioMicMute", "Silenciar microfone", "simba-audio-input-mute", { locked = true })
o.bind("XF86MonBrightnessUp", "Aumentar brilho", "simba-brightness-display +5%", { locked = true, repeating = true })
o.bind("XF86MonBrightnessDown", "Diminuir brilho", "simba-brightness-display 5%-", { locked = true, repeating = true })
o.bind("SHIFT + XF86MonBrightnessUp", "Brilho máximo", "simba-brightness-display 100%", { locked = true, repeating = true })
o.bind("SHIFT + XF86MonBrightnessDown", "Brilho mínimo", "simba-brightness-display 1%", { locked = true, repeating = true })
o.bind("XF86KbdBrightnessUp", "Aumentar luz do teclado", "simba-brightness-keyboard up", { locked = true, repeating = true })
o.bind("XF86KbdBrightnessDown", "Diminuir luz do teclado", "simba-brightness-keyboard down", { locked = true, repeating = true })
o.bind("XF86KbdLightOnOff", "Alternar luz do teclado", "simba-brightness-keyboard cycle", { locked = true })
o.bind_toggle("XF86TouchpadToggle", "Ativar/desativar touchpad", "touchpad", { locked = true })
o.bind("XF86TouchpadOn", "Ativar touchpad", "simba-toggle-touchpad on", { locked = true })
o.bind("XF86TouchpadOff", "Desativar touchpad", "simba-toggle-touchpad off", { locked = true })

-- Precise volume and brightness controls.
o.bind("ALT + XF86AudioRaiseVolume", "Aumentar volume (fino)", "simba-audio-output-volume +1", { locked = true, repeating = true })
o.bind("ALT + XF86AudioLowerVolume", "Diminuir volume (fino)", "simba-audio-output-volume -1", { locked = true, repeating = true })
o.bind("ALT + XF86MonBrightnessUp", "Aumentar brilho (fino)", "simba-brightness-display +1%", { locked = true, repeating = true })
o.bind("ALT + XF86MonBrightnessDown", "Diminuir brilho (fino)", "simba-brightness-display 1%-", { locked = true, repeating = true })

-- Media controls.
o.bind("XF86AudioNext", "Próxima faixa", "simba-shell media next", { locked = true })
o.bind("ALT + XF86AudioPlay", "Próxima faixa", "simba-shell media next", { locked = true })
o.bind("XF86AudioPause", "Pausar", "simba-shell media playPause", { locked = true })
o.bind("XF86AudioPlay", "Reproduzir", "simba-shell media playPause", { locked = true })
o.bind("XF86AudioPrev", "Faixa anterior", "simba-shell media previous", { locked = true })
o.bind("ALT + SHIFT + XF86AudioPlay", "Faixa anterior", "simba-shell media previous", { locked = true })
o.bind("XF86Eject", "Ejetar mídia", "eject", { locked = true })

o.bind("SHIFT + XF86AudioMute", "Trocar saída de áudio", "simba-audio-output-switch", { locked = true })
o.bind("SHIFT + XF86AudioPause", "Trocar fonte de mídia", "simba-audio-source-switch", { locked = true })
o.bind("SHIFT + XF86AudioPlay", "Trocar fonte de mídia", "simba-audio-source-switch", { locked = true })
