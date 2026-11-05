"""Nuvens no Explorador (rclone): Google Drive, OneDrive, Dropbox, MEGA, Box, pCloud,
iCloud, Proton Drive, Nextcloud/WebDAV e servidores SFTP.

Cada conta vira um "remote" do rclone e é montada em ~/Nuvem/<nome> por um serviço
do usuário (explorador-nuvem@<nome>.service, rclone mount com cache), então aparece
como uma pasta comum — abre, copia, arrasta e funciona com qualquer app.
O login das nuvens com OAuth abre no navegador (o rclone recebe a resposta).
"""
import json
import os
import re
import subprocess
from pathlib import Path
import sys as _sys, os as _os  # noqa: E401
_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))
from simba_i18n import t as _t  # noqa: E402  (traduções: /usr/share/simba-apps/idiomas)

HOME = Path.home()
RAIZ = HOME / _t("Nuvem")
REGISTRO = HOME / ".config/explorador/nuvens.json"
UNIDADE = HOME / ".config/systemd/user/explorador-nuvem@.service"
ICONES = Path(__file__).resolve().parent / "icones"
# remotes usados pelo backup da conta (Configurações › Contas): não aparecem aqui
INTERNOS = {"conta-gdrive", "conta-cripto"}
OPCOES = HOME / ".config/explorador/nuvem"          # <remote>.env: opções do rclone mount
CONF_RCLONE = Path(os.environ.get("RCLONE_CONFIG") or HOME / ".config/rclone/rclone.conf")

# Provedores que avisam o rclone das mudanças (--poll-interval): a lista de pastas pode
# ficar em cache por muito tempo e ser pré-carregada. Nos outros, cache curto.
COM_AVISO = {"drive", "onedrive", "dropbox", "box", "pcloud", "mega", "jottacloud", "putio"}
BASE_MONTAGEM = ("--vfs-cache-mode full --vfs-cache-max-age 168h --vfs-cache-max-size 20G "
                 "--vfs-read-chunk-size 16M --vfs-read-chunk-size-limit 512M --buffer-size 32M "
                 "--vfs-read-ahead 128M --vfs-fast-fingerprint --attr-timeout 10s "
                 "--transfers 8 --checkers 16 --umask 022 --links")


def opcoes_montagem(tipo):
    o = BASE_MONTAGEM
    if tipo in COM_AVISO:
        o += " --dir-cache-time 1000h --poll-interval 1m --vfs-refresh"
    else:
        o += " --dir-cache-time 5m"
    if tipo == "onedrive":
        # o Cofre Pessoal (Personal Vault) não pode ser listado pela API: só gera erro a cada atualização
        o += " --exclude=/Cofre?Pessoal/** --exclude=/Personal?Vault/**"
    if tipo == "drive":
        # o ritmo padrão do rclone para o Google Drive é bem conservador
        o += " --drive-pacer-min-sleep 10ms --drive-pacer-burst 200 --drive-chunk-size 64M"
    return o

PROVEDORES = [
    {"id": "gdrive", "nome": _t("Google Drive"), "tipo": "drive", "oauth": True, "params": ["scope=drive"]},
    {"id": "onedrive", "nome": _t("OneDrive"), "tipo": "onedrive", "oauth": True, "params": []},
    {"id": "dropbox", "nome": _t("Dropbox"), "tipo": "dropbox", "oauth": True, "params": []},
    {"id": "box", "nome": _t("Box"), "tipo": "box", "oauth": True, "params": []},
    {"id": "pcloud", "nome": "pCloud", "tipo": "pcloud", "oauth": True, "params": []},
    {"id": "mega", "nome": "MEGA", "tipo": "mega", "oauth": False,
     "campos": [("user", _t("E-mail"), False), ("pass", _t("Senha"), True)]},
    {"id": "proton", "nome": _t("Proton Drive"), "tipo": "protondrive", "oauth": False,
     "campos": [("username", _t("E-mail ou usuário"), False), ("password", _t("Senha"), True), ("2fa", _t("Código 2FA (se usar)"), False)]},
    {"id": "icloud", "nome": _t("iCloud Drive"), "tipo": "iclouddrive", "oauth": False,
     "campos": [("apple_id", _t("Apple ID"), False), ("password", _t("Senha"), True)]},
    {"id": "nextcloud", "nome": _t("Nextcloud / WebDAV"), "tipo": "webdav", "oauth": False,
     "campos": [("url", _t("Endereço (https://…/remote.php/dav/files/USUÁRIO)"), False), ("user", _t("Usuário"), False),
                ("pass", _t("Senha ou senha de app"), True)]},
    {"id": "sftp", "nome": _t("Servidor SFTP/SSH"), "tipo": "sftp", "oauth": False,
     "campos": [("host", _t("Servidor"), False), ("user", _t("Usuário"), False), ("pass", _t("Senha (vazio = chave SSH)"), True),
                ("port", _t("Porta"), False)]},
]
POR_ID = {p["id"]: p for p in PROVEDORES}
POR_TIPO = {}
for _p in PROVEDORES:
    POR_TIPO.setdefault(_p["tipo"], _p)

SERVICO = """[Unit]
Description=Nuvem %i (Explorador de Arquivos)
After=network-online.target
Wants=network-online.target

[Service]
Type=notify
ExecStartPre=/usr/bin/mkdir -p %h/Nuvem/%i
EnvironmentFile=-%h/.config/explorador/nuvem/%i.env
ExecStart=/usr/bin/rclone mount %i: %h/Nuvem/%i $OPCOES --volname %i
ExecStop=/usr/bin/fusermount3 -uz %h/Nuvem/%i
Restart=on-failure
RestartSec=15

[Install]
WantedBy=default.target
"""


def icone(prov_id):
    f = ICONES / f"{prov_id}.svg"
    return str(f) if f.exists() else ""


def _rc(*args, entrada=None, timeout=60):
    return subprocess.run(["rclone", *args], capture_output=True, text=True, input=entrada, timeout=timeout)


def _registro():
    try:
        return json.loads(REGISTRO.read_text())
    except (OSError, ValueError):
        return {}


def _gravar_registro(r):
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    REGISTRO.write_text(json.dumps(r, ensure_ascii=False, indent=1))


def nome_seguro(nome):
    n = re.sub(r"[^A-Za-z0-9_-]+", "-", nome.strip()).strip("-")
    return n or _t("Nuvem")


def _remotes():
    """{nome: tipo} lido direto do rclone.conf (sem abrir o rclone: a lateral chama isto)."""
    out, atual = {}, None
    try:
        linhas = CONF_RCLONE.read_text().splitlines()
    except OSError:
        return out
    for l in linhas:
        l = l.strip()
        if l.startswith("[") and l.endswith("]"):
            atual = l[1:-1]
            out[atual] = ""
        elif atual and l.startswith("type") and "=" in l:
            out[atual] = l.split("=", 1)[1].strip()
    return out


def _montados():
    """Pontos fuse.rclone de /proc/self/mounts (sem tocar a pasta, que pode estar ocupada)."""
    pts = set()
    try:
        for l in open("/proc/self/mounts"):
            c = l.split()
            if len(c) > 2 and c[2].startswith("fuse.rclone"):
                pts.add(c[1].encode().decode("unicode_escape"))
    except OSError:
        pass
    return pts


def listar():
    """[{nome, tipo, provedor, pasta, ativo}] — contas conectadas (sem as do backup)."""
    reg = _registro()
    montados = _montados()
    out = []
    for nome, tipo in _remotes().items():
        if nome in INTERNOS:
            continue
        prov = reg.get(nome, {}).get("provedor") or POR_TIPO.get(tipo, {}).get("id", "")
        pasta = RAIZ / nome
        out.append({"nome": nome, "tipo": tipo, "provedor": prov,
                    "titulo": reg.get(nome, {}).get("titulo") or nome,
                    "pasta": str(pasta), "ativo": str(pasta) in montados})
    return out


_espaco = {}


def espaco(nome):
    """(usado, total) em bytes, ou None. Guarda por 10 min (cada consulta vai à API)."""
    import time
    c = _espaco.get(nome)
    if c and time.monotonic() - c[0] < 600:
        return c[1]
    r = _espaco_api(nome)
    _espaco[nome] = (time.monotonic(), r)
    return r


def _espaco_api(nome):
    try:
        r = _rc("about", f"{nome}:", "--json", timeout=30)
        d = json.loads(r.stdout)
        total = d.get("total")
        usado = d.get("used", 0) + d.get("trashed", 0)
        return (usado, total) if total else None
    except Exception:  # noqa: BLE001
        return None


def _resposta_padrao(opt):
    nome = opt.get("Name", "")
    if nome == "config_type":
        return "onedrive"
    if opt.get("Default") not in (None, ""):
        d = opt["Default"]
        return str(d).lower() if isinstance(d, bool) else str(d)
    ex = opt.get("Examples") or []
    return str(ex[0].get("Value", "")) if ex else ""


def conectar(prov_id, titulo, campos, aviso_link=None):
    """Cria o remote (login no navegador, se OAuth), monta e liga na inicialização.
    Devolve o nome do remote. aviso_link(url) é chamado com o link de login."""
    p = POR_ID[prov_id]
    nome = nome_seguro(titulo)
    existentes = set(_remotes())
    base, n = nome, 2
    while nome in existentes:
        nome = f"{base}-{n}"
        n += 1
    args = ["config", "create", nome, p["tipo"], *p.get("params", [])]
    if prov_id == "nextcloud":   # Nextcloud/ownCloud pelo endereço; senão WebDAV comum
        url = (campos or {}).get("url", "")
        args.append("vendor=" + ("nextcloud" if "/remote.php/dav" in url else "owncloud" if "/remote.php/webdav" in url else "other"))
    obscuros = []
    for chave, valor in (campos or {}).items():
        if valor == "":
            continue
        if chave in ("pass", "password"):
            valor = _rc("obscure", "-", entrada=valor).stdout.strip()
            obscuros.append(chave)
        args.append(f"{chave}={valor}")
    if p["oauth"]:
        args.append("config_is_local=true")
    args.append("--non-interactive")
    proc = subprocess.Popen(["rclone", *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    # o link de login aparece no stderr (o navegador abre sozinho)
    import threading

    def ler_err():
        for l in proc.stderr:
            m = re.search(r"(http://127\.0\.0\.1:\d+/auth\?state=\S+)", l)
            if m and aviso_link:
                aviso_link(m.group(1))
    threading.Thread(target=ler_err, daemon=True).start()
    saida, _ = proc.communicate(timeout=600)
    # perguntas que sobraram (ex.: qual OneDrive): responde o padrão
    for _ in range(12):
        try:
            estado = json.loads(saida) if saida.strip().startswith("{") else {}
        except ValueError:
            estado = {}
        if not estado.get("State"):
            if estado.get("Error"):
                raise RuntimeError(estado["Error"])
            break
        resp = _resposta_padrao(estado.get("Option") or {})
        saida = _rc("config", "update", nome, "--continue", "--state", estado["State"],
                    "--result", resp, "--non-interactive", timeout=300).stdout
    if nome not in _remotes():
        raise RuntimeError(_t("o login não foi concluído"))
    reg = _registro()
    reg[nome] = {"provedor": prov_id, "titulo": titulo}
    _gravar_registro(reg)
    montar(nome)
    # Confere a montagem; se não subir, desfaz e mostra o motivo
    import time
    for _ in range(40):
        if str(RAIZ / nome) in _montados():
            return nome
        time.sleep(0.5)
    log = subprocess.run(["journalctl", "--user", "-u", f"explorador-nuvem@{nome}.service", "-n", "20", "-o", "cat"],
                         capture_output=True, text=True).stdout
    erro = next((l for l in reversed(log.splitlines()) if "ERROR" in l or "Failed to create" in l), _t("a pasta não montou"))
    desconectar(nome)
    raise RuntimeError(re.sub(r"^.*?ERROR\S*\s*:?\s*", "", erro)[:300])


def _unidade():
    UNIDADE.parent.mkdir(parents=True, exist_ok=True)
    if not UNIDADE.exists() or UNIDADE.read_text() != SERVICO:
        UNIDADE.write_text(SERVICO)
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)


def _gravar_opcoes(nome):
    """Grava <remote>.env; devolve True se mudou (o serviço precisa reiniciar)."""
    OPCOES.mkdir(parents=True, exist_ok=True)
    f = OPCOES / f"{nome}.env"
    novo = f"OPCOES=\"{opcoes_montagem(_remotes().get(nome, ''))}\"\n"
    if f.exists() and f.read_text() == novo:
        return False
    f.write_text(novo)
    return True


def atualizar_montagens():
    """Ao abrir o Explorador: contas montadas com opções antigas reiniciam com as novas."""
    mudou_unidade = not UNIDADE.exists() or UNIDADE.read_text() != SERVICO
    _unidade()
    for c in listar():
        if (_gravar_opcoes(c["nome"]) or mudou_unidade) and c["ativo"]:
            subprocess.run(["systemctl", "--user", "restart", f"explorador-nuvem@{c['nome']}.service"],
                           capture_output=True, timeout=90)


def montar(nome):
    _unidade()
    _gravar_opcoes(nome)
    (RAIZ / nome).mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["systemctl", "--user", "enable", "--now", f"explorador-nuvem@{nome}.service"],
                       capture_output=True, text=True, timeout=90)
    return r.returncode == 0


def desmontar(nome):
    subprocess.run(["systemctl", "--user", "disable", "--now", f"explorador-nuvem@{nome}.service"],
                   capture_output=True, timeout=60)


def desconectar(nome):
    desmontar(nome)
    _rc("config", "delete", nome, timeout=30)
    try:
        (RAIZ / nome).rmdir()
    except OSError:
        pass
    reg = _registro()
    reg.pop(nome, None)
    _gravar_registro(reg)
