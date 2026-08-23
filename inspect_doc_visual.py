import cv2
import numpy as np
from PIL import Image

def analyze_image(path):
    img = cv2.imread(path)
    h, w = img.shape[:2]
    print(f"Path: {path}, Size: {w}x{h}")
    
    # Save a copy as png or inspect text regions
    # Let's check text sharpness, compression, color histograms
    # In a text edited photo, someone used a photo editor (like Photoshop/phone editor)
    # to type text over an existing ID card or edit text fields.
    
    # Let's inspect differences across channels
    b, g, r = cv2.split(img)
    
    # Check text edges:
    # Digital text font rendered on an image has sharp unnatural edges:
    # Let's do Canny edge detection
    edges = cv2.Canny(img, 100, 200)
    print("Edge density:", np.sum(edges > 0) / (h * w))

    # Let's find contours of text characters
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print("Number of edge contours:", len(contours))

analyze_image("backend/uploads/DOC-1478.jpg")
