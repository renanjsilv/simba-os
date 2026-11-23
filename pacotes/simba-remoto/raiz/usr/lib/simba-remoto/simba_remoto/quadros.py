"""Conversão dos quadros de vídeo recebidos para RGB, fora da thread da rede e da interface.

O aiortc entrega quadros YUV na thread do asyncio. Converter (e redimensionar) ali travaria o
recebimento dos pacotes; converter na thread da interface deixaria a janela lenta. Aqui uma
thread própria pega sempre o quadro MAIS RECENTE (os intermediários são descartados se a
conversão não der conta), converte no tamanho em que vai ser exibido e entrega o resultado.
"""
import logging
import threading
import time

log = logging.getLogger("simba-remoto.quadros")


class ConversorQuadros:
    def __init__(self, entregar, formato="rgb24"):
        """entregar(dados_rgb: bytes, largura, altura, largura_original, altura_original) — chamado na
        thread do conversor; quem recebe deve só guardar e agendar o desenho."""
        self.entregar = entregar
        self.formato = formato
        self._quadro = None
        self._tamanho = None          # (w, h) desejado ou None = tamanho original
        self._evento = threading.Event()
        self._parar = False
        self.recebidos = 0
        self.convertidos = 0
        self._t = threading.Thread(target=self._laco, daemon=True, name="conversor-quadros")
        self._t.start()

    def novo_quadro(self, quadro):
        """Chamado na thread do asyncio: só guarda a referência (custo zero)."""
        self._quadro = quadro
        self.recebidos += 1
        self._evento.set()

    def definir_tamanho(self, largura, altura):
        """Tamanho em que a imagem vai ser exibida (já com a proporção certa). None = original."""
        novo = (max(2, int(largura)) & ~1, max(2, int(altura)) & ~1) if largura and altura else None
        if novo != self._tamanho:
            self._tamanho = novo
            self._evento.set()        # reconverte o último quadro no tamanho novo

    def parar(self):
        self._parar = True
        self._evento.set()

    def _laco(self):
        ultimo = None
        tamanho_ultimo = None
        while not self._parar:
            self._evento.wait(1.0)
            self._evento.clear()
            if self._parar:
                break
            q = self._quadro
            if q is None or (q is ultimo and self._tamanho == tamanho_ultimo):
                continue
            ultimo, tamanho_ultimo = q, self._tamanho
            try:
                if tamanho_ultimo and tamanho_ultimo != (q.width, q.height):
                    w, h = tamanho_ultimo
                    r = q.reformat(width=w, height=h, format=self.formato,
                                   interpolation="BILINEAR" if w < q.width else "FAST_BILINEAR")
                else:
                    r = q.reformat(format=self.formato)
                p = r.planes[0]
                bpp = 3 if self.formato in ("rgb24", "bgr24") else 4
                linha = r.width * bpp
                if p.line_size == linha:
                    dados = bytes(p)
                else:                 # linhas com preenchimento: tira o excesso
                    bruto = memoryview(bytes(p))
                    dados = b"".join(bruto[i * p.line_size: i * p.line_size + linha] for i in range(r.height))
                self.convertidos += 1
                self.entregar(dados, r.width, r.height, q.width, q.height)
            except Exception as e:
                log.warning("conversão de quadro falhou: %s", e)
                time.sleep(0.05)


def caber(larg_quadro, alt_quadro, larg_area, alt_area):
    """Retângulo (x, y, w, h) onde a imagem cabe na área mantendo a proporção."""
    if not larg_quadro or not alt_quadro or larg_area <= 0 or alt_area <= 0:
        return 0, 0, 0, 0
    esc = min(larg_area / larg_quadro, alt_area / alt_quadro)
    w, h = int(larg_quadro * esc), int(alt_quadro * esc)
    return (larg_area - w) // 2, (alt_area - h) // 2, w, h
