import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.Comum
import qs.Janela

// Restauração do sistema: pontos de restauração (snapper, config root) e o caminho
// para voltar a um deles. Restaurar de verdade é do limine-snapper-sync: o PC liga
// no ponto escolhido pelo menu de inicialização e, já dentro dele, a notificação
// "Restaurar agora" torna aquele estado o sistema normal.
Pagina {
  id: pg
  titulo: I18n.t("Restauração do sistema")
  subtitulo: I18n.t("Pontos de restauração guardam o sistema e os aplicativos como estavam. Se algo parar de funcionar depois de uma atualização ou instalação, volte para um deles. Seus arquivos pessoais não são afetados.")

  readonly property string bin: Sistema.bin + "/restauracao"
  property var s: null
  property bool criando: false
  property int apagarConfirma: -1
  property bool reiniciarConfirma: false

  function atualizar() { Sistema.json([bin, "estado"], function(v) { if (v) pg.s = v }) }
  function data(t) {
    var d = new Date(String(t).replace(" ", "T"))
    if (isNaN(d.getTime())) return String(t)
    return d.toLocaleDateString(Qt.locale(), I18n.t("dddd, d 'de' MMMM")) + I18n.t(" às ") + d.toLocaleTimeString(Qt.locale(), "HH:mm")
  }
  function admin(args, depois) {
    Sistema.rodar(["/usr/bin/simba-sistema"].concat(args), function(o, code) { pg.atualizar(); if (depois) depois(code) })
  }

  Component.onCompleted: atualizar()
  Timer { interval: 10000; running: true; repeat: true; onTriggered: pg.atualizar() }
  Timer { id: desarmar; interval: 5000; onTriggered: { pg.apagarConfirma = -1; pg.reiniciarConfirma = false } }

  Aviso {
    visible: pg.s !== null && !pg.s.permitido
    tipo: "aviso"
    texto: I18n.t("Os pontos de restauração ainda não foram liberados para este usuário. Rode o instalador do Simba OS (usuario-comum.sh) uma vez.")
  }

  Cartao {
    Linha {
      chave: "pontoCriar"; glifo: Icones.plusCircle
      titulo: I18n.t("Criar um ponto de restauração agora")
      descricao: I18n.t("Bom antes de instalar algo novo ou mexer em configurações do sistema")
      Botao {
        texto: I18n.t("Criar ponto"); tipo: "primario"; ocupado: pg.criando
        habilitado: !!(pg.s && pg.s.permitido)
        onClicado: {
          pg.criando = true
          Sistema.rodar([pg.bin, "criar"], function(o, code) {
            pg.criando = false; pg.atualizar()
            Navegacao.confirmar(code === 0 ? I18n.t("Ponto de restauração criado") : I18n.t("Não foi possível criar o ponto"), Icones.backupRestore)
          })
        }
      }
    }
    Linha {
      chave: "pontosAuto"; glifo: Icones.clockOutline
      titulo: I18n.t("Criar pontos automaticamente")
      descricao: I18n.t("Um por dia (guarda os 5 últimos dias e 2 semanas) · antes de cada atualização sempre é criado um · pede a senha")
      Interruptor {
        ligado: !!(pg.s && pg.s.automatico)
        onAlternado: function(x) { pg.admin(["pontos-automaticos", x ? "liga" : "desliga"]) }
      }
    }
  }

  Secao { titulo: I18n.t("Voltar para um ponto"); detalhe: I18n.t("Como funciona: o computador reinicia e mostra o menu de inicialização. Abra “Snapshots”, escolha a data e, quando o sistema abrir, clique em “Restaurar agora” na notificação.") }
  Cartao {
    Linha {
      chave: "restaurar"; glifo: Icones.backupRestore
      titulo: pg.s && pg.s.menuProxima ? I18n.t("O menu vai aparecer na próxima inicialização") : I18n.t("Reiniciar e escolher um ponto")
      descricao: pg.s && pg.s.menuProxima ? I18n.t("Já está tudo pronto: reinicie quando quiser") : I18n.t("Pede a senha de administrador · salve o que estiver aberto antes")
      Botao {
        visible: !!(pg.s && pg.s.menuProxima)
        texto: I18n.t("Cancelar"); tipo: "fantasma"
        onClicado: pg.admin(["menu-volta"])
      }
      Botao {
        texto: pg.reiniciarConfirma ? I18n.t("Reiniciar agora?") : I18n.t("Reiniciar e escolher")
        tipo: pg.reiniciarConfirma ? "perigo" : "normal"
        onClicado: {
          if (!pg.reiniciarConfirma) { pg.reiniciarConfirma = true; desarmar.restart(); return }
          pg.reiniciarConfirma = false
          pg.admin(["menu-restauracao"], function(code) { if (code === 0) Sistema.solto(["systemctl", "reboot"]) })
        }
      }
    }
  }

  Secao {
    titulo: I18n.t("Pontos guardados")
    detalhe: pg.s && pg.s.permitido && pg.s.pontos.length === 0 ? I18n.t("Nenhum ponto ainda — crie o primeiro acima.") : ""
  }
  Cartao {
    visible: !!(pg.s && pg.s.pontos.length)
    Repeater {
      model: pg.s ? pg.s.pontos : []
      delegate: Linha {
        id: lin
        required property var modelData
        glifo: lin.modelData.tipo === "timeline" ? Icones.clockOutline : Icones.history
        titulo: pg.data(lin.modelData.data)
        descricao: lin.modelData.descricao + " · nº " + lin.modelData.numero
        Botao {
          compacto: true
          tipo: pg.apagarConfirma === lin.modelData.numero ? "perigo" : "fantasma"
          texto: pg.apagarConfirma === lin.modelData.numero ? I18n.t("Apagar?") : I18n.t("Apagar")
          onClicado: {
            if (pg.apagarConfirma !== lin.modelData.numero) { pg.apagarConfirma = lin.modelData.numero; desarmar.restart(); return }
            pg.apagarConfirma = -1
            Sistema.rodar([pg.bin, "apagar", String(lin.modelData.numero)], function() { pg.atualizar() })
          }
        }
      }
    }
  }
}
