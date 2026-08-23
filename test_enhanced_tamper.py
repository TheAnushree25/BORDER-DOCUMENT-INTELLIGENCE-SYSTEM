import os
import io
import cv2
import numpy as np
from PIL import Image, ImageChops

def error_level_analysis(image: Image.Image, quality: int = 90):
    rgb = image.convert("RGB")
    cv_img = np.array(rgb)
    h, w = cv_img.shape[:2]
    total_pixels = max(1, h * w)
    
    # 1. Standard Error Level Analysis (ELA)
    buffer = io.BytesIO()
    rgb.save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    resaved = Image.open(buffer)
    
    diff = ImageChops.difference(rgb, resaved)
    diff_arr = np.asarray(diff).astype(np.float32)
    
    # 2. Localized Grid-based Anomaly Analysis (6x6 Grid)
    grid = 6
    gh, gw = h // grid, w // grid
    cell_variances = []
    cell_means = []
    
    for r in range(grid):
        for c in range(grid):
            cell = diff_arr[r * gh:(r + 1) * gh, c * gw:(c + 1) * gw]
            cell_variances.append(float(np.var(cell)))
            cell_means.append(float(np.mean(cell)))
            
    var_mean = np.mean(cell_variances) if cell_variances else 0
    var_max = np.max(cell_variances) if cell_variances else 0
    
    # 3. Digital Markup & Overlay Detection (Whiteout, Colored Scribble, Blackout)
    cv_base = cv2.cvtColor(cv_img, cv2.COLOR_RGB2BGR)
    hsv = cv2.cvtColor(cv_base, cv2.COLOR_BGR2HSV)
    h_c, s_c, v_c = cv2.split(hsv)
    
    # A. Digital Whiteout / Eraser tool (V > 242 and S < 18)
    whiteout_pixels = int(np.sum((v_c > 242) & (s_c < 18)))
    whiteout_ratio = whiteout_pixels / total_pixels
    whiteout_tamper = whiteout_ratio > 0.015 and whiteout_pixels > 2000
    
    # B. Digital Pen / Colored Marker / Neon Scribble (High saturation + high brightness)
    pen_pixels = int(np.sum((s_c > 140) & (v_c > 140)))
    pen_ratio = pen_pixels / total_pixels
    pen_tamper = pen_ratio > 0.001 and pen_pixels > 350
    
    # C. Digital Blackout / Redaction Brush (V < 12)
    blackout_pixels = int(np.sum(v_c < 12))
    blackout_ratio = blackout_pixels / total_pixels
    blackout_tamper = blackout_ratio > 0.01 and blackout_pixels > 1500

    # 4. Multi-Factor Scoring
    base_ela_score = min(40, diff_arr.mean() * 3.0)
    local_anomaly_score = min(35, (var_max / (var_mean + 1e-5)) * 3.5) if var_mean > 0 else 0
    
    overlay_score = 0
    reasons = []
    if whiteout_tamper:
        overlay_score += 55
        reasons.append(f"Synthetic whiteout / eraser patch detected ({whiteout_ratio*100:.1f}% area)")
    if pen_tamper:
        overlay_score += 55
        reasons.append(f"Digital pen / colored markup scribble detected ({pen_pixels} px)")
    if blackout_tamper:
        overlay_score += 50
        reasons.append(f"Digital blackout / redaction box detected ({blackout_ratio*100:.1f}% area)")

    total_score = min(100, int(base_ela_score + local_anomaly_score + overlay_score))
    tampering_detected = total_score >= 30 or overlay_score > 0
    
    # 5. Generate Bounding Boxes for Suspicious Regions
    regions = []
    # Check ELA grid anomalies
    threshold_var = max(15.0, var_mean * 1.5)
    for idx, v_val in enumerate(cell_variances):
        if v_val > threshold_var:
            r, c = divmod(idx, grid)
            regions.append({
                "x_pct": round(c / grid * 100, 1),
                "y_pct": round(r / grid * 100, 1),
                "w_pct": round(1 / grid * 100, 1),
                "h_pct": round(1 / grid * 100, 1),
                "severity": "high" if v_val > threshold_var * 1.8 else "medium",
                "label": "Compression / ELA anomaly"
            })
            
    # Check localized markup masks (whiteout/pen masks)
    if whiteout_tamper or pen_tamper:
        mask = ((v_c > 242) & (s_c < 18)) if whiteout_tamper else ((s_c > 140) & (v_c > 140))
        mask_u8 = mask.astype(np.uint8) * 255
        contours, _ = cv2.findContours(mask_u8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 400: # Significant stroke / box
                bx, by, bw_b, bh_b = cv2.boundingRect(cnt)
                regions.append({
                    "x_pct": round(bx / w * 100, 1),
                    "y_pct": round(by / h * 100, 1),
                    "w_pct": round(bw_b / w * 100, 1),
                    "h_pct": round(bh_b / h * 100, 1),
                    "severity": "high",
                    "label": "Digital Alteration / Markup Overlay"
                })

    detail_str = "; ".join(reasons) if reasons else ("Compression inconsistency detected via ELA" if tampering_detected else "No manipulation signature found (Heuristic)")

    max_diff = diff_arr.max() if diff_arr.max() > 0 else 1
    scale = 255.0 / max_diff
    ela_arr = np.clip(diff_arr * scale, 0, 255).astype(np.uint8)

    return {
        "tamper_score": total_score,
        "tampering_detected": bool(tampering_detected),
        "suspicious_regions": regions,
        "detail": detail_str,
        "ela_image": Image.fromarray(ela_arr),
    }

def test_tamper_all():
    upload_dir = "backend/uploads"
    clean_path = os.path.join(upload_dir, "DOC-1388.jpg")
    edited_1 = os.path.join(upload_dir, "DOC-1430.jpg")
    edited_2 = os.path.join(upload_dir, "DOC-1438.jpg")

    r_clean = error_level_analysis(Image.open(clean_path))
    print("CLEAN DOC:", r_clean["tamper_score"], "Detected:", r_clean["tampering_detected"], "Detail:", r_clean["detail"])
    assert r_clean["tampering_detected"] is False

    r_ed1 = error_level_analysis(Image.open(edited_1))
    print("EDITED DOC 1 (Whiteout):", r_ed1["tamper_score"], "Detected:", r_ed1["tampering_detected"], "Detail:", r_ed1["detail"], "Regions:", len(r_ed1["suspicious_regions"]))
    assert r_ed1["tampering_detected"] is True

    r_ed2 = error_level_analysis(Image.open(edited_2))
    print("EDITED DOC 2 (Scribble):", r_ed2["tamper_score"], "Detected:", r_ed2["tampering_detected"], "Detail:", r_ed2["detail"], "Regions:", len(r_ed2["suspicious_regions"]))
    assert r_ed2["tampering_detected"] is True

if __name__ == "__main__":
    test_tamper_all()
