import cv2
import numpy as np
from PIL import Image

def test_whiteout_thresholds():
    files = [
        ("Clean Aadhaar", "backend/uploads/DOC-1388.jpg"),
        ("Clean PAN", "backend/uploads/DOC-1386.jpg"),
        ("Edited Whiteout", "backend/uploads/DOC-1430.jpg"),
        ("Edited Scribble", "backend/uploads/DOC-1438.jpg"),
    ]

    for label, path in files:
        img = cv2.imread(path)
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        _, s, v = cv2.split(hsv)
        
        # Calculate local std
        mean = cv2.blur(gray.astype(np.float32), (5, 5))
        sq_mean = cv2.blur((gray.astype(np.float32))**2, (5, 5))
        local_std = np.sqrt(np.maximum(0, sq_mean - mean**2))
        
        # Pure digital flat whiteout (V > 245, S < 18, local_std < 1.8)
        mask = (v > 245) & (s < 18) & (local_std < 1.8)
        pixels = int(np.sum(mask))
        ratio = pixels / (h * w)

        print(f"=== {label} ===")
        print(f"Pixels: {pixels} ({ratio*100:.2f}%)")

test_whiteout_thresholds()
