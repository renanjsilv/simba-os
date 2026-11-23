"""Sinalização do Simba Remoto sem servidor próprio.

Caminhos (tentados em paralelo):
  1. LAN — broadcast UDP na porta 21118 (instantâneo na mesma rede).
  2. DHT Mainline — itens mutáveis BEP 44 assinados com a chave derivada do código.

Tudo cifrado com ChaCha20-Poly1305 usando a chave derivada do código (PBKDF2).
Ver PROTOCOLO.md.
"""
import asyncio
import hashlib
import hmac
import json
import os
import socket
import time
import zlib

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from .dht import DHT

VERSAO = 1
PORTA_LAN = 21118
MAGICO = b"SRM1"
ANUNCIO = b"SRA1"      # presença na rede local (JSON: c=código, n=nome, s=sistema)
CONSULTA = b"SRQ1"     # "quem está aí?"
AAD = b"simba-remoto/1"
PEDACO = 900
MAX_PEDACOS = 4
SAL_CLIENTE = [b"c%d" % i for i in range(MAX_PEDACOS)]
SAL_HOST = [b"h%d" % i for i in range(MAX_PEDACOS)]

# Dicionário de compressão (idêntico ao do app). Trechos mais comuns no fim.
DICIONARIO = (
    "a=candidate: 1 udp 1694498815  typ srflx raddr  rport  generation 0 network-id 1 network-cost 10\r\n"
    "a=candidate: 1 udp 2122260223  typ host generation 0 network-id 1 network-cost 10\r\n"
    "a=end-of-candidates\r\n"
    "m=application 9 UDP/DTLS/SCTP webrtc-datachannel\r\n"
    "a=sctp-port:5000\r\na=max-message-size:65536\r\n"
    "a=rtpmap:96 VP8/90000\r\na=rtcp-fb:96 goog-remb\r\na=rtcp-fb:96 transport-cc\r\n"
    "a=rtcp-fb:96 ccm fir\r\na=rtcp-fb:96 nack\r\na=rtcp-fb:96 nack pli\r\n"
    "a=rtpmap:102 H264/90000\r\n"
    "a=fmtp:102 level-asymmetry-allowed=1;packetization-mode=1;profile-level-id=42e01f\r\n"
    "a=rtcp-fb:102 goog-remb\r\na=rtcp-fb:102 transport-cc\r\na=rtcp-fb:102 ccm fir\r\n"
    "a=rtcp-fb:102 nack\r\na=rtcp-fb:102 nack pli\r\n"
    "a=extmap:4 urn:ietf:params:rtp-hdrext:sdes:mid\r\n"
    "v=0\r\no=- 0 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0 1\r\n"
    "a=extmap-allow-mixed\r\na=msid-semantic: WMS\r\n"
    "m=video 9 UDP/TLS/RTP/SAVPF 102 96\r\nc=IN IP4 0.0.0.0\r\na=rtcp:9 IN IP4 0.0.0.0\r\n"
    "a=ice-options:trickle\r\na=fingerprint:sha-256 \r\n"
    "a=setup:actpass\r\na=setup:active\r\na=mid:0\r\na=mid:1\r\na=recvonly\r\na=sendonly\r\n"
    "a=rtcp-mux\r\na=rtcp-rsize\r\na=ice-ufrag:\r\na=ice-pwd:\r\n"
    '{"v":1,"t":"oferta","sid":"","ts":,"nome":""}\n'
    '{"v":1,"t":"resposta","sid":"","ts":,"nome":""}\n'
).encode()


# ---------------- chaves ----------------
class Chaves:
    """Tudo o que deriva do código de 9 dígitos."""

    def __init__(self, codigo: str):
        digitos = "".join(c for c in codigo if c.isdigit())
        if len(digitos) != 9:
            raise ValueError("o código tem 9 dígitos")
        self.codigo = digitos
        mestre = hashlib.pbkdf2_hmac("sha256", digitos.encode(), b"simba-remoto/v1", 20000, 64)
        self.privada = Ed25519PrivateKey.from_private_bytes(mestre[:32])
        self.publica = self.privada.public_key().public_bytes_raw()
        self.aead = ChaCha20Poly1305(mestre[32:])
        self.ident_lan = hashlib.sha256(mestre[32:] + b"lan").digest()[:8]

    def selar(self, cabecalho: dict, sdp: str) -> bytes:
        texto = json.dumps(cabecalho, separators=(",", ":"), ensure_ascii=False).encode() + b"\n" + sdp.encode()
        c = zlib.compressobj(9, zlib.DEFLATED, 15, zdict=DICIONARIO)
        comp = c.compress(texto) + c.flush()
        nonce = os.urandom(12)
        return nonce + self.aead.encrypt(nonce, comp, AAD)

    def abrir(self, dados: bytes):
        comp = self.aead.decrypt(dados[:12], dados[12:], AAD)
        d = zlib.decompressobj(15, zdict=DICIONARIO)
        texto = d.decompress(comp) + d.flush()
        cab, _, sdp = texto.partition(b"\n")
        return json.loads(cab), sdp.decode()


# ---------------- senha do acesso não supervisionado ----------------
def chave_senha(senha: str, codigo: str) -> bytes:
    """A senha nunca trafega nem fica guardada: só esta chave derivada (PBKDF2, 50 mil iterações)."""
    digitos = "".join(c for c in codigo if c.isdigit())
    return hashlib.pbkdf2_hmac("sha256", senha.encode(), b"simba-remoto/senha/" + digitos.encode(), 50000, 32)


def _fingerprint(sdp: str) -> str:
    for linha in sdp.splitlines():
        if linha.startswith("a=fingerprint:sha-256 "):
            return linha.split(" ", 1)[1].strip().upper()
    return ""


def prova_senha(chave: bytes, sid: str, sdp_oferta: str) -> str:
    """Prova de que o celular sabe a senha, amarrada a esta sessão e à chave DTLS dele (não dá para reaproveitar)."""
    return hmac.new(chave, f"{sid}|{_fingerprint(sdp_oferta)}".encode(), hashlib.sha256).hexdigest()


def formatar_codigo(c: str) -> str:
    c = "".join(x for x in c if x.isdigit())
    return f"{c[0:3]} {c[3:6]} {c[6:9]}"


def codigo_verificacao(sdp_a: str, sdp_b: str) -> str:
    """Código curto igual nos dois lados (impressões digitais DTLS) — detecta intermediário."""
    def fp(s):
        for linha in s.splitlines():
            if linha.startswith("a=fingerprint:"):
                return linha.split(" ", 1)[1].strip().upper()
        return ""
    base = "|".join(sorted([fp(sdp_a), fp(sdp_b)])).encode()
    n = int.from_bytes(hashlib.sha256(base).digest()[:4], "big") % 1000000
    return f"{n // 1000:03d} {n % 1000:03d}"


# ---------------- pedaços para a DHT ----------------
def em_pedacos(selado: bytes):
    mid = os.urandom(8)
    partes = [selado[i:i + PEDACO] for i in range(0, len(selado), PEDACO)]
    if len(partes) > MAX_PEDACOS:
        raise ValueError("mensagem grande demais para a DHT")
    return [bytes([i, len(partes)]) + mid + p for i, p in enumerate(partes)]


# ---------------- canal DHT ----------------
class CanalDHT:
    def __init__(self, dht: DHT, chaves: Chaves, papel: str):
        self.dht = dht
        self.ch = chaves
        self.meus = SAL_HOST if papel == "host" else SAL_CLIENTE
        self.deles = SAL_CLIENTE if papel == "host" else SAL_HOST
        self.nos = {}           # salt -> lista de nós próximos (cache de leitura)
        self.tokens = {}        # salt -> (instante, [(nó, token)]) (cache de escrita)
        self.busca_completa = {}
        self.ultimo_seq = 0
        self.fixos = {}         # salt -> nós sempre sondados (o PC publica quais são, ver host.py)
        self.tokens_extra = {}  # salt -> [(nó, token)]: nós que o outro lado está sondando
        self._buscando = {}
        self._achado_busca = {}

    async def aquecer(self, escrita=True):
        """Pré-localiza os nós dos itens que vamos ler e os tokens para gravar,
        assim sondar e responder ficam em ~1 s em vez de ~8 s."""
        async def ler(sal):
            _, _, nos = await self.dht.obter(self.ch.publica, sal)
            if nos:
                self.nos[sal] = nos

        async def gravar(sal):
            alvos = await self.dht.preparar(self.ch.publica, sal)
            if alvos:
                self.tokens[sal] = (time.monotonic(), alvos)
        tarefas = [ler(self.deles[0])]
        if escrita:
            tarefas.append(gravar(self.meus[0]))
        await asyncio.gather(*tarefas, return_exceptions=True)

    async def enviar(self, selado: bytes):
        seq = int(time.time() * 1000)
        pedacos = em_pedacos(selado)

        async def um(i, p):
            t, alvos = self.tokens.get(self.meus[i], (0, None))
            extra = self.tokens_extra.get(self.meus[i], [])
            if time.monotonic() - t > 300:
                alvos = None
                if extra:
                    alvos = await self.dht.preparar(self.ch.publica, self.meus[i])
            if extra:
                vistos = {a for a, _ in alvos or []}
                # os nós que o outro lado sonda primeiro: ele acha a mensagem na próxima sondagem
                alvos = [x for x in extra if x[0] not in vistos] + list(alvos or [])
            n, _ = await self.dht.gravar(self.ch.privada, self.meus[i], p, seq, alvos)
            if n == 0 and alvos:
                n, _ = await self.dht.gravar(self.ch.privada, self.meus[i], p, seq)
            return n
        res = await asyncio.gather(*(um(i, p) for i, p in enumerate(pedacos)), return_exceptions=True)
        return all(isinstance(r, int) and r > 0 for r in res)

    async def tokens_de(self, sal, nos):
        """Pega tokens de escrita de nós específicos (os que o outro lado publicou que sonda)."""
        from .dht import alvo
        a = alvo(self.ch.publica, sal)
        rs = await asyncio.gather(*(self.dht.consultar(tuple(n), "get", {"target": a}, 1.5) for n in nos),
                                  return_exceptions=True)
        self.tokens_extra[sal] = [(tuple(n), r[b"token"]) for n, r in zip(nos, rs)
                                  if isinstance(r, dict) and r.get(b"token")]
        return len(self.tokens_extra[sal])

    async def _ler(self, sal, seq_min=None):
        nos = self.nos.get(sal)
        if self.fixos.get(sal):
            nos = list(dict.fromkeys(list(self.fixos[sal]) + list(nos or [])))
        if not nos:
            seq, v, usados = await self.dht.obter(self.ch.publica, sal, seq_min=seq_min)
            if usados:
                self.nos[sal] = usados
            return seq, v
        seq, v, usados = await self.dht.obter(self.ch.publica, sal, nos=nos, seq_min=seq_min)
        if usados and not self.fixos.get(sal):
            self.nos[sal] = usados
        # busca completa em segundo plano (o item pode ter ido para nós que não conhecíamos);
        # a sondagem rápida continua a cada volta enquanto ela roda
        achado = self._achado_busca.pop(sal, None)
        if seq is None and achado and (seq_min is None or achado[0] > seq_min):
            seq, v = achado
        if seq is None and time.monotonic() - self.busca_completa.get(sal, 0) > 3 \
                and not (self._buscando.get(sal) and not self._buscando[sal].done()):
            self.busca_completa[sal] = time.monotonic()

            async def completa():
                s2, v2, u2 = await self.dht.obter(self.ch.publica, sal, seq_min=seq_min)
                if u2:
                    self.nos[sal] = list(dict.fromkeys(list(u2) + list(self.nos.get(sal) or [])))[:24]
                if s2 is not None:
                    self._achado_busca[sal] = (s2, v2)
            self._buscando[sal] = asyncio.ensure_future(completa())
        return seq, v

    def nos_compactos(self, sal, n=8):
        """Nós que sondamos para `sal`, em 6 bytes cada (IPv4+porta), para mandar ao outro lado."""
        import struct
        out = b""
        for ip, porta in [a for a in (self.nos.get(sal) or []) if ":" not in a[0]][:n]:
            out += socket.inet_aton(ip) + struct.pack("!H", porta)
        return out

    async def receber(self, desde_ms=None):
        """Uma sondagem. Devolve os bytes selados de uma mensagem nova ou None.
        `desde_ms`: ignora itens gravados antes disso (o seq é o relógio de quem gravou, em ms) —
        assim a sondagem não para numa mensagem velha de outra sessão."""
        minimo = max(self.ultimo_seq, desde_ms or 0)
        seq, v = await self._ler(self.deles[0], minimo or None)
        if seq is None or seq <= minimo or not v or len(v) < 10:
            return None
        total, mid = v[1], v[2:10]
        partes = {0: v[10:]}
        if total > 1:
            rs = await asyncio.gather(*(self._ler(self.deles[i]) for i in range(1, total)),
                                      return_exceptions=True)
            for i, r in enumerate(rs, 1):
                if isinstance(r, tuple) and r[1] and r[1][2:10] == mid and r[1][0] == i:
                    partes[i] = r[1][10:]
        if len(partes) != total:
            return None          # pedaços ainda propagando; tenta na próxima sondagem
        self.ultimo_seq = seq
        return b"".join(partes[i] for i in range(total))


# ---------------- canal LAN ----------------
class _LanProto(asyncio.DatagramProtocol):
    def __init__(self, canal):
        self.canal = canal

    def datagram_received(self, data, addr):
        self.canal._chegou(data, addr)

    def error_received(self, exc):
        pass


class CanalLAN:
    """UDP na porta 21118 (IPv4 com broadcast + IPv6). Serve para três coisas:
    - pedidos/respostas cifrados (MAGICO + ident_lan + selado);
    - anúncio de presença na rede local (ANUNCIO), para a lista "nesta rede";
    - campainha: o cliente manda o pedido direto para o IP que o PC publicou na DHT.
    `chaves` pode ser None (só escuta anúncios)."""

    def __init__(self, chaves, host: bool, ao_anuncio=None, ao_consulta=None):
        self.ch = chaves
        self.host = host
        self.fila = asyncio.Queue()
        self.transporte = None
        self.transporte6 = None
        self.ao_anuncio = ao_anuncio        # fn(dados_dict, addr)
        self.ao_consulta = ao_consulta      # fn(addr)

    async def iniciar(self):
        loop = asyncio.get_running_loop()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("0.0.0.0", PORTA_LAN if self.host else 0))
        self.transporte, _ = await loop.create_datagram_endpoint(lambda: _LanProto(self), sock=sock)
        try:
            s6 = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            s6.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
            s6.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s6.bind(("::", PORTA_LAN if self.host else 0))
            self.transporte6, _ = await loop.create_datagram_endpoint(lambda: _LanProto(self), sock=s6)
        except OSError:
            self.transporte6 = None

    def fechar(self):
        for t in (self.transporte, self.transporte6):
            if t:
                t.close()

    def _chegou(self, data, addr):
        mag = data[:4]
        if mag == MAGICO:
            self.fila.put_nowait((data, addr))
        elif mag == ANUNCIO and self.ao_anuncio:
            try:
                self.ao_anuncio(json.loads(data[4:].decode()), addr)
            except ValueError:
                pass
        elif mag == CONSULTA and self.ao_consulta:
            self.ao_consulta(addr)

    def _mandar(self, pacote, addr):
        t = self.transporte6 if ":" in addr[0] else self.transporte
        if t:
            try:
                t.sendto(pacote, addr[:2])
            except OSError:
                pass

    def enviar(self, selado: bytes, addr=None):
        pacote = MAGICO + self.ch.ident_lan + selado
        if addr:
            self._mandar(pacote, addr)
            return
        for destino in _broadcasts():
            self._mandar(pacote, (destino, PORTA_LAN))

    def anunciar(self, dados: dict, addr=None):
        pacote = ANUNCIO + json.dumps(dados, separators=(",", ":"), ensure_ascii=False).encode()
        for destino in ([addr] if addr else [(d, PORTA_LAN) for d in _broadcasts()]):
            self._mandar(pacote, destino)

    def consultar(self):
        """Pergunta "quem está aí?" na rede local; os PCs respondem com um anúncio."""
        for destino in _broadcasts():
            self._mandar(CONSULTA, (destino, PORTA_LAN))

    async def receber(self):
        """Espera um pacote nosso. Devolve (selado, addr)."""
        while True:
            data, addr = await self.fila.get()
            if self.ch and data[4:12] == self.ch.ident_lan:
                return data[12:], addr


# ---------------- endereços diretos (campainha) ----------------
SAL_ENDERECOS = b"e0"


def enderecos_locais():
    """IPv4 privados das placas de rede + IPv6 globais (onde este PC pode ser alcançado direto)."""
    import ipaddress
    v4, v6 = set(), set()
    try:
        for fam, _, _, _, sa in socket.getaddrinfo(socket.gethostname(), None):
            ip = sa[0].split("%")[0]
            a = ipaddress.ip_address(ip)
            if fam == socket.AF_INET and a.is_private and not a.is_loopback:
                v4.add(ip)
            elif fam == socket.AF_INET6 and a.is_global:
                v6.add(ip)
    except (OSError, ValueError):
        pass
    for fam, alvo_ in ((socket.AF_INET, "192.0.2.1"), (socket.AF_INET6, "2001:4860:4860::8888")):
        try:                                   # o IP de saída padrão (não manda nada)
            s = socket.socket(fam, socket.SOCK_DGRAM)
            s.connect((alvo_, 53))
            ip = s.getsockname()[0]
            s.close()
            a = ipaddress.ip_address(ip)
            if fam == socket.AF_INET and a.is_private and not a.is_loopback:
                v4.add(ip)
            elif fam == socket.AF_INET6 and a.is_global:
                v6.add(ip)
        except (OSError, ValueError):
            pass
    return sorted(v4), sorted(v6)


def _broadcasts():
    destinos = {"255.255.255.255", "127.0.0.1"}
    try:
        import fcntl
        import struct
        for _, nome in socket.if_nameindex():
            if nome == "lo":
                continue
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                r = fcntl.ioctl(s.fileno(), 0x8919, struct.pack("256s", nome.encode()[:15]))  # SIOCGIFBRDADDR
                destinos.add(socket.inet_ntoa(r[20:24]))
            except OSError:
                pass
            finally:
                s.close()
    except Exception:
        pass
    return destinos
