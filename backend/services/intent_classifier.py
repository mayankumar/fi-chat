"""Classify user intent via Claude Haiku with entity extraction."""
from __future__ import annotations

import json
import logging
import re

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

_PROMPT = """You are an intent classifier for FundsIndia's mutual fund WhatsApp bot.

Classify the user message into exactly ONE intent. Be STRICT — prefer specific intents over general_chat.

== INTENTS (pick ONE) ==
- greeting: Hi, hello, good morning, thanks, etc.
- goal_discovery: User mentions ANY financial goal, saving target, investment plan, retirement, education, wealth, house, wedding, emergency fund, OR is answering questions about their goal (age, amount, timeline, SIP). If conversation context shows ongoing goal collection, this is goal_discovery.
- risk_assessment: Wants to know/assess their risk profile or risk tolerance
- portfolio_query: Questions about existing portfolio, holdings, returns, NAV, "show my portfolio", "my investments", "my SIPs", "goal progress". Set entities.query_type to "summary", "sips", or "goals" based on what they ask.
- transaction_action: Wants to buy, sell, redeem, switch, start/stop/pause/step-up SIP. Set entities.action to "pause" or "stepup" for SIP changes. Set entities.fund to the fund name if mentioned.
- research_question: Wants to LEARN about financial concepts (what is SIP, explain NAV, how does ELSS work, etc.)
- stock_question: Asks about specific stocks, share prices, equity, Nifty, Sensex
- product_inquiry: Asks about specific mutual fund schemes or categories
- pdf_modification: Wants PDF report generated or modified. Trigger words: "pdf", "report", "generate", "send report", "yes" (when previous assistant message offered PDF)
- tta_request: Wants to talk to human advisor / relationship manager / expert
- general_chat: General finance conversation that doesn't fit above categories
- off_topic: Completely unrelated (weather, sports, politics, jokes)

== CRITICAL RULES ==
1. If user is answering a question about their age, child's age, income, SIP amount, or timeline — classify as goal_discovery (they are mid-flow).
2. If user says "yes" or agrees after bot offered a PDF — classify as pdf_modification.
3. If user mentions saving for retirement, education, wealth, house, car, marriage — classify as goal_discovery.
4. NEVER classify goal-related answers as general_chat. Context matters!

== CONVERSATION CONTEXT ==
{history}

== CURRENT USER MESSAGE ==
{message}

== ADDITIONAL RULES ==
5. If user asks "show my portfolio", "my investments", "how are my funds doing" — classify as portfolio_query with query_type="summary".
6. If user asks "my SIPs", "SIP details", "next SIP date" — classify as portfolio_query with query_type="sips".
7. If user asks "goal progress", "am I on track" — classify as portfolio_query with query_type="goals".
8. If user says "pause my SIP", "stop SIP" — classify as transaction_action with action="pause".
9. If user says "step up SIP", "increase SIP", "SIP badhao" — classify as transaction_action with action="stepup".

Respond with ONLY a raw JSON object. No markdown, no code fences, no explanation.
{{"intent": "<intent>", "entities": {{"topic": "<if relevant>", "query_type": "<if portfolio_query>", "action": "<if transaction_action>", "fund": "<if mentioned>"}}, "confidence": <0.0-1.0>}}"""


def _extract_json(text: str) -> dict:
    """Extract JSON from model response, handling markdown code fences."""
    text = text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()
    return json.loads(text)


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
        result = _extract_json(raw)
        if result.get("intent") not in INTENT_TYPES:
            logger.warning("Unknown intent %r from model, falling back to general_chat", result.get("intent"))
            result["intent"] = "general_chat"
        logger.info("Classified: intent=%s confidence=%.2f entities=%s (usage: in=%d out=%d)",
                     result.get("intent"), result.get("confidence", 0), result.get("entities", {}),
                     response.usage.input_tokens, response.usage.output_tokens)
        return result
    except (json.JSONDecodeError, KeyError, ValueError):
        logger.error("Failed to parse intent JSON: %r", raw)
        return {"intent": "general_chat", "entities": {}, "confidence": 0.0}
