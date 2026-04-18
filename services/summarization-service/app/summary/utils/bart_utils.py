import asyncio
import logging

logger = logging.getLogger(__name__)

_summarizer = None


def _load_summarizer(model_name: str):
    from transformers import pipeline
    global _summarizer
    if _summarizer is None:
        logger.info(f"Loading BART model: {model_name}")
        _summarizer = pipeline("summarization", model=model_name)
    return _summarizer


async def summarize(text: str, model_name: str) -> str:
    """Run BART summarization in a thread executor (CPU-heavy)."""
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
