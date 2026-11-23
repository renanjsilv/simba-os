"""Janela do Simba Remoto (GTK4 + libadwaita). O servidor (asyncio) roda numa thread."""
import asyncio
import logging
import subprocess
import sys
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from .config import (carregar_config, definir_senha, novo_codigo,  # noqa: E402
                     obter_recentes, remover_recente, salvar_config)
from .sinal import formatar_codigo  # noqa: E402

log = logging.getLogger("simba-remoto")

CSS = b"""
.codigo { font-size: 38px; font-weight: 800; letter-spacing: 4px; font-feature-settings: "tnum"; }
.entrada-codigo { font-size: 22px; font-weight: 700; letter-spacing: 2px; font-feature-settings: "tnum"; }
.verificacao { font-size: 30px; font-weight: 800; letter-spacing: 3px; }
.estado-ok { color: #8fd18f; }
.estado-ruim { color: #e0a060; }
.cartao { padding: 20px; }
"""


class Janela(Adw.ApplicationWindow):
    def __init__(self, app, codigo_inicial=None):
        super().__init__(application=app, title="Simba Remoto", default_width=480, default_height=700)
        self.app = app
        self.loop = None
        self.servidor = None
        self._formatando_codigo = False

        prov = Gtk.CssProvider()
        prov.load_from_data(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), prov,
                                                  Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        barra = Adw.HeaderBar()
        menu = Gio.Menu()
        menu.append("Gerar novo endereço", "app.novo-codigo")
        menu.append("Sobre", "app.sobre")
        botao_menu = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        barra.pack_end(botao_menu)

        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18,
                        margin_top=18, margin_bottom=18, margin_start=18, margin_end=18)

        # --- cartão "Acessar outro computador"
        cartao_conectar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8, css_classes=["card", "cartao"])
        topo_c = Gtk.Box(spacing=12)
        img_c = Gtk.Image(icon_name="computer-symbolic", pixel_size=40)
        topo_c.append(img_c)
        tit_c = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        tit_c.append(Gtk.Label(label="Acessar outro computador", xalign=0, css_classes=["title-3"]))
        tit_c.append(Gtk.Label(label="Digite o endereço de 9 dígitos do computador que quer controlar", xalign=0,
                               css_classes=["dim-label", "caption"]))
        topo_c.append(tit_c)
        cartao_conectar.append(topo_c)

        linha_c = Gtk.Box(spacing=10, margin_top=8)
        self.entrada_conectar = Gtk.Entry(placeholder_text="000 000 000", hexpand=True,
                                          css_classes=["entrada-codigo"])
        self.entrada_conectar.connect("changed", self._ao_mudar_entrada_conectar)
        self.entrada_conectar.connect("activate", lambda *_: self._conectar())
        linha_c.append(self.entrada_conectar)

        btn_conectar = Gtk.Button(label="Conectar", css_classes=["suggested-action"], valign=Gtk.Align.CENTER)
        btn_conectar.connect("clicked", lambda *_: self._conectar())
        linha_c.append(btn_conectar)
        cartao_conectar.append(linha_c)
        caixa.append(cartao_conectar)

        # --- PCs nesta rede (descobertos automaticamente) e recentes
        self.grupo_vizinhos = Adw.PreferencesGroup(title="Nesta rede", visible=False)
        caixa.append(self.grupo_vizinhos)
        self._linhas_vizinhos = []
        self.vizinhos = []
        self.grupo_recentes = Adw.PreferencesGroup(title="Recentes")
        caixa.append(self.grupo_recentes)

        # --- cartão "este PC"
        cartao = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, css_classes=["card", "cartao"])
        topo = Gtk.Box(spacing=12)
        img = Gtk.Image(icon_name="simba", pixel_size=44)
        topo.append(img)
        tit = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        tit.append(Gtk.Label(label="Este PC", xalign=0, css_classes=["title-3"]))
        tit.append(Gtk.Label(label="Passe este endereço para quem vai acessar", xalign=0,
                             css_classes=["dim-label", "caption"]))
        topo.append(tit)
        cartao.append(topo)

        linha = Gtk.Box(spacing=6, halign=Gtk.Align.CENTER, margin_top=10)
        self.rotulo_codigo = Gtk.Label(css_classes=["codigo"], selectable=True)
        linha.append(self.rotulo_codigo)
        copiar = Gtk.Button(icon_name="edit-copy-symbolic", valign=Gtk.Align.CENTER,
                            tooltip_text="Copiar", css_classes=["flat", "circular"])
        copiar.connect("clicked", self._copiar)
        linha.append(copiar)
        cartao.append(linha)
        caixa.append(cartao)

        # --- estado do servidor
        self.grupo_estado = Adw.PreferencesGroup(title="Estado deste PC")
        self.linha_estado = Adw.ActionRow(title="Iniciando…", subtitle="Entrando na rede P2P")
        self.icone_estado = Gtk.Image(icon_name="network-idle-symbolic")
        self.linha_estado.add_prefix(self.icone_estado)
        self.botao_desconectar = Gtk.Button(label="Desconectar", valign=Gtk.Align.CENTER,
                                            css_classes=["destructive-action"], visible=False)
        self.botao_desconectar.connect("clicked", lambda *_: self.servidor and self._no_loop(self.servidor.desconectar))
        self.linha_estado.add_suffix(self.botao_desconectar)
        self.grupo_estado.add(self.linha_estado)
        caixa.append(self.grupo_estado)

        # --- acesso não supervisionado
        grupo_auto = Adw.PreferencesGroup(
            title="Acesso não supervisionado neste PC",
            description="Com uma senha, dá para entrar neste PC sem ninguém precisar aceitar aqui.")
        self.linha_auto = Adw.SwitchRow(title="Permitir acesso com senha")
        self.linha_auto.connect("notify::active", self._alternar_autonomo)
        grupo_auto.add(self.linha_auto)
        self.linha_senha = Adw.ActionRow(title="Senha", activatable=True)
        self.linha_senha.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
        self.linha_senha.connect("activated", lambda *_: self._dialogo_senha())
        grupo_auto.add(self.linha_senha)
        caixa.append(grupo_auto)

        # --- rede
        self.grupo_rede = Adw.PreferencesGroup(
            title="Caminhos de conexão",
            description="Sem servidor intermediário: o acesso encontra o PC pela rede local ou pela DHT.")
        self.linhas_rede = {}
        for chave, titulo in (("lan", "Rede local"), ("dht", "Rede P2P mundial (DHT)"),
                              ("ipv6", "IPv6 público"), ("upnp", "Porta aberta no roteador (UPnP)"),
                              ("stun", "Perfuração de NAT (STUN)")):
            r = Adw.ActionRow(title=titulo, subtitle="verificando…")
            ic = Gtk.Image(icon_name="content-loading-symbolic")
            r.add_suffix(ic)
            self.linhas_rede[chave] = (r, ic)
            self.grupo_rede.add(r)
        caixa.append(self.grupo_rede)

        rolagem = Gtk.ScrolledWindow(vexpand=True, hscrollbar_policy=Gtk.PolicyType.NEVER)
        rolagem.set_child(caixa)
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.append(barra)
        self.toasts = Adw.ToastOverlay(child=rolagem)
        vbox.append(self.toasts)
        self.set_content(vbox)

        self.cfg = carregar_config()
        self.rotulo_codigo.set_label(formatar_codigo(self.cfg["codigo"]))
        self._mudando = False
        self._atualizar_autonomo()
        self._atualizar_recentes()
        self.connect("close-request", self._fechar)
        self._iniciar_servidor()

        if codigo_inicial:
            GLib.idle_add(self._conectar, codigo_inicial)

    # ------------------------------------------------------------- cliente
    def _ao_mudar_entrada_conectar(self, entry):
        if self._formatando_codigo:
            return
        t = "".join(c for c in entry.get_text() if c.isdigit())[:9]
        if len(t) == 9:
            fmt = formatar_codigo(t)
        elif len(t) > 6:
            fmt = f"{t[:3]} {t[3:6]} {t[6:]}"
        elif len(t) > 3:
            fmt = f"{t[:3]} {t[3:]}"
        else:
            fmt = t
        if fmt != entry.get_text():
            self._formatando_codigo = True
            entry.set_text(fmt)
            entry.set_position(len(fmt))
            self._formatando_codigo = False
        if len(t) == 9:
            self._preaquecer(t)       # prepara o caminho enquanto a pessoa vai até o botão

    def _servidor_pronto(self):
        return bool(self.loop and self.servidor and getattr(self.servidor, "canal", None))

    def _preaquecer(self, codigo):
        if self._servidor_pronto():
            self.loop.call_soon_threadsafe(self.servidor.preaquecer, codigo)

    def _conectar(self, codigo=None):
        if codigo is None:
            codigo = self.entrada_conectar.get_text()
        digitos = "".join(c for c in codigo if c.isdigit())
        if len(digitos) != 9:
            self.toasts.add_toast(Adw.Toast(title="O endereço deve ter 9 dígitos.", timeout=3))
            return
        if digitos == self.cfg.get("codigo"):
            self.toasts.add_toast(Adw.Toast(title="Este é o endereço do próprio PC local.", timeout=3))
            return
        from .visualizador import JanelaVisualizador
        pronto = self._servidor_pronto()
        vis = JanelaVisualizador(self.app, digitos, self.cfg.get("nome"),
                                 servidor=self.servidor if pronto else None, loop=self.loop if pronto else None)
        vis.present()
        GLib.timeout_add(1500, self._atualizar_recentes)

    def _atualizar_vizinhos(self, lista):
        self.vizinhos = lista
        for row in self._linhas_vizinhos:
            self.grupo_vizinhos.remove(row)
        self._linhas_vizinhos = []
        for v in lista[:8]:
            row = Adw.ActionRow(title=v["nome"], subtitle=f"{formatar_codigo(v['codigo'])} · "
                                f"{'Windows' if v.get('so') == 'windows' else 'Linux'}", activatable=True)
            row.add_prefix(Gtk.Image(icon_name="network-wired-symbolic"))
            row.add_suffix(Gtk.Image(icon_name="go-next-symbolic"))
            row.connect("activated", lambda _r, c=v["codigo"]: self._conectar(c))
            self.grupo_vizinhos.add(row)
            self._linhas_vizinhos.append(row)
        self.grupo_vizinhos.set_visible(bool(lista))
        self._atualizar_recentes()

    def _atualizar_recentes(self):
        na_rede = {v["codigo"] for v in getattr(self, "vizinhos", [])}
        recentes = [r for r in obter_recentes() if r.get("codigo") not in na_rede]
        self.grupo_recentes.set_visible(bool(recentes))

        # Limpa linhas antigas
        while True:
            filho = None
            # PreferencesGroup children
            pass
            break
        # Recria o grupo com as linhas atuais
        # Em GTK4 Adw.PreferencesGroup não tem remove_all direto, então removemos linhas
        for row in getattr(self, "_linhas_recentes", []):
            self.grupo_recentes.remove(row)
        self._linhas_recentes = []

        for r in recentes:
            cod = r.get("codigo", "")
            nome = r.get("nome") or formatar_codigo(cod)
            row = Adw.ActionRow(title=nome, subtitle=formatar_codigo(cod), activatable=True)
            row.add_prefix(Gtk.Image(icon_name="computer-symbolic"))
            row.connect("activated", lambda _r, c=cod: self._conectar(c))

            btn_del = Gtk.Button(icon_name="user-trash-symbolic", valign=Gtk.Align.CENTER,
                                 css_classes=["flat", "circular"], tooltip_text="Remover")
            btn_del.connect("clicked", lambda _b, c=cod: self._remover_recente(c))
            row.add_suffix(btn_del)

            self.grupo_recentes.add(row)
            self._linhas_recentes.append(row)
        return False

    def _remover_recente(self, codigo):
        remover_recente(codigo)
        self._atualizar_recentes()

    # ------------------------------------------------------------- servidor
    def _iniciar_servidor(self):
        """Não bloqueia: aiortc/av/numpy são importados na thread, a janela já aparece pronta."""
        def rodar():
            from .host import Servidor
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.servidor = Servidor(aprovar=self._aprovar, evento=self._evento)
            self.loop = loop
            try:
                loop.run_until_complete(self.servidor.iniciar())
            except Exception as e:
                log.exception("servidor")
                self._evento("erro", {"texto": f"Falha ao iniciar: {e}"})
            loop.run_forever()
        threading.Thread(target=rodar, daemon=True, name="servidor").start()

    def _no_loop(self, f, *a):
        if self.loop:
            self.loop.call_soon_threadsafe(f, *a)

    def _parar_servidor(self):
        if self.loop and self.servidor:
            fut = asyncio.run_coroutine_threadsafe(self.servidor.parar(), self.loop)
            try:
                fut.result(5)
            except Exception:
                pass
            self.loop.call_soon_threadsafe(self.loop.stop)
        self.loop = self.servidor = None

    def _fechar(self, *_):
        self._parar_servidor()
        return False

    # chamado na thread do asyncio
    async def _aprovar(self, nome, sas):
        fut = self.loop.create_future()

        def responder(ok):
            self.loop.call_soon_threadsafe(lambda: fut.done() or fut.set_result(ok))
        GLib.idle_add(self._dialogo_pedido, nome, sas, responder)
        try:
            return await asyncio.wait_for(fut, 60)
        except asyncio.TimeoutError:
            GLib.idle_add(self._fechar_dialogo)
            return False
        except asyncio.CancelledError:
            GLib.idle_add(self._fechar_dialogo)
            raise

    def _evento(self, tipo, dados):
        GLib.idle_add(self._tratar_evento, tipo, dados)

    # ------------------------------------------------------------- interface
    def _dialogo_pedido(self, nome, sas, responder):
        self.present()
        _notificar("Pedido de acesso remoto", f"{nome} quer acessar este PC. Verificação: {sas}")
        d = Adw.AlertDialog(heading=f"{nome} quer acessar este PC",
                            body="Só aceite se foi você ou alguém de confiança. "
                                 "O código abaixo deve ser igual ao do computador remoto.")
        lbl = Gtk.Label(label=sas, css_classes=["verificacao"])
        d.set_extra_child(lbl)
        d.add_response("recusar", "Recusar")
        d.add_response("aceitar", "Aceitar")
        d.set_response_appearance("aceitar", Adw.ResponseAppearance.SUGGESTED)
        d.set_response_appearance("recusar", Adw.ResponseAppearance.DESTRUCTIVE)
        d.set_default_response("recusar")
        d.set_close_response("recusar")
        if not hasattr(self, "_dialogos"):
            self._dialogos = set()
        self._dialogos.add(d)

        def resposta(_d, r):
            self._dialogos.discard(d)
            responder(r == "aceitar")

        d.connect("response", resposta)
        d.present(self)
        return False

    def _fechar_dialogo(self):
        if hasattr(self, "_dialogos"):
            for d in list(self._dialogos):
                try:
                    d.force_close()
                except Exception:
                    pass
            self._dialogos.clear()
        if getattr(self, "_dialogo", None):
            self._dialogo.force_close()
            self._dialogo = None
        return False

    def _rede(self, chave, ok, texto):
        r, ic = self.linhas_rede[chave]
        r.set_subtitle(texto)
        ic.set_from_icon_name("emblem-ok-symbolic" if ok else ("dialog-warning-symbolic" if ok is False else "content-loading-symbolic"))
        ic.set_css_classes(["estado-ok"] if ok else ["estado-ruim"] if ok is False else [])

    def _estado(self, titulo, sub, icone, conectado=False):
        self.linha_estado.set_title(titulo)
        self.linha_estado.set_subtitle(sub)
        self.icone_estado.set_from_icon_name(icone)
        self.botao_desconectar.set_visible(conectado)

    def _tratar_evento(self, tipo, d):
        if tipo == "vizinhos":
            self._atualizar_vizinhos(d.get("lista", []))
            return False
        if tipo == "pronto":
            for r in obter_recentes()[:3]:
                self._preaquecer(r.get("codigo", ""))
            self._estado("Pronto para receber conexões", "Aguardando um pedido pelo endereço acima",
                         "network-transmit-receive-symbolic")
            self._rede("dht", True, f"conectado a {len(self.servidor.dht.bons)} nós")
            lan = getattr(self.servidor, "lan", None)
            self._rede("lan", bool(lan and lan.transporte),
                       "escutando na porta 21118/UDP" if lan and lan.transporte else "porta 21118 indisponível")
        elif tipo == "rede":
            self._rede("ipv6", bool(d.get("ipv6")),
                       d["ipv6"] if d.get("ipv6") else "sem IPv6 global (o ICE usa IPv4/STUN)")
            self._rede("upnp", bool(d.get("upnp")),
                       "porta aberta automaticamente a cada conexão" if d.get("upnp")
                       else "roteador sem UPnP (não é obrigatório)")
            ip = d.get("ip_externo")
            self._rede("stun", bool(ip), f"IP público {ip}" if ip else "sem resposta")
        elif tipo == "pedido":
            self._estado(f"Pedido de {d['nome']}", f"Verificação {d['verificacao']}", "dialog-question-symbolic")
        elif tipo == "conectando":
            self._estado(f"Conectando com {d['nome']}…", "Abrindo caminho direto (ICE)", "network-wireless-acquiring-symbolic")
        elif tipo == "conectado":
            total = d.get("total", 1)
            titulo = f"Conectado ({total} ativos)" if total > 1 else f"Conectado com {d['nome']}"
            self._estado(titulo, d.get("caminho", "P2P"), "video-display-symbolic", True)
            _notificar("Simba Remoto", f"{d['nome']} está vendo e controlando esta tela.")
        elif tipo == "sessao_encerrada":
            restantes = d.get("restantes", 0)
            nomes = d.get("nomes", [])
            _notificar("Simba Remoto", f"{d.get('nome', 'Dispositivo')} desconectou.")
            if restantes > 0:
                self._estado(f"{restantes} conexões ativas", ", ".join(nomes), "video-display-symbolic", True)
            else:
                self._estado("Pronto para receber conexões", "Conexão encerrada", "network-transmit-receive-symbolic", False)
        elif tipo in ("desconectado", "recusado"):
            self._estado("Pronto para receber conexões",
                         "Conexão encerrada" if tipo == "desconectado" else "Pedido recusado",
                         "network-transmit-receive-symbolic")
        elif tipo == "autonomo":
            self._estado(f"{d['nome']} entrou com a senha", "Acesso não supervisionado", "dialog-password-symbolic")
            _notificar("Simba Remoto", f"{d['nome']} entrou com a senha de acesso não supervisionado.")
        elif tipo == "reconectado":
            self._estado(f"{d['nome']} reconectou", "Conexão retomada automaticamente", "view-refresh-symbolic")
        elif tipo == "senha_errada":
            self.toasts.add_toast(Adw.Toast(title=f"Senha errada vinda de {d['nome']}", timeout=5))
            _notificar("Simba Remoto", f"Tentativa com senha errada: {d['nome']}")
        elif tipo == "erro":
            self.toasts.add_toast(Adw.Toast(title=d.get("texto", "erro"), timeout=6))
        return False

    def _copiar(self, *_):
        self.get_clipboard().set(self.cfg["codigo"])
        self.toasts.add_toast(Adw.Toast(title="Endereço copiado", timeout=2))

    # ------------------------------------------------------------- senha
    def _atualizar_autonomo(self):
        self._mudando = True
        tem = bool(self.cfg.get("senha_chave"))
        self.linha_auto.set_active(bool(self.cfg.get("autonomo")) and tem)
        self.linha_senha.set_subtitle("definida (toque para trocar)" if tem else "nenhuma — toque para definir")
        self._mudando = False

    def _alternar_autonomo(self, row, _p):
        if self._mudando:
            return
        if row.get_active() and not self.cfg.get("senha_chave"):
            self._dialogo_senha()
            return
        if not row.get_active():
            self.cfg = definir_senha(None)
            if self.servidor:
                self.servidor.cfg = self.cfg
            self._atualizar_autonomo()
            self.toasts.add_toast(Adw.Toast(title="Acesso com senha desligado", timeout=3))
        else:
            self.cfg["autonomo"] = True
            salvar_config(self.cfg)
            if self.servidor:
                self.servidor.cfg = self.cfg

    def _dialogo_senha(self):
        d = Adw.AlertDialog(heading="Senha de acesso não supervisionado",
                            body="Use pelo menos 8 caracteres. Ela não é guardada: o PC guarda só uma chave derivada.")
        caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        lista = Gtk.ListBox(css_classes=["boxed-list"], selection_mode=Gtk.SelectionMode.NONE)
        e1 = Adw.PasswordEntryRow(title="Senha")
        e2 = Adw.PasswordEntryRow(title="Repita a senha")
        lista.append(e1)
        lista.append(e2)
        caixa.append(lista)
        aviso = Gtk.Label(css_classes=["error", "caption"], xalign=0)
        caixa.append(aviso)
        d.set_extra_child(caixa)
        d.add_response("cancelar", "Cancelar")
        d.add_response("salvar", "Salvar")
        d.set_response_appearance("salvar", Adw.ResponseAppearance.SUGGESTED)
        d.set_response_enabled("salvar", False)
        d.set_close_response("cancelar")

        def validar(*_):
            a, b = e1.get_text(), e2.get_text()
            ok = len(a) >= 8 and a == b
            aviso.set_label("" if ok or not b else ("mínimo 8 caracteres" if len(a) < 8 else "as senhas não batem"))
            d.set_response_enabled("salvar", ok)
        e1.connect("changed", validar)
        e2.connect("changed", validar)

        def resposta(_d, r):
            if r == "salvar":
                self.cfg = definir_senha(e1.get_text())
                if self.servidor:
                    self.servidor.cfg = self.cfg
                self.toasts.add_toast(Adw.Toast(title="Senha salva. Acesso não supervisionado ligado.", timeout=3))
            self._atualizar_autonomo()
        d.connect("response", resposta)
        d.present(self)

    def trocar_codigo(self):
        self._parar_servidor()
        tinha_senha = bool(self.cfg.get("senha_chave"))
        self.cfg = carregar_config()
        self.cfg["codigo"] = novo_codigo()
        self.cfg = carregar_config()
        self.rotulo_codigo.set_label(formatar_codigo(self.cfg["codigo"]))
        self._atualizar_autonomo()
        if tinha_senha:
            self.toasts.add_toast(Adw.Toast(title="Endereço novo: defina a senha de novo", timeout=5))
        for chave in self.linhas_rede:
            self._rede(chave, None, "verificando…")
        self._estado("Reiniciando…", "Novo endereço", "network-idle-symbolic")
        self._iniciar_servidor()


def _notificar(titulo, texto):
    try:
        subprocess.Popen(["notify-send", "-a", "Simba Remoto", "-i", "simba", titulo, texto])
    except OSError:
        pass


class App(Adw.Application):
    def __init__(self, codigo_inicial=None):
        super().__init__(application_id="com.simba.Remoto", flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.janela = None
        self.codigo_inicial = codigo_inicial

    def do_activate(self):
        if not self.janela:
            self.janela = Janela(self, self.codigo_inicial)
            a = Gio.SimpleAction.new("novo-codigo", None)
            a.connect("activate", lambda *_: self.janela.trocar_codigo())
            self.add_action(a)
            s = Gio.SimpleAction.new("sobre", None)
            s.connect("activate", self._sobre)
            self.add_action(s)
        self.janela.present()

    def _sobre(self, *_):
        Adw.AboutDialog(application_name="Simba Remoto", application_icon="simba", version="0.2",
                        comments="Acesso remoto P2P sem servidor: DHT + WebRTC, criptografia de ponta a ponta.",
                        developer_name="Simba OS").present(self.janela)


def main(codigo_alvo=None):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    for n in ("aioice", "aiortc"):
        logging.getLogger(n).setLevel(logging.WARNING)
    sys.exit(App(codigo_inicial=codigo_alvo).run(sys.argv[:1]))
