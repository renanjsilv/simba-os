#!/usr/bin/env python3
"""Calculadora do Simba OS — inspirada na do Windows 11 (GTK4/libadwaita).

Modos Padrão e Científica, memória (MC MR M+ M− MS), histórico que fica salvo,
prévia do resultado enquanto digita e teclado completo:
  0–9 , .  + - * / ^ % ( ) !   Enter/= calcula   Backspace apaga   Delete limpa a entrada
  Esc limpa tudo   Ctrl+C copia   Ctrl+V cola   Ctrl+H histórico   Ctrl+1/Ctrl+2 modo
As contas são feitas por motor.py (sem eval).
"""
import json
import re
import sys
from pathlib import Path

import gi
sys.path.insert(0, "/usr/share/simba-apps/idiomas")
from simba_i18n import t as _t, DECIMAL as _DEC  # noqa: E402  (traduções: /usr/share/simba-apps/idiomas)

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, GObject, Gtk, Pango  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motor as M  # noqa: E402

APP_ID = "com.simba.Calculadora"
ESTADO = Path(GLib.get_user_state_dir()) / "simba" / "calculadora.json"
MILHAR = "." if _DEC == "," else ","
OPS = "+−×÷^"
MAX_HISTORICO = 60

CSS = """
.calc-previa { font-size: 15px; opacity: 0.65; }
.calc-visor { font-weight: 600; }
.calc-visor.t1 { font-size: 42px; }
.calc-visor.t2 { font-size: 34px; }
.calc-visor.t3 { font-size: 27px; }
.calc-visor.t4 { font-size: 21px; }
.calc-erro { color: @error_color; opacity: 1; }
.calc-teclas button { border-radius: 6px; min-height: 42px; font-size: 17px; padding: 0; }
.calc-teclas button.num { background: alpha(@window_fg_color, 0.11); font-weight: 600; font-size: 19px; }
.calc-teclas button.num:hover { background: alpha(@window_fg_color, 0.16); }
.calc-teclas button.op { background: alpha(@window_fg_color, 0.05); }
.calc-teclas button.op:hover { background: alpha(@window_fg_color, 0.10); }
.calc-teclas button.ligado { background: alpha(@accent_bg_color, 0.35); }
.calc-teclas button.suggested-action { font-size: 21px; }
.calc-memoria button { font-size: 13px; font-weight: 600; min-height: 30px; padding: 0 4px; }
.calc-angulo { font-size: 12px; font-weight: 700; min-height: 26px; padding: 0 10px; }
.calc-indicador { font-size: 12px; font-weight: 700; opacity: 0.6; }
.calc-hist-expr { font-size: 13px; opacity: 0.65; }
.calc-hist-res { font-size: 20px; font-weight: 600; }
.calc-hist row { border-radius: 6px; margin: 2px 6px; padding: 8px 10px; }
"""


def exibir(expr):
    """Texto do visor: separador de milhar nos números (a expressão guardada não tem)."""
    def grupo(m):
        inteiro, frac = m.group(1), m.group(2) or ""
        g = []
        while len(inteiro) > 3:
            g.insert(0, inteiro[-3:])
            inteiro = inteiro[:-3]
        g.insert(0, inteiro)
        return MILHAR.join(g) + frac
    return re.sub(r"(\d+)([" + re.escape(_DEC) + r"]\d*)?", grupo, expr)


def legivel(v, milhar="", sig=15):
    """Número como o visor mostra: "−" no sinal e notação 1,5×10^−12 (que a conta entende)."""
    s = M.formatar(v, decimal=_DEC, milhar=milhar, sig=sig)
    if "e" in s:
        mant, exp = s.split("e")
        s = mant + "×10^" + exp
    return s.replace("-", "−")


def numero_cru(v):
    """Número para o visor/continuar a conta (sem separador de milhar)."""
    return legivel(v)


def inicio_operando(expr, fim=None):
    """Índice onde começa o último operando de expr[:fim] (None se não termina num operando)."""
    s = expr if fim is None else expr[:fim]
    i = len(s)
    while i > 0 and s[i - 1] in "!%":
        i -= 1
    if i == 0:
        return None
    c = s[i - 1]
    if c == ")":
        nivel, j = 0, i - 1
        while j >= 0:
            if s[j] == ")":
                nivel += 1
            elif s[j] == "(":
                nivel -= 1
                if nivel == 0:
                    break
            j -= 1
        if j < 0:
            return None
        while j > 0 and (s[j - 1].isalpha() or s[j - 1] == "√") and s[j - 1] not in "πe":
            j -= 1
        ini = j
    elif c.isdigit() or c == _DEC:
        j = i
        while j > 0 and (s[j - 1].isdigit() or s[j - 1] == _DEC):
            j -= 1
        ini = j
    elif c in "πe":
        ini = i - 1
    else:
        return None
    # base de uma potência faz parte do operando (2^3 inteiro)
    if ini > 0 and s[ini - 1] == "^":
        antes = inicio_operando(s, ini - 1)
        if antes is not None:
            ini = antes
    return ini


class Janela(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title=_t("Calculadora"))
        self.set_default_size(340, 560)
        self.set_size_request(300, 470)

        self.expr = ""
        # resultado de "=" com precisão total: o visor mostra 15 algarismos, mas a conta que
        # continua dele usa o valor inteiro (1÷3 = 0,333…, ×3 = 1; sen 30° = 0,5)
        self.base = None             # (texto no visor, texto com 17 algarismos)
        self.resultado = False       # visor mostra o resultado de "="
        self.erro = ""
        self.memoria = None
        self.segunda = False
        estado = self._ler_estado()
        self.modo = estado.get("modo", "padrao")
        self.graus = estado.get("graus", True)
        self.historico = estado.get("historico", [])[:MAX_HISTORICO]
        self.memoria = estado.get("memoria")

        # ── visor ──
        self.previa = Gtk.Label(xalign=1, ellipsize=Pango.EllipsizeMode.START, css_classes=["calc-previa"])
        self.previa.set_selectable(False)
        self.visor = Gtk.Label(xalign=1, ellipsize=Pango.EllipsizeMode.START, css_classes=["calc-visor", "t1"], label="0")
        caixa_visor = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin_start=14, margin_end=14,
                              margin_top=4, margin_bottom=6, vexpand=False)
        caixa_visor.append(self.previa)
        caixa_visor.append(self.visor)

        # ── memória ──
        self.linha_memoria = Gtk.Box(homogeneous=True, spacing=2, margin_start=6, margin_end=6, css_classes=["calc-memoria"])
        self.bot_mem = {}
        for rotulo, dica, f in (("MC", _t("Limpar memória"), self.mem_limpar), ("MR", _t("Recuperar memória"), self.mem_recuperar),
                                ("M+", _t("Somar à memória"), lambda: self.mem_somar(1)),
                                ("M−", _t("Subtrair da memória"), lambda: self.mem_somar(-1)),
                                ("MS", _t("Guardar na memória"), self.mem_guardar)):
            b = Gtk.Button(label=rotulo, tooltip_text=dica, css_classes=["flat"], focus_on_click=False, can_focus=False)
            b.connect("clicked", lambda _b, f=f: f())
            self.bot_mem[rotulo] = b
            self.linha_memoria.append(b)

        # ── linha da científica: graus/radianos + indicador de memória ──
        self.bot_angulo = Gtk.Button(css_classes=["flat", "calc-angulo"], focus_on_click=False, can_focus=False,
                                     tooltip_text=_t("Alternar entre graus e radianos"))
        self.bot_angulo.connect("clicked", lambda *_: self.alternar_angulo())
        self.ind_memoria = Gtk.Label(label="M", css_classes=["calc-indicador"], tooltip_text=_t("Há um valor na memória"))
        self.linha_cientifica = Gtk.Box(spacing=6, margin_start=8, margin_end=12)
        self.linha_cientifica.append(self.bot_angulo)
        self.linha_cientifica.append(Gtk.Box(hexpand=True))
        self.linha_cientifica.append(self.ind_memoria)

        # ── teclas ──
        self.teclas = Gtk.Grid(row_homogeneous=True, column_homogeneous=True, row_spacing=3, column_spacing=3,
                               margin_start=6, margin_end=6, margin_bottom=6, vexpand=True, css_classes=["calc-teclas"])

        corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        corpo.append(Gtk.Box(vexpand=True))      # o visor fica perto das teclas, como no Windows
        corpo.append(caixa_visor)
        corpo.append(self.linha_cientifica)
        corpo.append(self.linha_memoria)
        corpo.append(self.teclas)

        # ── histórico (painel lateral) ──
        self.lista_hist = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE, css_classes=["navigation-sidebar", "calc-hist"])
        self.lista_hist.connect("row-activated", self._usar_historico)
        self.vazio_hist = Adw.StatusPage(title=_t("Ainda não há histórico"), icon_name="document-open-recent-symbolic",
                                         css_classes=["compact"], vexpand=True)
        rolagem = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True)
        rolagem.set_child(self.lista_hist)
        self.pilha_hist = Gtk.Stack()
        self.pilha_hist.add_named(rolagem, "lista")
        self.pilha_hist.add_named(self.vazio_hist, "vazio")
        limpar = Gtk.Button(icon_name="user-trash-symbolic", tooltip_text=_t("Limpar histórico"), css_classes=["flat"],
                            halign=Gtk.Align.END, margin_end=8, margin_bottom=8)
        limpar.connect("clicked", lambda *_: self.limpar_historico())
        self.bot_limpar_hist = limpar
        lado = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        cab = Adw.HeaderBar(show_title=False)
        cab.set_title_widget(Gtk.Label(label=_t("Histórico"), css_classes=["heading"]))
        lado_tv = Adw.ToolbarView()
        lado_tv.add_top_bar(cab)
        lado.append(self.pilha_hist)
        lado.append(limpar)
        lado_tv.set_content(lado)

        # ── cabeçalho: modo e histórico ──
        self.grupo_modo = Adw.ToggleGroup(css_classes=["round"])
        self.grupo_modo.add(Adw.Toggle(name="padrao", label=_t("Padrão")))
        self.grupo_modo.add(Adw.Toggle(name="cientifica", label=_t("Científica")))
        self.grupo_modo.set_active_name(self.modo)
        self.grupo_modo.connect("notify::active-name", lambda g, _p: self.mudar_modo(g.get_active_name()))
        self.bot_hist = Gtk.ToggleButton(icon_name="document-open-recent-symbolic", tooltip_text=_t("Histórico (Ctrl+H)"))
        cabecalho = Adw.HeaderBar()
        cabecalho.set_title_widget(self.grupo_modo)
        cabecalho.pack_end(self.bot_hist)

        principal = Adw.ToolbarView()
        principal.add_top_bar(cabecalho)
        principal.set_content(corpo)

        self.divisao = Adw.OverlaySplitView(sidebar_position=Gtk.PackType.END, show_sidebar=False,
                                            min_sidebar_width=240, max_sidebar_width=300)
        self.divisao.set_content(principal)
        self.divisao.set_sidebar(lado_tv)
        self.bot_hist.bind_property("active", self.divisao, "show-sidebar",
                                    GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE)
        # janela estreita: o histórico abre por cima das teclas
        ponto = Adw.Breakpoint.new(Adw.BreakpointCondition.parse("max-width: 600sp"))
        ponto.add_setter(self.divisao, "collapsed", True)
        self.add_breakpoint(ponto)
        self.set_content(self.divisao)

        tecla = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        tecla.connect("key-pressed", self._tecla)
        self.add_controller(tecla)
        self.connect("close-request", lambda *_: self._salvar_estado() or False)

        self.montar_teclas()
        self.atualizar_historico()
        self.atualizar()

    # ── teclas ────────────────────────────────────────────────────────────────
    def _botao(self, rotulo, f, classe="op", dica=None):
        b = Gtk.Button(label=rotulo, hexpand=True, vexpand=True, focus_on_click=False, can_focus=False,
                       css_classes=[classe] if classe else [])
        if dica:
            b.set_tooltip_text(dica)
        b.connect("clicked", lambda *_: f())
        return b

    def montar_teclas(self):
        while (filho := self.teclas.get_first_child()) is not None:
            self.teclas.remove(filho)
        d = lambda c: (lambda: self.digito(c))          # noqa: E731
        o = lambda c: (lambda: self.operador(c))        # noqa: E731
        num = lambda c: (c, d(c), "num", None)          # noqa: E731
        igual = ("=", self.igual, "suggested-action", _t("Calcular (Enter)"))
        sinal = ("+/−", self.trocar_sinal, "num", _t("Trocar sinal"))
        virgula = (_DEC, self.virgula, "num", None)
        if self.modo == "cientifica":
            s = self.segunda
            linhas = [
                [("2ª", self.alternar_segunda, "ligado op" if s else "op", _t("Segunda função")),
                 ("π", lambda: self.constante("π"), "op", None), ("e", lambda: self.constante("e"), "op", None),
                 ("C", self.limpar_tudo, "op", _t("Limpar tudo (Esc)")), ("⌫", self.apagar, "op", _t("Apagar (Backspace)"))],
                [("x³" if s else "x²", (lambda: self.potencia_fixa(3)) if s else (lambda: self.potencia_fixa(2)), "op", None),
                 ("1/x", self.inverso, "op", _t("Inverso")), ("|x|", lambda: self.funcao("abs"), "op", _t("Valor absoluto")),
                 ("(", lambda: self.parentese("("), "op", None), (")", lambda: self.parentese(")"), "op", None)],
                [("√x", lambda: self.funcao("√"), "op", _t("Raiz quadrada")), ("xʸ", o("^"), "op", _t("Potência")),
                 ("n!", self.fatorial, "op", _t("Fatorial")), ("mod", self.modulo, "op", _t("Resto da divisão")),
                 ("÷", o("÷"), "op", None)],
                [("sen⁻¹" if s else "sen", lambda: self.funcao("asen" if self.segunda else "sen"), "op", None),
                 num("7"), num("8"), num("9"), ("×", o("×"), "op", None)],
                [("cos⁻¹" if s else "cos", lambda: self.funcao("acos" if self.segunda else "cos"), "op", None),
                 num("4"), num("5"), num("6"), ("−", o("−"), "op", None)],
                [("tg⁻¹" if s else "tg", lambda: self.funcao("atg" if self.segunda else "tg"), "op", None),
                 num("1"), num("2"), num("3"), ("+", o("+"), "op", None)],
                [("ln" if s else "log", lambda: self.funcao("ln" if self.segunda else "log"), "op",
                  _t("Logaritmo natural") if s else _t("Logaritmo na base 10")),
                 sinal, num("0"), virgula, igual],
            ]
        else:
            linhas = [
                [("%", self.porcento, "op", _t("Porcentagem")), ("CE", self.limpar_entrada, "op", _t("Limpar entrada (Delete)")),
                 ("C", self.limpar_tudo, "op", _t("Limpar tudo (Esc)")), ("⌫", self.apagar, "op", _t("Apagar (Backspace)"))],
                [("1/x", self.inverso, "op", _t("Inverso")), ("x²", lambda: self.potencia_fixa(2), "op", _t("Quadrado")),
                 ("√x", lambda: self.funcao("√"), "op", _t("Raiz quadrada")), ("÷", o("÷"), "op", None)],
                [num("7"), num("8"), num("9"), ("×", o("×"), "op", None)],
                [num("4"), num("5"), num("6"), ("−", o("−"), "op", None)],
                [num("1"), num("2"), num("3"), ("+", o("+"), "op", None)],
                [sinal, num("0"), virgula, igual],
            ]
        for r, linha in enumerate(linhas):
            for c, (rotulo, f, classe, dica) in enumerate(linha):
                b = self._botao(rotulo, f, None, dica)
                for k in classe.split():
                    b.add_css_class(k)
                self.teclas.attach(b, c, r, 1, 1)
        self.linha_cientifica.set_visible(self.modo == "cientifica")

    # ── edição da expressão ───────────────────────────────────────────────────
    def _novo_se_resultado(self, continuar):
        """Depois de "=": um número começa conta nova; um operador continua do resultado."""
        if self.resultado:
            self.resultado = False
            if not continuar:
                self.expr = ""
        self.erro = ""

    def digito(self, c):
        self._novo_se_resultado(False)
        # sem zeros à esquerda: um número que é só "0" é trocado pelo dígito novo
        m = re.search(r"(?<![\d" + re.escape(_DEC) + r"])0$", self.expr)
        if m:
            self.expr = self.expr[:-1]
        self.expr += c
        self.atualizar()

    def virgula(self):
        self._novo_se_resultado(False)
        m = re.search(r"[\d" + re.escape(_DEC) + r"]*$", self.expr)
        atual = m.group(0) if m else ""
        if _DEC in atual:
            return
        self.expr += _DEC if atual else "0" + _DEC
        self.atualizar()

    def operador(self, op):
        self._novo_se_resultado(True)
        e = self.expr
        if e.endswith(" mod "):
            e = e[:-5]
        if not e:
            e = "" if op == "−" else "0"
        elif e[-1] == "(":
            if op != "−":
                return
        elif e[-1] in OPS:
            if op == "−" and e[-1] in "×÷^":
                pass                                  # 2×−3
            else:
                while e and e[-1] in OPS:
                    e = e[:-1]
                if not e:
                    e = "" if op == "−" else "0"
        self.expr = e + op
        self.atualizar()

    def modulo(self):
        self._novo_se_resultado(True)
        if inicio_operando(self.expr) is None:
            return
        self.expr += " mod "
        self.atualizar()

    def parentese(self, p):
        self._novo_se_resultado(p == ")")
        if p == ")":
            if self.expr.count("(") <= self.expr.count(")") or self.expr[-1:] in OPS + "(":
                return
        self.expr += p
        self.atualizar()

    def constante(self, c):
        self._novo_se_resultado(False)
        self.expr += c
        self.atualizar()

    def _envolver(self, antes, depois=")"):
        """Aplica a função ao último operando (como no Windows), ou abre a função."""
        self._novo_se_resultado(True)
        i = inicio_operando(self.expr)
        if i is None:
            self.expr += antes
        else:
            self.expr = self.expr[:i] + antes + self.expr[i:] + depois
        self.atualizar()

    def funcao(self, nome):
        self._envolver(nome + "(")
        if self.segunda and self.modo == "cientifica":
            self.alternar_segunda()

    def inverso(self):
        self._envolver("1÷(")

    def potencia_fixa(self, n):
        self._novo_se_resultado(True)
        if inicio_operando(self.expr) is None:
            return
        self.expr += "^" + str(n)
        self.atualizar()

    def fatorial(self):
        self._novo_se_resultado(True)
        if inicio_operando(self.expr) is None:
            return
        self.expr += "!"
        self.atualizar()

    def porcento(self):
        self._novo_se_resultado(True)
        if inicio_operando(self.expr) is None:
            return
        self.expr += "%"
        self.atualizar()

    def trocar_sinal(self):
        self._novo_se_resultado(True)
        i = inicio_operando(self.expr)
        if i is None:
            self.expr += "−"
        else:
            op = self.expr[i:]
            if op.startswith("(−") and op.endswith(")") and inicio_operando(op[1:-1].lstrip("−") or "x") is not None \
                    and op.count("(") == 1:
                self.expr = self.expr[:i] + op[2:-1]
            else:
                self.expr = self.expr[:i] + "(−" + op + ")"
        self.atualizar()

    def apagar(self):
        if self.resultado:
            self.resultado = False
            self.erro = ""
            self.atualizar()
            return
        self.erro = ""
        e = self.expr
        m = re.search(r"(asen|acos|atg|sen|cos|tg|log|ln|abs|√)\($| mod $", e)
        self.expr = e[:m.start()] if m else e[:-1]
        self.atualizar()

    def limpar_entrada(self):
        if self.resultado or self.erro:
            self.limpar_tudo()
            return
        i = inicio_operando(self.expr)
        if i is not None:
            self.expr = self.expr[:i]
        self.atualizar()

    def limpar_tudo(self):
        self.expr = ""
        self.resultado = False
        self.erro = ""
        self.atualizar()

    def alternar_segunda(self):
        self.segunda = not self.segunda
        self.montar_teclas()

    def alternar_angulo(self):
        self.graus = not self.graus
        self.atualizar()

    def mudar_modo(self, modo):
        if not modo or modo == self.modo:
            return
        self.modo = modo
        self.segunda = False
        self.montar_teclas()
        self.atualizar()
        self._salvar_estado()

    # ── contas ────────────────────────────────────────────────────────────────
    def _fechada(self):
        e = self.expr.rstrip()
        if e.endswith(" mod"):
            e = e[:-4]
        while e and e[-1] in OPS + "(":
            e = e[:-1]
        return e + ")" * max(0, e.count("(") - e.count(")"))

    def _para_calculo(self, conta):
        """Troca o resultado anterior (como aparece) pelo valor completo, se a conta parte dele."""
        if self.base:
            texto, preciso = self.base
            resto = conta[len(texto):]
            if conta.startswith(texto) and not (resto[:1].isdigit() or resto[:1] == _DEC):
                return preciso + resto
        return conta

    def valor_atual(self):
        """Valor do que está no visor (resultado ou conta em andamento)."""
        try:
            return M.calcular(self._para_calculo(self._fechada() or "0"), self.graus)
        except M.ErroCalculo:
            return None

    def igual(self):
        if self.resultado or not self.expr:
            return
        conta = self._fechada()
        try:
            v = M.calcular(self._para_calculo(conta), self.graus)
        except M.ErroCalculo as e:
            self.erro = _t(str(e))
            self.atualizar()
            return
        res = numero_cru(v)
        self.base = (res, legivel(v, sig=17))
        self.historico.insert(0, {"expr": conta, "res": res})
        del self.historico[MAX_HISTORICO:]
        self.ultima = conta
        self.expr = res
        self.resultado = True
        self.erro = ""
        self.atualizar_historico()
        self.atualizar()
        self._salvar_estado()

    # ── memória ───────────────────────────────────────────────────────────────
    def mem_guardar(self):
        v = self.valor_atual()
        if v is not None:
            self.memoria = v
            self.atualizar()

    def mem_somar(self, sinal):
        v = self.valor_atual()
        if v is not None:
            self.memoria = (self.memoria or 0) + sinal * v
            self.atualizar()

    def mem_limpar(self):
        self.memoria = None
        self.atualizar()

    def mem_recuperar(self):
        if self.memoria is None:
            return
        self._inserir_numero(numero_cru(self.memoria))

    def _inserir_numero(self, n):
        """Põe um número no visor: substitui o operando atual ou continua depois de um operador."""
        if self.resultado:
            self.expr = ""
            self.resultado = False
        self.erro = ""
        i = inicio_operando(self.expr)
        if i is not None:
            self.expr = self.expr[:i]
        if n.startswith("−"):
            n = "(" + n + ")"
        self.expr += n
        self.atualizar()

    # ── histórico ─────────────────────────────────────────────────────────────
    def atualizar_historico(self):
        while (r := self.lista_hist.get_first_child()) is not None:
            self.lista_hist.remove(r)
        for h in self.historico:
            caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            caixa.append(Gtk.Label(label=exibir(h["expr"]) + " =", xalign=1, wrap=True,
                                   wrap_mode=Pango.WrapMode.CHAR, css_classes=["calc-hist-expr"]))
            caixa.append(Gtk.Label(label=exibir(h["res"]), xalign=1, wrap=True,
                                   wrap_mode=Pango.WrapMode.CHAR, css_classes=["calc-hist-res"]))
            linha = Gtk.ListBoxRow(child=caixa, activatable=True)
            linha.res = h["res"]
            linha.conta = h["expr"]
            self.lista_hist.append(linha)
        self.pilha_hist.set_visible_child_name("lista" if self.historico else "vazio")
        self.bot_limpar_hist.set_sensitive(bool(self.historico))

    def _usar_historico(self, _lista, linha):
        self.expr = linha.res
        self.ultima = linha.conta
        self.resultado = True
        self.erro = ""
        self.atualizar()
        if self.divisao.get_collapsed():
            self.bot_hist.set_active(False)

    def limpar_historico(self):
        self.historico = []
        self.atualizar_historico()
        self._salvar_estado()

    # ── visor ─────────────────────────────────────────────────────────────────
    def atualizar(self):
        texto = exibir(self.expr) if self.expr else "0"
        self.visor.set_label(texto)
        n = len(texto)
        for k in ("t1", "t2", "t3", "t4"):
            self.visor.remove_css_class(k)
        self.visor.add_css_class("t1" if n <= 11 else "t2" if n <= 15 else "t3" if n <= 21 else "t4")

        self.previa.remove_css_class("calc-erro")
        if self.erro:
            self.previa.set_label(self.erro)
            self.previa.add_css_class("calc-erro")
        elif self.resultado:
            self.previa.set_label(exibir(getattr(self, "ultima", "")) + " =")
        else:
            prev = ""
            if re.search(r"[" + re.escape(OPS) + r"(!%√]|mod|[a-z]\(", self.expr.lstrip("−")):
                v = self.valor_atual()
                if v is not None:
                    prev = "= " + legivel(v, MILHAR)
            self.previa.set_label(prev)

        self.bot_angulo.set_label(_t("GRAUS") if self.graus else _t("RAD"))
        tem = self.memoria is not None
        self.bot_mem["MC"].set_sensitive(tem)
        self.bot_mem["MR"].set_sensitive(tem)
        self.ind_memoria.set_visible(tem)

    # ── teclado ───────────────────────────────────────────────────────────────
    def _tecla(self, _c, keyval, _code, estado):
        ctrl = estado & Gdk.ModifierType.CONTROL_MASK
        nome = Gdk.keyval_name(keyval) or ""
        ch = chr(Gdk.keyval_to_unicode(keyval)) if Gdk.keyval_to_unicode(keyval) else ""
        if ctrl:
            if nome in ("c", "C"):
                self.copiar()
            elif nome in ("v", "V"):
                self.colar()
            elif nome in ("h", "H"):
                self.bot_hist.set_active(not self.bot_hist.get_active())
            elif nome == "1":
                self.grupo_modo.set_active_name("padrao")
            elif nome == "2":
                self.grupo_modo.set_active_name("cientifica")
            else:
                return False
            return True
        if nome in ("Return", "KP_Enter") or ch == "=":
            self.igual()
        elif nome == "BackSpace":
            self.apagar()
        elif nome == "Escape":
            self.limpar_tudo()
        elif nome in ("Delete", "KP_Delete"):
            self.limpar_entrada()
        elif ch.isdigit():
            self.digito(ch)
        elif ch in ",." or nome in ("KP_Decimal", "KP_Separator"):
            self.virgula()
        elif ch == "+":
            self.operador("+")
        elif ch == "-":
            self.operador("−")
        elif ch in "*x":
            self.operador("×")
        elif ch == "/":
            self.operador("÷")
        elif ch == "^":
            self.operador("^")
        elif ch == "%":
            self.porcento()
        elif ch in "()":
            self.parentese(ch)
        elif ch == "!":
            self.fatorial()
        elif ch == "p":
            self.constante("π")
        else:
            return False
        return True

    def copiar(self):
        v = self.valor_atual() if not self.erro else None
        if v is None:
            return
        self.get_clipboard().set(M.formatar(v, decimal=_DEC, milhar=""))   # formato comum (planilhas)
        self.previa.set_label(_t("Copiado"))

    def colar(self):
        def pronto(cb, res):
            try:
                t = cb.read_text_finish(res) or ""
            except GLib.Error:
                return
            t = t.strip().replace(" ", "").replace(" ", "")
            # tira o separador de milhar do idioma e usa a vírgula/ponto decimal dele
            if MILHAR in t and _DEC in t:
                t = t.replace(MILHAR, "")
            t = (t.replace("*", "×").replace("/", "÷").replace("-", "−")
                 .replace(".", _DEC).replace(",", _DEC))
            if not t or not re.fullmatch(r"[\d" + re.escape(_DEC) + re.escape(OPS) + r"()%!πe]+", t):
                self.previa.set_label(_t("Não é um número ou conta válida"))
                return
            if self.resultado:
                self.expr, self.resultado = "", False
            self.erro = ""
            self.expr += t
            self.atualizar()
        self.get_clipboard().read_text_async(None, pronto)

    # ── estado salvo ──────────────────────────────────────────────────────────
    def _ler_estado(self):
        try:
            return json.loads(ESTADO.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _salvar_estado(self):
        try:
            ESTADO.parent.mkdir(parents=True, exist_ok=True)
            tmp = ESTADO.with_suffix(".tmp")
            tmp.write_text(json.dumps({"modo": self.modo, "graus": self.graus, "memoria": self.memoria,
                                       "historico": self.historico}, ensure_ascii=False), encoding="utf-8")
            tmp.replace(ESTADO)
        except OSError:
            pass


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.janela = None

    def do_startup(self):
        Adw.Application.do_startup(self)
        css = Gtk.CssProvider()
        css.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        sair = Gio.SimpleAction.new("sair", None)
        sair.connect("activate", lambda *_: self.janela and self.janela.close())
        self.add_action(sair)
        self.set_accels_for_action("app.sair", ["<Control>q", "<Control>w"])

    def do_activate(self):
        if self.janela is None:
            self.janela = Janela(self)
        self.janela.present()


if __name__ == "__main__":
    sys.exit(App().run(sys.argv))
