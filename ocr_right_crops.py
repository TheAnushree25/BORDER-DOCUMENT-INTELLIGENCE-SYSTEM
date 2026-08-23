import cv2
from rapidocr_onnxruntime import RapidOCR

ocr = RapidOCR()
res1, _ = ocr("crop_right_top.jpg")
res2, _ = ocr("crop_right_mid.jpg")
print("Crop 1 (Top Right) OCR:", res1)
print("Crop 2 (Mid Right) OCR:", res2)
