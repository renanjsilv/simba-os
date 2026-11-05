import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.Comum
import qs.Janela

// Impressoras e scanners: lista do CUPS (bin/impressoras), impressora padrão,
// página de teste e fila; adicionar/remover fica com o system-config-printer.
Pagina {
  id: pg
  titulo: I18n.t("Impressoras e scanners")
  subtitulo: I18n.t("Impressoras na rede e por USB costumam ser encontradas sozinhas. Se a sua não aparecer, use “Adicionar impressora”.")

  readonly property string bin: Sistema.bin + "/impressoras"
  property var s: null

  function atualizar() { Sistema.json([bin, "estado"], function(v) { if (v) pg.s = v }) }
  function nomeEstado(e) {
    return ({ idle: I18n.t("Pronta"), printing: I18n.t("Imprimindo"), disabled: I18n.t("Pausada"), stopped: I18n.t("Parada") })[e] || e
  }

  Component.onCompleted: atualizar()
  Timer { interval: 6000; running: true; repeat: true; onTriggered: pg.atualizar() }

  Aviso {
    visible: pg.s !== null && !pg.s.cups
    tipo: "aviso"
    texto: I18n.t("O serviço de impressão (CUPS) está desligado. Rode o instalador do Simba OS (usuario-comum.sh) para ligá-lo.")
  }

  Cartao {
    Linha {
      chave: "adicionarImpressora"; glifo: Icones.plusCircle
      titulo: I18n.t("Adicionar impressora")
      descricao: I18n.t("Procura impressoras na rede e no USB · pede a senha de administrador")
      Botao { texto: I18n.t("Adicionar"); tipo: "primario"; onClicado: Sistema.solto(["system-config-printer"]) }
    }
    Linha {
      chave: "digitalizar"; glifo: Icones.scanner
      titulo: I18n.t("Digitalizar documento")
      descricao: pg.s && pg.s.scanner ? I18n.t("Abre o Digitalizador de Documentos") : I18n.t("Instale o Digitalizador com o instalador do Simba OS")
      Botao { texto: I18n.t("Digitalizar"); habilitado: !!(pg.s && pg.s.scanner); onClicado: Sistema.solto(["simple-scan"]) }
    }
  }

  Secao {
    titulo: I18n.t("Impressoras")
    detalhe: pg.s && pg.s.impressoras.length === 0 ? I18n.t("Nenhuma impressora configurada ainda.") : ""
  }
  Cartao {
    visible: !!(pg.s && pg.s.impressoras.length)
    Repeater {
      model: pg.s ? pg.s.impressoras : []
      delegate: Linha {
        id: lin
        required property var modelData
        glifo: Icones.printer
        titulo: lin.modelData.descricao + (lin.modelData.padrao ? I18n.t("  · padrão") : "")
        descricao: pg.nomeEstado(lin.modelData.estado)
        Botao {
          visible: !lin.modelData.padrao
          compacto: true; tipo: "fantasma"; texto: I18n.t("Tornar padrão")
          onClicado: Sistema.rodar([pg.bin, "padrao", lin.modelData.nome], function(o, code) {
            pg.atualizar(); if (code === 0) Navegacao.confirmar(I18n.t("Impressora padrão: ") + lin.modelData.descricao, Icones.printer)
          })
        }
        Botao {
          compacto: true; texto: I18n.t("Página de teste")
          onClicado: Sistema.rodar([pg.bin, "teste", lin.modelData.nome], function(o, code) {
            Navegacao.confirmar(code === 0 ? I18n.t("Página de teste enviada") : I18n.t("Não foi possível imprimir"), Icones.printer)
          })
        }
        Botao {
          compacto: true; tipo: "fantasma"; texto: I18n.t("Fila")
          onClicado: Sistema.solto(["system-config-printer", "--show-jobs", lin.modelData.nome])
        }
      }
    }
  }

  Secao { titulo: I18n.t("Mais") }
  Cartao {
    Linha {
      chave: "gerenciarImpressoras"; glifo: Icones.cog
      titulo: I18n.t("Gerenciar impressoras")
      descricao: I18n.t("Remover, renomear, compartilhar e opções avançadas")
      Botao { texto: I18n.t("Abrir"); onClicado: Sistema.solto(["system-config-printer"]) }
    }
  }
}
