import asyncio
import json
import logging
import os

from app.config import settings

logger = logging.getLogger(__name__)


async def transcode_to_hls(video_id: str, input_path: str) -> dict:
    """Transcode a video file to HLS format. Returns hls_path and duration."""
    output_dir = os.path.join(settings.MEDIA_ROOT, "hls", video_id)
    os.makedirs(output_dir, exist_ok=True)
    manifest_path = os.path.join(output_dir, "index.m3u8")

    duration = await _get_duration(input_path)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-codec:", "copy",
        "-start_number", "0",
        "-hls_time", "6",
        "-hls_list_size", "0",
        "-f", "hls",
        manifest_path,
    ]
    await _run_subprocess(cmd, f"ffmpeg HLS transcode [{video_id}]")
    logger.info(f"[{video_id}] HLS manifest written: {manifest_path}")

    return {
        "hls_path": manifest_path,
        "duration": duration,
    }


async def _get_duration(input_path: str) -> float | None:
    """Extract video duration in seconds via ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        input_path,
    ]
    try:
        stdout = await _run_subprocess(cmd, "ffprobe")
        data = json.loads(stdout)
        return float(data["format"]["duration"])
    except Exception:
        logger.warning(f"Could not extract duration from {input_path}")
        return None


async def _run_subprocess(cmd: list[str], label: str) -> str:
    """Run a subprocess asynchronously; raise RuntimeError on non-zero exit."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(
            f"{label} failed (exit {proc.returncode}): {stderr.decode()}"
        )
    return stdout.decode()
