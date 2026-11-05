"""Fuzzy matching of WhatsApp chat names read by OCR.

  wa_match.py pick <term>      stdin: OCR'd result names, one per line.
                               Prints the chat to open. Exit 4 + the candidates if ambiguous,
                               exit 5 + the names seen if nothing matches.
  wa_match.py same <expected>  stdin: OCR'd conversation header. Exit 0 if it is that chat.
"""
import difflib
import re
import sys
import unicodedata

NOISE = {"arquivada", "conversas", "contatos", "mensagens", "grupos em comum"}


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def word_ok(w, words):
    return any(x.startswith(w) or difflib.SequenceMatcher(None, w, x).ratio() >= 0.85 for x in words)


def covers(term, name):
    words = norm(name).split()
    return all(word_ok(w, words) for w in norm(term).split())


def clean_names(lines):
    out = []
    for line in lines:
        line = re.sub(r"(\.\.\.|…)\s*$", "", line.strip()).strip()
        if len(norm(line)) >= 2 and norm(line) not in NOISE and line not in out:
            out.append(line)
    return out


def pick(term, lines):
    names = clean_names(lines)
    exact = [n for n in names if norm(n) == norm(term)]
    if exact:
        return exact[0], names
    matches = [n for n in names if covers(term, n)]
    if len(matches) == 1:
        return matches[0], names
    # several hits: prefer the one that starts exactly with the term ("Meu Bem" vs "Meu Bem Mãe")
    starts = [n for n in matches if norm(n).startswith(norm(term))]
    if len(starts) == 1 and len(norm(starts[0])) - len(norm(term)) <= 2:
        return starts[0], names
    return None, matches


def same(expected, header):
    first = next((l for l in header.splitlines() if norm(l)), "")
    a, b = norm(expected), norm(first)
    if not a or not b:
        return False
    return a in b or b in a or difflib.SequenceMatcher(None, a, b).ratio() >= 0.85 or covers(expected, first)


if __name__ == "__main__":
    mode, arg = sys.argv[1], sys.argv[2]
    text = sys.stdin.read()
    if mode == "pick":
        chosen, found = pick(arg, text.splitlines())
        if chosen:
            print(chosen)
            sys.exit(0)
        print("\n".join(found or clean_names(text.splitlines())))
        sys.exit(4 if found else 5)
    if mode == "same":
        sys.exit(0 if same(arg, text) else 1)
    sys.exit(__doc__)
