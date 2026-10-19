import re
from datetime import date

_WEIGHTS = [7, 3, 1]
_CHAR_VALUES = {c: i for i, c in enumerate("0123456789")}
_CHAR_VALUES.update({c: i + 10 for i, c in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")})
_CHAR_VALUES["<"] = 0
_DIGIT_TO_LETTER = str.maketrans("0125678", "OIZSGTB")

def _check_digit(data: str) -> int:
    total = 0
    for i, ch in enumerate(data):
        val = _CHAR_VALUES.get(ch, 0)
        total += val * _WEIGHTS[i % 3]
    return total % 10

def extract_mrz_lines(raw_text: str):
    candidates = []
    for line in raw_text.splitlines():
        cleaned = re.sub(r"[^A-Z0-9<]", "", line.strip().upper().replace(" ", ""))
        if len(cleaned) >= 30 and cleaned.count("<") >= 2:
            candidates.append(cleaned)
    return candidates[-2:] if len(candidates) >= 2 else candidates

def parse_td3(line1: str, line2: str) -> dict:
    result = {"valid_format": False, "checksum_valid": False, "fields": {}, "errors": []}
    line1 = line1.ljust(44, "<")[:44]
    line2 = line2.ljust(44, "<")[:44]

    if not (line1.startswith("P<") or line1.startswith("P")):
        result["errors"].append("Line 1 does not start with document type 'P'")

    try:
        names_part = line1[5:].split("<<", 1)
        surname = names_part[0].replace("<", " ").strip()
        given = names_part[1].replace("<", " ").strip() if len(names_part) > 1 else ""

        passport_no = line2[0:9].replace("<", "")
        passport_no_check = line2[9]
        nationality = line2[10:13].translate(_DIGIT_TO_LETTER)  # alpha-only field: undo OCR digit confusions
        dob = line2[13:19]
        dob_check = line2[19]
        sex = line2[20]
        expiry = line2[21:27]
        expiry_check = line2[27]

        result["fields"] = {
            "surname": surname, "given_names": given, "passport_number": passport_no,
            "nationality": nationality, "date_of_birth": _fmt_date(dob, is_expiry=False),
            "sex": {"M": "MALE", "F": "FEMALE"}.get(sex, "UNSPECIFIED"),
            "date_of_expiry": _fmt_date(expiry, is_expiry=True),
        }

        # ICAO 9303 TD3 has five check digits: document number, DOB, expiry, optional data and the composite.
        checks = {
            "passport_number": (line2[0:9], passport_no_check),
            "date_of_birth": (dob, dob_check),
            "date_of_expiry": (expiry, expiry_check),
            "personal_number": (line2[28:42], line2[42]),
            "composite": (line2[0:10] + line2[13:20] + line2[21:43], line2[43]),
        }
        all_ok = True
        for label, (data, printed) in checks.items():
            if label == "personal_number" and printed == "<" and set(data) == {"<"}:
                continue  # empty optional data may carry a filler check digit
            if not printed.isdigit() or _check_digit(data) != int(printed):
                all_ok = False
                result["errors"].append(f"{label} checksum mismatch")

        result["checksum_valid"] = all_ok
        result["valid_format"] = True
    except Exception as exc:
        result["errors"].append(f"MRZ parse failure: {exc}")

    return result

def _fmt_date(yymmdd: str, is_expiry: bool = False) -> str:
    if len(yymmdd) != 6 or not yymmdd.isdigit():
        return "UNKNOWN"
    yy, mm, dd = yymmdd[0:2], yymmdd[2:4], yymmdd[4:6]
    # Expiry dates are always in the future century; a birth year can't be later than this year.
    century = "20" if is_expiry or int(yy) <= date.today().year % 100 else "19"
    return f"{dd}/{mm}/{century}{yy}"
