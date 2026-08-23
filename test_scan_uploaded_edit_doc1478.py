import urllib.request
import json
import uuid

API_BASE = "http://127.0.0.1:5000"

def test_scan():
    # Login as admin
    import http.cookiejar
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    login_data = json.dumps({"username": "admin", "password": "Admin@123"}).encode("utf-8")
    req = urllib.request.Request(
        f"{API_BASE}/api/auth/login",
        data=login_data,
        headers={"Content-Type": "application/json"}
    )
    with opener.open(req) as resp:
        print("Login successful:", resp.status)

    # Upload DOC-1478.jpg
    with open("backend/uploads/DOC-1478.jpg", "rb") as f:
        file_bytes = f.read()

    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="document"; filename="edited_doc.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        f"{API_BASE}/api/scan",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        }
    )

    with opener.open(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    print("\n=== SCAN RESULT FOR DOC-1478 (Edited Photo) ===")
    print("Doc Code:", data.get("doc_code"))
    print("Risk Score:", data.get("risk", {}).get("score"))
    print("Risk Level:", data.get("risk", {}).get("level"))
    print("Recommendation:", data.get("risk", {}).get("recommendation"))
    print("Tampering Status:", data.get("analysis", {}).get("tampering"))
    print("OCR Status:", data.get("analysis", {}).get("ocr"))
    print("Extracted Info:", data.get("extracted"))
    print("Evidence Regions:", len(data.get("evidence", [])))
    for r in data.get("evidence", []):
        print("  -", r)

    assert data.get("risk", {}).get("score") >= 75
    assert data.get("risk", {}).get("level") == "High Risk"
    assert data.get("analysis", {}).get("tampering", {}).get("status") == "ALERT"
    assert len(data.get("evidence", [])) > 0
    print("\n[SUCCESS] Text edited document correctly detected as TAMPERED & REJECTED!")

if __name__ == "__main__":
    test_scan()
