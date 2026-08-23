import sys

def check_modules():
    modules = ["cv2", "mediapipe", "face_recognition", "dlib", "deepface", "insightface", "onnxruntime", "torch", "torchvision", "sklearn"]
    for m in modules:
        try:
            mod = __import__(m)
            ver = getattr(mod, "__version__", "installed")
            print(f"[FOUND] {m}: {ver}")
        except ImportError:
            print(f"[MISSING] {m}")

    # Check OpenCV FaceDetectorYN / FaceRecognizerSF
    import cv2
    has_yn = hasattr(cv2, "FaceDetectorYN")
    has_sf = hasattr(cv2, "FaceRecognizerSF")
    print(f"OpenCV FaceDetectorYN: {has_yn}, FaceRecognizerSF: {has_sf}")

if __name__ == "__main__":
    check_modules()
