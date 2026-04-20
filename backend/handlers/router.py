"""Intent router — dispatches classified intents to handlers."""
from __future__ import annotations

import logging

from backend.handlers.greeting import get_greeting
from backend.handlers.stock_redirect import get_stock_redirect
from backend.handlers.tta import get_tta_response
from backend.handlers.research import handle_research
from backend.services.conversation_agent import generate_response

logger = logging.getLogger("fi-chat.router")


async def route_intent(
    intent: dict,
    message: str,
    history: list[dict[str, str]],
    language: str,
    session: dict,
) -> str:
    """Route classified intent to the appropriate handler and return response text."""
    intent_type = intent.get("intent", "general_chat")

    if intent_type == "greeting":
        logger.info("Routing to GREETING handler (segment=%s)", session.get("user_segment"))
        return get_greeting(session.get("user_segment"), language)

    if intent_type == "stock_question":
        logger.info("Routing to STOCK REDIRECT handler")
        return get_stock_redirect(language)

    if intent_type == "tta_request":
        logger.info("Routing to TTA handler")
        session["handoff_state"] = "handoff_pending"
        return get_tta_response(language)

    if intent_type == "research_question":
        logger.info("Routing to RESEARCH handler (topic=%s)", intent.get("entities", {}).get("topic"))
        return await handle_research(message, history, language, intent)

    if intent_type == "off_topic":
        logger.info("Routing to OFF-TOPIC handler")
        return _off_topic_response(language)

    # goal_discovery, risk_assessment, portfolio_query, transaction_action,
    # product_inquiry, pdf_modification, general_chat
    logger.info("Routing to CONVERSATION AGENT (intent=%s)", intent_type)
    return await generate_response(
        message=message,
        history=history,
        language=language,
        intent=intent,
    )


def _off_topic_response(language: str) -> str:
    responses = {
        "en": "I'm best at helping with mutual funds and investments. Is there anything finance-related I can help you with?",
        "hi": "मैं mutual funds और investments में मदद करने में सबसे अच्छा हूँ। क्या कोई finance-related सवाल है जिसमें मैं मदद कर सकता हूँ?",
        "hinglish": "Main mutual funds aur investments mein help karne mein best hoon. Kya koi finance-related sawaal hai jismein main madad kar sakta hoon?",
    }
    return responses.get(language, responses["en"])
