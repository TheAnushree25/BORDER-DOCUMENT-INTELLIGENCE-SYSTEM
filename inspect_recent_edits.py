import os
import json
from PIL import Image
from backend.utils import tamper, ocr, document_extractor

def inspect_recent_edits():
    files = ["DOC-1430.jpg", "DOC-1436.jpg", "DOC-1438.jpg", "DOC-1439.jpg"]
    upload_dir = "backend/uploads"
    
    for f in files:
        path = os.path.join(upload_dir, f)
        if not os.path.exists(path):
            continue
        print("="*60)
        print(f"FILE: {f} (size: {os.path.getsize(path)} bytes)")
        print("="*60)
        img = Image.open(path)
        print(f"Dimensions: {img.size}, format: {img.format}, mode: {img.mode}")
        
        # Tampering Analysis
        t_res = tamper.error_level_analysis(img)
        print(">>> TAMPER RESULT:", json.dumps({
            "tamper_score": t_res["tamper_score"],
            "tampering_detected": t_res["tampering_detected"],
            "detail": t_res["detail"],
            "suspicious_regions_count": len(t_res["suspicious_regions"]),
            "regions": t_res["suspicious_regions"][:3]
        }, indent=2))
        
        # OCR Analysis
        raw_text = ocr.extract_text(img, filename=f)
        print(">>> RAW OCR TEXT:")
        print(raw_text)
        
        doc_type, ext = document_extractor.extract_document_data(raw_text)
        print(f">>> DOC TYPE: {doc_type}")
        print(">>> EXTRACTED:", json.dumps(ext, indent=2))

if __name__ == "__main__":
    inspect_recent_edits()
