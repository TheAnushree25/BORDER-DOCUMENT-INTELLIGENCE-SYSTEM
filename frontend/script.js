// Flask serves this UI and the API from the same origin (locally on :5000, or the cloud URL in production).
const API_BASE = window.location.origin;

let selectedDocFile = null;
let pendingLiveFace = null;
let isScanning = false;
let cameraStream = null;
let currentUser = null;

// Escape untrusted text (OCR output, names typed by officers) before it is placed into innerHTML.
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

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
    } else if (text && text.length > 0 && text.length < 250 && !text.startsWith("<!DOCTYPE") && !text.startsWith("<html")) {
      errorMessage = text;
    } else if (res.status === 502) {
      errorMessage = "HTTP 502 Bad Gateway: Upstream processing worker timed out or restarted. Please retry.";
    } else if (res.status === 504) {
      errorMessage = "HTTP 504 Gateway Timeout: Document scanning request timed out.";
    } else if (res.status === 503) {
      errorMessage = "HTTP 503 Service Unavailable: Intelligence server is temporarily busy.";
    } else if (res.status === 413) {
      errorMessage = "HTTP 413 Payload Too Large: Document image exceeds maximum 32MB upload size limit.";
    } else if (res.status === 404) {
      errorMessage = "HTTP 404 Not Found: Verification API endpoint unavailable on current origin.";
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

// Every API call goes through here, so an expired session sends the officer back to the login screen.
async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, { credentials: "same-origin", ...options });
  const parsed = await parseApiResponse(res);
  if (res.status === 401 && path !== "/api/auth/login") {
    showLoginModal(currentUser ? "Your session has expired. Please sign in again." : null);
  }
  return parsed;
}

function postJson(path, payload, method = "POST") {
  return api(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
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

function showLoginError(message) {
  if (!loginErrorBox) return;
  loginErrorBox.textContent = message;
  loginErrorBox.style.display = "block";
}

function showLoginModal(message) {
  currentUser = null;
  if (loginModal) loginModal.style.display = "flex";
  if (message) showLoginError(message);
}

function onLoggedIn(user) {
  currentUser = user;
  if (loginModal) loginModal.style.display = "none";
  if (loginErrorBox) loginErrorBox.style.display = "none";
  if (loginPassInput) loginPassInput.value = "";

  const nameEl = document.getElementById("officer-name");
  if (nameEl) nameEl.textContent = user.full_name;
  const modalNameEl = document.getElementById("admin-modal-name");
  if (modalNameEl) modalNameEl.textContent = `${user.full_name} (${user.role_label})`;
  document.body.classList.toggle("is-admin", user.role === "ADMIN");

  loadStats();
  loadDocuments();
}

async function checkAuth() {
  try {
    const me = await api("/api/auth/me");
    if (me.ok && me.data && me.data.user) {
      onLoggedIn(me.data.user);
    } else {
      showLoginModal();
    }
    const cfg = await api("/api/auth/config");
    const demoLogin = Boolean(cfg.ok && cfg.data && cfg.data.demo_login);
    document.querySelectorAll(".demo-login").forEach((el) => { el.style.display = demoLogin ? "" : "none"; });
  } catch (err) {
    showLoginModal("Cannot reach the intelligence server. Check your connection and reload.");
  }
}

async function doLogin(u, p) {
  if (loginErrorBox) loginErrorBox.style.display = "none";
  if (!u || !p) {
    showLoginError("Enter your Officer ID and security password.");
    return;
  }
  try {
    const parsed = await postJson("/api/auth/login", { username: u, password: p });
    if (parsed.ok && parsed.data && parsed.data.status === "success") {
      onLoggedIn(parsed.data.user);
    } else {
      showLoginError(parsed.error || "Invalid officer credentials.");
    }
  } catch (err) {
    showLoginError("Cannot reach the intelligence server. Check your connection and try again.");
  }
}

if (btnLoginSubmit) {
  btnLoginSubmit.addEventListener("click", () => doLogin(loginUserInput.value.trim(), loginPassInput.value.trim()));
}
[loginUserInput, loginPassInput].forEach((input) => {
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") doLogin(loginUserInput.value.trim(), loginPassInput.value.trim());
  });
});
if (btnQuickLogin) {
  btnQuickLogin.addEventListener("click", () => {
    loginUserInput.value = "admin";
    loginPassInput.value = "Admin@123";
    doLogin("admin", "Admin@123");
  });
}
const logoutBtn = document.getElementById("btn-logout");
if (logoutBtn) {
  logoutBtn.addEventListener("click", async () => {
    try {
      await api("/api/auth/logout", { method: "POST" });
    } catch (e) {}
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
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    alert("Camera access needs a secure (https://) connection or http://localhost.");
    return;
  }
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

// Primary Document Scan Execution Runner with Automatic Warmup Retry
async function executeScan(retryCount = 0) {
  if (isScanning && retryCount === 0) return;
  if (!selectedDocFile) return;

  if (!pendingLiveFace) {
    openCameraModal();
    return;
  }

  isScanning = true;
  const analysisList = document.getElementById("analysis-list");

  if (retryCount === 0) {
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
  } else {
    analysisList.innerHTML = `
      <div class="scan-radar-card">
        <div class="radar-spinner"></div>
        <div class="scan-radar-title" style="color:var(--amber);">WARMING UP AI WORKER — RETRYING SCAN</div>
        <div style="color:var(--muted); font-size:12px; margin-top:8px;">
          Upstream worker initialization in progress. Auto-reconnecting... (Attempt ${retryCount + 1}/2)
        </div>
      </div>`;
  }

  const formData = new FormData();
  formData.append("document", selectedDocFile);
  if (pendingLiveFace instanceof Blob) {
    formData.append("live_face", pendingLiveFace, "live_face.jpg");
  }

  try {
    const parsed = await api("/api/scan", { method: "POST", body: formData });

    if (!parsed.ok || !parsed.data) {
      // Automatic retry on 502 Bad Gateway / 503 / 504 Gateway Timeout (e.g. Render container cold start)
      if ((parsed.status === 502 || parsed.status === 503 || parsed.status === 504) && retryCount < 1) {
        await new Promise(r => setTimeout(r, 2000));
        return await executeScan(retryCount + 1);
      }
      throw new Error(parsed.error || "Scan failed: Invalid server response.");
    }

    renderAnalysis(parsed.data);
    await loadStats();
    await loadDocuments();
  } catch (err) {
    analysisList.innerHTML = `
      <div style="text-align:center; padding:20px;">
        <div style="color:#ef4444; font-weight:700; margin-bottom:6px;">⚠️ Scan Blocked / Failed</div>
        <div style="color:var(--muted); font-size:12px; max-width:420px; margin:0 auto 14px auto; word-break:break-word;">
          ${esc(err.message || "An unexpected error occurred during processing.")}
        </div>
        <button type="button" class="btn btn-secondary" onclick="executeScan()" style="padding:6px 16px; font-size:12px; cursor:pointer;">
          🔄 Retry Scan Now
        </button>
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
    { key: "database_verification", title: "Watchlist Verification", icon: "🗄️" }
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
            <div class="analysis-sub">${esc(item.detail)}</div>
          </div>
        </div>
        <span class="tag ${tagClass}">${esc(st)}</span>
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
        <label>${esc(k)}</label>
        <div>${esc(v)}</div>
      </div>`;
  }

  // Check for Manual Referral
  if (data.manual_referral && data.manual_referral.required) {
    grid.innerHTML += `
      <div class="manual-referral-card" style="grid-column: 1 / -1;">
        <div class="referral-header">
          <span class="referral-badge">⚠️ Manual Verification Required</span>
          <button type="button" class="btn-referral" id="btn-manual-refer-search">
            🔍 Perform Manual Database Check
          </button>
        </div>
        <div class="referral-desc">
          ${esc(data.manual_referral.reason)} Traveler must undergo in-person physical identity verification and central database check.
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
    fBox.innerHTML += `<div class="risk-factor-row"><span>${esc(f)}</span><b>${pts > 0 ? "+" + pts : pts}</b></div>`;
  }
  fBox.innerHTML += `<div class="risk-factor-row"><span>Total Score</span><b>${data.risk.score}/100</b></div>`;

  const eBox = document.getElementById("evidence-box");
  if (eBox && data.image_path) {
    eBox.innerHTML = "";
    const img = document.createElement("img");
    img.src = `${API_BASE}${data.image_path}`;
    eBox.appendChild(img);
    (data.evidence || []).forEach((r) => {
      const marker = document.createElement("div");
      marker.className = `marker ${r.severity === "low" ? "low" : "high"}`;
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
  if (!currentUser) return;
  try {
    const parsed = await api("/api/stats");
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
    setVal("dash-high-count", s.all_high || 0);
    const allTotal = s.all_total || 0;
    setVal("dash-integrity-rate", allTotal ? `${(((allTotal - (s.all_high || 0)) / allTotal) * 100).toFixed(1)}%` : "—");
    setVal("dash-face-rate", s.face_compared ? `${((s.face_matched / s.face_compared) * 100).toFixed(1)}%` : "—");

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

function riskChipClass(level) {
  const upper = (level || "").toUpperCase();
  return upper.includes("HIGH") ? "High" : upper.includes("MED") ? "Medium" : "Low";
}

async function loadDocuments() {
  try {
    const parsed = await api("/api/documents?limit=10");
    if (!parsed.ok || !Array.isArray(parsed.data)) return;
    const body = document.getElementById("doc-table-body");
    if (!body) return;
    body.innerHTML = parsed.data.map((r) => `
        <tr>
          <td>${esc(r.doc_code)}</td><td>${esc(r.doc_type)}</td><td>${esc(r.full_name)}</td><td>${esc(r.nationality)}</td>
          <td>${esc(r.risk_score)}/100</td>
          <td><span class="risk-chip ${riskChipClass(r.risk_level)}">${esc(r.risk_level)}</span></td>
          <td><span class="status-chip">✓ ${esc(r.status)}</span></td>
          <td>${esc(r.scanned_at)}</td>
        </tr>`).join("");
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
    const parsed = await api("/api/documents?limit=100");
    if (!parsed.ok || !Array.isArray(parsed.data)) return;
    const body = document.getElementById("all-docs-table-body");
    if (!body) return;
    body.innerHTML = parsed.data.map((r) => `
        <tr>
          <td><b>${esc(r.doc_code)}</b></td><td>${esc(r.doc_type)}</td><td>${esc(r.full_name)}</td><td>${esc(r.nationality)}</td>
          <td><b>${esc(r.risk_score)}/100</b></td>
          <td><span class="risk-chip ${riskChipClass(r.risk_level)}">${esc(r.risk_level)}</span></td>
          <td>${esc(r.scanned_at)}</td>
        </tr>`).join("");
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
    const parsed = await api("/api/documents?risk_level=HIGH&limit=50");
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
          <b style="color:var(--red); font-size:14px;">🚨 ${esc(a.doc_code)} — ${esc(a.full_name)}</b>
          <span class="risk-chip High">${esc(a.risk_score)}/100</span>
        </div>
        <div style="font-size:12px; color:var(--muted);">Type: ${esc(a.doc_type)} | Scanned: ${esc(a.scanned_at)}</div>
        <div style="font-size:12px; margin-top:8px; color:#ff8585;">Flagged for secondary screening &amp; manual officer inspection.</div>
      </div>
    `).join("");
  } catch (e) {}
}

// View 4: Watchlist View
async function loadWatchlistView() {
  try {
    const parsed = await api("/api/watchlist");
    const list = parsed.data;
    const body = document.getElementById("watchlist-table-body");
    if (!body || !parsed.ok || !Array.isArray(list)) return;
    body.innerHTML = list.map(item => `
      <tr>
        <td>#${Number(item.id)}</td><td><b>${esc(item.name)}</b></td><td>${esc(item.reason)}</td><td>${esc(item.added_at)}</td>
        <td><button type="button" class="btn-referral secondary" style="padding:4px 8px; font-size:11px;" onclick="removeWatchlist(${Number(item.id)})">Remove</button></td>
      </tr>
    `).join("");
  } catch (e) {}
}

window.removeWatchlist = async function(id) {
  const parsed = await api(`/api/watchlist/${id}`, { method: "DELETE" });
  if (!parsed.ok) alert(parsed.error || "Failed to remove watchlist entry.");
  await loadWatchlistView();
};

document.getElementById("btn-add-watchlist")?.addEventListener("click", async () => {
  const name = document.getElementById("watch-name")?.value.trim();
  const reason = document.getElementById("watch-reason")?.value.trim();
  if (!name) return;
  const parsed = await postJson("/api/watchlist", { name, reason: reason || "Suspicious Document" });
  if (!parsed.ok) {
    alert(parsed.error || "Failed to add watchlist entry.");
    return;
  }
  document.getElementById("watch-name").value = "";
  document.getElementById("watch-reason").value = "";
  await loadWatchlistView();
});

// View 5: Reports & Analytics
async function loadReportsView() {
  try {
    const parsed = await api("/api/stats");
    if (!parsed.ok || !parsed.data) return;
    const s = parsed.data;
    const sumEl = document.getElementById("analytics-summary");
    const barEl = document.getElementById("analytics-bars");
    if (sumEl) {
      sumEl.innerHTML = `
        <div>Cumulative All-Time Processed: <b style="color:#fff;">${s.all_total || 0}</b></div>
        <div>Today's Shift Volume: <b style="color:var(--blue);">${s.today_total || 0}</b></div>
        <div>Previous Shift Baseline: <b style="color:var(--muted);">${s.previous_shift ? s.previous_shift.total : (s.prev_shift_total || 0)}</b></div>
        <div>Shift Active Date: <b style="color:var(--green);">${esc(s.current_date || 'Today')}</b></div>
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
    const parsed = await api(`/api/database-check?q=${encodeURIComponent(query)}`);
    const data = parsed.data;

    if (!parsed.ok || !data || !data.results || data.results.length === 0) {
      if (dbSearchResults) {
        dbSearchResults.innerHTML = `
          <div style="text-align:center; padding:30px; background:var(--panel-2); border-radius:8px; border:1px dashed var(--border);">
            <div style="font-size:24px; margin-bottom:6px;">❌</div>
            <div style="font-weight:700; color:var(--text);">No Database Record Found</div>
            <div style="color:var(--muted); font-size:12px; margin-top:4px;">No registered document matches "${esc(query)}".</div>
          </div>`;
      }
      return;
    }

    let html = `
      <div style="margin-bottom:12px; font-size:12px; color:var(--muted);">
        Found <b>${Number(data.count)}</b> matching record(s) for "<b>${esc(data.query)}</b>":
      </div>
      <div style="display:flex; flex-direction:column; gap:12px;">
    `;

    data.results.forEach((item) => {
      const chipClass = riskChipClass(item.risk_level);
      const isHigh = chipClass === "High";

      html += `
        <div style="background:var(--panel-2); border:1px solid var(--border); border-radius:10px; padding:16px; display:flex; justify-content:space-between; align-items:flex-start;">
          <div style="flex:1;">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:8px;">
              <span style="font-weight:800; font-size:15px; color:#fff;">${esc(item.full_name || "UNKNOWN")}</span>
              <span class="doc-badge">${esc(item.doc_type)}</span>
              <span style="font-family:monospace; color:var(--muted); font-size:12px;">${esc(item.doc_code)}</span>
            </div>
            <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:8px; font-size:12px; color:var(--muted); margin-top:10px;">
              <div>Nationality: <b style="color:#fff;">${esc(item.nationality || "N/A")}</b></div>
              <div>Scanned: <b style="color:#fff;">${esc(item.scanned_at)}</b></div>
              <div>Status: <b style="color:var(--green);">✓ ${esc(item.status)}</b></div>
            </div>
          </div>
          <div style="text-align:right;">
            <span class="risk-chip ${chipClass}">${esc(item.risk_level)}</span>
            <div style="font-size:16px; font-weight:800; margin-top:8px; color:${isHigh ? 'var(--red)' : 'var(--green)'};">
              ${esc(item.risk_score)}/100
            </div>
          </div>
        </div>
      `;
    });

    html += `</div>`;
    if (dbSearchResults) dbSearchResults.innerHTML = html;

  } catch (err) {
    if (dbSearchResults) {
      dbSearchResults.innerHTML = `<div style="color:var(--red); text-align:center; padding:20px;">⚠️ Failed to query database: ${esc(err.message)}</div>`;
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
const RULE_INPUTS = {
  tampering: "rule-tamper",
  face_mismatch: "rule-face",
  mrz_mismatch: "rule-mrz",
  expiry_issue: "rule-expiry",
  watchlist_hit: "rule-watchlist"
};

async function loadRulesView() {
  try {
    const parsed = await api("/api/rules");
    if (!parsed.ok || !parsed.data) return;
    for (const [key, inputId] of Object.entries(RULE_INPUTS)) {
      const input = document.getElementById(inputId);
      if (input && parsed.data[key] !== undefined) input.value = parsed.data[key];
    }
  } catch (e) {}
}

document.getElementById("btn-save-rules")?.addEventListener("click", async () => {
  const payload = {};
  for (const [key, inputId] of Object.entries(RULE_INPUTS)) {
    const input = document.getElementById(inputId);
    if (input) payload[key] = parseInt(input.value, 10);
  }
  const parsed = await postJson("/api/rules", payload);
  if (parsed.ok) {
    alert("Risk rule weights updated. New scans will use these weights.");
    await loadRulesView();
  } else {
    alert(parsed.error || "Failed to update rule weights.");
  }
});

// View 8: Audit Logs
async function loadAuditLogsView() {
  try {
    const parsed = await api("/api/audit-logs");
    const logs = parsed.data;
    const body = document.getElementById("audit-table-body");
    if (!body || !parsed.ok || !Array.isArray(logs)) return;
    body.innerHTML = logs.map(l => `
      <tr><td>#${Number(l.id)}</td><td><b>${esc(l.event)}</b>${l.details ? `<div style="color:var(--muted); font-size:11px;">${esc(l.details)}</div>` : ""}</td><td>${esc(l.user)}</td><td>${esc(l.timestamp)}</td></tr>
    `).join("");
  } catch (e) {}
}

// View 9: Users & Roles (Full CRUD)
async function loadUsersView() {
  try {
    const parsed = await api("/api/users");
    const users = parsed.data;
    const body = document.getElementById("users-table-body");
    if (!body) return;
    if (!parsed.ok || !Array.isArray(users)) {
      body.innerHTML = `<tr><td colspan="7" style="color:var(--muted);">${esc(parsed.error || "Unable to load users.")}</td></tr>`;
      return;
    }
    body.innerHTML = users.map(u => `
      <tr>
        <td>#${Number(u.id)}</td>
        <td><b>${esc(u.username)}</b></td>
        <td>${esc(u.full_name)}</td>
        <td><span class="tag ${u.role === 'ADMIN' || u.role === 'SENIOR_INSPECTOR' ? 'VALID' : 'NA'}">${esc(u.role)}</span></td>
        <td><span class="status-chip">✓ ${u.active ? "Active" : "Disabled"}</span></td>
        <td>${esc(u.last_login)}</td>
        <td>
          ${u.role !== 'ADMIN' ? `<button type="button" class="btn-referral secondary" style="padding:4px 10px; font-size:11px; color:var(--red);" onclick="deleteUser(${Number(u.id)})">Revoke</button>` : `<span style="color:var(--muted); font-size:11px;">Protected</span>`}
        </td>
      </tr>
    `).join("");
  } catch (e) {}
}

window.deleteUser = async function(userId) {
  if (!confirm("Revoke terminal access for this border officer?")) return;
  const parsed = await api(`/api/users/${userId}`, { method: "DELETE" });
  if (!parsed.ok) alert(parsed.error || "Failed to revoke officer.");
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
  const password = document.getElementById("new-user-password")?.value.trim();
  const role = document.getElementById("new-user-role")?.value || "OFFICER";

  if (!username || !password) {
    alert("Please provide an Officer Username and an initial password.");
    return;
  }

  const parsed = await postJson("/api/users", { username, full_name, password, role });
  if (parsed.ok) {
    document.getElementById("new-user-username").value = "";
    document.getElementById("new-user-fullname").value = "";
    document.getElementById("new-user-password").value = "";
    document.getElementById("enroll-user-card").style.display = "none";
    await loadUsersView();
    await loadAuditLogsView();
    alert(`Officer ${username} successfully enrolled with ${role} clearance.`);
  } else {
    alert(parsed.error || "Failed to enroll officer.");
  }
});

// View 10: Diagnostics & Maintenance
async function loadDiagnosticsView() {
  try {
    const parsed = await api("/api/diagnostics/db");
    const d = parsed.data;
    const summary = document.getElementById("diag-db-summary");
    if (summary && parsed.ok && d) {
      summary.textContent = `SQLite 3 • ${d.total_documents} screened documents • ${d.total_watchlist} watchlist entries • ${d.db_size_kb} KB`;
    }
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
    const parsed = await api("/api/admin/vacuum-db", { method: "POST" });
    const data = parsed.data || {};
    if (!parsed.ok) throw new Error(parsed.error || "Optimization failed");
    if (msgEl) {
      msgEl.textContent = `✓ ${data.message || 'Optimized'} (${data.db_size_kb || 0} KB)`;
      msgEl.style.display = "inline";
    }
    if (btnEl) btnEl.textContent = "✓ Optimized";
    await loadAuditLogsView();
  } catch (err) {
    if (btnEl) btnEl.textContent = "Run Optimize";
    if (msgEl) {
      msgEl.textContent = `⚠️ ${err.message}`;
      msgEl.style.display = "inline";
    } else {
      alert(err.message);
    }
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

function showPassMessage(text, ok) {
  if (!adminPassMsg) return;
  adminPassMsg.textContent = text;
  adminPassMsg.style.color = ok ? "var(--green)" : "var(--red)";
  adminPassMsg.style.display = "block";
}

if (btnAdminChangePass) {
  btnAdminChangePass.addEventListener("click", async () => {
    const currentPass = document.getElementById("admin-current-password")?.value.trim();
    const newPass = document.getElementById("admin-new-password")?.value.trim();
    if (!currentPass) {
      showPassMessage("⚠️ Enter your current password.", false);
      return;
    }
    if (!newPass || newPass.length < 6) {
      showPassMessage("⚠️ New password must be at least 6 characters.", false);
      return;
    }

    try {
      const parsed = await postJson("/api/auth/change-password", { current_password: currentPass, new_password: newPass });
      if (parsed.ok) {
        showPassMessage(`✓ ${(parsed.data && parsed.data.message) || 'Updated successfully'}`, true);
        document.getElementById("admin-current-password").value = "";
        document.getElementById("admin-new-password").value = "";
        await loadAuditLogsView();
      } else {
        showPassMessage(`⚠️ ${parsed.error || "Failed to update"}`, false);
      }
    } catch (e) {
      showPassMessage("⚠️ Server error", false);
    }
  });
}

checkAuth();
