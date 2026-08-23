import urllib.request
import urllib.parse
import http.cookiejar
import json
import os

API_BASE = "http://127.0.0.1:5000"

def test_scan_edited():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # 1. Login
    login_data = json.dumps({"username": "admin", "password": "Admin@123"}).encode("utf-8")
    req_login = urllib.request.Request(
        f"{API_BASE}/api/auth/login",
        data=login_data,
        headers={"Content-Type": "application/json"}
    )
    with opener.open(req_login) as resp:
        print("Login Status:", resp.status)

    files_to_test = [
        ("Clean Aadhaar", "backend/uploads/DOC-1388.jpg", False),
        ("Edited Whiteout Aadhaar", "backend/uploads/DOC-1430.jpg", True),
        ("Edited Scribble Aadhaar", "backend/uploads/DOC-1438.jpg", True),
    ]

    for label, path, should_tamper in files_to_test:
        print("\n" + "="*60)
        print(f"TESTING: {label} ({path})")
        print("="*60)
        
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        with open(path, "rb") as f:
            file_bytes = f.read()

        filename = os.path.basename(path)
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

        req_scan = urllib.request.Request(
            f"{API_BASE}/api/scan",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )

        with opener.open(req_scan) as resp:
            data = json.loads(resp.read().decode("utf-8"))

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
            assert data["risk"]["score"] >= 75, f"Expected Risk Score >= 75 for {label}, got {data['risk']['score']}"
            assert "REJECT" in data["risk"]["recommendation"], f"Expected REJECT in recommendation, got {data['risk']['recommendation']}"
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
