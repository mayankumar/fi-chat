"""Classify user intent via Claude Haiku with entity extraction."""
from __future__ import annotations

import json
import logging

import anthropic

from backend.config import get_settings

logger = logging.getLogger("fi-chat.intent")

INTENT_TYPES = [
    "greeting",
    "goal_discovery",
    "risk_assessment",
    "portfolio_query",
    "transaction_action",
    "research_question",
    "stock_question",
    "product_inquiry",
    "pdf_modification",
    "tta_request",
    "general_chat",
    "off_topic",
]

_PROMPT = """You are an intent classifier for a mutual fund advisory WhatsApp bot (FundsIndia).

Classify the user message into exactly ONE intent and extract relevant entities.

Intents:
- greeting: Hi, hello, good morning, etc.
- goal_discovery: User wants help setting financial goals (retirement, education, house)
- risk_assessment: User wants to understand their risk profile
- portfolio_query: Questions about their existing portfolio, holdings, returns
- transaction_action: Wants to buy, sell, redeem, switch, start/stop SIP
- research_question: Wants to learn about financial concepts (SIP, NAV, ELSS, mutual funds, etc.)
- stock_question: Asks about specific stocks, share prices, equity trading
- product_inquiry: Asks about specific mutual fund schemes or categories
- pdf_modification: Wants changes to their advisory PDF/report
- tta_request: Wants to talk to a human advisor / relationship manager
- general_chat: General conversation loosely related to finance
- off_topic: Completely unrelated to finance (weather, sports, politics, etc.)

Conversation context (last few messages):
{history}

Current user message: {message}

Respond with ONLY valid JSON (no markdown):
{{"intent": "<intent>", "entities": {{"topic": "<if applicable>", "fund_name": "<if applicable>"}}, "confidence": <0.0-1.0>}}"""


async def classify_intent(message: str, history: list[dict] = None) -> dict:
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Build compact history context
    history_text = ""
    if history:
        recent = history[-6:]  # last 3 exchanges
        history_text = "\n".join(
            f"{m['role']}: {m['content'][:150]}" for m in recent
        )

    logger.debug("Classifying intent for: %r (history_len=%d)", message[:60], len(history or []))

    response = await client.messages.create(
        model=settings.haiku_model,
        max_tokens=150,
        messages=[
            {
                "role": "user",
                "content": _PROMPT.format(message=message, history=history_text),
            }
        ],
    )

    raw = response.content[0].text.strip()
    logger.debug("Raw intent response: %s", raw)

    try:
        result = json.loads(raw)
        if result.get("intent") not in INTENT_TYPES:
            logger.warning("Unknown intent %r from model, falling back to general_chat", result.get("intent"))
            result["intent"] = "general_chat"
        logger.info("Classified: intent=%s confidence=%.2f entities=%s (usage: in=%d out=%d)",
                     result.get("intent"), result.get("confidence", 0), result.get("entities", {}),
                     response.usage.input_tokens, response.usage.output_tokens)
        return result
    except (json.JSONDecodeError, KeyError):
        logger.error("Failed to parse intent JSON: %r", raw)
        return {"intent": "general_chat", "entities": {}, "confidence": 0.0}
