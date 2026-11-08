#!/usr/bin/env python3
"""Teste de integração da janela do chat, sem tela e sem gastar cota.

    testes/agentes/janela_integracao.sh

Roda a MainWindow de verdade (GTK no backend Broadway, HOME temporário) com um
"agente" falso que reproduz as saídas gravadas em fixtures/ aos poucos, como a
CLI real faria. Verifica: texto em tempo real, fila de mensagens, retomada da
sessão certa, interrupção (sem finalizar duas vezes) e troca por limite.
"""
import json
import os
from pathlib import Path
import sys
import tempfile

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1] / "pacotes/simba-apps/raiz/usr/share/simba-apps/agentes"

home = Path(tempfile.mkdtemp(prefix="agentes-teste-"))
os.environ["HOME"] = str(home)
os.environ["AGENTES_DEV"] = "1"
(home / ".config/agentes").mkdir(parents=True)
(home / ".config/agentes/config.json").write_text(json.dumps(
    {"ordem": ["claude"], "inativos": [], "trocaAutomatica": True, "esperar": 8, "modelos": {}, "seguro": False}))
(home / "Work").mkdir()

sys.path.insert(0, str(RAIZ))
import motor as M  # noqa: E402
import app as A  # noqa: E402
from gi.repository import GLib  # noqa: E402

FALSO = home / "agente_falso.py"
FALSO.write_text('''import sys, time
linhas = open(sys.argv[1]).read().splitlines()
atraso = float(sys.argv[2])
for l in linhas:
    print(l, flush=True)
    time.sleep(atraso)
''')
chamadas = []
roteiro = []  # fixture e atraso de cada execução, na ordem


def montar_falso(a, pedido, cfg, sessao=None, continuar=False, seguro=False):
    fixture, atraso = roteiro.pop(0)
    chamadas.append({"agente": a, "pedido": pedido, "sessao": sessao, "continuar": continuar, "seguro": seguro})
    return [sys.executable, str(FALSO), str(AQUI / "fixtures" / fixture), str(atraso)]


M.montar_comando = montar_falso
M.candidatos = lambda c, pular=(), verificar=True, seguro=False: [a for a in ["claude"] if a not in pular]
M.esgotado_ate = lambda a: None
M.marcar_esgotado = lambda a, ate=None: None
falhas = []


def checar(cond, msg):
    print(("  ok  " if cond else "  FALHOU  ") + msg)
    if not cond:
        falhas.append(msg)


class Teste:
    def __init__(self, win, app):
        self.win, self.app = win, app
        self.passos = iter(self.roteiro())
        GLib.timeout_add(300, self.proximo)

    def proximo(self):
        try:
            espera = next(self.passos)
        except StopIteration:
            self.app.quit()
            return False
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            falhas.append(f"exceção: {e}")
            self.app.quit()
            return False
        GLib.timeout_add(int(espera * 1000), self.proximo)
        return False

    def enviar(self, texto):
        self.win.text_input_buf.set_text(texto)
        self.win._on_enviar()

    def esperar_fim(self):
        while self.win._rodando():
            yield 0.1

    def roteiro(self):
        w = self.win
        textos_vistos = []
        orig = w._render_parcial

        def espiar():
            textos_vistos.append(w.ativo_texto)
            return orig()
        w._render_parcial = espiar

        print("1) resposta com ferramenta, em tempo real")
        roteiro.append(("claude-ferramenta.ndjson", 0.15))
        self.enviar("o que tem nesta pasta?")
        yield 0.4
        print("2) mensagem enviada durante a resposta vai para a fila")
        roteiro.append(("claude-ferramenta.ndjson", 0.05))
        self.enviar("e o tamanho?")
        checar(len(w.fila) == 1, "mensagem entrou na fila")
        yield from self.esperar_fim()
        checar(any(0 < len(t) < len("Há um único arquivo: `a.txt` (3 bytes).") for t in textos_vistos),
               "texto apareceu em partes antes do fim (markdown parcial)")
        primeira = next(m for m in w.conversa_mensagens if m["tipo"] == "assistant")
        checar(primeira["texto"] == "Há um único arquivo: `a.txt` (3 bytes).", "texto final da 1ª resposta")
        checar(primeira.get("modelo") == "claude-haiku-5-5", "badge com o modelo real do stream")
        checar(primeira.get("uso", {}).get("custo", 0) > 0, "uso/custo guardado na resposta")
        checar(w.sessoes.get("claude") == "491b53f0-6b17-4a5e-961c-02b9bbd45d15", "id da sessão capturado")
        yield 0.3  # a fila é despachada no fim da 1ª execução
        checar(len(w.fila) == 0 and len(chamadas) == 2, "fila despachada automaticamente")
        checar(chamadas[1]["sessao"] == "491b53f0-6b17-4a5e-961c-02b9bbd45d15",
               "2º pedido retoma a sessão certa (--resume <id>)")
        checar("Você está retomando" not in chamadas[1]["pedido"], "sem reenviar o histórico quando há sessão")
        yield from self.esperar_fim()

        print("3) interromper no meio")
        roteiro.append(("claude-ferramenta.ndjson", 0.4))
        self.enviar("faça algo demorado")
        yield 0.6
        roteiro.append(("claude-ferramenta.ndjson", 0.01))
        self.enviar("isto fica na fila")
        finalizacoes = []
        orig_fin = w._finalizar_resposta

        def contar(*a, **k):
            if not w.finalizado:
                finalizacoes.append(1)
            return orig_fin(*a, **k)
        w._finalizar_resposta = contar
        w._interromper()
        yield 1.5  # tempo para a thread antiga terminar e (não) finalizar de novo
        checar(len(finalizacoes) == 1, "resposta finalizada uma única vez")
        ultima = [m for m in w.conversa_mensagens if m["tipo"] == "assistant"][-1]
        checar(ultima.get("interrompida") and "Interrompido" in ultima["texto"], "marcada como interrompida")
        ini, fim = w.text_input_buf.get_bounds()
        checar(w.text_input_buf.get_text(ini, fim, True) == "isto fica na fila", "fila voltou para a caixa de texto")
        w._finalizar_resposta = orig_fin
        w.text_input_buf.set_text("")
        roteiro.clear()

        print("4) depois de interromper, o próximo pedido avisa o agente")
        roteiro.append(("claude-ferramenta.ndjson", 0.01))
        self.enviar("continue")
        checar(chamadas[-1]["pedido"].startswith("(A sua resposta anterior foi interrompida"), "aviso de interrupção")
        yield from self.esperar_fim()

        print("5) limite atingido → troca (sem outro agente: avisa e para)")
        roteiro.append(("claude-limite.sintetico.ndjson", 0.01))
        self.enviar("mais uma")
        yield from self.esperar_fim()
        yield 0.3
        sistemas = [m for m in w.conversa_mensagens if m["tipo"] == "sistema"]
        checar(any("Limite de uso atingido" in m["texto"] for m in sistemas), "aviso de limite na conversa")

        print("6) resposta que só *fala* de limite não troca de agente")
        p = A.AgentStreamParser(lambda s: None, lambda t: None, lambda d: None, agente="claude")
        p.feed('{"type":"assistant","message":{"content":[{"type":"text","text":"O rate limit foi atingido; tente novamente após o reset."}]}}\n')
        checar(not w._limite_atingido(p, 0), "sem troca falsa")

        print("7) conversa salva com as sessões")
        w._salvar_conversa()
        dados = json.loads(next((home / ".local/state/simba/agents/conversas").glob("*.json")).read_text())
        checar(dados.get("sessoes", {}).get("claude"), "sessões gravadas no histórico")
        yield 0.1


class AppTeste(A.App):
    def do_activate(self):
        win = A.MainWindow(self)
        win.present()
        self.teste = Teste(win, self)

    def do_command_line(self, cl):
        self.activate()
        return 0


AppTeste().run([sys.argv[0]])
print("\nRESULTADO:", "OK" if not falhas else f"{len(falhas)} falha(s)")
sys.exit(1 if falhas else 0)
