"""Pipeline orchestration."""

import logging
import time
from dataclasses import dataclass, field

from .chunking import split_text
from .config import DEFAULT_CHAIN, DEFAULT_TEMPERATURE, MIN_INPUT_WORDS
from .llm import paraphrase, strip_patterns, verify_preservation
from .translate import round_trip

logger = logging.getLogger(__name__)


@dataclass
class StageResult:
    name: str
    output: str
    warnings: list[str] = field(default_factory=list)
    seconds: float = 0.0


@dataclass
class HumanizeResult:
    final_text: str
    stages: list[StageResult]
    warnings: list[str]
    claim_loss: list[str]


def _redact(message: str, api_key: str) -> str:
    if api_key:
        return message.replace(api_key, "[REDACTED]")
    return message


def _notify(progress_cb, stage: str, chunk_index: int, total_chunks: int) -> None:
    if progress_cb is not None:
        progress_cb(stage, chunk_index, total_chunks)


def _run_stage(
    name: str,
    runner,
    fallback: str,
    progress_cb,
    chunk_index: int,
    total_chunks: int,
    api_key: str,
    warnings: list[str],
) -> tuple[str, StageResult]:
    """Run one chunk stage, falling back to the previous stage output on failure."""
    _notify(progress_cb, name, chunk_index, total_chunks)
    started = time.perf_counter()
    try:
        output, stage_warnings = runner()
    except Exception as exc:
        seconds = time.perf_counter() - started
        message = _redact(f"{name} failed: {exc}", api_key)
        logger.warning("%s", message)
        warnings.append(message)
        return fallback, StageResult(name, fallback, [message], seconds)

    seconds = time.perf_counter() - started
    stage_warnings = [_redact(w, api_key) for w in stage_warnings]
    warnings.extend(stage_warnings)
    return output, StageResult(name, output, stage_warnings, seconds)


def humanize_text(
    text: str,
    api_key: str,
    chain: list[str] = DEFAULT_CHAIN,
    temperature: float = DEFAULT_TEMPERATURE,
    run_verification: bool = True,
    progress_cb=None,
) -> HumanizeResult:
    """Rewrite text through paraphrase, translation round-trip, and pattern stripping.

    Progress callbacks receive (stage_name, chunk_index, total_chunks).
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Input text is empty.")
    stripped = text.strip()
    word_count = len(stripped.split())
    if word_count < MIN_INPUT_WORDS:
        raise ValueError(f"Input text must be at least {MIN_INPUT_WORDS} words (got {word_count}).")
    if not api_key or not api_key.strip():
        raise ValueError("A DeepSeek API key is required.")
    if not chain:
        raise ValueError("The translation chain is empty.")

    chunks = split_text(stripped)
    if not chunks:
        raise ValueError("Input text produced no chunks.")

    total = len(chunks)
    stages: list[StageResult] = []
    warnings: list[str] = []
    outputs: list[str] = []

    for index, chunk in enumerate(chunks, start=1):
        label = f"chunk {index}/{total}"

        current, stage = _run_stage(
            f"paraphrase [{label}]",
            lambda chunk=chunk: (paraphrase(chunk, api_key, temperature), []),
            chunk,
            progress_cb,
            index,
            total,
            api_key,
            warnings,
        )
        stages.append(stage)

        translated_source = current

        def do_translate(source=translated_source, label=label, index=index):
            def hop_callback(hop_index, hop_total, lang):
                _notify(
                    progress_cb,
                    f"translate [{label}] hop {hop_index + 1}/{hop_total} ({lang})",
                    index,
                    total,
                )

            return round_trip(source, chain, progress_cb=hop_callback)

        current, stage = _run_stage(
            f"translate [{label}]",
            do_translate,
            translated_source,
            progress_cb,
            index,
            total,
            api_key,
            warnings,
        )
        stages.append(stage)

        stripped_source = current
        current, stage = _run_stage(
            f"strip [{label}]",
            lambda source=stripped_source: (strip_patterns(source, api_key), []),
            stripped_source,
            progress_cb,
            index,
            total,
            api_key,
            warnings,
        )
        stages.append(stage)
        outputs.append(current)

    final_text = "\n\n".join(outputs)
    claim_loss: list[str] = []

    if run_verification:
        _notify(progress_cb, "verify", total, total)
        started = time.perf_counter()
        try:
            ok, loss = verify_preservation(stripped, final_text, api_key)
            claim_loss = [_redact(item, api_key) for item in loss]
            verify_warnings = (
                [] if ok else [f"Claim-preservation check flagged {len(claim_loss)} item(s)."]
            )
            verify_output = "NO LOSS" if ok else "\n".join(claim_loss)
        except Exception as exc:
            message = _redact(f"verify failed: {exc}", api_key)
            logger.warning("%s", message)
            verify_warnings = [message]
            verify_output = ""
        warnings.extend(verify_warnings)
        stages.append(
            StageResult(
                "verify",
                verify_output,
                verify_warnings,
                time.perf_counter() - started,
            )
        )

    return HumanizeResult(
        final_text=final_text,
        stages=stages,
        warnings=warnings,
        claim_loss=claim_loss,
    )
