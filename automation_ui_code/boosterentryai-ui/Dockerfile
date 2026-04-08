# ---------- Base Image ----------
FROM python:3.13-slim

# ---------- Working Directory ----------
WORKDIR /app

# ---------- System Dependencies (Node 22 + build tools) ----------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      curl gnupg build-essential libpq-dev && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# ---------- Python deps ----------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---------- UI deps (devDependencies incl. vite) ----------
# Copy only manifests first for better cache
COPY package*.json vite.config.* ./
RUN npm ci

# ---------- Copy the rest of the source ----------
COPY . .

# ---------- Ensure vite is resolvable ----------
ENV PATH="/app/node_modules/.bin:${PATH}"

# Defaults for entrypoint (both API and UI live at /app)
ENV API_DIR="/app"
ENV UI_DIR="/app"
ENV API_CMD="python app.py"
ENV UI_DEV_CMD="npm run dev -- --host 0.0.0.0 --port 30012"

EXPOSE 30010 30012

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh \
 && sed -i 's/\r$//' /docker-entrypoint.sh   # fix CRLF if edited on Windows

CMD ["/docker-entrypoint.sh"]
