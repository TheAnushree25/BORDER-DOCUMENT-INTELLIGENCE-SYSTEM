import os
from PIL import Image, ImageDraw, ImageFont

TEST_DIR = os.path.join(os.path.dirname(__file__), "test_samples")
os.makedirs(TEST_DIR, exist_ok=True)

def create_pan_sample():
    # Standard PAN Card dimensions: 850 x 540
    img = Image.new("RGB", (850, 540), color="#e0f2fe")
    draw = ImageDraw.Draw(img)

    # Top Header
    draw.rectangle([(0, 0), (850, 80)], fill="#0284c7")
    draw.text((220, 15), "INCOME TAX DEPARTMENT", fill="#ffffff")
    draw.text((260, 45), "GOVT. OF INDIA", fill="#ffffff")

    # Emblem placeholder
    draw.rectangle([(30, 20), (80, 70)], fill="#0369a1")

    # Photo Box
    draw.rectangle([(50, 120), (220, 320)], fill="#ffffff", outline="#64748b", width=2)
    draw.ellipse([(90, 150), (180, 240)], fill="#94a3b8")
    draw.rectangle([(70, 245), (200, 315)], fill="#475569")

    # PAN Details
    draw.text((260, 110), "Permanent Account Number", fill="#475569")
    draw.text((260, 140), "ABCDE1234F", fill="#0f172a")

    draw.text((260, 190), "Name", fill="#64748b")
    draw.text((260, 215), "UJJWAL GOND", fill="#0f172a")

    draw.text((260, 265), "Father's Name", fill="#64748b")
    draw.text((260, 290), "RAMESH GOND", fill="#0f172a")

    draw.text((260, 340), "Date of Birth", fill="#64748b")
    draw.text((260, 365), "02/02/2006", fill="#0f172a")

    # Signature box
    draw.rectangle([(50, 360), (220, 440)], fill="#ffffff", outline="#94a3b8")
    draw.text((80, 390), "Ujjwal Gond", fill="#1e293b")

    path = os.path.join(TEST_DIR, "sample_pancard.jpg")
    img.save(path, quality=95)
    print(f"Created PAN Card sample: {path}")
    return path

def create_aadhaar_sample():
    img = Image.new("RGB", (850, 540), color="#ffffff")
    draw = ImageDraw.Draw(img)

    # Tricolor top
    draw.rectangle([(0, 0), (850, 15)], fill="#ff9933")
    draw.rectangle([(0, 15), (850, 30)], fill="#ffffff")
    draw.rectangle([(0, 30), (850, 45)], fill="#138808")

    # Header
    draw.text((220, 60), "भारत सरकार / Government of India", fill="#000000")
    draw.text((200, 85), "Unique Identification Authority of India", fill="#333333")

    # Photo Box
    draw.rectangle([(50, 140), (220, 350)], fill="#f1f5f9", outline="#94a3b8", width=2)
    draw.ellipse([(90, 170), (180, 260)], fill="#cbd5e1")
    draw.rectangle([(70, 265), (200, 345)], fill="#64748b")

    # Biographical details
    draw.text((260, 150), "Name: UJJWAL GOND", fill="#000000")
    draw.text((260, 200), "DOB: 02/02/2006", fill="#000000")
    draw.text((260, 250), "Gender: MALE", fill="#000000")

    # Aadhaar Number
    draw.rectangle([(250, 340), (750, 410)], fill="#f8fafc", outline="#cbd5e1")
    draw.text((320, 360), "5489 7621 7245", fill="#dc2626")

    # Footer
    draw.rectangle([(0, 490), (850, 540)], fill="#dc2626")
    draw.text((280, 505), "मेरा आधार, मेरी पहचान", fill="#ffffff")

    path = os.path.join(TEST_DIR, "sample_aadhaar.jpg")
    img.save(path, quality=95)
    print(f"Created Aadhaar sample: {path}")
    return path

if __name__ == "__main__":
    create_pan_sample()
    create_aadhaar_sample()
