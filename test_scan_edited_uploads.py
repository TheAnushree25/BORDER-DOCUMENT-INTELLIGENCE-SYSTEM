import io
import json
import os
from backend.app import app

def test_scan_edited():
    client = app.test_client()

    # 1. Login
    resp_login = client.post(
        "/api/auth/login",
        data=json.dumps({"username": "admin", "password": "Admin@123"}),
        content_type="application/json"
    )
    print("Login Status:", resp_login.status_code)

    files_to_test = [
        ("Clean Aadhaar", "backend/uploads/DOC-1388.jpg", False),
        ("Edited Whiteout Aadhaar", "backend/uploads/DOC-1430.jpg", True),
        ("Edited Scribble Aadhaar", "backend/uploads/DOC-1438.jpg", True),
    ]

    for label, path, should_tamper in files_to_test:
        print("\n" + "="*60)
        print(f"TESTING: {label} ({path})")
        print("="*60)
        
        with open(path, "rb") as f:
            file_bytes = f.read()

        filename = os.path.basename(path)
        data = {
            "document": (io.BytesIO(file_bytes), filename)
        }

        resp = client.post("/api/scan", data=data, content_type="multipart/form-data")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.data}"
        data = resp.get_json()

        print("Doc Code:", data.get("doc_code"))
        print("Risk Score:", data.get("risk", {}).get("score"), "Level:", data.get("risk", {}).get("level"))
        print("Recommendation:", data.get("risk", {}).get("recommendation"))
        print("Tampering Status:", data.get("analysis", {}).get("tampering"))
        print("OCR Status:", data.get("analysis", {}).get("ocr"))
        print("Document Validation:", data.get("analysis", {}).get("document_validation"))
        print("Extracted Info:", data.get("extracted"))

        tamper_status = data.get("analysis", {}).get("tampering", {}).get("status")
        ocr_status = data.get("analysis", {}).get("ocr", {}).get("status")
        doc_val_status = data.get("analysis", {}).get("document_validation", {}).get("status")
        extracted_status = data.get("extracted", {}).get("Document Status")

        if should_tamper:
            assert tamper_status == "ALERT", f"Expected Tamper ALERT for {label}, got {tamper_status}"
            assert ocr_status == "ALERT", f"Expected OCR ALERT for {label}, got {ocr_status}"
            assert doc_val_status == "ALERT", f"Expected Doc Validation ALERT for {label}, got {doc_val_status}"
            assert data["risk"]["score"] >= 65, f"Expected Risk Score >= 65 for {label}, got {data['risk']['score']}"
            assert "REJECT" in data["risk"]["recommendation"] or "REFER" in data["risk"]["recommendation"], f"Expected REJECT/REFER in recommendation, got {data['risk']['recommendation']}"
            assert extracted_status == "COMPROMISED / TAMPERED", f"Expected COMPROMISED / TAMPERED extracted status"
            print(f"[SUCCESS] {label} correctly OVERRIDDEN as COMPROMISED & REJECTED (Risk: {data['risk']['score']}/100)!")
        else:
            assert tamper_status == "VALID", f"Expected VALID for {label}, got {tamper_status}"
            assert ocr_status == "VALID", f"Expected OCR VALID for {label}, got {ocr_status}"
            assert data["risk"]["score"] == 0, f"Expected clean score 0, got {data['risk']['score']}"
            print(f"[SUCCESS] {label} correctly cleared as VALID!")

    print("\n" + "="*60)
    print("ALL SECURITY LOGIC OVERRIDE TESTS PASSED 100%!")
    print("="*60)

if __name__ == "__main__":
    test_scan_edited()
