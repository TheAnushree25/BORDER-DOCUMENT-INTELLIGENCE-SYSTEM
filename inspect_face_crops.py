import os
import cv2
from PIL import Image
from backend.utils import face_match

def inspect_crops():
    upload_dir = "backend/uploads"
    for name, f in [("PAN_Ujjwal", "DOC-1386.jpg"), ("Aadhaar_Ujjwal", "DOC-1388.jpg"), ("Aadhaar_Anurag", "DOC-1390.jpg")]:
        img = Image.open(os.path.join(upload_dir, f))
        det = face_match.detect_face(img)
        print(f"=== {name} ({f}) ===")
        print(f"Found: {det['found']}")
        print(f"Box: {det['box']}")
        if det['_crop'] is not None:
            crop_h, crop_w = det['_crop'].shape[:2]
            print(f"Crop shape: {crop_w}x{crop_h}")
            out_crop_path = f"test_crop_{name}.jpg"
            cv2.imwrite(out_crop_path, det['_crop'])
            print(f"Saved crop to {out_crop_path}")

if __name__ == "__main__":
    inspect_crops()
