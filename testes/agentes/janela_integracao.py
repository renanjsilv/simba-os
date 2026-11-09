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
os.environ.pop("XDG_CACHE_HOME", None)  # prints colados vão para o HOME temporário
# captura de tela falsa: nunca fotografa a tela de verdade
_bin = home / "bin"
_bin.mkdir()
(_bin / "simba-capture-screenshot").write_text(
    "#!/bin/bash\nf=\"$SIMBA_SCREENSHOT_DIR/screenshot-teste.png\"\n"
    "printf '\\x89PNG\\r\\n\\x1a\\n' > \"$f\"\necho \"$f\"\n")
(_bin / "simba-capture-screenshot").chmod(0o755)
os.environ["PATH"] = f"{_bin}:{os.environ['PATH']}"
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

        print("0) janela parada não fica ocupando o processador")
        import resource
        yield 0.3
        antes = resource.getrusage(resource.RUSAGE_SELF).ru_utime
        yield 1.0
        gasto = resource.getrusage(resource.RUSAGE_SELF).ru_utime - antes
        checar(gasto < 0.3, f"CPU com a janela parada: {gasto:.2f}s em 1s")

        print("1) resposta com ferramenta, em tempo real")
        roteiro.append(("claude-ferramenta.ndjson", 0.15))
        self.enviar("o que tem nesta pasta?")
        yield 0.4
        # o status (spinner/pensando) fica abaixo do texto da resposta, no fim da conversa
        st, msg = self.win.ativo_status_box, self.win.ativo_mensagem
        filhos, f = [], (st.get_parent().get_first_child() if st and st.get_parent() else None)
        while f is not None:
            filhos.append(f)
            f = f.get_next_sibling()
        checar(st in filhos and msg in filhos and filhos.index(st) > filhos.index(msg),
               "status de pensamento fica abaixo do texto da resposta")
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

        print("8) colar um print (Ctrl+V com imagem) vira anexo e vai no pedido")
        from gi.repository import Gdk
        clip = w.text_input.get_clipboard()
        pixels = GLib.Bytes.new(bytes([255, 0, 0, 255]) * 16)
        textura = Gdk.MemoryTexture.new(4, 4, Gdk.MemoryFormat.R8G8B8A8, pixels, 16)
        clip.set_content(Gdk.ContentProvider.new_for_value(textura))
        w.text_input.grab_focus()
        w.text_input.emit("paste-clipboard")
        yield 0.8
        checar(len(w.anexos_pendentes) == 1 and Path(w.anexos_pendentes[0]).is_file(), "print colado virou anexo (PNG salvo)")
        checar(w.btn_enviar.get_sensitive(), "dá para enviar só com a imagem")
        caminho = w.anexos_pendentes[0] if w.anexos_pendentes else "?"
        roteiro.append(("claude-ferramenta.ndjson", 0.01))
        self.enviar("o que tem no print?")
        checar(caminho in chamadas[-1]["pedido"] and "o que tem no print?" in chamadas[-1]["pedido"],
               "caminho da imagem vai no pedido ao agente")
        ultima_user = [m for m in w.conversa_mensagens if m["tipo"] == "user"][-1]
        checar(ultima_user.get("anexos") == [caminho] and ultima_user["texto"] == "o que tem no print?",
               "anexo registrado na conversa (texto sem o caminho)")
        checar(not w.anexos_pendentes and not w.box_anexos.get_visible(), "faixa de anexos limpa depois de enviar")
        yield from self.esperar_fim()

        print("9) Ctrl+V com texto continua colando texto")
        clip.set_content(Gdk.ContentProvider.new_for_value("texto colado"))
        w.text_input_buf.set_text("")
        w.text_input.emit("paste-clipboard")
        yield 0.5
        ini, fim = w.text_input_buf.get_bounds()
        checar(w.text_input_buf.get_text(ini, fim, True) == "texto colado" and not w.anexos_pendentes,
               "texto colado normalmente, sem anexo")
        w.text_input_buf.set_text("")

        print("10) trocar o agente no meio da resposta não troca quem está respondendo")
        roteiro.append(("claude-ferramenta.ndjson", 0.2))
        self.enviar("pedido longo")
        yield 0.2
        w.dropdown.set_selected(0)
        checar(w.agente_atual == "claude", "agente_atual continua sendo o que responde")
        yield from self.esperar_fim()

        print("11) busca na conversa (Ctrl+F)")
        w._abrir_busca()
        yield 0.5
        foco = w.get_focus()
        checar(foco is not None and foco.is_ancestor(w.busca_entrada), "Ctrl+F põe o foco no campo de busca")
        w.busca_entrada.set_text("ARQUIVO")  # sem diferenciar maiúsculas/acentos
        w._buscar()
        n = len(w.busca_resultados)
        checar(n >= 1, f"achou as ocorrências ({n})")
        checar(" de " in w.busca_contagem.get_label(), "contagem 'n de m' na barra")
        yield 0.5
        checar(w._busca_ativa(), "barra continua aberta depois de achar")
        antes = w.busca_indice
        w._busca_ir(1)
        checar(n == 1 or w.busca_indice != antes, "Enter vai para a próxima")
        w.busca_entrada.set_text("zzz-nao-existe")
        w._buscar()
        checar(not w.busca_resultados, "termo inexistente: nada encontrado")
        w._fechar_busca()
        yield 0.2
        checar(not w._busca_ativa(), "Esc/fechar some com a barra")
        roteiro.append(("claude-ferramenta.ndjson", 0.05))
        self.enviar("resposta enquanto busco")
        w._abrir_busca()
        yield from self.esperar_fim()
        yield 0.2
        foco = w.get_focus()
        checar(foco is not None and (foco is w.busca_entrada or foco.is_ancestor(w.busca_entrada)),
               "fim da resposta não rouba o foco da busca")
        w._fechar_busca()

        print("12) painel de uso e custo")
        import painel
        periodos, agentes = painel.coletar()
        checar(periodos["hoje"]["respostas"] >= 1 and "claude" in agentes, "respostas de hoje somadas")
        checar(periodos["30d"]["custo"] > 0, "custo somado do uso salvo")
        w._abrir_painel_uso()
        yield 0.8
        dlg = w.get_visible_dialog()
        checar(dlg is not None, "painel aberto sobre o chat")
        conteudo = dlg.get_child().get_content().get_child() if dlg else None
        conteudo = conteudo.get_child() if isinstance(conteudo, A.Gtk.Viewport) else conteudo
        checar(isinstance(conteudo, A.Gtk.Box), "painel montou o conteúdo (cartões e tabela)")
        if dlg:
            dlg.close()

        print("13) capturar área da tela anexa o print")
        w._capturar_tela()
        yield 1.5
        checar(any(a.endswith("screenshot-teste.png") for a in w.anexos_pendentes), "print capturado virou anexo")
        checar(w.get_visible(), "janela voltou depois da captura")
        w._limpar_anexos()

        if w.navegador and w.navegador.socket:
            print("14) agente fecha o navegador e o chat volta ao foco")
            import json as js_
            import socket as sk
            import navegador as N

            def pedir(dados):
                with sk.socket(sk.AF_UNIX, sk.SOCK_STREAM) as s:
                    s.setblocking(False)
                    s.connect(w.navegador.socket)
                    s.sendall((js_.dumps(dados) + "\n").encode())
                    buf = b""
                    for _ in range(200):
                        try:
                            buf += s.recv(65536)
                        except BlockingIOError:
                            pass
                        if buf.endswith(b"\n"):
                            break
                        ctx = A.GLib.MainContext.default()
                        while ctx.pending():
                            ctx.iteration(False)
                    return js_.loads(buf or b"{}")

            w.navegador.mostrar()
            yield 0.3
            checar(w.navegador.get_visible() and w.btn_navegador.get_active(), "navegador aberto")
            checar(pedir({"cmd": "fechar"}).get("ok"), "comando fechar respondeu ok")
            yield 0.3
            checar(not w.navegador.get_visible() and not w.btn_navegador.get_active(), "navegador escondido")
            checar(w.get_focus() is w.text_input, "foco de volta na caixa de mensagem")
            checar("simba-navegador fechar" in N.INSTRUCAO_AGENTE, "instrução ensina o agente a fechar")
            checar(N._corpo_js('let a = 2; a * 3').endswith("return (function(){ return (a * 3); })();"),
                   "js com várias instruções devolve a última")


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
