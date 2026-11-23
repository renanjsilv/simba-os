"""Cliente do Simba Remoto: conecta a outro PC via código de 9 dígitos (LAN + DHT),
estabelece conexão WebRTC, recebe vídeo e envia comandos de controle.
"""
import asyncio
import json
import logging
import os
import threading
import time
from typing import Callable, Optional

from aiortc import RTCConfiguration, RTCIceServer, RTCPeerConnection, RTCSessionDescription

from .dht import DHT
from .sinal import (PORTA_LAN, CanalDHT, CanalLAN, Chaves, chave_senha, codigo_verificacao,
                    prova_senha)

log = logging.getLogger("simba-remoto.cliente")
STUNS = [
    "stun:stun.l.google.com:19302",
    "stun:stun.cloudflare.com:3478",
    "stun:stun1.l.google.com:19302",
]


def enxugar_sdp(sdp: str) -> str:
    """Enxuga o SDP para caber em um único pacote: só H264/VP8, sem candidatos TCP, etc."""
    linhas = sdp.replace("\r\n", "\n").split("\n")
    manter_pt = set()
    for l in linhas:
        if l.startswith("a=rtpmap:"):
            partes = l[9:].split(" ", 1)
            pt = partes[0]
            nome = partes[1].split("/")[0].upper() if len(partes) > 1 else ""
            if nome in ("H264", "VP8"):
                manter_pt.add(pt)
    saida = []
    for l in linhas:
        if l.startswith("m=video"):
            p = l.split(" ")
            pts = [x for x in p[3:] if x in manter_pt]
            l = " ".join(p[:3] + pts)
        elif l.startswith(("a=rtpmap:", "a=fmtp:", "a=rtcp-fb:")):
            pt = l.split(":", 1)[1].split(" ", 1)[0]
            if pt not in manter_pt:
                continue
        elif l.startswith("a=extmap:") and "sdes:mid" not in l:
            continue
        elif l.startswith("a=candidate:") and " tcp " in l:
            continue
        elif l.startswith(("a=ssrc", "a=msid:")):
            continue
        if l:
            saida.append(l)
    return "\r\n".join(saida) + "\r\n"


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


class ConexaoCliente:
    def __init__(
        self,
        codigo: str,
        meu_nome: str,
        senha: Optional[str] = None,
        ficha: Optional[tuple] = None,
        on_evento: Optional[Callable[[str, dict], None]] = None,
        on_quadro: Optional[Callable] = None,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        preparo=None,
        ip_vizinho: Optional[str] = None,
    ):
        self.codigo = "".join(c for c in codigo if c.isdigit())
        self.meu_nome = meu_nome
        self.senha = senha
        self.ficha = ficha                  # (id, bytes_chave)
        self.on_evento = on_evento
        self.on_quadro = on_quadro
        self.loop = loop or asyncio.get_event_loop()
        self.preparo = preparo              # host.Preparo: DHT já aquecida + endereços diretos
        self.ip_vizinho = ip_vizinho        # IP visto no anúncio da rede local
        self._dht_propria = False

        self.chaves = Chaves(self.codigo)
        self.pc: Optional[RTCPeerConnection] = None
        self.canal = None
        self.dht: Optional[DHT] = None
        self.cdht: Optional[CanalDHT] = None
        self.lan: Optional[CanalLAN] = None

        self.sid = ""
        self.sdp_local = ""
        self.selado = b""
        self.sas = ""
        self.nome_remoto = ""
        self.caminho = ""
        self.largura_tela = 0
        self.altura_tela = 0

        self.chave_senha = chave_senha(senha, self.codigo) if senha else None
        self.encerrado = False
        self.tarefas = []
        self._resposta_fut: Optional[asyncio.Future] = None
        self._ficha_recebida = None
        self._thread_loop = None

    def evento(self, tipo: str, **dados):
        log.info("Cliente ev [%s]: %s", tipo, dados)
        if self.on_evento:
            try:
                self.on_evento(tipo, dados)
            except Exception as e:
                log.debug("Erro no callback on_evento: %s", e)

    async def iniciar(self):
        self._thread_loop = threading.get_ident()
        try:
            self.evento("preparando", texto="Preparando conexão e derivando chaves…")
            ice_servers = [RTCIceServer(s) for s in STUNS]
            self.pc = RTCPeerConnection(RTCConfiguration(iceServers=ice_servers))
            self.canal = self.pc.createDataChannel("controle")

            @self.canal.on("open")
            def _aberto():
                log.info("Canal de controle WebRTC aberto")

            @self.canal.on("message")
            def _msg(m):
                try:
                    d = json.loads(m)
                    t = d.get("t")
                    if t == "tela":
                        self.largura_tela = d.get("w", 0)
                        self.altura_tela = d.get("h", 0)
                        self.nome_remoto = d.get("nome", self.nome_remoto)
                        self.evento("tela", w=self.largura_tela, h=self.altura_tela, nome=self.nome_remoto)
                    elif t == "ficha":
                        fid = d.get("id")
                        k = d.get("k")
                        if fid and k:
                            self._ficha_recebida = (fid, bytes.fromhex(k))
                            self.evento("ficha", id=fid, k=k)
                except Exception as ex:
                    log.debug("Mensagem controle inválida: %s", ex)

            @self.pc.on("track")
            def _track(track):
                log.info("Track de vídeo recebido: %s", track.kind)

                async def _ler():
                    while not self.encerrado:
                        try:
                            quadro = await track.recv()
                            if self.on_quadro and not self.encerrado:
                                self.on_quadro(quadro)
                        except Exception as e:
                            log.warning("leitura de vídeo parou: %r", e)
                            break
                asyncio.ensure_future(_ler())

            @self.pc.on("connectionstatechange")
            def _mudanca_estado():
                st = self.pc.connectionState if self.pc else "closed"
                log.info("Estado da conexão WebRTC: %s", st)
                if st == "connected":
                    self.caminho = _par_escolhido(self.pc)
                    self.evento("conectado", nome=self.nome_remoto or self.codigo,
                                caminho=self.caminho, sas=self.sas)
                elif st in ("failed", "closed"):
                    if not self.encerrado:
                        self._avisar_fim("A conexão com o computador remoto caiu." if st == "failed"
                                         else "O computador remoto encerrou a conexão.", caiu=st == "failed")

            self.pc.addTransceiver("video", direction="recvonly")
            try:                       # socket UDP antes da oferta: a porta vai dentro dela
                self.lan = CanalLAN(self.chaves, host=False)
                await self.lan.iniciar()
            except OSError as ex:
                log.warning("UDP local indisponível: %s", ex)
                self.lan = None
            oferta = await self.pc.createOffer()
            await self.pc.setLocalDescription(oferta)
            self.sdp_local = enxugar_sdp(self.pc.localDescription.sdp)

            self._criar_oferta_selada()

            self._resposta_fut = self.loop.create_future()
            self.evento("procurando", texto="Procurando o computador remoto na rede local e mundial (DHT)…")

            # Inicia canais LAN e DHT em paralelo
            await self._iniciar_lan()
            await self._iniciar_dht()

            # Aguarda resposta ou evento de senha/recusa
            asyncio.ensure_future(self._esperar_resposta())
        except Exception as e:
            log.exception("Falha ao iniciar cliente")
            self._fim_avisado = True
            self.evento("erro", texto=f"Erro ao iniciar conexão: {e}")
            await self.fechar()

    def _criar_oferta_selada(self):
        # respostas mais velhas que isto são de outras sessões (2 min de folga p/ relógios diferentes)
        self._desde_ms = int((time.time() - 120) * 1000)
        self.sid = os.urandom(8).hex()
        cab = {
            "v": 1,
            "t": "oferta",
            "sid": self.sid,
            "ts": int(time.time()),
            "nome": self.meu_nome,
        }
        if self.preparo:
            import base64
            nos = self.preparo.canal.nos_compactos(self.preparo.canal.deles[0])
            if nos:
                cab["nh"] = base64.b64encode(nos).decode()   # o PC grava a resposta nestes nós
        portas = self._portas_lan()
        if portas:
            cab["pl"] = portas        # o PC responde direto por UDP para cá, além da DHT
        if self.chave_senha:
            cab["prova"] = prova_senha(self.chave_senha, self.sid, self.sdp_local)
        if self.ficha:
            cab["ficha_id"] = self.ficha[0]
            cab["prova_ficha"] = prova_senha(self.ficha[1], self.sid, self.sdp_local)
        self.selado = self.chaves.selar(cab, self.sdp_local)

    async def _iniciar_lan(self):
        try:
            if not self.lan:
                return

            async def _laco_lan_envio():
                # reenvia rápido no começo (UDP pode perder pacote), depois a cada 1 s
                for i in range(70):
                    if self.encerrado or (self._resposta_fut and self._resposta_fut.done()):
                        break
                    if not self.lan:
                        break
                    self.lan.enviar(self.selado)
                    for addr in self._diretos():
                        self.lan.enviar(self.selado, addr)
                    await asyncio.sleep(0.15 if i < 6 else 1.0)

            async def _laco_lan_rec():
                while not self.encerrado and not (self._resposta_fut and self._resposta_fut.done()):
                    try:
                        dados, _ = await asyncio.wait_for(self.lan.receber(), 1.0)
                        self._tratar_sinal(dados, "rede local")
                    except asyncio.TimeoutError:
                        pass
                    except Exception:
                        break

            self.tarefas.append(asyncio.ensure_future(_laco_lan_envio()))
            self.tarefas.append(asyncio.ensure_future(_laco_lan_rec()))
        except Exception as ex:
            log.warning("LAN indisponível no cliente: %s", ex)

    def _portas_lan(self):
        try:
            p4 = self.lan.transporte.get_extra_info("sockname")[1] if self.lan and self.lan.transporte else 0
            p6 = (self.lan.transporte6.get_extra_info("sockname")[1]
                  if self.lan and self.lan.transporte6 else 0)
            return [p4, p6] if (p4 or p6) else None
        except Exception:
            return None

    def _diretos(self):
        """Endereços para mandar o pedido direto (campainha): vizinho da rede local + os que o PC
        publicou na DHT (IPv4 da rede dele e IPv6 global)."""
        ends = []
        if self.ip_vizinho:
            ends.append((self.ip_vizinho, PORTA_LAN))
        if self.preparo:
            ends += [tuple(a) for a in self.preparo.enderecos if tuple(a) not in ends]
        return ends

    async def _iniciar_dht(self):
        try:
            if self.preparo:
                self.cdht = self.preparo.canal          # DHT do app, já aquecida para este código
                self.dht = self.cdht.dht
                if not self.preparo.pronto.done():       # endereços diretos chegando: manda já
                    def _campainha(_f):
                        if self.lan and not self.encerrado:
                            for addr in self._diretos():
                                self.lan.enviar(self.selado, addr)
                    self.preparo.pronto.add_done_callback(_campainha)
            else:
                self.dht = DHT()
                self._dht_propria = True
                await self.dht.iniciar()
                self.cdht = CanalDHT(self.dht, self.chaves, "cliente")

            async def _laco_dht():
                # aquece e envia
                aq = asyncio.ensure_future(asyncio.sleep(0) if self.preparo else
                                           self.cdht.aquecer(escrita=False))
                ok = await self.cdht.enviar(self.selado)
                log.info("Oferta gravada na DHT: %s", ok)
                await aq
                if not (self._resposta_fut and self._resposta_fut.done()):
                    self.evento("aguardando_pc",
                                texto="Pedido enviado. Aguardando o computador remoto aceitar…")
                while not self.encerrado and not (self._resposta_fut and self._resposta_fut.done()):
                    try:
                        d = await self.cdht.receber(desde_ms=self._desde_ms)
                        if d:
                            self._tratar_sinal(d, "DHT")
                    except Exception as e:
                        log.debug("DHT poll err: %s", e)
                    await asyncio.sleep(0.5)

            self.tarefas.append(asyncio.ensure_future(_laco_dht()))
        except Exception as ex:
            log.warning("DHT indisponível no cliente: %s", ex)

    def _tratar_sinal(self, dados: bytes, via: str):
        try:
            cab, sdp = self.chaves.abrir(dados)
        except Exception:
            return
        if cab.get("sid") != self.sid:
            return
        t = cab.get("t")
        log.info("Sinal recebido [%s] via %s: %s", t, via, cab)
        if t == "senha":
            self.evento("pedir_senha", nome=cab.get("nome", self.nome_remoto))
        elif t == "recusa":
            motivo = cab.get("motivo", "")
            if "senha" in motivo:
                self.evento("senha_errada", motivo=motivo)
            else:
                self.evento("recusado", motivo=motivo or "O computador remoto recusou a conexão.")
                if self._resposta_fut and not self._resposta_fut.done():
                    self._resposta_fut.set_result((cab, sdp, via))
        elif t == "resposta":
            if self._resposta_fut and not self._resposta_fut.done():
                self._resposta_fut.set_result((cab, sdp, via))

    async def _esperar_resposta(self):
        try:
            cab, sdp_resposta, via = await asyncio.wait_for(self._resposta_fut, 90)
            if cab.get("t") == "recusa":
                self._fim_avisado = True
                await self.fechar()
                return

            self.nome_remoto = cab.get("nome", self.nome_remoto)
            self.sas = codigo_verificacao(self.sdp_local, sdp_resposta)
            self.evento("conectando", texto=f"Resposta recebida via {via}. Abrindo fluxo direto (P2P)…",
                        sas=self.sas, nome=self.nome_remoto)

            await self.pc.setRemoteDescription(RTCSessionDescription(sdp_resposta, "answer"))
            # Limpa sinalização para economizar recursos
            self._limpar_sinal()
            for _ in range(225):              # 45 s para o ICE achar um caminho
                if self.encerrado or (self.pc and self.pc.connectionState in ("connected", "failed", "closed")):
                    break
                await asyncio.sleep(0.2)
            else:
                self._fim_avisado = True
                self.evento("erro", texto="Não foi possível abrir um caminho direto até o computador remoto "
                                          "(redes muito fechadas dos dois lados).")
                await self.fechar()
        except asyncio.TimeoutError:
            self._fim_avisado = True
            self.evento("erro", texto="O computador remoto não respondeu. Confira o endereço e se o "
                                      "Simba Remoto está aberto nele.")
            await self.fechar()
        except Exception as e:
            log.exception("Erro processando resposta")
            self._fim_avisado = True
            self.evento("erro", texto=f"Erro ao estabelecer conexão: {e}")
            await self.fechar()

    async def entrar_com_senha(self, senha: str):
        """Reenvia a oferta assinada com a prova da senha fornecida."""
        self.chave_senha = chave_senha(senha, self.codigo)
        self._criar_oferta_selada()
        self.evento("aguardando_pc", texto="Verificando senha com o computador remoto…")
        # Envia novamente por LAN e DHT
        if self.lan:
            self.lan.enviar(self.selado)
        if self.cdht:
            asyncio.ensure_future(self.cdht.enviar(self.selado))

    # --- Envio de comandos de controle
    def enviar(self, msg: dict):
        """Pode ser chamado de qualquer thread (a interface): o canal do aiortc só pode ser usado
        dentro do loop asyncio dele; chamado de fora, a mensagem ficava parada e nunca saía."""
        dados = json.dumps(msg)
        try:
            if threading.get_ident() == self._thread_loop:
                self._enviar_no_loop(dados)
            else:
                self.loop.call_soon_threadsafe(self._enviar_no_loop, dados)
        except RuntimeError:
            pass                       # loop já encerrado

    def _enviar_no_loop(self, dados):
        if self.canal and self.canal.readyState == "open":
            try:
                self.canal.send(dados)
            except Exception as e:
                log.debug("Erro ao enviar comando: %s", e)

    def mover(self, x: float, y: float):
        self.enviar({"t": "mover", "x": max(0.0, min(1.0, float(x))), "y": max(0.0, min(1.0, float(y)))})

    def botao(self, qual: str, acao: str, x: Optional[float] = None, y: Optional[float] = None):
        msg = {"t": "botao", "b": qual, "acao": acao}
        if x is not None and y is not None:
            msg["x"] = max(0.0, min(1.0, float(x)))
            msg["y"] = max(0.0, min(1.0, float(y)))
        self.enviar(msg)

    def rolar(self, dx: int, dy: int):
        self.enviar({"t": "rolar", "dx": int(dx), "dy": int(dy)})

    def texto(self, s: str):
        if s:
            self.enviar({"t": "texto", "s": str(s)[:2000]})

    def tecla(self, k: str, mods=()):
        self.enviar({"t": "tecla", "k": str(k), "mods": list(mods)})

    def enviar_ctrl_alt_del(self):
        self.tecla("Delete", mods=["ctrl", "alt"])

    def enviar_super(self):
        self.tecla("Super", mods=[])

    def _limpar_sinal(self):
        if self.lan:
            try:
                self.lan.fechar()
            except Exception:
                pass
            self.lan = None
        if self.dht:
            if self._dht_propria:          # a DHT do app (preparo) continua viva para os próximos
                try:
                    self.dht.fechar()
                except Exception:
                    pass
            self.dht = None
            self.cdht = None

    async def fechar(self):
        if self.encerrado:
            return
        self.encerrado = True
        for t in self.tarefas:
            t.cancel()
        self._limpar_sinal()
        if self.canal:
            try:
                self.canal.close()
            except Exception:
                pass
            self.canal = None
        if self.pc:
            try:
                await self.pc.close()
            except Exception:
                pass
            self.pc = None
        self._avisar_fim("Desconectado.")

    def _avisar_fim(self, texto, caiu=False):
        if getattr(self, "_fim_avisado", False):
            return
        self._fim_avisado = True
        self.evento("desconectado", texto=texto, caiu=caiu, ficha=self._ficha_recebida is not None)

    @property
    def ficha_recebida(self):
        return self._ficha_recebida
