"""Skills: leitura do cabeçalho do SKILL.md e nomes seguros."""
import os, sys, unittest
D = os.path.join(os.path.dirname(__file__), "../../pacotes/simba-apps/raiz/usr/share/simba-apps/agentes")
sys.path.insert(0, os.path.abspath(D))
import skills  # noqa: E402


class TestSkills(unittest.TestCase):
    def test_cabecalho(self):
        t = "---\nname: pdf\ndescription: >\n  Lê e cria PDFs\n  com tabelas\nlicense: MIT\n---\n# corpo"
        c = skills.cabecalho(t)
        self.assertEqual(c["name"], "pdf")
        self.assertEqual(c["description"], "Lê e cria PDFs com tabelas")

    def test_sem_cabecalho(self):
        self.assertEqual(skills.cabecalho("# só texto"), {})

    def test_filtrar_pastas(self):
        f = skills._filtrar_pastas
        self.assertEqual(f([".agents/skills/rea", ".cursor-plugin/skills/rea", "skills/.curated/pdf"]),
                         [".agents/skills/rea", "skills/.curated/pdf"])
        self.assertEqual(f(["skills/test-driven-development", "tests/fixtures/x", "examples/y",
                            "node_modules/z/w", ".git/q"]), ["skills/test-driven-development"])

    def test_nome_seguro(self):
        self.assertEqual(skills._nome_seguro("Minha Skill"), "minha-skill")
        self.assertNotIn("/", skills._nome_seguro("a/b"))
        self.assertTrue(skills._nome_seguro("..."))


if __name__ == "__main__":
    unittest.main()
