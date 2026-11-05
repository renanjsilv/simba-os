#!/usr/bin/env python3
"""Train the "Draco" wake-word detector (openWakeWord features + a small classifier).

Positives ("Draco" ending near the end of a 2.4 s window):
  - every Piper voice in voices/ and 16 Microsoft neural voices (wake-train/edge, made by
    wake_edge.py), with speed, pitch, reverb, mic coloring, noise and background talk varied
  - your own takes in wake-train/minhas/*.wav (`draco treinar`, wake_record.py), augmented with
    faster/slower speech and distance; a quarter kept out to measure "sua voz"
  - wake-train/auto-sim: real triggers the transcript confirmed (saved by wake.py/draco)
Negatives:
  - ~5 h of Portuguese read by dozens of LibriVox speakers (wake-train/fala-pt/*.raw)
  - sound-alikes ("fraco", "Drácula", "braço"...) and everyday sentences in all voices
  - your own talk without the name (wake-train/minha-fala), and the room: wake-train/ambiente.raw, wake-train/negativos-reais/*.wav (things that
    used to trigger it) and wake-train/auto-nao (triggers the check rejected)

Honest test: two Microsoft voices, one Piper voice, half of Renan's takes and a fifth
of the LibriVox files are never trained on. The report gives recall and false alarms
per hour of speech for several thresholds, for the new model and the current one; the
chosen threshold (at most MAX_FA_PER_HOUR) is stored in the model for wake.py.

  wake_train.py              train, compare, and install models/draco_wake.npz if better
  wake_train.py --forcar     install even if it isn't better
  wake_train.py --refazer    also rebuild the cached synthetic/LibriVox features

Re-run it now and then: the auto-sim/auto-nao folders grow by themselves.
"""
import glob
import hashlib
import os
import random
import shutil
import sys
import wave

import numpy as np
from openwakeword.utils import AudioFeatures
from scipy.signal import butter, fftconvolve, resample_poly, sosfilt
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

CODIGO = os.path.dirname(os.path.abspath(__file__))   # /usr/share/draco (pacote)
DATA = os.path.expanduser("~/.local/share/draco")     # dados do usuário
TRAIN = os.path.join(DATA, "wake-train")
CACHE = os.path.join(TRAIN, "cache")
OUT = os.path.join(DATA, "models", "draco_wake.npz")
SR = 16000
CLIP = int(2.4 * SR)   # analysis window; the classifier sees its last 16 feature frames
N_FRAMES = 16
MAX_FA_PER_HOUR = 12.0 # false alarms per hour of nonstop nearby speech the threshold may allow
                       # (each one is invisible: Groq rejects it before the orb shows; it costs one request)
REFRACTORY = 2.0
HELD_OUT_PIPER = "pt_BR-jeff-medium"
HELD_OUT_EDGE = ("pt-BR-FranciscaNeural", "en-US-BrianMultilingualNeural")
rng = np.random.default_rng(7)
random.seed(7)

POSITIVE_TEXTS = ["Draco.", "Draco!", "Draco,", "Draco?", "Ei, Draco.", "Ô Draco.", "Fala, Draco.", "Oi Draco."]
SOUNDALIKES = ["dragão", "Drácula", "braço", "fraco", "claro", "barco", "trago", "Marcos", "draga", "traço",
               "craque", "Paco", "macaco", "drama", "Diego", "Raquel", "parco", "cravo", "graça", "bravo",
               "trato", "tráfego", "Dráuzio", "Dragon", "Arco", "Darco", "Franco", "Blanco", "Marco", "drástico",
               "dado", "Jacó", "o carro", "barato", "é claro", "trabalho", "obrigado"]
SENTENCES = """Bom dia, tudo bem com você?
Que horas são agora?
Vou passar no mercado depois do trabalho.
Você viu onde eu deixei a chave do carro?
Amanhã vai chover o dia inteiro.
Preciso terminar esse relatório hoje.
O jogo de ontem foi muito bom.
Liga pra sua mãe quando puder.
Esse filme é muito antigo, mas é ótimo.
A gente pode almoçar fora no domingo.
Abre a janela que está muito quente aqui.
Coloca uma música para tocar.
Qual é a previsão do tempo para amanhã?
Eu esqueci de pagar a conta de luz.
O cachorro está latindo lá fora.
Vamos marcar uma reunião na segunda-feira.
Me manda a foto que você tirou.
O ônibus atrasou de novo hoje cedo.
Você quer café ou chá?
Eu adoro pizza de calabresa.
O dragão voou sobre a cidade.
O Marcos foi trabalhar cedo.
Preciso comprar um cabo novo para o celular.
Drácula é um filme de terror clássico.
Ele quebrou o braço jogando bola.
O barco saiu do porto às seis horas.
Está claro que vai dar certo.
Eu trago o bolo para a festa.
O trânsito está horrível na avenida.
Não esquece de desligar o forno.
A internet caiu de novo.
Vou dormir mais cedo hoje.
Quanto custa esse tênis?
Meu irmão chega amanhã de viagem.
Pode deixar que eu resolvo isso.
Que saudade das férias na praia.
Vamos assistir uma série hoje à noite?
Esse computador está muito lento.
A reunião foi adiada para quinta.
Você já jantou?
Abre o Spotify e coloca algo relaxante.
Manda uma mensagem pra minha namorada.
Que dia é hoje?
Eu não entendi o que você falou.
Fala mais devagar, por favor.
Minha bateria está acabando.
Tá muito frio lá fora.
Bora jogar videogame mais tarde?
Isso aí, muito bem!
Cadê o controle da televisão?
Eu acho que vou pedir comida hoje.
Olha só que legal esse vídeo.
Ela disse que vai chegar atrasada.
Não sei se vou conseguir ir amanhã.
Deixa eu ver aqui no celular.
Tem que lavar a louça ainda.
Que barulho é esse lá fora?
Vou tomar banho e já volto.
A gente se fala depois, tá bom?
Esse jogo está travando muito.
Você lembra o nome daquele restaurante?
O preço da gasolina subiu de novo.
Tô morrendo de fome.
Vamos sair para caminhar no parque?
Acabou o café, alguém compra?
Desliga a luz da sala, por favor.
O Brasil ganhou o jogo ontem.
Você pode me ajudar com isso?
Hoje é aniversário da minha avó.
Fica tranquilo, vai dar tudo certo.
Draga de areia no rio, drama na novela e um dragão no desenho.
O cravo brigou com a rosa.
Trago notícias boas para você.
Claro que sim, pode contar comigo.
Que bravo esse cachorro do vizinho.
Muito obrigada pelo convite.
Não, não vou deixar.
Será? Eu quero ver.""".splitlines()


# ---------------------------------------------------------------- audio helpers

def to16k(x, sr):
    x = x.astype(np.float32)
    return x if sr == SR else resample_poly(x, SR, sr).astype(np.float32)


def load(path):
    """Any audio file as float32 16 kHz mono (int16 scale)."""
    if path.endswith(".raw"):
        return np.frombuffer(open(path, "rb").read(), np.int16).astype(np.float32)
    if path.endswith(".wav"):
        with wave.open(path) as w:
            sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
            a = np.frombuffer(w.readframes(n), np.int16).astype(np.float32)
        if ch > 1:
            a = a.reshape(-1, ch).mean(axis=1)
        return to16k(a, sr)
    import subprocess
    raw = subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(SR),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32)


def trim(x, rel=0.05):
    """Cut leading/trailing silence (relative to the clip's peak)."""
    env = np.convolve(np.abs(x), np.ones(160) / 160, "same")
    idx = np.where(env > max(rel * env.max(), 50))[0]
    return x[max(idx[0] - 160, 0):idx[-1] + 160] if len(idx) else x


AMBIENT = SPEECH_BG = None


def noise(n):
    """Background: the recorded room, distant LibriVox talk, or synthetic white/pink noise."""
    r = rng.random()
    if AMBIENT is not None and len(AMBIENT) > n and r < 0.35:
        s = rng.integers(0, len(AMBIENT) - n)
        return AMBIENT[s:s + n].copy()
    if SPEECH_BG is not None and r < 0.6:
        s = rng.integers(0, len(SPEECH_BG) - n)
        bg = SPEECH_BG[s:s + n].copy()
        return bg + rng.standard_normal(n).astype(np.float32) * 0.02 * (np.std(bg) + 1)
    w = rng.standard_normal(n).astype(np.float32)
    if rng.random() < 0.5:  # pinkish
        k = max(1, min(400, n))
        w = np.cumsum(w); w -= np.convolve(w, np.ones(k) / k, "same")
    return w / (np.std(w) + 1e-6) * 100


def augment(x, strong=False, speed=None):
    lo, hi = speed or ((0.85, 1.15) if strong else (0.9, 1.1))
    f = rng.uniform(lo, hi)  # speed + pitch
    x = resample_poly(x, 100, int(100 * f)).astype(np.float32)
    if rng.random() < 0.5:  # room reverb
        n = int(rng.uniform(0.1, 0.5) * SR)
        rir = rng.standard_normal(n) * np.exp(-np.linspace(0, rng.uniform(3, 9), n))
        rir[0] = 1.0
        x = fftconvolve(x, rir)[: len(x)].astype(np.float32)
    if rng.random() < 0.5:  # microphone/speaker coloring
        lo, hi = rng.uniform(80, 400), rng.uniform(3000, 7500)
        x = sosfilt(butter(2, [lo, hi], "bandpass", fs=SR, output="sos"), x).astype(np.float32)
    x = x / (np.max(np.abs(x)) + 1e-6) * rng.uniform(1500, 22000)  # level
    return x


def place(word, snr_range=(3, 30), tail=(0.05, 0.35)):
    """2.4 s clip of background with `word` ending `tail` s before the end."""
    out = noise(CLIP)
    snr = rng.uniform(*snr_range)
    out *= np.sqrt(np.mean(word ** 2) / (np.mean(out ** 2) + 1e-6)) / (10 ** (snr / 20))
    end = CLIP - int(rng.uniform(*tail) * SR)
    start = max(0, end - len(word))
    out[start:end] += word[-(end - start):]
    return np.clip(out, -32768, 32767)


def fit_clip(x):
    """A clip that already ends at the detection (auto-*): left-pad/cut to 2.4 s."""
    if len(x) >= CLIP:
        return x[-CLIP:]
    return np.concatenate([noise(CLIP - len(x)) * 0.1, x])


# ---------------------------------------------------------------- features

AF = None


def af():
    global AF
    if AF is None:
        AF = AudioFeatures(ncpu=os.cpu_count())
    return AF


def clip_features(clips):
    if not clips:
        return np.zeros((0, N_FRAMES * 96), np.float32)
    arr = np.stack([np.clip(c, -32768, 32767).astype(np.int16) for c in clips])
    emb = af().embed_clips(arr, batch_size=64)
    return emb[:, -N_FRAMES:, :].reshape(len(clips), -1).astype(np.float32)


def stream_features(x, hop=1):
    """Every 16-frame window (one per 80 ms * hop) of a long recording, like wake.py sees it."""
    x = np.concatenate([np.zeros(SR, np.float32), x])
    emb = af()._get_embeddings(np.clip(x, -32768, 32767).astype(np.int16))
    if len(emb) < N_FRAMES:
        return np.zeros((0, N_FRAMES * 96), np.float32)
    idx = np.arange(N_FRAMES, len(emb) + 1, hop)
    return np.stack([emb[i - N_FRAMES:i].reshape(-1) for i in idx]).astype(np.float32)


def cached(name, files, build):
    """Features for a static source, cached by its file list."""
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.sha1("\n".join(f"{os.path.realpath(f)}:{os.path.getsize(f)}" for f in files).encode()).hexdigest()[:12]
    path = os.path.join(CACHE, f"{name}.npz")
    if os.path.exists(path) and "--refazer" not in sys.argv:
        c = np.load(path)
        if str(c["key"]) == key:
            return {k: c[k] for k in c.files if k != "key"}
    print(f"  calculando {name}...", flush=True)
    out = build()
    np.savez_compressed(path, key=key, **out)
    return out


# ---------------------------------------------------------------- sources

def piper_source():
    from piper import PiperVoice, SynthesisConfig
    files = sorted(glob.glob(os.path.join(DATA, "voices", "*.onnx")))

    def synth(v, text, ls, ns, nw):
        cfg = SynthesisConfig(length_scale=ls, noise_scale=ns, noise_w_scale=nw)
        chunks = [c.audio_int16_array for c in v.synthesize(text, syn_config=cfg)]
        return trim(to16k(np.concatenate(chunks), v.config.sample_rate)) if chunks else np.zeros(1600, np.float32)

    def build():
        out = {k: [] for k in ("pos", "neg", "pos_test", "neg_test")}
        for p in files:
            name = os.path.basename(p)[:-5]
            v = PiperVoice.load(p)
            sfx = "_test" if name == HELD_OUT_PIPER else ""
            pos, neg = [], []
            for text in POSITIVE_TEXTS:
                for ls in (0.8, 0.95, 1.1, 1.3):
                    for ns in (0.4, 0.667, 0.9):
                        w = synth(v, text, ls, ns, rng.uniform(0.5, 1.0))
                        pos += [place(augment(w)) for _ in range(2)]
            for text in SOUNDALIKES:
                for ls in (0.85, 1.0, 1.2):
                    w = synth(v, text, ls, 0.667, 0.8)
                    neg += [place(augment(w)) for _ in range(3)]
            feats_neg = [clip_features(neg)]
            for text in SENTENCES:
                w = synth(v, text, rng.choice([0.9, 1.0, 1.15]), 0.667, 0.8)
                feats_neg.append(stream_features(np.concatenate([augment(w), noise(int(0.5 * SR)) * 0.2]), hop=2))
            out["pos" + sfx].append(clip_features(pos))
            out["neg" + sfx].append(np.vstack(feats_neg))
            print(f"    piper {name}: {len(pos)} pos", flush=True)
        return {k: np.vstack(v) for k, v in out.items()}

    return cached("piper", files, build)


def edge_source():
    pos_files = sorted(glob.glob(os.path.join(TRAIN, "edge", "pos", "*.mp3")))
    neg_files = sorted(glob.glob(os.path.join(TRAIN, "edge", "neg", "*.mp3")))

    def test(f):
        return os.path.basename(f).startswith(HELD_OUT_EDGE)

    def build():
        out = {k: [] for k in ("pos", "neg", "pos_test", "neg_test")}
        for f in pos_files:
            w = trim(load(f))
            out["pos_test" if test(f) else "pos"] += [place(augment(w, strong=True)) for _ in range(3)]
        words, sents = {"neg": [], "neg_test": []}, {"neg": [], "neg_test": []}
        for f in neg_files:
            w = trim(load(f))
            k = "neg_test" if test(f) else "neg"
            if "_w" in os.path.basename(f):
                words[k] += [place(augment(w)) for _ in range(2)]
            else:
                sents[k].append(stream_features(np.concatenate([augment(w), noise(int(0.5 * SR)) * 0.2]), hop=2))
        res = {"pos": clip_features(out["pos"]), "pos_test": clip_features(out["pos_test"])}
        for k in ("neg", "neg_test"):
            res[k] = np.vstack([clip_features(words[k])] + sents[k])
        return res

    return cached("edge", pos_files + neg_files, build) if pos_files else {}


def librivox_files():
    files = sorted(glob.glob(os.path.join(TRAIN, "fala-pt", "*.raw")))
    test = [f for i, f in enumerate(files) if i % 5 == 0]
    return [f for f in files if f not in test], test


def librivox_source():
    train, test = librivox_files()

    def build():
        tr = [stream_features(load(f), hop=2) for f in train]
        return {"neg": np.vstack(tr) if tr else np.zeros((0, N_FRAMES * 96), np.float32)}

    return cached("librivox", train, build) if train else {}


def real_sources():
    """Renan's takes and the room: small, recomputed every run."""
    out = {k: [] for k in ("pos", "neg", "pos_test", "neg_test")}
    # Your own takes (wake_record.py): every 4th is kept out for the "sua voz" test.
    # Wider speed range (fast "Draco"s) and quieter/noisier copies (from across the room).
    out["pos_own_test"] = []
    mine = sorted(glob.glob(os.path.join(TRAIN, "minhas", "*.wav")))
    for i, f in enumerate(mine):
        x = trim(load(f))
        joined = "_emendado_" in os.path.basename(f)  # "Draco" + the start of a request
        word = x[: int(0.9 * SR)] if len(x) > 1.2 * SR and not joined else x  # old long takes start with "Draco"
        tail = (0.0, 0.12) if joined else (0.05, 0.35)
        if i % 4 == 3:
            out["pos_own_test"] += [place(augment(word, speed=(0.95, 1.2)), (8, 30), tail) for _ in range(6)]
        else:
            out["pos"] += [place(augment(word, speed=(0.8, 1.35)), (0, 30), tail) for _ in range(80)]
    auto_sim = sorted(glob.glob(os.path.join(TRAIN, "auto-sim", "*.wav")))
    for f in auto_sim:
        x = load(f)
        out["pos"] += [fit_clip(x)] + [fit_clip(augment(x)) for _ in range(9)]
    auto_nao = sorted(glob.glob(os.path.join(TRAIN, "auto-nao", "*.wav")))
    for f in auto_nao:
        x = load(f)
        out["neg"] += [fit_clip(x)] + [fit_clip(augment(x)) for _ in range(4)]
    print(f"  suas gravações: {len(mine)}; auto-sim: {len(auto_sim)}; auto-nao: {len(auto_nao)}", flush=True)
    res = {k: clip_features(v) for k, v in out.items()}
    # Your own talk without the name (wake_record.py): it must stay quiet on your voice.
    talk = sorted(glob.glob(os.path.join(TRAIN, "minha-fala", "*.wav")))
    for f in talk:
        x = load(f)
        res["neg"] = np.vstack([res["neg"], stream_features(x), stream_features(augment(x)), stream_features(augment(x))])
    reais = sorted(glob.glob(os.path.join(TRAIN, "negativos-reais", "*.wav")))
    if reais:
        res["neg"] = np.vstack([res["neg"]] + [stream_features(load(f)) for f in reais])
    if AMBIENT is not None:
        half = len(AMBIENT) // 2
        res["neg"] = np.vstack([res["neg"], stream_features(AMBIENT[:half])])
    res["neg"] = np.vstack([res["neg"], clip_features([noise(CLIP) for _ in range(300)])])
    return res


# ---------------------------------------------------------------- training and evaluation

def false_alarms(scores, th):
    """Detections in a stream of 80 ms scores, with wake.py's refractory period."""
    n, last = 0, -1e9
    for i in np.where(scores >= th)[0]:
        if (i - last) * 0.08 >= REFRACTORY:
            n, last = n + 1, i
    return n


def load_model(path):
    m = np.load(path)

    def score(X):
        x = (X - m["mean"]) / m["scale"]
        h = np.maximum(x @ m["W1"] + m["b1"], 0)
        return 1 / (1 + np.exp(-(h @ m["W2"] + m["b2"]).ravel()))
    return score


GRID = (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.92, 0.94, 0.95, 0.96, 0.97, 0.98, 0.99)
INSTANT_FA = 3.0  # false alarms per hour allowed to show the orb before the cloud check


def evaluate(score, pos_test, test_streams, hours, label):
    sp = score(pos_test)
    s_streams = [score(X) for X in test_streams]
    rows = []
    for th in GRID:
        fa = sum(false_alarms(s, th) for s in s_streams) / hours
        rows.append((th, float(np.mean(sp >= th)), fa))
    print(f"\n{label}")
    for th, rec, fa in rows:
        print(f"  limiar {th:.2f}: acerta {rec:6.1%} dos 'Draco' de teste | {fa:5.2f} alarmes falsos/hora de fala")
    return rows


def pick(rows):
    """Lowest threshold within the false-alarm budget (best recall)."""
    ok = [r for r in rows if r[2] <= MAX_FA_PER_HOUR]
    return min(ok, key=lambda r: r[0]) if ok else max(rows, key=lambda r: r[0])


def main():
    global AMBIENT, SPEECH_BG
    amb = os.path.join(TRAIN, "ambiente.raw")
    if os.path.exists(amb):
        AMBIENT = load(amb)
    train_lv, test_lv = librivox_files()
    if train_lv:
        SPEECH_BG = np.concatenate([load(f)[: 60 * SR] for f in train_lv[::4]])

    print("fontes:", flush=True)
    sources = [piper_source(), edge_source(), librivox_source(), real_sources()]
    get = lambda k: np.vstack([s[k] for s in sources if k in s and len(s[k])])
    Xp, Xn, Xpt = get("pos"), get("neg"), get("pos_test")
    print(f"treino: {len(Xp)} positivos, {len(Xn)} negativos; teste: {len(Xpt)} positivos", flush=True)

    # Test streams: held-out LibriVox speakers, the other half of the room, held-out voices' sentences.
    streams = [stream_features(load(f)) for f in test_lv]
    seconds = sum(len(load(f)) for f in test_lv) / SR
    if AMBIENT is not None:
        half = AMBIENT[len(AMBIENT) // 2:]
        streams.append(stream_features(half))
        seconds += len(half) / SR
    hours = seconds / 3600
    print(f"fala de teste (nunca vista): {hours:.2f} h", flush=True)

    Xown = get("pos_own_test") if any("pos_own_test" in s and len(s["pos_own_test"]) for s in sources) else None
    if Xown is not None:
        print(f"seus 'Draco' de teste (nunca vistos no treino): {len(Xown)}", flush=True)

    def own(score, th):
        return float(np.mean(score(Xown) >= th)) if Xown is not None else None

    X = np.vstack([Xp, Xn]); y = np.r_[np.ones(len(Xp)), np.zeros(len(Xn))]
    w = np.r_[np.full(len(Xp), len(Xn) / len(Xp) * 0.3), np.ones(len(Xn))]  # balance the classes (partly)
    scaler = StandardScaler().fit(X)
    idx = rng.permutation(len(X))
    best = None
    for hidden, alpha in (((64,), 1e-2), ((128,), 1e-2), ((128,), 1e-3)):
        clf = MLPClassifier(hidden_layer_sizes=hidden, alpha=alpha, max_iter=300, early_stopping=True,
                            n_iter_no_change=8, random_state=7)
        clf.fit(scaler.transform(X[idx]), y[idx], sample_weight=w[idx])
        model = dict(mean=scaler.mean_, scale=scaler.scale_, W1=clf.coefs_[0], b1=clf.intercepts_[0],
                     W2=clf.coefs_[1], b2=clf.intercepts_[1])
        tmp = os.path.join(CACHE, "candidate.npz")
        np.savez(tmp, **model)
        score = load_model(tmp)
        rows = evaluate(score, Xpt, streams, hours, f"novo modelo {hidden} alpha={alpha}")
        th, rec, fa = pick(rows)
        mine = own(score, th)
        if mine is not None:
            print(f"  sua voz no limiar {th:.2f}: acerta {mine:.1%}")
        key = (mine if mine is not None else rec, rec, -fa)  # your voice first
        if best is None or key > best[0]:
            instant = min((r[0] for r in rows if r[0] >= th and r[2] <= INSTANT_FA), default=0.99)
            best = (key, th, rec, fa, mine, instant, model, hidden, alpha)

    _, th, rec, fa, mine, instant, model, hidden, alpha = best
    print(f"\nescolhido: {hidden} alpha={alpha}, limiar {th:.2f} (orb na hora a partir de {instant:.2f}): "
          f"acerta {rec:.1%} das vozes de teste, {fa:.2f} alarmes falsos/hora")
    old_mine = None
    if os.path.exists(OUT):
        m = np.load(OUT)
        old_th = float(m["threshold"]) if "threshold" in m.files else 0.75
        old_score = load_model(OUT)
        old_rows = evaluate(old_score, Xpt, streams, hours, "modelo atual (mesmo teste)")
        old = min(old_rows, key=lambda r: abs(r[0] - old_th))
        old_rec, old_fa = old[1], old[2]
        old_mine = own(old_score, old_th)
        print(f"atual no limiar em uso ({old_th:.2f}): acerta {old_rec:.1%}, {old_fa:.2f} alarmes falsos/hora"
              + (f"; sua voz: {old_mine:.1%}" if old_mine is not None else ""))
        if mine is not None:
            # Your voice decides, as long as other voices and false alarms don't get much worse.
            better = mine >= old_mine + 0.02 and rec >= old_rec - 0.15 and fa <= max(old_fa, MAX_FA_PER_HOUR)
        else:
            better = rec >= old_rec - 0.01 and fa <= max(old_fa, MAX_FA_PER_HOUR)
        if not better and "--forcar" not in sys.argv:
            print("o novo não é melhor: mantive o atual (use --forcar para instalar mesmo assim)")
            return
        shutil.copy(OUT, OUT + ".anterior")
    np.savez(OUT, threshold=th, instant=instant, **model)
    if mine is not None:
        print(f"sua voz: acerta {mine:.0%} dos seus Draco de teste" +
              (f", antes eram {old_mine:.0%}." if old_mine is not None else "."))
    print(f"instalado: {OUT} (limiar {th:.2f}, orb na hora a partir de {instant:.2f}); "
          "reinicie: systemctl --user restart draco-wake")


if __name__ == "__main__":
    main()
