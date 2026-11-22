import QtQuick
import QtQuick.Layouts
import QtQuick.Controls.Basic as C
import Quickshell
import qs.Comum
import qs.Janela

// Contas › Backup e sincronização no Google Drive.
// Inspirado na proposta visual nativa (sincronizacao-v2).
Pagina {
  id: pg
  titulo: I18n.t("Contas")
  subtitulo: I18n.t("Entre com o Google para guardar suas pastas e configurações no Drive e trazer tudo de volta numa máquina formatada.")
  interactive: !pg.mostrarModalPacotes && !pg.mostrarModalSair

  property var s: Navegacao.contaStatus
  property string senhaCripto: ""
  property bool usarCripto: false
  property bool confirmarRestaurar: false
  property bool confirmarSair: false
  property bool mostrarModalSair: false
  property bool mostrarModalPacotes: false
  property var pacotesLista: []
  property var pacotesFiltrados: []
  property var selecionadosMap: ({})
  property int qtdSelecionados: 0
  property string modoPacotesLocal: "todos"
  property string buscaPacotes: ""
  property bool carregandoPacotes: false
  property bool salvandoPacotes: false
  property bool mostrarCriptoAviso: false
  property string senhaCriptoNova: ""

  readonly property bool conectado: !!(s && s.conectado)
  readonly property bool ocupado: !!(s && (s.rodando || s.entrando))
  // Escolhas (o que vai para o backup, pausar, pastas) valem para a PRÓXIMA sincronização:
  // não travam enquanto um backup roda — antes ficavam apagadas quase o tempo todo.
  readonly property bool entrando: !!(s && s.entrando)
  readonly property bool precisaSenha: !!(s && s.cripto && s.erro && /senha|password/i.test(s.erro))
  readonly property bool pausado: !!(s && s.pausado)
  readonly property bool sincronizando: !!(s && (s.rodando || s.sincronizando))
  readonly property bool temConflito: !!(s && s.conflito)
  readonly property bool temErro: !!(s && s.erro && !precisaSenha)

  readonly property color corOk: "#8cc9a0"
  readonly property color corAzul: "#8fb4e8"
  readonly property color corAmbar: "#d9b56c"
  readonly property color corAviso: "#d99a8f"
  readonly property color corDesat: "#77777e"

  readonly property color corEstado: sincronizando ? corAzul : (pausado ? corAmbar : (temConflito || temErro ? corAviso : corOk))
  readonly property color corEstadoBg: Qt.rgba(corEstado.r, corEstado.g, corEstado.b, 0.14)
  readonly property string iconeEstado: sincronizando ? Icones.sync : (pausado ? Icones.pause : (temConflito || temErro ? Icones.alert : Icones.checkCircle))
  readonly property string textoEstado: sincronizando ? (s.progresso || I18n.t("Sincronizando…")) : (pausado ? I18n.t("Pausado") : (temConflito ? I18n.t("Precisa de você") : (temErro ? I18n.t("Atenção") : I18n.t("Tudo em dia"))))
  readonly property string subtextoEstado: pausado && s && s.pausado_ate ? (I18n.t("pausado até ") + pg.quando(s.pausado_ate)) : (sincronizando ? I18n.t("em andamento") : (I18n.t("sincronizado ") + pg.quando(s ? s.ultima : "")))

  function mb(b) {
    if (!b || b <= 0) return "0 MB"
    if (b >= 1099511627776) return (b / 1099511627776).toFixed(1).replace(".", I18n.decimal) + " TB"
    if (b >= 1073741824) return (b / 1073741824).toFixed(1).replace(".", I18n.decimal) + " GB"
    return Math.max(1, Math.round(b / 1048576)) + " MB"
  }

  function quando(iso) {
    if (!iso) return I18n.t("nunca")
    var d = new Date(iso), agora = new Date()
    var min = Math.round((agora - d) / 60000)
    if (min < 1) return I18n.t("agora mesmo")
    if (min < 60) return I18n.t("há ") + min + " min"
    if (min < 1440) return I18n.t("há ") + Math.round(min / 60) + " h"
    return d.toLocaleDateString(Qt.locale(), I18n.t("dd/MM/yyyy")) + I18n.t(" às ") + d.toLocaleTimeString(Qt.locale(), "HH:mm")
  }

  // Mostra a mudança na hora (o status completo pode levar alguns segundos) e grava.
  function alternarCategoria(id, v) {
    if (pg.s && pg.s.categorias) {
      var n = Object.assign({}, pg.s)
      n.categorias = Object.assign({}, pg.s.categorias)
      n.categorias[id] = v
      pg.s = n
    }
    Sistema.rodar(["conta", "categoria", id, v ? "liga" : "desliga"], function() { pg.atualizar() })
  }

  function atualizar() {
    Sistema.json(["conta", "status"], function(v) {
      if (v) {
        pg.s = v
        Navegacao.contaStatus = v
      }
    })
  }

  Component.onCompleted: pg.atualizar()

  // Atualização periódica: mais rápida durante operações
  Timer {
    interval: pg.s && (pg.s.rodando || pg.s.entrando) ? 2000 : 5000
    running: true; repeat: true
    onTriggered: pg.atualizar()
  }
  Timer { id: atrasoStatus; interval: 600; onTriggered: pg.atualizar() }

  function sincronizar() {
    Sistema.rodar(["conta", "sincronizar"], function(o, code) {
      pg.atualizar()
      if (code === 0) Navegacao.confirmar(I18n.t("Backup concluído"), Icones.checkCircle)
    })
    atrasoStatus.restart()
  }

  function restaurar() {
    confirmarRestaurar = false
    Sistema.rodar(["conta", "restaurar", "--sim", "--sem-pacotes"], function(o, code) {
      pg.atualizar()
      if (code === 0) Navegacao.confirmar(I18n.t("Configurações trazidas com sucesso"), Icones.backupRestore)
    })
    atrasoStatus.restart()
  }

  function entrar() {
    var args = ["conta", "entrar"], entrada = undefined
    if (usarCripto && senhaCripto.length >= 6) {
      args.push("--cripto", "-")
      entrada = senhaCripto + "\n"
    }
    Sistema.rodar(args, function(o, code) {
      campoCripto.text = ""
      pg.atualizar()
      if (code === 0) {
        Navegacao.versaoFoto++
        Navegacao.confirmar(I18n.t("Conta conectada"), Icones.accountCircle)
      }
    }, entrada)
    atrasoStatus.restart()
  }

  function abrirModalPacotes() {
    pg.mostrarModalPacotes = true
    pg.carregandoPacotes = true
    pg.buscaPacotes = ""
    Sistema.json(["conta", "pacotes-listar"], function(res) {
      pg.carregandoPacotes = false
      if (!res) return
      pg.modoPacotesLocal = res.modo || "todos"
      var mapa = {}
      var itens = res.itens || []
      var count = 0
      for (var i = 0; i < itens.length; i++) {
        var it = itens[i]
        var sel = (res.modo === "todos") ? true : !!it.selecionado
        mapa[it.id] = sel
        if (sel) count++
      }
      pg.selecionadosMap = mapa
      pg.qtdSelecionados = count
      pg.pacotesLista = itens
      pg.atualizarPacotesFiltrados()
    })
  }

  function atualizarPacotesFiltrados() {
    var b = (pg.buscaPacotes || "").trim().toLowerCase()
    if (!b) {
      pg.pacotesFiltrados = pg.pacotesLista
      return
    }
    var res = []
    for (var i = 0; i < pg.pacotesLista.length; i++) {
      var p = pg.pacotesLista[i]
      var str = ((p.nome || "") + " " + (p.id || "") + " " + (p.desc || "")).toLowerCase()
      if (str.indexOf(b) >= 0) {
        res.push(p)
      }
    }
    pg.pacotesFiltrados = res
  }

  function alternarPacote(id) {
    var novo = Object.assign({}, pg.selecionadosMap)
    novo[id] = !novo[id]
    pg.selecionadosMap = novo
    var c = 0
    for (var k in novo) { if (novo[k]) c++ }
    pg.qtdSelecionados = c
  }

  function marcarTodosPacotes(marcar) {
    var novo = Object.assign({}, pg.selecionadosMap)
    for (var i = 0; i < pg.pacotesLista.length; i++) {
      novo[pg.pacotesLista[i].id] = marcar
    }
    pg.selecionadosMap = novo
    pg.qtdSelecionados = marcar ? pg.pacotesLista.length : 0
  }

  function contarSelecionados() {
    if (pg.modoPacotesLocal === "todos") return pg.pacotesLista.length
    return pg.qtdSelecionados
  }

  function salvarEscolhasPacotes() {
    pg.salvandoPacotes = true
    if (pg.modoPacotesLocal === "todos") {
      Sistema.rodar(["conta", "pacotes-selecionar", "--modo", "todos"], function(o, code) {
        pg.salvandoPacotes = false
        pg.mostrarModalPacotes = false
        pg.atualizar()
        Navegacao.confirmar(I18n.t("Todos os programas incluídos no backup"), Icones.checkCircle)
      })
    } else {
      var sel = []
      for (var i = 0; i < pg.pacotesLista.length; i++) {
        var id = pg.pacotesLista[i].id
        if (pg.selecionadosMap[id]) sel.push(id)
      }
      var jsonIds = JSON.stringify(sel)
      Sistema.rodar(["conta", "pacotes-selecionar", "--modo", "escolher", "--json-ids", jsonIds], function(o, code) {
        pg.salvandoPacotes = false
        pg.mostrarModalPacotes = false
        pg.atualizar()
        Navegacao.confirmar(sel.length + " " + I18n.t("programas salvos para backup"), Icones.checkCircle)
      })
    }
  }

  // ── ESTADO DESCONECTADO (Seção 1a da proposta) ───────────────────────────
  Rectangle {
    Layout.fillWidth: true
    visible: !pg.conectado
    implicitHeight: colDesconectado.implicitHeight + 56
    radius: Tema.raioGrande
    gradient: Gradient {
      orientation: Gradient.Horizontal
      GradientStop { position: 0; color: Qt.rgba(Tema.realce.r, Tema.realce.g, Tema.realce.b, 0.22) }
      GradientStop { position: 1; color: Qt.rgba(Tema.realce.r, Tema.realce.g, Tema.realce.b, 0.06) }
    }
    border.width: 1
    border.color: Qt.rgba(Tema.realce.r, Tema.realce.g, Tema.realce.b, 0.40)
    Ancora { chave: "contaEntrar"; anchors.top: parent.top; width: parent.width }

    ColumnLayout {
      id: colDesconectado
      anchors.fill: parent
      anchors.margins: 32
      spacing: 12
      Layout.alignment: Qt.AlignHCenter

      Texto {
        text: I18n.t("SUA CONTA")
        color: Tema.texto3
        font.pixelSize: 12
        font.weight: Font.Bold
        Layout.alignment: Qt.AlignHCenter
      }

      Texto {
        text: I18n.t("Seus arquivos em todos os computadores")
        font.pixelSize: 24
        font.weight: Font.DemiBold
        Layout.alignment: Qt.AlignHCenter
      }

      Texto {
        text: I18n.t("Entre com sua conta Google. Suas pastas ficam guardadas no Drive e se atualizam sozinhas. Trocou de computador? É só entrar de novo.")
        color: Tema.texto2
        font.pixelSize: 14
        wrapMode: Text.WordWrap
        Layout.maximumWidth: 580
        horizontalAlignment: Text.AlignHCenter
        Layout.alignment: Qt.AlignHCenter
      }

      Item { Layout.preferredHeight: 6 }

      Botao {
        Layout.alignment: Qt.AlignHCenter
        texto: pg.s && pg.s.entrando ? I18n.t("Termine o login no navegador…") : I18n.t("Entrar com Google")
        glifo: Icones.accountCircle
        tipo: "primario"
        ocupado: !!(pg.s && pg.s.entrando)
        habilitado: !pg.ocupado && (!pg.usarCripto || pg.senhaCripto.length >= 6)
        onClicado: pg.entrar()
      }

      Texto {
        Layout.topMargin: 8
        Layout.alignment: Qt.AlignHCenter
        text: I18n.t("O Simba OS só acessa a pasta “Simba Conta” que ele mesmo cria no seu Drive.")
        color: Tema.texto3
        font.pixelSize: 13
      }
    }
  }

  Secao {
    visible: !pg.conectado
    titulo: I18n.t("Segurança e criptografia")
    detalhe: I18n.t("Opcional: proteja o backup com uma chave adicional.")
  }

  Cartao {
    visible: !pg.conectado
    Linha {
      chave: "contaCripto"
      glifo: Icones.shield
      titulo: I18n.t("Criptografar o backup com uma senha")
      descricao: I18n.t("Ninguém lê seus arquivos no Drive sem a senha — nem o Google. Também permite guardar chaves SSH e de API.")
      Interruptor { ligado: pg.usarCripto; onAlternado: function(x) { pg.usarCripto = x } }
    }
    Linha {
      visible: pg.usarCripto
      glifo: Icones.lock
      titulo: I18n.t("Senha do backup")
      descricao: pg.senhaCripto.length > 0 && pg.senhaCripto.length < 6 ? I18n.t("Use pelo menos 6 caracteres") : I18n.t("Anote num lugar seguro. Sem ela o backup não pode ser recuperado.")
      Campo { id: campoCripto; width: 240; echoMode: TextInput.Password; dica: I18n.t("mínimo 6 caracteres"); onTextChanged: pg.senhaCripto = text }
    }
  }

  // ── ESTADO CONECTADO (Seção 3 da proposta) ───────────────────────────────

  // 1. Cabeçalho geral de status (.head da proposta)
  Rectangle {
    id: cardHead
    visible: pg.conectado
    Layout.fillWidth: true
    implicitHeight: layoutHead.implicitHeight + 32
    radius: Tema.raioGrande
    color: Tema.superficie
    border.width: 1
    border.color: Tema.linha
    Ancora { chave: "conta"; anchors.top: parent.top; width: parent.width }

    RowLayout {
      id: layoutHead
      anchors.fill: parent
      anchors.margins: 18
      spacing: 16

      // Ícone grande circular (.head .big)
      Rectangle {
        Layout.preferredWidth: 44
        Layout.preferredHeight: 44
        radius: 22
        color: pg.corEstadoBg
        Layout.alignment: Qt.AlignVCenter
        Glifo {
          anchors.centerIn: parent
          g: pg.iconeEstado
          tamanho: 22
          color: pg.corEstado
        }
      }

      // Informações centrais (.head .tx)
      ColumnLayout {
        Layout.fillWidth: true
        Layout.alignment: Qt.AlignVCenter
        spacing: 2

        Texto {
          text: pg.textoEstado
          font.pixelSize: 17
          font.weight: Font.Bold
          Layout.fillWidth: true
        }

        Texto {
          text: (pg.s ? (pg.s.email || "Google Drive") : "") + " · " + pg.subtextoEstado
          color: Tema.texto3
          font.pixelSize: 13
          Layout.fillWidth: true
          elide: Text.ElideRight
        }

        Item { Layout.preferredHeight: 3 }

        // Barra de progresso + texto de cota
        RowLayout {
          spacing: 10
          Layout.alignment: Qt.AlignVCenter

          Rectangle {
            Layout.preferredWidth: 200
            Layout.preferredHeight: 6
            radius: 3
            color: Tema.linha
            clip: true
            Rectangle {
              height: parent.height
              radius: 3
              color: pg.corEstado
              width: {
                var total = (pg.s && pg.s.cota_total) ? pg.s.cota_total : (15 * 1024 * 1024 * 1024)
                var usado = (pg.s && pg.s.cota_usado !== undefined) ? pg.s.cota_usado : ((pg.s && pg.s.tamanho) ? pg.s.tamanho : 0)
                var fracao = total > 0 ? (usado / total) : 0
                return Math.max(6, parent.width * Math.min(1.0, Math.max(0.02, fracao)))
              }
            }
          }

          Texto {
            text: pg.mb(pg.s ? (pg.s.cota_usado !== undefined ? pg.s.cota_usado : pg.s.tamanho) : 0) + " " + I18n.t("de") + " " + (pg.s && pg.s.cota_total ? pg.mb(pg.s.cota_total) : "15 GB")
            color: Tema.texto2
            font.pixelSize: 12
            font.weight: Font.Medium
          }
        }
      }

      // Botão Pausar / Retomar
      Botao {
        texto: pg.pausado ? I18n.t("Retomar") : I18n.t("Pausar")
        glifo: pg.pausado ? Icones.sync : Icones.pause
        tipo: pg.pausado ? "primario" : "fantasma"
        compacto: true
        habilitado: !pg.entrando
        Layout.alignment: Qt.AlignVCenter
        onClicado: {
          if (pg.pausado) {
            Sistema.rodar(["conta", "retomar"], function() { pg.atualizar(); Navegacao.confirmar(I18n.t("Sincronização retomada"), Icones.checkCircle) })
          } else {
            Sistema.rodar(["conta", "pausar", "24"], function() { pg.atualizar(); Navegacao.confirmar(I18n.t("Sincronização pausada"), Icones.pause) })
          }
        }
      }

      // Botão Abrir no Drive
      Botao {
        texto: I18n.t("Abrir no Drive")
        glifo: Icones.openInNew
        tipo: "fantasma"
        compacto: true
        Layout.alignment: Qt.AlignVCenter
        onClicado: Qt.openUrlExternally("https://drive.google.com/drive/search?q=%22Simba%20Conta%22")
      }

      // Botão Sair da conta
      Botao {
        texto: I18n.t("Sair")
        glifo: Icones.logout
        tipo: "fantasma"
        compacto: true
        habilitado: !pg.ocupado
        Layout.alignment: Qt.AlignVCenter
        onClicado: pg.mostrarModalSair = true
      }
    }
  }

  // Banner de conflito entre computadores
  Aviso {
    Layout.fillWidth: true
    visible: pg.conectado && pg.temConflito
    tipo: "aviso"
    glifo: Icones.alert
    texto: I18n.t("Conflito de alterações:") + " " + (pg.s && pg.s.conflito && pg.s.conflito.maquina_remota ? pg.s.conflito.maquina_remota : I18n.t("Outro computador")) + " " + I18n.t("enviou configurações concorrentes. Escolha qual manter:")
    acoes: [
      Botao {
        texto: I18n.t("Manter deste computador")
        tipo: "primario"
        habilitado: !pg.ocupado
        onClicado: Sistema.rodar(["conta", "resolver", "local"], function() { pg.atualizar(); Navegacao.confirmar(I18n.t("Versão deste computador mantida"), Icones.checkCircle) })
      },
      Botao {
        texto: I18n.t("Usar da nuvem")
        tipo: "fantasma"
        habilitado: !pg.ocupado
        onClicado: Sistema.rodar(["conta", "resolver", "remoto"], function() { pg.atualizar(); Navegacao.confirmar(I18n.t("Alterações da nuvem aplicadas"), Icones.checkCircle) })
      }
    ]
  }

  // Conta ligada pelo acesso antigo (client_id compartilhado do rclone, que o Google está
  // desativando): pede para entrar de novo pelo acesso do Simba, mantendo as escolhas.
  Aviso {
    Layout.fillWidth: true
    visible: pg.conectado && !!(pg.s && pg.s.reconectar)
    tipo: "aviso"
    glifo: Icones.alert
    texto: I18n.t("Entre de novo na conta Google para continuar sincronizando: o acesso antigo está sendo desativado pelo Google. Suas pastas e escolhas ficam como estão.")
    acoes: Botao {
      texto: I18n.t("Reconectar")
      tipo: "primario"
      habilitado: !pg.entrando
      onClicado: Sistema.rodar(["conta", "reconectar"], function() { pg.atualizar() })
    }
  }

  // Banner se houver favoritos pendentes para o Brave
  Aviso {
    Layout.fillWidth: true
    visible: pg.conectado && !!(pg.s && pg.s.brave_pendente)
    tipo: "info"
    glifo: Icones.sync
    texto: I18n.t("Novos favoritos recebidos da nuvem estão prontos para o navegador.")
    acoes: Botao {
      texto: I18n.t("Aplicar agora")
      tipo: "primario"
      habilitado: !pg.ocupado
      onClicado: Sistema.rodar(["conta", "brave"], function(o, code) {
        pg.atualizar()
        Navegacao.confirmar(code === 0 ? I18n.t("Favoritos aplicados!") : I18n.t("Falha ao aplicar"), code === 0 ? Icones.checkCircle : Icones.alert)
      })
    }
  }

  // 2. Grid de duas colunas (.cfgcols da proposta)
  RowLayout {
    visible: pg.conectado
    Layout.fillWidth: true
    spacing: 24
    Layout.alignment: Qt.AlignTop

    // ── COLUNA ESQUERDA: Pastas sincronizadas & Seus computadores ─────────
    ColumnLayout {
      Layout.fillWidth: true
      Layout.preferredWidth: 1
      Layout.alignment: Qt.AlignTop
      spacing: 12

      // Título do grupo: Pastas sincronizadas (nos dois sentidos)
      RowLayout {
        Layout.fillWidth: true
        Texto {
          text: I18n.t("Pastas sincronizadas")
          font.pixelSize: 14
          font.weight: Font.DemiBold
        }
        Item { Layout.fillWidth: true }
        Texto {
          text: I18n.t("iguais em todos os computadores")
          color: Tema.texto3
          font.pixelSize: 12
        }
      }

      // Card com lista de pastas sincronizadas
      Cartao {
        Repeater {
          model: pg.s && pg.s.pastas_info ? pg.s.pastas_info : []
          delegate: Item {
            id: rowPasta
            required property var modelData
            required property int index
            Layout.fillWidth: true
            implicitHeight: 52

            Rectangle {
              visible: rowPasta.index > 0
              anchors.top: parent.top
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.leftMargin: 14
              anchors.rightMargin: 14
              height: 1
              color: Tema.linha
            }

            Rectangle {
              anchors.fill: parent
              anchors.margins: 2
              radius: Tema.raio
              color: areaPasta.containsMouse ? Tema.hover : "transparent"
              Behavior on color { ColorAnimation { duration: Tema.rapido } }
            }

            RowLayout {
              anchors.fill: parent
              anchors.leftMargin: 14
              anchors.rightMargin: 14
              spacing: 12

              ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                spacing: 2
                Texto {
                  text: rowPasta.modelData.nome
                  font.pixelSize: 14
                  font.weight: Font.Medium
                  Layout.fillWidth: true
                  elide: Text.ElideRight
                }
                Texto {
                  text: pg.mb(rowPasta.modelData.tamanho) + " · " + (rowPasta.modelData.arquivos === 1 ? I18n.t("1 arquivo") : ((rowPasta.modelData.arquivos || 0) + " " + I18n.t("arquivos")))
                  color: Tema.texto3
                  font.pixelSize: 13
                  Layout.fillWidth: true
                  elide: Text.ElideRight
                }
              }

              // Status badge à direita
              RowLayout {
                spacing: 6
                Layout.alignment: Qt.AlignVCenter | Qt.AlignRight

                Rectangle {
                  width: 7; height: 7; radius: 3.5
                  color: pg.corEstado
                }
                Texto {
                  text: pg.sincronizando ? I18n.t("Enviando") : (pg.pausado ? I18n.t("Pausado") : I18n.t("Em dia"))
                  color: Tema.texto2
                  font.pixelSize: 13
                }

                Botao {
                  visible: !rowPasta.modelData.padrao
                  glifo: Icones.deleteOutline
                  tipo: "fantasma"
                  habilitado: !pg.entrando
                  onClicado: Sistema.rodar(["conta", "pasta", "remover", rowPasta.modelData.id], function() { pg.atualizar() })
                }
              }
            }

            MouseArea {
              id: areaPasta
              anchors.fill: parent
              hoverEnabled: true
              cursorShape: Qt.PointingHandCursor
              onClicked: Sistema.rodar(["xdg-open", rowPasta.modelData.caminho])
            }
          }
        }

        // Linha interativa "Adicionar pasta…"
        Item {
          id: rowAdd
          Layout.fillWidth: true
          implicitHeight: 44

          Rectangle {
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            height: 1
            color: Tema.linha
          }

          Rectangle {
            anchors.fill: parent
            anchors.margins: 2
            radius: Tema.raio
            color: areaAdd.containsMouse ? Tema.hover : "transparent"
            Behavior on color { ColorAnimation { duration: Tema.rapido } }
          }

          Texto {
            anchors.centerIn: parent
            text: I18n.t("Adicionar pasta…")
            color: areaAdd.containsMouse ? Tema.realce : Tema.texto2
            font.weight: Font.Medium
            font.pixelSize: 14
          }

          MouseArea {
            id: areaAdd
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
              Sistema.rodar(["zenity", "--file-selection", "--directory", "--title=" + I18n.t("Escolha uma pasta para sincronizar")], function(o, code) {
                if (code === 0 && o.trim() !== "") {
                  Sistema.rodar(["conta", "pasta", "adicionar", o.trim()], function() {
                    pg.atualizar()
                    Navegacao.confirmar(I18n.t("Pasta adicionada à sincronização"), Icones.checkCircle)
                  })
                }
              })
            }
          }
        }
      }

      // Título do grupo: Seus computadores
      Texto {
        Layout.topMargin: 10
        text: I18n.t("Seus computadores")
        font.pixelSize: 14
        font.weight: Font.DemiBold
      }

      // Card com lista de computadores
      Cartao {
        Repeater {
          model: pg.s && pg.s.dispositivos ? pg.s.dispositivos : []
          delegate: Item {
            id: rowComp
            required property var modelData
            required property int index
            Layout.fillWidth: true
            implicitHeight: 52

            Rectangle {
              visible: rowComp.index > 0
              anchors.top: parent.top
              anchors.left: parent.left
              anchors.right: parent.right
              anchors.leftMargin: 14
              anchors.rightMargin: 14
              height: 1
              color: Tema.linha
            }

            RowLayout {
              anchors.fill: parent
              anchors.leftMargin: 14
              anchors.rightMargin: 14
              spacing: 12

              ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignVCenter
                spacing: 2

                RowLayout {
                  spacing: 6
                  Texto {
                    text: rowComp.modelData.maquina
                    font.pixelSize: 14
                    font.weight: Font.Medium
                  }
                  Rectangle {
                    visible: !!rowComp.modelData.este_dispositivo
                    radius: 4
                    color: Qt.rgba(255, 255, 255, 0.08)
                    implicitHeight: 18
                    implicitWidth: lblEste.implicitWidth + 10
                    Layout.alignment: Qt.AlignVCenter
                    Texto {
                      id: lblEste
                      anchors.centerIn: parent
                      text: I18n.t("Este computador")
                      font.pixelSize: 11
                      color: Tema.texto2
                      font.weight: Font.Medium
                    }
                  }
                }

                Texto {
                  text: rowComp.modelData.este_dispositivo
                        ? I18n.t("Ativo agora")
                        : (rowComp.modelData.data ? (I18n.t("Visto ") + pg.quando(rowComp.modelData.data)) : I18n.t("Vinculado")) + (rowComp.modelData.tamanho ? " · " + pg.mb(rowComp.modelData.tamanho) : "")
                  color: Tema.texto3
                  font.pixelSize: 13
                }
              }

              // Lado direito: dot Ativo ou botão Trazer para cá
              Item {
                Layout.preferredWidth: rowComp.modelData.este_dispositivo ? dotAtivo.implicitWidth : btnTrazer.implicitWidth
                Layout.preferredHeight: 34
                Layout.alignment: Qt.AlignVCenter | Qt.AlignRight

                RowLayout {
                  id: dotAtivo
                  anchors.right: parent.right
                  anchors.verticalCenter: parent.verticalCenter
                  visible: !!rowComp.modelData.este_dispositivo
                  spacing: 6
                  Rectangle { width: 7; height: 7; radius: 3.5; color: pg.corOk }
                  Texto { text: I18n.t("Ativo"); color: Tema.texto2; font.pixelSize: 13 }
                }

                Botao {
                  id: btnTrazer
                  anchors.right: parent.right
                  anchors.verticalCenter: parent.verticalCenter
                  visible: !rowComp.modelData.este_dispositivo
                  texto: I18n.t("Trazer para cá")
                  tipo: "fantasma"
                  compacto: true
                  habilitado: !pg.ocupado
                  onClicado: pg.restaurar()
                }
              }
            }
          }
        }
      }
    }

    // ── COLUNA DIREITA: Aplicativos e configurações (backup automático) ──
    ColumnLayout {
      Layout.fillWidth: true
      Layout.preferredWidth: 1
      Layout.alignment: Qt.AlignTop
      spacing: 12

      // Título do grupo: Aplicativos e configurações (backup automático)
      RowLayout {
        Layout.fillWidth: true
        Texto {
          text: I18n.t("Aplicativos e configurações")
          font.pixelSize: 14
          font.weight: Font.DemiBold
        }
        Item { Layout.fillWidth: true }
        Texto {
          text: I18n.t("backup automático")
          color: Tema.texto3
          font.pixelSize: 12
        }
      }

      // Card com switches das 6 categorias da proposta
      Cartao {
        // 1. Aparência
        Item {
          Layout.fillWidth: true
          implicitHeight: 52
          RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            spacing: 12
            ColumnLayout {
              Layout.fillWidth: true
              Layout.alignment: Qt.AlignVCenter
              spacing: 2
              Texto { text: I18n.t("Aparência"); font.pixelSize: 14; font.weight: Font.Medium }
              Texto { text: I18n.t("Papel de parede, tema e barra"); color: Tema.texto3; font.pixelSize: 13 }
            }
            Interruptor {
              ligado: !(pg.s && pg.s.categorias && pg.s.categorias.config === false)
              habilitado: !pg.entrando
              Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
              onAlternado: function(v) { pg.alternarCategoria("config", v) }
            }
          }
        }

        // 2. Brave
        Item {
          Layout.fillWidth: true
          implicitHeight: 52
          Rectangle { anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 14; anchors.rightMargin: 14; height: 1; color: Tema.linha }
          RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            spacing: 12
            ColumnLayout {
              Layout.fillWidth: true
              Layout.alignment: Qt.AlignVCenter
              spacing: 2
              Texto { text: I18n.t("Brave"); font.pixelSize: 14; font.weight: Font.Medium }
              Texto { text: I18n.t("Favoritos e histórico"); color: Tema.texto3; font.pixelSize: 13 }
            }
            Interruptor {
              ligado: !(pg.s && pg.s.categorias && (pg.s.categorias.brave === false || (pg.s.categorias.brave === undefined && pg.s.categorias.historico === false)))
              habilitado: !pg.entrando
              Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
              onAlternado: function(v) { pg.alternarCategoria("brave", v) }
            }
          }
        }

        // 3. Terminal e atalhos
        Item {
          Layout.fillWidth: true
          implicitHeight: 52
          Rectangle { anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 14; anchors.rightMargin: 14; height: 1; color: Tema.linha }
          RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            spacing: 12
            ColumnLayout {
              Layout.fillWidth: true
              Layout.alignment: Qt.AlignVCenter
              spacing: 2
              Texto { text: I18n.t("Terminal e atalhos"); font.pixelSize: 14; font.weight: Font.Medium }
              Texto { text: I18n.t("Atalhos de teclado, terminal e Neovim"); color: Tema.texto3; font.pixelSize: 13 }
            }
            Interruptor {
              ligado: !(pg.s && pg.s.categorias && (pg.s.categorias.terminal === false || (pg.s.categorias.terminal === undefined && pg.s.categorias.config === false)))
              habilitado: !pg.entrando
              Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
              onAlternado: function(v) { pg.alternarCategoria("terminal", v) }
            }
          }
        }

        // 4. Draco e Agentes de IA
        Item {
          Layout.fillWidth: true
          implicitHeight: 52
          Rectangle { anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 14; anchors.rightMargin: 14; height: 1; color: Tema.linha }
          RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            spacing: 12
            ColumnLayout {
              Layout.fillWidth: true
              Layout.alignment: Qt.AlignVCenter
              spacing: 2
              Texto { text: I18n.t("Draco e Agentes de IA"); font.pixelSize: 14; font.weight: Font.Medium }
              Texto { text: I18n.t("Preferências e conversas, sem chaves"); color: Tema.texto3; font.pixelSize: 13 }
            }
            Interruptor {
              ligado: !(pg.s && pg.s.categorias && (pg.s.categorias.draco === false || (pg.s.categorias.draco === undefined && pg.s.categorias.config === false)))
              habilitado: !pg.entrando
              Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
              onAlternado: function(v) { pg.alternarCategoria("draco", v) }
            }
          }
        }

        // 5. Programas instalados
        Item {
          id: rowPacotes
          Layout.fillWidth: true
          implicitHeight: 52
          Rectangle { anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 14; anchors.rightMargin: 14; height: 1; color: Tema.linha }

          Rectangle {
            anchors.fill: parent
            anchors.margins: 2
            radius: Tema.raio
            visible: !(pg.s && pg.s.categorias && pg.s.categorias.pacotes === false)
            color: areaRowPacotes.containsMouse ? Tema.hover : "transparent"
            Behavior on color { ColorAnimation { duration: Tema.rapido } }
          }

          RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            spacing: 12

            ColumnLayout {
              Layout.fillWidth: true
              Layout.alignment: Qt.AlignVCenter
              spacing: 2
              Texto {
                text: I18n.t("Programas instalados")
                font.pixelSize: 14
                font.weight: Font.Medium
                Layout.fillWidth: true
                elide: Text.ElideRight
              }
              RowLayout {
                spacing: 6
                Layout.fillWidth: true
                Texto {
                  text: {
                    if (pg.s && pg.s.categorias && pg.s.categorias.pacotes === false) return I18n.t("Backup de programas desativado")
                    if (pg.s && pg.s.pacotes_modo === "escolher") {
                      return (pg.s.qtd_pacotes_selecionados || 0) + " " + I18n.t("de") + " " + (pg.s.qtd_pacotes || 215) + " " + I18n.t("selecionados")
                    }
                    return I18n.t("Todos os ") + (pg.s && pg.s.qtd_pacotes ? pg.s.qtd_pacotes : 215) + " " + I18n.t("programas")
                  }
                  color: Tema.texto3
                  font.pixelSize: 13
                  elide: Text.ElideRight
                }
                Texto {
                  visible: !(pg.s && pg.s.categorias && pg.s.categorias.pacotes === false)
                  text: "· " + I18n.t("Escolher…")
                  color: areaRowPacotes.containsMouse ? Tema.realce : Tema.texto2
                  font.pixelSize: 13
                  font.weight: Font.Medium
                }
                Item { Layout.fillWidth: true }
              }
            }

            Interruptor {
              ligado: !(pg.s && pg.s.categorias && pg.s.categorias.pacotes === false)
              habilitado: !pg.entrando
              Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
              onAlternado: function(v) { pg.alternarCategoria("pacotes", v) }
            }
          }

          MouseArea {
            id: areaRowPacotes
            anchors.fill: parent
            anchors.rightMargin: 60
            hoverEnabled: true
            cursorShape: !(pg.s && pg.s.categorias && pg.s.categorias.pacotes === false) ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: {
              if (!(pg.s && pg.s.categorias && pg.s.categorias.pacotes === false)) {
                pg.abrirModalPacotes()
              }
            }
          }
        }

        // 6. Chaves SSH e de API
        Item {
          Layout.fillWidth: true
          implicitHeight: 52
          Rectangle { anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right; anchors.leftMargin: 14; anchors.rightMargin: 14; height: 1; color: Tema.linha }
          RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            spacing: 12
            ColumnLayout {
              Layout.fillWidth: true
              Layout.alignment: Qt.AlignVCenter
              spacing: 2
              Texto { text: I18n.t("Chaves SSH e de API"); font.pixelSize: 14; font.weight: Font.Medium }
              Texto { text: I18n.t("Só com uma senha de backup"); color: Tema.texto3; font.pixelSize: 13 }
            }
            Interruptor {
              ligado: !!(pg.s && pg.s.cripto && pg.s.categorias && pg.s.categorias.segredos)
              habilitado: !pg.entrando
              Layout.alignment: Qt.AlignVCenter | Qt.AlignRight
              onAlternado: function(v) {
                if (v && !(pg.s && pg.s.cripto)) {
                  pg.mostrarCriptoAviso = true
                } else {
                  pg.alternarCategoria("segredos", v)
                }
              }
            }
          }
        }
      }

      // Legenda explicativa (.nota da proposta)
      Texto {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        text: I18n.t("Último backup ") + pg.quando(pg.s ? pg.s.ultima : "") + I18n.t(". Senhas salvas no Brave não saem do navegador.")
        color: Tema.texto3
        font.pixelSize: 13
        Layout.topMargin: -4
      }
    }
  }

  // ── AÇÕES GERAIS E CONTA ──────────────────────────────────────────────────
  Secao {
    visible: pg.conectado
    titulo: I18n.t("Backup e conta")
    detalhe: I18n.t("Configurações gerais de sincronização e desconexão.")
  }

  Cartao {
    visible: pg.conectado

    Linha {
      chave: "contaAuto"
      glifo: Icones.sync
      titulo: I18n.t("Sincronização dinâmica e backup automático")
      descricao: I18n.t("A cada 5 minutos as pastas ficam iguais em todos os seus computadores e as configurações vão para o backup.")
      Interruptor {
        ligado: !!(pg.s && pg.s.auto)
        onAlternado: function(x) { Sistema.rodar(["conta", "auto", x ? "liga" : "desliga"], function() { pg.atualizar() }) }
      }
    }

    Linha {
      chave: "contaFundo"
      glifo: Icones.wallpaper
      titulo: I18n.t("Sincronizar papel de parede na hora")
      descricao: I18n.t("Ao trocar o papel de parede aqui, muda na hora nos seus outros computadores.")
      Interruptor {
        ligado: !(pg.s && pg.s.sincronizar_fundo === false)
        onAlternado: function(x) { Sistema.rodar(["conta", "fundo", x ? "liga" : "desliga"], function() { pg.atualizar() }) }
      }
    }

    Linha {
      chave: "contaSair"
      glifo: Icones.logout
      titulo: I18n.t("Sair da conta")
      descricao: I18n.t("Para de fazer backup neste computador. Os dados no Drive continuam lá.")
      Botao {
        texto: I18n.t("Sair da conta…")
        tipo: "perigo"
        glifo: Icones.logout
        habilitado: !pg.ocupado
        onClicado: pg.mostrarModalSair = true
      }
    }
  }

  // ── MODAL DE ESCOLHA DE PROGRAMAS ─────────────────────────────────────────
  Rectangle {
    id: modalPacotes
    parent: pg
    visible: pg.mostrarModalPacotes
    x: 0
    y: pg.contentY
    width: pg.width
    height: pg.height
    z: 9999
    color: Qt.rgba(0, 0, 0, 0.65)
    focus: visible

    Keys.onEscapePressed: function(e) { pg.mostrarModalPacotes = false; e.accepted = true }

    MouseArea {
      anchors.fill: parent
      onWheel: function(wheel) { wheel.accepted = true }
      onClicked: pg.mostrarModalPacotes = false
    }

    Rectangle {
      id: cardModalPacotes
      anchors.centerIn: parent
      width: Math.min(680, parent.width - 40)
      height: Math.min(620, parent.height - 40)
      radius: Tema.raioGrande
      color: Tema.superficie
      border.width: 1
      border.color: Tema.linha
      clip: true

      MouseArea {
        anchors.fill: parent
        onClicked: {}
      }

      ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 12

        // Cabeçalho do modal
        RowLayout {
          Layout.fillWidth: true
          spacing: 12

          Rectangle {
            width: 38
            height: 38
            radius: 19
            color: Qt.rgba(Tema.realce.r, Tema.realce.g, Tema.realce.b, 0.15)
            Layout.alignment: Qt.AlignVCenter
            Glifo {
              anchors.centerIn: parent
              g: Icones.application
              tamanho: 20
              color: Tema.realce
            }
          }

          ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Texto {
              text: I18n.t("Programas em backup")
              font.pixelSize: 17
              font.weight: Font.Bold
            }
            Texto {
              text: I18n.t("Defina se quer guardar todos os programas ou escolher manualmente.")
              color: Tema.texto3
              font.pixelSize: 13
            }
          }

          Botao {
            glifo: Icones.close
            tipo: "fantasma"
            compacto: true
            onClicado: pg.mostrarModalPacotes = false
          }
        }

        // Seletor de Modo: Todos ou Escolher
        Segmentado {
          Layout.fillWidth: true
          opcoes: [
            { valor: "todos", rotulo: I18n.t("Todos os programas (" + (pg.pacotesLista ? pg.pacotesLista.length : 0) + ")") },
            { valor: "escolher", rotulo: I18n.t("Escolher quais programas") }
          ]
          atual: pg.modoPacotesLocal
          onEscolhido: function(v) { pg.modoPacotesLocal = v }
        }

        // Modo Todos: Painel explicativo
        Rectangle {
          Layout.fillWidth: true
          Layout.fillHeight: true
          visible: pg.modoPacotesLocal === "todos"
          radius: Tema.raio
          color: Tema.superficieAlta
          border.width: 1
          border.color: Tema.linha

          ColumnLayout {
            anchors.centerIn: parent
            spacing: 12
            Layout.maximumWidth: parent.width - 48

            Rectangle {
              Layout.alignment: Qt.AlignHCenter
              width: 52; height: 52; radius: 26
              color: Qt.rgba(pg.corOk.r, pg.corOk.g, pg.corOk.b, 0.15)
              Glifo {
                anchors.centerIn: parent
                g: Icones.checkCircle
                tamanho: 28
                color: pg.corOk
              }
            }

            Texto {
              Layout.alignment: Qt.AlignHCenter
              text: I18n.t("Backup completo de programas")
              font.pixelSize: 16
              font.weight: Font.DemiBold
            }

            Texto {
              Layout.alignment: Qt.AlignHCenter
              Layout.maximumWidth: 460
              horizontalAlignment: Text.AlignHCenter
              wrapMode: Text.WordWrap
              color: Tema.texto2
              font.pixelSize: 13
              text: I18n.t("O Simba OS faz o backup da lista completa de pacotes nativos (pacman), pacotes AUR e Flatpaks instalados nesta máquina. Em uma nova máquina ou após formatar, todos serão reinstalados automaticamente.")
            }
          }
        }

        // Modo Escolher: Campo de busca e ações rápidas
        RowLayout {
          Layout.fillWidth: true
          visible: pg.modoPacotesLocal === "escolher"
          spacing: 10

          Campo {
            id: campoBuscaPacotes
            Layout.fillWidth: true
            dica: I18n.t("Buscar programa por nome ou pacote…")
            glifo: Icones.magnify
            text: pg.buscaPacotes
            onTextChanged: {
              pg.buscaPacotes = text
              pg.atualizarPacotesFiltrados()
            }
          }

          Botao {
            texto: I18n.t("Marcar todos")
            tipo: "fantasma"
            compacto: true
            onClicado: pg.marcarTodosPacotes(true)
          }

          Botao {
            texto: I18n.t("Desmarcar todos")
            tipo: "fantasma"
            compacto: true
            onClicado: pg.marcarTodosPacotes(false)
          }
        }

        // Modo Escolher: Linha de contador
        RowLayout {
          Layout.fillWidth: true
          visible: pg.modoPacotesLocal === "escolher"
          spacing: 8
          Texto {
            text: pg.contarSelecionados() + " " + I18n.t("de") + " " + pg.pacotesLista.length + " " + I18n.t("programas selecionados para backup")
            color: Tema.texto2
            font.pixelSize: 12
            font.weight: Font.Medium
          }
          Item { Layout.fillWidth: true }
          Texto {
            visible: pg.buscaPacotes.trim() !== ""
            text: pg.pacotesFiltrados.length + " " + I18n.t("encontrados")
            color: Tema.texto3
            font.pixelSize: 12
          }
        }

        // Modo Escolher: Lista de programas rolável
        Rectangle {
          Layout.fillWidth: true
          Layout.fillHeight: true
          visible: pg.modoPacotesLocal === "escolher"
          radius: Tema.raio
          color: Tema.superficieAlta
          border.width: 1
          border.color: Tema.linha
          clip: true

          ListView {
            id: vistaPacotes
            anchors.fill: parent
            anchors.margins: 4
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            model: pg.pacotesFiltrados
            spacing: 2

            C.ScrollBar.vertical: C.ScrollBar {
              id: barraPacotes
              policy: C.ScrollBar.AsNeeded
            }

            delegate: Item {
              id: rowItemPacote
              required property var modelData
              required property int index
              width: vistaPacotes.width - (barraPacotes.visible ? 12 : 0)
              height: 48

              readonly property bool marcado: !!(pg.selecionadosMap && pg.selecionadosMap[modelData.id])

              Rectangle {
                anchors.fill: parent
                radius: Tema.raioPequeno
                color: areaRowPacote.containsMouse ? Tema.hover : (rowItemPacote.marcado ? Qt.rgba(Tema.realce.r, Tema.realce.g, Tema.realce.b, 0.08) : "transparent")
                Behavior on color { ColorAnimation { duration: Tema.rapido } }
              }

              RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 12

                // Checkbox estilizado
                Rectangle {
                  Layout.preferredWidth: 20
                  Layout.preferredHeight: 20
                  radius: 4
                  color: rowItemPacote.marcado ? Tema.realce : "transparent"
                  border.width: rowItemPacote.marcado ? 0 : 1.5
                  border.color: rowItemPacote.marcado ? "transparent" : (areaRowPacote.containsMouse ? Tema.texto : Tema.texto3)
                  Layout.alignment: Qt.AlignVCenter

                  Glifo {
                    anchors.centerIn: parent
                    visible: rowItemPacote.marcado
                    g: Icones.check
                    tamanho: 14
                    color: Tema.sobreRealce
                  }
                }

                // Nome amigável e descrição
                ColumnLayout {
                  Layout.fillWidth: true
                  Layout.alignment: Qt.AlignVCenter
                  spacing: 1

                  RowLayout {
                    spacing: 8
                    Texto {
                      text: rowItemPacote.modelData.nome || rowItemPacote.modelData.id
                      font.pixelSize: 13
                      font.weight: Font.DemiBold
                      elide: Text.ElideRight
                    }
                    Texto {
                      visible: (rowItemPacote.modelData.nome || "") !== rowItemPacote.modelData.id
                      text: "(" + rowItemPacote.modelData.id + ")"
                      color: Tema.texto3
                      font.pixelSize: 12
                      elide: Text.ElideRight
                    }
                  }

                  Texto {
                    text: rowItemPacote.modelData.desc || ""
                    color: Tema.texto3
                    font.pixelSize: 12
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                  }
                }

                // Badge do tipo de pacote
                Rectangle {
                  radius: 4
                  implicitHeight: 18
                  implicitWidth: lblTipo.implicitWidth + 8
                  Layout.alignment: Qt.AlignVCenter
                  color: {
                    if (rowItemPacote.modelData.tipo === "aur") return Qt.rgba(0.9, 0.6, 0.2, 0.16)
                    if (rowItemPacote.modelData.tipo === "flatpak") return Qt.rgba(0.2, 0.7, 0.8, 0.16)
                    return Qt.rgba(255, 255, 255, 0.08)
                  }
                  Texto {
                    id: lblTipo
                    anchors.centerIn: parent
                    text: {
                      if (rowItemPacote.modelData.tipo === "aur") return "AUR"
                      if (rowItemPacote.modelData.tipo === "flatpak") return "Flatpak"
                      return I18n.t("Nativo")
                    }
                    font.pixelSize: 11
                    font.weight: Font.Medium
                    color: {
                      if (rowItemPacote.modelData.tipo === "aur") return "#e59866"
                      if (rowItemPacote.modelData.tipo === "flatpak") return "#5dade2"
                      return Tema.texto2
                    }
                  }
                }
              }

              MouseArea {
                id: areaRowPacote
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: pg.alternarPacote(rowItemPacote.modelData.id)
              }
            }
          }
        }

        // Rodapé com botões de ação
        RowLayout {
          Layout.fillWidth: true
          spacing: 10

          Item { Layout.fillWidth: true }

          Botao {
            texto: I18n.t("Cancelar")
            tipo: "fantasma"
            habilitado: !pg.salvandoPacotes
            onClicado: pg.mostrarModalPacotes = false
          }

          Botao {
            texto: pg.salvandoPacotes ? I18n.t("Salvando…") : I18n.t("Salvar escolhas")
            tipo: "primario"
            glifo: Icones.check
            ocupado: pg.salvandoPacotes
            habilitado: !pg.salvandoPacotes
            onClicado: pg.salvarEscolhasPacotes()
          }
        }
      }
    }
  }

  // ── MODAL DE CONFIRMAÇÃO DE SAÍDA ─────────────────────────────────────────
  Rectangle {
    id: modalSair
    parent: pg
    visible: pg.mostrarModalSair
    x: 0
    y: pg.contentY
    width: pg.width
    height: pg.height
    z: 9999
    color: Qt.rgba(0, 0, 0, 0.65)
    focus: visible

    Keys.onEscapePressed: function(e) { pg.mostrarModalSair = false; e.accepted = true }

    MouseArea {
      anchors.fill: parent
      onWheel: function(wheel) { wheel.accepted = true }
      onClicked: pg.mostrarModalSair = false
    }

    Rectangle {
      anchors.centerIn: parent
      width: Math.min(480, parent.width - 48)
      implicitHeight: layoutModalSair.implicitHeight + 40
      radius: Tema.raioGrande
      color: Tema.superficie
      border.width: 1
      border.color: Tema.linha

      MouseArea {
        anchors.fill: parent
        onClicked: {}
      }

      ColumnLayout {
        id: layoutModalSair
        anchors.fill: parent
        anchors.margins: 24
        spacing: 16

        RowLayout {
          spacing: 14
          Rectangle {
            width: 44; height: 44; radius: 22
            color: Qt.rgba(Tema.perigo.r, Tema.perigo.g, Tema.perigo.b, 0.15)
            Layout.alignment: Qt.AlignVCenter
            Glifo {
              anchors.centerIn: parent
              g: Icones.logout
              tamanho: 22
              color: Tema.perigo
            }
          }
          ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            Texto {
              text: I18n.t("Sair da conta Google?")
              font.pixelSize: 18
              font.weight: Font.Bold
            }
            Texto {
              text: pg.s && pg.s.email ? pg.s.email : I18n.t("Simba Conta")
              color: Tema.texto3
              font.pixelSize: 13
            }
          }
        }

        Texto {
          Layout.fillWidth: true
          wrapMode: Text.WordWrap
          color: Tema.texto2
          font.pixelSize: 14
          text: I18n.t("O Simba OS vai parar de fazer backup e sincronizar pastas e configurações neste computador.\n\nSeus dados salvos no Google Drive continuarão seguros e intactos. Você pode se reconectar novamente a qualquer momento.")
        }

        RowLayout {
          Layout.fillWidth: true
          Layout.topMargin: 8
          spacing: 10

          Item { Layout.fillWidth: true }

          Botao {
            texto: I18n.t("Cancelar")
            tipo: "fantasma"
            onClicado: pg.mostrarModalSair = false
          }

          Botao {
            texto: I18n.t("Sair da conta")
            tipo: "perigo"
            glifo: Icones.logout
            onClicado: {
              pg.mostrarModalSair = false
              Sistema.rodar(["conta", "sair"], function() {
                Navegacao.versaoFoto++
                Navegacao.contaStatus = null
                pg.atualizar()
                Navegacao.confirmar(I18n.t("Você saiu da conta"), Icones.logout)
              })
            }
          }
        }
      }
    }
  }
}
