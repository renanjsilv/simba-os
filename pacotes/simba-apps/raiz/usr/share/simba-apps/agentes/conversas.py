"""Barra lateral esquerda: nova conversa, procurar e conversas recentes.

Como a barra do Claude e do ChatGPT: "Nova conversa" e "Procurar" em cima, a lista
"Recentes" (título, agente e quando) embaixo, com a conversa aberta destacada e um
menu por conversa (renomear, exportar, apagar). A lista é lida dos arquivos salvos
numa thread, para a janela não engasgar com muitas conversas.
"""
from pathlib import Path
import sys
import threading
import time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

sys.path.insert(0, "/usr/share/simba-apps/idiomas")
from simba_i18n import t as _t  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marcas  # noqa: E402
import motor as M  # noqa: E402


def _assistente_da_conversa(dados):
    """(chave, modelo) do último agente que respondeu — para o logo e o nome."""
    for msg in reversed(dados.get("mensagens") or []):
        if isinstance(msg, dict) and msg.get("tipo") == "assistant" and msg.get("agente"):
            return msg["agente"], msg.get("modelo") or ""
    return "", ""


def agente_da_conversa(dados):
    chave, _modelo = _assistente_da_conversa(dados)
    return M.AGENTES.get(chave, {}).get("nome", chave) if chave else ""


def grupo_da_data(epoch, agora=None):
    """Seção da lista (como no ChatGPT): Hoje, Ontem, 7 dias, 30 dias, Mais antigas."""
    try:
        epoch = float(epoch)
    except (TypeError, ValueError):
        return _t("Mais antigas")
    agora = time.localtime(agora or time.time())
    meia_noite = time.mktime((agora.tm_year, agora.tm_mon, agora.tm_mday, 0, 0, 0, 0, 0, -1))
    if epoch >= meia_noite:
        return _t("Hoje")
    if epoch >= meia_noite - 86400:
        return _t("Ontem")
    if epoch >= meia_noite - 7 * 86400:
        return _t("Últimos 7 dias")
    if epoch >= meia_noite - 30 * 86400:
        return _t("Últimos 30 dias")
    return _t("Mais antigas")


def quando_curto(epoch):
    """Horário compacto da linha: a data só aparece quando o grupo ainda não diz o dia."""
    try:
        momento = time.localtime(float(epoch))
    except (TypeError, ValueError, OSError):
        return ""
    grupo = grupo_da_data(epoch)
    if grupo == _t("Hoje"):
        return time.strftime("%H:%M", momento)
    if grupo == _t("Ontem"):
        return _t("Ontem")
    if grupo in (_t("Últimos 7 dias"), _t("Últimos 30 dias")):
        return time.strftime("%d/%m", momento)
    return time.strftime("%d/%m/%y", momento)


def corresponde(dados, termo):
    termo = termo.lower()
    if termo in str(dados.get("titulo") or "").lower() or termo in str(dados.get("pasta") or "").lower():
        return True
    return any(termo in str(m.get("texto", "")).lower()
               for m in dados.get("mensagens") or [] if isinstance(m, dict))


class BarraConversas(Gtk.Box):
    """listar() → [dados]; abrir(dados); nova(); renomear(dados); apagar(dados); quando(epoch) → texto."""

    def __init__(self, listar, abrir, nova, renomear, apagar, quando):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add_css_class("barra-conversas")
        self.set_size_request(240, -1)
        self.listar, self.abrir, self.nova = listar, abrir, nova
        self.renomear, self.apagar, self.quando = renomear, apagar, quando
        self.itens = []
        self.atual = None
        self._lendo = False
        self._de_novo = False

        # Ação principal (Nova conversa) com peso próprio; Procurar fica discreto ao lado.
        acoes = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        acoes.add_css_class("barra-acoes")
        self.btn_nova = self._acao("list-add-symbolic", _t("Nova conversa"), lambda: self.nova(),
                                   f"{_t('Nova conversa')} (Ctrl+L)")
        self.btn_nova.add_css_class("barra-acao-nova")
        self.btn_nova.set_hexpand(True)
        acoes.append(self.btn_nova)
        self.btn_procurar = Gtk.Button.new_from_icon_name("edit-find-symbolic")
        self.btn_procurar.add_css_class("flat")
        self.btn_procurar.add_css_class("barra-acao-icone")
        self.btn_procurar.set_tooltip_text(_t("Procurar nas conversas"))
        self.btn_procurar.connect("clicked", lambda _b: self._alternar_busca())
        acoes.append(self.btn_procurar)
        self.append(acoes)

        self.busca = Gtk.SearchEntry()
        self.busca.set_placeholder_text(_t("Procurar nas conversas…"))
        self.busca.add_css_class("barra-conversas-busca")
        self.busca.connect("search-changed", lambda _e: self._preencher())
        self.busca.connect("stop-search", lambda _e: self._alternar_busca(False))
        self.rev_busca = Gtk.Revealer()
        self.rev_busca.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        self.rev_busca.set_transition_duration(180)
        self.rev_busca.set_child(self.busca)
        self.append(self.rev_busca)

        # "Recentes" é o nível de cima da hierarquia; a contagem ajuda a orientar.
        self.secao = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.secao.add_css_class("barra-secao-caixa")
        self.titulo = Gtk.Label(label=_t("Recentes"), xalign=0)
        self.titulo.add_css_class("barra-secao")
        self.titulo.set_hexpand(True)
        self.contagem = Gtk.Label(xalign=1)
        self.contagem.add_css_class("barra-secao-contagem")
        self.secao.append(self.titulo)
        self.secao.append(self.contagem)
        self.secao.set_visible(False)
        self.append(self.secao)

        self.lista = Gtk.ListBox()
        self.lista.add_css_class("barra-lista")
        self.lista.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.lista.connect("row-activated", self._ativada)
        self.lista.set_header_func(self._cabecalho)
        self.rolagem = Gtk.ScrolledWindow()
        self.rolagem.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.rolagem.set_vexpand(True)
        self.rolagem.set_child(self.lista)
        self.append(self.rolagem)

        # Estado vazio com ícone e frase curta, centralizado no espaço que sobra.
        self.vazio = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.vazio.add_css_class("barra-vazio")
        self.vazio.set_valign(Gtk.Align.CENTER)
        self.vazio.set_vexpand(True)
        self.vazio_icone = Gtk.Image.new_from_icon_name(marcas.GENERICO)
        self.vazio_icone.set_pixel_size(32)
        self.vazio_icone.set_halign(Gtk.Align.CENTER)
        self.vazio_icone.add_css_class("barra-vazio-icone")
        self.vazio_texto = Gtk.Label(xalign=0.5)
        self.vazio_texto.add_css_class("barra-vazio-texto")
        self.vazio_texto.set_wrap(True)
        self.vazio_texto.set_justify(Gtk.Justification.CENTER)
        self.vazio_texto.set_max_width_chars(26)
        self.vazio.append(self.vazio_icone)
        self.vazio.append(self.vazio_texto)
        self.vazio.set_visible(False)
        self.append(self.vazio)
        self.recarregar()

    def _acao(self, icone, texto, fn, dica):
        btn = Gtk.Button()
        btn.add_css_class("flat")
        btn.add_css_class("barra-acao")
        caixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        img = Gtk.Image.new_from_icon_name(icone)
        img.set_pixel_size(16)
        caixa.append(img)
        caixa.append(Gtk.Label(label=texto, xalign=0))
        btn.set_child(caixa)
        btn.set_tooltip_text(dica)
        btn.connect("clicked", lambda _b: fn())
        return btn

    def _alternar_busca(self, abrir=None):
        abrir = (not self.rev_busca.get_reveal_child()) if abrir is None else abrir
        self.rev_busca.set_reveal_child(abrir)
        if abrir:
            self.busca.grab_focus()
        elif self.busca.get_text():
            self.busca.set_text("")

    def procurar(self):
        self._alternar_busca(True)

    # ── dados ────────────────────────────────────────────────────────────────
    def recarregar(self):
        """Relê as conversas salvas (numa thread) e remonta a lista."""
        if self._lendo:
            self._de_novo = True
            return
        self._lendo = True

        def ler():
            try:
                itens = self.listar()
            except Exception:  # noqa: BLE001
                itens = []
            GLib.idle_add(self._lidas, itens)
        threading.Thread(target=ler, daemon=True).start()

    def _lidas(self, itens):
        self._lendo = False
        self.itens = itens
        self._preencher()
        if self._de_novo:
            self._de_novo = False
            self.recarregar()
        return False

    def marcar_atual(self, cid):
        self.atual = cid
        linha = self.lista.get_first_child()
        while linha is not None:
            if getattr(linha, "dados", None) is not None and linha.dados.get("id") == cid:
                self.lista.select_row(linha)
                return
            linha = linha.get_next_sibling()
        self.lista.unselect_all()

    def _preencher(self):
        filho = self.lista.get_first_child()
        while filho is not None:
            self.lista.remove(filho)
            filho = self.lista.get_first_child()
        termo = self.busca.get_text().strip()
        itens = [d for d in self.itens if corresponde(d, termo)] if termo else self.itens
        self.titulo.set_label(_t("Resultados") if termo else _t("Recentes"))
        self.contagem.set_label(str(len(itens)) if itens else "")
        self.secao.set_visible(bool(itens))
        for dados in itens:
            self.lista.append(self._linha(dados))
        # Com a lista vazia, o estado vazio ocupa o espaço (em vez de ficar colado embaixo).
        self.rolagem.set_visible(bool(itens))
        self.vazio.set_visible(not itens)
        self.vazio_icone.set_from_icon_name("system-search-symbolic" if termo else marcas.GENERICO)
        self.vazio_texto.set_label(_t("Nenhuma conversa encontrada.") if termo
                                   else _t("Suas conversas aparecem aqui automaticamente."))
        self.marcar_atual(self.atual)

    def titulos(self):
        """Títulos na ordem da lista (testes)."""
        saida = []
        linha = self.lista.get_first_child()
        while linha is not None:
            if getattr(linha, "dados", None) is not None:
                saida.append(linha.dados.get("titulo") or _t("Nova conversa"))
            linha = linha.get_next_sibling()
        return saida

    def _linha(self, dados):
        linha = Gtk.ListBoxRow()
        linha.add_css_class("barra-conversa")
        linha.dados = dados
        titulo = dados.get("titulo") or _t("Nova conversa")

        # Grade da linha: logo do agente | título + metadados | menu (coluna fixa,
        # para o horário não andar quando o "…" aparece).
        caixa = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        chave, modelo = _assistente_da_conversa(dados)
        # O logo fica num chip de tamanho fixo; aplicar o CSS direto na imagem
        # (como no avatar da resposta) centraliza o ícone — um Gtk.Box encosta
        # o ícone à esquerda do chip.
        logo = marcas.imagem(marcas.icone_agente(chave, modelo), 15)
        logo.add_css_class("barra-conversa-avatar")
        logo.set_size_request(24, 24)
        logo.set_halign(Gtk.Align.CENTER)
        logo.set_valign(Gtk.Align.CENTER)
        logo.set_opacity(0.92)
        caixa.append(logo)

        textos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        textos.set_hexpand(True)
        textos.set_valign(Gtk.Align.CENTER)

        lbl = Gtk.Label(label=titulo, xalign=0)
        lbl.set_wrap(True)
        lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        lbl.set_lines(2)
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
        lbl.add_css_class("barra-conversa-titulo")
        textos.append(lbl)

        meta = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        sub = Gtk.Label(label=agente_da_conversa(dados), xalign=0)
        sub.set_ellipsize(Pango.EllipsizeMode.END)
        sub.set_hexpand(True)
        sub.add_css_class("barra-conversa-sub")
        meta.append(sub)
        hora = Gtk.Label(label=quando_curto(dados.get("atualizada")), xalign=1)
        hora.add_css_class("barra-conversa-hora")
        meta.append(hora)
        textos.append(meta)
        caixa.append(textos)
        linha.set_tooltip_text(titulo)

        menu = Gtk.MenuButton(icon_name="view-more-symbolic")
        menu.add_css_class("flat")
        menu.add_css_class("barra-conversa-menu")
        menu.set_valign(Gtk.Align.CENTER)
        menu.set_tooltip_text(_t("Mais opções"))
        pop = Gtk.Popover()
        opcoes = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for icone, texto, fn in (("document-edit-symbolic", _t("Renomear"), self.renomear),
                                 ("user-trash-symbolic", _t("Apagar"), self.apagar)):
            b = Gtk.Button()
            b.add_css_class("flat")
            b.add_css_class("barra-conversa-opcao")
            c = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            c.append(Gtk.Image.new_from_icon_name(icone))
            c.append(Gtk.Label(label=texto, xalign=0))
            b.set_child(c)
            b.connect("clicked", lambda _b, f=fn, d=dados, p=pop: (p.popdown(), f(d)))
            opcoes.append(b)
        pop.set_child(opcoes)
        menu.set_popover(pop)
        caixa.append(menu)
        linha.set_child(caixa)
        return linha

    def _cabecalho(self, linha, anterior):
        """Título do grupo de datas acima da 1ª conversa de cada grupo."""
        dados = getattr(linha, "dados", None) or {}
        grupo = grupo_da_data(dados.get("atualizada"))
        ant = getattr(anterior, "dados", None) if anterior is not None else None
        if ant is not None and grupo_da_data(ant.get("atualizada")) == grupo:
            linha.set_header(None)
            return
        atual = linha.get_header()
        if atual is not None and getattr(atual, "grupo", None) == grupo:
            return
        # Rótulo de grupo alinhado com o texto do título das linhas (não com a borda).
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        caixa.add_css_class("barra-grupo-caixa")
        if anterior is None:
            caixa.add_css_class("primeiro")
        lbl = Gtk.Label(label=grupo, xalign=0)
        lbl.add_css_class("barra-grupo")
        caixa.append(lbl)
        caixa.grupo = grupo
        linha.set_header(caixa)

    def _ativada(self, _lista, linha):
        dados = getattr(linha, "dados", None)
        if dados is not None and dados.get("id") != self.atual:
            self.abrir(dados)
