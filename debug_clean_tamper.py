import io
import cv2
import numpy as np
from PIL import Image, ImageChops

def error_level_analysis(image: Image.Image, quality: int = 90):
    rgb = image.convert("RGB")
    cv_img = np.array(rgb)
    h, w = cv_img.shape[:2]
    total_pixels = max(1, h * w)
    
    cv_bgr = cv2.cvtColor(cv_img, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_bgr, cv2.COLOR_BGR2GRAY)

    # -------------------------------------------------------------
    # 1. Digital Stroke, Whiteout & Erasure Masking
    # -------------------------------------------------------------
    hsv = cv2.cvtColor(cv_bgr, cv2.COLOR_BGR2HSV)
    _, s_chan, v_chan = cv2.split(hsv)
    
    # Identify artificial unnatural solid whiteout / eraser strokes (pure synthetic white)
    solid_mask = (v_chan > 245) & (s_chan < 18)
    
    # Calculate local texture variance (digital strokes have zero noise variance)
    blur_sq = cv2.blur(gray.astype(np.float32)**2, (7, 7))
    sq_blur = cv2.blur(gray.astype(np.float32), (7, 7))**2
    local_std = np.sqrt(np.maximum(blur_sq - sq_blur, 0))
    
    # Synthetic flat strokes over text (near zero micro-texture)
    synthetic_flat_mask = (solid_mask) & (local_std < 1.8)
    flat_pixels = int(np.sum(synthetic_flat_mask))
    flat_pixel_ratio = float(flat_pixels) / total_pixels
    whiteout_tamper = flat_pixel_ratio > 0.01 and flat_pixels > 2000

    # -------------------------------------------------------------
    # 2. Local ELA (Error Level Analysis)
    # -------------------------------------------------------------
    buffer = io.BytesIO()
    rgb.save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    resaved = Image.open(buffer)
    
    diff = ImageChops.difference(rgb, resaved)
    diff_arr = np.asarray(diff).astype(np.float32)
    ela_gray = cv2.cvtColor(diff_arr.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    
    # High-frequency edge discontinuity (e.g. digital pen / sharp text border)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    lap_var = float(laplacian.var())
    sharp_discontinuity = lap_var > 200.0

    # -------------------------------------------------------------
    # 3. Contour Extraction for Altered / Overlaid Zones
    # -------------------------------------------------------------
    suspicious_regions = []
    
    # Find contours on synthetic flat strokes
    if whiteout_tamper:
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (11, 11))
        dilated = cv2.dilate(synthetic_flat_mask.astype(np.uint8), kernel, iterations=2)
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > (h * w * 0.0015):  # Catches small text alterations & large scribbles
                bx, by, bw_b, bh_b = cv2.boundingRect(cnt)
                suspicious_regions.append({
                    "x_pct": round(bx / w * 100, 1),
                    "y_pct": round(by / h * 100, 1),
                    "w_pct": round(bw_b / w * 100, 1),
                    "h_pct": round(bh_b / h * 100, 1),
                    "severity": "high",
                    "label": "Synthetic alteration / Digital overlay"
                })

    # -------------------------------------------------------------
    # 4. Grid-based Compression / Edge Anomaly Checks
    # -------------------------------------------------------------
    grid = 8
    gh, gw = h // grid, w // grid
    cell_variances = []
    for r in range(grid):
        for c in range(grid):
            cell = ela_gray[r * gh:(r + 1) * gh, c * gw:(c + 1) * gw]
            cell_variances.append(float(np.var(cell)))
            
    mean_var = np.mean(cell_variances) if cell_variances else 0
    std_var = np.std(cell_variances) if cell_variances else 0
    thresh_var = max(20.0, mean_var + (std_var * 1.5))
    
    for idx, c_var in enumerate(cell_variances):
        if c_var > thresh_var and c_var > 22.0:
            r, c = divmod(idx, grid)
            suspicious_regions.append({
                "x_pct": round(c / grid * 100, 1),
                "y_pct": round(r / grid * 100, 1),
                "w_pct": round(1 / grid * 100, 1),
                "h_pct": round(1 / grid * 100, 1),
                "severity": "medium",
                "label": "High-frequency noise anomaly (Text splice)"
            })

    # -------------------------------------------------------------
    # 5. Composite Scoring & Verdict
    # -------------------------------------------------------------
    stroke_score = min(70, flat_pixel_ratio * 4000)
    ela_score = min(30, diff_arr.mean() * 2.0)
    anomaly_score = min(30, len(suspicious_regions) * 10)
    lap_score = 35 if sharp_discontinuity else 0
    
    total_score = min(100, int(stroke_score + ela_score + anomaly_score + lap_score))
    tampering_detected = total_score >= 30 or whiteout_tamper or len(suspicious_regions) > 0 or sharp_discontinuity

    detail = "No manipulation signature detected via ELA"
    if tampering_detected:
        reasons = []
        if whiteout_tamper:
            reasons.append("Synthetic whiteout / digital erasure")
        if sharp_discontinuity:
            reasons.append(f"Sharp overlay discontinuity (Laplacian: {lap_var:.0f})")
        if len(suspicious_regions) > 0:
            reasons.append(f"{len(suspicious_regions)} localized anomaly zones")
        detail = f"Tampering Alert: {', '.join(reasons)} (Score: {total_score}/100)"

    max_diff = diff_arr.max() if diff_arr.max() > 0 else 1
    scale = 255.0 / max_diff
    ela_arr = np.clip(diff_arr * scale, 0, 255).astype(np.uint8)

    return {
        "tamper_score": total_score,
        "tampering_detected": tampering_detected,
        "suspicious_regions": suspicious_regions[:6],
        "detail": detail,
        "ela_image": Image.fromarray(ela_arr),
    }

def test_tamper_suite():
    clean_img = Image.open("backend/uploads/DOC-1388.jpg")
    r_clean = error_level_analysis(clean_img)
    print("CLEAN:", r_clean["tamper_score"], "Detected:", r_clean["tampering_detected"], "Detail:", r_clean["detail"])
    assert r_clean["tampering_detected"] is False

    whiteout_img = Image.open("backend/uploads/DOC-1430.jpg")
    r_w = error_level_analysis(whiteout_img)
    print("WHITEOUT:", r_w["tamper_score"], "Detected:", r_w["tampering_detected"], "Detail:", r_w["detail"], "Regions:", len(r_w["suspicious_regions"]))
    assert r_w["tampering_detected"] is True

    scribble_img = Image.open("backend/uploads/DOC-1438.jpg")
    r_s = error_level_analysis(scribble_img)
    print("SCRIBBLE:", r_s["tamper_score"], "Detected:", r_s["tampering_detected"], "Detail:", r_s["detail"], "Regions:", len(r_s["suspicious_regions"]))
    assert r_s["tampering_detected"] is True

    print("\nALL TAMPER TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    test_tamper_suite()
