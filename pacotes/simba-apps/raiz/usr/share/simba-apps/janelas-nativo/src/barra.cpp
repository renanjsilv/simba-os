#include "barra.hpp"

#include <linux/input-event-codes.h>

using namespace Render::GL;

static CHyprColor comAlfa(CHyprColor c, float a) {
    c.a *= a;
    return c;
}

// Mistura a cor de fundo com a de frente (realce sutil dos botões, como o Win11).
static CHyprColor misturar(const CHyprColor& a, const CHyprColor& b, float t) {
    return CHyprColor(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t, a.a + (b.a - a.a) * t);
}

CBarra::CBarra(PHLWINDOW w) : IHyprWindowDecoration(w), m_janela(w) {
    m_ouvBotao     = Event::bus()->m_events.input.mouse.button.listen([this](IPointer::SButtonEvent e, Event::SCallbackInfo& info) { aoBotao(info, e); });
    m_ouvMovimento = Event::bus()->m_events.input.mouse.move.listen([this](Vector2D c, Event::SCallbackInfo&) { aoMovimento(c); });
    m_visivel      = false;
}

CBarra::~CBarra() {
    if (m_avisouSnap)
        avisarSnap(false);
    std::erase_if(g->barras, [this](const auto& b) { return !b || b.get() == this; });
}

PHLWINDOW CBarra::dona() {
    return m_janela.lock();
}

std::string CBarra::getDisplayName() {
    return "JanelasBarra";
}

SDecorationPositioningInfo CBarra::getPositioningInfo() {
    SDecorationPositioningInfo info;
    info.policy         = m_visivel ? DECORATION_POSITION_STICKY : DECORATION_POSITION_ABSOLUTE;
    info.edges          = DECORATION_EDGE_TOP;
    info.priority       = 10005; // acima da borda (10000): a borda contorna barra + conteúdo, como parte do app
    info.reserved       = true;
    info.desiredExtents = {{0, m_visivel ? ALTURA_BARRA : 0}, {0, 0}};
    return info;
}

void CBarra::onPositioningReply(const SDecorationPositioningReply& reply) {
    m_caixa = reply.assignedGeometry;
}

eDecorationType CBarra::getDecorationType() {
    return DECORATION_CUSTOM;
}

eDecorationLayer CBarra::getDecorationLayer() {
    return DECORATION_LAYER_UNDER;
}

uint64_t CBarra::getDecorationFlags() {
    return DECORATION_ALLOWS_MOUSE_INPUT | DECORATION_PART_OF_MAIN_WINDOW;
}

void CBarra::updateWindow(PHLWINDOW) {
    reavaliar();
    damageEntire();
}

void CBarra::aoRecarregar() {
    m_texTitulo = nullptr;
    for (auto& i : m_icones)
        i.tex = nullptr;
    reavaliar();
    g_pDecorationPositioner->repositionDeco(this);
    damageEntire();
}

bool barraDeveAparecer(PHLWINDOW W) {
    if (!W || !hc::mapeada(W) || !g->habilitado)
        return false;
    const auto INFO = modoDecoracao(W);
    bool       quer = INFO.modo == DECO_SERVIDOR || INFO.modo == DECO_X11_SIM;
    bool       forcar = false;
    if (barraForcada(W, forcar))
        quer = forcar;
    if (quer && Fullscreen::controller()->getFullscreenModes(W).internal == Fullscreen::FSMODE_FULLSCREEN)
        quer = false;
    if (quer && !W->m_ruleApplicator->decorate().valueOrDefault())
        quer = false;
    return quer;
}

void CBarra::reavaliar() {
    const auto W    = dona();
    const bool quer = barraDeveAparecer(W);

    if (quer == m_visivel)
        return;

    m_visivel = quer;
    if (!m_visivel) {
        m_sobre = m_apertado = BOTAO_NENHUM;
        if (m_avisouSnap)
            avisarSnap(false);
    }
    g_pDecorationPositioner->repositionDeco(this);
    if (W)
        hc::atualizarDecoracoes(W);
    damageEntire();
    // marca janelas-barra: Quickshell (botoes-janela, prévias) e regras sabem quem tem barra
    if (W) {
        const auto CMD = std::format("hl.dsp.window.tag({{ tag = '{}janelas-barra', window = 'address:{}' }})", m_visivel ? "+" : "-", enderecoDe(W));
        g_pEventLoopManager->doLater([CMD] { HyprlandAPI::invokeHyprctlCommand("dispatch", CMD); });
    }
    // maximizada/encaixada: a barra entrou ou saiu, o janelas.lua refaz a caixa
    if (W && Fullscreen::controller()->getFullscreenModes(W).internal != Fullscreen::FSMODE_FULLSCREEN) {
        const auto CMD = std::format("if janelas and janelas.barra_mudou then janelas.barra_mudou('{}') end", enderecoDe(W));
        g_pEventLoopManager->doLater([CMD] { HyprlandAPI::invokeHyprctlCommand("eval", CMD); });
    }
}

void CBarra::damageEntire() {
    if (!m_visivel)
        return;
    g_pHyprRenderer->damageBox(caixaGlobal().expand(2));
}

CBox CBarra::caixaGlobal() {
    const auto W = dona();
    if (!W || !validMapped(W))
        return {};

    CBox box = m_caixa;
    box.translate(g_pDecorationPositioner->getEdgeDefinedPoint(DECORATION_EDGE_TOP, W));

    const auto WS = W->m_workspace;
    if (WS && !hc::fixada(W))
        box.translate(WS->m_renderOffset->value());
    return box;
}

Vector2D CBarra::cursorRelativo() {
    return g_pInputManager->getMouseCoordsInternal() - caixaGlobal().pos();
}

// Botões visíveis, da direita para a esquerda: fechar, maximizar, minimizar. Diálogos só
// têm fechar; janela de tamanho fixo não maximiza.
static std::vector<int> botoesDe(PHLWINDOW w) {
    bool dialogo = false, fixa = false;
    if (hc::toplevel(w)) {
        const auto TL = hc::toplevel(w);
        dialogo       = !TL->m_parent.expired();
        const auto MN = TL->m_current.minSize, MX = TL->m_current.maxSize;
        fixa          = MN.x > 1 && MN.y > 1 && MN == MX;
    } else if (hc::x11(w)) {
        dialogo = !hc::x11(w)->m_parent.expired() || hc::x11(w)->m_transient;
        if (const auto& SH = hc::x11(w)->m_sizeHints; SH)
            fixa = SH->min_width > 1 && SH->min_width == SH->max_width && SH->min_height == SH->max_height;
    }
    if (dialogo)
        return {2};
    if (fixa)
        return {2, 0};
    return {2, 1, 0};
}

CBarra::eBotao CBarra::botaoEm(const Vector2D& rel) {
    const auto W = dona();
    if (!W)
        return BOTAO_NENHUM;
    const auto BOX = caixaGlobal();
    if (rel.y < 0 || rel.y >= BOX.h || rel.x < 0 || rel.x >= BOX.w)
        return BOTAO_NENHUM;
    const auto BOTOES = botoesDe(W);
    for (size_t i = 0; i < BOTOES.size(); ++i) {
        const double x1 = BOX.w - LARGURA_BOTAO * (i + 1.0), x2 = BOX.w - LARGURA_BOTAO * (double)i;
        if (rel.x >= x1 && rel.x < x2)
            return (eBotao)BOTOES[i];
    }
    return BOTAO_NENHUM;
}

bool CBarra::entradaValida() {
    if (!m_visivel)
        return false;
    const auto W = dona();
    if (!W || !validMapped(W) || W->isHidden())
        return false;
    if (g_pSessionLockManager->isSessionLocked())
        return false;
    if (g_pSeatManager->m_seatGrab && !g_pSeatManager->m_seatGrab->accepts(W->wlSurface()->resource()))
        return false;
    if (hc::camadasExclusivas())
        return false;

    const auto MOUSE = g_pInputManager->getMouseCoordsInternal();
    const auto PMON  = W->m_monitor.lock();
    if (!PMON)
        return false;

    // A janela sob o cursor tem que ser esta (outra por cima tapa a barra).
    const auto SOB = Desktop::viewState()->hitTest().windowAt(MOUSE, Desktop::View::RESERVED_EXTENTS | Desktop::View::INPUT_EXTENTS | Desktop::View::ALLOW_FLOATING);
    if (SOB != W)
        return false;

    // Camadas por cima (barra do sistema, menus, prévias) têm a vez.
    PHLLS    ls = nullptr;
    Vector2D sc;
    Desktop::viewState()->hitTest().layerSurfaceAt(MOUSE, &PMON->m_layerSurfaceLayers[ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY], &sc, &ls);
    if (ls)
        return false;
    Desktop::viewState()->hitTest().layerSurfaceAt(MOUSE, &PMON->m_layerSurfaceLayers[ZWLR_LAYER_SHELL_V1_LAYER_TOP], &sc, &ls);
    if (ls)
        return false;
    return true;
}

void CBarra::aoBotao(Event::SCallbackInfo& info, IPointer::SButtonEvent e) {
    const auto W = dona();
    if (!W)
        return;

    if (e.state != WL_POINTER_BUTTON_STATE_PRESSED) {
        // soltar: só a barra que pegou o clique responde
        if (!m_cancelouDown)
            return;
        info.cancelled = true;
        m_cancelouDown = false;
        if (m_arrastando) {
            if (g_layoutManager->dragController()->target())
                g_layoutManager->endDragTarget();
            m_arrastando = false;
        }
        m_arrastoPendente = false;
        if (m_apertado != BOTAO_NENHUM) {
            const auto B = m_apertado;
            m_apertado   = BOTAO_NENHUM;
            damageEntire();
            if (botaoEm(cursorRelativo()) == B) {
                const auto ACAO = B == BOTAO_MIN ? "minimizar" : B == BOTAO_MAX ? "alternar" : "fechar";
                if (m_avisouSnap)
                    avisarSnap(false);
                m_sobre = BOTAO_NENHUM; // a janela muda de lugar; o hover volta no próximo movimento
                pedirAcao(W, ACAO);
            }
        }
        return;
    }

    if (!entradaValida())
        return;

    const auto REL = cursorRelativo();
    const auto BOX = caixaGlobal();
    if (REL.x < 0 || REL.y < 0 || REL.x >= BOX.w || REL.y >= BOX.h)
        return;

    // clique na barra: é desta janela, o app não recebe
    info.cancelled = true;
    m_cancelouDown = true;

    if (Desktop::focusState()->window() != W)
        Desktop::focusState()->fullWindowFocus(W, Desktop::FOCUS_REASON_CLICK);
    else if (W->wlSurface() && W->wlSurface()->resource())
        Desktop::focusState()->rawSurfaceFocus(W->wlSurface()->resource(), W);
    if (hc::flutuante(W))
        Desktop::windowState()->raise(W);

    const auto B = botaoEm(REL);
    if (B != BOTAO_NENHUM) {
        if (e.button == BTN_LEFT) {
            m_apertado = B;
            damageEntire();
        }
        return;
    }

    if (e.button == BTN_MIDDLE) {
        // botão do meio no título: manda a janela para trás das outras (como em muitos WMs)
        Desktop::windowState()->lower(W);
        return;
    }
    if (e.button != BTN_LEFT)
        return;

    const auto AGORA = Time::steadyNow();
    if (std::chrono::duration_cast<std::chrono::milliseconds>(AGORA - m_ultimoClique).count() < 400) {
        m_ultimoClique    = AGORA - std::chrono::seconds(10);
        m_arrastoPendente = false;
        pedirAcao(W, "alternar");
        return;
    }
    m_ultimoClique    = AGORA;
    m_arrastoPendente = true;
    m_pontoDown       = g_pInputManager->getMouseCoordsInternal();
}

void CBarra::aoMovimento(Vector2D coords) {
    if (!m_visivel)
        return;

    if (m_arrastoPendente && !m_arrastando) {
        if (coords.distance(m_pontoDown) >= 4.0)
            iniciarArrasto();
        return;
    }

    eBotao novo = BOTAO_NENHUM;
    if (entradaValida())
        novo = botaoEm(cursorRelativo());
    if (novo != m_sobre) {
        m_sobre = novo;
        damageEntire();
        const bool SOBREMAX = novo == BOTAO_MAX;
        if (SOBREMAX != m_avisouSnap)
            avisarSnap(SOBREMAX);
    }
}

void CBarra::iniciarArrasto() {
    m_arrastoPendente = false;
    m_arrastando      = true;
    const auto W      = dona();
    if (!W)
        return;
    // Maximizada/encaixada: volta ao tamanho de solta sob o cursor e segue o arrasto (Win11).
    const auto BOX = caixaGlobal();
    const auto FX  = BOX.w > 0 ? std::clamp((m_pontoDown.x - BOX.x) / BOX.w, 0.0, 1.0) : 0.5;
    const auto FY  = std::clamp(m_pontoDown.y - BOX.y, 0.0, (double)ALTURA_BARRA);
    const bool SOLTAR = estadoJanela(W) != EST_SOLTA;
    WP<CBarra> self   = m_self;
    g_pEventLoopManager->doLater([self, SOLTAR, FX, FY] {
        if (!self || !self->m_arrastando)
            return;
        const auto W = self->dona();
        if (!W)
            return;
        if (SOLTAR)
            pedirAcao(W, "soltar", std::format("{:.4f},{:.1f}", FX, FY));
        if (!g_layoutManager->dragController()->target())
            g_layoutManager->beginDragTarget(W->layoutTarget(), MBIND_MOVE);
    });
}

void CBarra::avisarSnap(bool sobre) {
    m_avisouSnap = sobre;
    const auto W = dona();
    if (!W)
        return;
    // Menu de layouts de encaixe do Win11 (botoes-janela) ancorado no centro do maximizar.
    const auto BOX = caixaGlobal();
    const auto BOT = botoesDe(W);
    const int  IDX = std::distance(BOT.begin(), std::ranges::find(BOT, 1));
    const auto X   = (int)std::round(BOX.x + BOX.w - LARGURA_BOTAO * (IDX + 0.5));
    const auto Y   = (int)std::round(BOX.y + BOX.h);
    if (sobre && IDX >= (int)BOT.size())
        return;
    const auto  MON = W->m_monitor.lock();
    const char* QS  = getenv("JANELAS_QS"); // teste: aponta para outra instância do botoes-janela
    Config::Supplementary::executor()->spawn(std::format("qs {} ipc call botoes sobreMaximizar {} {} {} {} {}", QS ? QS : "-c botoes-janela", enderecoDe(W), sobre ? "true" : "false",
                                                         X, Y, MON ? MON->m_name : std::string{"-"}));
}

// ── desenho ───────────────────────────────────────────────────────────────────

SP<Render::ITexture> CBarra::icone(eBotao b, float escala, const CHyprColor& cor, bool restaurar) {
    auto&          ic  = m_icones[b];
    const uint32_t HEX = cor.getAsHex();
    if (ic.tex && ic.escala == escala && ic.cor == HEX && ic.restaurar == restaurar)
        return ic.tex;

    const int LADO  = std::max(8, (int)std::round(8 * escala)); // glifo de 8 px lógicos
    const int MARG  = 2;
    const int TAM   = LADO + 2 * MARG;
    const double LW = std::max(1.0, (double)std::round(escala));
    const double O  = std::fmod(LW, 2.0) == 1.0 ? 0.5 : 0.0; // alinha linha ímpar ao pixel

    auto* SURF = cairo_image_surface_create(CAIRO_FORMAT_ARGB32, TAM, TAM);
    auto* CR   = cairo_create(SURF);
    cairo_set_operator(CR, CAIRO_OPERATOR_CLEAR);
    cairo_paint(CR);
    cairo_set_operator(CR, CAIRO_OPERATOR_OVER);
    cairo_set_source_rgba(CR, cor.r, cor.g, cor.b, cor.a);
    cairo_set_line_width(CR, LW);
    cairo_set_line_cap(CR, CAIRO_LINE_CAP_BUTT);
    cairo_set_line_join(CR, CAIRO_LINE_JOIN_MITER);

    const double X0 = MARG, Y0 = MARG, L = LADO;
    switch (b) {
        case BOTAO_MIN: {
            const double Y = std::floor(Y0 + L / 2.0) + O;
            cairo_move_to(CR, X0, Y);
            cairo_line_to(CR, X0 + L, Y);
            cairo_stroke(CR);
            break;
        }
        case BOTAO_MAX: {
            if (!restaurar) {
                cairo_rectangle(CR, X0 + O, Y0 + O, L - 2 * O - (O ? 0 : 0), L - 2 * O);
                cairo_stroke(CR);
            } else {
                // dois quadrados: o da frente embaixo à esquerda, o de trás só o contorno visível
                const double D = std::round(2 * escala);
                cairo_rectangle(CR, X0 + O, Y0 + D + O, L - D - 2 * O, L - D - 2 * O);
                cairo_stroke(CR);
                cairo_move_to(CR, X0 + D + O, Y0 + D);
                cairo_line_to(CR, X0 + D + O, Y0 + O);
                cairo_line_to(CR, X0 + L - O, Y0 + O);
                cairo_line_to(CR, X0 + L - O, Y0 + L - D - O);
                cairo_line_to(CR, X0 + L - D, Y0 + L - D - O);
                cairo_stroke(CR);
            }
            break;
        }
        case BOTAO_FECHAR: {
            cairo_set_line_cap(CR, CAIRO_LINE_CAP_ROUND);
            cairo_set_line_width(CR, LW * 1.05);
            cairo_move_to(CR, X0, Y0);
            cairo_line_to(CR, X0 + L, Y0 + L);
            cairo_move_to(CR, X0 + L, Y0);
            cairo_line_to(CR, X0, Y0 + L);
            cairo_stroke(CR);
            break;
        }
        default: break;
    }
    cairo_surface_flush(SURF);
    ic.tex       = g_pHyprRenderer->createTexture(SURF);
    ic.escala    = escala;
    ic.cor       = HEX;
    ic.restaurar = restaurar;
    cairo_destroy(CR);
    cairo_surface_destroy(SURF);
    return ic.tex;
}

#if JANELAS_HL057
void CBarra::draw(Render::CRenderContext& ctx, PHLMONITOR pMonitor, const float& a, const Render::SWindowRenderPresentation&) {
#else
void CBarra::draw(PHLMONITOR pMonitor, const float& a) {
#endif
    // o app pode trocar o modo de decoração a qualquer hora (Chromium: "usar barra de
    // título do sistema"); confere a cada quadro e refaz fora do desenho
    if (validMapped(m_janela) && barraDeveAparecer(dona()) != m_visivel && !m_reavaliacaoPendente) {
        m_reavaliacaoPendente = true;
        WP<CBarra> self       = m_self;
        g_pEventLoopManager->doLater([self] {
            if (!self)
                return;
            self->m_reavaliacaoPendente = false;
            self->reavaliar();
        });
    }
    if (!m_visivel || !validMapped(m_janela))
        return;
    const auto W = dona();
    if (!W->m_ruleApplicator->decorate().valueOrDefault())
        return;
#if JANELAS_HL057
    Render::IHyprRenderer::addPassElement(ctx, makeUnique<CBarraPass>(this, a));
#else
    g_pHyprRenderer->m_renderPass.add(makeUnique<CBarraPass>(this, a));
#endif
}

#if JANELAS_HL057
std::vector<UP<IPassElement>> CBarraPass::draw(Render::CRenderContext& ctx) {
    m_barra->renderizar(ctx, ctx.m_data.pMonitor.lock(), m_a);
    return {};
}

std::optional<CBox> CBarraPass::boundingBox(Render::CRenderContext& ctx) {
    return m_barra->caixaGlobal().translate(-ctx.m_data.pMonitor->m_position).expand(10);
}
#else
std::vector<UP<IPassElement>> CBarraPass::draw() {
    m_barra->renderizar(g_pHyprRenderer->m_renderData.pMonitor.lock(), m_a);
    return {};
}

std::optional<CBox> CBarraPass::boundingBox() {
    return m_barra->caixaGlobal().translate(-g_pHyprRenderer->m_renderData.pMonitor->m_position).expand(10);
}
#endif

void CBarra::renderizar(JN_CTX_P PHLMONITOR pMonitor, float a) {
    const auto W = dona();
    if (!W || !pMonitor)
        return;

    const auto& T      = tema();
    const bool  ATIVA  = Desktop::focusState()->window() == W;
    const float ESCALA = pMonitor->m_scale;

    const auto DECO = caixaGlobal();
    if (DECO.w < 1 || DECO.h < 1)
        return;

    const float ROUNDING   = hc::arredondamento(W) + hc::borda(W);
    const auto  SCALEDROUND = ROUNDING > 0 ? ROUNDING * ESCALA - 2 : 0;

    CBox barra = {DECO.x - pMonitor->m_position.x, DECO.y - pMonitor->m_position.y, DECO.w, DECO.h + ROUNDING * 3};
    barra.translate(hc::deslocamentoFlutuante(W)).scale(ESCALA).round();
    if (barra.w < 1 || barra.h < 1)
        return;

    CHyprColor fundo = T.fundo;
    fundo.a          = 1.0;

    g_pHyprOpenGL->scissor(JN_CTX barra);

    if (ROUNDING > 0) {
        // só os cantos de cima arredondados: recorta a área da janela com stencil
        CBox janela = {W->position(Desktop::View::IGeometric::GEOMETRIC_CURRENT).x + hc::deslocamentoFlutuante(W).x - pMonitor->m_position.x + 1,
                       W->position(Desktop::View::IGeometric::GEOMETRIC_CURRENT).y + hc::deslocamentoFlutuante(W).y - pMonitor->m_position.y + 1,
                       W->size(Desktop::View::IGeometric::GEOMETRIC_CURRENT).x - 2, W->size(Desktop::View::IGeometric::GEOMETRIC_CURRENT).y - 2};
        if (janela.w < 1 || janela.h < 1) {
            g_pHyprOpenGL->scissor(JN_CTX nullptr);
            return;
        }
        const auto WS = W->m_workspace;
        if (WS && !hc::fixada(W))
            janela.translate(WS->m_renderOffset->value());

        glClearStencil(0);
        glClear(GL_STENCIL_BUFFER_BIT);
        g_pHyprOpenGL->setCapStatus(GL_STENCIL_TEST, true);
        glStencilFunc(GL_ALWAYS, 1, -1);
        glStencilOp(GL_KEEP, GL_KEEP, GL_REPLACE);
        glColorMask(GL_FALSE, GL_FALSE, GL_FALSE, GL_FALSE);
        janela.scale(ESCALA).round();
        g_pHyprOpenGL->renderRect(JN_CTX janela, CHyprColor(0, 0, 0, 0), JN_RET{.round = (int)SCALEDROUND, .roundingPower = hc::potenciaArredondamento(W)});
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
        glStencilFunc(GL_NOTEQUAL, 1, -1);
        glStencilOp(GL_KEEP, GL_KEEP, GL_REPLACE);
    }

    g_pHyprOpenGL->renderRect(JN_CTX barra, comAlfa(fundo, a), JN_RET{.round = (int)SCALEDROUND, .roundingPower = hc::potenciaArredondamento(W)});

    if (ROUNDING > 0) {
        glClearStencil(0);
        glClear(GL_STENCIL_BUFFER_BIT);
        g_pHyprOpenGL->setCapStatus(GL_STENCIL_TEST, false);
        glStencilMask(-1);
        glStencilFunc(GL_ALWAYS, 1, 0xFF);
    }

    // área da barra sem o excesso de baixo
    CBox       caixa  = {barra.x, barra.y, std::round(DECO.w * ESCALA), std::round(DECO.h * ESCALA)};
    const auto BOTOES = botoesDe(W);
    const auto LB     = std::round(LARGURA_BOTAO * ESCALA);

    // botões: realce no hover/pressionado
    CHyprColor glifo = T.frente;
    glifo.a          = ATIVA ? 1.0 : 0.45;
    for (size_t i = 0; i < BOTOES.size(); ++i) {
        const auto B   = (eBotao)BOTOES[i];
        CBox       box = {caixa.x + caixa.w - LB * (i + 1), caixa.y, LB, caixa.h};
        box.round();
        const bool SOBRE = m_sobre == B && (m_apertado == BOTAO_NENHUM || m_apertado == B);
        const bool APERT = m_apertado == B && m_sobre == B;
        CHyprColor cor   = glifo;
        if (B == BOTAO_FECHAR && (SOBRE || APERT)) {
            const auto VERMELHO = APERT ? CHyprColor(0xB3 / 255.0, 0x26 / 255.0, 0x1A / 255.0, 1.0) : CHyprColor(0xC4 / 255.0, 0x2B / 255.0, 0x1C / 255.0, 1.0);
            g_pHyprOpenGL->renderRect(JN_CTX box, comAlfa(VERMELHO, a), JN_RET{});
            cor = CHyprColor(1, 1, 1, 1);
        } else if (SOBRE || APERT) {
            const auto REALCE = misturar(fundo, T.frente, APERT ? 0.06 : (T.claro ? 0.09 : 0.11));
            g_pHyprOpenGL->renderRect(JN_CTX box, comAlfa(REALCE, a), JN_RET{});
            if (APERT)
                cor.a *= 0.8;
        }
        const bool RESTAURAR = B == BOTAO_MAX && estadoJanela(W) == EST_MAX;
        const auto TEX       = icone(B, ESCALA, cor, RESTAURAR);
        if (TEX && TEX->m_texID != 0) {
            CBox ib = {box.x + (box.w - TEX->m_size.x) / 2.0, box.y + (box.h - TEX->m_size.y) / 2.0, TEX->m_size.x, TEX->m_size.y};
            ib.round();
            g_pHyprOpenGL->renderTexture(JN_CTX TEX, ib, JN_TEX{.a = a});
        }
    }

    // sem título: só os botões (barra compacta, a pedido do usuário)

    g_pHyprOpenGL->scissor(JN_CTX nullptr);
}
