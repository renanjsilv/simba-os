#!/usr/bin/env python3
"""conta — conta Google para levar o sistema para uma máquina formatada.

Faz backup das configurações, papéis de parede, histórico (terminal e Brave),
documentos e da lista de programas instalados numa pasta "Simba Conta" do
Google Drive (via rclone, escopo drive.file: o app só enxerga o que ele mesmo
criou) e restaura tudo numa instalação nova.

  conta status                      JSON com o estado (para a interface)
  conta entrar [--cripto SENHA]     instala o rclone se faltar, abre o login do Google no navegador
  conta sair                        esquece o login (os dados no Drive ficam)
  conta sincronizar [--silencioso]  envia o backup agora
  conta restaurar [--sim] [--sem-pacotes]   traz tudo do Drive para esta máquina
  conta pacotes                     instala os programas que faltam (abre um terminal)
  conta auto liga|desliga           sincronização automática (a cada 2 h e 10 min após ligar)
  conta categoria <id> liga|desliga escolhe o que entra no backup
  conta escolher [--categorias a,b] [--fundo liga|desliga]
                                    escolha do 1º login: o que sincronizar (antes disso nada é enviado)
  conta tamanho                     estima o tamanho do backup local
  conta fundo liga|desliga          papel de parede igual em todas as máquinas, na hora

Variáveis para teste: CONTA_RCLONE (binário), CONTA_REMOTO (remoto já configurado,
ex. "teste:" para um remoto local), CONTA_HOME (pasta pessoal alternativa).
"""
import argparse
import datetime
import fcntl
import fnmatch
import getpass
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
import sys as _sys, os as _os  # noqa: E401
_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))
from simba_i18n import t as _t, DECIMAL as _DEC  # noqa: E402  (traduções: /usr/share/simba-apps/idiomas)

HOME = Path(os.environ.get("CONTA_HOME") or Path.home())
CFG_DIR = HOME / ".config/conta"
CFG = CFG_DIR / "config.json"
ESTADO = HOME / ".local/state/conta/estado.json"
# Criado pelo instalador da ISO (gerar-iso/instalar-clone): na primeira
# inicialização abre Configurações › Contas com as boas-vindas (conta-boas-vindas).
BOAS_VINDAS = HOME / ".local/state/conta/boas-vindas"
# Foto da conta Google; ~/.face aponta para ela (avatar de Configurações, do
# menu Iniciar e da tela de login) — só se ~/.face não existir ou já for nosso.
# Existe = não oferecer o login nas instalações pela ISO (vai junto na ISO, pois
# ~/.local/share/conta entra nela; quem instala decide pelas Configurações).
SEM_BOAS_VINDAS = HOME / ".local/share/conta/sem-boas-vindas"
FOTO = HOME / ".local/state/conta/foto.jpg"
COTA = HOME / ".local/state/conta/cota.json"
FACE = HOME / ".face"
CACHE = HOME / ".cache/conta"
EXTRA = CACHE / "extra"
FERRAMENTA = Path(__file__).resolve()
RUN = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp"))
# testes (CONTA_HOME): trava própria, para não brigar com o conta de verdade desta máquina
TRAVA = (HOME / ".cache/conta" if os.environ.get("CONTA_HOME") else RUN) / "conta.lock"
NOME_REMOTO = "conta-gdrive"
NOME_CRIPTO = "conta-cripto"
PASTA = "Simba Conta"

CATEGORIAS = {
    "config": _t("Aparência"),
    "brave": _t("Brave"),
    "terminal": _t("Terminal e atalhos"),
    "draco": _t("Draco e Agentes de IA"),
    "pacotes": _t("Programas instalados"),
    "segredos": _t("Chaves SSH e chaves de API (só com criptografia)"),
    "documentos": _t("Documentos"),
    "imagens": _t("Imagens"),
    "pastas": _t("Pastas sincronizadas"),
    "historico": _t("Histórico do navegador e do terminal"),
}

# Caminhos relativos à pasta pessoal por categoria (pastas entram inteiras,
# menos o que casar com EXCLUIR).
INCLUIR = {
    "config": [
        ".config", ".local/bin", ".local/state/simba",
        ".local/share/applications", ".local/share/icons", ".local/share/fonts",
        ".local/share/gerenciador-tarefas", ".local/share/temas-boot", ".local/share/transcrever",
        ".local/share/conta", ".local/share/gerar-iso", ".local/share/anydesk-bridge",
        ".local/share/simba-idioma", ".local/share/nautilus-python", ".local/share/aether",
        ".XCompose", ".gitconfig",
    ],
    "terminal": [
        ".config/kitty", ".config/foot", ".config/alacritty", ".config/ghostty",
        ".config/nvim", ".bashrc", ".bash_profile", ".bash_history",
        ".local/share/fish", ".zshrc", ".zsh_history",
    ],
    "draco": [
        ".config/draco", ".local/share/draco",
    ],
    "imagens": [_t("Pictures"), _t("Wallpapers")],
    "historico": [".bash_history", ".local/share/recently-used.xbel", ".local/share/fish/fish_history",
                  ".zsh_history", ".python_history"],
    "documentos": [_t("Documents"), _t("Área de trabalho"), _t("Desktop")],
    "segredos": [".ssh", ".config/draco/chaves", ".config/draco/groq.key", ".local/share/draco/groq.key", ".gnupg"],
}

EXCLUIR = [
    # navegadores (o histórico/favoritos do Brave vão à parte, copiados com segurança)
    ".config/BraveSoftware", ".config/chromium", ".config/google-chrome", ".mozilla",
    # grandes / regeneráveis / específicos da máquina
    ".config/hydralauncher", ".config/rclone", ".config/pulse", ".config/Electron",
    ".local/share/draco/venv", ".local/share/draco/wake-train", ".local/share/draco/voices",
    ".local/share/draco/recordings", ".local/share/draco/logs", ".local/share/temas-boot/build",
    ".config/draco/gravacoes",
    "*/Cache", "*/cache", "*/Code Cache", "*/GPUCache", "*/CachedData", "*/Crashpad",
    "*/__pycache__", "*.log", "*.pyc", "*/.git/objects",
    # segredos ficam na categoria "segredos" (só com criptografia)
    ".ssh", ".gnupg", ".config/draco/chaves", ".config/draco/groq.key", ".local/share/draco/groq.key",
    ".local/share/keyrings", "*.sock.pid",
    ".config/gh/hosts.yml",
    ".local/share/conta/antes-da-restauracao", ".local/share/conta/brave-pendente",
    # área de transferência e notificações guardam texto copiado (senhas, chaves de API)
    ".local/state/simba/clipboard-history.json", ".local/state/simba/clipboard-images",
    ".local/state/simba/notifications", ".local/state/simba/notifications.json",
    # credenciais salvas de apps e modelos que se baixam de novo
    ".config/spotify", ".local/share/draco/models/whisper",
    # tema de ícones do Simba: vem no sistema (/usr/share/icons); a cópia de antes ia sem os
    # links internos e, restaurada, ficava por cima do tema bom e sumia com os ícones
    ".local/share/icons/Yaru-grey", ".local/share/icons/Yaru-gray",
]
# Pasta "Simba Conta" na pasta pessoal (como a do OneDrive): atalhos para tudo o que vai
# para o Drive. É o que o "Abrir pasta" da nuvem na barra abre. Só tem links: nunca entra
# no backup nem guarda arquivos.
PASTA_LOCAL = HOME / PASTA
EXCLUIR.append(PASTA)
LINKS = {}   # links simbólicos vistos no backup: rel → destino (vão em extra/links.json)
MAX_ARQUIVO = 200 * 1024 * 1024  # arquivos maiores que isso ficam de fora

BRAVE = HOME / ".config/BraveSoftware/Brave-Browser/Default"
BRAVE_ARQS = ["History", "Bookmarks", "Favicons", "Top Sites", "Shortcuts"]


# ── utilidades ───────────────────────────────────────────────────────────────
def ler_json(p, padrao):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return padrao


def gravar_json(p, v):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(v, ensure_ascii=False, indent=2))
    tmp.replace(p)


def config():
    c = ler_json(CFG, {})
    c.setdefault("auto", True)
    c.setdefault("cripto", False)
    c.setdefault("categorias", {})
    for k in CATEGORIAS:
        if k not in c["categorias"]:
            if k in ("segredos", "pastas"):
                c["categorias"][k] = False
            elif k in ("brave", "terminal", "draco"):
                c["categorias"][k] = c["categorias"].get("config", True)
            else:
                c["categorias"][k] = True
    c.setdefault("pastas_personalizadas", [])
    c.setdefault("pastas_excluidas", [])
    c.setdefault("sincronizar_fundo", True)
    # Escolha do que sincronizar, feita depois do 1º login (Configurações › Contas ou
    # boas-vindas). Contas de antes dessa tela (já com e-mail) contam como escolhidas.
    c.setdefault("escolha_feita", bool(c.get("email")))
    return c


def precisa_escolher(c=None):
    c = c or config()
    return not c.get("escolha_feita") and conectado()


def salvar_config(c):
    gravar_json(CFG, c)


def estado():
    return ler_json(ESTADO, {})


def salvar_estado(**kw):
    e = estado()
    e.update(kw)
    gravar_json(ESTADO, e)


def avisar(titulo, corpo="", urgente=False):
    if os.environ.get("CONTA_HOME"):
        return
    try:
        if shutil.which("simba-notification-send"):
            # clicar no aviso (ou nele na central de notificações) abre Configurações › Contas
            cmd = ["simba-notification-send", "--app-name", "Conta", "-i", "folder-remote",
                   *(["-u", "critical"] if urgente else []), titulo, corpo or " ", "--exec", "configuracoes", "contas"]
        else:
            cmd = ["notify-send", "-a", "Conta", "-i", "folder-remote", *(["-u", "critical"] if urgente else []),
                   titulo, corpo]
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass


def rclone_bin():
    for c in (os.environ.get("CONTA_RCLONE"), shutil.which("rclone")):
        if c and os.access(c, os.X_OK):
            return c
    return None


def rc(*args, check=True, capture=True, timeout=None, entrada=None):
    exe = rclone_bin()
    if not exe:
        raise SystemExit(_t("rclone não instalado"))
    # low-level-retries: o rclone espera e tenta de novo quando o Google responde
    # "rateLimitExceeded" (cota do client_id compartilhado do rclone). Com 1 tentativa só,
    # qualquer limite momentâneo derrubava o backup e gerava o aviso "Falha no backup".
    rclone_cmd = [exe, "--retries", "1", "--low-level-retries", "8", "--contimeout", "5s", *args]
    r = subprocess.run(rclone_cmd, capture_output=capture, text=True, timeout=timeout, input=entrada)
    if check and r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "").strip()[-800:] or f"rclone {args[0]} falhou")
    return r


def erro_temporario(msg):
    """Falhas que passam sozinhas (limite de uso da API do Google, rede, servidor fora):
    a próxima rodada do timer resolve, então não merecem notificação na hora."""
    m = str(msg).lower()
    if "storagequotaexceeded" in m:        # Drive cheio: não passa sozinho
        return False
    return any(k in m for k in (
        "ratelimitexceeded", "rate_limit_exceeded", "userratelimitexceeded", "quota",
        "too many requests", "429", "backenderror", "internal error", " 500", " 502", " 503",
        "timeout", "timed out", "no such host", "connection refused", "connection reset",
        "network is unreachable", "temporary failure", "i/o timeout",
        "falha ao enviar os arquivos (veja a conexão)"))


# Avisa da falha só se o backup estiver parado há esse tempo (erros temporários seguidos).
AVISAR_FALHA_APOS = 3 * 3600


def remoto_base():
    """Remoto do Drive na pasta da conta (sem criptografia)."""
    if os.environ.get("CONTA_REMOTO"):
        r = os.environ["CONTA_REMOTO"]
        return r + PASTA if r.endswith(":") else r.rstrip("/") + "/" + PASTA
    return f"{NOME_REMOTO}:{PASTA}"


def remoto_dados(c=None):
    c = c or config()
    if c.get("cripto"):
        return f"{NOME_CRIPTO}:"
    return remoto_base() + "/dados"


def conectado():
    if os.environ.get("CONTA_REMOTO"):
        return True
    if not rclone_bin():
        return False
    # O rclone grava o remoto assim que o login COMEÇA (antes de o Google autorizar): só vale
    # como conectado com o token gravado. Antes as boas-vindas diziam "Conectado" sem login.
    r = rc("config", "dump", check=False)
    try:
        remoto = json.loads(r.stdout or "{}").get(NOME_REMOTO) or {}
    except ValueError:
        return False
    try:
        token = json.loads(remoto.get("token") or "{}")
    except ValueError:
        token = {}
    return bool(token.get("access_token") or token.get("refresh_token"))


class Trava:
    def __enter__(self):
        TRAVA.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(TRAVA, "w")
        try:
            fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit(_t("já existe uma sincronização/restauração em andamento"))
        salvar_estado(sincronizando=True)
        return self

    def __exit__(self, *a):
        salvar_estado(sincronizando=False)
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


# ── seleção de arquivos ──────────────────────────────────────────────────────
def _excluido(rel, extras=()):
    for pad in (*EXCLUIR, *extras):
        if "*" in pad:
            # "*/Cache" casa com qualquer componente; "*.log" com o nome
            if pad.startswith("*/"):
                if pad[2:] in rel.split("/"):
                    return True
            elif fnmatch.fnmatch(os.path.basename(rel), pad):
                return True
        elif rel == pad or rel.startswith(pad + "/"):
            return True
    return False


def listar_arquivos(c=None):
    """Lista (relativa à pasta pessoal) do que vai para o Drive + tamanho total."""
    c = c or config()
    # documentos/imagens/pastas: sincronizadas nos dois sentidos (sincronizar_pastas), fora daqui
    cats = [k for k, v in c["categorias"].items() if v and k in INCLUIR and k not in ("documentos", "imagens")]
    if "segredos" in cats and not c.get("cripto"):
        cats.remove("segredos")
    excl_extra = list(c.get("pastas_excluidas", []))
    vistos, lista, total = set(), [], 0
    for cat in cats:
        liberar = INCLUIR["segredos"] if cat == "segredos" else []
        bases = list(INCLUIR.get(cat, []))
        if cat == "pastas":   # só as pastas que a pessoa marcou (boas-vindas / Contas)
            bases = [x for x in c.get("pastas_personalizadas", []) if x]
        if cat == "documentos":
            for p_extra in c.get("pastas_personalizadas", []):
                if p_extra and p_extra not in bases:
                    bases.append(p_extra)
        for base in bases:
            raiz = HOME / base
            if not raiz.exists() or raiz.is_symlink() and not raiz.is_file():
                continue
            if raiz.is_file():
                candidatos = [raiz]
            else:
                candidatos = []
                for d, dirs, arqs in os.walk(raiz, followlinks=False):
                    reld = os.path.relpath(d, HOME)
                    for x in dirs + arqs:                       # links: só registrados
                        q = Path(d) / x
                        if q.is_symlink() and not _excluido(f"{reld}/{x}", excl_extra):
                            try:
                                LINKS[os.path.relpath(q, HOME)] = os.readlink(q)
                            except OSError:
                                pass
                    dirs[:] = [x for x in dirs
                               if not (_excluido(f"{reld}/{x}", excl_extra) and not _liberado(f"{reld}/{x}", liberar))]
                    candidatos.extend(Path(d) / a for a in arqs)
            for p in candidatos:
                rel = os.path.relpath(p, HOME)
                if rel in vistos:
                    continue
                if _excluido(rel, excl_extra) and not _liberado(rel, liberar):
                    continue
                try:
                    st = p.lstat()
                except OSError:
                    continue
                if not p.is_file() or p.is_symlink() or st.st_size > MAX_ARQUIVO:
                    continue
                vistos.add(rel)
                lista.append(rel)
                total += st.st_size
    return sorted(lista), total


def _liberado(rel, liberar):
    return any(rel == b or rel.startswith(b + "/") for b in liberar)


# ── extras: pacotes, Brave, estado do sistema ────────────────────────────────
def preparar_extras(c, lista=()):
    if EXTRA.exists():
        shutil.rmtree(EXTRA)
    (EXTRA / "pacotes").mkdir(parents=True)
    # O Google Drive não guarda permissões: anota as que não são 0644 (executáveis,
    # chaves 0600) e as pastas privadas, para reaplicar na restauração.
    modos = {}
    for rel in lista:
        try:
            m = (HOME / rel).stat().st_mode & 0o7777
        except OSError:
            continue
        if m != 0o644:
            modos[rel] = m
    for d in (".ssh", ".gnupg", ".config/draco/chaves"):
        if (HOME / d).is_dir():
            modos[d] = (HOME / d).stat().st_mode & 0o7777
    gravar_json(EXTRA / "modos.json", modos)
    cats = c["categorias"]
    if cats.get("pacotes"):
        modo = c.get("pacotes_modo", "todos")
        selecionados = set(c.get("pacotes_selecionados", []))
        for nome, args in (("pacman.txt", ["pacman", "-Qqen"]), ("aur.txt", ["pacman", "-Qqem"])):
            out = subprocess.run(args, capture_output=True, text=True).stdout
            linhas = [l.strip() for l in out.splitlines() if l.strip()]
            if modo == "escolher" and selecionados:
                linhas = [l for l in linhas if l in selecionados]
            (EXTRA / "pacotes" / nome).write_text("\n".join(linhas) + "\n" if linhas else "")
        if shutil.which("flatpak"):
            out = subprocess.run(["flatpak", "list", "--app", "--columns=application"], capture_output=True, text=True).stdout
            linhas = [l.strip() for l in out.splitlines() if l.strip()]
            if modo == "escolher" and selecionados:
                linhas = [l for l in linhas if l in selecionados]
            (EXTRA / "pacotes" / "flatpak.txt").write_text("\n".join(linhas) + "\n" if linhas else "")
    if (cats.get("brave") or cats.get("historico")) and BRAVE.is_dir():
        dest = EXTRA / "brave"
        dest.mkdir()
        for a in BRAVE_ARQS:
            src = BRAVE / a
            if not src.exists():
                continue
            if a in ("History", "Favicons", "Top Sites", "Shortcuts") and shutil.which("sqlite3"):
                # cópia consistente mesmo com o Brave aberto
                r = subprocess.run(["sqlite3", f"file:{src}?mode=ro&immutable=1", f".backup '{dest / a}'"],
                                   capture_output=True, text=True, timeout=60)
                if r.returncode != 0:
                    shutil.copy2(src, dest / a)
            else:
                shutil.copy2(src, dest / a)
    unidades = subprocess.run(["systemctl", "--user", "list-unit-files", "--state=enabled", "--no-legend",
                               "--type=service,timer,path"], capture_output=True, text=True).stdout
    meus = [l.split()[0] for l in unidades.splitlines() if l.split() and (HOME / ".config/systemd/user" / l.split()[0]).exists()]
    (EXTRA / "systemd-user-ativos.txt").write_text("\n".join(meus) + "\n")
    tema = (HOME / ".local/state/simba/current/theme.name")
    plymouth = ""
    try:
        plymouth = subprocess.run(["tema-boot", "atual"], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    meta = {
        "data": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "maquina": nome_maquina(),
        "usuario": os.environ.get("USER", ""),
        "tema": tema.read_text().strip() if tema.exists() else "",
        "tema_boot": plymouth,
        "cripto": bool(c.get("cripto")),
    }
    # papel de parede atual (é um link: o rclone não segue): a imagem vai junto, para a
    # restauração aplicar o fundo antes de tudo
    try:
        fundo = (HOME / ".local/state/simba/current/background").resolve(strict=True)
        if fundo.is_file() and fundo.stat().st_size < 60 * 1024 * 1024:
            (EXTRA / "fundo").mkdir(parents=True, exist_ok=True)
            shutil.copy2(fundo, EXTRA / "fundo" / fundo.name)
            meta["fundo"] = str(fundo)
            meta["fundo_hash"] = _hash_arquivo(fundo)
    except OSError:
        pass
    if (EXTRA / "brave" / "Bookmarks").exists():
        meta["brave"] = {
            "mtime": (EXTRA / "brave" / "Bookmarks").stat().st_mtime,
            "data": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        }
    meta = registrar_dispositivo_local(meta)
    gravar_json(EXTRA / "links.json", LINKS)
    gravar_json(EXTRA / "meta.json", meta)
    return meta


# ── utilitários de rede, dispositivos e navegador ────────────────────────────
def rede_limitada():
    """Detecta se a conexão de rede ativa é limitada (dados móveis/hotspot celular)."""
    try:
        r = subprocess.run(
            ["busctl", "get-property", "org.freedesktop.NetworkManager",
             "/org/freedesktop/NetworkManager", "org.freedesktop.NetworkManager", "Metered"],
            capture_output=True, text=True, timeout=2
        )
        if r.returncode == 0:
            val = r.stdout.strip().split()[-1]
            if val in ("1", "3"):
                return True
    except Exception:
        pass
    try:
        r = subprocess.run(["nmcli", "-g", "GENERAL.METERED", "dev", "show"],
                           capture_output=True, text=True, timeout=2)
        if r.returncode == 0:
            for l in r.stdout.splitlines():
                if "yes" in l.lower():
                    return True
    except Exception:
        pass
    return False


def info_dispositivo_local():
    maquina = nome_maquina()
    usuario = getpass.getuser()
    eh_laptop = False
    try:
        eh_laptop = any(p.name.startswith("BAT") for p in Path("/sys/class/power_supply").iterdir())
    except Exception:
        pass

    fundo = ""
    try:
        link = HOME / ".local/state/simba/current/background"
        if link.exists():
            fundo = str(link.resolve())
    except Exception:
        pass

    tema = ""
    try:
        tema_arq = HOME / ".local/state/simba/current/theme.name"
        if tema_arq.exists():
            tema = tema_arq.read_text().strip()
    except Exception:
        pass

    return {
        "maquina": maquina,
        "usuario": usuario,
        "tipo": "laptop" if eh_laptop else "desktop",
        "data": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "tema": tema or "padrão",
        "fundo": fundo or "",
        "versao": "Simba OS"
    }


def registrar_dispositivo_local(meta):
    disps = meta.get("dispositivos")
    if not isinstance(disps, dict):
        disps = {}

    rem_meta = estado().get("remoto_meta", {})
    if isinstance(rem_meta, dict):
        for k, v in rem_meta.get("dispositivos", {}).items():
            if isinstance(v, dict) and k not in disps:
                disps[k] = v
        rem_maq = rem_meta.get("maquina")
        if rem_maq and rem_maq not in disps:
            disps[rem_maq] = {
                "maquina": rem_maq,
                "usuario": rem_meta.get("usuario", ""),
                "tipo": "desktop",
                "data": rem_meta.get("data", ""),
                "tema": rem_meta.get("tema", ""),
                "fundo": rem_meta.get("fundo", ""),
                "versao": "Simba OS"
            }

    info = info_dispositivo_local()
    disps[info["maquina"]] = info
    meta["dispositivos"] = disps
    return meta


def esta_pausado():
    """Verifica se a sincronização está pausada temporariamente (Modo Viagem)."""
    e = estado()
    pausado_ate_str = e.get("pausado_ate")
    if not pausado_ate_str:
        return False, ""
    try:
        dt = datetime.datetime.fromisoformat(pausado_ate_str)
        agora = datetime.datetime.now(datetime.timezone.utc)
        if agora < dt.astimezone(datetime.timezone.utc):
            return True, pausado_ate_str
        else:
            salvar_estado(pausado_ate="")
            return False, ""
    except Exception:
        salvar_estado(pausado_ate="")
        return False, ""


def cmd_pausar(a):
    horas = getattr(a, "horas", 24) or 24
    ate = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=horas)).isoformat(timespec="seconds")
    salvar_estado(pausado_ate=ate)
    avisar(_t("Modo Viagem Ativado"), _t("Sincronização com o Google Drive pausada por %1 horas.", horas))
    print(_t("Sincronização pausada por %1 horas (até %2).", horas, ate))
    return 0


def cmd_retomar(_a):
    salvar_estado(pausado_ate="")
    avisar(_t("Modo Viagem Desativado"), _t("Sincronização automática com a nuvem retomada."))
    print(_t("Sincronização retomada."))
    return 0


def cmd_resolver(a):
    e = estado()
    c = e.get("conflito")
    if not c:
        print(_t("Nenhum conflito pendente."))
        return 0

    escolha = a.escolha.lower()
    if escolha in ("local", "este", "manter-local"):
        salvar_estado(conflito=None)
        avisar(_t("Conflito Resolvido"), _t("A versão deste computador foi mantida e enviada à nuvem."))
        print(_t("Versão local mantida. Atualizando nuvem…"))
        return cmd_sincronizar(argparse.Namespace(silencioso=False, substituir=True, forcar=True))
    elif escolha in ("remoto", "nuvem", "usar-remoto"):
        salvar_estado(conflito=None)
        avisar(_t("Conflito Resolvido"), _t("As alterações da nuvem foram aplicadas com sucesso."))
        print(_t("Aplicando alterações da nuvem…"))
        puxar_alteracoes_remotas(silencioso=False, forcar=True)
        return 0
    else:
        print(_t("Escolha 'local' ou 'remoto'."), file=sys.stderr)
        return 1


def cmd_pasta(a):
    c = config()
    acao = a.acao.lower()
    if acao in ("adicionar", "incluir"):
        if not a.caminho:
            print(_t("caminho obrigatório"), file=sys.stderr)
            return 1
        p = a.caminho.strip()
        if p.startswith(str(HOME)):
            p = os.path.relpath(p, HOME)
        p = p.strip("/")
        if p and p not in c["pastas_personalizadas"]:
            c["pastas_personalizadas"].append(p)
            if p in c.get("pastas_excluidas", []):
                c["pastas_excluidas"].remove(p)
            salvar_config(c)
            print(_t("Pasta adicionada: %1", p))
    elif acao in ("remover", "excluir"):
        if not a.caminho:
            print(_t("caminho obrigatório"), file=sys.stderr)
            return 1
        p = a.caminho.strip()
        alvo_rel = os.path.relpath(p, HOME) if p.startswith(str(HOME)) else p
        alvo_rel = alvo_rel.strip("/")
        removido = None
        for item in list(c["pastas_personalizadas"]):
            if item in (p, alvo_rel, Path(p).name):
                c["pastas_personalizadas"].remove(item)
                removido = item
        if removido:
            salvar_config(c)
            print(_t("Pasta removida: %1", removido))
        elif p and p not in c.get("pastas_excluidas", []):
            c["pastas_excluidas"].append(p)
            salvar_config(c)
            print(_t("Pasta adicionada às exclusões: %1", p))
    elif acao == "listar":
        print(json.dumps({
            "local": str(PASTA_LOCAL),
            "personalizadas": c.get("pastas_personalizadas", []),
            "excluidas": c.get("pastas_excluidas", [])
        }, ensure_ascii=False))
        return 0
    marcar_pastas_alteradas()
    if conectado():
        atualizar_pasta_local()
    return 0


def pastas_sincronizadas(c=None):
    """Pastas da pasta pessoal que vão para o Drive (relativas), na ordem de exibição."""
    c = c or config()
    cats = c.get("categorias", {})
    rel = []
    if cats.get("documentos"):
        rel += INCLUIR["documentos"]
    if cats.get("imagens"):
        rel += INCLUIR["imagens"]
    if cats.get("pastas") or cats.get("documentos"):
        rel += [x for x in c.get("pastas_personalizadas", []) if x]
    vistos, saida = set(), []
    for x in rel:
        x = x.strip("/")
        alvo = (HOME / x).resolve() if (HOME / x).exists() else None
        if not alvo or not alvo.is_dir() or alvo in vistos or x == PASTA or x in c.get("pastas_excluidas", []):
            continue
        vistos.add(alvo)
        saida.append(x)
    return saida


def atualizar_pasta_local(c=None):
    """Mantém ~/Simba Conta com um atalho para cada pasta sincronizada. Mexe só em links."""
    if os.environ.get("CONTA_HOME") and not os.environ.get("CONTA_PASTA_LOCAL"):
        return None
    c = c or config()
    desejados = {}
    for rel in pastas_sincronizadas(c):
        desejados.setdefault(Path(rel).name, HOME / rel)
    try:
        PASTA_LOCAL.mkdir(exist_ok=True)
        for item in PASTA_LOCAL.iterdir():
            if item.is_symlink():
                alvo = desejados.get(item.name)
                if alvo is None or os.readlink(item) != str(alvo):
                    item.unlink()
        for nome, alvo in desejados.items():
            link = PASTA_LOCAL / nome
            if not link.exists() and not link.is_symlink():
                link.symlink_to(alvo)
        (PASTA_LOCAL / ".hidden").write_text("")   # deixa a pasta limpa no Explorador
    except OSError:
        return None
    return PASTA_LOCAL


def remover_pasta_local():
    if not PASTA_LOCAL.is_dir() or PASTA_LOCAL.is_symlink():
        return
    for item in PASTA_LOCAL.iterdir():
        if item.is_symlink():
            item.unlink()
    (PASTA_LOCAL / ".hidden").unlink(missing_ok=True)
    try:
        PASTA_LOCAL.rmdir()        # só se ficou vazia: arquivos da pessoa nunca saem
    except OSError:
        pass


# ── pastas sincronizadas entre as máquinas (bidirecional) ────────────────────
# As pastas escolhidas (Documentos, Imagens, Área de trabalho, extras) ficam IGUAIS em todas
# as máquinas da conta: `rclone bisync` entre cada pasta e dados/pastas/<nome> no Drive.
# Na 1ª vez de cada máquina o conteúdo dela é MESCLADO com o da nuvem (nada se perde); depois
# o que se cria, muda ou apaga numa máquina vai para as outras. Conflito (o mesmo arquivo
# mudado nas duas): fica a versão mais nova e a outra vira "nome.conflito1.ext" ao lado.
# O que é apagado ou substituído no Drive vai para lixeira/<data> (30 dias).
# Antes todas as pastas iam num espelho de mão única (dados/home): a última máquina a
# sincronizar apagava do Drive o que só existia na outra — eram backups individuais.
# A lista de pastas também é da conta (pastas.json no Drive): marcar/desmarcar uma pasta numa
# máquina vale para todas.
XDG_PASTAS = [("DOCUMENTS", "Documentos"), ("PICTURES", "Imagens"), ("DESKTOP", "Área de trabalho"),
              ("MUSIC", "Músicas"), ("VIDEOS", "Vídeos"), ("DOWNLOAD", "Downloads")]
BISYNC_DIR = HOME / ".local/state/conta/bisync"
PASTAS_REMOTAS = "pastas.json"


def _xdg_dir(xdg):
    try:
        d = subprocess.run(["xdg-user-dir", xdg], capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        d = ""
    if d and os.path.abspath(d) != str(HOME):
        return Path(d)
    padrao = {"DOCUMENTS": "Documentos", "PICTURES": "Imagens", "DESKTOP": "Área de trabalho",
              "MUSIC": "Músicas", "VIDEOS": "Vídeos", "DOWNLOAD": "Downloads"}
    return HOME / padrao[xdg]


def _pasta_logica(rel):
    """rel (relativo à pasta pessoal) → {"nome", "xdg"?, "rel"}: as pastas padrão têm um nome
    só na nuvem ("Documentos"), seja qual for o nome local (Documents/Documentos)."""
    alvo = (HOME / rel).resolve()
    for xdg, nome in XDG_PASTAS:
        try:
            if _xdg_dir(xdg).resolve() == alvo:
                return {"nome": nome, "xdg": xdg, "rel": rel}
        except OSError:
            pass
    return {"nome": Path(rel).name, "rel": rel}


def _caminho_local(p):
    return _xdg_dir(p["xdg"]) if p.get("xdg") else HOME / p["rel"]


def pastas_locais_logicas(c=None):
    c = c or config()
    vistos, saida = set(), []
    for rel in pastas_sincronizadas(c):
        p = _pasta_logica(rel)
        if p["nome"] and p["nome"] not in vistos:
            vistos.add(p["nome"])
            saida.append(p)
    return saida


def _ler_pastas_remotas():
    try:
        r = rc("cat", f"{remoto_base()}/{PASTAS_REMOTAS}", check=False, timeout=60)
        d = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else None
        return d.get("pastas") if isinstance(d, dict) else None
    except (ValueError, subprocess.SubprocessError, OSError):
        return None


def _gravar_pastas_remotas(pastas):
    info = {"pastas": pastas, "maquina": nome_maquina(),
            "data": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
    rc("rcat", f"{remoto_base()}/{PASTAS_REMOTAS}", entrada=json.dumps(info, ensure_ascii=False, indent=1), timeout=60)


def _adotar_pastas(c, pastas):
    """Passa a lista da conta para a configuração local (rel de cada pasta nesta máquina)."""
    rels = []
    for p in pastas:
        local = _caminho_local(p)
        try:
            local.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        rel = os.path.relpath(local, HOME)
        if not rel.startswith("..") and rel not in rels:
            rels.append(rel)
    c["pastas_personalizadas"] = rels
    c["categorias"]["pastas"] = bool(rels)
    # documentos/imagens viram pastas da lista (não vão mais no espelho de mão única)
    c["categorias"]["documentos"] = False
    c["categorias"]["imagens"] = False
    c["pastas_excluidas"] = [x for x in c.get("pastas_excluidas", []) if x not in rels]
    salvar_config(c)


def combinar_lista_pastas(c):
    """Lista de pastas da conta. 1ª vez nesta máquina: união da local com a da nuvem. Depois:
    uma mudança feita aqui (marcada em `pastas_alteradas`) vai para a nuvem; senão vale a da nuvem."""
    e = estado()
    locais = pastas_locais_logicas(c)
    remotas = _ler_pastas_remotas()
    if not e.get("pastas_unidas") or remotas is None:
        nomes = {p["nome"] for p in locais}
        uniao = locais + [p for p in (remotas or []) if p.get("nome") not in nomes]
        _gravar_pastas_remotas(uniao)
        _adotar_pastas(c, uniao)
        salvar_estado(pastas_unidas=True, pastas_alteradas=False)
        return uniao
    if e.get("pastas_alteradas"):
        _gravar_pastas_remotas(locais)
        salvar_estado(pastas_alteradas=False)
        return locais
    if [p.get("nome") for p in remotas] != [p["nome"] for p in locais]:
        _adotar_pastas(c, remotas)
        atualizar_pasta_local(c)
    return remotas


def _bisync(local, remoto, trabalho, resync, lixeira):
    cmd = [rclone_bin(), "bisync", str(local), remoto, "--workdir", str(trabalho),
           "--resilient", "--recover", "--max-lock", "2m",
           "--conflict-resolve", "newer", "--conflict-loser", "num", "--conflict-suffix", "conflito",
           "--suffix-keep-extension", "--compare", "size,modtime", "--create-empty-src-dirs",
           # sem --fast-list/--tpslimit: com eles cada pasta levava ~40 s em vez de ~4 s
           "--skip-links", "--max-size", str(MAX_ARQUIVO),
           "--backup-dir2", lixeira,
           "--exclude", ".~lock.*#", "--exclude", "*.part", "--exclude", "*.crdownload",
           "--exclude", ".Trash-*/**", "--exclude", "**/.cache/**", "--exclude", "**/__pycache__/**",
           "--exclude", "**/node_modules/**", "--exclude", "**/.git/**",
           "--stats", "2s", "--stats-one-line", "-v"]
    if resync:
        # 1ª vez: mescla (o que só existe de um lado vai para o outro; igual dos dois lados
        # fica o mais novo) — nunca apaga nada
        cmd += ["--resync", "--resync-mode", "newer"]
    return subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)


def sincronizar_pastas(c, silencioso=True):
    """Bisync de cada pasta da conta. Devolve (ok, mensagem de erro)."""
    pastas = combinar_lista_pastas(c)
    if not pastas:
        return True, ""
    dados = remoto_dados(c)
    lixeira = f"{dados}/lixeira/{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}/pastas"
    iniciadas = set(estado().get("bisync_iniciadas") or [])
    erros = []
    for p in pastas:
        local = _caminho_local(p)
        try:
            local.mkdir(parents=True, exist_ok=True)
            # o bisync se recusa a trabalhar com uma pasta totalmente vazia (proteção contra
            # apagar tudo): um arquivo oculto garante que nunca fique vazia
            marca = local / ".simba-conta"
            if not marca.exists():
                marca.write_text("Pasta sincronizada entre os computadores da conta (Simba OS).\n")
        except OSError as ex:
            erros.append(f"{p['nome']}: {ex}")
            continue
        # o estado do bisync é por par de pastas: muda junto se a pasta local mudar de lugar
        chave = f"{p['nome']}|{local}"
        trabalho = BISYNC_DIR / re.sub(r"[^\w.-]+", "_", chave)
        trabalho.mkdir(parents=True, exist_ok=True)
        remoto = f"{dados}/pastas/{p['nome']}"
        rotulo = _t("Sincronizando %1", p["nome"])
        salvar_estado(progresso=rotulo + "…")
        primeira = chave not in iniciadas
        if primeira:
            rc("mkdir", remoto, check=False, timeout=60)
        proc = _bisync(local, remoto, trabalho, primeira, lixeira)
        saida = []

        def ler(proc=proc):
            for linha in proc.stderr:
                saida.append(linha)
                if "%" in linha and "ETA" in linha:
                    salvar_estado(progresso=f"{rotulo}: {_legivel(linha.strip())}")
            return proc.wait()
        codigo = ler()
        if codigo != 0 and not primeira and any("--resync" in l for l in saida):
            # histórico do bisync perdido/corrompido: mescla de novo (seguro, não apaga nada)
            proc = _bisync(local, remoto, trabalho, True, lixeira)
            saida = []
            codigo = ler(proc)
        if codigo == 0:
            iniciadas.add(chave)
            salvar_estado(bisync_iniciadas=sorted(iniciadas))
        else:
            ultimo = next((l.strip() for l in reversed(saida) if "ERROR" in l or "error" in l.lower()), "")
            if any("too many deletes" in l.lower() or "max-delete" in l.lower() for l in saida):
                ultimo = _t("muitos arquivos apagados de uma vez em %1 — nada foi apagado; confira e sincronize de novo", p["nome"])
            erros.append(f"{p['nome']}: {ultimo[-200:]}")
    return (not erros), "; ".join(erros)


def marcar_pastas_alteradas():
    salvar_estado(pastas_alteradas=True)


def cmd_abrir_pasta(_a):
    """Abre ~/Simba Conta (atualizada) no gerenciador de arquivos."""
    alvo = atualizar_pasta_local() if conectado() else None
    if not alvo:
        alvo = HOME
    abrir = ["explorador", str(alvo)] if shutil.which("explorador") else ["xdg-open", str(alvo)]
    subprocess.Popen(abrir, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


# ── comandos ─────────────────────────────────────────────────────────────────
def cmd_status(_a):
    # --rapido: sem varrer as pastas nem consultar o Drive (para quem pergunta a cada poucos
    # segundos: bandeja, boas-vindas esperando o login). A versão completa demorava segundos
    # em pastas grandes e as chamadas se acumulavam.
    rapido = bool(getattr(_a, "rapido", False))
    c = config()
    e = estado()
    lig = conectado()
    timer = subprocess.run(["systemctl", "--user", "is-enabled", "conta-sync.timer"], capture_output=True, text=True).stdout.strip()
    rodando = False
    TRAVA.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(TRAVA, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f, fcntl.LOCK_UN)
    except BlockingIOError:
        rodando = True

    remoto_m = e.get("remoto_meta", {})
    dispositivos_map = remoto_m.get("dispositivos", {}) if isinstance(remoto_m, dict) else {}
    info_local = info_dispositivo_local()
    info_local["este_dispositivo"] = True
    lista_dispositivos = [info_local]
    maq_local = info_local["maquina"]
    if isinstance(dispositivos_map, dict):
        for k, v in dispositivos_map.items():
            if k != maq_local and isinstance(v, dict):
                disp = dict(v)
                disp["este_dispositivo"] = False
                lista_dispositivos.append(disp)

    pausado, ate = esta_pausado()

    # Pacotes instalados no sistema
    qtd_pacotes = 0
    try:
        if rapido:
            raise OSError
        r = subprocess.run(["pacman", "-Qqe"], capture_output=True, text=True, timeout=2)
        qtd_pacotes = len([l for l in r.stdout.splitlines() if l.strip()])
    except Exception:
        pass

    # Informações das pastas sincronizadas
    pastas_padrao = [
        {"id": "documentos", "nome": _t("Documentos"), "alvos": [HOME / "Documents", HOME / "Documentos"]},
        {"id": "imagens", "nome": _t("Imagens"), "alvos": [HOME / "Pictures", HOME / "Imagens"]},
        {"id": "desktop", "nome": _t("Área de trabalho"), "alvos": [HOME / "Área de trabalho", HOME / "Desktop"]},
    ]
    pastas_info = []
    caminhos_vistos = set()
    for p_item in pastas_padrao:
        alvo = next((p for p in p_item["alvos"] if p.exists()), None)
        caminho_str = str(alvo) if alvo else str(p_item["alvos"][0])
        caminhos_vistos.add(caminho_str)
        caminhos_vistos.add(p_item["id"])
        caminhos_vistos.add(p_item["nome"])
        tot, cnt = 0, 0
        if alvo and not rapido:
            for root, dirs, files in os.walk(alvo):
                for f in files:
                    try:
                        tot += (Path(root) / f).stat().st_size
                        cnt += 1
                    except OSError:
                        pass
        pastas_info.append({
            "id": p_item["id"],
            "nome": p_item["nome"],
            "caminho": caminho_str,
            "existe": bool(alvo),
            "arquivos": cnt,
            "tamanho": tot,
            "padrao": True,
        })

    for p_str in c.get("pastas_personalizadas", []):
        if p_str in caminhos_vistos or p_str in ("Documents", "Documentos", "Pictures", "Imagens", "Desktop", "Área de trabalho"):
            continue
        alvo = HOME / p_str if not os.path.isabs(p_str) else Path(p_str)
        caminho_str = str(alvo)
        if caminho_str in caminhos_vistos:
            continue
        caminhos_vistos.add(caminho_str)
        tot, cnt = 0, 0
        if alvo.exists() and not rapido:
            for root, dirs, files in os.walk(alvo):
                for f in files:
                    try:
                        tot += (Path(root) / f).stat().st_size
                        cnt += 1
                    except OSError:
                        pass
        pastas_info.append({
            "id": p_str,
            "nome": alvo.name or p_str,
            "caminho": caminho_str,
            "existe": alvo.exists(),
            "arquivos": cnt,
            "tamanho": tot,
            "padrao": False,
        })

    # Arquivos recentes para o painel estilo OneDrive
    recentes = []
    pastas_alvo = [HOME / "Documents", HOME / "Documentos", HOME / "Pictures", HOME / "Imagens", HOME / "Desktop", HOME / "Área de trabalho"]
    for p_str in c.get("pastas_personalizadas", []):
        alvo = HOME / p_str if not os.path.isabs(p_str) else Path(p_str)
        if alvo.is_dir() and alvo not in pastas_alvo:
            pastas_alvo.append(alvo)

    candidatos = []
    agora_ts = time.time()
    for pasta_dir in ([] if rapido else pastas_alvo):
        if not pasta_dir.is_dir():
            continue
        nome_pasta = pasta_dir.name
        try:
            for root, dirs, files in os.walk(pasta_dir):
                dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("Cache", "cache", "build")]
                for f in files:
                    if f.startswith("."):
                        continue
                    fp = Path(root) / f
                    try:
                        st = fp.stat()
                        candidatos.append((st.st_mtime, f, nome_pasta, st.st_size, str(fp)))
                    except OSError:
                        pass
        except OSError:
            pass

    candidatos.sort(key=lambda x: x[0], reverse=True)
    for idx, (mtime, nome_arq, pasta_nome, tamanho, caminho_completo) in enumerate(candidatos[:35]):
        dt_seg = max(0, int(agora_ts - mtime))
        is_uploading = (rodando or e.get("sincronizando")) and (idx == 0 or dt_seg < 120)

        if is_uploading:
            status_item = "sincronizando"
            pct = 65
            if e.get("progresso"):
                m_pct = re.search(r"(\d+)%", e.get("progresso", ""))
                if m_pct:
                    pct = int(m_pct.group(1))
            progresso_pct = pct
            tempo_txt = _t("Enviando… (%1%)", pct)
        elif pausado:
            status_item = "pausado"
            progresso_pct = 0
            tempo_txt = _t("Pausado")
        elif e.get("resultado") == "erro" and dt_seg < 300:
            status_item = "erro"
            progresso_pct = 0
            tempo_txt = _t("Erro")
        elif dt_seg < 60:
            status_item = "ok"
            progresso_pct = 100
            tempo_txt = _t("Enviado agora")
        elif dt_seg < 3600:
            status_item = "ok"
            progresso_pct = 100
            tempo_txt = _t("Salvo há %1 min", dt_seg // 60)
        elif dt_seg < 86400:
            status_item = "ok"
            progresso_pct = 100
            tempo_txt = _t("Salvo há %1 h", dt_seg // 3600)
        else:
            status_item = "ok"
            progresso_pct = 100
            tempo_txt = _t("Salvo há %1 dias", dt_seg // 86400)

        recentes.append({
            "nome": nome_arq,
            "pasta": pasta_nome,
            "tamanho": tamanho,
            "caminho": caminho_completo,
            "mtime": mtime,
            "estado": tempo_txt,
            "status": status_item,
            "progresso_pct": progresso_pct
        })

    if e.get("ultima"):
        recentes.append({
            "nome": _t("Papel de parede e tema"),
            "pasta": _t("Configurações"),
            "tamanho": 0,
            "caminho": str(HOME / ".config"),
            "mtime": agora_ts,
            "estado": _t("Salvo há 10 min"),
            "status": "ok",
            "progresso_pct": 100
        })

    cota = obter_cota_drive(somente_cache=rapido) if lig else {}
    cota_total = int(cota.get("total") or 0)
    cota_usado = int(cota.get("used") or 0)
    cota_livre = int(cota.get("free") or 0)

    pac_modo = c.get("pacotes_modo", "todos")
    pac_sel = c.get("pacotes_selecionados", [])
    qtd_pacotes_sel = len(pac_sel) if pac_modo == "escolher" and pac_sel else qtd_pacotes

    print(json.dumps({
        "rclone": bool(rclone_bin()),
        "conectado": lig,
        "email": c.get("email", ""),
        "nome": c.get("nome", ""),
        "cripto": bool(c.get("cripto")),
        "auto": timer == "enabled",
        "sincronizar_fundo": bool(c.get("sincronizar_fundo", True)),
        "categorias": c["categorias"],
        "rotulos": CATEGORIAS,
        "precisa_escolher": bool(lig and not c.get("escolha_feita")),
        "ultima": e.get("ultima", ""),
        "resultado": e.get("resultado", ""),
        "erro": e.get("erro", ""),
        "tamanho": e.get("tamanho", 0),
        "arquivos": e.get("arquivos", 0),
        "progresso": e.get("progresso", ""),
        "rodando": rodando,
        "sincronizando": rodando or bool(e.get("sincronizando")),
        "rede_limitada": rede_limitada(),
        "pausado": pausado,
        "pausado_ate": ate,
        "conflito": e.get("conflito"),
        "pastas_personalizadas": c.get("pastas_personalizadas", []),
        "pastas_excluidas": c.get("pastas_excluidas", []),
        "pastas_info": pastas_info,
        "recentes": recentes,
        "cota_total": cota_total,
        "cota_usado": cota_usado,
        "cota_livre": cota_livre,
        "pacotes_modo": pac_modo,
        "qtd_pacotes": qtd_pacotes,
        "qtd_pacotes_selecionados": qtd_pacotes_sel,
        "brave_pendente": (HOME / ".local/share/conta/brave-pendente").is_dir(),
        "dispositivos": lista_dispositivos,
        "entrando": e.get("entrando", False),
        "remoto_meta": e.get("remoto_meta", {}),
        "precisa_decidir": e.get("precisa_decidir", False),
        "link_login": e.get("link_login", ""),
        "boas_vindas": BOAS_VINDAS.exists() and not SEM_BOAS_VINDAS.exists() and not lig,
        "boas_vindas_iso": not SEM_BOAS_VINDAS.exists(),
        "foto": str(FOTO) if lig and FOTO.exists() else "",
        "pasta_local": str(PASTA_LOCAL) if lig and PASTA_LOCAL.is_dir() else "",
        "pastas_sincronizadas": pastas_sincronizadas(c) if lig else [],
        "reconectar": bool(lig and not rapido and usa_client_id_compartilhado()),
    }, ensure_ascii=False))


def instalar_rclone():
    if rclone_bin():
        return True
    avisar(_t("Instalando o rclone"), _t("Confirme a senha de administrador para conectar ao Google Drive."))
    r = subprocess.run(["pkexec", "pacman", "-S", "--needed", "--noconfirm", "rclone"], capture_output=True, text=True)
    return r.returncode == 0 and bool(rclone_bin())


def _token_acesso():
    try:
        dump = json.loads(rc("config", "dump").stdout)
        tok = json.loads(dump[NOME_REMOTO]["token"])
        return tok.get("access_token")
    except Exception:
        return None


def descobrir_usuario():
    """Nome e e-mail da conta Google (about.get do Drive com o token do rclone)."""
    if os.environ.get("CONTA_REMOTO"):
        return {"email": "teste@local", "nome": _t("Teste")}
    rc("about", f"{NOME_REMOTO}:", check=False, timeout=60)  # renova o token se preciso
    tok = _token_acesso()
    if not tok:
        return {}
    req = urllib.request.Request("https://www.googleapis.com/drive/v3/about?fields=user",
                                 headers={"Authorization": f"Bearer {tok}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            u = json.load(r).get("user", {})
        return {"email": u.get("emailAddress", ""), "nome": u.get("displayName", ""), "foto": u.get("photoLink", "")}
    except Exception:
        return {}


def obter_cota_drive(forcado=False, somente_cache=False):
    """Consulta cota real do Google Drive via rclone about com cache de 15 minutos."""
    agora = time.time()
    if somente_cache:
        return ler_json(COTA, {})
    if not forcado and COTA.exists():
        try:
            d = json.loads(COTA.read_text())
            if agora - d.get("timestamp", 0) < 900 and d.get("total"):
                return d
        except Exception:
            pass
    if not conectado() or not rclone_bin():
        return {}
    try:
        r = rc("about", f"{NOME_REMOTO}:", "--json", timeout=12)
        d = json.loads(r.stdout)
        d["timestamp"] = agora
        COTA.parent.mkdir(parents=True, exist_ok=True)
        COTA.write_text(json.dumps(d))
        return d
    except Exception:
        if COTA.exists():
            try:
                return json.loads(COTA.read_text())
            except Exception:
                pass
    return {}


def listar_pacotes_detalhes(c=None):
    """Lista todos os pacotes/programas instalados com nomes amigáveis e descrições."""
    if c is None:
        c = config()
    cache_arq = CACHE / "pacotes-info.json"
    agora = time.time()
    itens = []
    if cache_arq.exists():
        try:
            d = json.loads(cache_arq.read_text())
            if agora - d.get("timestamp", 0) < 300:  # cache de 5 min
                itens = d.get("itens", [])
        except Exception:
            pass

    if not itens:
        desktop_map = {}
        for d_path in [Path("/usr/share/applications"), HOME / ".local/share/applications"]:
            if d_path.is_dir():
                for p in d_path.glob("*.desktop"):
                    try:
                        content = p.read_text(errors="ignore")
                        nome_app, exec_app = "", ""
                        for line in content.splitlines():
                            if line.startswith("Name=") and not nome_app:
                                nome_app = line[5:].strip()
                            elif line.startswith("Exec=") and not exec_app:
                                exec_app = line[5:].split()[0].split("/")[-1].strip()
                        stem = p.stem.lower()
                        if nome_app:
                            desktop_map[stem] = nome_app
                            if exec_app:
                                desktop_map[exec_app.lower()] = nome_app
                    except Exception:
                        pass

        aur_set = set(subprocess.run(["pacman", "-Qqem"], capture_output=True, text=True).stdout.split())
        pacman_out = subprocess.run(["pacman", "-Qei"], capture_output=True, text=True).stdout

        cur = {}
        for line in pacman_out.splitlines():
            if not line.strip():
                if "Nome" in cur or "Name" in cur:
                    pkg_id = cur.get("Nome") or cur.get("Name")
                    desc = cur.get("Descrição") or cur.get("Description") or ""
                    friendly = desktop_map.get(pkg_id.lower())
                    if not friendly and pkg_id.endswith("-bin"):
                        friendly = desktop_map.get(pkg_id[:-4].lower())
                    if not friendly and pkg_id.endswith("-git"):
                        friendly = desktop_map.get(pkg_id[:-4].lower())
                    itens.append({
                        "id": pkg_id,
                        "nome": friendly or pkg_id,
                        "desc": desc,
                        "tipo": "aur" if pkg_id in aur_set else "pacman"
                    })
                cur = {}
                continue
            if ":" in line:
                k, v = line.split(":", 1)
                cur[k.strip()] = v.strip()

        if "Nome" in cur or "Name" in cur:
            pkg_id = cur.get("Nome") or cur.get("Name")
            desc = cur.get("Descrição") or cur.get("Description") or ""
            friendly = desktop_map.get(pkg_id.lower())
            itens.append({
                "id": pkg_id,
                "nome": friendly or pkg_id,
                "desc": desc,
                "tipo": "aur" if pkg_id in aur_set else "pacman"
            })

        # Flatpaks instalados
        if shutil.which("flatpak"):
            try:
                fp_out = subprocess.run(["flatpak", "list", "--app", "--columns=application,name,description"], capture_output=True, text=True).stdout
                for l in fp_out.splitlines():
                    parts = [p.strip() for p in l.split("\t") if p.strip()]
                    if len(parts) >= 2 and parts[0] not in ("ID de aplicativo", "Application ID"):
                        itens.append({
                            "id": parts[0],
                            "nome": parts[1],
                            "desc": parts[2] if len(parts) > 2 else "",
                            "tipo": "flatpak"
                        })
            except Exception:
                pass

        itens.sort(key=lambda x: x["nome"].lower())
        cache_arq.parent.mkdir(parents=True, exist_ok=True)
        try:
            cache_arq.write_text(json.dumps({"timestamp": agora, "itens": itens}))
        except Exception:
            pass

    modo = c.get("pacotes_modo", "todos")
    selecionados_set = set(c.get("pacotes_selecionados", []))

    res = []
    for it in itens:
        sel = True if modo == "todos" or not selecionados_set else (it["id"] in selecionados_set)
        res.append({
            "id": it["id"],
            "nome": it["nome"],
            "desc": it["desc"],
            "tipo": it["tipo"],
            "selecionado": sel
        })
    return res, modo


def cmd_pacotes_modo(a):
    c = config()
    c["pacotes_modo"] = a.modo
    if a.modo == "escolher" and not c.get("pacotes_selecionados"):
        itens, _ = listar_pacotes_detalhes(c)
        c["pacotes_selecionados"] = [it["id"] for it in itens]
    salvar_config(c)
    print(json.dumps({"modo": c["pacotes_modo"], "qtd": len(c.get("pacotes_selecionados", []))}))
    return 0


def cmd_pacotes_selecionar(a):
    c = config()
    if a.modo:
        c["pacotes_modo"] = a.modo
    if getattr(a, "json_ids", None):
        c["pacotes_selecionados"] = json.loads(a.json_ids)
    elif getattr(a, "ids", None) is not None:
        c["pacotes_selecionados"] = [x.strip() for x in a.ids.split(",") if x.strip()]
    salvar_config(c)
    print(json.dumps({"modo": c.get("pacotes_modo", "todos"), "qtd": len(c.get("pacotes_selecionados", []))}))
    return 0


def cmd_pacotes_listar(_a):
    c = config()
    itens, modo = listar_pacotes_detalhes(c)
    qtd_sel = len([x for x in itens if x["selecionado"]]) if modo == "escolher" else len(itens)
    print(json.dumps({
        "modo": modo,
        "total": len(itens),
        "selecionados_qtd": qtd_sel,
        "itens": itens
    }, ensure_ascii=False))
    return 0


def face_nosso():
    return FACE.is_symlink() and os.readlink(FACE) == str(FOTO)


def baixar_foto(link):
    """Baixa a foto de perfil (256 px) e liga ~/.face a ela."""
    if not link:
        return False
    link = re.sub(r"=s\d+(-c)?$", "", link) + "=s256-c"
    FOTO.parent.mkdir(parents=True, exist_ok=True)
    tmp = FOTO.with_suffix(".tmp")
    try:
        with urllib.request.urlopen(link, timeout=20) as r, open(tmp, "wb") as f:
            f.write(r.read())
        if tmp.stat().st_size < 100:
            raise ValueError(_t("imagem vazia"))
        tmp.replace(FOTO)
    except Exception:  # noqa: BLE001
        tmp.unlink(missing_ok=True)
        return False
    if face_nosso() or not (FACE.exists() or FACE.is_symlink()):
        FACE.unlink(missing_ok=True)
        FACE.symlink_to(FOTO)
    return True


def apagar_foto():
    if face_nosso():
        FACE.unlink()
    FOTO.unlink(missing_ok=True)


def cmd_foto(_a):
    if not conectado():
        return 1
    u = descobrir_usuario()
    return 0 if baixar_foto(u.get("foto", "")) else 1


def configurar_cripto(senha):
    obsc = rc("obscure", "-", entrada=senha).stdout.strip()
    sal = rc("obscure", "-", entrada=senha[::-1] + "simba-conta").stdout.strip()
    # Escrito direto no rclone.conf: nada de senha na linha de comando (visível no ps).
    arq = Path(rc("config", "file").stdout.strip().splitlines()[-1])
    arq.parent.mkdir(parents=True, exist_ok=True)
    texto = arq.read_text() if arq.exists() else ""
    texto = texto.rstrip("\n") + f"\n\n[{NOME_CRIPTO}]\ntype = crypt\nremote = {remoto_base()}/dados-cripto\n" \
        f"password = {obsc}\npassword2 = {sal}\n"
    arq.write_text(texto.lstrip("\n"))
    os.chmod(arq, 0o600)


def ler_senha(valor):
    return sys.stdin.readline().rstrip("\n") if valor == "-" else valor


# Janela do login do Google: app do navegador (--app) com a classe "<navegador>-127.0.0.1__…",
# flutuante e no centro — antes abria uma aba lado a lado, escondida atrás da janela (flutuante)
# das boas-vindas, e parecia que o navegador demorava a abrir. A regra também está em
# /usr/share/simba/default/hypr/apps/browser.lua; aqui vale para sessões abertas antes dela.
CLASSE_LOGIN = r"^(brave|chrome|chromium|google-chrome|microsoft-edge|vivaldi|helium)-127\.0\.0\.1__.*$"
REGRA_LOGIN = ('hl.window_rule({ match = { class = "%s" }, float = true, center = true, '
               'size = { 560, 690 }, tag = "-chromium-based-browser" })' % CLASSE_LOGIN.replace("\\", "\\\\"))


def _hypr(*args, timeout=3):
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or not shutil.which("hyprctl"):
        return None
    try:
        return subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None


def _janela_login():
    r = _hypr("clients", "-j")
    try:
        for cl in json.loads(r.stdout) if r else []:
            if re.match(CLASSE_LOGIN, cl.get("class") or ""):
                return cl.get("address")
    except ValueError:
        pass
    return None


def _navegador_chromium():
    """Executável do navegador padrão, se for da família Chromium (aceita --app=)."""
    d = ""
    # simba-cmd-default-browser resolve o simba-browser.desktop (o padrão do xdg) no navegador real
    for cmd in (["simba-cmd-default-browser"], ["xdg-settings", "get", "default-web-browser"]):
        if not shutil.which(cmd[0]):
            continue
        try:
            d = subprocess.run(cmd, capture_output=True, text=True, timeout=3).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            d = ""
        if d:
            break
    if not re.match(r"(brave|chromium|google-chrome|microsoft-edge|vivaldi|helium)", d):
        return None
    for base in (HOME / ".local/share/applications", Path("/usr/share/applications")):
        f = base / d
        if f.is_file():
            m = re.search(r"^Exec=(\S+)", f.read_text(errors="replace"), re.M)
            if m and shutil.which(m.group(1)):
                return m.group(1)
    return None


def abrir_login(url):
    """Abre o login do Google numa janela própria, na frente, e a deixa em foco."""
    _hypr("eval", REGRA_LOGIN)
    nav = _navegador_chromium()
    try:
        if nav and shutil.which("simba-launch-webapp"):
            subprocess.Popen(["simba-launch-webapp", url], start_new_session=True,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            cmd = ["simba-launch-browser", url] if shutil.which("simba-launch-browser") else ["/usr/bin/xdg-open", url]
            subprocess.Popen(cmd, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return

    def focar():
        for _ in range(60):          # até 30 s (navegador ainda fechado demora a subir)
            end = _janela_login()
            if end:
                _hypr("dispatch", f'hl.dsp.focus({{ window = "address:{end}" }})')
                return
            time.sleep(0.5)
    import threading
    threading.Thread(target=focar, daemon=True).start()


def fechar_login():
    """Login concluído: fecha a janela do login e devolve o foco às boas-vindas/Configurações."""
    end = _janela_login()
    if end:
        _hypr("dispatch", f'hl.dsp.window.close({{ window = "address:{end}" }})')
    r = _hypr("clients", "-j")
    try:
        for cl in json.loads(r.stdout) if r else []:
            if cl.get("class") in ("com.simba.BoasVindas", "com.simba.Configuracoes", "configuracoes"):
                _hypr("dispatch", f'hl.dsp.focus({{ window = "address:{cl.get("address")}" }})')
                break
    except ValueError:
        pass


# Credenciais OAuth do próprio Simba OS no Google Cloud (app "Desktop", só drive.file). O
# client_id compartilhado do rclone está sendo desativado pelo Google em 2026: sem um próprio,
# o login e a sincronização param. O segredo de um app de computador não é secreto (vai em
# todo app instalado); o que protege a conta de cada pessoa é o login dela.
# Formato: {"client_id": "...apps.googleusercontent.com", "client_secret": "..."}
CREDENCIAIS = [HOME / ".config/conta/google-oauth.json", Path("/usr/share/simba-apps/conta/google-oauth.json")]


def credenciais_google():
    for f in CREDENCIAIS:
        d = ler_json(f, {})
        if d.get("client_id") and d.get("client_secret"):
            return [f"client_id={d['client_id']}", f"client_secret={d['client_secret']}"]
    return []


def usa_client_id_compartilhado():
    """Conectado com o client_id do rclone (vazio no remoto) e o Simba já tem o próprio."""
    if not credenciais_google() or os.environ.get("CONTA_REMOTO"):
        return False
    try:
        dump = json.loads(rc("config", "dump", check=False).stdout or "{}")
    except ValueError:
        return False
    remoto = dump.get(NOME_REMOTO) or {}
    return bool(remoto) and not remoto.get("client_id")


def login_drive():
    """rclone espera a autorização; quem abre a página é o abrir_login (o rclone chamaria o
    xdg-open, que abre uma aba comum). O link também fica no estado (botão na interface)."""
    log = CACHE / "login.log"
    CACHE.mkdir(parents=True, exist_ok=True)
    # xdg-open falso só para o rclone: a página é aberta aqui, assim que o link aparece
    falso = CACHE / "sem-navegador"
    falso.mkdir(parents=True, exist_ok=True)
    (falso / "xdg-open").write_text("#!/bin/sh\nexit 0\n")
    (falso / "xdg-open").chmod(0o755)
    env = dict(os.environ, PATH=f"{falso}:{os.environ.get('PATH', '/usr/bin')}")
    # o rclone escreve a configuração (com o token do Google) na saída: o log é só do dono
    # e é apagado no fim — antes ficava legível por todos em ~/.cache/conta/login.log
    log.unlink(missing_ok=True)
    with open(os.open(log, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        p = subprocess.Popen([rclone_bin(), "config", "create", NOME_REMOTO, "drive", "scope=drive.file",
                              *credenciais_google(), "config_is_local=true"],
                             stdout=f, stderr=subprocess.STDOUT, text=True, env=env)
    fim = time.time() + 600
    aberto = False
    while p.poll() is None and time.time() < fim:
        m = re.search(r"(http://127\.0\.0\.1:53682/auth\?state=\S+)", log.read_text(errors="replace"))
        if m and estado().get("link_login") != m.group(1):
            salvar_estado(link_login=m.group(1))
        if m and not aberto:
            aberto = True
            abrir_login(m.group(1))
        time.sleep(0.15)
    if p.poll() is None:
        p.kill()
    if p.returncode != 0:
        # Falhou (prazo, login cancelado, Google recusou): guarda o motivo, sem nada de token
        # (só existe token quando dá certo), e fecha a janela — aberta, ela apontava para um
        # 127.0.0.1 que já não respondia ("conexão recusada").
        try:
            linhas = [l for l in log.read_text(errors="replace").splitlines()
                      if "token" not in l.lower() and "secret" not in l.lower()]
            erro = CACHE / "login-erro.log"
            erro.unlink(missing_ok=True)
            with open(os.open(erro, os.O_WRONLY | os.O_CREAT, 0o600), "w") as f:
                f.write("\n".join(linhas[-30:]) + "\n")
        except OSError:
            pass
    log.unlink(missing_ok=True)
    fechar_login()
    return p.returncode if p.returncode is not None else 1


def cmd_entrar(a):
    if a.cripto == "-":
        a.cripto = sys.stdin.readline().rstrip("\n")
    salvar_estado(entrando=True, erro="", link_login="")
    if not conectado():
        # Login novo: a pasta do Drive pode ser outra (outra conta, ou o acesso novo do Simba,
        # que não enxerga a pasta criada pelo acesso antigo do rclone): mescla tudo de novo.
        resetar_estado_nuvem()
        if not getattr(a, "manter_escolha", False):
            # Login novo: pergunta o que sincronizar antes de enviar qualquer coisa.
            c0 = config()
            c0["escolha_feita"] = False
            salvar_config(c0)
    try:
        if not instalar_rclone():
            salvar_estado(entrando=False, erro=_t("Não foi possível instalar o rclone (senha cancelada?)."))
            avisar(_t("Não foi possível entrar"), _t("O rclone não foi instalado."), True)
            return 1
        if not conectado():
            # Abre o navegador no login do Google e espera a autorização.
            r = login_drive()
            if r != 0 or not conectado():
                salvar_estado(entrando=False, erro=_t("Login cancelado ou não concluído."))
                rc("config", "delete", NOME_REMOTO, check=False)
                avisar(_t("Login não concluído"), _t("Tente de novo em Configurações › Contas."), True)
                return 1
        c = config()
        u = descobrir_usuario()
        baixar_foto(u.pop("foto", ""))
        c.update({k: v for k, v in u.items() if v})
        # Backup já existente nesta conta? Herda a criptografia dele.
        meta = remoto_meta()
        if meta.get("cripto") and not a.cripto:
            c["cripto"] = True
            salvar_config(c)
            salvar_estado(entrando=False, remoto_meta=meta, erro=_t("Este backup é criptografado: informe a senha para restaurar."))
            return 0
        if a.cripto:
            configurar_cripto(ler_senha(a.cripto))
            c["cripto"] = True
        salvar_config(c)
        salvar_estado(entrando=False, remoto_meta=meta, link_login="")
        if meta and not pode_enviar():
            salvar_estado(remoto_meta=meta)
        BOAS_VINDAS.unlink(missing_ok=True)
        if not c.get("escolha_feita"):
            # Nada é enviado nem ligado até a pessoa escolher o que sincronizar.
            subprocess.run(["systemctl", "--user", "disable", "--now", "conta-sync.timer"], capture_output=True)
            avisar(_t("Conta conectada"), _t("Agora escolha o que sincronizar em Configurações › Contas."))
            if not os.environ.get("CONTA_HOME") and not _boas_vindas_aberta():
                subprocess.Popen(["configuracoes", "contas"], start_new_session=True,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return 0
        if pode_enviar():
            cmd_auto(type("A", (), {"modo": "liga"})())
        avisar(_t("Conta conectada"), c.get("email") or _t("Google Drive"))
        try:
            subprocess.run(["systemctl", "--user", "enable", "--now", "conta-fundo.service"],
                           capture_output=True, timeout=10)
            fundo_puxar(c)
            fundo_enviar(c, inicio=True)
        except Exception:
            pass
        return 0
    except Exception as e:  # noqa: BLE001
        salvar_estado(entrando=False, erro=str(e)[-300:])
        return 1


def resetar_estado_nuvem():
    """Esquece o que foi combinado com a pasta do Drive anterior (bisync, lista de pastas,
    papel de parede, ferramenta publicada): a próxima sincronização mescla do zero."""
    shutil.rmtree(BISYNC_DIR, ignore_errors=True)
    FUNDO_ESTADO.unlink(missing_ok=True)
    salvar_estado(bisync_iniciadas=[], pastas_unidas=False, pastas_alteradas=False,
                  ferramenta_publicada="", ultimo_backup_config="", base_fundo="",
                  ultima_remota_aplicada="", remoto_meta={}, conflito=None, precisa_decidir=False)


def cmd_reconectar(_a):
    """Troca o acesso ao Google (ex.: do client_id do rclone para o do Simba) mantendo as
    escolhas: esquece o login, abre o login de novo e sincroniza tudo na pasta nova."""
    for n in (NOME_REMOTO, NOME_CRIPTO):
        rc("config", "delete", n, check=False)
    r = cmd_entrar(type("A", (), {"cripto": "", "manter_escolha": True})())
    if r == 0 and conectado() and config().get("escolha_feita"):
        if pode_enviar():
            cmd_auto(type("A", (), {"modo": "liga"})())
        subprocess.Popen(["/usr/bin/conta", "sincronizar", "--silencioso"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return r


def cmd_senha(a):
    """Define a senha de um backup criptografado já existente (máquina nova)."""
    rc("config", "delete", NOME_CRIPTO, check=False)
    configurar_cripto(ler_senha(a.senha))
    try:
        rc("lsf", remoto_dados(), "--max-depth", "1", timeout=120)
        rc("cat", f"{remoto_dados()}/extra/meta.json", timeout=120)
    except Exception:
        rc("config", "delete", NOME_CRIPTO, check=False)
        print(_t("senha incorreta"), file=sys.stderr)
        return 1
    c = config()
    c["cripto"] = True
    salvar_config(c)
    salvar_estado(erro="")
    return 0


def remoto_meta():
    try:
        return json.loads(rc("cat", f"{remoto_base()}/meta.json", timeout=60).stdout)
    except Exception:
        return {}


def cmd_sair(_a):
    for n in (NOME_REMOTO, NOME_CRIPTO):
        rc("config", "delete", n, check=False)
    c = config()
    for k in ("email", "nome", "pacotes_modo", "pacotes_selecionados"):
        c.pop(k, None)
    c["cripto"] = False
    c["escolha_feita"] = False
    salvar_config(c)
    apagar_foto()
    remover_pasta_local()
    if COTA.exists():
        try:
            COTA.unlink()
        except Exception:
            pass
    subprocess.run(["systemctl", "--user", "disable", "--now", "conta-fundo.service"], capture_output=True)
    subprocess.run(["systemctl", "--user", "disable", "--now", "conta-sync.timer"], capture_output=True)
    salvar_estado(resultado="", erro="", remoto_meta={})
    return 0


_UNIDADE = {"B": "B", "KiB": "KB", "MiB": "MB", "GiB": "GB", "TiB": "TB"}


def _legivel(linha):
    """'2026/11/02 12:26:41 INFO  :  63.479 MiB / 69.206 MiB, 92%, 5.643 KiB/s, ETA 17m19s (xfr#…'
    → '63 MB de 69 MB (92%) · faltam 17 min'"""
    m = re.search(r"([\d.]+)\s*(\w?i?B)\s*/\s*([\d.]+)\s*(\w?i?B),\s*(\d+)%(?:.*?ETA\s*([\w-]+))?", linha)
    if not m:
        return linha.split("Transferred:")[-1].strip()[:90]
    feito, u1, total, u2, pct, eta = m.groups()
    def n(v, u):
        v = f"{float(v):.1f}".replace(".", _DEC) if u in ("GiB", "TiB") else f"{float(v):.0f}"
        return f"{v} {_UNIDADE.get(u, u)}"
    txt = f"{n(feito, u1)} de {n(total, u2)} ({pct}%)"
    # Muitos arquivos pequenos: no Drive o tempo depende mais da contagem que dos bytes.
    x = re.search(r"xfr#(\d+)/(\d+)", linha)
    if x:
        return _t("%1 de %2 arquivos · %3", x.group(1), x.group(2), txt)
    if eta and eta != "-":
        h = re.search(r"(\d+)h", eta); mi = re.search(r"(\d+)m(?!s)", eta)
        if h:
            txt += _t(" · faltam %1 h %2 min", h.group(1), mi.group(1) if mi else 0)
        elif mi:
            txt += _t(" · faltam %1 min", mi.group(1))
        else:
            txt += _t(" · menos de 1 min")
    return txt


def _progresso(proc, rotulo):
    ultimo = 0
    for linha in proc.stderr:
        linha = linha.strip()
        if "Transferred:" in linha or "%" in linha and "ETA" in linha:
            if time.time() - ultimo > 1:
                salvar_estado(progresso=f"{rotulo}: {_legivel(linha)}")
                ultimo = time.time()
    return proc.wait()


def limpar_lixeira(dados):
    """Apaga do Drive as pastas lixeira/<AAAAMMDD-HHMMSS> com mais de 30 dias.
    Antes era `rclone delete --min-age 30d`, que percorria a lixeira inteira e
    passava de 10 min (derrubando o backup). Agora só lista as pastas do topo.
    Nunca faz o backup falhar."""
    try:
        r = rc("lsf", "--dirs-only", f"{dados}/lixeira", check=False, timeout=120)
        limite = datetime.datetime.now() - datetime.timedelta(days=30)
        for nome in r.stdout.split():
            nome = nome.rstrip("/")
            try:
                data = datetime.datetime.strptime(nome, "%Y%m%d-%H%M%S")
            except ValueError:
                continue
            if data < limite:
                rc("purge", f"{dados}/lixeira/{nome}", check=False, timeout=300)
    except Exception as e:  # noqa: BLE001
        print(_t("limpeza da lixeira ignorada: %1", e), file=sys.stderr)


def publicar_ferramenta():
    """Restaurador e a própria ferramenta, sem criptografia, na raiz da pasta (só quando mudam)."""
    base = FERRAMENTA.parent
    marca = f"{_hash_arquivo(FERRAMENTA)}"
    if estado().get("ferramenta_publicada") == marca:
        return
    rc("copyto", str(base / "Restaurar-Simba.sh"), f"{remoto_base()}/Restaurar-Simba.sh")
    rc("copyto", str(FERRAMENTA), f"{remoto_base()}/ferramenta/conta.py")
    leia = base / _t("LEIA-ME.txt")
    if leia.exists():
        rc("copyto", str(leia), f"{remoto_base()}/LEIA-ME.txt")
    salvar_estado(ferramenta_publicada=marca)


def pode_enviar():
    """Permite sincronização contínua. Se o usuário já confirmou a escolha das pastas
    ou se já sincronizou antes, o envio é liberado sem bloquear a máquina."""
    c = config()
    if c.get("escolha_feita"):
        return True
    e = estado()
    if e.get("ultima") or e.get("restaurado") or e.get("ultima_remota_aplicada"):
        return True
    return not remoto_meta()


def nome_maquina():
    return os.environ.get("CONTA_MAQUINA") or socket.gethostname()   # CONTA_MAQUINA: testes


def _hash_arquivo(p):
    """Identidade do papel de parede pelo conteúdo (o caminho muda de uma máquina para outra)."""
    import hashlib
    h = hashlib.sha256()
    try:
        with open(p, "rb") as f:
            h.update(f.read(64 * 1024 * 1024))
    except OSError:
        return ""
    return h.hexdigest()[:20]


def _fundo_local():
    try:
        img = (HOME / ".local/state/simba/current/background").resolve(strict=True)
        return img, _hash_arquivo(img)
    except OSError:
        return None, ""


def _tema_local():
    arq = HOME / ".local/state/simba/current/theme.name"
    return arq.read_text().strip() if arq.exists() else ""


def _decidir(local, remoto, base, remoto_mais_novo):
    """Sincronização em três vias (como o git): base = último valor combinado entre esta
    máquina e o Drive. Só o Drive mudou → aplicar; só aqui mudou → enviar; os dois mudaram para
    valores diferentes → conflito. Antes comparava só local × remoto e via \"conflito\" a cada
    troca feita em outra máquina (e podia desfazer a troca)."""
    if not remoto or local == remoto:
        return "igual"
    if base is None:                      # nunca combinamos: vale o mais novo
        return "aplicar" if remoto_mais_novo else "enviar"
    if remoto == base:
        return "enviar"
    if local == base:
        return "aplicar"
    return "conflito"


def marcar_base_enviada():
    """Depois de enviar: o que está aqui passa a ser a base combinada."""
    _img, h = _fundo_local()
    salvar_estado(base_fundo=h, base_tema=_tema_local())


def puxar_alteracoes_remotas(silencioso=False, forcar=False):
    """Verifica se há alterações novas no Google Drive enviadas por outra máquina
    (ex.: papel de parede alterado no notebook) e aplica dinamicamente."""
    if not conectado():
        return False

    pausado, ate = esta_pausado()
    if pausado and not forcar:
        if not silencioso:
            print(_t("Sincronização pausada pelo Modo Viagem até %1.", ate))
        return False

    salvar_estado(sincronizando=True)
    try:
        # Se havia favoritos do navegador aguardando o fechamento do Brave, tenta aplicar
        aplicar_brave_se_pendente()

        meta_remoto = remoto_meta()
        if not meta_remoto or not meta_remoto.get("data"):
            return False

        data_remota = meta_remoto.get("data")
        maquina_remota = meta_remoto.get("maquina", "")
        maquina_local = nome_maquina()

        e = estado()
        ultima_aplicada = e.get("ultima_remota_aplicada", "")
        ultima_local = e.get("ultima", "")

        # Mesma máquina: o que está no Drive é o nosso próprio envio
        if not forcar and maquina_remota == maquina_local:
            return False

        # Se já aplicamos esta versão remota anteriormente
        if not forcar and data_remota == ultima_aplicada:
            return False


        c = config()
        dados = remoto_dados(c)
        mudancas = []

        # 1–2. Papel de parede e tema: decisão em três vias (ver _decidir)
        img_local, fundo_local = _fundo_local()
        fundo_remoto = meta_remoto.get("fundo_hash") or ""
        tema_local, tema_remoto = _tema_local(), meta_remoto.get("tema") or ""
        mais_novo = bool(data_remota and (not ultima_local or data_remota > ultima_local))
        if forcar:                                    # "usar a versão da nuvem"
            d_fundo = "aplicar" if fundo_remoto and fundo_remoto != fundo_local else "igual"
            d_tema = "aplicar" if tema_remoto and tema_remoto != tema_local else "igual"
        else:
            d_fundo = _decidir(fundo_local, fundo_remoto, e.get("base_fundo"), mais_novo)
            d_tema = _decidir(tema_local, tema_remoto, e.get("base_tema"), mais_novo)
        # O papel de parede tem canal próprio e imediato (conta fundo vigiar, fundo.json no
        # Drive); o meta.json daqui é de até 20 min atrás e desfaria a troca mais nova.
        d_fundo = "ignorar"
        if "conflito" in (d_fundo, d_tema):
            conflito_info = {
                "maquina_remota": maquina_remota, "data_remota": data_remota, "data_local": ultima_local,
                "tema_remoto": tema_remoto, "tema_local": tema_local,
                "fundo_remoto": meta_remoto.get("fundo", ""), "fundo_local": str(img_local or ""),
            }
            salvar_estado(conflito=conflito_info)
            avisar(_t("Simba Conta — Conflito"),
                   _t("Alterações em %1 concorrem com as locais. Abra as Configurações para escolher.", maquina_remota))
            if not silencioso:
                print(_t("Conflito detectado entre %1 e a máquina local.", maquina_remota))
            return False

        if d_fundo == "aplicar":
            alvo = None
            original = Path(meta_remoto.get("fundo") or "")
            if original.name and original.is_file() and _hash_arquivo(original) == fundo_remoto:
                alvo = original                       # imagem que existe aqui também (do sistema)
            else:
                destino = HOME / ".local/share/conta/fundo"
                destino.mkdir(parents=True, exist_ok=True)
                try:
                    rc("copy", f"{dados}/extra/fundo", str(destino), check=False, timeout=60)
                    alvo = next((f for f in destino.iterdir() if f.is_file() and _hash_arquivo(f) == fundo_remoto), None)
                except (subprocess.SubprocessError, OSError):
                    alvo = None
            if alvo:
                _aplicar_fundo(alvo)
                mudancas.append(_t("papel de parede"))
                salvar_estado(base_fundo=fundo_remoto)
        elif d_fundo == "igual" and fundo_remoto:
            salvar_estado(base_fundo=fundo_remoto)

        if d_tema == "aplicar" and shutil.which("simba-theme-set") and not os.environ.get("CONTA_HOME"):
            try:
                subprocess.run(["simba-theme-set", tema_remoto], capture_output=True, timeout=60)
                mudancas.append(_t("tema (%1)", tema_remoto))
                salvar_estado(base_tema=tema_remoto)
            except (subprocess.SubprocessError, OSError):
                pass
        elif d_tema == "aplicar" and os.environ.get("CONTA_HOME"):
            # testes: grava o nome do tema (o que simba-theme-set faria), sem trocar a tela
            (HOME / ".local/state/simba/current").mkdir(parents=True, exist_ok=True)
            (HOME / ".local/state/simba/current/theme.name").write_text(tema_remoto + "\n")
            mudancas.append(_t("tema (%1)", tema_remoto))
            salvar_estado(base_tema=tema_remoto)
        elif d_tema == "igual" and tema_remoto:
            salvar_estado(base_tema=tema_remoto)

        # 3. Sincronização dinâmica de Favoritos / Atalhos do Navegador (Brave/Simba)
        brave_remoto = meta_remoto.get("brave")
        if brave_remoto and config().get("categorias", {}).get("historico", True):
            destino_temp = HOME / ".local/share/conta/brave-remoto"
            destino_temp.mkdir(parents=True, exist_ok=True)
            try:
                r = rc("copy", f"{dados}/extra/brave", str(destino_temp), check=False, timeout=30)
                if r and r.returncode == 0:
                    bm_remoto = destino_temp / "Bookmarks"
                    bm_local = BRAVE / "Bookmarks"
                    difere = False
                    if bm_remoto.exists():
                        if not bm_local.exists() or bm_remoto.read_bytes() != bm_local.read_bytes():
                            difere = True
                    if difere:
                        if _brave_aberto():
                            pendente = HOME / ".local/share/conta/brave-pendente"
                            if pendente.exists():
                                shutil.rmtree(pendente, ignore_errors=True)
                            shutil.copytree(destino_temp, pendente)
                            avisar(_t("Simba Conta — Navegador"),
                                   _t("Novos favoritos recebidos de %1. Eles serão aplicados quando você fechar o navegador.", maquina_remota or _t("outra máquina")))
                            mudancas.append(_t("favoritos do navegador (pendente)"))
                        else:
                            guarda = HOME / ".local/share/conta/antes-da-restauracao" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                            _restaurar_brave(destino_temp, guarda)
                            mudancas.append(_t("favoritos do navegador"))
            except (subprocess.TimeoutExpired, Exception):
                pass

        # 4. Salva carimbo da sincronização remota e limpa conflito se resolvido
        salvar_estado(ultima_remota_aplicada=data_remota, remoto_meta=meta_remoto, conflito=None)

        if mudancas:
            resumo = ", ".join(mudancas)
            avisar(_t("Simba Conta — Nuvem"),
                   _t("Alterações sincronizadas a partir de %1: %2.", maquina_remota or _t("outra máquina"), resumo))
            if not silencioso:
                print(_t("Alterações sincronizadas com sucesso (%1).", resumo))
            return True
        else:
            if not silencioso:
                print(_t("Nenhuma alteração pendente de outra máquina."))
            return False

    except Exception as exc:
        if not silencioso:
            print(_t("verificação remota falhou: %1", exc), file=sys.stderr)
        return False
    finally:
        salvar_estado(sincronizando=False)


# ── papel de parede imediato entre máquinas ──────────────────────────────────
# Quem troca o papel envia na hora (imagem em dados/fundo-atual + fundo.json, pequeno, na
# pasta da conta); as outras máquinas leem o fundo.json a cada FUNDO_INTERVALO segundos.
# FUNDO_ESTADO = último papel combinado com o Drive (o enviado ou o recebido): evita
# reenviar o que acabou de chegar e devolver para a nuvem a troca de outra máquina.
FUNDO_ESTADO = HOME / ".local/state/conta/fundo.json"
# 60 s: com 10 s eram ~1000 chamadas por hora à API só para ler o fundo.json, o que
# estourava o limite do Google e derrubava também o backup. Quem troca o papel envia na hora.
FUNDO_INTERVALO = int(os.environ.get("CONTA_FUNDO_INTERVALO") or 60)
FUNDO_MAX = 60 * 1024 * 1024
FUNDO_LINK = HOME / ".local/state/simba/current/background"


def _fundo_remoto_info():
    r = rc("cat", f"{remoto_base()}/fundo.json", check=False, timeout=90)
    if r.returncode != 0:
        if "not found" in (r.stderr or "").lower() or "doesn't exist" in (r.stderr or "").lower():
            return {}
        raise RuntimeError((r.stderr or "").strip()[-300:] or "rclone cat fundo.json falhou")
    try:
        v = json.loads(r.stdout or "{}")
    except ValueError:
        return {}
    return v if isinstance(v, dict) else {}


def _id_maquina():
    if os.environ.get("CONTA_MAQUINA"):        # testes
        return os.environ["CONTA_MAQUINA"]
    try:
        return Path("/etc/machine-id").read_text().strip()[:16] or nome_maquina()
    except OSError:
        return nome_maquina()


def fundo_enviar(c=None, inicio=False):
    c = c or config()
    img, h = _fundo_local()
    if not img or not h or not img.is_file() or img.stat().st_size > FUNDO_MAX:
        return False
    combinado = ler_json(FUNDO_ESTADO, {})
    if combinado.get("hash") == h:
        return False                       # já é o que está na nuvem (enviado ou recebido)
    # A nuvem também mudou desde o último acordo (outra máquina trocou)? Então as duas
    # trocaram: fica a troca mais recente.
    remoto_info = {}
    try:
        remoto_info = _fundo_remoto_info()
    except Exception:
        pass
    rh = remoto_info.get("hash") if remoto_info else None
    if rh and rh != h and rh != combinado.get("hash"):
        try:
            remoto_ts = datetime.datetime.fromisoformat(remoto_info.get("data", "")).timestamp()
        except Exception:
            remoto_ts = 0
        if remoto_ts > _fundo_mudou_em(img):
            fundo_puxar(c)
            return False
    tmp = CACHE / "fundo-envio"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    shutil.copy2(img, tmp / img.name)
    rc("sync", str(tmp), f"{remoto_dados(c)}/fundo-atual", timeout=600)
    shutil.rmtree(tmp, ignore_errors=True)
    info = {"hash": h, "nome": img.name, "original": str(img), "maquina": nome_maquina(),
            "id": _id_maquina(), "data": datetime.datetime.now().astimezone().isoformat(timespec="seconds")}
    rc("rcat", f"{remoto_base()}/fundo.json", entrada=json.dumps(info, ensure_ascii=False), timeout=60)
    gravar_json(FUNDO_ESTADO, info)
    salvar_estado(base_fundo=h)
    return True


def fundo_puxar(c=None):
    c = c or config()
    info = _fundo_remoto_info()
    h = info.get("hash")
    if not h:
        return False
    combinado = ler_json(FUNDO_ESTADO, {})
    if h == combinado.get("hash"):
        return False
    img_local, local = _fundo_local()
    if h == local or info.get("id") == _id_maquina():
        gravar_json(FUNDO_ESTADO, info)
        salvar_estado(base_fundo=h)
        return False
    # A nuvem mudou. Esta máquina só "ganha" se ELA TAMBÉM trocou desde o último acordo
    # (papel local diferente do combinado) e trocou depois. Antes comparava a data do link
    # do papel com a da nuvem: o link é recriado ao ligar/trocar tema, então a máquina
    # parada achava o próprio papel "mais novo", tentava enviar, via que já tinha enviado,
    # e nunca recebia a troca da outra.
    if local and combinado.get("hash") and local != combinado.get("hash"):
        try:
            remota_ts = datetime.datetime.fromisoformat(info.get("data", "")).timestamp()
        except (ValueError, TypeError):
            remota_ts = 0
        if _fundo_mudou_em(img_local) > remota_ts:
            fundo_enviar(c)
            return False
    alvo = None
    original = Path(info.get("original") or "")
    if original.name and original.is_file() and _hash_arquivo(original) == h:
        alvo = original                    # imagem que existe aqui também (papéis do sistema)
    else:
        destino = HOME / ".local/share/conta/fundo"
        destino.mkdir(parents=True, exist_ok=True)
        rc("copy", f"{remoto_dados(c)}/fundo-atual", str(destino), check=False, timeout=600)
        alvo = next((f for f in destino.iterdir() if f.is_file() and _hash_arquivo(f) == h), None)
        if alvo:                           # guarda só o atual
            for f in destino.iterdir():
                if f.is_file() and f != alvo:
                    f.unlink(missing_ok=True)
    if not alvo:
        return False
    gravar_json(FUNDO_ESTADO, info)        # antes de aplicar: a troca não volta para a nuvem
    salvar_estado(base_fundo=h)
    _aplicar_fundo(alvo)
    return True


def _fundo_mudou_em(img):
    """Quando o papel desta máquina foi trocado (visto pelo vigia; senão, a data do link)."""
    e = estado()
    if e.get("fundo_mudou_em") and e.get("fundo_mudou_link") == _link_fundo():
        return float(e["fundo_mudou_em"])
    try:
        return max(FUNDO_LINK.lstat().st_mtime, img.stat().st_mtime if img else 0)
    except OSError:
        return 0.0


def _fundo_ativo(c):
    return c.get("sincronizar_fundo", True) and c.get("escolha_feita") and not esta_pausado()[0] and conectado()


def _link_fundo():
    try:
        return os.readlink(FUNDO_LINK)
    except OSError:
        return ""


def cmd_fundo(a):
    if a.acao in ("liga", "desliga"):
        c = config()
        c["sincronizar_fundo"] = a.acao == "liga"
        salvar_config(c)
        return 0
    c = config()
    if a.acao == "enviar":
        return 0 if not _fundo_ativo(c) or fundo_enviar(c) else 0
    if a.acao == "puxar":
        return 0 if not _fundo_ativo(c) or fundo_puxar(c) else 0
    # vigiar: serviço do usuário (conta-fundo.service), leve: lê o link a cada 2 s e o
    # fundo.json da nuvem a cada FUNDO_INTERVALO s; não faz nada sem conta ou com a opção desligada.
    visto = _link_fundo()
    proxima = 0.0
    primeira = True
    espera_erro = FUNDO_INTERVALO
    while True:
        try:
            c = config()
            if c.get("sincronizar_fundo", True) and c.get("escolha_feita") and not esta_pausado()[0]:
                link = _link_fundo()
                if link != visto:
                    time.sleep(2)          # trocas seguidas: envia só a última
                    visto = _link_fundo()
                    salvar_estado(fundo_mudou_em=time.time(), fundo_mudou_link=visto)
                    if conectado():
                        fundo_enviar(c)
                if time.monotonic() >= proxima:
                    proxima = time.monotonic() + FUNDO_INTERVALO
                    if conectado():
                        if primeira:
                            # Ao ligar/iniciar: verifica e sincroniza quem definiu por último
                            fundo_puxar(c)
                            fundo_enviar(c, inicio=True)
                            primeira = False
                        else:
                            fundo_puxar(c)
                    visto = _link_fundo()
                    espera_erro = FUNDO_INTERVALO
        except Exception as exc:  # noqa: BLE001 — rede caiu, limite do Google etc.
            # Espera cada vez mais (até 15 min) em vez de insistir: insistir no limite
            # de uso só prolonga o bloqueio, para o papel e para o backup.
            espera_erro = min(900, espera_erro * 2)
            print(_t("papel de parede: %1", str(exc)[-200:].replace("\n", " ")), file=sys.stderr, flush=True)
            proxima = time.monotonic() + espera_erro
        time.sleep(2)


BACKUP_CONFIG_INTERVALO = 30 * 60


def _atualizar_timer():
    """Leva o intervalo novo para a cópia do timer em ~/.config (criada pelo `conta auto`)."""
    t = HOME / ".config/systemd/user/conta-sync.timer"
    if os.environ.get("CONTA_HOME") or not t.is_file():
        return
    try:
        if t.read_text() != TIMER:
            t.write_text(TIMER)
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, timeout=20)
            subprocess.run(["systemctl", "--user", "restart", "conta-sync.timer"], capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        pass


def cmd_sincronizar(a):
    if not conectado():
        print(_t("não conectado"), file=sys.stderr)
        return 0 if a.silencioso else 1  # timer de um clone ainda sem login: não é falha

    if precisa_escolher():
        if not a.silencioso:
            print(_t("Escolha primeiro o que sincronizar em Configurações › Contas."), file=sys.stderr)
        return 0
    if not any(v for k, v in config()["categorias"].items() if k in INCLUIR or k == "pacotes" or k == "pastas"):
        if not a.silencioso:
            print(_t("Nenhum item escolhido para o backup."), file=sys.stderr)
        return 0

    atualizar_pasta_local()

    # Modo Viagem (pausa temporária)
    pausado, ate = esta_pausado()
    if pausado and not getattr(a, "forcar", False) and not getattr(a, "substituir", False):
        if not a.silencioso:
            print(_t("Sincronização pausada pelo Modo Viagem até %1.", ate))
        return 0

    # Conexão limitada (dados móveis / hotspot do celular):
    # Se o timer rodar em conexão limitada, espaça para 2 horas para poupar a franquia
    limitada = rede_limitada()
    salvar_estado(rede_limitada=limitada)
    if limitada and not getattr(a, "forcar", False) and not a.substituir:
        e = estado()
        ultima_data_str = e.get("ultima")
        if ultima_data_str:
            try:
                ultima_dt = datetime.datetime.fromisoformat(ultima_data_str)
                agora = datetime.datetime.now(datetime.timezone.utc)
                if (agora - ultima_dt.astimezone(datetime.timezone.utc)).total_seconds() < 7200:
                    if not a.silencioso:
                        print(_t("Conexão limitada detectada (dados móveis). Sincronização espaçada para economizar dados."))
                    return 0
            except Exception:
                pass

    # Antes de enviar, confere se outra máquina publicou novidades (ex.: trocou wallpaper ou tema).
    # "Manter a versão deste computador" (substituir) não puxa nada: antes puxava com forcar e
    # aplicava a versão da nuvem antes de enviar, o contrário do que a pessoa escolheu.
    if not a.substituir:
        puxar_alteracoes_remotas(silencioso=a.silencioso, forcar=getattr(a, "forcar", False))
        if estado().get("conflito"):
            if not a.silencioso:
                print(_t("Há um conflito com outra máquina: escolha em Configurações › Contas antes de enviar."))
            return 0   # não envia: enviar agora apagaria a mudança da outra máquina

    # Aplica favoritos pendentes do navegador se o Brave foi fechado
    aplicar_brave_se_pendente()

    if not a.substituir and not pode_enviar():
        # Se ainda não escolheu, apenas aguarda a escolha
        if not config().get("escolha_feita"):
            return 0
        msg = _t("Aguardando configuração de sincronização.")
        salvar_estado(resultado="erro", erro=msg)
        return 4
    _atualizar_timer()
    if not estado().get("entrando"):
        (CACHE / "login.log").unlink(missing_ok=True)   # versões antigas deixavam o token nele
    with Trava():
        c = config()
        salvar_estado(progresso=_t("Preparando…"), erro="")
        try:
            ok_pastas, erro_pastas = sincronizar_pastas(c, a.silencioso)
            c = config()                      # a lista de pastas pode ter vindo da nuvem
            # O backup das configurações (milhares de arquivos) é pesado e não precisa ser
            # imediato: a cada 30 min, ou quando pedido à mão. As pastas vão a cada rodada.
            try:
                ultimo_cfg = datetime.datetime.fromisoformat(estado().get("ultimo_backup_config") or "").timestamp()
            except ValueError:
                ultimo_cfg = 0
            if a.silencioso and time.time() - ultimo_cfg < BACKUP_CONFIG_INTERVALO:
                if not ok_pastas:
                    raise RuntimeError(_t("pastas: %1", erro_pastas))
                agora = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
                salvar_estado(ultima=agora, resultado="ok", progresso="", erro="", falhas_seguidas=0)
                return 0
            lista, total = listar_arquivos(c)
            meta = preparar_extras(c, lista)
            CACHE.mkdir(parents=True, exist_ok=True)
            arq_lista = CACHE / "lista.txt"
            arq_lista.write_text("\n".join(lista) + "\n")
            # --fast-list: lista a pasta do Drive em poucas chamadas (antes, uma por pasta:
            # centenas a cada 20 min, o que estourava o limite de uso do Google).
            comuns = ["--skip-links", "--stats", "2s", "--stats-one-line", "-v", "--transfers", "4",
                      "--fast-list", "--tpslimit", "8", "--retries", "3", "--low-level-retries", "10"]
            dados = remoto_dados(c)
            # O que for apagado ou substituído no Drive vai para lixeira/<data> (30 dias).
            lixeira = f"{dados}/lixeira/{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}"
            p = subprocess.Popen([rclone_bin(), "sync", str(HOME), f"{dados}/home", "--files-from", str(arq_lista),
                                  "--delete-excluded", "--backup-dir", lixeira, *comuns],
                                 stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
            if _progresso(p, _t("Enviando arquivos")) != 0:
                raise RuntimeError(_t("falha ao enviar os arquivos (veja a conexão)"))
            p = subprocess.Popen([rclone_bin(), "sync", str(EXTRA), f"{dados}/extra", *comuns],
                                 stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
            if _progresso(p, _t("Enviando extras")) != 0:
                raise RuntimeError(_t("falha ao enviar histórico e lista de programas"))
            rc("rcat", f"{remoto_base()}/meta.json", entrada=json.dumps(meta, ensure_ascii=False, indent=2))
            limpar_lixeira(dados)
            publicar_ferramenta()
            if not ok_pastas:
                raise RuntimeError(_t("pastas: %1", erro_pastas))
            agora = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
            salvar_estado(ultimo_backup_config=agora)
            salvar_estado(ultima=agora, resultado="ok", tamanho=total, arquivos=len(lista), progresso="", remoto_meta=meta,
                          precisa_decidir=False, conflito=None, falhas_seguidas=0)
            marcar_base_enviada()
            if not a.silencioso:
                avisar(_t("Backup concluído"), _t("%1 arquivos sincronizados com o Google Drive.", len(lista)))
            return 0
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            falhas = int(estado().get("falhas_seguidas") or 0) + 1
            temporario = erro_temporario(msg)
            parado_ha = 0
            try:
                ultima = datetime.datetime.fromisoformat(estado().get("ultima") or "")
                parado_ha = time.time() - ultima.timestamp()
            except (ValueError, TypeError):
                parado_ha = AVISAR_FALHA_APOS
            if temporario:
                legivel = _t("O Google Drive limitou o acesso por alguns minutos; o backup tenta de novo sozinho.") \
                    if ("ratelimit" in msg.lower() or "rate_limit" in msg.lower() or "quota" in msg.lower()) \
                    else _t("Sem conexão com o Google Drive agora; o backup tenta de novo sozinho.")
            else:
                legivel = msg[-300:]
            salvar_estado(resultado="erro", erro=legivel, progresso="", falhas_seguidas=falhas)
            # Erro temporário (limite do Google, rede): só avisa se o backup está parado há horas.
            if not temporario or parado_ha >= AVISAR_FALHA_APOS or not a.silencioso:
                avisar(_t("Falha no backup"), legivel[-200:], True)
            print(msg[-800:], file=sys.stderr)
            return 0 if (temporario and a.silencioso) else 1


def _brave_aberto():
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                if Path(f"/proc/{d}/comm").read_text().strip() in ("brave", "brave-browser"):
                    return True
            except OSError:
                pass
    return False


def cmd_restaurar(a):
    if not conectado():
        print(_t("não conectado"), file=sys.stderr)
        return 1
    c = config()
    if c.get("cripto") and not os.environ.get("CONTA_REMOTO"):
        if NOME_CRIPTO + ":" not in rc("listremotes").stdout.split():
            print(_t("backup criptografado: defina a senha com `conta senha <senha>`"), file=sys.stderr)
            return 2
    if not a.sim and sys.stdin.isatty():
        r = input(_t("Os arquivos atuais que forem substituídos vão para ~/.local/share/conta/antes-da-restauracao. Continuar? [s/N] "))
        if r.strip().lower() not in ("s", "sim", "y"):
            return 1
    if not remoto_meta():
        salvar_estado(resultado="erro", erro=_t("Nenhum backup encontrado nesta conta do Google Drive."))
        print(_t("nenhum backup encontrado nesta conta"), file=sys.stderr)
        return 3
    with Trava():
        dados = remoto_dados(c)
        carimbo = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        guarda = HOME / ".local/share/conta/antes-da-restauracao" / carimbo
        salvar_estado(progresso=_t("Trazendo o papel de parede…"), erro="")
        try:
            _restaurar_fundo(dados)
            salvar_estado(progresso=_t("Baixando arquivos…"), erro="")
            # shell.json (barra) fica de fora daqui e entra por último, de uma vez: no meio da
            # cópia a barra não achava a configuração, caía no padrão e podia gravar ele por cima
            p = subprocess.Popen([rclone_bin(), "copy", f"{dados}/home", str(HOME), "--backup-dir", str(guarda),
                                  "--exclude", "/.local/share/conta/antes-da-restauracao/**",
                                  "--exclude", "/.config/simba/shell.json",
                                  "--exclude", "/.local/share/icons/Yaru-grey/**", "--exclude", "/.local/share/icons/Yaru-gray/**",
                                  "--stats", "2s", "--stats-one-line", "-v", "--transfers", "8"],
                                 stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
            if _progresso(p, _t("Baixando arquivos")) != 0:
                raise RuntimeError(_t("falha ao baixar os arquivos"))
            _restaurar_shell_json(dados, guarda)
            fo = CACHE / "fundo-original"
            if fo.exists():
                if Path(fo.read_text().strip()).is_file():
                    _aplicar_fundo(fo.read_text().strip())
                fo.unlink(missing_ok=True)
            ext = CACHE / "restaurar-extra"
            if ext.exists():
                shutil.rmtree(ext)
            rc("copy", f"{dados}/extra", str(ext))
            meta = ler_json(ext / "meta.json", {})
            # links que o backup registrou (o rclone não leva links): recria os que faltam
            for rel, alvo_link in ler_json(ext / "links.json", {}).items():
                dest = HOME / rel
                if not os.path.lexists(dest):
                    try:
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        os.symlink(alvo_link, dest)
                    except OSError:
                        pass
            aplicar_modos(ler_json(ext / "modos.json", {}))
            pendente = ""
            # Histórico e favoritos do Brave
            if (ext / "brave").is_dir():
                if _brave_aberto():
                    dest = HOME / ".local/share/conta/brave-pendente"
                    if dest.exists():
                        shutil.rmtree(dest)
                    shutil.copytree(ext / "brave", dest)
                    pendente = _t("Feche o Brave e rode `conta brave` para trazer o histórico e os favoritos.")
                else:
                    _restaurar_brave(ext / "brave", guarda)
            # Serviços do usuário que estavam ativos
            subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
            for u in (ext / "systemd-user-ativos.txt").read_text().split() if (ext / "systemd-user-ativos.txt").exists() else []:
                subprocess.run(["systemctl", "--user", "enable", u], capture_output=True)
            # Tema do Simba
            if meta.get("tema") and shutil.which("simba-theme-set") and not os.environ.get("CONTA_HOME"):
                subprocess.run(["simba-theme-set", meta["tema"]], capture_output=True, timeout=120)
            # Pacotes que faltam
            faltando = pacotes_faltando(ext / "pacotes")
            salvar_estado(progresso="", resultado="restaurado", precisa_decidir=False, pacotes_faltando=len(faltando["pacman"]) + len(faltando["aur"]),
                          restaurado=carimbo)
            corpo = _t("Configurações, papéis de parede e histórico restaurados.")
            if faltando["pacman"] or faltando["aur"]:
                corpo += _t(" Faltam %1 programas: Configurações › Contas › Instalar programas.", len(faltando['pacman']) + len(faltando['aur']))
            if pendente:
                corpo += " " + pendente
            cmd_auto(type("A", (), {"modo": "liga"})())
            marcar_base_enviada()          # aqui agora é igual ao backup: base combinada
            avisar(_t("Restauração concluída"), corpo)
            print(corpo)
            if not a.sem_pacotes and a.sim and sys.stdin.isatty() and (faltando["pacman"] or faltando["aur"]):
                instalar_pacotes(faltando, terminal_proprio=True)
            if not os.environ.get("CONTA_HOME"):
                subprocess.run(["hyprctl", "reload"], capture_output=True)
                subprocess.Popen(["simba-restart-shell"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return 0
        except Exception as e:  # noqa: BLE001
            salvar_estado(resultado="erro", erro=str(e)[-300:], progresso="")
            avisar(_t("Falha na restauração"), str(e)[-200:], True)
            return 1


def _aplicar_fundo(img):
    if os.environ.get("CONTA_HOME"):               # testes: só o link, sem mexer na tela
        link = HOME / ".local/state/simba/current/background"
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(Path(img).resolve())
        return
    if not shutil.which("simba-theme-bg-set"):
        return
    subprocess.run(["simba-theme-bg-set", str(img)], capture_output=True, timeout=30)


def _restaurar_fundo(dados):
    """Primeiro passo da restauração: o papel de parede, para a máquina já ficar com a cara
    da pessoa enquanto o resto baixa."""
    destino = HOME / ".local/share/conta/fundo"
    try:
        if destino.exists():
            shutil.rmtree(destino)
        destino.mkdir(parents=True)
        rc("copy", f"{dados}/extra/fundo", str(destino), check=False)
        meta = json.loads(rc("cat", f"{dados}/extra/meta.json", check=False).stdout or "{}")
    except (OSError, ValueError, subprocess.SubprocessError):
        return
    original = Path(meta.get("fundo") or "")
    if original.name and original.is_file():          # imagem do sistema que existe aqui também
        _aplicar_fundo(original)
        return
    copia = next((f for f in destino.iterdir() if f.is_file()), None)
    if copia:
        _aplicar_fundo(copia)
        # depois que os arquivos voltarem, aponta para o lugar original (ex.: ~/Imagens/x.jpg)
        if original.name:
            CACHE.mkdir(parents=True, exist_ok=True)
            (CACHE / "fundo-original").write_text(str(original))


def _restaurar_shell_json(dados, guarda):
    """A configuração da barra entra por último e de uma vez (troca atômica)."""
    alvo = HOME / ".config/simba/shell.json"
    tmp = alvo.with_name("shell.json.restaurando")
    try:
        r = rc("copyto", f"{dados}/home/.config/simba/shell.json", str(tmp), check=False)
        if r.returncode != 0 or not tmp.exists():
            return
        json.loads(tmp.read_text())                      # só entra se for JSON válido
        if alvo.exists():
            (guarda / ".config/simba").mkdir(parents=True, exist_ok=True)
            shutil.copy2(alvo, guarda / ".config/simba/shell.json")
        os.replace(tmp, alvo)
    except (OSError, ValueError):
        tmp.unlink(missing_ok=True)


def aplicar_modos(modos):
    for rel, m in modos.items():
        p = HOME / rel
        if p.exists() and not p.is_symlink():
            try:
                os.chmod(p, int(m))
            except OSError:
                pass


def _restaurar_brave(origem, guarda):
    BRAVE.mkdir(parents=True, exist_ok=True)
    (guarda / "brave").mkdir(parents=True, exist_ok=True)
    for a in BRAVE_ARQS:
        src = origem / a
        if not src.exists():
            continue
        dst = BRAVE / a
        if dst.exists():
            shutil.copy2(dst, guarda / "brave" / a)
        for sufixo in ("-journal", "-wal", "-shm"):
            Path(str(dst) + sufixo).unlink(missing_ok=True)
        shutil.copy2(src, dst)


def cmd_brave(_a):
    src = HOME / ".local/share/conta/brave-pendente"
    if not src.is_dir():
        print(_t("nada pendente"))
        return 0
    if _brave_aberto():
        print(_t("feche o Brave antes"), file=sys.stderr)
        return 1
    _restaurar_brave(src, HOME / ".local/share/conta/antes-da-restauracao" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
    shutil.rmtree(src)
    avisar(_t("Histórico do Brave restaurado"))
    return 0


def aplicar_brave_se_pendente():
    """Se houver favoritos ou histórico baixados da nuvem aguardando e o Brave estiver fechado, aplica."""
    pendente = HOME / ".local/share/conta/brave-pendente"
    if pendente.is_dir() and not _brave_aberto():
        try:
            guarda = HOME / ".local/share/conta/antes-da-restauracao" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
            _restaurar_brave(pendente, guarda)
            shutil.rmtree(pendente, ignore_errors=True)
            avisar(_t("Simba Conta — Navegador"), _t("Favoritos e histórico da nuvem aplicados ao navegador."))
            return True
        except Exception:
            pass
    return False


def pacotes_faltando(pasta):
    pasta = Path(pasta)
    instalados = set(subprocess.run(["pacman", "-Qq"], capture_output=True, text=True).stdout.split())
    repo = set(subprocess.run(["pacman", "-Slq"], capture_output=True, text=True).stdout.split())
    ler = lambda n: [l.strip() for l in (pasta / n).read_text().splitlines() if l.strip()] if (pasta / n).exists() else []
    pac = [p for p in ler("pacman.txt") if p not in instalados and p in repo]
    aur = [p for p in ler("aur.txt") if p not in instalados]
    fp = ler("flatpak.txt")
    if fp and shutil.which("flatpak"):
        tem = set(subprocess.run(["flatpak", "list", "--app", "--columns=application"], capture_output=True, text=True).stdout.split())
        fp = [p for p in fp if p not in tem]
    gravar_json(CACHE / "pacotes-faltando.json", {"pacman": pac, "aur": aur, "flatpak": fp})
    return {"pacman": pac, "aur": aur, "flatpak": fp}


def instalar_pacotes(f, terminal_proprio=False):
    linhas = [_t("echo 'Instalando os programas da sua conta…'")]
    if f["pacman"]:
        # Primeiro tudo de uma vez; se algo conflitar, um por um (o resto continua).
        lista = " ".join(f["pacman"])
        linhas.append(f"sudo pacman -S --needed {lista} || for p in {lista}; do sudo pacman -S --needed --noconfirm \"$p\" || echo \"Falhou: $p\"; done")
    if f["aur"] and shutil.which("yay"):
        linhas.append("yay -S --needed " + " ".join(f["aur"]))
    if f.get("flatpak"):
        linhas.append("flatpak install -y flathub " + " ".join(f["flatpak"]))
    linhas.append(_t("echo; echo 'Pronto. Pode fechar esta janela.'; read -r"))
    script = CACHE / "instalar-pacotes.sh"
    script.write_text("\n".join(linhas) + "\n")
    if terminal_proprio:
        return subprocess.call(["bash", str(script)])
    subprocess.Popen(["xdg-terminal-exec", "--", "bash", str(script)], start_new_session=True)
    return 0


def cmd_pacotes(_a):
    f = ler_json(CACHE / "pacotes-faltando.json", None)
    if f is None:
        ext = CACHE / "restaurar-extra" / "pacotes"
        if not ext.exists():
            print(_t("restaure a conta primeiro"), file=sys.stderr)
            return 1
        f = pacotes_faltando(ext)
    if not (f["pacman"] or f["aur"] or f.get("flatpak")):
        print(_t("nenhum programa faltando"))
        return 0
    return instalar_pacotes(f)


SERVICO = """[Unit]
Description=Backup da conta no Google Drive (conta sincronizar)
After=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/conta sincronizar --silencioso
Nice=10
IOSchedulingClass=idle
TimeoutStartSec=1h
"""
TIMER = """[Unit]
Description=Sincronização e backup automático da conta no Google Drive

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min
RandomizedDelaySec=30s

[Install]
WantedBy=timers.target
"""


def cmd_auto(a):
    if os.environ.get("CONTA_HOME"):
        return 0  # teste com pasta pessoal falsa: não mexe no systemd real
    d = HOME / ".config/systemd/user"
    d.mkdir(parents=True, exist_ok=True)
    (d / "conta-sync.service").write_text(SERVICO)
    (d / "conta-sync.timer").write_text(TIMER)
    subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True)
    acao = ["enable", "--now"] if a.modo == "liga" else ["disable", "--now"]
    subprocess.run(["systemctl", "--user", *acao, "conta-sync.timer"], capture_output=True)
    c = config()
    c["auto"] = a.modo == "liga"
    salvar_config(c)
    return 0


def cmd_categoria(a):
    if a.id not in CATEGORIAS:
        print(_t("categoria desconhecida"), file=sys.stderr)
        return 2
    c = config()
    c["categorias"][a.id] = a.modo == "liga"
    salvar_config(c)
    if a.id in ("pastas", "documentos", "imagens"):
        marcar_pastas_alteradas()
    if conectado():
        atualizar_pasta_local(c)
    return 0


def _boas_vindas_aberta():
    """A tela de boas-vindas mostra a escolha ela mesma: não abre as Configurações por cima."""
    for d in os.listdir("/proc"):
        if d.isdigit():
            try:
                cmd = Path(f"/proc/{d}/cmdline").read_bytes()
            except OSError:
                continue
            if b"boas-vindas/app.py" in cmd:
                return True
    return False


def cmd_escolher(a):
    """Escolha do que sincronizar (1º login). Depois dela o backup automático e o papel
    de parede entre máquinas ligam conforme o escolhido e a 1ª sincronização começa."""
    c = config()
    if a.categorias is not None:
        escolhidas = {x.strip() for x in a.categorias.split(",") if x.strip()}
        desconhecidas = escolhidas - set(CATEGORIAS)
        if desconhecidas:
            print(_t("categoria desconhecida: %1", ", ".join(sorted(desconhecidas))), file=sys.stderr)
            return 2
        for k in CATEGORIAS:
            c["categorias"][k] = k in escolhidas and (k != "segredos" or bool(c.get("cripto")))
    if getattr(a, "pastas", None) is not None:
        # escolha por pastas (boas-vindas): só elas; configurações, histórico etc. ficam de fora
        pastas = []
        for x in a.pastas.split(","):
            x = x.strip()
            if x.startswith(str(HOME)):
                x = os.path.relpath(x, HOME)
            x = x.strip("/")
            if x and not x.startswith("..") and (HOME / x).is_dir() and x not in pastas:
                pastas.append(x)
        c["pastas_personalizadas"] = pastas
        if a.categorias is None:
            for k in CATEGORIAS:
                c["categorias"][k] = False
        c["categorias"]["pastas"] = bool(pastas)
    if a.fundo:
        c["sincronizar_fundo"] = a.fundo == "liga"
    c["escolha_feita"] = True
    salvar_config(c)
    if getattr(a, "pastas", None) is not None or a.categorias is not None:
        marcar_pastas_alteradas()
    atualizar_pasta_local(c)
    if os.environ.get("CONTA_HOME"):
        return 0
    algum = any(c["categorias"].values())
    if algum and pode_enviar():
        cmd_auto(type("A", (), {"modo": "liga"})())
    elif not algum:
        cmd_auto(type("A", (), {"modo": "desliga"})())
    acao = ["enable", "--now"] if c["sincronizar_fundo"] else ["disable", "--now"]
    subprocess.run(["systemctl", "--user", *acao, "conta-fundo.service"], capture_output=True, timeout=10)
    if algum and pode_enviar():
        subprocess.Popen(["/usr/bin/conta", "sincronizar", "--silencioso"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return 0


def cmd_boas_vindas(a):
    if a.acao == "mostrar":
        return 0 if BOAS_VINDAS.exists() and not SEM_BOAS_VINDAS.exists() and not conectado() else 1
    if a.acao in ("liga", "desliga"):
        if a.acao == "liga":
            SEM_BOAS_VINDAS.unlink(missing_ok=True)
        else:
            SEM_BOAS_VINDAS.parent.mkdir(parents=True, exist_ok=True)
            SEM_BOAS_VINDAS.touch()
            BOAS_VINDAS.unlink(missing_ok=True)
        return 0
    if a.acao == "marcar":
        BOAS_VINDAS.parent.mkdir(parents=True, exist_ok=True)
        BOAS_VINDAS.touch()
    else:
        BOAS_VINDAS.unlink(missing_ok=True)
    return 0


def cmd_tamanho(_a):
    lista, total = listar_arquivos()
    print(json.dumps({"arquivos": len(lista), "tamanho": total}))
    return 0


def main():
    import argparse
    ap = argparse.ArgumentParser(prog="conta", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("status")
    p.add_argument("--rapido", action="store_true", help="sem varrer pastas nem consultar o Drive")
    p.set_defaults(f=cmd_status)
    p = sub.add_parser("entrar")
    p.add_argument("--cripto", default="", help="senha do backup; '-' lê da entrada padrão")
    p.set_defaults(f=cmd_entrar)
    p = sub.add_parser("senha")
    p.add_argument("senha")
    p.set_defaults(f=cmd_senha)
    sub.add_parser("sair").set_defaults(f=cmd_sair)
    sub.add_parser("reconectar", help="entra de novo mantendo as escolhas (troca do acesso ao Google)").set_defaults(f=cmd_reconectar)
    p = sub.add_parser("sincronizar")
    p.add_argument("--silencioso", action="store_true")
    p.add_argument("--substituir", action="store_true", help="envia mesmo havendo backup de outra máquina")
    p.add_argument("--forcar", action="store_true", help="força puxar alterações mesmo da mesma máquina")
    p.set_defaults(f=cmd_sincronizar)
    p = sub.add_parser("puxar", help="busca e aplica alterações remotas do Google Drive")
    p.add_argument("--silencioso", action="store_true")
    p.add_argument("--forcar", action="store_true", help="força puxar alterações mesmo da mesma máquina")
    p.set_defaults(f=lambda a: 0 if puxar_alteracoes_remotas(silencioso=a.silencioso, forcar=a.forcar) else 0)
    p = sub.add_parser("verificar", help="busca e aplica alterações remotas do Google Drive")
    p.add_argument("--silencioso", action="store_true")
    p.add_argument("--forcar", action="store_true", help="força puxar alterações mesmo da mesma máquina")
    p.set_defaults(f=lambda a: 0 if puxar_alteracoes_remotas(silencioso=a.silencioso, forcar=a.forcar) else 0)
    p = sub.add_parser("restaurar")
    p.add_argument("--sim", action="store_true")
    p.add_argument("--sem-pacotes", action="store_true")
    p.set_defaults(f=cmd_restaurar)
    sub.add_parser("pacotes").set_defaults(f=cmd_pacotes)
    sub.add_parser("brave").set_defaults(f=cmd_brave)
    p = sub.add_parser("auto")
    p.add_argument("modo", choices=["liga", "desliga"])
    p.set_defaults(f=cmd_auto)
    p = sub.add_parser("categoria")
    p.add_argument("id")
    p.add_argument("modo", choices=["liga", "desliga"])
    p.set_defaults(f=cmd_categoria)
    sub.add_parser("tamanho").set_defaults(f=cmd_tamanho)
    p = sub.add_parser("escolher", help="o que sincronizar (escolha do 1º login)")
    p.add_argument("--categorias", help="ids separados por vírgula (vazio = nenhuma)")
    p.add_argument("--pastas", help="pastas da pasta pessoal, separadas por vírgula (só elas vão)")
    p.add_argument("--fundo", choices=["liga", "desliga"])
    p.set_defaults(f=cmd_escolher)
    p = sub.add_parser("fundo", help="papel de parede imediato entre máquinas")
    p.add_argument("acao", choices=["vigiar", "enviar", "puxar", "liga", "desliga"])
    p.set_defaults(f=cmd_fundo)
    sub.add_parser("foto", help="baixa a foto de perfil da conta Google").set_defaults(f=cmd_foto)
    p = sub.add_parser("pausar", help="pausa a sincronização por X horas (Modo Viagem)")
    p.add_argument("horas", nargs="?", type=int, default=24)
    p.set_defaults(f=cmd_pausar)
    sub.add_parser("retomar", help="retoma a sincronização (desativa Modo Viagem)").set_defaults(f=cmd_retomar)
    p = sub.add_parser("resolver", help="resolve conflitos de versão entre máquinas")
    p.add_argument("escolha", choices=["local", "remoto", "este", "nuvem"])
    p.set_defaults(f=cmd_resolver)
    p = sub.add_parser("pasta", help="gerencia pastas adicionais na categoria documentos")
    p.add_argument("acao", choices=["adicionar", "incluir", "remover", "excluir", "listar"])
    p.add_argument("caminho", nargs="?", default="")
    p.set_defaults(f=cmd_pasta)
    sub.add_parser("abrir-pasta", help="abre ~/Simba Conta (atalhos para tudo o que é sincronizado)").set_defaults(f=cmd_abrir_pasta)
    p = sub.add_parser("boas-vindas", help="tela da primeira inicialização (mostrar: código 0 se deve aparecer)")
    p.add_argument("acao", choices=["mostrar", "marcar", "fechar", "liga", "desliga"],
                   help="liga/desliga: oferecer o login no 1º boot das instalações pela ISO")
    p.set_defaults(f=cmd_boas_vindas)
    p = sub.add_parser("pacotes-modo", help="modo de backup dos programas (todos ou escolher)")
    p.add_argument("modo", choices=["todos", "escolher"])
    p.set_defaults(f=cmd_pacotes_modo)
    p = sub.add_parser("pacotes-selecionar", help="define programas selecionados para backup")
    p.add_argument("--modo", choices=["todos", "escolher"], default=None)
    p.add_argument("--ids", default=None)
    p.add_argument("--json-ids", default=None)
    p.set_defaults(f=cmd_pacotes_selecionar)
    sub.add_parser("pacotes-listar", help="lista programas instalados com estado de backup").set_defaults(f=cmd_pacotes_listar)
    a = ap.parse_args()
    return a.f(a) or 0


if __name__ == "__main__":
    sys.exit(main())
