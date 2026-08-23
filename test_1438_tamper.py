from PIL import Image
from backend.utils import tamper
import json

img = Image.open("backend/uploads/DOC-1438.jpg")
res = tamper.error_level_analysis(img)
print("Tamper Score:", res["tamper_score"])
print("Tampering Detected:", res["tampering_detected"])
print("Detail:", res["detail"])
print("Suspicious Regions:", len(res["suspicious_regions"]))
for r in res["suspicious_regions"]:
    print(" ", r)
