import cv2
import numpy as np

img = cv2.imread("backend/uploads/DOC-1478.jpg")
h, w = img.shape[:2]

# Crop around x_pct: 13.6%, y_pct: 34.9%
fx = int(w * 0.136)
fy = int(h * 0.349)
fw = int(w * 0.104)
fh = int(h * 0.202)

crop = img[fy:fy+fh, fx:fx+fw]
cv2.imwrite("face_crop_detected.jpg", crop)
print(f"Face Box Coordinates: x={fx}, y={fy}, w={fw}, h={fh}")

# Find actual face in the card portrait
# In the card, the portrait is in the left side of the card (around x=30% of total image)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3)
print(f"Haar Faces found: {len(faces)}")
for (x, y, w_b, h_b) in faces:
    print(f"  Face at x={x} ({x/w*100:.1f}%), y={y} ({y/h*100:.1f}%), w={w_b} ({w_b/w*100:.1f}%), h={h_b} ({h_b/h*100:.1f}%)")

# Check YuNet detector
models_dir = "backend/models"
yunet_path = f"{models_dir}/face_detection_yunet_2023mar.onnx"
import os
if os.path.exists(yunet_path):
    yn = cv2.FaceDetectorYN.create(yunet_path, "", (w, h), score_threshold=0.3)
    _, yn_faces = yn.detect(img)
    if yn_faces is not None:
        print(f"YuNet Faces found: {len(yn_faces)}")
        for f in yn_faces:
            print(f"  YuNet Face: x={f[0]:.1f} ({f[0]/w*100:.1f}%), y={f[1]:.1f} ({f[1]/h*100:.1f}%), w={f[2]:.1f} ({f[2]/w*100:.1f}%), score={f[14]:.2f}")

