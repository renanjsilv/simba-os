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
SIMBA_CONHECE = {"pi", "omp", "opencode", "claude", "codex", "grok", "agy", "openclaw", "hermes", "copilot",
                 "crush", "cursor-agent", "muse"}

AGENTES = {
    "agy":      {"nome": "Antigravity", "modelo": "Google AI Pro",
                 "cmd": ["agy", "--dangerously-skip-permissions"],
                 "prompt": ["-p", "{p}", "--output-format", "stream-json"],
                 "continue": ["--continue", "-p", "{p}", "--output-format", "stream-json"],
                 "login": ["agy"], "conta": [], "verifica": ["agy", "models"], "env": "GEMINI_API_KEY"},
    "claude":   {"nome": "Claude Code", "modelo": "Claude 3.5 Sonnet",
                 "cmd": ["claude", "--permission-mode", "auto"],
                 "prompt": ["-p", "{p}", "--output-format", "stream-json", "--verbose"],
                 "continue": ["--continue", "-p", "{p}", "--output-format", "stream-json", "--verbose"],
                 "login": ["claude", "auth", "login"], "conta": [".claude/.credentials.json"]},
    "codex":    {"nome": "Codex", "modelo": "OpenAI o3-mini",
                 "cmd": ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "--skip-git-repo-check"],
                 "prompt": ["{p}"], "continue": ["resume", "--last", "{p}"],
                 "login": ["codex", "login"], "conta": [".codex/auth.json"]},
    "opencode": {"nome": "OpenCode", "modelo": "Open Source",
                 "cmd": ["opencode", "run"],
                 "prompt": ["{p}"], "continue": ["-c", "{p}"],
                 "login": ["opencode", "auth", "login"], "conta": [".local/share/opencode/auth.json"]},
    "copilot":  {"nome": "GitHub Copilot", "modelo": "Copilot",
                 "cmd": ["copilot", "--allow-all"],
                 "prompt": ["-p", "{p}"], "continue": ["--continue", "-p", "{p}"],
                 "login": ["copilot"], "conta": [".copilot/config.json"]},
    "cursor-agent": {"nome": "Cursor", "modelo": "Cursor Agent",
                     "cmd": ["cursor-agent", "--yolo", "--trust"],
                     "prompt": ["agent", "-p", "{p}"], "continue": ["agent", "-p", "{p}"],
                     "login": ["cursor-agent", "login"], "conta": [".cursor/cli-config.json"]},
    "grok":     {"nome": "Grok", "modelo": "xAI Grok",
                 "cmd": ["grok", "--permission-mode", "bypassPermissions"],
                 "prompt": ["--", "{p}"], "continue": ["--", "{p}"],
                 "login": ["grok"], "conta": []},
    "crush":    {"nome": "Crush", "modelo": "Charm AI",
                 "cmd": ["crush", "run"],
                 "prompt": ["{p}"], "continue": ["{p}"],
                 "login": ["crush"], "conta": []},
    "pi":       {"nome": "Pi", "modelo": "Pi AI",
                 "cmd": ["pi"],
                 "prompt": ["--", "{p}"], "continue": ["--", "{p}"],
                 "login": ["pi"], "conta": []},
}

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


def ler_config():
    instalados = [a for a in AGENTES if _achar(a)]
    padrao = {"ordem": list(instalados), "inativos": [a for a in instalados if conectado(a) is not True],
              "trocaAutomatica": True, "esperar": 8}
    try:
        c = json.loads(CONFIG.read_text())
    except (OSError, ValueError):
        c = {}
    padrao.update(c)
    for a in instalados:
        if a not in padrao["ordem"]:
            padrao["ordem"].append(a)
            if conectado(a) is not True and a not in padrao["inativos"]:
                padrao["inativos"].append(a)
    return padrao


def gravar_config(c):
    CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(c, ensure_ascii=False, indent=1))
    lista = [a for a in c["ordem"] if a not in c["inativos"] and a in SIMBA_CONHECE and _achar(a)]
    if lista:
        SIMBA_PADRAO.parent.mkdir(parents=True, exist_ok=True)
        SIMBA_PADRAO.write_text(lista[0] + "\n")


def conectado(a):
    info = AGENTES[a]
    if info.get("env") and os.environ.get(info["env"]):
        return True
    if info.get("verifica") and _achar(info["verifica"][0]):
        marca = ESTADO / f"login-{a}"
        try:
            quando, ok = marca.read_text().split()
            if time.time() - float(quando) < (600 if ok == "1" else 60):
                return ok == "1"
        except (OSError, ValueError):
            pass
        try:
            ok = subprocess.run(info["verifica"], cwd=HOME, stdin=subprocess.DEVNULL, capture_output=True,
                                timeout=20).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return None
        ESTADO.mkdir(parents=True, exist_ok=True)
        marca.write_text(f"{time.time()} {int(ok)}")
        return ok
    if not info["conta"]:
        return None
    return any((HOME / f).exists() and (HOME / f).stat().st_size > 2 for f in info["conta"])


def uso(a):
    try:
        d = json.loads((USO / f"{a}.json").read_text())
        out = {}
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


def candidatos(c, pular=()):
    return [a for a in c["ordem"] if a not in c["inativos"] and a not in pular
            and _achar(a) and conectado(a) is not False]


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


def passagem(agente, cwd, desde, tela, anterior=None):
    ESTADO.mkdir(parents=True, exist_ok=True)
    linhas = None
    try:
        if agente == "claude":
            linhas = transcricao_claude(cwd, desde)
        elif agente == "codex":
            linhas = transcricao_codex(cwd, desde)
    except Exception:  # noqa: BLE001
        linhas = None
    fonte = _t("transcrição da sessão")
    if not linhas:
        linhas = tela_limpa(tela)[-1500:]
        fonte = _t("texto que passou pelo terminal")
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
