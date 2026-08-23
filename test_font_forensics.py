import sys
import cv2
import numpy as np
from PIL import Image
import io
import re
from rapidocr_onnxruntime import RapidOCR

sys.stdout.reconfigure(encoding="utf-8")

ocr_engine = RapidOCR()

def analyze_font_consistency(img_path):
    img = cv2.imread(img_path)
    if img is None:
        print(f"Failed to load {img_path}")
        return
    h, w = img.shape[:2]
    
    # 1. Extract OCR text boxes with RapidOCR
    res, _ = ocr_engine(img_path)
    if not res:
        print(f"No OCR text found in {img_path}")
        return
        
    print(f"\n=======================================================")
    print(f"ANALYZING FONT & COLOR FORENSICS: {img_path}")
    print(f"=======================================================")
    
    text_patches = []
    
    for idx, (box, txt, score) in enumerate(res):
        if len(txt.strip()) < 2:
            continue
            
        pts = np.array(box, dtype=np.int32)
        x, y, bw, bh = cv2.boundingRect(pts)
        
        # Ensure coordinates are inside image
        x = max(0, min(x, w - 1))
        y = max(0, min(y, h - 1))
        bw = max(1, min(bw, w - x))
        bh = max(1, min(bh, h - y))
        
        if bw < 10 or bh < 8:
            continue
            
        crop = img[y:y+bh, x:x+bw]
        crop_gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        
        # Binarize text using Otsu to separate text ink from background
        _, thresh = cv2.threshold(crop_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        
        # If text is dark on light background, thresh > 0 is text foreground
        fg_pixels = crop_rgb[thresh > 0]
        bg_pixels = crop_rgb[thresh == 0]
        
        if len(fg_pixels) < 15 or len(bg_pixels) < 15:
            continue
            
        # 1. Text ink color (mean RGB and HSV)
        fg_mean_rgb = np.mean(fg_pixels, axis=0) # [R, G, B]
        fg_std_rgb = np.std(fg_pixels, axis=0)
        
        crop_hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        fg_hsv_pixels = crop_hsv[thresh > 0]
        fg_mean_hsv = np.mean(fg_hsv_pixels, axis=0) # [H, S, V]
        
        # 2. Text background color
        bg_mean_rgb = np.mean(bg_pixels, axis=0)
        
        # 3. Stroke width via Distance Transform
        dist = cv2.distanceTransform(thresh, cv2.DIST_L2, 5)
        stroke_width = float(np.mean(dist[thresh > 0]) * 2) if np.sum(thresh > 0) > 0 else 1.0
        
        # 4. Text edge sharpness (Laplacian variance of crop)
        lap_var = float(cv2.Laplacian(crop_gray, cv2.CV_64F).var())
        
        text_patches.append({
            "idx": idx,
            "text": txt,
            "box": box,
            "coords": (x, y, bw, bh),
            "x_pct": round(x / w * 100, 1),
            "y_pct": round(y / h * 100, 1),
            "w_pct": round(bw / w * 100, 1),
            "h_pct": round(bh / h * 100, 1),
            "fg_mean_rgb": fg_mean_rgb,
            "fg_std_rgb": fg_std_rgb,
            "fg_mean_hsv": fg_mean_hsv,
            "bg_mean_rgb": bg_mean_rgb,
            "stroke_width": stroke_width,
            "sharpness": lap_var,
            "fg_count": len(fg_pixels),
        })
        
        print(f"[{txt[:20]:20s}] RGB: ({fg_mean_rgb[0]:.1f}, {fg_mean_rgb[1]:.1f}, {fg_mean_rgb[2]:.1f}) | V: {fg_mean_hsv[2]:.1f} | Stroke: {stroke_width:.2f}px | Sharp: {lap_var:.1f}")

    if len(text_patches) < 2:
        print("Not enough text patches to compare.")
        return

    # Compute baseline font ink color & stroke across the document
    all_fg_rgb = np.array([p["fg_mean_rgb"] for p in text_patches])
    all_fg_v = np.array([p["fg_mean_hsv"][2] for p in text_patches])
    all_strokes = np.array([p["stroke_width"] for p in text_patches])
    all_sharp = np.array([p["sharpness"] for p in text_patches])
    
    median_rgb = np.median(all_fg_rgb, axis=0)
    median_v = np.median(all_fg_v)
    median_stroke = np.median(all_strokes)
    median_sharp = np.median(all_sharp)
    
    print(f"\n--- DOCUMENT BASELINE ---")
    print(f"Median Text Ink RGB: ({median_rgb[0]:.1f}, {median_rgb[1]:.1f}, {median_rgb[2]:.1f})")
    print(f"Median Text Value (Brightness): {median_v:.1f}")
    print(f"Median Stroke Width: {median_stroke:.2f}px")
    print(f"Median Edge Sharpness: {median_sharp:.1f}")
    
    font_anomalies = []
    
    for p in text_patches:
        # Distance in color space
        color_dist = float(np.linalg.norm(p["fg_mean_rgb"] - median_rgb))
        stroke_ratio = p["stroke_width"] / max(0.1, median_stroke)
        sharp_ratio = p["sharpness"] / max(1.0, median_sharp)
        
        is_anomaly = False
        reasons = []
        
        # 1. Font Ink Color Mismatch (e.g. digital black or mismatched color channel)
        if color_dist > 45.0:
            is_anomaly = True
            reasons.append(f"Ink color discrepancy (ΔE: {color_dist:.1f})")
            
        # 2. Font Stroke / Weight Inconsistency
        if stroke_ratio > 2.5 or stroke_ratio < 0.35:
            is_anomaly = True
            reasons.append(f"Mismatched stroke width ({p['stroke_width']:.1f}px vs norm {median_stroke:.1f}px)")
            
        # 3. Unnatural Digital Sharpness / Discontinuity
        if sharp_ratio > 3.5 and p["sharpness"] > 250.0:
            is_anomaly = True
            reasons.append(f"Unnatural digital font sharpness ({p['sharpness']:.1f})")
            
        if is_anomaly:
            font_anomalies.append({
                "text": p["text"],
                "x_pct": p["x_pct"],
                "y_pct": p["y_pct"],
                "w_pct": p["w_pct"],
                "h_pct": p["h_pct"],
                "color_dist": color_dist,
                "stroke_ratio": stroke_ratio,
                "reasons": reasons,
                "severity": "high" if (color_dist > 60 or stroke_ratio > 3.0) else "medium",
                "label": f"Font Anomaly: {', '.join(reasons)}"
            })
            print(f"  🚨 FONT ANOMALY in '{p['text']}': {', '.join(reasons)}")

    print(f"\nTotal Font & Color Anomalies Detected: {len(font_anomalies)}")

if __name__ == "__main__":
    analyze_font_consistency("backend/uploads/DOC-1388.jpg")
    analyze_font_consistency("backend/uploads/DOC-1478.jpg")
    analyze_font_consistency("backend/uploads/DOC-1430.jpg")
    analyze_font_consistency("backend/uploads/DOC-1438.jpg")
