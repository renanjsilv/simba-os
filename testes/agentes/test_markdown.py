"""Divisão da resposta em blocos (texto, código, tabela) — base do layout do chat."""
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[2] / "pacotes/simba-apps/raiz/usr/share/simba-apps/agentes"
sys.path.insert(0, str(RAIZ))

from markdown import inline_para_markup, parse_blocos, parse_tabela  # noqa: E402

EXEMPLO = """## Título

Texto com `código`.

```python
print("oi")
```

| A | B |
|---|--:|
| 1 | 2 |

Fim."""


class Blocos(unittest.TestCase):
    def test_separa_texto_codigo_tabela(self):
        tipos = [b["tipo"] for b in parse_blocos(EXEMPLO)]
        self.assertEqual(tipos, ["texto", "codigo", "tabela", "texto"])
        codigo = parse_blocos(EXEMPLO)[1]
        self.assertEqual((codigo["lang"], codigo["conteudo"], codigo["aberto"]), ("python", 'print("oi")', False))

    def test_codigo_sendo_gerado_ja_e_codigo(self):
        parcial = "Veja:\n\n```bash\nsudo pacman -Syu\nls"
        b = parse_blocos(parcial)
        self.assertEqual([x["tipo"] for x in b], ["texto", "codigo"])
        self.assertTrue(b[1]["aberto"])
        self.assertEqual(b[1]["conteudo"], "sudo pacman -Syu\nls")

    def test_streaming_so_muda_o_ultimo_bloco(self):
        antes = parse_blocos(EXEMPLO[:60])
        depois = parse_blocos(EXEMPLO)
        for a, d in zip(antes[:-1], depois):
            self.assertEqual(a, d)

    def test_til_e_cerca_longa(self):
        b = parse_blocos("~~~\na\n~~~\n\n````md\n```\ndentro\n```\n````")
        self.assertEqual([x["tipo"] for x in b], ["codigo", "codigo"])
        self.assertIn("```", b[1]["conteudo"])

    def test_barra_vertical_sem_separador_nao_e_tabela(self):
        self.assertEqual([x["tipo"] for x in parse_blocos("| só uma linha |")], ["texto"])

    def test_tabela(self):
        cab, alinh, corpo = parse_tabela("| A | B |\n|:-:|--:|\n| 1 | `x|y` |")
        self.assertEqual(cab, ["A", "B"])
        self.assertEqual(alinh, ["centro", "direita"])
        self.assertEqual(corpo[0][0], "1")

    def test_markup_escapado(self):
        self.assertEqual(inline_para_markup("a < b **c** `d`"), "a &lt; b <b>c</b> <tt>d</tt>")
        self.assertIn('href="https://x.com"', inline_para_markup("[x](https://x.com)"))


if __name__ == "__main__":
    unittest.main()
