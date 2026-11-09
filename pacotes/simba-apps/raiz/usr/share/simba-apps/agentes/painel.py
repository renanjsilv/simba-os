"""Painel de uso e custo: quanto cada agente respondeu, gastou e quanto do limite usou.

Os números vêm das conversas salvas (cada resposta guarda tokens e custo quando o
agente informa) e do widget de limites do Simba (janelas de 5 h e 7 dias).
"""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import threading
import time

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk, Pango  # noqa: E402

sys.path.insert(0, "/usr/share/simba-apps/idiomas")
from simba_i18n import t as _t  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marcas  # noqa: E402
import motor as M  # noqa: E402

CONVERSAS = Path.home() / ".local/state/simba/agents/conversas"


def compacto(n):
    """1284 → '1,3 mil'; 2_400_000 → '2,4 mi'."""
    n = float(n or 0)
    for div, nome in ((1_000_000, "mi"), (1000, "mil")):
        if n >= div:
            return f"{n / div:.1f}".replace(".0", "").replace(".", ",") + f" {nome}"
    return str(int(n))


def dinheiro(v):
    v = float(v or 0)
    if v and v < 0.01:
        return "< US$ 0,01"
    return "US$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def coletar(agora=None):
    """Soma as respostas salvas por período (hoje, 7 e 30 dias) e por agente (30 dias)."""
    agora = agora or time.time()
    hoje0 = datetime.fromtimestamp(agora).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    limites = {"hoje": hoje0, "7d": agora - 7 * 86400, "30d": agora - 30 * 86400}
    periodos = {k: {"respostas": 0, "tokens": 0, "custo": 0.0} for k in limites}
    agentes = {}
    try:
        arquivos = list(CONVERSAS.glob("*.json"))
    except OSError:
        arquivos = []
    for arq in arquivos:
        try:
            if arq.stat().st_mtime < limites["30d"]:
                continue  # conversa sem atividade no último mês
            dados = json.loads(arq.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for msg in dados.get("mensagens") or []:
            if not isinstance(msg, dict) or msg.get("tipo") != "assistant":
                continue
            quando = float(msg.get("quando") or 0)
            if quando < limites["30d"]:
                continue
            uso = msg.get("uso") or {}
            tokens = int(uso.get("entrada", 0) or 0) + int(uso.get("saida", 0) or 0)
            custo = float(uso.get("custo", 0) or 0)
            for k, inicio in limites.items():
                if quando >= inicio:
                    p = periodos[k]
                    p["respostas"] += 1
                    p["tokens"] += tokens
                    p["custo"] += custo
            a = agentes.setdefault(msg.get("agente") or "?", {"respostas": 0, "tokens": 0, "custo": 0.0,
                                                               "modelo": ""})
            a["respostas"] += 1
            a["tokens"] += tokens
            a["custo"] += custo
            a["modelo"] = a["modelo"] or msg.get("modelo") or ""
    return periodos, agentes


class PainelMixin:
    def _abrir_painel_uso(self):
        dialog = Adw.Dialog()
        dialog.set_title(_t("Uso e custo"))
        dialog.set_content_width(780)
        dialog.set_content_height(640)
        toolbar = Adw.ToolbarView()
        toolbar.add_top_bar(Adw.HeaderBar())
        rolagem = Gtk.ScrolledWindow()
        rolagem.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        carregando = Gtk.Spinner(spinning=True, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        carregando.set_size_request(32, 32)
        rolagem.set_child(carregando)
        toolbar.set_content(rolagem)
        dialog.set_child(toolbar)
        dialog.present(self)

        def ler():
            dados = coletar()
            GLib.idle_add(lambda: (rolagem.set_child(self._painel_conteudo(*dados)), False)[1])
        threading.Thread(target=ler, daemon=True).start()

    def _painel_conteudo(self, periodos, agentes):
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
        for lado in ("top", "bottom", "start", "end"):
            getattr(caixa, f"set_margin_{lado}")(24)

        # Fileira de números: hoje, 7 dias, 30 dias
        fileira = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, homogeneous=True)
        for chave, rotulo in (("hoje", _t("Hoje")), ("7d", _t("Últimos 7 dias")), ("30d", _t("Últimos 30 dias"))):
            p = periodos[chave]
            cartao = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            cartao.add_css_class("uso-cartao")
            r = Gtk.Label(label=rotulo, xalign=0)
            r.add_css_class("uso-rotulo")
            v = Gtk.Label(label=dinheiro(p["custo"]), xalign=0)
            v.add_css_class("uso-valor")
            d = Gtk.Label(xalign=0, wrap=True)
            d.set_label(f"{p['respostas']} {_t('respostas')} · {compacto(p['tokens'])} tokens")
            d.add_css_class("uso-detalhe")
            for w in (r, v, d):
                cartao.append(w)
            fileira.append(cartao)
        caixa.append(fileira)

        nota = Gtk.Label(
            label=_t("Custo estimado informado pelos próprios agentes (preço de API). Em planos por assinatura "
                     "é só uma referência, não uma cobrança. Agentes que não informam uso aparecem só com as respostas."),
            wrap=True, xalign=0)
        nota.add_css_class("uso-detalhe")
        caixa.append(nota)

        # Por agente (30 dias): tabela com uma barra fina, uma cor só
        titulo = Gtk.Label(label=_t("Por agente · últimos 30 dias"), xalign=0)
        titulo.add_css_class("heading")
        caixa.append(titulo)
        if not agentes:
            vazio = Gtk.Label(label=_t("Nenhuma resposta nos últimos 30 dias."), xalign=0)
            vazio.add_css_class("uso-detalhe")
            caixa.append(vazio)
        else:
            caixa.append(self._painel_tabela(agentes))

        # Limite agora
        limites = self._painel_limites()
        if limites is not None:
            t2 = Gtk.Label(label=_t("Limite usado agora"), xalign=0)
            t2.add_css_class("heading")
            caixa.append(t2)
            caixa.append(limites)
        return caixa

    def _painel_tabela(self, agentes):
        grade = Gtk.Grid(column_spacing=16, row_spacing=10)
        grade.add_css_class("uso-tabela")
        usa_custo = any(a["custo"] for a in agentes.values())
        chave = "custo" if usa_custo else "tokens"
        if not any(a[chave] for a in agentes.values()):
            chave = "respostas"
        maior = max(a[chave] for a in agentes.values()) or 1
        for col, texto in enumerate((_t("Agente"), "", _t("Respostas"), "Tokens", _t("Custo"))):
            cab = Gtk.Label(label=texto, xalign=0 if col < 2 else 1)
            cab.add_css_class("uso-rotulo")
            grade.attach(cab, col, 0, 1, 1)
        ordem = sorted(agentes.items(), key=lambda kv: (kv[1][chave], kv[1]["respostas"]), reverse=True)
        for linha, (aid, a) in enumerate(ordem, start=1):
            nome = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            nome.append(marcas.imagem(marcas.icone_agente(aid, a["modelo"]), 18))
            n = Gtk.Label(label=M.AGENTES.get(aid, {}).get("nome", aid), xalign=0)
            n.set_ellipsize(Pango.EllipsizeMode.END)
            nome.append(n)
            grade.attach(nome, 0, linha, 1, 1)

            barra = Gtk.ProgressBar(fraction=min(1.0, a[chave] / maior))
            barra.add_css_class("uso-barra")
            barra.set_hexpand(True)
            barra.set_valign(Gtk.Align.CENTER)
            barra.set_tooltip_text(f"{dinheiro(a['custo'])} · {compacto(a['tokens'])} tokens · "
                                   f"{a['respostas']} {_t('respostas')}")
            grade.attach(barra, 1, linha, 1, 1)
            for col, valor in ((2, str(a["respostas"])), (3, compacto(a["tokens"]) if a["tokens"] else "—"),
                               (4, dinheiro(a["custo"]) if a["custo"] else "—")):
                lbl = Gtk.Label(label=valor, xalign=1)
                lbl.add_css_class("uso-numero")
                grade.attach(lbl, col, linha, 1, 1)
        return grade

    def _painel_limites(self):
        linhas = []
        for aid in M.AGENTES:
            janelas = dict(getattr(self, "janelas_uso", {}).get(aid) or {})
            voltas = {}
            if not janelas:
                u = M.uso(aid)
                for chave, rotulo in (("sessao", "5h"), ("semana", "7d")):
                    if chave in u and M._futuro(u.get(f"{chave}Volta") or ""):
                        janelas[rotulo] = u[chave]
                        voltas[rotulo] = u[f"{chave}Volta"]
            janelas = {k: v for k, v in janelas.items() if k in ("5h", "7d")}
            if janelas:
                linhas.append((aid, janelas, voltas))
        if not linhas:
            return None
        grade = Gtk.Grid(column_spacing=14, row_spacing=10)
        for i, (aid, janelas, voltas) in enumerate(linhas):
            nome = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            nome.append(marcas.imagem(marcas.icone_agente(aid), 18))
            nome.append(Gtk.Label(label=M.AGENTES[aid]["nome"], xalign=0))
            grade.attach(nome, 0, i, 1, 1)
            col = 1
            for rotulo, nome_jan in (("5h", _t("5 horas")), ("7d", _t("7 dias"))):
                if rotulo not in janelas:
                    col += 1
                    continue
                grade.attach(self._medidor(nome_jan, janelas[rotulo], voltas.get(rotulo)), col, i, 1, 1)
                col += 1
        return grade

    def _medidor(self, nome, fracao, volta):
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        caixa.set_hexpand(True)
        topo = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        topo.append(Gtk.Label(label=nome, xalign=0, hexpand=True))
        pct = round(fracao * 100)
        if fracao >= 0.8:  # estado: ícone + texto, nunca só a cor
            aviso = Gtk.Image.new_from_icon_name("dialog-warning-symbolic")
            aviso.add_css_class("warning" if fracao < 0.95 else "error")
            topo.append(aviso)
        valor = Gtk.Label(label=f"{pct}%")
        valor.add_css_class("uso-numero")
        topo.append(valor)
        caixa.append(topo)
        barra = Gtk.LevelBar(min_value=0, max_value=1, value=min(1.0, fracao))
        for nome_off in ("low", "high", "full"):
            barra.remove_offset_value(nome_off)
        barra.add_offset_value("uso-ok", 0.8)
        barra.add_offset_value("uso-alto", 0.95)
        barra.add_offset_value("uso-critico", 1.0)
        barra.add_css_class("uso-medidor")
        caixa.append(barra)
        if volta:
            try:
                quando = datetime.fromisoformat(volta.replace("Z", "+00:00")).astimezone()
                hoje = datetime.now(timezone.utc).astimezone().date()
                texto = quando.strftime("%H:%M") if quando.date() == hoje else \
                    (_t("amanhã") + quando.strftime(" %H:%M") if quando.date() == hoje + timedelta(days=1)
                     else quando.strftime("%d/%m %H:%M"))
                lbl = Gtk.Label(label=f"{_t('Renova')} {texto}", xalign=0)
                lbl.add_css_class("uso-detalhe")
                caixa.append(lbl)
            except ValueError:
                pass
        return caixa
