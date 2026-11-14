"""Integrações do chat para os agentes (`simba-chat`), no mesmo molde do navegador embutido.

O chat abre um socket Unix ($XDG_RUNTIME_DIR/simba-chat/<app>-<pid>.sock, passado aos
agentes em SIMBA_CHAT). Cada conexão manda uma linha JSON {"cmd": ..., ...} e recebe
uma linha JSON de resposta. Comandos:

  perguntar   pergunta com botões de resposta na conversa; espera a pessoa escolher
  mostrar     abre um arquivo no painel de código ao lado da conversa (acompanha mudanças)
  codigo      mostra um texto no painel de código (lang, titulo, texto)
  notificar   avisa a pessoa (notificação do sistema + linha na conversa)
  fechar      fecha o painel de código
"""
import json
import os
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib  # noqa: E402

COMANDOS = ("perguntar", "mostrar", "codigo", "notificar", "fechar", "estado")


class Servidor:
    def __init__(self, tratar):
        """`tratar(pedido, responder)` roda na thread da interface."""
        self.tratar = tratar
        self.servico = None
        self.socket = None
        self._conexoes = set()

    def iniciar(self, nome):
        base = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/simba-{os.getuid()}") / "simba-chat"
        base.mkdir(parents=True, exist_ok=True)
        os.chmod(base, 0o700)
        caminho = base / f"{nome}-{os.getpid()}.sock"
        try:
            caminho.unlink()
        except FileNotFoundError:
            pass
        self.servico = Gio.SocketService()
        self.servico.add_address(Gio.UnixSocketAddress.new(str(caminho)), Gio.SocketType.STREAM,
                                 Gio.SocketProtocol.DEFAULT, None)
        os.chmod(caminho, 0o600)
        self.servico.connect("incoming", self._on_conexao)
        self.servico.start()
        self.socket = str(caminho)
        return self.socket

    def parar(self):
        if self.servico:
            self.servico.stop()
            self.servico.close()
            self.servico = None
        if self.socket:
            try:
                os.unlink(self.socket)
            except OSError:
                pass
            self.socket = None

    def _on_conexao(self, _servico, conexao, _origem):
        self._conexoes.add(conexao)
        entrada = Gio.DataInputStream.new(conexao.get_input_stream())
        entrada.read_line_async(GLib.PRIORITY_DEFAULT, None, self._on_linha, conexao)
        return True

    def _on_linha(self, entrada, resultado, conexao):
        try:
            linha, _n = entrada.read_line_finish_utf8(resultado)
            pedido = json.loads(linha or "{}")
        except Exception as e:  # noqa: BLE001
            self._responder(conexao, {"ok": False, "erro": f"pedido inválido: {e}"})
            return
        if pedido.get("cmd") not in COMANDOS:
            self._responder(conexao, {"ok": False, "erro": f"comando desconhecido: {pedido.get('cmd')}",
                                      "comandos": list(COMANDOS)})
            return
        respondido = [False]

        def responder(r):
            if not respondido[0]:
                respondido[0] = True
                self._responder(conexao, r)
        try:
            self.tratar(pedido, responder)
        except Exception as e:  # noqa: BLE001
            responder({"ok": False, "erro": str(e)})

    def _responder(self, conexao, resposta):
        dados = (json.dumps(resposta, ensure_ascii=False) + "\n").encode()
        try:
            conexao.get_output_stream().write_all(dados, None)
            conexao.close(None)
        except GLib.Error:
            pass
        self._conexoes.discard(conexao)


INSTRUCAO_AGENTE = """[Ferramentas do chat do Simba OS: simba-chat]
Além do navegador, o chat tem estas ferramentas, pelo terminal:
  simba-chat perguntar "Pergunta?" "Opção 1" "Opção 2" ...   mostra botões na conversa e espera a pessoa escolher; a escolha (ou o que ela digitou) sai na saída padrão. Use quando precisar de uma decisão do usuário no meio da tarefa, em vez de terminar a resposta só para perguntar. Pode demorar: rode com tempo limite longo (até 10 min).
  simba-chat mostrar <arquivo> [--linha N]   abre o arquivo no painel de código ao lado da conversa (acompanha as mudanças). Use ao criar ou alterar um arquivo que a pessoa vai querer ver inteiro.
  simba-chat codigo <linguagem> "<título>" < arquivo   mostra um texto no painel de código.
  simba-chat notificar "texto"     avisa a pessoa (notificação do sistema), ex.: ao terminar algo demorado.
  simba-chat fechar                 fecha o painel de código."""

INSTRUCAO_LIVRE = """[Modo livre do chat]
O usuário deixou este chat no modo livre: você tem autonomia para executar comandos e alterar arquivos nesta máquina sem pedir aprovação. Quando um passo precisar de um comando, execute-o você mesmo em vez de pedir para o usuário rodar. Para comandos de administrador use `sudo -A <comando>` (o Simba mostra uma janela de senha com o comando visível); nunca peça a senha no chat. Antes de algo destrutivo ou difícil de desfazer (apagar dados, formatar, mexer em boot), pergunte com `simba-chat perguntar`."""
