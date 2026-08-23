import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

def create_sample_id():
    w, h = 800, 520
    img = Image.new("RGB", (w, h), color=(245, 245, 248))
    draw = ImageDraw.Draw(img)

    # Passport Header
    draw.rectangle([0, 0, w, 70], fill=(20, 35, 60))
    draw.text((25, 20), "PASSPORT / PASSEPORT", fill=(255, 255, 255))
    draw.text((w - 200, 20), "REPUBLIC OF INDIA", fill=(220, 220, 240))

    # Face photo box
    face_box = [40, 90, 220, 310]
    draw.rectangle(face_box, fill=(210, 220, 230), outline=(80, 100, 130), width=2)

    # Draw an approximate face representation
    # Head
    draw.ellipse([80, 120, 180, 230], fill=(240, 195, 160))
    # Eyes
    draw.ellipse([100, 160, 115, 172], fill=(40, 40, 40))
    draw.ellipse([145, 160, 160, 172], fill=(40, 40, 40))
    # Nose
    draw.line([130, 168, 130, 190], fill=(180, 130, 100), width=2)
    # Mouth
    draw.arc([115, 195, 145, 212], 0, 180, fill=(160, 50, 50), width=2)
    # Hair
    draw.pieslice([80, 110, 180, 170], 180, 360, fill=(30, 25, 20))
    # Shoulders
    draw.pieslice([45, 225, 215, 340], 180, 360, fill=(40, 70, 120))

    # Details
    labels = [
        ("Type / Type", "P", 260, 95),
        ("Country Code / Code du pays", "IND", 450, 95),
        ("Passport No. / No du passeport", "R1234567", 600, 95),
        ("Surname / Nom", "YADAV", 260, 145),
        ("Given Names / Prenoms", "ABHISHEK", 260, 190),
        ("Nationality / Nationalite", "INDIAN", 260, 235),
        ("Date of Birth / Date de naissance", "12/04/2004", 450, 235),
        ("Sex / Sexe", "M", 600, 235),
        ("Date of Expiry / Date d'expiration", "09/05/2032", 450, 280),
    ]

    for lbl, val, x, y in labels:
        draw.text((x, y), lbl, fill=(120, 130, 150))
        draw.text((x, y + 16), val, fill=(10, 20, 40))

    # MRZ Zone
    draw.rectangle([0, 390, w, h], fill=(235, 238, 242), outline=(180, 190, 205), width=1)
    
    line1 = "P<INDYADAV<<ABHISHEK<<<<<<<<<<<<<<<<<<<<<<<"
    line2 = "R1234567<5IND0404125M3205091<<<<<<<<<<<<<<02"

    # Draw MRZ Text
    draw.text((30, 410), line1, fill=(0, 0, 0))
    draw.text((30, 455), line2, fill=(0, 0, 0))

    os.makedirs("test_samples", exist_ok=True)
    out_path = os.path.join("test_samples", "sample_passport.jpg")
    img.save(out_path, "JPEG", quality=95)
    print(f"Generated sample passport at: {out_path}")
    return out_path

if __name__ == "__main__":
    create_sample_id()
