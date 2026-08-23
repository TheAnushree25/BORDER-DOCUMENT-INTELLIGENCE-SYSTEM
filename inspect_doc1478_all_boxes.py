import sys
import cv2
import json
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR

sys.stdout.reconfigure(encoding="utf-8")

img_path = "backend/uploads/DOC-1478.jpg"
img = cv2.imread(img_path)
h, w = img.shape[:2]
print(f"DOC-1478 Image Size: w={w}, h={h}")

ocr = RapidOCR()
res, _ = ocr(img_path)

print(f"\nTotal OCR Items: {len(res)}")
for idx, (box, txt, score) in enumerate(res):
    pts = np.array(box, dtype=np.int32)
    bx, by, bw, bh = cv2.boundingRect(pts)
    x_pct = round(bx / w * 100, 1)
    y_pct = round(by / h * 100, 1)
    w_pct = round(bw / w * 100, 1)
    h_pct = round(bh / h * 100, 1)
    print(f"[{idx:2d}] score={score:.2f} | x_pct={x_pct:5.1f}%, y_pct={y_pct:5.1f}%, w_pct={w_pct:4.1f}%, h_pct={h_pct:4.1f}% | text='{txt}'")

