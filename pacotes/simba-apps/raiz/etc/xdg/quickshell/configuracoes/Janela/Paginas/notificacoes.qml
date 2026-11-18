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
  // Estilo dos cartões (lido pelo shell em ~/.config/simba/notificacoes.json; sem arquivo = "rpg")
  property string estilo: "rpg"
  property string tamanho: "pequeno"
  property string central: "escuro"
  readonly property var temasCentral: [
    { id: "escuro", nome: I18n.t("Windows 11 Dark Mica (Padrão)"), desc: I18n.t("Modo escuro translúcido com brilho e azul elétrico") },
    { id: "fluent", nome: I18n.t("Windows 11 Fluent Fiel"), desc: I18n.t("Vidro acrílico translúcido com cartões suaves") },
    { id: "pixel-rpg", nome: I18n.t("Simba Pixel Art Retrô"), desc: I18n.t("Estrutura Win11 em pixel art com fonte Simba Pixel e gatinho") },
    { id: "minimal", nome: I18n.t("Simba Minimal Moderno"), desc: I18n.t("Design limpo e monocromático sem transparências") }
  ]
  readonly property string arqEstilo: Sistema.home + "/.config/simba/notificacoes.json"
  readonly property string pastaPrevias: "file:///usr/share/simba-apps/notificacoes-estilos/"
  readonly property var estilosPixel: [
    { id: "rpg", nome: I18n.t("Caixa de diálogo RPG"), desc: I18n.t("Moldura dupla, como as falas de jogos antigos") },
    { id: "balao", nome: I18n.t("Balão do Simba"), desc: I18n.t("O gatinho avisa num balão de fala") },
    { id: "janela", nome: I18n.t("Janela clássica"), desc: I18n.t("Barra de título listrada com o nome do app") },
    { id: "conquista", nome: I18n.t("Conquista desbloqueada"), desc: I18n.t("Escuro, com barrinha de tempo em blocos") },
    { id: "portatil", nome: I18n.t("Portátil cinza"), desc: I18n.t("Tons de cinza e sombra pontilhada") },
    { id: "vidro-pixel", nome: I18n.t("Vidro pixelado"), desc: I18n.t("Translúcido em pontilhado, cantos em degrau") }
  ]
  readonly property var estilosNormais: [
    { id: "vidro", nome: I18n.t("Vidro"), desc: I18n.t("Translúcido com o fundo desfocado") },
    { id: "suave", nome: I18n.t("Cartão suave"), desc: I18n.t("Sombra macia e barrinha de tempo") },
    { id: "windows", nome: I18n.t("Estilo Windows 11"), desc: I18n.t("Cabeçalho com o nome do app") },
    { id: "escuro", nome: I18n.t("Escuro flutuante"), desc: I18n.t("Escuro mesmo no tema claro") },
    { id: "pilula", nome: I18n.t("Pílula compacta"), desc: I18n.t("Uma linha só, ocupa pouco espaço") },
    { id: "padrao", nome: I18n.t("Quadrado simples"), desc: I18n.t("O visual antigo, com borda") }
  ]
  function lerEstilo() {
    Sistema.sh("cat " + Sistema.q(pg.arqEstilo) + " 2>/dev/null", function(o) {
      var v = {}
      try { v = JSON.parse(o || "{}") || {} } catch (e) {}
      pg.estilo = v.estilo || "rpg"; pg.tamanho = v.tamanho || "pequeno"; pg.central = v.central || "escuro"
    })
  }
  function salvarPreferencias(testar) {
    var json = JSON.stringify({ estilo: pg.estilo, tamanho: pg.tamanho, central: pg.central }) + "\n"
    Sistema.rodar(["bash", "-c", "mkdir -p \"$(dirname \"$1\")\" && cat > \"$1\"", "--", pg.arqEstilo], function() {
      if (testar) Sistema.solto(["notify-send", "-a", "Configurações", "-i", "preferences-desktop-notification",
                                 I18n.t("Estilo das notificações"), I18n.t("Assim ficam as notificações agora.")])
    }, json)
  }
  function escolherEstilo(id) {
    pg.estilo = id
    pg.salvarPreferencias(true)
  }
  function escolherTamanho(v) { pg.tamanho = v; pg.salvarPreferencias(true) }
  function escolherCentral(v) { pg.central = v; pg.salvarPreferencias(false) }
  function carregar() {
    Sistema.sh("simba-shell notifications isDnd", function(o) { pg.dnd = o.trim() === "on" })
    Sistema.json([Sistema.ajudante, "notificacoes"], function(v) { if (v) pg.historico = v })
  }
  Component.onCompleted: { carregar(); lerEstilo() }
  Timer { interval: 4000; running: pg.visible; repeat: true; onTriggered: pg.carregar() }
  onVisibleChanged: if (visible) pg.carregar()

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


  // ── estilo ───────────────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Estilo dos avisos"); detalhe: I18n.t("Como os avisos aparecem no canto inferior direito. Vale na hora.") }
  Ancora { chave: "estiloNotif" }
  Repeater {
    model: [{ titulo: I18n.t("Pixel art"), lista: pg.estilosPixel }, { titulo: I18n.t("Clássicos"), lista: pg.estilosNormais }]
    delegate: ColumnLayout {
      id: grupo
      required property var modelData
      Layout.fillWidth: true
      spacing: 8
      Texto { text: grupo.modelData.titulo; font.weight: Font.DemiBold; color: Tema.texto2; Layout.topMargin: 4 }
      GridLayout {
        id: gradeEstilos
        Layout.fillWidth: true
        columns: Math.max(1, Math.floor((width + 12) / 252))
        columnSpacing: 12
        rowSpacing: 12
        Repeater {
          model: grupo.modelData.lista
          delegate: Rectangle {
            id: op
            required property var modelData
            readonly property bool escolhido: pg.estilo === op.modelData.id
            Layout.fillWidth: true
            Layout.preferredHeight: colOp.implicitHeight + 16
            radius: Tema.raio + 2
            color: escolhido ? Tema.selecao : (mOp.containsMouse ? Tema.hover : Tema.superficie)
            border.width: escolhido ? 2 : 1
            border.color: escolhido ? Tema.realce : Tema.linha
            ColumnLayout {
              id: colOp
              x: 8; y: 8; width: parent.width - 16
              spacing: 6
              Image {
                Layout.fillWidth: true
                Layout.preferredHeight: width * 150 / 440
                source: pg.pastaPrevias + op.modelData.id + ".png"
                fillMode: Image.PreserveAspectFit
                smooth: false
                mipmap: false
                asynchronous: true
              }
              RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Texto { text: op.modelData.nome; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
                Glifo { visible: op.escolhido; g: Icones.checkCircle; tamanho: 16; color: Tema.realce }
              }
              Texto { text: op.modelData.desc; color: Tema.texto3; font.pixelSize: Tema.tLegenda + 1; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            }
            MouseArea { id: mOp; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pg.escolherEstilo(op.modelData.id) }
          }
        }
      }
    }
  }

  Cartao {
    Layout.topMargin: 6
    Linha {
      chave: "tamanhoNotif"; glifo: Icones.messageText
      titulo: I18n.t("Tamanho dos avisos")
      descricao: I18n.t("O Pequeno ocupa menos espaço na tela.")
      Segmentado {
        opcoes: [{ valor: "pequeno", rotulo: I18n.t("Pequeno") }, { valor: "medio", rotulo: I18n.t("Médio") }, { valor: "grande", rotulo: I18n.t("Grande") }]
        atual: pg.tamanho
        onEscolhido: function(v) { pg.escolherTamanho(v) }
      }
    }
  }

  // ── tema da central (lista aberta pelo relógio) ─────────────────────────────
  Secao { titulo: I18n.t("Tema da central de notificações"); detalhe: I18n.t("Visual da lista de notificações que abre ao clicar no relógio.") }
  Ancora { chave: "temaCentral" }
  GridLayout {
    Layout.fillWidth: true
    columns: Math.max(1, Math.floor((width + 12) / 252))
    columnSpacing: 12
    rowSpacing: 12
    Repeater {
      model: pg.temasCentral
      delegate: Rectangle {
        id: tc
        required property var modelData
        readonly property bool escolhido: pg.central === tc.modelData.id
        Layout.fillWidth: true
        Layout.preferredHeight: colTc.implicitHeight + 16
        radius: Tema.raio + 2
        color: escolhido ? Tema.selecao : (mTc.containsMouse ? Tema.hover : Tema.superficie)
        border.width: escolhido ? 2 : 1
        border.color: escolhido ? Tema.realce : Tema.linha
        ColumnLayout {
          id: colTc
          x: 8; y: 8; width: parent.width - 16
          spacing: 6
          Item {
            Layout.fillWidth: true
            Layout.preferredHeight: width * 330 / 440
            Image {
              anchors.fill: parent
              visible: tc.modelData.id !== "auto"
              source: tc.modelData.id === "auto" ? "" : pg.pastaPrevias + "central/" + tc.modelData.id + ".png"
              fillMode: Image.PreserveAspectFit
              smooth: false
              asynchronous: true
            }
            // Automático: metade clássica, metade pixel
            Row {
              anchors.fill: parent
              visible: tc.modelData.id === "auto"
              Image { width: parent.width / 2; height: parent.height; source: pg.pastaPrevias + "central/fluent.png"; fillMode: Image.PreserveAspectCrop; horizontalAlignment: Image.AlignLeft; asynchronous: true }
              Image { width: parent.width / 2; height: parent.height; source: pg.pastaPrevias + "central/pixel-rpg.png"; fillMode: Image.PreserveAspectCrop; horizontalAlignment: Image.AlignRight; smooth: false; asynchronous: true }
            }
          }
          RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Texto { text: tc.modelData.nome; font.weight: Font.DemiBold; Layout.fillWidth: true; elide: Text.ElideRight }
            Glifo { visible: tc.escolhido; g: Icones.checkCircle; tamanho: 16; color: Tema.realce }
          }
          Texto { text: tc.modelData.desc; color: Tema.texto3; font.pixelSize: Tema.tLegenda + 1; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        }
        MouseArea { id: mTc; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: pg.escolherCentral(tc.modelData.id) }
      }
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
