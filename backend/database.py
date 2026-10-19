import json
import os
import re
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta

from werkzeug.security import check_password_hash, generate_password_hash

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
# DATA_DIR holds the SQLite file and the uploaded scans. Point it at a persistent disk in production.
DATA_DIR = os.path.abspath(os.environ.get("DATA_DIR") or BACKEND_DIR)
DB_PATH = os.path.join(DATA_DIR, "border_intel.db")
UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")

DEFAULT_ADMIN_PASSWORD = "Admin@123"
TIMESTAMP_FMT = "%d %b %Y, %I:%M %p"
ROLES = ("ADMIN", "SENIOR_INSPECTOR", "OFFICER", "ANALYST")

# (id, name, default weight, description)
DEFAULT_RULES = [
    ("tampering", "Tampering Detection (ELA)", 65, "Image compression artifact and splicing detection"),
    ("face_mismatch", "Face Biometric Mismatch", 30, "Discrepancy between document portrait and live capture"),
    ("mrz_mismatch", "ICAO TD3 MRZ Mismatch", 20, "Checksum validation failure or visual/MRZ mismatch"),
    ("expiry_issue", "Document Expiry Issue", 10, "Document is expired or has invalid validity period"),
    ("watchlist_hit", "Watchlist Match", 60, "Document holder matches an active watchlist entry"),
]

DEMO_WATCHLIST = [
    ("VIKRAM SINGH", "Interpol Red Notice"),
    ("JOHN CONNOR", "Document Forgery Suspect"),
    ("TARIQ AL-MANSOOR", "Visa Fraud Flag"),
]

SCHEMA = """
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
);
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'OFFICER',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_login TEXT
);
CREATE TABLE IF NOT EXISTS watchlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    document_number TEXT,
    nationality TEXT,
    reason TEXT NOT NULL,
    risk_level TEXT NOT NULL DEFAULT 'High Risk',
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    action TEXT NOT NULL,
    entity_type TEXT,
    entity_id TEXT,
    details TEXT,
    ip_address TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    weight INTEGER NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    description TEXT
);
"""


def now_str():
    return datetime.now().strftime(TIMESTAMP_FMT)


def today_str():
    return datetime.now().strftime("%d %b %Y")


def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with closing(get_conn()) as conn, conn:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT OR IGNORE INTO rules (id, name, weight, enabled, description) VALUES (?, ?, ?, 1, ?)",
            DEFAULT_RULES,
        )
        has_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] > 0
        if not has_users:
            # Brand-new database: create the administrator and the demo watchlist.
            admin_password = (os.environ.get("ADMIN_PASSWORD") or "").strip() or DEFAULT_ADMIN_PASSWORD
            try:
                conn.execute(
                    "INSERT INTO users (username, password_hash, full_name, role, active, created_at) "
                    "VALUES ('admin', ?, 'System Administrator', 'ADMIN', 1, ?)",
                    (generate_password_hash(admin_password), now_str()),
                )
                conn.executemany(
                    "INSERT INTO watchlist (name, reason, created_at) VALUES (?, ?, ?)",
                    [(name, reason, today_str()) for name, reason in DEMO_WATCHLIST],
                )
                _set_setting(conn, "demo_login", "true" if admin_password == DEFAULT_ADMIN_PASSWORD else "false")
            except sqlite3.IntegrityError:
                pass  # another worker seeded the database first
        if _get_setting(conn, "demo_login") is None:
            admin = conn.execute("SELECT password_hash FROM users WHERE username = 'admin'").fetchone()
            uses_default = bool(admin) and check_password_hash(admin["password_hash"], DEFAULT_ADMIN_PASSWORD)
            _set_setting(conn, "demo_login", "true" if uses_default else "false")


def _get_setting(conn, key):
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def _set_setting(conn, key, value):
    conn.execute(
        "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        (key, value, now_str()),
    )


def get_secret_key():
    """Returns a session signing key shared by every worker, generated once per database."""
    with closing(get_conn()) as conn, conn:
        conn.execute(
            "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES ('secret_key', ?, ?)",
            (secrets.token_hex(32), now_str()),
        )
        return _get_setting(conn, "secret_key")


def demo_login_enabled():
    with closing(get_conn()) as conn:
        return _get_setting(conn, "demo_login") == "true"


# ---------------------------------------------------------------- users

def _public_user(row):
    if row is None:
        return None
    return {
        "id": row["id"],
        "username": row["username"],
        "full_name": row["full_name"],
        "role": row["role"],
        "active": bool(row["active"]),
        "last_login": row["last_login"] or "Never",
    }


def get_user(user_id):
    with closing(get_conn()) as conn:
        return _public_user(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def verify_login(username, password):
    with closing(get_conn()) as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ? AND active = 1", (username,)).fetchone()
    if row and check_password_hash(row["password_hash"], password):
        return _public_user(row)
    return None


def touch_last_login(user_id):
    with closing(get_conn()) as conn, conn:
        conn.execute("UPDATE users SET last_login = ? WHERE id = ?", (now_str(), user_id))


def list_users():
    with closing(get_conn()) as conn:
        return [_public_user(r) for r in conn.execute("SELECT * FROM users ORDER BY id")]


def create_user(username, password, full_name, role):
    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, full_name, role, active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (username, generate_password_hash(password), full_name, role, now_str()),
        )
        return _public_user(conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone())


def delete_user(user_id):
    with closing(get_conn()) as conn, conn:
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


def change_password(user_id, current_password, new_password):
    with closing(get_conn()) as conn, conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not row or not check_password_hash(row["password_hash"], current_password):
            return False
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new_password), user_id))
        if row["username"] == "admin":
            _set_setting(conn, "demo_login", "true" if new_password == DEFAULT_ADMIN_PASSWORD else "false")
        return True


# ---------------------------------------------------------------- watchlist

def _watchlist_entry(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "document_number": row["document_number"],
        "reason": row["reason"],
        "added_at": row["created_at"],
    }


def list_watchlist():
    with closing(get_conn()) as conn:
        return [_watchlist_entry(r) for r in conn.execute("SELECT * FROM watchlist WHERE active = 1 ORDER BY id")]


def add_watchlist(name, reason, document_number=None):
    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            "INSERT INTO watchlist (name, document_number, reason, created_at) VALUES (?, ?, ?, ?)",
            (name, document_number, reason, today_str()),
        )
        return _watchlist_entry(conn.execute("SELECT * FROM watchlist WHERE id = ?", (cur.lastrowid,)).fetchone())


def delete_watchlist(entry_id):
    with closing(get_conn()) as conn, conn:
        conn.execute("DELETE FROM watchlist WHERE id = ?", (entry_id,))


def _name_tokens(name):
    return frozenset(re.findall(r"[A-Z]+", (name or "").upper()))


def _normalize_doc_number(value):
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def find_watchlist_matches(full_name, document_numbers=()):
    """Active entries whose name has the same words as `full_name` (any order) or whose document number matches."""
    tokens = _name_tokens(full_name)
    numbers = {_normalize_doc_number(n) for n in document_numbers} - {""}
    matches = []
    for entry in list_watchlist():
        entry_tokens = _name_tokens(entry["name"])
        same_name = bool(entry_tokens) and entry_tokens == tokens
        same_number = _normalize_doc_number(entry["document_number"]) in numbers
        if same_name or same_number:
            matches.append(entry)
    return matches


# ---------------------------------------------------------------- audit trail

def add_audit(username, action, details=None, ip=None, entity_type=None, entity_id=None):
    with closing(get_conn()) as conn, conn:
        conn.execute(
            "INSERT INTO audit_logs (username, action, entity_type, entity_id, details, ip_address, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (username, action, entity_type, entity_id, details, ip, now_str()),
        )


def list_audit_logs(limit=200):
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    return [
        {"id": r["id"], "event": r["action"], "user": r["username"], "details": r["details"], "timestamp": r["created_at"]}
        for r in rows
    ]


# ---------------------------------------------------------------- rule engine

def get_rule_weights():
    """Rule id -> weight; a disabled rule contributes 0."""
    with closing(get_conn()) as conn:
        rows = conn.execute("SELECT id, weight, enabled FROM rules").fetchall()
    return {r["id"]: int(r["weight"]) if r["enabled"] else 0 for r in rows}


def update_rule_weights(weights):
    with closing(get_conn()) as conn, conn:
        for rule_id, weight in weights.items():
            conn.execute("UPDATE rules SET weight = ? WHERE id = ?", (weight, rule_id))


# ---------------------------------------------------------------- documents

def insert_document(record: dict):
    """Stores a scan and returns (id, doc_code). The code is derived from the row id so it never collides."""
    with closing(get_conn()) as conn, conn:
        cur = conn.execute(
            """
            INSERT INTO documents
            (doc_type, full_name, nationality, risk_score, risk_level,
             status, scanned_at, extracted_json, analysis_json, evidence_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["doc_type"], record["full_name"], record["nationality"],
                record["risk_score"], record["risk_level"], record["status"], record["scanned_at"],
                json.dumps(record["extracted"]), json.dumps(record["analysis"]), json.dumps(record["evidence"]),
            ),
        )
        doc_id = cur.lastrowid
        for doc_code in (f"DOC-{1500 + doc_id}", f"DOC-{1500 + doc_id}-{secrets.token_hex(2).upper()}"):
            try:
                conn.execute(
                    "UPDATE documents SET doc_code = ?, image_path = ? WHERE id = ?",
                    (doc_code, f"/uploads/{doc_code}.jpg", doc_id),
                )
                return doc_id, doc_code
            except sqlite3.IntegrityError:
                continue  # code taken by a legacy row
    raise RuntimeError("Could not allocate a document code")


def list_documents(limit=50, offset=0, risk_level=None):
    query = "SELECT * FROM documents"
    params = []
    if risk_level:
        query += " WHERE UPPER(risk_level) LIKE ?"
        params.append(f"%{risk_level.upper()}%")
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    with closing(get_conn()) as conn:
        return [dict(r) for r in conn.execute(query, params).fetchall()]


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

    # 4. Biometric outcomes (only scans where a live face was compared)
    face_matched = conn.execute("""SELECT COUNT(*) as c FROM documents WHERE analysis_json LIKE '%"face_verification": {"status": "MATCH"%'""").fetchone()["c"]
    face_alerts = conn.execute("""SELECT COUNT(*) as c FROM documents WHERE analysis_json LIKE '%"face_verification": {"status": "ALERT"%'""").fetchone()["c"]

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
        "face_compared": int(face_matched + face_alerts),
        "face_matched": int(face_matched),
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


def table_counts():
    with closing(get_conn()) as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("documents", "users", "watchlist", "audit_logs", "rules")
        }


def search_documents(query_str: str):
    term = f"%{query_str.strip().upper()}%"
    with closing(get_conn()) as conn:
        rows = conn.execute("""
            SELECT * FROM documents
            WHERE UPPER(doc_code) LIKE ?
               OR UPPER(full_name) LIKE ?
               OR UPPER(extracted_json) LIKE ?
               OR UPPER(nationality) LIKE ?
            ORDER BY id DESC LIMIT 20
        """, (term, term, term, term)).fetchall()
    return [dict(r) for r in rows]
