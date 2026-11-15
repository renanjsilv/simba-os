#!/usr/bin/env python3
"""Clean up a Whisper transcript before it goes to Claude.

  transcript.py groq <verbose.json>     Groq/OpenAI verbose_json (segments + word timestamps)
  transcript.py text "<texto>"          plain text (local Whisper fallback)

Prints the request text. Drops segments Whisper made up (silence/noise:
"Obrigado.", "Legendas pela comunidade Amara.org"...).
"""
import json
import re
import sys

# Whisper's classic inventions on silence/noise in Portuguese (subtitle credits etc.)
HALLUCINATIONS = re.compile(
    r"^(obrigad[oa]s?( por assistir)?|tchau|legendas? .*|.*amara\.org.*|inscreva-se.*|"
    r"(e )?at[eé] (a )?pr[oó]xima|sous-titr.*|subt[ií]tulos.*)[.!? ]*$", re.I)


def made_up(seg):
    """A segment Whisper most likely invented (silence, noise, repetition loop)."""
    if seg.get("no_speech_prob", 0) > 0.6 and seg.get("avg_logprob", 0) < -0.5:
        return True
    if seg.get("compression_ratio", 0) > 2.4:
        return True
    return seg.get("no_speech_prob", 0) > 0.2 and HALLUCINATIONS.match(seg.get("text", "").strip()) is not None


def from_groq(data):
    segs = data.get("segments") or []
    words = data.get("words")
    if words is None:  # no word timestamps: fall back to the text
        text = " ".join(s["text"].strip() for s in segs if not made_up(s)) if segs else data.get("text", "")
        return from_text(text)
    bad = [(s["start"], s["end"]) for s in segs if made_up(s)]
    words = [w for w in words if not any(a - 0.05 <= w["start"] and w["end"] <= b + 0.05 for a, b in bad)]
    return " ".join(w["word"].strip() for w in words)


def from_text(text):
    text = text.strip()
    return "" if HALLUCINATIONS.match(text) else text


def clean(text):
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"^[,.;:!?…\- ]+", "", text).strip()


def main():
    mode, src = sys.argv[1], sys.argv[2]
    if mode == "groq":
        with open(src) as f:
            text = from_groq(json.load(f))
    else:
        text = from_text(src)
    print(clean(text))


if __name__ == "__main__":
    main()
