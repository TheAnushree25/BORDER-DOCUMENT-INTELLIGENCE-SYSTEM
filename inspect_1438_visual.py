import cv2
import numpy as np
from PIL import Image
from backend.utils import ocr

def inspect_1438_visual():
    img1388 = Image.open("backend/uploads/DOC-1388.jpg")
    img1438 = Image.open("backend/uploads/DOC-1438.jpg")
    print("1388 size:", img1388.size)
    print("1438 size:", img1438.size)

    # Let's inspect raw OCR on 1438
    t1438 = ocr.extract_text(img1438)
    t1388 = ocr.extract_text(img1388)
    print("--- 1388 OCR ---")
    print(t1388)
    print("--- 1438 OCR ---")
    print(t1438)

    # Check color histogram / digital pen strokes on 1438
    cv1438 = cv2.imread("backend/uploads/DOC-1438.jpg")
    hsv = cv2.cvtColor(cv1438, cv2.COLOR_BGR2HSV)
    h, s, v = cv2.split(hsv)
    
    # Check distinct color clusters (e.g. digital pen overlay)
    # Check for saturated pen pixels:
    # S > 100, V > 100, and non-skin tone / non-background
    # Aadhaar background is white/blue/orange
    # Any black/red/green/purple digital drawing:
    pen_mask = (s > 100) & (v > 100)
    print("Pen mask pixels (S>100 & V>100):", np.sum(pen_mask))
    
    # Check digital black/dark drawing strokes (V < 30)
    dark_mask = v < 30
    print("Dark strokes (V < 30):", np.sum(dark_mask))
    
    # High frequency gradient edges (Laplacian)
    gray = cv2.cvtColor(cv1438, cv2.COLOR_BGR2GRAY)
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    print("Laplacian Var on 1438:", lap.var())
    
    gray1388 = cv2.cvtColor(cv2.imread("backend/uploads/DOC-1388.jpg"), cv2.COLOR_BGR2GRAY)
    lap1388 = cv2.Laplacian(gray1388, cv2.CV_64F)
    print("Laplacian Var on 1388:", lap1388.var())

if __name__ == "__main__":
    inspect_1438_visual()
