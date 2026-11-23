"""Captura da tela pelo portal ScreenCast (xdg-desktop-portal-hyprland) + PipeWire + GStreamer.

A primeira vez o Hyprland pergunta qual tela compartilhar; o portal devolve um
"restore token" que guardamos para as próximas conexões não perguntarem de novo.
"""
import logging
import os
import threading
from pathlib import Path

import gi
gi.require_version("Gst", "1.0")
gi.require_version("GstVideo", "1.0")
from gi.repository import Gio, GLib, Gst, GstVideo  # noqa: E402
import numpy as np  # noqa: E402

log = logging.getLogger("simba-remoto.captura")
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "simba-remoto"
TOKEN = CONFIG / "token-tela"
LARGURA_MAX = 1920   # resolução nativa até Full HD (texto nítido)

Gst.init(None)


class Cancelado(Exception):
    pass


class Captura:
    def __init__(self, ao_quadro):
        """ao_quadro(bytes_i420, largura, altura) é chamado na thread do GStreamer."""
        self.ao_quadro = ao_quadro
        self.pipeline = None
        self.loop = None
        self.thread = None
        self.erro = None
        self.pronto = threading.Event()
        self.posicao = (0, 0)
        self.tamanho = (0, 0)     # tamanho lógico do monitor capturado
        self.largura = self.altura = 0
        self._vinfo = None

    # ---------- portal ----------
    def _chamar(self, metodo, params, assinatura):
        return self.con.call_sync(
            "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.ScreenCast", metodo,
            GLib.Variant(assinatura, params), None, Gio.DBusCallFlags.NONE, 60000, None)

    def _pedido(self, metodo, args_antes, opcoes, assinatura):
        """Faz uma chamada do portal e espera o sinal Response do Request."""
        self._n += 1
        token = f"simbaremoto{os.getpid()}_{self._n}"
        remetente = self.con.get_unique_name()[1:].replace(".", "_")
        caminho = f"/org/freedesktop/portal/desktop/request/{remetente}/{token}"
        resultado = {}
        fim = GLib.MainLoop(self.ctx)

        def resposta(_c, _s, _p, _i, _n, params):
            codigo, res = params.unpack()
            resultado["codigo"] = codigo
            resultado["res"] = res
            fim.quit()

        sub = self.con.signal_subscribe("org.freedesktop.portal.Desktop", "org.freedesktop.portal.Request",
                                        "Response", caminho, None, Gio.DBusSignalFlags.NO_MATCH_RULE, resposta)
        opcoes = dict(opcoes, handle_token=GLib.Variant("s", token))
        self._chamar(metodo, tuple(args_antes) + (opcoes,), assinatura)
        fim.run()
        self.con.signal_unsubscribe(sub)
        if resultado.get("codigo") != 0:
            raise Cancelado("o compartilhamento de tela foi cancelado")
        return resultado["res"]

    def _iniciar_portal(self):
        self._n = 0
        endereco = Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None)
        self.con = Gio.DBusConnection.new_for_address_sync(
            endereco, Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION,
            None, None)
        res = self._pedido("CreateSession", (), {
            "session_handle_token": GLib.Variant("s", f"simbaremoto{os.getpid()}")}, "(a{sv})")
        self.sessao = res["session_handle"]
        opc = {
            "types": GLib.Variant("u", 1),          # monitor
            "multiple": GLib.Variant("b", False),
            "cursor_mode": GLib.Variant("u", 2),    # cursor embutido no vídeo
            "persist_mode": GLib.Variant("u", 2),   # lembrar a escolha
        }
        try:
            opc["restore_token"] = GLib.Variant("s", TOKEN.read_text().strip())
        except OSError:
            pass
        # sem ninguém no PC: o seletor do Simba (simba-seletor-tela) escolhe o monitor sozinho.
        # O xdph abre o seletor já no SelectSources, por isso o aviso vem antes.
        aviso = _aviso_seletor()
        try:
            self._pedido("SelectSources", (self.sessao,), opc, "(oa{sv})")
            res = self._pedido("Start", (self.sessao, ""), {}, "(osa{sv})")
        finally:
            if aviso:
                aviso.unlink(missing_ok=True)
        if "restore_token" in res:
            CONFIG.mkdir(parents=True, exist_ok=True)
            TOKEN.write_text(res["restore_token"])
        no, props = res["streams"][0]
        self.posicao = tuple(props.get("position", (0, 0)))
        self.tamanho = tuple(props.get("size", (0, 0)))
        r = self.con.call_with_unix_fd_list_sync(
            "org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.ScreenCast", "OpenPipeWireRemote",
            GLib.Variant("(oa{sv})", (self.sessao, {})), None, Gio.DBusCallFlags.NONE, 10000, None, None)
        fd = r[1].get(r[0].unpack()[0])
        return fd, no

    # ---------- GStreamer ----------
    def _rodar(self):
        self.ctx = GLib.MainContext.new()
        self.ctx.push_thread_default()
        try:
            fd, no = self._iniciar_portal()
            w, h = self.tamanho or (1920, 1080)
            # descobrir tamanho real em pixels pelo monitor do Hyprland (escala)
            w_px, h_px = _pixels_monitor(self.posicao, (w, h))
            larg = min(LARGURA_MAX, w_px)
            larg -= larg % 2
            alt = int(round(h_px * larg / w_px / 4)) * 4      # I420 sem padding precisa de altura múltipla de 4
            self.largura, self.altura = larg, alt
            desc = (f"pipewiresrc fd={fd} path={no} do-timestamp=true keepalive-time=250 always-copy=true ! "
                    f"videoconvert n-threads=2 ! videoscale ! video/x-raw,format=I420,width={larg},height={alt} ! "
                    f"appsink name=saida emit-signals=true max-buffers=1 drop=true sync=false")
            self.pipeline = Gst.parse_launch(desc)
            self.pipeline.get_by_name("saida").connect("new-sample", self._amostra)
            self.pipeline.set_state(Gst.State.PLAYING)
            log.info("capturando %sx%s (monitor %s em %s)", larg, alt, self.tamanho, self.posicao)
        except Exception as e:
            self.erro = e
            self.pronto.set()
            return
        self.pronto.set()
        self.loop = GLib.MainLoop(self.ctx)
        self.loop.run()
        self.pipeline.set_state(Gst.State.NULL)
        try:
            self.con.call_sync("org.freedesktop.portal.Desktop", self.sessao,
                               "org.freedesktop.portal.Session", "Close", None, None,
                               Gio.DBusCallFlags.NONE, 2000, None)
        except Exception:
            pass

    def _amostra(self, sink):
        amostra = sink.emit("pull-sample")
        buf = amostra.get_buffer()
        if self._vinfo is None:
            self._vinfo = GstVideo.VideoInfo.new_from_caps(amostra.get_caps())
        ok, info = buf.map(Gst.MapFlags.READ)
        if ok:
            try:
                self.ao_quadro(_i420_compacto(info.data, self._vinfo, self.largura, self.altura),
                               self.largura, self.altura)
            finally:
                buf.unmap(info)
        return Gst.FlowReturn.OK

    def iniciar(self):
        """Bloqueia até a captura começar (ou falhar)."""
        if os.environ.get("SIMBA_REMOTO_TELA_TESTE"):
            return self._teste()
        self.thread = threading.Thread(target=self._rodar, daemon=True, name="captura")
        self.thread.start()
        if not self.pronto.wait(30):
            raise Cancelado("o compartilhamento de tela não respondeu (seletor do Hyprland?)")
        if self.erro:
            raise self.erro

    def _teste(self):
        self.posicao, self.tamanho = (0, 0), (1280, 720)
        self.largura, self.altura = 1280, 720
        self.pipeline = Gst.parse_launch(
            "videotestsrc is-live=true pattern=smpte ! video/x-raw,format=I420,width=1280,height=720,framerate=30/1 ! "
            "appsink name=saida emit-signals=true max-buffers=1 drop=true sync=false")
        self.pipeline.get_by_name("saida").connect("new-sample", self._amostra)
        self.pipeline.set_state(Gst.State.PLAYING)

    def parar(self):
        if self.pipeline and not self.loop:
            self.pipeline.set_state(Gst.State.NULL)
        if self.loop:
            self.loop.quit()


def _i420_compacto(dados, vinfo, w, h):
    """Tira o preenchimento (stride) das linhas: larguras como 1366 vêm com bytes extras por linha."""
    st, off = vinfo.stride, vinfo.offset
    if st[0] == w and st[1] == w // 2 and off[1] == w * h:
        return bytes(dados[: w * h * 3 // 2])
    b = np.frombuffer(dados, np.uint8)
    y = b[off[0]: off[0] + st[0] * h].reshape(h, st[0])[:, :w]
    u = b[off[1]: off[1] + st[1] * (h // 2)].reshape(h // 2, st[1])[:, : w // 2]
    v = b[off[2]: off[2] + st[2] * (h // 2)].reshape(h // 2, st[2])[:, : w // 2]
    return y.tobytes() + u.tobytes() + v.tobytes()


def _aviso_seletor():
    """Diz ao simba-seletor-tela qual monitor compartilhar (o que tem foco)."""
    try:
        import json
        import subprocess
        mons = json.loads(subprocess.check_output(["hyprctl", "-j", "monitors"], timeout=3))
        nome = next((m["name"] for m in mons if m.get("focused")), mons[0]["name"])
        d = Path(os.environ.get("XDG_RUNTIME_DIR", "/tmp")) / "simba-remoto"
        d.mkdir(parents=True, exist_ok=True)
        arq = d / "escolher-tela"
        arq.write_text(nome + "\n")
        return arq
    except Exception as e:
        log.warning("aviso ao seletor falhou: %s", e)
        return None


def _pixels_monitor(posicao, tamanho_logico):
    try:
        import json
        import subprocess
        for m in json.loads(subprocess.check_output(["hyprctl", "-j", "monitors"], timeout=3)):
            if (m["x"], m["y"]) == tuple(posicao):
                w, h = m["width"], m["height"]
                if m.get("transform", 0) % 2:
                    w, h = h, w
                return w, h
    except Exception:
        pass
    return tamanho_logico
