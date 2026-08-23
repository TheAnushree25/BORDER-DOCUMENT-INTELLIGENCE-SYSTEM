import os
from PIL import Image
from backend.utils import face_match

def test_real_doc_selfie():
    # Test on real scanned uploads
    img1 = Image.open("backend/uploads/DOC-1350.jpg")
    img2 = Image.open("backend/uploads/DOC-1351.jpg")
    res = face_match.compare_faces(img1, img2)
    print("Real Photo Verification Result:")
    print(f"Match: {res['match']}")
    print(f"Similarity: {res['similarity']}%")
    print(f"Reason: {res['reason']}")
    assert res["match"] is True, "Identical scans should match"
    print("[OK] Real Document Biometric Verification Succeeded!")

if __name__ == "__main__":
    test_real_doc_selfie()
