import cv2
import numpy as np
from PIL import Image, ImageChops
import io
import json
from backend.utils import ocr, document_extractor

def inspect_image(path):
    print(f"=== INSPECTING: {path} ===")
    img_bgr = cv2.imread(path)
    h, w = img_bgr.shape[:2]
    print(f"Dimensions: {w}x{h}")
    
    # 1. OCR text
    ocr_lines = ocr.extract_text(Image.open(path))
    print(f"OCR Extracted ({len(ocr_lines)} lines):")
    for l in ocr_lines:
        print("  >", l)
        
    doc_type = document_extractor.classify_document(ocr_lines)
    extracted = document_extractor.extract_fields(ocr_lines, doc_type)
    print(f"Doc Type: {doc_type}")
    print(f"Extracted: {extracted}")

    # 2. ELA analysis
    pil_img = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    pil_img.save(buf, "JPEG", quality=90)
    buf.seek(0)
    resaved = Image.open(buf)
    diff = ImageChops.difference(pil_img, resaved)
    diff_arr = np.asarray(diff).astype(np.float32)
    diff_mean = diff_arr.mean()
    diff_max = diff_arr.max()
    print(f"\nELA mean: {diff_mean:.2f}, max: {diff_max:.2f}")

    # 3. HSV / Luminance
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    _, s_chan, v_chan = cv2.split(hsv)
    
    # Laplacian & Sobel
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    print(f"Laplacian var: {lap.var():.2f}")

    # High frequency / local std
    blur_sq = cv2.blur(gray.astype(np.float32)**2, (7, 7))
    sq_blur = cv2.blur(gray.astype(np.float32), (7, 7))**2
    local_std = np.sqrt(np.maximum(blur_sq - sq_blur, 0))
    print(f"Local std mean: {local_std.mean():.2f}, min: {local_std.min():.2f}, max: {local_std.max():.2f}")
    
    # 4. Check for pure digital text overlays or color differences in text
    # In text edited photo: often text is inserted with pure black or digital font, or patched with solid color background
    # Let's check text box regions
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    cl1 = clahe.apply(gray)
    
    # Let's check pixel distributions for pasted text/boxes
    # Let's inspect where differences occur compared to a normal Aadhaar/PAN
    print("\nLocal std histogram in high brightness:")
    white_mask = (v_chan > 230) & (s_chan < 40)
    print(f"White mask count: {np.sum(white_mask)} ({np.sum(white_mask)/(h*w)*100:.2f}%)")
    print(f"White mask local_std < 2.5: {np.sum((white_mask) & (local_std < 2.5))}")
    print(f"White mask local_std < 3.5: {np.sum((white_mask) & (local_std < 3.5))}")
    print(f"White mask local_std < 5.0: {np.sum((white_mask) & (local_std < 5.0))}")

    # Check 8x8 grid ELA variances
    ela_gray = cv2.cvtColor(diff_arr.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    grid = 8
    gh, gw = h // grid, w // grid
    cell_variances = []
    for r in range(grid):
        row_str = []
        for c in range(grid):
            cell = ela_gray[r * gh:(r + 1) * gh, c * gw:(c + 1) * gw]
            v = float(np.var(cell))
            cell_variances.append(v)
            row_str.append(f"{v:5.1f}")
        print("  ELA Grid row:", " ".join(row_str))
    print(f"Grid ELA mean: {np.mean(cell_variances):.2f}, std: {np.std(cell_variances):.2f}, max: {np.max(cell_variances):.2f}")

if __name__ == "__main__":
    inspect_image("backend/uploads/DOC-1478.jpg")
