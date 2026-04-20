"""Intent router — dispatches classified intents to handlers."""
from __future__ import annotations

import logging

from backend.handlers.greeting import get_greeting
from backend.handlers.stock_redirect import get_stock_redirect
from backend.handlers.tta import get_tta_response
from backend.handlers.research import handle_research
from backend.handlers.goal_discovery import handle_goal_discovery
from backend.handlers.pdf_handler import handle_pdf_request
from backend.handlers.portfolio import handle_portfolio_query, handle_sip_action
from backend.services.conversation_agent import generate_response

logger = logging.getLogger("fi-chat.router")


def _wrap(text: str) -> dict:
    """Wrap plain text into structured response format (no buttons)."""
    return {"messages": [text], "template_name": None}


async def route_intent(
    intent: dict,
    message: str,
    history: list[dict[str, str]],
    language: str,
    session: dict,
) -> dict:
    """Route classified intent to the appropriate handler.

    Returns: {"messages": [str, ...], "template_name": str | None}
    """
    intent_type = intent.get("intent", "general_chat")

    if intent_type == "greeting":
        logger.info("Routing to GREETING handler (segment=%s)", session.get("user_segment"))
        return get_greeting(session.get("user_segment"), language, phone=session.get("phone", ""))

    if intent_type == "stock_question":
        logger.info("Routing to STOCK REDIRECT handler")
        return get_stock_redirect(language)

    if intent_type == "tta_request":
        logger.info("Routing to TTA handler")
        session["handoff_state"] = "handoff_pending"
        return get_tta_response(language)

    if intent_type == "research_question":
        logger.info("Routing to RESEARCH handler (topic=%s)", intent.get("entities", {}).get("topic"))
        text = await handle_research(message, history, language, intent)
        return _wrap(text)

    if intent_type == "pdf_modification":
        logger.info("Routing to PDF handler")
        return await handle_pdf_request(session, language)

    if intent_type in ("goal_discovery", "risk_assessment"):
        logger.info("Routing to GOAL DISCOVERY handler")
        text = await handle_goal_discovery(message, history, language, session)
        return _wrap(text)

    # Route to goal discovery if user is mid-flow (collecting params)
    # OR if a plan exists and user might be modifying it (let the handler decide)
    flow = session.get("flow_state", {})
    if flow.get("goal_collected") and not flow.get("current_plan"):
        logger.info("Routing to GOAL DISCOVERY handler (mid-flow, collecting)")
        text = await handle_goal_discovery(message, history, language, session)
        return _wrap(text)

    if intent_type == "portfolio_query":
        logger.info("Routing to PORTFOLIO handler")
        entities = intent.get("entities", {})
        query_type = entities.get("query_type", "summary")
        phone = session.get("phone", "")
        return handle_portfolio_query(phone, language, query_type)

    if intent_type == "transaction_action":
        logger.info("Routing to SIP ACTION handler")
        entities = intent.get("entities", {})
        action = entities.get("action", "")
        fund = entities.get("fund", "")
        phone = session.get("phone", "")
        if action in ("pause", "stepup"):
            return handle_sip_action(phone, language, action, fund)
        # Fall through to conversation agent for other transaction types

    if intent_type == "off_topic":
        logger.info("Routing to OFF-TOPIC handler")
        return _wrap(_off_topic_response(language))

    # product_inquiry, general_chat, unhandled transaction_action
    logger.info("Routing to CONVERSATION AGENT (intent=%s)", intent_type)
    text = await generate_response(
        message=message,
        history=history,
        language=language,
        intent=intent,
        phone=session.get("phone", ""),
    )
    return _wrap(text)


def _off_topic_response(language: str) -> str:
    responses = {
        "en": "I appreciate the chat! 😊 But I'm best at helping with *mutual funds & investments*.\n\nIs there anything finance-related I can help you with? 💰",
        "hi": "बात करने के लिए शुक्रिया! 😊 लेकिन मेरी specialty *mutual funds और investments* है।\n\nक्या कोई finance-related सवाल है? 💰",
        "hinglish": "Chat ke liye thanks! 😊 Lekin meri specialty *mutual funds aur investments* hai.\n\nKoi finance-related sawaal hai kya? 💰",
    }
    return responses.get(language, responses["en"])
