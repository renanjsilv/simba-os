import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Networking
import qs.Comum
import qs.Janela

Pagina {
  id: pg
  titulo: pg.props ? pg.props : I18n.t("Rede e internet")
  subtitulo: pg.props ? I18n.t("Propriedades da rede Wi-Fi") : I18n.t("Wi-Fi, conexões e DNS (NetworkManager).")

  property var detalhes: []
  property string dns: ""
  property string senhaPara: ""

  // ── propriedades de uma rede salva (como no Windows 11) ───────────────────
  property string props: ""            // SSID com a tela de propriedades aberta
  property var pi: null                // simba-rede info
  property bool editIp: false
  property bool editDns: false
  property bool ipManual: false
  property bool dnsManual: false
  property string senhaVista: ""
  property bool esquecerConfirma: false
  property var salvas: []              // todas as redes Wi-Fi salvas (mesmo fora de alcance)
  function abrirProps(ssid) {
    props = ssid; pi = null; editIp = false; editDns = false; senhaVista = ""; esquecerConfirma = false
    lerProps()
  }
  function lerProps() {
    if (!props) return
    Sistema.rodar(["simba-rede", "info", props], function(o, code, err) {
      if (code !== 0) { Navegacao.confirmar((err || o).trim() || I18n.t("Rede não encontrada"), Icones.alert); pg.props = ""; return }
      try { pg.pi = JSON.parse(o) } catch (e) { pg.pi = null }
      if (pg.pi) { pg.ipManual = pg.pi.ip_manual; pg.dnsManual = pg.pi.dns_manual }
    })
  }
  // aplica uma mudança; "reconectar" refaz a conexão ativa para valer na hora
  function mudar(args, reconectar, msg) {
    Sistema.rodar(["simba-rede"].concat(args), function(o, code, err) {
      if (code !== 0) { Navegacao.confirmar((err || o).trim() || I18n.t("Não foi possível salvar"), Icones.alert); pg.lerProps(); return }
      var fim = function() { pg.lerProps(); pg.carregar(); if (msg) Navegacao.confirmar(msg, Icones.checkCircle) }
      if (reconectar && pg.pi && pg.pi.ativa) Sistema.rodar(["simba-rede", "aplicar", pg.props], fim); else fim()
    })
  }
  function abrirPelaBusca() {
    var d = Navegacao.destaque || ""
    if (Navegacao.pagina === "rede" && d.indexOf("props:") === 0) abrirProps(d.slice(6))
  }
  Connections { target: Navegacao; function onPulsoChanged() { pg.abrirPelaBusca() } }

  // ── tentativa de conexão: nunca fica "carregando" sem resposta ──────────
  // Antes o botão girava enquanto o NetworkManager tentava (pode ser para sempre: roteador que
  // aceita a senha mas não entrega endereço) e uma falha não aparecia em lugar nenhum.
  property string tentando: ""        // rede que esta página mandou conectar
  property string avisoPara: ""       // rede com mensagem embaixo
  property string aviso: ""
  property bool avisoErro: false
  function conectar(rede, senha) {
    pg.tentando = rede.name; pg.avisoPara = rede.name; pg.aviso = I18n.t("Conectando…"); pg.avisoErro = false
    limite.restart()
    if (senha !== undefined) rede.connectWithPsk(senha); else rede.connect()
  }
  function falhou(nome, texto) {
    if (pg.tentando !== nome) return
    limite.stop(); pg.tentando = ""
    pg.avisoPara = nome; pg.aviso = texto; pg.avisoErro = true
  }
  function textoFalha(reason, protegida) {
    if (protegida && (reason === ConnectionFailReason.NoSecrets || reason === ConnectionFailReason.WifiAuthTimeout))
      return I18n.t("Senha incorreta. Confira (maiúsculas contam) e tente de novo.")
    if (reason === ConnectionFailReason.WifiNetworkLost) return I18n.t("A rede saiu do alcance. Chegue mais perto do roteador e tente de novo.")
    if (reason === ConnectionFailReason.WifiClientDisconnected || reason === ConnectionFailReason.WifiClientFailed)
      return I18n.t("O roteador recusou a conexão. Tente de novo; se continuar, reinicie o roteador.")
    return I18n.t("Não foi possível conectar. Tente de novo.")
  }
  // Conectou: confere se o roteador entregou um endereço IPv4 (sem ele não há internet nem DNS)
  function conferirEndereco(nome) {
    var dev = pg.wifi ? pg.wifi.name : ""
    Sistema.sh("ip -4 -o addr show " + (dev ? "dev " + dev + " " : "") + "scope global | grep -q inet", function(o, code) {
      if (pg.avisoPara !== nome) return
      if (code === 0) { pg.aviso = I18n.t("Conectado"); pg.avisoErro = false; apagarAviso.restart() }
      else { pg.aviso = I18n.t("Conectado, mas o roteador não entregou um endereço (IPv4): sem internet. Desconecte e conecte de novo; se repetir, reinicie o roteador."); pg.avisoErro = true }
    })
  }
  Timer { id: apagarAviso; interval: 4000; onTriggered: if (!pg.avisoErro) { pg.avisoPara = ""; pg.aviso = "" } }
  Timer { id: conferir; property string nome: ""; interval: 12000; onTriggered: pg.conferirEndereco(nome) }
  Timer {
    id: limite
    interval: 45000
    onTriggered: {
      var nome = pg.tentando
      var rs = pg.redes
      for (var i = 0; i < rs.length; i++) if (rs[i].name === nome && !rs[i].connected) rs[i].disconnect()   // cancela a tentativa
      pg.falhou(nome, I18n.t("A rede não respondeu em 45 segundos. A senha pode estar certa, mas o roteador não liberou a conexão (não entregou endereço). Tente de novo, chegue mais perto ou reinicie o roteador."))
    }
  }

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
    Sistema.sh("nmcli -t -f TYPE,NAME connection show 2>/dev/null | sed -n 's/^802-11-wireless://p'", function(o) {
      pg.salvas = o.trim().split("\n").filter(function(l) { return l }).map(function(l) { return l.replace(/\\:/g, ":") })
    })
  }
  Component.onCompleted: { carregar(); lerFirewall(); abrirPelaBusca() }
  Timer { interval: 5000; running: true; repeat: true; onTriggered: pg.carregar() }

  function barras(s) { return s >= 75 ? Icones.wifiStrength4 : s >= 50 ? Icones.wifiStrength3 : s >= 25 ? Icones.wifiStrength2 : Icones.wifiStrength1 }

  Cartao {
    visible: pg.props === ""
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

  Secao { titulo: I18n.t("Redes Wi-Fi"); visible: pg.props === "" && Networking.wifiEnabled && pg.wifi !== null; detalhe: pg.redes.length ? "" : I18n.t("Procurando…") }
  Ancora { chave: "redes" }
  Cartao {
    visible: pg.props === "" && Networking.wifiEnabled && pg.redes.length > 0
    Repeater {
      model: pg.redes.slice(0, 12)
      delegate: Item {
        id: rd
        required property var modelData
        required property int index
        Layout.fillWidth: true
        implicitHeight: 54 + (pg.senhaPara === modelData.name ? 52 : 0) + (pg.avisoPara === modelData.name && pg.aviso ? avisoTxt.implicitHeight + 10 : 0)
        Connections {
          target: rd.modelData
          function onConnectionFailed(reason) { pg.falhou(rd.modelData.name, pg.textoFalha(reason, rd.modelData.security !== WifiSecurityType.Open)) }
          function onConnectedChanged() {
            if (rd.modelData.connected && pg.tentando === rd.modelData.name) {
              limite.stop(); pg.tentando = ""; pg.aviso = I18n.t("Conectado · conferindo a internet…")
              conferir.nome = rd.modelData.name; conferir.restart()
            }
          }
        }
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
            visible: rd.modelData.known || rd.modelData.connected
            compacto: true; tipo: "fantasma"; glifo: Icones.cog
            onClicado: pg.abrirProps(rd.modelData.name)
          }
          Botao {
            compacto: true
            texto: rd.modelData.connected ? I18n.t("Desconectar") : I18n.t("Conectar")
            tipo: rd.modelData.connected ? "normal" : "primario"
            ocupado: pg.tentando === rd.modelData.name || (rd.modelData.stateChanging && pg.tentando === "")
            onClicado: {
              if (rd.modelData.connected) { rd.modelData.disconnect(); if (pg.avisoPara === rd.modelData.name) { pg.avisoPara = ""; pg.aviso = "" } }
              else if (rd.modelData.known || rd.modelData.security === WifiSecurityType.Open) pg.conectar(rd.modelData)
              else pg.senhaPara = (pg.senhaPara === rd.modelData.name ? "" : rd.modelData.name)
            }
          }
        }
        RowLayout {
          visible: pg.senhaPara === rd.modelData.name
          x: 48; y: 54; width: parent.width - 64; height: 40
          spacing: 8
          Campo { id: senha; Layout.fillWidth: true; dica: I18n.t("Senha de “") + rd.modelData.name + "”"; echoMode: TextInput.Password; onAccepted: ok.clicado() }
          Botao { id: ok; texto: I18n.t("Entrar"); tipo: "primario"; compacto: true; onClicado: { pg.conectar(rd.modelData, senha.text); pg.senhaPara = ""; senha.text = "" } }
        }
        Texto {
          id: avisoTxt
          visible: pg.avisoPara === rd.modelData.name && pg.aviso !== ""
          x: 48; y: 54 + (pg.senhaPara === rd.modelData.name ? 52 : 0); width: parent.width - 64
          text: pg.aviso; wrapMode: Text.WordWrap
          color: pg.avisoErro ? Tema.perigo : Tema.texto3; font.pixelSize: Tema.tLegenda + 1
        }
      }
    }
  }

  Secao { titulo: I18n.t("Segurança"); visible: pg.props === "" }
  Cartao {
    visible: pg.props === ""
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

  Secao { titulo: I18n.t("Mais"); visible: pg.props === "" }
  Cartao {
    visible: pg.props === ""
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

  // ── redes salvas (inclusive fora de alcance), como "Gerenciar redes conhecidas" ──
  Secao { visible: pg.props === "" && pg.salvas.length > 0; titulo: I18n.t("Redes salvas") }
  Cartao {
    visible: pg.props === "" && pg.salvas.length > 0
    Repeater {
      model: pg.salvas
      delegate: Linha {
        required property var modelData
        glifo: Icones.wifi; titulo: modelData
        descricao: I18n.t("Propriedades, IP, DNS ou esquecer")
        Botao { compacto: true; texto: I18n.t("Propriedades"); onClicado: pg.abrirProps(modelData) }
      }
    }
  }

  // ── tela de propriedades ───────────────────────────────────────────────────
  Item {
    visible: pg.props !== ""
    Layout.fillWidth: true; implicitHeight: 36
    Botao { glifo: Icones.arrowLeft; texto: I18n.t("Voltar às redes"); tipo: "fantasma"; compacto: true; onClicado: pg.props = "" }
  }
  Texto { visible: pg.props !== "" && pg.pi === null; text: I18n.t("Carregando…"); color: Tema.texto3 }

  Cartao {
    visible: pg.props !== "" && pg.pi !== null
    Linha {
      glifo: Icones.wifi; titulo: I18n.t("Conectar automaticamente quando estiver no alcance")
      Interruptor { ligado: !!(pg.pi && pg.pi.automatico); onAlternado: function(x) { pg.mudar(["automatico", pg.props, x ? "sim" : "nao"], false) } }
    }
    Linha {
      glifo: Icones.wifi; titulo: I18n.t("Conexão limitada")
      descricao: I18n.t("Para planos com limite de dados: atualizações e sincronizações esperam")
      Interruptor { ligado: !!(pg.pi && pg.pi.limitada === "sim"); onAlternado: function(x) { pg.mudar(["limitada", pg.props, x ? "sim" : "auto"], false) } }
    }
    Linha {
      glifo: Icones.wifi; titulo: I18n.t("Endereço de hardware aleatório")
      descricao: I18n.t("Usa um endereço MAC próprio para esta rede, que dificulta rastrear o computador (reconecta)")
      Interruptor { ligado: !!(pg.pi && pg.pi.mac_aleatorio); onAlternado: function(x) { pg.mudar(["mac", pg.props, x ? "aleatorio" : "fixo"], true, I18n.t("Endereço de hardware alterado")) } }
    }
    Linha {
      glifo: Icones.wifi; titulo: I18n.t("IPv6")
      descricao: I18n.t("Desligue só se esta rede tiver problemas com IPv6 (reconecta)")
      Interruptor { ligado: !!(pg.pi && pg.pi.ipv6); onAlternado: function(x) { pg.mudar(["ipv6", pg.props, x ? "sim" : "nao"], true) } }
    }
  }

  Secao { visible: pg.props !== "" && pg.pi !== null; titulo: I18n.t("Configurações de IP") }
  Cartao {
    visible: pg.props !== "" && pg.pi !== null
    Linha {
      glifo: Icones.wifi; titulo: I18n.t("Atribuição de IP")
      descricao: !pg.pi ? "" : (pg.pi.ip_manual ? I18n.t("Manual · ") + pg.pi.ip + " · " + pg.pi.mascara + (pg.pi.gateway ? " · " + pg.pi.gateway : "") : I18n.t("Automático (DHCP)"))
      Botao { compacto: true; texto: pg.editIp ? I18n.t("Fechar") : I18n.t("Editar"); onClicado: { pg.editIp = !pg.editIp; if (pg.pi) pg.ipManual = pg.pi.ip_manual } }
    }
    ColumnLayout {
      visible: pg.editIp
      Layout.fillWidth: true; Layout.leftMargin: 56; Layout.rightMargin: 16; Layout.bottomMargin: 14
      spacing: 10
      Segmentado {
        opcoes: [{ valor: false, rotulo: I18n.t("Automático (DHCP)") }, { valor: true, rotulo: I18n.t("Manual") }]
        atual: pg.ipManual; onEscolhido: function(v) { pg.ipManual = v }
      }
      GridLayout {
        visible: pg.ipManual
        columns: 2; columnSpacing: 12; rowSpacing: 8
        Texto { text: I18n.t("Endereço IP"); color: Tema.texto2 }
        Campo { id: cIp; Layout.preferredWidth: 220; dica: "192.168.0.50"; text: pg.pi ? (pg.pi.ip || (pg.pi.agora ? pg.pi.agora.ipv4 : "")) : "" }
        Texto { text: I18n.t("Máscara de sub-rede"); color: Tema.texto2 }
        Campo { id: cMascara; Layout.preferredWidth: 220; dica: "255.255.255.0"; text: pg.pi ? (pg.pi.mascara || (pg.pi.agora ? pg.pi.agora.mascara : "255.255.255.0")) : "" }
        Texto { text: I18n.t("Gateway"); color: Tema.texto2 }
        Campo { id: cGw; Layout.preferredWidth: 220; dica: "192.168.0.1"; text: pg.pi ? (pg.pi.gateway || (pg.pi.agora ? pg.pi.agora.gateway : "")) : "" }
      }
      Texto {
        Layout.fillWidth: true; wrapMode: Text.WordWrap; color: Tema.texto3; font.pixelSize: Tema.tLegenda
        text: pg.ipManual ? I18n.t("Use um endereço livre da sua rede; um IP repetido derruba a internet deste ou de outro aparelho.")
                          : I18n.t("O roteador escolhe o endereço sozinho (recomendado).")
      }
      RowLayout {
        spacing: 8
        Botao { texto: I18n.t("Salvar"); tipo: "primario"; compacto: true
                onClicado: { pg.editIp = false
                             if (pg.ipManual) pg.mudar(["ip", pg.props, "manual", cIp.text, cMascara.text, cGw.text], true, I18n.t("IP manual salvo"))
                             else pg.mudar(["ip", pg.props, "auto"], true, I18n.t("IP automático")) } }
        Botao { texto: I18n.t("Cancelar"); compacto: true; onClicado: pg.editIp = false }
      }
    }
    Linha {
      glifo: Icones.wifi; titulo: I18n.t("Servidores DNS")
      descricao: !pg.pi ? "" : (pg.pi.dns_manual && pg.pi.dns.length ? I18n.t("Manual · ") + pg.pi.dns.join(", ") : I18n.t("Automático (do roteador)"))
      Botao { compacto: true; texto: pg.editDns ? I18n.t("Fechar") : I18n.t("Editar"); onClicado: { pg.editDns = !pg.editDns; if (pg.pi) pg.dnsManual = pg.pi.dns_manual } }
    }
    ColumnLayout {
      visible: pg.editDns
      Layout.fillWidth: true; Layout.leftMargin: 56; Layout.rightMargin: 16; Layout.bottomMargin: 14
      spacing: 10
      Segmentado {
        opcoes: [{ valor: false, rotulo: I18n.t("Automático") }, { valor: true, rotulo: I18n.t("Manual") }]
        atual: pg.dnsManual; onEscolhido: function(v) { pg.dnsManual = v }
      }
      GridLayout {
        visible: pg.dnsManual
        columns: 2; columnSpacing: 12; rowSpacing: 8
        Texto { text: I18n.t("DNS preferencial"); color: Tema.texto2 }
        Campo { id: cDns1; Layout.preferredWidth: 220; dica: "1.1.1.1"; text: pg.pi && pg.pi.dns.length > 0 ? pg.pi.dns[0] : "" }
        Texto { text: I18n.t("DNS alternativo"); color: Tema.texto2 }
        Campo { id: cDns2; Layout.preferredWidth: 220; dica: "8.8.8.8"; text: pg.pi && pg.pi.dns.length > 1 ? pg.pi.dns[1] : "" }
      }
      RowLayout {
        visible: pg.dnsManual
        spacing: 6
        Texto { text: I18n.t("Preencher:"); color: Tema.texto3; font.pixelSize: Tema.tLegenda }
        Repeater {
          model: [{ n: "Cloudflare", a: "1.1.1.1", b: "1.0.0.1" }, { n: "Google", a: "8.8.8.8", b: "8.8.4.4" }, { n: "Quad9", a: "9.9.9.9", b: "149.112.112.112" }]
          delegate: Botao { required property var modelData; compacto: true; tipo: "fantasma"; texto: modelData.n; onClicado: { cDns1.text = modelData.a; cDns2.text = modelData.b } }
        }
      }
      RowLayout {
        spacing: 8
        Botao { texto: I18n.t("Salvar"); tipo: "primario"; compacto: true
                onClicado: { pg.editDns = false
                             if (pg.dnsManual) pg.mudar(["dns", pg.props, "manual", cDns1.text, cDns2.text], true, I18n.t("DNS salvo"))
                             else pg.mudar(["dns", pg.props, "auto"], true, I18n.t("DNS automático")) } }
        Botao { texto: I18n.t("Cancelar"); compacto: true; onClicado: pg.editDns = false }
      }
    }
  }

  Secao { visible: pg.props !== "" && pg.pi !== null; titulo: I18n.t("Detalhes") }
  Cartao {
    visible: pg.props !== "" && pg.pi !== null
    Repeater {
      model: {
        var i = pg.pi; if (!i) return []
        var a = i.agora || {}
        var l = [[I18n.t("Nome da rede (SSID)"), i.ssid], [I18n.t("Segurança"), i.seguranca]]
        if (!i.ativa) l.push([I18n.t("Situação"), I18n.t("Não conectada agora")])
        if (a.protocolo) l.push([I18n.t("Protocolo"), a.protocolo])
        if (a.banda) l.push([I18n.t("Banda de rede"), a.banda + (a.canal ? I18n.t(" · canal ") + a.canal : "")])
        if (a.velocidade) l.push([I18n.t("Velocidade"), a.velocidade])
        if (a.sinal) l.push([I18n.t("Sinal"), a.sinal])
        if (a.ipv4) l.push([I18n.t("Endereço IPv4"), a.ipv4])
        if (a.mascara) l.push([I18n.t("Máscara de sub-rede"), a.mascara])
        if (a.gateway) l.push([I18n.t("Gateway"), a.gateway])
        if (a.ipv6 && a.ipv6.length) l.push([I18n.t("Endereço IPv6"), a.ipv6.join("\n")])
        if (a.dns && a.dns.length) l.push([I18n.t("Servidores DNS"), a.dns.join("\n")])
        if (a.mac) l.push([I18n.t("Endereço físico (MAC)"), a.mac])
        return l
      }
      delegate: Linha {
        required property var modelData
        titulo: modelData[0]
        Texto { text: modelData[1]; color: Tema.texto2; horizontalAlignment: Text.AlignRight }
      }
    }
    Linha {
      titulo: I18n.t("Senha da rede")
      descricao: pg.senhaVista
      Botao {
        compacto: true; glifo: Icones.eye
        texto: pg.senhaVista ? I18n.t("Ocultar") : I18n.t("Mostrar")
        onClicado: {
          if (pg.senhaVista) { pg.senhaVista = ""; return }
          Sistema.rodar(["simba-rede", "senha", pg.props], function(o, code) { pg.senhaVista = code === 0 && o.trim() ? o.trim() : I18n.t("(sem senha salva)") })
        }
      }
    }
    Linha {
      titulo: I18n.t("Copiar os detalhes")
      Botao {
        compacto: true; texto: I18n.t("Copiar")
        onClicado: {
          var i = pg.pi || {}, a = i.agora || {}
          var t = [i.ssid, i.seguranca, a.protocolo, a.banda, a.ipv4, a.mascara, a.gateway, (a.dns || []).join(" "), a.mac].filter(function(x) { return x }).join("\n")
          Sistema.rodar(["wl-copy"], function() { Navegacao.confirmar(I18n.t("Detalhes copiados"), Icones.checkCircle) }, t)
        }
      }
    }
  }

  Cartao {
    visible: pg.props !== "" && pg.pi !== null
    Linha {
      glifo: Icones.deleteOutline; titulo: I18n.t("Esquecer esta rede")
      descricao: I18n.t("Apaga a senha e as configurações salvas. Para voltar, conecte de novo com a senha.")
      Botao {
        compacto: true; tipo: "perigo"
        texto: pg.esquecerConfirma ? I18n.t("Esquecer agora?") : I18n.t("Esquecer")
        onClicado: {
          if (!pg.esquecerConfirma) { pg.esquecerConfirma = true; return }
          var nome = pg.props
          Sistema.rodar(["simba-rede", "esquecer", nome], function(o, code, err) {
            if (code !== 0) { Navegacao.confirmar((err || o).trim(), Icones.alert); return }
            pg.props = ""; pg.carregar(); Navegacao.confirmar(I18n.t("Rede esquecida: ") + nome, Icones.checkCircle)
          })
        }
      }
    }
  }
}
