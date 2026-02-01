"""Download videos, validate duration, merge with FFmpeg (scale, pad, xfade)."""
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple

import httpx

# Target dimensions: (width, height) for quality + aspect_ratio
DIMENSIONS = {
    ("720", "16:9"): (1280, 720),
    ("720", "9:16"): (720, 1280),
    ("720", "1:1"): (720, 720),
    ("1080", "16:9"): (1920, 1080),
    ("1080", "9:16"): (1080, 1920),
    ("1080", "1:1"): (1080, 1080),
}

MAX_DURATION_SECONDS = 7200  # 2 hours
XFADE_DURATION = 0.5
DOWNLOAD_TIMEOUT = 300  # 5 min per file


def get_dimensions(quality: str, aspect_ratio: str) -> Tuple[int, int]:
    """Return (width, height) for the given quality and aspect ratio."""
    key = (quality, aspect_ratio)
    if key not in DIMENSIONS:
        raise ValueError(f"Unsupported quality/aspect_ratio: {quality} / {aspect_ratio}")
    return DIMENSIONS[key]


def download_video(url: str, dest: Path) -> None:
    """Download a single video from URL to dest. Raises on failure."""
    with httpx.stream("GET", url, timeout=DOWNLOAD_TIMEOUT, follow_redirects=True) as r:
        r.raise_for_status()
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)


def get_duration_and_has_audio(path: Path) -> Tuple[float, bool]:
    """Use ffprobe to get duration in seconds and whether the file has audio. Raises if invalid."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration:stream=codec_type",
            "-of", "default=noprint_wrappers=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise ValueError(f"Invalid or unsupported video: {result.stderr or result.stdout}")

    duration = None
    has_audio = False
    for line in (result.stdout or "").strip().split("\n"):
        if line.startswith("duration="):
            try:
                duration = float(line.split("=", 1)[1].strip())
            except (IndexError, ValueError):
                pass
        if line.strip() == "codec_type=audio":
            has_audio = True

    if duration is None:
        # Fallback: only format duration
        result2 = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result2.returncode != 0:
            raise ValueError("Could not get duration")
        duration = float((result2.stdout or "").strip())

    return duration, has_audio


def merge_videos(
    paths: List[Path],
    quality: str,
    aspect_ratio: str,
    output_path: Path,
    durations: List[float],
    has_audio_list: List[bool],
) -> float:
    """
    Merge videos with scale, pad, xfade (video) and acrossfade (audio).
    paths, durations, and has_audio_list must have the same length.
    Returns total output duration in seconds.
    """
    if len(paths) < 2:
        raise ValueError("At least 2 videos required")
    w, h = get_dimensions(quality, aspect_ratio)
    n = len(paths)
    transition = XFADE_DURATION
    need_silence = not all(has_audio_list)
    # Input index for anullsrc (only added if at least one clip has no audio)
    silence_idx = n

    # Build filter_complex
    # 1) Scale and pad each video to w x h
    video_filters = []
    for i in range(n):
        video_filters.append(
            f"[{i}:v]scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1[v{i}]"
        )
    video_part = ";".join(video_filters)

    # 2) xfade chain: [v0][v1]xfade -> [v01], [v01][v2]xfade -> [v02], ...
    offset = durations[0] - transition
    xfade_parts = [f"[v0][v1]xfade=transition=fade:duration={transition}:offset={offset}[v01]"]
    for i in range(2, n):
        prev_label = "v01" if i == 2 else f"v0{i}"
        curr_label = f"v0{i + 1}"
        offset = sum(durations[:i]) - i * transition
        xfade_parts.append(
            f"[{prev_label}][v{i}]xfade=transition=fade:duration={transition}:offset={offset}[{curr_label}]"
        )
    last_video = f"v0{n}"

    # 3) Audio: [i:a] or [silence_idx:a] trimmed to duration -> [ai]; then acrossfade chain
    audio_prep = []
    for i in range(n):
        if has_audio_list[i]:
            audio_prep.append(
                f"[{i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
                f"atrim=0:{durations[i]},asetpts=PTS-STARTPTS[a{i}]"
            )
        else:
            audio_prep.append(
                f"[{silence_idx}:a]atrim=0:{durations[i]},asetpts=PTS-STARTPTS[a{i}]"
            )
    audio_prep_str = ";".join(audio_prep)
    acrossfade_parts = [f"[a0][a1]acrossfade=d={transition}:c1=tri:c2=tri[a01]"]
    for i in range(2, n):
        prev = "a01" if i == 2 else f"a0{i}"
        curr = f"a0{i + 1}"
        acrossfade_parts.append(f"[{prev}][a{i}]acrossfade=d={transition}:c1=tri:c2=tri[{curr}]")
    last_audio = f"a0{n}"
    filter_complex = (
        f"{video_part};"
        f"{';'.join(xfade_parts)};"
        f"{audio_prep_str};"
        f"{';'.join(acrossfade_parts)}"
    )
    filter_complex += f";[{last_video}][{last_audio}]concat=n=1:v=1:a=1[outv][outa]"

    cmd = [
        "ffmpeg", "-y",
        *[str(p) for p in paths],
    ]
    if need_silence:
        cmd.extend(["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"])
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        str(output_path),
    ])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed: {result.stderr[-2000:] if result.stderr else result.stdout}")

    total_duration = sum(durations) - (n - 1) * transition
    return total_duration
