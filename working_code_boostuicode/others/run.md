# BoosterEntryAI - Deployment Guide

## 🚀 Quick Start (Docker - Recommended)

### Build Image
```bash
docker build -t boosterentryai .
```

### Run Container
```bash
docker run -d -p 30010:30010 -p 30012:30012 --name boosterentryai boosterentryai
```

### Check Logs
```bash
docker logs boosterentryai
docker exec boosterentryai cat /app/flask.log
docker exec boosterentryai cat /app/telegram.log
```

### Stop/Start
```bash
docker stop boosterentryai
docker start boosterentryai
```

### Access Separate Terminals in Docker

**Open shell into container:**
```bash
docker exec -it boosterentryai bash
```

**Run individual services manually:**
```bash
# Terminal 1: Flask Backend
docker exec -it boosterentryai python app.py

# Terminal 2: Telegram Listener
docker exec -it boosterentryai python telegram_user_client.py
```

**Watch logs in real-time:**
```bash
# Terminal 1: Flask logs
docker exec -it boosterentryai tail -f /app/flask.log

# Terminal 2: Telegram logs
docker exec -it boosterentryai tail -f /app/telegram.log
```

> **Note:** The container automatically runs all 3 services on startup via `docker-entrypoint.sh`. Use `docker exec` only for debugging or manual control.

### Export & Transfer Docker Image

**Save image to tar file (on local machine):**
```bash
docker save -o boosterentryai.tar boosterentryai
```

**Transfer to server:**
```bash
scp boosterentryai.tar user@103.14.123.44:/home/user/
```

**Load image on server:**
```bash
docker load -i boosterentryai.tar
```

**Run on server:**
```bash
docker run -d -p 30010:30010 -p 30012:30012 --name boosterentryai boosterentryai
```

---

## 🖥️ Manual Run (Without Docker)

### Prerequisites
```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Node dependencies
npm install
```

### Terminal 1: Flask Backend
```bash
python app.py
# Runs on http://0.0.0.0:30010
```

### Terminal 2: Telegram Listener
```bash
python telegram_user_client.py
# Listens for driver replies
```

### Terminal 3: React Frontend
```bash
npm run dev -- --host 0.0.0.0 --port 30012
# Runs on http://0.0.0.0:30012
```

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `app.py` | Flask API server |
| `telegram_user_client.py` | Listens for telegram replies |
| `telegram_sender.py` | Sends telegram messages |
| `routes/vehicle_hire_routes.py` | Vehicle hire API endpoints |

---

## 🔧 Configuration

### Frontend API URL
Edit `src/api/axios.js`:
```javascript
baseURL: "http://YOUR_SERVER_IP:30010"
```

### Database
Set in `.env` or environment:
```
DB_HOST=103.14.123.44
DB_USER=sql_developer
DB_PASSWORD=your_password
DB_NAME=mydb
```

---

## 🌐 Access URLs

| Service | URL |
|---------|-----|
| Frontend | http://YOUR_SERVER_IP:30012 |
| API | http://YOUR_SERVER_IP:30010 |

---

## ⚠️ First Time Setup

1. Ensure Telegram session files exist:
   - `vehicle_hire_sender.session`
   - `vehicle_hire_session.session`

2. If sessions don't exist, run locally first:
   ```bash
   python telegram_user_client.py
   # Enter OTP when prompted
   ```

3. Copy session files to server

---

## 🔄 Update & Redeploy

```bash
# Pull latest code
git pull

# Rebuild Docker image
docker build -t boosterentryai .

# Restart container
docker rm -f boosterentryai
docker run -d -p 30010:30010 -p 30012:30012 --name boosterentryai boosterentryai
```
