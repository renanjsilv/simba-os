"""Tela "Skills" do painel Detalhes: descobrir skills no GitHub, instalar nos agentes e usar."""
import threading
import time

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

import skills as S  # noqa: E402
from simba_i18n import t as _t  # noqa: E402


def _rotulo(texto="", classes=(), **kw):
    lbl = Gtk.Label(label=texto, xalign=0, **kw)
    for c in classes:
        lbl.add_css_class(c)
    return lbl


def _estrelas(n):
    if not n:
        return ""
    return "★ " + (f"{n / 1000:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " mil" if n >= 1000 else str(n))


def _em_segundo_plano(func, pronto):
    def alvo():
        try:
            r, erro = func(), None
        except S.Erro as e:
            r, erro = None, str(e)
        except Exception as e:  # noqa: BLE001
            r, erro = None, _t("Erro inesperado: %1", e)
        GLib.idle_add(lambda: (pronto(r, erro), False)[1])
    threading.Thread(target=alvo, daemon=True).start()


class TelaSkills(Gtk.Box):
    def __init__(self, ao_voltar, usar=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("detalhes-tela-agente")
        self.usar = usar
        self.instaladas_nomes = set()
        self._busca_id = 0

        cab = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        cab.add_css_class("detalhes-agente-cab")
        voltar = Gtk.Button(icon_name="go-previous-symbolic")
        for c in ("flat", "detalhes-voltar"):
            voltar.add_css_class(c)
        voltar.set_valign(Gtk.Align.CENTER)
        voltar.set_tooltip_text(_t("Voltar"))
        voltar.connect("clicked", lambda _b: ao_voltar())
        cab.append(voltar)
        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        textos.set_hexpand(True)
        textos.append(_rotulo(_t("Skills"), ("detalhes-agente-nome",)))
        textos.append(_rotulo(_t("Habilidades extras para os agentes"), ("detalhes-agente-papel",)))
        cab.append(textos)
        self.append(cab)

        self.abas = Gtk.Stack()
        self.abas.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        troca = Gtk.StackSwitcher(stack=self.abas, halign=Gtk.Align.CENTER)
        troca.set_margin_top(6)
        troca.set_margin_bottom(6)
        self.append(troca)
        self.append(self.abas)
        self.abas.set_vexpand(True)

        # ── Descobrir ──
        desc = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        desc.set_margin_start(10)
        desc.set_margin_end(10)
        self.busca = Gtk.SearchEntry(placeholder_text=_t("Buscar skills no GitHub…"))
        self.busca.connect("search-changed", self._buscar_atrasado)
        desc.append(self.busca)
        aviso = _rotulo(_t("Skills podem trazer scripts que o agente executa: instale só de fontes que você confia."),
                        ("detalhes-dica",))
        aviso.set_wrap(True)
        desc.append(aviso)
        self.voltar_colecoes = Gtk.Button(label=_t("‹ Coleções"), halign=Gtk.Align.START)
        self.voltar_colecoes.add_css_class("flat")
        self.voltar_colecoes.set_visible(False)
        self.voltar_colecoes.connect("clicked", lambda _b: self.mostrar_colecoes())
        desc.append(self.voltar_colecoes)
        self.estado = _rotulo("", ("detalhes-dica",))
        self.estado.set_wrap(True)
        desc.append(self.estado)
        rol = Gtk.ScrolledWindow(vexpand=True)
        rol.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.lista = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        rol.set_child(self.lista)
        desc.append(rol)
        self.abas.add_titled(desc, "descobrir", _t("Descobrir"))

        # ── Instaladas ──
        inst = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        inst.set_margin_start(10)
        inst.set_margin_end(10)
        rol2 = Gtk.ScrolledWindow(vexpand=True)
        rol2.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.lista_inst = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        rol2.set_child(self.lista_inst)
        inst.append(rol2)
        rodape = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        rodape.set_margin_top(4)
        rodape.set_margin_bottom(8)
        self.lbl_atual = _rotulo(_t("Atualizadas sozinhas todo dia."), ("detalhes-dica",))
        self.lbl_atual.set_wrap(True)
        self.lbl_atual.set_hexpand(True)
        rodape.append(self.lbl_atual)
        self.btn_atualizar = Gtk.Button(label=_t("Atualizar agora"))
        self.btn_atualizar.add_css_class("flat")
        self.btn_atualizar.connect("clicked", lambda _b: self.atualizar_agora())
        rodape.append(self.btn_atualizar)
        inst.append(rodape)
        self.abas.add_titled(inst, "instaladas", _t("Instaladas"))

    # ── ao abrir ───────────────────────────────────────────────────────────────
    def abrir(self):
        self.carregar_instaladas()
        if not self.lista.get_first_child():
            self.mostrar_colecoes()
        # atualização automática também ao abrir, se a última foi há mais de um dia
        try:
            import json
            ult = json.loads((S.CACHE / "ultima-atualizacao.json").read_text()).get("quando", 0)
        except (OSError, ValueError):
            ult = 0
        if time.time() - ult > 86400 and S.instaladas():
            self.atualizar_agora(silencioso=True)

    def _limpar(self, caixa):
        while (f := caixa.get_first_child()) is not None:
            caixa.remove(f)

    def _cartao(self):
        c = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        c.add_css_class("detalhes-cartao")
        c.set_margin_bottom(2)
        return c

    # ── coleções (em alta) ─────────────────────────────────────────────────────
    def mostrar_colecoes(self):
        self.voltar_colecoes.set_visible(False)
        self.estado.set_label(_t("Carregando as coleções mais conhecidas…"))
        self._limpar(self.lista)

        def pronto(r, erro):
            self.estado.set_label(erro or _t("Coleções mais conhecidas e em alta no GitHub:"))
            for c in r or []:
                self.lista.append(self._linha_colecao(c))
        _em_segundo_plano(S.em_alta, pronto)

    def _linha_colecao(self, c):
        b = Gtk.Button()
        b.add_css_class("flat")
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        caixa.set_margin_top(6)
        caixa.set_margin_bottom(6)
        topo = Gtk.Box(spacing=6)
        nome = _rotulo(c["repo"], ("detalhes-valor",))
        nome.set_ellipsize(Pango.EllipsizeMode.END)
        nome.set_hexpand(True)
        topo.append(nome)
        topo.append(_rotulo(_estrelas(c.get("estrelas")), ("detalhes-dica",)))
        caixa.append(topo)
        sub = " · ".join(x for x in (c.get("rotulo"), c.get("descricao")) if x)
        if sub:
            d = _rotulo(sub, ("detalhes-dica",))
            d.set_wrap(True)
            d.set_lines(2)
            d.set_ellipsize(Pango.EllipsizeMode.END)
            caixa.append(d)
        b.set_child(caixa)
        b.connect("clicked", lambda _b: self.mostrar_repo(c["repo"]))
        return b

    def mostrar_repo(self, repo):
        self.voltar_colecoes.set_visible(True)
        self.estado.set_label(_t("Lendo as skills de %1…", repo))
        self._limpar(self.lista)

        def pronto(r, erro):
            if erro:
                self.estado.set_label(erro)
                return
            self.estado.set_label(_t("%1 skills em %2", len(r), repo) if r else _t("Nenhuma skill (SKILL.md) em %1.", repo))
            for s in r:
                self.lista.append(self._linha_skill(s))
        _em_segundo_plano(lambda: S.skills_do_repo(repo), pronto)

    # ── busca ──────────────────────────────────────────────────────────────────
    def _buscar_atrasado(self, entrada):
        self._busca_id += 1
        meu = self._busca_id
        GLib.timeout_add(500, lambda: (meu == self._busca_id and self._buscar(entrada.get_text()), False)[1])

    def _buscar(self, texto):
        if not texto.strip():
            self.mostrar_colecoes()
            return
        self.voltar_colecoes.set_visible(True)
        self.estado.set_label(_t("Buscando “%1” no GitHub…", texto))
        self._limpar(self.lista)
        meu = self._busca_id

        def pronto(r, erro):
            if meu != self._busca_id:
                return
            if erro:
                self.estado.set_label(erro)
                return
            sk, rp = r.get("skills", []), r.get("repos", [])
            self.estado.set_label(_t("%1 skills e %2 coleções encontradas", len(sk), len(rp)) if (sk or rp)
                                  else _t("Nada encontrado para “%1”.", texto))
            for s in sk:
                self.lista.append(self._linha_skill(s))
            for c in rp:
                self.lista.append(self._linha_colecao(c))
        _em_segundo_plano(lambda: S.buscar(texto), pronto)

    # ── uma skill ──────────────────────────────────────────────────────────────
    def _linha_skill(self, s, instalada=False):
        c = self._cartao()
        corpo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        corpo.set_margin_start(10)
        corpo.set_margin_end(10)
        corpo.set_margin_top(8)
        corpo.set_margin_bottom(8)
        nome = _rotulo(s["nome"], ("detalhes-valor",))
        nome.set_ellipsize(Pango.EllipsizeMode.END)
        corpo.append(nome)
        if s.get("descricao"):
            d = _rotulo(s["descricao"], ("detalhes-dica",))
            d.set_wrap(True)
            d.set_lines(3)
            d.set_ellipsize(Pango.EllipsizeMode.END)
            corpo.append(d)
        meta = s.get("repo", "")
        if instalada and s.get("atualizada"):
            meta += _t(" · atualizada %1", s["atualizada"][:10])
        elif s.get("estrelas"):
            meta += "  " + _estrelas(s["estrelas"])
        m = _rotulo(meta, ("detalhes-dica",))
        m.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        corpo.append(m)
        botoes = Gtk.Box(spacing=6, halign=Gtk.Align.END)
        botoes.set_margin_top(4)
        if instalada:
            usar = Gtk.Button(label=_t("Usar"))
            usar.add_css_class("suggested-action")
            usar.set_tooltip_text(_t("Escreve no chat um pedido usando esta skill"))
            usar.connect("clicked", lambda _b: self.usar and self.usar(s["nome"], s.get("descricao", "")))
            botoes.append(usar)
            rem = Gtk.Button(label=_t("Remover"))
            rem.add_css_class("destructive-action")
            rem.connect("clicked", lambda b: self._remover(s["nome"], b))
            botoes.append(rem)
        else:
            ja = S._nome_seguro(s["nome"]) in self.instaladas_nomes
            b = Gtk.Button(label=_t("Instalada") if ja else _t("Instalar"))
            b.set_sensitive(not ja)
            if not ja:
                b.add_css_class("suggested-action")
            b.connect("clicked", lambda bt: self._instalar(s, bt))
            botoes.append(b)
        corpo.append(botoes)
        c.append(corpo)
        return c

    def _instalar(self, s, botao):
        botao.set_sensitive(False)
        botao.set_label(_t("Instalando…"))

        def pronto(r, erro):
            if erro:
                botao.set_label(_t("Tentar de novo"))
                botao.set_sensitive(True)
                botao.set_tooltip_text(erro)
                self.estado.set_label(erro)
                return
            botao.set_label(_t("Instalada"))
            botao.remove_css_class("suggested-action")
            n = len(r.get("agentes", []))
            self.estado.set_label(_t("“%1” instalada em %2 pastas de agentes. Use pela aba Instaladas.", r["nome"], n))
            self.carregar_instaladas()
        _em_segundo_plano(lambda: S.instalar(s["repo"], s["caminho"]), pronto)

    def _remover(self, nome, botao):
        botao.set_sensitive(False)
        _em_segundo_plano(lambda: S.remover(nome), lambda r, e: self.carregar_instaladas())

    # ── instaladas ─────────────────────────────────────────────────────────────
    def carregar_instaladas(self):
        def pronto(r, erro):
            self._limpar(self.lista_inst)
            r = r or []
            self.instaladas_nomes = {s["nome"] for s in r}
            if not r:
                vazio = _rotulo(_t("Nenhuma skill instalada ainda. Procure em Descobrir."), ("detalhes-dica",))
                vazio.set_wrap(True)
                vazio.set_margin_top(12)
                self.lista_inst.append(vazio)
            for s in r:
                self.lista_inst.append(self._linha_skill(s, instalada=True))
            if self.ao_mudar:
                self.ao_mudar(len(r))
        _em_segundo_plano(S.instaladas, pronto)

    ao_mudar = None

    def atualizar_agora(self, silencioso=False):
        self.btn_atualizar.set_sensitive(False)
        self.lbl_atual.set_label(_t("Conferindo atualizações no GitHub…"))

        def pronto(r, erro):
            self.btn_atualizar.set_sensitive(True)
            if erro or not r:
                self.lbl_atual.set_label(erro or _t("Atualizadas sozinhas todo dia."))
                return
            m = r.get("mudaram", [])
            self.lbl_atual.set_label(_t("Atualizadas agora: %1", ", ".join(m)) if m
                                     else _t("Tudo em dia. Atualizadas sozinhas todo dia."))
            self.carregar_instaladas()
        _em_segundo_plano(lambda: S.atualizar(silencioso=True), pronto)
