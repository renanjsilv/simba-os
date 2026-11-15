"""Títulos resumidos pela IA: limpeza da resposta, contexto, escolha do provedor e a fila
do app (com o gerador trocado por um falso; nada vai para a rede)."""
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

AGENTES = Path(__file__).resolve().parents[2] / "pacotes/simba-apps/raiz/usr/share/simba-apps/agentes"
sys.path.insert(0, str(AGENTES))
sys.path.insert(0, str(AGENTES.parents[0] / "idiomas"))

import titulos as TIT  # noqa: E402


class Limpar(unittest.TestCase):
    def test_limpa(self):
        self.assertEqual(TIT.limpar('Título: "botão fechar do Explorador."'), "Botão fechar do Explorador")
        self.assertEqual(TIT.limpar("pensando...\n**Transcrição local do Draco**"), "Transcrição local do Draco")
        self.assertIsNone(TIT.limpar(""))
        self.assertIsNone(TIT.limpar("uma frase enorme que claramente não é um título curto de jeito nenhum aqui"))

    def test_contexto(self):
        msgs = [{"tipo": "user", "texto": "arruma o botão"}, {"tipo": "assistant", "texto": "Pronto, corrigi."},
                {"tipo": "user", "texto": "e o ícone?"}, {"tipo": "user", "texto": "terceiro"}]
        c = TIT.contexto(msgs)
        self.assertIn("Pedido: arruma o botão", c)
        self.assertIn("Resposta: Pronto, corrigi.", c)
        self.assertIn("e o ícone?", c)
        self.assertNotIn("terceiro", c)


class Provedor(unittest.TestCase):
    """O resumo vai para o mesmo provedor da conversa; a Groq é a reserva."""

    def setUp(self):
        self.chamados = []
        self.orig = (TIT._claude, TIT._opencode, TIT._groq)
        TIT._claude = lambda p: self.chamados.append("claude")
        TIT._opencode = lambda p, m: self.chamados.append(("opencode", m))
        TIT._groq = lambda p: self.chamados.append("groq") or "Título da Groq"

    def tearDown(self):
        TIT._claude, TIT._opencode, TIT._groq = self.orig

    def msgs(self, agente, modelo=""):
        return [{"tipo": "user", "texto": "oi"}, {"tipo": "assistant", "agente": agente, "modelo": modelo, "texto": "olá"}]

    def test_claude(self):
        self.assertEqual(TIT.gerar(self.msgs("claude")), "Título da Groq")
        self.assertEqual(self.chamados, ["claude", "groq"])

    def test_opencode_mesmo_modelo(self):
        TIT.gerar(self.msgs("opencode", "x/y"))
        self.assertEqual(self.chamados[0], ("opencode", "x/y"))

    def test_outro_agente_nao_usa_claude_nem_opencode(self):
        TIT.gerar(self.msgs("codex"))
        self.assertEqual(self.chamados, ["groq"])


class Fila(unittest.TestCase):
    """A fila do app: conversa atual em memória, antigas gravadas no arquivo."""

    def test_fila(self):
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import GLib
        import historico

        pasta = Path(tempfile.mkdtemp())
        historico.CONVERSAS = pasta
        orig = TIT.gerar
        TIT.gerar = lambda msgs: "Resumo de " + msgs[0]["texto"]
        orig_disp = TIT.disponivel
        TIT.disponivel = lambda: True
        try:
            def conversa(cid, texto, **extra):
                d = {"id": cid, "titulo": texto[:10], "mensagens": [
                    {"tipo": "user", "texto": texto}, {"tipo": "assistant", "agente": "claude", "texto": "ok"}], **extra}
                (pasta / f"{cid}.json").write_text(json.dumps(d))

            conversa("a", "antiga")
            conversa("b", "renomeada", titulo_manual=True)
            conversa("c", "já feita", titulo_ia="X", titulo_ia_v=TIT.VERSAO)

            class App(historico.HistoricoMixin):
                conversa_id = "atual"
                conversa_titulo_manual = None
                conversa_mensagens = [{"tipo": "user", "texto": "atual"}, {"tipo": "assistant", "texto": "ok"}]
                mudou = 0
                salvou = 0

                def _salvar_conversa(self):
                    self.salvou += 1

                def _conversas_mudaram(self):
                    self.mudou += 1

            app = App()
            app._titulos_antigos()
            app._pedir_titulo_ia()
            ctx = GLib.MainContext.default()
            fim = time.time() + 5
            while time.time() < fim and (app._titulos_fila or app._titulos_pendentes or ctx.pending()):
                ctx.iteration(False)
                time.sleep(0.01)
            while ctx.pending():
                ctx.iteration(False)

            ler = lambda cid: json.loads((pasta / f"{cid}.json").read_text())
            self.assertEqual(ler("a")["titulo"], "Resumo de antiga")
            self.assertEqual(ler("a")["titulo_ia_v"], TIT.VERSAO)
            self.assertNotIn("titulo_ia", ler("b"))          # renomeada pela pessoa: intocada
            self.assertEqual(ler("c")["titulo_ia"], "X")     # já resumida: não refaz
            self.assertEqual(app._titulos_ia()["atual"], "Resumo de atual")
            self.assertEqual(app._titulo_conversa(), "Resumo de atual")
            self.assertEqual(app.salvou, 1)
            self.assertGreaterEqual(app.mudou, 1)
            self.assertEqual(oct(os.stat(pasta / "a.json").st_mode & 0o777), "0o600")
        finally:
            TIT.gerar = orig
            TIT.disponivel = orig_disp


if __name__ == "__main__":
    unittest.main()
