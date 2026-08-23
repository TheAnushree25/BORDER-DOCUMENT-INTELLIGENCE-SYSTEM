import os
import cv2
import numpy as np
from PIL import Image

def compare_clean_vs_edited():
    upload_dir = "backend/uploads"
    clean_aadh = os.path.join(upload_dir, "DOC-1388.jpg")
    edited_aadh_1 = os.path.join(upload_dir, "DOC-1430.jpg")
    edited_aadh_2 = os.path.join(upload_dir, "DOC-1438.jpg")

    def inspect(path, label):
        print("="*60)
        print(f"{label}: {os.path.basename(path)}")
        img = cv2.imread(path)
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 1. Check local variance in 8x8 blocks
        # Natural photographs have sensor noise/paper texture (variance >= 2.0).
        # Digital brush/eraser/whiteout/copy-paste patches have variance < 1.0.
        bs = 8
        bh, bw = h // bs, w // bs
        flat_blocks = 0
        total_blocks = bh * bw
        for r in range(bh):
            for c in range(bw):
                patch = gray[r*bs:(r+1)*bs, c*bs:(c+1)*bs]
                if np.var(patch) < 1.5:
                    flat_blocks += 1
        flat_ratio = flat_blocks / total_blocks
        print(f"Flat synthetic patches (<1.5 var): {flat_blocks}/{total_blocks} ({flat_ratio*100:.2f}%)")

        # 2. Check localized high-gradient sharp edges (drawing lines / synthetic boxes)
        # Sobel gradient
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        mag = cv2.magnitude(gx, gy)
        sharp_pixels = np.sum(mag > 120)
        sharp_ratio = sharp_pixels / (h * w)
        print(f"Sharp unnatural gradient pixels (>120): {sharp_pixels} ({sharp_ratio*100:.2f}%)")

        # 3. High color saturation patches / pure colors (digital markers)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h_c, s_c, v_c = cv2.split(hsv)
        marker_pixels = np.sum((s_c > 180) & (v_c > 180)) # Neon / pure digital pen colors
        whiteout_pixels = np.sum((v_c > 248) & (s_c < 10)) # Digital white brush
        blackout_pixels = np.sum(v_c < 10) # Digital black brush
        print(f"Digital pen / pure color pixels: {marker_pixels} ({marker_pixels/(h*w)*100:.2f}%)")
        print(f"Digital whiteout brush pixels: {whiteout_pixels} ({whiteout_pixels/(h*w)*100:.2f}%)")
        print(f"Digital blackout brush pixels: {blackout_pixels} ({blackout_pixels/(h*w)*100:.2f}%)")

        # 4. ELA Hotspots (6x6 Grid)
        pil_img = Image.open(path).convert("RGB")
        import io
        from PIL import ImageChops
        buf = io.BytesIO()
        pil_img.save(buf, "JPEG", quality=90)
        buf.seek(0)
        resaved = Image.open(buf)
        diff = ImageChops.difference(pil_img, resaved)
        diff_arr = np.asarray(diff).astype(np.float32)
        print(f"ELA mean: {diff_arr.mean():.4f}, ELA max: {diff_arr.max():.4f}")

    inspect(clean_aadh, "CLEAN UNEDITED DOCUMENT")
    inspect(edited_aadh_1, "USER EDITED DOCUMENT 1")
    inspect(edited_aadh_2, "USER EDITED DOCUMENT 2")

if __name__ == "__main__":
    compare_clean_vs_edited()
