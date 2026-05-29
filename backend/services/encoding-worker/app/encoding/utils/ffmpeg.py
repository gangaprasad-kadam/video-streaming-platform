import asyncio
import json
import logging
import os

from app.config import settings

logger = logging.getLogger(__name__)


async def transcode_to_hls(video_id: str, input_path: str) -> dict:
    """Transcode a video file to HLS format using ffmpeg.

    Creates an output directory at ``MEDIA_ROOT/hls/{video_id}``, runs ffmpeg
    to produce segmented HLS files and an ``.m3u8`` manifest, and probes the
    source file for its duration.

    Args:
        video_id: Unique video identifier; used to name the output directory.
        input_path: Absolute filesystem path to the source video file.

    Returns:
        A dict containing:
            - ``hls_path`` (str): Absolute path to the generated ``.m3u8`` manifest.
            - ``duration`` (float | None): Video length in seconds, or ``None``
              if ffprobe could not determine it.

    Raises:
        RuntimeError: If the ffmpeg subprocess exits with a non-zero code.
    """
    output_dir = os.path.join(settings.MEDIA_ROOT, "hls", video_id)
    os.makedirs(output_dir, exist_ok=True)
    manifest_path = os.path.join(output_dir, "index.m3u8")

    duration = await _get_duration(input_path)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c:v", "libx264",   # H.264 — universally supported in HLS/TS (handles VP9, AV1, etc.)
        "-crf", "23",        # quality level: 23 is a good default (lower = better, 18-28 range)
        "-preset", "fast",   # encoding speed vs compression tradeoff
        "-profile:v", "main",
        "-level:v", "4.0",
        "-c:a", "aac",       # AAC audio for HLS browser compatibility
        "-b:a", "128k",
        "-movflags", "+faststart",
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
    """Return the duration of a media file in seconds using ffprobe.

    Args:
        input_path: Absolute path to the media file to probe.

    Returns:
        Duration as a float (seconds), or ``None`` if ffprobe fails or the
        duration field is absent in the output.
    """
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
    """Run an external command asynchronously and return its stdout.

    Args:
        cmd: The command and its arguments to execute.
        label: Human-readable name for the command, used in error messages.

    Returns:
        The decoded stdout string produced by the subprocess.

    Raises:
        RuntimeError: If the process exits with a non-zero return code,
            including the stderr output in the exception message.
    """
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
