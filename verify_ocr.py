import os
import json
from PIL import Image
from backend.utils import ocr, document_extractor, mrz

def test_file(filename):
    path = os.path.join("test_samples", filename)
    print(f"\n========================================")
    print(f"TESTING OCR ON: {filename}")
    print(f"========================================")
    img = Image.open(path)
    text = ocr.extract_text(img, filename=filename)
    print(f"--- EXTRACTED OCR TEXT ({len(text)} chars) ---")
    print(text)
    
    # MRZ lines for passport
    mrz_lines = mrz.extract_mrz_lines(text)
    mrz_result = None
    if len(mrz_lines) == 2:
        mrz_result = mrz.parse_td3(mrz_lines[0], mrz_lines[1])
        
    doc_type, extracted = document_extractor.extract_document_data(text, mrz_result=mrz_result)
    print(f"\n>>> DETECTED DOCUMENT TYPE: {doc_type}")
    print(f">>> EXTRACTED STRUCTURED FIELDS:")
    print(json.dumps(extracted, indent=2))
    return doc_type, extracted

if __name__ == "__main__":
    test_file("sample_pancard.jpg")
    test_file("sample_aadhaar.jpg")
    test_file("sample_passport.jpg")
