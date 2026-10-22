import re

PAN_REGEX = re.compile(r"\b([A-Z]{5}[0-9]{4}[A-Z])\b")
AADHAAR_REGEX = re.compile(r"\b(\d{4})\s*(\d{4})\s*(\d{4})\b")
DATE_PATTERN = re.compile(r"(0?[1-9]|[12][0-9]|3[01])[\/\-\.\s:](0?[1-9]|1[0-2])[\/\-\.\s:](19\d{2}|20\d{2})")

IGNORE_TERMS = {
    "GOVERNMENT", "INDIA", "BHARAT", "AUTHORITY", "UIDAI", "ENROLMENT", 
    "MALE", "FEMALE", "TRANSGENDER", "AADHAAR", "AADHAR", "FATHER", "HUSBAND", 
    "HELP", "DATE", "BIRTH", "PROOF", "IDENTITY", "ISSUED", "ISSUE", "GOVT", 
    "CARD", "INCOME", "TAX", "DEPARTMENT", "PERMANENT", "ACCOUNT", "NUMBER",
    "DOWNLOAD", "VID", "MERA", "PEHCHAN", "ADDRESS", "AND", "SIGNATURE", "MALE/FEMALE",
    "FT", "SNAME", "FATHERNAME", "FATHERS", "INCOMETAX", "OFINDLA", "OFINDIA",
    "CITIZENSHIP", "VERIFICATION", "SCANNING", "OFFLINE", "ONLINE", "AUTHENTICATION",
    "IS", "OF", "NOT", "DISCLAIMER", "CODE", "XML", "USED", "WITH", "LSSUED", "NAME"
}

def clean_ocr_lines(raw_text: str):
    # RapidOCR often drops the space between words ("RahulVerma"); split such camel-case runs back into words.
    return [re.sub(r"(?<=[a-z])(?=[A-Z])", " ", l.strip()) for l in raw_text.splitlines() if len(l.strip()) > 1]

def detect_document_type(ocr_text: str, mrz_lines: list = None) -> str:
    upper = ocr_text.upper()
    if mrz_lines and len(mrz_lines) == 2 and (mrz_lines[0].startswith("P<") or mrz_lines[0].startswith("P")):
        return "Passport"
    if "PASSPORT" in upper or ("REPUBLIC OF INDIA" in upper and "P<" in upper):
        return "Passport"
    if PAN_REGEX.search(upper.replace(" ", "")) or "INCOME TAX" in upper or "INCOMETAX" in upper or "PERMANENT ACCOUNT" in upper:
        return "PAN Card"
    if AADHAAR_REGEX.search(ocr_text) or any(k in upper for k in ["UIDAI", "AADHAAR", "AADHAR", "UNIQUE IDENTIFICATION"]):
        return "Aadhaar Card"
    return "ID Card" if len(ocr_text.strip()) > 20 else "Unknown"

def extract_aadhaar_fields(ocr_text: str) -> dict:
    lines = clean_ocr_lines(ocr_text)
    upper = ocr_text.upper()
    fields = {"Document Type": "Aadhaar Card"}

    # 1. 12-Digit Masked Aadhaar Number
    a_m = AADHAAR_REGEX.search(ocr_text)
    if a_m:
        digs = f"{a_m.group(1)}{a_m.group(2)}{a_m.group(3)}"
        fields["Aadhaar Number"] = f"XXXX XXXX {digs[-4:]}"
    else:
        dig_only = re.findall(r"\d{12}", ocr_text.replace(" ", ""))
        if dig_only:
            fields["Aadhaar Number"] = f"XXXX XXXX {dig_only[0][-4:]}"
        else:
            fields["Aadhaar Number"] = "UNKNOWN"

    # 2. Date of Birth (Prioritize line with DOB / जन्म तिथि / Birth)
    dob_val, dob_idx = None, -1
    
    # Priority Pass 1: Explicit DOB keyword line
    for idx, line in enumerate(lines):
        u = line.upper()
        if any(k in u for k in ["DOB", "BIRTH", "जन्म"]):
            m = DATE_PATTERN.search(line)
            if m:
                dob_val = f"{m.group(1).zfill(2)}/{m.group(2).zfill(2)}/{m.group(3)}"
                dob_idx = idx
                break

    # Priority Pass 2: Any valid date that is NOT an Issue or Download date
    if not dob_val:
        for idx, line in enumerate(lines):
            u = line.upper().replace("LSSUED", "ISSUED").replace("1SSUED", "ISSUED")
            if any(k in u for k in ["ISSUE", "DOWNLOAD", "CITIZENSHIP", "PROOF", "AUTHENTICATION"]):
                continue
            m = DATE_PATTERN.search(line)
            if m:
                dob_val = f"{m.group(1).zfill(2)}/{m.group(2).zfill(2)}/{m.group(3)}"
                dob_idx = idx
                break

    fields["Date of Birth"] = dob_val if dob_val else "UNKNOWN"

    # 3. Gender
    if "FEMALE" in upper or "महिला" in ocr_text:
        fields["Gender"] = "FEMALE"
    elif "MALE" in upper or "पुरुष" in ocr_text or "/MALE" in upper.replace(" ", ""):
        fields["Gender"] = "MALE"
    else:
        fields["Gender"] = "UNKNOWN"

    # 4. Full Name Extraction (Line immediately preceding DOB, ignoring headers/disclaimers)
    name_val = None
    if dob_idx > 0:
        for offset in range(1, min(4, dob_idx + 1)):
            cand = lines[dob_idx - offset].strip()
            u_cand = cand.upper()
            if any(k in u_cand for k in ["GOVERNMENT", "INDIA", "AADHAAR", "PROOF", "CITIZENSHIP", "DOWNLOAD", "ISSUE", "IDENTITY", "LSSUED"]):
                continue
            words = [w for w in re.findall(r"[A-Za-z]+", cand) if w.upper() not in IGNORE_TERMS and len(w) >= 2]
            if len(words) >= 2:
                name_val = " ".join(words).title()
                break

    if not name_val:
        for line in lines:
            u_l = line.upper()
            if any(k in u_l for k in ["GOVERNMENT", "INDIA", "AADHAAR", "PROOF", "CITIZENSHIP", "DOWNLOAD", "ISSUE", "HELP", "VID", "IDENTITY", "LSSUED"]):
                continue
            words = [w for w in re.findall(r"[A-Za-z]+", line) if w.upper() not in IGNORE_TERMS and len(w) >= 2]
            if len(words) >= 2:
                name_val = " ".join(words).title()
                break

    fields["Full Name"] = name_val if name_val else "UNREADABLE"
    fields["Address"] = "N/A"
    return fields

def extract_pan_fields(ocr_text: str) -> dict:
    lines = clean_ocr_lines(ocr_text)
    upper = ocr_text.upper()
    fields = {"Document Type": "PAN Card"}

    # 1. PAN Number
    pan_m = PAN_REGEX.search(upper.replace(" ", ""))
    fields["PAN Number"] = pan_m.group(1) if pan_m else "UNKNOWN"

    # 2. Date of Birth
    dob_m = DATE_PATTERN.search(ocr_text)
    fields["Date of Birth"] = f"{dob_m.group(1).zfill(2)}/{dob_m.group(2).zfill(2)}/{dob_m.group(3)}" if dob_m else "UNKNOWN"

    # 3. Full Name and Father's Name Parsing
    clean_lines = []
    for line in lines:
        u_line = line.upper()
        if any(k in u_line for k in ["INCOME", "TAX", "PERMANENT", "ACCOUNT", "GOVT", "INDIA", "INDLA", "SIGNATURE", "DATE", "BIRTH", "DEPARTMENT"]):
            continue
        if PAN_REGEX.search(u_line.replace(" ", "")):
            continue
        if DATE_PATTERN.search(line):
            continue
        words = [w for w in re.findall(r"[A-Za-z]+", line) if w.upper() not in IGNORE_TERMS and len(w) >= 2]
        if len(words) >= 2:
            clean_lines.append(" ".join(words).title())

    fields["Full Name"] = clean_lines[0] if len(clean_lines) >= 1 else "UNKNOWN"
    fields["Father's Name"] = clean_lines[1] if len(clean_lines) >= 2 else "NOT DETECTED"

    # Current PAN cards print "Name" / "Father's Name" labels above the values; prefer those when present.
    labelled = {}
    for label, value in zip(lines, lines[1:]):
        key = re.sub(r"[^A-Z]", "", label.upper())
        if key.endswith("NAME") and re.fullmatch(r"[A-Za-z .]{3,}", value) and not PAN_REGEX.search(value.upper()):
            labelled["Father's Name" if "FATHER" in key else "Full Name"] = value.upper().replace(".", " ").strip()
    if "Full Name" in labelled:
        name, father = labelled["Full Name"], labelled.get("Father's Name", "")
        # Words run together in capitals ("RAHULVERMA"): the surname is usually shared with the father's name.
        common = 0
        while common < min(len(name), len(father)) and name[-1 - common] == father[-1 - common]:
            common += 1
        if " " not in name and 3 <= common < len(name):
            name = f"{name[:-common]} {name[-common:]}"
            if " " not in father and common < len(father):
                father = f"{father[:-common]} {father[-common:]}"
        fields["Full Name"] = name.title()
        if father:
            fields["Father's Name"] = father.title()
    return fields

def extract_passport_fields(mrz_result: dict) -> dict:
    f = mrz_result.get("fields", {})
    return {
        "Document Type": "Passport",
        "Full Name": f"{f.get('given_names', '').upper()} {f.get('surname', '').upper()}".strip() or "UNKNOWN",
        "Passport No.": f.get("passport_number", "UNKNOWN"),
        "Nationality": f.get("nationality", "UNKNOWN"),
        "Date of Birth": f.get("date_of_birth", "UNKNOWN"),
        "Gender": f.get("sex", "UNKNOWN"),
        "Date of Expiry": f.get("date_of_expiry", "UNKNOWN"),
    }

def extract_generic_fields(ocr_text: str, doc_type: str = "ID Card") -> dict:
    lines = clean_ocr_lines(ocr_text)
    fields = {"Document Type": doc_type}
    dob_m = DATE_PATTERN.search(ocr_text)
    if dob_m:
        fields["Date of Birth"] = f"{dob_m.group(1).zfill(2)}/{dob_m.group(2).zfill(2)}/{dob_m.group(3)}"
    candidates = [re.sub(r"[^a-zA-Z\s]", "", l).strip() for l in lines if len(l.split()) >= 2 and len(l) > 4]
    fields["Full Name"] = candidates[0].title() if candidates else "UNREADABLE"
    return fields
