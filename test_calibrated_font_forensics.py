import sys
import cv2
import numpy as np
from PIL import Image
import re
from rapidocr_onnxruntime import RapidOCR

sys.stdout.reconfigure(encoding="utf-8")
ocr_engine = RapidOCR()

def analyze_font_and_color_forensics(img_path):
    img = cv2.imread(img_path)
    if img is None:
        return {"tampered": False, "score": 0, "anomalies": []}
        
    h, w = img.shape[:2]
    res, _ = ocr_engine(img_path)
    if not res:
        return {"tampered": False, "score": 0, "anomalies": []}

    text_patches = []
    
    for idx, (box, txt, score) in enumerate(res):
        txt_clean = txt.strip()
        if len(txt_clean) < 2:
            continue
            
        pts = np.array(box, dtype=np.int32)
        x, y, bw, bh = cv2.boundingRect(pts)
        
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        bw = max(1, min(bw, w - x))
        bh = max(1, min(bh, h - y))
        
        if bw < 12 or bh < 8:
            continue
            
        crop = img[y:y+bh, x:x+bw]
        crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        
        # Otsu thresholding
        _, thresh = cv2.threshold(crop_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        fg_mask = thresh > 0
        bg_mask = thresh == 0
        
        if np.sum(fg_mask) < 15 or np.sum(bg_mask) < 15:
            continue
            
        fg_rgb = np.mean(crop_rgb[fg_mask], axis=0) # [R, G, B]
        bg_rgb = np.mean(crop_rgb[bg_mask], axis=0)
        
        # Local background micro-texture
        blur_sq = cv2.blur(crop_gray.astype(np.float32)**2, (3, 3))
        sq_blur = cv2.blur(crop_gray.astype(np.float32), (3, 3))**2
        local_std = np.sqrt(np.maximum(blur_sq - sq_blur, 0))
        bg_texture = float(np.mean(local_std[bg_mask]))
        
        # Stroke width
        dist = cv2.distanceTransform(thresh, cv2.DIST_L2, 5)
        stroke_w = float(np.mean(dist[fg_mask]) * 2) if np.sum(fg_mask) > 0 else 1.0
        
        # Edge sharpness
        lap = float(cv2.Laplacian(crop_gray, cv2.CV_64F).var())
        
        # Categorize: Header/Disclaimer vs Personal Data Field
        is_header = any(k in txt_clean.upper() for k in ["GOVERNMENT", "INDIA", "INCOME TAX", "PASSPORT", "REPUBLIC", "PROOF", "CITIZENSHIP", "VERIFICATION", "XML", "AUTHENTICATION"])
        
        text_patches.append({
            "text": txt_clean,
            "x_pct": round(x / w * 100, 1),
            "y_pct": round(y / h * 100, 1),
            "w_pct": round(bw / w * 100, 1),
            "h_pct": round(bh / h * 100, 1),
            "fg_rgb": fg_rgb,
            "bg_rgb": bg_rgb,
            "bg_texture": bg_texture,
            "stroke_w": stroke_w,
            "sharpness": lap,
            "is_header": is_header,
        })

    # Separate data fields
    data_patches = [p for p in text_patches if not p["is_header"]]
    if len(data_patches) < 2:
        data_patches = text_patches

    # Baseline text metrics for data fields
    data_fg_rgb = np.array([p["fg_rgb"] for p in data_patches])
    data_bg_texture = np.array([p["bg_texture"] for p in data_patches])
    
    baseline_fg_rgb = np.median(data_fg_rgb, axis=0) if len(data_fg_rgb) > 0 else np.array([50, 50, 50])
    baseline_bg_texture = np.median(data_bg_texture) if len(data_bg_texture) > 0 else 5.0
    
    anomalies = []
    
    for p in text_patches:
        reasons = []
        is_num = bool(re.search(r"^\d{4}\s?\d{4}\s?\d{4}$", p["text"]))
        
        # 1. Font Ink Color Mismatch among standard body text
        color_delta = float(np.linalg.norm(p["fg_rgb"] - baseline_fg_rgb))
        if color_delta > 90.0 and not p["is_header"] and not is_num:
            reasons.append(f"Mismatched font ink color (DeltaE: {color_delta:.0f})")
            
        # 2. Text background patch erasure (zero texture / pasted box under text)
        if p["bg_texture"] < 1.2 and baseline_bg_texture > 3.0:
            reasons.append(f"Synthetic flat background patch under text (texture {p['bg_texture']:.1f})")
            
        # 3. Out of bounds floating text (text at x > 85% or illegal margin)
        if p["x_pct"] > 82.0 and bool(re.search(r"\d{4,}", p["text"])):
            reasons.append(f"Spliced floating text layout at margin ({p['x_pct']}%)")
            
        if reasons:
            anomalies.append({
                "text": p["text"],
                "x_pct": p["x_pct"],
                "y_pct": p["y_pct"],
                "w_pct": p["w_pct"],
                "h_pct": p["h_pct"],
                "severity": "high",
                "label": f"Font & Color Anomaly: {', '.join(reasons)}"
            })

    tampered = len(anomalies) > 0
    score = min(100, len(anomalies) * 35)
    
    print(f"\n[{img_path}] Tampered: {tampered} | Anomalies: {len(anomalies)}")
    for a in anomalies:
        print(f"  🚨 {a['label']} on '{a['text']}' at (x: {a['x_pct']}%, y: {a['y_pct']}%)")
        
    return {"tampered": tampered, "score": score, "anomalies": anomalies}

if __name__ == "__main__":
    print("=== TESTING FONT & COLOR FORENSIC DETECTOR ===")
    r_clean = analyze_font_and_color_forensics("backend/uploads/DOC-1388.jpg")
    assert r_clean["tampered"] is False, "Clean document should have 0 font anomalies!"
    print("[SUCCESS] Clean Aadhaar passed with 0 font anomalies!")

    r_edit = analyze_font_and_color_forensics("backend/uploads/DOC-1478.jpg")
    assert r_edit["tampered"] is True, "Edited document must be flagged by font/layout detector!"
    print("[SUCCESS] Edited document DOC-1478 correctly flagged!")

    r_white = analyze_font_and_color_forensics("backend/uploads/DOC-1430.jpg")
    assert r_white["tampered"] is True, "Whiteout document must be flagged!"
    print("[SUCCESS] Whiteout document DOC-1430 correctly flagged!")

    r_scribble = analyze_font_and_color_forensics("backend/uploads/DOC-1438.jpg")
    assert r_scribble["tampered"] is True, "Scribble document must be flagged!"
    print("[SUCCESS] Scribble document DOC-1438 correctly flagged!")

    print("\nALL FONT & COLOR FORENSICS TESTS PASSED 100%!")
