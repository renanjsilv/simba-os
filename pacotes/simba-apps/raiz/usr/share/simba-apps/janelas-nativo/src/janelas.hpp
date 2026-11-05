// janelas-nativo: barras de título e controles de janela estilo Windows 11 desenhados pelo
// próprio Hyprland, decididos pelo protocolo de decoração que o app negocia.
// Ver ~/.local/share/janelas-nativo/LEIAME (resumo no topo de main.cpp).
#pragma once

#define WLR_USE_UNSTABLE

#include <algorithm>
#include <any>
#include <array>
#include <chrono>
#include <cmath>
#include <deque>
#include <expected>
#include <filesystem>
#include <format>
#include <fstream>
#include <functional>
#include <list>
#include <map>
#include <memory>
#include <optional>
#include <ranges>
#include <regex>
#include <set>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <variant>
#include <vector>

#include <cairo/cairo.h>
#include <wayland-server.h>

// Membros privados do protocolo de decoração: o plugin responde ao modo que o app pede
// (o Hyprland responde sempre "lado do servidor"), então precisa mexer neles.
#define private public
#define protected public
#include <hyprland/src/protocols/XDGDecoration.hpp>
#include <hyprland/src/protocols/ServerDecorationKDE.hpp>
#include <hyprland/src/protocols/XDGShell.hpp>
#include <hyprland/src/managers/SeatManager.hpp>
#include <hyprland/src/xwayland/XWM.hpp>
#undef private
#undef protected

#include <hyprland/src/plugins/PluginAPI.hpp>
#include <hyprland/src/Compositor.hpp>
// Hyprland 0.57 reorganizou a janela (desktop/view/window/, backends Wayland/X11) e tirou o
// KeybindManager. JANELAS_HL057 marca o código de cada versão (o resto é igual).
#if __has_include(<hyprland/src/desktop/view/window/Window.hpp>)
#define JANELAS_HL057 1
#include <hyprland/src/desktop/view/window/Window.hpp>
#else
#define JANELAS_HL057 0
#include <hyprland/src/desktop/view/Window.hpp>
#endif
#include <hyprland/src/desktop/view/LayerSurface.hpp>
#include <hyprland/src/desktop/view/Popup.hpp>
#include <hyprland/src/desktop/view/WLSurface.hpp>
#include <hyprland/src/desktop/state/FocusState.hpp>
#include <hyprland/src/desktop/state/WindowState.hpp>
#include <hyprland/src/desktop/state/LayerState.hpp>
#include <hyprland/src/desktop/state/ViewState.hpp>
#include <hyprland/src/desktop/state/ViewHitTester.hpp>
#include <hyprland/src/protocols/XDGShell.hpp>
#include <hyprland/src/protocols/LayerShell.hpp>
#include <hyprland/src/protocols/core/Compositor.hpp>
#include <hyprland/src/xwayland/XSurface.hpp>
#include <hyprland/src/xwayland/XWayland.hpp>
#include <hyprland/src/managers/SeatManager.hpp>
#include <hyprland/src/managers/SessionLockManager.hpp>
#include <hyprland/src/managers/input/InputManager.hpp>
#include <hyprland/src/managers/eventLoop/EventLoopManager.hpp>
#include <hyprland/src/managers/fullscreen/FullscreenController.hpp>
#include <hyprland/src/render/Renderer.hpp>
#include <hyprland/src/render/OpenGL.hpp>
#include <hyprland/src/render/decorations/IHyprWindowDecoration.hpp>
#include <hyprland/src/render/decorations/DecorationPositioner.hpp>
#include <hyprland/src/render/pass/PassElement.hpp>
#include <hyprland/src/render/pass/SurfacePassElement.hpp>
#include <hyprland/src/config/ConfigManager.hpp>
#include <hyprland/src/config/ConfigValue.hpp>
#include <hyprland/src/config/supplementary/executor/Executor.hpp>
#include <hyprland/src/event/EventBus.hpp>
#include <hyprland/src/helpers/time/Time.hpp>
#include <hyprland/src/helpers/signal/Signal.hpp>
#include <hyprland/src/state/MonitorState.hpp>
#include <hyprland/src/layout/LayoutManager.hpp>
#include <hyprland/src/layout/supplementary/DragController.hpp>
#include "compat.hpp"

extern "C" {
#include <lua.h>
#include <lauxlib.h>
}

inline HANDLE PHANDLE = nullptr;

// Como o app quer ser decorado (resultado da negociação de protocolo).
enum eModoDeco : uint8_t {
    DECO_SERVIDOR = 0, // xdg-decoration/KDE pediram (ou aceitaram) decoração do servidor: barra nossa
    DECO_CLIENTE,      // o app pediu para desenhar a própria (GTK com headerbar, Chromium, Electron...)
    DECO_NENHUM,       // não negociou nada (GTK4/libadwaita, SDL sem decoração...): desenha a própria
    DECO_X11_SIM,      // X11 sem _MOTIF_WM_HINTS desligando bordas: barra nossa
    DECO_X11_NAO,      // X11 que pediu sem bordas (Steam, Chrome X11, override-redirect)
};

struct SInfoDeco {
    eModoDeco   modo = DECO_NENHUM;
    std::string motivo;
};

SInfoDeco   modoDecoracao(PHLWINDOW w);
bool        barraForcada(PHLWINDOW w, bool& mostrar); // config ~/.config/janelas-nativo/regras
bool        barraDeveAparecer(PHLWINDOW w);
bool        x11SemBordas(PHLWINDOW w);
std::string enderecoDe(PHLWINDOW w);

// Estado do janelas.lua informado por hl.plugin.janelas.estado(addr, modo).
enum eEstadoJanela : uint8_t {
    EST_SOLTA = 0,
    EST_MAX,
    EST_ZONA,
};
eEstadoJanela estadoJanela(PHLWINDOW w);

// Ações: chamam janelas.lua (hyprctl dispatch 'janelas.pedido(addr, acao)'), com
// alternativa interna se o Lua não responder.
void pedirAcao(PHLWINDOW w, const std::string& acao, const std::string& extra = "");

// Cores do tema do Simba (~/.local/state/simba/current/theme/colors.toml).
struct STema {
    CHyprColor fundo     = CHyprColor(0.12, 0.12, 0.12, 1.0);
    CHyprColor frente    = CHyprColor(1.0, 1.0, 1.0, 1.0);
    CHyprColor realce    = CHyprColor(0.55, 0.55, 0.55, 1.0);
    bool       claro     = false;
    std::string fonte    = "Sans";
};
STema& tema();
void   lerTema();

class CBarra;
struct SEstadoGlobal {
    std::vector<WP<CBarra>>                    barras;
    std::unordered_map<uintptr_t, eEstadoJanela> estados; // CWindow* → estado do janelas.lua
    std::unordered_map<uintptr_t, CHyprSignalListener> ouvintesEstado;
    std::unordered_map<uintptr_t, bool>         x11SemBordas; // _MOTIF_WM_HINTS lido no mapeamento
    std::unordered_map<uintptr_t, bool>         forcadas;     // hyprctl janelas forcar <addr> sim|nao (só esta janela)
    // Estado xdg "maximized" verdadeiro (só ligado quando o janelas.lua diz "max"): o botão
    // maximizar/restaurar do app mostra o ícone certo e manda set/unset coerente. Janela que,
    // fora de maximizada, desenha sombra com deslocamento (xdg_surface.set_window_geometry
    // com x/y > 0, que o Hyprland não aplica) volta ao "sempre maximizada" do Hyprland.
    std::unordered_map<uintptr_t, CHyprSignalListener> ouvintesCommit;
    std::unordered_set<uintptr_t>               sempreMax;    // janelas com deslocamento de sombra
    std::unordered_set<std::string>             classesSempreMax; // idem, lembrado por classe
    bool                                        estadoReal = true; // hyprctl janelas estadoreal on|off
    std::vector<std::pair<std::regex, bool>>   regras; // classe → mostrar(true)/ocultar(false)
    std::string                                textoRegras;
    bool                                       habilitado = true;
};
inline UP<SEstadoGlobal> g;

// Medidas da barra (pixels lógicos), como a barra de título do Windows 11.
constexpr int ALTURA_BARRA  = 24;
constexpr int LARGURA_BOTAO = 36;
