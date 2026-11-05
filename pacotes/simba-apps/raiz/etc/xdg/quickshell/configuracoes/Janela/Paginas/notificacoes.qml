import QtQuick
import QtQuick.Layouts
import qs.Comum
import qs.Janela

Pagina {
  id: pg
  titulo: I18n.t("Notificações")
  subtitulo: I18n.t("Os avisos que aparecem no canto da tela (servidor de notificações do Simba OS).")

  property bool dnd: false
  property var historico: []

  function carregar() {
    Sistema.sh("simba-shell notifications isDnd", function(o) { pg.dnd = o.trim() === "on" })
    Sistema.json([Sistema.ajudante, "notificacoes"], function(v) { if (v) pg.historico = v })
  }
  Component.onCompleted: carregar()
  Timer { interval: 4000; running: true; repeat: true; onTriggered: pg.carregar() }

  function quando(ms) {
    var d = (Date.now() - ms) / 1000
    if (d < 60) return "agora"
    if (d < 3600) return I18n.t("há ") + Math.round(d / 60) + " min"
    if (d < 86400) return I18n.t("há ") + Math.round(d / 3600) + " h"
    return Qt.formatDateTime(new Date(ms), "dd/MM HH:mm")
  }

  Cartao {
    Linha {
      chave: "naoPerturbe"; glifo: pg.dnd ? Icones.bellOff : Icones.bell
      titulo: I18n.t("Não perturbe")
      descricao: pg.dnd ? I18n.t("Notificações silenciadas — elas continuam indo para o histórico") : I18n.t("Notificações aparecem normalmente · Super+Ctrl+, alterna")
      Interruptor {
        ligado: pg.dnd
        onAlternado: function(x) {
          pg.dnd = x
          Sistema.sh("simba-shell notifications setDnd " + (x ? "on" : "off") + " >/dev/null; simba-shell -q simba.indicators refresh", function() { pg.carregar() })
        }
      }
    }
    Linha {
      chave: "testeNotif"; glifo: Icones.messageText
      titulo: I18n.t("Enviar uma notificação de teste")
      Botao { texto: I18n.t("Enviar"); onClicado: Sistema.solto(["simba-notification-send", "-g", "󰂚", "Configurações", I18n.t("Assim ficam as notificações com o tema ") + Tema.nome + "."]) }
    }
  }

  RowLayout {
    Layout.fillWidth: true
    Layout.topMargin: 18
    Secao { titulo: I18n.t("Recentes"); detalhe: I18n.t("As últimas ") + pg.historico.length + I18n.t(" notificações (o sistema guarda até 10)."); Layout.topMargin: 0 }
    Ancora { chave: "historico"; Layout.preferredWidth: 0 }
    Botao { texto: I18n.t("Mostrar de novo"); glifo: Icones.history; compacto: true; onClicado: Sistema.solto(["simba-shell", "notifications", "showHistory"]) }
    Botao {
      id: limpar
      texto: I18n.t("Limpar"); glifo: Icones.broom; compacto: true
      onClicado: Sistema.rodar(["simba-shell", "notifications", "clear"], function() { pg.carregar(); Navegacao.confirmar(I18n.t("Histórico limpo"), Icones.broom) })
    }
  }
  Ancora { chave: "limparNotif" }
  Cartao {
    visible: pg.historico.length > 0
    Repeater {
      model: pg.historico
      delegate: Linha {
        required property var modelData
        glifo: modelData.glyph || Icones.bell
        titulo: (modelData.app ? modelData.app + " · " : "") + (modelData.summary || "")
        descricao: String(modelData.body || "").replace(/<[^>]+>/g, "")
        Texto { text: pg.quando(modelData.timestamp); color: Tema.texto3; font.pixelSize: Tema.tLegenda + 1 }
      }
    }
  }
  Texto { visible: pg.historico.length === 0; text: I18n.t("Nenhuma notificação recente."); color: Tema.texto3 }
}
