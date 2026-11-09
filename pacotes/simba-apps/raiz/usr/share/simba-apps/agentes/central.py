"""Central de agentes: as Configurações dos Agentes de IA dentro do chat."""
import json
from pathlib import Path
import subprocess
import sys
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk  # noqa: E402

sys.path.insert(0, "/usr/share/simba-apps/idiomas")
from simba_i18n import t as _t  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import motor as M  # noqa: E402
import marcas  # noqa: E402


class CentralMixin:
    # ── Central de agentes: Configurações dentro do chat ─────────────────────
    def _abrir_central(self):
        if self.central_dialog:
            self.central_dialog.present(self)
            self._carregar_estado_central(forcar=True)
            return

        dialog = Adw.Dialog()
        dialog.set_title(_t("Central de agentes"))
        dialog.set_content_width(760)
        dialog.set_content_height(620)
        dialog.connect("closed", self._central_fechou)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title=_t("Central de agentes"),
                subtitle=_t("Modelos, ordem, contas e instalação — sem sair do chat"),
            )
        )
        btn_atualizar = Gtk.Button(icon_name="view-refresh-symbolic")
        btn_atualizar.add_css_class("flat")
        btn_atualizar.set_tooltip_text(_t("Atualizar status"))
        btn_atualizar.connect("clicked", lambda _b: self._carregar_estado_central(forcar=True))
        header.pack_start(btn_atualizar)
        toolbar.add_top_bar(header)

        page = Adw.PreferencesPage()

        grupo_geral = Adw.PreferencesGroup(title=_t("Comportamento"))
        self.central_switch = Adw.SwitchRow(
            title=_t("Trocar de agente quando o limite acabar"),
            subtitle=_t("Leva o contexto: pedido, conversa, comandos e estado do Git"),
        )
        self.central_switch_handler = self.central_switch.connect(
            "notify::active", self._central_troca_alterada
        )
        grupo_geral.add(self.central_switch)

        self.central_spin = Adw.SpinRow.new_with_range(0, 30, 1)
        self.central_spin.set_title(_t("Esperar antes de trocar"))
        self.central_spin.set_subtitle(_t("Tempo para cancelar com Esc · 0 troca na hora"))
        self.central_spin_handler = self.central_spin.connect(
            "notify::value", self._central_espera_alterada
        )
        grupo_geral.add(self.central_spin)
        page.add(grupo_geral)

        self.central_grupo_ordem = Adw.PreferencesGroup(
            title=_t("Agentes e modelos"),
            description=_t(
                "A ordem define quem assume quando o limite acaba. Desligue um agente para tirá-lo da cascata."
            ),
        )
        page.add(self.central_grupo_ordem)

        self.central_grupo_add = Adw.PreferencesGroup(
            title=_t("Adicionar agentes"),
            description=_t("Baixe com um clique e conecte a conta depois."),
        )
        self.central_grupo_add.set_visible(False)
        page.add(self.central_grupo_add)

        dica = Adw.PreferencesGroup()
        dica_row = Adw.ActionRow(
            title=_t("Dica"),
            subtitle=_t(
                "O modelo do agente selecionado também pode ser trocado direto no rodapé do chat."
            ),
        )
        dica_row.set_activatable(False)
        dica.add(dica_row)
        page.add(dica)

        self.central_toast = Adw.ToastOverlay()
        self.central_toast.set_child(page)
        toolbar.set_content(self.central_toast)
        dialog.set_child(toolbar)

        self.central_dialog = dialog
        self.central_linhas_ordem = []
        self.central_linhas_add = []
        self.central_widgets = {}
        self.central_add_widgets = {}
        self.central_ids_inst = ()
        self.central_ids_disp = ()
        dialog.present(self)
        self._carregar_estado_central(forcar=True)

    def _central_fechou(self, *_args):
        for attr in ("central_poll_id", "central_refresh_id", "central_espera_id"):
            ident = getattr(self, attr, 0)
            if ident:
                GLib.source_remove(ident)
                setattr(self, attr, 0)
        self.central_dialog = None
        self.central_toast = None
        self.central_estado = None
        self.central_widgets = {}
        self.central_add_widgets = {}
        self.central_ids_inst = ()
        self.central_ids_disp = ()

    def _toast_central(self, texto):
        if self.central_toast and texto:
            self.central_toast.add_toast(Adw.Toast.new(texto))

    def _carregar_estado_central(self, forcar=False):
        if not self.central_dialog:
            return
        if self.central_carregando:
            if forcar:
                self.central_pendente = True
            return
        self.central_carregando = True

        def worker():
            dados = None
            try:
                r = subprocess.run(
                    ["/usr/bin/agentes", "estado"],
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                if r.returncode == 0 and r.stdout.strip():
                    dados = json.loads(r.stdout)
            except Exception:
                dados = None
            GLib.idle_add(self._central_recebeu, dados)

        threading.Thread(target=worker, daemon=True).start()

    def _central_recebeu(self, dados):
        self.central_carregando = False
        if not self.central_dialog:
            return False
        if dados is None:
            self._toast_central(_t("Não foi possível ler o estado dos agentes"))
        else:
            self.central_estado = dados
            self._preencher_central(dados)
        if self.central_pendente:
            self.central_pendente = False
            self._carregar_estado_central(forcar=True)
        return False

    def _preencher_central(self, dados):
        agentes = dados.get("agentes") or []
        instalados = [a for a in agentes if a.get("instalado")]
        disponiveis = [a for a in agentes if not a.get("instalado") and a.get("instalavel")]

        self.central_switch.handler_block(self.central_switch_handler)
        self.central_switch.set_active(bool(dados.get("trocaAutomatica", True)))
        self.central_switch.handler_unblock(self.central_switch_handler)

        self.central_spin.handler_block(self.central_spin_handler)
        try:
            self.central_spin.set_value(float(dados.get("esperar", 8)))
        except (TypeError, ValueError):
            self.central_spin.set_value(8)
        self.central_spin.handler_unblock(self.central_spin_handler)

        ids_inst = tuple(a["id"] for a in instalados)
        ids_disp = tuple(a["id"] for a in disponiveis)
        if ids_inst != self.central_ids_inst or ids_disp != self.central_ids_disp:
            self._reconstruir_central(instalados, disponiveis)
        else:
            self._atualizar_linhas_central(instalados)

        # Enquanto houver instalação em andamento, acompanha o progresso.
        if any(a.get("instalando") for a in agentes):
            if not self.central_poll_id:
                self.central_poll_id = GLib.timeout_add(2000, self._poll_instalacao)
        elif self.central_poll_id:
            GLib.source_remove(self.central_poll_id)
            self.central_poll_id = 0

    def _poll_instalacao(self):
        self.central_poll_id = 0
        if not self.central_dialog:
            return False
        self._carregar_estado_central(forcar=True)
        return False

    def _reconstruir_central(self, instalados, disponiveis):
        for grupo, linhas in (
            (self.central_grupo_ordem, self.central_linhas_ordem),
            (self.central_grupo_add, self.central_linhas_add),
        ):
            for linha in linhas:
                try:
                    grupo.remove(linha)
                except Exception:
                    pass
        self.central_linhas_ordem = []
        self.central_linhas_add = []
        self.central_widgets = {}
        self.central_add_widgets = {}

        for i, a in enumerate(instalados):
            self._criar_linha_agente(a, i, len(instalados))
        if not instalados:
            vazio = Adw.ActionRow(
                title=_t("Nenhum agente instalado"),
                subtitle=_t("Use “Adicionar agentes” abaixo para começar."),
            )
            vazio.set_activatable(False)
            self.central_grupo_ordem.add(vazio)
            self.central_linhas_ordem.append(vazio)

        for a in disponiveis:
            self._criar_linha_disponivel(a)

        self.central_grupo_add.set_visible(bool(disponiveis))
        self.central_ids_inst = tuple(a["id"] for a in instalados)
        self.central_ids_disp = tuple(a["id"] for a in disponiveis)
        self._atualizar_linhas_central(instalados)

    def _icone_agente(self, aid):
        # Mesmo logo da empresa usado no chat (marcas.py)
        return marcas.imagem(marcas.icone_agente(aid, M.modelo_escolhido(aid, M.ler_config(verificar=False))), 24)

    def _opcoes_modelo(self, aid, atual):
        opcoes = [{"valor": "", "rotulo": _t("Padrão do agente")}]
        vistos = {""}
        try:
            modelos = M.modelos(aid)
        except Exception:
            modelos = []
        for o in modelos:
            valor = str((o or {}).get("valor", "")).strip()
            if valor and valor not in vistos:
                vistos.add(valor)
                opcoes.append({"valor": valor, "rotulo": o.get("rotulo") or valor})
        if atual and atual not in vistos:
            opcoes.append({"valor": atual, "rotulo": atual})
        return opcoes

    def _criar_linha_agente(self, a, indice, total):
        exp = Adw.ExpanderRow()
        exp.set_title(f"{indice + 1}. {a['nome']}")
        icone = self._icone_agente(a["id"])
        if icone:
            exp.add_prefix(icone)

        subir = Gtk.Button(icon_name="go-up-symbolic")
        subir.add_css_class("flat")
        subir.add_css_class("circular")
        subir.set_tooltip_text(_t("Subir na ordem"))
        subir.set_sensitive(indice > 0)
        subir.connect("clicked", lambda _b, aid=a["id"]: self._mover_agente(aid, -1))
        exp.add_suffix(subir)

        descer = Gtk.Button(icon_name="go-down-symbolic")
        descer.add_css_class("flat")
        descer.add_css_class("circular")
        descer.set_tooltip_text(_t("Descer na ordem"))
        descer.set_sensitive(indice < total - 1)
        descer.connect("clicked", lambda _b, aid=a["id"]: self._mover_agente(aid, 1))
        exp.add_suffix(descer)

        interruptor = Gtk.Switch()
        interruptor.set_valign(Gtk.Align.CENTER)
        interruptor.set_active(bool(a.get("ativo")))
        interruptor.set_tooltip_text(_t("Ligar ou desligar na cascata"))
        switch_handler = interruptor.connect(
            "notify::active", lambda s, _p, aid=a["id"]: self._ativar_agente(aid, s.get_active())
        )
        exp.add_suffix(interruptor)

        opcoes = self._opcoes_modelo(a["id"], a.get("modelo", ""))
        combo = Adw.ComboRow(title=_t("Modelo"))
        combo.set_model(Gtk.StringList(strings=[o["rotulo"] for o in opcoes]))
        combo.set_selected(self._indice_modelo(opcoes, a.get("modelo", "")))
        combo.connect(
            "notify::selected",
            lambda c, _p, aid=a["id"], ops=opcoes: self._modelo_linha(aid, ops, c.get_selected()),
        )
        exp.add_row(combo)

        conta = Adw.ActionRow(title=_t("Conta"), subtitle=self._texto_conta(a))
        btn_login = Gtk.Button(label=_t("Entrar"))
        btn_login.set_valign(Gtk.Align.CENTER)
        btn_login.connect("clicked", lambda _b, aid=a["id"]: self._entrar_agente(aid))
        conta.add_suffix(btn_login)
        conta.set_visible(a.get("conectado") is not True)
        exp.add_row(conta)

        remover = None
        if a.get("instalavel"):
            remover = Adw.ActionRow(
                title=_t("Remover"),
                subtitle=_t("Desinstala o agente deste computador"),
            )
            btn_remover = Gtk.Button(icon_name="user-trash-symbolic")
            btn_remover.add_css_class("flat")
            btn_remover.set_valign(Gtk.Align.CENTER)
            btn_remover.set_tooltip_text(_t("Remover agente"))
            btn_remover.connect(
                "clicked",
                lambda _b, aid=a["id"], nome=a["nome"]: self._confirmar_remocao(aid, nome),
            )
            remover.add_suffix(btn_remover)
            exp.add_row(remover)

        self.central_grupo_ordem.add(exp)
        self.central_linhas_ordem.append(exp)
        self.central_widgets[a["id"]] = {
            "exp": exp,
            "subir": subir,
            "descer": descer,
            "switch": interruptor,
            "switch_handler": switch_handler,
            "combo": combo,
            "combo_opcoes": opcoes,
            "conta": conta,
            "remover": remover,
        }

        if self.agente_atual == a["id"] or (not self.agente_atual and indice == 0):
            exp.set_expanded(True)

    def _criar_linha_disponivel(self, a):
        linha = Adw.ActionRow(title=a["nome"], subtitle=a.get("sobre") or _t("Disponível para instalar"))
        icone = self._icone_agente(a["id"])
        if icone:
            linha.add_prefix(icone)
        instalando = bool(a.get("instalando"))
        spinner = Gtk.Spinner()
        spinner.set_valign(Gtk.Align.CENTER)
        spinner.set_visible(instalando)
        if instalando:
            spinner.start()
        linha.add_suffix(spinner)
        btn = Gtk.Button(label=_t("Instalando…") if instalando else _t("Instalar"))
        btn.set_valign(Gtk.Align.CENTER)
        btn.add_css_class("suggested-action" if not instalando else "flat")
        btn.set_sensitive(not instalando)
        btn.connect("clicked", lambda _b, aid=a["id"], nome=a["nome"]: self._instalar_agente(aid, nome))
        linha.add_suffix(btn)
        self.central_grupo_add.add(linha)
        self.central_linhas_add.append(linha)
        self.central_add_widgets[a["id"]] = {"linha": linha, "btn": btn, "spinner": spinner}

    def _indice_modelo(self, opcoes, atual):
        for i, o in enumerate(opcoes):
            if o["valor"] == (atual or ""):
                return i
        return 0

    def _modelo_linha(self, aid, opcoes, indice):
        if 0 <= indice < len(opcoes):
            self._definir_modelo(aid, opcoes[indice]["valor"])
            self._toast_central(_t("Modelo atualizado"))

    def _atualizar_linhas_central(self, instalados):
        for i, a in enumerate(instalados):
            w = self.central_widgets.get(a["id"])
            if not w:
                continue
            w["exp"].set_title(f"{i + 1}. {a['nome']}")
            w["exp"].set_subtitle(self._descrever_agente(a))
            w["subir"].set_sensitive(i > 0)
            w["descer"].set_sensitive(i < len(instalados) - 1)
            w["switch"].handler_block(w["switch_handler"])
            w["switch"].set_active(bool(a.get("ativo")))
            w["switch"].handler_unblock(w["switch_handler"])
            conectado = a.get("conectado")
            w["conta"].set_visible(conectado is not True)
            w["conta"].set_subtitle(self._texto_conta(a))
            if w.get("remover") is not None:
                w["remover"].set_visible(bool(a.get("instalavel")))

    def _descrever_agente(self, a):
        if a.get("conectado") is False:
            return _t("Sem conta conectada — use Entrar abaixo")
        partes = []
        if not a.get("ativo"):
            partes.append(_t("Desligado na cascata"))
        if a.get("esgotadoTexto"):
            partes.append(f"{_t('Sem limite até')} {a['esgotadoTexto']}")
        uso = a.get("uso") or {}
        if uso.get("sessao") is not None:
            partes.append(f"{_t('Sessão')} {round(uso['sessao'] * 100)}%")
        if uso.get("semana") is not None:
            partes.append(f"{_t('Semana')} {round(uso['semana'] * 100)}%")
        if a.get("conectado") is None:
            partes.append(_t("Login não verificável"))
        return " · ".join(partes) or _t("Conectado")

    def _texto_conta(self, a):
        conectado = a.get("conectado")
        if conectado is True:
            return _t("Conta conectada")
        if conectado is False:
            return _t("Sem conta conectada")
        return _t("Login não verificável — entre só se já usou este agente")

    def _central_troca_alterada(self, row, _param):
        self._rodar_agentes(
            ["opcao", "trocaAutomatica", "true" if row.get_active() else "false"],
            _t("Troca automática atualizada"),
        )

    def _central_espera_alterada(self, row, _param):
        try:
            valor = int(round(row.get_value()))
        except (TypeError, ValueError):
            return
        # O SpinRow emite notify::value a cada passo: espera o usuário parar.
        if self.central_espera_id:
            GLib.source_remove(self.central_espera_id)
        self.central_espera_id = GLib.timeout_add(
            700, lambda: self._aplicar_espera(valor)
        )

    def _aplicar_espera(self, valor):
        self.central_espera_id = 0
        self._rodar_agentes(
            ["opcao", "esperar", str(valor)], _t("Tempo de espera atualizado")
        )
        return False

    def _agendar_refresh_central(self, atraso=900):
        if not self.central_dialog:
            return
        if self.central_refresh_id:
            GLib.source_remove(self.central_refresh_id)
        self.central_refresh_id = GLib.timeout_add(
            atraso, self._refresh_central_agendado
        )

    def _refresh_central_agendado(self):
        self.central_refresh_id = 0
        if self.central_dialog:
            self._carregar_estado_central(forcar=True)
        return False

    def _rodar_agentes(self, args, aviso=None, timeout=120):
        def worker():
            try:
                subprocess.run(
                    ["/usr/bin/agentes"] + list(args),
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except Exception:
                pass

            def done():
                if aviso:
                    self._toast_central(aviso)
                self._carregar_agentes()
                self._agendar_refresh_central()
                return False

            GLib.idle_add(done)

        threading.Thread(target=worker, daemon=True).start()

    def _ativar_agente(self, aid, ativo):
        self._rodar_agentes(
            ["ativar", aid, "1" if ativo else "0"],
            _t("Agente ligado na cascata") if ativo else _t("Agente desligado da cascata"),
        )

    def _mover_agente(self, aid, delta):
        if not self.central_estado:
            return
        agentes = self.central_estado.get("agentes", [])
        instalados = [a for a in agentes if a.get("instalado")]
        ordem = [a["id"] for a in instalados]
        if aid not in ordem:
            return
        i = ordem.index(aid)
        j = i + delta
        if not (0 <= j < len(ordem)):
            return
        instalados[i], instalados[j] = instalados[j], instalados[i]
        ordem[i], ordem[j] = ordem[j], ordem[i]

        # Reordena na hora: a leitura completa do estado pode demorar.
        disponiveis = [a for a in agentes if not a.get("instalado") and a.get("instalavel")]
        restantes = [a for a in agentes if not a.get("instalado")]
        self.central_estado["agentes"] = instalados + restantes
        self._reconstruir_central(instalados, disponiveis)
        w = self.central_widgets.get(aid)
        if w:
            w["exp"].set_expanded(True)
        self._rodar_agentes(["ordem"] + ordem, _t("Ordem atualizada"))

    def _entrar_agente(self, aid):
        self._rodar_agentes(["entrar", aid], _t("Login aberto em um terminal"), timeout=30)

    def _instalar_agente(self, aid, nome):
        self._toast_central(f"{_t('Instalando')} {nome}…")
        w = self.central_add_widgets.get(aid)
        if w:
            w["btn"].set_label(_t("Instalando…"))
            w["btn"].set_sensitive(False)
            w["btn"].remove_css_class("suggested-action")
            w["btn"].add_css_class("flat")
            w["spinner"].set_visible(True)
            w["spinner"].start()
        self._rodar_agentes(["instalar", aid], _t("Instalação concluída"), timeout=3600)
        if not self.central_poll_id:
            self.central_poll_id = GLib.timeout_add(1500, self._poll_instalacao)

    def _confirmar_remocao(self, aid, nome):
        alerta = Adw.AlertDialog.new(
            _t("Remover agente?"),
            f"{nome} {_t('será desinstalado deste computador.')}",
        )
        alerta.add_response("cancelar", _t("Cancelar"))
        alerta.add_response("remover", _t("Remover"))
        alerta.set_response_appearance("remover", Adw.ResponseAppearance.DESTRUCTIVE)
        alerta.set_close_response("cancelar")

        def resposta(_d, r):
            if r == "remover":
                self._rodar_agentes(["remover", aid], _t("Agente removido"), timeout=120)

        alerta.connect("response", resposta)
        alerta.present(self.central_dialog)
