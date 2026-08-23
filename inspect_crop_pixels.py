import cv2
import numpy as np

img1 = cv2.imread("crop_right_top.jpg")
img2 = cv2.imread("crop_right_mid.jpg")
print("Crop 1 mean RGB:", img1.mean(axis=(0,1)), "min:", img1.min(), "max:", img1.max())
print("Crop 2 mean RGB:", img2.mean(axis=(0,1)), "min:", img2.min(), "max:", img2.max())
