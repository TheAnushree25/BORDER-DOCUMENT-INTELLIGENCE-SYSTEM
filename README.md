# Border Document Intelligence System
### AI-Powered Document Screening & Fraud Detection Platform

A border-control screening platform built for Smart India Hackathon (SIH). It reads passports, PAN cards and Aadhaar cards with OCR, verifies ICAO Doc 9303 TD3 Machine Readable Zone (MRZ) check digits, looks for image tampering, compares the document portrait with a live webcam capture, checks the holder against a watchlist and computes a 0–100 risk score with a recommendation.

---

## 🚀 Run it locally

Python 3.10 or newer:

```bash
pip install -r requirements.txt
python app.py
```

Open **http://localhost:5000**. Flask serves both the web UI and the API, so there is no separate frontend server.

- **Default login**: `admin` / `Admin@123`. While that default password is active, the login screen offers a one-click demo login. Set `ADMIN_PASSWORD` before the first start (or change it in the admin panel) and the demo button disappears.
- **Tesseract OCR (optional fallback)**: RapidOCR is the main engine and installs with pip. Tesseract is used when RapidOCR returns too little text: `winget install UB-Mannheim.TesseractOCR` (Windows), `sudo apt-get install tesseract-ocr` (Linux), `brew install tesseract` (macOS).
- **Sample documents**: `test_samples/` has synthetic passport, PAN and Aadhaar images to try.
- **Webcam**: browsers only allow the camera on `http://localhost` or `https://`.

### Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The tests start the real app against a temporary database, scan the sample documents end to end, and check login, roles, the watchlist and the rule engine.

---

## ⚙️ Configuration

All settings are environment variables:

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `ADMIN_PASSWORD` | `Admin@123` | Password for the `admin` account, used when the database is first created. |
| `SECRET_KEY` | generated and stored in the database | Signs login sessions. Set a long random value in production. |
| `DATA_DIR` | `backend/` (Docker: `/app/data`) | Where the SQLite database and scanned images are stored. Point it at a persistent disk to keep data. |
| `SESSION_COOKIE_SECURE` | `false` | Set to `true` when the site is served over HTTPS. |
| `WEB_CONCURRENCY` | `1` | Gunicorn worker processes. Each one loads its own models (~300 MB of RAM). |
| `PORT` | `5000` (Docker: `10000`) | Port to listen on. Cloud hosts set this automatically. |
| `TZ` | `Asia/Kolkata` in Docker | Time zone for scan timestamps and shift reports. |

Deployment instructions: **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)**.

---

## 🏗️ Project structure

```
├── app.py / wsgi.py           # Entry points (python app.py, gunicorn wsgi:app)
├── backend/
│   ├── app.py                 # Flask API: session login, roles, screening pipeline
│   ├── database.py            # SQLite: documents, users, watchlist, audit log, rules
│   ├── models/                # YuNet face detector + SFace face recognizer (ONNX)
│   ├── create_sample_passport.py
│   └── utils/
│       ├── ocr.py             # RapidOCR with Tesseract fallback, card auto-crop
│       ├── mrz.py             # ICAO 9303 TD3 parser and all five check digits
│       ├── document_extractor.py  # Passport / PAN / Aadhaar field parsing
│       ├── tamper.py          # Error Level Analysis and paint/whiteout detection
│       ├── face_match.py      # YuNet + SFace matching, HOG fallback, liveness hint
│       └── risk.py            # Weighted risk score
├── frontend/                  # Single-page UI (index.html, script.js, style.css)
├── tests/                     # pytest suite
├── test_samples/              # Synthetic documents
├── Dockerfile, docker-compose.yml, render.yaml, railway.json, Procfile, gunicorn.conf.py
└── DEPLOYMENT_GUIDE.md
```

---

## 🔑 Users & roles

Every API endpoint except `/health`, `/api/health`, login and `/api/auth/config` requires a signed-in session, including the scanned images under `/uploads/`. Passwords are stored as Werkzeug password hashes.

| Role | Can do |
| :--- | :--- |
| `ADMIN` | Everything, including users, rule weights, exports, database backup and maintenance. |
| `SENIOR_INSPECTOR`, `OFFICER`, `ANALYST` | Scan documents, view records and alerts, manage the watchlist, search, view the audit log. |

---

## 📡 REST API

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/login` | Public | Signs in (`username`, `password`) and starts a session. |
| `POST` | `/api/auth/logout` | Signed in | Ends the session. |
| `GET` | `/api/auth/me` | Signed in | Current user. |
| `GET` | `/api/auth/config` | Public | Whether the one-click demo login is available. |
| `POST` | `/api/auth/change-password` | Signed in | Changes your password (`current_password`, `new_password`). |
| `POST` | `/api/scan` | Signed in | Runs the screening pipeline on `document` (+ optional `live_face`) images. |
| `GET` | `/api/stats` | Signed in | Today / previous shift / all-time counts. |
| `GET` | `/api/documents` | Signed in | Scan history (`limit`, `offset`, `risk_level`). |
| `GET` | `/api/database-check?q=` | Signed in | Searches stored scans by name, ID or number. |
| `GET` / `POST` | `/api/watchlist` | Signed in | Lists or adds watchlist entries. |
| `DELETE` | `/api/watchlist/<id>` | Signed in | Removes a watchlist entry. |
| `GET` | `/api/audit-logs` | Signed in | Audit trail. |
| `GET` / `POST` | `/api/rules` | Read: signed in, write: Admin | Risk rule weights (0–100). |
| `GET` / `POST` | `/api/users` | Admin | Lists or enrolls users. |
| `DELETE` | `/api/users/<id>` | Admin | Revokes a user (their session ends immediately). |
| `GET` | `/api/admin/export-report?format=csv\|json` | Admin | Downloads the scan report. |
| `GET` | `/api/admin/backup-db` | Admin | Downloads a consistent copy of the SQLite database. |
| `POST` | `/api/admin/vacuum-db` | Admin | Integrity check + VACUUM. |
| `GET` | `/api/diagnostics/db` | Signed in | Record counts and engine availability. |
| `GET` | `/health`, `/api/health` | Public | Health check for load balancers. |

---

## 🔍 What each check really does

| Check | Type | Implementation |
| :--- | :--- | :--- |
| **MRZ validation** | Real check | ICAO 9303 TD3 7-3-1 check digits for document number, date of birth, expiry, optional data and the composite digit. |
| **Expiry** | Real check | Passport expiry date from the MRZ compared with today. |
| **OCR extraction** | Real check | RapidOCR (ONNX) with Tesseract fallback; regex parsing for PAN, Aadhaar and passport fields. |
| **Tamper detection** | Heuristic | Error Level Analysis, flat digital-paint/whiteout detection and compression-grid anomalies. Expect false positives and misses. |
| **Face verification** | Prototype | YuNet detection + SFace embeddings (cosine similarity), HOG fallback, blur-based liveness hint. Not certified biometrics. |
| **Watchlist** | Simulated registry | Local SQLite list, matched on the holder's name (word order ignored) or document number. |
| **Risk score** | Rule engine | Sum of the Rule Engine weights; ≥ 30 is Medium, ≥ 60 is High. Tampering and watchlist matches are always High unless their weight is set to 0. |

---

## ⚖️ Prototype limitations

- The watchlist and "central registry" are a local demo database, not a government system.
- Face matching and tamper detection are screening aids for a hackathon prototype. Border gates use certified biometric systems (ISO/IEC 19794-5) and trained document examiners.
- Scanned identity documents are personal data. Do not commit `backend/uploads/` or the database (both are in `.gitignore`), and do not upload real people's documents to a public demo.
