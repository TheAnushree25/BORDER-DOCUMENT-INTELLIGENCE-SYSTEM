# Defaults only; the live weights come from the Rule Engine (rules table) and are passed in by the API.
DEFAULT_WEIGHTS = {
    "tampering": 65,
    "face_mismatch": 30,
    "mrz_mismatch": 20,
    "expiry_issue": 10,
    "watchlist_hit": 60,
}

def compute_risk(doc_type: str, mrz_result: dict, tamper_result: dict, face_result: dict | None, expiry_flag: bool,
                 watchlist_hit: bool, weights: dict | None = None):
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    factors = {}
    score = 0

    tampered = bool(tamper_result.get("tampering_detected", False))
    if tampered:
        factors["Tampering Signature Detected"] = w["tampering"]
        score += w["tampering"]
    else:
        factors["Tampering Signature Detected"] = 0

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

    # Tampering and watchlist hits escalate on their own unless the rule is switched off (weight 0).
    if score >= 60 or (tampered and w["tampering"] > 0) or (watchlist_hit and w["watchlist_hit"] > 0):
        level = "High Risk"
        recommendation = "REJECT / REFER FOR FORENSIC INVESTIGATION"
        if watchlist_hit:
            recommendation = "WATCHLIST MATCH - DETAIN FOR SECONDARY INSPECTION"
    elif face_mismatch_detected or score >= 30:
        level = "Medium Risk"
        recommendation = "REFER FOR MANUAL OFFICER VERIFICATION & PHYSICAL INSPECTION"
    else:
        level = "Low Risk"
        recommendation = "Cleared - Routine Processing"

    return {"score": score, "level": level, "recommendation": recommendation, "factors": factors}
