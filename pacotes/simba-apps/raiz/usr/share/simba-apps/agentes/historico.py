"""Histórico persistente das conversas (salvar, listar, abrir, exportar)."""
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
import time
import uuid

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

sys.path.insert(0, "/usr/share/simba-apps/idiomas")
from simba_i18n import t as _t  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motor as M  # noqa: E402

HOME = Path.home()
CONVERSAS = HOME / ".local/state/simba/agents/conversas"


class HistoricoMixin:
    # ── Histórico persistente de conversas ───────────────────────────────────
    def _garantir_id_conversa(self):
        if not self.conversa_id:
            agora = datetime.now().strftime("%Y%m%d-%H%M%S")
            self.conversa_id = f"{agora}-{uuid.uuid4().hex[:6]}"
            self.conversa_criada = time.time()
        return self.conversa_id

    def _titulo_conversa(self):
        for msg in self.conversa_mensagens:
            if msg.get("tipo") == "user":
                texto = " ".join(str(msg.get("texto", "")).split())
                if texto:
                    return texto[:57] + ("…" if len(texto) > 57 else "")
        return _t("Nova conversa")

    def _sincronizar_ativo(self):
        """Copia o texto ainda não renderizado da resposta ativa para o registro."""
        if (
            self.ativo_registro is not None
            and not self.finalizado
        ):
            self.ativo_registro["texto"] = self.ativo_texto

    def _salvar_conversa(self):
        if self.salvar_fonte:
            try:
                GLib.source_remove(self.salvar_fonte)
            except Exception:
                pass
            self.salvar_fonte = 0
        if not any(m.get("tipo") == "user" for m in self.conversa_mensagens):
            return
        self._sincronizar_ativo()
        cid = self._garantir_id_conversa()
        dados = {
            "id": cid,
            "titulo": self._titulo_conversa(),
            "criada": self.conversa_criada or time.time(),
            "atualizada": time.time(),
            "pasta": str(self.work_dir),
            # id da sessão de cada agente: ao reabrir, a conversa continua na
            # mesma sessão em vez de mandar o histórico de novo
            "sessoes": dict(self.sessoes),
            "mensagens": self.conversa_mensagens,
        }
        try:
            CONVERSAS.mkdir(parents=True, exist_ok=True, mode=0o700)
            destino = CONVERSAS / f"{cid}.json"
            temporario = destino.with_suffix(".json.tmp")
            temporario.write_text(
                json.dumps(dados, ensure_ascii=False), encoding="utf-8"
            )
            os.chmod(temporario, 0o600)
            os.replace(temporario, destino)
        except OSError:
            pass

    def _agendar_salvamento(self, atraso=1200):
        if self.salvar_fonte:
            try:
                GLib.source_remove(self.salvar_fonte)
            except Exception:
                pass
        self.salvar_fonte = GLib.timeout_add(atraso, self._salvar_agendado)

    def _salvar_agendado(self):
        self.salvar_fonte = 0
        self._salvar_conversa()
        return False

    def _ao_fechar(self, *_args):
        self._salvar_conversa()
        return False

    def _listar_conversas(self):
        itens = []
        try:
            arquivos = list(CONVERSAS.glob("*.json"))
        except OSError:
            return itens
        for arquivo in arquivos:
            try:
                dados = json.loads(arquivo.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(dados, dict):
                continue
            mensagens = dados.get("mensagens")
            if not isinstance(mensagens, list) or not mensagens:
                continue
            dados["id"] = dados.get("id") or arquivo.stem
            itens.append(dados)
        itens.sort(key=lambda d: d.get("atualizada", 0), reverse=True)
        return itens[:60]

    def _quando_legivel(self, quando):
        try:
            dt = datetime.fromtimestamp(float(quando))
        except (TypeError, ValueError, OSError):
            return ""
        hoje = datetime.now().date()
        if dt.date() == hoje:
            return f"{_t('Hoje')}, {dt:%H:%M}"
        if (hoje - dt.date()).days == 1:
            return f"{_t('Ontem')}, {dt:%H:%M}"
        return dt.strftime("%d/%m/%Y, %H:%M")

    def _abrir_historico(self):
        if self._rodando():
            return
        if self.historico_dialog:
            try:
                self.historico_dialog.close()
            except Exception:
                pass
            self.historico_dialog = None

        dialog = Adw.Dialog()
        dialog.set_title(_t("Conversas"))
        dialog.set_content_width(560)
        dialog.set_content_height(620)
        self.historico_dialog = dialog

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(title=_t("Conversas"), subtitle=_t("Retome de onde parou"))
        )
        toolbar.add_top_bar(header)

        # Barra de pesquisa de conversas
        search_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        search_box.set_margin_start(18)
        search_box.set_margin_end(18)
        search_box.set_margin_top(8)
        search_box.set_margin_bottom(8)
        search_entry = Gtk.SearchEntry()
        search_entry.set_placeholder_text(_t("Buscar no histórico…"))
        search_entry.set_hexpand(True)
        search_box.append(search_entry)
        toolbar.add_top_bar(search_box)

        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        caixa.set_margin_top(18)
        caixa.set_margin_bottom(18)
        caixa.set_margin_start(18)
        caixa.set_margin_end(18)

        search_entry.connect(
            "search-changed",
            lambda entry: self._preencher_historico(caixa, dialog, filtro=entry.get_text().strip()),
        )

        self._preencher_historico(caixa, dialog)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        clamp = Adw.Clamp()
        clamp.set_maximum_size(640)
        clamp.set_child(caixa)
        scroller.set_child(clamp)
        toolbar.set_content(scroller)
        dialog.set_child(toolbar)

        dialog.connect("closed", self._historico_fechou)
        dialog.present(self)

    def _historico_fechou(self, dialog=None, *_args):
        if dialog is None or self.historico_dialog is dialog:
            self.historico_dialog = None

    def _preencher_historico(self, caixa, dialog, filtro=""):
        while True:
            filho = caixa.get_first_child()
            if not filho:
                break
            caixa.remove(filho)

        if not filtro:
            grupo_novo = Adw.PreferencesGroup()
            row_nova = Adw.ActionRow(
                title=_t("Nova conversa"),
                subtitle=_t("Começar uma conversa do zero"),
            )
            row_nova.add_prefix(Gtk.Image.new_from_icon_name("document-new-symbolic"))
            row_nova.set_activatable(True)
            row_nova.connect("activated", self._nova_conversa_do_historico)
            grupo_novo.add(row_nova)
            caixa.append(grupo_novo)

        grupo = Adw.PreferencesGroup(title=_t("Recentes") if not filtro else _t("Resultados da busca"))
        itens = self._listar_conversas()
        if filtro:
            termo = filtro.lower()
            def corresponde(d):
                if termo in (d.get("titulo") or "").lower():
                    return True
                if termo in (d.get("pasta") or "").lower():
                    return True
                for m in d.get("mensagens", []):
                    if termo in str(m.get("texto", "")).lower():
                        return True
                return False
            itens = [d for d in itens if corresponde(d)]

        if not itens:
            vazio = Adw.ActionRow(
                title=_t("Nenhuma conversa salva ainda") if not filtro else _t("Nenhuma conversa encontrada"),
                subtitle=_t("Suas conversas aparecem aqui automaticamente.") if not filtro else _t("Tente buscar por outras palavras."),
            )
            vazio.set_activatable(False)
            grupo.add(vazio)
        else:
            for dados in itens:
                agente = ""
                for msg in reversed(dados.get("mensagens", [])):
                    if msg.get("tipo") == "assistant" and msg.get("agente"):
                        agente = M.AGENTES.get(msg["agente"], {}).get(
                            "nome", msg["agente"]
                        )
                        break
                quando = self._quando_legivel(dados.get("atualizada"))
                total = len([m for m in dados.get("mensagens", []) if m.get("tipo") in ("user", "assistant")])
                rotulo_total = f"{total} {_t('mensagem' if total == 1 else 'mensagens')}"
                partes = [p for p in (agente, quando, rotulo_total) if p]
                row = Adw.ActionRow(
                    title=dados.get("titulo") or _t("Nova conversa"),
                    subtitle=" · ".join(partes),
                )
                row.set_activatable(True)
                row.connect(
                    "activated",
                    lambda _r, d=dados, dlg=dialog: self._carregar_conversa(d, dlg),
                )

                btn_renomear = Gtk.Button(icon_name="document-edit-symbolic")
                btn_renomear.add_css_class("flat")
                btn_renomear.set_valign(Gtk.Align.CENTER)
                btn_renomear.set_tooltip_text(_t("Renomear conversa"))
                btn_renomear.connect(
                    "clicked",
                    lambda _b, d=dados, c=caixa, dlg=dialog, f=filtro: self._confirmar_renomear_conversa(
                        d, c, dlg, f
                    ),
                )
                row.add_suffix(btn_renomear)

                btn_apagar = Gtk.Button(icon_name="user-trash-symbolic")
                btn_apagar.add_css_class("flat")
                btn_apagar.set_valign(Gtk.Align.CENTER)
                btn_apagar.set_tooltip_text(_t("Apagar conversa"))
                btn_apagar.connect(
                    "clicked",
                    lambda _b, d=dados, c=caixa, dlg=dialog, f=filtro: self._confirmar_apagar_conversa(
                        d, c, dlg, f
                    ),
                )
                row.add_suffix(btn_apagar)
                grupo.add(row)
        caixa.append(grupo)

    def _nova_conversa_do_historico(self, *_args):
        if self.historico_dialog:
            try:
                self.historico_dialog.close()
            except Exception:
                pass
            self.historico_dialog = None
        self._limpar_chat()
        self.text_input.grab_focus()

    def _confirmar_renomear_conversa(self, dados, caixa, dialog, filtro=""):
        alerta = Adw.AlertDialog.new(_t("Renomear conversa"), _t("Digite o novo título da conversa:"))
        alerta.add_response("cancelar", _t("Cancelar"))
        alerta.add_response("salvar", _t("Salvar"))
        alerta.set_response_appearance("salvar", Adw.ResponseAppearance.SUGGESTED)
        alerta.set_default_response("salvar")
        alerta.set_close_response("cancelar")

        entry = Gtk.Entry()
        entry.set_text(dados.get("titulo") or _t("Nova conversa"))
        entry.set_margin_start(12)
        entry.set_margin_end(12)
        alerta.set_extra_child(entry)

        def resposta(_d, r):
            if r != "salvar":
                return
            novo = entry.get_text().strip()
            if not novo:
                return
            dados["titulo"] = novo
            cid = dados.get("id")
            if cid:
                destino = CONVERSAS / f"{cid}.json"
                try:
                    destino.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
                except OSError:
                    pass
            if self.historico_dialog is dialog and caixa.get_root():
                self._preencher_historico(caixa, dialog, filtro)

        alerta.connect("response", resposta)
        alerta.present(dialog)

    def _confirmar_apagar_conversa(self, dados, caixa, dialog, filtro=""):
        alerta = Adw.AlertDialog.new(
            _t("Apagar conversa?"),
            f"{dados.get('titulo') or _t('Nova conversa')}\n"
            f"{_t('A conversa será apagada deste computador.')}",
        )
        alerta.add_response("cancelar", _t("Cancelar"))
        alerta.add_response("apagar", _t("Apagar"))
        alerta.set_response_appearance("apagar", Adw.ResponseAppearance.DESTRUCTIVE)
        alerta.set_close_response("cancelar")

        def resposta(_d, r):
            if r != "apagar":
                return
            cid = dados.get("id")
            if cid:
                try:
                    (CONVERSAS / f"{cid}.json").unlink()
                except OSError:
                    pass
                if cid == self.conversa_id:
                    self.conversa_id = None
                    self.conversa_criada = None
                    self.conversa_mensagens = []
                    self.ativo_registro = None
                    self._limpar_chat()
                if self.historico_dialog is dialog and caixa.get_root():
                    self._preencher_historico(caixa, dialog, filtro)

        alerta.connect("response", resposta)
        alerta.present(dialog)

    def _carregar_conversa(self, dados, dialog):
        if self._rodando():
            return
        try:
            dialog.close()
        except Exception:
            pass
        self.historico_dialog = None

        mensagens = dados.get("mensagens")
        if not isinstance(mensagens, list):
            mensagens = []

        self._limpar_chat()
        self.conversa_id = dados.get("id")
        self.conversa_criada = dados.get("criada") or time.time()
        self.conversa_mensagens = list(mensagens)
        self.ativo_registro = None
        self.precisa_contexto = bool(self.conversa_mensagens)

        pasta = dados.get("pasta")
        if pasta:
            caminho = Path(str(pasta))
            if caminho.is_dir():
                self.work_dir = caminho
                self._atualizar_pasta_ui()
        sessoes = dados.get("sessoes")
        if isinstance(sessoes, dict) and pasta and Path(str(pasta)) == self.work_dir:
            self.sessoes = {a: s for a, s in sessoes.items() if a in M.AGENTES and isinstance(s, str)}
            self.conversas_iniciadas = set(self.sessoes)

        for msg in self.conversa_mensagens:
            tipo = msg.get("tipo")
            if tipo == "user":
                self._adicionar_bolha_usuario(msg.get("texto", ""), registro=False, anexos=msg.get("anexos"))
            elif tipo == "assistant":
                widgets = self._adicionar_bolha_assistente(
                    msg.get("agente", ""),
                    registro=False,
                    ativo=False,
                    modelo=msg.get("modelo", ""),
                    hora=msg.get("hora"),
                    duracao=msg.get("duracao"),
                )
                texto = msg.get("texto", "")
                if texto:
                    widgets["mensagem"].definir(texto)
                    widgets["mensagem"].concluir()
                # bloco "Pensando" como ficou no fim da resposta (conversas antigas
                # só têm a lista de textos "atividade": viram passos simples)
                widgets["bloco"].seguro = bool(msg.get("seguro"))
                widgets["bloco"].carregar(msg)
                widgets["card"].atualizar_acoes(widgets["bloco"].passos)
            elif tipo == "sistema":
                self._adicionar_sistema(msg.get("texto", ""), registro=False)
            elif tipo == "handover":
                self._adicionar_aviso_handover(
                    msg.get("antigo", ""), msg.get("proximo", ""), registro=False
                )

        # Mantém o último agente usado nesta conversa selecionado, se ainda existir
        ultimo_agente = next(
            (
                msg.get("agente")
                for msg in reversed(self.conversa_mensagens)
                if msg.get("tipo") == "assistant" and msg.get("agente")
            ),
            None,
        )
        if ultimo_agente:
            for i, item in enumerate(self.dropdown_items):
                if item["id"] == ultimo_agente:
                    self.dropdown.escolher(i)
                    break

        self.empty_state.set_visible(not self.conversa_mensagens)
        self._scroll_para_fim(forcar=True)
        self.text_input.grab_focus()

    def _pedido_com_contexto(self, pedido):
        anteriores = []
        for msg in self.conversa_mensagens:
            tipo = msg.get("tipo")
            if tipo == "user":
                texto = str(msg.get("texto", "")).strip()
                if texto:
                    anteriores.append(f"Usuário: {texto[:2000]}")
            elif tipo == "assistant":
                texto = str(msg.get("texto", "")).strip()
                if texto:
                    nome = M.AGENTES.get(msg.get("agente", ""), {}).get(
                        "nome", msg.get("agente", "IA")
                    )
                    anteriores.append(f"{nome}: {texto[:2000]}")
        if anteriores and anteriores[-1].startswith("Usuário:"):
            anteriores.pop()
        if not anteriores:
            return pedido
        contexto = "\n\n".join(anteriores)
        if len(contexto) > 12000:
            contexto = "…\n" + contexto[-12000:]
        return (
            "Você está retomando uma conversa anterior. Use o contexto abaixo apenas "
            "para continuar o trabalho; não repita o que já foi feito.\n\n"
            f"{contexto}\n\nNovo pedido do usuário:\n{pedido}"
        )

    def _exportar_conversa(self):
        """Pergunta onde salvar (antes gravava direto na pasta do projeto)."""
        if not self.conversa_mensagens:
            self._adicionar_sistema(_t("Nada para exportar: a conversa está vazia."), registro=False)
            return
        titulo_limpo = re.sub(r"[^\w\-_\. ]", "_", self._titulo_conversa())[:40].strip() or "conversa"
        dialog = Gtk.FileDialog(title=_t("Exportar conversa"))
        dialog.set_initial_folder(Gio.File.new_for_path(str(self.work_dir)))
        dialog.set_initial_name(f"{titulo_limpo}.md")
        dialog.save(self, None, self._exportar_para)

    def _exportar_para(self, dialog, resultado):
        try:
            arquivo = dialog.save_finish(resultado)
        except GLib.Error:
            return  # cancelado
        if arquivo is None or not arquivo.get_path():
            return
        destino = Path(arquivo.get_path())
        linhas = [
            f"# {self._titulo_conversa()}\n",
            f"*Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}*\n",
            f"*Pasta de trabalho: {self.work_dir}*\n",
            "────────────────────────────────────────\n",
        ]
        for msg in self.conversa_mensagens:
            tipo = msg.get("tipo")
            if tipo == "user":
                anexos = "".join(f"\n- 📎 `{c}`" for c in msg.get("anexos") or [])
                linhas.append(f"\n### 👤 {_t('Usuário')}\n\n{msg.get('texto', '')}{anexos}\n")
            elif tipo == "assistant":
                agente = msg.get("agente", "")
                nome = M.AGENTES.get(agente, {}).get("nome", agente or _t("IA"))
                modelo = msg.get("modelo", "")
                dur = f" · {msg['duracao']}" if msg.get("duracao") else ""
                linhas.append(f"\n### 🤖 {nome} ({modelo}{dur})\n\n{msg.get('texto', '')}\n")
            elif tipo == "handover":
                linhas.append(f"\n> ⚡ {msg.get('antigo', '')} → {msg.get('proximo', '')}\n")
        try:
            destino.write_text("\n".join(linhas), encoding="utf-8")
        except OSError as e:
            self._adicionar_sistema(f"{_t('Erro ao exportar conversa:')} {e}", registro=False)
            return
        self._adicionar_sistema(f"{_t('Conversa exportada para')} {destino}", registro=False)
