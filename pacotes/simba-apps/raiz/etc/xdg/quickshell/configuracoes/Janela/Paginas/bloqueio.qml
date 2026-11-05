import QtQuick
import QtQuick.Layouts
import qs.Comum
import qs.Janela

Pagina {
  id: pg
  titulo: I18n.t("Bloqueio e inatividade")
  subtitulo: I18n.t("Quando a proteção de tela entra e quando o computador pede a senha. Os tempos contam a partir do momento em que você para de usar o computador.")

  property int protecao: -1
  property int bloqueio: -1
  property bool acordado: false
  property bool protecaoDesligada: false

  function carregar() {
    Sistema.json([Sistema.ajudante, "shell"], function(v) {
      if (!v) return
      var i = v.idle || {}
      pg.protecao = i.screensaver !== undefined ? Number(i.screensaver) : 150
      pg.bloqueio = i.lock !== undefined ? Number(i.lock) : 300
    })
    Sistema.json(["simba-toggle-idle", "status"], function(v) { if (v) pg.acordado = !!v.enabled })
    Sistema.sh("simba-toggle-enabled screensaver-off && echo sim", function(o) { pg.protecaoDesligada = o.trim() === "sim" })
  }
  Component.onCompleted: carregar()

  readonly property var tempos: [
    { valor: 0, rotulo: I18n.t("Nunca") }, { valor: 60, rotulo: I18n.t("1 minuto") }, { valor: 120, rotulo: I18n.t("2 minutos") },
    { valor: 180, rotulo: I18n.t("3 minutos") }, { valor: 300, rotulo: I18n.t("5 minutos") }, { valor: 600, rotulo: I18n.t("10 minutos") },
    { valor: 900, rotulo: I18n.t("15 minutos") }, { valor: 1200, rotulo: I18n.t("20 minutos") }, { valor: 1800, rotulo: I18n.t("30 minutos") },
    { valor: 2700, rotulo: I18n.t("45 minutos") }, { valor: 3600, rotulo: I18n.t("1 hora") }, { valor: 7200, rotulo: I18n.t("2 horas") }
  ]
  function opcoesCom(atual) {
    var o = tempos.slice()
    if (atual > 0 && !o.some(function(t) { return t.valor === atual })) {
      o.push({ valor: atual, rotulo: (atual % 60 === 0 ? atual / 60 + " min" : atual + " s") + " (personalizado)" })
      o.sort(function(a, b) { return a.valor - b.valor })
    }
    return o
  }
  function texto(s) {
    if (s <= 0) return "nunca"
    if (s < 60) return s + " s"
    if (s < 3600) return Math.round(s / 60) + " min"
    return (s / 3600).toFixed(s % 3600 ? 1 : 0).replace(".", I18n.decimal) + " h"
  }
  function salvar(p, b) {
    Sistema.rodar([Sistema.bin + "/inatividade", String(p), String(b)], function(o, code, err) {
      pg.carregar()
      if (code === 0) Navegacao.confirmar(I18n.t("Tempos de inatividade salvos"), Icones.timer)
      else Navegacao.confirmar(err.trim() || I18n.t("Falhou"), Icones.alert)
    })
  }

  // ── timeline: one track per event, length = time until it happens ───────
  Rectangle {
    id: linhaTempo
    Layout.fillWidth: true
    Layout.preferredHeight: col.implicitHeight + 36
    radius: Tema.raioGrande
    color: Tema.superficie
    border.width: 1
    border.color: Tema.linha
    readonly property real maximo: Math.max(600, pg.protecao, pg.bloqueio) * 1.1
    ColumnLayout {
      id: col
      x: 20; y: 18
      width: parent.width - 40
      spacing: 14
      RowLayout {
        Layout.fillWidth: true
        Texto { text: I18n.t("Depois que você para de usar o computador"); color: Tema.texto2; font.pixelSize: Tema.tLegenda + 1; Layout.fillWidth: true }
        Texto { visible: pg.acordado; text: I18n.t("Manter acordado ligado: nada disso acontece"); color: Tema.aviso; font.pixelSize: Tema.tLegenda + 1 }
      }
      Repeater {
        model: [
          { t: pg.protecao, rotulo: I18n.t("Proteção de tela"), glifo: Icones.monitorScreenshot },
          { t: pg.bloqueio, rotulo: I18n.t("Bloqueio com senha"), glifo: Icones.lock }
        ]
        delegate: RowLayout {
          required property var modelData
          readonly property bool nunca: modelData.t <= 0
          Layout.fillWidth: true
          spacing: 12
          Glifo { g: modelData.glifo; tamanho: 16; color: parent.nunca ? Tema.texto3 : Tema.texto }
          Texto { text: modelData.rotulo; Layout.preferredWidth: 150; color: parent.nunca ? Tema.texto3 : Tema.texto }
          Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 10
            Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 4; radius: 2; color: Tema.superficieMax }
            Rectangle {
              visible: !parent.parent.nunca
              anchors.verticalCenter: parent.verticalCenter
              width: Math.max(10, parent.width * Math.min(1, modelData.t / linhaTempo.maximo))
              height: 4; radius: 2
              color: Tema.realce
              Behavior on width { NumberAnimation { duration: Tema.lento; easing.type: Easing.OutCubic } }
              Rectangle { anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter; width: 10; height: 10; radius: Tema.raio > 0 ? 5 : 1; color: Tema.realce }
            }
          }
          Texto { text: parent.nunca ? "nunca" : pg.texto(modelData.t); color: Tema.texto2; Layout.preferredWidth: 64; horizontalAlignment: Text.AlignRight }
        }
      }
    }
  }

  Secao { titulo: I18n.t("Tempos") }
  Cartao {
    Linha {
      chave: "protecao"; glifo: Icones.monitorScreenshot
      titulo: I18n.t("Proteção de tela após")
      descricao: pg.protecao === 0 ? I18n.t("Desativada") : I18n.t("A animação do Simba aparece depois de ") + pg.texto(pg.protecao) + " parado"
      Selecao {
        width: 200
        opcoes: pg.opcoesCom(pg.protecao)
        atual: pg.protecao
        onEscolhido: function(v) { pg.salvar(v, pg.bloqueio) }
      }
    }
    Linha {
      chave: "bloquearApos"; glifo: Icones.lockClock
      titulo: I18n.t("Bloquear após")
      descricao: pg.bloqueio === 0 ? I18n.t("Nunca bloqueia sozinho") : I18n.t("Pede a senha depois de ") + pg.texto(pg.bloqueio) + " parado"
      Selecao {
        width: 200
        opcoes: pg.opcoesCom(pg.bloqueio)
        atual: pg.bloqueio
        onEscolhido: function(v) { pg.salvar(pg.protecao, v) }
      }
    }
    Linha {
      chave: "manterAcordado"; glifo: Icones.coffee
      titulo: I18n.t("Manter acordado")
      descricao: I18n.t("Ignora os tempos acima até você desligar (ex.: apresentação, download longo)")
      Interruptor { ligado: pg.acordado; onAlternado: function(on) { Sistema.rodar(["simba-toggle-idle", on ? "stay-awake" : "allow-idle"], function() { pg.carregar() }) } }
    }
  }

  Secao { titulo: I18n.t("Proteção de tela") }
  Cartao {
    Linha {
      chave: "protecaoAtiva"; glifo: Icones.monitorScreenshot
      titulo: I18n.t("Permitir a proteção de tela")
      descricao: I18n.t("Desligada, a tela só bloqueia (sem a animação)")
      Interruptor { ligado: !pg.protecaoDesligada; onAlternado: function() { Sistema.rodar(["simba-toggle-screensaver"], function() { pg.carregar() }) } }
    }
    Linha {
      chave: "protecaoAgora"; glifo: Icones.play
      titulo: I18n.t("Ver a proteção de tela agora")
      descricao: I18n.t("Mexa o mouse ou aperte uma tecla para sair")
      Botao { texto: I18n.t("Iniciar"); onClicado: Sistema.soltoSh("sleep 0.4; simba-launch-screensaver force") }
    }
    Linha {
      chave: "protecaoTexto"; glifo: Icones.formatText
      titulo: I18n.t("Texto da proteção de tela")
      descricao: I18n.t("O letreiro em arte ASCII")
      Botao { texto: I18n.t("Editar"); onClicado: Sistema.solto(["simba-branding-screensaver", "text"]) }
      Botao { texto: I18n.t("Imagem…"); onClicado: Sistema.solto(["simba-branding-screensaver", "image"]) }
      Botao { tipo: "fantasma"; glifo: Icones.backupRestore; onClicado: Sistema.solto(["simba-branding-screensaver", "reset"]) }
    }
  }

  Secao { titulo: I18n.t("Tela de bloqueio") }
  Cartao {
    Linha {
      chave: "bloquearAgora"; glifo: Icones.lock
      titulo: I18n.t("Bloquear agora")
      descricao: I18n.t("Também com Super+Ctrl+L ou pelo menu do sistema")
      Botao { texto: I18n.t("Bloquear"); tipo: "primario"; glifo: Icones.lock; onClicado: Sistema.soltoSh("sleep 0.3; simba-system-lock") }
    }
    Linha {
      chave: "previaBloqueio"; glifo: Icones.eyeOutline
      titulo: I18n.t("Ver como fica a tela de bloqueio")
      descricao: I18n.t("Usa o papel de parede desfocado e as cores do tema. Clique para fechar a prévia.")
      Botao { texto: I18n.t("Visualizar"); onClicado: Sistema.soltoSh("simba-shell lock preview >/dev/null; sleep 8; simba-shell lock hidePreview >/dev/null") }
    }
  }
}
