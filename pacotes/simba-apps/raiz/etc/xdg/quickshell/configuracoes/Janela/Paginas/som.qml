import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Services.Pipewire
import qs.Comum
import qs.Janela

Pagina {
  id: pg
  titulo: I18n.t("Som")
  subtitulo: I18n.t("Saídas, microfones e o volume de cada aplicativo (PipeWire).")

  readonly property var nos: Pipewire.nodes ? Pipewire.nodes.values : []
  readonly property var saidas: nos.filter(function(n) { return n.audio && n.isSink && !n.isStream })
  readonly property var entradas: nos.filter(function(n) { return n.audio && !n.isSink && !n.isStream && String(n.name).indexOf(".monitor") < 0 })
  // Playback streams only (media.class Stream/Output/Audio): recording streams
  // (e.g. a transcription app capturing the mic) are left alone.
  readonly property var apps: nos.filter(function(n) { return n.audio && n.isStream && n.properties && n.properties["media.class"] === "Stream/Output/Audio" })
  readonly property var saida: Pipewire.defaultAudioSink
  readonly property var entrada: Pipewire.defaultAudioSource

  PwObjectTracker { objects: pg.saidas.concat(pg.entradas).concat(pg.apps) }
  PwNodePeakMonitor { id: picoSaida; node: pg.saida; enabled: pg.saida !== null }
  PwNodePeakMonitor { id: picoEntrada; node: pg.entrada; enabled: pg.entrada !== null }

  function nomeNo(n) {
    if (!n) return "—"
    return n.nickname || n.description || n.name
  }
  function glifoNo(n) {
    var s = (String(n.description) + " " + String(n.name)).toLowerCase()
    if (s.indexOf("hdmi") >= 0 || s.indexOf("displayport") >= 0) return Icones.television
    if (s.indexOf("headphone") >= 0 || s.indexOf("headset") >= 0 || s.indexOf("fone") >= 0) return Icones.headphones
    if (s.indexOf("bluez") >= 0 || s.indexOf("bluetooth") >= 0) return Icones.headphonesBluetooth
    if (!n.isSink) return Icones.microphone
    return Icones.speaker
  }
  function definirPadrao(n, saida) {
    Sistema.rodar([saida ? "simba-audio-output-set-default" : "simba-audio-input-set-default", String(n.id), String(n.name)], function(o, code) {
      if (code !== 0) { if (saida) Pipewire.preferredDefaultAudioSink = n; else Pipewire.preferredDefaultAudioSource = n }
      Navegacao.confirmar((saida ? I18n.t("Saída: ") : I18n.t("Microfone: ")) + pg.nomeNo(n), saida ? Icones.speaker : Icones.microphone)
    })
  }

  component Medidor: Item {
    property real nivel: 0
    implicitHeight: 4
    Rectangle { anchors.fill: parent; radius: 2; color: Tema.superficieMax }
    Rectangle {
      height: parent.height; radius: 2
      width: parent.width * Math.min(1, parent.nivel)
      color: Tema.realce
      Behavior on width { NumberAnimation { duration: 80 } }
    }
  }

  component Dispositivo: Rectangle {
    id: d
    property var no: null
    property bool padrao: false
    property bool saida: true
    Layout.fillWidth: true
    Layout.preferredHeight: 52
    radius: Tema.raio
    color: padrao ? Tema.superficieAlta : (md.containsMouse ? Tema.hover : "transparent")
    border.width: padrao ? 1 : 0
    border.color: Tema.linhaForte
    RowLayout {
      anchors.fill: parent
      anchors.leftMargin: 12
      anchors.rightMargin: 12
      spacing: 12
      Rectangle {
        Layout.preferredWidth: 18; Layout.preferredHeight: 18
        radius: Tema.raio > 0 ? 9 : 2
        color: "transparent"
        border.width: 2
        border.color: d.padrao ? Tema.realce : Tema.texto3
        Rectangle { anchors.centerIn: parent; width: 8; height: 8; radius: Tema.raio > 0 ? 4 : 0; color: Tema.realce; visible: d.padrao }
      }
      Glifo { g: pg.glifoNo(d.no); tamanho: 18; color: d.padrao ? Tema.texto : Tema.texto2 }
      ColumnLayout {
        Layout.fillWidth: true
        spacing: 1
        Texto { text: pg.nomeNo(d.no); font.weight: d.padrao ? Font.DemiBold : Font.Normal; elide: Text.ElideRight; Layout.fillWidth: true }
        Texto { text: d.no ? d.no.name : ""; color: Tema.texto3; font.pixelSize: Tema.tLegenda; elide: Text.ElideMiddle; Layout.fillWidth: true }
      }
      Texto { visible: d.padrao; text: I18n.t("Em uso"); color: Tema.texto3; font.pixelSize: Tema.tLegenda + 1 }
    }
    MouseArea { id: md; anchors.fill: parent; hoverEnabled: true; enabled: !d.padrao; cursorShape: Qt.PointingHandCursor; onClicked: pg.definirPadrao(d.no, d.saida) }
  }

  // ── output ───────────────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Saída"); Layout.topMargin: 2 }
  Cartao {
    Linha {
      chave: "volume"; glifo: pg.saida && pg.saida.audio && pg.saida.audio.muted ? Icones.volumeOff : Icones.volumeHigh
      titulo: I18n.t("Volume")
      descricao: pg.nomeNo(pg.saida)
      Botao {
        compacto: true; tipo: "fantasma"
        glifo: pg.saida && pg.saida.audio && pg.saida.audio.muted ? Icones.volumeOff : Icones.volumeHigh
        onClicado: if (pg.saida && pg.saida.audio) pg.saida.audio.muted = !pg.saida.audio.muted
      }
      Deslizante {
        width: 260
        de: 0; ate: 100; passo: 1
        valor: pg.saida && pg.saida.audio ? Math.round(pg.saida.audio.volume * 100) : 0
        habilitado: pg.saida !== null
        sufixo: "%"
        onMovido: function(x) { if (pg.saida && pg.saida.audio) pg.saida.audio.volume = x / 100 }
      }
    }
    Item {
      Layout.fillWidth: true
      Layout.preferredHeight: 18
      Medidor { x: 64; width: parent.width - 80; anchors.verticalCenter: parent.verticalCenter; nivel: picoSaida.peak }
    }
    Linha {
      chave: "saida"; glifo: Icones.speaker
      titulo: I18n.t("Dispositivo de saída")
      descricao: pg.saidas.length + (pg.saidas.length === 1 ? I18n.t(" disponível") : I18n.t(" disponíveis"))
      expandido: true
      extra: Repeater {
        model: pg.saidas
        delegate: Dispositivo { required property var modelData; no: modelData; saida: true; padrao: pg.saida !== null && modelData.id === pg.saida.id }
      }
    }
  }

  // ── input ────────────────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Entrada") }
  Cartao {
    Linha {
      chave: "volumeMic"; glifo: pg.entrada && pg.entrada.audio && pg.entrada.audio.muted ? Icones.microphoneOff : Icones.microphone
      titulo: I18n.t("Volume do microfone")
      descricao: pg.nomeNo(pg.entrada)
      Botao {
        compacto: true; tipo: "fantasma"
        glifo: pg.entrada && pg.entrada.audio && pg.entrada.audio.muted ? Icones.microphoneOff : Icones.microphone
        onClicado: Sistema.rodar(["simba-audio-input-mute"])
      }
      Deslizante {
        width: 260
        de: 0; ate: 100; passo: 1
        valor: pg.entrada && pg.entrada.audio ? Math.round(pg.entrada.audio.volume * 100) : 0
        habilitado: pg.entrada !== null
        sufixo: "%"
        onMovido: function(x) { if (pg.entrada && pg.entrada.audio) pg.entrada.audio.volume = x / 100 }
      }
    }
    Item {
      Layout.fillWidth: true
      Layout.preferredHeight: 18
      RowLayout {
        x: 64; width: parent.width - 80; anchors.verticalCenter: parent.verticalCenter
        Texto { text: I18n.t("Fale para testar"); color: Tema.texto3; font.pixelSize: Tema.tLegenda }
        Medidor { Layout.fillWidth: true; nivel: picoEntrada.peak }
      }
    }
    Linha {
      chave: "entradaDisp"; glifo: Icones.microphoneSettings
      titulo: I18n.t("Microfone")
      descricao: pg.entradas.length + (pg.entradas.length === 1 ? I18n.t(" disponível") : I18n.t(" disponíveis"))
      expandido: true
      extra: Repeater {
        model: pg.entradas
        delegate: Dispositivo { required property var modelData; no: modelData; saida: false; padrao: pg.entrada !== null && modelData.id === pg.entrada.id }
      }
    }
  }

  // ── apps ─────────────────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Volume por aplicativo"); detalhe: pg.apps.length ? "" : I18n.t("Nenhum aplicativo tocando som agora.") }
  Ancora { chave: "appsVolume" }
  Cartao {
    visible: pg.apps.length > 0
    Repeater {
      model: pg.apps
      delegate: Linha {
        required property var modelData
        glifo: Icones.application
        titulo: modelData.properties && modelData.properties["application.name"] ? modelData.properties["application.name"] : pg.nomeNo(modelData)
        descricao: modelData.properties && modelData.properties["media.name"] ? modelData.properties["media.name"] : ""
        Botao { compacto: true; tipo: "fantasma"; glifo: modelData.audio && modelData.audio.muted ? Icones.volumeOff : Icones.volumeHigh; onClicado: if (modelData.audio) modelData.audio.muted = !modelData.audio.muted }
        Deslizante {
          width: 220; de: 0; ate: 100; passo: 1; sufixo: "%"
          valor: modelData.audio ? Math.round(modelData.audio.volume * 100) : 0
          onMovido: function(x) { if (modelData.audio) modelData.audio.volume = x / 100 }
        }
      }
    }
  }

  Secao { titulo: I18n.t("Problemas") }
  Cartao {
    Linha {
      chave: "reiniciarAudio"; glifo: Icones.restart
      titulo: I18n.t("Reiniciar o áudio")
      descricao: I18n.t("Quando o som some ou um fone não aparece")
      Botao { texto: I18n.t("Reiniciar"); onClicado: Sistema.rodar(["simba-restart-audio"], function() { Navegacao.confirmar(I18n.t("Áudio reiniciado"), Icones.restart) }) }
    }
  }
}
