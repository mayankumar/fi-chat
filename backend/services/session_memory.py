"""Tier-2 memory — session summaries for returning user context.

When a session goes idle (>30 min) or is explicitly closed, generate a summary
and store it. On next visit, the summary is loaded into context.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path

import anthropic

from backend.config import get_settings

logger = logging.getLogger("fi-chat.memory")

MEMORY_DIR = Path("session_memories")
MEMORY_DIR.mkdir(exist_ok=True)


_SUMMARY_PROMPT = """Summarize this WhatsApp conversation between a customer and FundsIndia's AI assistant (Finn) in 3-5 sentences. Focus on:
- What the customer wanted (goals, questions, issues)
- What was accomplished (plans generated, info provided)
- Any pending actions or unresolved items
- Customer's mood and preferences

CONVERSATION:
{conversation}

Respond with ONLY a JSON object (no markdown):
{{"summary": "...", "key_topics": ["...", "..."], "pending_actions": ["...", "..."], "customer_mood": "positive|neutral|frustrated"}}"""


async def generate_session_summary(phone: str, messages: list[dict]) -> dict | None:
    """Generate a summary of the session for future context."""
    if len(messages) < 4:
        return None

    conv_text = "\n".join(
        f"{m['role'].upper()}: {m['content'][:200]}" for m in messages[-20:]
    )

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        response = await client.messages.create(
            model=settings.haiku_model,
            max_tokens=300,
            messages=[
                {"role": "user", "content": _SUMMARY_PROMPT.format(conversation=conv_text)}
            ],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            raw = raw.strip()

        result = json.loads(raw)
        result["phone"] = phone
        result["message_count"] = len(messages)

        # Persist
        safe_phone = phone.replace("+", "").replace(":", "_")
        path = MEMORY_DIR / f"{safe_phone}.json"

        # Append to existing memories (keep last 5 sessions)
        existing = []
        if path.exists():
            try:
                existing = json.loads(path.read_text())
                if not isinstance(existing, list):
                    existing = [existing]
            except (json.JSONDecodeError, Exception):
                existing = []

        existing.append(result)
        existing = existing[-5:]  # keep last 5 session summaries

        path.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
        logger.info("Session memory saved for %s (%d summaries total)", phone, len(existing))
        return result

    except Exception as exc:
        logger.warning("Session memory generation failed: %s", exc)
        return None


def get_session_memories(phone: str) -> list[dict]:
    """Load past session summaries for a phone number."""
    safe_phone = phone.replace("+", "").replace(":", "_")
    path = MEMORY_DIR / f"{safe_phone}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return data
        return [data]
    except (json.JSONDecodeError, Exception):
        return []


def build_memory_context(phone: str) -> str:
    """Build a context string from past session memories for injection into prompts."""
    memories = get_session_memories(phone)
    if not memories:
        return ""

    parts = ["\n\n== PAST SESSION CONTEXT (returning user) =="]
    for i, mem in enumerate(memories[-3:], 1):  # last 3 sessions
        parts.append(f"Session {i}: {mem.get('summary', 'N/A')}")
        pending = mem.get("pending_actions", [])
        if pending:
            parts.append(f"  Pending: {', '.join(pending)}")

    return "\n".join(parts)
