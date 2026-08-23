import sqlite3
import json
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "border_intel.db")

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_code TEXT UNIQUE,
            doc_type TEXT,
            full_name TEXT,
            nationality TEXT,
            risk_score INTEGER,
            risk_level TEXT,
            status TEXT,
            scanned_at TEXT,
            extracted_json TEXT,
            analysis_json TEXT,
            evidence_json TEXT,
            image_path TEXT
        )
    """)
    conn.commit()
    conn.close()

def next_doc_code():
    conn = get_conn()
    row = conn.execute("SELECT MAX(id) as m FROM documents").fetchone()
    conn.close()
    next_id = (row["m"] or 0) + 1
    return f"DOC-{1500 + next_id}"

def insert_document(record: dict):
    conn = get_conn()
    try:
        conn.execute("""
            INSERT INTO documents
            (doc_code, doc_type, full_name, nationality, risk_score, risk_level,
             status, scanned_at, extracted_json, analysis_json, evidence_json, image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record["doc_code"], record["doc_type"], record["full_name"], record["nationality"],
            record["risk_score"], record["risk_level"], record["status"], record["scanned_at"],
            json.dumps(record["extracted"]), json.dumps(record["analysis"]),
            json.dumps(record["evidence"]), record.get("image_path", ""),
        ))
        conn.commit()
        doc_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    except sqlite3.IntegrityError:
        # Fallback with timestamp to guarantee uniqueness
        import time
        unique_code = f"DOC-{int(time.time()) % 100000}"
        record["doc_code"] = unique_code
        conn.execute("""
            INSERT INTO documents
            (doc_code, doc_type, full_name, nationality, risk_score, risk_level,
             status, scanned_at, extracted_json, analysis_json, evidence_json, image_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            unique_code, record["doc_type"], record["full_name"], record["nationality"],
            record["risk_score"], record["risk_level"], record["status"], record["scanned_at"],
            json.dumps(record["extracted"]), json.dumps(record["analysis"]),
            json.dumps(record["evidence"]), record.get("image_path", ""),
        ))
        conn.commit()
        doc_id = conn.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
    finally:
        conn.close()
    return doc_id

def list_documents(limit=50, offset=0, risk_level=None):
    conn = get_conn()
    query = "SELECT * FROM documents"
    params = []
    if risk_level:
        query += " WHERE UPPER(risk_level) LIKE ?"
        params.append(f"%{risk_level.upper()}%")
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats():
    conn = get_conn()
    
    # Format matching scanned_at (e.g., "23 Aug 2026")
    today_str = datetime.now().strftime("%d %b %Y")
    hour = datetime.now().hour

    if 6 <= hour < 14:
        cur_shift = "Shift A (Morning 06:00-14:00)"
        prev_shift = "Shift C (Night 22:00-06:00)"
    elif 14 <= hour < 22:
        cur_shift = "Shift B (Evening 14:00-22:00)"
        prev_shift = "Shift A (Morning 06:00-14:00)"
    else:
        cur_shift = "Shift C (Night 22:00-06:00)"
        prev_shift = "Shift B (Evening 14:00-22:00)"
    
    # 1. Total All-Time Counts
    total_all = conn.execute("SELECT COUNT(*) as c FROM documents").fetchone()["c"]
    high_all = conn.execute("SELECT COUNT(*) as c FROM documents WHERE UPPER(risk_level) LIKE '%HIGH%'").fetchone()["c"]
    med_all = conn.execute("SELECT COUNT(*) as c FROM documents WHERE UPPER(risk_level) LIKE '%MED%'").fetchone()["c"]
    low_all = conn.execute("SELECT COUNT(*) as c FROM documents WHERE UPPER(risk_level) LIKE '%LOW%'").fetchone()["c"]
    
    # 2. Today's Counts (Auto-resets to 0 when date rolls over at midnight)
    today_total = conn.execute("SELECT COUNT(*) as c FROM documents WHERE scanned_at LIKE ?", (f"%{today_str}%",)).fetchone()["c"]
    today_high = conn.execute("SELECT COUNT(*) as c FROM documents WHERE scanned_at LIKE ? AND UPPER(risk_level) LIKE '%HIGH%'", (f"%{today_str}%",)).fetchone()["c"]
    today_med = conn.execute("SELECT COUNT(*) as c FROM documents WHERE scanned_at LIKE ? AND UPPER(risk_level) LIKE '%MED%'", (f"%{today_str}%",)).fetchone()["c"]
    today_low = conn.execute("SELECT COUNT(*) as c FROM documents WHERE scanned_at LIKE ? AND UPPER(risk_level) LIKE '%LOW%'", (f"%{today_str}%",)).fetchone()["c"]

    # 3. Previous Shift / Previous Day Counts
    prev_row = conn.execute("SELECT DISTINCT SUBSTR(scanned_at, 1, 11) as d FROM documents WHERE scanned_at NOT LIKE ? ORDER BY id DESC LIMIT 1", (f"%{today_str}%",)).fetchone()
    prev_date_str = prev_row["d"].strip() if prev_row else (datetime.now() - timedelta(days=1)).strftime("%d %b %Y")

    prev_total = conn.execute("SELECT COUNT(*) as c FROM documents WHERE scanned_at LIKE ?", (f"%{prev_date_str}%",)).fetchone()["c"]
    prev_high = conn.execute("SELECT COUNT(*) as c FROM documents WHERE scanned_at LIKE ? AND UPPER(risk_level) LIKE '%HIGH%'", (f"%{prev_date_str}%",)).fetchone()["c"]
    prev_med = conn.execute("SELECT COUNT(*) as c FROM documents WHERE scanned_at LIKE ? AND UPPER(risk_level) LIKE '%MED%'", (f"%{prev_date_str}%",)).fetchone()["c"]
    prev_low = conn.execute("SELECT COUNT(*) as c FROM documents WHERE scanned_at LIKE ? AND UPPER(risk_level) LIKE '%LOW%'", (f"%{prev_date_str}%",)).fetchone()["c"]
    
    conn.close()
    
    return {
        "today_total": int(today_total),
        "today_high": int(today_high),
        "today_med": int(today_med),
        "today_low": int(today_low),
        "all_total": int(total_all),
        "all_high": int(high_all),
        "all_med": int(med_all),
        "all_low": int(low_all),
        "current_date": today_str,
        "current_shift": cur_shift,
        "previous_shift": {
            "name": prev_shift,
            "date": prev_date_str,
            "total": int(prev_total),
            "high": int(prev_high),
            "med": int(prev_med),
            "low": int(prev_low),
            "handover_status": "Handover Verified & Logged"
        },
        # Backwards compatibility keys
        "total": int(today_total),
        "high": int(today_high),
        "medium": int(today_med),
        "low": int(today_low),
        "today": int(today_total),
        "prev_shift_total": int(prev_total),
        "prev_shift_high": int(prev_high),
        "prev_shift_med": int(prev_med),
        "prev_shift_low": int(prev_low),
        "prev_shift_date": prev_date_str
    }

def search_documents(query_str: str):
    conn = get_conn()
    term = f"%{query_str.strip().upper()}%"
    rows = conn.execute("""
        SELECT * FROM documents 
        WHERE UPPER(doc_code) LIKE ? 
           OR UPPER(full_name) LIKE ? 
           OR UPPER(extracted_json) LIKE ?
           OR UPPER(nationality) LIKE ?
        ORDER BY id DESC LIMIT 20
    """, (term, term, term, term)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

