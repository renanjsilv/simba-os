"""Bloco "Pensando": o que a IA raciocinou e executou durante uma resposta.

Enquanto o agente trabalha, o cabeçalho mostra o passo atual (com brilho) e um
cronômetro; clicar abre a linha do tempo: raciocínio, passos com ícone por tipo e
cartões para o que mexe na máquina (comandos e edições de arquivo, com a saída).
Ao terminar, recolhe para "Pensou por 1 min 20 s · 7 passos".

Leve de propósito: recolhido, o bloco não cria nenhuma linha; aberto, mostra só
os últimos passos (os anteriores entram sob demanda) e os detalhes de cada cartão
só são montados quando abertos. As animações param com a resposta.
"""
from html import escape
from pathlib import Path
import re
import sys
import time
import weakref

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Adw, Gdk, GLib, Graphene, Gsk, Gtk, Pango  # noqa: E402

sys.path.insert(0, "/usr/share/simba-apps/idiomas")
from simba_i18n import t as _t  # noqa: E402

ICONES = {
    "comando": "utilities-terminal-symbolic",
    "leitura": "text-x-generic-symbolic",
    "edicao": "document-edit-symbolic",
    "busca": "edit-find-symbolic",
    "web": "web-browser-symbolic",
    "subagente": "system-users-symbolic",
    "fundo": "document-open-recent-symbolic",
    "tarefas": "view-list-bullet-symbolic",
    "pensamento": "weather-few-clouds-symbolic",
    "outro": "applications-engineering-symbolic",
}
CARTOES = ("comando", "edicao")
LIMITE_LINHAS = 40        # passos visíveis de uma vez em cada nível da linha do tempo
MAX_PASSOS = 600          # passos guardados por resposta (o resto só é contado)
ORCAMENTO_SAIDA = 200000  # caracteres de saída guardados por resposta
PREVIA_SAIDA = 12         # linhas de saída antes do "mostrar mais"
PREVIA_DIFF = 10
MAX_RACIOCINIO = 40000

_repintaveis = weakref.WeakSet()   # linhas com cores que dependem do tema claro/escuro
_tema_ligado = False


def animacoes():
    """Preferência do sistema: False = reduzir animações."""
    cfg = Gtk.Settings.get_default()
    return bool(cfg.get_property("gtk-enable-animations")) if cfg else True


def duracao(seg):
    """12 → '12 s'; 80 → '1 min 20 s'; 3700 → '1 h 01 min'."""
    seg = max(0, int(round(seg)))
    if seg < 60:
        return f"{seg} s"
    m, s = divmod(seg, 60)
    if m < 60:
        return f"{m} min {s:02d} s" if s else f"{m} min"
    h, m = divmod(m, 60)
    return f"{h} h {m:02d} min"


def _milhar(n):
    n = int(n or 0)
    return f"{n / 1000:.0f}k" if n >= 1000 else str(n)


def _escuro():
    return Adw.StyleManager.get_default().get_dark()


def _paleta():
    # comandos e diffs ficam num fundo escuro de terminal nos dois temas
    if True:
        return {"cmd": "#78aeed", "txt": "#8ff0a4", "opc": "#ffbe6f", "var": "#dc8add", "apagado": "#9a9996",
                "mais": "#8ff0a4", "menos": "#ff7b63"}
    return {"cmd": "#1a5fb4", "txt": "#1b7a4b", "opc": "#8f4700", "var": "#813d9c", "apagado": "#77767b",
            "mais": "#1b7a4b", "menos": "#c01c28"}


_SHELL = re.compile(
    r"(?P<com>(?:(?<=\s)|^)#[^\n]*)"
    r"|(?P<txt>'[^']*'|\"(?:[^\"\\]|\\.)*\")"
    r"|(?P<var>\$\{[^}]*\}|\$\w+)"
    r"|(?P<op>&&|\|\||[|;&]|\d?>>?|<)"
    r"|(?P<opc>(?:(?<=\s)|^)-{1,2}[\w][\w-]*)"
    r"|(?P<pal>[^\s'\"$|;&<>]+)"
    r"|(?P<esp>\s+)"
    r"|(?P<resto>.)", re.S)
_PREFIXOS = ("sudo", "env", "time", "nohup", "exec", "then", "do", "else", "if", "while", "!")


def realce_shell(comando):
    """Comando de terminal → markup do Pango (nome do comando, opções, textos, operadores)."""
    cor = _paleta()
    saida, inicio = [], True
    for m in _SHELL.finditer(comando):
        tipo, tok = m.lastgroup, escape(m.group(0), quote=False)
        if tipo == "com":
            saida.append(f'<span foreground="{cor["apagado"]}" style="italic">{tok}</span>')
        elif tipo == "txt":
            saida.append(f'<span foreground="{cor["txt"]}">{tok}</span>')
            inicio = False
        elif tipo == "var":
            saida.append(f'<span foreground="{cor["var"]}">{tok}</span>')
            inicio = False
        elif tipo == "op":
            saida.append(f'<span foreground="{cor["apagado"]}">{tok}</span>')
            inicio = m.group(0) in ("&&", "||", "|", ";", "&")
        elif tipo == "opc":
            saida.append(f'<span foreground="{cor["opc"]}">{tok}</span>')
        elif tipo == "pal":
            palavra = m.group(0)
            if inicio and "=" in palavra and not palavra.startswith("="):
                saida.append(tok)                       # VAR=valor antes do comando
            elif inicio:
                saida.append(f'<span foreground="{cor["cmd"]}" weight="bold">{tok}</span>')
                inicio = palavra in _PREFIXOS
            else:
                saida.append(tok)
        else:
            saida.append(tok)
            if tipo == "esp" and "\n" in m.group(0):
                inicio = True
    return "".join(saida)


def realce_diff(linhas):
    """Linhas de diff ('+', '-', ' ', '⋯') → markup do Pango."""
    cor = _paleta()
    saida = []
    for l in linhas:
        tok = escape(l[1:] if l[:1] in "+- " else l, quote=False)
        if l.startswith("+"):
            saida.append(f'<span foreground="{cor["mais"]}">+ {tok}</span>')
        elif l.startswith("-"):
            saida.append(f'<span foreground="{cor["menos"]}">− {tok}</span>')
        elif l == "⋯":
            saida.append(f'<span foreground="{cor["apagado"]}">  ⋯</span>')
        else:
            saida.append(f'<span foreground="{cor["apagado"]}">  {tok}</span>')
    return "\n".join(saida)


def passos_de_atividade(atividade):
    """Conversas antigas guardavam só textos de status: vira uma lista de passos simples."""
    prefixos = (
        (_t("Executando:"), "comando"), (_t("Lendo:"), "leitura"), (_t("Listando:"), "leitura"),
        (_t("Editando:"), "edicao"), (_t("Pesquisando na web:"), "web"), (_t("Abrindo:"), "web"),
        (_t("Procurando:"), "busca"), (_t("Subagente:"), "subagente"),
        (_t("Em segundo plano:"), "fundo"), (_t("Segundo plano:"), "fundo"),
        (_t("Atualizando a lista de tarefas"), "tarefas"),
    )
    passageiros = (_t("✦ Pensando..."), _t("✦ Pensando na resposta..."), _t("Enviando o pedido ao modelo…"),
                   _t("Executando ações..."), _t("Subagente trabalhando em segundo plano:"),
                   _t("Aguardando em segundo plano:"))
    passos, subagente, vistos = [], None, set()
    for i, texto in enumerate(atividade or []):
        texto = str(texto or "").strip()
        if not texto or texto.startswith(passageiros) or texto.startswith("✦"):
            continue
        filho = texto.startswith("↳ ")
        if filho:
            texto = texto[2:].strip()
        tipo = next((t for p, t in prefixos if texto.startswith(p)), "outro")
        if tipo == "subagente":
            if " · " in texto:      # progresso do mesmo subagente ("… · 3 ações · 15k tokens")
                continue
            if texto in vistos:
                continue
            vistos.add(texto)
        p = {"id": f"a{i}", "tipo": tipo, "texto": texto, "simples": True}
        if filho and subagente:
            p["pai"] = subagente
        elif tipo == "subagente":
            subagente = p["id"]
        passos.append(p)
    return passos


def markup_pensamento(texto):
    """Raciocínio em markdown simples → markup do Pango (negrito, itálico, código, títulos)."""
    saida = []
    for linha in str(texto or "").strip("\n").split("\n"):
        l = escape(linha, quote=False)
        l = re.sub(r"^#{1,6}\s+(.*)$", r"<b>\1</b>", l)
        l = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", l)
        l = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", l)
        l = re.sub(r"`([^`]+)`", r"<tt>\1</tt>", l)
        l = re.sub(r"^(\s*)[-*]\s+", r"\1• ", l)
        saida.append(l)
    return "\n".join(saida)


def _rotulo(texto="", classes=(), **kw):
    lbl = Gtk.Label(label=texto, xalign=0, **kw)
    for c in classes:
        lbl.add_css_class(c)
    return lbl


def _acessivel(widget, texto):
    widget.update_property([Gtk.AccessibleProperty.LABEL], [texto])


def _ligar_tema():
    """Uma vez: ao trocar claro/escuro, refaz as cores dos comandos e diffs à vista."""
    global _tema_ligado
    if _tema_ligado:
        return
    _tema_ligado = True
    Adw.StyleManager.get_default().connect(
        "notify::dark", lambda *_: [w.repintar() for w in list(_repintaveis)])


# ── rótulo com brilho ───────────────────────────────────────────────────────
class RotuloBrilho(Gtk.Label):
    """Rótulo cujo texto recebe uma faixa de luz passando (shimmer) enquanto `brilhar(True)`.

    O quadro só é redesenhado enquanto o rótulo está na tela (relógio de quadros do
    GTK) e a ~30 fps; com as animações do sistema desligadas, fica um texto parado.
    """
    __gtype_name__ = "SimbaRotuloBrilho"
    PERIODO = 1_700_000  # µs para a faixa atravessar o texto

    def __init__(self, **kw):
        super().__init__(**kw)
        self._ativo = False
        self._tick = 0
        self._fase = 0.0
        self._ultimo = 0

    def brilhar(self, ativo):
        ativo = bool(ativo) and animacoes()
        if ativo == self._ativo:
            return
        self._ativo = ativo
        if ativo:
            self._tick = self.add_tick_callback(self._tique)
        elif self._tick:
            self.remove_tick_callback(self._tick)
            self._tick = 0
        self.queue_draw()

    def _tique(self, _w, relogio):
        agora = relogio.get_frame_time()
        if agora - self._ultimo >= 33000:
            self._ultimo = agora
            self._fase = (agora % self.PERIODO) / self.PERIODO
            self.queue_draw()
        return True

    def do_snapshot(self, snapshot):
        larg, alt = self.get_width(), self.get_height()
        if not self._ativo or larg <= 0 or alt <= 0:
            Gtk.Label.do_snapshot(self, snapshot)
            return
        snapshot.push_mask(Gsk.MaskMode.ALPHA)
        Gtk.Label.do_snapshot(self, snapshot)
        snapshot.pop()
        cor = self.get_color()
        fraca, forte = Gdk.RGBA(), Gdk.RGBA()
        fraca.red, fraca.green, fraca.blue, fraca.alpha = cor.red, cor.green, cor.blue, 0.42
        forte.red, forte.green, forte.blue, forte.alpha = cor.red, cor.green, cor.blue, 1.0
        faixa = max(70.0, larg * 0.22)
        centro = -faixa + self._fase * (larg + 2 * faixa)
        paradas = []
        for pos, c in ((0.0, fraca), (0.5, forte), (1.0, fraca)):
            p = Gsk.ColorStop()
            p.offset, p.color = pos, c
            paradas.append(p)
        snapshot.append_linear_gradient(
            Graphene.Rect().init(0, 0, larg, alt),
            Graphene.Point().init(centro - faixa, 0), Graphene.Point().init(centro + faixa, 0), paradas)
        snapshot.pop()


def _girador(tamanho=14):
    g = Adw.Spinner() if hasattr(Adw, "Spinner") else Gtk.Spinner(spinning=True)
    g.set_size_request(tamanho, tamanho)
    g.set_valign(Gtk.Align.CENTER)
    return g


class Digitando(Gtk.Box):
    """Três pontos pulsando + o que o agente faz agora; fica no fim da resposta em andamento."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.add_css_class("digitando")
        pontos = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        pontos.set_valign(Gtk.Align.CENTER)
        for i in range(3):
            p = Gtk.Box()
            p.add_css_class("digitando-ponto")
            p.add_css_class(f"p{i + 1}")
            p.set_size_request(6, 6)
            p.set_valign(Gtk.Align.CENTER)
            pontos.append(p)
        self.append(pontos)
        self.rotulo = RotuloBrilho(xalign=0)
        self.rotulo.add_css_class("digitando-texto")
        self.rotulo.set_ellipsize(Pango.EllipsizeMode.END)
        self.rotulo.set_hexpand(True)
        self.append(self.rotulo)
        self.set_visible(False)
        _acessivel(self, _t("O agente está respondendo"))

    def mostrar(self, texto=None):
        if texto is not None:
            self.rotulo.set_label(texto)
        self.rotulo.brilhar(True)
        self.set_visible(True)

    def parar(self):
        self.rotulo.brilhar(False)
        self.set_visible(False)


# ── linha do tempo ──────────────────────────────────────────────────────────
class ListaPassos(Gtk.Box):
    """Um nível da linha do tempo; mostra os últimos passos e guarda os anteriores sob demanda."""

    def __init__(self, bloco, dados, aninhada=False):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        self.bloco = bloco
        self.dados = dados          # a mesma lista do bloco (não é cópia)
        self.aninhada = aninhada
        self.limite = LIMITE_LINHAS
        self.linhas = {}
        self.primeiro = max(0, len(dados) - self.limite)
        self.btn_antes = Gtk.Button()
        self.btn_antes.add_css_class("flat")
        self.btn_antes.add_css_class("passo-mais")
        self.btn_antes.set_halign(Gtk.Align.START)
        self.btn_antes.connect("clicked", lambda _b: self.mostrar_anteriores())
        self.append(self.btn_antes)
        for p in dados[self.primeiro:]:
            self._criar(p)
        self._atualizar_botao()

    def _criar(self, passo, depois_de=None):
        linha = LinhaPasso(self.bloco, passo)
        self.linhas[passo["id"]] = linha
        if depois_de is None:
            self.append(linha)
        else:
            self.insert_child_after(linha, depois_de)
        return linha

    def _atualizar_botao(self):
        n = self.primeiro
        self.btn_antes.set_visible(n > 0)
        if n > 0:
            texto = (_t("Mostrar %1 ações anteriores", n) if self.aninhada
                     else _t("Mostrar %1 passos anteriores", n)) if n > 1 else _t("Mostrar o passo anterior")
            self.btn_antes.set_label(texto)

    def acrescentado(self, passo):
        """`passo` acabou de entrar no fim de self.dados."""
        self._criar(passo)
        while len(self.linhas) > self.limite and self.primeiro < len(self.dados):
            velho = self.dados[self.primeiro]
            linha = self.linhas.pop(velho["id"], None)
            if linha is not None:
                self.remove(linha)
            self.primeiro += 1
        self._atualizar_botao()

    def atualizar(self, passo):
        linha = self.linhas.get(passo["id"])
        if linha is not None:
            linha.atualizar()
        return linha

    def mostrar_anteriores(self):
        novo = max(0, self.primeiro - LIMITE_LINHAS)
        ancora = self.btn_antes
        for p in self.dados[novo:self.primeiro]:
            ancora = self._criar(p, depois_de=ancora)
        self.limite += self.primeiro - novo
        self.primeiro = novo
        self._atualizar_botao()


class LinhaPasso(Gtk.Box):
    """Um passo: linha simples (ícone, descrição, duração) ou cartão (comando/edição)."""

    def __init__(self, bloco, passo):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.bloco = bloco
        self.passo = passo
        self.cartao = None       # True/False depois de montado
        self.filhos = None
        self.saida_rev = None
        self.saida_lbl = None
        self.saida_cheia = False
        self.diff_cheio = False
        self._montar()

    # ── construção ───────────────────────────────────────────────────────────
    def _eh_cartao(self):
        p = self.passo
        e = p.get("entrada") or {}
        return (p.get("tipo") in CARTOES and not p.get("simples")
                and bool(e.get("comando") or e.get("arquivo") or e.get("diff")))

    def _montar(self):
        filho = self.get_first_child()
        while filho is not None:
            self.remove(filho)
            filho = self.get_first_child()
        self.saida_rev = self.saida_lbl = self.filhos = None
        self.cartao = self._eh_cartao()
        if self.passo.get("tipo") == "pensamento":
            # trecho do raciocínio entre um passo e outro (como no Claude): texto corrido
            self.add_css_class("passo-pensamento")
            self.pensamento = Gtk.Label(xalign=0)
            self.pensamento.set_wrap(True)
            self.pensamento.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            self.pensamento.set_selectable(True)
            self.pensamento.add_css_class("pensamento-texto")
            _acessivel(self.pensamento, _t("Raciocínio do modelo"))
            self.append(self.pensamento)
            self.atualizar()
            return
        for c in ("passo-cartao", "passo-linha", "erro", "negado"):
            self.remove_css_class(c)
        self.add_css_class("passo-cartao" if self.cartao else "passo-linha")

        p = self.passo
        cab = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        cab.add_css_class("passo-cab")
        icone = Gtk.Image.new_from_icon_name(
            ICONES.get("fundo" if p.get("fundo") and p.get("tipo") == "outro" else p.get("tipo"), ICONES["outro"]))
        icone.set_pixel_size(14)
        icone.add_css_class("passo-icone")
        icone.set_valign(Gtk.Align.CENTER)
        cab.append(icone)

        self.titulo = _rotulo(classes=("passo-titulo",))
        self.titulo.set_ellipsize(Pango.EllipsizeMode.END)
        cab.append(self.titulo)
        self.info = _rotulo(classes=("passo-info",))   # também empurra estado e duração para a direita
        self.info.set_ellipsize(Pango.EllipsizeMode.END)
        self.info.set_hexpand(True)
        cab.append(self.info)

        self.estado_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.estado_box.add_css_class("passo-estado")
        self.estado_box.set_valign(Gtk.Align.CENTER)
        self.estado_lbl = Gtk.Label()
        self.estado_box.append(self.estado_lbl)
        cab.append(self.estado_box)
        self.girador = None
        self.dur = _rotulo(classes=("passo-dur",))
        cab.append(self.dur)
        self.append(cab)

        if self.cartao:
            self.btn_copiar = Gtk.Button(icon_name="edit-copy-symbolic")
            self.btn_copiar.add_css_class("flat")
            self.btn_copiar.add_css_class("passo-botao")
            self.btn_copiar.set_valign(Gtk.Align.CENTER)
            self.btn_copiar.connect("clicked", self._copiar)
            cab.append(self.btn_copiar)

            self.corpo = Gtk.Label(xalign=0)
            self.corpo.add_css_class("passo-codigo")
            self.corpo.set_selectable(True)
            self.corpo.set_wrap(True)
            self.corpo.set_wrap_mode(Pango.WrapMode.CHAR)
            self.corpo.set_natural_wrap_mode(Gtk.NaturalWrapMode.NONE)
            self.append(self.corpo)
            self.btn_diff = Gtk.Button()
            self.btn_diff.add_css_class("flat")
            self.btn_diff.add_css_class("passo-mais")
            self.btn_diff.set_halign(Gtk.Align.START)
            self.btn_diff.connect("clicked", self._alternar_diff)
            self.btn_diff.set_visible(False)
            self.append(self.btn_diff)

            self.btn_saida = Gtk.ToggleButton()
            self.btn_saida.add_css_class("flat")
            self.btn_saida.add_css_class("passo-saida-btn")
            self.btn_saida.set_halign(Gtk.Align.START)
            caixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
            self.seta_saida = Gtk.Image.new_from_icon_name("pan-end-symbolic")
            self.seta_saida.set_pixel_size(10)
            self.lbl_saida = Gtk.Label()
            caixa.append(self.seta_saida)
            caixa.append(self.lbl_saida)
            self.btn_saida.set_child(caixa)
            self.btn_saida.connect("toggled", self._alternar_saida)
            self.btn_saida.set_visible(False)
            self.append(self.btn_saida)
            _repintaveis.add(self)
            _ligar_tema()

        if p.get("tipo") == "subagente" and self.bloco.filhos.get(p["id"]):
            self._criar_filhos()
        self.atualizar()

    def _criar_filhos(self):
        self.filhos = ListaPassos(self.bloco, self.bloco.filhos[self.passo["id"]], aninhada=True)
        self.filhos.add_css_class("passo-filhos")
        self.append(self.filhos)

    # ── atualização ──────────────────────────────────────────────────────────
    def _texto_estado(self):
        """(texto, classe, dica) do selo de estado."""
        p, seguro = self.passo, self.bloco.seguro
        estado = p.get("estado")
        edicao = p.get("tipo") == "edicao"
        if estado == "rodando":
            if not self.bloco.vivo:
                estado = None
            elif p.get("fundo"):
                return _t("Em segundo plano…"), "rodando", _t("Continua rodando em segundo plano")
            else:
                return (_t("Alterando…") if edicao else _t("Executando…")), "rodando", ""
        if estado == "negado":
            if seguro:
                return (_t("Negado · somente leitura"), "negado",
                        _t("Modo somente leitura: isto precisaria da sua aprovação e foi negado. Nada foi alterado."))
            return _t("Negado"), "negado", _t("O agente não teve permissão para isto. Nada foi alterado.")
        if estado == "erro":
            return _t("Falhou"), "erro", ("" if seguro else
                                          _t("Modo livre: executado sem pedir aprovação; terminou com erro."))
        if estado == "parado":
            return _t("Interrompido"), "parado", ""
        if seguro:
            return _t("Concluído"), "ok", _t("Permitido no modo somente leitura")
        return ((_t("Alterado automaticamente") if edicao else _t("Executado automaticamente")), "auto",
                _t("Modo livre: o agente fez isto sem pedir aprovação."))

    def atualizar(self):
        if self.passo.get("tipo") == "pensamento":
            self.pensamento.set_markup(markup_pensamento(self.passo.get("texto")))
            return
        if self._eh_cartao() != self.cartao:
            self._montar()
            return
        p = self.passo
        e = p.get("entrada") or {}
        estado = p.get("estado")
        rodando = estado == "rodando" and self.bloco.vivo
        texto = p.get("texto") or p.get("nome") or ""

        # duração (só quando passa de 1 s: abaixo disso é ruído)
        d = p.get("dur")
        self.dur.set_label(duracao(d) if d and d >= 1 else "")
        self.dur.set_visible(bool(d and d >= 1))

        if rodando and self.girador is None:
            self.girador = _girador(12)
            self.estado_box.prepend(self.girador)
        elif not rodando and self.girador is not None:
            self.estado_box.remove(self.girador)
            self.girador = None
        for c in ("erro", "negado"):
            (self.add_css_class if estado == c else self.remove_css_class)(c)

        if self.cartao:
            rotulo, classe, dica = self._texto_estado()
            self.estado_lbl.set_label(rotulo)
            for c in ("rodando", "auto", "ok", "erro", "negado", "parado"):
                (self.estado_box.add_css_class if c == classe else self.estado_box.remove_css_class)(c)
            self.estado_box.set_tooltip_text(dica or None)
            self.estado_box.set_visible(True)
            if p.get("tipo") == "comando":
                self.titulo.set_label(e.get("descricao") or _t("Comando no computador"))
                self.info.set_label("")
                self.btn_copiar.set_tooltip_text(_t("Copiar o comando"))
                _acessivel(self.btn_copiar, _t("Copiar o comando"))
            else:
                caminho = e.get("arquivo") or ""
                self.titulo.set_label(Path(caminho).name or caminho or _t("Arquivo"))
                self.titulo.set_tooltip_text(caminho or None)
                conta = []
                if e.get("novo") or e.get("operacao") == "add":
                    conta.append(_t("novo arquivo"))
                elif e.get("operacao") == "delete":
                    conta.append(_t("apagado"))
                if e.get("mais"):
                    conta.append(f"+{e['mais']}")
                if e.get("menos"):
                    conta.append(f"−{e['menos']}")
                self.info.set_label("  ".join(conta))
                self.btn_copiar.set_tooltip_text(_t("Copiar o caminho do arquivo"))
                _acessivel(self.btn_copiar, _t("Copiar o caminho do arquivo"))
            self.repintar()
            saida = p.get("saida") or ""
            self.btn_saida.set_visible(bool(saida))
            if saida:
                n = int(p.get("linhas") or saida.count("\n") + 1)
                nome = _t("Saída") if estado != "erro" and estado != "negado" else _t("Mensagem de erro")
                self.lbl_saida.set_label(f"{nome} · {n} {_t('linha') if n == 1 else _t('linhas')}")
                self.btn_saida.set_tooltip_text(_t("Mostrar ou esconder a saída"))
                if self.saida_lbl is not None:
                    self._preencher_saida()
        else:
            self.titulo.set_label(texto)
            self.titulo.set_tooltip_text(texto if len(texto) > 60 else None)
            partes = []
            if p.get("tipo") == "subagente":
                if p.get("acoes"):
                    partes.append(f"{p['acoes']} {_t('ação') if p['acoes'] == 1 else _t('ações')}")
                if p.get("tokens"):
                    partes.append(f"{_milhar(p['tokens'])} tokens")
                if rodando and p.get("detalhe"):
                    partes.append(p["detalhe"])
            if estado in ("erro", "negado") and p.get("nota"):
                partes.append(p["nota"])
            self.info.set_label(" · ".join(partes))
            self.info.set_tooltip_text(" · ".join(partes) if partes else None)
            rotulo = {"erro": _t("Falhou"), "parado": _t("Interrompido"),
                      "negado": _t("Negado · somente leitura") if self.bloco.seguro else _t("Negado")}.get(estado, "")
            if rodando and p.get("fundo"):
                rotulo = _t("Em segundo plano…")
            self.estado_lbl.set_label(rotulo)
            self.estado_lbl.set_visible(bool(rotulo))
            for c in ("erro", "negado", "parado"):
                (self.estado_box.add_css_class if c == estado else self.estado_box.remove_css_class)(c)
            self.estado_box.set_visible(rodando or bool(rotulo))
            if p.get("tipo") == "subagente" and self.filhos is None and self.bloco.filhos.get(p["id"]):
                self._criar_filhos()

    def repintar(self):
        """Corpo do cartão (cores dependem do tema)."""
        if not self.cartao:
            return
        e = self.passo.get("entrada") or {}
        if self.passo.get("tipo") == "comando":
            cmd = e.get("comando") or ""
            corte = len(cmd) > 1600
            self.corpo.set_markup(realce_shell(cmd[:1600]) + (" …" if corte else ""))
            self.corpo.set_visible(bool(cmd))
            return
        linhas = (e.get("diff") or "").split("\n") if e.get("diff") else []
        self.corpo.set_visible(bool(linhas))
        resto = len(linhas) - PREVIA_DIFF
        mostra = linhas if self.diff_cheio or resto <= 2 else linhas[:PREVIA_DIFF]
        self.corpo.set_markup(realce_diff(mostra))
        if resto > 2:
            self.btn_diff.set_visible(True)
            cortado = e.get("cortado")
            self.btn_diff.set_label(
                (_t("Mostrar menos") if not cortado else _t("Mostrar menos (há mais %1 linhas no arquivo)", cortado))
                if self.diff_cheio else _t("Mostrar mais %1 linhas", resto))
        else:
            self.btn_diff.set_visible(False)

    # ── ações ────────────────────────────────────────────────────────────────
    def _copiar(self, btn):
        e = self.passo.get("entrada") or {}
        texto = e.get("comando") if self.passo.get("tipo") == "comando" else e.get("arquivo")
        if not texto:
            return
        Gdk.Display.get_default().get_clipboard().set(texto)
        btn.set_icon_name("object-select-symbolic")
        dica = btn.get_tooltip_text()
        btn.set_tooltip_text(_t("Copiado"))
        btn.add_css_class("copiado")

        def voltar():
            btn.set_icon_name("edit-copy-symbolic")
            btn.set_tooltip_text(dica)
            btn.remove_css_class("copiado")
            return False
        GLib.timeout_add(1600, voltar)

    def _alternar_diff(self, _b):
        self.diff_cheio = not self.diff_cheio
        self.repintar()

    def _preencher_saida(self):
        saida = self.passo.get("saida") or ""
        linhas = saida.split("\n")
        resto = len(linhas) - PREVIA_SAIDA
        if self.saida_cheia or resto <= 3:
            self.saida_lbl.set_label(saida)
            self.btn_saida_mais.set_visible(resto > 3)
            self.btn_saida_mais.set_label(_t("Mostrar menos"))
        else:
            self.saida_lbl.set_label("\n".join(linhas[:PREVIA_SAIDA]))
            self.btn_saida_mais.set_visible(True)
            self.btn_saida_mais.set_label(_t("Mostrar mais %1 linhas", resto))

    def _alternar_saida(self, btn):
        aberto = btn.get_active()
        if aberto and self.saida_rev is None:
            # montado só agora: a maioria das saídas nunca é aberta
            self.saida_rev = Gtk.Revealer()
            self.saida_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
            self.saida_rev.set_transition_duration(160)
            caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            caixa.add_css_class("passo-saida")
            self.saida_lbl = Gtk.Label(xalign=0, yalign=0)
            self.saida_lbl.add_css_class("passo-saida-texto")
            self.saida_lbl.set_selectable(True)
            rolagem = Gtk.ScrolledWindow()
            rolagem.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
            rolagem.set_propagate_natural_height(True)
            rolagem.set_child(self.saida_lbl)
            caixa.append(rolagem)
            self.btn_saida_mais = Gtk.Button()
            self.btn_saida_mais.add_css_class("flat")
            self.btn_saida_mais.add_css_class("passo-mais")
            self.btn_saida_mais.set_halign(Gtk.Align.START)

            def mais(_b):
                self.saida_cheia = not self.saida_cheia
                self._preencher_saida()
            self.btn_saida_mais.connect("clicked", mais)
            caixa.append(self.btn_saida_mais)
            self.saida_rev.set_child(caixa)
            self.append(self.saida_rev)
            self._preencher_saida()
        if self.saida_rev is not None:
            self.saida_rev.set_reveal_child(aberto)
        self.seta_saida.set_from_icon_name("pan-down-symbolic" if aberto else "pan-end-symbolic")
        btn.update_state([Gtk.AccessibleState.EXPANDED], [int(aberto)])

    def abrir_saida(self):
        if self.cartao and self.btn_saida.get_visible():
            self.btn_saida.set_active(True)


# ── o bloco ─────────────────────────────────────────────────────────────────
class BlocoPensando(Gtk.Box):
    """Cabeçalho clicável + linha do tempo recolhível de uma resposta."""

    def __init__(self, registro=None, seguro=False, vivo=True, ao_abrir=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("pensando")
        self.registro = registro
        self.seguro = bool(seguro)
        self.vivo = bool(vivo)
        self.ao_abrir = ao_abrir or (lambda: None)
        self.passos = []            # todos, na ordem (é a lista guardada na conversa)
        self.por_id = {}
        self.raiz = []              # passos de primeiro nível
        self.filhos = {}            # id do subagente → passos dele
        self.descartados = 0
        self.orcamento = ORCAMENTO_SAIDA
        self.raciocinio = ""
        self._seg = None            # trecho de raciocínio em andamento (passo "pensamento")
        self._n_seg = 0
        self._racio_pendente = []
        self._racio_fonte = 0
        self._racio_no_buffer = 0
        self.inicio = time.monotonic()
        self.segundos = None        # duração total, depois de concluir
        self.interrompido = False
        self.antigo = False         # conversa antiga: sem duração
        self._status = ""
        self._aviso = ""
        self._relogio = 0
        self.lista = None
        self.racio_view = None
        if registro is not None:
            registro["passos"] = self.passos

        self.botao = Gtk.ToggleButton()
        self.botao.add_css_class("flat")
        self.botao.add_css_class("pensando-cabecalho")
        self.botao.set_halign(Gtk.Align.START)
        cab = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.girador = _girador(14)
        cab.append(self.girador)
        self.icone = Gtk.Image.new_from_icon_name("object-select-symbolic")
        self.icone.set_pixel_size(14)
        self.icone.add_css_class("pensando-icone")
        self.icone.set_visible(False)
        cab.append(self.icone)
        self.rotulo = RotuloBrilho(xalign=0)
        self.rotulo.add_css_class("pensando-atual")
        self.rotulo.set_ellipsize(Pango.EllipsizeMode.END)
        cab.append(self.rotulo)
        self.tempo = _rotulo(classes=("pensando-tempo",))
        self.tempo.set_ellipsize(Pango.EllipsizeMode.END)
        cab.append(self.tempo)
        self.seta = Gtk.Image.new_from_icon_name("pan-end-symbolic")
        self.seta.set_pixel_size(12)
        self.seta.add_css_class("pensando-seta")
        cab.append(self.seta)
        self.botao.set_child(cab)
        self.botao.set_tooltip_text(_t("Ver o que a IA pensou e executou"))
        self.botao.connect("toggled", self._alternar)
        self.append(self.botao)

        self.revelador = Gtk.Revealer()
        self.revelador.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.revelador.set_transition_duration(200)
        self.corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.corpo.add_css_class("pensando-corpo")
        self.revelador.set_child(self.corpo)
        self.append(self.revelador)

        self.connect("unrealize", lambda *_: self._parar_relogio())
        if self.vivo:
            self._status = _t("Pensando…")
            self._relogio = GLib.timeout_add_seconds(1, self._tique)
            self.rotulo.brilhar(True)
        self._atualizar_cabecalho()

    # ── cabeçalho ────────────────────────────────────────────────────────────
    def _tique(self):
        if not self.vivo or self.get_root() is None:
            self._relogio = 0
            return False
        if self.get_mapped():
            self._atualizar_tempo()
        return True

    def _parar_relogio(self):
        if self._relogio:
            GLib.source_remove(self._relogio)
            self._relogio = 0
        if self._racio_fonte:
            GLib.source_remove(self._racio_fonte)
            self._racio_fonte = 0
        self.rotulo.brilhar(False)

    def _atualizar_tempo(self):
        if not self.vivo:
            self.tempo.set_label("")
            self.tempo.set_visible(False)
            return
        if self._aviso:
            self.tempo.set_label(self._aviso)
            self.tempo.add_css_class("aviso")
        else:
            self.tempo.remove_css_class("aviso")
            self.tempo.set_label(_t("Pensando há %1", duracao(time.monotonic() - self.inicio)))
        self.tempo.set_visible(True)

    def resumo(self):
        """'Pensou por 1 min 20 s · 7 passos' (depois de concluir)."""
        n = len([p for p in self.raiz if p.get("tipo") != "pensamento"]) + self.descartados
        passos = f"{n} {_t('passo') if n == 1 else _t('passos')}" if n else ""
        if self.antigo or self.segundos is None:
            return passos or _t("Atividade")
        base = (_t("Interrompido após %1", duracao(self.segundos)) if self.interrompido
                else _t("Pensou por %1", duracao(self.segundos)))
        return f"{base} · {passos}" if passos else base

    def texto_cabecalho(self):
        """O que o cabeçalho mostra agora, em texto (leitores de tela e testes)."""
        partes = [self.rotulo.get_label()]
        if self.tempo.get_visible() and self.tempo.get_label():
            partes.append(self.tempo.get_label())
        return " · ".join(x for x in partes if x)

    def _atualizar_cabecalho(self):
        self.girador.set_visible(self.vivo)
        self.icone.set_visible(not self.vivo)
        if self.vivo:
            self.rotulo.set_label(self._status)
        else:
            self.rotulo.set_label(self.resumo())
            self.icone.set_from_icon_name(
                "media-playback-stop-symbolic" if self.interrompido else "object-select-symbolic")
        self._atualizar_tempo()
        tem = self.tem_conteudo()
        self.seta.set_visible(tem)
        self.botao.set_can_target(tem)
        self.botao.set_focusable(tem)
        _acessivel(self.botao, f"{self.texto_cabecalho()}. {_t('Ver o que a IA pensou e executou')}")

    def tem_conteudo(self):
        return bool(self.passos or self.raciocinio or self._racio_pendente)

    def status(self, texto):
        """Passo atual, no cabeçalho (some o aviso do vigia: houve novidade)."""
        texto = " ".join(str(texto or "").split())
        if texto.startswith("✦ "):
            texto = texto[2:]
        if not texto or not self.vivo:
            return
        self._status = texto
        self._aviso = ""
        self.rotulo.set_label(texto)
        self._atualizar_tempo()

    def status_atual(self):
        return self._status

    def aviso(self, texto):
        """Aviso do vigia ('sem novidade há N min…') no lugar do cronômetro."""
        self._aviso = texto or ""
        self._atualizar_tempo()
        _acessivel(self.botao, self.texto_cabecalho())

    # ── abrir/fechar ─────────────────────────────────────────────────────────
    def _alternar(self, botao):
        aberto = botao.get_active()
        if aberto:
            self._montar_corpo()
        self.revelador.set_reveal_child(aberto)
        self.seta.set_from_icon_name("pan-down-symbolic" if aberto else "pan-end-symbolic")
        botao.update_state([Gtk.AccessibleState.EXPANDED], [int(aberto)])
        if aberto:
            self.ao_abrir()

    def expandir(self, aberto=True):
        if self.tem_conteudo() or not aberto:
            self.botao.set_active(aberto)

    def aberto(self):
        return self.botao.get_active()

    def _montar_corpo(self):
        if self.raciocinio and self.racio_view is None and not self._n_seg:
            self._criar_raciocinio()
        if self.lista is None and self.raiz:
            self.lista = ListaPassos(self, self.raiz)
            self.corpo.append(self.lista)

    def _criar_raciocinio(self):
        """Conversas antigas: o raciocínio inteiro num texto só, acima dos passos."""
        self.racio_view = Gtk.Label(xalign=0)
        self.racio_view.set_wrap(True)
        self.racio_view.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.racio_view.set_selectable(True)
        self.racio_view.add_css_class("pensamento-texto")
        _acessivel(self.racio_view, _t("Raciocínio do modelo"))
        self.racio_view.set_markup(markup_pensamento(self.raciocinio))
        self.corpo.prepend(self.racio_view)
        self._racio_no_buffer = len(self.raciocinio)

    def _rolar_raciocinio(self):
        return False

    # ── eventos ao vivo ──────────────────────────────────────────────────────
    def passo(self, ev):
        """Cria ou atualiza um passo a partir de um evento do parser."""
        pid = str(ev.get("id") or "")
        if not pid:
            return
        p = self.por_id.get(pid)
        novo = p is None
        if novo and not ev.get("pai") and ev.get("tipo") != "pensamento":
            if self._racio_pendente:
                if self._racio_fonte:
                    GLib.source_remove(self._racio_fonte)
                self._descarregar_raciocinio()
            self._seg = None        # o próximo raciocínio vira outro trecho, depois deste passo
        if novo:
            if len(self.passos) >= MAX_PASSOS:
                self.descartados += 1
                return
            p = {"id": pid, "tipo": ev.get("tipo") or "outro", "texto": "", "t0": round(time.time(), 2)}
            pai = ev.get("pai")
            if pai and pai in self.por_id and pai != pid:
                p["pai"] = pai
            self.por_id[pid] = p
            self.passos.append(p)
        for k in ("tipo", "nome", "texto", "fundo", "acoes", "tokens", "detalhe", "nota", "linhas"):
            if ev.get(k) is not None:
                p[k] = ev[k]
        if isinstance(ev.get("entrada"), dict):
            p.setdefault("entrada", {}).update(ev["entrada"])
        if ev.get("saida"):
            saida = str(ev["saida"])
            if len(saida) > self.orcamento:
                saida = saida[:max(400, self.orcamento)] + "\n⋯"
            self.orcamento = max(0, self.orcamento - len(saida))
            p["saida"] = saida
        estado = ev.get("estado")
        if estado:
            p["estado"] = estado
            if estado != "rodando":
                p["dur"] = round(max(0.0, time.time() - p.get("t0", time.time())), 1)

        if novo:
            if p.get("pai"):
                irmaos = self.filhos.setdefault(p["pai"], [])
                irmaos.append(p)
                dono = self._linha(p["pai"])
                if dono is not None:
                    if dono.filhos is None:
                        dono.atualizar()        # cria a lista aninhada (já com este passo)
                    else:
                        dono.filhos.acrescentado(p)
            else:
                self.raiz.append(p)
                if self.lista is not None:
                    self.lista.acrescentado(p)
                elif self.aberto():
                    self._montar_corpo()
            if len(self.passos) == 1:
                self._atualizar_cabecalho()   # passa a ser clicável
        else:
            linha = self._linha(pid)
            if linha is not None:
                linha.atualizar()

    def _linha(self, pid):
        """A linha na tela de um passo (None se o bloco está recolhido ou o passo, fora da vista)."""
        p = self.por_id.get(pid)
        if p is None or self.lista is None:
            return None
        if p.get("pai"):
            dono = self._linha(p["pai"])
            return dono.filhos.linhas.get(pid) if dono is not None and dono.filhos is not None else None
        return self.lista.linhas.get(pid)

    def raciocinar(self, texto):
        """Pedaço do raciocínio do modelo; vai para a tela em lotes."""
        if not texto or len(self.raciocinio) >= MAX_RACIOCINIO:
            return
        self._racio_pendente.append(texto)
        if not self._racio_fonte:
            self._racio_fonte = GLib.timeout_add(150, self._descarregar_raciocinio)

    def _descarregar_raciocinio(self):
        self._racio_fonte = 0
        primeiro = not self.raciocinio
        novo = "".join(self._racio_pendente)
        self._racio_pendente = []
        if primeiro:
            novo = novo.lstrip("\n")
        self.raciocinio += novo
        if self.registro is not None:
            self.registro["raciocinio"] = self.raciocinio.strip()
        # o trecho atual vira (ou continua) um passo "pensamento" na linha do tempo
        if novo.strip() or self._seg is not None:
            if self._seg is None:
                self._n_seg += 1
                pid = f"pensamento-{self._n_seg}"
                self.passo({"id": pid, "tipo": "pensamento", "texto": novo.lstrip("\n")})
                self._seg = self.por_id.get(pid)
            else:
                self._seg["texto"] = (self._seg.get("texto", "") + novo)
                linha = self._linha(self._seg["id"])
                if linha is not None:
                    linha.atualizar()
        if primeiro and self.raciocinio:
            self._atualizar_cabecalho()
        # resumo corrente: a última linha do raciocínio vira o passo atual do cabeçalho
        linhas = [l.strip(" *#_`") for l in self.raciocinio.strip().split("\n") if l.strip(" *#_`")]
        if linhas and self.vivo:
            ultima = linhas[-1]
            self.rotulo.set_label(ultima if len(ultima) <= 110 else "…" + ultima[-109:])
        return False

    def concluir(self, segundos=None, interrompida=False):
        """Fim da resposta: para as animações e recolhe para o resumo."""
        if not self.vivo:
            return
        if self._racio_pendente:
            if self._racio_fonte:
                GLib.source_remove(self._racio_fonte)
            self._descarregar_raciocinio()
        self.vivo = False
        self._parar_relogio()
        self.segundos = (time.monotonic() - self.inicio) if segundos is None else segundos
        self.interrompido = bool(interrompida)
        for p in self.passos:
            if p.get("estado") == "rodando":
                # o processo acabou sem dizer como este passo terminou
                if interrompida:
                    p["estado"] = "parado"
                else:
                    p.pop("estado", None)
                linha = self._linha(p["id"])
                if linha is not None:
                    linha.atualizar()
        if self.registro is not None:
            self.registro["pensou"] = round(self.segundos, 1)
            if self.descartados:
                self.registro["passos_a_mais"] = self.descartados
        self._aviso = ""
        self.set_visible(self.tem_conteudo())
        self.botao.set_active(False)
        self._atualizar_cabecalho()

    # ── conversa salva ───────────────────────────────────────────────────────
    def carregar(self, registro):
        """Remonta o bloco de uma resposta guardada (ou de uma conversa antiga, só com textos)."""
        self.vivo = False
        self._parar_relogio()
        passos = registro.get("passos")
        if not isinstance(passos, list) or not passos:
            passos = passos_de_atividade(registro.get("atividade"))
            self.antigo = True
        for p in passos:
            if not isinstance(p, dict) or not p.get("id"):
                continue
            p = dict(p)
            pid = str(p["id"])
            if p.get("estado") == "rodando":   # o chat fechou no meio da resposta
                p.pop("estado")
            self.por_id[pid] = p
            self.passos.append(p)
            pai = p.get("pai")
            if pai and pai in self.por_id:
                self.filhos.setdefault(pai, []).append(p)
            else:
                self.raiz.append(p)
        self._n_seg = sum(1 for p in self.passos if p.get("tipo") == "pensamento")
        self.descartados = int(registro.get("passos_a_mais") or 0)
        self.raciocinio = str(registro.get("raciocinio") or "")
        if isinstance(registro.get("pensou"), (int, float)):
            self.segundos = float(registro["pensou"])
        else:
            self.antigo = True
        self.interrompido = bool(registro.get("interrompida"))
        self.set_visible(self.tem_conteudo())
        self._atualizar_cabecalho()
