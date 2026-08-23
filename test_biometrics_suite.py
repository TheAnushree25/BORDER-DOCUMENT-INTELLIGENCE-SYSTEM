import cv2
import numpy as np
from PIL import Image, ImageDraw
from backend.utils import face_match, document_extractor

def create_synthetic_face(skin_color=(235, 200, 175), eye_color=(40, 40, 40)):
    img = Image.new("RGB", (300, 300), color=(245, 245, 250))
    draw = ImageDraw.Draw(img)
    # Head contour
    draw.ellipse([50, 40, 250, 260], fill=skin_color, outline=(30, 30, 30), width=3)
    # Hair
    draw.chord([45, 30, 255, 140], start=180, end=360, fill=(30, 25, 20))
    # Eyes
    draw.ellipse([85, 110, 125, 135], fill=(255, 255, 255), outline=(30, 30, 30), width=2)
    draw.ellipse([98, 115, 118, 130], fill=eye_color)
    draw.ellipse([175, 110, 215, 135], fill=(255, 255, 255), outline=(30, 30, 30), width=2)
    draw.ellipse([182, 115, 202, 130], fill=eye_color)
    # Nose
    draw.polygon([(150, 130), (140, 175), (160, 175)], fill=(skin_color[0]-25, skin_color[1]-25, skin_color[2]-25))
    # Mouth
    draw.arc([110, 185, 190, 225], start=0, end=180, fill=(160, 40, 40), width=4)
    return img

def test_biometrics():
    print("========================================")
    print("TESTING BIOMETRIC FACE VERIFICATION")
    print("========================================")

    face_a = create_synthetic_face(skin_color=(240, 210, 185))
    face_a_selfie = create_synthetic_face(skin_color=(238, 208, 182))
    face_b = create_synthetic_face(skin_color=(160, 110, 80), eye_color=(20, 20, 80))

    det_a = face_match.detect_face(face_a)
    print(f"Face A Detected: {det_a['found']} | Box: {det_a['box']}")
    assert det_a["found"], "Face A must be detected"

    # 1. Matching faces
    res_match = face_match.compare_faces(face_a, face_a_selfie)
    print(f"Same Person Match: {res_match['match']} | Similarity: {res_match['similarity']}% | Reason: {res_match['reason']}")
    assert res_match["match"] is True, "Same person should match"
    assert res_match["similarity"] >= 50, "Similarity should be >= 50%"

    print("\n[OK] Biometric Facial Verification Test Passed with flying colors!")

if __name__ == "__main__":
    test_biometrics()
