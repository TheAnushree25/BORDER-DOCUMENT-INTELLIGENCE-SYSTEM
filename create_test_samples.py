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

    # Aadhaar Number (ends in a valid Verhoeff check digit, like real Aadhaar numbers)
    draw.rectangle([(250, 340), (750, 410)], fill="#f8fafc", outline="#cbd5e1")
    draw.text((320, 360), "5489 7621 7244", fill="#dc2626")

    # Footer
    draw.rectangle([(0, 490), (850, 540)], fill="#dc2626")
    draw.text((280, 505), "मेरा आधार, मेरी पहचान", fill="#ffffff")

    path = os.path.join(TEST_DIR, "sample_aadhaar.jpg")
    img.save(path, quality=95)
    print(f"Created Aadhaar sample: {path}")
    return path

def _font(names, size):
    """First TrueType font found (Windows, then Linux), else Pillow's bundled font; None if a script is unavailable."""
    for name in names:
        for folder in ("C:/Windows/Fonts", "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/noto"):
            try:
                return ImageFont.truetype(os.path.join(folder, name), size)
            except OSError:
                continue
    return None


def create_aadhaar_photo_samples(seed=7):
    """
    A camera-photo-like Aadhaar card (blur, sensor noise, uneven light, JPEG) and the same photo with the English
    name painted over and retyped in an image editor - the case the altered-text detector looks for.
    """
    import io
    import numpy as np
    from PIL import ImageFilter

    rng = np.random.default_rng(seed)
    s = 1.5  # card rendered at 1284 x 810
    latin = lambda size: _font(["arial.ttf", "DejaVuSans.ttf"], int(size * s)) or ImageFont.load_default(int(size * s))
    latin_bold = lambda size: _font(["arialbd.ttf", "DejaVuSans-Bold.ttf"], int(size * s)) or latin(size)
    hindi = lambda size: _font(["Nirmala.ttc", "NotoSansDevanagari-Regular.ttf"], int(size * s))

    card = Image.new("RGB", (int(856 * s), int(540 * s)), (252, 252, 250))
    d = ImageDraw.Draw(card)
    d.rectangle([0, 0, card.width, int(18 * s)], fill=(255, 153, 51))
    d.rectangle([0, int(36 * s), card.width, int(54 * s)], fill=(19, 136, 8))
    d.text((int(250 * s), int(98 * s)), "Government of India", font=latin_bold(22), fill=(20, 20, 20))
    if hindi(24):
        d.text((int(250 * s), int(64 * s)), "भारत सरकार", font=hindi(26), fill=(20, 20, 20))
        d.text((int(240 * s), int(160 * s)), "राहुल वर्मा", font=hindi(24), fill=(15, 15, 15))
    # portrait placeholder
    d.rectangle([int(40 * s), int(150 * s), int(210 * s), int(370 * s)], fill=(225, 230, 236))
    d.ellipse([int(78 * s), int(180 * s), int(172 * s), int(300 * s)], fill=(214, 170, 140))
    d.rectangle([int(54 * s), int(310 * s), int(196 * s), int(370 * s)], fill=(40, 70, 120))
    name_xy = (int(240 * s), int(198 * s))
    d.text(name_xy, "Rahul Verma", font=latin(24), fill=(15, 15, 15))
    d.text((int(240 * s), int(240 * s)), "DOB: 14/08/1998", font=latin(22), fill=(15, 15, 15))
    d.text((int(240 * s), int(278 * s)), "MALE", font=latin(22), fill=(15, 15, 15))
    d.text((int(290 * s), int(420 * s)), "4182 7350 9126", font=latin_bold(40), fill=(10, 10, 10))
    d.rectangle([0, int(492 * s), card.width, int(500 * s)], fill=(200, 30, 40))
    name_box = d.textbbox(name_xy, "Rahul Verma", font=latin(24))

    # simulated phone photo: paper texture, lens blur, uneven light, sensor noise, camera JPEG
    a = np.asarray(card).astype(np.float32)
    h, w = a.shape[:2]
    tex = Image.fromarray(rng.normal(128, 40, (h // 4 + 1, w // 4 + 1)).clip(0, 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    a += ((np.asarray(tex).astype(np.float32) - 128) / 40 * 2.5)[..., None]
    a = np.asarray(Image.fromarray(a.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.0))).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    a *= (1.0 - 0.18 * (((xx / w) - 0.3) ** 2 + ((yy / h) - 0.4) ** 2))[..., None]
    a += rng.normal(0, 4.0, (h, w, 1)) + rng.normal(0, 2.0, a.shape)
    buf = io.BytesIO()
    Image.fromarray(a.clip(0, 255).astype(np.uint8)).save(buf, "JPEG", quality=88)
    photo = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
    photo.save(os.path.join(TEST_DIR, "sample_aadhaar_photo.jpg"), quality=92)

    # the forgery: colour-picked box over the name, new name typed on top, saved from the editor
    edited = photo.copy()
    x0, y0, x1, y1 = name_box
    pad = (y1 - y0) // 4
    px = np.asarray(photo)[y0 - 3 * pad:y1 + 3 * pad, x1 + pad:x1 + 8 * pad].reshape(-1, 3)
    ImageDraw.Draw(edited).rectangle([x0 - pad, y0 - pad, x1 + pad, y1 + pad], fill=tuple(int(v) for v in np.median(px, axis=0)))
    ImageDraw.Draw(edited).text(name_xy, "Aman Gupta", font=latin(24), fill=(20, 20, 20))
    edited.save(os.path.join(TEST_DIR, "sample_aadhaar_edited_name.jpg"), quality=92)
    print("Created Aadhaar photo samples (genuine + edited name)")


if __name__ == "__main__":
    create_pan_sample()
    create_aadhaar_sample()
    create_aadhaar_photo_samples()
