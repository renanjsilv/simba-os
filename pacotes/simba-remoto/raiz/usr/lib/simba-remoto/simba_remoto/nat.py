"""Quebra de NAT do lado do PC: abre porta no roteador (UPnP-IGD) e acrescenta
candidatos ICE extras. IPv6 global e STUN o próprio ICE já cobrem."""
import ipaddress
import logging
import re
import socket
import threading

log = logging.getLogger("simba-remoto.nat")


def _privado(ip):
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


class _IGD:
    """Cliente UPnP-IGD mínimo em Python puro (SSDP + SOAP), sem biblioteca nativa."""
    TIPOS = ("urn:schemas-upnp-org:service:WANIPConnection:2",
             "urn:schemas-upnp-org:service:WANIPConnection:1",
             "urn:schemas-upnp-org:service:WANPPPConnection:1")

    def __init__(self, url_controle, tipo, ip_local):
        self.url, self.tipo, self.lanaddr = url_controle, tipo, ip_local

    @classmethod
    def descobrir(cls, espera=2.0):
        import urllib.parse
        import urllib.request
        import xml.etree.ElementTree as ET
        msg = ("M-SEARCH * HTTP/1.1\r\nHOST: 239.255.255.250:1900\r\nMAN: \"ssdp:discover\"\r\n"
               "MX: 2\r\nST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n\r\n").encode()
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(espera)
        locais = []
        try:
            s.sendto(msg, ("239.255.255.250", 1900))
            while True:
                dados, _ = s.recvfrom(4096)
                for linha in dados.decode(errors="ignore").split("\r\n"):
                    if linha.lower().startswith("location:"):
                        locais.append(linha.split(":", 1)[1].strip())
        except OSError:
            pass
        finally:
            s.close()
        for loc in dict.fromkeys(locais):
            try:
                xml = urllib.request.urlopen(loc, timeout=3).read()
                raiz = ET.fromstring(xml)
                for serv in raiz.iter():
                    if not serv.tag.endswith("service"):
                        continue
                    campos = {c.tag.split("}")[-1]: (c.text or "").strip() for c in serv}
                    if campos.get("serviceType") in cls.TIPOS:
                        url = urllib.parse.urljoin(loc, campos.get("controlURL", ""))
                        host = urllib.parse.urlparse(loc).hostname
                        t = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                        t.connect((host, 1900))
                        ip_local = t.getsockname()[0]
                        t.close()
                        return cls(url, campos["serviceType"], ip_local)
            except Exception:
                continue
        return None

    def _soap(self, acao, args):
        import re as _re
        import urllib.request
        corpo = "".join(f"<{k}>{v}</{k}>" for k, v in args)
        env = ('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
               's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
               f'<u:{acao} xmlns:u="{self.tipo}">{corpo}</u:{acao}></s:Body></s:Envelope>').encode()
        req = urllib.request.Request(self.url, env, {"Content-Type": 'text/xml; charset="utf-8"',
                                                     "SOAPAction": f'"{self.tipo}#{acao}"'})
        resp = urllib.request.urlopen(req, timeout=4).read().decode(errors="ignore")
        return {m.group(1): m.group(2) for m in _re.finditer(r"<(?:\w+:)?(\w+)>([^<]*)</", resp)}

    def ip_externo(self):
        return self._soap("GetExternalIPAddress", []).get("NewExternalIPAddress")

    def mapear(self, externa, ip, interna, duracao=3600):
        self._soap("AddPortMapping", [("NewRemoteHost", ""), ("NewExternalPort", externa),
                                      ("NewProtocol", "UDP"), ("NewInternalPort", interna),
                                      ("NewInternalClient", ip), ("NewEnabled", 1),
                                      ("NewPortMappingDescription", "Simba Remoto"),
                                      ("NewLeaseDuration", duracao)])
        return True

    def remover(self, externa):
        self._soap("DeletePortMapping", [("NewRemoteHost", ""), ("NewExternalPort", externa),
                                         ("NewProtocol", "UDP")])


class UPnP:
    def __init__(self):
        self.u = None
        self.ip_externo = None
        self.mapeadas = []
        self.lock = threading.Lock()

    def descobrir(self):
        """Bloqueante (~2 s). Chamar numa thread."""
        try:
            u = _IGD.descobrir()
            if u:
                self.ip_externo = u.ip_externo()
                self.u = u
                log.info("UPnP ok: IP externo %s", self.ip_externo)
        except Exception as e:
            log.info("UPnP indisponível: %s", e)
            self.u = None
        if not self.u:
            log.info("UPnP indisponível no roteador")
        return self.u is not None

    def mapear(self, porta_local, ip_local):
        if not self.u:
            return None
        with self.lock:
            for externa in (porta_local, porta_local + 1, 40000 + porta_local % 20000):
                try:
                    if self.u.mapear(externa, ip_local, porta_local):
                        self.mapeadas.append(externa)
                        return externa
                except Exception:
                    continue
        return None

    def liberar(self):
        with self.lock:
            for p in self.mapeadas:
                try:
                    self.u.remover(p)
                except Exception:
                    pass
            self.mapeadas.clear()

    @property
    def disponivel(self):
        return self.u is not None and bool(self.ip_externo) and not _privado(self.ip_externo)


def ipv6_global():
    try:
        s = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
        s.connect(("2001:4860:4860::8888", 53))
        ip = s.getsockname()[0]
        s.close()
        return ip if ipaddress.ip_address(ip).is_global else None
    except OSError:
        return None


def acrescentar_upnp(sdp: str, upnp: UPnP) -> str:
    """Para cada candidato host IPv4 privado, mapeia a porta no roteador e anuncia
    o endereço externo como candidato extra — o outro lado entra direto pela porta aberta."""
    if not upnp.disponivel:
        return sdp
    extras = []
    vistos = set()
    for m in re.finditer(r"a=candidate:\S+ 1 udp \d+ (\S+) (\d+) typ host", sdp):
        ip, porta = m.group(1), int(m.group(2))
        if ":" in ip or not _privado(ip) or (ip, porta) in vistos:
            continue
        vistos.add((ip, porta))
        ext = upnp.mapear(porta, ip)
        if ext:
            extras.append(f"a=candidate:upnp{len(extras)} 1 udp 1694498814 {upnp.ip_externo} {ext} "
                          f"typ srflx raddr {ip} rport {porta}")
    if not extras:
        return sdp
    linhas = sdp.split("\r\n")
    saida = []
    for i, l in enumerate(linhas):
        saida.append(l)
        prox = linhas[i + 1] if i + 1 < len(linhas) else ""
        if l.startswith("a=candidate:") and not prox.startswith("a=candidate:"):
            saida.extend(extras)
    return "\r\n".join(saida)
