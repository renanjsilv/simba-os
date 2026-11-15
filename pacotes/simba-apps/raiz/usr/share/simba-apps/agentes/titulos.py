"""Títulos das conversas resumidos por IA (2 a 5 palavras), para a lista "Recentes".

O título cortado da primeira mensagem ("essa parte que está d…") não diz o assunto. Depois
da primeira resposta, uma chamada rápida resume o contexto ("Botão fechar do Explorador").

Privacidade: o resumo é feito pelo MESMO provedor que já teve a conversa (Claude → Claude
Haiku; OpenCode → o mesmo modelo do OpenCode). Só quando o agente da conversa não serve
para isso (Codex, Antigravity...) entra a chave da Groq que a pessoa cadastrou no Draco.
Uma conversa nunca vai para um provedor grátis que treina com os dados se não estava lá.
Sem nenhum caminho, fica o título antigo (começo da primeira mensagem).

Tudo aqui bloqueia (rodar numa thread). Medido: Groq ~0,5 s, OpenCode ~3 s, Claude ~3 s.
"""
import json
import os
import re
import subprocess
import urllib.request
from pathlib import Path

import motor as M

HOME = Path.home()
CWD = HOME / ".cache/simba/agentes/titulos"   # pasta neutra: as sessões não caem num projeto
GROQ_KEY = HOME / ".config/draco/chaves/groq"
GROQ_MODELO = "openai/gpt-oss-20b"
VERSAO = 1   # sobe quando o jeito de resumir mudar: os títulos antigos são refeitos

PROMPT = """Crie um título curto em português para esta conversa, de 2 a 5 palavras, que diga o assunto principal (como o título de uma conversa no ChatGPT). Sem aspas, sem ponto final, sem emojis. Responda só o título.
Exemplos de bons títulos: Botão fechar do Explorador · Transcrição local do Draco · Erro ao gerar a ISO · Ícone novo na barra

{contexto}"""


def contexto(mensagens):
    """O pedido inicial, o começo da resposta e o pedido seguinte, se houver."""
    partes, usuario, resposta = [], 0, False
    for m in mensagens:
        texto = " ".join(str(m.get("texto") or "").split())
        if not texto:
            continue
        if m.get("tipo") == "user" and usuario < 2:
            usuario += 1
            partes.append(f"Pedido: {texto[:1200 if usuario == 1 else 400]}")
        elif m.get("tipo") == "assistant" and not resposta:
            resposta = True
            partes.append(f"Resposta: {texto[:500]}")
        if usuario >= 2 and resposta:
            break
    return "\n\n".join(partes)


def agente_da_conversa(mensagens):
    """(agente, modelo) da primeira resposta."""
    for m in mensagens:
        if m.get("tipo") == "assistant" and m.get("agente"):
            return m["agente"], m.get("modelo") or ""
    return "", ""


def limpar(texto):
    """Uma linha, sem aspas/prefixos/ponto final; None se não parecer um título."""
    linhas = [x.strip() for x in str(texto or "").splitlines() if x.strip()]
    if not linhas:
        return None
    t = re.sub(r"^(t[íi]tulo|title)\s*:\s*", "", linhas[-1], flags=re.I)
    t = t.strip(" \t\"'“”‘’`*#_").rstrip(".").strip()
    if not t or len(t) > 70 or len(t.split()) > 9:
        return None
    return t[0].upper() + t[1:]


def _rodar(cmd, timeout=60):
    CWD.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(cmd, cwd=CWD, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
    return r.stdout if r.returncode == 0 else ""


def _claude(prompt):
    exe = M._achar("claude")
    if not exe:
        return None
    # sem ferramentas e sem gravar sessão: só o texto
    return limpar(_rodar([exe, "-p", "--model", "haiku", "--no-session-persistence", "--tools=", prompt]))


def _opencode(prompt, modelo):
    exe = M._achar("opencode")
    if not exe:
        return None
    if not modelo or (M.eh_gratis(modelo) and modelo not in M.modelos_gratis()):
        modelo = M.modelo_gratis() if M.usa_gratis("opencode") else modelo
    cmd = [exe, "run", "--format", "json", *(["-m", modelo] if modelo else []), prompt]
    texto = ""
    for linha in _rodar(cmd).splitlines():
        try:
            ev = json.loads(linha)
        except ValueError:
            continue
        if ev.get("type") == "text":
            texto += (ev.get("part") or {}).get("text", "")
    return limpar(texto)


def _groq(prompt):
    try:
        chave = GROQ_KEY.read_text().strip()
    except OSError:
        return None
    if not chave:
        return None
    corpo = json.dumps({"model": GROQ_MODELO, "messages": [{"role": "user", "content": prompt}],
                        "max_completion_tokens": 300, "temperature": 0.2, "reasoning_effort": "low"}).encode()
    pedido = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions", data=corpo, headers={
        "Authorization": f"Bearer {chave}", "Content-Type": "application/json", "User-Agent": "simba-agentes"})
    with urllib.request.urlopen(pedido, timeout=15) as r:
        d = json.load(r)
    return limpar(d["choices"][0]["message"]["content"])


def gerar(mensagens):
    """O título resumido, ou None (sem caminho disponível ou todos falharam)."""
    ctx = contexto(mensagens)
    if not ctx:
        return None
    prompt = PROMPT.format(contexto=ctx)
    agente, modelo = agente_da_conversa(mensagens)
    caminhos = []
    if agente == "claude":
        caminhos.append(lambda: _claude(prompt))
    elif agente == "opencode":
        caminhos.append(lambda: _opencode(prompt, modelo))
    caminhos.append(lambda: _groq(prompt))
    for c in caminhos:
        try:
            t = c()
        except Exception:  # noqa: BLE001 — rede, timeout, CLI sem login: tenta o próximo
            t = None
        if t:
            return t
    return None


def disponivel():
    """Há algum jeito de resumir nesta máquina?"""
    return bool(M._achar("claude") or M._achar("opencode") or (GROQ_KEY.exists() and GROQ_KEY.stat().st_size))


if __name__ == "__main__":  # teste: titulos.py <conversa.json>
    import sys
    dados = json.loads(Path(sys.argv[1]).read_text())
    print(gerar(dados.get("mensagens") or []))
