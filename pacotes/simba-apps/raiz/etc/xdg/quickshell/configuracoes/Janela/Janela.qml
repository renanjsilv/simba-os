import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic as C
import Quickshell
import Quickshell.Io
import qs.Comum
import "Busca.js" as Busca

// The settings window. Created on demand and destroyed when closed (the
// desktop layer and Super+P keep running in the same process).
Scope {
  id: j
  property var confirmacao: null
  readonly property bool aberta: carregador.active

  // A lateral mostra grupos (como no Windows 11); as páginas de um grupo viram
  // abas no topo do conteúdo. Os ids das páginas não mudaram: `configuracoes
  // bluetooth`, a busca e os atalhos internos continuam abrindo a página certa.
  readonly property var grupos: [
    { id: "inicio", titulo: I18n.t("Início"), glifo: Icones.home, paginas: [
      { id: "inicio", titulo: I18n.t("Início"), glifo: Icones.home } ] },
    { separador: true },
    { id: "g-contas", titulo: I18n.t("Contas"), glifo: Icones.accountCircle, paginas: [
      { id: "contas", titulo: I18n.t("Contas"), aba: I18n.t("Sua conta"), glifo: Icones.accountCircle },
      { id: "bloqueio", titulo: I18n.t("Bloqueio e inatividade"), glifo: Icones.lockClock } ] },
    { id: "g-sistema", titulo: I18n.t("Sistema"), glifo: Icones.laptop, paginas: [
      { id: "tela", titulo: I18n.t("Tela"), glifo: Icones.monitor },
      { id: "som", titulo: I18n.t("Som"), glifo: Icones.volumeHigh },
      { id: "notificacoes", titulo: I18n.t("Notificações"), glifo: Icones.bell },
      { id: "energia", titulo: I18n.t("Energia e bateria"), aba: I18n.t("Energia"), glifo: Icones.batteryHeart },
      { id: "restauracao", titulo: I18n.t("Restauração do sistema"), aba: I18n.t("Restauração"), glifo: Icones.backupRestore },
      { id: "sistema", titulo: I18n.t("Sobre o sistema"), aba: I18n.t("Sobre"), glifo: Icones.informationOutline } ] },
    { id: "g-dispositivos", titulo: I18n.t("Bluetooth e dispositivos"), glifo: Icones.devices, paginas: [
      { id: "bluetooth", titulo: I18n.t("Bluetooth"), glifo: Icones.bluetooth },
      { id: "entrada", titulo: I18n.t("Teclado, mouse e touchpad"), aba: I18n.t("Teclado e mouse"), glifo: Icones.keyboard },
      { id: "atalhos", titulo: I18n.t("Atalhos de teclado"), aba: I18n.t("Atalhos"), glifo: Icones.keyboardOutline },
      { id: "impressoras", titulo: I18n.t("Impressoras e scanners"), aba: I18n.t("Impressoras"), glifo: Icones.printer } ] },
    { id: "g-rede", titulo: I18n.t("Rede e internet"), glifo: Icones.wifi, paginas: [
      { id: "rede", titulo: I18n.t("Rede e internet"), glifo: Icones.wifi } ] },
    { id: "g-personalizacao", titulo: I18n.t("Personalização"), glifo: Icones.palette, paginas: [
      { id: "personalizacao", titulo: I18n.t("Tema e papel de parede"), aba: I18n.t("Tema e fundo"), glifo: Icones.palette },
      { id: "barra", titulo: I18n.t("Barra"), glifo: Icones.dockTop },
      { id: "area", titulo: I18n.t("Área de trabalho"), glifo: Icones.viewGridOutline },
      { id: "janelas", titulo: I18n.t("Janelas e animações"), aba: I18n.t("Janelas"), glifo: Icones.dockWindow } ] },
    { id: "g-apps", titulo: I18n.t("Aplicativos"), glifo: Icones.apps, paginas: [
      { id: "apps", titulo: I18n.t("Aplicativos padrão"), glifo: Icones.apps },
      { id: "wine", titulo: I18n.t("Compatibilidade Windows"), aba: I18n.t("Windows (.exe)"), glifo: Icones.gamepadVariant },
      { id: "agentes", titulo: I18n.t("Agentes de IA"), glifo: Icones.robot } ] }
  ]
  // todas as páginas, na ordem dos grupos (busca, Ctrl+PgUp/PgDn)
  readonly property var paginas: {
    var o = []
    grupos.forEach(function(g) {
      (g.paginas || []).forEach(function(p) { o.push(Object.assign({ grupo: g.id }, p)) })
    })
    return o
  }
  function infoPagina(id) {
    for (var i = 0; i < paginas.length; i++) if (paginas[i].id === id) return paginas[i]
    return paginas[0]
  }
  function grupoDe(id) {
    for (var i = 0; i < grupos.length; i++) {
      var ps = grupos[i].paginas || []
      for (var k = 0; k < ps.length; k++) if (ps[k].id === id) return grupos[i]
    }
    return grupos[0]
  }
  // última aba aberta de cada grupo: voltar ao grupo volta para ela
  property var ultimaDoGrupo: ({})
  Connections {
    target: Navegacao
    function onPaginaChanged() {
      var m = Object.assign({}, j.ultimaDoGrupo)
      m[j.grupoDe(Navegacao.pagina).id] = Navegacao.pagina
      j.ultimaDoGrupo = m
    }
  }
  function abrirGrupo(id) {
    for (var i = 0; i < grupos.length; i++) {
      var g = grupos[i]
      if (g.id !== id) continue
      var ultima = ultimaDoGrupo[id]
      Navegacao.ir(ultima || g.paginas[0].id)
      return
    }
    Navegacao.ir(id)
  }
  function paginaDaChave(chave) { return Busca.paginaDe(chave) || "inicio" }

  function fechar() { carregador.active = false }
  function focar() {
    Sistema.solto(["hyprctl", "dispatch", 'hl.dsp.focus({ window = "class:com.simba.Configuracoes" })'])
  }
  Connections {
    target: Navegacao
    function onPedirJanela() {
      if (carregador.active) j.focar()
      else carregador.active = true
    }
  }
  onAbertaChanged: Navegacao.janelaAberta = aberta

  LazyLoader {
    id: carregador
    active: false

    FloatingWindow {
      id: win
      title: I18n.t("Configurações")
      visible: true
      implicitWidth: 1120
      implicitHeight: 720
      minimumSize: Qt.size(680, 460)
      color: Tema.janela
      onVisibleChanged: if (!visible) carregador.active = false

      Item {
        id: raiz
        anchors.fill: parent
        focus: true
        readonly property bool compacta: width < 880
        property bool buscando: lateral.busca.text.trim().length > 0

        Keys.onPressed: function(e) {
          if ((e.modifiers & Qt.ControlModifier) && (e.key === Qt.Key_F || e.key === Qt.Key_K)) {
            if (raiz.compacta) lateral.compactaBusca = true
            lateral.busca.forceActiveFocus(); lateral.busca.selectAll(); e.accepted = true
          } else if (e.key === Qt.Key_Escape) {
            if (lateral.busca.text.length) { lateral.busca.text = ""; raiz.forceActiveFocus() }
            else j.fechar()
            e.accepted = true
          } else if ((e.modifiers & Qt.ControlModifier) && e.key === Qt.Key_W) {
            j.fechar(); e.accepted = true
          } else if ((e.modifiers & Qt.AltModifier) && (e.key === Qt.Key_Up || e.key === Qt.Key_Down)) {
            raiz.moverPagina(e.key === Qt.Key_Up ? -1 : 1); e.accepted = true
          } else if ((e.modifiers & Qt.ControlModifier) && e.key === Qt.Key_PageDown) {
            raiz.moverPagina(1); e.accepted = true
          } else if ((e.modifiers & Qt.ControlModifier) && e.key === Qt.Key_PageUp) {
            raiz.moverPagina(-1); e.accepted = true
          }
        }
        function moverPagina(d) {
          var ids = j.paginas.map(function(p) { return p.id })
          var i = ids.indexOf(Navegacao.pagina)
          Navegacao.ir(ids[(i + d + ids.length) % ids.length])
        }

        Mica { anchors.fill: parent }

        RowLayout {
          anchors.fill: parent
          spacing: 0

          Lateral {
            id: lateral
            property bool compactaBusca: false
            Layout.fillHeight: true
            Layout.preferredWidth: compacta ? 64 : 286
            compacta: raiz.compacta && !compactaBusca
            paginas: j.grupos
            Behavior on Layout.preferredWidth { NumberAnimation { duration: Tema.medio; easing.type: Tema.curva } }
            onEscolhida: function(id) {
              if (id === "__busca") { compactaBusca = true; busca.forceActiveFocus(); return }
              busca.text = ""
              j.abrirGrupo(id)
              raiz.forceActiveFocus()
            }
            onBuscaFoco: function(f) { if (!f && busca.text === "") compactaBusca = false }
            onBuscaBaixo: { resultados.forceActiveFocus(); resultados.currentIndex = 0 }
            onBuscaEnter: if (resultados.count > 0) resultados.abrir(0)
          }

          Item {
            id: colunaDireita
            Layout.fillWidth: true
            Layout.fillHeight: true

          // Title strip: drag to move the window; its right end stays empty for
          // the minimize/maximize/close overlay (botoes-janela) at the top-right.
          Item {
            id: faixaTitulo
            anchors.left: parent.left
            anchors.right: parent.right
            height: 40
            Texto {
              anchors.verticalCenter: parent.verticalCenter
              x: 20
              text: raiz.buscando ? I18n.t("Configurações  ›  Busca") : I18n.t("Configurações  ›  ") + (j.grupoDe(Navegacao.pagina).paginas.length > 1
                    ? j.grupoDe(Navegacao.pagina).titulo + "  ›  " : "") + j.infoPagina(Navegacao.pagina).titulo
              color: Tema.texto3
              font.pixelSize: Tema.tLegenda + 1
            }
            MouseArea {
              anchors.fill: parent
              anchors.rightMargin: botoesNativos.width
              onPressed: win.startSystemMove()
              onDoubleClicked: botoesNativos.acao("alternar")
            }

            // Native caption buttons (Win11: 46 x 32, close turns red). The
            // Hyprland title bar is hidden for this app (botoes-janela config).
            Row {
              id: botoesNativos
              anchors.top: parent.top
              anchors.right: parent.right
              property string endereco: ""
              property bool maximizada: false
              function acao(a) {
                Sistema.solto(["hyprctl", "dispatch", "janelas.pedido('" + endereco + "', '" + a + "')"])
              }
              Process {
                id: acharEndereco
                command: ["bash", "-c", "hyprctl clients -j | jq -r '[.[] | select(.class==\"com.simba.Configuracoes\")][0].address // empty'"]
                running: true
                stdout: StdioCollector {
                  onStreamFinished: {
                    botoesNativos.endereco = text.trim()
                    if (!botoesNativos.endereco) tentarDeNovo.restart()
                  }
                }
              }
              Timer { id: tentarDeNovo; interval: 300; onTriggered: acharEndereco.running = true }
              FileView {
                id: estadoJanelas
                path: Quickshell.env("XDG_RUNTIME_DIR") + "/hypr-janelas.estado"
                watchChanges: true
                printErrors: false
                onFileChanged: reload()
                onLoaded: botoesNativos.conferir()
                onTextChanged: botoesNativos.conferir()
              }
              function conferir() {
                maximizada = endereco !== "" && estadoJanelas.text().split("\n").indexOf("max " + endereco) >= 0
              }
              onEnderecoChanged: conferir()
              Repeater {
                model: [
                  { a: "minimizar", g: Icones.minus },
                  { a: "alternar", g: botoesNativos.maximizada ? Icones.windowRestore : Icones.windowMaximize },
                  { a: "fechar", g: Icones.close }
                ]
                delegate: Rectangle {
                  id: bt
                  required property var modelData
                  readonly property bool fecha: modelData.a === "fechar"
                  width: 46; height: 32
                  color: btm.pressed ? (fecha ? "#b3261a" : Tema.pressionado) : btm.containsMouse ? (fecha ? "#c42b1c" : Tema.hover) : "transparent"
                  Glifo {
                    anchors.centerIn: parent
                    g: bt.modelData.g
                    tamanho: 14
                    color: bt.fecha && btm.containsMouse ? "white" : Tema.texto2
                  }
                  MouseArea {
                    id: btm
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: {
                      var a = bt.modelData.a
                      if (a === "fechar") j.fechar(); else botoesNativos.acao(a)
                    }
                  }
                }
              }
            }
          }

          Item {
            id: area
            anchors.fill: parent
            anchors.topMargin: 40
            clip: true

            // ── abas do grupo ────────────────────────────────────────────
            Item {
              id: abas
              readonly property var grupo: j.grupoDe(Navegacao.pagina)
              readonly property bool mostrar: !raiz.buscando && grupo.paginas.length > 1
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.top: parent.top
              height: mostrar ? 48 : 0
              opacity: mostrar ? 1 : 0
              visible: opacity > 0
              Behavior on opacity { NumberAnimation { duration: Tema.rapido } }
              Flickable {
                // alinhado com a coluna das páginas (Pagina.qml)
                width: Math.min(parent.width - 64, 940)
                x: Math.round((parent.width - width) / 2)
                y: 8
                height: 36
                clip: true
                contentWidth: seletorAbas.width + 4
                contentHeight: height
                interactive: contentWidth > width
                flickableDirection: Flickable.HorizontalFlick
                boundsBehavior: Flickable.StopAtBounds
                Segmentado {
                  id: seletorAbas
                  x: 2
                  y: 2
                  opcoes: abas.grupo.paginas.map(function(p) { return { valor: p.id, rotulo: p.aba || p.titulo, glifo: p.glifo } })
                  atual: Navegacao.pagina
                  onEscolhido: function(v) { Navegacao.ir(v) }
                }
              }
            }

            // ── page host ────────────────────────────────────────────────
            Loader {
              id: pagina
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.bottom: parent.bottom
              anchors.top: abas.bottom
              property string atual: ""
              opacity: raiz.buscando ? 0 : 1
              visible: opacity > 0
              Behavior on opacity { NumberAnimation { duration: Tema.rapido } }
              asynchronous: false
              function carregar(id) {
                if (atual === id) return
                atual = id
                saida.restart()
              }
              SequentialAnimation {
                id: saida
                NumberAnimation { target: pagina.item; property: "opacity"; to: 0; duration: Tema.animacoes ? 80 : 0 }
                ScriptAction { script: pagina.source = Qt.resolvedUrl("Paginas/" + pagina.atual + ".qml") }
              }
              onStatusChanged: if (status === Loader.Error) console.warn("configuracoes: falha ao carregar página", atual)
              Component.onCompleted: { atual = Navegacao.pagina; source = Qt.resolvedUrl("Paginas/" + atual + ".qml") }
              Connections {
                target: Navegacao
                function onPaginaChanged() { pagina.carregar(Navegacao.pagina) }
              }
            }

            // ── search results ───────────────────────────────────────────
            Item {
              anchors.fill: parent
              opacity: raiz.buscando ? 1 : 0
              visible: opacity > 0
              Behavior on opacity { NumberAnimation { duration: Tema.medio } }

              readonly property var achados: raiz.buscando ? Busca.buscar(lateral.busca.text, j.paginas, I18n.t) : []

              ColumnLayout {
                width: Math.min(parent.width - 64, 940)
                x: Math.round((parent.width - width) / 2)
                y: 26
                height: parent.height - 26
                spacing: 6
                Texto {
                  text: parent.parent.achados.length ? I18n.t("Resultados para “") + lateral.busca.text.trim() + "”" : I18n.t("Nada encontrado para “") + lateral.busca.text.trim() + "”"
                  font.pixelSize: Tema.tTitulao
                  font.weight: Font.Bold
                  Layout.fillWidth: true
                  elide: Text.ElideRight
                }
                Texto {
                  text: parent.parent.achados.length ? parent.parent.achados.length + (parent.parent.achados.length === 1 ? I18n.t(" configuração") : I18n.t(" configurações")) + I18n.t(" · ↑↓ para navegar, Enter para abrir")
                                                     : I18n.t("Tente outra palavra: “gaps”, “resolução”, “bloqueio”, “touchpad”…")
                  color: Tema.texto3
                  Layout.fillWidth: true
                  Layout.bottomMargin: 10
                }
                ListView {
                  id: resultados
                  Layout.fillWidth: true
                  Layout.fillHeight: true
                  clip: true
                  spacing: 4
                  model: parent.parent.achados
                  keyNavigationEnabled: true
                  highlightMoveDuration: 0
                  boundsBehavior: Flickable.StopAtBounds
                  function abrir(i) {
                    var r = model[i]
                    if (!r) return
                    lateral.busca.text = ""
                    Navegacao.ir(r.pagina, r.chave)
                    raiz.forceActiveFocus()
                  }
                  Keys.onReturnPressed: abrir(currentIndex)
                  Keys.onUpPressed: function(e) { if (currentIndex <= 0) lateral.busca.forceActiveFocus(); else decrementCurrentIndex() }
                  delegate: Rectangle {
                    id: res
                    required property var modelData
                    required property int index
                    readonly property bool sel: resultados.activeFocus && resultados.currentIndex === index
                    width: resultados.width
                    height: 58
                    radius: Tema.raioGrande
                    color: sel ? Tema.superficieMax : (mr.containsMouse ? Tema.superficieAlta : Tema.superficie)
                    border.width: 1
                    border.color: sel ? Tema.linhaForte : Tema.linha
                    Behavior on color { ColorAnimation { duration: Tema.rapido } }
                    opacity: 0
                    Component.onCompleted: entrada.start()
                    NumberAnimation on opacity { id: entrada; running: false; from: 0; to: 1; duration: Tema.medio + res.index * 25 }
                    RowLayout {
                      anchors.fill: parent
                      anchors.leftMargin: 14
                      anchors.rightMargin: 14
                      spacing: 14
                      Rectangle {
                        Layout.preferredWidth: 34; Layout.preferredHeight: 34
                        radius: Tema.raioPequeno + 1
                        color: Tema.superficieAlta
                        border.width: 1; border.color: Tema.linha
                        Glifo { anchors.centerIn: parent; g: res.modelData.glifo; tamanho: 17 }
                      }
                      ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Texto { text: res.modelData.titulo; font.weight: Font.Medium; font.pixelSize: Tema.tCorpo + 1; Layout.fillWidth: true; elide: Text.ElideRight }
                        Texto { text: res.modelData.caminho; color: Tema.texto3; font.pixelSize: Tema.tLegenda + 1; Layout.fillWidth: true; elide: Text.ElideRight }
                      }
                      Glifo { g: Icones.chevronRight; tamanho: 16; color: Tema.texto3 }
                    }
                    MouseArea { id: mr; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: resultados.abrir(res.index) }
                  }
                }
              }
            }

            // ── confirmation pill ────────────────────────────────────────
            Rectangle {
              id: pilula
              property string texto: ""
              property string glifo: ""
              anchors.horizontalCenter: parent.horizontalCenter
              y: parent.height - (mostrando ? height + 22 : -10)
              opacity: mostrando ? 1 : 0
              property bool mostrando: false
              Behavior on y { NumberAnimation { duration: Tema.lento; easing.type: Easing.OutBack; easing.overshoot: 1.1 } }
              Behavior on opacity { NumberAnimation { duration: Tema.medio } }
              width: linhaPilula.implicitWidth + 32
              height: 38
              radius: Tema.raio > 0 ? height / 2 : 2
              color: Tema.texto
              Sombra { alvo: pilula; deslocamento: 6 }
              Row {
                id: linhaPilula
                anchors.centerIn: parent
                spacing: 8
                Glifo { g: pilula.glifo || Icones.checkboxMarkedCircle; tamanho: 16; color: Tema.janela; anchors.verticalCenter: parent.verticalCenter }
                Texto { text: pilula.texto; color: Tema.janela; font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
              }
              Timer { id: esconder; interval: 2200; onTriggered: pilula.mostrando = false }
              Connections {
                target: Navegacao
                function onAviso(texto, glifo) {
                  pilula.texto = texto
                  pilula.glifo = glifo
                  pilula.mostrando = true
                  esconder.restart()
                }
              }
            }
          }
          }
        }
      }
    }
  }
}
