import csv
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
import threading
from contextlib import closing
from datetime import date, datetime, timedelta
from functools import wraps

CURRENT_DIR = os.path.abspath(os.path.dirname(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from flask import Flask, Response, g, jsonify, request, send_file, send_from_directory, session
from PIL import Image, ImageOps

import database as db
from utils import document_extractor, face_match, field_checks, mrz, ocr, risk, tamper, text_forensics

UPLOAD_DIR = db.UPLOAD_DIR
FRONTEND_DIR = os.path.join(os.path.dirname(CURRENT_DIR), "frontend")

app = Flask(__name__)
app.config.update(
    MAX_CONTENT_LENGTH=32 * 1024 * 1024,  # 32 MB max upload limit
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "").lower() in ("1", "true", "yes"),
    PERMANENT_SESSION_LIFETIME=timedelta(hours=12),
)
db.init_db()
app.secret_key = os.environ.get("SECRET_KEY") or db.get_secret_key()

# The OCR and face models are shared, stateful objects, so a worker runs one scan at a time.
# This also caps peak memory on small (512 MB) instances.
SCAN_LOCK = threading.Lock()

PUBLIC_API_PATHS = {"/api/health", "/api/login", "/api/auth/login", "/api/auth/config"}
ROLE_LABELS = {
    "ADMIN": "System Administrator",
    "SENIOR_INSPECTOR": "Senior Inspector",
    "OFFICER": "Border Officer",
    "ANALYST": "Forensic Analyst",
}
UNREADABLE = {"", "UNKNOWN", "UNREADABLE", "NOT DETECTED"}


def client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    return forwarded.split(",")[0].strip() or request.remote_addr


def audit(action, details=None, username=None):
    if username is None:
        user = g.get("user")
        username = user["username"] if user else "system"
    db.add_audit(username, action, details=details, ip=client_ip())


def user_payload(user):
    return {**user, "role_label": ROLE_LABELS.get(user["role"], user["role"]), "unit": "Border Security Intelligence Unit"}


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if g.user["role"] != "ADMIN":
            return jsonify({"error": "Administrator access required"}), 403
        return fn(*args, **kwargs)
    return wrapper


@app.before_request
def require_login():
    path = request.path
    protected = (path.startswith("/api/") and path not in PUBLIC_API_PATHS) or path.startswith("/uploads/")
    if not protected:
        return None
    user = db.get_user(session["uid"]) if session.get("uid") else None
    if not user or not user["active"]:
        if session.get("uid"):
            session.clear()
        return jsonify({"error": "Authentication required"}), 401
    g.user = user
    return None


@app.errorhandler(413)
def request_entity_too_large(error):
    return jsonify({"error": "Uploaded document image exceeds maximum size limit (32MB)."}), 413


# ---------------------------------------------------------------- authentication

@app.route("/api/login", methods=["POST"])
@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    username = str(data.get("username", "")).strip().lower()
    password = str(data.get("password", "")).strip()

    user = db.verify_login(username, password) if username and password else None
    if not user:
        audit("Failed Login Attempt", username=username or "unknown")
        return jsonify({"status": "error", "message": "Invalid Officer ID or Security Password"}), 401

    session.clear()
    session.permanent = True
    session["uid"] = user["id"]
    db.touch_last_login(user["id"])
    audit(f"Officer Login: {user['username']}", username=user["username"])
    return jsonify({"status": "success", "message": "Authenticated successfully", "user": user_payload(user)}), 200


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    audit(f"Officer Logout: {g.user['username']}")
    session.clear()
    return jsonify({"status": "success"})


@app.route("/api/auth/me", methods=["GET"])
def current_user():
    return jsonify({"user": user_payload(g.user)})


@app.route("/api/auth/config", methods=["GET"])
def auth_config():
    # The one-click demo login is offered only while the admin still uses the published default password.
    return jsonify({"demo_login": db.demo_login_enabled()})


@app.route("/api/auth/change-password", methods=["POST"])
@app.route("/api/admin/change-password", methods=["POST"])
def change_password():
    data = request.get_json(silent=True) or {}
    current = str(data.get("current_password", "")).strip()
    new_pass = str(data.get("new_password", "")).strip()
    if len(new_pass) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if not db.change_password(g.user["id"], current, new_pass):
        return jsonify({"error": "Current password is incorrect"}), 403
    audit("Security Password Rotated")
    return jsonify({"status": "success", "message": "Security password updated successfully."})


@app.route("/health", methods=["GET"])
@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "service": "border-doc-intel",
        "timestamp": datetime.now().isoformat()
    }), 200


# ---------------------------------------------------------------- dashboard data

@app.route("/api/stats", methods=["GET"])
def stats():
    return jsonify(db.get_stats())


@app.route("/api/documents", methods=["GET"])
def documents():
    limit = max(1, min(request.args.get("limit", 50, type=int), 500))
    offset = max(0, request.args.get("offset", 0, type=int))
    rows = db.list_documents(limit=limit, offset=offset, risk_level=request.args.get("risk_level"))
    return jsonify(rows)


@app.route("/api/watchlist", methods=["GET", "POST", "DELETE"])
def handle_watchlist():
    if request.method == "GET":
        return jsonify(db.list_watchlist())
    if request.method == "DELETE":  # legacy form: DELETE /api/watchlist?id=3
        return delete_watchlist_item(request.args.get("id", type=int))

    data = request.get_json(silent=True) or {}
    name = " ".join(str(data.get("name", "")).split()).upper()
    if not name:
        return jsonify({"error": "Suspect name is required"}), 400
    reason = str(data.get("reason", "")).strip() or "Suspicious Activity"
    document_number = str(data.get("document_number", "")).strip().upper() or None
    entry = db.add_watchlist(name[:120], reason[:200], document_number)
    audit(f"Watchlist Added: {entry['name']}")
    return jsonify(entry), 201


@app.route("/api/watchlist/<int:item_id>", methods=["DELETE"])
def delete_watchlist_item(item_id):
    if item_id:
        db.delete_watchlist(item_id)
        audit(f"Watchlist Removed: #{item_id}")
    return jsonify({"status": "success", "watchlist": db.list_watchlist()})


@app.route("/api/audit-logs", methods=["GET"])
def get_audit_logs():
    return jsonify(db.list_audit_logs())


@app.route("/api/rules", methods=["GET", "POST", "PUT"])
def handle_rules():
    if request.method == "GET":
        return jsonify(db.get_rule_weights())
    if g.user["role"] != "ADMIN":
        return jsonify({"error": "Administrator access required"}), 403

    data = request.get_json(silent=True) or {}
    known = db.get_rule_weights()
    updates = {}
    for key, value in data.items():
        if key not in known:
            continue
        try:
            weight = int(value)
        except (TypeError, ValueError):
            return jsonify({"error": f"Weight for '{key}' must be a whole number"}), 400
        if not 0 <= weight <= 100:
            return jsonify({"error": f"Weight for '{key}' must be between 0 and 100"}), 400
        updates[key] = weight
    db.update_rule_weights(updates)
    audit("Rule Engine Weights Updated", details=json.dumps(updates))
    return jsonify({"status": "success", "rules": db.get_rule_weights()})


@app.route("/api/users", methods=["GET", "POST"])
@admin_required
def handle_users():
    if request.method == "GET":
        return jsonify(db.list_users())

    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip().lower()
    password = str(data.get("password", "")).strip()
    full_name = str(data.get("full_name", "")).strip() or username.capitalize()
    role = str(data.get("role", "OFFICER")).strip().upper()
    if not re.fullmatch(r"[a-z0-9_.-]{3,32}", username):
        return jsonify({"error": "Username must be 3-32 characters (letters, digits, _ . -)"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400
    if role not in db.ROLES:
        return jsonify({"error": f"Unknown role '{role}'"}), 400
    try:
        new_user = db.create_user(username, password, full_name[:80], role)
    except sqlite3.IntegrityError:
        return jsonify({"error": f"Username '{username}' already exists"}), 409
    audit(f"New Officer Enrolled: {username} ({role})")
    return jsonify(new_user), 201


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    target = db.get_user(user_id)
    if not target:
        return jsonify({"error": "User not found"}), 404
    if target["username"] == "admin" or target["id"] == g.user["id"]:
        return jsonify({"error": "This account is protected and cannot be revoked"}), 400
    db.delete_user(user_id)
    audit(f"Officer Revoked/Deleted: {target['username']}")
    return jsonify({"status": "success"})


# ---------------------------------------------------------------- administration

def _csv_cell(value):
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text  # keep spreadsheet apps from running formulas


@app.route("/api/admin/export-report", methods=["GET"])
@admin_required
def export_report():
    fmt = request.args.get("format", "json").lower()
    docs = db.list_documents(limit=500)
    audit(f"Intelligence Report Exported ({fmt.upper()})")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Document ID", "Type", "Full Name", "Nationality", "Risk Score", "Risk Level", "Status", "Scanned At"])
        for d in docs:
            writer.writerow([_csv_cell(d.get(k)) for k in
                             ("doc_code", "doc_type", "full_name", "nationality", "risk_score", "risk_level", "status", "scanned_at")])
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=border_intelligence_report_{stamp}.csv"}
        )
    return Response(
        json.dumps(docs, indent=2),
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment;filename=border_intelligence_report_{stamp}.json"}
    )


@app.route("/api/admin/vacuum-db", methods=["POST"])
@admin_required
def vacuum_db():
    with closing(db.get_conn()) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.execute("VACUUM")
        conn.execute("ANALYZE")
    audit("Database Optimized & Vacuumed", details=f"integrity_check={integrity}")

    db_size = os.path.getsize(db.DB_PATH) if os.path.exists(db.DB_PATH) else 0
    return jsonify({
        "status": "success",
        "message": "Database optimized, indexed, and verified intact." if integrity == "ok" else f"Integrity check reported: {integrity}",
        "db_size_kb": round(db_size / 1024, 1),
        "integrity": "PASSED" if integrity == "ok" else "FAILED"
    })


@app.route("/api/admin/backup-db", methods=["GET"])
@admin_required
def download_db_backup():
    # Use SQLite's online backup so the copy is consistent even while scans are being written.
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = os.path.join(tmp_dir, "backup.db")
        with closing(db.get_conn()) as src, closing(sqlite3.connect(tmp_path)) as dst:
            src.backup(dst)
        with open(tmp_path, "rb") as f:
            data = f.read()
    audit("SQLite Database Backup Downloaded")
    return send_file(
        io.BytesIO(data),
        mimetype="application/vnd.sqlite3",
        as_attachment=True,
        download_name=f"border_intel_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    )


@app.route("/api/diagnostics/db", methods=["GET"])
def db_diagnostics():
    counts = db.table_counts()
    db_size = os.path.getsize(db.DB_PATH) if os.path.exists(db.DB_PATH) else 0
    return jsonify({
        "status": "ok",
        "total_documents": counts["documents"],
        "today_documents": db.get_stats()["today_total"],
        "total_users": counts["users"],
        "total_watchlist": counts["watchlist"],
        "total_audit_logs": counts["audit_logs"],
        "db_size_kb": round(db_size / 1024, 1),
        "tables": list(counts),
        "tesseract_available": ocr.TESSERACT_AVAILABLE,
        "neural_face_models": face_match._YUNET_AVAILABLE,
    })


@app.route("/api/database-check", methods=["GET"])
def database_check():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": [], "count": 0, "message": "Enter a search query."})

    records = db.search_documents(q)
    formatted = []
    for r in records:
        try:
            ext = json.loads(r["extracted_json"])
        except Exception:
            ext = {}
        formatted.append({
            "doc_code": r["doc_code"],
            "doc_type": r["doc_type"],
            "full_name": r["full_name"],
            "nationality": r["nationality"],
            "risk_score": r["risk_score"],
            "risk_level": r["risk_level"],
            "scanned_at": r["scanned_at"],
            "status": r["status"],
            "details": ext
        })

    return jsonify({
        "query": q,
        "count": len(formatted),
        "results": formatted
    })


# ---------------------------------------------------------------- screening pipeline

def sanitize_for_json(obj):
    """
    Recursively sanitize objects to guarantee 100% native Python JSON serializability.
    Converts numpy scalars, arrays, datetime, etc.
    """
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(item) for item in obj]
    elif hasattr(obj, "item") and callable(getattr(obj, "item")):
        return obj.item()
    elif isinstance(obj, (float, int, str, bool)) or obj is None:
        return obj
    elif hasattr(obj, "tolist") and callable(getattr(obj, "tolist")):
        return obj.tolist()
    return str(obj)


def load_image(stream, max_dim, keep_full=False):
    image = Image.open(stream)
    image.load()
    # Honour phone-camera rotation once, so OCR, forensics, face boxes and the saved evidence all agree.
    image = ImageOps.exif_transpose(image).convert("RGB")
    full = image
    # Memory-Safe Auto Scale: cap oversized images to prevent container OOM crashes
    if max(image.size) > max_dim:
        image = image.copy()
        image.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return (image, full) if keep_full else image


def parse_dmy(value):
    try:
        return datetime.strptime(value, "%d/%m/%Y").date()
    except (TypeError, ValueError):
        return None


@app.route("/api/scan", methods=["POST"])
def scan_document():
    if "document" not in request.files:
        return jsonify({"error": "No document file uploaded"}), 400

    live_file = request.files.get("live_face")
    try:
        image, full = load_image(request.files["document"].stream, max_dim=1280, keep_full=True)
        # Grayscale copy at upload resolution for the altered-text check: camera blur and noise survive there.
        forensic_gray = text_forensics.prepare_image(full)
        del full
    except Exception as e:
        return jsonify({"error": f"Invalid document image format: {str(e)}"}), 400

    live_image = None
    if live_file is not None and live_file.filename:
        try:
            live_image = load_image(live_file.stream, max_dim=800)
        except Exception as e:
            return jsonify({"error": f"Invalid live face image format: {str(e)}"}), 400

    try:
        response_payload = run_screening(image, live_image, forensic_gray)
    except Exception as err:
        app.logger.exception("Internal scan processing error")
        return jsonify({"error": f"Internal scan processing error: {str(err)}"}), 500
    return jsonify(sanitize_for_json(response_payload))


def evidence_box(box, image, severity, label):
    """Evidence overlay region (percent of the saved image) around an [x0, y0, x1, y1] pixel box."""
    w, h = image.size
    pad = 0.2 * (box[3] - box[1])
    x0, y0 = max(0.0, box[0] - pad), max(0.0, box[1] - pad)
    x1, y1 = min(float(w), box[2] + pad), min(float(h), box[3] + pad)
    return {
        "x_pct": round(x0 / w * 100, 1), "y_pct": round(y0 / h * 100, 1),
        "w_pct": round((x1 - x0) / w * 100, 1), "h_pct": round((y1 - y0) / h * 100, 1),
        "severity": severity, "label": label,
    }


def field_for_text(text, extracted):
    """Name of the extracted field printed on an OCR line ("Full Name" for "Aman Gupta"), if any."""
    line = re.sub(r"[^A-Z0-9]", "", text.upper())
    for field, value in extracted.items():
        key = re.sub(r"[^A-Z0-9]", "", str(value).upper().replace("XXXX", ""))
        if field not in ("Document Type", "Document Status") and len(key) >= 4 and key in line:
            return field
    return None


def run_screening(image, live_image, forensic_gray=None):
    analysis, extracted, evidence_regions = {}, {}, []

    with SCAN_LOCK:
        # 1. Fast Single-Pass OCR
        ocr_result = ocr.extract_text_fast(image)
        raw_ocr_text = ocr_result.get("text", "")
        ocr_lines = ocr_result.get("lines", [])
        # 2. Forensic Tampering Analysis
        tamper_result = tamper.error_level_analysis(image, ocr_text=raw_ocr_text, ocr_boxes=ocr_lines)
        # 3. Altered-text forensics: every printed word compared with the rest of the document
        if forensic_gray is None:
            forensic_gray = text_forensics.prepare_image(image)
        text_scan = text_forensics.analyze(forensic_gray, ocr_lines, scale=forensic_gray.shape[1] / float(image.width))
        # 4. Biometric Face Verification
        match_data = face_match.compare_faces(image, live_image) if live_image is not None else None

    # 5. Document Classification & Field Parsing
    mrz_lines = mrz.extract_mrz_lines(raw_ocr_text)
    doc_type = document_extractor.detect_document_type(raw_ocr_text, mrz_lines)

    mrz_result = {"valid_format": False, "checksum_valid": False, "fields": {}, "errors": []}
    if doc_type == "Passport":
        if len(mrz_lines) == 2:
            mrz_result = mrz.parse_td3(mrz_lines[0], mrz_lines[1])
        extracted = document_extractor.extract_passport_fields(mrz_result)
        analysis["mrz"] = {
            "status": "VALID" if mrz_result["checksum_valid"] else "ALERT",
            "detail": "MRZ checksum valid" if mrz_result["checksum_valid"] else "; ".join(mrz_result["errors"]) or "MRZ invalid"
        }
    elif doc_type == "PAN Card":
        extracted = document_extractor.extract_pan_fields(raw_ocr_text)
        analysis["mrz"] = {"status": "N/A", "detail": "MRZ not applicable to PAN Cards"}
    elif doc_type == "Aadhaar Card":
        extracted = document_extractor.extract_aadhaar_fields(raw_ocr_text)
        analysis["mrz"] = {"status": "N/A", "detail": "MRZ not applicable to Aadhaar documents"}
    else:
        extracted = document_extractor.extract_generic_fields(raw_ocr_text, doc_type)
        analysis["mrz"] = {"status": "N/A", "detail": "MRZ not detected for generic document"}

    analysis["tampering"] = {
        "status": "ALERT" if tamper_result["tampering_detected"] else "VALID",
        "detail": tamper_result["detail"]
    }
    evidence_regions.extend(tamper_result.get("suspicious_regions", []))

    # 6. Altered text and cross-field consistency
    altered = text_scan["suspicious"]
    places = []
    for item in altered:
        field = field_for_text(item["text"], extracted)
        places.append(f"{field} ('{item['text']}')" if field else f"'{item['text']}'")
        evidence_regions.append(evidence_box(item["box"], image, "high", f"Altered Text: {field or item['text']}"))
    if altered:
        analysis["text_integrity"] = {
            "status": "ALERT",
            "detail": f"Text typed or pasted over the document: {', '.join(places)}. {altered[0]['reasons'][0].capitalize()}"
        }
    elif text_scan["judged"]:
        analysis["text_integrity"] = {
            "status": "VALID",
            "detail": f"{text_scan['checked']} printed words compared; all match the document's print and capture"
        }
    else:
        analysis["text_integrity"] = {"status": "N/A", "detail": "Not enough printed text to compare"}

    with SCAN_LOCK:
        read_hindi = (lambda box: ocr.read_hindi(image, box)) if ocr.HIN_AVAILABLE else None
        field_result = field_checks.run(doc_type, extracted, raw_ocr_text, ocr_lines, mrz_result, read_hindi)
    mismatches = field_result["findings"]
    for finding in mismatches:
        if finding.get("box"):
            evidence_regions.append(evidence_box(finding["box"], image, "medium", f"Data Mismatch: {finding['check']}"))
    if mismatches:
        analysis["field_consistency"] = {"status": "ALERT", "detail": "; ".join(f["detail"] for f in mismatches)}
    elif field_result["checked"]:
        analysis["field_consistency"] = {"status": "VALID", "detail": "Consistent: " + ", ".join(field_result["checked"])}
    else:
        analysis["field_consistency"] = {"status": "N/A", "detail": f"No cross-checkable fields read on this {doc_type}"}
    if doc_type == "Aadhaar Card" and read_hindi is None:
        analysis["field_consistency"]["detail"] += " (Hindi/English name check needs Tesseract with the Hindi language pack)"

    if match_data is not None:
        face_result = {**match_data, "compared": True}
        if match_data.get("doc_box"):
            if match_data["match"]:
                evidence_regions.append({
                    **match_data["doc_box"],
                    "severity": "low",
                    "label": f"Verified Portrait ({match_data['similarity']}%)"
                })
            else:
                evidence_regions.append({
                    **match_data["doc_box"],
                    "severity": "high",
                    "label": f"Face Mismatch / Untrusted Portrait ({match_data['similarity']}%)"
                })
        analysis["face_verification"] = {
            "status": "MATCH" if match_data["match"] else "ALERT",
            "detail": match_data["reason"]
        }
    else:
        match_data = {"match": True, "similarity": 100, "reason": "Biometric face comparison omitted"}
        face_result = {**match_data, "compared": False}
        analysis["face_verification"] = {
            "status": "N/A",
            "detail": "Live biometric capture not provided"
        }

    # 7. Document Integrity & Validity Assessment
    expiry_date = parse_dmy(extracted.get("Date of Expiry"))
    expired = bool(expiry_date and expiry_date < date.today())
    if tamper_result["tampering_detected"]:
        analysis["ocr"] = {"status": "ALERT", "detail": "Extraction compromised due to physical/digital alteration"}
        analysis["document_validation"] = {"status": "ALERT", "detail": "Structural integrity failed (Tampering detected)"}
        extracted["Document Status"] = "COMPROMISED / TAMPERED"
    else:
        ocr_ok = bool(raw_ocr_text.strip()) and (extracted.get("Full Name") not in ["UNKNOWN", "UNREADABLE"])
        analysis["ocr"] = {
            "status": "VALID" if ocr_ok else "ALERT",
            "detail": f"{doc_type} recognized, fields extracted" if ocr_ok else "Text unreadable or incomplete"
        }
        if expired:
            analysis["document_validation"] = {"status": "ALERT", "detail": f"{doc_type} expired on {extracted['Date of Expiry']}"}
        else:
            analysis["document_validation"] = {
                "status": "VALID" if doc_type != "Unknown" else "ALERT",
                "detail": f"{doc_type} structure recognized" if doc_type != "Unknown" else "Unrecognized security structure"
            }
        if altered:
            analysis["document_validation"] = {"status": "ALERT", "detail": f"Printed text altered: {', '.join(places)}"}
            extracted["Document Status"] = "COMPROMISED / TEXT ALTERED"

    # 8. Watchlist Verification
    holder = str(extracted.get("Full Name", "")).strip()
    holder_readable = holder.upper() not in UNREADABLE
    doc_numbers = [str(extracted.get(k, "")) for k in ("Passport No.", "PAN Number")]
    doc_numbers = [n for n in doc_numbers if n.upper() not in UNREADABLE]
    watchlist_hits = db.find_watchlist_matches(holder if holder_readable else "", doc_numbers)
    if watchlist_hits:
        hit = watchlist_hits[0]
        analysis["database_verification"] = {"status": "ALERT", "detail": f"Watchlist match: {hit['name']} ({hit['reason']})"}
    elif holder_readable or doc_numbers:
        analysis["database_verification"] = {
            "status": "VALID",
            "detail": f"No match against {len(db.list_watchlist())} active watchlist entries"
        }
    else:
        analysis["database_verification"] = {"status": "N/A", "detail": "Watchlist check skipped: holder name not extracted"}

    # 9. Risk Scoring (weights come from the Rule Engine)
    risk_result = risk.compute_risk(
        doc_type=doc_type,
        mrz_result=mrz_result,
        tamper_result=tamper_result,
        face_result=face_result,
        expiry_flag=expired,
        watchlist_hit=bool(watchlist_hits),
        weights=db.get_rule_weights(),
        text_tampered=bool(altered),
        data_mismatch=bool(mismatches)
    )

    record = {
        "doc_type": doc_type,
        "full_name": extracted.get("Full Name", "UNKNOWN"),
        "nationality": extracted.get("Nationality", "N/A"),
        "risk_score": risk_result["score"],
        "risk_level": risk_result["level"],
        "status": "Completed",
        "scanned_at": db.now_str(),
        "extracted": extracted,
        "analysis": analysis,
        "evidence": sanitize_for_json(evidence_regions),
    }
    doc_id, doc_code = db.insert_document(record)
    image_path = f"/uploads/{doc_code}.jpg"
    try:
        image.save(os.path.join(UPLOAD_DIR, f"{doc_code}.jpg"), "JPEG")
    except OSError as save_err:
        app.logger.warning("Could not save scan image %s: %s", doc_code, save_err)
    audit(f"Document Scanned: {doc_code}", details=f"{doc_type}, {risk_result['level']} ({risk_result['score']}/100)")

    if watchlist_hits:
        referral_reason = f"Watchlist match ({watchlist_hits[0]['reason']}). Detain for secondary inspection."
    elif altered:
        referral_reason = f"Altered document text ({', '.join(places)}). Retain the document and verify the holder with the issuing authority."
    elif not match_data["match"]:
        referral_reason = "Biometric face mismatch. In-person physical identity verification and secondary border officer inspection required."
    elif mismatches:
        referral_reason = f"Field data mismatch ({mismatches[0]['check']}). Verify the document with the issuing authority."
    else:
        referral_reason = "Risk score threshold reached. Manual officer verification required."
    manual_referral = {
        "required": bool(watchlist_hits or altered or mismatches or not match_data["match"] or risk_result["score"] >= 30),
        "reason": referral_reason,
        "search_term": extracted.get("Full Name") or extracted.get("PAN Number") or extracted.get("Aadhaar Number") or doc_code
    }

    return {
        "id": doc_id,
        "doc_code": doc_code,
        "document_type": doc_type,
        "extracted": extracted,
        "analysis": analysis,
        "risk": risk_result,
        "evidence": evidence_regions,
        "manual_referral": manual_referral,
        "image_path": image_path
    }


# ---------------------------------------------------------------- files

@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route("/")
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:path>")
def serve_frontend_static(path):
    file_path = os.path.join(FRONTEND_DIR, path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return send_from_directory(FRONTEND_DIR, path)
    if path.startswith("api/"):
        return jsonify({"error": "Not Found"}), 404
    return send_from_directory(FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes")
    app.run(debug=debug, host="0.0.0.0", port=port)
