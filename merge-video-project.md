# Video Merge API – Project Guide

A guide to build a video merging API similar to your bg-remover-api. Accepts a list of video URLs, merges them with configurable quality and aspect ratio, and returns a URL to the merged video stored on Railway.

---

## Overview

| Requirement | Implementation |
|-------------|----------------|
| **Input** | JSON body with array of 2–10 video URLs |
| **Validation** | Total duration ≤ 2 hours |
| **Output** | Public or presigned URL to merged video |
| **Quality** | 720p or 1080p |
| **Aspect ratio** | 9:16, 16:9, 1:1 |
| **Audio** | Always on when source videos have audio |
| **Transitions** | Smooth transitions between clips |

---

## Tech Stack

- **Python 3.11+**
- **FastAPI** – same as bg-remover-api
- **FFmpeg** – video merging, transcoding, transitions
- **httpx** – download videos from URLs
- **boto3** – Railway Storage (S3-compatible)
- **ffmpeg-python** (optional) – nicer Python bindings for FFmpeg

---

## Project Structure

```
merge-video-api/
├── main.py              # FastAPI app, routes
├── requirements.txt
├── Procfile
├── railway.json
├── .env.example
├── .gitignore
├── utils/
│   ├── __init__.py
│   ├── auth.py          # X-API-Key (same as bg-remover)
│   ├── storage.py       # Upload to Railway bucket (adapt for video)
│   └── video_processor.py  # FFmpeg merge logic
└── merge-video-project.md  # This guide
```

---

## API Design

### Endpoint

```
POST /api/v1/merge
```

### Request Body

```json
{
  "video_urls": [
    "https://example.com/video1.mp4",
    "https://example.com/video2.mp4"
  ],
  "quality": "1080",
  "aspect_ratio": "16:9"
}
```

| Field | Type | Required | Values | Default |
|-------|------|----------|--------|---------|
| `video_urls` | string[] | Yes | 2–10 valid HTTP(S) URLs | — |
| `quality` | string | No | `"720"` or `"1080"` | `"1080"` |
| `aspect_ratio` | string | No | `"9:16"`, `"16:9"`, `"1:1"` | `"16:9"` |

### Response (success)

```json
{
  "success": true,
  "merged_url": "https://...",
  "duration_seconds": 180.5,
  "processing_time": 45.2,
  "clips_merged": 3
}
```

### Response (error)

```json
{
  "error": "Total duration (7300s) exceeds maximum of 7200s"
}
```

---

## Implementation Details

### 1. FFmpeg Installation

Railway and most hosts don’t include FFmpeg by default. Options:

**Option A: Nixpacks (Railway)**  
Add `nixpacks.toml` in project root:

```toml
[phases.setup]
nixPkgs = ["ffmpeg"]
```

**Option B: Apt package**  
Add `Aptfile` or use a custom build step that runs:

```bash
apt-get update && apt-get install -y ffmpeg
```

**Option C: Docker**  
Use an image with FFmpeg preinstalled (e.g. `python:3.11-slim` + install ffmpeg in Dockerfile).

---

### 2. Video Download & Validation

1. Download each video from URL into a temp directory.
2. Use **ffprobe** to get duration:

   ```bash
   ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 video.mp4
   ```

3. Sum durations; reject if total > 7200 seconds (2 hours).
4. Reject if any download fails or file is not a valid video.

---

### 3. Merging Strategy with Transitions

Use FFmpeg’s **concat** filter chain with **xfade** for transitions:

- Concat demuxer alone = hard cuts.
- **xfade** = crossfade between segments (e.g. 0.5–1 second).

Example approach:

1. Build a filter graph that:
   - Scales/pads each video to target resolution and aspect ratio.
   - Concatenates with xfade between clips.
   - Keeps audio (use `concat=n=N:v=1:a=1` and include audio in filter graph).

2. Target dimensions from `quality` + `aspect_ratio`:

   | Quality | 16:9 | 9:16 | 1:1 |
   |---------|------|------|-----|
   | 720 | 1280×720 | 720×1280 | 720×720 |
   | 1080 | 1920×1080 | 1080×1920 | 1080×1080 |

---

### 4. FFmpeg Filter Example (Conceptual)

```text
[0:v]scale=...:force_original_aspect_ratio=decrease,pad=...:x=(ow-iw)/2:y=(oh-ih)/2,setsar=1[v0];
[1:v]scale=...:force_original_aspect_ratio=decrease,pad=...:x=(ow-iw)/2:y=(oh-ih)/2,setsar=1[v1];
[v0][v1]xfade=transition=fade:duration=0.5:offset=... [v];
[0:a][1:a]acrossfade=d=0.5 [a]
```

- Adjust `scale` and `pad` per target aspect ratio.
- Chain xfade for 3+ clips (each transition needs correct `offset`).

Libraries like **ffmpeg-python** or **moviepy** can simplify building these graphs.

---

### 5. Audio Handling

- Use `-c:a aac` (or copy if all sources are AAC) for output.
- Keep original audio from each clip; align with video via concat.
- Use `acrossfade` for audio transitions between segments.
- If a clip has no audio, FFmpeg can add silence with `anullsrc`.

---

### 6. Storage Upload

Adapt your `utils/storage.py` from bg-remover:

- Object key: `merged-{uuid}-{timestamp}.mp4`
- Content-Type: `video/mp4`
- Same boto3 + presigned URL logic.
- Railway bucket can handle large files; ensure timeouts and memory are sufficient.

---

### 7. Processing Flow (High Level)

```
1. Validate request (2–10 URLs, quality, aspect_ratio)
2. Download each video to temp dir
3. ffprobe each file → get duration, validate format
4. Sum durations → reject if > 7200s
5. Build FFmpeg command (scale, pad, xfade, concat)
6. Run FFmpeg → output to temp file
7. Upload output to Railway bucket
8. Return presigned/public URL
9. Clean up temp files
```

---

### 8. Timeout Considerations

- Merging can take minutes for long videos.
- Use **BackgroundTasks** or **Celery** for production:
  - Sync: long HTTP timeout (e.g. 600s) for shorter merges.
  - Async: return `job_id`, client polls `GET /api/v1/merge/{job_id}` for status and URL.

For a first version, sync with a 10–15 minute timeout is acceptable.

---

## Environment Variables

```env
API_KEY=your-secure-api-key
BUCKET=your-railway-bucket-name
ENDPOINT=https://storage.railway.app
ACCESS_KEY_ID=...
SECRET_ACCESS_KEY=...
REGION=auto
PORT=8000
```

Same as bg-remover-api; reuse your auth and storage setup.

---

## Suggested Dependencies (requirements.txt)

```txt
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
httpx>=0.25.0
boto3>=1.29.0
python-dotenv>=1.0.0
python-multipart>=0.0.6
pydantic>=2.0.0
# Optional: ffmpeg-python or moviepy for cleaner FFmpeg usage
ffmpeg-python>=0.2.0
```

---

## Error Handling

| Scenario | HTTP | Message |
|----------|------|---------|
| Too few/many URLs | 400 | "Provide between 2 and 10 video URLs" |
| Invalid URL | 400 | "Invalid URL: ..." |
| Download failed | 422 | "Failed to download video from URL: ..." |
| Invalid video format | 400 | "Video at index N is not a supported format" |
| Total duration > 2h | 400 | "Total duration (Xs) exceeds maximum of 7200s" |
| FFmpeg error | 500 | "Video processing failed" |
| Storage error | 500 | "Failed to upload merged video" |

---

## Railway Deployment

- Same as bg-remover-api: deploy from GitHub, add bucket, set variables.
- Ensure FFmpeg is available (nixpacks, Aptfile, or Docker).
- Consider more memory/CPU for video workloads.
- Health check path: `/health`.

---

## Testing Locally

1. Install FFmpeg: `ffmpeg -version`
2. Create `.env` from `.env.example`
3. Run: `uvicorn main:app --reload`
4. Example request:

   ```bash
   curl -X POST http://localhost:8000/api/v1/merge \
     -H "X-API-Key: YOUR_KEY" \
     -H "Content-Type: application/json" \
     -d '{"video_urls": ["https://...", "https://..."], "quality": "720", "aspect_ratio": "9:16"}'
   ```

---

## Optional Enhancements

- **Transition type**: Parameter for fade, wipe, etc. (xfade supports several)
- **Transition duration**: e.g. 0.3–1.5 seconds
- **Format support**: Limit to mp4/webm; validate with ffprobe
- **Rate limiting**: Per-API-key limits for expensive merges
- **Webhook**: Notify when async merge is done

---

## Summary Checklist

- [ ] FastAPI app with `/api/v1/merge` POST
- [ ] Request validation: 2–10 URLs, quality, aspect_ratio
- [ ] Download videos, ffprobe for duration
- [ ] Reject if total duration > 7200s
- [ ] FFmpeg merge with xfade transitions
- [ ] Scale/pad to target resolution and aspect ratio
- [ ] Keep audio from sources
- [ ] Upload to Railway bucket
- [ ] Return merged video URL
- [ ] X-API-Key auth (reuse bg-remover pattern)
- [ ] FFmpeg available in deploy environment
