import asyncio
import logging

logger = logging.getLogger(__name__)

_summarizer = None


def _load_summarizer(model_name: str):
    """Load (or return the cached) HuggingFace summarization pipeline.

    Uses a module-level singleton so the model is only loaded once per process.

    Args:
        model_name: HuggingFace model identifier (e.g. ``"sshleifer/distilbart-cnn-12-6"``).

    Returns:
        The loaded HuggingFace ``pipeline`` instance for summarization.
    """
    from transformers import pipeline
    global _summarizer
    if _summarizer is None:
        logger.info(f"Loading BART model: {model_name}")
        _summarizer = pipeline("summarization", model=model_name)
    return _summarizer


async def summarize(text: str, model_name: str) -> str:
    """Summarize text using a BART model, offloaded to a thread executor.

    The input is truncated to 1000 characters to stay within the model's
    token limit. Returns an empty string for blank input.

    Args:
        text: Full transcript text to summarize.
        model_name: HuggingFace model identifier for the BART summarizer.

    Returns:
        A condensed summary string, or ``""`` if the input was blank.
    """
    if not text.strip():
        return ""

    # BART has a max token limit — truncate to ~1000 chars for safety
    truncated = text[:1000]

    loop = asyncio.get_event_loop()

    def _run():
        summarizer = _load_summarizer(model_name)
        result = summarizer(truncated, max_length=150, min_length=30, do_sample=False)
        return result[0]["summary_text"]

    return await loop.run_in_executor(None, _run)
