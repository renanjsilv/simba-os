"""Captura da tela no Windows (GDI via mss), com o cursor desenhado por cima."""
import ctypes
import logging
import threading
import time

import av
import numpy as np

log = logging.getLogger("simba-remoto.captura")
LARGURA_MAX = 1920
FPS = 30


class _PONTO(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _CURSORINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("flags", ctypes.c_uint),
                ("hCursor", ctypes.c_void_p), ("ptScreenPos", _PONTO)]


def _cursor():
    try:
        ci = _CURSORINFO()
        ci.cbSize = ctypes.sizeof(ci)
        if ctypes.windll.user32.GetCursorInfo(ctypes.byref(ci)) and ci.flags & 1:
            return ci.ptScreenPos.x, ci.ptScreenPos.y
    except Exception:
        pass
    return None


# seta de cursor simples (1 = branco, 2 = preto)
_SETA = [
    "2", "22", "212", "2112", "21112", "211112", "2111112", "21111112", "211111112",
    "2111111112", "21111122222", "2112112", "212 2112", "22  2112", "2    2112", "     2112", "      22",
]
_SETA_MASCARA = np.zeros((len(_SETA), 11), np.uint8)
for _y, _l in enumerate(_SETA):
    for _x, _c in enumerate(_l):
        _SETA_MASCARA[_y, _x] = {"1": 1, "2": 2}.get(_c, 0)


def _desenhar_cursor(img, cx, cy):
    h, w = img.shape[:2]
    mh, mw = _SETA_MASCARA.shape
    if cx >= w or cy >= h or cx < 0 or cy < 0:
        return
    sub = img[cy:min(cy + mh, h), cx:min(cx + mw, w)]
    m = _SETA_MASCARA[:sub.shape[0], :sub.shape[1]]
    sub[m == 1, :3] = 255
    sub[m == 2, :3] = 0


class Captura:
    def __init__(self, ao_quadro):
        self.ao_quadro = ao_quadro
        self.rodando = False
        self.thread = None
        self.posicao = (0, 0)
        self.tamanho = (0, 0)
        self.largura = self.altura = 0

    def iniciar(self):
        import mss
        with mss.mss() as s:
            mon = s.monitors[1]           # monitor principal
        self.posicao = (mon["left"], mon["top"])
        self.tamanho = (mon["width"], mon["height"])
        w, h = self.tamanho
        larg = min(LARGURA_MAX, w)
        larg -= larg % 2
        self.largura, self.altura = larg, int(round(h * larg / w / 4)) * 4
        self.rodando = True
        self.thread = threading.Thread(target=self._laco, args=(mon,), daemon=True, name="captura")
        self.thread.start()
        log.info("capturando %sx%s -> %sx%s", w, h, self.largura, self.altura)

    def _laco(self, mon):
        import mss
        intervalo = 1 / FPS
        with mss.mss() as s:
            while self.rodando:
                t0 = time.monotonic()
                try:
                    img = np.array(s.grab(mon))           # BGRA
                    c = _cursor()
                    if c:
                        _desenhar_cursor(img, c[0] - mon["left"], c[1] - mon["top"])
                    q = av.VideoFrame.from_ndarray(img, format="bgra").reformat(
                        width=self.largura, height=self.altura, format="yuv420p")
                    self.ao_quadro(q.to_ndarray().tobytes(), self.largura, self.altura)
                except Exception as e:
                    log.debug("captura: %s", e)
                    time.sleep(0.2)
                resto = intervalo - (time.monotonic() - t0)
                if resto > 0:
                    time.sleep(resto)

    def parar(self):
        self.rodando = False
