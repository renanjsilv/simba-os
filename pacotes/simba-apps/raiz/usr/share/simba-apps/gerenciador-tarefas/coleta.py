"""Coleta de dados do sistema direto do /proc e /sys (sem psutil).

Tudo aqui é síncrono e barato (~300 processos em poucos ms); a interface
chama as funções a cada atualização e guarda o estado anterior para as taxas.
"""
import json
import os
import pwd
import socket
import subprocess
import time
import sys as _sys, os as _os  # noqa: E401
_sys.path.insert(0, _os.path.expanduser("/usr/share/simba-apps/idiomas"))
from simba_i18n import t as _t, DECIMAL as _DEC  # noqa: E402  (traduções: /usr/share/simba-apps/idiomas)

CLK = os.sysconf("SC_CLK_TCK")
PAGINA = os.sysconf("SC_PAGE_SIZE")
NCPU = os.cpu_count() or 1
MEU_UID = os.getuid()

_usuarios = {}


def nome_usuario(uid):
    if uid not in _usuarios:
        try:
            _usuarios[uid] = pwd.getpwuid(uid).pw_name
        except KeyError:
            _usuarios[uid] = str(uid)
    return _usuarios[uid]


def _ler(caminho, padrao=""):
    try:
        with open(caminho, "rb") as f:
            return f.read().decode("utf-8", "replace")
    except OSError:
        return padrao


# ── processos ────────────────────────────────────────────────────────────────
class Proc:
    __slots__ = ("pid", "ppid", "nome", "estado", "uid", "ticks", "threads",
                 "mem", "io", "cmd", "exe", "cpu", "disco", "inicio")


INTERPRETADORES = ("python", "python3", "node", "bash", "sh", "perl", "ruby", "bun", "deno")


def _nome_de(comm, cmdline):
    # Interpretadores: mostra o script ("python (wake.py)").
    base = comm.split(".")[0] if comm.startswith("python") else comm
    if comm in ("qs", "quickshell"):
        for i, a in enumerate(cmdline[:-1]):
            if a in ("-c", "--config"):
                return f"{comm} ({cmdline[i + 1]})"
            if a in ("-p", "--path"):
                return f"{comm} ({os.path.basename(os.path.dirname(cmdline[i + 1].rstrip('/'))) or cmdline[i + 1]})"
    if base in INTERPRETADORES or comm.startswith("python3."):
        if cmdline[1:2] in (["-c"], ["-m"]):
            return f"{comm} ({'código' if cmdline[1] == '-c' else (cmdline[2] if len(cmdline) > 2 else '')})"
        for a in cmdline[1:]:
            if a.startswith("-"):
                continue
            if "/" in a or "." in a:
                return f"{comm} ({os.path.basename(a)[:40]})"
            break
    # comm é cortado em 15 caracteres; o argv[0] completo dá um nome melhor.
    if cmdline:
        a0 = os.path.basename(cmdline[0].split(" ")[0]) if cmdline[0] else ""
        if a0 and (len(comm) >= 15 and a0.startswith(comm[:10])):
            return a0
    return comm


class Processos:
    """Amostra os processos e calcula CPU %/disco entre duas leituras."""

    def __init__(self):
        self.anterior = {}  # pid -> (ticks, io, inicio)
        self.t_anterior = None

    def amostrar(self):
        agora = time.monotonic()
        dt = (agora - self.t_anterior) if self.t_anterior else None
        procs = {}
        for entrada in os.scandir("/proc"):
            if not entrada.name.isdigit():
                continue
            pid = int(entrada.name)
            base = "/proc/" + entrada.name
            stat = _ler(base + "/stat")
            if not stat:
                continue
            fecha = stat.rfind(")")
            comm = stat[stat.find("(") + 1:fecha]
            campos = stat[fecha + 2:].split()
            # campos[0]=estado [1]=ppid ... [11]=utime [12]=stime [17]=threads [19]=starttime
            try:
                p = Proc()
                p.pid = pid
                p.estado = campos[0]
                p.ppid = int(campos[1])
                p.ticks = int(campos[11]) + int(campos[12])
                p.threads = int(campos[17])
                p.inicio = int(campos[19])
            except (IndexError, ValueError):
                continue
            # Threads do kernel (filhos do kthreadd) não interessam.
            if p.ppid == 2 or pid == 2:
                continue
            try:
                p.uid = entrada.stat().st_uid
            except OSError:
                continue
            statm = _ler(base + "/statm").split()
            # Memória "privada" (residente - compartilhada), como o conjunto de
            # trabalho privado do Gerenciador de Tarefas do Windows.
            try:
                p.mem = max(0, int(statm[1]) - int(statm[2])) * PAGINA
            except (IndexError, ValueError):
                p.mem = 0
            io = _ler(base + "/io")
            total_io = None
            if io:
                lido = escrito = 0
                for linha in io.splitlines():
                    if linha.startswith("read_bytes:"):
                        lido = int(linha.split()[1])
                    elif linha.startswith("write_bytes:"):
                        escrito = int(linha.split()[1])
                total_io = lido + escrito
            p.io = total_io
            cmd = _ler(base + "/cmdline").split("\0")
            cmd = [c for c in cmd if c]
            p.cmd = " ".join(cmd)
            p.nome = _nome_de(comm, cmd)
            p.exe = None
            ant = self.anterior.get(pid)
            if dt and ant and ant[2] == p.inicio:
                p.cpu = max(0.0, (p.ticks - ant[0]) / CLK / dt / NCPU * 100)
                p.disco = max(0.0, (p.io - ant[1]) / dt) if (p.io is not None and ant[1] is not None) else 0.0
            else:
                p.cpu = 0.0
                p.disco = 0.0
            procs[pid] = p
        self.anterior = {pid: (p.ticks, p.io, p.inicio) for pid, p in procs.items()}
        self.t_anterior = agora
        return procs


def contar_processos():
    """(processos, threads) de usuário, sem threads do kernel — leitura leve."""
    n = th = 0
    for e in os.scandir("/proc"):
        if not e.name.isdigit():
            continue
        st = _ler(f"/proc/{e.name}/stat")
        f = st[st.rfind(")") + 2:].split() if st else []
        if len(f) > 17 and f[1] != "2" and e.name != "2":
            n += 1
            th += int(f[17])
    return n, th


def descendentes(procs, raiz):
    filhos = {}
    for p in procs.values():
        filhos.setdefault(p.ppid, []).append(p.pid)
    saida, pilha = [], [raiz]
    while pilha:
        pid = pilha.pop()
        if pid in procs:
            saida.append(pid)
        pilha.extend(filhos.get(pid, []))
    return saida


def janelas_hyprland():
    try:
        out = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=2).stdout
        return json.loads(out or "[]")
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []


# ── desempenho ───────────────────────────────────────────────────────────────
class Cpu:
    def __init__(self):
        self.ant = None
        self.modelo = ""
        for linha in _ler("/proc/cpuinfo").splitlines():
            if linha.startswith("model name"):
                self.modelo = linha.split(":", 1)[1].strip()
                break
        self.nucleos = len({l for l in _ler("/proc/cpuinfo").splitlines() if l.startswith("core id")}) or NCPU
        mx = _ler("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq").strip()
        self.vel_max = int(mx) / 1e6 if mx.isdigit() else 0
        bs = _ler("/sys/devices/system/cpu/cpu0/cpufreq/base_frequency").strip()
        self.vel_base = int(bs) / 1e6 if bs.isdigit() else self.vel_max

    def amostrar(self):
        partes = _ler("/proc/stat").splitlines()[0].split()[1:]
        v = [int(x) for x in partes]
        ocioso = v[3] + v[4]
        total = sum(v[:8])
        uso = 0.0
        if self.ant:
            dt = total - self.ant[0]
            uso = 0.0 if dt <= 0 else max(0.0, min(100.0, (1 - (ocioso - self.ant[1]) / dt) * 100))
        self.ant = (total, ocioso)
        return uso

    @staticmethod
    def velocidade():
        fs = []
        for i in range(NCPU):
            f = _ler(f"/sys/devices/system/cpu/cpu{i}/cpufreq/scaling_cur_freq").strip()
            if f.isdigit():
                fs.append(int(f))
        return (sum(fs) / len(fs) / 1e6) if fs else 0


def memoria():
    m = {}
    for linha in _ler("/proc/meminfo").splitlines():
        k, _, v = linha.partition(":")
        m[k] = int(v.split()[0]) * 1024
    total = m.get("MemTotal", 1)
    disp = m.get("MemAvailable", 0)
    return {
        "total": total,
        "disponivel": disp,
        "usada": total - disp,
        "cache": m.get("Cached", 0) + m.get("Buffers", 0) + m.get("SReclaimable", 0),
        "swap_total": m.get("SwapTotal", 0),
        "swap_usada": m.get("SwapTotal", 0) - m.get("SwapFree", 0),
        "comprometida": m.get("Committed_AS", 0),
        "limite": m.get("CommitLimit", 0),
    }


def discos():
    """Discos físicos (sem partições, loop, ram, zram, dm)."""
    saida = []
    for nome in sorted(os.listdir("/sys/block")):
        if nome.startswith(("loop", "ram", "zram", "dm-", "sr")):
            continue
        saida.append(nome)
    return saida


class Disco:
    def __init__(self, nome):
        self.nome = nome
        self.ant = None
        modelo = _ler(f"/sys/block/{nome}/device/model").strip()
        self.modelo = modelo or nome
        rot = _ler(f"/sys/block/{nome}/queue/rotational").strip()
        self.tipo = "HDD" if rot == "1" else (_t("SSD (NVMe)") if nome.startswith("nvme") else "SSD")
        setores = _ler(f"/sys/block/{nome}/size").strip()
        self.capacidade = int(setores) * 512 if setores.isdigit() else 0

    def amostrar(self):
        v = _ler(f"/sys/block/{self.nome}/stat").split()
        agora = time.monotonic()
        if len(v) < 10:
            return 0.0, 0.0, 0.0
        lidos, escritos, ticks = int(v[2]) * 512, int(v[6]) * 512, int(v[9])
        r = (0.0, 0.0, 0.0)
        if self.ant:
            dt = agora - self.ant[0]
            if dt > 0:
                ativo = min(100.0, (ticks - self.ant[3]) / (dt * 1000) * 100)
                r = (ativo, (lidos - self.ant[1]) / dt, (escritos - self.ant[2]) / dt)
        self.ant = (agora, lidos, escritos, ticks)
        return r


def interfaces():
    saida = []
    for nome in sorted(os.listdir("/sys/class/net")):
        if nome == "lo" or nome.startswith(("veth", "vnet", "docker", "br-", "virbr", "tun", "tailscale")):
            continue
        if _ler(f"/sys/class/net/{nome}/operstate").strip() not in ("up", "unknown"):
            continue
        saida.append(nome)
    return saida


class Rede:
    def __init__(self, nome):
        self.nome = nome
        self.ant = None
        self.wifi = os.path.isdir(f"/sys/class/net/{nome}/wireless")

    def amostrar(self):
        rx = int(_ler(f"/sys/class/net/{self.nome}/statistics/rx_bytes", "0").strip() or 0)
        tx = int(_ler(f"/sys/class/net/{self.nome}/statistics/tx_bytes", "0").strip() or 0)
        agora = time.monotonic()
        r = (0.0, 0.0)
        if self.ant:
            dt = agora - self.ant[0]
            if dt > 0:
                r = ((rx - self.ant[1]) / dt, (tx - self.ant[2]) / dt)
        self.ant = (agora, rx, tx)
        return r

    def ip(self):
        try:
            out = subprocess.run(["ip", "-o", "-4", "addr", "show", self.nome], capture_output=True, text=True, timeout=1).stdout
            return out.split()[3].split("/")[0] if out.split() else "—"
        except (OSError, IndexError, subprocess.TimeoutExpired):
            return "—"


def tempo_atividade():
    s = int(float(_ler("/proc/uptime", "0").split()[0]))
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{d}:{h:02d}:{m:02d}:{s:02d}"


def nome_maquina():
    return socket.gethostname()


# ── serviços (systemd) ───────────────────────────────────────────────────────
def _memorias_cgroup():
    """nome da unidade -> (bytes, primeiro pid), varrendo /sys/fs/cgroup."""
    mapa = {}
    for raiz, dirs, _ in os.walk("/sys/fs/cgroup"):
        nome = os.path.basename(raiz)
        if nome.endswith(".service") and nome not in mapa:
            # "anon" = memória dos processos, sem o cache de arquivos (que o memory.current inclui)
            mem = 0
            for linha in _ler(raiz + "/memory.stat").splitlines():
                if linha.startswith("anon "):
                    mem = int(linha.split()[1])
                    break
            pids = _ler(raiz + "/cgroup.procs").split()
            mapa[nome] = (mem, int(pids[0]) if pids else 0)
            # Unidades do user@.service: os serviços do usuário ficam dentro dele.
            if nome != f"user@{MEU_UID}.service":
                dirs[:] = []
    return mapa


def servicos():
    saida = []
    mem = _memorias_cgroup()
    for escopo, args in ((_t("Sistema"), []), (_t("Usuário"), ["--user"])):
        try:
            out = subprocess.run(["systemctl", *args, "list-units", "--type=service", "--all",
                                  "-o", "json", "--no-pager"], capture_output=True, text=True, timeout=5).stdout
            unidades = json.loads(out or "[]")
        except (OSError, ValueError, subprocess.TimeoutExpired):
            unidades = []
        for u in unidades:
            if u.get("load") == "not-found":
                continue
            nome = u["unit"]
            m, pid = mem.get(nome, (0, 0)) if u.get("active") == "active" else (0, 0)
            saida.append({
                "unidade": nome,
                "escopo": escopo,
                "descricao": u.get("description", ""),
                "ativo": u.get("active", ""),
                "sub": u.get("sub", ""),
                "memoria": m,
                "pid": pid,
            })
    return saida


# ── formatação ───────────────────────────────────────────────────────────────
def fmt_bytes(b, casas=1):
    for un in ("B", "KB", "MB", "GB", "TB"):
        if abs(b) < 1024 or un == "TB":
            if un in ("B", "KB"):
                return f"{b:.0f} {un}"
            return f"{b:.{casas}f} {un}".replace(".", _DEC)
        b /= 1024
    return f"{b:.1f} TB"


def fmt_mb(b):
    return f"{b / 1048576:.1f} MB".replace(".", _DEC)


def fmt_taxa(b):
    if b < 1:
        return _t("0 MB/s")
    if b < 1048576 * 0.1:
        return f"{b / 1048576:.1f} MB/s".replace(".", _DEC)
    return f"{b / 1048576:.1f} MB/s".replace(".", _DEC)


def fmt_bits(b):
    bits = b * 8
    for un in ("bps", _t("Kbps"), _t("Mbps"), _t("Gbps")):
        if bits < 1000 or un == "Gbps":
            return f"{bits:.0f} {un}" if un in ("bps", "Kbps") else f"{bits:.1f} {un}".replace(".", _DEC)
        bits /= 1000
    return _t("%1 Gbps", format(bits, ".1f"))
