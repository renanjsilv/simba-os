import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Bluetooth
import qs.Comum
import qs.Janela

Pagina {
  id: pg
  titulo: I18n.t("Bluetooth")
  subtitulo: I18n.t("Fones, caixas, mouses e teclados sem fio.")

  readonly property var ad: Bluetooth.defaultAdapter
  readonly property var dispositivos: {
    if (!ad || !ad.devices) return []
    var v = ad.devices.values.slice()
    v.sort(function(a, b) { return (b.connected - a.connected) || (b.paired - a.paired) || String(a.name).localeCompare(String(b.name)) })
    return v
  }
  readonly property var pareados: dispositivos.filter(function(d) { return d.paired })
  readonly property var novos: dispositivos.filter(function(d) { return !d.paired && d.name && d.name !== d.address })
  Binding { target: pg.ad; property: "discovering"; value: true; when: pg.ad !== null && pg.ad.enabled }

  function glifo(d) {
    var i = String(d.icon || "")
    if (i.indexOf("headset") >= 0 || i.indexOf("headphone") >= 0 || i.indexOf("audio") >= 0) return Icones.headphonesBluetooth
    if (i.indexOf("mouse") >= 0) return Icones.mouse
    if (i.indexOf("keyboard") >= 0) return Icones.keyboard
    if (i.indexOf("phone") >= 0) return Icones.cellphone
    if (i.indexOf("speaker") >= 0) return Icones.speakerWireless
    if (i.indexOf("gaming") >= 0 || i.indexOf("joystick") >= 0) return Icones.gamepadVariant
    return Icones.bluetooth
  }

  Cartao {
    Linha {
      chave: "btAtivo"; glifo: pg.ad && pg.ad.enabled ? Icones.bluetooth : Icones.bluetoothOff
      titulo: I18n.t("Bluetooth")
      descricao: !pg.ad ? I18n.t("Nenhum adaptador encontrado") : (pg.ad.enabled ? I18n.t("Ligado · visível como “") + pg.ad.name + "”" : I18n.t("Desligado"))
      Interruptor { ligado: !!(pg.ad && pg.ad.enabled); habilitado: pg.ad !== null; onAlternado: function(x) { pg.ad.enabled = x } }
    }
  }

  component Disp: Item {
    id: it
    property var d: null
    property bool primeiro: false
    Layout.fillWidth: true
    implicitHeight: 58
    Rectangle { visible: !it.primeiro; anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 16; anchors.rightMargin: 16; height: 1; color: Tema.linha }
    RowLayout {
      anchors.fill: parent
      anchors.leftMargin: 16
      anchors.rightMargin: 16
      spacing: 14
      Rectangle {
        Layout.preferredWidth: 34; Layout.preferredHeight: 34
        radius: Tema.raioPequeno + 1
        color: it.d && it.d.connected ? Tema.realce : Tema.superficieAlta
        Glifo { anchors.centerIn: parent; g: it.d ? pg.glifo(it.d) : ""; tamanho: 17; color: it.d && it.d.connected ? Tema.sobreRealce : Tema.texto }
      }
      ColumnLayout {
        Layout.fillWidth: true
        spacing: 1
        Texto { text: it.d ? (it.d.name || it.d.address) : ""; font.weight: it.d && it.d.connected ? Font.DemiBold : Font.Normal; elide: Text.ElideRight; Layout.fillWidth: true }
        Texto {
          text: !it.d ? "" : (it.d.pairing ? I18n.t("Pareando…") : it.d.connected ? I18n.t("Conectado") + (it.d.batteryAvailable ? I18n.t(" · bateria ") + Math.round(it.d.battery * 100) + "%" : "") : it.d.paired ? I18n.t("Pareado") : I18n.t("Disponível"))
          color: Tema.texto3; font.pixelSize: Tema.tLegenda + 1
        }
      }
      Botao {
        compacto: true
        visible: it.d !== null
        texto: !it.d ? "" : (it.d.connected ? I18n.t("Desconectar") : it.d.paired ? I18n.t("Conectar") : I18n.t("Parear"))
        tipo: it.d && !it.d.connected ? "primario" : "normal"
        ocupado: !!(it.d && (it.d.pairing || it.d.state === BluetoothDeviceState.Connecting || it.d.state === BluetoothDeviceState.Disconnecting))
        onClicado: {
          if (it.d.connected) it.d.disconnect()
          else if (it.d.paired) it.d.connect()
          else { it.d.trusted = true; it.d.pair() }
        }
      }
      Botao { compacto: true; tipo: "fantasma"; glifo: Icones.lixeira; visible: !!(it.d && it.d.paired); onClicado: it.d.forget() }
    }
  }

  Secao { titulo: I18n.t("Seus dispositivos"); visible: pg.pareados.length > 0 }
  Ancora { chave: "btDispositivos" }
  Cartao {
    visible: pg.pareados.length > 0
    Repeater { model: pg.pareados; delegate: Disp { required property var modelData; required property int index; d: modelData; primeiro: index === 0 } }
  }

  Secao {
    titulo: I18n.t("Por perto")
    visible: !!(pg.ad && pg.ad.enabled)
    detalhe: pg.novos.length ? I18n.t("Coloque o aparelho em modo de pareamento e clique em Parear.") : I18n.t("Procurando aparelhos… deixe o seu em modo de pareamento.")
  }
  Cartao {
    visible: pg.novos.length > 0 && !!(pg.ad && pg.ad.enabled)
    Repeater { model: pg.novos.slice(0, 12); delegate: Disp { required property var modelData; required property int index; d: modelData; primeiro: index === 0 } }
  }

  Cartao {
    Layout.topMargin: 14
    Linha {
      chave: "btPainel"; glifo: Icones.dockTop
      titulo: I18n.t("Painel Bluetooth da barra")
      Botao { texto: I18n.t("Abrir"); onClicado: Sistema.solto(["simba-shell", "simba.bluetooth", "open"]) }
    }
  }
}
