import os
import cv2
import numpy as np
from PIL import Image
from backend.utils import face_match

def test_uploaded_face_matches():
    upload_dir = "backend/uploads"
    # User's uploaded documents
    pan_img = Image.open(os.path.join(upload_dir, "DOC-1386.jpg"))
    aadhaar_ujjwal = Image.open(os.path.join(upload_dir, "DOC-1388.jpg"))
    aadhaar_anurag = Image.open(os.path.join(upload_dir, "DOC-1390.jpg"))
    
    print("--- 1. Testing PAN (Ujjwal) vs Aadhaar (Ujjwal) ---")
    res1 = face_match.compare_faces(pan_img, aadhaar_ujjwal)
    print("Result 1 (Same Person - Ujjwal):", res1)
    
    print("\n--- 2. Testing Aadhaar (Ujjwal) vs Aadhaar (Anurag) ---")
    res2 = face_match.compare_faces(aadhaar_ujjwal, aadhaar_anurag)
    print("Result 2 (Different Person - Ujjwal vs Anurag):", res2)

    print("\n--- 3. Testing PAN (Ujjwal) vs Aadhaar (Anurag) ---")
    res3 = face_match.compare_faces(pan_img, aadhaar_anurag)
    print("Result 3 (Different Person - Ujjwal vs Anurag):", res3)

if __name__ == "__main__":
    test_uploaded_face_matches()
