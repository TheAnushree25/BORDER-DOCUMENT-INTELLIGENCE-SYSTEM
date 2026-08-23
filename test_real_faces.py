import os
from PIL import Image
from backend.utils import face_match

def test_real_images():
    upload_dir = "backend/uploads"
    for fname in os.listdir(upload_dir):
        if fname.endswith(".jpg"):
            path = os.path.join(upload_dir, fname)
            try:
                img = Image.open(path)
                res = face_match.detect_face(img)
                if res["found"]:
                    print(f"File {fname}: Face FOUND! Box={res['box']}")
            except Exception as e:
                pass

if __name__ == "__main__":
    test_real_images()
