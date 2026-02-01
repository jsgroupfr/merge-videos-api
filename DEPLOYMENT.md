# Video Merge API – Deployment Guide

Deploy the Video Merge API to [Railway](https://railway.app) or any platform that supports Python, FFmpeg, and S3-compatible storage.

---

## Prerequisites

- **Git** – to push and deploy from a repo
- **FFmpeg** – installed in the deployment environment (Railway uses Nixpacks; see below)
- **S3-compatible storage** – e.g. [Railway Volume / Bucket](https://docs.railway.app/reference/volumes) or any S3-compatible service

---

## 1. Push to GitHub

From your project root:

```bash
git init
git add .
git commit -m "Initial commit: Video Merge API"
git branch -M main
git remote add origin https://github.com/juppfy/merge-videos-api.git
git push -u origin main
```

Ensure `.env` is **not** committed (it is listed in `.gitignore`). Use `.env.example` as a template.

---

## 2. Railway Deployment

### 2.1 Create a project

1. Go to [railway.app](https://railway.app) and sign in.
2. **New Project** → **Deploy from GitHub repo**.
3. Select **juppfy/merge-videos-api** (or your fork).
4. Railway will detect the app and use **Nixpacks**; `nixpacks.toml` ensures FFmpeg is installed.

### 2.2 Add storage (S3-compatible bucket)

1. In your Railway project, click **+ New** → **Database** or **Volume**.
2. For **Railway’s built-in storage**, add a **Volume** and note the bucket name and credentials (or use Railway’s S3-compatible storage if offered).
3. Alternatively, use **AWS S3**, **Cloudflare R2**, or any S3-compatible provider. You will need:
   - Bucket name  
   - Endpoint URL  
   - Access Key ID  
   - Secret Access Key  
   - Region (often `auto` for Railway)

### 2.3 Set environment variables

In Railway: **Your Service** → **Variables** → add:

| Variable | Required | Description |
|----------|----------|-------------|
| `API_KEY` | Yes | Secret key for `X-API-Key` header; use a long random string. |
| `BUCKET` | Yes | S3 bucket name (e.g. Railway bucket name). |
| `ENDPOINT` | Yes | S3 endpoint URL (e.g. `https://storage.railway.app` or your provider’s URL). |
| `ACCESS_KEY_ID` | Yes | S3 access key. |
| `SECRET_ACCESS_KEY` | Yes | S3 secret key. |
| `REGION` | No | S3 region; default `auto` for Railway. |
| `PORT` | No | Set by Railway automatically; only override if needed. |

Copy from `.env.example` and fill in real values. **Do not** commit `.env` or production keys.

### 2.4 Deploy and health check

- Railway builds from the repo and runs: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Health check**: `GET /health` should return `{"status":"ok"}`. Configure this in Railway’s service settings if the platform supports it.
- **Timeout**: Merging can take several minutes. Consider increasing request timeout (e.g. 600s) or moving to async jobs later.

### 2.5 Optional: custom domain and HTTPS

In Railway, attach a custom domain to the service; HTTPS is provided automatically.

---

## 3. Other platforms (Docker, Render, Fly.io, etc.)

### FFmpeg must be available

- **Nixpacks** (Railway): already configured via `nixpacks.toml`.
- **Docker**: use an image that includes FFmpeg, e.g.:

  ```dockerfile
  FROM python:3.11-slim
  RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
  WORKDIR /app
  COPY requirements.txt .
  RUN pip install --no-cache-dir -r requirements.txt
  COPY . .
  CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
  ```

- **Render / Heroku**: add FFmpeg via buildpack or Aptfile, e.g. `ffmpeg` in an `Aptfile` if the stack supports it.

### Environment variables

Set the same variables as in **2.3** on your platform’s dashboard or CLI.

### Start command

```bash
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
```

Use `Procfile` or your platform’s equivalent if needed.

---

## 4. Verify deployment

1. **Health**:  
   `curl https://your-app.up.railway.app/health`  
   Expected: `{"status":"ok"}`

2. **Merge** (replace `YOUR_API_KEY` and URLs):  
   ```bash
   curl -X POST https://your-app.up.railway.app/api/v1/merge \
     -H "X-API-Key: YOUR_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"video_urls": ["https://example.com/v1.mp4", "https://example.com/v2.mp4"], "quality": "720", "aspect_ratio": "16:9"}'
   ```  
   Expected: JSON with `success: true`, `merged_url`, `duration_seconds`, `processing_time`, `clips_merged`.

3. **Errors** (e.g. missing key):  
   Expected: `{"error": "Invalid or missing API key"}` with status 401.

---

## 5. Troubleshooting

| Issue | What to check |
|-------|----------------|
| **502 / timeout** | Increase request timeout; merges can take 5–15 minutes for long videos. |
| **FFmpeg not found** | Ensure Nixpacks (Railway) or your image/buildpack installs FFmpeg. |
| **Upload / storage errors** | Verify `BUCKET`, `ENDPOINT`, `ACCESS_KEY_ID`, `SECRET_ACCESS_KEY`, and bucket permissions. |
| **401 Unauthorized** | Ensure `X-API-Key` header matches `API_KEY` in the environment. |
| **400 Total duration exceeds** | Total duration of all input videos must be ≤ 7200 seconds (2 hours). |

---

## 6. Security and limits

- Keep `API_KEY` secret and rotate it if exposed.
- Use HTTPS only in production.
- The API accepts 2–10 URLs and rejects total duration > 2 hours; adjust limits in code if needed.
- Consider rate limiting or async jobs for production at scale.

---

## Repo and license

- **Repository**: [github.com/juppfy/merge-videos-api](https://github.com/juppfy/merge-videos-api)
- Open source; see repo for license and contributing guidelines.
