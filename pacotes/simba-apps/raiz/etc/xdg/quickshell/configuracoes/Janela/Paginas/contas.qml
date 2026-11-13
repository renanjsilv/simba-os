import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.Comum
import qs.Janela

// Contas › Backup no Google Drive (como "Backup do Windows" com a conta Microsoft).
// Tudo passa pelo /usr/bin/conta (rclone, pasta "Simba Conta" no Drive).
Pagina {
  id: pg
  titulo: I18n.t("Contas")
  subtitulo: I18n.t("Entre com o Google para guardar o sistema no Drive e trazer tudo de volta numa máquina formatada.")

  property var s: null
  property string senhaCripto: ""
  property bool usarCripto: false
  property bool confirmarRestaurar: false
  property bool confirmarSair: false
  property real tamanhoLocal: 0
  property int arquivosLocal: 0

  function atualizar() { Sistema.json(["conta", "status"], function(v) { if (v) pg.s = v }) }
  function medir() {
    Sistema.json(["conta", "tamanho"], function(v) { if (v) { pg.tamanhoLocal = v.tamanho; pg.arquivosLocal = v.arquivos } })
  }
  Component.onCompleted: { atualizar(); medir() }
  // Conta conectada sem foto baixada (login antigo): baixa uma vez.
  property bool fotoPedida: false
  onSChanged: {
    if (s && s.conectado && !s.foto && !fotoPedida && !s.rodando) {
      fotoPedida = true
      Sistema.rodar(["conta", "foto"], function(o, code) { if (code === 0) { Navegacao.versaoFoto++; pg.atualizar() } })
    }
  }
  // Mais rápido enquanto algo está rodando (login, envio, restauração).
  Timer {
    interval: pg.s && (pg.s.rodando || pg.s.entrando) ? 1000 : 4000
    running: true; repeat: true
    onTriggered: pg.atualizar()
  }

  readonly property bool conectado: !!(s && s.conectado)
  readonly property bool ocupado: !!(s && (s.rodando || s.entrando))
  readonly property bool precisaSenha: !!(s && s.cripto && s.erro && /senha|password/i.test(s.erro))

  function mb(b) {
    if (b >= 1073741824) return (b / 1073741824).toFixed(1).replace(".", I18n.decimal) + " GB"
    return Math.max(1, Math.round(b / 1048576)) + " MB"
  }
  function quando(iso) {
    if (!iso) return "nunca"
    var d = new Date(iso), agora = new Date()
    var min = Math.round((agora - d) / 60000)
    if (min < 1) return I18n.t("agora mesmo")
    if (min < 60) return I18n.t("há ") + min + " min"
    if (min < 1440) return I18n.t("há ") + Math.round(min / 60) + " h"
    return d.toLocaleDateString(Qt.locale(), I18n.t("dd/MM/yyyy")) + I18n.t(" às ") + d.toLocaleTimeString(Qt.locale(), "HH:mm")
  }

  function entrar() {
    var args = ["conta", "entrar"], entrada = undefined
    // A senha vai pela entrada padrão (não aparece na lista de processos).
    if (usarCripto && senhaCripto.length >= 6) { args.push("--cripto", "-"); entrada = senhaCripto + "\n" }
    Sistema.rodar(args, function(o, code) {
      campoCripto.text = ""
      pg.atualizar(); pg.medir()
      if (code === 0) { Navegacao.versaoFoto++; Navegacao.confirmar(I18n.t("Conta conectada"), Icones.accountCircle) }
    }, entrada)
    atrasoStatus.restart()
  }
  Timer { id: atrasoStatus; interval: 600; onTriggered: pg.atualizar() }
  function sincronizar(substituir) {
    Sistema.rodar(substituir ? ["conta", "sincronizar", "--substituir"] : ["conta", "sincronizar"], function(o, code) {
      pg.atualizar()
      if (code === 0) Navegacao.confirmar(I18n.t("Backup concluído"), Icones.checkCircle)
    })
    atrasoStatus.restart()
  }
  function restaurar() {
    confirmarRestaurar = false
    Sistema.rodar(["conta", "restaurar", "--sim", "--sem-pacotes"], function(o, code) {
      pg.atualizar()
      if (code === 0) Navegacao.confirmar(I18n.t("Conta restaurada"), Icones.backupRestore)
    })
    atrasoStatus.restart()
  }

  // ── boas-vindas: primeira inicialização depois de formatar ──────────────
  // (~/.local/state/conta/boas-vindas, criado pelo instalador da ISO)
  Rectangle {
    Layout.fillWidth: true
    visible: !!(pg.s && pg.s.boas_vindas)
    implicitHeight: colBoas.implicitHeight + 56
    radius: Tema.raioGrande
    gradient: Gradient {
      orientation: Gradient.Horizontal
      GradientStop { position: 0; color: Qt.rgba(Tema.realce.r, Tema.realce.g, Tema.realce.b, 0.30) }
      GradientStop { position: 1; color: Qt.rgba(Tema.realce.r, Tema.realce.g, Tema.realce.b, 0.08) }
    }
    border.width: 1
    border.color: Qt.rgba(Tema.realce.r, Tema.realce.g, Tema.realce.b, 0.45)
    RowLayout {
      anchors.fill: parent
      anchors.margins: 28
      spacing: 24
      Glifo { Layout.alignment: Qt.AlignTop; g: Icones.backupRestore; tamanho: 56; color: Tema.realce }
      ColumnLayout {
        id: colBoas
        Layout.fillWidth: true
        spacing: 8
        Texto { text: I18n.t("Já usa este sistema em outro computador?"); font.pixelSize: 24; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Texto {
          Layout.fillWidth: true
          wrapMode: Text.WordWrap
          color: Tema.texto2
          text: I18n.t("Opcional. Entre com sua conta Google para trazer um backup: configurações, papel de parede, ") +
                I18n.t("histórico do navegador e do terminal, documentos e a lista de programas. ") +
                I18n.t("Se é a primeira vez, é só pular — dá para entrar depois aqui em Contas.")
        }
        RowLayout {
          Layout.topMargin: 8
          spacing: 10
          Botao {
            texto: pg.s && pg.s.entrando ? I18n.t("Termine o login no navegador…") : I18n.t("Entrar com o Google")
            glifo: Icones.accountCircle
            tipo: "primario"
            ocupado: !!(pg.s && pg.s.entrando)
            habilitado: !pg.ocupado
            onClicado: pg.entrar()
          }
          Botao {
            texto: I18n.t("Pular")
            tipo: "fantasma"
            habilitado: !pg.ocupado
            onClicado: Sistema.rodar(["conta", "boas-vindas", "fechar"], function() { pg.atualizar() })
          }
          Botao {
            texto: I18n.t("Não perguntar mais")
            tipo: "fantasma"
            habilitado: !pg.ocupado
            onClicado: Sistema.rodar(["conta", "boas-vindas", "desliga"], function() { pg.atualizar() })
          }
        }
      }
    }
  }

  // ── cabeçalho da conta ───────────────────────────────────────────────────
  Rectangle {
    Layout.fillWidth: true
    Layout.preferredHeight: 128
    radius: Tema.raioGrande
    color: Tema.superficie
    border.width: 1
    border.color: Tema.linha
    Ancora { chave: "conta"; anchors.top: parent.top; width: parent.width }
    RowLayout {
      anchors.fill: parent
      anchors.margins: 24
      spacing: 20
      // Conectada: foto da conta Google (~/.face); senão, inicial ou ícone.
      Item {
        Layout.preferredWidth: 72; Layout.preferredHeight: 72
        Avatar {
          anchors.fill: parent
          visible: pg.conectado
          redondo: true
          nome: pg.conectado ? (pg.s.nome || pg.s.email || "") : ""
        }
        Rectangle {
          anchors.fill: parent
          visible: !pg.conectado
          radius: 36
          color: Tema.superficieAlta
          Glifo { anchors.centerIn: parent; g: Icones.account; tamanho: 36; color: Tema.texto2 }
        }
      }
      ColumnLayout {
        Layout.fillWidth: true
        spacing: 4
        Texto {
          text: pg.conectado ? (pg.s.nome || I18n.t("Conta Google")) : I18n.t("Nenhuma conta conectada")
          font.pixelSize: Tema.tTitulo || 20; font.weight: Font.DemiBold
        }
        Texto {
          text: pg.conectado ? (pg.s.email || I18n.t("Google Drive")) + (pg.s.cripto ? I18n.t(" · backup criptografado") : "")
                             : I18n.t("Seu sistema não está sendo salvo em nenhum lugar.")
          color: Tema.texto2
        }
        Texto {
          visible: pg.conectado
          text: pg.s && pg.s.rodando ? (pg.s.progresso || I18n.t("Sincronizando…"))
                : I18n.t("Último backup: ") + pg.quando(pg.s ? pg.s.ultima : "") + (pg.s && pg.s.arquivos ? " · " + pg.s.arquivos + " arquivos, " + pg.mb(pg.s.tamanho) : "")
          color: pg.s && pg.s.resultado === "erro" ? Tema.perigo : Tema.texto3
          font.pixelSize: Tema.tLegenda
        }
      }
      Botao {
        visible: pg.conectado
        texto: pg.s && pg.s.rodando ? I18n.t("Sincronizando…") : I18n.t("Sincronizar agora")
        glifo: Icones.sync
        tipo: "primario"
        ocupado: !!(pg.s && pg.s.rodando)
        habilitado: !pg.ocupado && !pg.precisaSenha
        onClicado: pg.sincronizar()
      }
    }
  }

  // Login em andamento: link caso o navegador não tenha aberto.
  Aviso {
    Layout.fillWidth: true
    visible: !!(pg.s && pg.s.entrando && pg.s.link_login)
    texto: I18n.t("Se o navegador não abriu, abra o login do Google por aqui.")
    acoes: Botao { texto: I18n.t("Abrir login"); onClicado: Qt.openUrlExternally(pg.s.link_login) }
  }
  // Conta com backup de outra máquina: decidir antes de enviar qualquer coisa.
  Aviso {
    Layout.fillWidth: true
    visible: !!(pg.s && pg.s.conectado && pg.s.precisa_decidir && !pg.precisaSenha)
    tipo: "aviso"
    texto: I18n.t("Esta conta já tem um backup") + (pg.s && pg.s.remoto_meta && pg.s.remoto_meta.maquina ? " de " + pg.s.remoto_meta.maquina : "") + I18n.t(". Restaure-o para trazer tudo para cá, ou substitua-o pelos arquivos deste computador.")
    acoes: [
      Botao { texto: I18n.t("Restaurar"); tipo: "primario"; habilitado: !pg.ocupado; onClicado: pg.restaurar() },
      Botao { texto: I18n.t("Substituir"); tipo: "perigo"; habilitado: !pg.ocupado; onClicado: pg.sincronizar(true) }
    ]
  }
  // Conflito de versão concorrente entre computadores
  Aviso {
    Layout.fillWidth: true
    visible: !!(pg.s && pg.s.conectado && pg.s.conflito)
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
  Aviso {
    Layout.fillWidth: true
    visible: !!(pg.s && pg.s.erro) && !(pg.s.precisa_decidir && !pg.precisaSenha)
    tipo: pg.precisaSenha ? "aviso" : "perigo"
    texto: pg.s ? pg.s.erro : ""
  }

  // ── entrar ───────────────────────────────────────────────────────────────
  // O botão do Google vem primeiro e em destaque; a criptografia é uma opção abaixo dele.
  Rectangle {
    Layout.fillWidth: true
    visible: !pg.conectado && !(pg.s && pg.s.boas_vindas)
    implicitHeight: colEntrar.implicitHeight + 56
    radius: Tema.raioGrande
    gradient: Gradient {
      orientation: Gradient.Horizontal
      GradientStop { position: 0; color: Qt.rgba(Tema.realce.r, Tema.realce.g, Tema.realce.b, 0.22) }
      GradientStop { position: 1; color: Qt.rgba(Tema.realce.r, Tema.realce.g, Tema.realce.b, 0.06) }
    }
    border.width: 1
    border.color: Qt.rgba(Tema.realce.r, Tema.realce.g, Tema.realce.b, 0.40)
    Ancora { chave: "contaEntrar"; anchors.top: parent.top; width: parent.width }
    RowLayout {
      anchors.fill: parent
      anchors.margins: 28
      spacing: 24
      Glifo { Layout.alignment: Qt.AlignTop; g: Icones.accountCircle; tamanho: 56; color: Tema.realce }
      ColumnLayout {
        id: colEntrar
        Layout.fillWidth: true
        spacing: 8
        Texto { text: I18n.t("Entre com sua conta Google"); font.pixelSize: 24; font.weight: Font.DemiBold; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Texto {
          Layout.fillWidth: true
          wrapMode: Text.WordWrap
          color: Tema.texto2
          text: I18n.t("Abre o login do Google no navegador. O app só enxerga a pasta “Simba Conta” que ele mesmo cria no seu Drive.") +
                (pg.s && !pg.s.rclone ? " " + I18n.t("Na primeira vez instala o rclone (pede a senha de administrador).") : "")
        }
        Botao {
          Layout.topMargin: 8
          texto: pg.s && pg.s.entrando ? I18n.t("Termine o login no navegador…") : I18n.t("Entrar com o Google")
          glifo: Icones.accountCircle
          tipo: "primario"
          ocupado: !!(pg.s && pg.s.entrando)
          habilitado: !pg.ocupado && (!pg.usarCripto || pg.senhaCripto.length >= 6)
          onClicado: pg.entrar()
        }
      }
    }
  }
  Secao { visible: !pg.conectado; titulo: I18n.t("Opções"); detalhe: I18n.t("Escolha antes de entrar.") }
  Cartao {
    visible: !pg.conectado
    Linha {
      chave: "contaCripto"
      glifo: Icones.shield
      titulo: I18n.t("Criptografar o backup com uma senha")
      descricao: I18n.t("Ninguém lê seus arquivos no Drive sem a senha — nem o Google. Também permite guardar chaves SSH e de API. Sem a senha não há como recuperar.")
      Interruptor { ligado: pg.usarCripto; onAlternado: function(x) { pg.usarCripto = x } }
    }
    Linha {
      visible: pg.usarCripto
      glifo: Icones.lock
      titulo: I18n.t("Senha do backup")
      descricao: pg.senhaCripto.length > 0 && pg.senhaCripto.length < 6 ? I18n.t("Use pelo menos 6 caracteres") : I18n.t("Anote num lugar seguro")
      Campo { id: campoCripto; width: 240; echoMode: TextInput.Password; dica: I18n.t("mínimo 6 caracteres"); onTextChanged: pg.senhaCripto = text }
    }
  }

  // ── senha de um backup criptografado já existente (máquina nova) ─────────
  Cartao {
    visible: pg.conectado && pg.precisaSenha
    Linha {
      glifo: Icones.lock
      titulo: I18n.t("Senha do backup")
      descricao: I18n.t("Este backup foi criptografado em outra máquina.")
      Campo { id: campoSenha; width: 200; echoMode: TextInput.Password; dica: I18n.t("senha") }
      Botao {
        texto: I18n.t("Desbloquear")
        tipo: "primario"
        onClicado: Sistema.rodar(["conta", "senha", "-"], function(o, code) {
          pg.atualizar()
          Navegacao.confirmar(code === 0 ? I18n.t("Backup desbloqueado") : I18n.t("Senha incorreta"), code === 0 ? Icones.check : Icones.alert)
        }, (function() { var t = campoSenha.text; campoSenha.text = ""; return t + "\n" })())
      }
    }
  }

  // ── o que entra no backup ────────────────────────────────────────────────
  Secao { visible: pg.conectado; titulo: I18n.t("O que é salvo"); detalhe: I18n.t("Neste computador: ") + pg.arquivosLocal + " arquivos, " + pg.mb(pg.tamanhoLocal) + I18n.t(". Caches, navegadores (fora histórico e favoritos), jogos e senhas do chaveiro ficam de fora.") }
  Ancora { chave: "contaItens" }
  Cartao {
    visible: pg.conectado
    Repeater {
      model: pg.s ? ["config", "imagens", "historico", "documentos", "pacotes", "segredos"] : []
      delegate: Linha {
        id: cat
        required property string modelData
        readonly property bool bloqueada: modelData === "segredos" && !pg.s.cripto
        glifo: ({ config: Icones.folderCog, imagens: Icones.folderOpen, historico: Icones.clockOutline,
                  documentos: Icones.folderText, pacotes: Icones.apps, segredos: Icones.lock })[modelData]
        titulo: pg.s.rotulos[modelData]
        descricao: ({ config: I18n.t("~/.config, scripts, apps e temas próprios, estado do sistema"),
                      imagens: I18n.t("Imagens e papéis de parede"),
                      historico: I18n.t("Histórico e favoritos do Brave, histórico do terminal e arquivos recentes"),
                      documentos: I18n.t("Documentos e atalhos da área de trabalho"),
                      pacotes: I18n.t("Programas do pacman, AUR e Flatpak — reinstalados na restauração"),
                      segredos: cat.bloqueada ? I18n.t("Disponível só com o backup criptografado") : I18n.t("~/.ssh e chaves do Draco") })[modelData]
        habilitado: !cat.bloqueada
        Interruptor {
          ligado: !!pg.s.categorias[cat.modelData] && !cat.bloqueada
          habilitado: !cat.bloqueada && !pg.ocupado
          onAlternado: function(x) {
            Sistema.rodar(["conta", "categoria", cat.modelData, x ? "liga" : "desliga"], function() { pg.atualizar(); pg.medir() })
          }
        }
      }
    }
  }

  // Pastas adicionais na categoria Documentos
  Cartao {
    visible: pg.conectado && !!(pg.s && pg.s.categorias && pg.s.categorias.documentos)
    Linha {
      glifo: Icones.folderPlus
      titulo: I18n.t("Pastas personalizadas em Documentos")
      descricao: I18n.t("Além de Documentos/ e Desktop/, você pode incluir outras pastas da sua pasta pessoal.")
      Campo {
        id: campoNovaPasta
        width: 180
        dica: I18n.t("Ex: Projetos")
        onAccepted: if (text.trim() !== "") {
          Sistema.rodar(["conta", "pasta", "adicionar", text.trim()], function() {
            campoNovaPasta.text = ""
            pg.atualizar()
            pg.medir()
          })
        }
      }
      Botao {
        texto: I18n.t("Adicionar")
        tipo: "fantasma"
        glifo: Icones.plus
        habilitado: campoNovaPasta.text.trim() !== "" && !pg.ocupado
        onClicado: {
          Sistema.rodar(["conta", "pasta", "adicionar", campoNovaPasta.text.trim()], function() {
            campoNovaPasta.text = ""
            pg.atualizar()
            pg.medir()
          })
        }
      }
    }
    Repeater {
      model: pg.s && pg.s.pastas_personalizadas ? pg.s.pastas_personalizadas : []
      delegate: Linha {
        glifo: Icones.folder
        titulo: modelData
        descricao: I18n.t("Pasta incluída na sincronização do Google Drive")
        Botao {
          texto: I18n.t("Remover")
          tipo: "fantasma"
          glifo: Icones.close
          habilitado: !pg.ocupado
          onClicado: Sistema.rodar(["conta", "pasta", "remover", modelData], function() { pg.atualizar(); pg.medir() })
        }
      }
    }
  }

  // ── avisos de conexão e navegador ─────────────────────────────────────────
  Aviso {
    visible: pg.conectado && !!(pg.s && pg.s.pausado)
    tipo: "aviso"
    glifo: Icones.pause
    texto: I18n.t("Modo Viagem ativado: A sincronização com o Google Drive está pausada até ") + pg.quando(pg.s ? pg.s.pausado_ate : "") + "."
    acoes: Botao {
      texto: I18n.t("Retomar agora")
      tipo: "primario"
      habilitado: !pg.ocupado
      onClicado: Sistema.rodar(["conta", "retomar"], function() { pg.atualizar(); Navegacao.confirmar(I18n.t("Sincronização retomada"), Icones.checkCircle) })
    }
  }
  Aviso {
    visible: pg.conectado && !!(pg.s && pg.s.rede_limitada)
    tipo: "aviso"
    glifo: Icones.wifi
    texto: I18n.t("Conexão limitada detectada (dados móveis/roteamento celular). O Simba OS está espaçando a sincronização automática para economizar sua franquia de dados.")
  }

  Aviso {
    visible: pg.conectado && !!(pg.s && pg.s.brave_pendente)
    tipo: "info"
    glifo: Icones.sync
    texto: I18n.t("Novos favoritos e atalhos recebidos da nuvem estão prontos para o navegador.")
    acoes: Botao {
      texto: I18n.t("Aplicar agora")
      tipo: "primario"
      habilitado: !pg.ocupado
      onClicado: Sistema.rodar(["conta", "brave"], function(o, code) {
        pg.atualizar()
        Navegacao.confirmar(code === 0 ? I18n.t("Favoritos aplicados!") : (o.trim() || I18n.t("Feche o navegador antes")), code === 0 ? Icones.checkCircle : Icones.alert)
      })
    }
  }

  // ── automático / restaurar / sair ────────────────────────────────────────
  Secao { visible: pg.conectado; titulo: I18n.t("Backup e restauração") }
  Cartao {
    visible: pg.conectado
    Linha {
      chave: "contaAuto"
      glifo: Icones.sync
      titulo: I18n.t("Sincronização dinâmica e backup automático")
      descricao: I18n.t("A cada 20 minutos: sincroniza alterações (como papel de parede) entre suas máquinas e salva o backup.")
      Interruptor {
        ligado: !!(pg.s && pg.s.auto)
        onAlternado: function(x) { Sistema.rodar(["conta", "auto", x ? "liga" : "desliga"], function() { pg.atualizar() }) }
      }
    }
    Linha {
      chave: "contaModoViagem"
      glifo: Icones.pause
      titulo: I18n.t("Modo Viagem (Pausar sincronização)")
      descricao: pg.s && pg.s.pausado && pg.s.pausado_ate
                 ? I18n.t("Sincronização temporariamente pausada até ") + pg.quando(pg.s.pausado_ate) + I18n.t(". Ideal em conexões móveis ou roteamento de celular.")
                 : I18n.t("Pausa temporariamente envios e downloads automáticos no Google Drive por 24 horas.")
      Botao {
        visible: !(pg.s && pg.s.pausado)
        texto: I18n.t("Pausar por 24h")
        tipo: "fantasma"
        glifo: Icones.pause
        habilitado: !pg.ocupado
        onClicado: Sistema.rodar(["conta", "pausar", "24"], function() { pg.atualizar(); Navegacao.confirmar(I18n.t("Sincronização pausada por 24h"), Icones.pause) })
      }
      Botao {
        visible: !!(pg.s && pg.s.pausado)
        texto: I18n.t("Retomar")
        tipo: "primario"
        glifo: Icones.sync
        habilitado: !pg.ocupado
        onClicado: Sistema.rodar(["conta", "retomar"], function() { pg.atualizar(); Navegacao.confirmar(I18n.t("Sincronização retomada"), Icones.checkCircle) })
      }
    }
    Linha {
      glifo: Icones.refresh
      titulo: I18n.t("Verificar novidades na nuvem agora")
      descricao: I18n.t("Busca se houve mudança de papel de parede, tema ou configurações feita em outro computador.")
      Botao {
        texto: I18n.t("Verificar agora")
        habilitado: !pg.ocupado && !pg.precisaSenha
        onClicado: Sistema.rodar(["conta", "puxar", "--forcar"], function(o, code) {
          pg.atualizar()
          Navegacao.confirmar(I18n.t("Verificação concluída"), Icones.checkCircle)
        })
      }
    }
    Linha {
      chave: "contaRestaurar"
      glifo: Icones.backupRestore
      titulo: I18n.t("Restaurar desta conta")
      descricao: pg.s && pg.s.remoto_meta && pg.s.remoto_meta.data
                 ? I18n.t("Backup de ") + pg.s.remoto_meta.maquina + ", " + pg.quando(pg.s.remoto_meta.data) + ". Arquivos substituídos vão para ~/.local/share/conta/antes-da-restauracao."
                 : I18n.t("Traz configurações, papéis de parede, histórico e documentos do Drive para cá.")
      Botao { visible: !pg.confirmarRestaurar; texto: I18n.t("Restaurar…"); habilitado: !pg.ocupado && !pg.precisaSenha; onClicado: pg.confirmarRestaurar = true }
      Botao { visible: pg.confirmarRestaurar; texto: I18n.t("Cancelar"); tipo: "fantasma"; onClicado: pg.confirmarRestaurar = false }
      Botao { visible: pg.confirmarRestaurar; texto: I18n.t("Substituir e restaurar"); tipo: "perigo"; onClicado: pg.restaurar() }
    }
    Linha {
      chave: "contaPacotes"
      glifo: Icones.apps
      titulo: I18n.t("Instalar programas da conta")
      descricao: I18n.t("Depois de restaurar: abre um terminal que instala os programas que faltam")
      Botao { texto: I18n.t("Instalar…"); habilitado: !pg.ocupado; onClicado: Sistema.rodar(["conta", "pacotes"], function(o, code) { if (o.trim()) Navegacao.confirmar(o.trim(), Icones.apps) }) }
    }
    Linha {
      chave: "contaSair"
      glifo: Icones.logout
      titulo: I18n.t("Sair da conta")
      descricao: I18n.t("Para de fazer backup neste computador. Os dados no Drive continuam lá.")
      Botao { visible: !pg.confirmarSair; texto: I18n.t("Sair"); habilitado: !pg.ocupado; onClicado: pg.confirmarSair = true }
      Botao { visible: pg.confirmarSair; texto: I18n.t("Cancelar"); tipo: "fantasma"; onClicado: pg.confirmarSair = false }
      Botao { visible: pg.confirmarSair; texto: I18n.t("Sair da conta"); tipo: "perigo"; onClicado: { pg.confirmarSair = false; Sistema.rodar(["conta", "sair"], function() { Navegacao.versaoFoto++; pg.atualizar() }) } }
    }
  }

  // ── dispositivos no ecossistema ──────────────────────────────────────────
  Secao {
    visible: pg.conectado && !!(pg.s && pg.s.dispositivos && pg.s.dispositivos.length > 0)
    titulo: I18n.t("Dispositivos no ecossistema")
    detalhe: I18n.t("Computadores vinculados a este Simba Conta e sincronizados via Google Drive.")
  }
  Cartao {
    visible: pg.conectado && !!(pg.s && pg.s.dispositivos && pg.s.dispositivos.length > 0)
    Repeater {
      model: pg.s && pg.s.dispositivos ? pg.s.dispositivos : []
      delegate: Linha {
        glifo: modelData.tipo === "laptop" ? Icones.laptop : Icones.monitor
        titulo: modelData.maquina + (modelData.este_dispositivo ? " (" + I18n.t("Este computador") + ")" : "")
        descricao: (modelData.este_dispositivo ? I18n.t("Último envio: ") : I18n.t("Última sincronização: ")) +
                   pg.quando(modelData.data) +
                   (modelData.tema ? " · " + I18n.t("Tema: ") + modelData.tema : "")
        Texto {
          visible: modelData.este_dispositivo
          text: I18n.t("Ativo")
          color: Tema.sucesso
          font.weight: Font.Medium
          font.pixelSize: Tema.tLegenda + 1
        }
      }
    }
  }

  // ── máquina formatada ────────────────────────────────────────────────────
  Secao { titulo: I18n.t("Numa máquina formatada"); detalhe: I18n.t("Como trazer tudo de volta depois de reinstalar o sistema.") }
  Cartao {
    Linha {
      chave: "contaBoasVindas"
      glifo: Icones.accountCircle
      titulo: I18n.t("Oferecer entrar com o Google no primeiro boot")
      descricao: I18n.t("Opcional. Nas instalações feitas pela sua ISO, Contas abre sozinha no primeiro boot com a opção de restaurar um backup (dá para pular).")
      Interruptor {
        ligado: !!(pg.s && pg.s.boas_vindas_iso)
        onAlternado: function(x) { Sistema.rodar(["conta", "boas-vindas", x ? "liga" : "desliga"], function() { pg.atualizar() }) }
      }
    }
    Linha {
      chave: "contaFormatada"
      glifo: Icones.informationOutline
      titulo: I18n.t("Restaurar num computador formatado")
      descricao: I18n.t("Instalando pela sua ISO (Gerar ISO), esta tela abre sozinha no primeiro boot. Com o Simba original (sem a sua ISO): baixe “Restaurar-Simba.sh” da pasta “Simba Conta” no Drive e rode no terminal: bash ~/Downloads/Restaurar-Simba.sh")
      Botao { texto: I18n.t("Abrir o Drive"); onClicado: Qt.openUrlExternally("https://drive.google.com/drive/search?q=%22Simba%20Conta%22") }
    }
  }
}
