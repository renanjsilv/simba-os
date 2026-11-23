"""Configuração do Simba Remoto (endereço, senha, recentes). Leve de propósito: a janela
importa isto para abrir na hora, sem esperar aiortc/av/numpy."""
import json
import os
import random
import socket
import sys
import time
from pathlib import Path

from .sinal import chave_senha

if sys.platform == "win32":
    CONFIG = Path(os.environ.get("APPDATA", Path.home())) / "Simba Remoto"
else:
    CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "simba-remoto"


def carregar_config():
    arq = CONFIG / "config.json"
    try:
        cfg = json.loads(arq.read_text())
    except (OSError, ValueError):
        cfg = {}
    if not cfg.get("codigo"):
        cfg["codigo"] = str(random.SystemRandom().randint(100_000_000, 999_999_999))
        CONFIG.mkdir(parents=True, exist_ok=True)
        arq.write_text(json.dumps(cfg, indent=2))
        if sys.platform != "win32":
            os.chmod(arq, 0o600)
    cfg.setdefault("nome", socket.gethostname())
    return cfg


def salvar_config(cfg):
    arq = CONFIG / "config.json"
    CONFIG.mkdir(parents=True, exist_ok=True)
    arq.write_text(json.dumps(cfg, indent=2))
    if sys.platform != "win32":
        os.chmod(arq, 0o600)


def novo_codigo():
    cfg = carregar_config()
    cfg["codigo"] = str(random.SystemRandom().randint(100_000_000, 999_999_999))
    # a chave da senha depende do código: trocar o endereço exige definir a senha de novo
    cfg.pop("senha_chave", None)
    cfg["autonomo"] = False
    salvar_config(cfg)
    return cfg["codigo"]


def definir_senha(senha):
    """senha vazia/None desliga o acesso não supervisionado."""
    cfg = carregar_config()
    if senha:
        cfg["senha_chave"] = chave_senha(senha, cfg["codigo"]).hex()
        cfg["autonomo"] = True
    else:
        cfg.pop("senha_chave", None)
        cfg["autonomo"] = False
    salvar_config(cfg)
    return cfg


def salvar_recente(codigo, nome=None):
    cfg = carregar_config()
    c = "".join(x for x in codigo if x.isdigit())
    if len(c) != 9:
        return
    recentes = cfg.get("recentes", [])
    recentes = [r for r in recentes if r.get("codigo") != c]
    recentes.insert(0, {"codigo": c, "nome": nome or c, "ts": int(time.time())})
    cfg["recentes"] = recentes[:10]
    salvar_config(cfg)


def remover_recente(codigo):
    cfg = carregar_config()
    c = "".join(x for x in codigo if x.isdigit())
    cfg["recentes"] = [r for r in cfg.get("recentes", []) if r.get("codigo") != c]
    senhas = cfg.get("senhas_salvas", {})
    senhas.pop(c, None)
    cfg["senhas_salvas"] = senhas
    salvar_config(cfg)


def obter_recentes():
    cfg = carregar_config()
    return cfg.get("recentes", [])


def salvar_senha_remota(codigo, chave_hex):
    cfg = carregar_config()
    c = "".join(x for x in codigo if x.isdigit())
    senhas = cfg.setdefault("senhas_salvas", {})
    senhas[c] = chave_hex
    salvar_config(cfg)


def obter_senha_remota(codigo):
    cfg = carregar_config()
    c = "".join(x for x in codigo if x.isdigit())
    return cfg.get("senhas_salvas", {}).get(c)


def remover_senha_remota(codigo):
    cfg = carregar_config()
    c = "".join(x for x in codigo if x.isdigit())
    senhas = cfg.get("senhas_salvas", {})
    if c in senhas:
        del senhas[c]
        cfg["senhas_salvas"] = senhas
        salvar_config(cfg)
