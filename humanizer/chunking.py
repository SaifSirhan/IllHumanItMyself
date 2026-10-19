"""Paragraph-safe text splitting."""

import logging
import re

from .config import MAX_CHUNK_WORDS

logger = logging.getLogger(__name__)

_PARAGRAPH_RE = re.compile(r"\n\s*\n")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def _word_count(text: str) -> int:
    return len(text.split())


def _split_paragraph(paragraph: str, max_words: int) -> list[str]:
    """Split an oversized paragraph on sentence boundaries, never inside one."""
    sentences = [s for s in _SENTENCE_RE.split(paragraph) if s.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0
    for sentence in sentences:
        words = _word_count(sentence)
        if current and current_words + words > max_words:
            chunks.append(" ".join(current))
            current, current_words = [], 0
        current.append(sentence)
        current_words += words
    if current:
        chunks.append(" ".join(current))
    return chunks


def split_text(text: str, max_words: int = MAX_CHUNK_WORDS) -> list[str]:
    """Split on blank-line paragraph boundaries. Never split mid-sentence.

    A single paragraph longer than max_words is split on sentence boundaries.
    Chunks preserve the original word order.
    """
    text = text.strip()
    if not text:
        return []
    if max_words <= 0:
        raise ValueError("max_words must be positive")

    paragraphs = [p.strip() for p in _PARAGRAPH_RE.split(text) if p.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_words = 0

    def flush() -> None:
        nonlocal current, current_words
        if current:
            chunks.append("\n\n".join(current))
            current, current_words = [], 0

    for paragraph in paragraphs:
        words = _word_count(paragraph)
        if words > max_words:
            flush()
            chunks.extend(_split_paragraph(paragraph, max_words))
            continue
        if current and current_words + words > max_words:
            flush()
        current.append(paragraph)
        current_words += words
    flush()

    logger.info("Split text into %d chunk(s)", len(chunks))
    return chunks
