"""Testes do parser do chat dos Agentes de IA com saídas gravadas das CLIs.

    python3 -m unittest discover -s testes/agentes -v

fixtures/*.ndjson: saídas reais (Claude Code 2.1, OpenCode 2.2; Codex sem login).
fixtures/*.sintetico.ndjson: montadas a partir do formato documentado, para
casos difíceis de reproduzir (limite atingido, Codex logado).
Ao atualizar uma CLI, grave uma saída nova e rode os testes: os formatos
mudam sem aviso.
"""
from pathlib import Path
import sys
import unittest

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1] / "pacotes/simba-apps/raiz/usr/share/simba-apps/agentes"
sys.path.insert(0, str(RAIZ))

from parser import AgentStreamParser, descrever_ferramenta  # noqa: E402
import motor as M  # noqa: E402


def rodar(fixture, agente, pedacos=7):
    """Alimenta o parser em pedaços pequenos (como chega pelo pty) e devolve o resultado."""
    eventos = {"status": [], "texto": [], "meta": [], "fim": []}
    p = AgentStreamParser(
        on_status=eventos["status"].append,
        on_text=eventos["texto"].append,
        on_done=eventos["fim"].append,
        agente=agente,
        on_meta=eventos["meta"].append,
    )
    dados = (AQUI / "fixtures" / fixture).read_text()
    for i in range(0, len(dados), pedacos):
        p.feed(dados[i:i + pedacos])
    p.finish()
    return p, eventos


class Claude(unittest.TestCase):
    def test_texto_em_tempo_real_sem_duplicar(self):
        p, ev = rodar("claude-ferramenta.ndjson", "claude")
        self.assertEqual(p.texto, "Há um único arquivo: `a.txt` (3 bytes).")
        self.assertGreater(len(ev["texto"]), 1, "o texto deve chegar em pedaços (mensagens parciais)")

    def test_ferramenta_aparece_na_atividade(self):
        p, ev = rodar("claude-ferramenta.ndjson", "claude")
        self.assertTrue(any("ls -la /tmp/fixt" in a for a in p.actions), p.actions)
        self.assertTrue(any("Bash" in s or "Executando" in s for s in ev["status"]))

    def test_metadados(self):
        p, _ = rodar("claude-ferramenta.ndjson", "claude")
        self.assertEqual(p.sessao, "491b53f0-6b17-4a5e-961c-02b9bbd45d15")
        self.assertEqual(p.modelo, "claude-haiku-5-5")
        self.assertEqual(p.janelas, {"5h": 0.04, "7d": 0.0})
        # quando cada limite zera (epoch do rate_limit_event), para o chat mostrar
        self.assertEqual(p.voltas, {"5h": 1794160200, "7d": 1794733200})
        self.assertGreater(p.uso["saida"], 0)
        self.assertAlmostEqual(p.uso["custo"], 0.00292691, places=6)
        self.assertFalse(p.erro)
        self.assertFalse(p.limite)

    def test_limite_estruturado(self):
        p, _ = rodar("claude-limite.sintetico.ndjson", "claude")
        self.assertTrue(p.limite)
        self.assertEqual(p.limite_ate, 1794160200)
        self.assertIn("session limit", p.erro)
        self.assertTrue(M.detectar_limite(p.texto_detectavel))

    def test_blocos_separados(self):
        eventos = []
        p = AgentStreamParser(lambda s: None, eventos.append, lambda d: None, agente="claude")
        msg = '{"type":"assistant","message":{"content":[{"type":"text","text":"%s"}]}}\n'
        p.feed(msg % "Vou ler o arquivo." + msg % "Pronto.")
        self.assertEqual(p.texto, "Vou ler o arquivo.\n\nPronto.")


class ClaudeSegundoPlano(unittest.TestCase):
    """Subagente em segundo plano: o processo segue vivo depois da resposta e emite
    várias rodadas (um "result" cada). Saída real gravada do Claude Code."""

    def test_atividade_do_subagente_aparece(self):
        p, ev = rodar("claude-subagente-fundo.ndjson", "claude")
        self.assertTrue(any(a.startswith("Subagente:") for a in p.actions), p.actions)
        self.assertTrue(any(a.startswith("↳ Executando:") for a in p.actions), p.actions)
        self.assertTrue(any("tokens" in s and "Subagente" in s for s in ev["status"]), "progresso com tokens")

    def test_texto_do_subagente_fica_fora_da_resposta(self):
        p, _ = rodar("claude-subagente-fundo.ndjson", "claude")
        self.assertNotIn("O comando de espera", p.texto)
        self.assertTrue(p.texto.startswith("lancado"), p.texto)
        self.assertTrue(p.texto.rstrip().endswith("terminou"), p.texto)

    def test_espera_em_segundo_plano_e_fim(self):
        """Depois do 1º "result" ainda há tarefa pendente (não é travamento); no fim, nenhuma."""
        pendencias = []
        p = AgentStreamParser(lambda s: None, lambda t: None,
                              lambda d: pendencias.append(len(p.tarefas_pendentes())), agente="claude")
        p.feed((AQUI / "fixtures" / "claude-subagente-fundo.ndjson").read_text())
        self.assertGreater(pendencias[0], 0)
        self.assertEqual(p.tarefas_pendentes(), [])
        self.assertTrue(p.fim_rodada)
        self.assertGreaterEqual(p.resultados, 3)

    def test_uso_soma_as_rodadas(self):
        p, _ = rodar("claude-subagente-fundo.ndjson", "claude")
        self.assertGreater(p.uso["saida"], 500, "a última rodada (vazia) não pode zerar o uso")
        self.assertAlmostEqual(p.uso["custo"], 0.008804065, places=6)
        self.assertGreater(sum(p.uso_tarefas.values()), 20000)

    def test_repeticao_da_mesma_acao(self):
        p = AgentStreamParser(lambda s: None, lambda t: None, lambda d: None, agente="claude")
        linha = '{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"ls"}}]}}\n'
        p.feed(linha * 12)
        self.assertEqual(p.repeticoes, 12)
        p.feed(linha.replace('"ls"', '"pwd"'))
        self.assertEqual(p.repeticoes, 1)


class Codex(unittest.TestCase):
    def test_resposta_e_comando(self):
        p, ev = rodar("codex-ferramenta.sintetico.ndjson", "codex")
        self.assertEqual(p.texto, "Existe apenas o arquivo `a.txt`.")
        self.assertEqual(p.sessao, "0199a213-81c0-7800-8aa1-bbab2a035a53")
        self.assertTrue(any("bash -lc ls" in a for a in p.actions))
        self.assertEqual(p.uso["saida"], 122)

    def test_sem_login_vira_erro_e_nao_texto(self):
        p, ev = rodar("codex-sem-login.ndjson", "codex")
        self.assertFalse(p.has_text, "erros e reconexões não podem ir para a bolha")
        self.assertIn("401", p.erro)
        self.assertTrue(any("Reconnecting" in s for s in ev["status"]))

    def test_log_de_stderr_nao_entra_na_resposta(self):
        textos = []
        p = AgentStreamParser(lambda s: None, textos.append, lambda d: None, agente="codex")
        p.feed("2026-11-08T13:33:49Z ERROR codex_api::endpoint: failed to connect\n")
        self.assertEqual(textos, [])
        self.assertIn("failed to connect", p.erro)


class OpenCode(unittest.TestCase):
    def test_texto_ferramentas_sessao_e_tokens(self):
        p, _ = rodar("opencode-ferramenta.ndjson", "opencode")
        self.assertEqual(p.texto, "Existe apenas o arquivo `a.txt` nesta pasta.")
        self.assertEqual(p.sessao, "ses_e44a2495effe0e4Wu3s7UQ1Uxh")
        self.assertEqual(len([a for a in p.actions if "Executando" in a]), 3, p.actions)
        self.assertGreater(p.uso["entrada"], 0)


class TextoPuro(unittest.TestCase):
    def test_agente_de_texto(self):
        textos = []
        p = AgentStreamParser(lambda s: None, textos.append, lambda d: None, agente="grok")
        p.feed("\x1b[32mOlá!\x1b[0m\r\n⠋⠙\nRunning command: ls\nTudo certo.\n")
        p.finish()
        self.assertEqual(p.texto, "Olá!\nTudo certo.\n")


class Motor(unittest.TestCase):
    def test_retoma_a_sessao_certa(self):
        cfg = {"modelos": {}}
        cmd = M.montar_comando("claude", "oi", cfg, sessao="abc")
        self.assertIn("--resume", cmd)
        self.assertEqual(cmd[cmd.index("--resume") + 1], "abc")
        self.assertNotIn("--continue", cmd)
        self.assertIn("--include-partial-messages", cmd)
        cmd = M.montar_comando("codex", "oi", cfg, sessao="t1")
        self.assertEqual(cmd[-3:], ["resume", "t1", "oi"])
        self.assertIn("--json", cmd)
        cmd = M.montar_comando("opencode", "oi", cfg, sessao="ses_1")
        self.assertEqual(cmd[-3:], ["-s", "ses_1", "oi"])

    def test_modo_seguro(self):
        cfg = {"modelos": {"codex": "gpt-5.5"}}
        cmd = M.montar_comando("codex", "oi", cfg, seguro=True)
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", cmd)
        self.assertIn("read-only", cmd)
        self.assertIn("gpt-5.5", cmd)
        cmd = M.montar_comando("claude", "oi", cfg, seguro=True)
        self.assertNotIn("auto", cmd[:3])
        self.assertFalse(M.suporta_seguro("grok"))
        for a, info in M.AGENTES.items():
            for parte in info.get("cmdSeguro") or []:
                self.assertNotRegex(parte, r"dangerously|yolo|allow-all|bypass|--force", a)

    def test_resposta_que_fala_de_limite_nao_e_limite(self):
        p = AgentStreamParser(lambda s: None, lambda t: None, lambda d: None, agente="claude")
        p.feed('{"type":"assistant","message":{"content":[{"type":"text","text":'
               '"A API retorna 429 quando o rate limit é atingido; tente novamente após o reset."}]}}\n'
               '{"type":"result","subtype":"success","is_error":false,"result":"ok"}\n')
        # o texto sozinho casaria com a regex; sem erro/limite estruturado, não troca
        self.assertTrue(M.detectar_limite(p.texto_detectavel))
        self.assertFalse(p.erro or p.limite)


class Descricao(unittest.TestCase):
    def test_ferramentas(self):
        self.assertIn("Lendo", descrever_ferramenta("Read", {"file_path": "/a/b/c.py"}))
        self.assertIn("c.py", descrever_ferramenta("Edit", {"file_path": "/a/b/c.py"}))
        self.assertIn("git status", descrever_ferramenta("Bash", {"command": "git status"}))


if __name__ == "__main__":
    unittest.main()
