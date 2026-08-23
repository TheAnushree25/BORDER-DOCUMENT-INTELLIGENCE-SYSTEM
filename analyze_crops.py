import cv2
import numpy as np

def analyze_crops():
    crop_pan_ujjwal = cv2.imread("test_crop_PAN_Ujjwal.jpg")
    crop_aadh_ujjwal = cv2.imread("test_crop_Aadhaar_Ujjwal.jpg")
    crop_aadh_anurag = cv2.imread("test_crop_Aadhaar_Anurag.jpg")

    def test_pair(name1, img1, name2, img2):
        print(f"\n--- Comparing {name1} vs {name2} ---")
        # Resize to 128x128
        i1 = cv2.resize(img1, (128, 128))
        i2 = cv2.resize(img2, (128, 128))
        
        g1 = cv2.cvtColor(i1, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(i2, cv2.COLOR_BGR2GRAY)
        
        # CLAHE histogram equalization
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        eq1 = clahe.apply(g1)
        eq2 = clahe.apply(g2)
        
        # 1. Structural similarity (SSIM approximation / Normalized Cross-Correlation)
        res_norm = cv2.matchTemplate(eq1, eq2, cv2.TM_CCOEFF_NORMED)[0][0]
        print(f"1. TM_CCOEFF_NORMED (CLAHE Grayscale): {res_norm:.4f}")
        
        # 2. Multi-scale search (scale +- 15%, translations +- 10px)
        best_tm = -1.0
        for s in [0.85, 0.90, 0.95, 1.0, 1.05, 1.10, 1.15]:
            nw, nh = int(128 * s), int(128 * s)
            res_s = cv2.resize(eq2, (nw, nh))
            # Pad or crop to 128x128
            if s < 1.0:
                canvas = np.full((128, 128), np.mean(res_s), dtype=np.uint8)
                ox, oy = (128 - nw) // 2, (128 - nh) // 2
                canvas[oy:oy+nh, ox:ox+nw] = res_s
                comp = canvas
            else:
                ox, oy = (nw - 128) // 2, (nh - 128) // 2
                comp = res_s[oy:oy+128, ox:ox+128]
            
            score = cv2.matchTemplate(eq1, comp, cv2.TM_CCOEFF_NORMED)[0][0]
            if score > best_tm:
                best_tm = score
        print(f"2. Multi-scale Best TM: {best_tm:.4f}")
        
        # 3. Normalized Gradients (Sobel)
        gx1 = cv2.Sobel(eq1, cv2.CV_32F, 1, 0)
        gy1 = cv2.Sobel(eq1, cv2.CV_32F, 0, 1)
        mag1 = cv2.magnitude(gx1, gy1)
        
        gx2 = cv2.Sobel(eq2, cv2.CV_32F, 1, 0)
        gy2 = cv2.Sobel(eq2, cv2.CV_32F, 0, 1)
        mag2 = cv2.magnitude(gx2, gy2)
        
        cv2.normalize(mag1, mag1, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(mag2, mag2, 0, 1, cv2.NORM_MINMAX)
        grad_score = cv2.matchTemplate(mag1, mag2, cv2.TM_CCOEFF_NORMED)[0][0]
        print(f"3. Sobel Gradient Match: {grad_score:.4f}")

        # 4. Center Crop (Eyes & Nose area: 25% to 75%)
        c1 = eq1[32:96, 32:96]
        c2 = eq2[32:96, 32:96]
        center_score = cv2.matchTemplate(c1, c2, cv2.TM_CCOEFF_NORMED)[0][0]
        print(f"4. Center Eyes/Nose Match: {center_score:.4f}")

        # 5. Color Histograms in HSV
        hsv1 = cv2.cvtColor(i1, cv2.COLOR_BGR2HSV)
        hsv2 = cv2.cvtColor(i2, cv2.COLOR_BGR2HSV)
        hist1 = cv2.calcHist([hsv1], [0, 1], None, [16, 16], [0, 180, 0, 256])
        hist2 = cv2.calcHist([hsv2], [0, 1], None, [16, 16], [0, 180, 0, 256])
        cv2.normalize(hist1, hist1, 0, 1, cv2.NORM_MINMAX)
        cv2.normalize(hist2, hist2, 0, 1, cv2.NORM_MINMAX)
        hsv_corr = cv2.compareHist(hist1, hist2, cv2.HISTCMP_CORREL)
        print(f"5. HSV Color Hist Correlation: {hsv_corr:.4f}")

    test_pair("PAN (Ujjwal)", crop_pan_ujjwal, "Aadhaar (Ujjwal) [SAME PERSON]", crop_aadh_ujjwal)
    test_pair("Aadhaar (Ujjwal)", crop_aadh_ujjwal, "Aadhaar (Anurag) [DIFFERENT PERSON]", crop_aadh_anurag)
    test_pair("PAN (Ujjwal)", crop_pan_ujjwal, "Aadhaar (Anurag) [DIFFERENT PERSON]", crop_aadh_anurag)

if __name__ == "__main__":
    analyze_crops()
