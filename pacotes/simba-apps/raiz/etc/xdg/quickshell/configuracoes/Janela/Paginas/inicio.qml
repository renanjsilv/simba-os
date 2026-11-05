import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Services.Pipewire
import Quickshell.Services.UPower
import Quickshell.Networking
import Quickshell.Bluetooth
import qs.Comum
import qs.Janela

Pagina {
  id: pg
  readonly property int hora: new Date().getHours()
  readonly property string saudacao: hora < 5 ? I18n.t("Boa madrugada") : hora < 12 ? I18n.t("Bom dia") : hora < 18 ? I18n.t("Boa tarde") : I18n.t("Boa noite")
  titulo: saudacao + "."
  subtitulo: I18n.t("Tudo do seu Simba OS num só lugar. Dica: Ctrl+F procura qualquer ajuste.")

  property bool luz: false
  property bool dnd: false
  property bool acordado: false
  property var tela: null
  property string ssid: ""

  PwObjectTracker { objects: [Pipewire.defaultAudioSink, Pipewire.defaultAudioSource] }
  readonly property var saida: Pipewire.defaultAudioSink
  readonly property var bat: UPower.displayDevice
  readonly property var bt: Bluetooth.defaultAdapter

  function atualizar() {
    Sistema.json(["simba-shell", "nightlight", "status"], function(v) { if (v) pg.luz = !!v.enabled })
    Sistema.sh("simba-shell notifications isDnd", function(o) { pg.dnd = o.trim() === "on" })
    Sistema.json(["simba-toggle-idle", "status"], function(v) { if (v) pg.acordado = !!v.enabled })
    Sistema.json([Sistema.tela, "estado"], function(v) { if (v) pg.tela = v })
    Sistema.sh("nmcli -t -f NAME,TYPE connection show --active 2>/dev/null | grep -E ':802-11-wireless$' | head -1 | sed 's/:802-11-wireless$//'", function(o) { pg.ssid = o.trim() })
  }
  Component.onCompleted: atualizar()
  Timer { interval: 4000; running: true; repeat: true; onTriggered: pg.atualizar() }

  readonly property var nomesModo: ({ notebook: I18n.t("Somente tela do notebook"), duplicar: I18n.t("Duplicada"), estender: I18n.t("Estendida"), segunda: I18n.t("Somente segunda tela"), unico: I18n.t("Uma tela") })
  readonly property string perfil: PowerProfiles.profile === PowerProfile.Performance ? I18n.t("Desempenho") : PowerProfiles.profile === PowerProfile.PowerSaver ? I18n.t("Economia") : I18n.t("Equilibrado")

  // ── quick settings ───────────────────────────────────────────────────────
  component Bloco: Rectangle {
    id: b
    property string glifo: ""
    property string rotulo: ""
    property string detalhe: ""
    property bool ativo: false
    signal clicado()
    Layout.fillWidth: true
    Layout.preferredHeight: 74
    radius: Tema.raioGrande
    color: ativo ? Tema.realce : (mb.containsMouse ? Tema.superficieAlta : Tema.superficie)
    border.width: ativo ? 0 : 1
    border.color: Tema.linha
    scale: mb.pressed ? 0.96 : 1
    Behavior on color { ColorAnimation { duration: Tema.medio } }
    Behavior on scale { NumberAnimation { duration: Tema.rapido } }
    RowLayout {
      anchors.fill: parent
      anchors.leftMargin: 14
      anchors.rightMargin: 12
      spacing: 12
      Rectangle {
        Layout.preferredWidth: 36; Layout.preferredHeight: 36
        radius: Tema.raio > 0 ? 18 : 0
        color: b.ativo ? Tema.alfa(Tema.sobreRealce, 0.12) : Tema.superficieAlta
        Glifo { anchors.centerIn: parent; g: b.glifo; tamanho: 18; color: b.ativo ? Tema.sobreRealce : Tema.texto }
      }
      ColumnLayout {
        Layout.fillWidth: true
        spacing: 1
        Texto { text: b.rotulo; font.weight: Font.DemiBold; color: b.ativo ? Tema.sobreRealce : Tema.texto; Layout.fillWidth: true; elide: Text.ElideRight }
        Texto { text: b.detalhe; font.pixelSize: Tema.tLegenda + 1; color: b.ativo ? Tema.alfa(Tema.sobreRealce, 0.75) : Tema.texto3; Layout.fillWidth: true; elide: Text.ElideRight }
      }
    }
    MouseArea { id: mb; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: b.clicado() }
  }

  Secao { titulo: I18n.t("Ajustes rápidos"); Layout.topMargin: 2 }
  GridLayout {
    Layout.fillWidth: true
    columns: width > 900 ? 4 : 3
    columnSpacing: 10
    rowSpacing: 10
    Bloco {
      glifo: Icones.weatherNight; rotulo: I18n.t("Luz noturna"); ativo: pg.luz
      detalhe: pg.luz ? I18n.t("Ligada") : I18n.t("Desligada")
      onClicado: { pg.luz = !pg.luz; Sistema.rodar(["simba-shell", "nightlight", "toggle"], function() { pg.atualizar() }) }
    }
    Bloco {
      glifo: pg.dnd ? Icones.bellOff : Icones.bell; rotulo: I18n.t("Não perturbe"); ativo: pg.dnd
      detalhe: pg.dnd ? I18n.t("Notificações silenciadas") : I18n.t("Notificações ativas")
      onClicado: { pg.dnd = !pg.dnd; Sistema.rodar(["simba-toggle-notification-silencing"], function() { pg.atualizar() }) }
    }
    Bloco {
      glifo: Icones.coffee; rotulo: I18n.t("Manter acordado"); ativo: pg.acordado
      detalhe: pg.acordado ? I18n.t("Sem bloqueio automático") : I18n.t("Inatividade normal")
      onClicado: { pg.acordado = !pg.acordado; Sistema.rodar(["simba-toggle-idle"], function() { pg.atualizar() }) }
    }
    Bloco {
      glifo: PowerProfiles.profile === PowerProfile.PowerSaver ? Icones.leaf : PowerProfiles.profile === PowerProfile.Performance ? Icones.lightningBolt : Icones.speedometerMedium
      rotulo: I18n.t("Modo de energia"); detalhe: pg.perfil
      ativo: PowerProfiles.profile === PowerProfile.Performance
      onClicado: {
        var ordem = PowerProfiles.hasPerformanceProfile ? [PowerProfile.PowerSaver, PowerProfile.Balanced, PowerProfile.Performance] : [PowerProfile.PowerSaver, PowerProfile.Balanced]
        var i = ordem.indexOf(PowerProfiles.profile)
        PowerProfiles.profile = ordem[(i + 1) % ordem.length]
      }
    }
    Bloco {
      glifo: Networking.wifiEnabled ? Icones.wifi : Icones.wifiOff; rotulo: I18n.t("Wi-Fi"); ativo: Networking.wifiEnabled
      detalhe: Networking.wifiEnabled ? (pg.ssid || I18n.t("Ligado")) : I18n.t("Desligado")
      onClicado: Networking.wifiEnabled = !Networking.wifiEnabled
    }
    Bloco {
      glifo: pg.bt && pg.bt.enabled ? Icones.bluetooth : Icones.bluetoothOff; rotulo: I18n.t("Bluetooth")
      ativo: !!(pg.bt && pg.bt.enabled)
      detalhe: !pg.bt ? I18n.t("Sem adaptador") : (pg.bt.enabled ? I18n.t("Ligado") : I18n.t("Desligado"))
      onClicado: if (pg.bt) pg.bt.enabled = !pg.bt.enabled
    }
    Bloco {
      glifo: Icones.viewGridOutline; rotulo: I18n.t("Ícones na área de trabalho")
      ativo: Preferencias.obter("area.mostrarIcones", true)
      detalhe: ativo ? I18n.t("Visíveis") : I18n.t("Ocultos")
      onClicado: Preferencias.definir("area.mostrarIcones", !ativo)
    }
    Bloco {
      glifo: Icones.dockTop; rotulo: I18n.t("Barra")
      property bool oculta: false
      ativo: !oculta
      detalhe: oculta ? I18n.t("Oculta") : I18n.t("Visível")
      Component.onCompleted: Sistema.sh("simba-toggle-enabled bar-off && echo sim", function(o) { oculta = o.trim() === "sim" })
      onClicado: { oculta = !oculta; Sistema.rodar(["simba-toggle-bar", oculta ? "on" : "off"]) }
    }
    Bloco {
      glifo: Icones.monitorMultiple; rotulo: I18n.t("Projetar")
      ativo: false
      detalhe: pg.tela ? pg.nomesModo[pg.tela.modo] || "" : "…"
      onClicado: Navegacao.ir("tela", "modoProjecao")
    }
  }

  // ── at a glance ──────────────────────────────────────────────────────────
  component Resumo: Rectangle {
    id: r
    property string glifo: ""
    property string rotulo: ""
    property string valor: ""
    property string detalhe: ""
    property string pagina: ""
    property real progresso: -1
    Layout.fillWidth: true
    Layout.preferredHeight: 118
    radius: Tema.raioGrande
    color: mr.containsMouse ? Tema.superficieAlta : Tema.superficie
    border.width: 1
    border.color: mr.containsMouse ? Tema.linhaForte : Tema.linha
    Behavior on color { ColorAnimation { duration: Tema.rapido } }
    ColumnLayout {
      anchors.fill: parent
      anchors.margins: 16
      spacing: 4
      RowLayout {
        spacing: 8
        Glifo { g: r.glifo; tamanho: 15; color: Tema.texto2 }
        Texto { text: r.rotulo; color: Tema.texto2; font.pixelSize: Tema.tLegenda + 1; Layout.fillWidth: true }
        Glifo { g: Icones.arrowRight; tamanho: 14; color: Tema.texto3; opacity: mr.containsMouse ? 1 : 0; Behavior on opacity { NumberAnimation { duration: Tema.rapido } } }
      }
      Item { Layout.fillHeight: true }
      Texto { text: r.valor; font.pixelSize: 22; font.weight: Font.Bold; Layout.fillWidth: true; elide: Text.ElideRight }
      Texto { text: r.detalhe; color: Tema.texto3; font.pixelSize: Tema.tLegenda + 1; Layout.fillWidth: true; elide: Text.ElideRight }
      Rectangle {
        visible: r.progresso >= 0
        Layout.fillWidth: true
        Layout.preferredHeight: 3
        radius: 1.5
        color: Tema.superficieMax
        Rectangle { width: parent.width * Math.max(0, Math.min(1, r.progresso)); height: parent.height; radius: 1.5; color: Tema.realce; Behavior on width { NumberAnimation { duration: Tema.lento } } }
      }
    }
    MouseArea { id: mr; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: Navegacao.ir(r.pagina) }
  }

  Secao { titulo: I18n.t("Visão geral") }
  GridLayout {
    Layout.fillWidth: true
    columns: width > 760 ? 3 : 2
    columnSpacing: 10
    rowSpacing: 10
    Resumo {
      glifo: Icones.monitor; rotulo: I18n.t("Tela"); pagina: "tela"
      valor: pg.tela ? (pg.tela.monitores.filter(function(m) { return !m.disabled }).length + (pg.tela.monitores.filter(function(m) { return !m.disabled }).length === 1 ? I18n.t(" tela ativa") : I18n.t(" telas ativas"))) : "…"
      detalhe: pg.tela ? pg.nomesModo[pg.tela.modo] + I18n.t(" · Super+P para mudar") : ""
    }
    Resumo {
      glifo: Icones.volumeHigh; rotulo: I18n.t("Som"); pagina: "som"
      valor: pg.saida && pg.saida.audio ? (pg.saida.audio.muted ? I18n.t("Mudo") : Math.round(pg.saida.audio.volume * 100) + "%") : "—"
      detalhe: pg.saida ? (pg.saida.nickname || pg.saida.description || "") : I18n.t("Sem saída de áudio")
      progresso: pg.saida && pg.saida.audio && !pg.saida.audio.muted ? pg.saida.audio.volume : 0
    }
    Resumo {
      glifo: Icones.batteryHeart; rotulo: I18n.t("Bateria"); pagina: "energia"
      valor: pg.bat && pg.bat.isPresent ? Math.round(pg.bat.percentage * 100) + "%" : I18n.t("Na tomada")
      detalhe: pg.bat && pg.bat.isPresent ? (UPower.onBattery ? I18n.t("Usando a bateria · ") + pg.perfil : I18n.t("Carregando · ") + pg.perfil) : pg.perfil
      progresso: pg.bat && pg.bat.isPresent ? pg.bat.percentage : -1
    }
    Resumo {
      glifo: Icones.palette; rotulo: I18n.t("Tema"); pagina: "personalizacao"
      valor: Tema.nome.split("-").map(function(w) { return w.charAt(0).toUpperCase() + w.slice(1) }).join(" ")
      detalhe: (Tema.escuro ? I18n.t("Escuro") : I18n.t("Claro")) + " · " + Tema.fonte
    }
    Resumo {
      glifo: Networking.wifiEnabled ? Icones.wifi : Icones.wifiOff; rotulo: I18n.t("Rede"); pagina: "rede"
      valor: pg.ssid || (Networking.wifiEnabled ? I18n.t("Sem Wi-Fi") : I18n.t("Wi-Fi desligado"))
      detalhe: pg.ssid ? I18n.t("Conectado") : I18n.t("Toque para ver as redes")
    }
    Resumo {
      glifo: Icones.keyboard; rotulo: I18n.t("Atalhos"); pagina: "atalhos"
      valor: "Super + P"
      detalhe: I18n.t("Projetar: notebook, duplicar, estender…")
    }
  }

  Secao { titulo: I18n.t("Na área de trabalho") }
  Cartao {
    Linha {
      glifo: Icones.cursorDefault
      titulo: I18n.t("Clique com o botão direito na área de trabalho")
      descricao: I18n.t("Atualizar, novo arquivo ou pasta, colar, trocar papel de parede, abrir o terminal e estas configurações.")
      navegavel: true
      onClicado: Navegacao.ir("area")
    }
    Linha {
      glifo: Icones.monitorMultiple
      titulo: I18n.t("Super + P troca o modo de projeção")
      descricao: I18n.t("Somente o notebook, duplicar, estender ou somente a segunda tela — com 15 s para desfazer.")
      navegavel: true
      onClicado: Navegacao.ir("tela", "modoProjecao")
    }
  }
}
