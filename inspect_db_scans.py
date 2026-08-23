import sqlite3
import json

def inspect_db_records():
    conn = sqlite3.connect("backend/border_intel.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, doc_code, doc_type, full_name, risk_score, risk_level, extracted_json, analysis_json, image_path FROM documents ORDER BY id DESC LIMIT 10")
    rows = cursor.fetchall()
    
    for r in rows:
        print("="*60)
        print(f"ID: {r['id']} | CODE: {r['doc_code']} | TYPE: {r['doc_type']} | NAME: {r['full_name']} | RISK: {r['risk_score']}")
        print("IMAGE:", r['image_path'])
        ext = json.loads(r['extracted_json'])
        print("EXTRACTED:", json.dumps(ext, indent=2))
        analysis = json.loads(r['analysis_json'])
        print("FACE VERIFICATION:", json.dumps(analysis.get('face_verification'), indent=2))

if __name__ == "__main__":
    inspect_db_records()
