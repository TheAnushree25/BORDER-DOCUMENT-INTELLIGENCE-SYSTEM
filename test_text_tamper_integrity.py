import os
import re
from rapidocr_onnxruntime import RapidOCR
from PIL import Image
import numpy as np
import cv2
from backend.utils import tamper

ocr_engine = RapidOCR()

def check_document_integrity(img_path):
    img = Image.open(img_path)
    w, h = img.size
    
    # 1. Pixel Forensics
    t_res = tamper.error_level_analysis(img)
    
    # 2. Text & Layout Forensics
    res, _ = ocr_engine(img_path)
    boxes = [item[0] for item in (res or [])]
    texts = [item[1] for item in (res or [])]
    scores = [item[2] for item in (res or [])]
    
    # Check for duplicate numbers or floating text
    aadhaar_numbers = []
    pan_numbers = []
    anomalous_text_regions = []
    
    for box, txt in zip(boxes, texts):
        # Clean text
        clean = re.sub(r'[^0-9A-Za-z]', '', txt)
        # Aadhaar 12-digit number
        digits = re.findall(r'\b\d{12}\b', clean) or re.findall(r'\b\d{4}\s?\d{4}\s?\d{4}\b', txt)
        for d in digits:
            d_clean = d.replace(" ", "")
            if len(d_clean) == 12:
                top_left = box[0]
                bx, by = top_left[0], top_left[1]
                bw = box[1][0] - box[0][0]
                bh = box[2][1] - box[1][1]
                aadhaar_numbers.append({
                    "number": d_clean,
                    "box": box,
                    "x_pct": round(bx / w * 100, 1),
                    "y_pct": round(by / h * 100, 1),
                    "w_pct": round(bw / w * 100, 1),
                    "h_pct": round(bh / h * 100, 1),
                })
        
        # Check out-of-bounds floating text (e.g. text right at outer margin > 88% width or < 3% width that is not standard)
        top_left = box[0]
        bx, by = top_left[0], top_left[1]
        bw = box[1][0] - box[0][0]
        bh = box[2][1] - box[1][1]
        x_pct = bx / w * 100
        y_pct = by / h * 100
        
        # Numbers floating in non-standard margins (e.g. right border x > 85%)
        if len(re.findall(r'\d{6,}', clean)) > 0 and x_pct > 82:
            anomalous_text_regions.append({
                "x_pct": round(x_pct, 1),
                "y_pct": round(y_pct, 1),
                "w_pct": round(bw / w * 100, 1),
                "h_pct": round(bh / h * 100, 1),
                "severity": "high",
                "label": f"Spliced / Floating ID text: '{txt}'"
            })
            
    # If multiple identical or conflicting Aadhaar numbers found in different locations
    if len(aadhaar_numbers) > 1:
        # Check if coordinates are far apart
        for i in range(len(aadhaar_numbers)):
            for j in range(i+1, len(aadhaar_numbers)):
                n1, n2 = aadhaar_numbers[i], aadhaar_numbers[j]
                dist = abs(n1["x_pct"] - n2["x_pct"]) + abs(n1["y_pct"] - n2["y_pct"])
                if dist > 20: # Far apart
                    anomalous_text_regions.append({
                        "x_pct": n1["x_pct"],
                        "y_pct": n1["y_pct"],
                        "w_pct": n1["w_pct"],
                        "h_pct": n1["h_pct"],
                        "severity": "high",
                        "label": f"Duplicate Spliced Number ({n1['number']})"
                    })
                    anomalous_text_regions.append({
                        "x_pct": n2["x_pct"],
                        "y_pct": n2["y_pct"],
                        "w_pct": n2["w_pct"],
                        "h_pct": n2["h_pct"],
                        "severity": "high",
                        "label": f"Duplicate Spliced Number ({n2['number']})"
                    })

    is_text_tampered = len(anomalous_text_regions) > 0
    final_tampering_detected = t_res["tampering_detected"] or is_text_tampered
    all_regions = t_res["suspicious_regions"] + anomalous_text_regions
    
    score = max(t_res["tamper_score"], 80 if is_text_tampered else 0)
    
    print(f"[{os.path.basename(img_path)}]:")
    print(f"  Tampering Detected: {final_tampering_detected}")
    print(f"  Score: {score}")
    print(f"  Suspicious Regions: {len(all_regions)}")
    for r in all_regions:
        print("   -", r)
        
print("=== TESTING INTEGRITY ON DOC-1478 & DOC-1388 ===")
check_document_integrity("backend/uploads/DOC-1478.jpg")
print("\n--- Clean Document DOC-1388 ---")
check_document_integrity("backend/uploads/DOC-1388.jpg")
print("\n--- Whiteout Document DOC-1430 ---")
check_document_integrity("backend/uploads/DOC-1430.jpg")
print("\n--- Scribble Document DOC-1438 ---")
check_document_integrity("backend/uploads/DOC-1438.jpg")
