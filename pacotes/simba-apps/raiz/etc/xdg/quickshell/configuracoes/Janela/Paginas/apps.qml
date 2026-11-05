import QtQuick
import QtQuick.Layouts
import qs.Comum
import qs.Janela

Pagina {
  id: pg
  titulo: I18n.t("Aplicativos padrão")
  subtitulo: I18n.t("O que abre com os atalhos do sistema (Super+Enter, Super+Shift+B…) e com links e arquivos.")

  property var p: null
  function carregar() { Sistema.json([Sistema.ajudante, "padroes"], function(v) { if (v) pg.p = v }) }
  Component.onCompleted: carregar()
  function definir(cmd, valor, rotulo) {
    Sistema.rodar([cmd, valor], function(o, code) {
      pg.carregar()
      Navegacao.confirmar(code === 0 ? rotulo + " definido" : I18n.t("Não deu certo"), code === 0 ? Icones.checkboxMarkedCircle : Icones.alert)
    })
  }

  Cartao {
    Linha {
      chave: "navegador"; glifo: Icones.web
      titulo: I18n.t("Navegador")
      descricao: I18n.t("Links, Super+Shift+B e os web apps")
      Selecao { width: 220; opcoes: pg.p ? pg.p.navegador.opcoes : []; atual: pg.p ? pg.p.navegador.atual : ""; onEscolhido: function(x) { pg.definir("simba-default-browser", x, I18n.t("Navegador")) } }
    }
    Linha {
      chave: "terminal"; glifo: Icones.terminal
      titulo: I18n.t("Terminal")
      descricao: I18n.t("Super+Enter e os apps de terminal")
      Selecao { width: 220; opcoes: pg.p ? pg.p.terminal.opcoes : []; atual: pg.p ? pg.p.terminal.atual : ""; onEscolhido: function(x) { pg.definir("simba-default-terminal", x, I18n.t("Terminal")) } }
    }
    Linha {
      chave: "editor"; glifo: Icones.fileDocumentEdit
      titulo: I18n.t("Editor")
      descricao: I18n.t("Arquivos de texto e de configuração")
      Selecao { width: 220; opcoes: pg.p ? pg.p.editor.opcoes : []; atual: pg.p ? pg.p.editor.atual : ""; onEscolhido: function(x) { pg.definir("simba-default-editor", x, I18n.t("Editor")) } }
    }
    Linha {
      chave: "agente"; glifo: Icones.robot
      titulo: I18n.t("Agente de IA")
      descricao: I18n.t("O assistente que o sistema abre com Super+Shift+Ctrl+A")
      Selecao { width: 220; opcoes: pg.p ? pg.p.agente.opcoes : []; atual: pg.p ? pg.p.agente.atual : ""; onEscolhido: function(x) { pg.definir("simba-default-agent", x, I18n.t("Agente")) } }
    }
  }

  Secao { titulo: I18n.t("Tipos de arquivo") }
  Cartao {
    Linha {
      glifo: Icones.folderCog
      titulo: I18n.t("Escolher o app de um tipo de arquivo")
      descricao: I18n.t("No Arquivos (Nautilus): clique direito no arquivo › Abrir com outro aplicativo › marque “Sempre usar”.")
      Botao { texto: I18n.t("Abrir Arquivos"); onClicado: Sistema.solto(["uwsm-app", "--", "nautilus", "--new-window"]) }
    }
  }
}
