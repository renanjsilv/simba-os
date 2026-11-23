"""Mouse e teclado no Windows via SendInput (texto em Unicode: acentos funcionam em qualquer layout)."""
import ctypes
import logging
from ctypes import wintypes

log = logging.getLogger("simba-remoto.entrada")
u32 = ctypes.windll.user32

INPUT_MOUSE, INPUT_KEYBOARD = 0, 1
KEYEVENTF_KEYUP, KEYEVENTF_UNICODE, KEYEVENTF_EXTENDEDKEY = 0x2, 0x4, 0x1
MOUSE = {
    ("esq", "desce"): 0x0002, ("esq", "sobe"): 0x0004,
    ("dir", "desce"): 0x0008, ("dir", "sobe"): 0x0010,
    ("meio", "desce"): 0x0020, ("meio", "sobe"): 0x0040,
}
MOUSEEVENTF_WHEEL, MOUSEEVENTF_HWHEEL = 0x0800, 0x1000

VK = {
    "Enter": 0x0D, "Backspace": 0x08, "Tab": 0x09, "Escape": 0x1B, "Delete": 0x2E, "Insert": 0x2D,
    "Home": 0x24, "End": 0x23, "PageUp": 0x21, "PageDown": 0x22,
    "Left": 0x25, "Up": 0x26, "Right": 0x27, "Down": 0x28, "Space": 0x20, "Print": 0x2C, "Menu": 0x5D, "Super": 0x5B,
    **{f"F{i}": 0x6F + i for i in range(1, 13)},
}
ESTENDIDAS = {0x5B, 0x2E, 0x2D, 0x24, 0x23, 0x21, 0x22, 0x25, 0x26, 0x27, 0x28}
MODS = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "super": 0x5B, "altgr": 0xA5}

ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _U(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def _enviar(*entradas):
    arr = (INPUT * len(entradas))(*entradas)
    u32.SendInput(len(entradas), arr, ctypes.sizeof(INPUT))


def _mouse(flags, dado=0):
    i = INPUT(type=INPUT_MOUSE)
    i.u.mi = MOUSEINPUT(0, 0, dado & 0xFFFFFFFF, flags, 0, 0)
    return i


def _tecla(vk=0, scan=0, flags=0):
    i = INPUT(type=INPUT_KEYBOARD)
    if vk in ESTENDIDAS:
        flags |= KEYEVENTF_EXTENDEDKEY
    i.u.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    return i


class Entrada:
    def __init__(self, posicao, tamanho):
        self.x0, self.y0 = posicao
        self.w, self.h = tamanho

    def fechar(self):
        pass

    def mover(self, nx, ny):
        nx = min(max(float(nx), 0.0), 1.0)
        ny = min(max(float(ny), 0.0), 1.0)
        u32.SetCursorPos(round(self.x0 + nx * (self.w - 1)), round(self.y0 + ny * (self.h - 1)))

    def botao(self, qual, acao):
        if acao == "clique":
            _enviar(_mouse(MOUSE[(qual, "desce")]), _mouse(MOUSE[(qual, "sobe")]))
        elif (qual, acao) in MOUSE:
            _enviar(_mouse(MOUSE[(qual, acao)]))

    def rolar(self, dx, dy):
        # no celular, arrastar para baixo = conteúdo sobe (mesmo sentido do Linux: REL_WHEEL positivo = para cima)
        if dy:
            _enviar(_mouse(MOUSEEVENTF_WHEEL, int(dy) * 120))
        if dx:
            _enviar(_mouse(MOUSEEVENTF_HWHEEL, int(dx) * 120))

    def texto(self, s):
        evs = []
        for ch in s:
            if ch == "\n":
                evs += [_tecla(0x0D), _tecla(0x0D, flags=KEYEVENTF_KEYUP)]
                continue
            unid = ch.encode("utf-16-le")
            for j in range(0, len(unid), 2):
                cod = int.from_bytes(unid[j:j + 2], "little")
                evs += [_tecla(0, cod, KEYEVENTF_UNICODE), _tecla(0, cod, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP)]
        if evs:
            _enviar(*evs)

    def tecla(self, k, mods=()):
        if k in VK:
            vk = VK[k]
        elif len(k) == 1:
            r = u32.VkKeyScanW(ord(k))
            if r == -1:
                return self.texto(k)
            vk = r & 0xFF
        else:
            return
        ms = [MODS[m] for m in mods if m in MODS]
        evs = [_tecla(m) for m in ms] + [_tecla(vk), _tecla(vk, flags=KEYEVENTF_KEYUP)]
        evs += [_tecla(m, flags=KEYEVENTF_KEYUP) for m in reversed(ms)]
        _enviar(*evs)

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
