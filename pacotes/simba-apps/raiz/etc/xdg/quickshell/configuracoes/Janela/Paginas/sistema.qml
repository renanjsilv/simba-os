import QtQuick
import QtQuick.Layouts
import Quickshell
import Quickshell.Io
import qs.Comum
import qs.Janela

Pagina {
  id: pg
  titulo: I18n.t("Sistema")
  subtitulo: I18n.t("Sobre este computador, atualizações, idioma e hora.")

  property var s: null
  property string atualizacoes: ""
  property bool verificando: false
  property string fuso: ""
  property bool confirmarShell: false
  Component.onCompleted: {
    Sistema.json([Sistema.ajudante, "sobre"], function(v) { if (v) pg.s = v })
    Sistema.sh("timedatectl show -p Timezone --value", function(o) { pg.fuso = o.trim() })
  }

  function gb(b) { return (b / 1073741824).toFixed(b > 107374182400 ? 0 : 1).replace(".", I18n.decimal) + " GB" }
  function duracao(sg) {
    var d = Math.floor(sg / 86400), h = Math.floor((sg % 86400) / 3600), m = Math.floor((sg % 3600) / 60)
    return (d ? d + (d === 1 ? " dia, " : " dias, ") : "") + (h ? h + " h " : "") + m + " min"
  }

  // ── hero ─────────────────────────────────────────────────────────────────
  Rectangle {
    Layout.fillWidth: true
    Layout.preferredHeight: 168
    radius: Tema.raioGrande
    color: Tema.superficie
    border.width: 1
    border.color: Tema.linha
    Ancora { chave: "sobre"; anchors.top: parent.top; width: parent.width }
    RowLayout {
      anchors.fill: parent
      anchors.margins: 24
      spacing: 24
      // laptop drawing with the wallpaper on it
      Item {
        Layout.preferredWidth: 170
        Layout.preferredHeight: 110
        Rectangle {
          id: tampa
          x: 12; width: 146; height: 92
          radius: Tema.raio + 2
          color: Tema.superficieMax
          border.width: 1
          border.color: Tema.linhaForte
          clip: true
          Image { anchors.fill: parent; anchors.margins: 5; source: "file://" + Tema.estadoSimba + "/background"; fillMode: Image.PreserveAspectCrop; sourceSize.width: 300; asynchronous: true; cache: false }
        }
        Rectangle { y: 94; width: 170; height: 8; radius: 4; color: Tema.texto3 }
      }
      ColumnLayout {
        Layout.fillWidth: true
        spacing: 3
        Texto { text: pg.s ? (pg.s.fabricante + " " + pg.s.modelo).trim() || pg.s.host : ""; font.pixelSize: Tema.tTitulao; font.weight: Font.Bold; elide: Text.ElideRight; Layout.fillWidth: true }
        Texto { text: pg.s ? I18n.t("Nome na rede: ") + pg.s.host : ""; color: Tema.texto2 }
        Texto { text: pg.s ? String(pg.s.os) + " " + pg.s.simba.replace(/-\d+$/, "") + " · " + pg.s.sessao + I18n.t(" · Linux ") + pg.s.kernel : ""; color: Tema.texto3; font.pixelSize: Tema.tLegenda + 1; elide: Text.ElideRight; Layout.fillWidth: true }
        Texto { text: pg.s ? I18n.t("Ligado há ") + pg.duracao(pg.s.uptime) : ""; color: Tema.texto3; font.pixelSize: Tema.tLegenda + 1 }
      }
    }
  }

  component Espec: Rectangle {
    property string glifo: ""
    property string rotulo: ""
    property string valor: ""
    property string detalhe: ""
    property real uso: -1
    Layout.fillWidth: true
    Layout.preferredHeight: 104
    radius: Tema.raioGrande
    color: Tema.superficie
    border.width: 1
    border.color: Tema.linha
    ColumnLayout {
      anchors.fill: parent
      anchors.margins: 14
      spacing: 3
      RowLayout { spacing: 8; Glifo { g: parent.parent.parent.glifo; tamanho: 15; color: Tema.texto2 } Texto { text: parent.parent.parent.rotulo; color: Tema.texto2; font.pixelSize: Tema.tLegenda + 1 } }
      Item { Layout.fillHeight: true }
      Texto { text: parent.parent.valor; font.weight: Font.DemiBold; elide: Text.ElideRight; Layout.fillWidth: true }
      Texto { text: parent.parent.detalhe; color: Tema.texto3; font.pixelSize: Tema.tLegenda; elide: Text.ElideRight; Layout.fillWidth: true; visible: text !== "" }
      Rectangle {
        visible: parent.parent.uso >= 0
        Layout.fillWidth: true; Layout.preferredHeight: 4; radius: 2; color: Tema.superficieMax
        Rectangle { width: parent.width * Math.max(0, Math.min(1, parent.parent.parent.uso)); height: 4; radius: 2; color: Tema.realce; Behavior on width { NumberAnimation { duration: 900; easing.type: Easing.OutCubic } } }
      }
    }
  }

  GridLayout {
    Layout.fillWidth: true
    Layout.topMargin: 4
    columns: width > 720 ? 4 : 2
    columnSpacing: 10
    rowSpacing: 10
    Espec { glifo: Icones.chip; rotulo: I18n.t("Processador"); valor: pg.s ? pg.s.cpu : ""; detalhe: pg.s ? pg.s.nucleos + I18n.t(" núcleos") : "" }
    Espec { glifo: Icones.memory; rotulo: I18n.t("Memória"); valor: pg.s ? pg.gb(pg.s.memTotal) : ""; detalhe: pg.s ? pg.gb(pg.s.memTotal - pg.s.memLivre) + I18n.t(" em uso") : ""; uso: pg.s ? 1 - pg.s.memLivre / pg.s.memTotal : -1 }
    Espec { glifo: Icones.harddisk; rotulo: I18n.t("Disco"); valor: pg.s ? pg.gb(pg.s.discoTotal) : ""; detalhe: pg.s ? pg.gb(pg.s.discoLivre) + " livres" : ""; uso: pg.s ? 1 - pg.s.discoLivre / pg.s.discoTotal : -1 }
    Espec { glifo: Icones.expansionCard; rotulo: I18n.t("Vídeo"); valor: pg.s && pg.s.gpu.length ? pg.s.gpu[0] : ""; detalhe: pg.s && pg.s.gpu.length > 1 ? "+ " + pg.s.gpu[1] : "" }
  }

  Cartao {
    Layout.topMargin: 6
    Linha {
      glifo: Icones.informationOutline
      titulo: I18n.t("Ficha completa (fastfetch)")
      Botao { texto: I18n.t("Abrir"); onClicado: Sistema.solto(["simba-launch-about"]) }
    }
  }

  property var atu: null
  function textoAtualizacoes(v) {
    if (!v || v.quando === undefined) return I18n.t("Sistema, apps da Loja, Escritório (Craft) e firmware, num clique")
    if (!v.total) return I18n.t("Tudo em dia · sistema, Loja e Escritório")
    var p = []
    if (v.sistema + v.aur) p.push((v.sistema + v.aur) + I18n.t(" do sistema"))
    if (v.loja) p.push(v.loja + I18n.t(" da Loja"))
    if (v.craft) p.push(v.craft + I18n.t(" do Escritório"))
    if (v.firmware) p.push(v.firmware + I18n.t(" de firmware"))
    return v.total + (v.total === 1 ? I18n.t(" atualização: ") : I18n.t(" atualizações: ")) + p.join(" · ")
  }
  Secao { titulo: I18n.t("Atualizações") }
  Cartao {
    Linha {
      chave: "atualizar"; glifo: Icones.update
      titulo: I18n.t("Atualizar tudo")
      descricao: pg.verificando ? I18n.t("Procurando atualizações…") : pg.textoAtualizacoes(pg.atu)
      Component.onCompleted: Sistema.json(["simba-atualizar", "estado"], function(v) { if (v) pg.atu = v })
      Botao {
        texto: I18n.t("Verificar")
        ocupado: pg.verificando
        onClicado: {
          pg.verificando = true
          Sistema.json(["simba-atualizar", "verificar"], function(v) { pg.verificando = false; if (v) pg.atu = v; if (v && !v.total) pg.nov = null })
        }
      }
      Botao { texto: I18n.t("Atualizar tudo"); tipo: "primario"; onClicado: Sistema.solto(["simba-atualizar", "aplicar"]) }
    }
  }

  // ── changelog do que está para atualizar (simba-novidades) ───────────────
  property var nov: null
  readonly property var novItens: nov && nov.itens ? nov.itens : []
  function rotuloOrigem(o) {
    return { sistema: I18n.t("Arch"), aur: "AUR", loja: I18n.t("Loja"), craft: I18n.t("Escritório"), firmware: I18n.t("Firmware") }[o] || o
  }
  function glifoOrigem(o) {
    return { sistema: Icones.update, aur: Icones.zipBox, loja: Icones.apps, craft: Icones.fileDocument, firmware: Icones.chip }[o] || Icones.update
  }
  function versao(v) { return String(v || "").replace(/^\d+:/, "") }
  Secao {
    titulo: I18n.t("O que vai ser atualizado")
    visible: pg.novItens.length > 0
    detalhe: pg.nov && pg.nov.githubLimitado ? I18n.t("O GitHub limitou as consultas agora; algumas notas aparecem só com o link.") : I18n.t("Clique num item para ver as novidades da versão.")
  }
  Cartao {
    visible: pg.novItens.length > 0
    FileView {
      path: Sistema.home + "/.cache/simba/novidades.json"
      watchChanges: true
      printErrors: false
      onFileChanged: reload()
      onLoaded: { try { pg.nov = JSON.parse(text()) } catch (e) { } }
    }
    Repeater {
      model: pg.novItens
      delegate: Linha {
        id: item
        required property var modelData
        property bool verOriginal: false
        glifo: pg.glifoOrigem(modelData.origem)
        titulo: modelData.nome
        descricao: (modelData.ignorada ? I18n.t("Ignorada") + " · " : "") + (modelData.de ? pg.versao(modelData.de) + " → " : "") + pg.versao(modelData.para) + " · " + pg.rotuloOrigem(modelData.origem)
                   + (modelData.descricao ? " · " + modelData.descricao : "")
        navegavel: true
        onClicado: expandido = !expandido
        extra: [
          Text {
            Layout.fillWidth: true
            Layout.leftMargin: 48
            text: item.expandido ? ((item.verOriginal && item.modelData.original ? item.modelData.original : item.modelData.notas) || I18n.t("Sem notas.")) : ""
            textFormat: Text.MarkdownText
            wrapMode: Text.Wrap
            color: Tema.texto2
            linkColor: Tema.realce
            font.family: Tema.fonte
            font.pixelSize: Tema.tCorpo
            onLinkActivated: function(l) { Qt.openUrlExternally(l) }
            HoverHandler { cursorShape: parent.hoveredLink ? Qt.PointingHandCursor : Qt.ArrowCursor }
          },
          RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 48
            Layout.bottomMargin: 4
            Texto {
              text: I18n.t("Fonte: ") + (item.modelData.fonte || "") + (item.modelData.original ? (item.verOriginal ? I18n.t(" · texto original") : I18n.t(" · traduzido automaticamente")) : "")
              color: Tema.texto3; font.pixelSize: Tema.tLegenda; Layout.fillWidth: true; elide: Text.ElideRight
            }
            Botao {
              visible: !!item.modelData.ignoravel
              texto: item.modelData.ignorada ? I18n.t("Voltar a atualizar") : I18n.t("Ignorar esta versão")
              onClicado: Sistema.rodar(item.modelData.ignorada ? ["simba-atualizar", "designorar", item.modelData.nome]
                                                               : ["simba-atualizar", "ignorar", item.modelData.nome, item.modelData.para],
                                       function() { Sistema.solto(["/usr/bin/simba-novidades"]); Sistema.json(["simba-atualizar", "estado"], function(v) { if (v) pg.atu = v }) })
            }
            Botao { visible: !!item.modelData.original; texto: item.verOriginal ? I18n.t("Ver em português") : I18n.t("Ver original"); onClicado: item.verOriginal = !item.verOriginal }
            Botao { visible: !!item.modelData.link; texto: I18n.t("Abrir no navegador"); onClicado: Qt.openUrlExternally(item.modelData.link) }
          }
        ]
      }
    }
  }

  Secao { titulo: I18n.t("Região") }
  Cartao {
    Linha {
      chave: "idioma"; glifo: Icones.translate
      titulo: I18n.t("Idioma do sistema")
      descricao: pg.s ? (pg.s.idioma.indexOf("pt_BR") === 0 ? I18n.t("Português (Brasil)") : pg.s.idioma) + I18n.t(" · troca pela tradução simba-idioma (pede a senha, vale após entrar de novo)") : ""
      Selecao {
        width: 200
        opcoes: [{ valor: "pt_BR", rotulo: I18n.t("Português (Brasil)") }, { valor: "en_US", rotulo: I18n.t("English (US)") }]
        atual: pg.s && pg.s.idioma.indexOf("pt_BR") === 0 ? "pt_BR" : "en_US"
        onEscolhido: function(x) { Sistema.solto(["simba-launch-floating-terminal-with-presentation", "sudo simba-idioma " + x]) }
      }
    }
    Linha {
      chave: "fuso"; glifo: Icones.earth
      titulo: I18n.t("Fuso horário")
      descricao: pg.fuso + I18n.t(" · agora ") + Qt.formatTime(new Date(), "HH:mm")
      Botao { texto: I18n.t("Mudar…"); onClicado: Sistema.solto(["simba-menu-timezone"]) }
    }
  }

  Secao { titulo: I18n.t("Manutenção") }
  Cartao {
    // ── liberar espaço (simba-limpar) ─────────────────────────────────────
    Linha {
      id: limpeza
      chave: "limpar"; glifo: Icones.broom
      titulo: I18n.t("Liberar espaço")
      property var cats: []
      property bool ocupado: false
      readonly property real total: { var t = 0; for (var i = 0; i < cats.length; i++) if (cats[i].pode) t += cats[i].bytes; return t }
      descricao: ocupado ? I18n.t("Calculando…") : cats.length ? I18n.f("%1 podem ser liberados · caches de apps, AUR e programação", pg.gb(total))
                 : I18n.t("Caches de apps, AUR e programação, lixeira e pacotes antigos")
      navegavel: true
      function analisar() {
        ocupado = true
        Sistema.json(["simba-limpar", "analisar"], function(v) { limpeza.ocupado = false; if (v) limpeza.cats = v })
      }
      function limpar(ids) {
        ocupado = true
        Sistema.json(["simba-limpar", "limpar"].concat(ids), function(v) {
          if (v) Sistema.notificar(v.erros.length ? v.erros.join(" · ") : I18n.f("%1 liberados", pg.gb(v.liberado)), Icones.broom)
          limpeza.analisar()
        })
      }
      onClicado: { expandido = !expandido; if (expandido) analisar() }
      Botao {
        texto: I18n.t("Limpar caches"); tipo: "primario"; ocupado: limpeza.ocupado
        onClicado: limpeza.limpar(["seguro"])
      }
      extra: Repeater {
        model: limpeza.cats
        delegate: RowLayout {
          required property var modelData
          Layout.fillWidth: true
          Layout.leftMargin: 48
          ColumnLayout {
            Layout.fillWidth: true
            spacing: 1
            Texto { text: modelData.nome; font.weight: Font.Medium }
            Texto { text: modelData.motivo || modelData.detalhe; color: modelData.motivo ? Tema.perigo : Tema.texto3; font.pixelSize: Tema.tLegenda; wrapMode: Text.WordWrap; Layout.fillWidth: true }
          }
          Texto { text: modelData.bytes > 0 ? pg.gb(modelData.bytes) : "—"; color: Tema.texto2 }
          Botao { texto: I18n.t("Limpar"); compacto: true; habilitado: modelData.pode && !limpeza.ocupado; onClicado: limpeza.limpar([modelData.id]) }
        }
      }
    }
    Linha {
      chave: "reiniciarShell"; glifo: Icones.restart
      titulo: I18n.t("Reiniciar a barra e as notificações")
      descricao: pg.confirmarShell ? I18n.t("Clique de novo para confirmar") : I18n.t("Se a barra travar ou sumir (simba-shell)")
      Botao {
        texto: pg.confirmarShell ? I18n.t("Confirmar") : I18n.t("Reiniciar")
        tipo: pg.confirmarShell ? "perigo" : "normal"
        onClicado: {
          if (!pg.confirmarShell) { pg.confirmarShell = true; voltar.restart(); return }
          pg.confirmarShell = false
          Sistema.solto(["simba-restart-shell"])
        }
      }
      Timer { id: voltar; interval: 4000; onTriggered: pg.confirmarShell = false }
    }
    Linha {
      glifo: Icones.folderCog
      titulo: I18n.t("Pasta de configuração do Hyprland")
      descricao: "~/.config/hypr"
      Botao { texto: I18n.t("Abrir"); onClicado: Sistema.solto(["xdg-open", Sistema.home + "/.config/hypr"]) }
    }
  }

  Secao { titulo: I18n.t("Sobre o app Configurações") }
  Cartao {
    Linha {
      chave: "sobreApp"; glifo: Icones.cog
      titulo: I18n.t("Configurações")
      descricao: I18n.t("Feito em Quickshell, com as cores e a fonte do tema atual. Código em /etc/xdg/quickshell/configuracoes · preferências em ~/.config/configuracoes · Super+P, clique direito na área de trabalho e esta janela rodam no mesmo processo.")
      Botao { texto: I18n.t("Pasta"); onClicado: Sistema.solto(["xdg-open", Quickshell.shellDir]) }
    }
  }
}
