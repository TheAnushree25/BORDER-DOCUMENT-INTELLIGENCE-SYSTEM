import os
import cv2
import numpy as np
from PIL import Image, ImageDraw
from backend.utils import tamper, face_match, document_extractor

def test_tampering_detection():
    print("========================================")
    print("1. TESTING MULTI-SIGNAL TAMPERING DETECTOR")
    print("========================================")
    upload_dir = "backend/uploads"
    clean_path = os.path.join(upload_dir, "DOC-1388.jpg")
    edited_whiteout = os.path.join(upload_dir, "DOC-1430.jpg")
    edited_scribble = os.path.join(upload_dir, "DOC-1438.jpg")

    # 1. Real Clean Document
    clean_img = Image.open(clean_path)
    clean_res = tamper.error_level_analysis(clean_img)
    print(f"Clean Document ({os.path.basename(clean_path)}): Score={clean_res['tamper_score']}, Detected={clean_res['tampering_detected']}")
    assert clean_res["tampering_detected"] is False
    assert clean_res["tamper_score"] < 30

    # 2. Real Edited Document with Whiteout Alteration
    whiteout_img = Image.open(edited_whiteout)
    w_res = tamper.error_level_analysis(whiteout_img)
    print(f"Edited Whiteout Document ({os.path.basename(edited_whiteout)}): Score={w_res['tamper_score']}, Detected={w_res['tampering_detected']}, Detail={w_res['detail']}")
    assert w_res["tampering_detected"] is True
    assert w_res["tamper_score"] >= 60

    # 3. Real Edited Document with Sharp Overlay/Scribble
    scribble_img = Image.open(edited_scribble)
    s_res = tamper.error_level_analysis(scribble_img)
    print(f"Edited Scribble Document ({os.path.basename(edited_scribble)}): Score={s_res['tamper_score']}, Detected={s_res['tampering_detected']}, Detail={s_res['detail']}")
    assert s_res["tampering_detected"] is True
    assert s_res["tamper_score"] >= 35

    print("[OK] Multi-signal tampering detector correctly flags both whiteout and digital scribbles while clearing genuine IDs!")

def test_biometric_face_matching():
    print("\n========================================")
    print("2. TESTING BIOMETRIC FACE MATCHING")
    print("========================================")
    upload_dir = "backend/uploads"
    pan_path = os.path.join(upload_dir, "DOC-1386.jpg")
    aadh_ujjwal_path = os.path.join(upload_dir, "DOC-1388.jpg")
    aadh_anurag_path = os.path.join(upload_dir, "DOC-1390.jpg")

    if os.path.exists(pan_path) and os.path.exists(aadh_ujjwal_path):
        pan_img = Image.open(pan_path)
        aadh_ujjwal_img = Image.open(aadh_ujjwal_path)
        aadh_anurag_img = Image.open(aadh_anurag_path)

        res_same = face_match.compare_faces(pan_img, aadh_ujjwal_img)
        print("Same Person (Ujjwal PAN vs Ujjwal Aadhaar):", res_same)
        assert res_same["similarity"] >= 60 and res_same["match"] is True

        res_diff = face_match.compare_faces(pan_img, aadh_anurag_img)
        print("Different Person (Ujjwal PAN vs Anurag Aadhaar):", res_diff)
        assert res_diff["match"] is False and res_diff["similarity"] < 50
        print("[OK] Face matching accurately differentiates genuine match from impostors!")

def test_aadhaar_extraction():
    print("\n========================================")
    print("3. TESTING ROBUST AADHAAR FIELD EXTRACTION")
    print("========================================")
    raw_ocr = """Government of India
AadhaarNo.lssued:19/01/2016
Ujwal Gond
A/DOB:02/02/2006
/Male
Aadhaaris proof ofidentity,not of citizenship
or date of birth.It should be used with verification (online
authentication or scanning ofQR code/offlineXML)
503186657245"""

    fields = document_extractor.extract_aadhaar_fields(raw_ocr)
    print("Extracted Aadhaar Fields:", fields)
    assert fields["Full Name"].upper() == "UJWAL GOND"
    assert fields["Date of Birth"] == "02/02/2006" # Issue date 19/01/2016 successfully ignored
    assert fields["Gender"] == "MALE"
    assert fields["Aadhaar Number"] == "XXXX XXXX 7245"
    print("[OK] Aadhaar fields parsed 100% accurately without noise words or issue date confusion!")

if __name__ == "__main__":
    test_tampering_detection()
    test_biometric_face_matching()
    test_aadhaar_extraction()
    print("\n========================================")
    print("ALL FORENSIC & BIOMETRIC SUITE TESTS PASSED 100%!")
    print("========================================")
