"""Motor da Calculadora: analisa e calcula expressões sem eval().

Gramática (precedência crescente):
    soma     := produto (('+' | '-') produto)*
    produto  := unario (('×' | '÷' | 'mod') unario)*      (multiplicação implícita: 2π, 3(4), (1)(2))
    unario   := ('-' | '+') unario | potencia
    potencia := posfixo ('^' unario)?                      (à direita: 2^3^2 = 2^9)
    posfixo  := atomo ('!' | '%')*
    atomo    := número | 'π' | 'e' | função '(' soma ')' | '(' soma ')'

Porcentagem como no Windows: "a + b%" e "a − b%" usam b% de a (200 + 10% = 220);
em qualquer outro lugar b% é b/100 (50 × 10% = 5).
"""
import math

FUNCOES = ("sen", "cos", "tg", "asen", "acos", "atg", "ln", "log", "raiz", "abs")
OPERADORES = "+-×÷^!%()"


class ErroCalculo(Exception):
    """Mensagem já pronta para mostrar (o app traduz)."""


def tokens(texto, decimal=","):
    """Quebra o texto em fichas: números (float), operadores, funções e constantes."""
    s = (texto.replace("*", "×").replace("/", "÷").replace("−", "-").replace("√", "raiz")
         .replace("pi", "π").replace("sin", "sen").replace("tan", "tg"))
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c.isdigit() or c in ".,":
            j, visto = i, False
            while j < len(s) and (s[j].isdigit() or s[j] in ".,"):
                if s[j] in ".,":
                    if visto:
                        raise ErroCalculo("Número inválido")
                    visto = True
                j += 1
            bruto = s[i:j].replace(",", ".")
            if bruto == ".":
                raise ErroCalculo("Número inválido")
            out.append(float(bruto))
            i = j
            continue
        if c in OPERADORES or c in "π":
            out.append(c)
            i += 1
            continue
        if c == "e":
            out.append("e")
            i += 1
            continue
        for nome in sorted(FUNCOES + ("mod",), key=len, reverse=True):
            if s.startswith(nome, i):
                out.append(nome)
                i += len(nome)
                break
        else:
            raise ErroCalculo("Expressão inválida")
    return out


class _Analisador:
    def __init__(self, fichas, graus):
        self.f = fichas
        self.i = 0
        self.graus = graus

    def ver(self):
        return self.f[self.i] if self.i < len(self.f) else None

    def pegar(self):
        t = self.ver()
        self.i += 1
        return t

    def soma(self):
        v, _ = self.produto()
        while self.ver() in ("+", "-"):
            op = self.pegar()
            d, pct = self.produto()
            if pct is not None:          # a ± b%  →  a ± a·b/100
                d = v * pct / 100
            v = v + d if op == "+" else v - d
        return v

    def produto(self):
        """Devolve (valor, b) — b = o número antes de '%' quando o termo é só "b%"."""
        v, pct = self.unario()
        while True:
            t = self.ver()
            if t in ("×", "÷", "mod"):
                self.pegar()
                d, _ = self.unario()
                if t == "×":
                    v = v * d
                elif t == "÷":
                    if d == 0:
                        raise ErroCalculo("Não é possível dividir por zero")
                    v = v / d
                else:
                    if d == 0:
                        raise ErroCalculo("Não é possível dividir por zero")
                    v = math.fmod(v, d)
                pct = None
            elif isinstance(t, float) or t in ("(", "π", "e") or t in FUNCOES:
                d, _ = self.unario()      # multiplicação implícita
                v = v * d
                pct = None
            else:
                return v, pct

    def unario(self):
        t = self.ver()
        if t in ("-", "+"):
            self.pegar()
            v, pct = self.unario()
            return (-v if t == "-" else v), (None if pct is None else (-pct if t == "-" else pct))
        return self.potencia()

    def potencia(self):
        v, pct = self.posfixo()
        if self.ver() == "^":
            self.pegar()
            e, _ = self.unario()
            try:
                r = math.pow(v, e)
            except (OverflowError, ValueError):
                raise ErroCalculo("Resultado indefinido")
            return r, None
        return v, pct

    def posfixo(self):
        v = self.atomo()
        pct = None
        while self.ver() in ("!", "%"):
            if self.pegar() == "!":
                if v < 0 or v != int(v):
                    raise ErroCalculo("Fatorial só de inteiros não negativos")
                if v > 170:
                    raise ErroCalculo("Resultado grande demais")
                v = float(math.factorial(int(v)))
                pct = None
            else:
                pct = v
                v = v / 100
        return v, pct

    def atomo(self):
        t = self.pegar()
        if t is None:
            raise ErroCalculo("Expressão incompleta")
        if isinstance(t, float):
            return t
        if t == "π":
            return math.pi
        if t == "e":
            return math.e
        if t == "(":
            v = self.soma()
            if self.ver() == ")":
                self.pegar()
            return v                      # parêntese aberto no fim fecha sozinho
        if t in FUNCOES:
            if self.ver() == "(":
                self.pegar()
                x = self.soma()
                if self.ver() == ")":
                    self.pegar()
            else:
                x, _ = self.unario()
            return self.funcao(t, x)
        raise ErroCalculo("Expressão inválida")

    def funcao(self, nome, x):
        rad = math.radians if self.graus else (lambda a: a)
        deg = math.degrees if self.graus else (lambda a: a)
        try:
            if nome == "sen":
                return _limpo(math.sin(rad(x)))
            if nome == "cos":
                return _limpo(math.cos(rad(x)))
            if nome == "tg":
                if self.graus and math.fmod(abs(x), 180) == 90:
                    raise ErroCalculo("Entrada inválida")
                return _limpo(math.tan(rad(x)))
            if nome == "asen":
                return deg(math.asin(x))
            if nome == "acos":
                return deg(math.acos(x))
            if nome == "atg":
                return deg(math.atan(x))
            if nome == "ln":
                return math.log(x)
            if nome == "log":
                return math.log10(x)
            if nome == "raiz":
                return math.sqrt(x)
            if nome == "abs":
                return abs(x)
        except ValueError:
            raise ErroCalculo("Entrada inválida")
        raise ErroCalculo("Expressão inválida")


def _limpo(v):
    """sen(180°) dá 1,2e-16 em ponto flutuante: arredonda o ruído para zero."""
    return 0.0 if abs(v) < 1e-12 else v


def calcular(texto, graus=True):
    fichas = tokens(texto)
    if not fichas:
        raise ErroCalculo("Expressão vazia")
    a = _Analisador(fichas, graus)
    v = a.soma()
    if a.ver() is not None:
        raise ErroCalculo("Expressão inválida")
    if math.isnan(v) or math.isinf(v):
        raise ErroCalculo("Resultado indefinido")
    return v


def formatar(v, decimal=",", milhar=".", sig=15):
    """`sig` algarismos significativos (15 (some com o ruído 0,1+0,2), separador de milhar."""
    if v == 0:
        return "0"
    if abs(v) >= 1e16 or abs(v) < 1e-9:
        m, e = f"{v:.12e}".split("e")
        m = m.rstrip("0").rstrip(".")
        return m.replace(".", decimal) + "e" + str(int(e))
    s = f"{v:.{sig}g}"
    if "e" in s:
        s = f"{v:.15f}".rstrip("0").rstrip(".")
    neg = s.startswith("-")
    s = s.lstrip("-")
    inteiro, _, frac = s.partition(".")
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    r = milhar.join(grupos) + (decimal + frac if frac else "")
    return ("-" if neg else "") + r
