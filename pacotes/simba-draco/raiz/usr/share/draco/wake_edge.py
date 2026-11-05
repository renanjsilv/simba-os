#!/usr/bin/env python3
"""More voices for wake_train.py: "Draco" (and sound-alikes/sentences) from Microsoft's
neural voices via edge-tts, into wake-train/edge/{pos,neg}/*.mp3. Run once; it skips
what's already there. Needs internet.
"""
import asyncio
import os
import random

import edge_tts

CODIGO = os.path.dirname(os.path.abspath(__file__))   # /usr/share/draco (pacote)
DATA = os.path.expanduser("~/.local/share/draco")     # dados do usuário
OUT = os.path.join(DATA, "wake-train", "edge")
VOICES = ["pt-BR-AntonioNeural", "pt-BR-FranciscaNeural", "pt-BR-ThalitaMultilingualNeural",
          "pt-PT-DuarteNeural", "pt-PT-RaquelNeural", "en-US-AndrewMultilingualNeural",
          "en-US-AvaMultilingualNeural", "en-US-BrianMultilingualNeural", "en-US-EmmaMultilingualNeural",
          "en-AU-WilliamMultilingualNeural", "de-DE-FlorianMultilingualNeural", "de-DE-SeraphinaMultilingualNeural",
          "fr-FR-RemyMultilingualNeural", "fr-FR-VivienneMultilingualNeural", "it-IT-GiuseppeMultilingualNeural",
          "ko-KR-HyunsuMultilingualNeural"]
POS = ["Draco.", "Draco!", "Draco?", "Draco,", "Ei, Draco.", "Ô Draco!", "Fala, Draco.", "Oi, Draco."]
PROSODY = [("+0%", "+0Hz"), ("-20%", "-8Hz"), ("+20%", "+8Hz"), ("-10%", "+15Hz"), ("+10%", "-15Hz")]
NEG = ["dragão", "Drácula", "braço", "fraco", "claro", "barco", "trago", "Marcos", "draga", "traço",
       "craque", "Paco", "macaco", "drama", "Diego", "parco", "cravo", "graça", "bravo", "trato", "Dráuzio",
       "Arco", "Franco", "Blanco", "Marco", "drástico", "dado", "tráfico", "Jacó", "Taco", "Draga", "galego",
       "o carro", "barato", "tá caro", "é claro", "de cabo", "do lado", "trabalho", "obrigado"]
SENTENCES = ["Que horas são agora?", "Vou passar no mercado depois do trabalho.", "Você viu onde eu deixei a chave?",
             "Muito obrigada pelo convite.", "Não, não vou deixar.", "Será? Eu quero ver.", "E aí, tudo certo?",
             "Ele está fraco hoje, quebrou o braço.", "Claro que sim, pode contar comigo.", "O dragão voou alto.",
             "Esse barco é muito caro.", "Eu trago o bolo amanhã.", "O Marcos chegou atrasado de novo.",
             "Tá muito frio lá fora.", "Desliga a televisão, por favor.", "Cadê o controle remoto?",
             "Bora jogar videogame mais tarde?", "Eu acho que vou pedir comida hoje.", "A gente se fala depois.",
             "O Drácula é um clássico do terror.", "Que drama, hein!", "Esse cara é craque de bola."]


async def one(sem, text, voice, rate, pitch, path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return
    async with sem:
        for attempt in range(3):
            try:
                await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(path)
                return
            except Exception:
                await asyncio.sleep(1 + attempt)
        if os.path.exists(path):
            os.unlink(path)


async def main():
    random.seed(3)
    for d in ("pos", "neg"):
        os.makedirs(os.path.join(OUT, d), exist_ok=True)
    sem = asyncio.Semaphore(12)
    jobs = []
    for v in VOICES:
        for i, t in enumerate(POS):
            for j, (r, p) in enumerate(PROSODY):
                jobs.append(one(sem, t, v, r, p, os.path.join(OUT, "pos", f"{v}_{i}_{j}.mp3")))
        for i, t in enumerate(NEG):
            r, p = random.choice(PROSODY)
            jobs.append(one(sem, t, v, r, p, os.path.join(OUT, "neg", f"{v}_w{i}.mp3")))
        for i, t in enumerate(SENTENCES):
            r, p = random.choice(PROSODY)
            jobs.append(one(sem, t, v, r, p, os.path.join(OUT, "neg", f"{v}_s{i}.mp3")))
    await asyncio.gather(*jobs)
    print({d: len(os.listdir(os.path.join(OUT, d))) for d in ("pos", "neg")})


if __name__ == "__main__":
    asyncio.run(main())
