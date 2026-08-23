import urllib.request
import urllib.parse
import json
import io
from PIL import Image, ImageDraw

BASE_URL = "http://localhost:5000"

def make_doc_with_face():
    img = Image.new("RGB", (600, 400), color=(250, 250, 252))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 20, 580, 380], outline=(100, 100, 100), width=2)
    # Draw simple face portrait
    draw.ellipse([40, 80, 180, 240], fill=(240, 210, 180), outline=(50, 50, 50), width=2)
    draw.ellipse([70, 120, 95, 145], fill=(50, 50, 50))
    draw.ellipse([125, 120, 150, 145], fill=(50, 50, 50))
    draw.arc([80, 160, 140, 200], start=0, end=180, fill=(150, 50, 50), width=3)
    # Add Aadhaar text
    draw.text((220, 80), "Government of India", fill=(0, 0, 0))
    draw.text((220, 120), "Name: UJJWAL GOND", fill=(0, 0, 0))
    draw.text((220, 160), "DOB: 02/02/2006", fill=(0, 0, 0))
    draw.text((220, 200), "Gender: MALE", fill=(0, 0, 0))
    draw.text((220, 240), "5489 7621 7245", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def make_selfie():
    img = Image.new("RGB", (300, 300), color=(220, 230, 240))
    draw = ImageDraw.Draw(img)
    # Draw selfie face
    draw.ellipse([60, 50, 240, 250], fill=(240, 210, 180), outline=(50, 50, 50), width=2)
    draw.ellipse([100, 110, 130, 140], fill=(50, 50, 50))
    draw.ellipse([170, 110, 200, 140], fill=(50, 50, 50))
    draw.arc([110, 160, 190, 210], start=0, end=180, fill=(150, 50, 50), width=3)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()

def post_multipart(url, files, opener):
    boundary = "----WebKitFormBoundaryBorderIntel7MA4YWxkTrZu0gW"
    body = bytearray()
    for field_name, (filename, file_bytes) in files.items():
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'.encode("utf-8"))
        body.extend(b"Content-Type: image/jpeg\r\n\r\n")
        body.extend(file_bytes)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    res = opener.open(req)
    return json.loads(res.read().decode("utf-8"))

def test_live_photo():
    cookie_jar = urllib.request.HTTPCookieProcessor()
    opener = urllib.request.build_opener(cookie_jar)

    # Login
    login_data = json.dumps({"username": "admin", "password": "Admin@123"}).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=login_data, headers={"Content-Type": "application/json"}, method="POST")
    opener.open(req)
    print("[OK] Logged in as Admin")

    doc_bytes = make_doc_with_face()
    selfie_bytes = make_selfie()

    # 1. Test Document + Live Photo
    print("\n--- Test Document with Live Selfie Photo ---")
    res = post_multipart(
        f"{BASE_URL}/api/scan",
        {
            "document": ("aadhaar_doc.jpg", doc_bytes),
            "live_face": ("live_selfie.jpg", selfie_bytes),
        },
        opener,
    )
    face_check = res.get("analysis", {}).get("face_verification", {})
    print(f"Face Verification Status: {face_check.get('status')}")
    print(f"Detail: {face_check.get('detail')}")
    print(f"Extracted Document Type: {res.get('document_type')}")
    print(f"Full Name: {res.get('extracted', {}).get('Full Name')}")
    print(f"Risk Score: {res.get('risk', {}).get('score')}")
    assert face_check.get("status") in ["MATCH", "ALERT", "VALID"], "Face verification must return valid status"
    print("[OK] Live Photo Biometric Verification test passed successfully!")

if __name__ == "__main__":
    test_live_photo()
