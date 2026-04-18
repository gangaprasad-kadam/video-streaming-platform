import asyncio
import logging
import os

logger = logging.getLogger(__name__)

_model = None


def _load_model(model_name: str):
    import whisper
    global _model
    if _model is None:
        logger.info(f"Loading Whisper model: {model_name}")
        _model = whisper.load_model(model_name)
    return _model


async def extract_audio(video_id: str, hls_path: str) -> str:
    """Extract audio from HLS manifest using ffmpeg. Returns WAV file path."""
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
    """Run Whisper transcription in a thread executor (CPU-heavy)."""
    loop = asyncio.get_event_loop()

    def _run():
        model = _load_model(model_name)
        return model.transcribe(audio_path)

    result = await loop.run_in_executor(None, _run)
    return result


def extract_key_moments(segments: list) -> list[dict]:
    """Extract up to 10 meaningful key moments from Whisper segments."""
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
    """Remove temporary audio file."""
    try:
        os.remove(audio_path)
    except OSError:
        pass
