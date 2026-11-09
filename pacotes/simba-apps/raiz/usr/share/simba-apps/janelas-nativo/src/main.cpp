// janelas-nativo — controles de janela nativos do compositor (Hyprland 0.56, config Lua).
//
// 1. Decoração decidida pelo protocolo. O app diz como quer ser decorado:
//    - xdg-decoration: pede "servidor" (Qt, foot, mpv, SDL, Firefox com barra do sistema...)
//      ou "cliente" (Chromium/Brave/Electron com barra própria). A barra só aparece para quem
//      pediu (ou aceitou) "servidor". (O Hyprland responde "servidor" a todos — ver abaixo.)
//    - org_kde_kwin_server_decoration (GTK3): idem.
//    - nenhum dos dois (GTK4/libadwaita): o app desenha os próprios botões; sem barra.
//    - X11: sem barra se _MOTIF_WM_HINTS pede sem bordas (Steam, Chrome X11, AnyDesk).
//    Resultado: toda janela tem exatamente um conjunto de botões.
// 2. Pedidos do próprio app (botões nativos, duplo clique no título, atalhos do app):
//    xdg_toplevel.set_minimized / set_maximized / unset_maximized e os equivalentes X11
//    (WM_CHANGE_STATE, _NET_WM_STATE) vão para o janelas.lua (minimizar, alternar).
//    O botão maximizar do app alterna maximizada ⇄ restaurada pelo estado do janelas.lua.
// 3. Foco de teclado: com input.follow_mouse = 0 (foco no clique) o Hyprland ainda dá o
//    teclado a camadas "on-demand" (área de trabalho do Configurações) só de passar o mouse,
//    sem trocar a janela ativa; depois, clicar na janela não devolve o teclado porque para
//    o Hyprland ela já está em foco. Aqui: passar o mouse não tira o teclado de ninguém, e
//    clicar numa janela/camada garante o teclado nela.
//
// hyprctl janelas foco | lista | recarregar     (diagnóstico)
// Lua: hl.plugin.janelas.estado(addr, "max"|"zona"|"solta"), hl.plugin.janelas.barra(addr)
#define JANELAS_COMPAT_IMPL
#include "janelas.hpp"
#include "barra.hpp"

#include <linux/input-event-codes.h>

APICALL EXPORT std::string PLUGIN_API_VERSION() {
    return HYPRLAND_API_VERSION;
}

// ── utilidades ────────────────────────────────────────────────────────────────

// últimos eventos (hyprctl janelas eventos): pedidos dos apps, ações, correções de foco
static std::deque<std::string> g_eventos;
static std::vector<std::regex>  g_regrasCliente;  // config.json "cliente": app_id que recebe decoração do cliente
static std::vector<std::regex>  g_regrasServidor; // config.json "servidor": processo (comm) que fica com a do servidor (GTK3)
static void registrar(const std::string& s) {
    const auto T  = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
    char       buf[16];
    std::strftime(buf, sizeof(buf), "%H:%M:%S", std::localtime(&T));
    g_eventos.emplace_back(std::format("{} {}", buf, s));
    while (g_eventos.size() > 40)
        g_eventos.pop_front();
}

std::string enderecoDe(PHLWINDOW w) {
    return std::format("0x{:x}", (uintptr_t)w.get());
}

static PHLWINDOW janelaPorEndereco(const std::string& s) {
    std::string a = s;
    if (a.starts_with("address:"))
        a = a.substr(8);
    if (a.starts_with("0x"))
        a = a.substr(2);
    uintptr_t v = 0;
    try {
        v = std::stoull(a, nullptr, 16);
    } catch (...) { return nullptr; }
    for (const auto& w : Desktop::windowState()->windows())
        if ((uintptr_t)w.get() == v)
            return w;
    return nullptr;
}

static PHLWINDOW janelaDaSuperficie(SP<CWLSurfaceResource> s) {
    if (!s)
        return nullptr;
    const auto HL = Desktop::View::CWLSurface::fromResource(s);
    if (!HL || !HL->view())
        return nullptr;
    if (auto w = Desktop::View::CWindow::fromView(HL->view()))
        return w;
    if (auto p = Desktop::View::CPopup::fromView(HL->view())) {
        const auto T1 = p->getT1Owner();
        if (T1 && T1->view())
            return Desktop::View::CWindow::fromView(T1->view());
    }
    return nullptr;
}

static PHLLS camadaDaSuperficie(SP<CWLSurfaceResource> s) {
    if (!s)
        return nullptr;
    const auto HL = Desktop::View::CWLSurface::fromResource(s);
    if (!HL || !HL->view())
        return nullptr;
    if (auto l = Desktop::View::CLayerSurface::fromView(HL->view()))
        return l;
    if (auto p = Desktop::View::CPopup::fromView(HL->view())) {
        const auto T1 = p->getT1Owner();
        if (T1 && T1->view())
            return Desktop::View::CLayerSurface::fromView(T1->view());
    }
    return nullptr;
}

static CBarra* barraDe(PHLWINDOW w) {
    for (auto& b : g->barras)
        if (b && b->dona() == w)
            return b.get();
    return nullptr;
}

// ── tema ──────────────────────────────────────────────────────────────────────

STema& tema() {
    static STema t;
    return t;
}

static std::optional<CHyprColor> corHex(const std::string& s) {
    std::string h = s;
    if (h.starts_with("#"))
        h = h.substr(1);
    if (h.size() != 6 && h.size() != 8)
        return std::nullopt;
    try {
        const auto V = std::stoul(h.substr(0, 6), nullptr, 16);
        const auto A = h.size() == 8 ? std::stoul(h.substr(6, 2), nullptr, 16) : 255;
        return CHyprColor(((V >> 16) & 0xff) / 255.0, ((V >> 8) & 0xff) / 255.0, (V & 0xff) / 255.0, A / 255.0);
    } catch (...) { return std::nullopt; }
}

void lerTema() {
    auto&             t    = tema();
    const char*       HOME = getenv("HOME");
    const std::string ARQ  = std::string(HOME ? HOME : "") + "/.local/state/simba/current/theme/colors.toml";
    std::ifstream     f(ARQ);
    std::string       linha, modo;
    static const std::regex RE(R"(^\s*([a-z_]+)\s*=\s*"([^"]*)\")");
    while (std::getline(f, linha)) {
        std::smatch m;
        if (!std::regex_search(linha, m, RE))
            continue;
        const auto K = m[1].str(), V = m[2].str();
        if (K == "mode")
            modo = V;
        else if (K == "background") {
            if (auto c = corHex(V))
                t.fundo = *c;
        } else if (K == "foreground") {
            if (auto c = corHex(V))
                t.frente = *c;
        } else if (K == "accent") {
            if (auto c = corHex(V))
                t.realce = *c;
        }
    }
    const double LUM = 0.2126 * t.fundo.r + 0.7152 * t.fundo.g + 0.0722 * t.fundo.b;
    t.claro          = modo.empty() ? LUM > 0.5 : modo == "light";

    // fonte da interface (a mesma dos apps GTK)
    if (FILE* p = popen("gsettings get org.gnome.desktop.interface font-name 2>/dev/null", "r")) {
        char buf[256] = {0};
        if (fgets(buf, sizeof(buf), p)) {
            std::string s = buf;
            std::erase(s, '\'');
            std::erase(s, '\n');
            // "Adwaita Sans 11" → "Adwaita Sans"
            if (auto pos = s.find_last_of(' '); pos != std::string::npos && pos + 1 < s.size() && std::isdigit((unsigned char)s[pos + 1]))
                s = s.substr(0, pos);
            if (!s.empty())
                t.fonte = s;
        }
        pclose(p);
    }
}

// ── regras por classe ─────────────────────────────────────────────────────────
// ~/.config/botoes-janela/config.json {"mostrar": [regex...], "ocultar": [regex...]} — o
// mesmo arquivo de Configurações › Janelas › Botões de janela. Para apps que negociam uma
// coisa e fazem outra; normalmente vazio. Relido quando muda (no máximo 1×/s).

static std::string arquivoRegras() {
    const char* HOME = getenv("HOME");
    return std::string(HOME ? HOME : "") + "/.config/botoes-janela/config.json";
}

static void lerRegras() {
    g->regras.clear();
    g_regrasCliente.clear();
    g_regrasServidor.clear();
    std::ifstream     f(arquivoRegras());
    std::stringstream ss;
    ss << f.rdbuf();
    const std::string TXT = ss.str();
    for (const auto& [chave, mostrar] : {std::pair{"mostrar", 1}, std::pair{"ocultar", 0}, std::pair{"cliente", 2}, std::pair{"servidor", 3}}) {
        const std::regex RE(std::string("\"") + chave + "\"\\s*:\\s*\\[([^\\]]*)\\]");
        std::smatch      m;
        if (!std::regex_search(TXT, m, RE))
            continue;
        const std::string LISTA = m[1].str();
        static const std::regex ITEM(R"re("((?:[^"\\]|\\.)*)")re");
        for (auto it = std::sregex_iterator(LISTA.begin(), LISTA.end(), ITEM); it != std::sregex_iterator(); ++it) {
            std::string v = (*it)[1].str();
            // desfaz escapes do JSON (\\ → \)
            std::string r;
            for (size_t i = 0; i < v.size(); ++i) {
                if (v[i] == '\\' && i + 1 < v.size())
                    ++i;
                r += v[i];
            }
            try {
                if (mostrar == 2)
                    g_regrasCliente.emplace_back(r);
                else if (mostrar == 3)
                    g_regrasServidor.emplace_back(r);
                else
                    g->regras.emplace_back(std::regex(r), mostrar == 1);
            } catch (...) {}
        }
    }
}

static void conferirRegras() {
    static auto ULTIMA = std::chrono::steady_clock::now() - std::chrono::seconds(10);
    static std::filesystem::file_time_type MTIME{};
    const auto AGORA = std::chrono::steady_clock::now();
    if (AGORA - ULTIMA < std::chrono::seconds(1))
        return;
    ULTIMA = AGORA;
    std::error_code ec;
    const auto      MT = std::filesystem::last_write_time(arquivoRegras(), ec);
    if (ec || MT == MTIME)
        return;
    MTIME = MT;
    lerRegras();
}

bool barraForcada(PHLWINDOW w, bool& mostrar) {
    if (const auto IT = g->forcadas.find((uintptr_t)w.get()); IT != g->forcadas.end()) {
        mostrar = IT->second;
        return true;
    }
    conferirRegras();
    for (const auto& [re, m] : g->regras) {
        if (std::regex_search(hc::classe(w), re) || std::regex_search(hc::classeInicial(w), re)) {
            mostrar = m;
            return true;
        }
    }
    return false;
}

// ── negociação de decoração ───────────────────────────────────────────────────

static void decoracaoMudou(wl_resource* toplevel, SP<CWLSurfaceResource> superficie);

// X11: o app desliga as decorações do gerenciador com _MOTIF_WM_HINTS (decorations = 0) —
// GTK3 com headerbar, Chrome/Electron X11, Steam, Wine sem moldura. O Hyprland não lê isso.
static bool lerMotif(PHLWINDOW w) {
    if (!g_pXWayland || !g_pXWayland->m_wm || !hc::x11(w))
        return false;
    auto* C = g_pXWayland->m_wm->getConnection();
    if (!C || !HYPRATOMS.contains("_MOTIF_WM_HINTS"))
        return false;
    const auto COOKIE = xcb_get_property(C, 0, hc::x11(w)->m_xID, HYPRATOMS["_MOTIF_WM_HINTS"], XCB_GET_PROPERTY_TYPE_ANY, 0, 5);
    auto*      R      = xcb_get_property_reply(C, COOKIE, nullptr);
    if (!R)
        return false;
    bool       sem = false;
    const auto N   = xcb_get_property_value_length(R) / 4;
    if (R->format == 32 && N >= 3) {
        const auto* V = (const uint32_t*)xcb_get_property_value(R);
        sem           = (V[0] & 2) && V[2] == 0; // MWM_HINTS_DECORATIONS e nenhuma decoração
    }
    free(R);
    return sem;
}

bool x11SemBordas(PHLWINDOW w) {
    const auto K  = (uintptr_t)w.get();
    const auto IT = g->x11SemBordas.find(K);
    if (IT != g->x11SemBordas.end())
        return IT->second;
    const bool SEM     = lerMotif(w);
    g->x11SemBordas[K] = SEM;
    return SEM;
}

SInfoDeco modoDecoracao(PHLWINDOW w) {
    SInfoDeco r;
    if (!w)
        return r;

    if (hc::ehX11(w)) {
        if (hc::overrideRedirect(w))
            return {DECO_X11_NAO, "x11 override-redirect"};
        if (hc::x11SemBordasHyprland(w))
            return {DECO_X11_NAO, "x11 menu/dica/splash"};
        if (x11SemBordas(w))
            return {DECO_X11_NAO, "x11 _MOTIF_WM_HINTS sem decoração (desenha a própria)"};
        return {DECO_X11_SIM, "x11 com bordas do gerenciador"};
    }

    if (!hc::xdg(w) || !hc::toplevel(w))
        return {DECO_NENHUM, "sem xdg_toplevel"};

    const auto TL = hc::toplevel(w);
    if (PROTO::xdgDecoration) {
        for (const auto& [res, deco] : PROTO::xdgDecoration->m_decorations) {
            if (!deco || CXDGToplevelResource::fromResource(res) != TL)
                continue;
            if (deco->mostRecentlyRequested == ZXDG_TOPLEVEL_DECORATION_V1_MODE_CLIENT_SIDE)
                return {DECO_CLIENTE, "xdg-decoration: app pediu lado do cliente"};
            if (deco->mostRecentlySent == ZXDG_TOPLEVEL_DECORATION_V1_MODE_CLIENT_SIDE)
                return {DECO_CLIENTE, "xdg-decoration: lado do cliente (regra \"cliente\")"};
            return {DECO_SERVIDOR, deco->mostRecentlyRequested == ZXDG_TOPLEVEL_DECORATION_V1_MODE_SERVER_SIDE ? "xdg-decoration: app pediu lado do servidor" :
                                                                                                                   "xdg-decoration: app aceita o padrão (servidor)"};
        }
    }

    const auto SURF = w->wlSurface() ? w->wlSurface()->resource() : nullptr;
    if (PROTO::serverDecorationKDE && SURF) {
        for (const auto& d : PROTO::serverDecorationKDE->m_decos) {
            if (!d || d->m_surf != SURF)
                continue;
            if (d->m_mostRecentlyRequested == ORG_KDE_KWIN_SERVER_DECORATION_MANAGER_MODE_CLIENT ||
                (d->m_mostRecentlyRequested == ORG_KDE_KWIN_SERVER_DECORATION_MANAGER_MODE_NONE && d->m_mostRecentlySent != ORG_KDE_KWIN_SERVER_DECORATION_MANAGER_MODE_SERVER))
                return {DECO_CLIENTE, "kde-server-decoration: app pediu lado do cliente"};
            return {DECO_SERVIDOR, "kde-server-decoration: lado do servidor"};
        }
    }

    return {DECO_NENHUM, "não negociou decoração (desenha a própria)"};
}

// O Hyprland responde "servidor" a todo pedido de modo (e grava o que o app pediu em
// mostRecentlyRequested). Responder "cliente" faria o GTK3/Chromium desenharem sombra com
// deslocamento de xdg_surface.set_window_geometry, que o Hyprland não aplica na janela
// principal (FIXME em render/ElementRenderer.cpp) — a janela apareceria deslocada. Então a
// resposta continua a do Hyprland; o que decide a barra é o pedido do app, que segue
// desenhando a própria barra de título (headerbar, abas do Chromium...). Os hooks abaixo só
// avisam quando um objeto de decoração nasce, para reavaliar a barra na hora.
typedef void (*tOnGetDecoration)(CXDGDecorationProtocol*, CZxdgDecorationManagerV1*, uint32_t, wl_resource*);
static CFunctionHook* g_hookXdg = nullptr;

// Apps que recebem "decoração do lado do cliente" mesmo pedindo a do servidor (o app desenha a
// própria moldura). Regra "cliente" no config.json (regex do app_id); g_regrasCliente no topo.
static bool querCliente(const std::string& appid) {
    for (const auto& re : g_regrasCliente)
        if (std::regex_search(appid, re))
            return true;
    return false;
}

// Troca as respostas do Hyprland (sempre "servidor") pela regra: o app_id é conferido na hora de
// cada pedido de modo (o Chromium manda set_app_id antes do set_mode, mas depois de criar a
// decoração).
static bool kdeServidor(wl_client* c);

// Qt 6 desenha a própria barra (plugin de decoração "adwaita" do qtwayland) quando o compositor
// responde "cliente": todo app Qt 6 ganha botões nativos sem regra por app. (Qt 5 aqui não tem
// plugins de decoração → fica com a do servidor.) Exceção: regra "servidor" (nome do processo).
static bool g_qtCliente = false; // moldura padrão do Qt destoa: a barra do plugin é a uniforme. // hyprctl janelas qtcsd on|off
static std::unordered_map<wl_client*, bool> g_clientesQt6;
static std::vector<wl_listener*>            g_ouvintesClientes;

static bool clienteQt6(wl_client* c) {
    if (!c)
        return false;
    if (const auto IT = g_clientesQt6.find(c); IT != g_clientesQt6.end())
        return IT->second;
    // o cache some quando o cliente sai (o endereço do wl_client pode ser reaproveitado);
    // os ouvintes são removidos no PLUGIN_EXIT (o código deles some com o plugin)
    auto* L   = new wl_listener;
    L->notify = [](wl_listener* l, void* data) {
        g_clientesQt6.erase((wl_client*)data);
        std::erase(g_ouvintesClientes, l);
        wl_list_remove(&l->link);
        delete l;
    };
    wl_client_add_destroy_listener(c, L);
    g_ouvintesClientes.push_back(L);
    pid_t pid = 0;
    wl_client_get_credentials(c, &pid, nullptr, nullptr);
    std::ifstream f(std::format("/proc/{}/maps", pid));
    std::string   l;
    bool          qt = false;
    while (std::getline(f, l))
        if (l.find("libQt6WaylandClient") != std::string::npos) {
            qt = true;
            break;
        }
    g_clientesQt6[c] = qt;
    return qt;
}

static uint32_t modoPara(CXDGDecoration* deco) {
    const auto TL = CXDGToplevelResource::fromResource(deco->toplevelResource());
    if (!TL)
        return ZXDG_TOPLEVEL_DECORATION_V1_MODE_SERVER_SIDE;
    if (querCliente(TL->m_state.appid))
        return ZXDG_TOPLEVEL_DECORATION_V1_MODE_CLIENT_SIDE;
    const auto C = wl_resource_get_client(deco->toplevelResource());
    if (g_qtCliente && clienteQt6(C) && !kdeServidor(C))
        return ZXDG_TOPLEVEL_DECORATION_V1_MODE_CLIENT_SIDE;
    return ZXDG_TOPLEVEL_DECORATION_V1_MODE_SERVER_SIDE;
}

static void assumirDecoracao(CXDGDecoration* deco) {
    const auto R = hc::recursoDecoracao(deco);
    if (!R)
        return;
    R->setSetMode([deco](CZxdgToplevelDecorationV1* r, zxdgToplevelDecorationV1Mode mode) {
        const auto M = (zxdgToplevelDecorationV1Mode)modoPara(deco);
        r->sendConfigure(M);
        deco->mostRecentlyRequested = mode;
        deco->mostRecentlySent      = M;
        if (M == ZXDG_TOPLEVEL_DECORATION_V1_MODE_CLIENT_SIDE)
            registrar(std::format("decoração do cliente (regra) para {}", CXDGToplevelResource::fromResource(deco->toplevelResource())->m_state.appid));
    });
    R->setUnsetMode([deco](CZxdgToplevelDecorationV1* r) {
        const auto M = (zxdgToplevelDecorationV1Mode)modoPara(deco);
        r->sendConfigure(M);
        deco->mostRecentlyRequested = 0;
        deco->mostRecentlySent      = M;
    });
    const auto M = (zxdgToplevelDecorationV1Mode)modoPara(deco);
    if (M == ZXDG_TOPLEVEL_DECORATION_V1_MODE_CLIENT_SIDE) {
        R->sendConfigure(M);
        deco->mostRecentlySent = M;
    }
}

// o app_id pode chegar depois da decoração (Qt): reavalia quando os metadados mudam
static std::unordered_map<wl_resource*, std::pair<CHyprSignalListener, CHyprSignalListener>> g_ouvintesAppId;

static void reavaliarModo(wl_resource* toplevel) {
    const auto IT = PROTO::xdgDecoration->m_decorations.find(toplevel);
    if (IT == PROTO::xdgDecoration->m_decorations.end() || !IT->second)
        return;
    auto*      deco = IT->second.get();
    const auto M    = modoPara(deco);
    if (deco->mostRecentlySent == M)
        return;
    const auto R = hc::recursoDecoracao(deco);
    if (!R)
        return;
    R->sendConfigure((zxdgToplevelDecorationV1Mode)M);
    deco->mostRecentlySent = M;
    const auto TL = CXDGToplevelResource::fromResource(toplevel);
    if (M == ZXDG_TOPLEVEL_DECORATION_V1_MODE_CLIENT_SIDE)
        registrar(std::format("decoração do cliente (regra) para {}", TL ? TL->m_state.appid : "?"));
    // vale no próximo xdg_surface.configure (que só vai junto de um toplevel configure)
    if (TL && TL->m_owner && !TL->m_owner->m_initialCommit)
        TL->setSize(TL->m_pendingApply.size);
    decoracaoMudou(toplevel, nullptr);
}

static void hkOnGetDecoration(CXDGDecorationProtocol* thisptr, CZxdgDecorationManagerV1* pMgr, uint32_t id, wl_resource* xdgToplevel) {
    ((tOnGetDecoration)g_hookXdg->m_original)(thisptr, pMgr, id, xdgToplevel);
    const auto IT = PROTO::xdgDecoration->m_decorations.find(xdgToplevel);
    if (IT != PROTO::xdgDecoration->m_decorations.end() && IT->second) {
        assumirDecoracao(IT->second.get());
        if (const auto TL = CXDGToplevelResource::fromResource(xdgToplevel)) {
            auto& O  = g_ouvintesAppId[xdgToplevel];
            O.first  = TL->m_events.metadataChanged.listen([xdgToplevel] {
                if (!g_regrasCliente.empty())
                    reavaliarModo(xdgToplevel);
            });
            O.second = TL->m_events.destroy.listen([xdgToplevel] { g_pEventLoopManager->doLater([xdgToplevel] { g_ouvintesAppId.erase(xdgToplevel); }); });
        }
    }
    decoracaoMudou(xdgToplevel, nullptr);
}

// GTK3 decide se desenha a própria barra (CSD) pelo "default_mode" do protocolo KDE: o
// Hyprland anuncia "servidor" e aí o GTK3 sem headerbar (xournal++, virt-manager, AnyDesk,
// LocalSend...) fica sem botões próprios e ganha a barra do compositor. GTK_CSD=1 não vale no
// Wayland. Aqui o anúncio passa a ser "cliente" (como no GNOME) e o pedido de cada janela é
// honrado; exceções na regra "servidor" (nome do processo, /proc/<pid>/comm).
static std::string processoDe(wl_client* c) {
    pid_t pid = 0;
    if (!c)
        return "";
    wl_client_get_credentials(c, &pid, nullptr, nullptr);
    std::ifstream f(std::format("/proc/{}/comm", pid));
    std::string   s;
    std::getline(f, s);
    return s;
}

static bool kdeServidor(wl_client* c) {
    if (g_regrasServidor.empty())
        return false;
    const auto P = processoDe(c);
    for (const auto& re : g_regrasServidor)
        if (std::regex_search(P, re))
            return true;
    return false;
}

static bool g_kdeCliente = true; // hyprctl janelas gtk3csd on|off

typedef void (*tBindKde)(CServerDecorationKDEProtocol*, wl_client*, void*, uint32_t, uint32_t);
static CFunctionHook* g_hookBindKde = nullptr;

static void hkBindKde(CServerDecorationKDEProtocol* thisptr, wl_client* client, void* data, uint32_t ver, uint32_t id) {
    ((tBindKde)g_hookBindKde->m_original)(thisptr, client, data, ver, id);
    if (!g_kdeCliente || kdeServidor(client))
        return;
    auto* G = hc::gerentesKde(thisptr);
    if (!G || G->empty() || !G->back())
        return;
    // o gerente recém-ligado é o último; o evento novo substitui o "servidor" de antes
    G->back()->sendDefaultMode(ORG_KDE_KWIN_SERVER_DECORATION_MANAGER_MODE_CLIENT);
}

typedef void (*tCreateKde)(CServerDecorationKDEProtocol*, COrgKdeKwinServerDecorationManager*, uint32_t, wl_resource*);
static CFunctionHook* g_hookKde = nullptr;

static void hkCreateKde(CServerDecorationKDEProtocol* thisptr, COrgKdeKwinServerDecorationManager* pMgr, uint32_t id, wl_resource* surf) {
    ((tCreateKde)g_hookKde->m_original)(thisptr, pMgr, id, surf);
    if (g_kdeCliente && pMgr && !kdeServidor(pMgr->client())) {
        auto* DS = hc::decoracoesKde(thisptr);
        if (DS && !DS->empty() && DS->back()) {
            CServerDecorationKDE* D = DS->back().get();
            if (const auto R = hc::recursoKde(D)) {
                // responde o que o app pediu (o Hyprland responde sempre "servidor")
                R->setRequestMode([D](COrgKdeKwinServerDecoration* r, uint32_t mode) {
                    const uint32_t M = mode == ORG_KDE_KWIN_SERVER_DECORATION_MANAGER_MODE_SERVER ? ORG_KDE_KWIN_SERVER_DECORATION_MANAGER_MODE_SERVER :
                                                                                                    ORG_KDE_KWIN_SERVER_DECORATION_MANAGER_MODE_CLIENT;
                    r->sendMode(M);
                    D->m_mostRecentlySent      = M;
                    D->m_mostRecentlyRequested = mode;
                    if (D->m_surf)
                        decoracaoMudou(nullptr, D->m_surf);
                });
                R->sendMode(ORG_KDE_KWIN_SERVER_DECORATION_MANAGER_MODE_CLIENT);
                D->m_mostRecentlySent = ORG_KDE_KWIN_SERVER_DECORATION_MANAGER_MODE_CLIENT;
            }
        }
    }
    decoracaoMudou(nullptr, CWLSurfaceResource::fromResource(surf));
}

static void decoracaoMudou(wl_resource* toplevel, SP<CWLSurfaceResource> superficie) {
    // o configure de decoração só vale junto com o próximo xdg_surface.configure
    for (const auto& w : Desktop::windowState()->windows()) {
        bool minha = false;
        if (toplevel && hc::toplevel(w) && CXDGToplevelResource::fromResource(toplevel) == hc::toplevel(w))
            minha = true;
        if (superficie && w->wlSurface() && w->wlSurface()->resource() == superficie)
            minha = true;
        if (!minha)
            continue;
        if (auto b = barraDe(w))
            b->reavaliar();
    }
}

// ── geometria da janela (xdg_surface.set_window_geometry) ─────────────────────
// Fora de maximizada, GTK4/libadwaita (e outros) desenham sombra e margem de redimensionar em
// volta da janela e dizem onde está a janela de verdade com set_window_geometry(x, y, l, a).
// O Hyprland 0.56/0.57 ignora o x/y na superfície principal (FIXME em ElementRenderer.cpp):
// desenha a superfície inteira a partir do canto da janela — o conteúdo sai deslocado e cortado.
// O clique e os popups já descontam a geometria; aqui o desenho também passa a descontar:
//   - superfície principal: UV recortada no retângulo da geometria;
//   - subsuperfícies: deslocadas por -x/-y;
//   - dano: a janela inteira a cada commit enquanto houver deslocamento.
static bool           g_corrigirGeometria = true; // hyprctl janelas geometria on|off
static CFunctionHook* g_hookUV            = nullptr;
static CFunctionHook* g_hookTexBox        = nullptr;
static CFunctionHook* g_hookSurfaceAt     = nullptr;
static CFunctionHook* g_hookBoxGlobal     = nullptr;
// janelas que estão agora com a geometria deslocada (mantido nos commits)
static std::unordered_map<uintptr_t, PHLWINDOWREF> g_deslocadas;

// retângulo da geometria dentro da superfície, se ele estiver deslocado e for coerente
static std::optional<CBox> geometriaDeslocada(PHLWINDOW w) {
    if (!w || hc::ehX11(w) || !hc::xdg(w) || !w->wlSurface() || !w->wlSurface()->resource())
        return std::nullopt;
    const auto S   = w->wlSurface()->resource();
    const auto G   = hc::xdg(w)->m_current.geometry;
    const auto TAM = S->m_current.size;
    if (G.x == 0 && G.y == 0)
        return std::nullopt;
    if (G.w < 1 || G.h < 1 || TAM.x < 1 || TAM.y < 1)
        return std::nullopt;
    // x/y > 0: sombra/margem em volta (GTK, Chromium, Qt): a geometria fica dentro da superfície.
    // x/y < 0: barra/bordas em subsuperfícies fora da principal (foot, libdecor, winit).
    if (G.x > 0 && G.x + G.w > TAM.x + 0.5)
        return std::nullopt;
    if (G.y > 0 && G.y + G.h > TAM.y + 0.5)
        return std::nullopt;
    if (G.x < -300 || G.y < -300)
        return std::nullopt;
    return G;
}

static bool geometriaCorrigida() {
    return g_corrigirGeometria && g_hookUV && g_hookTexBox && g_hookSurfaceAt && g_hookBoxGlobal;
}

typedef void (*tCalcUV)(void*, JN_CTX_P PHLWINDOW, SP<CWLSurfaceResource>, PHLMONITOR, bool, const Vector2D&, const Vector2D&, bool);
static void hkCalcUV(void* thisptr, JN_CTX_P PHLWINDOW w, SP<CWLSurfaceResource> s, PHLMONITOR m, bool main, const Vector2D& proj, const Vector2D& projU, bool fix) {
    ((tCalcUV)g_hookUV->m_original)(thisptr, JN_CTX w, s, m, main, proj, projU, fix);
    if (!g_corrigirGeometria || !main || !w || !s || !w->wlSurface() || s != w->wlSurface()->resource())
        return;
    const auto G = geometriaDeslocada(w);
    if (!G || G->x < 0 || G->y < 0) // negativo: a principal não é recortada, só deslocada (hkGetTexBox)
        return;
    const auto TAM = s->m_current.size; // coordenadas da superfície (destino do viewport, se houver)
    const auto BUF = s->m_current.bufferSize;
    if (BUF.x < 1 || BUF.y < 1)
        return;
    // recorte do buffer que vira a superfície (wp_viewport source; senão o buffer inteiro)
    CBox FONTE = {0, 0, BUF.x, BUF.y};
    if (s->m_current.viewport.hasSource)
        FONTE = s->m_current.viewport.source;
#if JANELAS_HL057
    auto& RD = ctx.m_data;
#else
    auto& RD = g_pHyprRenderer->m_renderData;
#endif
    // ponto da superfície → UV do buffer
    auto uv = [&](double x, double y) { return Vector2D{(FONTE.x + x / TAM.x * FONTE.w) / BUF.x, (FONTE.y + y / TAM.y * FONTE.h) / BUF.y}; };
    RD.primarySurfaceUVTopLeft     = uv(G->x, G->y);
    RD.primarySurfaceUVBottomRight = uv(G->x + G->w, G->y + G->h);
}

// Clique/movimento: o Hyprland procura a superfície em (pos - canto da janela) sem somar o x/y
// da geometria. Soma aqui (popups ficam como estão: o Hyprland já os posiciona pela geometria).
typedef SP<CWLSurfaceResource> (*tWindowSurfaceAt)(const void*, const Vector2D&, PHLWINDOW, Vector2D&);
static SP<CWLSurfaceResource> hkWindowSurfaceAt(const void* thisptr, const Vector2D& pos, PHLWINDOW w, Vector2D& local) {
    const auto ORIG = (tWindowSurfaceAt)g_hookSurfaceAt->m_original;
    if (!g_corrigirGeometria || !w || hc::ehX11(w) || !hc::popups(w) || hc::popups(w)->at(pos))
        return ORIG(thisptr, pos, w, local);
    const auto G = geometriaDeslocada(w);
    if (!G)
        return ORIG(thisptr, pos, w, local);
    return ORIG(thisptr, pos + G->pos(), w, local);
}

// Caixa global da superfície (coordenadas locais do ponteiro com botão apertado, arrastar e
// soltar, restrições do ponteiro...): a principal e as subsuperfícies começam em -x/-y.
typedef std::optional<CBox> (*tBoxGlobal)(const Desktop::View::CWLSurface*);
static std::optional<CBox> hkBoxGlobal(const Desktop::View::CWLSurface* thisptr) {
    auto r = ((tBoxGlobal)g_hookBoxGlobal->m_original)(thisptr);
    if (!r || !g_corrigirGeometria || g_deslocadas.empty() || !thisptr)
        return r;
    const auto RES = thisptr->resource();
    if (!RES)
        return r;
    for (const auto& [k, ref] : g_deslocadas) {
        const auto W = ref.lock();
        if (!W || !W->wlSurface() || !W->wlSurface()->resource())
            continue;
        bool minha = W->wlSurface()->resource() == RES;
        if (!minha) {
            std::pair<SP<CWLSurfaceResource>, bool> busca = {RES, false};
            W->wlSurface()->resource()->breadthfirst(
                [](SP<CWLSurfaceResource> s, const Vector2D&, void* d) {
                    auto* B = (std::pair<SP<CWLSurfaceResource>, bool>*)d;
                    if (s == B->first)
                        B->second = true;
                },
                &busca);
            minha = busca.second;
        }
        if (!minha)
            continue;
        if (const auto G = geometriaDeslocada(W))
            r->translate(-G->pos());
        break;
    }
    return r;
}

typedef CBox (*tGetTexBox)(CSurfacePassElement*);
static CBox hkGetTexBox(CSurfacePassElement* thisptr) {
    CBox b = ((tGetTexBox)g_hookTexBox->m_original)(thisptr);
    const auto& D = thisptr->m_data;
    if (!g_corrigirGeometria || D.popup || !D.pWindow)
        return b;
    const auto G = geometriaDeslocada(D.pWindow);
    if (!G)
        return b;
    if (D.mainSurface) {
        // deslocamento negativo: a principal começa depois da barra/borda, no tamanho dela
        if (G->x < 0 || G->y < 0) {
            const auto TAM = D.surface ? D.surface->m_current.size : Vector2D{};
            b.translate(Vector2D{G->x < 0 ? -G->x : 0, G->y < 0 ? -G->y : 0});
            if (TAM.x >= 1 && TAM.y >= 1) {
                b.w = TAM.x;
                b.h = TAM.y;
            }
        }
        return b;
    }
    b.translate(-G->pos());
    return b;
}

// ── estado do janelas.lua e pedidos ───────────────────────────────────────────

eEstadoJanela estadoJanela(PHLWINDOW w) {
    const auto IT = g->estados.find((uintptr_t)w.get());
    return IT == g->estados.end() ? EST_SOLTA : IT->second;
}

// Diz ao app se ele está maximizado: xdg_toplevel "maximized" (Wayland) ou _NET_WM_STATE (X11).
// O Hyprland liga "maximized" em toda janela Wayland ao mapear (para o app não desenhar sombra:
// ele não aplica o deslocamento de xdg_surface.set_window_geometry na janela principal — FIXME
// em render/ElementRenderer.cpp). Mas ele também manda os estados "tiled" nas 4 bordas, e com
// eles GTK4/Chromium/Electron já desenham sem sombra. Então aqui o estado é o verdadeiro (só
// "max" do janelas.lua liga maximized): o botão do app mostra ☐ ou ❐ certo e manda
// set_maximized/unset_maximized coerentes. Quem mesmo assim desenhar sombra deslocada (GTK3
// com as margens de redimensionar) é pego em vigiarDeslocamento e volta ao "sempre maximizada".
static bool sempreMaximizada(PHLWINDOW w) {
    return !g->estadoReal || g->sempreMax.contains((uintptr_t)w.get());
}

static void informarMaximizada(PHLWINDOW w, bool max) {
    if (!w)
        return;
    if (hc::toplevel(w)) {
        const bool  QUER = sempreMaximizada(w) ? true : max;
        const auto  TL   = hc::toplevel(w);
        const auto& ST   = TL->m_pendingApply.states;
        const bool  ERA  = std::ranges::find(ST, XDG_TOPLEVEL_STATE_MAXIMIZED) != ST.end();
        if (ERA != QUER)
            registrar(std::format("{} ({}): xdg maximized → {}", enderecoDe(w), hc::classe(w), QUER ? "sim" : "não"));
        TL->setMaximized(QUER);
        // Reenvia o xdg_toplevel.configure completo (estados + tamanho) mesmo sem mudança: o
        // Chromium troca de estado sozinho ao pedir set/unset_maximized e só volta ao certo com
        // um configure novo. NUNCA um xdg_surface.configure sozinho (scheduleConfigure): o GTK4
        // aplica isso como "nenhum estado" (nem maximized, nem tiled, nem activated) e passa a
        // desenhar sombra com set_window_geometry deslocado ~25 px — era isso o "deslocamento"
        // atribuído ao Hyprland.
        TL->setSize(TL->m_pendingApply.size);
    } else if (hc::x11(w) && !hc::x11(w)->m_overrideRedirect) {
        hc::x11(w)->m_maximized = max;
        hc::x11(w)->setMinimized(hc::x11(w)->m_minimized); // reenvia _NET_WM_STATE
    }
}

// Depois de cada commit da janela: se ela não está maximizada (para o app) e mesmo assim põe a
// área útil deslocada dentro da superfície (sombra/margem de redimensionar), o Hyprland a
// desenharia fora do lugar → volta ao "sempre maximizada" (e lembra a classe nesta sessão).
static void vigiarDeslocamento(PHLWINDOW w) {
    if (!w || !hc::xdg(w) || !hc::toplevel(w))
        return;
    const auto KEY = (uintptr_t)w.get();
    if (g->ouvintesCommit.contains(KEY))
        return;
    PHLWINDOWREF ref = w;
    g->ouvintesCommit[KEY] = hc::xdg(w)->m_events.commit.listen([ref] {
        const auto W = ref.lock();
        if (!W || !hc::xdg(W) || !hc::toplevel(W) || !hc::mapeada(W))
            return;
        const auto K = (uintptr_t)W.get();
        if (geometriaDeslocada(W))
            g_deslocadas[K] = ref;
        else
            g_deslocadas.erase(K);
        if (g->sempreMax.contains(K) || !g->estadoReal)
            return;
        const auto& ST  = hc::toplevel(W)->m_pendingApply.states;
        const bool  MAX = std::ranges::find(ST, XDG_TOPLEVEL_STATE_MAXIMIZED) != ST.end();
        const bool  FS  = std::ranges::find(ST, XDG_TOPLEVEL_STATE_FULLSCREEN) != ST.end();
        if (MAX || FS)
            return;
        const auto GEO = hc::xdg(W)->m_current.geometry;
        if (GEO.x <= 0 && GEO.y <= 0)
            return;
        if (geometriaCorrigida()) {
            // o desenho desconta a geometria; o dano do Hyprland não (vem em coordenadas da
            // superfície a partir do canto da janela) → janela inteira
            g_pHyprRenderer->damageWindow(W);
            return;
        }
        g->sempreMax.insert(K);
        g->classesSempreMax.insert(hc::classeInicial(W).empty() ? hc::classe(W) : hc::classeInicial(W));
        registrar(std::format("{} ({}) desenha sombra deslocada ({}, {}) fora de maximizada: fica sempre maximizada para o app", enderecoDe(W), hc::classe(W), GEO.x, GEO.y));
        informarMaximizada(W, true);
    });
}

static bool minimizada(PHLWINDOW w) {
    return w && hc::wsMinimizadas(w->m_workspace);
}

void pedirAcao(PHLWINDOW w, const std::string& acao, const std::string& extra) {
    if (!w)
        return;
    const auto ADDR = enderecoDe(w);
    const auto CMD  = extra.empty() ? std::format("janelas.pedido('{}', '{}')", ADDR, acao) : std::format("janelas.pedido('{}', '{}', '{}')", ADDR, acao, extra);
    const auto R    = HyprlandAPI::invokeHyprctlCommand("dispatch", CMD);
    registrar(std::format("ação {} em {} ({}) → {}", acao, ADDR, hc::classe(w), R.substr(0, R.find('\n'))));
    if (R.starts_with("ok"))
        return;

    // janelas.lua ausente ou com erro: faz o básico sozinho
    Log::logger->log(Log::ERR, std::string_view{std::format("[janelas] janelas.pedido falhou ({}): {}", acao, R)});
    const auto SEL = "address:" + ADDR;
    if (acao == "fechar")
        HyprlandAPI::invokeHyprctlCommand("dispatch", std::format("hl.dsp.window.close({{ window = '{}' }})", SEL));
    else if (acao == "minimizar")
        HyprlandAPI::invokeHyprctlCommand("dispatch", std::format("hl.dsp.window.move({{ workspace = 'special:minimizadas', follow = false, window = '{}' }})", SEL));
    else if (acao == "alternar" || acao == "maximizar" || acao == "restaurar")
        HyprlandAPI::invokeHyprctlCommand("dispatch", std::format("hl.dsp.window.fullscreen({{ mode = 'maximized', window = '{}' }})", SEL));
}

static void adiarAcao(PHLWINDOW w, const std::string& acao) {
    PHLWINDOWREF ref = w;
    g_pEventLoopManager->doLater([ref, acao] {
        if (const auto W = ref.lock(); W && hc::mapeada(W))
            pedirAcao(W, acao);
    });
}

// Pedidos do próprio app (botões nativos GTK/Chromium/Electron, X11 WM_CHANGE_STATE...).
static void aoPedidoDeEstado(PHLWINDOWREF ref) {
    const auto W = ref.lock();
    if (!W || !hc::mapeada(W))
        return;

    std::optional<bool> mx, mn;
    if (hc::toplevel(W)) {
        mx = hc::toplevel(W)->m_state.requestsMaximize;
        mn = hc::toplevel(W)->m_state.requestsMinimize;
    } else if (hc::x11(W)) {
        // no X11 o pedido fica guardado: consome aqui (o Hyprland já leu antes)
        mx = hc::x11(W)->m_state.requestsMaximize;
        mn = hc::x11(W)->m_state.requestsMinimize;
        hc::x11(W)->m_state.requestsMaximize.reset();
        hc::x11(W)->m_state.requestsMinimize.reset();
    }

    if (!mx.has_value() && !mn.has_value())
        return;
    registrar(std::format("pedido do app {} ({}): maximizar={} minimizar={} estado={}", enderecoDe(W), hc::classe(W), mx.has_value() ? (*mx ? "set" : "unset") : "-",
                          mn.has_value() ? (*mn ? "set" : "unset") : "-", estadoJanela(W) == EST_MAX ? "max" : estadoJanela(W) == EST_ZONA ? "zona" : "solta"));
    if (mn.has_value() && *mn && !minimizada(W)) {
        adiarAcao(W, "minimizar");
        return;
    }
    if (!mx.has_value())
        return;
    const auto EST = estadoJanela(W);
    if (sempreMaximizada(W) && !hc::ehX11(W)) {
        // o app acha que está sempre maximizado: o botão dele manda unset_maximized mesmo com a
        // janela solta — vale como "alternar" (janelas.lua decide)
        informarMaximizada(W, true);
        adiarAcao(W, "alternar");
        return;
    }
    // estado verdadeiro: set = maximizar, unset = restaurar (encaixada também restaura, como
    // no Windows). Pedido que não muda nada só reafirma o estado (o app volta ao certo).
    if (*mx && EST != EST_MAX)
        adiarAcao(W, "maximizar");
    else if (!*mx && EST != EST_SOLTA)
        adiarAcao(W, "restaurar");
    else
        informarMaximizada(W, EST == EST_MAX);
}

static void suprimirMaximizarDoHyprland(PHLWINDOW w) {
    // o janelas.lua cuida de maximizar; o Hyprland não pode maximizar por conta própria
    // (o Simba já suprime com suppress_event, isto garante)
    hc::suprimirMaximizar(w);
}

static void ouvirJanela(PHLWINDOW w) {
    const auto KEY = (uintptr_t)w.get();
    if (g->ouvintesEstado.contains(KEY))
        return;
    PHLWINDOWREF ref = w;
    registrar(std::format("ouvindo pedidos de {} ({})", enderecoDe(w), hc::classe(w)));
    if (hc::toplevel(w))
        g->ouvintesEstado[KEY] = hc::toplevel(w)->m_events.stateChanged.listen([ref] { aoPedidoDeEstado(ref); });
    else if (hc::x11(w))
        g->ouvintesEstado[KEY] = hc::x11(w)->m_events.stateChanged.listen([ref] { aoPedidoDeEstado(ref); });
}

// O Hyprland anuncia só "fullscreen" e "maximize" em xdg_toplevel.wm_capabilities; sem
// "minimize" o GTK4/libadwaita desabilita o próprio botão minimizar. O plugin minimiza
// (special:minimizadas), então anuncia de novo com minimize — antes do primeiro configure.
static void anunciarCapacidades(PHLWINDOW w, bool reconfigurar) {
    if (!w || !hc::xdg(w) || !hc::toplevel(w))
        return;
    const auto TL = hc::toplevel(w);
    if (!TL->m_resource || TL->m_resource->version() < 5)
        return;
    wl_array arr;
    wl_array_init(&arr);
    for (uint32_t c : {XDG_TOPLEVEL_WM_CAPABILITIES_FULLSCREEN, XDG_TOPLEVEL_WM_CAPABILITIES_MAXIMIZE, XDG_TOPLEVEL_WM_CAPABILITIES_MINIMIZE})
        *(uint32_t*)wl_array_add(&arr, sizeof(uint32_t)) = c;
    TL->m_resource->sendWmCapabilities(&arr);
    wl_array_release(&arr);
    if (reconfigurar) // configure completo (um xdg_surface.configure sozinho zera os estados no GTK4)
        TL->setSize(TL->m_pendingApply.size);
}

static void aoAbrirJanela(PHLWINDOW w) {
    if (!w)
        return;
    // (estado de endereço reaproveitado é apagado no destroy; apagar aqui perderia o "max" que o
    // janelas.lua pode ter mandado no window.open dele, que às vezes roda antes deste)
    g->forcadas.erase((uintptr_t)w.get());
    if (hc::ehX11(w))
        g->x11SemBordas.erase((uintptr_t)w.get());
    suprimirMaximizarDoHyprland(w);
    ouvirJanela(w);
    g->sempreMax.erase((uintptr_t)w.get());
    if (g->classesSempreMax.contains(hc::classeInicial(w).empty() ? hc::classe(w) : hc::classeInicial(w)))
        g->sempreMax.insert((uintptr_t)w.get());
    vigiarDeslocamento(w);
    {
        // o Hyprland ligou "maximized" ao mapear; o janelas.lua manda o estado dele logo em
        // seguida (window.open) — janela que ele não gerencia (diálogo, solta) fica "solta"
        PHLWINDOWREF ref = w;
        g_pEventLoopManager->doLater([ref] {
            if (const auto W = ref.lock(); W && hc::mapeada(W))
                informarMaximizada(W, estadoJanela(W) == EST_MAX);
        });
    }
    if (hc::temDecoracao(w, "JanelasBarra"))
        return;
#if JANELAS_HL057
    auto barra    = makeShared<CBarra>(w);
#else
    auto barra    = makeUnique<CBarra>(w);
#endif
    barra->m_self = barra;
    g->barras.emplace_back(barra);
    CBarra* P = barra.get();
    HyprlandAPI::addWindowDecoration(PHANDLE, w, std::move(barra));
    P->reavaliar();
}

// ── foco de teclado ───────────────────────────────────────────────────────────
// Com foco no clique (follow_mouse = 0) só um clique muda o teclado de lugar.

static bool g_noMovimento   = false; // dentro do processamento de um movimento do mouse
static bool g_permitirFoco  = false; // foco pedido por este plugin (clique)
static int  g_hoverBloqueado = 0;
static bool g_correcaoFoco   = true; // hyprctl janelas correcao on|off (para comparar)

typedef void (*tRawSurfaceFocus)(Desktop::CFocusState*, SP<CWLSurfaceResource>, PHLWINDOW);
static CFunctionHook* g_hookFoco = nullptr;

static void hkRawSurfaceFocus(Desktop::CFocusState* thisptr, SP<CWLSurfaceResource> surf, PHLWINDOW owner) {
    static auto PFOLLOW = CConfigValue<Config::INTEGER>("input:follow_mouse");
    if (g_correcaoFoco && g_noMovimento && !g_permitirFoco && !owner && surf && *PFOLLOW == 0) {
        // passar o mouse sobre uma camada on-demand (ex.: área de trabalho) não rouba o
        // teclado da janela ativa
        const auto LS = camadaDaSuperficie(surf);
        if (LS && LS->m_layerSurface && hc::interatividadeTeclado(LS->m_layerSurface.get()) == ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_ON_DEMAND) {
            if (g_hoverBloqueado++ % 50 == 0)
                registrar(std::format("hover não roubou o teclado (camada '{}')", LS->m_namespace));
            return;
        }
    }
    ((tRawSurfaceFocus)g_hookFoco->m_original)(thisptr, surf, owner);
}

static std::string descreverSuperficie(SP<CWLSurfaceResource> s);

static bool superficieDaJanela(SP<CWLSurfaceResource> s, PHLWINDOW w) {
    return s && w && janelaDaSuperficie(s) == w;
}

// Depois que o Hyprland tratou o clique: garante o teclado no que foi clicado.
static void conferirFocoAposClique() {
    if (!g_correcaoFoco)
        return;
    if (g_pSessionLockManager->isSessionLocked() || g_pSeatManager->m_seatGrab || hc::camadasExclusivas())
        return;
    if (g_layoutManager && g_layoutManager->dragController()->target())
        return;

    const auto MOUSE = g_pInputManager->getMouseCoordsInternal();
    const auto PMON  = State::monitorState()->query().vec(MOUSE).run();
    if (!PMON)
        return;
    const auto KB = g_pSeatManager->m_state.keyboardFocus.lock();

    auto focarCamada = [&](PHLLS ls, SP<CWLSurfaceResource> s) -> bool {
        if (!ls || !ls->m_layerSurface)
            return false;
        if (hc::interatividadeTeclado(ls->m_layerSurface.get()) == ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_NONE)
            return true; // barra etc.: clique não mexe no teclado
        if (KB && camadaDaSuperficie(KB) == ls)
            return true;
        g_permitirFoco = true;
        Desktop::focusState()->rawSurfaceFocus(ls->wlSurface()->resource());
        g_permitirFoco = false;
        return true;
    };

    PHLLS    ls = nullptr;
    Vector2D sc;
    auto     s = Desktop::viewState()->hitTest().layerPopupSurfaceAt(MOUSE, PMON, &sc, &ls);
    if (s && ls) {
        // popup de camada sem grab (com grab já saímos acima): teclado nele se a camada aceita
        if (ls->m_layerSurface && hc::interatividadeTeclado(ls->m_layerSurface.get()) != ZWLR_LAYER_SURFACE_V1_KEYBOARD_INTERACTIVITY_NONE && KB != s) {
            g_permitirFoco = true;
            Desktop::focusState()->rawSurfaceFocus(s);
            g_permitirFoco = false;
        }
        return;
    }
    for (auto camada : {ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY, ZWLR_LAYER_SHELL_V1_LAYER_TOP}) {
        ls = nullptr;
        s  = Desktop::viewState()->hitTest().layerSurfaceAt(MOUSE, &PMON->m_layerSurfaceLayers[camada], &sc, &ls);
        if (ls && focarCamada(ls, s))
            return;
    }

    const auto W = Desktop::viewState()->hitTest().windowAt(MOUSE, Desktop::View::RESERVED_EXTENTS | Desktop::View::INPUT_EXTENTS | Desktop::View::ALLOW_FLOATING);
    if (W) {
        if (W != Desktop::focusState()->window())
            return; // o Hyprland trocou (ou recusou) a janela: não interfere
        if (superficieDaJanela(KB, W))
            return;
        // A janela "está em foco" mas o teclado está em outro lugar (camada, nada...):
        // devolve o teclado para ela — o clique é a intenção do usuário.
        if (W->wlSurface() && W->wlSurface()->resource()) {
            registrar(std::format("clique devolveu o teclado para {} ({}), estava em {}", enderecoDe(W), hc::classe(W), descreverSuperficie(KB)));
            g_permitirFoco = true;
            Desktop::focusState()->rawSurfaceFocus(W->wlSurface()->resource(), W);
            g_permitirFoco = false;
        }
        return;
    }

    for (auto camada : {ZWLR_LAYER_SHELL_V1_LAYER_BOTTOM, ZWLR_LAYER_SHELL_V1_LAYER_BACKGROUND}) {
        ls = nullptr;
        s  = Desktop::viewState()->hitTest().layerSurfaceAt(MOUSE, &PMON->m_layerSurfaceLayers[camada], &sc, &ls);
        if (ls && focarCamada(ls, s))
            return;
    }
}

// ── diagnóstico (hyprctl janelas ...) ────────────────────────────────────────

static std::string descreverSuperficie(SP<CWLSurfaceResource> s) {
    if (!s)
        return "nada";
    if (auto w = janelaDaSuperficie(s))
        return std::format("janela {} ({}){}", enderecoDe(w), hc::classe(w), w->wlSurface() && w->wlSurface()->resource() == s ? "" : " [subsuperfície/popup]");
    if (auto l = camadaDaSuperficie(s)) {
        const auto I = l->m_layerSurface ? hc::interatividadeTeclado(l->m_layerSurface.get()) : -1;
        return std::format("camada '{}' (interatividade {})", l->m_namespace, I == 0 ? "none" : I == 1 ? "exclusive" : I == 2 ? "on-demand" : "?");
    }
    return std::format("superfície {:x}", (uintptr_t)s.get());
}

static std::string cmdJanelas(std::string req) {
    std::string arg = req;
    if (auto p = arg.find(' '); p != std::string::npos)
        arg = arg.substr(p + 1);
    else
        arg = "";
    while (!arg.empty() && arg.front() == ' ')
        arg.erase(arg.begin());

    std::string out;
    if (arg.empty() || arg == "foco") {
        const auto FW = Desktop::focusState()->window();
        out += std::format("janela ativa (Hyprland): {}\n", FW ? std::format("{} ({})", enderecoDe(FW), hc::classe(FW)) : "nenhuma");
        out += std::format("superfície de foco (Hyprland): {}\n", descreverSuperficie(Desktop::focusState()->surface()));
        out += std::format("teclado (seat): {}\n", descreverSuperficie(g_pSeatManager->m_state.keyboardFocus.lock()));
        out += std::format("ponteiro (seat): {}\n", descreverSuperficie(g_pSeatManager->m_state.pointerFocus.lock()));
        out += std::format("grab do seat: {}\n", g_pSeatManager->m_seatGrab ? std::format("sim ({} superfícies)", g_pSeatManager->m_seatGrab->m_surfs.size()) : "não");
        out += std::format("camadas exclusivas: {}\n", hc::numCamadasExclusivas());
        out += std::format("roubos de teclado por hover bloqueados: {}\n", g_hoverBloqueado);
        const bool OK = !FW || superficieDaJanela(g_pSeatManager->m_state.keyboardFocus.lock(), FW);
        out += std::format("consistente: {}\n", OK ? "sim" : "NÃO (janela ativa sem o teclado)");
    } else if (arg == "lista") {
        for (const auto& w : Desktop::windowState()->windows()) {
            if (!hc::mapeada(w))
                continue;
            const auto I = modoDecoracao(w);
            const auto B = barraDe(w);
            const auto E = estadoJanela(w);
            out += std::format("{} {} [{}] barra={} estado={}{} ws={} — {}\n", enderecoDe(w), hc::classe(w), hc::ehX11(w) ? "x11" : "wayland", B && B->visivel() ? "sim" : "não",
                               E == EST_MAX ? "max" : E == EST_ZONA ? "zona" : "solta", sempreMaximizada(w) && !hc::ehX11(w) ? " (app: sempre max)" : "",
                               hc::wsNome(w->m_workspace), I.motivo);
            if (hc::toplevel(w)) {
                const auto& ST  = hc::toplevel(w)->m_pendingApply.states;
                const auto  GEO = hc::xdg(w)->m_current.geometry;
                out += std::format("    xdg maximized={} geometria={},{} {}x{}\n", std::ranges::find(ST, XDG_TOPLEVEL_STATE_MAXIMIZED) != ST.end() ? "sim" : "não", GEO.x, GEO.y, GEO.w, GEO.h);
            }
        }
    } else if (arg.starts_with("forcar ")) {
        // forcar <addr> sim|nao|auto — para um app que trocou de modo sem avisar pelo
        // protocolo (Brave ao ligar "usar barra de título do sistema" com a janela aberta)
        std::istringstream is(arg.substr(7));
        std::string        a, v;
        is >> a >> v;
        const auto W = janelaPorEndereco(a);
        if (!W)
            return "janela não encontrada\n";
        if (v == "auto")
            g->forcadas.erase((uintptr_t)W.get());
        else
            g->forcadas[(uintptr_t)W.get()] = v != "nao";
        if (auto b = barraDe(W))
            b->reavaliar();
        out = "ok\n";
    } else if (arg == "eventos") {
        for (const auto& e : g_eventos)
            out += e + "\n";
        if (out.empty())
            out = "(nenhum evento)\n";
    } else if (arg.starts_with("csd ")) {
        // experimento: diz ao app "decoração do lado do cliente" (o app desenha a moldura)
        const auto W = janelaPorEndereco(arg.substr(4));
        if (!W || !hc::toplevel(W))
            return "janela não encontrada\n";
        const auto TL = hc::toplevel(W);
        for (const auto& [res, deco] : PROTO::xdgDecoration->m_decorations) {
            if (!deco || CXDGToplevelResource::fromResource(res) != TL)
                continue;
            if (auto R = hc::recursoDecoracao(deco.get())) {
                R->sendConfigure(ZXDG_TOPLEVEL_DECORATION_V1_MODE_CLIENT_SIDE);
                deco->mostRecentlySent = ZXDG_TOPLEVEL_DECORATION_V1_MODE_CLIENT_SIDE;
            }
        }
        TL->setSize(TL->m_pendingApply.size);
        out = "ok\n";
    } else if (arg.starts_with("qtcsd")) {
        if (arg.ends_with("off"))
            g_qtCliente = false;
        else if (arg.ends_with("on"))
            g_qtCliente = true;
        out = std::format("Qt 6 com barra própria: {} (vale para janelas abertas depois)\n", g_qtCliente ? "ligado" : "desligado");
    } else if (arg.starts_with("gtk3csd")) {
        if (arg.ends_with("off"))
            g_kdeCliente = false;
        else if (arg.ends_with("on"))
            g_kdeCliente = true;
        out = std::format("GTK3 com barra própria (protocolo KDE \"cliente\"): {} (vale para apps abertos depois)\n", g_kdeCliente ? "ligado" : "desligado");
    } else if (arg.starts_with("geometria")) {
        if (arg.ends_with("off"))
            g_corrigirGeometria = false;
        else if (arg.ends_with("on"))
            g_corrigirGeometria = true;
        for (auto& m : State::monitorState()->monitors())
            g_pHyprRenderer->damageMonitor(m);
        out = std::format("correção da geometria xdg: {} (ganchos {})\n", g_corrigirGeometria ? "ligada" : "desligada", geometriaCorrigida() || !g_corrigirGeometria ? "ok" : "AUSENTES");
    } else if (arg.starts_with("estadoreal")) {
        // estadoreal on|off: estado xdg "maximized" verdadeiro ou sempre ligado (comportamento antigo)
        if (arg.ends_with("off"))
            g->estadoReal = false;
        else if (arg.ends_with("on"))
            g->estadoReal = true;
        for (const auto& w : Desktop::windowState()->windows())
            if (hc::mapeada(w))
                informarMaximizada(w, estadoJanela(w) == EST_MAX);
        out = std::format("estado maximizado verdadeiro: {}\n", g->estadoReal ? "ligado" : "desligado (sempre maximizada)");
    } else if (arg.starts_with("correcao")) {
        if (arg.ends_with("off"))
            g_correcaoFoco = false;
        else if (arg.ends_with("on"))
            g_correcaoFoco = true;
        out = std::format("correção de foco: {}\n", g_correcaoFoco ? "ligada" : "desligada");
    } else if (arg == "ligar" || arg == "desligar") {
        // barras de título liga/desliga (os pedidos dos apps e a correção de foco continuam)
        g->habilitado = arg == "ligar";
        for (auto& b : g->barras)
            if (b)
                b->reavaliar();
        out = std::format("barras de título: {}\n", g->habilitado ? "ligadas" : "desligadas");
    } else if (arg == "recarregar") {
        lerTema();
        lerRegras();
        for (auto& b : g->barras)
            if (b)
                b->aoRecarregar();
        out = "ok\n";
    } else
        out = "uso: hyprctl janelas foco|lista|eventos|recarregar|ligar|desligar|forcar <addr> sim|nao|auto|correcao on|off|estadoreal on|off\n";
    return out;
}

// ── funções Lua (hl.plugin.janelas.*) ────────────────────────────────────────

static int luaEstado(lua_State* L) {
    const char* A = luaL_checkstring(L, 1);
    const char* M = luaL_optstring(L, 2, "solta");
    const auto  W = janelaPorEndereco(A);
    if (!W)
        return 0;
    const std::string MS = M;
    const auto        E  = MS == "max" ? EST_MAX : MS == "zona" ? EST_ZONA : EST_SOLTA;
    const auto        K  = (uintptr_t)W.get();
    const auto        ANT = estadoJanela(W);
    g->estados[K]        = E;
    (void)ANT;
    informarMaximizada(W, E == EST_MAX);
    if (auto b = barraDe(W))
        b->damageEntire();
    return 0;
}

static int luaBarra(lua_State* L) {
    const char* A = luaL_checkstring(L, 1);
    const auto  W = janelaPorEndereco(A);
    lua_pushinteger(L, W && barraDeveAparecer(W) ? ALTURA_BARRA : 0);
    return 1;
}

// ── ciclo de vida ─────────────────────────────────────────────────────────────

static CFunctionHook* criarHook(const std::string& nome, const std::string& classe, void* destino) {
    const auto ACHADOS = HyprlandAPI::findFunctionsByName(PHANDLE, nome);
    for (const auto& f : ACHADOS) {
        if (f.demangled.find(classe + "::" + nome) == std::string::npos)
            continue;
        auto* h = HyprlandAPI::createFunctionHook(PHANDLE, f.address, destino);
        if (h && h->hook())
            return h;
    }
    HyprlandAPI::addNotification(PHANDLE, std::format("[janelas] não achei {}::{}", classe, nome), CHyprColor{1.0, 0.3, 0.3, 1.0}, 8000);
    return nullptr;
}

APICALL EXPORT PLUGIN_DESCRIPTION_INFO PLUGIN_INIT(HANDLE handle) {
    PHANDLE = handle;

    const std::string HASH        = __hyprland_api_get_hash();
    const std::string CLIENT_HASH = __hyprland_api_get_client_hash();
    if (HASH != CLIENT_HASH) {
        HyprlandAPI::addNotification(PHANDLE, "[janelas] versão do Hyprland mudou: rode janelas-nativo compilar", CHyprColor{1.0, 0.2, 0.2, 1.0}, 8000);
        throw std::runtime_error("[janelas] versão incompatível");
    }

    g = makeUnique<SEstadoGlobal>();
    {
        const char* HOME = getenv("HOME");
        std::error_code ec;
        g->habilitado = !std::filesystem::exists(std::string(HOME ? HOME : "") + "/.config/janelas-nativo/desligado", ec);
    }
    lerTema();
    lerRegras();

    g_hookXdg  = criarHook("onGetDecoration", "CXDGDecorationProtocol", (void*)&hkOnGetDecoration);
    g_hookKde  = criarHook("createDecoration", "CServerDecorationKDEProtocol", (void*)&hkCreateKde);
    g_hookBindKde = criarHook("bindManager", "CServerDecorationKDEProtocol", (void*)&hkBindKde);
    g_hookFoco = criarHook("rawSurfaceFocus", "CFocusState", (void*)&hkRawSurfaceFocus);
    g_hookUV     = criarHook("calculateUVForSurface", "IElementRenderer", (void*)&hkCalcUV);
    g_hookTexBox = criarHook("getTexBox", "CSurfacePassElement", (void*)&hkGetTexBox);
    g_hookSurfaceAt = criarHook("windowSurfaceAt", "CViewHitTester", (void*)&hkWindowSurfaceAt);
    g_hookBoxGlobal = criarHook("getSurfaceBoxGlobal", "CWLSurface", (void*)&hkBoxGlobal);

    static auto L0 = Event::bus()->m_events.window.create.listen([](PHLWINDOW w) { anunciarCapacidades(w, false); });
    static auto L1 = Event::bus()->m_events.window.open.listen([](PHLWINDOW w) { aoAbrirJanela(w); });
    static auto L2 = Event::bus()->m_events.window.updateRules.listen([](PHLWINDOW w) {
        suprimirMaximizarDoHyprland(w);
        if (auto b = barraDe(w))
            b->reavaliar();
    });
    static auto L3 = Event::bus()->m_events.window.fullscreen.listen([](PHLWINDOW w) {
        if (auto b = barraDe(w))
            b->reavaliar();
    });
    static auto L4 = Event::bus()->m_events.window.title.listen([](PHLWINDOW w) {
        if (auto b = barraDe(w))
            b->damageEntire();
    });
    static auto L5 = Event::bus()->m_events.window.active.listen([](PHLWINDOW, Desktop::eFocusReason) {
        for (auto& b : g->barras)
            if (b)
                b->damageEntire();
    });
    static auto L6 = Event::bus()->m_events.window.destroy.listen([](PHLWINDOWREF w) {
        const auto K = (uintptr_t)w.get();
        g->ouvintesEstado.erase(K);
        g->ouvintesCommit.erase(K);
        g_deslocadas.erase(K);
        g->sempreMax.erase(K);
        g->estados.erase(K);
        g->x11SemBordas.erase(K);
        g->forcadas.erase(K);
    });
    static auto L7 = Event::bus()->m_events.config.reloaded.listen([] {
        lerTema();
        lerRegras();
        for (const auto& w : Desktop::windowState()->windows())
            if (hc::mapeada(w))
                suprimirMaximizarDoHyprland(w);
        for (auto& b : g->barras)
            if (b)
                b->aoRecarregar();
    });
    static auto L8 = Event::bus()->m_events.window.moveToWorkspace.listen([](PHLWINDOW w, PHLWORKSPACE ws) {
        // X11: avisa o app que foi minimizado (WM_STATE iconic) ou voltou
        if (w && hc::x11(w) && ws)
            hc::x11(w)->setMinimized(hc::wsMinimizadas(ws));
    });

    // foco no clique
    static auto M1 = Event::bus()->m_events.input.mouse.move.listen([](Vector2D, Event::SCallbackInfo&) {
        if (g_noMovimento)
            return;
        g_noMovimento = true;
        g_pEventLoopManager->doLater([] { g_noMovimento = false; });
    });
    static auto M2 = Event::bus()->m_events.input.mouse.button.listen([](IPointer::SButtonEvent e, Event::SCallbackInfo&) {
        if (e.state != WL_POINTER_BUTTON_STATE_PRESSED)
            return;
        g_pEventLoopManager->doLater([] { conferirFocoAposClique(); });
    });

#if JANELAS_HL057
    HyprlandAPI::registerHyprCtlCommand(PHANDLE, IPC::Socket1::SCommand{.name = "janelas", .match = IPC::Socket1::COMMAND_MATCH_PREFIX,
                                                                        .handler = [](const IPC::Socket1::SRequest& r) { return IPC::Socket1::SResponse(cmdJanelas(r.command)); }});
#else
    HyprlandAPI::registerHyprCtlCommand(PHANDLE, SHyprCtlCommand{.name = "janelas", .exact = false, .fn = [](eHyprCtlOutputFormat, std::string req) { return cmdJanelas(req); }});
#endif
    HyprlandAPI::addLuaFunction(PHANDLE, "janelas", "estado", ::luaEstado);
    HyprlandAPI::addLuaFunction(PHANDLE, "janelas", "barra", ::luaBarra);

    for (auto& w : Desktop::windowState()->windows()) {
        if (w->isHidden() && !minimizada(w))
            continue;
        if (!hc::mapeada(w))
            continue;
        anunciarCapacidades(w, true);
        aoAbrirJanela(w);
    }

    // o janelas.lua manda de novo o estado (max/zona/solta) de cada janela
    g_pEventLoopManager->doLater([] { HyprlandAPI::invokeHyprctlCommand("eval", "if janelas and janelas.sincronizar then janelas.sincronizar() end"); });

    return {"janelas", "Barras e controles de janela do Simba OS, decididos pelo protocolo", "renan", "1.0"};
}

APICALL EXPORT void PLUGIN_EXIT() {
    // Nada do Hyprland pode continuar apontando para código deste plugin depois de descarregado:
    // pedidos de modo de decoração voltam a não ter resposta (o wrapper ignora pedido sem
    // handler) e os ouvintes de cliente saem da lista do libwayland.
    if (PROTO::xdgDecoration)
        for (const auto& [res, deco] : PROTO::xdgDecoration->m_decorations)
            if (const auto R = deco ? hc::recursoDecoracao(deco.get()) : nullptr) {
                R->setSetMode({});
                R->setUnsetMode({});
            }
    if (PROTO::serverDecorationKDE)
        if (auto* DS = hc::decoracoesKde(PROTO::serverDecorationKDE.get()))
            for (const auto& d : *DS)
                if (const auto R = d ? hc::recursoKde(d.get()) : nullptr)
                    R->setRequestMode({});
    for (auto* l : g_ouvintesClientes) {
        wl_list_remove(&l->link);
        delete l;
    }
    g_ouvintesClientes.clear();
    g_clientesQt6.clear();
    g_ouvintesAppId.clear();
    for (auto& m : State::monitorState()->monitors())
        m->m_scheduledRecalc = true;
#if !JANELAS_HL057
    g_pHyprRenderer->m_renderPass.removeAllOfType("CBarraPass");
#endif
    // as decorações voltam ao comportamento do Hyprland (sempre servidor) só em objetos novos;
    // os hooks são removidos pelo próprio Hyprland ao descarregar.
    if (g)
        g->ouvintesEstado.clear();
}
