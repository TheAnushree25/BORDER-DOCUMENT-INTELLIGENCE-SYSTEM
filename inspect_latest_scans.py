import os
import json
from PIL import Image
from backend.utils import ocr, document_extractor, face_match

def inspect_latest_uploads():
    files = ["DOC-1386.jpg", "DOC-1388.jpg", "DOC-1389.jpg", "DOC-1390.jpg", "DOC-1392.jpg", "DOC-1393.jpg"]
    upload_dir = "backend/uploads"
    
    for f in files:
        path = os.path.join(upload_dir, f)
        if not os.path.exists(path):
            continue
        print("="*60)
        print(f"FILE: {f} (size: {os.path.getsize(path)} bytes)")
        print("="*60)
        img = Image.open(path)
        print(f"Image size: {img.size}, mode: {img.mode}")
        
        # 1. OCR text
        raw_text = ocr.extract_text(img, filename=f)
        print("--- RAW OCR TEXT ---")
        print(raw_text)
        print("--------------------")
        
        # 2. Document Classification & Extracted Fields
        doc_type, ext = document_extractor.extract_document_data(raw_text)
        print(f">>> DOCUMENT TYPE: {doc_type}")
        print(">>> EXTRACTED FIELDS:", json.dumps(ext, indent=2))
        
        # 3. Face detection
        face = face_match.detect_face(img)
        print(f">>> FACE DETECTION: found={face['found']}, box={face['box']}")

if __name__ == "__main__":
    inspect_latest_uploads()
