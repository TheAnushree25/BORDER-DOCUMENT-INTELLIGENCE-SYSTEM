import cv2
import numpy as np
from PIL import Image, ImageChops
import io

def analyze_forensics(path):
    img = cv2.imread(path)
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h_c, s_c, v_c = cv2.split(hsv)
    
    # 1. ELA
    pil_img = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    pil_img.save(buf, "JPEG", quality=90)
    buf.seek(0)
    resaved = Image.open(buf)
    diff = ImageChops.difference(pil_img, resaved)
    diff_arr = np.asarray(diff).astype(np.float32)
    ela_gray = cv2.cvtColor(diff_arr.astype(np.uint8), cv2.COLOR_RGB2GRAY)
    
    print(f"=== {path} ===")
    print("ELA Mean:", diff_arr.mean())
    print("ELA Max:", diff_arr.max())
    print("ELA 99th percentile:", np.percentile(diff_arr, 99))
    
    # 2. Local variance / microtexture
    blur_sq = cv2.blur(gray.astype(np.float32)**2, (7, 7))
    sq_blur = cv2.blur(gray.astype(np.float32), (7, 7))**2
    local_std = np.sqrt(np.maximum(blur_sq - sq_blur, 0))
    print("Local STD Mean:", local_std.mean())
    print("Local STD Min:", local_std.min())
    
    # Check text edges and high-contrast digital text
    # In digitally typed text on an image (e.g. Photoshop / Canva / MS Paint text tool),
    # text characters have perfectly sharp pixel transitions or anti-aliased font edges with zero sensor noise
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobely = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    sobel_mag = np.sqrt(sobelx**2 + sobely**2)
    
    print("Sobel Mag Mean:", sobel_mag.mean())
    print("Sobel Mag 95th pct:", np.percentile(sobel_mag, 95))
    print("Sobel Mag 99th pct:", np.percentile(sobel_mag, 99))

    # Check Laplacian
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    print("Laplacian Var:", lap.var())

    # Check color uniformity in text background / boxes
    # Often an edited text area has a bounding box or uniform colored rectangle placed behind the text
    # Let's check 16x16 grid variance of local_std and ELA
    grid = 8
    gh, gw = h // grid, w // grid
    for r in range(grid):
        row_ela = []
        row_std = []
        for c in range(grid):
            cell_ela = ela_gray[r * gh:(r + 1) * gh, c * gw:(c + 1) * gw]
            cell_std = local_std[r * gh:(r + 1) * gh, c * gw:(c + 1) * gw]
            row_ela.append(f"{np.var(cell_ela):5.1f}")
            row_std.append(f"{np.mean(cell_std):4.1f}")
        print(f"Row {r} ELA Var: " + " ".join(row_ela))
        print(f"Row {r} STD Mean: " + " ".join(row_std))

analyze_forensics("backend/uploads/DOC-1478.jpg")
print("\n--- Compare with Clean Aadhaar DOC-1388 ---")
analyze_forensics("backend/uploads/DOC-1388.jpg")
