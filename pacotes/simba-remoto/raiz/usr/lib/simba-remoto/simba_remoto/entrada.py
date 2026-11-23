"""Injeção de mouse/teclado no Hyprland.

- posição do cursor: dispatcher Lua `hl.dsp.cursor.move` pelo socket do Hyprland (absoluto, exato)
- botões e rolagem: dispositivo virtual /dev/uinput (python-evdev)
- teclado: wtype (protocolo virtual-keyboard: respeita qualquer layout e acentos)
"""
import logging
import os
import queue
import socket
import subprocess
import threading

log = logging.getLogger("simba-remoto.entrada")

TECLAS_WTYPE = {
    "Enter": "Return", "Backspace": "BackSpace", "Tab": "Tab", "Escape": "Escape",
    "Delete": "Delete", "Home": "Home", "End": "End", "PageUp": "Prior", "PageDown": "Next",
    "Up": "Up", "Down": "Down", "Left": "Left", "Right": "Right", "Insert": "Insert",
    "Space": "space", "Print": "Print", "Menu": "Menu", "Super": "Super_L",
    **{f"F{i}": f"F{i}" for i in range(1, 13)},
}
MODS = {"ctrl": "ctrl", "alt": "alt", "shift": "shift", "super": "logo", "altgr": "altgr"}


def _socket_hypr():
    return f"{os.environ.get('XDG_RUNTIME_DIR')}/hypr/{os.environ.get('HYPRLAND_INSTANCE_SIGNATURE')}/.socket.sock"


class Entrada:
    def __init__(self, posicao, tamanho):
        self.x0, self.y0 = posicao
        self.w, self.h = tamanho
        self.ui = None
        # teclado: uma fila só, executada em ordem (antes cada letra abria um wtype em paralelo
        # e elas chegavam embaralhadas)
        self._fila_teclado = queue.Queue()
        threading.Thread(target=self._laco_teclado, daemon=True, name="teclado").start()
        self._hypr_sock = None
        try:
            from evdev import UInput, ecodes as e
            self.e = e
            self.ui = UInput({e.EV_KEY: [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE],
                              e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL, e.REL_HWHEEL,
                                         e.REL_WHEEL_HI_RES, e.REL_HWHEEL_HI_RES]},
                             name="Simba Remoto (mouse)")
        except Exception as ex:
            log.warning("uinput indisponível (%s): cliques desativados", ex)

    def fechar(self):
        self._fila_teclado.put(None)
        if self.ui:
            self.ui.close()

    def _laco_teclado(self):
        while True:
            args = self._fila_teclado.get()
            if args is None:
                return
            # junta textos seguidos num wtype só (digitação rápida)
            if args[1] == "--":
                texto = args[2]
                while not self._fila_teclado.empty():
                    prox = self._fila_teclado.queue[0]
                    if prox is None or prox[1] != "--":
                        break
                    texto += self._fila_teclado.get()[2]
                args = ["wtype", "--", texto]
            try:
                subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            except Exception as e:
                log.debug("wtype: %s", e)

    def _hypr(self, cmd):
        try:
            s = socket.socket(socket.AF_UNIX)
            s.settimeout(1)
            s.connect(_socket_hypr())
            s.sendall(cmd.encode())
            s.recv(64)
            s.close()
        except OSError as ex:
            log.debug("hyprland: %s", ex)

    def mover(self, nx, ny):
        nx = min(max(float(nx), 0.0), 1.0)
        ny = min(max(float(ny), 0.0), 1.0)
        x = round(self.x0 + nx * (self.w - 1))
        y = round(self.y0 + ny * (self.h - 1))
        self._hypr(f"eval hl.dispatch(hl.dsp.cursor.move({{x={x},y={y}}}))")

    def botao(self, qual, acao):
        if not self.ui:
            return
        e = self.e
        b = {"esq": e.BTN_LEFT, "dir": e.BTN_RIGHT, "meio": e.BTN_MIDDLE}.get(qual)
        if b is None:
            return
        if acao in ("desce", "clique"):
            self.ui.write(e.EV_KEY, b, 1)
            self.ui.syn()
        if acao in ("sobe", "clique"):
            self.ui.write(e.EV_KEY, b, 0)
            self.ui.syn()

    def rolar(self, dx, dy):
        if not self.ui:
            return
        e = self.e
        if dy:
            self.ui.write(e.EV_REL, e.REL_WHEEL, int(dy))
            self.ui.write(e.EV_REL, e.REL_WHEEL_HI_RES, int(dy) * 120)
        if dx:
            self.ui.write(e.EV_REL, e.REL_HWHEEL, int(dx))
            self.ui.write(e.EV_REL, e.REL_HWHEEL_HI_RES, int(dx) * 120)
        self.ui.syn()

    def texto(self, s):
        if s:
            self._fila_teclado.put(["wtype", "--", s])

    def tecla(self, k, mods=()):
        nome = TECLAS_WTYPE.get(k, k if len(k) == 1 else None)
        if not nome:
            return
        args = ["wtype"]
        ms = [MODS[m] for m in mods if m in MODS]
        for m in ms:
            args += ["-M", m]
        args += ["-k", nome]
        for m in reversed(ms):
            args += ["-m", m]
        self._fila_teclado.put(args)

    def tratar(self, msg: dict):
        t = msg.get("t")
        if t == "mover":
            self.mover(msg.get("x", 0), msg.get("y", 0))
        elif t == "botao":
            if "x" in msg:
                self.mover(msg["x"], msg["y"])
            self.botao(msg.get("b", "esq"), msg.get("acao", "clique"))
        elif t == "rolar":
            self.rolar(msg.get("dx", 0), msg.get("dy", 0))
        elif t == "texto":
            self.texto(str(msg.get("s", ""))[:2000])
        elif t == "tecla":
            self.tecla(str(msg.get("k", "")), msg.get("mods", []))
