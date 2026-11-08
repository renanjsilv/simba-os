#!/usr/bin/env python3
"""Motor compartilhado para os Agentes de IA do Simba OS.

Gerencia os agentes instalados, configurações, checagem de limites e arquivo de passagem.
"""
from datetime import datetime, timezone
import glob
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, "/usr/share/simba-apps/idiomas")
from simba_i18n import t as _t  # noqa: E402

HOME = Path.home()
CONFIG = HOME / ".config/agentes/config.json"
ESTADO = HOME / ".local/state/agentes"
USO = HOME / ".local/state/simba/agents/usage"
SIMBA_PADRAO = HOME / ".config/simba/defaults/agent"
USO_ID = {"cursor-agent": "cursor"}  # nome do arquivo de uso quando difere do id
SIMBA_CONHECE = {"pi", "omp", "opencode", "claude", "codex", "grok", "agy", "openclaw", "hermes", "copilot",
                 "crush", "cursor-agent", "muse"}

# Campos de cada agente:
#   cmd         comando base (modo livre: o agente edita e executa sem perguntar)
#   cmdSeguro   comando base no modo somente leitura (sem ele, o agente fica de fora)
#   prompt      argumentos do primeiro pedido ({p} = pedido)
#   retomar     argumentos para continuar UMA sessão específica ({s} = id da sessão);
#               o id vem do próprio stream (session_id / sessionID / thread_id)
#   continue    reserva para quem não informa o id: continua a sessão mais recente
#   modelo      rótulo exibido quando nenhum modelo foi escolhido
AGENTES = {
    "agy":      {"nome": "Antigravity", "modelo": "Google",
                 "cmd": ["agy", "--dangerously-skip-permissions"],
                 "cmdSeguro": ["agy", "--mode", "plan"],
                 "prompt": ["-p", "{p}", "--output-format", "stream-json"],
                 "continue": ["--continue", "-p", "{p}", "--output-format", "stream-json"],
                 "login": ["agy"], "conta": [], "verifica": ["agy", "models"], "env": "GEMINI_API_KEY"},
    "claude":   {"nome": "Claude Code", "modelo": "Anthropic",
                 "cmd": ["claude", "--permission-mode", "auto"],
                 # modo print + "default": o que precisaria de aprovação é negado
                 "cmdSeguro": ["claude", "--permission-mode", "default"],
                 "prompt": ["-p", "{p}", "--output-format", "stream-json", "--verbose",
                            "--include-partial-messages"],
                 "retomar": ["--resume", "{s}", "-p", "{p}", "--output-format", "stream-json", "--verbose",
                             "--include-partial-messages"],
                 "continue": ["--continue", "-p", "{p}", "--output-format", "stream-json", "--verbose",
                              "--include-partial-messages"],
                 "login": ["claude", "auth", "login"], "conta": [".claude/.credentials.json"]},
    "codex":    {"nome": "Codex", "modelo": "OpenAI",
                 "cmd": ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "--skip-git-repo-check",
                         "--json"],
                 "cmdSeguro": ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check", "--json"],
                 "prompt": ["{p}"], "retomar": ["resume", "{s}", "{p}"], "continue": ["resume", "--last", "{p}"],
                 "login": ["codex", "login"], "conta": [".codex/auth.json"]},
    "opencode": {"nome": "OpenCode", "modelo": "Open Source",
                 # --format json evita que a transcrição da interface (spinners,
                 # leituras de arquivo, comandos) se misture à resposta no chat.
                 "cmd": ["opencode", "run", "--format", "json"],
                 # agente "plan" do OpenCode: não edita arquivos
                 "cmdSeguro": ["opencode", "run", "--format", "json", "--agent", "plan"],
                 "prompt": ["{p}"], "retomar": ["-s", "{s}", "{p}"], "continue": ["-c", "{p}"],
                 "login": ["opencode", "auth", "login"], "conta": [".local/share/opencode/auth.json"],
                 # OpenCode 2 guarda a conta no banco (opencode.db), não em auth.json; a lista
                 # de credenciais abaixo é a fonte oficial (auth.json fica só como reserva)
                 "verifica": ["opencode", "auth", "list", "--format", "json"], "verificaJson": "connections"},
    "copilot":  {"nome": "GitHub Copilot", "modelo": "GitHub",
                 "cmd": ["copilot", "--allow-all"],
                 # sem --allow-all, o modo -p nega as ferramentas que pediriam aprovação
                 "cmdSeguro": ["copilot"],
                 "prompt": ["-p", "{p}"], "continue": ["--continue", "-p", "{p}"],
                 "login": ["copilot"], "conta": [".copilot/config.json"]},
    "cursor-agent": {"nome": "Cursor", "modelo": "Cursor",
                     "cmd": ["cursor-agent", "--yolo", "--trust"],
                     # sem --force/--yolo, comandos não são executados no modo print
                     "cmdSeguro": ["cursor-agent", "--trust"],
                     "prompt": ["agent", "-p", "{p}"], "continue": ["agent", "-p", "{p}"],
                     "login": ["cursor-agent", "login"], "conta": [".cursor/cli-config.json"]},
    "grok":     {"nome": "Grok", "modelo": "xAI",
                 "cmd": ["grok", "--permission-mode", "bypassPermissions"],
                 "prompt": ["--", "{p}"], "continue": ["--", "{p}"],
                 "login": ["grok"], "conta": [".grok/auth.json"],
                 # `grok models` sempre sai com 0; o texto é que diz se entrou ("You are not authenticated.")
                 "verifica": ["grok", "models"], "verificaSaida": r"\byou are logged in\b",
                 "verificaSaidaNegada": r"\bnot (authenticated|logged in)\b|\bsign in\b"},
    "crush":    {"nome": "Crush", "modelo": "Charm",
                 "cmd": ["crush", "run"],
                 "prompt": ["{p}"], "continue": ["{p}"],
                 "login": ["crush"], "conta": []},
    "pi":       {"nome": "Pi", "modelo": "Pi",
                 "cmd": ["pi"],
                 "prompt": ["--", "{p}"], "continue": ["--", "{p}"],
                 "login": ["pi"], "conta": []},
}


def suporta_seguro(a):
    return bool(AGENTES.get(a, {}).get("cmdSeguro"))


def montar_comando(a, pedido, cfg, sessao=None, continuar=False, seguro=False):
    """Linha de comando completa de um pedido em modo print.

    Com `sessao`, retoma exatamente aquela sessão; `continuar` (sem id) só é usado
    por agentes que não informam o id da sessão.
    """
    info = AGENTES[a]
    base = info.get("cmdSeguro") if seguro else info["cmd"]
    cmd = aplicar_modelo(a, list(base), modelo_escolhido(a, cfg))
    if sessao and info.get("retomar"):
        modelo = info["retomar"]
    elif continuar and info.get("continue"):
        modelo = info["continue"]
    else:
        modelo = info.get("prompt")
    if modelo:
        cmd += [x.replace("{p}", pedido).replace("{s}", sessao or "") for x in modelo]
    elif pedido:
        cmd.append(pedido)
    return cmd


# ── modelos de cada agente ──────────────────────────────────────────────────
# Cada CLI escolhe o modelo de um jeito. Onde a CLI sabe listar, a lista é
# consultada uma vez e guardada em ~/.local/state/agentes/modelos.json (24 h).
# Assim a página de Configurações abre rápido e continua mostrando a última
# lista conhecida mesmo sem internet.
MODELO_FLAG = {
    "claude": ["--model", "{m}"],
    "codex": ["-m", "{m}"],
    "agy": ["--model", "{m}"],
    "opencode": ["--model", "{m}"],
    "copilot": ["--model", "{m}"],
    "cursor-agent": ["--model", "{m}"],
    "grok": ["-m", "{m}"],
    "crush": ["-m", "{m}"],
    "pi": ["--model", "{m}"],
}
# No modo interativo (TUI), estes CLIs aceitam a flag de modelo. OpenCode e
# Crush escolhem no próprio aplicativo; o chat gráfico usa o modo print deles.
MODELO_INTERATIVO = {"claude", "codex", "agy", "copilot", "cursor-agent", "grok", "pi"}
MODELO_COMANDO = {
    "agy": ["agy", "models"],
    "opencode": ["opencode", "models"],
    "grok": ["grok", "models"],
    "crush": ["crush", "models"],
    "cursor-agent": ["cursor-agent", "models"],
    "pi": ["pi", "--list-models"],
    "copilot": ["copilot", "help", "config"],
}
MODELOS_ESTATICOS = {
    "claude": ["fable", "opus", "sonnet", "haiku",
               "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5",
               "claude-opus-4-6", "claude-sonnet-4-6", "claude-opus-4-5",
               "claude-sonnet-4-5", "claude-haiku-4-5"],
    "codex": ["gpt-5.3-codex", "gpt-5.3-codex-spark", "gpt-5.4", "gpt-5.4-mini",
              "gpt-5.5", "gpt-5.5-pro", "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna",
              "gpt-6-astra", "gpt-6-luna", "gpt-6-sol", "gpt-6.1-sol", "gpt-6.1-terra"],
    "agy": ["gemini-3.8-flash-high", "gemini-3.8-flash-medium", "gemini-3.8-flash-low",
            "claude-sonnet-4-6", "claude-opus-4-6-thinking", "gpt-oss-120b-medium"],
    "opencode": ["opencode/claude-sonnet-5-5", "opencode/claude-opus-5-5",
                 "opencode/gpt-5.5", "opencode/gpt-5.3-codex", "opencode/gemini-3.1-pro",
                 "opencode/grok-4.7", "opencode/kimi-k3", "opencode/deepseek-v4.1-flash-free"],
    "copilot": ["auto", "claude-sonnet-5.5", "claude-opus-5.5", "claude-haiku-5.5",
                "gpt-6.1-sol", "gpt-6-luna", "gpt-5.3-codex", "gemini-4-argon",
                "grok-4.7", "kimi-k3"],
    "cursor-agent": ["auto", "gpt-5", "gpt-5.3-codex", "gpt-5.4", "gpt-5.5",
                     "claude-opus-4-8", "claude-opus-4-6", "claude-sonnet-4-6",
                     "gemini-3.1-pro", "gemini-3.8-flash", "grok-4.7"],
    "grok": ["grok-4.7"],
    "crush": [],
    "pi": ["anthropic/claude-sonnet-5-5", "anthropic/claude-opus-5-5",
           "openai/gpt-5.5", "openai/gpt-5.3-codex", "google/gemini-3.1-pro",
           "xai/grok-4.7"],
}
CACHE_MODELOS = ESTADO / "modelos.json"


def _opcao_modelo(valor, rotulo=""):
    valor = str(valor).strip()
    if not rotulo and "/" in valor:
        provedor, _, nome = valor.partition("/")
        return {"valor": valor, "rotulo": nome or valor, "detalhe": provedor}
    return {"valor": valor, "rotulo": rotulo or valor, "detalhe": ""}


def _unicos(opcoes):
    vistos, saida = set(), []
    for o in opcoes:
        valor = str((o or {}).get("valor", "")).strip()
        if not valor or valor in vistos:
            continue
        vistos.add(valor)
        if not o.get("rotulo"):
            o = _opcao_modelo(valor)
        saida.append(o)
    return saida


def _parsear_modelos(a, texto):
    """Transforma a saída textual de cada CLI em opções do seletor."""
    out = []
    if a == "copilot":
        dentro = False
        for linha in texto.splitlines():
            if re.match(r"\s*`model`\s*:", linha):
                dentro = True
                continue
            if dentro and re.match(r"\s*`[A-Za-z]", linha) and not linha.lstrip().startswith("-"):
                break
            if dentro:
                m = re.match(r'\s*-\s*"([^"]+)"', linha)
                if m:
                    out.append(_opcao_modelo(m.group(1)))
        return _unicos(out)
    if a == "agy":
        for linha in texto.splitlines():
            if "\t" not in linha:
                continue
            valor, _, rotulo = linha.partition("\t")
            valor, rotulo = valor.strip(), rotulo.strip()
            if not valor or valor.startswith(("Fetching", "Error", "You are")):
                continue
            out.append({"valor": valor, "rotulo": rotulo or valor, "detalhe": ""})
        return _unicos(out)
    if a in ("opencode", "crush"):
        for linha in texto.splitlines():
            valor = linha.strip()
            if "/" in valor and not valor.startswith(("Error", "Warning", "Use ", "See ")):
                out.append(_opcao_modelo(valor))
        return _unicos(out)
    if a == "grok":
        for linha in texto.splitlines():
            s = linha.strip()
            if s.startswith("*"):
                s = s[1:].strip()
            elif not s or s.startswith(("You are", "Default model", "Available models")):
                continue
            s = re.sub(r"\s*\(default\)\s*$", "", s, flags=re.I)
            m = re.match(r"([A-Za-z0-9][\w./:-]*)", s)
            if m and not m.group(1).lower().startswith(("error", "you", "http")):
                out.append(_opcao_modelo(m.group(1)))
        return _unicos(out)
    # Cursor e Pi imprimem tabelas/listas; o primeiro token de cada linha útil serve.
    for linha in texto.splitlines():
        s = linha.strip().lstrip("*-• ").strip()
        if not s or s.startswith(("Error", "Available", "Loading", "No models", "Use ", "See ", "Model")):
            continue
        m = re.match(r"([A-Za-z0-9][\w./:\-\[\]=,]*)", s)
        if m:
            out.append(_opcao_modelo(m.group(1)))
    return _unicos(out)


def _consultar_modelos(a):
    cmd = MODELO_COMANDO.get(a)
    if not cmd or not shutil.which(cmd[0]):
        return []
    try:
        r = subprocess.run(cmd, cwd=HOME, stdin=subprocess.DEVNULL, capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return []
    texto = (r.stdout or b"").decode("utf-8", "replace")
    if not texto.strip():
        texto = (r.stderr or b"").decode("utf-8", "replace")
    return _parsear_modelos(a, texto)


def _ler_cache_modelos():
    try:
        d = json.loads(CACHE_MODELOS.read_text())
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _gravar_cache_modelos(d):
    try:
        CACHE_MODELOS.parent.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_MODELOS.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, ensure_ascii=False))
        tmp.replace(CACHE_MODELOS)
    except OSError:
        pass


def modelos_estaticos(a):
    """Lista curta de reserva, para a página abrir na hora antes da consulta."""
    return _unicos([_opcao_modelo(v) for v in MODELOS_ESTATICOS.get(a, [])])


def modelos(a, atualizar=False):
    """Opções de modelo do agente (cache em disco; consulta a CLI só se pedido)."""
    cache = _ler_cache_modelos()
    item = cache.get(a) if isinstance(cache.get(a), dict) else None
    if item and item.get("opcoes"):
        ttl = 3600 if item.get("falhou") else 86400
        fresco = time.time() - float(item.get("quando", 0) or 0) < ttl
        if not atualizar or fresco:
            return item["opcoes"]
    if atualizar:
        lista = _consultar_modelos(a)
        if lista:
            cache[a] = {"quando": time.time(), "opcoes": lista}
            _gravar_cache_modelos(cache)
            return lista
        opcoes = item["opcoes"] if item and item.get("opcoes") else modelos_estaticos(a)
        cache[a] = {"quando": time.time(), "opcoes": opcoes, "falhou": True}
        _gravar_cache_modelos(cache)
        return opcoes
    return modelos_estaticos(a)


def modelos_todos(atualizar=True):
    return {a: modelos(a, atualizar=atualizar) for a in AGENTES}


def modelo_escolhido(a, cfg):
    mods = cfg.get("modelos") if isinstance(cfg, dict) else None
    if not isinstance(mods, dict):
        return ""
    valor = mods.get(a, "")
    return valor.strip() if isinstance(valor, str) else ""


def aplicar_modelo(a, cmd, modelo, interativo=False):
    """Acrescenta a flag de modelo ao comando, quando o CLI aceita."""
    if not modelo:
        return cmd
    if interativo and a not in MODELO_INTERATIVO:
        return cmd
    flag = MODELO_FLAG.get(a)
    if not flag:
        return cmd
    return list(cmd) + [x.replace("{m}", modelo) for x in flag]


INSTALAR = {
    "claude": {"mise": '"latest"', "sobre": "Anthropic · conta Claude ou chave de API"},
    "agy": {"script": "https://antigravity.google/cli/install.sh", "bin": HOME / ".local/bin/agy",
            "sobre": "Google · conta Google"},
    "codex": {"mise": '"latest"', "sobre": "OpenAI · conta ChatGPT"},
    "copilot": {"mise": '"latest"', "sobre": "GitHub · conta GitHub com Copilot"},
    "cursor-agent": {"mise": r"""{ version = "latest", bin_path = "bin", strip_components = 0, url = 'https://downloads.cursor.com/lab/{{ version }}/{{ os(macos="darwin") }}/{{ arch(x64="x64", arm64="arm64") }}/agent-cli-package.tar.gz', version_date_expr = 'map(versions, { [#, replace(#[:10], ".", "-")] })', version_list_url = "https://cursor.com/install", version_regex = 'downloads\.cursor\.com/lab/([0-9]{4}\.[0-9]{2}\.[0-9]{2}-[0-9a-f]+)/', postinstall = 'mkdir -p "$MISE_TOOL_INSTALL_PATH/bin" && ln -sfn ../dist-package/cursor-agent "$MISE_TOOL_INSTALL_PATH/bin/cursor-agent"' }""",
                     "sobre": "Cursor · conta Cursor"},
    "grok": {"mise": """{ version = "latest", bin = "grok", url = 'https://storage.googleapis.com/grok-build-public-artifacts/cli/grok-{{ version }}-{{ os() }}-{{ arch(x64="x86_64", arm64="aarch64") }}', version_list_url = "https://x.ai/cli/stable" }""",
             "sobre": "xAI · conta do Grok"},
    "opencode": {"mise": '{ version = "latest", allow_builds = ["@opencode/cli"] }', "sobre": "Código aberto · vários provedores"},
    "crush": {"mise": '"latest"', "sobre": "Charm · vários provedores"},
    "pi": {"mise": '"latest"', "sobre": "Código aberto · vários provedores"},
}
MISE_CONFIG = HOME / ".config/mise/config.toml"

FORTES = re.compile(r"(usage limit reached|you'?ve (hit|reached) your (usage |session |weekly )?limit|"
                    r"limit reached.{0,40}reset|out of (extra )?usage|quota exceeded|resource_exhausted|"
                    r"exhausted your (daily )?quota|insufficient_quota|credit balance is too low|"
                    r"limite de uso (atingido|alcançado)|você atingiu (o|seu) limite)", re.I)
LIMITE = re.compile(r"\b(limit|limits|quota|limite|cota|rate.?limit(ed)?)\b", re.I)
ACABOU = re.compile(r"(\breset|\bresets\b|\bupgrade\b|try again|exceeded|\breached\b|exhausted|esgot|atingid)", re.I)
PARCIAL = re.compile(r"(used|usou|utilizou)\s+\d{1,2}(\.\d+)?\s*%|approaching|perto do limite|\b\d{1,2}% (of|do|da)\b", re.I)
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(\x07|\x1b\\)|\x1b[()][0-9A-B]|\x1b[=>78]|\r")
ANSI_CSI = re.compile(r"\x1b\[([0-9;?]*)(\??[a-zA-Z])")
ANSI_OSC = re.compile(r"\x1b\][^\x07\x1b]*(\x07|\x1b\\)")
ANSI_OTHER = re.compile(r"\x1b[()][0-9A-B]|\x1b[=>78]")


class TerminalCleaner:
    """Interpreta códigos de controle de terminal (ANSI/VT100) para manter o texto limpo.

    Remove sequências de cores e cursor, interpreta retornos de carro (\\r),
    limpeza de linha (\\x1b[2K / \\x1b[K) e cursor up (\\x1b[1A) para que spinners
    e barras de progresso não poluam a saída de texto.
    """

    def __init__(self):
        self.linhas = []
        self.atual = ""

    def feed(self, texto):
        texto = texto.replace("\r\n", "\n")
        texto = ANSI_OSC.sub("", texto)
        texto = ANSI_OTHER.sub("", texto)
        i = 0
        n = len(texto)
        while i < n:
            if texto[i:i+2] == "\x1b[":
                m = ANSI_CSI.match(texto, i)
                if m:
                    args, cmd = m.group(1), m.group(2)
                    if cmd in ("K", "2K"):
                        self.atual = ""
                    elif cmd == "A":
                        count = int(args) if args.isdigit() else 1
                        for _ in range(count):
                            if self.linhas:
                                self.atual = self.linhas.pop()
                    elif cmd == "J" and args in ("2", "3"):
                        self.linhas.clear()
                        self.atual = ""
                    i = m.end()
                    continue
            ch = texto[i]
            if ch == "\r":
                self.atual = ""
            elif ch == "\n":
                self.linhas.append(self.atual)
                self.atual = ""
            else:
                self.atual += ch
            i += 1

    def get_text(self):
        res = self.linhas + ([self.atual] if self.atual else [])
        return "\n".join(res)


def _achar(a):
    """O comando do agente, mesmo antes de o PATH desta sessão ter os atalhos novos."""
    cmd = AGENTES[a]["cmd"][0]
    return shutil.which(cmd) or shutil.which(cmd, path=f"{HOME}/.local/share/mise/shims:{HOME}/.local/bin")


def ler_config(verificar=True):
    instalados = [a for a in AGENTES if _achar(a)]
    existe = CONFIG.exists()
    try:
        c = json.loads(CONFIG.read_text())
        if not isinstance(c, dict):
            c = {}
    except (OSError, ValueError):
        c = {}
    # Configuração já existente: a lista e os inativos são a fonte da verdade.
    # Não consulta o login de cada agente (subprocessos de até 20 s) toda vez
    # que a interface abre ou troca um modelo — era o que travava a janela.
    if not existe or not c:
        c["ordem"] = list(instalados)
        c["inativos"] = [a for a in instalados if verificar and conectado(a) is not True]
    else:
        c.setdefault("ordem", list(instalados))
        c.setdefault("inativos", [])
    c.setdefault("trocaAutomatica", True)
    c.setdefault("esperar", 8)
    c.setdefault("modelos", {})
    c.setdefault("seguro", False)
    # agentes instalados depois entram no fim da lista, desligados até você ligar
    for a in instalados:
        if a not in c["ordem"]:
            c["ordem"].append(a)
            if a not in c["inativos"]:
                c["inativos"].append(a)
    return c


def gravar_config(c):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(c, ensure_ascii=False, indent=1))
    lista = [a for a in c["ordem"] if a not in c["inativos"] and a in SIMBA_CONHECE and _achar(a)]
    if lista:
        SIMBA_PADRAO.parent.mkdir(parents=True, exist_ok=True)
        SIMBA_PADRAO.write_text(lista[0] + "\n")


def _verificar(a, info):
    """True/False para "conta conectada"; None quando não deu para concluir.

    Além do código de saída (padrão), aceita checar o texto (`verificaSaida`) ou um
    campo do JSON impresso (`verificaJson`), porque alguns CLIs saem com 0 mesmo
    quando não há login.
    """
    try:
        r = subprocess.run(info["verifica"], cwd=HOME, stdin=subprocess.DEVNULL, capture_output=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    saida = (r.stdout or b"").decode("utf-8", "replace")
    if info.get("verificaJson"):
        texto = saida.strip()
        corte = min([i for i in (texto.find("["), texto.find("{")) if i >= 0] or [-1])
        try:
            dados = json.loads(texto[corte:]) if corte >= 0 else None
        except ValueError:
            return None
        if isinstance(dados, list):
            return any(isinstance(x, dict) and bool(x.get(info["verificaJson"])) for x in dados)
        return bool(dados.get(info["verificaJson"])) if isinstance(dados, dict) else None
    if info.get("verificaSaida"):
        if re.search(info["verificaSaida"], saida, re.I):
            return True
        if info.get("verificaSaidaNegada") and re.search(info["verificaSaidaNegada"], saida, re.I):
            return False
        return None
    return r.returncode == 0


def conectado(a, verificar=True):
    info = AGENTES[a]
    if info.get("env") and os.environ.get(info["env"]):
        return True
    if info.get("verifica") and _achar(info["verifica"][0]):
        marca = ESTADO / f"login-{a}"
        try:
            quando, ok = marca.read_text().split()
            # Cache longo: evita rodar a CLI de login a cada abertura/troca de modelo.
            if time.time() - float(quando) < (86400 if ok == "1" else 300):
                return ok == "1"
        except (OSError, ValueError):
            pass
        if not verificar:
            # Caminho rápido da interface: não executa a CLI agora.
            if not info["conta"]:
                return None
            return any((HOME / f).exists() and (HOME / f).stat().st_size > 2 for f in info["conta"])
        ok = _verificar(a, info)
        if ok is not None:
            ESTADO.mkdir(parents=True, exist_ok=True)
            marca.write_text(f"{time.time()} {int(ok)}")
            return ok
    if not info["conta"]:
        return None
    return any((HOME / f).exists() and (HOME / f).stat().st_size > 2 for f in info["conta"])


def uso(a):
    """Fração usada (0–1) das janelas de limite, lida do widget de agentes do Simba.

    O widget grava `limits` [{label, percent, resetsAt}]; versões antigas usavam
    `windows` [{label, usedPercent, resetsAt}]. Os dois formatos são aceitos.
    """
    try:
        d = json.loads((USO / f"{USO_ID.get(a, a)}.json").read_text())
        out = {}
        for w in d.get("limits") or []:
            label, pct = str(w.get("label", "")).lower(), w.get("percent")
            if pct is None:
                continue
            chave = "sessao" if ("session" in label or "5-hour" in label or "5h" in label) else \
                    "semana" if ("week" in label or "7-day" in label or "7d" in label) else None
            if chave and chave not in out:
                out[chave] = float(pct)
                if w.get("resetsAt"):
                    out[f"{chave}Volta"] = w["resetsAt"]
        if out:
            return out
        for w in d.get("windows", []):
            label, pct = w.get("label", "").lower(), w.get("usedPercent")
            if pct is None:
                continue
            if "session" in label or "5h" in label or "30m" in label:
                out["sessao"] = pct
                if w.get("resetsAt"):
                    out["sessaoVolta"] = w["resetsAt"]
            elif "week" in label or "7d" in label:
                out["semana"] = pct
                if w.get("resetsAt"):
                    out["semanaVolta"] = w["resetsAt"]
        return out
    except (OSError, ValueError):
        return {}


def _futuro(iso):
    try:
        t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return iso if t > datetime.now(timezone.utc) else None
    except (AttributeError, ValueError):
        return None


def esgotado_ate(a):
    u = uso(a)
    for k in ("sessao", "semana"):
        if u.get(k, 0) >= 0.99 and u.get(f"{k}Volta"):
            fut = _futuro(u[f"{k}Volta"])
            if fut:
                return fut
    try:
        marcas = json.loads((ESTADO / "esgotados.json").read_text())
        return _futuro(marcas.get(a))
    except (OSError, ValueError):
        return None


def marcar_esgotado(a, ate_iso=None):
    if not ate_iso:
        volta = uso(a).get("sessaoVolta") or uso(a).get("semanaVolta")
        ate_iso = _futuro(volta) if volta else None
    if not ate_iso:
        t = datetime.now(timezone.utc).timestamp() + 5 * 3600
        ate_iso = datetime.fromtimestamp(t, tz=timezone.utc).isoformat()
    ESTADO.mkdir(parents=True, exist_ok=True)
    f = ESTADO / "esgotados.json"
    try:
        marcas = json.loads(f.read_text())
    except (OSError, ValueError):
        marcas = {}
    marcas[a] = ate_iso
    f.write_text(json.dumps(marcas))


def candidatos(c, pular=(), verificar=True, seguro=False):
    return [a for a in c["ordem"] if a in AGENTES and a not in c["inativos"] and a not in pular
            and _achar(a) and (not seguro or suporta_seguro(a))
            and (not verificar or conectado(a) is not False)]


def hora(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime("%d/%m %H:%M")
    except (AttributeError, ValueError):
        return "?"


def _corta(t, n):
    t = str(t)
    return t if len(t) <= n else t[:n] + " […]"


def transcricao_claude(cwd, desde):
    pasta = HOME / ".claude/projects" / re.sub(r"[/.]", "-", str(cwd))
    arqs = [p for p in pasta.glob("*.jsonl") if p.stat().st_mtime >= desde - 5]
    if not arqs:
        return None
    arq = max(arqs, key=lambda p: p.stat().st_mtime)
    linhas = []
    for l in arq.read_text(errors="replace").splitlines():
        try:
            e = json.loads(l)
        except ValueError:
            continue
        msg = e.get("message") or {}
        cont = msg.get("content")
        if e.get("type") == "user":
            if isinstance(cont, str):
                linhas.append(_t("**Usuário:** %1", cont))
            elif isinstance(cont, list):
                for b in cont:
                    if b.get("type") == "text":
                        linhas.append(_t("**Usuário:** %1", b.get('text', '')))
        elif e.get("type") == "assistant" and isinstance(cont, list):
            for b in cont:
                if b.get("type") == "text" and b.get("text", "").strip():
                    linhas.append(f"**Agente:** {b['text']}")
                elif b.get("type") == "tool_use":
                    inp = b.get("input") or {}
                    alvo = inp.get("command") or inp.get("file_path") or inp.get("path") or inp.get("pattern") or ""
                    linhas.append(f"- ferramenta `{b.get('name')}`: {_corta(alvo, 300)}")
    return linhas


def transcricao_codex(cwd, desde):
    arqs = [Path(p) for p in glob.glob(str(HOME / ".codex/sessions/**/rollout-*.jsonl"), recursive=True)]
    arqs = [p for p in arqs if p.stat().st_mtime >= desde - 5]
    if not arqs:
        return None
    arq = max(arqs, key=lambda p: p.stat().st_mtime)
    linhas = []
    for l in arq.read_text(errors="replace").splitlines():
        try:
            e = json.loads(l)
        except ValueError:
            continue
        p = e.get("payload") or {}
        if p.get("type") == "message":
            quem = _t("Usuário") if p.get("role") == "user" else _t("Agente")
            for b in p.get("content") or []:
                t = b.get("text", "")
                if t.strip() and not t.startswith("<environment_context>"):
                    linhas.append(f"**{quem}:** {t}")
        elif p.get("type") in ("function_call", "local_shell_call", "custom_tool_call"):
            linhas.append(f"- ferramenta `{p.get('name', p.get('type'))}`: {_corta(p.get('arguments') or p.get('input') or '', 300)}")
    return linhas


def transcricao_agy(cwd, desde):
    brain = HOME / ".gemini/antigravity-cli/brain"
    if not brain.exists():
        return None
    arqs = [p for p in brain.glob("*/.system_generated/logs/transcript.jsonl") if p.stat().st_mtime >= desde - 5]
    if not arqs:
        arqs = [p for p in brain.glob("*/transcript.jsonl") if p.stat().st_mtime >= desde - 5]
    if not arqs:
        return None
    arq = max(arqs, key=lambda p: p.stat().st_mtime)
    linhas = []
    for l in arq.read_text(errors="replace").splitlines():
        try:
            e = json.loads(l)
        except ValueError:
            continue
        tipo = e.get("type")
        if tipo == "USER_INPUT":
            cont = e.get("content", "")
            if isinstance(cont, str):
                m = re.search(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", cont, re.DOTALL)
                txt = m.group(1).strip() if m else cont.strip()
                if txt:
                    linhas.append(f"**Usuário:** {txt}")
        elif tipo == "PLANNER_RESPONSE":
            txt = (e.get("content") or "").strip()
            if txt:
                linhas.append(f"**Agente:** {txt}")
            for tc in e.get("tool_calls") or []:
                nome_ferr = tc.get("name", "ferramenta")
                args = tc.get("args") or {}
                cmd = args.get("CommandLine") or args.get("Path") or args.get("query") or ""
                linhas.append(f"- ferramenta `{nome_ferr}`: {_corta(str(cmd), 300)}")
    return linhas or None


def transcricao_opencode(cwd, desde):
    db_path = HOME / ".local/share/opencode/opencode.db"
    if not db_path.exists():
        return None
    try:
        import sqlite3
        with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
            cur = conn.cursor()
            limite_ms = int((desde - 5) * 1000)
            cur.execute(
                "SELECT id FROM session_v2 WHERE time_created >= ? OR time_updated >= ? ORDER BY time_updated DESC LIMIT 1",
                (limite_ms, limite_ms),
            )
            row = cur.fetchone()
            if not row:
                cur.execute("SELECT id FROM session_v2 ORDER BY time_updated DESC LIMIT 1")
                row = cur.fetchone()
            if not row:
                return None
            session_id = row[0]
            cur.execute(
                "SELECT type, data FROM session_message WHERE session_id = ? ORDER BY seq ASC",
                (session_id,),
            )
            linhas = []
            for m_type, m_data in cur.fetchall():
                try:
                    d = json.loads(m_data)
                except ValueError:
                    continue
                if m_type == "user":
                    txt = d.get("text", "").strip()
                    if txt:
                        linhas.append(f"**Usuário:** {txt}")
                elif m_type == "assistant":
                    conteudos = d.get("content") or []
                    if isinstance(conteudos, list):
                        for b in conteudos:
                            if not isinstance(b, dict):
                                continue
                            if b.get("type") == "text" and b.get("text", "").strip():
                                linhas.append(f"**Agente:** {b['text'].strip()}")
                            elif b.get("type") == "tool_use":
                                nome_ferr = b.get("name", "ferramenta")
                                inp = b.get("input") or {}
                                alvo = inp.get("command") or inp.get("path") or ""
                                linhas.append(f"- ferramenta `{nome_ferr}`: {_corta(str(alvo), 300)}")
            return linhas or None
    except Exception:
        return None


def tela_limpa(buf):
    if not isinstance(buf, str):
        buf = buf.decode("utf-8", "replace")
    tc = TerminalCleaner()
    tc.feed(buf)
    out, ant = [], None
    for l in tc.get_text().splitlines():
        l = l.rstrip()
        if l and l != ant:
            out.append(l)
        ant = l
    return out


def limpar_ansi(s):
    tc = TerminalCleaner()
    tc.feed(s)
    return tc.get_text()


def _limpar_avisos_de_limite(linhas):
    """Tira do contexto as mensagens de limite de uso.

    O arquivo de passagem é lido pelo próximo agente; se ele contiver o aviso
    "You've hit your weekly limit" do agente anterior, a detecção de limite
    dispara de novo e troca de agente sem necessidade.
    """
    if not linhas:
        return linhas
    def aviso(l):
        s = str(l)
        return bool(FORTES.search(s)) or (
            len(s.strip()) < 220 and LIMITE.search(s) and ACABOU.search(s)
            and not PARCIAL.search(s)
        )
    return [l for l in linhas if not aviso(l)]


def passagem(agente, cwd, desde, tela, anterior=None):
    ESTADO.mkdir(parents=True, exist_ok=True)
    linhas = None
    try:
        if agente == "claude":
            linhas = transcricao_claude(cwd, desde)
        elif agente == "codex":
            linhas = transcricao_codex(cwd, desde)
        elif agente == "agy":
            linhas = transcricao_agy(cwd, desde)
        elif agente == "opencode":
            linhas = transcricao_opencode(cwd, desde)
    except Exception:  # noqa: BLE001
        linhas = None
    fonte = _t("transcrição da sessão")
    if not linhas:
        linhas = tela_limpa(tela)[-1500:]
        fonte = _t("texto que passou pelo terminal")
    linhas = _limpar_avisos_de_limite(linhas)
    texto = "\n\n".join(linhas) if fonte.startswith("transcrição") else "```\n" + "\n".join(linhas) + "\n```"
    if len(texto) > 90000:
        texto = texto[:15000] + "\n\n[… parte do meio omitida …]\n\n" + texto[-70000:]
    git = ""
    if shutil.which("git"):
        r = subprocess.run(["git", "-C", str(cwd), "status", "--short"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            d = subprocess.run(["git", "-C", str(cwd), "diff", "--stat"], capture_output=True, text=True, timeout=10).stdout
            git = f"\n## Estado do Git em {cwd}\n\n```\n{r.stdout.strip() or '(sem mudanças)'}\n{d.strip()}\n```\n"
    ant = ""
    if anterior and Path(anterior).exists():
        ant = (f"\n## Passagem anterior\n\nEste trabalho já tinha passado por outro agente antes; o arquivo da passagem "
               f"anterior é `{anterior}` (leia se precisar do começo da história).\n")
    nome = AGENTES[agente]["nome"]
    arq = ESTADO / f"passagem-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    arq.write_text(f"""# Passagem de trabalho entre agentes

O {nome} estava fazendo este trabalho e **atingiu o limite de uso**. Você vai continuar.

- Pasta de trabalho: `{cwd}`
- Começou em: {datetime.fromtimestamp(desde).strftime('%d/%m/%Y %H:%M')}
- Fonte desta conversa: {fonte}

## Como continuar

1. Leia a conversa abaixo inteira: o primeiro pedido do usuário é a tarefa; as últimas
   mensagens mostram onde parou.
2. Confira no disco o que já foi feito (arquivos, comandos) antes de refazer qualquer coisa.
3. Continue exatamente de onde parou, no mesmo idioma do usuário, sem pedir para ele repetir.
{ant}
## Conversa até agora

{texto}
{git}""")
    return arq


def detectar_limite(texto):
    if FORTES.search(texto):
        return True
    return any(len(l.strip()) < 220 and LIMITE.search(l) and ACABOU.search(l) and not PARCIAL.search(l)
               for l in texto.splitlines())


def encerrar(pid):
    import signal
    for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(os.getpgid(pid), sig)
        except OSError:
            try:
                os.kill(pid, sig)
            except OSError:
                return
        for _ in range(20):
            p, _ = os.waitpid(pid, os.WNOHANG)
            if p:
                return
            time.sleep(0.1)
