import os
from PIL import Image
import pytesseract
from backend.utils import ocr, document_extractor

path = os.path.join("test_samples", "sample_aadhaar.jpg")
img = Image.open(path)
text = ocr.extract_text(img)
print("--- EXTRACTED OCR TEXT ---")
print(repr(text))
print("--- VISIBLE TEXT ---")
print(text)
print("--- DETECTED TYPE ---")
print(document_extractor.detect_document_type(text))
