# Defaults only; the live weights come from the Rule Engine (rules table) and are passed in by the API.
DEFAULT_WEIGHTS = {
    "tampering": 65,
    "text_tampering": 50,
    "face_mismatch": 30,
    "data_mismatch": 35,
    "mrz_mismatch": 20,
    "expiry_issue": 10,
    "watchlist_hit": 60,
}

def compute_risk(doc_type: str, mrz_result: dict, tamper_result: dict, face_result: dict | None, expiry_flag: bool,
                 watchlist_hit: bool, weights: dict | None = None, text_tampered: bool = False,
                 data_mismatch: bool = False):
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    factors = {}
    score = 0

    tampered = bool(tamper_result.get("tampering_detected", False))
    if tampered:
        factors["Tampering Signature Detected"] = w["tampering"]
        score += w["tampering"]
    else:
        factors["Tampering Signature Detected"] = 0

    # Text typed or pasted over the printed document (text_forensics)
    if text_tampered:
        factors["Altered / Overwritten Text"] = w["text_tampering"]
        score += w["text_tampering"]
    else:
        factors["Altered / Overwritten Text"] = 0

    face_mismatch_detected = False
    if face_result and face_result.get("compared", False):
        if not face_result.get("match", True):
            factors["Biometric Face Mismatch"] = w["face_mismatch"]
            score += w["face_mismatch"]
            face_mismatch_detected = True
        else:
            factors["Biometric Face Mismatch"] = 0
    else:
        factors["Biometric Verification"] = 0

    # Printed fields that contradict each other (field_checks)
    if data_mismatch:
        factors["Field Data Mismatch"] = w["data_mismatch"]
        score += w["data_mismatch"]
    else:
        factors["Field Data Mismatch"] = 0

    if doc_type in ["Passport", "Travel Document"]:
        if not mrz_result.get("checksum_valid", False):
            factors["MRZ Checksum / Format Mismatch"] = w["mrz_mismatch"]
            score += w["mrz_mismatch"]
        else:
            factors["MRZ Checksum / Format Mismatch"] = 0
    else:
        factors["MRZ Validation"] = 0

    if expiry_flag:
        factors["Document Expired"] = w["expiry_issue"]
        score += w["expiry_issue"]
    else:
        factors["Document Expired"] = 0

    if watchlist_hit:
        factors["Watchlist Match"] = w["watchlist_hit"]
        score += w["watchlist_hit"]
    else:
        factors["Watchlist Match"] = 0

    score = min(100, score)

    # Tampering, altered text and watchlist hits escalate on their own unless the rule is switched off (weight 0).
    text_altered = text_tampered and w["text_tampering"] > 0
    if score >= 60 or (tampered and w["tampering"] > 0) or text_altered or (watchlist_hit and w["watchlist_hit"] > 0):
        level = "High Risk"
        recommendation = "REJECT / REFER FOR FORENSIC INVESTIGATION"
        if text_altered:
            recommendation = "ALTERED DOCUMENT TEXT - REJECT / REFER FOR FORENSIC INVESTIGATION"
        if watchlist_hit:
            recommendation = "WATCHLIST MATCH - DETAIN FOR SECONDARY INSPECTION"
    elif (face_mismatch_detected and w["face_mismatch"] > 0) or (data_mismatch and w["data_mismatch"] > 0) or score >= 30:
        level = "Medium Risk"
        recommendation = "REFER FOR MANUAL OFFICER VERIFICATION & PHYSICAL INSPECTION"
    else:
        level = "Low Risk"
        recommendation = "Cleared - Routine Processing"

    return {"score": score, "level": level, "recommendation": recommendation, "factors": factors}
