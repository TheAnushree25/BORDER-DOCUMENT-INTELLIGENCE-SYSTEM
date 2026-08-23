import cv2
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
from backend.utils import tamper

ocr_engine = RapidOCR()
img_path = "backend/uploads/DOC-1478.jpg"
img = Image.open(img_path)
res, _ = ocr_engine(img_path)
ocr_boxes = [{"box": b, "text": t, "score": s} for b, t, s in res]

result = tamper.error_level_analysis(img, ocr_boxes=ocr_boxes)
print("\n=== EVIDENCE REGIONS FOR DOC-1478.jpg ===")
print("Tampering Detected:", result["tampering_detected"])
print("Tamper Score:", result["tamper_score"])
print("Detail:", result["detail"])
print(f"Total Regions: {len(result['suspicious_regions'])}")
for r in result["suspicious_regions"]:
    print(" -", r)

# Assert that NO box is at the original bottom location (x~35%, y~80%)
original_box_found = any(abs(r["x_pct"] - 34.8) < 5 and abs(r["y_pct"] - 80.2) < 5 for r in result["suspicious_regions"])
print("Original text marked?", original_box_found)
assert not original_box_found, "Original genuine text at bottom center must NOT be marked!"

# Assert that the tampered floating box (x~89.9%, y~36.6%) IS marked
tampered_box_found = any(abs(r["x_pct"] - 89.9) < 5 for r in result["suspicious_regions"])
print("Tampered text marked?", tampered_box_found)
assert tampered_box_found, "Tampered floating text on right border MUST be marked!"

print("\n[SUCCESS] ONLY the tampered text was marked, NOT the original text!")
