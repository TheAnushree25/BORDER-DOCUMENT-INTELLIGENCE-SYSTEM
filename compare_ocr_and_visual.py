from PIL import Image
import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR

ocr_engine = RapidOCR()

res_1388, _ = ocr_engine("backend/uploads/DOC-1388.jpg")
res_1478, _ = ocr_engine("backend/uploads/DOC-1478.jpg")

print("=== DOC-1388 (Original Clean) OCR ===")
for box, txt, score in (res_1388 or []):
    safe_txt = txt.encode("ascii", "replace").decode("ascii")
    print(f"  [{score:.2f}] {safe_txt} at {box[0]}")

print("\n=== DOC-1478 (Uploaded Edit) OCR ===")
for box, txt, score in (res_1478 or []):
    safe_txt = txt.encode("ascii", "replace").decode("ascii")
    print(f"  [{score:.2f}] {safe_txt} at {box[0]}")
