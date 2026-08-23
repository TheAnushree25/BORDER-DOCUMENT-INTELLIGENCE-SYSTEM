import cv2
import sys
from rapidocr_onnxruntime import RapidOCR

sys.stdout.reconfigure(encoding="utf-8")

ocr_engine = RapidOCR()
res, _ = ocr_engine("backend/uploads/DOC-1478.jpg")

print(f"=== DOC-1478 ALL OCR BOXES ({len(res)}) ===")
for i, item in enumerate(res):
    box, txt, score = item
    print(f"Box #{i}: score={score:.2f}, text={repr(txt)}")
    print(f"  coords: top_left={box[0]}, bottom_right={box[2]}")
