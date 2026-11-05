"""Parse Portuguese time expressions into an exact datetime.

  when.py em "<duração>"   "20 minutos", "1h30", "meia hora", "uma hora e meia", "2 horas e 15 minutos"
  when.py as "<quando>"    "21:00", "21h", "21h30", "9 da noite", "8 da manhã", "meio-dia", "meia-noite",
                           "amanhã 8h", "amanhã às 7:30", "segunda 10h", "20/10 15h", "2026-10-20 15:00"
Prints "<epoch>\t<dd/mm/aaaa HH:MM>" or exits 1 with an error message.
"""
import re
import sys
import unicodedata
from datetime import datetime, timedelta

WORDS = {
    "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6, "sete": 7,
    "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14, "quatorze": 14,
    "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19, "vinte": 20,
    "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60,
}
WEEKDAYS = ["segunda", "terca", "quarta", "quinta", "sexta", "sabado", "domingo"]


def norm(s):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"(\d)\s*e\s*meia\b", r"\1:30", s)          # "8 e meia" -> 8:30
    s = re.sub(r"\b(vinte|trinta|quarenta|cinquenta) e (\w+)",
               lambda m: str(WORDS[m.group(1)] + WORDS.get(m.group(2), 0)), s)
    s = re.sub(r"\b(" + "|".join(WORDS) + r")\b", lambda m: str(WORDS[m.group(1)]), s)
    s = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", s)  # "meio-dia" -> "meio dia", keeps 2026-10-20
    return " ".join(s.split())


def duration(text):
    t = norm(text)
    if re.fullmatch(r"(daqui a |em |por )?meia hora", t):
        return timedelta(minutes=30)
    total = timedelta()
    m = re.fullmatch(r"(?:daqui a |em |por )?(\d+)\s*h(?:oras?)?\s*(?:e\s*)?(\d+)?\s*(?:m|min|minutos?)?", t)
    if m:  # "1h30", "2 horas e 15 minutos", "1 hora"
        total = timedelta(hours=int(m.group(1)), minutes=int(m.group(2) or 0))
        if re.search(r"e meia", t):
            total += timedelta(minutes=30)
        return total
    for n, unit in re.findall(r"(\d+(?:[.,]\d+)?)\s*(h|horas?|m|min|minutos?|s|seg|segundos?)\b", t):
        n = float(n.replace(",", "."))
        total += timedelta(hours=n) if unit.startswith("h") else (
            timedelta(seconds=n) if unit.startswith("s") else timedelta(minutes=n))
    if "e meia" in t and total:
        total += timedelta(minutes=30)
    if not total:
        raise ValueError(f"não entendi a duração '{text}'")
    return total


def moment(text, now):
    t = norm(text)
    t = re.sub(r"\b(as|a|para|pras?|hoje)\b", " ", t)
    day = now.date()
    explicit_day = False
    if "depois de amanha" in t:
        day += timedelta(days=2); explicit_day = True; t = t.replace("depois de amanha", " ")
    elif "amanha" in t:
        day += timedelta(days=1); explicit_day = True; t = t.replace("amanha", " ")
    for i, wd in enumerate(WEEKDAYS):
        if re.search(rf"\b{wd}", t):
            ahead = (i - now.weekday()) % 7 or 7
            day = now.date() + timedelta(days=ahead); explicit_day = True
            t = re.sub(rf"\b{wd}\w*( feira)?", " ", t)
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", t) or None
    if m:
        day = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date(); explicit_day = True
        t = t.replace(m.group(0), " ")
    m = re.search(r"\b(?:dia )?(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b", t)
    if m:
        year = int(m.group(3)) if m.group(3) else now.year
        year += 2000 if year < 100 else 0
        day = datetime(year, int(m.group(2)), int(m.group(1))).date(); explicit_day = True
        t = t.replace(m.group(0), " ")

    if "meio dia" in t:
        hour, minute = 12, 0
    elif "meia noite" in t:
        hour, minute = 0, 0
        if not explicit_day:
            day += timedelta(days=1); explicit_day = True
    else:
        m = re.search(r"\b(\d{1,2})(?:\s*(?::|h)\s*(\d{2})?)?(?:\s*(?:horas?|hs?))?\b", t)
        if not m:
            raise ValueError(f"não entendi o horário '{text}'")
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        if re.search(r"\b(noite|tarde)\b", t) and hour < 12:
            hour += 12
        if "madrugada" in t and hour == 12:
            hour = 0
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError(f"horário inválido em '{text}'")
    when = datetime.combine(day, datetime.min.time()).replace(hour=hour, minute=minute)
    if when <= now and not explicit_day:
        # "às 9" said at 10:00 means 21:00 if that's still today, else tomorrow
        ambiguous = hour < 12 and not re.search(r"\b(manha|madrugada)\b", t) and ":" not in text and "h" not in t
        later = when + timedelta(hours=12)
        when = later if ambiguous and later > now else when + timedelta(days=1)
    if when <= now:
        raise ValueError(f"'{text}' já passou")
    return when


if __name__ == "__main__":
    try:
        if sys.argv[1] == "em":
            target = datetime.now() + duration(" ".join(sys.argv[2:]))
        else:
            target = moment(" ".join(sys.argv[2:]), datetime.now())
    except (ValueError, IndexError) as e:
        print(e, file=sys.stderr)
        sys.exit(1)
    print(f"{int(target.timestamp())}\t{target:%d/%m/%Y %H:%M}")
