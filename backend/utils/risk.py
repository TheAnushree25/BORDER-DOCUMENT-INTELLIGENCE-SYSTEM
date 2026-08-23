WEIGHTS = {
    "tampering": 65,
    "face_mismatch": 30,
    "mrz_mismatch": 20,
    "expiry_issue": 10,
    "database_no_match": 10,
}

def compute_risk(doc_type: str, mrz_result: dict, tamper_result: dict, face_result: dict | None, expiry_flag: bool, db_match: bool):
    factors = {}
    score = 0

    if tamper_result.get("tampering_detected", False):
        factors["Tampering Signature Detected"] = WEIGHTS["tampering"]
        score += WEIGHTS["tampering"]
    else:
        factors["Tampering Signature Detected"] = 0

    face_mismatch_detected = False
    if face_result and face_result.get("compared", False):
        if not face_result.get("match", True):
            factors["Biometric Face Mismatch"] = WEIGHTS["face_mismatch"]
            score += WEIGHTS["face_mismatch"]
            face_mismatch_detected = True
        else:
            factors["Biometric Face Mismatch"] = 0
    else:
        factors["Biometric Verification"] = 0

    if doc_type in ["Passport", "Travel Document"]:
        if not mrz_result.get("checksum_valid", False):
            factors["MRZ Checksum / Format Mismatch"] = WEIGHTS["mrz_mismatch"]
            score += WEIGHTS["mrz_mismatch"]
        else:
            factors["MRZ Checksum / Format Mismatch"] = 0
    else:
        factors["MRZ Validation"] = 0

    if expiry_flag:
        factors["Document Expired"] = WEIGHTS["expiry_issue"]
        score += WEIGHTS["expiry_issue"]
    else:
        factors["Document Expired"] = 0

    if not db_match:
        factors["Database Record Mismatch"] = WEIGHTS["database_no_match"]
        score += WEIGHTS["database_no_match"]
    else:
        factors["Database Record Mismatch"] = 0

    score = min(100, score)

    if score >= 60 or tamper_result.get("tampering_detected", False):
        level = "High Risk"
        recommendation = "REJECT / REFER FOR FORENSIC INVESTIGATION"
    elif face_mismatch_detected or score >= 30:
        level = "Medium Risk" if score < 60 else "High Risk"
        recommendation = "REFER FOR MANUAL OFFICER VERIFICATION & PHYSICAL INSPECTION"
    else:
        level = "Low Risk"
        recommendation = "Cleared - Routine Processing"

    return {"score": score, "level": level, "recommendation": recommendation, "factors": factors}
