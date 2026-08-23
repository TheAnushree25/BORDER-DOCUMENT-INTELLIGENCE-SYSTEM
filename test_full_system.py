import urllib.request
import urllib.parse
import json
import os
import sys

BASE_URL = "http://localhost:5000"

def test_pipeline():
    print("========================================")
    print("STARTING FULL END-TO-END SYSTEM TEST")
    print("========================================")

    # 1. Health check
    res = urllib.request.urlopen(f"{BASE_URL}/api/health")
    health = json.loads(res.read().decode())
    assert health["status"] == "ok", "Health check failed"
    print("[OK] 1. Health check passed:", health["services"])

    # 2. Login as admin
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())
    login_data = json.dumps({"username": "admin", "password": "Admin@123"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=login_data, headers={"Content-Type": "application/json"})
    res = opener.open(req)
    login_resp = json.loads(res.read().decode())
    assert login_resp["status"] == "ok", "Login failed"
    print("[OK] 2. Admin login passed:", login_resp["user"]["full_name"], f"({login_resp['user']['role']})")

    # 3. Check /api/auth/me
    req = urllib.request.Request(f"{BASE_URL}/api/auth/me")
    res = opener.open(req)
    me_resp = json.loads(res.read().decode())
    assert me_resp["authenticated"] is True, "Auth me failed"
    print("[OK] 3. Session persistence check passed:", me_resp["user"]["username"])

    # 4. Seed demo data
    req = urllib.request.Request(f"{BASE_URL}/api/demo/seed", data=b"{}", headers={"Content-Type": "application/json"})
    res = opener.open(req)
    seed_resp = json.loads(res.read().decode())
    assert seed_resp["status"] == "ok", "Seed failed"
    print("[OK] 4. Demo data seed passed:", seed_resp["message"])

    # 5. Check stats
    res = opener.open(f"{BASE_URL}/api/stats")
    stats = json.loads(res.read().decode())
    print("[OK] 5. Current screening stats:", stats)

    # 6. List documents
    res = opener.open(f"{BASE_URL}/api/documents?limit=5")
    docs = json.loads(res.read().decode())
    assert len(docs) > 0, "No documents found"
    print(f"[OK] 6. List documents passed ({len(docs)} records retrieved). First doc: {docs[0]['doc_code']} ({docs[0]['full_name']})")

    # 7. Check priority alerts
    res = opener.open(f"{BASE_URL}/api/alerts")
    alerts = json.loads(res.read().decode())
    print(f"[OK] 7. Priority risk alerts queue passed: {len(alerts)} alerts active")

    # 8. Check Watchlist
    res = opener.open(f"{BASE_URL}/api/watchlist")
    watchlist = json.loads(res.read().decode())
    assert len(watchlist) > 0, "No watchlist entries found"
    print(f"[OK] 8. Watchlist passed: {len(watchlist)} registered entries. Top entry: {watchlist[0]['name']}")

    # 9. Check Rule Engine
    res = opener.open(f"{BASE_URL}/api/rules")
    rules = json.loads(res.read().decode())
    assert len(rules) > 0, "No rules found"
    print(f"[OK] 9. Rule engine passed: {len(rules)} active forensic inspection rules")

    # 10. Check Audit Logs
    res = opener.open(f"{BASE_URL}/api/audit-logs?limit=5")
    audit = json.loads(res.read().decode())
    assert len(audit) > 0, "No audit logs found"
    print(f"[OK] 10. Audit trail passed: {len(audit)} recent logged security events")

    # 11. Check Database Diagnostics
    res = opener.open(f"{BASE_URL}/api/database/status")
    db_status = json.loads(res.read().decode())
    print(f"[OK] 11. Database check passed: Size {db_status['db_size_formatted']}, Counts: {db_status['counts']}")

    # 12. Check Reports Summary
    res = opener.open(f"{BASE_URL}/api/reports/summary")
    rep = json.loads(res.read().decode())
    print(f"[OK] 12. Reports summary passed: High risk rate {rep['high_risk_rate']}%, Document types: {rep['type_distribution']}")

    print("========================================")
    print("ALL 12 INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("========================================")

if __name__ == "__main__":
    test_pipeline()
