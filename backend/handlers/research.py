"""Research question handler — delegates to conversation agent for concept explanations."""
from __future__ import annotations

from backend.services.conversation_agent import generate_response


async def handle_research(
    message: str,
    history: list[dict[str, str]],
    language: str,
    intent: dict,
) -> str:
    """Generate educational response about financial concepts."""
    return await generate_response(
        message=message,
        history=history,
        language=language,
        intent=intent,
    )
