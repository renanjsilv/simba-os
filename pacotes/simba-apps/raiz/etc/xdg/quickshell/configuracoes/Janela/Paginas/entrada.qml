import QtQuick
import QtQuick.Layouts
import qs.Comum
import qs.Janela

Pagina {
  id: pg
  titulo: I18n.t("Teclado, mouse e touchpad")
  subtitulo: I18n.t("Vale na hora e fica salvo num bloco no fim de ~/.config/hypr/input.lua (suas linhas continuam lá).")

  property var layouts: []
  property var variantes: []
  property bool touchpad: false
  property bool touchpadDesligado: false
  function v(k, p) { return Hypr.valor(k, p) }
  function definir(k, x) { Hypr.definir(k, x) }

  readonly property string layoutAtual: String(v("input:kb_layout", "us")).split(",")[0]
  onLayoutAtualChanged: carregarVariantes()
  function carregarVariantes() { Sistema.json([Sistema.ajudante, "variantes", layoutAtual], function(x) { if (x) pg.variantes = x }) }

  Component.onCompleted: {
    Hypr.recarregar()
    Sistema.json([Sistema.ajudante, "layouts"], function(x) { if (x) pg.layouts = x })
    carregarVariantes()
    Sistema.sh("simba-hw-touchpad >/dev/null && echo sim; test -f ~/.local/state/simba/toggles/hypr/touchpad-disabled-name && echo desligado", function(o) {
      pg.touchpad = o.indexOf("sim") >= 0
      pg.touchpadDesligado = o.indexOf("desligado") >= 0
    })
  }

  Aviso { visible: Hypr.erro !== ""; tipo: "perigo"; texto: I18n.t("O Hyprland recusou um ajuste: ") + Hypr.erro }

  // ── keyboard ─────────────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Teclado"); Layout.topMargin: 2 }
  Cartao {
    Linha {
      chave: "kbLayout"; glifo: Icones.keyboard
      titulo: I18n.t("Layout do teclado")
      descricao: String(pg.v("input:kb_layout", "")).indexOf(",") >= 0 ? I18n.t("Vários layouts configurados: ") + pg.v("input:kb_layout", "") : I18n.t("ABNT2 = Portuguese (Brazil)")
      Selecao {
        width: 280
        larguraLista: 340
        opcoes: pg.layouts
        atual: pg.layoutAtual
        onEscolhido: function(x) { Hypr.definir("input:kb_layout", x); Hypr.definir("input:kb_variant", ""); Navegacao.confirmar(I18n.t("Layout: ") + x, Icones.keyboard) }
      }
    }
    Linha {
      chave: "kbVariante"; glifo: Icones.keyboardVariant
      titulo: I18n.t("Variante")
      Selecao {
        width: 280
        larguraLista: 380
        opcoes: pg.variantes
        atual: String(pg.v("input:kb_variant", "")).split(",")[0]
        onEscolhido: function(x) { pg.definir("input:kb_variant", x) }
      }
    }
    Linha {
      chave: "capsLock"; glifo: Icones.formatLetterCase
      titulo: I18n.t("Tecla Caps Lock")
      readonly property string ops: String(pg.v("input:kb_options", ""))
      descricao: ops === "" ? I18n.t("Liga as maiúsculas") : (ops.indexOf("compose:caps") >= 0 ? I18n.t("Vira a tecla Compose (acentos e símbolos); maiúsculas com as duas Shift") : I18n.t("Opções: ") + ops)
      Segmentado {
        opcoes: [{ valor: "", rotulo: I18n.t("Maiúsculas") }, { valor: "compose:caps,shift:both_capslock_cancel", rotulo: I18n.t("Compose") }]
        atual: String(pg.v("input:kb_options", ""))
        onEscolhido: function(x) { pg.definir("input:kb_options", x) }
      }
    }
    Linha {
      chave: "repeticaoTaxa"; glifo: Icones.speedometer
      titulo: I18n.t("Velocidade de repetição")
      descricao: I18n.t("Quantas vezes por segundo uma tecla segurada se repete")
      Deslizante { width: 240; de: 10; ate: 80; valor: pg.v("input:repeat_rate", 40); sufixo: "/s"; onSolto: function(x) { pg.definir("input:repeat_rate", x) } }
    }
    Linha {
      chave: "repeticaoAtraso"; glifo: Icones.timer
      titulo: I18n.t("Atraso antes de repetir")
      Deslizante { width: 240; de: 150; ate: 800; passo: 25; valor: pg.v("input:repeat_delay", 250); sufixo: " ms"; onSolto: function(x) { pg.definir("input:repeat_delay", x) } }
    }
    Linha {
      chave: "numlock"; glifo: Icones.cpu64Bit
      titulo: I18n.t("Num Lock ligado ao entrar")
      Interruptor { ligado: pg.v("input:numlock_by_default", true); onAlternado: function(x) { pg.definir("input:numlock_by_default", x) } }
    }
    Linha {
      chave: "testeTeclado"; glifo: Icones.formatText
      titulo: I18n.t("Testar")
      descricao: I18n.t("Digite aqui para conferir o layout e a repetição")
      Campo { width: 280; dica: I18n.t("çãé ~ ´ ` ^ ? / | \\") }
    }
  }

  // ── mouse ────────────────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Mouse") }
  Cartao {
    Linha {
      chave: "mouseSensibilidade"; glifo: Icones.cursorDefault
      titulo: I18n.t("Velocidade do ponteiro")
      descricao: I18n.t("Vale para mouse e touchpad · 0 = padrão")
      Deslizante { width: 240; de: -1; ate: 1; passo: 0.05; casas: 2; valor: pg.v("input:sensitivity", 0); onSolto: function(x) { pg.definir("input:sensitivity", x) } }
    }
    Linha {
      chave: "mouseAceleracao"; glifo: Icones.speedometerMedium
      titulo: I18n.t("Aceleração do ponteiro")
      descricao: I18n.t("Sem aceleração = movimento 1:1, preferido para jogos")
      Segmentado {
        opcoes: [{ valor: "adaptive", rotulo: I18n.t("Adaptativa") }, { valor: "flat", rotulo: I18n.t("Sem aceleração") }]
        atual: pg.v("input:accel_profile", "") === "flat" ? "flat" : "adaptive"
        onEscolhido: function(x) { pg.definir("input:accel_profile", x) }
      }
    }
    Linha {
      chave: "mouseNatural"; glifo: Icones.swapVertical
      titulo: I18n.t("Rolagem natural")
      descricao: I18n.t("O conteúdo acompanha o dedo, como no celular")
      Interruptor { ligado: pg.v("input:natural_scroll", false); onAlternado: function(x) { pg.definir("input:natural_scroll", x) } }
    }
    Linha {
      chave: "mouseRolagem"; glifo: Icones.mouse
      titulo: I18n.t("Velocidade da rolagem")
      Deslizante { width: 240; de: 0.2; ate: 3; passo: 0.1; valor: pg.v("input:scroll_factor", 1); formatar: function(x) { return x.toFixed(1).replace(".", I18n.decimal) + "×" }; onSolto: function(x) { pg.definir("input:scroll_factor", x) } }
    }
    Linha {
      chave: "canhoto"; glifo: Icones.swapHorizontal
      titulo: I18n.t("Modo canhoto")
      descricao: I18n.t("Troca o botão esquerdo pelo direito")
      Interruptor { ligado: pg.v("input:left_handed", false); onAlternado: function(x) { pg.definir("input:left_handed", x) } }
    }
    Linha {
      chave: "focoMouse"; glifo: Icones.cursorPointer
      titulo: I18n.t("Foco segue o mouse")
      descricao: I18n.t("A janela sob o cursor recebe o teclado sem clicar. Desligado (como no Windows), a janela clicada vem para a frente de todas")
      Interruptor { ligado: pg.v("input:follow_mouse", 1) === 1; onAlternado: function(x) { pg.definir("input:follow_mouse", x ? 1 : 0) } }
    }
  }

  // ── touchpad ─────────────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Touchpad"); visible: pg.touchpad }
  Cartao {
    visible: pg.touchpad
    Linha {
      chave: "touchpadAtivo"; glifo: Icones.gestureTap
      titulo: I18n.t("Touchpad")
      descricao: pg.touchpadDesligado ? I18n.t("Desligado (útil com mouse)") : I18n.t("Ligado")
      Interruptor { ligado: !pg.touchpadDesligado; onAlternado: function(x) { Sistema.rodar(["simba-toggle-touchpad", x ? "on" : "off"], function() { pg.touchpadDesligado = !x }) } }
    }
    Linha {
      chave: "touchpadNatural"; glifo: Icones.swapVertical
      titulo: I18n.t("Rolagem natural")
      Interruptor { ligado: pg.v("input:touchpad:natural_scroll", false); onAlternado: function(x) { pg.definir("input:touchpad:natural_scroll", x) } }
    }
    Linha {
      chave: "toqueClique"; glifo: Icones.gestureTap
      titulo: I18n.t("Tocar para clicar")
      Interruptor { ligado: pg.v("input:touchpad:tap-to-click", true); onAlternado: function(x) { pg.definir("input:touchpad:tap-to-click", x) } }
    }
    Linha {
      chave: "cliqueDedos"; glifo: Icones.gestureTwoTap
      titulo: I18n.t("Clique com dois dedos = botão direito")
      descricao: I18n.t("Desligado, o botão direito é o canto inferior direito")
      Interruptor { ligado: pg.v("input:touchpad:clickfinger_behavior", true); onAlternado: function(x) { pg.definir("input:touchpad:clickfinger_behavior", x) } }
    }
    Linha {
      chave: "digitandoDesativa"; glifo: Icones.keyboardOutline
      titulo: I18n.t("Desativar enquanto digita")
      Interruptor { ligado: pg.v("input:touchpad:disable_while_typing", true); onAlternado: function(x) { pg.definir("input:touchpad:disable_while_typing", x) } }
    }
    Linha {
      chave: "touchpadRolagem"; glifo: Icones.gestureSwipe
      titulo: I18n.t("Velocidade da rolagem")
      Deslizante { width: 240; de: 0.1; ate: 2; passo: 0.05; valor: pg.v("input:touchpad:scroll_factor", 0.4); formatar: function(x) { return x.toFixed(2).replace(".", I18n.decimal) + "×" }; onSolto: function(x) { pg.definir("input:touchpad:scroll_factor", x) } }
    }
    Linha {
      chave: "arrastar3"; glifo: Icones.dragVariant
      titulo: I18n.t("Arrastar com três dedos")
      descricao: I18n.t("Move janelas e seleciona texto sem segurar o clique")
      Interruptor { ligado: pg.v("input:touchpad:drag_3fg", 0) > 0; onAlternado: function(x) { pg.definir("input:touchpad:drag_3fg", x ? 1 : 0) } }
    }
    Linha {
      chave: "gestos"; glifo: Icones.gestureSwipeHorizontal
      titulo: I18n.t("Trocar de área de trabalho com três dedos")
      descricao: I18n.t("Deslize para os lados")
      Interruptor { ligado: Preferencias.obter("gestos", false); onAlternado: function(x) { Hypr.definirGestos(x) } }
    }
  }

  RowLayout {
    Layout.fillWidth: true
    Layout.topMargin: 14
    Item { Layout.fillWidth: true }
    Botao {
      glifo: Icones.backupRestore
      texto: I18n.t("Restaurar padrões")
      onClicado: { Hypr.restaurar(Hypr.entrada); Hypr.definirGestos(false); Navegacao.confirmar(I18n.t("Entrada restaurada"), Icones.backupRestore) }
    }
  }
}
