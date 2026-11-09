"""Leitura da saída dos agentes de IA (sem GTK, para poder ser testada sozinha).

Cada CLI fala um dialeto: Claude Code (stream-json com mensagens parciais),
Codex (`exec --json`), OpenCode (`run --format json`), Antigravity (stream-json
próprio) e os demais em texto puro. O parser separa:

- o texto da resposta (vai para a bolha do chat);
- a atividade (ferramentas, comandos, arquivos) que vai para a pílula/detalhes;
- metadados: id da sessão (para retomar a conversa certa), modelo, uso de tokens,
  custo, janelas de limite e erros (para a troca automática de agente).
"""
from pathlib import Path
import json
import re
import sys

sys.path.insert(0, "/usr/share/simba-apps/idiomas")
try:
    from simba_i18n import t as _t  # noqa: E402
except ImportError:  # testes fora do sistema
    def _t(texto, *args):
        for i, a in enumerate(args, 1):
            texto = texto.replace(f"%{i}", str(a))
        return texto

# Sequências ANSI (cores, cursor, limpeza de linha) que alguns CLIs ainda emitem
# mesmo no modo de impressão. Elas não podem chegar ao texto do chat.
ANSI_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\)|[@-_])")

# Agentes cuja resposta chega só em JSON: qualquer linha de texto puro é log da
# CLI (stderr misturado no pty) e não pode virar texto da conversa.
SO_JSON = {"claude", "codex", "opencode"}


def _curto(texto, n):
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= n else texto[: n - 1] + "…"


def descrever_ferramenta(nome, entrada):
    """Frase curta para a pílula de atividade, a partir do nome e da entrada da ferramenta."""
    entrada = entrada if isinstance(entrada, dict) else {}
    low = (nome or "").lower()
    cmd = entrada.get("command") or entrada.get("CommandLine") or entrada.get("cmd")
    if isinstance(cmd, list):
        cmd = " ".join(str(c) for c in cmd)
    caminho = (entrada.get("file_path") or entrada.get("filePath") or entrada.get("path")
               or entrada.get("Path") or entrada.get("notebook_path") or "")
    arquivo = Path(str(caminho)).name or str(caminho)
    consulta = entrada.get("query") or entrada.get("pattern") or entrada.get("url") or ""
    if cmd or low in ("bash", "shell", "run_command", "command_execution"):
        return f"{_t('Executando:')} {_curto(cmd or nome, 60)}"
    if low in ("read", "read_file", "view_file", "view"):
        return f"{_t('Lendo:')} {arquivo or '…'}"
    if low in ("edit", "write", "multiedit", "write_to_file", "replace_file_content", "edit_file",
               "patch", "apply_patch", "file_change", "notebookedit"):
        return f"{_t('Editando:')} {arquivo or '…'}"
    if low in ("websearch", "search_web", "web_search"):
        return f"{_t('Pesquisando na web:')} {_curto(consulta, 40)}"
    if low in ("webfetch", "fetch", "web_fetch"):
        return f"{_t('Abrindo:')} {_curto(consulta, 50)}"
    if low in ("grep", "glob", "search", "find", "codebase_search"):
        return f"{_t('Procurando:')} {_curto(consulta or arquivo, 40)}"
    if low in ("list_dir", "ls", "list"):
        return f"{_t('Listando:')} {arquivo or _t('arquivos')}"
    if low in ("task", "agent"):
        desc = entrada.get("description") or entrada.get("prompt") or ""
        return f"{_t('Subagente:')} {_curto(desc, 50)}"
    if low in ("todowrite", "todo", "todo_list"):
        return f"{_t('Atualizando a lista de tarefas')}"
    alvo = arquivo or consulta
    return f"{nome}{': ' + _curto(alvo, 50) if alvo else ''}"


class AgentStreamParser:
    """Interpreta streams JSON (NDJSON) ou texto puro dos agentes de IA.

    Callbacks (chamados na thread de leitura; quem usa decide como levar à GUI):
      on_status(texto)  atividade/ferramenta em andamento
      on_text(texto)    pedaço do texto da resposta
      on_done(texto)    fim da resposta (texto final, se a CLI informar)
      on_meta(dict)     metadados novos (sessao, modelo, uso, janelas…)
    """

    def __init__(self, on_status, on_text, on_done, agente=None, on_meta=None):
        self.on_status = on_status
        self.on_text = on_text
        self.on_done = on_done
        self.on_meta = on_meta or (lambda _m: None)
        self.agente = agente
        self.buffer = ""
        self.actions = []
        self.last_response = ""
        self.has_text = False
        self.texto = ""            # tudo o que já foi para a bolha
        # Só o texto que a IA responde (e os erros) entram na detecção de limite.
        # Resultados de ferramentas (ex.: um arquivo lido) não podem disparar a
        # troca de agente.
        self.texto_detectavel = ""
        self.erro = ""             # mensagem de erro informada pela CLI
        self.limite = False        # a CLI disse, de forma estruturada, que o limite acabou
        self.limite_ate = None     # epoch (s) de quando volta, se informado
        self.sessao = None
        self.modelo = None
        self.uso = {}              # entrada, saida, custo
        self.janelas = {}          # {"5h": 0.04, "7d": 0.0} (fração usada)
        self._parcial = False      # Claude: texto já chegou por deltas
        self._bloco_novo = False   # Claude: próximo delta abre um bloco de texto novo
        self._done = False

    # ── utilidades ───────────────────────────────────────────────────────────
    def _registrar(self, txt):
        if txt:
            self.texto_detectavel = (self.texto_detectavel + txt)[-4000:]

    def _texto(self, txt, separar=False):
        """Acrescenta texto da resposta; `separar` põe uma linha em branco entre blocos."""
        if not txt:
            return
        if separar and self.texto and not self.texto.endswith("\n") and not txt.startswith("\n"):
            txt = "\n\n" + txt
        self.texto += txt
        self.has_text = True
        self._registrar(txt)
        self.on_text(txt)

    def _status(self, desc, acao=False):
        if acao and desc not in self.actions:
            self.actions.append(desc)
        self.on_status(desc)

    def _meta(self, **kw):
        mudou = {k: v for k, v in kw.items() if v is not None and getattr(self, k, None) != v}
        for k, v in mudou.items():
            setattr(self, k, v)
        if mudou:
            self.on_meta(mudou)

    def _somar_uso(self, entrada=0, saida=0, custo=None, substituir=False):
        u = {} if substituir else dict(self.uso)
        u["entrada"] = (0 if substituir else u.get("entrada", 0)) + int(entrada or 0)
        u["saida"] = (0 if substituir else u.get("saida", 0)) + int(saida or 0)
        if custo is not None:
            u["custo"] = (0 if substituir else u.get("custo", 0.0)) + float(custo or 0)
        self.uso = u
        self.on_meta({"uso": u})

    def _erro(self, msg):
        msg = str(msg or "").strip()
        if msg:
            self.erro = msg if not self.erro else f"{self.erro}\n{msg}"
            self.erro = self.erro[-2000:]
            self._registrar("\n" + msg)

    # ── entrada ──────────────────────────────────────────────────────────────
    def feed(self, chunk: str):
        self.buffer += chunk
        lines = self.buffer.split("\n")
        self.buffer = lines.pop()
        for line in lines:
            self._linha(line)

    def _linha(self, line):
        line = ANSI_RE.sub("", line.replace("\r", ""))
        line_s = line.strip()
        if not line_s:
            return
        if line_s.startswith("{") and line_s.endswith("}"):
            try:
                data = json.loads(line_s)
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict):
                self._handle_json(data)
                return
        self._handle_plain_text(line_s)

    def finish(self):
        if self.buffer.strip():
            self._linha(self.buffer)
        self.buffer = ""
        if not self._done:
            self._done = True
            self.on_done(self.last_response)

    # ── JSON ─────────────────────────────────────────────────────────────────
    def _handle_json(self, data: dict):
        sessao = data.get("session_id") or data.get("sessionID") or data.get("thread_id")
        if isinstance(sessao, str) and sessao:
            self._meta(sessao=sessao)

        if isinstance(data.get("event"), str):  # Antigravity ("event": "step_update")
            self._antigravity(data)
            return
        t = data.get("type")
        if not isinstance(t, str):
            return
        if t in ("system", "stream_event", "assistant", "user", "result", "rate_limit_event"):
            self._claude(t, data)
        elif t == "error" and isinstance(data.get("error"), dict):
            self._opencode(t, data)
        elif "." in t or t == "error":
            self._codex(t, data)
        elif isinstance(data.get("part"), dict) or t in ("text", "tool_use", "step_start", "step_finish"):
            self._opencode(t, data)
        elif t == "content_block_delta":  # formato antigo, sem envelope
            self._texto((data.get("delta") or {}).get("text", ""))

    def _antigravity(self, data):
        event = data.get("event")
        if event == "step_update":
            su = data.get("step_update", {})
            st, state = su.get("step_type"), su.get("state")
            if st == "tool":
                tinfo = su.get("tool_info", {}) or {}
                desc = descrever_ferramenta(su.get("tool_name", "ferramenta"), tinfo.get("parameters", {}))
                if state == "ACTIVE":
                    self._status(desc)
                elif state == "DONE":
                    self._status(desc, acao=True)
                    self.on_status(_t("✦ Pensando na resposta..."))
            elif st == "agent_response":
                self._texto(su.get("text_delta"))
        elif event == "result":
            res = data.get("result", {}) or {}
            self.last_response = res.get("response", "") or ""
            self._registrar(self.last_response)
            if res.get("error"):
                self._erro(res.get("error"))
            for k in ("conversation_id", "conversationId", "cascade_id"):
                if isinstance(res.get(k), str):
                    self._meta(sessao=res[k])

    def _claude(self, t, data):
        if t == "system":
            if data.get("subtype") == "init":
                self._meta(modelo=data.get("model"))
            return
        if t == "rate_limit_event":
            info = data.get("rate_limit_info") or {}
            janelas = {}
            for nome, w in (info.get("unifiedWindows") or {}).items():
                if isinstance(w, dict) and w.get("utilization") is not None:
                    rotulo = {"five_hour": "5h", "seven_day": "7d"}.get(nome, nome)
                    janelas[rotulo] = float(w["utilization"])
            if janelas:
                self._meta(janelas=janelas)
            if info.get("status") == "rejected":
                self.limite = True
                self.limite_ate = info.get("resetsAt")
            return
        if t == "stream_event":
            ev = data.get("event") or {}
            et = ev.get("type")
            if data.get("parent_tool_use_id"):
                return  # texto de subagente: fica fora da resposta
            if et == "content_block_start":
                bloco = ev.get("content_block") or {}
                if bloco.get("type") == "text":
                    self._bloco_novo = True
                elif bloco.get("type") == "tool_use":
                    self._status(descrever_ferramenta(bloco.get("name", ""), {}))
                elif bloco.get("type") == "thinking":
                    self.on_status(_t("✦ Pensando..."))
            elif et == "content_block_delta":
                delta = ev.get("delta") or {}
                if delta.get("type") == "text_delta" and delta.get("text"):
                    self._parcial = True
                    self._texto(delta["text"], separar=self._bloco_novo)
                    self._bloco_novo = False
            return
        if t == "assistant":
            if data.get("parent_tool_use_id"):
                return
            msg = data.get("message") or {}
            self._meta(modelo=msg.get("model"))
            for c in msg.get("content") or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text" and not self._parcial:
                    self._texto(c.get("text", ""), separar=True)
                elif c.get("type") == "tool_use":
                    self._status(descrever_ferramenta(c.get("name", ""), c.get("input")), acao=True)
            if msg.get("error") or data.get("error"):
                self._erro(msg.get("error") or data.get("error"))
            return
        if t == "user":
            return  # resultados de ferramentas
        if t == "result":
            self.last_response = data.get("result", "") or ""
            if data.get("is_error") or str(data.get("subtype", "")).startswith("error"):
                self._erro(self.last_response or data.get("subtype"))
            else:
                self._registrar("")
            u = data.get("usage") or {}
            entrada = sum(int(u.get(k) or 0) for k in
                          ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            self._somar_uso(entrada, u.get("output_tokens", 0), data.get("total_cost_usd"), substituir=True)
            if not self.has_text and self.last_response and not self.erro:
                self._texto(self.last_response)
            self._done = True
            self.on_done(self.last_response)

    def _codex(self, t, data):
        if t == "error":
            msg = str(data.get("message", ""))
            if msg.lower().startswith("reconnecting"):
                self.on_status(f"⚠ {_curto(msg, 70)}")
            else:
                self._erro(msg)
            return
        if t == "turn.failed":
            self._erro((data.get("error") or {}).get("message", "") or "turn.failed")
            return
        if t == "turn.completed":
            u = data.get("usage") or {}
            self._somar_uso(u.get("input_tokens", 0), u.get("output_tokens", 0))
            return
        if t == "turn.started":
            self.on_status(_t("✦ Pensando na resposta..."))
            return
        item = data.get("item")
        if not isinstance(item, dict):
            return
        it = item.get("type") or item.get("item_type")
        fim = t == "item.completed"
        if it == "agent_message":
            if fim:
                self._texto(item.get("text", ""), separar=True)
        elif it == "reasoning":
            self.on_status(_t("✦ Pensando..."))
        elif it == "command_execution":
            self._status(descrever_ferramenta("shell", {"command": item.get("command", "")}), acao=fim)
        elif it == "file_change":
            for ch in item.get("changes") or []:
                self._status(descrever_ferramenta("edit", {"path": ch.get("path", "")}), acao=fim)
        elif it == "web_search":
            self._status(descrever_ferramenta("web_search", {"query": item.get("query", "")}), acao=fim)
        elif it == "mcp_tool_call":
            nome = f"{item.get('server', '')}.{item.get('tool', '')}".strip(".")
            self._status(descrever_ferramenta(nome, item.get("arguments")), acao=fim)
        elif it == "todo_list":
            self._status(descrever_ferramenta("todo", {}))
        elif it == "error":
            self.on_status(f"⚠ {_curto(item.get('message', ''), 70)}")

    def _opencode(self, t, data):
        part = data.get("part") if isinstance(data.get("part"), dict) else {}
        if t == "text":
            if part.get("type", "text") == "text":
                self._texto(part.get("text", ""), separar=True)
                self.last_response = self.texto
        elif t == "step_start":
            self.on_status(_t("✦ Pensando na resposta..."))
        elif t == "step_finish":
            tok = part.get("tokens") or {}
            cache = tok.get("cache") or {}
            self._somar_uso((tok.get("input") or 0) + (cache.get("read") or 0) + (cache.get("write") or 0),
                            (tok.get("output") or 0) + (tok.get("reasoning") or 0), part.get("cost"))
        elif t == "tool_use":
            state = part.get("state") or {}
            nome = part.get("tool") or data.get("name") or "ferramenta"
            entrada = state.get("input") or data.get("input") or {}
            self._status(descrever_ferramenta(nome, entrada), acao=True)
            if state.get("status") == "error" and state.get("error"):
                self.on_status(f"⚠ {_curto(state['error'], 70)}")
        elif t == "error":
            err = data.get("error") or {}
            msg = err.get("message") or (err.get("data") or {}).get("message") or json.dumps(err)[:300]
            self._erro(msg)

    # ── texto puro ───────────────────────────────────────────────────────────
    def _handle_plain_text(self, line: str):
        clean = ANSI_RE.sub("", line.replace("\r", ""))
        clean = re.sub(r"[⠀-⣿]+", "", clean).strip()
        if not clean:
            return
        # Agentes JSON: texto puro é log/erro da CLI, nunca resposta.
        if self.agente in SO_JSON:
            if re.search(r"\b(error|erro|fatal|panic|unauthori[sz]ed|limit|quota)\b", clean, re.I):
                self._erro(clean)
            self.on_status(f"{_curto(clean, 70)}")
            return
        m = re.match(r"^(?:Running command|Reading file|Editing file|Searching)\s*:?\s*(.*)", clean, re.I)
        if m:
            self._status(f"{_curto(clean, 60)}")
            return
        if re.search(r"(?:Antigravity CLI|ctrl\+o to expand|\bcommands? \(\+\d+)", clean, re.I):
            self.on_status(_t("Executando ações..."))
            return
        self._texto(clean + "\n")
