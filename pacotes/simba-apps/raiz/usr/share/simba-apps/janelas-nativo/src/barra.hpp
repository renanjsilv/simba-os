#pragma once

#include "janelas.hpp"

// Barra de título estilo Windows 11: título à esquerda; minimizar, maximizar/restaurar e
// fechar à direita (46×32, fechar fica vermelho no hover). Só aparece quando o app pediu
// decoração do servidor (ver modoDecoracao()) e a janela não está em tela cheia.
class CBarra : public IHyprWindowDecoration {
  public:
    CBarra(PHLWINDOW);
    virtual ~CBarra();

    virtual SDecorationPositioningInfo getPositioningInfo();
    virtual void                       onPositioningReply(const SDecorationPositioningReply& reply);
#if JANELAS_HL057
    virtual void draw(Render::CRenderContext& ctx, PHLMONITOR, const float& a, const Render::SWindowRenderPresentation& presentation);
#else
    virtual void                       draw(PHLMONITOR, float const& a);
#endif
    virtual eDecorationType            getDecorationType();
    virtual void                       updateWindow(PHLWINDOW);
    virtual void                       damageEntire();
    virtual eDecorationLayer           getDecorationLayer();
    virtual uint64_t                   getDecorationFlags();
    virtual std::string                getDisplayName();

    PHLWINDOW                          dona();
    // Recalcula se a barra deve aparecer (modo de decoração, tela cheia, regras).
    void                               reavaliar();
    void                               aoRecarregar();
    bool                               visivel() const {
        return m_visivel;
    }
    void renderizar(JN_CTX_P PHLMONITOR, float a);
    CBox caixaGlobal();

    WP<CBarra> m_self;
    bool       m_reavaliacaoPendente = false;

  private:
    enum eBotao : int8_t {
        BOTAO_NENHUM = -1,
        BOTAO_MIN    = 0,
        BOTAO_MAX,
        BOTAO_FECHAR,
    };

    PHLWINDOWREF         m_janela;
    CBox                 m_caixa;
    bool                 m_visivel = false;

    SP<Render::ITexture> m_texTitulo;
    std::string          m_ultimoTitulo;
    float                m_escalaTitulo = 0;
    int                  m_largTitulo   = 0;
    bool                 m_focoTitulo   = false;
    uint32_t             m_corTitulo    = 0;

    // ícones dos botões: [botão][claro/escuro do glifo]: recriados ao mudar escala/estado
    struct SIcone {
        SP<Render::ITexture> tex;
        float                escala = 0;
        uint32_t             cor    = 0;
        bool                 restaurar = false;
    };
    std::array<SIcone, 3> m_icones;

    eBotao                m_sobre       = BOTAO_NENHUM; // mouse em cima
    eBotao                m_apertado    = BOTAO_NENHUM; // botão pressionado (ação ao soltar)
    bool                  m_arrastoPendente = false;
    bool                  m_arrastando  = false;
    bool                  m_cancelouDown = false;
    Vector2D              m_pontoDown;
    Time::steady_tp       m_ultimoClique = Time::steadyNow();
    bool                  m_avisouSnap  = false;

    CHyprSignalListener   m_ouvBotao, m_ouvMovimento, m_ouvToqueDown, m_ouvToqueUp;

    Vector2D              cursorRelativo();
    eBotao                botaoEm(const Vector2D& rel);
    bool                  entradaValida();
    void                  aoBotao(Event::SCallbackInfo& info, IPointer::SButtonEvent e);
    void                  aoMovimento(Vector2D coords);
    void                  iniciarArrasto();
    void                  avisarSnap(bool sobre);
    SP<Render::ITexture>  icone(eBotao b, float escala, const CHyprColor& cor, bool restaurar);
};

class CBarraPass : public IPassElement {
  public:
    CBarraPass(CBarra* barra, float a) : m_barra(barra), m_a(a) {}
    virtual ~CBarraPass() = default;

#if JANELAS_HL057
    virtual std::vector<UP<IPassElement>> draw(Render::CRenderContext& ctx) override;
    virtual bool                          needsLiveBlur(Render::CRenderContext&) override {
        return false;
    }
    virtual bool needsPrecomputeBlur(Render::CRenderContext&) override {
        return false;
    }
    virtual std::optional<CBox> boundingBox(Render::CRenderContext& ctx) override;
#else
    virtual std::vector<UP<IPassElement>> draw() override;
    virtual bool                          needsLiveBlur() override {
        return false;
    }
    virtual bool needsPrecomputeBlur() override {
        return false;
    }
    virtual std::optional<CBox> boundingBox() override;
#endif
    virtual const char*         passName() override {
        return "CBarraPass";
    }
    virtual ePassElementType type() override {
        return EK_CUSTOM;
    }

  private:
    CBarra* m_barra = nullptr;
    float   m_a     = 1.F;
};
