# 🚀 Border Document Intelligence System — Production Deployment Guide

This project is packaged with production configurations for **Render / Railway (Docker)**, **Ubuntu Cloud VPS (AWS EC2 / DigitalOcean / Linode)**, and **Local Edge / Windows On-Premises Checkpoints**.

---

## 🌟 Option 1: Free Cloud Deployment (Render.com / Railway.app) — *Easiest with Docker*

Render and Railway automatically detect and build the root **`Dockerfile`**, pre-configuring **Tesseract OCR (Eng + Hin)**, **OpenCV**, and **Gunicorn multi-threading**.

### Step 1: Push Code to GitHub
```bash
git init
git add .
git commit -m "Deploy Border Document Intelligence System"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

### Step 2: Deploy on Render
1. Visit **[dashboard.render.com](https://dashboard.render.com/)** and click **New +** → **Web Service**.
2. Connect your GitHub repository.
3. Configure the service:
   - **Environment / Runtime**: `Docker`
   - **Plan**: `Free`
   - **Health Check Path**: `/api/health`
4. Click **Deploy Web Service**.
5. Render will build the container and provide your live public HTTPS URL (e.g., `https://border-doc-intel.onrender.com`).

---

## ☁️ Option 2: Deploy on an Ubuntu Cloud VPS (AWS EC2 / DigitalOcean / Linode)

If deploying directly on an Ubuntu 22.04 / 24.04 Linux Virtual Private Server:

### Step 1: Install System Dependencies & Tesseract OCR
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv git tesseract-ocr tesseract-ocr-hin tesseract-ocr-eng libgl1 libglib2.0-0 nginx
```

### Step 2: Clone Repository & Setup Python Virtual Environment
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
cd BORDER-DOC-INTEL
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

### Step 3: Configure Systemd Background Service
Create the service unit file:
```bash
sudo nano /etc/systemd/system/border_intel.service
```

Paste the following configuration (replace `<USER>` and `/path/to/BORDER-DOC-INTEL` with your actual username and path):
```ini
[Unit]
Description=Border Intelligence Flask Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/BORDER-DOC-INTEL/backend
ExecStart=/home/ubuntu/BORDER-DOC-INTEL/venv/bin/gunicorn --workers 3 --threads 4 --bind 127.0.0.1:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl start border_intel
sudo systemctl enable border_intel
sudo systemctl status border_intel
```

### Step 4: Configure Nginx Reverse Proxy
Create the Nginx site configuration:
```bash
sudo nano /etc/nginx/sites-available/border_intel
```

Paste:
```nginx
server {
    listen 80;
    server_name your_server_ip_or_domain;
    client_max_body_size 25M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/border_intel /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Step 5: Enable Free SSL / HTTPS *(Required for Live Webcam Permissions)*
Web browsers automatically block webcam and biometric camera access on insecure `http://` domains. Secure your domain with free Let's Encrypt SSL:
```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your_domain.com
```

---

## 🐳 Option 3: 1-Command Docker Deployment

To run directly on any server with Docker installed:
```bash
docker compose up --build -d
```
Your service will be live on `http://YOUR_SERVER_IP:5000` with persistent storage for documents and SQLite database in `./backend/`.

---

## 🏢 Option 4: On-Premises Windows Production Server

Double-click **`start_production.bat`** in the project root to run the multi-threaded Waitress WSGI server on port `5000`.

---

### 🛡️ Production Verification Checklist

- [x] **Unified Frontend & Backend**: Flask serves static HTML/CSS/JS files and API endpoints on a single origin.
- [x] **Dynamic Port Detection**: `PORT` environment variable detected automatically for cloud platforms.
- [x] **Relative API Origin**: `API_BASE` set to `window.location.origin` in `frontend/script.js`.
- [x] **Pre-Configured OCR & Biometrics**: Tesseract OCR (Eng/Hin) and OpenCV configured in Docker and requirements.
