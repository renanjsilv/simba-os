"""Codificador H.264 afinado para tela (substitui o do aiortc, pensado para webcam).

- x264 `superfast` + `zerolatency`: ~4x menos tempo por quadro que o padrão (medium)
- qualidade constante (CRF) com teto de banda (VBV) = estimativa da rede: tela parada custa
  quase nada e texto fica nítido; rolagem usa a banda disponível
- NÃO recria o codificador a cada variação de banda (o aiortc recriava a cada 10%, cada vez
  mandando um quadro-chave enorme → engasgos); só se a banda mudar mais de 2x e no máximo a cada 4 s
"""
import fractions
import time

import av
from aiortc.codecs import h264

MAX_FPS = 30
CRF = "22"


def _encode_frame(self, frame, force_keyframe):
    agora = time.monotonic()
    alvo = self.target_bitrate
    if self.codec is not None:
        atual = getattr(self, "_sr_bitrate", alvo)
        mudou_muito = alvo > atual * 2 or alvo < atual / 2
        if (frame.width != self.codec.width or frame.height != self.codec.height
                or (mudou_muito and agora - getattr(self, "_sr_criado", 0) > 4)):
            self.buffer_data = b""
            self.buffer_pts = None
            self.codec = None

    frame.pict_type = av.video.frame.PictureType.I if force_keyframe else av.video.frame.PictureType.NONE

    if self.codec is None:
        kbps = max(500, alvo // 1000)
        c = av.CodecContext.create("libx264", "w")
        c.width = frame.width
        c.height = frame.height
        c.pix_fmt = "yuv420p"
        c.framerate = fractions.Fraction(MAX_FPS, 1)
        c.time_base = fractions.Fraction(1, MAX_FPS)
        c.options = {
            "preset": "superfast",
            "tune": "zerolatency",
            "crf": CRF,
            "level": "41",
            # buffer de ~1/3 s: segura picos sem acumular atraso
            "x264-params": f"vbv-maxrate={kbps}:vbv-bufsize={max(200, kbps // 3)}:keyint=300:min-keyint=30",
        }
        c.profile = "Baseline"
        self.codec = c
        self._sr_bitrate = alvo
        self._sr_criado = agora

    dados = b""
    for pacote in self.codec.encode(frame):
        dados += bytes(pacote)
    if dados:
        yield from self._split_bitstream(dados)


def instalar():
    h264.H264Encoder._encode_frame = _encode_frame
    h264.MIN_BITRATE = 1_000_000
    h264.DEFAULT_BITRATE = 6_000_000
    h264.MAX_BITRATE = 15_000_000
