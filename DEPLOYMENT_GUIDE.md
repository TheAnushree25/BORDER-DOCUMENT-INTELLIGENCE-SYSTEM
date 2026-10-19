# 🚀 Deployment Guide

The app is one Docker container: Flask + Gunicorn serve the UI and the API on the same URL, and SQLite plus the scanned images live in `DATA_DIR` (`/app/data` in Docker).

## Before you deploy

1. **Set a real admin password.** Set `ADMIN_PASSWORD` before the first start. While the admin account still uses the published `Admin@123`, anyone can sign in with the one-click demo button.
2. **Set `SECRET_KEY`** to a long random string (Render's blueprint generates one for you).
3. **Use HTTPS.** Browsers only allow the webcam on `https://` (or `localhost`). Render, Railway and Hugging Face give you HTTPS automatically.
4. **Decide about storage.** Free hosting wipes the disk on every restart and redeploy, so scans, users and the watchlist reset. To keep them, attach a persistent disk at `/app/data`.
5. **Memory.** One worker uses roughly 300–400 MB while scanning. Keep `WEB_CONCURRENCY=1` on 512 MB plans; that is what caused the earlier 502 errors (two workers loading two copies of the models).

---

## Option 1: Render (already configured in `render.yaml`)

1. Push this repository to GitHub.
2. In the Render dashboard click **New → Blueprint**, pick the repository, and click **Apply**. Render reads `render.yaml`, builds the `Dockerfile`, generates `SECRET_KEY`, and asks you for `ADMIN_PASSWORD`.
3. The first build takes about 5–10 minutes. You then get a URL like `https://border-doc-intel.onrender.com`.

**Already created the service by hand?** In the service's **Settings**, check that the runtime is **Docker** and the Health Check Path is `/health`. Under **Environment** add `SECRET_KEY` (random string), `ADMIN_PASSWORD`, `SESSION_COOKIE_SECURE=true` and `WEB_CONCURRENCY=1`, then **Manual Deploy → Clear build cache & deploy**.

**Free plan caveats.** 512 MB RAM and 0.1 CPU: the app fits with one worker, but a scan can take 30–60 seconds, the service sleeps after 15 idle minutes (the next visit takes about a minute to wake), and data resets on each deploy. For a live demo, the **Starter** plan (0.5 CPU) is much faster. To keep data, add a **Disk** (paid plans) with mount path `/app/data`.

---

## Option 2: Hugging Face Spaces (free, 2 vCPU and 16 GB RAM)

Faster than Render's free plan for OCR and face models.

1. Create a Space at https://huggingface.co/new-space with SDK **Docker** (blank template).
2. In the Space **Settings → Variables and secrets**, add secrets `SECRET_KEY`, `ADMIN_PASSWORD` and a variable `SESSION_COOKIE_SECURE=true`.
3. Push this code to the Space's git repository. The Space's `README.md` must start with this header so Hugging Face knows the port:

   ```yaml
   ---
   title: Border Document Intelligence
   sdk: docker
   app_port: 10000
   ---
   ```
4. Open the app at its direct URL, `https://<user>-<space>.hf.space`. The embedded view on huggingface.co blocks the login cookie.

Data resets when the Space restarts unless you buy persistent storage (mounted at `/data`; then set `DATA_DIR=/data`).

---

## Option 3: Railway

Railway builds the `Dockerfile` using `railway.json`. Create a project from the GitHub repo, add the variables `SECRET_KEY`, `ADMIN_PASSWORD` and `SESSION_COOKIE_SECURE=true`, then generate a domain under **Settings → Networking**. To keep data, add a **Volume** mounted at `/app/data`.

---

## Option 4: Your own server (persistent data)

On any Linux VPS with Docker (AWS EC2, DigitalOcean, Azure; 1 GB RAM or more):

```bash
git clone https://github.com/enigmaeyes4u/BORDER-DOCUMENT-INTELLIGENCE-SYSTEM.git
cd BORDER-DOCUMENT-INTELLIGENCE-SYSTEM
cp .env.example .env        # then edit SECRET_KEY and ADMIN_PASSWORD
docker compose up -d --build
```

The app runs on port 5000 and keeps its data in the `border_data` Docker volume. For HTTPS (needed for the webcam), point a domain at the server and put Caddy in front, which gets a certificate automatically:

```bash
sudo apt install -y caddy
sudo caddy reverse-proxy --from your-domain.com --to localhost:5000
```

Add `SESSION_COOKIE_SECURE=true` to `.env` once HTTPS works, then `docker compose up -d`.

---

## Option 5: Windows checkpoint PC (no Docker)

```bat
pip install -r requirements.txt
start_production.bat
```

This runs Waitress on http://localhost:5000. Data is stored in `backend\` next to the code.

---

## Not supported: Vercel and other serverless hosts

The OCR and face models exceed serverless bundle limits, and the app needs a writable disk for SQLite and the scanned images. Use one of the container options above.

---

## Troubleshooting

| Symptom | Cause and fix |
| :--- | :--- |
| 502 / worker restarts during a scan | Out of memory. Keep `WEB_CONCURRENCY=1` or use an instance with more RAM. Check the host's logs for `Killed` / OOM. |
| First scan after a while is very slow | Cold start: the service was asleep, or the models load on the first scan. |
| Camera does not open | The page is not on HTTPS, or the browser blocked camera permission. |
| Logged out after every deploy | `SECRET_KEY` is not set, so a new one is generated with each fresh database. Set it as an environment variable. |
| "Authentication required" on every request | The browser is not keeping the session cookie: use the site's direct URL, and only set `SESSION_COOKIE_SECURE=true` when serving over HTTPS. |
| All data disappeared | Free hosts use temporary disks. Attach persistent storage at `DATA_DIR`. |
