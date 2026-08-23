import os
import cv2
import numpy as np
from PIL import Image

def analyze_edited_images():
    files = ["DOC-1430.jpg", "DOC-1436.jpg", "DOC-1438.jpg", "DOC-1439.jpg"]
    upload_dir = "backend/uploads"
    
    for f in files:
        path = os.path.join(upload_dir, f)
        if not os.path.exists(path):
            continue
        print("="*60)
        print(f"FILE: {f} ({os.path.getsize(path)} bytes)")
        print("="*60)
        img_bgr = cv2.imread(path)
        h, w = img_bgr.shape[:2]
        print(f"Dimensions: {w}x{h}")
        
        # Check color channels and artifacts
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
        
        # 1. Laplacian variance (blurriness / sharpness transitions)
        lap = cv2.Laplacian(gray, cv2.CV_64F)
        print(f"Laplacian var: {lap.var():.2f}")
        
        # 2. Canny Edge Density
        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(np.sum(edges > 0)) / (h * w)
        print(f"Canny edge density: {edge_density:.4f}")
        
        # 3. Check for solid color rectangles / brush strokes (like drawing on top of photo)
        # Check local standard deviation in 8x8 blocks
        block_size = 16
        bh, bw = h // block_size, w // block_size
        low_var_blocks = 0
        high_grad_blocks = 0
        total_blocks = bh * bw
        
        for r in range(bh):
            for c in range(bw):
                blk = gray[r*block_size:(r+1)*block_size, c*block_size:(c+1)*block_size]
                v = np.var(blk)
                if v < 1.0: # Perfectly uniform synthetic patch
                    low_var_blocks += 1
                if v > 1500.0: # High contrast artificial edge
                    high_grad_blocks += 1
                    
        print(f"Uniform flat patches (synthetic overlay): {low_var_blocks}/{total_blocks} ({low_var_blocks/total_blocks*100:.1f}%)")
        print(f"High gradient anomaly patches: {high_grad_blocks}/{total_blocks} ({high_grad_blocks/total_blocks*100:.1f}%)")

        # 4. Check ELA distribution
        pil_img = Image.open(path).convert("RGB")
        import io
        from PIL import ImageChops
        buf = io.BytesIO()
        pil_img.save(buf, "JPEG", quality=90)
        buf.seek(0)
        resaved = Image.open(buf)
        diff = ImageChops.difference(pil_img, resaved)
        diff_np = np.asarray(diff).astype(np.float32)
        print(f"ELA Mean: {diff_np.mean():.4f}, Max: {diff_np.max():.4f}, Std: {diff_np.std():.4f}")

if __name__ == "__main__":
    analyze_edited_images()
