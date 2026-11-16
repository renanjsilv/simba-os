"""Modo Automático: agente que volta recebe o que os outros disseram desde a última resposta dele."""
import os, sys, unittest
D = os.path.join(os.path.dirname(__file__), "../../pacotes/simba-apps/raiz/usr/share/simba-apps/agentes")
sys.path.insert(0, os.path.abspath(D))
sys.path.insert(0, os.path.abspath(os.path.join(D, "../idiomas")))
import historico  # noqa: E402

Mixin = next(v for v in vars(historico).values() if isinstance(v, type) and hasattr(v, "_pedido_com_novidades"))


class Falso(Mixin):
    def __init__(self, msgs):
        self.conversa_mensagens = msgs


def conversa():
    return [
        {"tipo": "user", "texto": "qual a versão do pacote?"},
        {"tipo": "assistant", "agente": "claude", "texto": "É a 1.0."},
        {"tipo": "user", "texto": "atualiza para a 2.0"},
        {"tipo": "assistant", "agente": "codex", "texto": "Atualizei: agora é a 2.0."},
        {"tipo": "user", "texto": "e agora, qual a versão?"},
    ]


class TestTroca(unittest.TestCase):
    def test_volta_com_novidades(self):
        f = Falso(conversa())
        p = f._pedido_com_novidades("claude", "e agora, qual a versão?")
        self.assertIn("atualiza para a 2.0", p)
        self.assertIn("Atualizei: agora é a 2.0.", p)
        self.assertNotIn("É a 1.0.", p)              # o que ele já sabe não repete
        self.assertTrue(p.endswith("e agora, qual a versão?"))
        self.assertEqual(p.count("e agora, qual a versão?"), 1)

    def test_sem_novidades_nao_mexe(self):
        f = Falso(conversa())
        self.assertEqual(f._pedido_com_novidades("codex", "e agora, qual a versão?"), "e agora, qual a versão?")

    def test_ultimo_e_participacao(self):
        f = Falso(conversa())
        self.assertTrue(f._foi_o_ultimo_a_responder("codex"))
        self.assertFalse(f._foi_o_ultimo_a_responder("claude"))
        self.assertEqual(f._ultima_resposta_de("opencode"), -1)


if __name__ == "__main__":
    unittest.main()
