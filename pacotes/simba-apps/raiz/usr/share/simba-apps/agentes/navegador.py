"""Navegador embutido no chat dos Agentes de IA.

Um painel ao lado da conversa (WebKitGTK 6) que tanto a pessoa quanto o agente
usam. O agente controla o painel pelo comando `simba-navegador`, que fala com
este processo por um socket Unix só do usuário ($XDG_RUNTIME_DIR, 0700/0600).
O caminho do socket vai para os agentes na variável SIMBA_NAVEGADOR.

Protocolo: uma linha JSON por conexão {"cmd": "...", ...} → uma linha JSON
{"ok": true/false, ...}. Comandos em PainelNavegador.COMANDOS.

Sessão (cookies, logins) em ~/.local/share/agentes/navegador — fica fora da ISO
(gerar-iso/excluir-logins.txt). Valores de campos de senha nunca são lidos.
"""
import json
import os
import sys
import time
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gio, GLib, Gtk, WebKit  # noqa: E402

sys.path.insert(0, "/usr/share/simba-apps/idiomas")
from simba_i18n import t as _t  # noqa: E402

HOME = Path.home()
DADOS = HOME / ".local/share/agentes/navegador"
CACHE = HOME / ".cache/agentes/navegador"
INICIAL = "https://duckduckgo.com/"

# ── JavaScript injetado ──────────────────────────────────────────────────────
# Tudo devolve JSON.stringify(...) para atravessar o JSC como texto.
JS_BASE = r"""
(function () {
  if (window.__simba) return;
  const visivel = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return false;
    const s = getComputedStyle(el);
    return s.visibility !== 'hidden' && s.display !== 'none' && s.opacity !== '0';
  };
  const rotulo = (el) => {
    const t = (el.getAttribute('aria-label') || el.innerText || el.value || el.getAttribute('title') ||
               el.getAttribute('alt') || el.getAttribute('placeholder') || el.getAttribute('name') || '').trim();
    return t.replace(/\s+/g, ' ').slice(0, 90);
  };
  const SEL = 'a[href], button, input:not([type=hidden]), textarea, select, summary, ' +
              '[role=button], [role=link], [role=tab], [role=menuitem], [role=checkbox], [contenteditable=""], [contenteditable=true]';
  window.__simba = {
    elementos() {
      let n = 0;
      const out = [];
      document.querySelectorAll('[data-simba-ref]').forEach(e => e.removeAttribute('data-simba-ref'));
      for (const el of document.querySelectorAll(SEL)) {
        if (!visivel(el) || el.disabled) continue;
        n += 1;
        el.setAttribute('data-simba-ref', String(n));
        const tag = el.tagName.toLowerCase();
        const tipo = (el.getAttribute('type') || '').toLowerCase();
        const item = { ref: n, tag, rotulo: rotulo(el) };
        if (tipo) item.tipo = tipo;
        if (tag === 'a') item.href = el.href.slice(0, 120);
        if ((tag === 'input' || tag === 'textarea' || tag === 'select') && tipo !== 'password') {
          if (el.value) item.valor = String(el.value).slice(0, 60);
        }
        if (tipo === 'password') item.senha = true;
        if (tipo === 'checkbox' || tipo === 'radio') item.marcado = el.checked;
        if (document.activeElement === el) item.foco = true;
        out.push(item);
        if (n >= 400) break;
      }
      return out;
    },
    achar(alvo) {
      if (alvo === null || alvo === undefined || alvo === '') return document.activeElement;
      if (/^\d+$/.test(String(alvo))) {
        let el = document.querySelector('[data-simba-ref="' + alvo + '"]');
        if (!el) { this.elementos(); el = document.querySelector('[data-simba-ref="' + alvo + '"]'); }
        return el;
      }
      try { const el = document.querySelector(alvo); if (el) return el; } catch (e) {}
      const txt = String(alvo).toLowerCase();
      let melhor = null;
      for (const el of document.querySelectorAll(SEL)) {
        if (!visivel(el)) continue;
        const r = rotulo(el).toLowerCase();
        if (r === txt) return el;
        if (!melhor && r.includes(txt)) melhor = el;
      }
      return melhor;
    },
    texto(max) {
      const t = (document.body ? document.body.innerText : '').replace(/\n{3,}/g, '\n\n');
      return t.length > max ? t.slice(0, max) + '\n…(cortado)' : t;
    }
  };
})();
"""


def _js_chamar(corpo):
    """Embrulha um corpo JS (que usa `S` = window.__simba e faz return) em JSON."""
    return JS_BASE + "\nJSON.stringify((function(){ const S = window.__simba; " + corpo + " })());"


def _corpo_js(codigo):
    """`js` sem return: devolve o valor da última instrução (aceita várias, separadas por ;)."""
    instrucoes = codigo.strip().rstrip(";").rsplit(";", 1)
    ultima = instrucoes[-1].strip()
    antes = instrucoes[0] + ";\n" if len(instrucoes) > 1 else ""
    return antes + "return (function(){ return (" + ultima + "); })();"


class PainelNavegador(Gtk.Box):
    COMANDOS = ("abrir", "ler", "elementos", "clicar", "digitar", "tecla", "rolar", "js", "captura",
                "esperar", "voltar", "avancar", "recarregar", "url", "mostrar", "fechar")

    def __init__(self, ao_mostrar=None, ao_esconder=None):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.add_css_class("navegador")
        self.ao_mostrar = ao_mostrar
        self.ao_esconder = ao_esconder
        self._esperando_carga = []
        self._conexoes = set()
        self.servico = None
        self.socket = None

        DADOS.mkdir(parents=True, exist_ok=True)
        CACHE.mkdir(parents=True, exist_ok=True)
        os.chmod(DADOS, 0o700)
        sessao = WebKit.NetworkSession.new(str(DADOS), str(CACHE))
        sessao.get_cookie_manager().set_persistent_storage(
            str(DADOS / "cookies.sqlite"), WebKit.CookiePersistentStorage.SQLITE)
        self.web = WebKit.WebView(network_session=sessao)
        self.web.set_vexpand(True)
        self.web.set_hexpand(True)
        cfg = self.web.get_settings()
        cfg.set_enable_developer_extras(False)
        cfg.set_javascript_can_open_windows_automatically(False)
        self.web.connect("load-changed", self._on_carga)
        self.web.connect("load-failed", self._on_falha)
        self.web.connect("notify::uri", lambda *_: self._atualizar_url())
        self.web.connect("notify::estimated-load-progress", self._on_progresso)
        self.web.connect("create", self._on_nova_janela)

        # barra: voltar, avançar, recarregar, endereço, abrir fora, fechar
        barra = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        barra.add_css_class("navegador-barra")
        for m in ("top", "bottom", "start", "end"):
            getattr(barra, f"set_margin_{m}")(6)

        def botao(icone, dica, acao):
            b = Gtk.Button(icon_name=icone)
            b.add_css_class("flat")
            b.set_tooltip_text(dica)
            b.connect("clicked", lambda _: acao())
            barra.append(b)
            return b

        self.btn_voltar = botao("go-previous-symbolic", _t("Voltar"), self.web.go_back)
        self.btn_avancar = botao("go-next-symbolic", _t("Avançar"), self.web.go_forward)
        botao("view-refresh-symbolic", _t("Recarregar"), self.web.reload)
        self.endereco = Gtk.Entry()
        self.endereco.set_hexpand(True)
        self.endereco.set_placeholder_text(_t("Endereço ou busca"))
        self.endereco.connect("activate", lambda e: self.abrir(e.get_text()))
        barra.append(self.endereco)
        botao("web-browser-symbolic", _t("Abrir no navegador padrão"),
              lambda: Gio.AppInfo.launch_default_for_uri(self.web.get_uri() or INICIAL, None))
        botao("window-close-symbolic", _t("Fechar o navegador"), self.esconder)
        self.append(barra)

        self.progresso = Gtk.ProgressBar()
        self.progresso.add_css_class("osd")
        self.progresso.set_visible(False)
        self.append(self.progresso)

        sobre = Gtk.Overlay()
        sobre.set_child(self.web)
        self.aviso = Gtk.Label(label=_t("A IA está usando o navegador"))
        self.aviso.add_css_class("navegador-aviso")
        self.aviso.set_halign(Gtk.Align.CENTER)
        self.aviso.set_valign(Gtk.Align.END)
        self.aviso.set_margin_bottom(14)
        self.aviso.set_visible(False)
        sobre.add_overlay(self.aviso)
        self.append(sobre)
        self._fonte_aviso = 0
        self._iniciou = False

    # ── uso pela interface ──────────────────────────────────────────────────
    def mostrar(self):
        if not self._iniciou:
            self._iniciou = True
            if not self.web.get_uri():
                self.web.load_uri(INICIAL)
        if self.ao_mostrar:
            self.ao_mostrar()

    def esconder(self):
        if self.ao_esconder:
            self.ao_esconder()

    def abrir(self, texto):
        texto = (texto or "").strip()
        if not texto:
            return
        if "://" not in texto and not texto.startswith("about:"):
            if " " in texto or "." not in texto:
                texto = "https://duckduckgo.com/?q=" + GLib.uri_escape_string(texto, None, False)
            else:
                texto = "https://" + texto
        self._iniciou = True
        self.web.load_uri(texto)
        self.mostrar()

    def _atualizar_url(self):
        uri = self.web.get_uri() or ""
        if not self.endereco.has_focus():
            self.endereco.set_text(uri)
        self.btn_voltar.set_sensitive(self.web.can_go_back())
        self.btn_avancar.set_sensitive(self.web.can_go_forward())

    def _on_progresso(self, *_):
        p = self.web.get_estimated_load_progress()
        self.progresso.set_fraction(p)
        self.progresso.set_visible(0 < p < 1)

    def _on_nova_janela(self, _web, acao):
        # links que abririam outra janela (target=_blank) abrem aqui mesmo
        uri = acao.get_request().get_uri()
        if uri:
            self.web.load_uri(uri)
        return None

    def _on_carga(self, _web, evento):
        if evento == WebKit.LoadEvent.FINISHED:
            self._liberar_espera()

    def _on_falha(self, _web, _evento, uri, erro):
        self._liberar_espera(erro=f"{uri}: {erro.message}")
        return False

    def _liberar_espera(self, erro=None):
        esperando, self._esperando_carga = self._esperando_carga, []
        for cb in esperando:
            cb(erro)

    def _sinalizar_ia(self):
        self.aviso.set_visible(True)
        if self._fonte_aviso:
            GLib.source_remove(self._fonte_aviso)
        self._fonte_aviso = GLib.timeout_add(2500, self._esconder_aviso)

    def _esconder_aviso(self):
        self.aviso.set_visible(False)
        self._fonte_aviso = 0
        return False

    # ── servidor de controle ────────────────────────────────────────────────
    def iniciar_controle(self, nome):
        base = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/simba-{os.getuid()}") / "simba-navegador"
        base.mkdir(parents=True, exist_ok=True)
        os.chmod(base, 0o700)
        caminho = base / f"{nome}-{os.getpid()}.sock"
        try:
            caminho.unlink()
        except FileNotFoundError:
            pass
        self.servico = Gio.SocketService()
        self.servico.add_address(Gio.UnixSocketAddress.new(str(caminho)), Gio.SocketType.STREAM,
                                 Gio.SocketProtocol.DEFAULT, None)
        os.chmod(caminho, 0o600)
        self.servico.connect("incoming", self._on_conexao)
        self.servico.start()
        self.socket = str(caminho)
        return self.socket

    def parar_controle(self):
        if self.servico:
            self.servico.stop()
            self.servico.close()
            self.servico = None
        if self.socket:
            try:
                os.unlink(self.socket)
            except OSError:
                pass

    def _on_conexao(self, _servico, conexao, _origem):
        self._conexoes.add(conexao)
        entrada = Gio.DataInputStream.new(conexao.get_input_stream())
        entrada.read_line_async(GLib.PRIORITY_DEFAULT, None, self._on_linha, conexao)
        return True

    def _on_linha(self, entrada, resultado, conexao):
        try:
            linha, _n = entrada.read_line_finish_utf8(resultado)
            pedido = json.loads(linha or "{}")
        except Exception as e:  # noqa: BLE001
            self._responder(conexao, {"ok": False, "erro": f"pedido inválido: {e}"})
            return
        cmd = pedido.get("cmd")
        if cmd not in self.COMANDOS:
            self._responder(conexao, {"ok": False, "erro": f"comando desconhecido: {cmd}",
                                      "comandos": list(self.COMANDOS)})
            return
        self._sinalizar_ia()
        try:
            getattr(self, "_cmd_" + cmd)(pedido, lambda r: self._responder(conexao, r))
        except Exception as e:  # noqa: BLE001
            self._responder(conexao, {"ok": False, "erro": str(e)})

    def _responder(self, conexao, resposta):
        dados = (json.dumps(resposta, ensure_ascii=False) + "\n").encode()
        try:
            conexao.get_output_stream().write_all(dados, None)
            conexao.close(None)
        except GLib.Error:
            pass
        self._conexoes.discard(conexao)

    # ── utilidades dos comandos ─────────────────────────────────────────────
    def _js(self, corpo, pronto):
        def fim(web, res, _dado=None):
            try:
                valor = web.evaluate_javascript_finish(res)
                texto = valor.to_string() if valor is not None else "null"
                pronto(json.loads(texto) if texto not in (None, "", "undefined") else None, None)
            except Exception as e:  # noqa: BLE001
                pronto(None, str(getattr(e, "message", e)))
        self.web.evaluate_javascript(_js_chamar(corpo), -1, None, None, None, fim, None)

    def _estado(self):
        return {"url": self.web.get_uri() or "", "titulo": self.web.get_title() or ""}

    def _esperar_carga(self, cb, limite=30):
        """Chama cb(erro) quando a página terminar de carregar (ou no limite)."""
        if not self.web.is_loading():
            GLib.timeout_add(150, lambda: (cb(None), False)[1])
            return
        feito = {"v": False}

        def uma_vez(erro):
            if not feito["v"]:
                feito["v"] = True
                cb(erro)
        self._esperando_carga.append(uma_vez)
        GLib.timeout_add_seconds(limite, lambda: (uma_vez("tempo esgotado esperando a página"), False)[1])

    def _depois_de_acao(self, responder, extra=None):
        """Após clicar/teclar: dá tempo para a navegação começar e espera carregar."""
        def checar():
            def fim(erro):
                r = {"ok": True, **self._estado(), **(extra or {})}
                if erro:
                    r["aviso"] = erro
                responder(r)
            self._esperar_carga(fim, limite=20)
            return False
        GLib.timeout_add(400, checar)

    # ── comandos ────────────────────────────────────────────────────────────
    def _cmd_abrir(self, p, responder):
        self.abrir(p.get("url", ""))
        GLib.timeout_add(200, lambda: (self._esperar_carga(
            lambda erro: responder({"ok": not erro, **self._estado(), **({"erro": erro} if erro else {})})), False)[1])

    def _cmd_mostrar(self, _p, responder):
        self.mostrar()
        responder({"ok": True, **self._estado()})

    def _cmd_fechar(self, _p, responder):
        self.esconder()
        responder({"ok": True})

    def _cmd_url(self, _p, responder):
        responder({"ok": True, "carregando": self.web.is_loading(), **self._estado()})

    def _cmd_voltar(self, _p, responder):
        self.web.go_back()
        self._depois_de_acao(responder)

    def _cmd_avancar(self, _p, responder):
        self.web.go_forward()
        self._depois_de_acao(responder)

    def _cmd_recarregar(self, _p, responder):
        self.web.reload()
        self._depois_de_acao(responder)

    def _cmd_ler(self, p, responder):
        maximo = int(p.get("max") or 12000)
        def fim(v, erro):
            if erro:
                responder({"ok": False, "erro": erro, **self._estado()})
                return
            responder({"ok": True, **self._estado(), "texto": v["texto"], "elementos": v["elementos"]})
        self._js(f"return {{texto: S.texto({maximo}), elementos: S.elementos()}};", fim)

    def _cmd_elementos(self, _p, responder):
        self._js("return S.elementos();", lambda v, erro: responder(
            {"ok": not erro, **self._estado(), **({"erro": erro} if erro else {"elementos": v})}))

    def _cmd_clicar(self, p, responder):
        alvo = json.dumps(p.get("alvo", ""))
        corpo = (f"const el = S.achar({alvo}); if (!el) return {{achou: false}};"
                 "el.scrollIntoView({block: 'center'}); el.focus && el.focus();"
                 "const r = (el.innerText || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 80);"
                 "el.click(); return {achou: true, rotulo: r};")

        def fim(v, erro):
            if erro or not v or not v.get("achou"):
                responder({"ok": False, "erro": erro or "elemento não encontrado (rode `elementos`)", **self._estado()})
                return
            self._depois_de_acao(responder, {"clicado": v.get("rotulo", "")})
        self._js(corpo, fim)

    def _cmd_digitar(self, p, responder):
        alvo = json.dumps(p.get("alvo", ""))
        texto = json.dumps(p.get("texto", ""))
        limpar = "true" if p.get("limpar") else "false"
        corpo = (f"const el = S.achar({alvo}); if (!el) return {{achou: false}};"
                 "el.scrollIntoView({block: 'center'}); el.focus();"
                 f"if ({limpar}) {{ if (el.select) el.select(); document.execCommand('delete'); }}"
                 f"const t = {texto};"
                 # insertText dispara os eventos de input de verdade (React, campos que
                 # pulam sozinhos para o próximo, como o código do GitHub)
                 "for (const ch of t) { const a = document.activeElement || el;"
                 "  if (!document.execCommand('insertText', false, ch)) {"
                 "    if ('value' in a) { a.value += ch; a.dispatchEvent(new Event('input', {bubbles: true})); } } }"
                 "const f = document.activeElement;"
                 "return {achou: true, foco: f ? (f.getAttribute('data-simba-ref') || f.tagName.toLowerCase()) : ''};")

        def fim(v, erro):
            if erro or not v or not v.get("achou"):
                responder({"ok": False, "erro": erro or "campo não encontrado (rode `elementos`)", **self._estado()})
                return
            if p.get("enter"):
                self._cmd_tecla({"tecla": "Enter"}, responder)
            else:
                responder({"ok": True, **self._estado(), "foco": v.get("foco")})
        self._js(corpo, fim)

    def _cmd_tecla(self, p, responder):
        tecla = json.dumps(p.get("tecla", "Enter"))
        corpo = (f"const k = {tecla}; const el = document.activeElement || document.body;"
                 "const op = {key: k, code: k, bubbles: true, cancelable: true};"
                 "const ok = el.dispatchEvent(new KeyboardEvent('keydown', op));"
                 "el.dispatchEvent(new KeyboardEvent('keypress', op));"
                 "el.dispatchEvent(new KeyboardEvent('keyup', op));"
                 "if (k === 'Enter' && ok && el.form) { if (el.form.requestSubmit) el.form.requestSubmit(); else el.form.submit(); }"
                 "if (k === 'Tab') { const l = [...document.querySelectorAll('input,button,a[href],textarea,select')];"
                 "  const i = l.indexOf(el); if (i >= 0 && l[i + 1]) l[i + 1].focus(); }"
                 "return {ok: true};")
        self._js(corpo, lambda v, erro: (responder({"ok": False, "erro": erro}) if erro
                                          else self._depois_de_acao(responder)))

    def _cmd_rolar(self, p, responder):
        dy = -0.8 if p.get("direcao") == "cima" else 0.8
        self._js(f"window.scrollBy(0, window.innerHeight * {dy}); return {{y: Math.round(window.scrollY)}};",
                 lambda v, erro: responder({"ok": not erro, **self._estado(), **(v or {})}))

    def _cmd_js(self, p, responder):
        codigo = p.get("codigo", "")
        corpo = codigo if "return" in codigo else _corpo_js(codigo)
        self._js(corpo, lambda v, erro: responder(
            {"ok": not erro, **({"erro": erro} if erro else {"resultado": v})}))

    def _cmd_esperar(self, p, responder):
        procurado = str(p.get("texto", "")).lower()
        limite = time.time() + float(p.get("segundos") or 20)

        def tentar():
            def fim(v, _erro):
                if v and procurado in v.lower():
                    responder({"ok": True, **self._estado()})
                elif time.time() > limite:
                    responder({"ok": False, "erro": "texto não apareceu no tempo", **self._estado()})
                else:
                    GLib.timeout_add(500, lambda: (tentar(), False)[1])
            self._js("return S.texto(200000);", fim)
        tentar()

    def _cmd_captura(self, p, responder):
        destino = p.get("arquivo") or str(HOME / ".cache/agentes/navegador" / f"captura-{int(time.time())}.png")

        def fim(web, res, _dado=None):
            try:
                textura = web.get_snapshot_finish(res)
                textura.save_to_png(destino)
                responder({"ok": True, **self._estado(), "arquivo": destino})
            except Exception as e:  # noqa: BLE001
                responder({"ok": False, "erro": str(getattr(e, "message", e))})
        self.web.get_snapshot(WebKit.SnapshotRegion.VISIBLE, WebKit.SnapshotOptions.NONE, None, fim, None)


INSTRUCAO_AGENTE = """[Ferramenta do chat do Simba OS: navegador embutido]
Este chat tem um navegador ao lado da conversa, que o usuário também vê. Quando precisar abrir uma página (login no GitHub, documentação, um painel web), use-o pelo terminal em vez de pedir para o usuário abrir:
  simba-navegador abrir <url>          abre e espera carregar
  simba-navegador ler                  texto da página + elementos numerados
  simba-navegador elementos            só os elementos clicáveis/campos, com número
  simba-navegador clicar <n|texto>     clica no elemento (número de `elementos` ou o texto dele)
  simba-navegador digitar <n> <texto> [--enter] [--limpar]
  simba-navegador tecla Enter|Tab|Escape
  simba-navegador esperar <texto> [segundos]    espera um texto aparecer
  simba-navegador captura              PNG da tela do navegador (abra a imagem para ver)
  simba-navegador rolar baixo|cima · voltar · url · js <código>
  simba-navegador fechar               esconde o navegador; a conversa volta a ocupar a janela
Senhas e códigos de dois fatores: deixe o usuário digitar no próprio navegador e espere (`esperar`) em vez de pedir no chat. O navegador guarda os logins entre conversas.
Quando terminar o que precisava fazer na página, rode `simba-navegador fechar` para o chat voltar ao foco. Só deixe aberto se o usuário ainda tiver algo a fazer nela (digitar uma senha, aprovar um login) ou se ele pediu para ver a página."""
