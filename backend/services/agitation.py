"""Agitation detection — Haiku monitors sentiment, triggers proactive TTA at high frustration."""
from __future__ import annotations

import json
import logging
import re

import anthropic

from backend.config import get_settings

logger = logging.getLogger("fi-chat.agitation")

# Check agitation every N user messages
_CHECK_INTERVAL = 3
_THRESHOLD = 6  # Score >= this triggers proactive TTA


_PROMPT = """You are a sentiment analyst for a financial advisory WhatsApp bot.

Analyze this conversation for customer frustration/agitation on a scale of 0-10:
- 0-2: Happy, engaged, satisfied
- 3-5: Neutral, some mild frustration but manageable
- 6-7: Frustrated — confused, repeating themselves, expressing dissatisfaction
- 8-10: Very agitated — angry, threatening to leave, demanding human help

CONVERSATION (last few messages):
{conversation}

Consider:
- Repeated questions (bot not understanding)
- Expressions of frustration ("this is not helping", "I already said", "useless")
- Demands for human help (even indirect: "is there a real person")
- Excessive short responses showing disengagement
- Uppercase, exclamation marks, negative language

Respond with ONLY a raw JSON object:
{{"score": <0-10>, "reason": "<brief explanation>"}}"""


async def check_agitation(messages: list[dict]) -> dict | None:
    """Check agitation level based on recent messages.

    Returns {"score": int, "reason": str} if check was performed, None if skipped.
    Only checks every _CHECK_INTERVAL user messages.
    """
    # Count user messages
    user_msgs = [m for m in messages if m["role"] == "user"]
    if len(user_msgs) < _CHECK_INTERVAL:
        return None

    # Only check at intervals
    if len(user_msgs) % _CHECK_INTERVAL != 0:
        return None

    # Build conversation context (last 8 messages)
    recent = messages[-8:]
    conv_text = "\n".join(
        f"{m['role'].upper()}: {m['content'][:200]}" for m in recent
    )

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        response = await client.messages.create(
            model=settings.haiku_model,
            max_tokens=100,
            messages=[
                {"role": "user", "content": _PROMPT.format(conversation=conv_text)}
            ],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            raw = raw.strip()

        result = json.loads(raw)
        score = int(result.get("score", 0))
        reason = result.get("reason", "")

        logger.info("Agitation check: score=%d reason=%s (msgs=%d)", score, reason[:60], len(user_msgs))
        return {"score": score, "reason": reason}

    except Exception as exc:
        logger.warning("Agitation check failed: %s", exc)
        return None


def should_trigger_tta(agitation_result: dict | None) -> bool:
    """Returns True if agitation score meets threshold for proactive TTA."""
    if not agitation_result:
        return False
    return agitation_result.get("score", 0) >= _THRESHOLD


def get_proactive_tta_message(language: str) -> str:
    """Message to send when agitation triggers proactive TTA."""
    messages = {
        "en": (
            "I sense you might need more personalized guidance 🤔\n\n"
            "Would you like me to connect you with one of our *expert advisors*? "
            "They can help you with detailed, tailored advice for your specific situation! 🧑‍💼"
        ),
        "hi": (
            "Lagta hai aapko zyada personalized guidance chahiye 🤔\n\n"
            "Kya main aapko humare *expert advisor* se connect karun? "
            "Woh aapki specific situation ke liye detailed advice de sakte hain! 🧑‍💼"
        ),
        "hinglish": (
            "Lagta hai aapko more personalized guidance chahiye 🤔\n\n"
            "Kya main aapko humare *expert advisor* se connect karun? "
            "They can give you detailed, tailored advice! 🧑‍💼"
        ),
    }
    return messages.get(language, messages["en"])
