import cv2
import numpy as np
from PIL import Image

_face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
_eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")

def _pil_to_cv(img: Image.Image):
    return cv2.cvtColor(np.array(img.convert("RGB")), cv2.COLOR_RGB2BGR)

def assess_crop_quality(crop, label="Photo"):
    """
    Analyzes resolution, blur, underexposure, and glare on a face crop.
    """
    issues = []
    if crop is None or crop.size == 0:
        return ["No image data"]
        
    h, w = crop.shape[:2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    
    # 1. Resolution Check
    if min(h, w) < 55:
        issues.append(f"Low resolution on {label} ({w}x{h}px)")
        
    # 2. Blur / Sharpness Check
    lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if lap_var < 16.0:
        issues.append(f"{label} has high blur / out-of-focus camera")
        
    # 3. Brightness & Glare Check
    mean_b = float(np.mean(gray))
    std_b = float(np.std(gray))
    if mean_b < 38:
        issues.append(f"{label} is underexposed / dark lighting")
    elif mean_b > 225:
        issues.append(f"{label} has strong camera glare / overexposure")
    elif std_b < 18:
        issues.append(f"{label} has washed-out low contrast")
        
    return issues

def detect_face(image: Image.Image):
    cv_img = _pil_to_cv(image)
    h_img, w_img = cv_img.shape[:2]

    # If the image itself is already a portrait crop (<320px and ~1:1 aspect ratio)
    if min(h_img, w_img) <= 320 and 0.65 <= (w_img / float(h_img)) <= 1.35:
        return {
            "found": True,
            "box": {
                "x_pct": 0.0,
                "y_pct": 0.0,
                "w_pct": 100.0,
                "h_pct": 100.0,
                "label": "Document Face Portrait"
            },
            "_crop": cv_img
        }

    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    gray_eq = cv2.equalizeHist(gray)
    
    candidates = []
    for sf, mn in [(1.08, 3), (1.05, 2), (1.12, 4)]:
        faces = _face_cascade.detectMultiScale(gray_eq, scaleFactor=sf, minNeighbors=mn, minSize=(30, 30))
        if len(faces) == 0:
            faces = _face_cascade.detectMultiScale(gray, scaleFactor=sf, minNeighbors=mn, minSize=(25, 25))
            
        for (x, y, w, h) in faces:
            aspect = float(w) / max(h, 1)
            if 0.75 <= aspect <= 1.35:
                face_roi = gray_eq[y:y+int(h*0.65), x:x+w]
                eyes = _eye_cascade.detectMultiScale(face_roi, scaleFactor=1.1, minNeighbors=2, minSize=(8, 8))
                
                # Check skin tone in YCrCb
                crop_cand = cv_img[y:y+h, x:x+w]
                ycrcb = cv2.cvtColor(crop_cand, cv2.COLOR_BGR2YCrCb)
                skin_mask = cv2.inRange(ycrcb, np.array([0, 133, 77]), np.array([255, 173, 127]))
                skin_ratio = np.count_nonzero(skin_mask) / float(w * h)

                # Prioritize central card faces with genuine skin and eyes
                score = (skin_ratio * 50.0) + (len(eyes) * 30.0) + ((1.0 - abs(aspect - 1.0)) * 20.0)
                candidates.append((score, len(eyes), (x, y, w, h)))

    if not candidates:
        return {"found": False, "box": None, "_crop": None}

    candidates.sort(key=lambda c: c[0], reverse=True)
    best_score, eye_cnt, (x, y, w, h) = candidates[0]
    
    pad_x = int(w * 0.12)
    pad_y = int(h * 0.12)
    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_y)
    x2 = min(w_img, x + w + pad_x)
    y2 = min(h_img, y + h + pad_y)

    return {
        "found": True,
        "box": {
            "x_pct": round((x / w_img) * 100, 1),
            "y_pct": round((y / h_img) * 100, 1),
            "w_pct": round((w / w_img) * 100, 1),
            "h_pct": round((h / h_img) * 100, 1),
            "label": "Document Face Portrait"
        },
        "_crop": cv_img[y1:y2, x1:x2]
    }

def check_liveness(cv_crop):
    """
    Checks if the live selfie is a real person or a screen/paper spoof using Laplacian texture variance.
    """
    if cv_crop is None or cv_crop.size == 0:
        return False, 0.0
    gray = cv2.cvtColor(cv_crop, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F).var()
    is_live = bool(laplacian > 18.0)
    return is_live, round(float(laplacian), 1)

def _normalize_face(crop):
    size = (160, 160)
    resized = cv2.resize(crop, size)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    bilateral = cv2.bilateralFilter(gray, 7, 50, 50)
    eq = cv2.equalizeHist(bilateral)
    return eq

def compare_faces(doc_image: Image.Image, live_image: Image.Image):
    doc_res = detect_face(doc_image)
    live_res = detect_face(live_image)

    if not doc_res["found"] or not live_res["found"]:
        missing = "ID Document" if not doc_res["found"] else "Live Selfie"
        return {
            "match": False,
            "similarity": 0,
            "is_real_person": False,
            "status": "ALERT",
            "doc_box": doc_res.get("box"),
            "quality_issues": [f"Face portrait not clearly detected in {missing}"],
            "reason": f"Face portrait not clearly detected in {missing}. Please adjust lighting and face camera directly."
        }

    is_live, liveness_score = check_liveness(live_res["_crop"])

    # Quality Diagnostics
    doc_quality = assess_crop_quality(doc_res["_crop"], label="ID Card Portrait")
    live_quality = assess_crop_quality(live_res["_crop"], label="Live Selfie")
    all_quality_issues = doc_quality + live_quality

    g1 = _normalize_face(doc_res["_crop"])
    g2 = _normalize_face(live_res["_crop"])

    # 1. Zero-Mean Facial Core HOG (Isolates unique facial morphology from generic template)
    core1 = cv2.resize(g1[25:135, 20:140], (64, 64))
    core2 = cv2.resize(g2[25:135, 20:140], (64, 64))
    hog = cv2.HOGDescriptor((64, 64), (16, 16), (8, 8), (8, 8), 9)
    hc1 = hog.compute(core1).flatten()
    hc2 = hog.compute(core2).flatten()
    
    hc1_c = hc1 - np.mean(hc1)
    hc2_c = hc2 - np.mean(hc2)
    ident_hog = max(0.0, float(np.dot(hc1_c, hc2_c) / (np.linalg.norm(hc1_c) * np.linalg.norm(hc2_c) + 1e-6)))

    # 2. Key Feature Template Cross-Correlations on Eyes, Nose, Mouth
    eyes1 = g1[30:70, 25:135]
    nose1 = g1[60:100, 38:122]
    mouth1 = g1[90:130, 30:130]

    e_corr = max(0.0, float(np.max(cv2.matchTemplate(g2, eyes1, cv2.TM_CCOEFF_NORMED))))
    n_corr = max(0.0, float(np.max(cv2.matchTemplate(g2, nose1, cv2.TM_CCOEFF_NORMED))))
    m_corr = max(0.0, float(np.max(cv2.matchTemplate(g2, mouth1, cv2.TM_CCOEFF_NORMED))))
    template_corr = (e_corr * 0.40) + (n_corr * 0.35) + (m_corr * 0.25)

    # Combined Metric (Identity HOG 60%, Key Templates 40%)
    combined = (ident_hog * 0.60) + (template_corr * 0.40)

    # Calibrated Threshold:
    # Same Person: combined >= 0.38 -> 65% to 98% (MATCH)
    # Different Person: combined < 0.38 -> 15% to 48% (ALERT)
    if combined >= 0.38:
        similarity = int(65 + ((combined - 0.38) / 0.62) * 33)
    else:
        similarity = int((combined / 0.38) * 45)

    similarity = int(np.clip(similarity, 10, 98))
    is_match = (similarity >= 60) and is_live

    # Build descriptive diagnostic reason
    if is_match:
        reason = f"Live biometric match confirmed (Similarity: {similarity}%)"
    else:
        reasons = []
        if not is_live:
            reasons.append("Liveness check failed (Screen/Photo spoof suspected)")
        if similarity < 60:
            reasons.append(f"Biometric Mismatch ({similarity}%) — Issue: Facial bone structure & feature mismatch")
        if all_quality_issues:
            reasons.append(f"Diagnostic Warnings: {', '.join(all_quality_issues)}")
        reason = " | ".join(reasons)

    return {
        "match": is_match,
        "similarity": similarity,
        "is_real_person": is_live,
        "liveness_score": liveness_score,
        "doc_box": doc_res.get("box"),
        "quality_issues": all_quality_issues,
        "status": "MATCH" if is_match else "ALERT",
        "reason": reason
    }
