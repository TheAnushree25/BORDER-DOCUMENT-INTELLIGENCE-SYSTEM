"""Cross-field consistency: values printed on a document that have to agree with each other.

Someone who types a new name or number over a card rarely fixes the other fields that depend on it:
- every Aadhaar number ends in a Verhoeff check digit (UIDAI), so a hand-edited number almost never validates;
- Aadhaar prints the holder's name and gender twice, in Hindi and in English, and an overwritten English name
  no longer matches the Hindi one (needs Tesseract with the Hindi language pack);
- a PAN encodes the holder type in its 4th character and, for individuals, the surname initial in its 5th;
- a passport repeats the name, number and dates in the machine readable zone.
Each check returns findings {"check", "detail", "box"}; "box" is the [x0, y0, x1, y1] OCR line it concerns, or None.
"""
import re
import unicodedata
from difflib import SequenceMatcher

# ---------------------------------------------------------------- Aadhaar: Verhoeff check digit

_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]


def verhoeff_valid(number: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(number)):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][int(ch)]]
    return c == 0


# A 4-4-4 group that is not part of a longer digit run (the 16-digit VID is printed in 4-digit groups too).
_AADHAAR_NUMBER = re.compile(r"(?<!\d)(?<!\d )(\d{4}) ?(\d{4}) ?(\d{4})(?! ?\d)")


def _aadhaar_number_line(lines, raw_text):
    """(12-digit number, its OCR line box) printed on an Aadhaar card, skipping VID and masked numbers."""
    candidates = [(ln.get("text", ""), ln.get("box")) for ln in lines] or [(t, None) for t in raw_text.splitlines()]
    for text, box in candidates:
        if "VID" in text.upper():
            continue
        m = _AADHAAR_NUMBER.search(text.strip())
        if m:
            return "".join(m.groups()), box
    return None, None


# ---------------------------------------------------------------- Aadhaar: Hindi name vs English name

_DEVANAGARI_CONSONANTS = {
    "क": "k", "ख": "k", "ग": "g", "घ": "g", "ङ": "n", "च": "c", "छ": "c", "ज": "j", "झ": "j", "ञ": "n",
    "ट": "t", "ठ": "t", "ड": "d", "ढ": "d", "ण": "n", "त": "t", "थ": "t", "द": "d", "ध": "d", "न": "n",
    "प": "p", "फ": "f", "ब": "b", "भ": "b", "म": "m", "य": "y", "र": "r", "ल": "l", "ळ": "l", "व": "v",
    "श": "s", "ष": "s", "स": "s", "ह": "", "ं": "n", "ँ": "n",
}


def _skeleton_hindi(word: str) -> str:
    """Consonant skeleton of a Devanagari word in a loose Latin phonetic alphabet (vowels dropped)."""
    # NFD splits nukta letters (ड़ "ड़" -> "ड" + nukta); ड़/ढ़ sound like "r", the others keep their base letter
    word = unicodedata.normalize("NFD", word).replace("ड़", "र").replace("ढ़", "र")
    out = [_DEVANAGARI_CONSONANTS.get(ch, "") for ch in word]
    return _collapse("".join(out))


def _skeleton_latin(word: str) -> str:
    """The same skeleton for an English spelling of an Indian name ("Abhishek" -> "bsk", like "अभिषेक")."""
    w = re.sub(r"[^a-z]", "", word.lower())
    # "ch" is held as "C" so that a lone "c" can become "k"
    for src, dst in (("ksh", "ks"), ("chh", "C"), ("ch", "C"), ("sh", "s"), ("th", "t"), ("dh", "d"), ("kh", "k"),
                     ("gh", "g"), ("jh", "j"), ("bh", "b"), ("ph", "f"), ("ck", "k"), ("x", "ks"), ("q", "k"),
                     ("c", "k"), ("w", "v"), ("z", "j"), ("C", "c")):
        w = w.replace(src, dst)
    return _collapse(re.sub(r"[aeiouh]", "", w))


def _collapse(s: str) -> str:
    return re.sub(r"(.)\1+", r"\1", s)


def names_match(hindi_name: str, english_name: str):
    """
    Compares a Devanagari name with its English spelling by consonant skeleton.
    Returns None when either side is too short to judge, else a similarity in 0-1: the better of the plain
    similarity and the share of the English skeleton found in order in the Hindi one (OCR may pick up extra marks).
    """
    h_skel = "".join(_skeleton_hindi(w) for w in re.findall(r"[\u0900-\u097F]+", hindi_name))
    e_skel = "".join(_skeleton_latin(w) for w in re.findall(r"[A-Za-z]+", english_name))
    if len(h_skel) < 2 or len(e_skel) < 2:
        return None
    sm = SequenceMatcher(None, h_skel, e_skel)
    coverage = sum(block.size for block in sm.get_matching_blocks()) / len(e_skel)
    return round(max(sm.ratio(), coverage), 2)


_HINDI_GENDER = {"पुरुष": "MALE", "महिला": "FEMALE", "ट्रांसजेंडर": "TRANSGENDER"}


def _find_line(lines, predicate):
    for ln in lines:
        if predicate(ln.get("text", "")):
            return ln
    return None


def _letters(s):
    return re.sub(r"[^A-Z]", "", str(s).upper())


def check_aadhaar(extracted, raw_text, lines, read_hindi=None):
    findings, checked = [], []

    number, box = _aadhaar_number_line(lines, raw_text)
    if number:
        checked.append("Aadhaar checksum")
        if number[0] in "01" or not verhoeff_valid(number):
            findings.append({
                "check": "Aadhaar checksum",
                "detail": f"Aadhaar number XXXX XXXX {number[-4:]} fails the UIDAI Verhoeff check digit "
                          "(number edited or misprinted)",
                "box": box,
            })

    if read_hindi is not None:
        name = extracted.get("Full Name", "")
        target = _letters(name)
        name_line = _find_line(lines, lambda t: target in _letters(t)) if len(target) >= 4 else None
        if name_line:
            x0, y0, x1, y1 = name_line["box"]
            h = y1 - y0
            # The Hindi name is printed directly above the English one, starting at the same margin.
            hindi = read_hindi([x0 - 0.3 * h, y0 - 1.6 * h, x0 + max(1.6 * (x1 - x0), 6 * h), y0 - 0.05 * h])
            similarity = names_match(hindi, name) if hindi and len(re.findall(r"[\u0900-\u097F]", hindi)) >= 3 else None
            if similarity is not None:
                checked.append("Hindi / English name")
                if similarity < 0.5:
                    findings.append({
                        "check": "Hindi / English name",
                        "detail": f"English name '{name}' does not match the Hindi name '{hindi.strip()}' printed above it "
                                  f"(similarity {int(similarity * 100)}%)",
                        "box": name_line["box"],
                    })

        gender = extracted.get("Gender", "")
        gender_line = _find_line(lines, lambda t: re.search(r"\b(FE)?MALE\b|TRANSGENDER", t.upper()) is not None)
        if gender in ("MALE", "FEMALE") and gender_line:
            hindi = read_hindi(gender_line["box"]) or ""
            hindi_gender = next((g for word, g in _HINDI_GENDER.items() if word in hindi), None)
            if hindi_gender:
                checked.append("Hindi / English gender")
                if hindi_gender != gender:
                    findings.append({
                        "check": "Hindi / English gender",
                        "detail": f"Gender reads {gender} in English but {hindi_gender} in Hindi",
                        "box": gender_line["box"],
                    })
    return findings, checked


# ---------------------------------------------------------------- PAN

_PAN = re.compile(r"([A-Z]{5}[0-9]{4}[A-Z])")
_PAN_HOLDER_TYPES = "ABCFGHJLPT"  # company, person, HUF, firm, AOP, trust, BOI, local authority, AJP, government


def _common_suffix(a, b):
    n = 0
    while n < min(len(a), len(b)) and a[-1 - n] == b[-1 - n]:
        n += 1
    return n


def check_pan(extracted, raw_text, lines):
    findings, checked = [], []
    pan = extracted.get("PAN Number", "")
    if not _PAN.fullmatch(pan or ""):
        return findings, checked
    pan_line = _find_line(lines, lambda t: pan in t.upper().replace(" ", ""))
    box = pan_line["box"] if pan_line else None

    checked.append("PAN structure")
    if pan[3] not in _PAN_HOLDER_TYPES:
        findings.append({
            "check": "PAN structure",
            "detail": f"PAN {pan} has an invalid holder-type letter '{pan[3]}' (4th character)",
            "box": box,
        })
        return findings, checked

    name = str(extracted.get("Full Name", "")).upper()
    if pan[3] != "P" or name in ("", "UNKNOWN", "UNREADABLE"):
        return findings, checked
    checked.append("PAN surname letter")
    words = re.findall(r"[A-Z]+", name)
    if len(words) == 1:
        # RapidOCR often drops the space in capitals ("RAHULVERMA"): recover the surname from the father's name.
        father = _letters(extracted.get("Father's Name", ""))
        n = _common_suffix(words[0], father)
        if 3 <= n < len(words[0]):
            words = [words[0][:-n], words[0][-n:]]
    initials = {w[0] for w in words if w}
    consistent = pan[4] in initials if len(words) > 1 else pan[4] in name
    if not consistent:
        name_line = _find_line(lines, lambda t: _letters(name) and _letters(name) in _letters(t))
        findings.append({
            "check": "PAN / name",
            "detail": f"PAN {pan} belongs to a holder whose surname starts with '{pan[4]}', "
                      f"but the card name is '{extracted.get('Full Name')}'",
            "box": (name_line or {}).get("box") or box,
        })
    return findings, checked


# ---------------------------------------------------------------- passport: visual zone vs MRZ

_LABELS = {
    "surname": re.compile(r"SURNAME"),
    "given": re.compile(r"GIVEN\s*NAME"),
    "number": re.compile(r"PASSPORT\s*NO"),
    "dob": re.compile(r"DATE\s*OF\s*BIRTH"),
}
_DATE = re.compile(r"(\d{2})[/\-. ](\d{2})[/\-. ](\d{4})")


def _value_below(lines, label_line):
    """The OCR line printed right under a field label (same left margin)."""
    x0, y0, x1, y1 = label_line["box"]
    h = y1 - y0
    best = None
    for ln in lines:
        bx0, by0, _, _ = ln["box"]
        if ln is label_line or not (y1 - 0.3 * h <= by0 <= y1 + 1.8 * h) or abs(bx0 - x0) > 1.5 * h:
            continue
        if best is None or by0 < best["box"][1]:
            best = ln
    return best


def check_passport(extracted, mrz_result, lines):
    findings, checked = [], []
    fields = mrz_result.get("fields") or {}
    if not mrz_result.get("valid_format") or not lines:
        return findings, checked
    viz = {}
    for key, pattern in _LABELS.items():
        label = _find_line(lines, lambda t, p=pattern: p.search(t.upper()) is not None)
        value = _value_below(lines, label) if label else None
        if value:
            viz[key] = value

    def compare(key, printed, expected, what):
        if not (printed and expected):
            return
        checked.append(f"Passport {what} / MRZ")
        if printed != expected and SequenceMatcher(None, printed, expected).ratio() < 0.8:  # allow a misread character
            findings.append({
                "check": f"Passport {what} / MRZ",
                "detail": f"Printed {what} '{viz[key]['text'].strip()}' does not match the machine readable zone",
                "box": viz[key]["box"],
            })

    if "surname" in viz:
        compare("surname", _letters(viz["surname"]["text"]), _letters(fields.get("surname")), "surname")
    if "given" in viz:
        compare("given", _letters(viz["given"]["text"]), _letters(fields.get("given_names")), "given name")
    if "number" in viz:
        printed = re.sub(r"[^A-Z0-9]", "", viz["number"]["text"].upper())
        compare("number", printed, re.sub(r"[^A-Z0-9]", "", str(fields.get("passport_number", ""))), "passport number")
    if "dob" in viz:
        m = _DATE.search(viz["dob"]["text"])
        if m and fields.get("date_of_birth", "UNKNOWN") != "UNKNOWN":
            compare("dob", "/".join(m.groups()), fields["date_of_birth"], "date of birth")
    return findings, checked


def run(doc_type, extracted, raw_text, lines, mrz_result=None, read_hindi=None):
    """{"findings": [...], "checked": [names of the checks that could be performed]} for one document."""
    lines = [ln for ln in (lines or []) if ln.get("box")]
    if doc_type == "Aadhaar Card":
        findings, checked = check_aadhaar(extracted, raw_text, lines, read_hindi)
    elif doc_type == "PAN Card":
        findings, checked = check_pan(extracted, raw_text, lines)
    elif doc_type == "Passport":
        findings, checked = check_passport(extracted, mrz_result or {}, lines)
    else:
        findings, checked = [], []
    return {"findings": findings, "checked": checked}
