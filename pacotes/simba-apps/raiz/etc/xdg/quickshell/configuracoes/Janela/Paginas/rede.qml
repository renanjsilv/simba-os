import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Networking
import qs.Comum
import qs.Janela

Pagina {
  id: pg
  titulo: I18n.t("Rede e internet")
  subtitulo: I18n.t("Wi-Fi, conexões e DNS (NetworkManager).")

  property var detalhes: []
  property string dns: ""
  property string senhaPara: ""

  readonly property var wifi: {
    var ds = Networking.devices ? Networking.devices.values : []
    for (var i = 0; i < ds.length; i++) if (ds[i].type === DeviceType.Wifi) return ds[i]
    return null
  }
  readonly property var redes: {
    if (!wifi || !wifi.networks) return []
    var v = wifi.networks.values.slice()
    v.sort(function(a, b) { return (b.connected - a.connected) || (b.known - a.known) || (b.signalStrength - a.signalStrength) })
    return v
  }
  Binding { target: pg.wifi; property: "scannerEnabled"; value: true; when: pg.wifi !== null && Networking.wifiEnabled }

  property bool firewall: true
  function lerFirewall() { Sistema.sh("grep -q '^ENABLED=yes' /etc/ufw/ufw.conf", function(o, code) { pg.firewall = code === 0 }) }

  function carregar() {
    Sistema.sh("nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device 2>/dev/null | grep -vE ':(loopback|bridge|tun|wifi-p2p):'; echo @@; ip -4 -o addr show scope global 2>/dev/null | awk '{print $2\" \"$4}'", function(o) {
      var p = o.split("@@")
      var ips = {}
      ;(p[1] || "").trim().split("\n").forEach(function(l) { var x = l.split(" "); if (x[0]) ips[x[0]] = x[1] })
      pg.detalhes = (p[0] || "").trim().split("\n").filter(function(l) { return l }).map(function(l) {
        var c = l.split(":")
        return { dispositivo: c[0], tipo: c[1], estado: c[2], conexao: c.slice(3).join(":"), ip: ips[c[0]] || "" }
      })
    })
    Sistema.sh("simba-dns 2>/dev/null", function(o) { pg.dns = o.trim() })
  }
  Component.onCompleted: { carregar(); lerFirewall() }
  Timer { interval: 5000; running: true; repeat: true; onTriggered: pg.carregar() }

  function barras(s) { return s >= 75 ? Icones.wifiStrength4 : s >= 50 ? Icones.wifiStrength3 : s >= 25 ? Icones.wifiStrength2 : Icones.wifiStrength1 }

  Cartao {
    Linha {
      chave: "wifi"; glifo: Networking.wifiEnabled ? Icones.wifi : Icones.wifiOff
      titulo: I18n.t("Wi-Fi")
      descricao: !Networking.wifiHardwareEnabled ? I18n.t("Bloqueado pelo botão/tecla do aparelho") : (Networking.wifiEnabled ? I18n.t("Ligado") : I18n.t("Desligado"))
      Interruptor { ligado: Networking.wifiEnabled; habilitado: Networking.wifiHardwareEnabled; onAlternado: function(x) { Networking.wifiEnabled = x } }
    }
    Repeater {
      model: pg.detalhes
      delegate: Linha {
        required property var modelData
        glifo: modelData.tipo === "wifi" ? Icones.wifi : (modelData.tipo === "ethernet" ? Icones.ethernet : Icones.lan)
        titulo: (modelData.tipo === "wifi" ? I18n.t("Wi-Fi") : modelData.tipo === "ethernet" ? I18n.t("Cabo (Ethernet)") : modelData.tipo) + " · " + modelData.dispositivo
        descricao: (modelData.estado.indexOf("connected") === 0 ? I18n.t("Conectado a ") + modelData.conexao : modelData.estado === "unavailable" ? I18n.t("Sem cabo / indisponível") : modelData.estado === "disconnected" ? I18n.t("Desconectado") : modelData.estado) + (modelData.ip ? " · " + modelData.ip : "")
      }
    }
  }

  Secao { titulo: I18n.t("Redes Wi-Fi"); visible: Networking.wifiEnabled && pg.wifi !== null; detalhe: pg.redes.length ? "" : I18n.t("Procurando…") }
  Ancora { chave: "redes" }
  Cartao {
    visible: Networking.wifiEnabled && pg.redes.length > 0
    Repeater {
      model: pg.redes.slice(0, 12)
      delegate: Item {
        id: rd
        required property var modelData
        required property int index
        Layout.fillWidth: true
        implicitHeight: 54 + (pg.senhaPara === modelData.name ? 52 : 0)
        Behavior on implicitHeight { NumberAnimation { duration: Tema.medio } }
        clip: true
        Rectangle { visible: rd.index > 0; anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 16; anchors.rightMargin: 16; height: 1; color: Tema.linha }
        RowLayout {
          x: 16; width: parent.width - 32; height: 54
          spacing: 14
          Glifo { g: pg.barras(rd.modelData.signalStrength * (rd.modelData.signalStrength <= 1 ? 100 : 1)); tamanho: 18; color: rd.modelData.connected ? Tema.realce : Tema.texto }
          ColumnLayout {
            Layout.fillWidth: true
            spacing: 1
            Texto { text: rd.modelData.name || I18n.t("(rede oculta)"); font.weight: rd.modelData.connected ? Font.DemiBold : Font.Normal; elide: Text.ElideRight; Layout.fillWidth: true }
            Texto {
              text: (rd.modelData.connected ? I18n.t("Conectada · ") : rd.modelData.known ? I18n.t("Salva · ") : "") + (rd.modelData.security === WifiSecurityType.Open ? I18n.t("Aberta") : I18n.t("Protegida"))
              color: Tema.texto3; font.pixelSize: Tema.tLegenda + 1
            }
          }
          Glifo { visible: rd.modelData.security !== WifiSecurityType.Open; g: Icones.lock; tamanho: 13; color: Tema.texto3 }
          Botao {
            compacto: true
            texto: rd.modelData.connected ? I18n.t("Desconectar") : I18n.t("Conectar")
            tipo: rd.modelData.connected ? "normal" : "primario"
            ocupado: rd.modelData.stateChanging
            onClicado: {
              if (rd.modelData.connected) rd.modelData.disconnect()
              else if (rd.modelData.known || rd.modelData.security === WifiSecurityType.Open) rd.modelData.connect()
              else pg.senhaPara = (pg.senhaPara === rd.modelData.name ? "" : rd.modelData.name)
            }
          }
        }
        RowLayout {
          visible: pg.senhaPara === rd.modelData.name
          x: 48; y: 54; width: parent.width - 64; height: 40
          spacing: 8
          Campo { id: senha; Layout.fillWidth: true; dica: I18n.t("Senha de “") + rd.modelData.name + "”"; echoMode: TextInput.Password; onAccepted: ok.clicado() }
          Botao { id: ok; texto: I18n.t("Entrar"); tipo: "primario"; compacto: true; onClicado: { rd.modelData.connectWithPsk(senha.text); pg.senhaPara = ""; senha.text = "" } }
        }
      }
    }
  }

  Secao { titulo: I18n.t("Segurança") }
  Cartao {
    Linha {
      chave: "firewall"; glifo: pg.firewall ? Icones.shieldCheck : Icones.shieldOff
      titulo: I18n.t("Firewall")
      descricao: pg.firewall ? I18n.t("Ligado · bloqueia conexões que chegam da rede (recomendado)") : I18n.t("Desligado · outros aparelhos da rede podem tentar se conectar a este computador")
      Interruptor {
        ligado: pg.firewall
        onAlternado: function(x) {
          Sistema.rodar(["/usr/bin/simba-sistema", "firewall", x ? "liga" : "desliga"], function(o, code) {
            pg.lerFirewall()
            if (code === 0) Navegacao.confirmar(x ? I18n.t("Firewall ligado") : I18n.t("Firewall desligado"), Icones.shield)
          })
        }
      }
    }
  }

  Secao { titulo: I18n.t("Mais") }
  Cartao {
    Linha {
      chave: "dns"; glifo: Icones.dns
      titulo: I18n.t("Servidor DNS")
      descricao: I18n.t("Pede a senha de administrador")
      Selecao {
        width: 200
        opcoes: [{ valor: "DHCP", rotulo: I18n.t("Automático (DHCP)") }, { valor: "Cloudflare", rotulo: I18n.t("Cloudflare (1.1.1.1)") }, { valor: "Google", rotulo: I18n.t("Google (8.8.8.8)") }, { valor: "Custom", rotulo: I18n.t("Personalizado…") }]
        atual: pg.dns
        onEscolhido: function(x) {
          if (x === "Custom") Sistema.solto(["simba-launch-floating-terminal-with-presentation", "simba-dns Custom"])
          else Sistema.rodar(["simba-dns", x], function(o, code) { pg.carregar(); if (code === 0) Navegacao.confirmar(I18n.t("DNS: ") + x, Icones.dns) })
        }
      }
    }
    Linha {
      chave: "qrWifi"; glifo: Icones.qrcode
      titulo: I18n.t("Compartilhar o Wi-Fi por QR Code")
      descricao: I18n.t("Aponte a câmera do celular para entrar na rede")
      Botao { texto: I18n.t("Mostrar"); onClicado: Sistema.solto(["simba-shell", "shell", "summon", "simba.wifiqr", "{}"]) }
    }
    Linha {
      chave: "velocidadeRede"; glifo: Icones.speedometer
      titulo: I18n.t("Teste de velocidade")
      Botao { texto: I18n.t("Testar"); onClicado: Sistema.solto(["simba-shell", "shell", "summon", "simba.speedtest", "{}"]) }
    }
    Linha {
      chave: "painelRede"; glifo: Icones.dockTop
      titulo: I18n.t("Painel de rede da barra")
      Botao { texto: I18n.t("Abrir"); onClicado: Sistema.solto(["simba-shell", "simba.network", "open"]) }
    }
  }
}
