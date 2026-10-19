"""DeepSeek API calls."""

import logging
import time

from openai import APIError, NotFoundError, OpenAI

from .config import (
    DEEPSEEK_BASE_URL,
    DEEPSEEK_FALLBACK_MODEL,
    DEEPSEEK_MODEL,
    LLM_BACKOFF_SECONDS,
    LLM_RETRIES,
    LLM_TIMEOUT_SECONDS,
    VERIFY_TEMPERATURE,
    STRIP_TEMPERATURE,
)
from .prompts import PARAPHRASE_SYSTEM, STRIP_SYSTEM, VERIFY_SYSTEM

logger = logging.getLogger(__name__)


def _client(api_key: str) -> OpenAI:
    return OpenAI(
        api_key=api_key,
        base_url=DEEPSEEK_BASE_URL,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=0,
    )


def _redact(message: str, api_key: str) -> str:
    if api_key:
        return message.replace(api_key, "[REDACTED]")
    return message


def call_llm(api_key: str, system: str, user: str, temperature: float) -> str:
    """Call DeepSeek with retries. Raises RuntimeError after retries are exhausted."""
    model = DEEPSEEK_MODEL
    last_error: Exception | None = None

    for attempt in range(LLM_RETRIES):
        try:
            completion = _client(api_key).chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
            content = (completion.choices[0].message.content or "").strip()
            if not content:
                raise ValueError("DeepSeek returned an empty response")
            return content
        except NotFoundError as exc:
            last_error = exc
            if model != DEEPSEEK_FALLBACK_MODEL:
                logger.warning(
                    "Model %s was not found; falling back to %s",
                    model,
                    DEEPSEEK_FALLBACK_MODEL,
                )
                model = DEEPSEEK_FALLBACK_MODEL
                continue
        except (APIError, TimeoutError) as exc:
            last_error = exc
        except ValueError as exc:
            last_error = exc

        if attempt < LLM_RETRIES - 1:
            time.sleep(LLM_BACKOFF_SECONDS[attempt])

    message = f"DeepSeek API call failed after {LLM_RETRIES} attempts: {last_error}"
    raise RuntimeError(_redact(message, api_key)) from last_error


def paraphrase(text: str, api_key: str, temperature: float = 1.3) -> str:
    return call_llm(api_key, PARAPHRASE_SYSTEM, text, temperature)


def strip_patterns(text: str, api_key: str) -> str:
    return call_llm(api_key, STRIP_SYSTEM, text, STRIP_TEMPERATURE)


def verify_preservation(
    original: str, rewritten: str, api_key: str
) -> tuple[bool, list[str]]:
    """Return (ok, loss_list) for facts present in original but missing in rewritten."""
    user = f"TEXT A:\n{original}\n\nTEXT B:\n{rewritten}"
    response = call_llm(api_key, VERIFY_SYSTEM, user, VERIFY_TEMPERATURE)
    if "NO LOSS" in response.upper():
        return True, []

    items: list[str] = []
    other_lines: list[str] = []
    for line in response.splitlines():
        line = line.strip()
        if not line:
            continue
        if line[:1] in "-*•":
            items.append(line.lstrip("-*• ").strip())
        else:
            other_lines.append(line)
    if not items:
        items = other_lines
    return (not items, [item for item in items if item])
