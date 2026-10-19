"""Round-trip translation chain via deep-translator."""

import logging
import time

from deep_translator import GoogleTranslator

from .config import (
    MAX_LEN_RATIO,
    MIN_LEN_RATIO,
    TRANSLATE_BACKOFF_SECONDS,
    TRANSLATE_HOP_DELAY_SECONDS,
    TRANSLATE_RETRIES,
)

logger = logging.getLogger(__name__)


def translate(text: str, source: str, target: str) -> str:
    """Single translation hop. 3 attempts with 1.5s backoff."""
    last_error: Exception | None = None
    for attempt in range(TRANSLATE_RETRIES):
        try:
            output = GoogleTranslator(source=source, target=target).translate(text)
            output = (output or "").strip()
            if not output:
                raise RuntimeError("translator returned an empty response")
            return output
        except Exception as exc:  # deep-translator raises varied error types
            last_error = exc
            if attempt < TRANSLATE_RETRIES - 1:
                time.sleep(TRANSLATE_BACKOFF_SECONDS)

    raise RuntimeError(
        f"Translation {source}->{target} failed after {TRANSLATE_RETRIES} attempts: {last_error}"
    ) from last_error


def _coherent(src: str, out: str) -> bool:
    """Reject empty, identical, or implausibly long/short translations."""
    if not out or not out.strip():
        return False
    src_clean = src.strip()
    out_clean = out.strip()
    if not src_clean or out_clean == src_clean:
        return False
    ratio = len(out_clean) / len(src_clean)
    return MIN_LEN_RATIO <= ratio <= MAX_LEN_RATIO


def round_trip(
    text: str, chain: list[str], progress_cb=None
) -> tuple[str, list[str]]:
    """Translate through each language in chain, then back to English.

    Failed or incoherent hops are skipped with a warning. If no hop succeeds,
    RuntimeError is raised instead of returning the input unchanged.
    """
    warnings: list[str] = []
    current_text = text
    current_lang = "en"
    total_hops = len(chain) + 1
    successes = 0

    for index, lang in enumerate(chain):
        if progress_cb is not None:
            progress_cb(index, total_hops, lang)
        try:
            output = translate(current_text, current_lang, lang)
            if not _coherent(current_text, output):
                raise RuntimeError("incoherent translation output")
            current_text, current_lang = output, lang
            successes += 1
        except Exception as exc:
            warnings.append(f"Skipped {current_lang}->{lang}: {exc}")
            logger.warning("Skipped translation hop %s->%s: %s", current_lang, lang, exc)
        # Keep hops apart to avoid rate limiting; the final hop waits too.
        time.sleep(TRANSLATE_HOP_DELAY_SECONDS)

    if successes == 0:
        raise RuntimeError("Every translation hop failed: " + "; ".join(warnings))

    if progress_cb is not None:
        progress_cb(len(chain), total_hops, "en")

    if current_lang != "en":
        try:
            output = translate(current_text, current_lang, "en")
            if not _coherent(current_text, output):
                raise RuntimeError("incoherent final translation output")
            current_text = output
        except Exception as exc:
            raise RuntimeError(f"Final hop back to English failed: {exc}") from exc

    return current_text, warnings
