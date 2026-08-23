import cv2
import numpy as np
from PIL import Image

def analyze_dob_patch():
    img = cv2.imread("backend/uploads/DOC-1478.jpg")
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    _, s_chan, v_chan = cv2.split(hsv)
    
    # Calculate local texture variance
    blur_sq = cv2.blur(gray.astype(np.float32)**2, (5, 5))
    sq_blur = cv2.blur(gray.astype(np.float32), (5, 5))**2
    local_std = np.sqrt(np.maximum(blur_sq - sq_blur, 0))
    
    # Solid flat patch (V > 235, S < 25, local_std < 2.5)
    solid_mask = (v_chan > 235) & (s_chan < 25) & (local_std < 2.5)
    flat_pixels = int(np.sum(solid_mask))
    print(f"Total flat pixels in image: {flat_pixels} ({flat_pixels/(h*w)*100:.3f}%)")
    
    # Find contours
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    dilated = cv2.dilate(solid_mask.astype(np.uint8), kernel, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    print(f"Total contours found: {len(contours)}")
    for i, cnt in enumerate(contours):
        area = cv2.contourArea(cnt)
        if area > 300: # Text patch threshold
            bx, by, bw, bh = cv2.boundingRect(cnt)
            print(f"Altered text contour #{i}: x={bx} ({bx/w*100:.1f}%), y={by} ({by/h*100:.1f}%), w={bw} ({bw/w*100:.1f}%), h={bh} ({bh/h*100:.1f}%), area={area}")

analyze_dob_patch()
print("\n--- Clean Aadhaar DOC-1388 ---")
def analyze_clean():
    img = cv2.imread("backend/uploads/DOC-1388.jpg")
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    _, s_chan, v_chan = cv2.split(hsv)
    blur_sq = cv2.blur(gray.astype(np.float32)**2, (5, 5))
    sq_blur = cv2.blur(gray.astype(np.float32), (5, 5))**2
    local_std = np.sqrt(np.maximum(blur_sq - sq_blur, 0))
    solid_mask = (v_chan > 235) & (s_chan < 25) & (local_std < 2.5)
    flat_pixels = int(np.sum(solid_mask))
    print(f"Total flat pixels in clean image: {flat_pixels} ({flat_pixels/(h*w)*100:.3f}%)")
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))
    dilated = cv2.dilate(solid_mask.astype(np.uint8), kernel, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for i, cnt in enumerate(contours):
        area = cv2.contourArea(cnt)
        if area > 300:
            bx, by, bw, bh = cv2.boundingRect(cnt)
            print(f"Clean contour #{i}: x={bx}, y={by}, w={bw}, h={bh}, area={area}")
analyze_clean()
