import cv2
import numpy as np

def inspect_1438():
    img = cv2.imread("backend/uploads/DOC-1438.jpg")
    h, w = img.shape[:2]
    print(f"DOC-1438 shape: {w}x{h}")
    
    # Check ELA with PIL
    from PIL import Image, ImageChops
    import io
    pil_img = Image.open("backend/uploads/DOC-1438.jpg").convert("RGB")
    buf = io.BytesIO()
    pil_img.save(buf, "JPEG", quality=90)
    buf.seek(0)
    resaved = Image.open(buf)
    diff = ImageChops.difference(pil_img, resaved)
    diff_arr = np.asarray(diff).astype(np.float32)
    
    print("ELA Mean:", diff_arr.mean())
    print("ELA Max:", diff_arr.max())
    print("ELA 99th percentile:", np.percentile(diff_arr, 99))
    
    # Find connected components of high-ELA pixels (> 8.0)
    high_ela = (diff_arr.mean(axis=2) > 6.0).astype(np.uint8) * 255
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(high_ela)
    print(f"High ELA connected components: {num_labels - 1}")
    for i in range(1, num_labels):
        area = stats[i, cv2.CC_STAT_AREA]
        if area > 100:
            x = stats[i, cv2.CC_STAT_LEFT]
            y = stats[i, cv2.CC_STAT_TOP]
            bw = stats[i, cv2.CC_STAT_WIDTH]
            bh = stats[i, cv2.CC_STAT_HEIGHT]
            print(f"Component {i}: area={area}, box=({x},{y},{bw},{bh})")

if __name__ == "__main__":
    inspect_1438()
