# ---------- Full Application Docker Image ----------
# Includes: FastAPI + Flask API + React Frontend + Telegram
# Ports: 30010 (Flask), 30011 (FastAPI), 30012 (React UI)

FROM python:3.13-slim

WORKDIR /app

# ---------- System Dependencies (Node 22 + build tools + OCR) ----------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl gnupg build-essential libpq-dev \
      tesseract-ocr tesseract-ocr-eng ghostscript unpaper && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# ---------- Python deps ----------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- Copy the rest of the source FIRST ----------
COPY . .

# ---------- UI deps (install after copy to ensure package.json is there) ----------
RUN npm ci

# ---------- Create PDF storage directory ----------
RUN mkdir -p /app/pdf_storage

# ---------- Ensure vite is resolvable ----------
ENV PATH="/app/node_modules/.bin:${PATH}"
ENV PYTHONUNBUFFERED=1
ENV PDF_STORAGE_PATH=/app/pdf_storage

# Defaults for entrypoint
ENV API_DIR="/app"
ENV UI_DIR="/app"
ENV API_CMD="python app.py"
ENV UI_DEV_CMD="npm run dev -- --host 0.0.0.0 --port 30012"

EXPOSE 30010 30011 30012

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh \
 && sed -i 's/\r$//' /docker-entrypoint.sh

CMD ["/docker-entrypoint.sh"]
