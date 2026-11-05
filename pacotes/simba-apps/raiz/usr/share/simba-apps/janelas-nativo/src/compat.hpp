#pragma once
// Compatibilidade Hyprland 0.56 ⇄ 0.57.
//
// A 0.57 dividiu a janela em backends (Wayland/X11), metadados e apresentação; os campos que
// o plugin lia direto (m_xdgSurface, m_xwaylandSurface, m_class, m_isX11, rounding()...) viraram
// acessores ou ficaram privados. Todo acesso do plugin à janela passa por hc::*, que escolhe o
// caminho de cada versão (JANELAS_HL057, decidido em janelas.hpp pelos cabeçalhos instalados).

#if JANELAS_HL057
#include <hyprland/src/desktop/view/window/WaylandBackend.hpp>
#include <hyprland/src/desktop/view/window/X11Backend.hpp>
#include <hyprland/src/desktop/view/window/WindowMetadata.hpp>
#include <hyprland/src/desktop/view/window/WindowPresentation.hpp>
#include <hyprland/src/workspace/AbstractWorkspace.hpp>
#include <hyprland/src/render/types.hpp>
#endif

// Desenho: a 0.57 passa um contexto de render explícito (antes era estado global).
#if JANELAS_HL057
#define JN_CTX_P Render::CRenderContext &ctx,
#define JN_CTX ctx,
#define JN_RET Render::GL::CHyprOpenGLImpl::SRectRenderData
#define JN_TEX Render::GL::CHyprOpenGLImpl::STextureRenderData
#else
#define JN_CTX_P
#define JN_CTX
#define JN_RET Render::GL::CHyprOpenGLImpl::SRectRenderData
#define JN_TEX Render::GL::CHyprOpenGLImpl::STextureRenderData
#endif

namespace hc {

    // definidos em main.cpp (JANELAS_COMPAT_IMPL): na 0.57 leem membros privados dos backends
    SP<CXDGSurfaceResource> xdg(const PHLWINDOW& w);
    SP<CXWaylandSurface>    x11(const PHLWINDOW& w);
    // objeto zxdg_toplevel_decoration_v1 da decoração (privado no Hyprland)
    SP<CZxdgToplevelDecorationV1> recursoDecoracao(CXDGDecoration* d);
    // protocolo KDE (GTK3): gerentes ligados e objeto de cada decoração (privados)
    std::vector<UP<COrgKdeKwinServerDecorationManager>>* gerentesKde(CServerDecorationKDEProtocol* p);
    SP<COrgKdeKwinServerDecoration>                      recursoKde(CServerDecorationKDE* d);
    std::vector<UP<CServerDecorationKDE>>*               decoracoesKde(CServerDecorationKDEProtocol* p);

    inline bool ehX11(const PHLWINDOW& w) {
#if JANELAS_HL057
        return w && w->backend().isX11();
#else
        return w && w->m_isX11;
#endif
    }

    inline SP<CXDGToplevelResource> toplevel(const PHLWINDOW& w) {
        const auto X = xdg(w);
        return X ? X->m_toplevel.lock() : nullptr;
    }

    inline std::string classe(const PHLWINDOW& w) {
#if JANELAS_HL057
        return w ? w->metadata().appID() : "";
#else
        return w ? w->m_class : "";
#endif
    }

    inline std::string classeInicial(const PHLWINDOW& w) {
#if JANELAS_HL057
        return w ? w->metadata().initialAppID() : "";
#else
        return w ? w->m_initialClass : "";
#endif
    }

    inline bool mapeada(const PHLWINDOW& w) {
#if JANELAS_HL057
        return w && w->mapped();
#else
        return w && w->m_isMapped;
#endif
    }

    // X11 override-redirect (menus, dicas)
    inline bool overrideRedirect(const PHLWINDOW& w) {
#if JANELAS_HL057
        return w && w->backend().isX11() && w->backend().traits().overrideRedirect;
#else
        return w && w->isX11OverrideRedirect();
#endif
    }

    // X11 que o próprio Hyprland já trata como sem bordas (menus, dicas, splash)
    inline bool x11SemBordasHyprland(const PHLWINDOW& w) {
#if JANELAS_HL057
        return w && w->backend().isX11() && w->backend().traits().suggestsNoBorder;
#else
        return w && w->m_X11DoesntWantBorders;
#endif
    }

    inline SP<Desktop::View::CPopup> popups(const PHLWINDOW& w) {
#if JANELAS_HL057
        return w ? w->popupHead() : nullptr;
#else
        return w ? w->m_popupHead : nullptr;
#endif
    }

    inline bool temDecoracao(const PHLWINDOW& w, const std::string& nome) {
#if JANELAS_HL057
        for (const auto& d : w->presentation().decorations())
#else
        for (const auto& d : w->m_windowDecorations)
#endif
            if (d && d->getDisplayName() == nome)
                return true;
        return false;
    }

    inline void suprimirMaximizar(const PHLWINDOW& w) {
#if JANELAS_HL057
        (void)w; // 0.57: só pela regra suppress_event = "maximize" (o Simba põe em toda janela)
#else
        w->m_suppressedEvents |= Desktop::View::SUPPRESS_MAXIMIZE;
#endif
    }

    inline void atualizarDecoracoes(const PHLWINDOW& w) {
#if JANELAS_HL057
        w->presentation().updateDecorations();
#else
        w->updateWindowDecos();
#endif
    }

    inline bool flutuante(const PHLWINDOW& w) {
#if JANELAS_HL057
        return w->isFloating();
#else
        return w->m_isFloating;
#endif
    }

    inline bool fixada(const PHLWINDOW& w) {
#if JANELAS_HL057
        return (bool)(w->m_state & Desktop::View::WINDOW_STATE_PINNED);
#else
        return w->m_pinned;
#endif
    }

    inline float arredondamento(const PHLWINDOW& w) {
#if JANELAS_HL057
        return w->presentation().rounding();
#else
        return w->rounding();
#endif
    }

    inline float potenciaArredondamento(const PHLWINDOW& w) {
#if JANELAS_HL057
        return w->presentation().roundingPower();
#else
        return w->roundingPower();
#endif
    }

    inline int borda(const PHLWINDOW& w) {
#if JANELAS_HL057
        return w->presentation().borderSize();
#else
        return w->getRealBorderSize();
#endif
    }

    inline Vector2D deslocamentoFlutuante(const PHLWINDOW& w) {
#if JANELAS_HL057
        return w->presentation().floatingOffset();
#else
        return w->m_floatingOffset;
#endif
    }

    inline bool wsEspecial(const PHLWORKSPACE& ws) {
#if JANELAS_HL057
        return ws && ws->type() == Workspace::eWorkspaceType::SPECIAL;
#else
        return ws && ws->m_isSpecialWorkspace;
#endif
    }

    inline std::string wsNome(const PHLWORKSPACE& ws) {
#if JANELAS_HL057
        return ws ? ws->addressableName() : "?";
#else
        return ws ? ws->m_name : "?";
#endif
    }

    inline bool wsMinimizadas(const PHLWORKSPACE& ws) {
        if (!wsEspecial(ws))
            return false;
#if JANELAS_HL057
        return ws->addressableName() == "special:minimizadas" || ws->displayName() == "special:minimizadas" || ws->displayName() == "minimizadas";
#else
        return ws->m_name == "special:minimizadas";
#endif
    }

    inline uint32_t interatividadeTeclado(CLayerShellResource* ls) {
#if JANELAS_HL057
        return ls->m_current.keyboardInteractivity;
#else
        return ls->m_current.interactivity;
#endif
    }

    inline bool camadasExclusivas() {
#if JANELAS_HL057
        return !g_pInputManager->m_exclusiveKeyboardLSes.empty();
#else
        return !g_pInputManager->m_exclusiveLSes.empty();
#endif
    }

    inline size_t numCamadasExclusivas() {
#if JANELAS_HL057
        return g_pInputManager->m_exclusiveKeyboardLSes.size();
#else
        return g_pInputManager->m_exclusiveLSes.size();
#endif
    }
}

#ifdef JANELAS_COMPAT_IMPL
namespace hc {
    template <typename Tag, typename Tag::type M>
    struct SRoubarDeco {
        friend typename Tag::type pegar(Tag) {
            return M;
        }
    };
    struct STagDeco {
        using type = SP<CZxdgToplevelDecorationV1> CXDGDecoration::*;
        friend type pegar(STagDeco);
    };
    template struct SRoubarDeco<STagDeco, &CXDGDecoration::m_resource>;
    SP<CZxdgToplevelDecorationV1> recursoDecoracao(CXDGDecoration* d) {
        return d ? d->*pegar(STagDeco{}) : nullptr;
    }
    struct STagKdeGer {
        using type = std::vector<UP<COrgKdeKwinServerDecorationManager>> CServerDecorationKDEProtocol::*;
        friend type pegar(STagKdeGer);
    };
    template struct SRoubarDeco<STagKdeGer, &CServerDecorationKDEProtocol::m_managers>;
    struct STagKdeDecos {
        using type = std::vector<UP<CServerDecorationKDE>> CServerDecorationKDEProtocol::*;
        friend type pegar(STagKdeDecos);
    };
    template struct SRoubarDeco<STagKdeDecos, &CServerDecorationKDEProtocol::m_decos>;
    struct STagKdeRes {
        using type = SP<COrgKdeKwinServerDecoration> CServerDecorationKDE::*;
        friend type pegar(STagKdeRes);
    };
    template struct SRoubarDeco<STagKdeRes, &CServerDecorationKDE::m_resource>;
    std::vector<UP<COrgKdeKwinServerDecorationManager>>* gerentesKde(CServerDecorationKDEProtocol* p) {
        return p ? &(p->*pegar(STagKdeGer{})) : nullptr;
    }
    std::vector<UP<CServerDecorationKDE>>* decoracoesKde(CServerDecorationKDEProtocol* p) {
        return p ? &(p->*pegar(STagKdeDecos{})) : nullptr;
    }
    SP<COrgKdeKwinServerDecoration> recursoKde(CServerDecorationKDE* d) {
        return d ? d->*pegar(STagKdeRes{}) : nullptr;
    }
#if JANELAS_HL057
    // Acesso a membro privado sem macros: instanciação explícita de template pode nomear membros
    // privados (C++ [temp.spec]/6). Só leitura de ponteiros fracos que o próprio Hyprland guarda.
    template <typename Tag, typename Tag::type M>
    struct SRoubar {
        friend typename Tag::type pegar(Tag) {
            return M;
        }
    };
    struct STagX11 {
        using type = WP<CXWaylandSurface> Desktop::View::CX11Backend::*;
        friend type pegar(STagX11);
    };
    template struct SRoubar<STagX11, &Desktop::View::CX11Backend::m_xwaylandSurface>;
    struct STagXdg {
        using type = WP<CXDGSurfaceResource> Desktop::View::CWaylandBackend::*;
        friend type pegar(STagXdg);
    };
    template struct SRoubar<STagXdg, &Desktop::View::CWaylandBackend::m_resource>;
#endif

    SP<CXDGSurfaceResource> xdg(const PHLWINDOW& w) {
        if (!w)
            return nullptr;
#if JANELAS_HL057
        if (w->backend().isX11())
            return nullptr;
        auto* B = dynamic_cast<Desktop::View::CWaylandBackend*>(&w->backend());
        return B ? (B->*pegar(STagXdg{})).lock() : nullptr;
#else
        return w->m_xdgSurface.lock();
#endif
    }

    SP<CXWaylandSurface> x11(const PHLWINDOW& w) {
        if (!w)
            return nullptr;
#if JANELAS_HL057
        if (!w->backend().isX11())
            return nullptr;
        auto* B = dynamic_cast<Desktop::View::CX11Backend*>(&w->backend());
        return B ? (B->*pegar(STagX11{})).lock() : nullptr;
#else
        return w->m_xwaylandSurface.lock();
#endif
    }

}
#endif
