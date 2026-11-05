import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Services.UPower
import qs.Comum
import qs.Janela

Pagina {
  id: pg
  titulo: I18n.t("Energia e bateria")
  subtitulo: I18n.t("Modo de energia na tomada e na bateria, estado da bateria e as ações de energia.")

  property var prefs: ({ ac: "", battery: "" })
  property bool suspenderOculto: false
  property bool hibernar: false
  property string confirmando: ""

  readonly property var bat: {
    var ds = UPower.devices ? UPower.devices.values : []
    for (var i = 0; i < ds.length; i++) if (ds[i].isLaptopBattery) return ds[i]
    return null
  }

  function carregar() {
    Sistema.sh("d=${XDG_STATE_HOME:-$HOME/.local/state}/simba/powerprofiles; cat $d/ac 2>/dev/null || echo; echo @@; cat $d/battery 2>/dev/null || echo; echo @@; simba-toggle-enabled suspend-off && echo sim; echo @@; simba-hibernation-available && echo sim", function(o) {
      var p = o.split("@@").map(function(x) { return x.trim() })
      pg.prefs = { ac: p[0] || "performance", battery: p[1] || "balanced" }
      pg.suspenderOculto = p[2] === "sim"
      pg.hibernar = p[3] === "sim"
    })
  }
  Component.onCompleted: carregar()

  function definirPref(fonte, perfil) {
    Sistema.sh("d=${XDG_STATE_HOME:-$HOME/.local/state}/simba/powerprofiles; mkdir -p \"$d\"; echo " + perfil + " > \"$d/" + fonte + "\"; simba-powerprofiles-set autodetect", function() {
      pg.carregar()
      Navegacao.confirmar((fonte === "ac" ? I18n.t("Na tomada: ") : I18n.t("Na bateria: ")) + pg.nomePerfil(perfil), Icones.lightningBolt)
    })
  }
  function nomePerfil(p) { return p === "performance" ? I18n.t("Desempenho") : p === "power-saver" ? I18n.t("Economia") : I18n.t("Equilibrado") }
  readonly property var opcoesPerfil: (PowerProfiles.hasPerformanceProfile
    ? [{ valor: "power-saver", rotulo: I18n.t("Economia"), glifo: Icones.leaf }, { valor: "balanced", rotulo: I18n.t("Equilibrado"), glifo: Icones.speedometerMedium }, { valor: "performance", rotulo: I18n.t("Desempenho"), glifo: Icones.lightningBolt }]
    : [{ valor: "power-saver", rotulo: I18n.t("Economia"), glifo: Icones.leaf }, { valor: "balanced", rotulo: I18n.t("Equilibrado"), glifo: Icones.speedometerMedium }])

  function tempo(s) {
    if (!s || s <= 0) return ""
    var h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60)
    return h > 0 ? h + " h " + (m < 10 ? "0" : "") + m + " min" : m + " min"
  }

  // ── battery hero ─────────────────────────────────────────────────────────
  Rectangle {
    visible: pg.bat !== null
    Layout.fillWidth: true
    Layout.preferredHeight: 150
    radius: Tema.raioGrande
    color: Tema.superficie
    border.width: 1
    border.color: Tema.linha
    Ancora { chave: "bateria"; anchors.top: parent.top; width: parent.width }
    RowLayout {
      anchors.fill: parent
      anchors.margins: 22
      spacing: 26
      // big battery
      Item {
        Layout.preferredWidth: 150
        Layout.preferredHeight: 70
        Rectangle {
          id: corpo
          width: 140; height: 70
          radius: Tema.raio + 4
          color: "transparent"
          border.width: 3
          border.color: Tema.texto2
          Rectangle {
            x: 6; y: 6
            height: parent.height - 12
            width: Math.max(4, (parent.width - 12) * (pg.bat ? pg.bat.percentage : 0))
            radius: Math.max(0, Tema.raio)
            color: pg.bat && pg.bat.percentage < 0.15 ? Tema.perigo : Tema.realce
            Behavior on width { NumberAnimation { duration: 900; easing.type: Easing.OutCubic } }
            // charging shimmer
            Rectangle {
              visible: !UPower.onBattery
              width: 18; height: parent.height
              color: Tema.alfa(Tema.janela, 0.25)
              NumberAnimation on x { from: -18; to: corpo.width; duration: 1600; loops: Animation.Infinite; running: !UPower.onBattery && Tema.animacoes }
            }
          }
          Glifo { anchors.centerIn: parent; visible: !UPower.onBattery; g: Icones.lightningBolt; tamanho: 26; color: Tema.janela }
        }
        Rectangle { x: 142; y: 24; width: 7; height: 22; radius: 2; color: Tema.texto2 }
      }
      ColumnLayout {
        Layout.fillWidth: true
        spacing: 2
        Texto { text: pg.bat ? Math.round(pg.bat.percentage * 100) + "%" : ""; font.pixelSize: Tema.tDisplay + 6; font.weight: Font.Bold; font.letterSpacing: -1 }
        Texto {
          text: !pg.bat ? "" : UPower.onBattery
            ? I18n.t("Usando a bateria") + (pg.tempo(pg.bat.timeToEmpty) ? I18n.t(" · resta ") + pg.tempo(pg.bat.timeToEmpty) : "")
            : (pg.bat.state === UPowerDeviceState.FullyCharged ? I18n.t("Carregada · na tomada") : I18n.t("Carregando") + (pg.tempo(pg.bat.timeToFull) ? I18n.t(" · cheia em ") + pg.tempo(pg.bat.timeToFull) : ""))
          color: Tema.texto2
        }
        Texto {
          text: pg.bat && Math.abs(pg.bat.changeRate) > 0.05 ? I18n.t("Consumo agora: ") + Math.abs(pg.bat.changeRate).toFixed(1).replace(".", I18n.decimal) + " W" : ""
          color: Tema.texto3
          font.pixelSize: Tema.tLegenda + 1
        }
      }
    }
  }
  Aviso { visible: pg.bat === null; texto: I18n.t("Este computador não tem bateria.") }

  // ── profiles ─────────────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Modo de energia"); detalhe: I18n.t("Agora: ") + pg.nomePerfil(PowerProfiles.profile === PowerProfile.Performance ? "performance" : PowerProfiles.profile === PowerProfile.PowerSaver ? "power-saver" : "balanced") + I18n.t(". O Simba OS troca sozinho ao ligar ou tirar da tomada.") }
  Cartao {
    Linha {
      chave: "perfil"; glifo: Icones.powerPlug
      titulo: I18n.t("Na tomada")
      descricao: UPower.onBattery ? "" : I18n.t("Em uso agora")
      Segmentado { opcoes: pg.opcoesPerfil; atual: pg.prefs.ac; onEscolhido: function(x) { pg.definirPref("ac", x) } }
    }
    Linha {
      glifo: Icones.battery
      visible: pg.bat !== null
      titulo: I18n.t("Na bateria")
      descricao: UPower.onBattery ? I18n.t("Em uso agora") : ""
      Segmentado { opcoes: pg.opcoesPerfil; atual: pg.prefs.battery; onEscolhido: function(x) { pg.definirPref("battery", x) } }
    }
  }

  Secao { titulo: I18n.t("Bateria"); visible: pg.bat !== null }
  Cartao {
    visible: pg.bat !== null
    Linha {
      chave: "saudeBateria"; glifo: Icones.batteryHeart
      titulo: I18n.t("Saúde da bateria")
      descricao: pg.bat && pg.bat.energyCapacity > 0 ? I18n.t("Carga máxima de hoje comparada à de fábrica · ") + (pg.bat.model || "bateria") : ""
      Texto {
        text: pg.bat && pg.bat.healthSupported ? Math.round(pg.bat.healthPercentage) + "%" : "—"
        font.pixelSize: Tema.tTitulo + 2
        font.weight: Font.Bold
      }
    }
    Linha {
      glifo: Icones.lightningBolt
      titulo: I18n.t("Energia armazenada")
      Texto { text: pg.bat ? pg.bat.energy.toFixed(1).replace(".", I18n.decimal) + " de " + pg.bat.energyCapacity.toFixed(1).replace(".", I18n.decimal) + I18n.t(" Wh") : ""; color: Tema.texto2 }
    }
  }

  // ── actions ──────────────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Ações") }
  Ancora { chave: "acoesEnergia" }
  GridLayout {
    Layout.fillWidth: true
    columns: width > 700 ? 5 : 3
    columnSpacing: 10
    rowSpacing: 10
    Repeater {
      model: [
        { id: "suspender", rotulo: I18n.t("Suspender"), glifo: Icones.sleep, cmd: "systemctl suspend" },
        { id: "hibernar", rotulo: I18n.t("Hibernar"), glifo: Icones.harddisk, cmd: "systemctl hibernate" },
        { id: "sair", rotulo: I18n.t("Sair da sessão"), glifo: Icones.logout, cmd: "simba-system-logout" },
        { id: "reiniciar", rotulo: I18n.t("Reiniciar"), glifo: Icones.restart, cmd: "simba-system-reboot" },
        { id: "desligar", rotulo: I18n.t("Desligar"), glifo: Icones.power, cmd: "simba-system-shutdown" }
      ]
      delegate: Rectangle {
        id: ac
        required property var modelData
        readonly property bool pedindo: pg.confirmando === modelData.id
        visible: modelData.id !== "hibernar" || pg.hibernar
        Layout.fillWidth: true
        Layout.preferredHeight: 92
        radius: Tema.raioGrande
        color: pedindo ? Tema.alfa(Tema.perigo, 0.16) : (ma.containsMouse ? Tema.superficieAlta : Tema.superficie)
        border.width: 1
        border.color: pedindo ? Tema.alfa(Tema.perigo, 0.5) : Tema.linha
        Behavior on color { ColorAnimation { duration: Tema.rapido } }
        ColumnLayout {
          anchors.centerIn: parent
          spacing: 6
          Glifo { Layout.alignment: Qt.AlignHCenter; g: ac.modelData.glifo; tamanho: 24; color: ac.pedindo ? Tema.perigo : Tema.texto }
          Texto { Layout.alignment: Qt.AlignHCenter; text: ac.pedindo ? I18n.t("Clique para confirmar") : ac.modelData.rotulo; font.pixelSize: ac.pedindo ? Tema.tLegenda + 1 : Tema.tCorpo; color: ac.pedindo ? Tema.perigo : Tema.texto }
        }
        MouseArea {
          id: ma
          anchors.fill: parent
          hoverEnabled: true
          cursorShape: Qt.PointingHandCursor
          onClicked: {
            if (ac.pedindo) { pg.confirmando = ""; Sistema.soltoSh("sleep 0.3; " + ac.modelData.cmd) }
            else { pg.confirmando = ac.modelData.id; desfazer.restart() }
          }
        }
      }
    }
  }
  Timer { id: desfazer; interval: 3500; onTriggered: pg.confirmando = "" }

  Cartao {
    Layout.topMargin: 10
    Linha {
      chave: "suspenderMenu"; glifo: Icones.sleep
      titulo: I18n.t("Mostrar “Suspender” no menu do sistema")
      Interruptor { ligado: !pg.suspenderOculto; onAlternado: function() { Sistema.rodar(["simba-toggle-suspend"], function() { pg.carregar() }) } }
    }
  }
}
