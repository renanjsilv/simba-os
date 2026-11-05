import QtQuick
import QtQuick.Layouts
import QtQuick.Effects
import Quickshell
import qs.Comum
import qs.Janela

Pagina {
  id: pg
  titulo: I18n.t("Janelas e animações")
  subtitulo: I18n.t("Espaços, bordas, cantos, transparência e movimento. A prévia mostra o resultado antes de soltar o controle.")

  // Draft values while a slider is being dragged (the preview follows them).
  property var rascunho: ({})
  property bool semEspacos: false
  function v(k, padrao) { return rascunho[k] !== undefined ? rascunho[k] : Hypr.valor(k, padrao) }
  function arrastar(k, x) { var r = Object.assign({}, rascunho); r[k] = x; rascunho = r }
  function soltar(k, x) { Hypr.definir(k, x); var r = Object.assign({}, rascunho); delete r[k]; rascunho = r }
  function definir(k, x) { Hypr.definir(k, x) }

  Component.onCompleted: {
    carregarBotoes()
    Hypr.recarregar()
    Sistema.sh("test -f ~/.local/state/simba/toggles/hypr/window-no-gaps.lua && echo sim", function(o) { pg.semEspacos = o.trim() === "sim" })
  }

  Aviso {
    visible: pg.semEspacos
    tipo: "aviso"
    texto: I18n.t("O modo “sem espaços” do sistema está ligado e zera espaços, bordas e cantos por cima destes ajustes.")
    Botao { texto: I18n.t("Desligar"); compacto: true; onClicado: Sistema.rodar(["simba-hyprland-window-gaps-toggle"], function() { pg.semEspacos = false; Hypr.recarregar() }) }
  }
  Aviso {
    visible: Hypr.erro !== ""
    tipo: "perigo"
    texto: I18n.t("O Hyprland recusou um ajuste: ") + Hypr.erro
  }

  // ── live preview ─────────────────────────────────────────────────────────
  Rectangle {
    id: previa
    Layout.fillWidth: true
    Layout.preferredHeight: 250
    radius: Tema.raioGrande
    color: Tema.superficie
    border.width: 1
    border.color: Tema.linha
    clip: true

    readonly property real escala: 0.62
    readonly property real gi: pg.v("general:gaps_in", 5) * escala
    readonly property real go: pg.v("general:gaps_out", 10) * escala
    readonly property real bs: Math.max(0, pg.v("general:border_size", 2) * escala)
    readonly property real rd: pg.v("decoration:rounding", 0) * escala
    readonly property real opA: pg.v("decoration:active_opacity", 1)
    readonly property real opI: pg.v("decoration:inactive_opacity", 1)
    readonly property bool dim: pg.v("decoration:dim_inactive", false)
    readonly property real dimF: pg.v("decoration:dim_strength", 0.5)
    readonly property bool sombra: pg.v("decoration:shadow:enabled", false)
    readonly property real sombraR: pg.v("decoration:shadow:range", 4)
    readonly property bool blur: pg.v("decoration:blur:enabled", false)

    Rectangle {
      id: tela
      anchors.fill: parent
      anchors.margins: 14
      radius: Tema.raio
      color: Tema.fundo
      clip: true
      Image {
        id: papelPrevia
        anchors.fill: parent
        source: "file://" + Tema.estadoSimba + "/background"
        fillMode: Image.PreserveAspectCrop
        sourceSize.width: 700
        asynchronous: true
        cache: false
      }
      // bar
      Rectangle { id: barra; width: parent.width; height: 14; color: Tema.alfa(Tema.fundo, 0.9) }

      Item {
        id: areaJanelas
        x: previa.go; y: barra.height + previa.go
        width: parent.width - 2 * previa.go
        height: parent.height - barra.height - 2 * previa.go
        Behavior on x { NumberAnimation { duration: Tema.medio; easing.type: Tema.curva } }
        Behavior on y { NumberAnimation { duration: Tema.medio; easing.type: Tema.curva } }

        Repeater {
          model: [
            { x: 0, y: 0, w: 0.56, h: 1, ativa: true },
            { x: 0.56, y: 0, w: 0.44, h: 0.5, ativa: false },
            { x: 0.56, y: 0.5, w: 0.44, h: 0.5, ativa: false }
          ]
          delegate: Item {
            id: jan
            required property var modelData
            readonly property real g: previa.gi / 2
            x: modelData.x * areaJanelas.width + (modelData.x > 0 ? g : 0)
            y: modelData.y * areaJanelas.height + (modelData.y > 0 ? g : 0)
            width: modelData.w * areaJanelas.width - (modelData.x > 0 || modelData.w < 1 ? g : 0)
            height: modelData.h * areaJanelas.height - (modelData.h < 1 ? g : 0)
            Behavior on x { NumberAnimation { duration: Tema.medio; easing.type: Tema.curva } }
            Behavior on y { NumberAnimation { duration: Tema.medio; easing.type: Tema.curva } }
            Behavior on width { NumberAnimation { duration: Tema.medio; easing.type: Tema.curva } }
            Behavior on height { NumberAnimation { duration: Tema.medio; easing.type: Tema.curva } }

            Rectangle {
              id: formaSombra
              anchors.fill: corpo
              radius: corpo.radius
              color: "black"
              visible: false
            }
            MultiEffect {
              anchors.fill: formaSombra
              source: formaSombra
              visible: previa.sombra
              shadowEnabled: true
              shadowBlur: Math.min(1, previa.sombraR / 20)
              shadowColor: "#000000"
              shadowOpacity: 0.7
              blurMax: 32
              autoPaddingEnabled: true
              opacity: 0.9
            }
            // blurred wallpaper behind translucent windows
            ShaderEffectSource {
              id: recorte
              anchors.fill: corpo
              sourceItem: papelPrevia
              sourceRect: Qt.rect(areaJanelas.x + jan.x, areaJanelas.y + jan.y, jan.width, jan.height)
              visible: false
            }
            MultiEffect {
              anchors.fill: corpo
              source: recorte
              visible: previa.blur && (jan.modelData.ativa ? previa.opA : previa.opI) < 1
              blurEnabled: true
              blur: 0.8
              blurMax: 24
              maskEnabled: true
              maskSource: mascaraCorpo
            }
            Rectangle { id: mascaraCorpo; anchors.fill: corpo; radius: corpo.radius; visible: false; layer.enabled: true }

            Rectangle {
              id: corpo
              anchors.fill: parent
              radius: previa.rd
              color: Tema.alfa(Tema.fundo, jan.modelData.ativa ? previa.opA : previa.opI)
              border.width: previa.bs
              border.color: jan.modelData.ativa ? Tema.acento : "#595959"
              Behavior on radius { NumberAnimation { duration: Tema.medio } }
              Behavior on border.width { NumberAnimation { duration: Tema.medio } }
              Column {
                x: 10 + previa.bs; y: 10 + previa.bs
                spacing: 5
                Repeater {
                  model: jan.modelData.ativa ? 7 : 3
                  Rectangle {
                    required property int index
                    width: (jan.width - 30) * [0.5, 0.8, 0.35, 0.65, 0.25, 0.7, 0.45][index]
                    height: 4; radius: 2
                    color: [Tema.cor("green", Tema.texto), Tema.texto2, Tema.cor("blue", Tema.texto3), Tema.texto3, Tema.cor("yellow", Tema.texto2), Tema.texto3, Tema.cor("magenta", Tema.texto3)][index]
                  }
                }
              }
              Rectangle {
                anchors.fill: parent
                radius: parent.radius
                color: "black"
                opacity: !jan.modelData.ativa && previa.dim ? previa.dimF * 0.8 : 0
                Behavior on opacity { NumberAnimation { duration: Tema.medio } }
              }
            }
          }
        }
      }
    }
    Rectangle {
      anchors.right: parent.right; anchors.bottom: parent.bottom; anchors.margins: 22
      width: legenda.implicitWidth + 16; height: 24; radius: Tema.raio > 0 ? 12 : 0
      color: Tema.alfa(Tema.janela, 0.85)
      Texto { id: legenda; anchors.centerIn: parent; text: I18n.t("Prévia"); font.pixelSize: Tema.tLegenda; color: Tema.texto2 }
    }
  }

  // ── spacing ──────────────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Espaços e bordas") }
  Cartao {
    Linha {
      chave: "gapsIn"; glifo: Icones.arrowSplitVertical
      titulo: I18n.t("Espaço entre janelas"); descricao: I18n.t("Padrão do sistema: 5 px")
      Deslizante { width: 240; de: 0; ate: 30; valor: Hypr.valor("general:gaps_in", 5); sufixo: " px"
        onMovido: function(x) { pg.arrastar("general:gaps_in", x) }
        onSolto: function(x) { pg.soltar("general:gaps_in", x) } }
    }
    Linha {
      chave: "gapsOut"; glifo: Icones.borderAll
      titulo: I18n.t("Margem da tela"); descricao: I18n.t("Distância até a borda da tela · padrão 10 px")
      Deslizante { width: 240; de: 0; ate: 60; valor: Hypr.valor("general:gaps_out", 10); sufixo: " px"
        onMovido: function(x) { pg.arrastar("general:gaps_out", x) }
        onSolto: function(x) { pg.soltar("general:gaps_out", x) } }
    }
    Linha {
      chave: "borda"; glifo: Icones.shapeSquareRoundedPlus
      titulo: I18n.t("Espessura da borda"); descricao: I18n.t("A cor vem do tema · padrão 2 px")
      Deslizante { width: 240; de: 0; ate: 10; valor: Hypr.valor("general:border_size", 2); sufixo: " px"
        onMovido: function(x) { pg.arrastar("general:border_size", x) }
        onSolto: function(x) { pg.soltar("general:border_size", x) } }
    }
    Linha {
      chave: "arredondamento"; glifo: Icones.roundedCorner
      titulo: I18n.t("Cantos arredondados"); descricao: I18n.t("Também arredonda este app, a barra e os menus do sistema")
      Deslizante { width: 240; de: 0; ate: 24; valor: Hypr.valor("decoration:rounding", 0); sufixo: " px"
        onMovido: function(x) { pg.arrastar("decoration:rounding", x) }
        onSolto: function(x) { pg.soltar("decoration:rounding", x) } }
    }
    Linha {
      id: linhaCurva
      chave: "curvatura"; glifo: Icones.sineWave
      titulo: I18n.t("Suavidade dos cantos"); descricao: I18n.t("2 = círculo · 4 ou mais = “squircle”, como no macOS")
      habilitado: Hypr.valor("decoration:rounding", 0) > 0
      Deslizante { width: 240; de: 1; ate: 10; passo: 0.5; casas: 1; valor: Hypr.valor("decoration:rounding_power", 2); habilitado: linhaCurva.habilitado
        onSolto: function(x) { pg.definir("decoration:rounding_power", x) } }
    }
  }

  // ── effects ──────────────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Transparência e efeitos") }
  Cartao {
    Linha {
      chave: "opacidadeAtiva"; glifo: Icones.opacity
      titulo: I18n.t("Opacidade da janela ativa"); descricao: I18n.t("Multiplica a opacidade padrão do sistema")
      Deslizante { width: 240; de: 0.5; ate: 1; passo: 0.01; valor: Hypr.valor("decoration:active_opacity", 1)
        formatar: function(x) { return Math.round(x * 100) + "%" }
        onMovido: function(x) { pg.arrastar("decoration:active_opacity", x) }
        onSolto: function(x) { pg.soltar("decoration:active_opacity", x) } }
    }
    Linha {
      chave: "opacidadeInativa"; glifo: Icones.opacity
      titulo: I18n.t("Opacidade das janelas inativas")
      Deslizante { width: 240; de: 0.5; ate: 1; passo: 0.01; valor: Hypr.valor("decoration:inactive_opacity", 1)
        formatar: function(x) { return Math.round(x * 100) + "%" }
        onMovido: function(x) { pg.arrastar("decoration:inactive_opacity", x) }
        onSolto: function(x) { pg.soltar("decoration:inactive_opacity", x) } }
    }
    Linha {
      chave: "escurecer"; glifo: Icones.contrast
      titulo: I18n.t("Escurecer janelas inativas"); descricao: I18n.t("Dá destaque à janela em foco")
      expandido: Hypr.valor("decoration:dim_inactive", false)
      Interruptor { ligado: Hypr.valor("decoration:dim_inactive", false); onAlternado: function(x) { pg.definir("decoration:dim_inactive", x) } }
      extra: RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: 48
        Texto { text: I18n.t("Intensidade"); color: Tema.texto2; Layout.fillWidth: true }
        Deslizante { Layout.preferredWidth: 240; de: 0.05; ate: 0.9; passo: 0.05; valor: Hypr.valor("decoration:dim_strength", 0.5)
          formatar: function(x) { return Math.round(x * 100) + "%" }
          onMovido: function(x) { pg.arrastar("decoration:dim_strength", x) }
          onSolto: function(x) { pg.soltar("decoration:dim_strength", x) } }
      }
    }
    Linha {
      chave: "desfoque"; glifo: Icones.blur
      titulo: I18n.t("Desfoque (blur)"); descricao: I18n.t("Vidro fosco atrás de janelas translúcidas. Usa mais GPU.")
      expandido: Hypr.valor("decoration:blur:enabled", false)
      Interruptor { ligado: Hypr.valor("decoration:blur:enabled", false); onAlternado: function(x) { pg.definir("decoration:blur:enabled", x) } }
      extra: [
        RowLayout {
          Layout.fillWidth: true; Layout.leftMargin: 48
          Texto { text: I18n.t("Raio"); color: Tema.texto2; Layout.fillWidth: true }
          Deslizante { Layout.preferredWidth: 240; de: 1; ate: 20; valor: Hypr.valor("decoration:blur:size", 8)
            onSolto: function(x) { pg.definir("decoration:blur:size", x) } }
        },
        RowLayout {
          Layout.fillWidth: true; Layout.leftMargin: 48
          Texto { text: I18n.t("Passadas (qualidade)"); color: Tema.texto2; Layout.fillWidth: true }
          Deslizante { Layout.preferredWidth: 240; de: 1; ate: 4; valor: Hypr.valor("decoration:blur:passes", 1)
            onSolto: function(x) { pg.definir("decoration:blur:passes", x) } }
        }
      ]
    }
    Linha {
      chave: "sombras"; glifo: Icones.boxShadow
      titulo: I18n.t("Sombras"); descricao: I18n.t("Profundidade sob as janelas")
      expandido: Hypr.valor("decoration:shadow:enabled", false)
      Interruptor { ligado: Hypr.valor("decoration:shadow:enabled", false); onAlternado: function(x) { pg.definir("decoration:shadow:enabled", x) } }
      extra: RowLayout {
        Layout.fillWidth: true; Layout.leftMargin: 48
        Texto { text: I18n.t("Alcance"); color: Tema.texto2; Layout.fillWidth: true }
        Deslizante { Layout.preferredWidth: 240; de: 1; ate: 40; valor: Hypr.valor("decoration:shadow:range", 4); sufixo: " px"
          onMovido: function(x) { pg.arrastar("decoration:shadow:range", x) }
          onSolto: function(x) { pg.soltar("decoration:shadow:range", x) } }
      }
    }
  }

  // ── motion ───────────────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Movimento") }
  Cartao {
    Linha {
      chave: "animacoes"; glifo: Icones.animationPlay
      titulo: I18n.t("Animações"); descricao: I18n.t("Abrir, fechar e mover janelas e camadas. Este app também respeita.")
      Interruptor { ligado: Hypr.valor("animations:enabled", true); onAlternado: function(x) { pg.definir("animations:enabled", x) } }
    }
    Linha {
      id: linhaVel
      chave: "velocidade"; glifo: Icones.speedometer
      titulo: I18n.t("Velocidade das animações")
      habilitado: Hypr.valor("animations:enabled", true)
      Segmentado {
        habilitado: linhaVel.habilitado
        opcoes: [{ valor: 0.6, rotulo: I18n.t("Rápida") }, { valor: 1.0, rotulo: I18n.t("Padrão") }, { valor: 1.5, rotulo: I18n.t("Suave") }, { valor: 2.2, rotulo: I18n.t("Lenta") }]
        atual: Number(Preferencias.obter("animVelocidade", 1.0))
        onEscolhido: function(x) { Hypr.definirVelocidade(x) }
      }
    }
  }

  // ── window buttons (separate component: ~/.config/quickshell/botoes-janela) ─
  property bool botoesAtivos: false
  property var botoesCfg: ({ mostrar: [], ocultar: [] })
  readonly property string botoesArquivo: Sistema.home + "/.config/botoes-janela/config.json"
  function carregarBotoes() {
    Sistema.sh("systemctl --user is-active botoes-janela.service", function(o) { pg.botoesAtivos = o.trim() === "active" })
    Sistema.sh("cat " + Sistema.q(botoesArquivo) + " 2>/dev/null", function(o) {
      try { var v = JSON.parse(o); pg.botoesCfg = { mostrar: v.mostrar || [], ocultar: v.ocultar || [] } } catch (e) {}
    })
  }
  function salvarBotoes(cfg) {
    pg.botoesCfg = cfg
    var texto = JSON.stringify(cfg, null, 2) + "\n"
    Sistema.sh("mkdir -p ~/.config/botoes-janela && cat > " + Sistema.q(botoesArquivo + ".tmp") + " && mv -f " + Sistema.q(botoesArquivo + ".tmp") + " " + Sistema.q(botoesArquivo),
               function() { Navegacao.confirmar(I18n.t("Botões de janela atualizados"), Icones.dockWindow) }, texto)
  }

  Secao { titulo: I18n.t("Botões de janela"); detalhe: I18n.t("Minimizar, maximizar e fechar no canto superior direito das janelas que não desenham botões próprios (componente botoes-janela).") }
  Cartao {
    Linha {
      id: linhaBotoes
      chave: "botoesJanela"; glifo: Icones.dotsHorizontal
      titulo: I18n.t("Botões de janela (minimizar, maximizar, fechar)")
      descricao: pg.botoesAtivos ? I18n.t("Ligados · janelas minimizadas voltam pelo aviso na base da tela") : I18n.t("Desligados")
      expandido: pg.botoesAtivos
      Interruptor {
        ligado: pg.botoesAtivos
        onAlternado: function(x) {
          pg.botoesAtivos = x
          Sistema.rodar(["systemctl", "--user", x ? "enable" : "disable", "--now", "botoes-janela.service"], function() { pg.carregarBotoes() })
        }
      }
      extra: [
        RowLayout {
          Layout.fillWidth: true; Layout.leftMargin: 48
          Texto { text: I18n.t("Sempre mostrar em"); color: Tema.texto2; Layout.preferredWidth: 150 }
          Campo {
            Layout.fillWidth: true
            dica: I18n.t("classes (regex), separadas por vírgula — ex.: ^code$, steam")
            text: pg.botoesCfg.mostrar.join(", ")
            onEditingFinished: pg.salvarBotoes({ mostrar: text.split(",").map(function(t) { return t.trim() }).filter(function(t) { return t }), ocultar: pg.botoesCfg.ocultar })
          }
        },
        RowLayout {
          Layout.fillWidth: true; Layout.leftMargin: 48
          Texto { text: I18n.t("Nunca mostrar em"); color: Tema.texto2; Layout.preferredWidth: 150 }
          Campo {
            Layout.fillWidth: true
            dica: I18n.t("classes (regex), separadas por vírgula")
            text: pg.botoesCfg.ocultar.join(", ")
            onEditingFinished: pg.salvarBotoes({ mostrar: pg.botoesCfg.mostrar, ocultar: text.split(",").map(function(t) { return t.trim() }).filter(function(t) { return t }) })
          }
        },
        Texto {
          Layout.leftMargin: 48
          text: I18n.t("A classe de uma janela aparece em “hyprctl clients”. Vale na hora.")
          color: Tema.texto3; font.pixelSize: Tema.tLegenda
        }
      ]
    }
  }

  // ── behaviour ────────────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Comportamento") }
  Cartao {
    Linha {
      chave: "layout"; glifo: Icones.viewDashboard
      titulo: I18n.t("Organização das janelas")
      descricao: Hypr.valor("general:layout", "dwindle") === "lua:janelas" ? I18n.t("Cada janela abre maximizada; encaixe com Super+setas ou parando o mouse no maximizar")
        : Hypr.valor("general:layout", "dwindle") === "scrolling" ? I18n.t("Colunas lado a lado que rolam, como no niri") : (Hypr.valor("general:layout", "dwindle") === "master" ? I18n.t("Uma janela principal e as outras empilhadas") : I18n.t("Cada nova janela divide o espaço ao meio"))
      Segmentado {
        opcoes: [{ valor: "lua:janelas", rotulo: I18n.t("Windows") }, { valor: "dwindle", rotulo: I18n.t("Espiral") }, { valor: "master", rotulo: I18n.t("Mestre") }, { valor: "scrolling", rotulo: I18n.t("Rolagem") }]
        atual: Hypr.valor("general:layout", "dwindle")
        onEscolhido: function(x) { pg.definir("general:layout", x) }
      }
    }
    Linha {
      chave: "redimensionarBorda"; glifo: Icones.arrowExpand
      titulo: I18n.t("Redimensionar pelas bordas"); descricao: I18n.t("Arraste a borda de uma janela com o mouse")
      Interruptor { ligado: Hypr.valor("general:resize_on_border", false); onAlternado: function(x) { pg.definir("general:resize_on_border", x) } }
    }
    Linha {
      chave: "focoAtivar"; glifo: Icones.bellRing
      titulo: I18n.t("Focar janelas que pedem atenção"); descricao: I18n.t("Um app que se ativa (ex.: link aberto no navegador) vem para a frente")
      Interruptor { ligado: Hypr.valor("misc:focus_on_activate", true); onAlternado: function(x) { pg.definir("misc:focus_on_activate", x) } }
    }
    Linha {
      chave: "cursorDigitar"; glifo: Icones.cursorDefault
      titulo: I18n.t("Ocultar cursor ao digitar")
      Interruptor { ligado: Hypr.valor("cursor:hide_on_key_press", true); onAlternado: function(x) { pg.definir("cursor:hide_on_key_press", x) } }
    }
    Linha {
      chave: "cursorParado"; glifo: Icones.timer
      titulo: I18n.t("Ocultar cursor parado")
      Selecao {
        width: 170
        opcoes: [{ valor: 0, rotulo: I18n.t("Nunca") }, { valor: 3, rotulo: I18n.t("Após 3 s") }, { valor: 5, rotulo: I18n.t("Após 5 s") }, { valor: 10, rotulo: I18n.t("Após 10 s") }, { valor: 30, rotulo: I18n.t("Após 30 s") }]
        atual: Math.round(Hypr.valor("cursor:inactive_timeout", 0))
        onEscolhido: function(x) { pg.definir("cursor:inactive_timeout", x) }
      }
    }
  }

  RowLayout {
    Layout.fillWidth: true
    Layout.topMargin: 14
    Texto { text: I18n.t("Os ajustes ficam num bloco marcado no fim de ~/.config/hypr/looknfeel.lua."); color: Tema.texto3; font.pixelSize: Tema.tLegenda + 1; Layout.fillWidth: true; wrapMode: Text.WordWrap }
    Botao {
      glifo: Icones.backupRestore
      texto: I18n.t("Restaurar padrões do sistema")
      onClicado: {
        Hypr.restaurar(Hypr.looknfeel)
        Hypr.definirVelocidade(1.0)
        Navegacao.confirmar(I18n.t("Padrões restaurados"), Icones.backupRestore)
      }
    }
  }
}
