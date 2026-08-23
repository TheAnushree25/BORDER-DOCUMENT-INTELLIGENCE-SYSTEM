import glob
import os
import cv2
import numpy as np
from PIL import Image
from rapidocr_onnxruntime import RapidOCR
from backend.utils import tamper, document_extractor

ocr_engine = RapidOCR()

recent_docs = sorted(glob.glob("backend/uploads/DOC-*.jpg"), key=os.path.getmtime, reverse=True)[:10]

print("=== TESTING RECENT UPLOADS ===")
for p in recent_docs:
    img = Image.open(p)
    t_res = tamper.error_level_analysis(img)
    
    # RapidOCR extraction
    res, _ = ocr_engine(p)
    lines = [item[1] for item in (res or [])]
    boxes = [item[0] for item in (res or [])]
    
    print(f"\nFile: {os.path.basename(p)}")
    print(f"  Tamper Score: {t_res['tamper_score']}, Detected: {t_res['tampering_detected']}")
    print(f"  Detail: {t_res['detail']}")
    print(f"  OCR Boxes Count: {len(boxes)}")
    for b, l in zip(boxes[:8], lines[:8]):
        print(f"    {b[0]}: {l}")
