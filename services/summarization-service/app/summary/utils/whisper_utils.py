import asyncio
import logging
import os

logger = logging.getLogger(__name__)

_model = None


def _load_model(model_name: str):
    """Load (or return the cached) Whisper model.

    Uses a module-level singleton so the model is only loaded once per process.

    Args:
        model_name: Whisper model size identifier (e.g. ``"base"``, ``"small"``).

    Returns:
        The loaded Whisper model instance.
    """
    import whisper
    global _model
    if _model is None:
        logger.info(f"Loading Whisper model: {model_name}")
        _model = whisper.load_model(model_name)
    return _model


async def extract_audio(video_id: str, hls_path: str) -> str:
    """Extract a mono 16 kHz WAV audio track from an HLS stream using ffmpeg.

    Args:
        video_id: UUID string of the video (used to name the output file).
        hls_path: Path to the HLS master manifest (``.m3u8``).

    Returns:
        Absolute path to the extracted WAV file.

    Raises:
        RuntimeError: If ffmpeg exits with a non-zero return code.
    """
    audio_path = f"/tmp/audio_{video_id}.wav"
    cmd = [
        "ffmpeg", "-y",
        "-i", hls_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", "16000",
        "-ac", "1",
        audio_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed: {stderr.decode()}")
    return audio_path


async def transcribe(audio_path: str, model_name: str) -> dict:
    """Transcribe a WAV file using Whisper, offloaded to a thread executor.

    The Whisper inference is CPU-heavy, so it runs in a thread pool to avoid
    blocking the event loop.

    Args:
        audio_path: Filesystem path to the WAV audio file.
        model_name: Whisper model size identifier (e.g. ``"base"``).

    Returns:
        Whisper result dict containing ``"text"`` (full transcript) and
        ``"segments"`` (per-segment timing and confidence data).
    """
    loop = asyncio.get_event_loop()

    def _run():
        model = _load_model(model_name)
        return model.transcribe(audio_path)

    result = await loop.run_in_executor(None, _run)
    return result


def extract_key_moments(segments: list) -> list[dict]:
    """Pick up to 10 meaningful key moments from Whisper segment data.

    A segment is included when its ``no_speech_prob`` is below 0.4 and its
    text is longer than 15 characters, filtering out silent or very short clips.

    Args:
        segments: List of Whisper segment dicts, each with ``start``,
            ``text``, and ``no_speech_prob`` keys.

    Returns:
        List of up to 10 dicts, each with ``timestamp`` (float, seconds)
        and ``label`` (str, first 120 chars of segment text).
    """
    key_moments = []
    for seg in segments:
        text = seg.get("text", "").strip()
        no_speech_prob = seg.get("no_speech_prob", 1.0)
        if no_speech_prob < 0.4 and len(text) > 15:
            key_moments.append({
                "timestamp": round(float(seg.get("start", 0)), 1),
                "label": text[:120],
            })
    return key_moments[:10]


def cleanup_audio(audio_path: str) -> None:
    """Delete a temporary audio file, silently ignoring missing-file errors.

    Args:
        audio_path: Filesystem path to the WAV file to remove.
    """
    try:
        os.remove(audio_path)
    except OSError:
        pass
