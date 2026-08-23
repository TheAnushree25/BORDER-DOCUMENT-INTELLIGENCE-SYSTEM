import os
import urllib.request
import cv2
import numpy as np

MODELS_DIR = os.path.join(os.path.dirname(__file__), "backend", "models")
os.makedirs(MODELS_DIR, exist_ok=True)

YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

yunet_path = os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx")
sface_path = os.path.join(MODELS_DIR, "face_recognition_sface_2021dec.onnx")

def download_models():
    print(f"Downloading YuNet to {yunet_path}...")
    if not os.path.exists(yunet_path) or os.path.getsize(yunet_path) < 100000:
        urllib.request.urlretrieve(YUNET_URL, yunet_path)
    print(f"[OK] YuNet size: {os.path.getsize(yunet_path)} bytes")

    print(f"Downloading SFace to {sface_path}...")
    if not os.path.exists(sface_path) or os.path.getsize(sface_path) < 500000:
        urllib.request.urlretrieve(SFACE_URL, sface_path)
    print(f"[OK] SFace size: {os.path.getsize(sface_path)} bytes")

if __name__ == "__main__":
    download_models()
