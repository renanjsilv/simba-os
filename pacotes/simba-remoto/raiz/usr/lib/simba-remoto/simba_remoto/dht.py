"""Cliente mínimo da DHT Mainline do BitTorrent (BEP 5) com itens mutáveis (BEP 44).

É a "sinalização sem servidor" do Simba Remoto: a oferta/resposta WebRTC (cifradas)
são gravadas como itens mutáveis assinados com Ed25519 na rede DHT pública
(milhões de nós de qBittorrent, Transmission, libtorrent...). Nenhum servidor nosso.

O nó roda em modo somente-leitura (BEP 43, "ro": 1): pergunta e grava, mas não
entra na tabela de roteamento dos outros (ficaria atrás de NAT de qualquer jeito).
"""
import asyncio
import hashlib
import json
import os
import random
import socket
import struct
import time
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey)
from cryptography.exceptions import InvalidSignature

from . import bencode

INICIAIS = [
    ("router.bittorrent.com", 6881),
    ("dht.transmissionbt.com", 6881),
    ("router.utorrent.com", 6881),
    ("dht.libtorrent.org", 25401),
    ("dht.aelitis.com", 6881),
]
K = 8          # nós mais próximos que guardam o item
ALFA = 8       # consultas em paralelo
CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "simba-remoto" / "nos-dht.json"


def _dist(a: bytes, b: bytes) -> int:
    return int.from_bytes(a, "big") ^ int.from_bytes(b, "big")


def _nos_compactos(b: bytes, v6=False):
    tam = 38 if v6 else 26
    for i in range(0, len(b) - tam + 1, tam):
        nid = b[i:i + 20]
        if v6:
            ip = socket.inet_ntop(socket.AF_INET6, b[i + 20:i + 36])
            porta = struct.unpack("!H", b[i + 36:i + 38])[0]
        else:
            ip = socket.inet_ntoa(b[i + 20:i + 24])
            porta = struct.unpack("!H", b[i + 24:i + 26])[0]
        if porta:
            yield nid, (ip, porta)


def assinatura_buffer(salt: bytes, seq: int, v: bytes) -> bytes:
    buf = b""
    if salt:
        buf += b"4:salt" + bencode.codificar(salt)
    return buf + b"3:seqi%de1:v" % seq + bencode.codificar(v)


def alvo(chave_pub: bytes, salt: bytes) -> bytes:
    return hashlib.sha1(chave_pub + salt).digest()


class _Proto(asyncio.DatagramProtocol):
    def __init__(self, dht):
        self.dht = dht

    def datagram_received(self, data, addr):
        self.dht._recebido(data, addr)

    def error_received(self, exc):
        pass


class DHT:
    def __init__(self):
        self.id = os.urandom(20)
        self.transporte = None
        self.pendentes: dict[bytes, asyncio.Future] = {}
        self.bons: dict[tuple, bytes] = {}   # addr -> id (nós que responderam)
        self.ip_externo = None               # BEP 42: o "ip" que os nós nos veem

    async def iniciar(self):
        loop = asyncio.get_running_loop()
        self.transporte, _ = await loop.create_datagram_endpoint(
            lambda: _Proto(self), local_addr=("0.0.0.0", 0))
        try:
            for ip, porta, nid in json.loads(CACHE.read_text()):
                self.bons[(ip, porta)] = bytes.fromhex(nid)
        except Exception:
            pass

    def fechar(self):
        self._salvar_cache()
        if self.transporte:
            self.transporte.close()

    def _salvar_cache(self):
        try:
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            nos = [[a[0], a[1], n.hex()] for a, n in self.bons.items() if len(n) == 20][-300:]
            if nos:
                CACHE.write_text(json.dumps(nos))
        except Exception:
            pass

    # ---------- KRPC ----------
    def _recebido(self, data, addr):
        try:
            msg = bencode.decodificar(data)
            tid = msg.get(b"t")
        except Exception:
            return
        fut = self.pendentes.pop(tid, None)
        if not fut or fut.done():
            return
        if msg.get(b"y") == b"r":
            r = msg.get(b"r", {})
            if b"id" in r:
                self.bons[addr] = r[b"id"]
            ip = msg.get(b"ip")
            if isinstance(ip, bytes) and len(ip) == 6:
                self.ip_externo = (socket.inet_ntoa(ip[:4]), struct.unpack("!H", ip[4:])[0])
            fut.set_result(r)
        else:
            fut.set_exception(RuntimeError(str(msg.get(b"e"))))

    async def consultar(self, addr, metodo: str, args: dict, espera=2.0):
        tid = os.urandom(4)
        while tid in self.pendentes:
            tid = os.urandom(4)
        fut = asyncio.get_running_loop().create_future()
        self.pendentes[tid] = fut
        args = dict(args, id=self.id)
        pacote = bencode.codificar({"t": tid, "y": "q", "q": metodo, "a": args, "ro": 1})
        try:
            self.transporte.sendto(pacote, addr)
            return await asyncio.wait_for(fut, espera)
        except (asyncio.TimeoutError, OSError):
            self.bons.pop(addr, None)
            raise
        finally:
            self.pendentes.pop(tid, None)

    async def _iniciais(self):
        loop = asyncio.get_running_loop()
        addrs = list(self.bons.keys())
        for host, porta in INICIAIS:
            try:
                infos = await loop.getaddrinfo(host, porta, family=socket.AF_INET, type=socket.SOCK_DGRAM)
                addrs += [i[4][:2] for i in infos]
            except OSError:
                pass
        return list(dict.fromkeys(addrs))

    # ---------- busca iterativa ----------
    async def busca(self, alvo_: bytes, seq_min=None):
        """Busca os K nós mais próximos do alvo. Devolve lista de
        (dist, addr, id, resposta) dos que responderam, mais próximos primeiro."""
        candidatos = {}   # addr -> id
        for a in await self._iniciais():
            candidatos[a] = self.bons.get(a, b"")
        consultados = set()
        respostas = {}    # addr -> (id, r)

        def ordem(item):
            addr, nid = item
            return _dist(nid, alvo_) if nid else (1 << 161)

        args = {"target": alvo_}
        if seq_min is not None:
            args["seq"] = seq_min

        async def um(addr):
            try:
                r = await self.consultar(addr, "get", args, 1.2)
            except Exception:
                return
            nid = r.get(b"id", b"")
            if len(nid) != 20:
                return
            respostas[addr] = (nid, r)
            for nid2, a2 in _nos_compactos(r.get(b"nodes", b"")):
                if a2 not in candidatos:
                    candidatos[a2] = nid2

        inicio = time.monotonic()
        voando = set()
        while time.monotonic() - inicio < 12:
            ordenados = sorted(candidatos.items(), key=ordem)
            # parar quando os K mais próximos que responderam já foram todos consultados
            melhores = sorted(respostas.items(), key=lambda x: _dist(x[1][0], alvo_))[:K]
            limite = _dist(melhores[-1][1][0], alvo_) if len(melhores) >= K else None
            fila = [a for a, nid in ordenados if a not in consultados
                    and (limite is None or (nid and _dist(nid, alvo_) < limite))]
            while fila and len(voando) < ALFA:
                a = fila.pop(0)
                consultados.add(a)
                voando.add(asyncio.ensure_future(um(a)))
            if not voando:
                break
            _, voando = await asyncio.wait(voando, return_when=asyncio.FIRST_COMPLETED)
        for t in voando:
            t.cancel()
        self._salvar_cache()
        res = sorted(((_dist(nid, alvo_), a, nid, r) for a, (nid, r) in respostas.items()),
                     key=lambda x: x[0])
        return res[:K * 2]

    # ---------- BEP 44 ----------
    @staticmethod
    def _valor_valido(r, pub: bytes, salt: bytes):
        v, seq, sig, k = r.get(b"v"), r.get(b"seq"), r.get(b"sig"), r.get(b"k")
        if v is None or seq is None or sig is None or k != pub:
            return None
        try:
            Ed25519PublicKey.from_public_bytes(pub).verify(sig, assinatura_buffer(salt, seq, v))
        except (InvalidSignature, ValueError):
            return None
        return seq, v

    async def obter(self, pub: bytes, salt: bytes, nos=None, seq_min=None):
        """Lê o item mutável (pub, salt). Se `nos` for dado, consulta só esses
        (mais rápido para quem fica sondando). Devolve (seq, v, nos_usados) ou (None, None, nos)."""
        a = alvo(pub, salt)
        args = {"target": a}
        if seq_min is not None:
            args["seq"] = seq_min
        if nos:
            # sondagem rápida: devolve assim que algum nó tiver um valor válido (não espera o mais lento)
            tarefas = {asyncio.ensure_future(self.consultar(n, "get", args, 1.5)): n for n in nos}
            achados = []
            pendentes = set(tarefas)
            while pendentes:
                feitas, pendentes = await asyncio.wait(pendentes, return_when=asyncio.FIRST_COMPLETED)
                for t in feitas:
                    r = t.result() if not t.exception() else None
                    if isinstance(r, dict):
                        achados.append((tarefas[t], r))
                vals = [self._valor_valido(r, pub, salt) for _, r in achados]
                if any(v and (seq_min is None or v[0] > seq_min) for v in vals):
                    break
            for t in pendentes:
                t.cancel()
            if len(achados) < len(nos) and pendentes:
                achados_addrs = {a for a, _ in achados}
                achados += [(n, {}) for n in nos if n not in achados_addrs]   # mantém a lista de nós
        else:
            res = await self.busca(a, seq_min)
            achados = [(addr, r) for _, addr, _, r in res]
        melhor = (None, None)
        for _, r in achados:
            val = self._valor_valido(r, pub, salt)
            if val and seq_min is not None and val[0] <= seq_min:
                continue
            if val and (melhor[0] is None or val[0] > melhor[0]):
                melhor = val
        usados = [addr for addr, r in achados if r][:K * 2] if achados else (nos or [])
        if nos and len(usados) < len(nos):
            usados = list(nos)
        return melhor[0], melhor[1], usados

    async def preparar(self, pub: bytes, salt: bytes):
        """Busca os nós que vão guardar (pub, salt) e seus tokens de escrita (valem ~10 min)."""
        res = await self.busca(alvo(pub, salt))
        return [(addr, r[b"token"]) for _, addr, _, r in res if r.get(b"token")][:K * 2]

    async def gravar(self, privada: Ed25519PrivateKey, salt: bytes, v: bytes, seq: int, com_token=None):
        """Grava o item nos K nós mais próximos. Devolve (quantos aceitaram, nós)."""
        pub = privada.public_key().public_bytes_raw()
        if len(bencode.codificar(v)) > 1000:
            raise ValueError("valor maior que 1000 bytes")
        if not com_token:
            com_token = await self.preparar(pub, salt)
        sig = privada.sign(assinatura_buffer(salt, seq, v))
        args = {"k": pub, "salt": salt, "seq": seq, "sig": sig, "v": v}
        tarefas = [asyncio.ensure_future(self.consultar(addr, "put", dict(args, token=tok), 1.5))
                   for addr, tok in com_token]
        # volta quando 3 nós confirmarem (o resto continua gravando em segundo plano)
        ok = 0
        pendentes = set(tarefas)
        while pendentes and ok < min(3, len(tarefas)):
            feitas, pendentes = await asyncio.wait(pendentes, return_when=asyncio.FIRST_COMPLETED)
            ok += sum(1 for t in feitas if not t.exception() and isinstance(t.result(), dict))
        for t in pendentes:          # continuam gravando; o resultado não importa mais
            t.add_done_callback(lambda t: t.cancelled() or t.exception())
        return ok, [addr for addr, _ in com_token]
