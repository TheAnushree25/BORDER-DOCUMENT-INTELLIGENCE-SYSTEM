import cv2
import json
from PIL import Image
import numpy as np
from rapidocr_onnxruntime import RapidOCR
from backend.utils import tamper, face_match

img_path = "backend/uploads/DOC-1478.jpg"
img = cv2.imread(img_path)
h, w = img.shape[:2]
print(f"Image Size: w={w}, h={h}")

pil_img = Image.open(img_path)
ocr_engine = RapidOCR()
res, _ = ocr_engine(img_path)
ocr_boxes = [{"box": b, "text": t, "score": s} for b, t, s in res]

# Tamper analysis
t_res = tamper.error_level_analysis(pil_img, ocr_boxes=ocr_boxes)
print("\n--- Tamper Result ---")
print("Detail:", t_res["detail"])
print("Suspicious Regions:")
for r in t_res["suspicious_regions"]:
    print(" ", r)

# Face detection
f_res = face_match.detect_face(pil_img)
print("\n--- Face Result ---")
print("Found:", f_res["found"])
print("Box:", f_res["box"])

