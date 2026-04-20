"""FundsIndia WhatsApp AI Advisory Bot — FastAPI application."""
from __future__ import annotations

import asyncio
import logging
import time

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.services.session_store import SessionStore
from backend.services.twilio_sender import TwilioSender
from backend.services.language import detect_language
from backend.services.consent import get_disclaimer, check_consent_reply, CONSENT_VERSION
from backend.services.intent_classifier import classify_intent
from backend.handlers.router import route_intent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("fi-chat")

app = FastAPI(title="FundsIndia AI Advisory Bot", version="0.1.0")

# Mount static files for PDFs later
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# Singletons
_store = SessionStore()
_sender: TwilioSender | None = None

_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response/>'


def _ack() -> PlainTextResponse:
    return PlainTextResponse(_EMPTY_TWIML, media_type="application/xml")


def _get_sender() -> TwilioSender:
    global _sender
    if _sender is None:
        _sender = TwilioSender()
    return _sender


def _short_phone(phone: str) -> str:
    """Return last 4 digits for privacy-safe logging."""
    digits = phone.replace("whatsapp:", "").replace("+", "")
    return f"...{digits[-4:]}" if len(digits) >= 4 else phone


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@app.post("/webhook")
async def whatsapp_webhook(request: Request) -> PlainTextResponse:
    """Receive Twilio WhatsApp webhook, process async, return empty TwiML immediately."""
    form = await request.form()
    phone = form.get("From", "")
    body = (form.get("Body") or "").strip()
    button_payload = form.get("ButtonPayload")

    tag = _short_phone(phone)

    if not phone:
        logger.warning("WEBHOOK — empty From field, ignoring")
        return _ack()

    # Reject empty / media-only messages
    if not body and not button_payload:
        num_media = int(form.get("NumMedia", "0"))
        if num_media > 0:
            logger.info("[%s] WEBHOOK — media-only message (%d files), rejecting", tag, num_media)
            asyncio.create_task(
                _send_reply(phone, "I can only process text messages for now. Please send me a text!")
            )
        else:
            logger.info("[%s] WEBHOOK — empty message, ignoring", tag)
        return _ack()

    logger.info("[%s] WEBHOOK — received: %r", tag, body[:80])

    # Fire-and-forget processing
    asyncio.create_task(_process_message(phone, body))
    return _ack()


async def _process_message(phone: str, message: str) -> None:
    """Main message processing pipeline."""
    tag = _short_phone(phone)
    t_start = time.monotonic()

    try:
        session = _store.get(phone)
        is_new = session["language"] is None
        logger.info("[%s] PIPELINE START — new_session=%s consent=%s", tag, is_new, session["consent_given"])

        # 1. Detect language on first message or periodically
        if session["language"] is None:
            logger.info("[%s] LANG DETECT — calling Haiku...", tag)
            t0 = time.monotonic()
            session["language"] = await detect_language(message)
            logger.info("[%s] LANG DETECT — result=%s (%.1fs)", tag, session["language"], time.monotonic() - t0)
            _store.save(phone)

        language = session["language"]

        # 2. Consent gate
        if not session["consent_given"]:
            consent_result = check_consent_reply(message)

            if consent_result and consent_result["accepted"]:
                session["consent_given"] = True
                session["consent_version"] = CONSENT_VERSION
                session["user_segment"] = consent_result["segment"]
                _store.save(phone)
                logger.info("[%s] CONSENT — accepted, segment=%s", tag, consent_result["segment"])

                from backend.handlers.greeting import get_greeting
                greeting = get_greeting(session["user_segment"], language)
                logger.info("[%s] RESPONSE ↓↓↓\n%s", tag, greeting)
                await _send_reply(phone, greeting)
                logger.info("[%s] PIPELINE DONE — sent greeting (%.1fs total)", tag, time.monotonic() - t_start)
                return

            # Send disclaimer
            if session.get("consent_pending_since") is None:
                from datetime import datetime, timezone
                session["consent_pending_since"] = datetime.now(timezone.utc).isoformat()
                _store.save(phone)

            logger.info("[%s] CONSENT — pending, sending disclaimer", tag)
            disclaimer = get_disclaimer(language)
            logger.info("[%s] RESPONSE ↓↓↓\n%s", tag, disclaimer)
            await _send_reply(phone, disclaimer)
            logger.info("[%s] PIPELINE DONE — sent disclaimer (%.1fs total)", tag, time.monotonic() - t_start)
            return

        # 3. Save user message
        _store.add_message(phone, "user", message)
        history = _store.get_history(phone)
        logger.info("[%s] HISTORY — %d messages in context", tag, len(history))

        # 4. Classify intent
        logger.info("[%s] INTENT — classifying via Haiku...", tag)
        t0 = time.monotonic()
        intent = await classify_intent(message, history)
        session["active_intent"] = intent.get("intent")
        _store.save(phone)
        logger.info(
            "[%s] INTENT — %s (confidence=%.2f, entities=%s) (%.1fs)",
            tag, intent.get("intent"), intent.get("confidence", 0),
            intent.get("entities", {}), time.monotonic() - t0,
        )

        # 5. Route to handler
        logger.info("[%s] ROUTE — dispatching to %s handler", tag, intent.get("intent"))
        t0 = time.monotonic()
        response = await route_intent(
            intent=intent,
            message=message,
            history=history[:-1],
            language=language,
            session=session,
        )
        logger.info("[%s] ROUTE — handler returned %d chars (%.1fs)", tag, len(response), time.monotonic() - t0)
        logger.info("[%s] RESPONSE ↓↓↓\n%s", tag, response)

        # 6. Save assistant response and send
        _store.add_message(phone, "assistant", response)
        await _send_reply(phone, response)

        elapsed = time.monotonic() - t_start
        logger.info("[%s] PIPELINE DONE — total %.1fs", tag, elapsed)

    except Exception:
        logger.exception("[%s] PIPELINE ERROR", tag)
        await _send_reply(phone, "Sorry, something went wrong. Please try again.")


async def _send_reply(phone: str, text: str) -> None:
    tag = _short_phone(phone)
    try:
        logger.info("[%s] TWILIO SEND — %d chars", tag, len(text))
        sender = _get_sender()
        await sender.send_text(to=phone, text=text)
        logger.info("[%s] TWILIO SEND — delivered", tag)
    except Exception:
        logger.exception("[%s] TWILIO SEND — FAILED", tag)
