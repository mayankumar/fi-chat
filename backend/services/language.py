"""Detect user language (en / hi / hinglish) via Claude Haiku."""

import logging

import anthropic

from backend.config import get_settings

logger = logging.getLogger("fi-chat.language")

_PROMPT = """Classify the language of the following user message into exactly one of: en, hi, hinglish

Rules:
- "en" = English
- "hi" = Hindi (Devanagari script)
- "hinglish" = Hindi written in Latin script, or mixed Hindi-English

Respond with ONLY the language code, nothing else.

Message: {message}"""


async def detect_language(message: str) -> str:
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    logger.debug("Sending language detection request for: %r", message[:60])

    response = await client.messages.create(
        model=settings.haiku_model,
        max_tokens=10,
        messages=[{"role": "user", "content": _PROMPT.format(message=message)}],
    )

    raw = response.content[0].text.strip().lower()
    lang = raw if raw in ("en", "hi", "hinglish") else "en"

    if raw != lang:
        logger.warning("Unexpected language response %r, defaulting to 'en'", raw)

    logger.info("Detected language: %s (raw=%r, usage: in=%d out=%d)",
                lang, raw, response.usage.input_tokens, response.usage.output_tokens)
    return lang
