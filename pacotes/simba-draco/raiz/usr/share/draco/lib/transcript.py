#!/usr/bin/env python3
"""Clean up a Whisper transcript before it goes to Claude.

  transcript.py groq <verbose.json> [--wake <s> [--gatilho <verbose.json>]]
                                                   Groq verbose_json (word timestamps)
  transcript.py text "<texto>" [--wake <s>]        plain text (local Whisper fallback)
  transcript.py gatilho <verbose.json>             exit 0 if the trigger clip says "Draco", else 2

Prints the request text. Drops segments Whisper made up (silence/noise:
"Obrigado.", "Legendas pela comunidade Amara.org"...).

With --wake <s> (the request came from the wake word, and the audio starts with the
<s> seconds before the detection) it is also the final check that "Draco" was really
said: a Draco-like word must start before <s> + WAKE_SLACK. That word and everything
said before it (someone else talking) are removed. --gatilho is the transcript of
the trigger audio alone (those <s> seconds): in a long, noisy recording Whisper
sometimes drops the name, but it hears it in the short clip; then everything said
before the detection is removed instead.
Exit codes: 0 ok, 2 no "Draco" (false alarm), 3 nothing left to do (only "Draco").
"""
import difflib
import json
import re
import sys
import unicodedata

WAKE_SLACK = 0.6  # the detector fires right after the word; allow a little drift
# Whisper's classic inventions on silence/noise in Portuguese (subtitle credits etc.)
HALLUCINATIONS = re.compile(
    r"^(obrigad[oa]s?( por assistir)?|tchau|legendas? .*|.*amara\.org.*|inscreva-se.*|"
    r"(e )?at[eé] (a )?pr[oó]xima|sous-titr.*|subt[ií]tulos.*)[.!? ]*$", re.I)


def norm(word):
    return unicodedata.normalize("NFKD", word.lower()).encode("ascii", "ignore").decode().strip(".,!?;:…\"'()- ")


def is_draco(word, strict=True):
    """"Draco" as Whisper writes it (Draco, Drako, Dracu, Daco, Darco...). Strict mode
    needs a leading d, so fraco/braço/traço/claro don't count."""
    w = norm(word)
    if not w or (strict and not w.startswith("d")):
        return False
    return difflib.SequenceMatcher(None, w, "draco").ratio() >= 0.75


def made_up(seg):
    """A segment Whisper most likely invented (silence, noise, repetition loop)."""
    if seg.get("no_speech_prob", 0) > 0.6 and seg.get("avg_logprob", 0) < -0.5:
        return True
    if seg.get("compression_ratio", 0) > 2.4:
        return True
    return seg.get("no_speech_prob", 0) > 0.2 and HALLUCINATIONS.match(seg.get("text", "").strip()) is not None


def says_draco(data):
    """The trigger clip's transcript has "Draco" (in a segment Whisper didn't invent)."""
    segs = data.get("segments") or [{"text": data.get("text", "")}]
    return any(is_draco(w) for s in segs if not made_up(s) for w in s.get("text", "").split())


def from_groq(data, wake, trigger=None):
    segs = data.get("segments") or []
    bad = [(s["start"], s["end"]) for s in segs if made_up(s)]
    words = data.get("words")
    if words is None:  # no word timestamps: fall back to the text
        text = " ".join(s["text"].strip() for s in segs if not made_up(s)) if segs else data.get("text", "")
        if wake is not None and trigger is not None and says_draco(trigger) and not any(is_draco(w) for w in text.split()[:8]):
            return text
        return from_text(text, wake, strict=True)
    words = [w for w in words if not any(a - 0.05 <= w["start"] and w["end"] <= b + 0.05 for a, b in bad)]
    if wake is not None:
        i = next((i for i, w in enumerate(words) if w["start"] <= wake + WAKE_SLACK and is_draco(w["word"])), None)
        if i is not None:
            words = words[i + 1:]
        elif trigger is not None and says_draco(trigger):
            words = [w for w in words if w["end"] > wake + 0.1]
        else:
            return None
    return " ".join(w["word"].strip() for w in words)


def from_text(text, wake, strict=False):
    text = text.strip()
    if HALLUCINATIONS.match(text):
        return "" if wake is None else None
    if wake is None:
        return text
    words = text.split()
    # No timestamps: "Draco" must be among the first words (before it: someone else, cut off).
    i = next((i for i, w in enumerate(words[:8]) if is_draco(w, strict)), None)
    if i is None:
        # Local Whisper often mangles the name ("Drag", "Dragou"); the detector and its
        # verifier already agreed, so only refuse when the text clearly starts elsewhere.
        if strict or not words:
            return None
        i = 0 if norm(words[0]).startswith(("dr", "da")) else -1
    return " ".join(words[i + 1:])


def clean(text):
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"^[,.;:!?…\- ]+", "", text).strip()


def main():
    args = sys.argv[1:]
    wake = trigger = None
    if "--gatilho" in args:
        k = args.index("--gatilho")
        try:
            with open(args[k + 1]) as f:
                trigger = json.load(f)
        except (OSError, ValueError):
            pass
        del args[k:k + 2]
    if "--wake" in args:
        k = args.index("--wake")
        wake = float(args[k + 1])
        del args[k:k + 2]
    mode, src = args[0], args[1]
    if mode == "gatilho":
        with open(src) as f:
            sys.exit(0 if says_draco(json.load(f)) else 2)
    if mode == "groq":
        with open(src) as f:
            text = from_groq(json.load(f), wake, trigger)
    else:
        text = from_text(src, wake)
    if text is None:
        sys.exit(2)
    text = clean(text)
    print(text)
    sys.exit(3 if wake is not None and len(re.sub(r"\W", "", text)) < 2 else 0)


if __name__ == "__main__":
    main()
