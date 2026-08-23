import urllib.request
import urllib.parse
import json
import os
import mimetypes

BASE_URL = "http://localhost:5000"

def post_multipart(url, fields, files, opener):
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = bytearray()

    for k, v in fields.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode("utf-8"))
        body.extend(f"{v}\r\n".encode("utf-8"))

    for k, filepath in files.items():
        filename = os.path.basename(filepath)
        mime = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{k}"; filename="{filename}"\r\n'.encode("utf-8"))
        body.extend(f"Content-Type: {mime}\r\n\r\n".encode("utf-8"))
        with open(filepath, "rb") as f:
            body.extend(f.read())
        body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    res = opener.open(req)
    return json.loads(res.read().decode("utf-8"))

def test_all():
    print("========================================")
    print("TESTING MULTI-DOCUMENT SCAN PIPELINE (PAN, AADHAAR, PASSPORT)")
    print("========================================")

    # 1. Login as Admin
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    login_data = json.dumps({"username": "admin", "password": "Admin@123"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=login_data, headers={"Content-Type": "application/json"})
    opener.open(req)
    print("[OK] 1. Admin login successful")

    # 2. TEST 1: PAN Card
    pan_path = os.path.join(os.path.dirname(__file__), "test_samples", "sample_pancard.jpg")
    print("\n--- TEST 1: PAN Card Upload ---")
    resp_pan = post_multipart(f"{BASE_URL}/api/scan", {}, {"document": pan_path}, opener)
    
    print("Detected Document Type:", resp_pan["document_type"])
    print("Extracted Fields:", json.dumps(resp_pan["extracted"], indent=2))
    print("OCR Status:", resp_pan["analysis"]["ocr"]["status"], f"({resp_pan['analysis']['ocr']['detail']})")
    print("MRZ Analysis Status:", resp_pan["analysis"]["mrz"]["status"], f"({resp_pan['analysis']['mrz']['detail']})")
    print("Document Validation:", resp_pan["analysis"]["document_validation"]["status"])
    print("Risk Score & Level:", resp_pan["risk"]["score"], f"({resp_pan['risk']['level']})")

    assert resp_pan["document_type"] == "PAN Card", f"Expected PAN Card, got {resp_pan['document_type']}"
    assert resp_pan["analysis"]["mrz"]["status"] == "N/A", "MRZ must be N/A for PAN Card"
    assert resp_pan["analysis"]["document_validation"]["status"] == "VALID", "PAN validation should be VALID"
    assert resp_pan["extracted"].get("PAN Number") == "ABCDE1234F", f"PAN number mismatch: {resp_pan['extracted'].get('PAN Number')}"
    assert resp_pan["extracted"].get("Full Name") == "UJJWAL GOND", f"Name mismatch: {resp_pan['extracted'].get('Full Name')}"
    assert resp_pan["extracted"].get("Father's Name") == "RAMESH GOND", f"Father name mismatch: {resp_pan['extracted'].get('Father\'s Name')}"
    assert resp_pan["extracted"].get("Date of Birth") == "02/02/2006", f"DOB mismatch: {resp_pan['extracted'].get('Date of Birth')}"
    assert "Passport No." not in resp_pan["extracted"], "Passport No. must NOT be in PAN extracted fields"
    print("[OK] TEST 1: PAN Card verified successfully!")

    # 3. TEST 2: Aadhaar Card
    aadhaar_path = os.path.join(os.path.dirname(__file__), "test_samples", "sample_aadhaar.jpg")
    print("\n--- TEST 2: Aadhaar Card Upload ---")
    resp_aadhaar = post_multipart(f"{BASE_URL}/api/scan", {}, {"document": aadhaar_path}, opener)
    
    print("Detected Document Type:", resp_aadhaar["document_type"])
    print("Extracted Fields:", json.dumps(resp_aadhaar["extracted"], indent=2))
    print("OCR Status:", resp_aadhaar["analysis"]["ocr"]["status"], f"({resp_aadhaar['analysis']['ocr']['detail']})")
    print("MRZ Analysis Status:", resp_aadhaar["analysis"]["mrz"]["status"])
    print("Document Validation:", resp_aadhaar["analysis"]["document_validation"]["status"])

    assert resp_aadhaar["document_type"] == "Aadhaar Card", f"Expected Aadhaar Card, got {resp_aadhaar['document_type']}"
    assert resp_aadhaar["analysis"]["mrz"]["status"] == "N/A", "MRZ must be N/A for Aadhaar"
    assert resp_aadhaar["analysis"]["document_validation"]["status"] == "VALID", "Aadhaar validation should be VALID"
    assert resp_aadhaar["extracted"].get("Aadhaar Number") == "XXXX XXXX 7245", f"Masked Aadhaar number mismatch: {resp_aadhaar['extracted'].get('Aadhaar Number')}"
    assert (resp_aadhaar["extracted"].get("Full Name") or "").upper() == "UJJWAL GOND", f"Name mismatch: {resp_aadhaar['extracted'].get('Full Name')}"
    assert resp_aadhaar["extracted"].get("Date of Birth") == "02/02/2006", f"DOB mismatch: {resp_aadhaar['extracted'].get('Date of Birth')}"
    assert resp_aadhaar["extracted"].get("Gender") == "MALE", f"Gender mismatch: {resp_aadhaar['extracted'].get('Gender')}"
    assert "Passport No." not in resp_aadhaar["extracted"], "Passport No. must NOT be in Aadhaar extracted fields"
    print("[OK] TEST 2: Aadhaar Card verified successfully!")

    # 4. TEST 3: Passport
    passport_path = os.path.join(os.path.dirname(__file__), "test_samples", "sample_passport.jpg")
    print("\n--- TEST 3: Passport Upload ---")
    resp_passport = post_multipart(f"{BASE_URL}/api/scan", {}, {"document": passport_path}, opener)
    
    print("Detected Document Type:", resp_passport["document_type"])
    print("Extracted Fields:", json.dumps(resp_passport["extracted"], indent=2))
    print("MRZ Analysis Status:", resp_passport["analysis"]["mrz"]["status"], f"({resp_passport['analysis']['mrz']['detail']})")

    assert resp_passport["document_type"] == "Passport", f"Expected Passport, got {resp_passport['document_type']}"
    assert resp_passport["analysis"]["mrz"]["status"] in ["VALID", "ALERT"], "MRZ must be evaluated for Passport"
    assert resp_passport["extracted"].get("Passport No.") == "R1234567"
    assert resp_passport["extracted"].get("Full Name") == "ABHISHEK YADAV"
    print("[OK] TEST 3: Passport verified successfully!")

    # 5. TEST 4: Unreadable/Unknown image
    unreadable_path = os.path.join(os.path.dirname(__file__), "test_samples", "sample_unreadable.jpg")
    print("\n--- TEST 4: Unreadable Document Upload ---")
    resp_unreadable = post_multipart(f"{BASE_URL}/api/scan", {}, {"document": unreadable_path}, opener)

    print("Detected Document Type:", resp_unreadable["document_type"])
    print("OCR Analysis Status:", resp_unreadable["analysis"]["ocr"]["status"])
    print("Document Validation Status:", resp_unreadable["analysis"]["document_validation"]["status"])
    assert resp_unreadable["document_type"] == "Unknown"
    assert resp_unreadable["analysis"]["ocr"]["status"] == "ALERT"
    print("[OK] TEST 4: Unreadable document handled gracefully!")

    # 6. TEST 5: Admin OCR Debug Endpoint
    print("\n--- TEST 5: Admin OCR Debug Endpoint ---")
    req = urllib.request.Request(f"{BASE_URL}/api/debug/last-ocr")
    res = opener.open(req)
    debug_info = json.loads(res.read().decode("utf-8"))
    print("Last OCR Debug output:", json.dumps(debug_info, indent=2))
    assert "raw_ocr" in debug_info, "Debug info must contain raw_ocr"
    print("[OK] TEST 5: Admin OCR Debug endpoint verified!")

    print("\n========================================")
    print("ALL 5 END-TO-END MULTI-DOCUMENT TESTS PASSED WITH 100% SUCCESS!")
    print("========================================")

if __name__ == "__main__":
    test_all()
