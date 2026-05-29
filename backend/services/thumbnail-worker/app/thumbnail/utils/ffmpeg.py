import asyncio
import logging
import os

from app.config import settings

logger = logging.getLogger(__name__)


async def extract_thumbnail(
    video_id: str,
    input_path: str,
    timestamp: str = "00:00:05",
) -> str:
    """Extract a single JPEG frame from a video file using ffmpeg.

    Args:
        video_id: Used to name the output file as ``<video_id>.jpg``.
        input_path: Absolute path to the source video file.
        timestamp: Timecode in ``HH:MM:SS`` format at which to capture the
            frame. Defaults to ``"00:00:05"``.

    Returns:
        Absolute path to the saved JPEG thumbnail.

    Raises:
        RuntimeError: If the ffmpeg subprocess exits with a non-zero code.
    """
    output_dir = os.path.join(settings.MEDIA_ROOT, "thumbnails")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{video_id}.jpg")

    cmd = [
        "ffmpeg", "-y",
        "-ss", timestamp,
        "-i", input_path,
        "-vframes", "1",
        "-q:v", "2",
        output_path,
    ]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg thumbnail extraction failed (exit {proc.returncode}): {stderr.decode()}"
        )

    return output_path
