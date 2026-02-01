"""
Video Merge API – accepts 2–10 video URLs, merges with quality/aspect ratio, returns merged video URL.
"""
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, field_validator

from utils.auth import get_api_key
from utils.storage import upload_merged_video
from utils.video_processor import (
    MAX_DURATION_SECONDS,
    download_video,
    get_duration_and_has_audio,
    merge_videos,
)

# --- Request / Response models ---


class MergeRequest(BaseModel):
    video_urls: List[str] = Field(...)
    quality: str = Field(default="1080", pattern="^(720|1080)$")
    aspect_ratio: str = Field(default="16:9", pattern="^(9:16|16:9|1:1)$")

    @field_validator("video_urls")
    @classmethod
    def validate_urls(cls, v: List[str]) -> List[str]:
        if not v or len(v) < 2 or len(v) > 10:
            raise ValueError("Provide between 2 and 10 video URLs")
        url_re = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)
        for i, u in enumerate(v):
            u = (u or "").strip()
            if not u or not url_re.match(u):
                raise ValueError(f"Invalid URL: {u!r}")
        return [u.strip() for u in v]


class MergeSuccessResponse(BaseModel):
    success: bool = True
    merged_url: str
    duration_seconds: float
    processing_time: float
    clips_merged: int


# --- Router ---

router = APIRouter(prefix="/api/v1", tags=["merge"])


@router.post("/merge", response_model=MergeSuccessResponse)
def merge(
    body: MergeRequest,
    _api_key: str = Depends(get_api_key),
) -> MergeSuccessResponse:
    """
    Merge 2–10 video URLs into one video with configurable quality and aspect ratio.
    Total duration must not exceed 2 hours. Returns URL to the merged video.
    """
    start = time.perf_counter()
    temp_dir = Path(tempfile.mkdtemp())
    try:
        # 1) Download each video
        paths: List[Path] = []
        for i, url in enumerate(body.video_urls):
            dest = temp_dir / f"clip_{i}.mp4"
            try:
                download_video(url, dest)
            except Exception as e:
                raise HTTPException(
                    status_code=422,
                    detail=f"Failed to download video from URL: {url[:80]}...",
                ) from e
            paths.append(dest)

        # 2) Probe duration and audio for each
        durations: List[float] = []
        has_audio_list: List[bool] = []
        for i, p in enumerate(paths):
            try:
                dur, has_audio = get_duration_and_has_audio(p)
                durations.append(dur)
                has_audio_list.append(has_audio)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Video at index {i} is not a supported format",
                ) from e

        total_duration = sum(durations)
        if total_duration > MAX_DURATION_SECONDS:
            raise HTTPException(
                status_code=400,
                detail=f"Total duration ({int(total_duration)}s) exceeds maximum of {MAX_DURATION_SECONDS}s",
            )

        # 3) Merge with FFmpeg
        out_path = temp_dir / "merged.mp4"
        try:
            output_duration = merge_videos(
                paths,
                body.quality,
                body.aspect_ratio,
                out_path,
                durations,
                has_audio_list,
            )
        except RuntimeError as e:
            raise HTTPException(status_code=500, detail="Video processing failed") from e

        # 4) Upload to Railway bucket
        try:
            merged_url = upload_merged_video(out_path, key_prefix=f"merged-{uuid.uuid4().hex[:12]}")
        except Exception as e:
            raise HTTPException(status_code=500, detail="Failed to upload merged video") from e

        elapsed = time.perf_counter() - start
        return MergeSuccessResponse(
            merged_url=merged_url,
            duration_seconds=round(output_duration, 2),
            processing_time=round(elapsed, 2),
            clips_merged=len(paths),
        )
    finally:
        # 5) Cleanup temp files
        for f in (temp_dir.iterdir() if temp_dir.exists() else []):
            try:
                f.unlink()
            except OSError:
                pass
        try:
            temp_dir.rmdir()
        except OSError:
            pass


# --- App ---

app = FastAPI(
    title="Video Merge API",
    description="Merge 2–10 video URLs with configurable quality and aspect ratio.",
    version="1.0.0",
)

app.include_router(router)


@app.exception_handler(HTTPException)
def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Return errors as { \"error\": \"...\" } per API spec."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail if isinstance(exc.detail, str) else str(exc.detail)},
    )


@app.exception_handler(RequestValidationError)
def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return validation errors as { \"error\": \"...\" }."""
    errors = exc.errors()
    msg = errors[0].get("msg", "Validation error") if errors else "Validation error"
    return JSONResponse(status_code=400, content={"error": msg})


@app.get("/health")
def health():
    """Health check for Railway / load balancers."""
    return {"status": "ok"}
