"""Tiny OCR server: loads Tesseract (Portuguese) once, then answers requests.

stdin, one request per line:   <png path>\t<page seg mode>\t<plain|green>
stdout, per request:           the recognized text, then the line @@OCR_END@@

"green" keeps only bright/green text (WhatsApp names and highlights), dropping the
grey previews and dates: green channel -> threshold -> black text on white.
Runs as a coprocess of dr-whatsapp, so the model loads once per command instead
of once per screenshot (~0.4s each).
"""
import ctypes
import locale
import os
import sys

locale.setlocale(locale.LC_ALL, "C")  # required by the Tesseract API

tess = ctypes.CDLL("libtesseract.so.5")
lept = ctypes.CDLL("libleptonica.so.6")

tess.TessBaseAPICreate.restype = ctypes.c_void_p
tess.TessBaseAPIInit3.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
tess.TessBaseAPISetPageSegMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
tess.TessBaseAPISetImage2.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
tess.TessBaseAPIGetUTF8Text.argtypes = [ctypes.c_void_p]
tess.TessBaseAPIGetUTF8Text.restype = ctypes.c_void_p
tess.TessDeleteText.argtypes = [ctypes.c_void_p]

lept.pixRead.argtypes = [ctypes.c_char_p]
lept.pixRead.restype = ctypes.c_void_p
lept.pixConvertRGBToGray.argtypes = [ctypes.c_void_p, ctypes.c_float, ctypes.c_float, ctypes.c_float]
lept.pixConvertRGBToGray.restype = ctypes.c_void_p
lept.pixThresholdToBinary.argtypes = [ctypes.c_void_p, ctypes.c_int]
lept.pixThresholdToBinary.restype = ctypes.c_void_p
lept.pixDestroy.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
lept.pixInvert.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
lept.pixInvert.restype = ctypes.c_void_p

api = tess.TessBaseAPICreate()
datapath = os.environ.get("TESSDATA_PREFIX", "/usr/share/tessdata").encode()
if tess.TessBaseAPIInit3(api, datapath, b"por") != 0:
    sys.exit("ocr_server: could not load the Portuguese model")


def destroy(pix):
    if pix:
        p = ctypes.c_void_p(pix)
        lept.pixDestroy(ctypes.byref(p))


def recognize(path, psm, mode):
    pix = lept.pixRead(path.encode())
    if not pix:
        return ""
    owned = [pix]
    if mode == "green":
        gray = lept.pixConvertRGBToGray(pix, 0.0, 1.0, 0.0)
        # pixels darker than the threshold become black: that's the background
        # and the grey text, so the result is white text on black...
        binary = lept.pixThresholdToBinary(gray, 168) if gray else None
        # ...and inverting gives black text on white (in 1bpp, 1 = black).
        inverted = lept.pixInvert(None, binary) if binary else None
        owned += [gray, binary, inverted]
        pix = inverted or pix
    tess.TessBaseAPISetPageSegMode(api, psm)
    tess.TessBaseAPISetImage2(api, pix)
    ptr = tess.TessBaseAPIGetUTF8Text(api)
    text = ctypes.string_at(ptr).decode("utf-8", "replace") if ptr else ""
    if ptr:
        tess.TessDeleteText(ptr)
    for p in owned:
        destroy(p)
    return text


for line in sys.stdin:
    try:
        path, psm, mode = line.rstrip("\n").split("\t")
        out = recognize(path, int(psm), mode)
    except Exception as e:  # keep serving; the caller just sees no text
        out = ""
        print(f"ocr_server: {e}", file=sys.stderr)
    sys.stdout.write(out.rstrip("\n") + "\n@@OCR_END@@\n")
    sys.stdout.flush()
