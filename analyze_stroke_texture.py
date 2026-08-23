import os
import cv2
import numpy as np
from PIL import Image

def analyze_stroke_texture():
    upload_dir = "backend/uploads"
    clean_aadh = os.path.join(upload_dir, "DOC-1388.jpg")
    clean_pan = os.path.join(upload_dir, "DOC-1386.jpg")
    edited_whiteout = os.path.join(upload_dir, "DOC-1430.jpg")
    edited_scribble = os.path.join(upload_dir, "DOC-1438.jpg")

    def test_img(path, name):
        img = cv2.imread(path)
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 1. Pure digital whiteout patch (V > 248 with local std < 1.5)
        # Calculate local standard deviation using 5x5 blur
        mean = cv2.blur(gray.astype(np.float32), (5, 5))
        sq_mean = cv2.blur((gray.astype(np.float32))**2, (5, 5))
        local_std = np.sqrt(np.maximum(0, sq_mean - mean**2))
        
        # Digital flat whiteout: brightness > 245 AND local_std < 1.8
        digital_whiteout = (gray > 245) & (local_std < 1.8)
        num_whiteout = np.sum(digital_whiteout)
        
        # Digital flat colored scribble: high saturation AND local_std < 2.0
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        s = hsv[:, :, 1]
        v = hsv[:, :, 2]
        digital_scribble = (s > 120) & (v > 120) & (local_std < 2.0)
        num_scribble = np.sum(digital_scribble)
        
        print(f"=== {name} ===")
        print(f"Digital flat whiteout pixels: {num_whiteout} ({num_whiteout/(h*w)*100:.2f}%)")
        print(f"Digital flat scribble pixels: {num_scribble} ({num_scribble/(h*w)*100:.2f}%)")

    test_img(clean_aadh, "Clean Aadhaar (DOC-1388)")
    test_img(clean_pan, "Clean PAN (DOC-1386)")
    test_img(edited_whiteout, "Edited Whiteout (DOC-1430)")
    test_img(edited_scribble, "Edited Scribble (DOC-1438)")

if __name__ == "__main__":
    analyze_stroke_texture()
