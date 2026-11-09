-- Extra autostart processes.
-- o.launch_on_start("my-service")

-- Draco on-screen orb, preloaded so F10 shows it instantly.
o.launch_on_start("qs -c draco -n")
-- Draco speech server: keeps the Piper voice loaded so replies start instantly.
o.launch_on_start("draco servidor-voz")
-- Configurações (~/.config/quickshell/configuracoes): settings window, Super+P
-- display switcher and the desktop layer (right-click menu + icons), preloaded.
o.launch_on_start("env QT_WAYLAND_DISABLE_WINDOWDECORATION=1 qs -c configuracoes -n")
-- Primeira inicialização após formatar (instalada pela ISO): boas-vindas da conta
-- Google em Configurações › Contas. Não faz nada nas outras vezes.
o.launch_on_start("/usr/bin/conta-boas-vindas")
-- Simba OS: apresentação do sistema só na primeira inicialização (marcador em
-- ~/.local/state/simba/boas-vindas-vista, nunca levado na ISO).
o.launch_on_start("/usr/bin/boas-vindas --primeira-vez")
-- Barras de título e botões de janela estilo Windows 11 desenhados pelo Hyprland (plugin
-- ~/.local/share/janelas-nativo; recompila sozinho quando o Hyprland é atualizado).
o.launch_on_start("/usr/share/simba-apps/janelas-nativo/janelas-nativo carregar")
