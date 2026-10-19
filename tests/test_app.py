"""End-to-end checks of the API with the real OCR and forensics pipeline.

Run from the project root:
    pip install -r requirements-dev.txt
    pytest
"""
import io
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "test_samples")

# The app reads DATA_DIR when it is imported, so point it at a throwaway directory first.
os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="bdis-test-")
os.environ.pop("ADMIN_PASSWORD", None)
sys.path.insert(0, ROOT)

from backend.app import app  # noqa: E402
from backend.utils import mrz, risk  # noqa: E402


def login(client, username="admin", password="Admin@123"):
    return client.post("/api/auth/login", json={"username": username, "password": password})


def scan(client, sample):
    with open(os.path.join(SAMPLES, sample), "rb") as f:
        payload = {"document": (io.BytesIO(f.read()), sample)}
    return client.post("/api/scan", data=payload, content_type="multipart/form-data")


@pytest.fixture()
def client():
    return app.test_client()


@pytest.fixture()
def admin(client):
    assert login(client).status_code == 200
    return client


def test_health_and_ui_are_public(client):
    assert client.get("/health").status_code == 200
    assert client.get("/api/health").status_code == 200
    assert b"BORDER DOCUMENT INTELLIGENCE SYSTEM" in client.get("/").data


@pytest.mark.parametrize("path", [
    "/api/stats", "/api/documents", "/api/watchlist", "/api/users", "/api/audit-logs",
    "/api/admin/backup-db", "/api/admin/export-report?format=csv", "/uploads/DOC-1501.jpg",
])
def test_data_requires_login(client, path):
    assert client.get(path).status_code == 401


def test_wrong_password_is_rejected(client):
    assert login(client, password="not-the-password").status_code == 401
    assert client.get("/api/stats").status_code == 401


def test_demo_login_is_offered_while_default_password_is_set(client):
    assert client.get("/api/auth/config").get_json() == {"demo_login": True}


def test_stats_on_an_empty_database(admin):
    # Used to raise NameError (missing timedelta import) whenever no scan existed from an earlier day.
    res = admin.get("/api/stats")
    assert res.status_code == 200
    assert res.get_json()["all_total"] == 0


def test_passport_scan_end_to_end(admin):
    res = scan(admin, "sample_passport.jpg")
    assert res.status_code == 200, res.get_data(as_text=True)
    body = res.get_json()
    assert body["document_type"] == "Passport"
    assert body["analysis"]["mrz"]["status"] == "VALID"
    assert body["extracted"]["Full Name"] == "ABHISHEK YADAV"
    assert body["extracted"]["Nationality"] == "IND"
    assert body["analysis"]["database_verification"]["status"] == "VALID"

    # The evidence image is stored and served to logged-in users only.
    assert admin.get(body["image_path"]).status_code == 200
    assert app.test_client().get(body["image_path"]).status_code == 401
    assert admin.get("/api/documents").get_json()[0]["doc_code"] == body["doc_code"]


def test_watchlist_match_uses_rule_engine_weight(admin):
    assert admin.post("/api/rules", json={"watchlist_hit": 55}).status_code == 200
    entry = admin.post("/api/watchlist", json={"name": "ujjwal  gond", "reason": "Test alert"}).get_json()
    try:
        body = scan(admin, "sample_pancard.jpg").get_json()
        assert body["document_type"] == "PAN Card"
        assert body["analysis"]["database_verification"]["status"] == "ALERT"
        assert body["risk"]["factors"]["Watchlist Match"] == 55
        assert body["risk"]["level"] == "High Risk"
        assert body["manual_referral"]["required"] is True
    finally:
        admin.delete(f"/api/watchlist/{entry['id']}")
        admin.post("/api/rules", json={"watchlist_hit": 60})


def test_rule_weights_are_validated(admin):
    assert admin.post("/api/rules", json={"tampering": 500}).status_code == 400
    assert admin.post("/api/rules", json={"tampering": "abc"}).status_code == 400


def test_officer_cannot_use_admin_endpoints(admin):
    res = admin.post("/api/users", json={
        "username": "officer_test", "password": "secret12", "full_name": "Test Officer", "role": "OFFICER",
    })
    assert res.status_code == 201
    officer = app.test_client()
    assert login(officer, "officer_test", "secret12").status_code == 200
    assert officer.get("/api/stats").status_code == 200
    for path in ["/api/users", "/api/admin/backup-db", "/api/admin/export-report?format=csv"]:
        assert officer.get(path).status_code == 403
    assert officer.post("/api/rules", json={"tampering": 1}).status_code == 403

    # Revoking the account ends its session immediately.
    assert admin.delete(f"/api/users/{res.get_json()['id']}").status_code == 200
    assert officer.get("/api/stats").status_code == 401


def test_admin_backup_and_export(admin):
    backup = admin.get("/api/admin/backup-db")
    assert backup.status_code == 200
    assert backup.data[:16] == b"SQLite format 3\x00"
    report = admin.get("/api/admin/export-report?format=csv")
    assert report.status_code == 200
    assert b"Document ID" in report.data


def test_password_change_turns_off_demo_login(admin):
    change = "/api/auth/change-password"
    assert admin.post(change, json={"current_password": "wrong", "new_password": "NewPass#1"}).status_code == 403
    assert admin.post(change, json={"current_password": "Admin@123", "new_password": "NewPass#1"}).status_code == 200
    try:
        assert admin.get("/api/auth/config").get_json() == {"demo_login": False}
        assert login(app.test_client()).status_code == 401
        assert login(app.test_client(), password="NewPass#1").status_code == 200
    finally:
        admin.post(change, json={"current_password": "NewPass#1", "new_password": "Admin@123"})


def test_mrz_check_digits_match_icao_specimen():
    # ICAO Doc 9303 Part 4 specimen passport
    line1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
    line2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
    result = mrz.parse_td3(line1, line2)
    assert result["checksum_valid"], result["errors"]
    assert result["fields"]["date_of_birth"] == "12/08/1974"

    assert "composite checksum mismatch" in mrz.parse_td3(line1, line2[:-1] + "7")["errors"]
    assert "personal_number checksum mismatch" in mrz.parse_td3(line1, line2[:42] + "50")["errors"]


def test_tampering_escalates_unless_rule_is_off():
    clean = {"tampering_detected": False}
    tampered = {"tampering_detected": True}
    assert risk.compute_risk("PAN Card", {}, clean, None, False, False)["level"] == "Low Risk"
    assert risk.compute_risk("PAN Card", {}, tampered, None, False, False)["level"] == "High Risk"
    assert risk.compute_risk("PAN Card", {}, tampered, None, False, False, weights={"tampering": 0})["level"] == "Low Risk"
