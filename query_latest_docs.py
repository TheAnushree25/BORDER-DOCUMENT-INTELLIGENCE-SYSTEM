import sqlite3
import json

conn = sqlite3.connect("backend/border_intel.db")
conn.row_factory = sqlite3.Row
rows = conn.execute("SELECT * FROM documents ORDER BY id DESC LIMIT 5").fetchall()
for row in rows:
    print(f"=== Doc ID: {row['id']} | Code: {row['doc_code']} | Status: {row['status']} | Risk: {row['risk_score']} ({row['risk_level']}) ===")
    print("Type:", row["doc_type"], "| Name:", row["full_name"])
    print("Analysis:", json.dumps(json.loads(row["analysis_json"]), indent=2))
    print("Extracted:", row["extracted_json"])
    print()
conn.close()
