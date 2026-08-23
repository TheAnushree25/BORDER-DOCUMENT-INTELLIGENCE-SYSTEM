# Border Document Intelligence System
### AI-Powered Document Screening &amp; Fraud Detection Platform

A professional Border Security / Immigration Document Intelligence and Fraud Detection screening platform for Smart India Hackathon (SIH) and border control checkpoints. It processes international passports and travel credentials, extracts text via OCR, verifies ICAO Doc 9303 TD3 Machine Readable Zone (MRZ) checksums, analyzes image tampering artifacts using Error Level Analysis (ELA), matches document portrait photos with real-time live webcam captures, queries active watchlists, and computes a composite risk score with dynamic decision recommendations.

---

## 🏗️ Architecture & Project Directory Tree

```
border-doc-intel/
├── backend/
│   ├── app.py                     # Flask REST API with Session Auth & RBAC
│   ├── database.py                # SQLite persistence (Documents, Users, Watchlist, Audit, Rules, Settings)
│   ├── requirements.txt           # Python dependencies
│   ├── border_intel.db            # SQLite database file (auto-initialized)
│   ├── create_sample_passport.py  # Test passport generation utility
│   ├── uploads/                   # Scanned document image repository (auto-created)
│   └── utils/
│       ├── __init__.py
│       ├── ocr.py                 # Pytesseract OCR extraction & preprocessing with Windows auto-discovery
│       ├── mrz.py                 # ICAO 9303 TD3 parser & 7-3-1 modulus-10 checksum engine
│       ├── tamper.py              # Error Level Analysis (ELA 90Q) manipulation detection
│       ├── face_match.py          # OpenCV Haar cascade face detection & 2D HSV histogram correlation
│       └── risk.py                # Dynamic rule-weighted risk scoring engine
├── frontend/
│   ├── index.html                 # Complete Single Page Application (11 functional views & modals)
│   ├── style.css                  # Dark navy design system, responsive grids & toast alerts
│   └── script.js                  # Frontend state machine, webcam controller & Canvas gauge
├── test_samples/
│   └── sample_passport.jpg        # Synthetic passport test sample
├── PROBLEM_STATEMENT.md           # Problem framing, data flow diagram & panel mapping
└── README.md                      # Complete system documentation
```

---

## 🔑 Default Administrator Credentials

For evaluation and demonstration purposes, a default administrative account is automatically seeded upon first database initialization:

- **Username**: `admin`
- **Password**: `Admin@123`
- **Role**: `ADMIN` *(Full access to dashboard, screening, user management, audit trail, rule engine, and settings)*

> **Security Note**: Passwords are securely hashed using PBKDF2:SHA256 (`werkzeug.security.generate_password_hash`) and are never stored or transmitted in plain text.

---

## 🚀 Quickstart & Execution Guide

### 1. Install Python Dependencies
Python 3.10+ is recommended:
```powershell
# From project root
pip install -r backend/requirements.txt
```

### 2. Optional: Tesseract OCR Binary
Tesseract OCR is auto-detected at standard system locations (`C:\Program Files\Tesseract-OCR\tesseract.exe`, `/usr/bin/tesseract`, etc.):
- **Windows**: `winget install UB-Mannheim.TesseractOCR`
- **Linux (Ubuntu/Debian)**: `sudo apt-get install tesseract-ocr`
- **macOS**: `brew install tesseract`

### 3. Start the Backend API Server
```powershell
python backend/app.py
```
*Backend server runs on `http://127.0.0.1:5000` with active CORS support.*

### 4. Serve the Frontend Application
In a separate terminal, serve the frontend directory using Python's built-in HTTP server:
```powershell
python -m http.server 8000 --directory frontend
```
*Access the interface in any modern browser at `http://localhost:8000`.*

---

## 📷 Live Webcam Biometric Face Capture

The system includes real webcam capture powered by HTML5 `navigator.mediaDevices.getUserMedia`:
- Click **"Capture Live Face"** on the dashboard or verification terminal to open the live webcam modal.
- Modern web browsers require a **secure context** (`http://localhost`, `http://127.0.0.1`, or `https://`) to grant camera access.
- When you click **"Capture Face"**, the current video frame is captured to a Blob, sent as `live_face` in `multipart/form-data`, and compared against the face detected on the travel document.

---

## 📡 REST API Reference

### Authentication & Users
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/login` | Public | Authenticates officer and creates session. |
| `POST` | `/api/auth/logout` | Authenticated | Terminates active session. |
| `GET` | `/api/auth/me` | Authenticated | Returns current authenticated user profile. |
| `GET` | `/api/users` | Admin Only | Lists all officer and analyst accounts. |
| `POST` | `/api/users` | Admin Only | Creates a new user account with role assignment. |
| `PUT` | `/api/users/<id>` | Admin Only | Updates user details, role, or password. |
| `DELETE` | `/api/users/<id>` | Admin Only | Deletes user account. |

### Document Intelligence & Screening
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/scan` | Authenticated | Runs full screening pipeline (`document` image + optional `live_face`). |
| `GET` | `/api/stats` | Authenticated | Returns aggregate count of Scanned, High, Medium, and Low risk docs. |
| `GET` | `/api/documents` | Authenticated | Filtered, searchable, and paginated document scan history. |
| `GET` | `/api/documents/<id>` | Authenticated | Fetches full forensic inspection record by ID. |
| `GET` | `/api/alerts` | Authenticated | Returns priority queue of High & Medium risk alerts. |

### Watchlist, Rules, Audit & System
| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` / `POST` | `/api/watchlist` | Authenticated | Manages national security watchlist entries and flags. |
| `DELETE` | `/api/watchlist/<id>` | Authenticated | Deletes watchlist entry. |
| `GET` / `PUT` | `/api/rules` | Admin Only | Manages risk factor weights and enabled status. |
| `GET` | `/api/audit-logs` | Authenticated | Fetches chronological immutable audit trail. |
| `GET` | `/api/database/status`| Authenticated | Returns database file size, record counts, and diagnostics. |
| `GET` / `PUT` | `/api/settings` | Admin Only | Reads and updates risk thresholds and system config. |
| `POST` | `/api/demo/seed` | Admin / Demo | Seeds 5 realistic demonstration travel documents. |
| `POST` | `/api/demo/clear` | Admin / Demo | Clears document scan records for testing resets. |

---

## 🔍 Verification Matrix: Real Checks vs. Heuristics vs. Stubs

| Inspection Module | Type | Technical Implementation | Description |
| :--- | :--- | :--- | :--- |
| **MRZ Checksum Validation** | **Real Check** | ICAO Doc 9303 TD3 standard (weights `[7, 3, 1]`, mod 10) | Mathematical modulus-10 checksum validation of document number, DOB, and expiry dates. |
| **Tamper Detection (ELA)** | **Heuristic** | Error Level Analysis (Pillow + NumPy) | Recompresses image at 90 quality to locate digital splicing and pixel level anomalies. |
| **Facial Verification** | **Prototype** | OpenCV Haar Cascade + 2D HSV Histogram Correlation | Detects face bounding boxes and compares color histogram correlation between doc and live webcam photo. |
| **OCR Text Extraction** | **Real Check** | Tesseract OCR (Pytesseract) | Extracts visual text zones and MRZ lines from travel document images. |
| **Risk Scoring Engine** | **Rule Engine** | Dynamic database-driven multi-factor weighted aggregation | Computes 0–100 risk score and assigns Low, Medium, or High risk tiers. |
| **Watchlist / Central Registry** | **Simulated** | SQLite Local Lookup | Validates travelers against local security alerts and Interpol demo notices. |

---

## ⚖️ Data Honesty & Prototype Limitations

- **Simulated Databases**: Watchlist and Central Registry verification queries a local SQLite database designed for demonstration and hackathon evaluation.
- **Biometric Accuracy**: Facial verification uses OpenCV Haar cascades and HSV histogram correlation as an educational and prototype screening heuristic. Biometric-grade border gates utilize deep metric embeddings (e.g. ArcFace/FaceNet with ISO/IEC 19794-5 standards).
#   B O R D E R - D O C U M E N T - I N T E L L I G E N C E - S Y S T E M  
 #   B O R D E R - D O C U M E N T - I N T E L L I G E N C E - S Y S T E M  
 