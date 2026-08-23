import sqlite3
import json

conn = sqlite3.connect("backend/border_intel.db")
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT * FROM documents WHERE doc_code='DOC-1478'").fetchone()
if row:
    print("DOC-1478 Record:")
    print("Doc Code:", row["doc_code"])
    print("Doc Type:", row["doc_type"])
    print("Full Name:", row["full_name"])
    print("Risk Score:", row["risk_score"])
    print("Risk Level:", row["risk_level"])
    print("Status:", row["status"])
    print("Extracted JSON:", json.loads(row["extracted_json"]))
    print("Analysis JSON:", json.dumps(json.loads(row["analysis_json"]), indent=2))
else:
    print("No record found for DOC-1478")
conn.close()
