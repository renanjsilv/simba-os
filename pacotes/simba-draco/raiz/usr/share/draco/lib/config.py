#!/usr/bin/env python3
"""Draco settings: which AI answers, which service transcribes, voice and timings.

Lives in ~/.config/draco: config.env (plain settings, KEY="value") and chaves/<provider>
(API keys, 0600). The settings window (Super+F10, ~/.config/quickshell/draco-config)
and the draco script both go through this file.

  config.py status             everything, as JSON (for the settings window)
  config.py pronto             exit 0 if an AI is configured (else 1)
  config.py env                shell exports for the draco script (eval "$(config.py env)")
  config.py set <CHAVE> <valor>
  config.py chave <provedor>   store the API key from $DRACO_CHAVE or stdin ("" removes it)
  config.py testar <provedor>  check that it works, as JSON {"ok": bool, "msg": "..."}
  config.py login              open a terminal to sign in to a Claude subscription
  config.py modelos <provedor> [--atualizar]
                               the models it offers right now, as JSON (cached 6 h)
  config.py modelo <provedor> <id>   choose one (saved per provider: MODELO_<PROVEDOR>)
"""
import json
import os
import shlex
import subprocess
import sys
import time

HOME = os.path.expanduser("~")
DIR = os.path.join(HOME, ".config", "draco")
ENV = os.path.join(DIR, "config.env")
KEYS = os.path.join(DIR, "chaves")
DATA = os.path.join(HOME, ".local", "share", "draco")
CODIGO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # /usr/share/draco
CLAUDE = os.path.join(HOME, ".local", "share", "mise", "installs", "claude", "latest", "claude")
CACHE = os.path.join(HOME, ".cache", "draco", "modelos")
PROXY_PORT = 47821  # lib/anthropic_proxy.py: OpenAI-only services behind Claude Code

# The brain is Claude Code; besides Anthropic itself it runs on any service with an
# Anthropic-compatible endpoint (ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN).
BRAINS = [
    {"id": "assinatura", "nome": "Assinatura Claude", "desc": "Pro ou Max: entra com a sua conta, sem chave",
     "login": True, "recomendado": True},
    {"id": "anthropic", "nome": "API da Anthropic", "desc": "Claude pago por uso",
     "url_chave": "https://console.anthropic.com/settings/keys"},
    {"id": "openrouter", "nome": "OpenRouter", "desc": "Claude e outros modelos com uma chave só",
     "base": "https://openrouter.ai/api", "url_chave": "https://openrouter.ai/settings/keys"},
    # OpenAI format only: Claude Code reaches it through lib/anthropic_proxy.py
    {"id": "nvidia", "nome": "NVIDIA", "desc": "Grátis: Kimi, GLM, DeepSeek e outros modelos abertos (até 40 pedidos/min)",
     "proxy": "https://integrate.api.nvidia.com/v1", "url_chave": "https://build.nvidia.com/settings/api-keys",
     "gratis": True},
    {"id": "zai", "nome": "Z.ai (GLM)", "desc": "GLM, plano de código barato",
     "base": "https://api.z.ai/api/anthropic", "url_chave": "https://z.ai/manage-apikey/apikey-list"},
    {"id": "deepseek", "nome": "DeepSeek", "desc": "DeepSeek, bem barato",
     "base": "https://api.deepseek.com/anthropic", "url_chave": "https://platform.deepseek.com/api_keys"},
    {"id": "kimi", "nome": "Moonshot (Kimi)", "desc": "Kimi K2",
     "base": "https://api.moonshot.ai/anthropic", "url_chave": "https://platform.moonshot.ai/console/api-keys"},
]
# Transcription: OpenAI-style /audio/transcriptions with verbose_json word timestamps
# (lib/transcript.py needs them to find "Draco"), or Whisper on this computer.
STTS = [
    {"id": "groq", "nome": "Groq", "desc": "Whisper large, rápido e grátis (recomendado)", "recomendado": True,
     "base": "https://api.groq.com/openai/v1", "modelo": "whisper-large-v3-turbo",
     "url_chave": "https://console.groq.com/keys"},
    {"id": "openai", "nome": "OpenAI", "desc": "Whisper da OpenAI, pago por uso",
     "base": "https://api.openai.com/v1", "modelo": "whisper-1",
     "url_chave": "https://platform.openai.com/api-keys"},
    {"id": "local", "nome": "Neste computador", "desc": "Sem internet nem chave, mas erra mais e é mais lento"},
]
# Model chosen per provider (MODELO_<ID>); empty = this default. Claude: measured on
# Draco's own requests, Opus ~2 s slower per request than Sonnet and Haiku no faster
# once a tool is involved, so Sonnet ("sonnet" = always the newest Sonnet).
DEFAULT_MODEL = {"assinatura": "sonnet", "anthropic": "sonnet", "nvidia": "moonshotai/kimi-k2.6",
                 "groq": "whisper-large-v3-turbo", "openai": "whisper-1"}
# Microsoft's neural voices (free, online; tts.py falls back to the local VOZ_LOCAL).
# Measured time to the first sound: Antonio/Francisca ~1.0 s, Thalita ~2.3 s; the
# "Multilingual" voices from other languages arrive slower than real time (stutter).
# Idioma da sessão (/usr/share/simba-apps/idiomas): o Draco ouve, pensa e fala nele. Cada idioma tem a
# sua voz guardada (VOZ/VOZ_LOCAL em português, VOZ_EN/VOZ_LOCAL_EN em inglês…).
sys.path.insert(0, "/usr/share/simba-apps/idiomas")
from simba_i18n import t as _t, n as _n, idioma as _idioma  # noqa: E402
_l = _idioma()
LING = "pt" if not _l or _l.startswith("pt") else _l.split("_")[0]
SUF = "" if LING == "pt" else "_" + LING.upper()
VOZ_KEY, VOZ_LOCAL_KEY = "VOZ" + SUF, "VOZ_LOCAL" + SUF
EDGE_POR_LINGUA = {
    "pt": [("pt-BR-AntonioNeural", "Antonio", _n("masculina")), ("pt-BR-FranciscaNeural", "Francisca", _n("feminina")),
           ("pt-BR-ThalitaMultilingualNeural", "Thalita", _n("feminina, a mais natural, ~1 s mais lenta para começar"))],
    "en": [("en-US-AndrewNeural", "Andrew", _n("masculina")), ("en-US-AvaNeural", "Ava", _n("feminina")),
           ("en-US-EmmaNeural", "Emma", _n("feminina"))],
}
EDGE_VOICES = EDGE_POR_LINGUA.get(LING, EDGE_POR_LINGUA["en"])
PIPER_PREFIXO = {"pt": "pt_BR-", "en": "en_US-"}.get(LING, LING + "_")
VOZ_PADRAO = {"pt": ("pt_BR-faber-medium", "pt_BR-faber-medium"), "en": ("edge:en-US-AndrewNeural", "en_US-ryan-medium")}
DEFAULTS = {"CEREBRO": "", "TRANSCRICAO": "local", "VOZ": "pt_BR-faber-medium", "VOZ_LOCAL": "pt_BR-faber-medium",
            "VOZ_EN": VOZ_PADRAO["en"][0], "VOZ_LOCAL_EN": VOZ_PADRAO["en"][1],
            "ESPERA": "5", "SILENCIO": "2", "MEMORIA": "10",
            "LIMIAR": "",  # wake word score needed; empty = the model's own (lower = more sensitive)
            **{f"MODELO_{p['id'].upper()}": "" for p in BRAINS + STTS if p["id"] != "local"}}
LIMITS = {"ESPERA": (2, 15), "SILENCIO": (0.8, 5), "MEMORIA": (0, 120), "LIMIAR": (0.5, 0.99)}


def provider(pid):
    return next((p for p in BRAINS + STTS if p["id"] == pid), None)


def migrate():
    """Before the settings existed: the Groq key was ~/.local/share/draco/groq.key and the
    brain was always the Claude subscription. Carry both over once. Later: one model for
    all (MODELO / CEREBRO_MODELO) became one per provider."""
    if os.path.exists(ENV):
        cfg = load(raw=True)
        old = {k: cfg[k] for k in ("MODELO", "CEREBRO_MODELO") if k in cfg}
        if old:
            changes = {}
            if old.get("MODELO") and old["MODELO"] != "sonnet":
                changes["MODELO_ASSINATURA"] = changes["MODELO_ANTHROPIC"] = old["MODELO"]
            if old.get("CEREBRO_MODELO") and cfg.get("CEREBRO"):
                changes[f"MODELO_{cfg['CEREBRO'].upper()}"] = old["CEREBRO_MODELO"]
            save(changes, drop=tuple(old))
        return
    changes = {}
    old = os.path.join(DATA, "groq.key")
    if os.path.exists(old) and not get_key("groq"):
        set_key("groq", open(old).read().strip())
    if get_key("groq"):
        changes["TRANSCRICAO"] = "groq"
    if claude_login()[0]:
        changes["CEREBRO"] = "assinatura"
    if changes:
        save(changes)


def load(raw=False):
    cfg = {} if raw else dict(DEFAULTS)
    try:
        with open(ENV) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    cfg[k.strip()] = " ".join(shlex.split(v)) if v.strip() else ""
    except OSError:
        pass
    return cfg


def save(changes, drop=()):
    cfg = load()
    cfg.update(changes)
    for k in drop:
        cfg.pop(k, None)
    os.makedirs(DIR, exist_ok=True)
    tmp = ENV + ".tmp"
    with open(tmp, "w") as f:
        f.write("# Draco: configurações (Super+F10 abre a tela; /usr/share/draco/lib/config.py)\n")
        for k, v in cfg.items():
            f.write(f"{k}={shlex.quote(str(v))}\n")
    os.replace(tmp, ENV)


def get_key(pid):
    try:
        with open(os.path.join(KEYS, pid)) as f:
            return f.read().strip()
    except OSError:
        return ""


def set_key(pid, value):
    os.makedirs(KEYS, mode=0o700, exist_ok=True)
    path = os.path.join(KEYS, pid)
    if not value:
        if os.path.exists(path):
            os.unlink(path)
        return
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(value.strip() + "\n")
    os.replace(path + ".tmp", path)


def claude_login():
    """(signed in to a claude.ai subscription?, detail)"""
    if not os.path.exists(CLAUDE):
        return False, "Claude Code não está instalado"
    try:
        out = subprocess.run([CLAUDE, "auth", "status"], capture_output=True, text=True, timeout=15).stdout
        st = json.loads(out)
    except (subprocess.SubprocessError, ValueError, OSError):
        return False, "não consegui ver o login"
    if st.get("loggedIn") and st.get("authMethod") == "claude.ai":
        return True, st.get("email") or "conectado"
    return False, "falta entrar na conta"


def brain_state(cfg, check_login=True):
    pid = cfg.get("CEREBRO", "")
    p = provider(pid)
    if not p or p not in BRAINS:
        return False, "nenhuma IA escolhida"
    if p.get("login"):
        return claude_login() if check_login else (True, "")
    return (True, "chave salva") if get_key(pid) else (False, "falta a chave")


def stt_state(cfg):
    pid = cfg.get("TRANSCRICAO", "local")
    if pid == "local":
        return True, "neste computador"
    return (True, "chave salva") if get_key(pid) else (False, "falta a chave")


def model_of(cfg, pid):
    return cfg.get(f"MODELO_{pid.upper()}") or DEFAULT_MODEL.get(pid, "")


def ensure_proxy():
    """Start lib/anthropic_proxy.py if it isn't listening (it exits by itself when idle)."""
    import socket
    with socket.socket() as s:
        s.settimeout(0.2)
        if s.connect_ex(("127.0.0.1", PROXY_PORT)) == 0:
            return
    subprocess.Popen(["setsid", "-f", sys.executable, os.path.join(CODIGO, "lib", "anthropic_proxy.py"),
                      "--porta", str(PROXY_PORT)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(40):
        time.sleep(0.05)
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", PROXY_PORT)) == 0:
                return


def brain_env(cfg, start_proxy=True):
    """Environment for running Claude Code on the chosen provider."""
    pid = cfg.get("CEREBRO", "")
    p = provider(pid) or {}
    env = {}
    model = model_of(cfg, pid)
    if pid == "anthropic":
        env["ANTHROPIC_API_KEY"] = get_key(pid)
    elif p.get("base"):
        env.update(ANTHROPIC_BASE_URL=p["base"], ANTHROPIC_AUTH_TOKEN=get_key(pid), ANTHROPIC_API_KEY="")
    elif p.get("proxy"):
        if start_proxy:
            ensure_proxy()
        env.update(ANTHROPIC_BASE_URL=f"http://127.0.0.1:{PROXY_PORT}/{pid}", ANTHROPIC_AUTH_TOKEN=get_key(pid),
                   ANTHROPIC_API_KEY="")
    if model:
        env["ANTHROPIC_MODEL"] = model
        if pid not in ("assinatura", "anthropic"):
            env["ANTHROPIC_SMALL_FAST_MODEL"] = model
    return env


def stt():
    """(base url, key, model) of the transcription service, or None for local Whisper."""
    cfg = load()
    p = provider(cfg.get("TRANSCRICAO", "local"))
    if not p or not p.get("base") or not get_key(p["id"]):
        return None
    return p["base"], get_key(p["id"]), model_of(cfg, p["id"]) or p["modelo"]


def number(cfg, k):
    try:
        v = float(cfg.get(k, DEFAULTS[k]))
    except ValueError:
        v = float(DEFAULTS[k])
    lo, hi = LIMITS[k]
    return min(max(v, lo), hi)


def voices():
    d = os.path.join(DATA, "voices")
    names = sorted(f[:-5] for f in os.listdir(d) if f.endswith(".onnx") and f.startswith(PIPER_PREFIXO)) if os.path.isdir(d) else []
    return ([{"id": "edge:" + v, "nome": n, "tipo": "natural", "desc": _t(desc)} for v, n, desc in EDGE_VOICES] +
            [{"id": n, "nome": n.split("-")[1].capitalize() if "-" in n else n, "tipo": "local", "desc": ""} for n in names])


def status():
    cfg = load()
    b_ok, b_msg = brain_state(cfg)
    s_ok, s_msg = stt_state(cfg)

    def card(p, kind):
        c = {k: v for k, v in p.items()}
        c["tipo"] = kind
        c["tem_chave"] = bool(get_key(p["id"]))
        c["precisa_chave"] = not p.get("login") and p["id"] != "local"
        c["modelo"] = model_of(cfg, p["id"])
        c["tem_modelos"] = p["id"] != "local"
        return c
    return {
        "pronto": b_ok,
        "cerebro": {"id": cfg["CEREBRO"], "ok": b_ok, "msg": b_msg},
        "transcricao": {"id": cfg["TRANSCRICAO"], "ok": s_ok, "msg": s_msg},
        "cerebros": [card(p, "cerebro") for p in BRAINS],
        "transcricoes": [card(p, "transcricao") for p in STTS],
        "voz": cfg.get(VOZ_KEY) or DEFAULTS.get(VOZ_KEY, ""), "vozes": voices(), "lingua": LING,
        "escuta": not os.path.exists(os.path.join(DATA, "wake.disabled")),
        "espera": number(cfg, "ESPERA"), "silencio": number(cfg, "SILENCIO"), "memoria": number(cfg, "MEMORIA"),
    }


def env():
    cfg = load()
    out = {"DRACO_PRONTO": "1" if brain_state(cfg, check_login=False)[0] else "",
           "DRACO_VOZ": cfg.get(VOZ_KEY) or DEFAULTS.get(VOZ_KEY, ""), "DRACO_LINGUA": LING, "DRACO_MEMORIA": str(int(number(cfg, "MEMORIA") * 60))}
    s = stt()
    out.update(DRACO_STT_URL=s[0], DRACO_STT_KEY=s[1], DRACO_STT_MODELO=s[2]) if s else \
        out.update(DRACO_STT_URL="", DRACO_STT_KEY="", DRACO_STT_MODELO="")
    out["DRACO_CLAUDE_ENV"] = " ".join(f"{k}={shlex.quote(v)}" for k, v in brain_env(cfg).items())
    out["DRACO_MODELO"] = model_of(cfg, cfg.get("CEREBRO", ""))
    for k, v in out.items():
        print(f"{k}={shlex.quote(v)}")


def http(url, headers, timeout=10, body=None):
    import urllib.error  # here: ~140 ms to import, and only the key test needs it
    import urllib.request
    req = urllib.request.Request(url, headers=headers, data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.read(300).decode(errors="ignore")
    except (urllib.error.URLError, OSError) as e:
        return 0, str(e)


# ---------------------------------------------------------------- available models

def http_json(url, headers, timeout=15):
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "draco/1.0", **headers}),
                                    timeout=timeout) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, None
    except (urllib.error.URLError, OSError, ValueError):
        return 0, None


CLAUDE_ALIASES = [
    {"id": "sonnet", "nome": "Sonnet (sempre o mais novo)", "tags": ["recomendado"]},
    {"id": "opus", "nome": "Opus (sempre o mais novo)", "tags": ["mais inteligente"]},
    {"id": "haiku", "nome": "Haiku (sempre o mais novo)", "tags": ["mais leve"]},
]
# Services with their own model list (with a key); without one, OpenRouter's public list
# of the same family is shown instead (names may differ a little: marked "aproximada").
OWN_LIST = {"zai": "https://api.z.ai/api/paas/v4/models", "deepseek": "https://api.deepseek.com/models",
            "kimi": "https://api.moonshot.ai/v1/models"}
OPENROUTER_PREFIX = {"zai": "z-ai/", "deepseek": "deepseek/", "kimi": "moonshotai/"}
# NVIDIA lists embeddings, safety filters, vision-only and base models too: not chat models.
NVIDIA_SKIP = ("embed", "rerank", "guard", "safety", "reward", "deplot", "fuyu", "kosmos", "neva", "vila", "nvclip",
               "parse", "retriever", "detector", "calibration", "translate", "codegemma", "starcoder", "codellama",
               "gemma-2b", "recurrentgemma", "llama2-70b", "mixtral-8x22b-v0.1", "-vision-", "phi-3-vision", "cosmos")
NVIDIA_GOOD = ("moonshotai/kimi", "z-ai/glm-5.3", "deepseek-ai/deepseek-v4", "nvidia/nemotron-3-super",
               "nvidia/nemotron-3-ultra", "mistralai/mistral-large-2")


def claude_list(headers):
    code, data = http_json("https://api.anthropic.com/v1/models?limit=100",
                           {"anthropic-version": "2023-06-01", **headers})
    if code != 200 or not data:
        return None
    return [{"id": m["id"], "nome": m.get("display_name") or m["id"], "tags": []} for m in data.get("data", [])]


def openrouter_all():
    code, data = http_json("https://openrouter.ai/api/v1/models", {})
    return data.get("data", []) if code == 200 and data else None


def fetch_models(pid):
    """(models, source, error) for one provider, live from its API."""
    key = get_key(pid)
    if pid == "assinatura":
        try:
            with open(os.path.join(HOME, ".claude", ".credentials.json")) as f:
                tok = json.load(f)["claudeAiOauth"]["accessToken"]
            full = claude_list({"Authorization": f"Bearer {tok}", "anthropic-beta": "oauth-2025-04-20"})
        except (OSError, KeyError, ValueError):
            full = None
        return CLAUDE_ALIASES + (full or []), "sua conta", None if full else "não consegui buscar a lista completa"
    if pid == "anthropic":
        full = claude_list({"x-api-key": key}) if key else None
        return CLAUDE_ALIASES + (full or []), "API da Anthropic", None if full else "salve a chave para ver a lista completa"
    if pid == "openrouter":
        data = openrouter_all()
        if data is None:
            return [], "", "não consegui falar com o OpenRouter"
        out = []
        sonnets = sorted(m["id"] for m in data if m["id"].startswith("anthropic/claude-sonnet") and ":" not in m["id"])
        for m in data:
            if "tools" not in (m.get("supported_parameters") or []) or m["id"].endswith(":batch"):
                continue  # Draco needs tool calling; batch variants are for offline jobs
            tags = []
            if sonnets and m["id"] == sonnets[-1]:
                tags.append("recomendado")
            if m["id"].endswith(":free") or str((m.get("pricing") or {}).get("prompt")) in ("0", "0.0"):
                tags.append("grátis")
            out.append({"id": m["id"], "nome": m.get("name") or m["id"], "tags": tags})
        out.sort(key=lambda m: ("recomendado" not in m["tags"], "grátis" not in m["tags"], m["nome"].lower()))
        return out, "OpenRouter (só os que usam ferramentas)", None
    if pid in OWN_LIST:
        if key:
            code, data = http_json(OWN_LIST[pid], {"Authorization": f"Bearer {key}"})
            if code == 200 and data:
                return [{"id": m["id"], "nome": m["id"], "tags": []} for m in data.get("data", [])], provider(pid)["nome"], None
        data = openrouter_all() or []
        pre = OPENROUTER_PREFIX[pid]
        out, seen = [], set()
        for m in data:
            mid = m["id"][len(pre):].split(":")[0] if m["id"].startswith(pre) else None
            if mid and mid not in seen:
                seen.add(mid)
                out.append({"id": mid, "nome": (m.get("name") or mid).split(":")[0], "tags": []})
        return out, "lista aproximada (OpenRouter)", None if key else "salve a chave para ver a lista exata"
    if pid == "nvidia":
        code, data = http_json("https://integrate.api.nvidia.com/v1/models", {})
        if code != 200 or not data:
            return [], "", "não consegui falar com a NVIDIA"
        out = []
        for m in data.get("data", []):
            mid = m["id"]
            if any(x in mid for x in NVIDIA_SKIP):
                continue
            out.append({"id": mid, "nome": mid.split("/", 1)[-1], "tags": ["recomendado"] if mid.startswith(NVIDIA_GOOD) else []})
        out.sort(key=lambda m: ("recomendado" not in m["tags"], m["nome"].lower()))
        return out, "NVIDIA (grátis)", None
    if pid in ("groq", "openai"):
        p = provider(pid)
        if key:
            code, data = http_json(p["base"] + "/models", {"Authorization": f"Bearer {key}"})
            if code == 200 and data:
                # word timestamps (to find "Draco") only come from the Whisper models
                ws = sorted((m["id"] for m in data.get("data", []) if m["id"].startswith("whisper")), reverse=True)
                return [{"id": w, "nome": w, "tags": ["recomendado"] if w == p["modelo"] else []} for w in ws], p["nome"], None
        return [{"id": p["modelo"], "nome": p["modelo"], "tags": ["recomendado"]}], p["nome"], \
            None if key else "salve a chave para ver a lista"
    return [], "", "esse provedor não tem modelos para escolher"


def models(pid, refresh=False):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{pid}.json")
    if not refresh:
        try:
            if time.time() - os.path.getmtime(path) < 6 * 3600:
                with open(path) as f:
                    res = json.load(f)
                res["atual"] = model_of(load(), pid)
                return res
        except (OSError, ValueError):
            pass
    lst, source, err = fetch_models(pid)
    res = {"modelos": lst, "fonte": source, "erro": err}
    if lst and not err:
        with open(path, "w") as f:
            json.dump(res, f, ensure_ascii=False)
    res["atual"] = model_of(load(), pid)
    return res


def test(pid):
    p = provider(pid)
    if not p:
        return {"ok": False, "msg": "provedor desconhecido"}
    if pid == "local":
        ok = subprocess.run(["sh", "-c", "command -v voxtype"], capture_output=True).returncode == 0
        return {"ok": ok, "msg": "pronto" if ok else "voxtype não está instalado"}
    if p.get("login"):
        ok, msg = claude_login()
        return {"ok": ok, "msg": f"conectado ({msg})" if ok else msg}
    key = get_key(pid)
    if not key:
        return {"ok": False, "msg": "falta a chave"}
    ua = {"User-Agent": "draco/1.0"}
    if p in STTS:
        code, body = http(p["base"] + "/models", {"Authorization": f"Bearer {key}", **ua})
    elif pid == "anthropic":
        code, body = http("https://api.anthropic.com/v1/models",
                          {"x-api-key": key, "anthropic-version": "2023-06-01", **ua})
    else:
        # A quick look first (a refused key makes Claude Code retry for a long time)...
        if p.get("proxy"):
            model = model_of(load(), pid)
            code, body = http(p["proxy"] + "/chat/completions",
                              {"Authorization": f"Bearer {key}", "content-type": "application/json", **ua}, timeout=30,
                              body={"model": model, "max_tokens": 1, "messages": [{"role": "user", "content": "oi"}]})
            if code in (404, 410):
                return {"ok": False, "msg": f"o modelo {model} não está disponível agora; escolha outro"}
        else:
            code, body = http(p["base"].rstrip("/") + "/v1/messages",
                          {"Authorization": f"Bearer {key}", "x-api-key": key, "anthropic-version": "2023-06-01",
                           "content-type": "application/json", **ua}, timeout=15,
                          body={"model": model_of(load(), pid) or "claude-sonnet-4-5", "max_tokens": 1,
                                "messages": [{"role": "user", "content": "oi"}]})
        if code in (401, 403):
            return {"ok": False, "msg": "chave recusada"}
        if code == 402:
            return {"ok": False, "msg": "conta sem crédito"}
        if code == 0:
            return {"ok": False, "msg": f"sem conexão com {p['nome']}"}
        # ...then the real thing: ask Claude Code a tiny question through this provider.
        if not os.path.exists(CLAUDE):
            return {"ok": False, "msg": "Claude Code não está instalado"}
        cfg = load()
        cfg["CEREBRO"] = pid
        run_env = {**os.environ, **brain_env(cfg)}
        try:
            r = subprocess.run([CLAUDE, "-p", "--tools", "", "--strict-mcp-config", "Responda apenas: ok"],
                               capture_output=True, text=True, timeout=60, env=run_env, cwd=DATA)
        except subprocess.TimeoutExpired:
            return {"ok": False, "msg": "não respondeu em 60 s"}
        out = (r.stdout + r.stderr).strip()
        return {"ok": r.returncode == 0 and bool(r.stdout.strip()),
                "msg": "funcionando" if r.returncode == 0 and r.stdout.strip() else (out[:160] or "falhou")}
    if code == 200:
        return {"ok": True, "msg": "chave válida"}
    if code in (401, 403):
        return {"ok": False, "msg": "chave recusada"}
    return {"ok": False, "msg": f"erro {code or 'de conexão'}: {body[:120]}"}


def restart_voice():
    subprocess.run(["pkill", "-f", "draco/tts.py serve"], capture_output=True)


def login():
    """Sign in to claude.ai: `claude auth login` opens the browser and finishes by itself
    when the browser calls back, so no terminal (its "paste the code" prompt is only a
    fallback and looked like the login was stuck). Blocks until it ends, so the settings
    window can verify right after. The window floats over the browser: hide it and
    maximize the browser during the login, then bring it back."""
    win, drwin = "^Draco: configurações$", os.path.join(CODIGO, "bin", "dr-win")
    sh = lambda *a: subprocess.run([drwin, *a], capture_output=True)
    braves = lambda: {c["address"] for c in json.loads(subprocess.run(
        ["hyprctl", "clients", "-j"], capture_output=True, text=True).stdout or "[]")
        if c.get("class") == "brave-browser"}
    # open the login in its own browser window (xdg-open shim), so closing it later
    # leaves the user's other tabs alone
    shim = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/tmp"), "draco-login-bin")
    os.makedirs(shim, exist_ok=True)
    with open(os.path.join(shim, "xdg-open"), "w") as f:
        f.write('#!/bin/sh\nexec brave --new-window "$@" >/dev/null 2>&1\n')
    os.chmod(os.path.join(shim, "xdg-open"), 0o755)
    env = {**os.environ, "PATH": shim + ":" + os.environ.get("PATH", ""),
           "BROWSER": os.path.join(shim, "xdg-open")}
    before = braves()
    subprocess.Popen(["notify-send", "-a", "Draco", "-i", "dialog-information", "Draco",
                      "Entre na sua conta Claude no navegador que abriu."])
    p = subprocess.Popen([CLAUDE, "auth", "login"], stdin=subprocess.DEVNULL, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    new = set()
    for _ in range(100):
        new = braves() - before
        if new or p.poll() is not None:
            break
        time.sleep(0.1)
    sh("hide", win)
    for a in new:
        subprocess.run(["hyprctl", "dispatch", f'hl.dsp.focus({{ window = "address:{a}" }})'],
                       capture_output=True)
        subprocess.run(["hyprctl", "dispatch", 'hl.dsp.window.fullscreen({ mode = "maximized" })'], capture_output=True)
    try:
        ok = p.wait(timeout=600) == 0
    except subprocess.TimeoutExpired:
        p.kill(); ok = False
    if not ok:
        subprocess.Popen(["notify-send", "-a", "Draco", "-u", "critical", "Draco",
                          "Não consegui entrar na conta Claude. Tente de novo."])
    if ok:
        time.sleep(1.5)  # let the "you're signed in" page show for a moment
        for a in new:
            subprocess.run(["hyprctl", "dispatch", f'hl.dsp.window.close({{ window = "address:{a}" }})'],
                           capture_output=True)
    sh("focus", win)


def main():
    migrate()
    args = sys.argv[1:]
    cmd = args[0] if args else "status"
    if cmd == "status":
        print(json.dumps(status(), ensure_ascii=False))
    elif cmd == "pronto":
        sys.exit(0 if brain_state(load(), check_login=False)[0] else 1)
    elif cmd == "env":
        env()
    elif cmd == "set":
        k, v = args[1], args[2] if len(args) > 2 else ""
        if k not in DEFAULTS:
            sys.exit(f"configuração desconhecida: {k}")
        if k == "VOZ":
            k = VOZ_KEY      # a voz escolhida vale para o idioma atual
        save({k: v, **({VOZ_LOCAL_KEY: v} if k == VOZ_KEY and not v.startswith("edge:") else {})})
        if k == VOZ_KEY:
            restart_voice()
    elif cmd == "chave":
        if not provider(args[1]):
            sys.exit("provedor desconhecido")
        # the key comes in $DRACO_CHAVE (settings window) or stdin, never on the command line
        set_key(args[1], os.environ["DRACO_CHAVE"] if "DRACO_CHAVE" in os.environ else sys.stdin.read())
        try:
            os.unlink(os.path.join(CACHE, f"{args[1]}.json"))  # a new key may see other models
        except OSError:
            pass
    elif cmd == "testar":
        print(json.dumps(test(args[1]), ensure_ascii=False))
    elif cmd == "login":
        login()
    elif cmd == "modelos":
        if not provider(args[1]):
            sys.exit("provedor desconhecido")
        print(json.dumps(models(args[1], "--atualizar" in args), ensure_ascii=False))
    elif cmd == "modelo":
        if not provider(args[1]) or args[1] == "local":
            sys.exit("provedor desconhecido")
        save({f"MODELO_{args[1].upper()}": args[2] if len(args) > 2 else ""})
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
