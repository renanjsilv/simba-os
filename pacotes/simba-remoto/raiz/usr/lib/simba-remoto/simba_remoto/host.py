"""Servidor do Simba Remoto: espera conexões (LAN + DHT), pede aprovação e transmite a tela por WebRTC."""
import asyncio
import hmac
import json
import logging
import os
import random
import socket
import sys
import threading
import time
from pathlib import Path

import av
import numpy as np
from aiortc import (RTCConfiguration, RTCIceServer, RTCPeerConnection,
                    RTCSessionDescription, VideoStreamTrack)
from aiortc.codecs import vpx

from . import nat
from .dht import DHT
from .sinal import (PORTA_LAN, SAL_ENDERECOS, CanalDHT, CanalLAN, Chaves, chave_senha,
                    codigo_verificacao, enderecos_locais, prova_senha)

log = logging.getLogger("simba-remoto")
STUN = "stun:stun.l.google.com:19302"

# Tela tem muito texto: codificador afinado (preset rápido, CRF, sem recriar a cada variação de banda)
from . import codificador  # noqa: E402
codificador.instalar()
vpx.DEFAULT_BITRATE = 4_000_000
vpx.MAX_BITRATE = 12_000_000


from .config import (CONFIG, carregar_config, salvar_config, novo_codigo, definir_senha,  # noqa: E402,F401
                     salvar_recente, remover_recente, obter_recentes, salvar_senha_remota,
                     obter_senha_remota, remover_senha_remota)


class TrackTela(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.loop = asyncio.get_running_loop()
        self.novo = asyncio.Event()
        self.ultimo = None

    def quadro(self, dados, w, h):          # thread do GStreamer
        self.ultimo = (dados, w, h)
        self.loop.call_soon_threadsafe(self.novo.set)

    async def recv(self):
        pts, base = await self.next_timestamp()
        if self.ultimo is None or not self.novo.is_set():
            try:
                await asyncio.wait_for(self.novo.wait(), 1.0)
            except asyncio.TimeoutError:
                pass
        self.novo.clear()
        if self.ultimo is None:
            quadro = av.VideoFrame(640, 360, "yuv420p")
            for p in quadro.planes:
                p.update(bytes(p.buffer_size))
        else:
            dados, w, h = self.ultimo
            arr = np.frombuffer(dados, np.uint8)[: w * h * 3 // 2].reshape(h * 3 // 2, w)
            quadro = av.VideoFrame.from_ndarray(arr, format="yuv420p")
        quadro.pts = pts
        quadro.time_base = base
        return quadro


def consertar_oferta(sdp: str) -> str:
    """Seções de áudio sem a descrição do Opus (o app 1.0/1.1 apagava os codecs do áudio que o
    Android põe por conta própria) fariam o aiortc recusar tudo: deixa a seção só com Opus."""
    linhas = sdp.replace("\r\n", "\n").split("\n")
    saida = []
    i = 0
    while i < len(linhas):
        l = linhas[i]
        if l.startswith("m=audio"):
            fim = i + 1
            while fim < len(linhas) and not linhas[fim].startswith("m="):
                fim += 1
            secao = linhas[i + 1:fim]
            if not any(x.lower().startswith("a=rtpmap:") and "opus/" in x.lower() for x in secao):
                saida.append(" ".join(l.split(" ")[:3] + ["111"]))
                saida += [x for x in secao if x and not x.startswith(("a=rtpmap:", "a=fmtp:", "a=rtcp-fb:"))]
                saida += ["a=rtpmap:111 opus/48000/2", "a=fmtp:111 minptime=10;useinbandfec=1"]
                i = fim
                continue
        if l:
            saida.append(l)
        i += 1
    return "\r\n".join(saida) + "\r\n"


class _EntradaTeste:
    def tratar(self, msg):
        log.info("entrada (teste): %s", msg)

    def fechar(self):
        pass


class Sessao:
    def __init__(self, servidor, cab, sdp_oferta, responder, autorizado=False):
        self.s = servidor
        self.autorizado = autorizado        # senha do acesso não supervisionado conferida
        self.aprovacao = None               # tarefa esperando o clique no PC
        self.ficha = None
        self.encerrada = False
        self.conectado = False
        self.cab = cab
        self.sdp_oferta = sdp_oferta
        self.responder = responder          # async fn(selado)
        self.pc = None
        self.track = None
        self.entrada = None
        self.fim = asyncio.Event()

    async def rodar(self):
        s = self.s
        nome = str(self.cab.get("nome", "?"))[:60]
        self.pc = pc = RTCPeerConnection(RTCConfiguration(iceServers=[RTCIceServer(STUN)]))
        track = TrackTela()
        self.track = track
        if s.ultimo_quadro:
            track.quadro(*s.ultimo_quadro)
        await pc.setRemoteDescription(RTCSessionDescription(consertar_oferta(self.sdp_oferta), "offer"))
        pc.addTrack(track)
        await pc.setLocalDescription(await pc.createAnswer())
        sdp = pc.localDescription.sdp
        sas = codigo_verificacao(self.sdp_oferta, sdp)
        if self.autorizado:
            aceito = True
            s.evento("reconectado" if getattr(self, "reconexao", False) else "autonomo", nome=nome)
        else:
            s.evento("pedido", nome=nome, verificacao=sas)
            if s.cfg.get("autonomo") and s.cfg.get("senha_chave"):
                # avisa quem conecta que dá para entrar com a senha (sem esperar alguém no PC).
                # Só se o pedido continuar esperando: o aviso e a resposta vão para o mesmo item da
                # DHT, e um aviso gravado depois apagaria a resposta.
                async def avisar_senha():
                    await asyncio.sleep(0.8)
                    if self.aprovacao is not None and not self.aprovacao.done():
                        await self.responder(s.chaves.selar(self._cab("senha"), ""))
                asyncio.ensure_future(avisar_senha())
            self.aprovacao = asyncio.ensure_future(s.aprovar(nome, sas))
            try:
                aceito = await self.aprovacao
            except asyncio.CancelledError:
                # outro pedido do mesmo cliente chegou com a senha certa
                await pc.close()
                self.fim.set()
                return
            finally:
                self.aprovacao = None
        if not aceito:
            await self.responder(s.chaves.selar(self._cab("recusa"), ""))
            await pc.close()
            s.evento("recusado", nome=nome)
            return

        # captura compartilhada da tela
        try:
            captura = await s.obter_captura()
        except Exception as e:
            log.error("captura falhou: %s", e)
            await self.responder(s.chaves.selar(self._cab("recusa", motivo=f"captura: {e}"), ""))
            await pc.close()
            s.evento("erro", texto=f"Não foi possível capturar a tela: {e}")
            return

        if os.environ.get("SIMBA_REMOTO_TELA_TESTE"):
            self.entrada = _EntradaTeste()       # testes: não mexe no mouse/teclado de verdade
        else:
            if sys.platform == "win32":
                from .entrada_windows import Entrada
            else:
                from .entrada import Entrada
            self.entrada = Entrada(captura.posicao, captura.tamanho)

        @pc.on("datachannel")
        def _canal(canal):
            @canal.on("message")
            def _msg(m):
                try:
                    self.entrada.tratar(json.loads(m))
                except Exception as e:
                    log.debug("mensagem ruim: %s", e)
            canal.send(json.dumps({"t": "tela", "w": captura.largura, "h": captura.altura,
                                   "nome": s.cfg["nome"]}))
            # ficha de reconexão: só trafega aqui dentro (DTLS). Se a conexão cair (celular
            # minimizado, troca de rede), o cliente volta sem precisar de aceite/senha.
            fid, chave = os.urandom(8).hex(), os.urandom(32)
            s.fichas[fid] = {"chave": chave, "nome": nome, "expira": None}
            self.ficha = fid
            canal.send(json.dumps({"t": "ficha", "id": fid, "k": chave.hex()}))

        @pc.on("connectionstatechange")
        async def _estado():
            st = pc.connectionState
            log.info("conexão: %s", st)
            if st == "connected":
                self.conectado = True
                par = _par_escolhido(pc)
                conectados = len([x for x in s.sessoes.values() if x.conectado])
                s.evento("conectado", nome=nome, caminho=par, total=conectados)
            elif st in ("failed", "closed"):
                self.fim.set()

        sdp = await asyncio.get_running_loop().run_in_executor(None, nat.acrescentar_upnp, sdp, s.upnp)
        await self.responder(s.chaves.selar(self._cab("resposta"), sdp))
        s.evento("conectando", nome=nome)
        try:
            await asyncio.wait_for(self._esperar_conectar(), 45)
        except asyncio.TimeoutError:
            s.evento("erro", texto=f"{nome} não conseguiu alcançar este PC (tempo esgotado).")
            self.fim.set()
        await self.fim.wait()
        await self.encerrar()

    async def _esperar_conectar(self):
        while self.pc.connectionState not in ("connected", "failed", "closed"):
            await asyncio.sleep(0.2)

    def _cab(self, t, **extra):
        return {"v": 1, "t": t, "sid": self.cab.get("sid", ""), "ts": int(time.time()),
                "nome": self.s.cfg["nome"], **extra}

    async def encerrar(self):
        if self.encerrada:
            return
        self.encerrada = True
        self.s.remover_sessao(self)
        if self.ficha and self.ficha in self.s.fichas:
            self.s.fichas[self.ficha]["expira"] = time.time() + 600
        if self.entrada:
            try:
                self.entrada.fechar()
            except Exception as e:
                log.debug("erro ao fechar entrada: %s", e)
        if self.pc:
            try:
                await self.pc.close()
            except Exception:
                pass
        self.fim.set()


def _par_escolhido(pc):
    try:
        sctp = pc.sctp
        ice = (sctp.transport.transport if sctp else pc.getTransceivers()[0].receiver.transport.transport)
        par = ice._connection._nominated.get(1)
        if par:
            tipo = par.remote_candidate.type
            ip = par.remote_candidate.host
            if tipo == "host":
                return "direto (IPv6)" if ":" in ip else "direto (rede local)"
            if par.local_candidate.foundation.startswith("upnp") or tipo in ("srflx", "prflx"):
                return "direto pela internet (P2P, NAT atravessado)"
            return "retransmitido"
    except Exception:
        pass
    return "direto (P2P)"


class Preparo:
    """Caminho até outro PC já aquecido: canal DHT com nós/tokens localizados e endereços diretos."""

    def __init__(self, servidor, codigo):
        self.codigo = codigo
        self.criado = time.time()
        self.chaves = Chaves(codigo)
        self.canal = CanalDHT(servidor.dht, self.chaves, "cliente")
        self.enderecos = []
        self.pronto = asyncio.ensure_future(self._rodar(servidor))

    async def _rodar(self, s):
        async def ends():
            try:
                _, v, _ = await s.dht.obter(self.chaves.publica, SAL_ENDERECOS)
                if v:
                    cab, _ = self.chaves.abrir(v)
                    if cab.get("t") == "end" and time.time() - cab.get("ts", 0) < 3 * 3600:
                        self.enderecos = [tuple(a[:2]) for a in cab.get("a", [])][:8]
                        nos = [tuple(n[:2]) for n in cab.get("n", [])][:12]
                        if nos:
                            k = await self.canal.tokens_de(self.canal.meus[0], nos)
                            log.debug("tokens nos nós sondados por %s: %d", self.codigo, k)
            except Exception as e:
                log.debug("endereços de %s: %s", self.codigo, e)
        await asyncio.gather(self.canal.aquecer(escrita=True), ends(), return_exceptions=True)
        log.info("preparado %s: endereços %s", self.codigo, self.enderecos)


class Servidor:
    """Roda num loop asyncio. `aprovar(nome, sas)` -> bool (async) e `evento(tipo, **dados)` vêm da interface."""

    def __init__(self, aprovar=None, evento=None):
        self.cfg = carregar_config()
        self.chaves = Chaves(self.cfg["codigo"])
        self._aprovar = aprovar
        self._evento = evento
        self.upnp = nat.UPnP()
        self.dht = DHT()
        self.sessoes = {}                   # sid -> Sessao
        self.captura = None
        self.captura_iniciando = None
        self.ultimo_quadro = None
        self.vistos = set()
        self.tarefas = []
        self.estado_rede = {}
        self.inicio = time.time()
        self.falhas = []
        self.fichas = {}                    # id -> {chave, nome, expira}
        self.vizinhos = {}                  # código -> {nome, so, ip, visto}: PCs nesta rede
        self.preparados = {}                # código -> Preparo (caminho até outro PC já aquecido)
        self.lan = None

    def evento(self, tipo, **dados):
        log.info("%s %s", tipo, dados)
        if self._evento:
            self._evento(tipo, dados)

    async def aprovar(self, nome, sas):
        if self._aprovar is None:
            return False
        r = self._aprovar(nome, sas)
        if asyncio.iscoroutine(r) or isinstance(r, asyncio.Future):
            return await r
        return bool(r)

    async def iniciar(self):
        loop = asyncio.get_running_loop()
        # rede local primeiro: é instantânea (a DHT leva alguns segundos para entrar)
        self.lan = CanalLAN(self.chaves, host=True, ao_anuncio=self._anuncio_recebido,
                            ao_consulta=self._consulta_recebida)
        try:
            await self.lan.iniciar()
            self.tarefas.append(asyncio.ensure_future(self._laco_lan()))
            self.tarefas.append(asyncio.ensure_future(self._laco_anuncio()))
        except OSError as e:
            log.warning("LAN indisponível: %s", e)
            self.lan = None
        await self.dht.iniciar()
        self.canal = CanalDHT(self.dht, self.chaves, "host")
        self.tarefas.append(asyncio.ensure_future(self._laco_dht()))
        self.tarefas.append(asyncio.ensure_future(self._diagnostico(loop)))

    async def _diagnostico(self, loop):
        upnp = await loop.run_in_executor(None, self.upnp.descobrir)
        v6 = await loop.run_in_executor(None, nat.ipv6_global)
        for _ in range(30):
            if self.dht.ip_externo:
                break
            await asyncio.sleep(0.5)
        self.estado_rede = {
            "upnp": bool(upnp and self.upnp.disponivel),
            "ipv6": v6,
            "ip_externo": (self.dht.ip_externo or ("",))[0],
            "dht": len(self.dht.bons),
        }
        self.evento("rede", **self.estado_rede)

    async def parar(self):
        for t in self.tarefas:
            t.cancel()
        for s in list(self.sessoes.values()):
            await s.encerrar()
        self.sessoes.clear()
        if self.captura:
            try:
                self.captura.parar()
            except Exception:
                pass
            self.captura = None
        self.ultimo_quadro = None
        self.dht.fechar()
        if getattr(self, "lan", None):
            self.lan.fechar()

    def _ao_quadro_captura(self, dados, w, h):
        self.ultimo_quadro = (dados, w, h)
        for s in list(self.sessoes.values()):
            if s.track and not s.encerrada:
                s.track.quadro(dados, w, h)

    async def obter_captura(self):
        if self.captura and self.captura.largura > 0:
            return self.captura
        if self.captura_iniciando:
            await self.captura_iniciando
            if self.captura:
                return self.captura

        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self.captura_iniciando = fut
        try:
            if sys.platform == "win32":
                from .captura_windows import Captura
            else:
                from .captura import Captura
            cap = Captura(self._ao_quadro_captura)
            await loop.run_in_executor(None, cap.iniciar)
            self.captura = cap
            fut.set_result(cap)
            return cap
        except Exception as e:
            fut.set_exception(e)
            raise
        finally:
            self.captura_iniciando = None

    def remover_sessao(self, sessao):
        sid = sessao.cab.get("sid")
        if sid in self.sessoes:
            del self.sessoes[sid]
        elif sessao in self.sessoes.values():
            for k, v in list(self.sessoes.items()):
                if v is sessao:
                    del self.sessoes[k]
                    break
        if not self.sessoes:
            if self.captura:
                try:
                    self.captura.parar()
                except Exception as e:
                    log.warning("erro ao parar captura: %s", e)
                self.captura = None
            self.ultimo_quadro = None
            threading.Thread(target=self.upnp.liberar, daemon=True).start()
            self.evento("desconectado")
        else:
            conectados = [s for s in self.sessoes.values() if s.conectado]
            nomes = [s.cab.get("nome", "?") for s in conectados]
            self.evento("sessao_encerrada", nome=sessao.cab.get("nome", "?"),
                        restantes=len(conectados), nomes=nomes)

    # ------------------------------------------------ presença na rede local
    def _meu_anuncio(self):
        return {"c": self.cfg["codigo"], "n": self.cfg["nome"][:40],
                "s": "windows" if sys.platform == "win32" else "linux"}

    def _anuncio_recebido(self, d, addr):
        cod = str(d.get("c", ""))
        if len(cod) != 9 or not cod.isdigit() or cod == self.cfg["codigo"]:
            return
        novo = cod not in self.vizinhos
        self.vizinhos[cod] = {"nome": str(d.get("n", ""))[:40] or cod, "so": str(d.get("s", ""))[:10],
                              "ip": addr[0], "visto": time.time()}
        if novo:
            self.evento("vizinhos", lista=self.lista_vizinhos())

    def _consulta_recebida(self, addr):
        if self.lan:
            self.lan.anunciar(self._meu_anuncio(), addr)

    def lista_vizinhos(self):
        agora = time.time()
        return sorted(({"codigo": c, **v} for c, v in self.vizinhos.items() if agora - v["visto"] < 75),
                      key=lambda v: v["nome"].lower())

    async def _laco_anuncio(self):
        """Anuncia este PC e pergunta quem mais está na rede (ao abrir) e depois a cada 20 s."""
        self.lan.consultar()
        n = 0
        while True:
            self.lan.anunciar(self._meu_anuncio())
            await asyncio.sleep(0.5 if n < 2 else 20)
            n += 1
            antes = len(self.vizinhos)
            agora = time.time()
            self.vizinhos = {c: v for c, v in self.vizinhos.items() if agora - v["visto"] < 75}
            if len(self.vizinhos) != antes:
                self.evento("vizinhos", lista=self.lista_vizinhos())

    # ------------------------------------------------ endereços diretos na DHT (campainha)
    async def _laco_enderecos(self):
        ultimo = None
        while True:
            try:
                v4, v6 = await asyncio.get_running_loop().run_in_executor(None, enderecos_locais)
                lista = [[ip, PORTA_LAN] for ip in v6 + v4]
                # nós da DHT que este PC sonda: quem conecta grava o pedido neles também, e o pedido
                # é achado na próxima sondagem (~1 s) em vez de depender de os dois verem os mesmos nós
                sal_c = self.canal.deles[0]
                nos = [list(n) for n in (self.canal.nos.get(sal_c) or []) if ":" not in n[0]][:12]
                anteriores = self.canal.fixos.get(sal_c, [])[:12]
                self.canal.fixos[sal_c] = [tuple(n) for n in nos] + [n for n in anteriores
                                                                      if list(n) not in nos]
                if lista or nos:
                    selado = self.chaves.selar({"v": 1, "t": "end", "ts": int(time.time()), "a": lista,
                                                "n": nos}, "")
                    alvos = await self.dht.preparar(self.chaves.publica, SAL_ENDERECOS)
                    n, _ = await self.dht.gravar(self.chaves.privada, SAL_ENDERECOS, selado,
                                                 int(time.time() * 1000), alvos)
                    log.info("endereços publicados na DHT (%d nós): %s", n, lista)
                    ultimo = lista
            except Exception as e:
                log.debug("publicar endereços: %s", e)
            await asyncio.sleep(240)           # itens na DHT duram ~2 h; renovar mantém o IP atual

    # ------------------------------------------------ preparar conexão de saída
    def preaquecer(self, codigo):
        """Chamado quando a pessoa termina de digitar um código (ou para os recentes): já acha os
        nós da DHT e os endereços diretos daquele PC, para o Conectar sair na hora."""
        cod = "".join(c for c in codigo if c.isdigit())
        if len(cod) != 9 or cod == self.cfg["codigo"]:
            return None
        p = self.preparados.get(cod)
        if p and time.time() - p.criado < 240:
            return p
        p = Preparo(self, cod)
        self.preparados[cod] = p
        return p

    async def _laco_lan(self):
        while True:
            selado, addr = await self.lan.receber()
            async def responder(dados, addr=addr):
                for _ in range(3):
                    self.lan.enviar(dados, addr)
                    await asyncio.sleep(0.05)
            await self._tratar(selado, responder, "lan")

    async def _laco_dht(self):
        await self.canal.aquecer()
        self.evento("pronto")
        # publica endereços e nós sondados depois do aquecimento (a lista de nós já existe)
        self.tarefas.append(asyncio.ensure_future(self._laco_enderecos()))
        ultimo_aquecer = time.monotonic()
        while True:
            try:
                # ofertas valem 40 s; 2 min de folga para relógios desacertados entre os PCs
                selado = await self.canal.receber(desde_ms=int((time.time() - 160) * 1000))
                if selado:
                    async def responder(dados):
                        ok = await self.canal.enviar(dados)
                        log.info("resposta gravada na DHT: %s", ok)
                    await self._tratar(selado, responder, "dht")
            except Exception as e:
                log.debug("sondagem DHT: %s", e)
            if time.monotonic() - ultimo_aquecer > 30:
                ultimo_aquecer = time.monotonic()
                asyncio.ensure_future(self.canal.aquecer())
            await asyncio.sleep(1.0)

    async def _tratar(self, selado, responder, origem):
        try:
            cab, sdp = self.chaves.abrir(selado)
        except Exception:
            return
        sid = cab.get("sid")
        if cab.get("t") != "oferta" or not sid or sid in self.vistos:
            return
        # ofertas velhas ficam na DHT por até 2 h: só vale o que for recente
        ts = cab.get("ts", 0)
        if abs(time.time() - ts) > 40 or ts < self.inicio - 5:
            return
        self.vistos.add(sid)
        log.info("oferta %s via %s de %s", sid, origem, cab.get("nome"))

        def recusar(motivo):
            return responder(self.chaves.selar({"v": 1, "t": "recusa", "sid": sid, "ts": int(time.time()),
                                                "nome": self.cfg["nome"], "motivo": motivo}, ""))
        autorizado = False
        reconexao = False
        agora = time.time()
        self.fichas = {k: v for k, v in self.fichas.items() if v["expira"] is None or v["expira"] > agora}
        ficha = self.fichas.get(str(cab.get("ficha_id", "")))
        if ficha and cab.get("prova_ficha"):
            esperado = prova_senha(ficha["chave"], sid, sdp)
            if hmac.compare_digest(esperado, str(cab["prova_ficha"])):
                autorizado = reconexao = True
                del self.fichas[cab["ficha_id"]]        # uma ficha por reconexão; a sessão nova emite outra
                log.info("reconexão de %s com ficha", cab.get("nome"))
                for s in list(self.sessoes.values()):
                    if s.ficha == cab.get("ficha_id") or s.cab.get("sid") == sid:
                        if s.aprovacao:
                            s.aprovacao.cancel()
                        await s.encerrar()
        if not autorizado and cab.get("prova"):
            agora = time.time()
            self.falhas = [t for t in self.falhas if agora - t < 300]
            if len(self.falhas) >= 5:
                await recusar("muitas senhas erradas; tente em 5 minutos")
                return
            chave = self.cfg.get("senha_chave")
            if not (self.cfg.get("autonomo") and chave):
                await recusar("acesso com senha desativado neste PC")
                return
            esperado = prova_senha(bytes.fromhex(chave), sid, sdp)
            if not hmac.compare_digest(esperado, str(cab["prova"])):
                self.falhas.append(agora)
                self.evento("senha_errada", nome=cab.get("nome", "?"))
                await recusar("senha incorreta")
                return
            autorizado = True
            # pedido anterior com mesmo sid ainda esperando o clique no PC: cancela
            for s in list(self.sessoes.values()):
                if s.cab.get("sid") == sid and s.aprovacao:
                    s.aprovacao.cancel()
        if len(self.sessoes) >= 16:
            await recusar("muitas conexões ativas no momento")
            return
        tokens_cliente = None
        if origem == "dht" and cab.get("nh"):
            # o cliente disse quais nós sonda: pega tokens deles já (em paralelo com a sessão)
            import base64
            import struct
            try:
                b = base64.b64decode(cab["nh"])[:8 * 6]
                nos = [(socket.inet_ntoa(b[i:i + 4]), struct.unpack("!H", b[i + 4:i + 6])[0])
                       for i in range(0, len(b) - 5, 6)]
                tokens_cliente = asyncio.ensure_future(self.canal.tokens_de(self.canal.meus[0], nos))
            except Exception:
                tokens_cliente = None
        if tokens_cliente is not None:
            resp_original = responder

            async def responder(dados, _r=resp_original, _t=tokens_cliente):
                try:
                    await asyncio.wait_for(asyncio.shield(_t), 1.5)
                except Exception:
                    pass
                await _r(dados)
        responder = self._responder_tambem_direto(responder, cab, sdp, origem)
        sessao = Sessao(self, cab, sdp, responder, autorizado)
        sessao.reconexao = reconexao
        self.sessoes[sid] = sessao
        asyncio.ensure_future(self._rodar_sessao(sessao))

    def _responder_tambem_direto(self, responder, cab, sdp, origem):
        """Além do caminho por onde a oferta chegou, manda a resposta por UDP direto para os IPs que o
        cliente pôs no SDP (IPv6 global, rede local), na porta que ele informou em "pl". O cliente já
        mandou pacotes dessa porta para cá, então o roteador dele deixa a resposta entrar: com IPv6
        isso evita esperar a DHT."""
        portas = cab.get("pl")
        if not self.lan or not isinstance(portas, list) or len(portas) != 2:
            return responder
        destinos = []
        for linha in sdp.splitlines():
            if not linha.startswith("a=candidate:"):
                continue
            p = linha.split()
            if len(p) < 8 or p[2].lower() != "udp" or p[7] not in ("host", "srflx"):
                continue
            ip = p[4]
            porta = portas[1] if ":" in ip else portas[0]
            if porta and isinstance(porta, int) and (ip, porta) not in destinos and not ip.endswith(".local"):
                destinos.append((ip, porta))
        destinos = destinos[:8]
        if not destinos:
            return responder

        async def ambos(dados):
            for _ in range(3):
                for d in destinos:
                    self.lan.enviar(dados, d)
                await asyncio.sleep(0.05)
            await responder(dados)
        return ambos

    async def _rodar_sessao(self, sessao):
        try:
            await sessao.rodar()
        except Exception as e:
            log.exception("sessão falhou")
            # guarda a oferta para diagnóstico e avisa o celular (senão ele fica esperando à toa)
            try:
                d = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "simba-remoto"
                d.mkdir(parents=True, exist_ok=True)
                (d / "ultima-oferta-com-erro.sdp").write_text(sessao.sdp_oferta)
                await sessao.responder(self.chaves.selar(sessao._cab("recusa", motivo=f"erro no PC: {e}"), ""))
            except Exception:
                pass
            self.evento("erro", texto=f"Falha ao abrir a conexão: {e}")
            await sessao.encerrar()

    def recarregar_config(self):
        self.cfg = carregar_config()

    def desconectar(self):
        for s in list(self.sessoes.values()):
            asyncio.ensure_future(s.encerrar())
