import cv2
import numpy as np
from PIL import Image, ImageChops
import io

def debug_1438_full():
    img = cv2.imread("backend/uploads/DOC-1438.jpg")
    h, w = img.shape[:2]
    
    # ELA
    pil_img = Image.open("backend/uploads/DOC-1438.jpg").convert("RGB")
    buf = io.BytesIO()
    pil_img.save(buf, "JPEG", quality=90)
    buf.seek(0)
    resaved = Image.open(buf)
    diff = ImageChops.difference(pil_img, resaved)
    diff_arr = np.asarray(diff).astype(np.float32)

    print("Diff min:", diff_arr.min(), "mean:", diff_arr.mean(), "max:", diff_arr.max())
    
    # Check pixels with diff > 4.0
    diff_mag = diff_arr.mean(axis=2)
    print("Pixels with diff > 4.0:", np.sum(diff_mag > 4.0))
    print("Pixels with diff > 6.0:", np.sum(diff_mag > 6.0))
    print("Pixels with diff > 8.0:", np.sum(diff_mag > 8.0))
    print("Pixels with diff > 10.0:", np.sum(diff_mag > 10.0))

    # Clean unedited comparison
    clean_pil = Image.open("backend/uploads/DOC-1388.jpg").convert("RGB")
    buf2 = io.BytesIO()
    clean_pil.save(buf2, "JPEG", quality=90)
    buf2.seek(0)
    clean_resaved = Image.open(buf2)
    clean_diff = ImageChops.difference(clean_pil, clean_resaved)
    clean_diff_arr = np.asarray(clean_diff).astype(np.float32)
    clean_diff_mag = clean_diff_arr.mean(axis=2)
    print("\nClean image diff > 4.0:", np.sum(clean_diff_mag > 4.0))
    print("Clean image diff > 6.0:", np.sum(clean_diff_mag > 6.0))
    print("Clean image diff > 8.0:", np.sum(clean_diff_mag > 8.0))
    print("Clean image diff > 10.0:", np.sum(clean_diff_mag > 10.0))

if __name__ == "__main__":
    debug_1438_full()
