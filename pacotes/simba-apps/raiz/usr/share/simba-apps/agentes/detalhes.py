"""Painel de detalhes à direita da conversa (como o "session rail" do Claude Code e o
"Activity" do ChatGPT).

Cartões, de cima para baixo:
  Ambiente   pasta de trabalho, agente e modelo, modo (livre / somente leitura)
  Contexto   quanto da janela de contexto do modelo a conversa ocupa (barra + %)
  Agentes    o agente principal e cada subagente/tarefa em segundo plano, com o
             estado individual (trabalhando, concluído, falhou) e a última ação
  Atividade  contagem do que foi executado e a linha do tempo inteira da resposta
             (raciocínio, comandos, edições, leituras), atualizada ao vivo

O bloco "Pensando" da conversa mostra só o último passo; o histórico completo é aqui.
Leve: os cartões de agentes são remontados no máximo a cada 250 ms e a linha do
tempo só é montada quando o painel está na tela.
"""
from pathlib import Path
import sys

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Pango  # noqa: E402

sys.path.insert(0, "/usr/share/simba-apps/idiomas")
from simba_i18n import t as _t  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import atividade  # noqa: E402

HOME = Path.home()


def janela_contexto(agente, modelo):
    """Tamanho (tokens) da janela de contexto do modelo, quando dá para saber."""
    m = str(modelo or "").lower()
    if "[1m]" in m or m.endswith("-1m"):
        return 1_000_000
    if "gemini" in m or agente == "gemini":
        return 1_000_000
    if agente == "claude" or "claude" in m or m in ("opus", "sonnet", "haiku", "fable"):
        return 200_000
    if agente == "codex" or m.startswith(("gpt-5", "o3", "o4")):
        return 272_000
    return None


def tokens_curto(n):
    """14_500 → '14,5 mil'; 1_200_000 → '1,2 mi'."""
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " " + _t("mi")
    if n >= 1000:
        return f"{n / 1000:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " " + _t("mil")
    return str(n)


def caminho_curto(p):
    p = str(p or "")
    h = str(HOME)
    return "~" + p[len(h):] if p == h or p.startswith(h + "/") else p


def contar_acoes(passos):
    """Resumo do que a resposta executou: '3 comandos · 1 edição · 4 leituras'."""
    nomes = (("comando", _t("comando"), _t("comandos")), ("edicao", _t("edição"), _t("edições")),
             ("leitura", _t("leitura"), _t("leituras")), ("busca", _t("busca"), _t("buscas")),
             ("web", _t("acesso à web"), _t("acessos à web")),
             ("subagente", _t("subagente"), _t("subagentes")))
    partes = []
    for tipo, um, varios in nomes:
        n = sum(1 for p in passos or [] if p.get("tipo") == tipo)
        if n:
            partes.append(f"{n} {um if n == 1 else varios}")
    return " · ".join(partes)


def estado_subagente(p, vivo):
    """(texto, classe) do selo de um subagente ou tarefa em segundo plano."""
    e = p.get("estado")
    if e == "rodando" and vivo:
        return _t("Trabalhando…"), "rodando"
    if e == "erro":
        return _t("Falhou"), "erro"
    if e in ("parado", "negado") or (e == "rodando" and not vivo):
        return _t("Interrompido"), "parado"
    return _t("Concluído"), "ok"


def _rotulo(texto="", classes=(), **kw):
    lbl = Gtk.Label(label=texto, xalign=0, **kw)
    for c in classes:
        lbl.add_css_class(c)
    return lbl


class PainelDetalhes(Gtk.Box):
    def __init__(self, ao_fechar=None, abrir_pasta=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("painel-detalhes")
        self.set_size_request(280, -1)
        self.ao_fechar = ao_fechar
        self.abrir_pasta = abrir_pasta
        self.bloco = None
        self.nome_agente = ""
        self.icone_agente = None
        self.pasta = None
        self._fonte = 0
        self._ctx = (None, None)
        self.seguir = True

        cab = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        cab.add_css_class("detalhes-cab")
        titulo = _rotulo(_t("Detalhes"), ("detalhes-titulo",))
        titulo.set_hexpand(True)
        cab.append(titulo)
        fechar = Gtk.Button(icon_name="window-close-symbolic")
        fechar.add_css_class("flat")
        fechar.add_css_class("detalhes-fechar")
        fechar.set_tooltip_text(_t("Fechar o painel de detalhes"))
        fechar.connect("clicked", lambda _b: self.ao_fechar and self.ao_fechar())
        cab.append(fechar)
        self.append(cab)

        # em cima (rola sozinho se crescer): ambiente, contexto e agentes
        topo = Gtk.ScrolledWindow()
        topo.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.AUTOMATIC)
        topo.set_propagate_natural_height(True)
        topo.set_max_content_height(460)
        conteudo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        conteudo.add_css_class("detalhes-conteudo")
        topo.set_child(conteudo)
        topo.get_child().set_scroll_to_focus(False)  # clicar num texto não rola o painel
        self.append(topo)
        # embaixo, ocupando o resto: a linha do tempo, que acompanha o fim
        self.rolagem = Gtk.ScrolledWindow()
        self.rolagem.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.AUTOMATIC)
        self.rolagem.set_vexpand(True)
        baixo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        baixo.add_css_class("detalhes-conteudo")
        self.rolagem.set_child(baixo)
        self.rolagem.get_child().set_scroll_to_focus(False)  # clicar num texto não rola o painel
        self.append(self.rolagem)
        adj = self.rolagem.get_vadjustment()
        adj.connect("value-changed", self._rolagem_mudou)
        adj.connect("notify::upper", lambda *_: self.seguir and GLib.idle_add(self._rolar_fim))

        # ── Ambiente ──
        conteudo.append(self._secao(_t("Ambiente")))
        amb = self._caixa_cartao()
        self.btn_pasta = Gtk.Button()
        self.btn_pasta.add_css_class("flat")
        self.btn_pasta.add_css_class("detalhes-linha-botao")
        self.lbl_pasta = _rotulo("", ("detalhes-valor",))
        self.lbl_pasta.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        linha_pasta = self._linha("folder-symbolic", self.lbl_pasta)
        abrir = Gtk.Image.new_from_icon_name("go-next-symbolic")
        abrir.set_pixel_size(12)
        abrir.add_css_class("detalhes-seta")
        linha_pasta.append(abrir)
        self.btn_pasta.set_child(linha_pasta)
        self.btn_pasta.connect("clicked", lambda _b: self.abrir_pasta and self.pasta and self.abrir_pasta(self.pasta))
        amb.append(self.btn_pasta)
        self.img_agente = Gtk.Image.new_from_icon_name("simba-agente")
        self.img_agente.set_pixel_size(16)
        self.lbl_agente = _rotulo("", ("detalhes-valor",))
        self.lbl_agente.set_ellipsize(Pango.EllipsizeMode.END)
        amb.append(self._linha(None, self.lbl_agente, imagem=self.img_agente))
        self.img_modo = Gtk.Image.new_from_icon_name("changes-allow-symbolic")
        self.img_modo.set_pixel_size(16)
        self.lbl_modo = _rotulo("", ("detalhes-valor",))
        self.lbl_modo.set_ellipsize(Pango.EllipsizeMode.END)
        self.linha_modo = self._linha(None, self.lbl_modo, imagem=self.img_modo)
        amb.append(self.linha_modo)
        conteudo.append(amb)

        # ── Contexto ──
        linha_ctx = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        linha_ctx.add_css_class("detalhes-secao")
        t_ctx = _rotulo(_t("Contexto"), ("detalhes-secao-titulo",))
        t_ctx.set_hexpand(True)
        linha_ctx.append(t_ctx)
        self.lbl_ctx_pct = _rotulo("", ("detalhes-ctx-pct",))
        linha_ctx.append(self.lbl_ctx_pct)
        conteudo.append(linha_ctx)
        ctx = self._caixa_cartao()
        self.barra_ctx = Gtk.LevelBar()
        self.barra_ctx.add_css_class("detalhes-ctx-barra")
        self.barra_ctx.set_min_value(0)
        self.barra_ctx.set_max_value(1)
        for nome in ("low", "high", "full"):
            self.barra_ctx.remove_offset_value(nome)
        ctx.append(self.barra_ctx)
        self.lbl_ctx = _rotulo("", ("detalhes-dica",))
        self.lbl_ctx.set_wrap(True)
        ctx.append(self.lbl_ctx)
        conteudo.append(ctx)
        self._anim_ctx = None
        if hasattr(Adw, "TimedAnimation"):
            alvo = Adw.CallbackAnimationTarget.new(lambda v: self.barra_ctx.set_value(v))
            self._anim_ctx = Adw.TimedAnimation.new(self.barra_ctx, 0, 0, 600, alvo)
            self._anim_ctx.set_easing(Adw.Easing.EASE_OUT_CUBIC)

        # ── Agentes ──
        conteudo.append(self._secao(_t("Agentes")))
        self.caixa_agentes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.caixa_agentes.add_css_class("detalhes-agentes")
        conteudo.append(self.caixa_agentes)
        self._cartoes = {}
        self.vazio_agentes = self._vazio("system-run-symbolic", _t("Nenhuma resposta em andamento."))
        self.caixa_agentes.append(self.vazio_agentes)
        self.sem_sub = _rotulo(_t("Nenhum subagente nesta resposta."), ("detalhes-dica", "detalhes-sem-sub"))
        self.sem_sub.set_wrap(True)
        self.caixa_agentes.append(self.sem_sub)
        sep = self._separador()
        self.append(sep)

        # ── Atividade ──
        conteudo = baixo
        linha_at = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        linha_at.add_css_class("detalhes-secao")
        t_at = _rotulo(_t("Atividade"), ("detalhes-secao-titulo",))
        t_at.set_hexpand(True)
        linha_at.append(t_at)
        conteudo.append(linha_at)
        self.lbl_resumo = _rotulo("", ("detalhes-resumo",))
        self.lbl_resumo.set_wrap(True)
        conteudo.append(self.lbl_resumo)
        self.vazio_atividade = self._vazio("view-list-bullet-symbolic",
                                           _t("Os comandos, edições e subagentes de cada resposta aparecem aqui."))
        conteudo.append(self.vazio_atividade)
        self.lbl_racio = Gtk.Label(xalign=0)
        self.lbl_racio.set_wrap(True)
        self.lbl_racio.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.lbl_racio.set_selectable(True)
        self.lbl_racio.add_css_class("pensamento-texto")
        self.lbl_racio.add_css_class("detalhes-racio")
        self.lbl_racio.set_visible(False)
        conteudo.append(self.lbl_racio)
        self.caixa_linha = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.caixa_linha.add_css_class("detalhes-linha-do-tempo")
        conteudo.append(self.caixa_linha)

        self.connect("map", lambda *_: self._montar_linha_do_tempo())
        self.contexto(None, None)
        self._remontar()

    # ── montagem ─────────────────────────────────────────────────────────────
    def _secao(self, texto):
        lbl = _rotulo(texto, ("detalhes-secao", "detalhes-secao-titulo"))
        return lbl

    def _caixa_cartao(self):
        c = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        c.add_css_class("detalhes-cartao")
        return c

    def _vazio(self, icone, texto):
        caixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        caixa.add_css_class("detalhes-vazio")
        img = Gtk.Image.new_from_icon_name(icone)
        img.set_pixel_size(16)
        img.set_valign(Gtk.Align.START)
        caixa.append(img)
        lbl = _rotulo(texto)
        lbl.set_wrap(True)
        lbl.set_hexpand(True)
        caixa.append(lbl)
        return caixa

    def _separador(self):
        s = Gtk.Separator()
        s.add_css_class("detalhes-sep")
        return s

    def _linha(self, icone, rotulo, imagem=None):
        caixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        caixa.add_css_class("detalhes-linha")
        img = imagem or Gtk.Image.new_from_icon_name(icone)
        img.set_pixel_size(16)
        img.add_css_class("detalhes-icone")
        caixa.append(img)
        rotulo.set_hexpand(True)
        caixa.append(rotulo)
        return caixa

    # ── dados de fora ────────────────────────────────────────────────────────
    def ambiente(self, pasta=None, agente=None, icone=None, modelo=None, seguro=None):
        if pasta is not None:
            self.pasta = Path(pasta)
            self.lbl_pasta.set_label(caminho_curto(pasta))
            self.btn_pasta.set_tooltip_text(f"{_t('Pasta de trabalho:')} {pasta}\n{_t('Clique para abrir')}")
        if agente is not None:
            texto = f"{agente} · {modelo}" if modelo else agente
            self.lbl_agente.set_label(texto)
            self.lbl_agente.set_tooltip_text(texto)
            self.nome_agente = agente
        if icone:
            self.img_agente.set_from_icon_name(icone)
            self.icone_agente = icone
        if seguro is not None:
            self.lbl_modo.set_label(_t("Somente leitura") if seguro else _t("Livre · executa sem pedir aprovação"))
            self.img_modo.set_from_icon_name("changes-prevent-symbolic" if seguro else "changes-allow-symbolic")

    def contexto(self, tokens, janela):
        """tokens = tamanho da conversa que o modelo lê agora; janela = limite do modelo."""
        self._ctx = (tokens, janela)
        if not tokens:
            self.lbl_ctx_pct.set_label("—")
            self._valor_ctx(0)
            self.lbl_ctx.set_label(_t("Aparece depois da primeira resposta."))
            return
        if janela:
            frac = min(1.0, tokens / janela)
            pct = max(1, round(frac * 100)) if tokens else 0
            self.lbl_ctx_pct.set_label(f"{pct}%")
            self._valor_ctx(frac)
            self.lbl_ctx.set_label(_t("%1 de %2 tokens", tokens_curto(tokens), tokens_curto(janela)))
            for c in ("alto", "critico"):
                self.barra_ctx.remove_css_class(c)
            if frac >= 0.9:
                self.barra_ctx.add_css_class("critico")
            elif frac >= 0.7:
                self.barra_ctx.add_css_class("alto")
        else:
            self.lbl_ctx_pct.set_label(tokens_curto(tokens))
            self._valor_ctx(0)
            self.lbl_ctx.set_label(_t("%1 tokens na conversa", tokens_curto(tokens)))

    def _valor_ctx(self, frac):
        """Barra de contexto desliza até o valor novo (sem animação se o sistema pediu)."""
        if self._anim_ctx is None:
            self.barra_ctx.set_value(frac)
            return
        self._anim_ctx.pause()
        self._anim_ctx.set_value_from(self.barra_ctx.get_value())
        self._anim_ctx.set_value_to(frac)
        self._anim_ctx.play()

    def contexto_pct(self):
        tokens, janela = self._ctx
        return round(min(1.0, tokens / janela) * 100) if tokens and janela else None

    def mostrar_bloco(self, bloco, agente=None, icone=None):
        """Passa a mostrar a atividade de uma resposta (a em andamento ou uma antiga)."""
        if agente:
            self.nome_agente = agente
        if icone:
            self.icone_agente = icone
        if bloco is self.bloco:
            self._agendar()
            return
        if self.bloco is not None:
            self.bloco.observador = None
            self.bloco.soltar_linha_do_tempo()
        self.bloco = bloco
        if bloco is not None:
            bloco.observador = self._mudou
        self.seguir = True
        self._montar_linha_do_tempo()
        self._remontar()

    def limpar(self):
        self.mostrar_bloco(None)
        self.contexto(None, None)

    def _montar_linha_do_tempo(self):
        b = self.bloco
        racio = b.raciocinio_sem_trechos() if b is not None else ""
        self.lbl_racio.set_visible(bool(racio))
        if racio:
            self.lbl_racio.set_markup(atividade.markup_pensamento(racio))
        if b is None or not self.get_mapped():
            return
        lista = b.linha_do_tempo()
        if lista.get_parent() is not self.caixa_linha:
            if lista.get_parent() is not None:
                lista.get_parent().remove(lista)
            self.caixa_linha.append(lista)

    # ── atualização ──────────────────────────────────────────────────────────
    def _mudou(self, _bloco, _passo):
        self._agendar()

    def _agendar(self):
        if not self._fonte:
            self._fonte = GLib.timeout_add(250, self._remontar)

    def _remontar(self):
        """Atualiza os cartões no lugar (só cria os novos), para não piscar a cada passo."""
        self._fonte = 0
        b = self.bloco
        self.vazio_agentes.set_visible(b is None)
        self.vazio_atividade.set_visible(b is None)
        self.lbl_resumo.set_visible(b is not None)
        if b is None:
            for cartao in self._cartoes.values():
                self.caixa_agentes.remove(cartao)
            self._cartoes = {}
            self.sem_sub.set_visible(False)
            return False
        vistos = []
        # agente principal
        if b.vivo:
            estado, classe = _t("Trabalhando…"), "rodando"
            sub = b.status_atual() or _t("Pensando…")
        elif b.interrompido:
            estado, classe = _t("Interrompido"), "parado"
            sub = b.resumo()
        else:
            estado, classe = _t("Concluído"), "ok"
            sub = b.resumo()
        self._cartao("principal", vistos).atualizar(
            self.nome_agente or _t("Agente de IA"), _t("Principal"), sub, estado, classe,
            self.icone_agente or "simba-agente")
        # subagentes e trabalhos em segundo plano, cada um com o seu estado
        extras = [p for p in b.passos if p.get("tipo") == "subagente" or p.get("fundo")]
        for i, p in enumerate(extras):
            estado, classe = estado_subagente(p, b.vivo)
            subagente = p.get("tipo") == "subagente"
            nome = str(p.get("texto") or "")
            for prefixo in (_t("Subagente:"), _t("Em segundo plano:")):
                if nome.startswith(prefixo):
                    nome = nome[len(prefixo):].strip()
            info = []
            if p.get("acoes"):
                info.append(f"{p['acoes']} {_t('ação') if p['acoes'] == 1 else _t('ações')}")
            if p.get("tokens"):
                info.append(f"{tokens_curto(p['tokens'])} tokens")
            filhos = b.filhos.get(p.get("id")) or []
            ultima = next((f for f in reversed(filhos) if f.get("tipo") != "pensamento"), None)
            atual = (ultima.get("texto") if ultima else None) or p.get("detalhe") or ""
            linhas = " · ".join(info)
            if atual:
                linhas = f"{linhas}\n↳ {atual}" if linhas else f"↳ {atual}"
            self._cartao(p.get("id") or f"extra-{i}", vistos).atualizar(
                nome or (_t("Subagente") if subagente else _t("Tarefa")),
                _t("Subagente") if subagente else _t("Em segundo plano"),
                linhas, estado, classe,
                atividade.ICONES["subagente" if subagente else "fundo"])
        for chave in [c for c in self._cartoes if c not in vistos]:
            self.caixa_agentes.remove(self._cartoes.pop(chave))
        # ordem: na ordem em que apareceram, antes do aviso "nenhum subagente"
        ant = self.vazio_agentes
        for chave in vistos:
            c = self._cartoes[chave]
            if c.get_prev_sibling() is not ant:
                self.caixa_agentes.reorder_child_after(c, ant)
            ant = c
        self.sem_sub.set_visible(not extras)
        if self.sem_sub.get_prev_sibling() is not ant:
            self.caixa_agentes.reorder_child_after(self.sem_sub, ant)
        resumo = contar_acoes(b.passos)
        self.lbl_resumo.set_label(resumo or (_t("Ainda nada executado.") if b.vivo else _t("Nenhuma ação executada.")))
        return False

    def _cartao(self, chave, vistos):
        vistos.append(chave)
        c = self._cartoes.get(chave)
        if c is None:
            c = CartaoAgente()
            self._cartoes[chave] = c
            self.caixa_agentes.append(c)
        return c

    def agentes_listados(self):
        """[(nome, estado)] dos cartões de agentes (testes e leitores de tela)."""
        saida = []
        f = self.caixa_agentes.get_first_child()
        while f is not None:
            if isinstance(f, CartaoAgente):
                saida.append((f.nome, f.estado))
            f = f.get_next_sibling()
        return saida

    # ── rolagem: acompanha o fim enquanto a pessoa não rola para cima ───────
    def _rolagem_mudou(self, adj):
        self.seguir = adj.get_value() + adj.get_page_size() >= adj.get_upper() - 40

    def _rolar_fim(self):
        adj = self.rolagem.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())
        return False


class CartaoAgente(Gtk.Box):
    """Cartão de um agente/subagente; atualizar() troca só o que mudou."""

    CLASSES = ("rodando", "ok", "erro", "parado")

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        self.add_css_class("detalhes-agente")
        self.nome = self.estado = None
        self._classe = None
        topo = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.avatar = Gtk.Box()
        self.avatar.add_css_class("detalhes-agente-avatar")
        self.avatar.set_valign(Gtk.Align.START)
        self.img = Gtk.Image.new_from_icon_name("simba-agente")
        self.img.set_pixel_size(16)
        self.img.set_halign(Gtk.Align.CENTER)
        self.img.set_valign(Gtk.Align.CENTER)
        self.avatar.set_halign(Gtk.Align.START)
        self.avatar.set_hexpand(False)
        self.avatar.append(self.img)
        topo.append(self.avatar)
        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        textos.set_hexpand(True)
        self.lbl_nome = _rotulo("", ("detalhes-agente-nome",))
        self.lbl_nome.set_ellipsize(Pango.EllipsizeMode.END)
        textos.append(self.lbl_nome)
        linha2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.lbl_papel = _rotulo("", ("detalhes-agente-papel",))
        self.lbl_papel.set_ellipsize(Pango.EllipsizeMode.END)
        linha2.append(self.lbl_papel)
        textos.append(linha2)
        topo.append(textos)
        self.selo = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=5)
        self.selo.add_css_class("passo-estado")
        self.selo.set_valign(Gtk.Align.CENTER)
        self.selo.set_halign(Gtk.Align.START)
        self.ponto = Gtk.Box()
        self.ponto.add_css_class("detalhes-ponto")
        self.ponto.set_valign(Gtk.Align.CENTER)
        self.selo.append(self.ponto)
        self.lbl_estado = Gtk.Label()
        self.selo.append(self.lbl_estado)
        linha2.append(self.selo)
        self.append(topo)
        self.lbl_sub = _rotulo("", ("detalhes-agente-sub",))
        self.lbl_sub.set_wrap(True)
        self.lbl_sub.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.lbl_sub.set_lines(3)
        self.lbl_sub.set_ellipsize(Pango.EllipsizeMode.END)
        self.append(self.lbl_sub)

    def atualizar(self, nome, papel, sub, estado, classe, icone):
        if nome != self.nome:
            self.lbl_nome.set_label(nome)
            self.lbl_nome.set_tooltip_text(nome)
        self.nome, self.estado = nome, estado
        if self.lbl_papel.get_label() != papel:
            self.lbl_papel.set_label(papel)
        if self.lbl_estado.get_label() != estado:
            self.lbl_estado.set_label(estado)
        sub = sub or ""
        if self.lbl_sub.get_label() != sub:
            self.lbl_sub.set_label(sub)
        self.lbl_sub.set_visible(bool(sub))
        if self.img.get_icon_name() != icone:
            self.img.set_from_icon_name(icone)
        if classe != self._classe:
            for c in self.CLASSES:
                self.remove_css_class(c)
                self.selo.remove_css_class(c)
            self.add_css_class(classe)
            self.selo.add_css_class(classe)
            self._classe = classe
