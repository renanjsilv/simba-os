"""Bencode mínimo (BitTorrent)."""


def codificar(x) -> bytes:
    if isinstance(x, bool):
        x = int(x)
    if isinstance(x, int):
        return b"i%de" % x
    if isinstance(x, str):
        x = x.encode()
    if isinstance(x, (bytes, bytearray)):
        return b"%d:%s" % (len(x), bytes(x))
    if isinstance(x, (list, tuple)):
        return b"l" + b"".join(codificar(i) for i in x) + b"e"
    if isinstance(x, dict):
        itens = sorted((k.encode() if isinstance(k, str) else k, v) for k, v in x.items())
        return b"d" + b"".join(codificar(k) + codificar(v) for k, v in itens) + b"e"
    raise TypeError(type(x))


def _dec(b: bytes, i: int):
    c = b[i:i + 1]
    if c == b"i":
        f = b.index(b"e", i)
        return int(b[i + 1:f]), f + 1
    if c == b"l":
        i += 1
        r = []
        while b[i:i + 1] != b"e":
            v, i = _dec(b, i)
            r.append(v)
        return r, i + 1
    if c == b"d":
        i += 1
        r = {}
        while b[i:i + 1] != b"e":
            k, i = _dec(b, i)
            v, i = _dec(b, i)
            r[k] = v
        return r, i + 1
    if c.isdigit():
        f = b.index(b":", i)
        n = int(b[i:f])
        if n < 0 or f + 1 + n > len(b):
            raise ValueError("string truncada")
        return b[f + 1:f + 1 + n], f + 1 + n
    raise ValueError("bencode inválido")


def decodificar(b: bytes):
    v, i = _dec(b, 0)
    return v
