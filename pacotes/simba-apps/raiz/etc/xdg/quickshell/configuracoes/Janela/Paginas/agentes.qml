import QtQuick
import QtQuick.Layouts
import Quickshell
import qs.Comum
import qs.Janela

// Agentes de IA em sequência (/usr/bin/agentes): a ordem de uso, quais estão
// ligados, o login de cada um e a troca automática quando o limite acaba.
Pagina {
  id: pg
  titulo: I18n.t("Agentes de IA")
  subtitulo: I18n.t("Use vários agentes em sequência: quando o limite de um acaba, o próximo continua o trabalho com o contexto, sem você reconfigurar nada.")

  readonly property string bin: "/usr/bin/agentes"
  property var s: null
  readonly property var instalados: s ? s.agentes.filter(function(a) { return a.instalado }) : []
  readonly property var disponiveis: s ? s.agentes.filter(function(a) { return !a.instalado && a.instalavel }) : []
  readonly property bool instalandoAlgum: s ? s.agentes.some(function(a) { return a.instalando }) : false
  property var instalandoLocal: ({})

  function atualizar() {
    Sistema.json([bin, "estado"], function(v) {
      if (v) {
        pg.s = v
        var m = Object.assign({}, pg.instalandoLocal)
        var mudou = false
        for (var i = 0; i < v.agentes.length; i++) {
          var ag = v.agentes[i]
          if (m[ag.id] && (ag.instalado || !ag.instalando)) {
            delete m[ag.id]
            mudou = true
          }
        }
        if (mudou) pg.instalandoLocal = m
      }
    })
  }
  function rodar(args) { Sistema.rodar([bin].concat(args), function() { pg.atualizar() }) }
  function mover(id, d) {
    var ids = instalados.map(function(a) { return a.id })
    var i = ids.indexOf(id), j = i + d
    if (i < 0 || j < 0 || j >= ids.length) return
    ids[i] = ids[j]; ids[j] = id
    rodar(["ordem"].concat(ids))
  }
  function pct(x) { return Math.round((x || 0) * 100) + "%" }
  function descricao(a) {
    if (a.conectado === false) return I18n.t("Sem conta conectada — clique em Entrar")
    var p = []
    if (a.esgotadoTexto) p.push(I18n.t("Sem limite até ") + a.esgotadoTexto)
    if (a.uso && a.uso.sessao !== undefined) p.push(I18n.t("Sessão ") + pct(a.uso.sessao))
    if (a.uso && a.uso.semana !== undefined) p.push(I18n.t("Semana ") + pct(a.uso.semana))
    if (a.conectado === null) p.push(I18n.t("Login não verificável — ligue só se já entrou nele"))
    return p.length ? p.join(" · ") : I18n.t("Conectado")
  }
  function instalar(id) {
    var m = Object.assign({}, pg.instalandoLocal)
    m[id] = true
    pg.instalandoLocal = m
    Sistema.solto([pg.bin, "instalar", id])
    pg.atualizar()
  }

  Component.onCompleted: atualizar()
  Timer {
    interval: (pg.instalandoAlgum || Object.keys(pg.instalandoLocal).length > 0) ? 1500 : 5000
    running: true
    repeat: true
    onTriggered: pg.atualizar()
  }

  Cartao {
    Linha {
      chave: "agentesAbrir"
      glifo: Icones.robot
      titulo: I18n.t("Abrir o agente")
      descricao: I18n.t("Super+Shift+Ctrl+A ou “Agentes de IA” na barra · começa pelo primeiro ligado que ainda tem limite")
      Botao { texto: I18n.t("Abrir"); tipo: "primario"; onClicado: Sistema.solto([pg.bin, "abrir"]) }
    }
  }

  Secao { titulo: I18n.t("Ordem de uso"); detalhe: I18n.t("Quando o limite de um acaba, passa para o próximo ligado. Para trocar, o agente precisa estar com a conta conectada.") }
  Ancora { chave: "agentesOrdem" }
  Cartao {
    Repeater {
      model: pg.instalados
      delegate: Linha {
        id: lin
        required property var modelData
        required property int index
        glifo: Icones.robot
        titulo: (lin.index + 1) + ". " + lin.modelData.nome
        descricao: pg.descricao(lin.modelData)
        Botao { compacto: true; tipo: "fantasma"; glifo: Icones.chevronUp; habilitado: lin.index > 0; onClicado: pg.mover(lin.modelData.id, -1) }
        Botao { compacto: true; tipo: "fantasma"; glifo: Icones.chevronDown; habilitado: lin.index < pg.instalados.length - 1; onClicado: pg.mover(lin.modelData.id, 1) }
        Botao { visible: lin.modelData.conectado !== true; texto: I18n.t("Entrar"); onClicado: pg.rodar(["entrar", lin.modelData.id]) }
        Interruptor {
          ligado: lin.modelData.ativo
          onAlternado: function(x) { pg.rodar(["ativar", lin.modelData.id, x ? "1" : "0"]) }
        }
        Botao {
          compacto: true
          tipo: "fantasma"
          glifo: Icones.deleteOutline
          visible: lin.modelData.instalavel
          onClicado: pg.rodar(["remover", lin.modelData.id])
        }
      }
    }
  }

  Secao {
    visible: pg.disponiveis.length > 0
    titulo: I18n.t("Instalar outros agentes")
    detalhe: I18n.t("Baixe com um clique, sem precisar de comandos no terminal.")
  }
  Cartao {
    visible: pg.disponiveis.length > 0
    Repeater {
      model: pg.disponiveis
      delegate: Linha {
        id: dispLin
        required property var modelData
        readonly property bool emAndamento: dispLin.modelData.instalando || !!pg.instalandoLocal[dispLin.modelData.id]
        glifo: Icones.robot
        titulo: dispLin.modelData.nome
        descricao: dispLin.modelData.sobre || I18n.t("Disponível para instalar")
        Botao {
          texto: dispLin.emAndamento ? I18n.t("Instalando…") : I18n.t("Instalar")
          tipo: "primario"
          ocupado: dispLin.emAndamento
          habilitado: !dispLin.emAndamento
          onClicado: pg.instalar(dispLin.modelData.id)
        }
      }
    }
  }

  Secao { titulo: I18n.t("Troca automática") }
  Cartao {
    Linha {
      chave: "agentesTroca"
      glifo: Icones.swapVertical
      titulo: I18n.t("Trocar de agente quando o limite acabar")
      descricao: I18n.t("Leva o contexto: pedido, conversa, comandos e estado do Git vão para o próximo agente")
      Interruptor { ligado: !!(pg.s && pg.s.trocaAutomatica); onAlternado: function(x) { pg.rodar(["opcao", "trocaAutomatica", x ? "true" : "false"]) } }
    }
    Linha {
      chave: "agentesEsperar"
      glifo: Icones.timer
      titulo: I18n.t("Esperar antes de trocar")
      descricao: I18n.t("Tempo para cancelar com Esc, caso não seja o limite de verdade · 0 troca na hora")
      Deslizante {
        width: 220; de: 0; ate: 30; passo: 1; sufixo: " s"
        valor: pg.s ? pg.s.esperar : 8
        onSolto: function(v) { pg.rodar(["opcao", "esperar", String(v)]) }
      }
    }
  }
}
