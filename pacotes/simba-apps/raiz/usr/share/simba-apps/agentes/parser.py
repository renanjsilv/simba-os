"""Leitura da saída dos agentes de IA (sem GTK, para poder ser testada sozinha).

Cada CLI fala um dialeto: Claude Code (stream-json com mensagens parciais),
Codex (`exec --json`), OpenCode (`run --format json`), Antigravity (stream-json
próprio) e os demais em texto puro. O parser separa:

- o texto da resposta (vai para a bolha do chat);
- a atividade (ferramentas, comandos, arquivos) que vai para a pílula/detalhes;
- metadados: id da sessão (para retomar a conversa certa), modelo, uso de tokens,
  custo, janelas de limite e erros (para a troca automática de agente);
- eventos estruturados (on_evento) para o bloco "Pensando": cada passo com tipo,
  entrada (comando, arquivo, diff), saída e estado, e o texto do raciocínio.
"""
from pathlib import Path
import difflib
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


# Tipos de passo (o chat escolhe o ícone e o cartão por eles)
_TIPOS = (
    ("leitura", ("read", "read_file", "view_file", "view", "list_dir", "ls", "list", "notebookread")),
    ("edicao", ("edit", "write", "multiedit", "write_to_file", "replace_file_content", "edit_file",
                "patch", "apply_patch", "file_change", "notebookedit")),
    ("web", ("websearch", "search_web", "web_search", "webfetch", "fetch", "web_fetch")),
    ("busca", ("grep", "glob", "search", "find", "codebase_search", "toolsearch")),
    ("subagente", ("task", "agent")),
    ("tarefas", ("todowrite", "todo", "todo_list")),
)
SAIDA_MAX = 6000      # caracteres da saída de um comando que seguem para o chat
DIFF_MAX = 160        # linhas de diff guardadas por edição


def tipo_ferramenta(nome, entrada=None):
    """comando | leitura | edicao | busca | web | subagente | tarefas | outro."""
    entrada = entrada if isinstance(entrada, dict) else {}
    low = (nome or "").lower()
    if entrada.get("command") or entrada.get("CommandLine") or entrada.get("cmd") \
            or low in ("bash", "shell", "run_command", "command_execution", "monitor"):
        return "comando"
    for tipo, nomes in _TIPOS:
        if low in nomes:
            return tipo
    return "outro"


def _cortar_meio(texto, limite=SAIDA_MAX):
    """Texto longo: fica o começo e o fim (o erro costuma estar no fim)."""
    if len(texto) <= limite:
        return texto
    cabeca = limite * 2 // 3
    return texto[:cabeca] + "\n⋯\n" + texto[-(limite - cabeca):]


def _diff(antes, depois):
    """Diff resumido (linhas '+', '-', ' ' e '⋯' entre trechos) e contagem (+, −)."""
    a, d = str(antes or "").splitlines(), str(depois or "").splitlines()
    linhas, mais, menos = [], 0, 0
    for l in difflib.unified_diff(a, d, lineterm="", n=1):
        if l.startswith(("---", "+++")):
            continue
        if l.startswith("@@"):
            if linhas:
                linhas.append("⋯")
            continue
        mais += l.startswith("+")
        menos += l.startswith("-")
        linhas.append(l[:400])
    return linhas, mais, menos


def resumir_entrada(tipo, entrada):
    """O que o chat precisa para desenhar o passo (e guardar na conversa), já enxuto."""
    entrada = entrada if isinstance(entrada, dict) else {}
    r = {}
    if tipo == "comando":
        cmd = entrada.get("command") or entrada.get("CommandLine") or entrada.get("cmd") or ""
        if isinstance(cmd, list):
            cmd = " ".join(str(c) for c in cmd)
        if cmd:
            r["comando"] = str(cmd)[:8000]
        if isinstance(entrada.get("description"), str) and entrada["description"].strip():
            r["descricao"] = _curto(entrada["description"], 120)
    elif tipo == "edicao":
        caminho = (entrada.get("file_path") or entrada.get("filePath") or entrada.get("path")
                   or entrada.get("Path") or entrada.get("notebook_path") or entrada.get("TargetFile") or "")
        if caminho:
            r["arquivo"] = str(caminho)
        linhas, mais, menos = [], 0, 0
        pares = []
        for e in entrada.get("edits") or []:
            if isinstance(e, dict):
                pares.append((e.get("old_string", e.get("oldString")), e.get("new_string", e.get("newString"))))
        velho = entrada.get("old_string", entrada.get("oldString"))
        novo = entrada.get("new_string", entrada.get("newString", entrada.get("new_source")))
        if velho is not None or novo is not None:
            pares.append((velho, novo))
        for velho, novo in pares:
            l, m, n = _diff(velho, novo)
            if linhas and l:
                linhas.append("⋯")
            linhas += l
            mais += m
            menos += n
        conteudo = entrada.get("content", entrada.get("CodeContent"))
        remendo = entrada.get("patch") or entrada.get("input")
        if not pares and isinstance(conteudo, str):
            corpo = conteudo.splitlines()
            linhas, mais = ["+" + l[:400] for l in corpo], len(corpo)
            r["novo"] = True
        elif not pares and isinstance(remendo, str) and "\n" in remendo:
            for l in remendo.splitlines():
                if l.startswith(("+++", "---", "***")):
                    continue
                if l.startswith("@@"):
                    linhas.append("⋯")
                elif l[:1] in "+- ":
                    linhas.append(l[:400])
                    mais += l.startswith("+")
                    menos += l.startswith("-")
        if entrada.get("kind") in ("add", "delete", "update"):
            r["operacao"] = entrada["kind"]
        if linhas:
            if len(linhas) > DIFF_MAX:
                r["cortado"] = len(linhas) - DIFF_MAX
                linhas = linhas[:DIFF_MAX]
            r["diff"] = "\n".join(linhas)
        if mais or menos:
            r["mais"], r["menos"] = mais, menos
    return r


def _texto_resultado(conteudo):
    """Texto de um tool_result (string ou lista de blocos)."""
    if isinstance(conteudo, str):
        return conteudo
    partes = []
    for c in conteudo if isinstance(conteudo, list) else []:
        if isinstance(c, dict) and c.get("type") == "text":
            partes.append(str(c.get("text") or ""))
    return "\n".join(partes)


# Recusa por falta de permissão (modo somente leitura), e não um erro do próprio comando:
# "Permission denied" de um `cat /etc/shadow` não pode cair aqui.
_NEGADO_RE = re.compile(r"requested permissions? to|haven't granted|permission to use \S+ has been denied|"
                        r"denied this tool|in plan mode|plan mode is active|read-only mode|"
                        r"requires approval|approval (was )?(denied|rejected)", re.I)


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
      on_evento(dict)   opcional: passos estruturados e raciocínio
          {"ev": "passo", "id", ...}  cria ou atualiza um passo. Campos (todos opcionais
              depois do id): tipo, nome, texto, pai (id do subagente), entrada (ver
              resumir_entrada), estado ("rodando" | "ok" | "erro" | "negado"), saida,
              linhas, fundo (segue em segundo plano), acoes, tokens, detalhe, nota.
          {"ev": "raciocinio", "texto"}  pedaço do raciocínio do modelo.
    """

    def __init__(self, on_status, on_text, on_done, agente=None, on_meta=None, on_evento=None):
        self.on_status = on_status
        self.on_text = on_text
        self.on_done = on_done
        self.on_meta = on_meta or (lambda _m: None)
        self.on_evento = on_evento or (lambda _e: None)
        self._tipos = {}           # id do passo → tipo (para saber o que fazer com o resultado)
        self._fundo = set()        # passos que continuam em segundo plano depois do tool_result
        self._tarefa_passo = {}    # task_id → id do passo
        self._seq = 0
        self._pensou_parcial = False
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
        # Trabalho em segundo plano (Claude: subagentes e comandos que continuam depois
        # da resposta). Enquanto houver, o processo segue vivo de propósito.
        self.tarefas = {}          # id → {"tipo": "local_agent"|"local_bash"…, "descricao": …}
        self.uso_tarefas = {}      # id → tokens gastos pelo subagente
        self.resultados = 0        # quantos "result" já chegaram (um por rodada)
        self.fim_rodada = False    # o último evento foi um "result" e nada veio depois
        # Mesma ação repetida em seguida (agente preso num laço): o chat cancela.
        self.repeticoes = 0
        self._ultima_acao = None

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

    def _passo(self, pid, nome=None, entrada=None, **campos):
        """Cria/atualiza um passo estruturado. Sem id, cada chamada é um passo novo."""
        if not pid:
            self._seq += 1
            pid = f"p{self._seq}"
        pid = str(pid)
        ev = {"ev": "passo", "id": pid}
        if nome is not None:
            tipo = tipo_ferramenta(nome, entrada)
            # a entrada completa pode chegar depois (e mudar "outro" para "comando")
            if tipo != "outro" or pid not in self._tipos:
                self._tipos[pid] = tipo
            ev["tipo"] = self._tipos[pid]
            ev["nome"] = str(nome)
            resumo = resumir_entrada(ev["tipo"], entrada)
            if resumo:
                ev["entrada"] = resumo
        ev.update({k: v for k, v in campos.items() if v is not None})
        self.on_evento(ev)
        return pid

    def _resultado(self, pid, saida="", erro=False, negado=False):
        """Fim de um passo: estado e, para comandos e edições, a saída."""
        if not pid:
            return
        pid = str(pid)
        saida = ANSI_RE.sub("", str(saida or "")).replace("\r", "").strip("\n")
        m = re.fullmatch(r"\s*<tool_use_error>(.*)</tool_use_error>\s*", saida, re.S)
        if m:
            saida = m.group(1)
        ev = {"ev": "passo", "id": pid}
        if erro and (negado or _NEGADO_RE.search(saida[:600])):
            ev["estado"] = "negado"
        elif erro:
            ev["estado"] = "erro"
        elif pid in self._fundo:
            ev["fundo"] = True      # segue rodando; o aviso de tarefa conclui
        else:
            ev["estado"] = "ok"
        if saida and self._tipos.get(pid) in ("comando", "edicao"):
            ev["linhas"] = saida.count("\n") + 1
            ev["saida"] = _cortar_meio(saida)
        elif saida and erro:
            ev["nota"] = _curto(saida, 300)
        self.on_evento(ev)

    def _raciocinio(self, texto):
        if texto:
            self.on_evento({"ev": "raciocinio", "texto": str(texto)})

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
                pid = su.get("step_id") or su.get("tool_call_id") or f"ag:{desc}"
                if state == "ACTIVE":
                    self._status(desc)
                    self._passo(pid, su.get("tool_name", "ferramenta"), tinfo.get("parameters", {}),
                                texto=desc, estado="rodando")
                elif state == "DONE":
                    self._status(desc, acao=True)
                    self._passo(pid, su.get("tool_name", "ferramenta"), tinfo.get("parameters", {}),
                                texto=desc, estado="ok")
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

    def tarefas_pendentes(self, tipo=None):
        """Descrições do que ainda roda em segundo plano (opcionalmente só de um tipo)."""
        return [x.get("descricao") or "" for x in self.tarefas.values()
                if tipo is None or x.get("tipo") == tipo]

    def _contar_repeticao(self, nome, entrada):
        try:
            chave = (nome, json.dumps(entrada, sort_keys=True, default=str))
        except (TypeError, ValueError):
            chave = (nome, str(entrada))
        self.repeticoes = self.repeticoes + 1 if chave == self._ultima_acao else 1
        self._ultima_acao = chave

    def _status_espera(self):
        """Depois da resposta: diz o que ainda está rodando, para não parecer travado."""
        agentes = self.tarefas_pendentes("local_agent")
        outras = [d for d in self.tarefas_pendentes() if d not in agentes]
        if agentes:
            self.on_status(f"{_t('Subagente trabalhando em segundo plano:')} {_curto(agentes[0], 60)}")
        elif outras:
            self.on_status(f"{_t('Aguardando em segundo plano:')} {_curto(outras[0], 60)}")

    def _claude_tarefa(self, sub, data):
        tid = data.get("task_id")
        if sub == "background_tasks_changed":
            self.tarefas = {
                x.get("task_id"): {"tipo": x.get("task_type"), "descricao": x.get("description") or ""}
                for x in data.get("tasks") or [] if isinstance(x, dict) and x.get("task_id")}
            self.on_meta({"tarefas": len(self.tarefas)})
            if self.fim_rodada:
                self._status_espera()
        elif sub == "task_started":
            desc = _curto(data.get("description"), 60)
            agente = data.get("task_type") == "local_agent"
            if agente:
                self._status(f"{_t('Subagente:')} {desc}", acao=True)
            elif data.get("is_backgrounded"):
                self._status(f"{_t('Em segundo plano:')} {desc}", acao=True)
            # o passo é o da ferramenta que lançou a tarefa (Agent, Bash em segundo plano…)
            pid = str(data.get("tool_use_id") or tid or "")
            if pid and (agente or data.get("is_backgrounded")):
                if tid:
                    self._tarefa_passo[tid] = pid
                if data.get("is_backgrounded"):
                    self._fundo.add(pid)
                novo = pid not in self._tipos
                if agente:
                    self._tipos[pid] = "subagente"
                else:
                    self._tipos.setdefault(pid, "comando")
                pai = self._tarefa_passo.get(data.get("parent_task_id"))
                self._passo(pid, tipo=self._tipos[pid], estado="rodando",
                            fundo=True if data.get("is_backgrounded") else None,
                            texto=(f"{_t('Subagente:')} {desc}" if agente else
                                   f"{_t('Em segundo plano:')} {desc}" if novo else None),
                            pai=pai if novo else None)
        elif sub == "task_progress":
            u = data.get("usage") or {}
            pid = self._tarefa_passo.get(tid) or data.get("tool_use_id")
            if pid:
                self._passo(pid, acoes=u.get("tool_uses"), tokens=u.get("total_tokens"),
                            detalhe=_curto(data.get("description"), 70) or None)
            if tid and u.get("total_tokens") is not None:
                self.uso_tarefas[tid] = int(u.get("total_tokens") or 0)
                self.on_meta({"uso_tarefas": sum(self.uso_tarefas.values())})
            partes = [f"{_t('Subagente:')} {_curto(data.get('description'), 55)}"]
            if u.get("tool_uses"):
                partes.append(f"{u['tool_uses']} {_t('ações')}")
            if u.get("total_tokens"):
                partes.append(f"{int(u['total_tokens']) / 1000:.0f}k tokens")
            self.on_status(" · ".join(partes))
        elif sub == "task_notification":
            resumo = _curto(data.get("summary") or data.get("status"), 70)
            self._status(f"{_t('Segundo plano:')} {resumo}", acao=True)
            pid = self._tarefa_passo.get(tid) or data.get("tool_use_id")
            if pid:
                self._fundo.discard(str(pid))
                ok = str(data.get("status") or "completed") == "completed"
                self._passo(pid, estado="ok" if ok else "erro", nota=None if ok else resumo)

    def _claude(self, t, data):
        # Só a atividade do agente principal abre uma rodada nova; o que os subagentes
        # fazem em segundo plano não muda o fato de a resposta já ter sido dada.
        if ((t in ("stream_event", "assistant", "user") and not data.get("parent_tool_use_id"))
                or (t == "system" and data.get("subtype") in ("init", "status"))):
            self.fim_rodada = False
        if t == "system":
            sub = data.get("subtype")
            if sub == "init":
                self._meta(modelo=data.get("model"))
            elif sub == "status":
                # O que a CLI está fazendo antes de vir texto: sem isto, a espera (grande
                # logo depois de trocar de modelo: a conversa inteira é relida) parece travamento.
                st = str(data.get("status") or "")
                if st == "requesting":
                    self.on_status(_t("Enviando o pedido ao modelo…"))
                elif "compact" in st:
                    self.on_status(_t("Resumindo a conversa para caber no modelo (pode levar alguns minutos)…"))
                elif st:
                    self.on_status(_curto(st, 70))
            elif isinstance(sub, str) and (sub.startswith("task_") or sub == "background_tasks_changed"):
                self._claude_tarefa(sub, data)
            return
        if t == "rate_limit_event":
            info = data.get("rate_limit_info") or {}
            janelas, voltas = {}, {}
            for nome, w in (info.get("unifiedWindows") or {}).items():
                if isinstance(w, dict) and w.get("utilization") is not None:
                    rotulo = {"five_hour": "5h", "seven_day": "7d"}.get(nome, nome)
                    janelas[rotulo] = float(w["utilization"])
                    if isinstance(w.get("resetsAt"), (int, float)):
                        voltas[rotulo] = int(w["resetsAt"])  # quando a janela zera (epoch)
            if janelas:
                self._meta(janelas=janelas, voltas=voltas or None)
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
                    desc = descrever_ferramenta(bloco.get("name", ""), {})
                    self._status(desc)
                    self._passo(bloco.get("id"), bloco.get("name", ""), {}, texto=desc, estado="rodando")
                elif bloco.get("type") == "thinking":
                    self.on_status(_t("✦ Pensando..."))
                    if bloco.get("thinking"):
                        self._pensou_parcial = True
                        self._raciocinio(bloco["thinking"])
            elif et == "content_block_delta":
                delta = ev.get("delta") or {}
                if delta.get("type") == "text_delta" and delta.get("text"):
                    self._parcial = True
                    self._texto(delta["text"], separar=self._bloco_novo)
                    self._bloco_novo = False
                elif delta.get("type") == "thinking_delta" and delta.get("thinking"):
                    self._pensou_parcial = True
                    self._raciocinio(delta["thinking"])
            elif et == "content_block_stop" and self._pensou_parcial:
                self._raciocinio("\n\n")   # separa um bloco de raciocínio do seguinte
                self._pensou_parcial = None  # None: já chegou por deltas nesta mensagem
            return
        if t == "assistant":
            if data.get("parent_tool_use_id"):
                # Subagente: o texto dele fica fora da resposta, mas o que ele está
                # fazendo aparece na atividade (senão o chat parece parado).
                for c in (data.get("message") or {}).get("content") or []:
                    if isinstance(c, dict) and c.get("type") == "tool_use":
                        desc = descrever_ferramenta(c.get("name", ""), c.get("input"))
                        self._status("↳ " + desc, acao=True)
                        self._passo(c.get("id"), c.get("name", ""), c.get("input"), texto=desc,
                                    estado="rodando", pai=str(data["parent_tool_use_id"]))
                return
            msg = data.get("message") or {}
            self._meta(modelo=msg.get("model"))
            for c in msg.get("content") or []:
                if not isinstance(c, dict):
                    continue
                if c.get("type") == "text" and not self._parcial:
                    self._texto(c.get("text", ""), separar=True)
                elif c.get("type") == "tool_use":
                    self._contar_repeticao(c.get("name", ""), c.get("input"))
                    desc = descrever_ferramenta(c.get("name", ""), c.get("input"))
                    self._status(desc, acao=True)
                    self._passo(c.get("id"), c.get("name", ""), c.get("input"), texto=desc, estado="rodando")
                elif c.get("type") == "thinking" and c.get("thinking") and self._pensou_parcial is False:
                    self._raciocinio(c["thinking"] + "\n\n")  # sem mensagens parciais
            if self._pensou_parcial is None:
                self._pensou_parcial = False
            if msg.get("error") or data.get("error"):
                self._erro(msg.get("error") or data.get("error"))
            return
        if t == "user":
            # Resultados das ferramentas: a saída não entra na conversa (nem na detecção
            # de limite); vai só para o cartão do passo.
            conteudo = (data.get("message") or {}).get("content")
            for c in conteudo if isinstance(conteudo, list) else []:
                if isinstance(c, dict) and c.get("type") == "tool_result":
                    self._resultado(c.get("tool_use_id"), _texto_resultado(c.get("content")),
                                    erro=bool(c.get("is_error")))
            return
        if t == "result":
            self.last_response = data.get("result", "") or ""
            for neg in data.get("permission_denials") or []:
                if isinstance(neg, dict) and neg.get("tool_use_id"):
                    self._passo(neg["tool_use_id"], estado="negado")
            if data.get("is_error") or str(data.get("subtype", "")).startswith("error"):
                self._erro(self.last_response or data.get("subtype"))
            else:
                self._registrar("")
            u = data.get("usage") or {}
            entrada = sum(int(u.get(k) or 0) for k in
                          ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            # Um processo pode ter várias rodadas (uma a cada aviso de tarefa em segundo
            # plano): os tokens somam; o custo informado já é o total do processo.
            self.resultados += 1
            self._somar_uso(entrada, u.get("output_tokens", 0), substituir=self.resultados == 1)
            if data.get("total_cost_usd") is not None:
                self.uso["custo"] = max(float(data.get("total_cost_usd") or 0), self.uso.get("custo", 0.0))
                self.on_meta({"uso": self.uso})
            if not self.has_text and self.last_response and not self.erro:
                self._texto(self.last_response)
            self._done = True
            self.fim_rodada = True
            self.on_done(self.last_response)
            self._status_espera()

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
        iid = item.get("id")

        def passo(pid, nome, entrada):
            desc = descrever_ferramenta(nome, entrada)
            self._status(desc, acao=fim)
            if not fim:
                self._passo(pid, nome, entrada, texto=desc, estado="rodando")
            elif not pid:  # sem id não dá para casar início e fim: um passo só, já pronto
                self._passo(None, nome, entrada, texto=desc, estado="ok")
            else:
                self._passo(pid, nome, entrada, texto=desc)
            return pid

        if it == "agent_message":
            if fim:
                self._texto(item.get("text", ""), separar=True)
        elif it == "reasoning":
            self.on_status(_t("✦ Pensando..."))
            if fim and item.get("text"):
                self._raciocinio(str(item["text"]) + "\n\n")
        elif it == "command_execution":
            pid = passo(iid, "shell", {"command": item.get("command", "")})
            if fim and pid:
                falhou = item.get("exit_code") not in (0, None) or item.get("status") == "failed"
                self._resultado(pid, item.get("aggregated_output"), erro=falhou,
                                negado=item.get("status") == "declined")
        elif it == "file_change":
            for i, ch in enumerate(item.get("changes") or []):
                pid = passo(f"{iid}:{i}" if iid else None, "edit", {"path": ch.get("path", ""), "kind": ch.get("kind")})
                if fim and pid:
                    self._resultado(pid, erro=item.get("status") == "failed")
        elif it == "web_search":
            pid = passo(iid, "web_search", {"query": item.get("query", "")})
            if fim and pid:
                self._resultado(pid)
        elif it == "mcp_tool_call":
            nome = f"{item.get('server', '')}.{item.get('tool', '')}".strip(".")
            pid = passo(iid, nome, item.get("arguments"))
            if fim and pid:
                self._resultado(pid, erro=item.get("status") == "failed")
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
            desc = descrever_ferramenta(nome, entrada)
            self._status(desc, acao=True)
            situacao = state.get("status")
            pid = self._passo(part.get("callID") or part.get("id"), nome, entrada, texto=desc,
                              estado=None if situacao in ("completed", "error") else "rodando")
            if situacao == "error":
                self._resultado(pid, state.get("error"), erro=True)
            elif situacao == "completed" or situacao is None:
                saida = state.get("output")
                self._resultado(pid, saida if isinstance(saida, str) else "")
            if state.get("status") == "error" and state.get("error"):
                self.on_status(f"⚠ {_curto(state['error'], 70)}")
        elif t == "reasoning":
            if part.get("text"):
                self.on_status(_t("✦ Pensando..."))
                self._raciocinio(str(part["text"]) + "\n\n")
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
        m = re.match(r"^(Running command|Reading file|Editing file|Searching)\s*:?\s*(.*)", clean, re.I)
        if m:
            self._status(f"{_curto(clean, 60)}")
            nome = {"running command": "shell", "reading file": "read", "editing file": "edit",
                    "searching": "search"}[m.group(1).lower()]
            entrada = {"command": m.group(2)} if nome == "shell" else {"path": m.group(2)}
            self._passo(None, nome, entrada if m.group(2) else {}, texto=_curto(clean, 60))
            return
        if re.search(r"(?:Antigravity CLI|ctrl\+o to expand|\bcommands? \(\+\d+)", clean, re.I):
            self.on_status(_t("Executando ações..."))
            return
        self._texto(clean + "\n")
