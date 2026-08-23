import cv2

img = cv2.imread("backend/uploads/DOC-1478.jpg")
h, w = img.shape[:2]

# Crop 1: x=86.3%, y=13.0%, w=8.2%, h=3.6%
x1, y1, w1, h1 = int(w * 0.863), int(h * 0.130), int(w * 0.082), int(h * 0.036)
cv2.imwrite("crop_right_top.jpg", img[y1:y1+h1, x1:x1+w1])

# Crop 2: x=89.9%, y=36.6%, w=8.2%, h=2.2%
x2, y2, w2, h2 = int(w * 0.899), int(h * 0.366), int(w * 0.082), int(h * 0.022)
cv2.imwrite("crop_right_mid.jpg", img[y2:y2+h2, x2:x2+w2])

print("Crop 1 coords:", x1, y1, w1, h1)
print("Crop 2 coords:", x2, y2, w2, h2)
