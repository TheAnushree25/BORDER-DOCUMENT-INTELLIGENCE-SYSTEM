import cv2
import numpy as np

def compare():
    img_clean = cv2.imread("backend/uploads/DOC-1388.jpg")
    img_edit = cv2.imread("backend/uploads/DOC-1478.jpg")
    
    print("Clean shape:", img_clean.shape)
    print("Edit shape:", img_edit.shape)
    
    if img_clean.shape != img_edit.shape:
        img_edit_res = cv2.resize(img_edit, (img_clean.shape[1], img_clean.shape[0]))
    else:
        img_edit_res = img_edit
        
    diff = cv2.absdiff(img_clean, img_edit_res)
    gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    
    thresh = cv2.threshold(gray_diff, 20, 255, cv2.THRESH_BINARY)[1]
    num_diff_pixels = np.sum(thresh > 0)
    print(f"Different pixels (>20 intensity difference): {num_diff_pixels}")
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    print(f"Number of difference contours: {len(contours)}")
    for i, c in enumerate(contours):
        area = cv2.contourArea(c)
        if area > 100:
            x, y, w, h = cv2.boundingRect(c)
            print(f"Diff Zone #{i}: x={x}, y={y}, w={w}, h={h}, area={area}")

compare()
