import os
import shutil
import cv2
import numpy as np
from PIL import Image, ImageOps
import pytesseract

# 1. Discover standard Tesseract locations on Windows
_TESS_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    os.path.expandvars(r"%USERPROFILE%\AppData\Local\Tesseract-OCR\tesseract.exe"),
]

TESSERACT_AVAILABLE = False
if shutil.which("tesseract"):
    TESSERACT_AVAILABLE = True
else:
    for path in _TESS_CANDIDATES:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            TESSERACT_AVAILABLE = True
            break

# 2. Discover RapidOCR engine (Lazy loaded per worker process for Gunicorn fork safety)
_RAPID_ENGINE = None
_RAPID_INITIALIZED = False

def _get_rapid_engine():
    global _RAPID_ENGINE, _RAPID_INITIALIZED
    if not _RAPID_INITIALIZED:
        _RAPID_INITIALIZED = True
        try:
            from rapidocr_onnxruntime import RapidOCR
            _RAPID_ENGINE = RapidOCR()
        except Exception:
            _RAPID_ENGINE = None
    return _RAPID_ENGINE

# 3. Check language availability
_AVAILABLE_LANGS = []
if TESSERACT_AVAILABLE:
    try:
        _AVAILABLE_LANGS = pytesseract.get_languages(config="")
    except Exception:
        _AVAILABLE_LANGS = []

HIN_AVAILABLE = "hin" in _AVAILABLE_LANGS
OCR_LANG = "eng+hin" if HIN_AVAILABLE else "eng"


def auto_detect_and_crop_card(cv_img):
    """
    Detects rectangular document card edges on backgrounds (e.g. table surface)
    and performs perspective correction.
    If the image is already a cropped document or no valid card boundary is found, returns original.
    """
    return _crop_card(cv_img)[0]


def _crop_card(cv_img):
    """Returns (card image, perspective matrix from cv_img to the card), the matrix is None when nothing was cropped."""
    orig = cv_img.copy()
    h, w = orig.shape[:2]
    aspect = w / float(max(h, 1))

    # If the image is already a clean card aspect ratio (between 1.4 and 1.8), keep full card!
    if 1.40 <= aspect <= 1.80 and min(h, w) > 400:
        return orig, None

    gray = cv2.cvtColor(orig, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 30, 150)

    contours, _ = cv2.findContours(edged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    for c in contours:
        area = cv2.contourArea(c)
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        
        # Must occupy meaningful portion of outer frame (between 35% and 92%)
        if len(approx) == 4 and (h * w * 0.35) < area < (h * w * 0.92):
            pts = approx.reshape(4, 2).astype("float32")
            rect = np.zeros((4, 2), dtype="float32")
            s = pts.sum(axis=1)
            rect[0] = pts[np.argmin(s)]
            rect[2] = pts[np.argmax(s)]
            diff = np.diff(pts, axis=1)
            rect[1] = pts[np.argmin(diff)]
            rect[3] = pts[np.argmax(diff)]

            (tl, tr, br, bl) = rect
            widthA = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
            widthB = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
            maxWidth = max(int(widthA), int(widthB))

            heightA = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
            heightB = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
            maxHeight = max(int(heightA), int(heightB))

            # Must have card-like aspect ratio (between 1.25 and 1.95)
            card_aspect = maxWidth / float(max(maxHeight, 1))
            if maxWidth > 200 and maxHeight > 120 and (1.25 <= card_aspect <= 1.95):
                dst = np.array([
                    [0, 0],
                    [maxWidth - 1, 0],
                    [maxWidth - 1, maxHeight - 1],
                    [0, maxHeight - 1]
                ], dtype="float32")
                M = cv2.getPerspectiveTransform(rect, dst)
                warped = cv2.warpPerspective(orig, M, (maxWidth, maxHeight))
                return warped, M

    return orig, None


def _line_box(points, scale, warp, width, height):
    """Maps an OCR quadrilateral from the (scaled, cropped) OCR input back to an [x0, y0, x1, y1] box on the source image."""
    pts = np.asarray(points, dtype=np.float32).reshape(-1, 2) / scale
    if warp is not None:
        pts = cv2.perspectiveTransform(pts.reshape(-1, 1, 2), np.linalg.inv(warp)).reshape(-1, 2)
    x0, y0 = np.clip(pts.min(axis=0), 0, [width, height])
    x1, y1 = np.clip(pts.max(axis=0), 0, [width, height])
    return [round(float(x0), 1), round(float(y0), 1), round(float(x1), 1), round(float(y1), 1)]


def read_hindi(image: Image.Image, box) -> str | None:
    """Devanagari text inside `box` ([x0, y0, x1, y1] on `image`) via Tesseract's Hindi model; None when unavailable."""
    if not HIN_AVAILABLE:
        return None
    w, h = image.size
    x0, y0 = max(0, int(box[0])), max(0, int(box[1]))
    x1, y1 = min(w, int(round(box[2]))), min(h, int(round(box[3])))
    if x1 - x0 < 8 or y1 - y0 < 8:
        return None
    crop = image.crop((x0, y0, x1, y1)).convert("L")
    if crop.height < 64:
        crop = crop.resize((int(crop.width * 64 / crop.height), 64), Image.Resampling.LANCZOS)
    try:
        return pytesseract.image_to_string(crop, lang="hin", config="--psm 7").strip()
    except Exception:
        return None


def extract_text_fast(image: Image.Image) -> dict:
    """
    Sub-second high-accuracy OCR pipeline with card auto-crop, deskew, and dual engine support.
    """
    try:
        img = ImageOps.exif_transpose(image).convert("RGB")
        cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)

        # 1. Card Auto Crop / Deskew (if on background table)
        cropped_card, warp = _crop_card(cv_img)

        # 2. Optimized Preprocessing for OCR
        ch, cw = cropped_card.shape[:2]
        gray = cv2.cvtColor(cropped_card, cv2.COLOR_BGR2GRAY)
        
        # Scale for OCR preprocessing
        if cw < 900:
            scale_ocr = 900.0 / float(cw)
            gray_pre = cv2.resize(gray, (0, 0), fx=scale_ocr, fy=scale_ocr, interpolation=cv2.INTER_CUBIC)
        elif cw > 1200:
            scale_ocr = 1200.0 / float(cw)
            gray_pre = cv2.resize(gray, (0, 0), fx=scale_ocr, fy=scale_ocr, interpolation=cv2.INTER_AREA)
        else:
            gray_pre = gray

        denoised = cv2.bilateralFilter(gray_pre, 9, 75, 75)
        clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
        enhanced = clahe.apply(denoised)

        text = ""
        engine_used = "none"
        # Each recognised line with its confidence and [x0, y0, x1, y1] box on the input image (RapidOCR only).
        line_boxes = []

        # 3. RapidOCR primary (Scale to max 960px for sub-second execution & low RAM)
        rapid_engine = _get_rapid_engine()
        if rapid_engine is not None:
            try:
                scale_rapid = 960.0 / float(max(ch, cw)) if max(ch, cw) > 960 else 1.0
                if scale_rapid < 1.0:
                    rapid_input = cv2.resize(cropped_card, (0, 0), fx=scale_rapid, fy=scale_rapid, interpolation=cv2.INTER_AREA)
                else:
                    rapid_input = cropped_card

                rapid_res, _ = rapid_engine(rapid_input)
                if rapid_res:
                    items = [item for item in rapid_res if len(item) > 2 and item[1].strip()]
                    text = "\n".join(item[1] for item in items)
                    h_img, w_img = cv_img.shape[:2]
                    line_boxes = [
                        {"text": item[1], "score": float(item[2]), "box": _line_box(item[0], scale_rapid, warp, w_img, h_img)}
                        for item in items
                    ]
                    engine_used = "rapidocr"
            except Exception:
                pass

        # 4. Tesseract fallback if RapidOCR didn't return sufficient text
        if (not text.strip() or len(text.strip()) < 20) and TESSERACT_AVAILABLE:
            config_psm6 = r"--oem 3 --psm 6"
            try:
                tess_text = pytesseract.image_to_string(enhanced, lang=OCR_LANG, config=config_psm6)
                if len(tess_text.strip()) > len(text.strip()):
                    text = tess_text
                    engine_used = "tesseract"
                    line_boxes = []
            except Exception:
                pass

        return {
            "text": text,
            "language": OCR_LANG,
            "engine": engine_used,
            "lines": line_boxes
        }
    except Exception as exc:
        return {
            "text": "",
            "language": OCR_LANG,
            "engine": "failed",
            "lines": []
        }
