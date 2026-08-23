import cv2
import numpy as np

def inspect_edits():
    img_edit = cv2.imread("backend/uploads/DOC-1478.jpg")
    img_clean = cv2.imread("backend/uploads/DOC-1388.jpg")
    
    # Save side-by-side or difference image
    h, w = img_edit.shape[:2]
    print(f"Edit size: {w}x{h}")

    # Let's inspect where text fields are located in DOC-1478.jpg
    # E.g. Name, DOB, Aadhaar Number, Gender
    # Let's inspect crops:
    # 1. Top header
    # 2. Name zone (y: 20-35%, x: 35-70%)
    # 3. DOB zone (y: 35-50%, x: 35-70%)
    # 4. Aadhaar number zone (y: 70-85%, x: 30-75%)
    
    # Let's check text sharpness & noise in these crops
    crops = {
        "Name": img_edit[int(h*0.20):int(h*0.35), int(w*0.35):int(w*0.75)],
        "DOB": img_edit[int(h*0.35):int(h*0.48), int(w*0.35):int(w*0.75)],
        "Number": img_edit[int(h*0.68):int(h*0.85), int(w*0.25):int(w*0.80)],
        "Top": img_edit[0:int(h*0.20), int(w*0.20):int(w*0.80)]
    }

    for name, crop in crops.items():
        ch, cw = crop.shape[:2]
        cgray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        clap = cv2.Laplacian(cgray, cv2.CV_64F).var()
        
        cblur_sq = cv2.blur(cgray.astype(np.float32)**2, (5, 5))
        csq_blur = cv2.blur(cgray.astype(np.float32), (5, 5))**2
        clocal_std = np.sqrt(np.maximum(cblur_sq - csq_blur, 0))
        
        # Check for pure flat background around text (inserted text on clean white rectangle)
        chsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        _, cs, cv = cv2.split(chsv)
        flat_mask = (cv > 220) & (cs < 35) & (clocal_std < 2.5)
        flat_ratio = np.sum(flat_mask) / (ch * cw)

        print(f"Crop [{name}]: Laplacian={clap:.1f}, Mean Local STD={clocal_std.mean():.2f}, Flat Background Ratio={flat_ratio*100:.2f}%")

inspect_edits()
