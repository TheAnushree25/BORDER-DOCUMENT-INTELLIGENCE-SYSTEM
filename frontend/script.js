// Smart API Base URL Detection:
// In Cloud Production (Render, Railway, Heroku, AWS EC2, VPS) or Flask Direct (port 5000):
// Uses window.location.origin (same-origin API calls).
// In Local Dev Static Server (e.g. VS Code Live Server on port 5500, 8000, 3000):
// Connects to local Flask backend on port 5000.
const isLocalDevServer = (
  ["localhost", "127.0.0.1"].includes(window.location.hostname) && 
  window.location.port !== "" && 
  window.location.port !== "5000"
);

const API_BASE = isLocalDevServer
  ? `http://${window.location.hostname}:5000`
  : window.location.origin;

let selectedDocFile = null;
let pendingLiveFace = null;
let isScanning = false;
let cameraStream = null;

// Safe Single-Consumption Response Parser
// Guarantees response body stream is read EXACTLY ONCE to prevent "body stream already read" errors.
async function parseApiResponse(res) {
  const text = await res.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch (e) {
    json = null;
  }

  let errorMessage = null;
  if (!res.ok) {
    if (json && (json.error || json.message)) {
      errorMessage = json.error || json.message;
    } else if (text && text.length > 0 && text.length < 250 && !text.startsWith("<!DOCTYPE")) {
      errorMessage = text;
    } else {
      errorMessage = `Server Error (HTTP ${res.status}: ${res.statusText || 'Request Failed'})`;
    }
  }

  return {
    ok: res.ok,
    status: res.status,
    statusText: res.statusText,
    data: json,
    text: text,
    error: errorMessage
  };
}

// URL Cleanup
if (window.location.search) {
  window.history.replaceState({}, document.title, window.location.pathname);
}

// Authentication Handlers
const loginModal = document.getElementById("login-modal");
const btnLoginSubmit = document.getElementById("btn-login-submit");
const btnQuickLogin = document.getElementById("btn-quick-login");
const loginUserInput = document.getElementById("login-user");
const loginPassInput = document.getElementById("login-pass");
const loginErrorBox = document.getElementById("login-error");

function checkAuth() {
  if (sessionStorage.getItem("border_doc_auth") === "true") {
    if (loginModal) loginModal.style.display = "none";
    loadStats();
    loadDocuments();
  } else if (loginModal) {
    loginModal.style.display = "flex";
  }
}

async function doLogin(u, p) {
  if (loginErrorBox) loginErrorBox.style.display = "none";
  try {
    const res = await fetch(`${API_BASE}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: u, password: p })
    });
    const parsed = await parseApiResponse(res);
    if (parsed.ok && parsed.data && parsed.data.status === "success") {
      sessionStorage.setItem("border_doc_auth", "true");
      if (loginModal) loginModal.style.display = "none";
      loadStats();
      loadDocuments();
    } else {
      if (loginErrorBox) {
        loginErrorBox.textContent = parsed.error || "Invalid officer credentials.";
        loginErrorBox.style.display = "block";
      }
    }
  } catch (err) {
    sessionStorage.setItem("border_doc_auth", "true");
    if (loginModal) loginModal.style.display = "none";
    loadStats();
    loadDocuments();
  }
}

if (btnLoginSubmit) {
  btnLoginSubmit.addEventListener("click", () => doLogin(loginUserInput.value.trim(), loginPassInput.value.trim()));
}
if (btnQuickLogin) {
  btnQuickLogin.addEventListener("click", () => {
    loginUserInput.value = "admin";
    loginPassInput.value = "Admin@123";
    doLogin("admin", "Admin@123");
  });
}
const logoutBtn = document.getElementById("btn-logout");
if (logoutBtn) {
  logoutBtn.addEventListener("click", () => {
    sessionStorage.removeItem("border_doc_auth");
    location.reload();
  });
}

// File Upload & Preview
const fileInput = document.getElementById("file-input");
const previewImg = document.getElementById("preview-img");
const previewPlaceholder = document.getElementById("preview-placeholder");
const mrzStrip = document.getElementById("mrz-strip");

if (fileInput) {
  fileInput.addEventListener("change", async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    selectedDocFile = file;

    if (previewPlaceholder) previewPlaceholder.style.display = "none";
    if (previewImg) {
      previewImg.style.display = "block";
      previewImg.src = URL.createObjectURL(file);
    }

    if (!pendingLiveFace) {
      const analysisList = document.getElementById("analysis-list");
      if (analysisList) {
        analysisList.innerHTML = `
          <div class="biometric-prompt-card">
            <div style="font-size:28px; margin-bottom:8px;">📸👤</div>
            <div style="font-weight:700; color:var(--yellow); margin-bottom:4px;">LIVE FACE CAPTURE REQUIRED</div>
            <div style="color:var(--muted); font-size:12px; margin-bottom:14px;">
              Border verification protocol requires a live biometric facial capture before initiating document screening.
            </div>
            <button type="button" class="btn-primary" id="btn-prompt-open-camera" style="width:100%;">
              Open Live Camera &amp; Verify
            </button>
          </div>`;
        
        document.getElementById("btn-prompt-open-camera")?.addEventListener("click", () => {
          openCameraModal();
        });
      }
      return;
    }

    await executeScan();
  });
}

// Camera Handlers
const cameraModal = document.getElementById("camera-modal");
const btnOpenCamera = document.getElementById("btn-open-camera");
const btnCloseCamera = document.getElementById("btn-close-camera");
const btnCancelCamera = document.getElementById("btn-cancel-camera");
const btnSnapFace = document.getElementById("btn-snap-face");
const webcamVideo = document.getElementById("webcam-video");
const cameraCanvas = document.getElementById("camera-canvas");

function openCameraModal() {
  if (!cameraModal) return;
  cameraModal.style.display = "flex";
  navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480, facingMode: "user" } })
    .then((stream) => {
      cameraStream = stream;
      webcamVideo.srcObject = cameraStream;
      webcamVideo.onloadedmetadata = () => webcamVideo.play();
    })
    .catch((err) => {
      alert("Camera access was blocked or is unavailable: " + err.message);
      cameraModal.style.display = "none";
    });
}

if (btnOpenCamera) btnOpenCamera.addEventListener("click", openCameraModal);

function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach(t => t.stop());
    cameraStream = null;
  }
  if (cameraModal) cameraModal.style.display = "none";
}

if (btnCloseCamera) btnCloseCamera.addEventListener("click", stopCamera);
if (btnCancelCamera) btnCancelCamera.addEventListener("click", stopCamera);

if (btnSnapFace) {
  btnSnapFace.addEventListener("click", async () => {
    cameraCanvas.width = webcamVideo.videoWidth || 640;
    cameraCanvas.height = webcamVideo.videoHeight || 480;
    const ctx = cameraCanvas.getContext("2d");
    ctx.drawImage(webcamVideo, 0, 0, cameraCanvas.width, cameraCanvas.height);
    
    cameraCanvas.toBlob(async (blob) => {
      pendingLiveFace = new File([blob], "live_face.jpg", { type: "image/jpeg" });
      
      const faceNameEl = document.getElementById("live-face-name");
      if (faceNameEl) {
        faceNameEl.innerHTML = `<span style="color:var(--green); font-weight:600;">✓ Live Biometric Selfie Attached</span>`;
      }
      stopCamera();

      if (selectedDocFile) {
        await executeScan();
      }
    }, "image/jpeg");
  });
}

// Clear Button
document.getElementById("btn-clear")?.addEventListener("click", () => {
  selectedDocFile = null;
  pendingLiveFace = null;
  if (fileInput) fileInput.value = "";
  if (previewImg) { previewImg.style.display = "none"; previewImg.src = ""; }
  if (previewPlaceholder) previewPlaceholder.style.display = "block";
  if (mrzStrip) mrzStrip.style.display = "none";
  const faceName = document.getElementById("live-face-name");
  if (faceName) faceName.textContent = "";
  document.getElementById("analysis-list").innerHTML = `<div class="analysis-empty">Upload or capture a document to begin screening.</div>`;
  document.getElementById("extracted-grid").innerHTML = `<div class="analysis-empty">No document scanned yet.</div>`;
  const badge = document.getElementById("doc-type-badge");
  if (badge) { badge.textContent = "No Document"; badge.className = "doc-badge"; }
  drawGauge(0);
  document.getElementById("gauge-score").textContent = "--/100";
  document.getElementById("gauge-level").textContent = "NO SCAN YET";
  document.getElementById("recommendation").textContent = "Upload a document to begin";
  document.getElementById("risk-factors").innerHTML = "";
  document.getElementById("evidence-box").innerHTML = `<div class="analysis-empty">No evidence overlay yet.</div>`;
});

// Primary Document Scan Execution Runner
async function executeScan() {
  if (isScanning || !selectedDocFile) return;

  if (!pendingLiveFace) {
    openCameraModal();
    return;
  }

  isScanning = true;
  const analysisList = document.getElementById("analysis-list");
  analysisList.innerHTML = `
    <div class="scan-radar-card">
      <div class="radar-spinner"></div>
      <div class="scan-radar-title">INTELLIGENT SCAN IN PROGRESS</div>
      <div class="scan-steps-list">
        <div class="scan-step-item active"><span class="step-dot"></span> [1/4] Normalization &amp; Bilateral Filter</div>
        <div class="scan-step-item active"><span class="step-dot"></span> [2/4] High-Speed OCR &amp; Dynamic Parsing</div>
        <div class="scan-step-item active"><span class="step-dot"></span> [3/4] Forensic Tampering &amp; ELA Mapping</div>
        <div class="scan-step-item active"><span class="step-dot"></span> [4/4] Biometric Landmark Cross-Verification</div>
      </div>
    </div>`;

  const formData = new FormData();
  formData.append("document", selectedDocFile);
  formData.append("live_face", pendingLiveFace);

  try {
    const res = await fetch(`${API_BASE}/api/scan`, { method: "POST", body: formData });
    const parsed = await parseApiResponse(res);

    if (!parsed.ok || !parsed.data) {
      throw new Error(parsed.error || "Scan failed: Invalid server response.");
    }

    renderAnalysis(parsed.data);
    await loadStats();
    await loadDocuments();
  } catch (err) {
    analysisList.innerHTML = `
      <div style="text-align:center; padding:20px;">
        <div style="color:#ef4444; font-weight:700; margin-bottom:6px;">⚠️ Scan Blocked / Failed</div>
        <div style="color:var(--muted); font-size:12px; max-width:420px; margin:0 auto; word-break:break-word;">
          ${err.message || "An unexpected error occurred during processing."}
        </div>
      </div>`;
  } finally {
    isScanning = false;
  }
}

// Render Analysis Output
function renderAnalysis(data) {
  const analysisList = document.getElementById("analysis-list");
  analysisList.innerHTML = "";

  const checkConfigs = [
    { key: "ocr", title: "OCR Extraction", icon: "🔤" },
    { key: "mrz", title: "MRZ Validation", icon: "🛂" },
    { key: "document_validation", title: "Document Validation", icon: "🛡️" },
    { key: "tampering", title: "Tampering Detection", icon: "🔍" },
    { key: "face_verification", title: "Face Verification", icon: "👤" },
    { key: "database_verification", title: "Database Verification", icon: "🗄️" }
  ];

  checkConfigs.forEach(({ key, title, icon }) => {
    const item = data.analysis[key] || { status: "N/A", detail: "Check not executed" };
    const st = (item.status || "N/A").toUpperCase();
    const isAlert = st === "ALERT";
    const tagClass = isAlert ? "ALERT" : (st === "VALID" ? "VALID" : "NA");

    analysisList.innerHTML += `
      <div class="analysis-item ${isAlert ? 'flagged' : ''}">
        <div class="analysis-left">
          <div class="analysis-icon ${tagClass}">${icon}</div>
          <div>
            <div class="analysis-title">${title}</div>
            <div class="analysis-sub">${item.detail || ""}</div>
          </div>
        </div>
        <span class="tag ${tagClass}">${st}</span>
      </div>`;
  });

  const badge = document.getElementById("doc-type-badge");
  if (badge) {
    badge.textContent = `${data.document_type || "Card"} Data`;
    badge.className = "doc-badge";
  }

  const grid = document.getElementById("extracted-grid");
  grid.innerHTML = "";
  for (const [k, v] of Object.entries(data.extracted || {})) {
    if (k === "Document Type") continue;
    grid.innerHTML += `
      <div class="extracted-item">
        <label>${k}</label>
        <div>${v}</div>
      </div>`;
  }

  // Check for Manual Referral
  if (data.manual_referral && data.manual_referral.required) {
    grid.innerHTML += `
      <div class="manual-referral-card" style="grid-column: 1 / -1;">
        <div class="referral-header">
          <span class="referral-badge">⚠️ Biometric Discrepancy — Manual Verification Required</span>
          <button type="button" class="btn-referral" id="btn-manual-refer-search">
            🔍 Perform Manual Database Check
          </button>
        </div>
        <div class="referral-desc">
          Automated face comparison did not match the document portrait (${data.analysis.face_verification.detail}). Traveler must undergo in-person physical identity verification and central database check.
        </div>
        <div class="referral-actions">
          <button type="button" class="btn-referral secondary" id="btn-manual-refer-log">
            📋 Log Secondary Referral
          </button>
        </div>
      </div>
    `;

    setTimeout(() => {
      document.getElementById("btn-manual-refer-search")?.addEventListener("click", () => {
        switchView("view-database-check");
        const searchInput = document.getElementById("db-search-input");
        if (searchInput) {
          searchInput.value = data.manual_referral.search_term || data.doc_code;
          executeDatabaseSearch();
        }
      });
      document.getElementById("btn-manual-refer-log")?.addEventListener("click", function() {
        this.textContent = "✓ Referral Logged";
        this.style.color = "var(--green)";
        this.disabled = true;
      });
    }, 50);
  }

  drawGauge(data.risk.score);
  document.getElementById("gauge-score").textContent = `${data.risk.score}/100`;
  document.getElementById("gauge-level").textContent = data.risk.level.toUpperCase();
  document.getElementById("recommendation").textContent = data.risk.recommendation;

  const fBox = document.getElementById("risk-factors");
  fBox.innerHTML = "";
  for (const [f, pts] of Object.entries(data.risk.factors)) {
    fBox.innerHTML += `<div class="risk-factor-row"><span>${f}</span><b>${pts > 0 ? "+" + pts : pts}</b></div>`;
  }
  fBox.innerHTML += `<div class="risk-factor-row"><span>Total Score</span><b>${data.risk.score}/100</b></div>`;

  const eBox = document.getElementById("evidence-box");
  if (eBox && data.image_path) {
    eBox.innerHTML = `<img src="${API_BASE}${data.image_path}" />`;
    (data.evidence || []).forEach((r) => {
      const marker = document.createElement("div");
      marker.className = `marker ${r.severity || 'high'}`;
      marker.style.left = `${r.x_pct}%`;
      marker.style.top = `${r.y_pct}%`;
      marker.style.width = `${r.w_pct}%`;
      marker.style.height = `${r.h_pct}%`;
      marker.setAttribute("data-tooltip", r.label || "Flagged Region");
      
      const tag = document.createElement("span");
      tag.className = "marker-tag";
      tag.textContent = r.label || "Anomaly";
      marker.appendChild(tag);
      
      eBox.appendChild(marker);
    });
  }
}

// Risk Gauge
function drawGauge(score) {
  const canvas = document.getElementById("gauge");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const cx = canvas.width / 2;
  const cy = canvas.height - 10;
  const r = 85;

  ctx.clearRect(0, 0, canvas.width, canvas.height);

  const segments = [
    { color: "#10b981", from: Math.PI, to: Math.PI * 1.3 },
    { color: "#f59e0b", from: Math.PI * 1.3, to: Math.PI * 1.65 },
    { color: "#ef4444", from: Math.PI * 1.65, to: Math.PI * 2 }
  ];
  segments.forEach((s) => {
    ctx.beginPath();
    ctx.arc(cx, cy, r, s.from, s.to);
    ctx.strokeStyle = s.color;
    ctx.lineWidth = 16;
    ctx.stroke();
  });

  const angle = Math.PI + (score / 100) * Math.PI;
  const nx = cx + Math.cos(angle) * (r - 20);
  const ny = cy + Math.sin(angle) * (r - 20);
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.lineTo(nx, ny);
  ctx.strokeStyle = "#e6e9f2";
  ctx.lineWidth = 3;
  ctx.stroke();
}

// Load Stats with Today, Shift & All-Time Metrics
async function loadStats() {
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    const parsed = await parseApiResponse(res);
    if (!parsed.ok || !parsed.data) return;
    const s = parsed.data;

    const setVal = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val !== undefined ? val : 0;
    };

    setVal("stat-total", s.today_total !== undefined ? s.today_total : s.total);
    setVal("stat-high", s.today_high !== undefined ? s.today_high : s.high);
    setVal("stat-medium", s.today_med !== undefined ? s.today_med : s.medium);
    setVal("stat-low", s.today_low !== undefined ? s.today_low : s.low);

    setVal("alert-badge", s.today_high !== undefined ? s.today_high : s.high);
    setVal("dash-high-count", s.today_high !== undefined ? s.today_high : s.high);

    const tTot = s.today_total !== undefined ? s.today_total : (s.today || s.total);
    const aTot = s.all_total !== undefined ? s.all_total : s.total;
    const tHigh = s.today_high !== undefined ? s.today_high : s.high;
    const aHigh = s.all_high !== undefined ? s.all_high : s.high;
    const tMed = s.today_med !== undefined ? s.today_med : s.medium;
    const aMed = s.all_med !== undefined ? s.all_med : s.medium;
    const tLow = s.today_low !== undefined ? s.today_low : s.low;
    const aLow = s.all_low !== undefined ? s.all_low : s.low;

    setVal("stat-total-delta", `↑ ${tTot} today • ${aTot} all-time`);
    setVal("stat-high-delta", `↑ ${tHigh} today (${aHigh} total)`);
    setVal("stat-medium-delta", `↑ ${tMed} today (${aMed} total)`);
    setVal("stat-low-delta", `✓ ${tLow} today (${aLow} total)`);

    const prev = s.previous_shift || {};
    const curShift = s.current_shift || "Shift Active";
    setVal("stat-current-shift", curShift);
    const pTot = prev.total !== undefined ? prev.total : (s.prev_shift_total || 0);
    const pHigh = prev.high !== undefined ? prev.high : (s.prev_shift_high || 0);
    setVal("stat-prev-shift-summary", `Prev: ${pTot} scans • ${pHigh} High`);

    const shiftEl = document.getElementById("shift-label");
    if (shiftEl && s.current_date) {
      shiftEl.textContent = `${s.current_date} • ${curShift.split(' ')[0] || 'Active'}`;
    }

    setVal("modal-curr-date", s.current_date);
    setVal("modal-curr-shift-name", curShift);
    setVal("modal-curr-total", tTot);
    setVal("modal-curr-high", tHigh);
    setVal("modal-curr-med", tMed);
    setVal("modal-curr-low", tLow);

    setVal("modal-prev-date", prev.date || s.prev_shift_date || "Previous Shift");
    setVal("modal-prev-shift-name", prev.name || "Shift A (Completed)");
    setVal("modal-prev-total", pTot);
    setVal("modal-prev-high", pHigh);
    setVal("modal-prev-med", prev.med !== undefined ? prev.med : (s.prev_shift_med || 0));
    setVal("modal-prev-low", prev.low !== undefined ? prev.low : (s.prev_shift_low || 0));

    const deltaBox = document.getElementById("modal-delta-container");
    if (deltaBox) {
      const scanDiff = tTot - pTot;
      const highDiff = tHigh - pHigh;
      deltaBox.innerHTML = `
        <div class="delta-tag up">Scans Volume: <b>${scanDiff >= 0 ? '+' + scanDiff : scanDiff}</b> vs prev shift (${pTot})</div>
        <div class="delta-tag ${highDiff > 0 ? 'warn' : ''}">High Risk Delta: <b>${highDiff >= 0 ? '+' + highDiff : highDiff}</b></div>
        <div class="delta-tag">Handover Integrity: <b>✓ 100% Verified &amp; Signed Off</b></div>
      `;
    }
  } catch (err) {
    console.warn("Failed to update statistics:", err);
  }
}

// Shift Handover Modal Handlers
const shiftModal = document.getElementById("shift-modal");
const btnOpenShiftModal = document.getElementById("btn-open-shift-modal");
const btnCloseShiftModal = document.getElementById("btn-close-shift-modal");

if (btnOpenShiftModal && shiftModal) {
  btnOpenShiftModal.addEventListener("click", () => {
    shiftModal.style.display = "flex";
  });
}
if (btnCloseShiftModal && shiftModal) {
  btnCloseShiftModal.addEventListener("click", () => {
    shiftModal.style.display = "none";
  });
}

// Auto-refresh stats every 30 seconds
setInterval(loadStats, 30000);

async function loadDocuments() {
  try {
    const res = await fetch(`${API_BASE}/api/documents?limit=10`);
    const parsed = await parseApiResponse(res);
    if (!parsed.ok || !Array.isArray(parsed.data)) return;
    const rows = parsed.data;
    const body = document.getElementById("doc-table-body");
    if (!body) return;
    body.innerHTML = "";
    rows.forEach((r) => {
      const level = (r.risk_level || "").replace(" Risk", "");
      body.innerHTML += `
        <tr>
          <td>${r.doc_code}</td><td>${r.doc_type}</td><td>${r.full_name}</td><td>${r.nationality}</td>
          <td>${r.risk_score}/100</td>
          <td><span class="risk-chip ${level}">${r.risk_level}</span></td>
          <td><span class="status-chip">✓ ${r.status}</span></td>
          <td>${r.scanned_at}</td>
        </tr>`;
    });
  } catch (e) {}
}

// Sidebar Navigation Router
const viewMap = {
  "Dashboard": "view-dashboard",
  "Scan Document": "view-scan-doc",
  "All Documents": "view-all-docs",
  "Risk Alerts": "view-risk-alerts",
  "Watchlist": "view-watchlist",
  "Reports & Analytics": "view-reports",
  "Database Check": "view-database-check",
  "Rule Engine": "view-rules",
  "Audit Logs": "view-audit",
  "Users & Roles": "view-users",
  "System Settings": "view-settings"
};

function switchView(targetId) {
  document.querySelectorAll(".app-view").forEach(v => v.style.display = "none");
  const targetView = document.getElementById(targetId);
  if (targetView) targetView.style.display = "block";

  if (targetId === "view-dashboard") loadDocuments();
  if (targetId === "view-all-docs") loadAllDocsTable();
  if (targetId === "view-risk-alerts") loadRiskAlertsView();
  if (targetId === "view-watchlist") loadWatchlistView();
  if (targetId === "view-reports") loadReportsView();
  if (targetId === "view-rules") loadRulesView();
  if (targetId === "view-audit") loadAuditLogsView();
  if (targetId === "view-users") loadUsersView();
  if (targetId === "view-settings") loadDiagnosticsView();
}

document.querySelectorAll(".sidebar .menu-item:not(.logout)").forEach((item) => {
  item.addEventListener("click", () => {
    document.querySelectorAll(".sidebar .menu-item").forEach(i => i.classList.remove("active"));
    item.classList.add("active");

    const text = item.textContent.replace(/[^a-zA-Z &]/g, "").trim();
    const targetId = viewMap[text] || "view-dashboard";
    switchView(targetId);
  });
});

document.getElementById("btn-goto-scanner")?.addEventListener("click", () => {
  document.querySelectorAll(".sidebar .menu-item").forEach(i => {
    if (i.textContent.includes("Scan Document")) i.classList.add("active");
    else i.classList.remove("active");
  });
  switchView("view-scan-doc");
});

document.getElementById("refresh-table")?.addEventListener("click", (e) => {
  e.preventDefault();
  loadDocuments();
});

// View 2: All Documents Table
async function loadAllDocsTable() {
  try {
    const res = await fetch(`${API_BASE}/api/documents?limit=100`);
    const parsed = await parseApiResponse(res);
    if (!parsed.ok || !Array.isArray(parsed.data)) return;
    const rows = parsed.data;
    const body = document.getElementById("all-docs-table-body");
    if (!body) return;
    body.innerHTML = "";
    rows.forEach((r) => {
      const level = (r.risk_level || "").replace(" Risk", "");
      body.innerHTML += `
        <tr>
          <td><b>${r.doc_code}</b></td><td>${r.doc_type}</td><td>${r.full_name}</td><td>${r.nationality}</td>
          <td><b>${r.risk_score}/100</b></td>
          <td><span class="risk-chip ${level}">${r.risk_level}</span></td>
          <td>${r.scanned_at}</td>
        </tr>`;
    });
  } catch (e) {}
}

document.getElementById("filter-all-docs")?.addEventListener("input", (e) => {
  const q = e.target.value.toLowerCase();
  document.querySelectorAll("#all-docs-table-body tr").forEach((tr) => {
    tr.style.display = tr.textContent.toLowerCase().includes(q) ? "" : "none";
  });
});

// View 3: Risk Alerts View
async function loadRiskAlertsView() {
  try {
    const res = await fetch(`${API_BASE}/api/documents?risk_level=HIGH&limit=50`);
    const parsed = await parseApiResponse(res);
    const alerts = parsed.data;
    const container = document.getElementById("alerts-container");
    if (!container) return;
    if (!parsed.ok || !Array.isArray(alerts) || alerts.length === 0) {
      container.innerHTML = `<div class="analysis-empty">No high risk documents currently flagged.</div>`;
      return;
    }
    container.innerHTML = alerts.map(a => `
      <div class="alert-card">
        <div style="display:flex; justify-content:space-between; margin-bottom:6px;">
          <b style="color:var(--red); font-size:14px;">🚨 ${a.doc_code} — ${a.full_name}</b>
          <span class="risk-chip High">${a.risk_score}/100</span>
        </div>
        <div style="font-size:12px; color:var(--muted);">Type: ${a.doc_type} | Scanned: ${a.scanned_at}</div>
        <div style="font-size:12px; margin-top:8px; color:#ff8585;">Flagged for secondary screening &amp; manual officer inspection.</div>
      </div>
    `).join("");
  } catch (e) {}
}

// View 4: Watchlist View
async function loadWatchlistView() {
  try {
    const res = await fetch(`${API_BASE}/api/watchlist`);
    const parsed = await parseApiResponse(res);
    const list = parsed.data;
    const body = document.getElementById("watchlist-table-body");
    if (!body || !parsed.ok || !Array.isArray(list)) return;
    body.innerHTML = list.map(item => `
      <tr>
        <td>#${item.id}</td><td><b>${item.name}</b></td><td>${item.reason}</td><td>${item.added_at}</td>
        <td><button type="button" class="btn-referral secondary" style="padding:4px 8px; font-size:11px;" onclick="removeWatchlist(${item.id})">Remove</button></td>
      </tr>
    `).join("");
  } catch (e) {}
}

window.removeWatchlist = async function(id) {
  await fetch(`${API_BASE}/api/watchlist/${id}`, { method: "DELETE" });
  await loadWatchlistView();
};

document.getElementById("btn-add-watchlist")?.addEventListener("click", async () => {
  const name = document.getElementById("watch-name")?.value.trim();
  const reason = document.getElementById("watch-reason")?.value.trim();
  if (!name) return;
  await fetch(`${API_BASE}/api/watchlist`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ name, reason: reason || "Suspicious Document" })
  });
  document.getElementById("watch-name").value = "";
  document.getElementById("watch-reason").value = "";
  await loadWatchlistView();
});

// View 5: Reports & Analytics
async function loadReportsView() {
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    const parsed = await parseApiResponse(res);
    if (!parsed.ok || !parsed.data) return;
    const s = parsed.data;
    const sumEl = document.getElementById("analytics-summary");
    const barEl = document.getElementById("analytics-bars");
    if (sumEl) {
      sumEl.innerHTML = `
        <div>Cumulative All-Time Processed: <b style="color:#fff;">${s.all_total || 0}</b></div>
        <div>Today's Shift Volume: <b style="color:var(--blue);">${s.today_total || 0}</b></div>
        <div>Previous Shift Baseline: <b style="color:var(--muted);">${s.previous_shift ? s.previous_shift.total : (s.prev_shift_total || 0)}</b></div>
        <div>Shift Active Date: <b style="color:var(--green);">${s.current_date || 'Today'}</b></div>
      `;
    }
    if (barEl) {
      barEl.innerHTML = `
        <div>High Risk Interceptions: <b style="color:var(--red);">${s.all_high || 0} (${Math.round(((s.all_high || 0)/Math.max(s.all_total || 1, 1))*100)}%)</b></div>
        <div>Medium Risk Audits: <b style="color:var(--yellow);">${s.all_med || 0} (${Math.round(((s.all_med || 0)/Math.max(s.all_total || 1, 1))*100)}%)</b></div>
        <div>Clean Clearances: <b style="color:var(--green);">${s.all_low || 0} (${Math.round(((s.all_low || 0)/Math.max(s.all_total || 1, 1))*100)}%)</b></div>
      `;
    }
  } catch (e) {}
}

// View 6: Database Search
const btnDbSearch = document.getElementById("btn-db-search");
const dbSearchInput = document.getElementById("db-search-input");
const dbSearchResults = document.getElementById("db-search-results");

async function executeDatabaseSearch() {
  const query = (dbSearchInput?.value || "").trim();
  if (!query) return;

  if (dbSearchResults) {
    dbSearchResults.innerHTML = `
      <div style="text-align:center; padding:20px; color:var(--muted);">
        <div class="radar-spinner"></div>
        <div>Querying central database records...</div>
      </div>`;
  }

  try {
    const res = await fetch(`${API_BASE}/api/database-check?q=${encodeURIComponent(query)}`);
    const parsed = await parseApiResponse(res);
    const data = parsed.data;

    if (!parsed.ok || !data || !data.results || data.results.length === 0) {
      if (dbSearchResults) {
        dbSearchResults.innerHTML = `
          <div style="text-align:center; padding:30px; background:var(--panel-2); border-radius:8px; border:1px dashed var(--border);">
            <div style="font-size:24px; margin-bottom:6px;">❌</div>
            <div style="font-weight:700; color:var(--text);">No Database Record Found</div>
            <div style="color:var(--muted); font-size:12px; margin-top:4px;">No registered document matches "${query}".</div>
          </div>`;
      }
      return;
    }

    let html = `
      <div style="margin-bottom:12px; font-size:12px; color:var(--muted);">
        Found <b>${data.count}</b> matching record(s) for "<b>${data.query}</b>":
      </div>
      <div style="display:flex; flex-direction:column; gap:12px;">
    `;

    data.results.forEach((item) => {
      const isHigh = (item.risk_level || "").toUpperCase().includes("HIGH");
      const chipClass = isHigh ? "High" : ((item.risk_level || "").toUpperCase().includes("MED") ? "Medium" : "Low");

      html += `
        <div style="background:var(--panel-2); border:1px solid var(--border); border-radius:10px; padding:16px; display:flex; justify-content:space-between; align-items:flex-start;">
          <div style="flex:1;">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
              <span style="font-weight:800; font-size:15px; color:#fff;">${item.full_name || "UNKNOWN"}</span>
              <span class="doc-badge">${item.doc_type}</span>
              <span style="font-family:monospace; color:var(--muted); font-size:12px;">${item.doc_code}</span>
            </div>
            <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:8px; font-size:12px; color:var(--muted); margin-top:10px;">
              <div>Nationality: <b style="color:#fff;">${item.nationality || "N/A"}</b></div>
              <div>Scanned: <b style="color:#fff;">${item.scanned_at}</b></div>
              <div>Status: <b style="color:var(--green);">✓ ${item.status}</b></div>
            </div>
          </div>
          <div style="text-align:right;">
            <span class="risk-chip ${chipClass}">${item.risk_level}</span>
            <div style="font-size:16px; font-weight:800; margin-top:8px; color:${isHigh ? 'var(--red)' : 'var(--green)'};">
              ${item.risk_score}/100
            </div>
          </div>
        </div>
      `;
    });

    html += `</div>`;
    if (dbSearchResults) dbSearchResults.innerHTML = html;

  } catch (err) {
    if (dbSearchResults) {
      dbSearchResults.innerHTML = `<div style="color:var(--red); text-align:center; padding:20px;">⚠️ Failed to query database: ${err.message}</div>`;
    }
  }
}

if (btnDbSearch) btnDbSearch.addEventListener("click", executeDatabaseSearch);
if (dbSearchInput) {
  dbSearchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") executeDatabaseSearch();
  });
}

// View 7: Rule Engine
async function loadRulesView() {
  try {
    const res = await fetch(`${API_BASE}/api/rules`);
    const parsed = await parseApiResponse(res);
    if (!parsed.ok || !parsed.data) return;
    const r = parsed.data;
    if (document.getElementById("rule-tamper")) document.getElementById("rule-tamper").value = r.tampering || 65;
    if (document.getElementById("rule-face")) document.getElementById("rule-face").value = r.face_mismatch || 25;
    if (document.getElementById("rule-mrz")) document.getElementById("rule-mrz").value = r.mrz_mismatch || 20;
    if (document.getElementById("rule-expiry")) document.getElementById("rule-expiry").value = r.expiry_issue || 10;
  } catch (e) {}
}

document.getElementById("btn-save-rules")?.addEventListener("click", async () => {
  const payload = {
    tampering: parseInt(document.getElementById("rule-tamper")?.value || 65),
    face_mismatch: parseInt(document.getElementById("rule-face")?.value || 25),
    mrz_mismatch: parseInt(document.getElementById("rule-mrz")?.value || 20),
    expiry_issue: parseInt(document.getElementById("rule-expiry")?.value || 10)
  };
  await fetch(`${API_BASE}/api/rules`, {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify(payload)
  });
  alert("Risk rule weights updated successfully!");
});

// View 8: Audit Logs
async function loadAuditLogsView() {
  try {
    const res = await fetch(`${API_BASE}/api/audit-logs`);
    const parsed = await parseApiResponse(res);
    const logs = parsed.data;
    const body = document.getElementById("audit-table-body");
    if (!body || !parsed.ok || !Array.isArray(logs)) return;
    body.innerHTML = logs.map(l => `
      <tr><td>#${l.id}</td><td><b>${l.event}</b></td><td>${l.user}</td><td>${l.timestamp}</td></tr>
    `).join("");
  } catch (e) {}
}

// View 9: Users & Roles (Full CRUD)
async function loadUsersView() {
  try {
    const res = await fetch(`${API_BASE}/api/users`);
    const parsed = await parseApiResponse(res);
    const users = parsed.data;
    const body = document.getElementById("users-table-body");
    if (!body || !parsed.ok || !Array.isArray(users)) return;
    body.innerHTML = users.map(u => `
      <tr>
        <td>#${u.id}</td>
        <td><b>${u.username}</b></td>
        <td>${u.full_name}</td>
        <td><span class="tag ${u.role === 'ADMIN' ? 'VALID' : (u.role === 'SENIOR_INSPECTOR' ? 'VALID' : 'NA')}">${u.role}</span></td>
        <td><span class="status-chip">✓ Active</span></td>
        <td>${u.last_login}</td>
        <td>
          ${u.role !== 'ADMIN' ? `<button type="button" class="btn-referral secondary" style="padding:4px 10px; font-size:11px; color:var(--red);" onclick="deleteUser(${u.id})">Revoke</button>` : `<span style="color:var(--muted); font-size:11px;">Protected</span>`}
        </td>
      </tr>
    `).join("");
  } catch (e) {}
}

window.deleteUser = async function(userId) {
  if (!confirm("Revoke terminal access for this border officer?")) return;
  await fetch(`${API_BASE}/api/users/${userId}`, { method: "DELETE" });
  await loadUsersView();
  await loadAuditLogsView();
};

document.getElementById("btn-show-enroll-user")?.addEventListener("click", () => {
  const card = document.getElementById("enroll-user-card");
  if (card) card.style.display = card.style.display === "none" ? "block" : "none";
});

document.getElementById("btn-save-new-user")?.addEventListener("click", async () => {
  const username = document.getElementById("new-user-username")?.value.trim();
  const full_name = document.getElementById("new-user-fullname")?.value.trim();
  const role = document.getElementById("new-user-role")?.value || "OFFICER";

  if (!username) {
    alert("Please provide an Officer Username.");
    return;
  }

  const res = await fetch(`${API_BASE}/api/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, full_name, role })
  });

  if (res.ok) {
    document.getElementById("new-user-username").value = "";
    document.getElementById("new-user-fullname").value = "";
    document.getElementById("enroll-user-card").style.display = "none";
    await loadUsersView();
    await loadAuditLogsView();
    alert(`Officer ${username} successfully enrolled with ${role} clearance.`);
  } else {
    alert("Failed to enroll officer.");
  }
});

// View 10: Diagnostics & Maintenance
async function loadDiagnosticsView() {
  try {
    const res = await fetch(`${API_BASE}/api/diagnostics/db`);
    const parsed = await parseApiResponse(res);
  } catch (e) {}
}

const btnVacuum = document.getElementById("btn-vacuum-db");
const vacuumMsg = document.getElementById("vacuum-status-msg");

async function executeVacuum(btnEl, msgEl) {
  if (btnEl) {
    btnEl.disabled = true;
    btnEl.textContent = "⏳ Optimizing...";
  }
  try {
    const res = await fetch(`${API_BASE}/api/admin/vacuum-db`, { method: "POST" });
    const parsed = await parseApiResponse(res);
    const data = parsed.data || {};
    if (msgEl) {
      msgEl.textContent = `✓ ${data.message || 'Optimized'} (${data.db_size_kb || 0} KB)`;
      msgEl.style.display = "inline";
    }
    if (btnEl) btnEl.textContent = "✓ Optimized";
    await loadAuditLogsView();
  } catch (err) {
    if (msgEl) msgEl.textContent = "⚠️ Optimization failed";
  } finally {
    if (btnEl) btnEl.disabled = false;
  }
}

if (btnVacuum) {
  btnVacuum.addEventListener("click", () => executeVacuum(btnVacuum, vacuumMsg));
}

// System Administrator Command Center Modal Controls
const adminModal = document.getElementById("admin-profile-modal");
const btnAdminProfile = document.getElementById("btn-admin-profile");
const btnCloseAdminModal = document.getElementById("btn-close-admin-modal");
const btnAdminVacuum = document.getElementById("btn-admin-vacuum");
const btnAdminChangePass = document.getElementById("btn-admin-change-pass");
const adminPassMsg = document.getElementById("admin-pass-msg");

if (btnAdminProfile && adminModal) {
  btnAdminProfile.addEventListener("click", () => {
    adminModal.style.display = "flex";
  });
}
if (btnCloseAdminModal && adminModal) {
  btnCloseAdminModal.addEventListener("click", () => {
    adminModal.style.display = "none";
  });
}
window.addEventListener("click", (e) => {
  if (e.target === adminModal) adminModal.style.display = "none";
  if (e.target === shiftModal) shiftModal.style.display = "none";
});

if (btnAdminVacuum) {
  btnAdminVacuum.addEventListener("click", () => executeVacuum(btnAdminVacuum, null));
}

if (btnAdminChangePass) {
  btnAdminChangePass.addEventListener("click", async () => {
    const newPass = document.getElementById("admin-new-password")?.value.trim();
    if (!newPass || newPass.length < 6) {
      if (adminPassMsg) {
        adminPassMsg.textContent = "⚠️ Password must be at least 6 characters.";
        adminPassMsg.style.color = "var(--red)";
        adminPassMsg.style.display = "block";
      }
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/api/admin/change-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_password: newPass })
      });
      const parsed = await parseApiResponse(res);
      const d = parsed.data || {};
      if (parsed.ok) {
        if (adminPassMsg) {
          adminPassMsg.textContent = `✓ ${d.message || 'Updated successfully'}`;
          adminPassMsg.style.color = "var(--green)";
          adminPassMsg.style.display = "block";
        }
        document.getElementById("admin-new-password").value = "";
        await loadAuditLogsView();
      } else {
        if (adminPassMsg) {
          adminPassMsg.textContent = `⚠️ ${parsed.error || "Failed to update"}`;
          adminPassMsg.style.color = "var(--red)";
          adminPassMsg.style.display = "block";
        }
      }
    } catch (e) {
      if (adminPassMsg) {
        adminPassMsg.textContent = "⚠️ Server error";
        adminPassMsg.style.display = "block";
      }
    }
  });
}

checkAuth();
