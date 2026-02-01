# Video Merge API – REST API Guide

How to call the Video Merge API: authentication, endpoints, request/response format, and example `curl` commands.

---

## Base URL

- **Local:** `http://localhost:8000`
- **Production:** Your deployed URL (e.g. `https://your-app.up.railway.app`)

Replace `BASE_URL` in the examples below with your actual base URL.

---

## Authentication

All merge requests require an API key in the header:

| Header      | Required | Description                          |
|------------|----------|--------------------------------------|
| `X-API-Key` | Yes      | Your API key (set in env as `API_KEY`) |
| `Content-Type` | Yes  | `application/json` for merge requests |

**Example:**

```bash
-H "X-API-Key: YOUR_API_KEY"
-H "Content-Type: application/json"
```

---

## Endpoints

### Health check

**GET** `/health`  
No auth. Use to verify the service is up.

**Response (200):**

```json
{
  "status": "ok"
}
```

**Example:**

```bash
curl -s "https://BASE_URL/health"
```

---

### Merge videos

**POST** `/api/v1/merge`

Merge 2–10 video URLs into one video with configurable quality and aspect ratio. Total duration of all inputs must not exceed 2 hours (7200 seconds).

#### Request body

| Field          | Type     | Required | Values                          | Default  |
|----------------|----------|----------|----------------------------------|----------|
| `video_urls`   | string[] | Yes      | 2–10 valid HTTP(S) URLs          | —        |
| `quality`      | string   | No       | `"720"` or `"1080"`              | `"1080"` |
| `aspect_ratio`  | string   | No       | `"9:16"`, `"16:9"`, `"1:1"`      | `"16:9"` |

#### Success response (200)

```json
{
  "success": true,
  "merged_url": "https://...",
  "duration_seconds": 180.5,
  "processing_time": 45.2,
  "clips_merged": 3
}
```

#### Error response (4xx / 5xx)

```json
{
  "error": "Error message here"
}
```

Common errors: `400` (validation, duration limit), `401` (invalid/missing API key), `422` (download failed), `500` (processing or upload failed).

---

## cURL examples

Replace:

- `BASE_URL` → your API base URL (e.g. `https://your-app.up.railway.app` or `http://localhost:8000`)
- `YOUR_API_KEY` → your actual API key
- Video URLs → real, publicly accessible HTTP(S) URLs to `.mp4` (or supported) videos

---

### 1. Health check

```bash
curl -s "https://BASE_URL/health"
```

---

### 2. Merge 2 videos (min)

```bash
curl -X POST "https://BASE_URL/api/v1/merge" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "video_urls": [
      "https://example.com/video1.mp4",
      "https://example.com/video2.mp4"
    ],
    "quality": "1080",
    "aspect_ratio": "16:9"
  }'
```

**One-liner (replace URLs and key):**

```bash
curl -X POST "https://BASE_URL/api/v1/merge" -H "X-API-Key: YOUR_API_KEY" -H "Content-Type: application/json" -d '{"video_urls":["https://example.com/video1.mp4","https://example.com/video2.mp4"],"quality":"1080","aspect_ratio":"16:9"}'
```

---

### 3. Merge 2 videos – 720p, 9:16 (vertical)

```bash
curl -X POST "https://BASE_URL/api/v1/merge" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "video_urls": [
      "https://example.com/clip1.mp4",
      "https://example.com/clip2.mp4"
    ],
    "quality": "720",
    "aspect_ratio": "9:16"
  }'
```

---

### 4. Merge 10 videos (max)

```bash
curl -X POST "https://BASE_URL/api/v1/merge" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "video_urls": [
      "https://example.com/video1.mp4",
      "https://example.com/video2.mp4",
      "https://example.com/video3.mp4",
      "https://example.com/video4.mp4",
      "https://example.com/video5.mp4",
      "https://example.com/video6.mp4",
      "https://example.com/video7.mp4",
      "https://example.com/video8.mp4",
      "https://example.com/video9.mp4",
      "https://example.com/video10.mp4"
    ],
    "quality": "1080",
    "aspect_ratio": "16:9"
  }'
```

**One-liner (replace URLs and key):**

```bash
curl -X POST "https://BASE_URL/api/v1/merge" -H "X-API-Key: YOUR_API_KEY" -H "Content-Type: application/json" -d '{"video_urls":["https://example.com/v1.mp4","https://example.com/v2.mp4","https://example.com/v3.mp4","https://example.com/v4.mp4","https://example.com/v5.mp4","https://example.com/v6.mp4","https://example.com/v7.mp4","https://example.com/v8.mp4","https://example.com/v9.mp4","https://example.com/v10.mp4"],"quality":"1080","aspect_ratio":"16:9"}'
```

---

### 5. Merge 3 videos – 1:1 square, 720p

```bash
curl -X POST "https://BASE_URL/api/v1/merge" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "video_urls": [
      "https://example.com/a.mp4",
      "https://example.com/b.mp4",
      "https://example.com/c.mp4"
    ],
    "quality": "720",
    "aspect_ratio": "1:1"
  }'
```

---

## Testing with real URLs

Use publicly accessible MP4 URLs. For quick tests you can use sample videos, for example:

- [Sample Videos (W3C)](https://www.w3schools.com/html/mov_bbb.mp4)
- [Big Buck Bunny sample](https://sample-videos.com/video321/mp4/720/big_buck_bunny_720p_1mb.mp4) (if still available)
- Any direct link to an `.mp4` file you host or that allows public GET

**Example with sample URLs (replace `YOUR_API_KEY` and `BASE_URL`):**

```bash
curl -X POST "https://BASE_URL/api/v1/merge" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "video_urls": [
      "https://www.w3schools.com/html/mov_bbb.mp4",
      "https://www.w3schools.com/html/movie.mp4"
    ],
    "quality": "720",
    "aspect_ratio": "16:9"
  }'
```

---

## Limits and notes

- **URLs:** Between 2 and 10 per request; each must be a valid HTTP or HTTPS URL.
- **Duration:** Sum of all input durations must be ≤ 7200 seconds (2 hours).
- **Timeout:** Merging can take several minutes; use a long client timeout (e.g. 600 seconds).
- **Output:** `merged_url` is a presigned or public URL to the merged MP4; typically valid for 7 days (configurable in storage).
