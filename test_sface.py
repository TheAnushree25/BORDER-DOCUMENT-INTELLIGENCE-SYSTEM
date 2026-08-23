import os
import cv2
import numpy as np
from PIL import Image

MODELS_DIR = os.path.join(os.path.dirname(__file__), "backend", "models")
yunet_path = os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx")
sface_path = os.path.join(MODELS_DIR, "face_recognition_sface_2021dec.onnx")

detector = cv2.FaceDetectorYN.create(
    model=yunet_path,
    config="",
    input_size=(320, 320),
    score_threshold=0.6,
    nms_threshold=0.3,
    top_k=5000,
    backend_id=cv2.dnn.DNN_BACKEND_OPENCV,
    target_id=cv2.dnn.DNN_TARGET_CPU,
)

recognizer = cv2.FaceRecognizerSF.create(
    model=sface_path,
    config="",
    backend_id=cv2.dnn.DNN_BACKEND_OPENCV,
    target_id=cv2.dnn.DNN_TARGET_CPU,
)

def get_face_features(img_path):
    img = cv2.imread(img_path)
    h, w = img.shape[:2]
    detector.setInputSize((w, h))
    _, faces = detector.detect(img)
    if faces is None or len(faces) == 0:
        # Try CLAHE equalized image
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        eq = cv2.cvtColor(clahe.apply(gray), cv2.COLOR_GRAY2BGR)
        _, faces = detector.detect(eq)
        if faces is None or len(faces) == 0:
            print(f"No face detected in {img_path}")
            return None, None

    # Pick largest face
    best_face = max(faces, key=lambda f: f[2] * f[3])
    aligned = recognizer.alignCrop(img, best_face)
    feat = recognizer.feature(aligned)
    return best_face, feat

def test_sface():
    upload_dir = "backend/uploads"
    pan_path = os.path.join(upload_dir, "DOC-1386.jpg")
    aadh_ujjwal_path = os.path.join(upload_dir, "DOC-1388.jpg")
    aadh_anurag_path = os.path.join(upload_dir, "DOC-1390.jpg")

    f_pan, feat_pan = get_face_features(pan_path)
    f_aadh_u, feat_aadh_u = get_face_features(aadh_ujjwal_path)
    f_aadh_a, feat_aadh_a = get_face_features(aadh_anurag_path)

    print("\n" + "="*60)
    print("TESTING SOTA DEEP FACE VERIFICATION (OpenCV SFace)")
    print("="*60)

    # 1. Same Person (Ujjwal PAN vs Ujjwal Aadhaar)
    cos_same = recognizer.match(feat_pan, feat_aadh_u, cv2.FaceRecognizerSF_FR_COSINE)
    l2_same = recognizer.match(feat_pan, feat_aadh_u, cv2.FaceRecognizerSF_FR_NORM_L2)
    print(f"1. Same Person (Ujjwal PAN vs Ujjwal Aadhaar): Cosine = {cos_same:.4f}, L2 Dist = {l2_same:.4f}")

    # 2. Different Person (Ujjwal Aadhaar vs Anurag Aadhaar)
    cos_diff1 = recognizer.match(feat_aadh_u, feat_aadh_a, cv2.FaceRecognizerSF_FR_COSINE)
    l2_diff1 = recognizer.match(feat_aadh_u, feat_aadh_a, cv2.FaceRecognizerSF_FR_NORM_L2)
    print(f"2. Different Person (Ujjwal Aadhaar vs Anurag Aadhaar): Cosine = {cos_diff1:.4f}, L2 Dist = {l2_diff1:.4f}")

    # 3. Different Person (Ujjwal PAN vs Anurag Aadhaar)
    cos_diff2 = recognizer.match(feat_pan, feat_aadh_a, cv2.FaceRecognizerSF_FR_COSINE)
    l2_diff2 = recognizer.match(feat_pan, feat_aadh_a, cv2.FaceRecognizerSF_FR_NORM_L2)
    print(f"3. Different Person (Ujjwal PAN vs Anurag Aadhaar): Cosine = {cos_diff2:.4f}, L2 Dist = {l2_diff2:.4f}")

if __name__ == "__main__":
    test_sface()
