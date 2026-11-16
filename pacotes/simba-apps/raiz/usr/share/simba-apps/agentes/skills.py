"""Skills de agentes de IA (formato aberto SKILL.md) vindas do GitHub.

Uma skill é uma pasta com um SKILL.md (cabeçalho com name/description) e, às vezes, scripts e
arquivos de apoio. Elas são baixadas uma vez em ~/.local/share/agentes/skills/<nome> e ligadas
nas pastas que cada agente lê (Claude Code, Codex, OpenCode, Copilot, o padrão ~/.agents…).
"Atualizar" confere no GitHub se a pasta da skill mudou e baixa de novo (timer diário).

Uso pela linha de comando (saída JSON): simba-skills em-alta | repo <dono/repo> | buscar <texto>
| instalar <dono/repo> <caminho> | remover <nome> | instaladas | atualizar [--silencioso]
"""
import concurrent.futures
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HOME = Path.home()
BASE = HOME / ".local/share/agentes/skills"
REGISTRO = BASE / ".registro.json"
CACHE = HOME / ".cache/agentes/skills"
# pasta de cada agente: (onde ligar, pasta que indica que o agente existe; None = sempre)
DESTINOS = [
    (".agents/skills", None),                    # padrão aberto (OpenCode, Copilot e outros leem)
    (".claude/skills", ".claude"),               # Claude Code
    (".codex/skills", ".codex"),                 # Codex
    (".config/opencode/skills", ".config/opencode"),
    (".copilot/skills", ".copilot"),             # GitHub Copilot CLI
    (".pi/agent/skills", ".pi"),
    (".hermes/skills", ".hermes"),
]
# coleções mais conhecidas (aparecem sempre primeiro); o resto vem ao vivo do GitHub
DESTAQUES = [
    ("anthropics/skills", "Anthropic · oficial"),
    ("openai/skills", "OpenAI · oficial"),
    ("vercel-labs/agent-skills", "Vercel · oficial"),
    ("github/awesome-copilot", "GitHub · oficial"),
    ("huggingface/skills", "Hugging Face · oficial"),
    ("obra/superpowers", "Superpowers"),
]
LIMITE_ARQUIVOS = 300
LIMITE_BYTES = 30 * 1024 * 1024
VALIDADE_CACHE = 6 * 3600


class Erro(Exception):
    pass


# ── GitHub ───────────────────────────────────────────────────────────────────
_token = None


def _token_github():
    """Token do `gh` (se a pessoa entrou no GitHub): busca por código e limite maior."""
    global _token
    if _token is None:
        _token = os.environ.get("GITHUB_TOKEN", "")
        if not _token and shutil.which("gh"):
            try:
                r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
                _token = r.stdout.strip() if r.returncode == 0 else ""
            except (OSError, subprocess.SubprocessError):
                _token = ""
    return _token


def _get(url, bruto=False):
    req = urllib.request.Request(url, headers={"User-Agent": "simba-skills",
                                               "Accept": "application/vnd.github+json"})
    tok = _token_github()
    if tok and "api.github.com" in url:
        req.add_header("Authorization", "Bearer " + tok)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            dados = r.read()
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise Erro("O GitHub limitou as consultas por agora. Tente de novo em alguns minutos"
                       + ("" if tok else " (entrar no GitHub com `gh auth login` aumenta o limite)") + ".")
        if e.code == 404:
            raise Erro("Não encontrado no GitHub.")
        raise Erro(f"GitHub respondeu {e.code}.")
    except (urllib.error.URLError, TimeoutError, OSError):
        raise Erro("Sem conexão com o GitHub.")
    return dados if bruto else json.loads(dados)


def _api(caminho, **params):
    q = ("?" + urllib.parse.urlencode(params)) if params else ""
    return _get("https://api.github.com/" + caminho + q)


def _raw(repo, ref, caminho):
    return _get(f"https://raw.githubusercontent.com/{repo}/{ref}/{urllib.parse.quote(caminho)}", bruto=True)


def _cache(nome, func):
    CACHE.mkdir(parents=True, exist_ok=True)
    arq = CACHE / (re.sub(r"[^\w.-]", "_", nome) + ".json")
    try:
        if time.time() - arq.stat().st_mtime < VALIDADE_CACHE:
            return json.loads(arq.read_text())
    except (OSError, ValueError):
        pass
    v = func()
    arq.write_text(json.dumps(v, ensure_ascii=False))
    return v


def cabecalho(texto):
    """name/description do bloco --- … --- do SKILL.md."""
    out = {}
    m = re.match(r"﻿?---\s*\n(.*?)\n---", texto, re.S)
    if not m:
        return out
    chave = None
    for linha in m.group(1).splitlines():
        mm = re.match(r"^([A-Za-z_-]+):\s*(.*)$", linha)
        if mm:
            chave, valor = mm.group(1).lower(), mm.group(2).strip()
            out[chave] = valor.strip("'\"") if valor not in ("|", ">", "|-", ">-") else ""
        elif chave and linha.startswith((" ", "\t")):
            out[chave] = (out.get(chave, "") + " " + linha.strip()).strip()
    return out


def _arvore(repo):
    info = _api(f"repos/{repo}")
    ref = info.get("default_branch", "main")
    arv = _api(f"repos/{repo}/git/trees/{urllib.parse.quote(ref)}", recursive="1")
    return info, ref, arv.get("tree", [])


def skills_do_repo(repo):
    """Todas as skills (pastas com SKILL.md) de um repositório."""
    def montar():
        info, ref, arv = _arvore(repo)
        shas = {e["path"]: e["sha"] for e in arv if e.get("type") == "tree"}
        pastas = [e["path"][:-len("SKILL.md")].rstrip("/") for e in arv
                  if e.get("type") == "blob" and (e["path"] == "SKILL.md" or e["path"].endswith("/SKILL.md"))]
        pastas = [p for p in pastas if not re.search(r"(^|/)(\.|node_modules/|test|example)", p)][:80]

        def ler(p):
            try:
                cab = cabecalho(_raw(repo, ref, (p + "/" if p else "") + "SKILL.md").decode("utf-8", "replace"))
            except Erro:
                cab = {}
            return {"nome": cab.get("name") or (p.rsplit("/", 1)[-1] if p else repo.split("/")[1]),
                    "descricao": cab.get("description", "")[:400], "repo": repo, "caminho": p,
                    "ref": ref, "sha": shas.get(p, ""), "estrelas": info.get("stargazers_count", 0)}
        with concurrent.futures.ThreadPoolExecutor(8) as ex:
            return sorted(ex.map(ler, pastas), key=lambda s: s["nome"].lower())
    return _cache("repo-" + repo, montar)


def em_alta():
    """Coleções em destaque + as mais estreladas do tópico agent-skills (ao vivo, 6 h de cache)."""
    def montar():
        vistos, lista = set(), []
        for repo, rotulo in DESTAQUES:
            lista.append({"repo": repo, "rotulo": rotulo, "estrelas": 0, "descricao": "", "oficial": True})
            vistos.add(repo.lower())
        try:
            for topico in ("agent-skills", "claude-skills"):
                r = _api("search/repositories", q=f"topic:{topico}", sort="stars", per_page="15")
                for it in r.get("items", []):
                    if it["full_name"].lower() in vistos:
                        for d in lista:
                            if d["repo"].lower() == it["full_name"].lower():
                                d["estrelas"], d["descricao"] = it["stargazers_count"], it.get("description") or ""
                        continue
                    vistos.add(it["full_name"].lower())
                    lista.append({"repo": it["full_name"], "rotulo": "", "estrelas": it["stargazers_count"],
                                  "descricao": (it.get("description") or "")[:200], "oficial": False})
        except Erro:
            pass
        for d in lista:   # destaque fora do tópico pesquisado: estrelas e descrição direto do repositório
            if d["oficial"] and not d["estrelas"]:
                try:
                    it = _api(f"repos/{d['repo']}")
                    d["estrelas"], d["descricao"] = it.get("stargazers_count", 0), (it.get("description") or "")[:200]
                except Erro:
                    pass
        return lista
    return _cache("em-alta", montar)


def buscar(texto):
    """Busca skills no GitHub: por código (SKILL.md, precisa do login do gh) e por repositório."""
    texto = texto.strip()
    if not texto:
        return []
    achadas, vistos = [], set()
    # 1º as coleções conhecidas (oficiais): é onde estão as skills boas e mantidas
    termos = [t for t in re.split(r"\s+", texto.lower()) if t]
    def casa(sk):
        alvo = (sk["nome"] + " " + sk.get("descricao", "")).lower()
        return all(t in alvo for t in termos)
    def do_destaque(repo):
        try:
            return [sk for sk in skills_do_repo(repo) if casa(sk)]
        except Erro:
            return []
    with concurrent.futures.ThreadPoolExecutor(6) as ex:
        for lista in ex.map(do_destaque, [r for r, _ in DESTAQUES]):
            for sk in lista:
                k = (sk["repo"], sk["caminho"])
                if k not in vistos:
                    vistos.add(k)
                    sk["oficial"] = True
                    achadas.append(sk)
    oficiais = len(achadas)
    if _token_github():
        try:
            r = _api("search/code", q=f"{texto} filename:SKILL.md", per_page="30")
            itens = r.get("items", [])

            def ler(it):
                repo, p = it["repository"]["full_name"], it["path"][:-len("SKILL.md")].rstrip("/")
                ref = it["repository"].get("default_branch") or "HEAD"
                try:
                    cab = cabecalho(_raw(repo, "HEAD", it["path"]).decode("utf-8", "replace"))
                except Erro:
                    cab = {}
                return {"nome": cab.get("name") or p.rsplit("/", 1)[-1] or repo.split("/")[1],
                        "descricao": cab.get("description", "")[:400], "repo": repo, "caminho": p,
                        "ref": ref, "sha": "", "estrelas": 0}
            novas = []
            with concurrent.futures.ThreadPoolExecutor(8) as ex:
                for s in ex.map(ler, itens):
                    k = (s["repo"], s["caminho"])
                    if k not in vistos:
                        vistos.add(k)
                        novas.append(s)
            # o resto, das mais estreladas para as menos (a busca por código não ordena por qualidade)
            repos_u = sorted({s["repo"] for s in novas})[:20]
            def estrelas(r):
                try:
                    return r, _api(f"repos/{r}").get("stargazers_count", 0)
                except Erro:
                    return r, 0
            with concurrent.futures.ThreadPoolExecutor(8) as ex:
                est = dict(ex.map(estrelas, repos_u))
            for s in novas:
                s["estrelas"] = est.get(s["repo"], 0)
            novas.sort(key=lambda s: -s["estrelas"])
            achadas += novas
        except Erro:
            pass
    repos = []
    try:
        r = _api("search/repositories", q=f"{texto} skills in:name,description,topics", sort="stars", per_page="10")
        repos = [{"repo": it["full_name"], "estrelas": it["stargazers_count"],
                  "descricao": (it.get("description") or "")[:200]} for it in r.get("items", [])]
    except Erro:
        if not achadas:
            raise
    return {"skills": achadas, "repos": repos}


# ── instalação ───────────────────────────────────────────────────────────────
def _registro():
    try:
        return json.loads(REGISTRO.read_text())
    except (OSError, ValueError):
        return {}


def _gravar_registro(r):
    BASE.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRO.with_suffix(".tmp")
    tmp.write_text(json.dumps(r, ensure_ascii=False, indent=1))
    tmp.replace(REGISTRO)


def _nome_seguro(n):
    n = re.sub(r"[^\w.-]+", "-", n.strip().lower()).strip("-.")
    return n[:60] or "skill"


def ligar(nome):
    """Liga a skill nas pastas dos agentes instalados; não mexe em pasta de mesmo nome que não é nossa."""
    alvo = BASE / nome
    ligados = []
    for dest, existe in DESTINOS:
        if existe and not (HOME / existe).exists():
            continue
        d = HOME / dest
        d.mkdir(parents=True, exist_ok=True)
        link = d / nome
        if link.is_symlink():
            link.unlink()
        elif link.exists():
            continue
        link.symlink_to(alvo)
        ligados.append(dest)
    return ligados


def desligar(nome):
    alvo = (BASE / nome).resolve()
    for dest, _ in DESTINOS:
        link = HOME / dest / nome
        if link.is_symlink() and Path(os.path.realpath(link)) == alvo:
            link.unlink()


def instalar(repo, caminho, nome=None):
    info, ref, arv = _arvore(repo)
    pre = (caminho.strip("/") + "/") if caminho.strip("/") else ""
    arquivos = [e for e in arv if e.get("type") == "blob" and e["path"].startswith(pre)]
    if not any(e["path"] == pre + "SKILL.md" for e in arquivos):
        raise Erro("Essa pasta não tem SKILL.md: não é uma skill.")
    if len(arquivos) > LIMITE_ARQUIVOS or sum(e.get("size", 0) for e in arquivos) > LIMITE_BYTES:
        raise Erro("Skill grande demais para instalar por aqui.")
    sha = next((e["sha"] for e in arv if e.get("type") == "tree" and e["path"] == caminho.strip("/")), "")
    with tempfile.TemporaryDirectory(dir=str(BASE.parent) if BASE.parent.exists() else None) as tmp:
        t = Path(tmp)

        def baixar(e):
            rel = e["path"][len(pre):]
            if ".." in Path(rel).parts:
                return
            dst = t / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(_raw(repo, ref, e["path"]))
            if e.get("mode") == "100755":
                dst.chmod(0o755)
        with concurrent.futures.ThreadPoolExecutor(8) as ex:
            list(ex.map(baixar, arquivos))
        cab = cabecalho((t / "SKILL.md").read_text(encoding="utf-8", errors="replace"))
        nome = _nome_seguro(nome or cab.get("name") or caminho.rsplit("/", 1)[-1] or repo.split("/")[1])
        BASE.mkdir(parents=True, exist_ok=True)
        destino = BASE / nome
        if destino.exists():
            shutil.rmtree(destino)
        shutil.move(str(t), str(destino))
        destino.chmod(0o755)
    reg = _registro()
    reg[nome] = {"repo": repo, "caminho": caminho.strip("/"), "ref": ref, "sha": sha,
                 "descricao": cab.get("description", "")[:400],
                 "atualizada": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
    _gravar_registro(reg)
    return {"nome": nome, "agentes": ligar(nome)}


def remover(nome):
    desligar(nome)
    shutil.rmtree(BASE / nome, ignore_errors=True)
    reg = _registro()
    reg.pop(nome, None)
    _gravar_registro(reg)
    return {"nome": nome}


def instaladas():
    reg = _registro()
    out = []
    for nome, r in sorted(reg.items()):
        if not (BASE / nome / "SKILL.md").exists():
            continue
        agentes = [d for d, _ in DESTINOS if (HOME / d / nome).is_symlink()]
        out.append(dict(r, nome=nome, agentes=agentes))
    return out


def atualizar(silencioso=False):
    """Baixa de novo as skills cuja pasta mudou no GitHub; religa nos agentes instalados depois."""
    mudaram, erros = [], []
    for nome, r in list(_registro().items()):
        try:
            _info, _ref, arv = _arvore(r["repo"])
            sha = next((e["sha"] for e in arv if e.get("type") == "tree" and e["path"] == r["caminho"]), "")
            if r["caminho"] == "":
                sha = _api(f"repos/{r['repo']}/commits/{urllib.parse.quote(_ref)}").get("sha", "")
            if sha and sha != r.get("sha"):
                instalar(r["repo"], r["caminho"], nome)
                mudaram.append(nome)
            else:
                ligar(nome)   # agente instalado depois da skill também a recebe
        except Erro as e:
            erros.append(f"{nome}: {e}")
    estado = {"quando": time.time(), "mudaram": mudaram, "erros": erros}
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / "ultima-atualizacao.json").write_text(json.dumps(estado, ensure_ascii=False))
    if mudaram:
        try:
            subprocess.run(["notify-send", "-a", "Agentes de IA", "Skills atualizadas", ", ".join(mudaram)],
                           timeout=5)
        except (OSError, subprocess.SubprocessError):
            pass
    return estado


def principal(argv):
    try:
        if argv[:1] == ["em-alta"]:
            r = em_alta()
        elif argv[:1] == ["repo"] and len(argv) > 1:
            r = skills_do_repo(argv[1])
        elif argv[:1] == ["buscar"] and len(argv) > 1:
            r = buscar(" ".join(argv[1:]))
        elif argv[:1] == ["instalar"] and len(argv) > 2:
            r = instalar(argv[1], argv[2])
        elif argv[:1] == ["remover"] and len(argv) > 1:
            r = remover(argv[1])
        elif argv[:1] == ["instaladas"]:
            r = instaladas()
        elif argv[:1] == ["atualizar"]:
            r = atualizar("--silencioso" in argv)
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except Erro as e:
        print(json.dumps({"erro": str(e)}, ensure_ascii=False))
        return 1
    print(json.dumps(r, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1:]))
