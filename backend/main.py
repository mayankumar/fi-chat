"""FundsIndia WhatsApp AI Advisory Bot — FastAPI application."""
from __future__ import annotations

import asyncio
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from backend.config import get_settings
from backend.api.dashboard import router as dashboard_router
from backend.api.voice import router as voice_router
from backend.api.actions import router as actions_router
from backend.services.session_store import get_session_store
from backend.services.twilio_sender import TwilioSender, TEMPLATE_POST_PDF
from backend.services.language import detect_language
from backend.services.consent import get_disclaimer, check_consent_reply, CONSENT_VERSION
from backend.services.intent_classifier import classify_intent
from backend.handlers.router import route_intent
from backend.handlers.tta import get_tta_followup
from backend.data.mock_users import get_user
from backend.services.handoff import create_handoff
from backend.services.agitation import check_agitation, should_trigger_tta, get_proactive_tta_message
from backend.services.session_memory import generate_session_summary, build_memory_context
from backend.services.speech import transcribe, synthesize

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("fi-chat")

app = FastAPI(title="FundsIndia AI Advisory Bot", version="0.1.0")

# CORS for dashboard (allow all origins for demo/hackathon)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dashboard + Voice + SIP Action APIs
app.include_router(dashboard_router)
app.include_router(voice_router)
app.include_router(actions_router)

# Mount static files for PDFs and media
app.mount("/static", StaticFiles(directory="backend/static"), name="static")

# Singletons
_store = get_session_store()
_sender: TwilioSender | None = None

_EMPTY_TWIML = '<?xml version="1.0" encoding="UTF-8"?><Response/>'

# Split delimiter used by Claude in responses
_SPLIT_DELIMITER = "|||"


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


@app.on_event("startup")
async def _startup_readiness_report() -> None:
    """Log which optional features are wired up so operators don't hit
    auth/URL failures at first use without warning."""
    from backend.config import config_status

    report = config_status()
    for line in report["ok"]:
        logger.info("CONFIG OK      — %s", line)
    for line in report["missing"]:
        logger.warning("CONFIG MISSING — %s", line)


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

    # Use button payload as message if present
    effective_message = button_payload or body

    # Handle media messages (voice notes, images, etc.)
    num_media = int(form.get("NumMedia", "0"))
    media_content_type = form.get("MediaContentType0", "")
    media_url_incoming = form.get("MediaUrl0", "")

    if not effective_message:
        if num_media > 0 and media_content_type.startswith("audio/"):
            # Voice message — transcribe and process
            logger.info("[%s] WEBHOOK — voice message detected (%s)", tag, media_content_type)
            asyncio.create_task(_process_voice_message(phone, media_url_incoming))
            return _ack()
        elif num_media > 0:
            logger.info("[%s] WEBHOOK — media-only message (%d files, type=%s), rejecting", tag, num_media, media_content_type)
            asyncio.create_task(
                _send_text(phone, "I can only process text and voice messages for now. Please send me a text or voice note! 📝🎤")
            )
        else:
            logger.info("[%s] WEBHOOK — empty message, ignoring", tag)
        return _ack()

    logger.info("[%s] WEBHOOK — received: %r (button=%s)", tag, body[:80], button_payload)

    # Fire-and-forget processing
    asyncio.create_task(_process_message(phone, effective_message))
    return _ack()


async def _process_message(phone: str, message: str, skip_save: bool = False) -> None:
    """Main message processing pipeline."""
    tag = _short_phone(phone)
    t_start = time.monotonic()

    try:
        session = _store.get(phone)
        is_new = session["language"] is None
        logger.info("[%s] PIPELINE START — new_session=%s consent=%s", tag, is_new, session["consent_given"])

        # 1. Detect language on first message
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
                # Auto-detect segment from mock user data
                known_user = get_user(phone)
                if known_user:
                    session["user_segment"] = known_user["segment"]
                else:
                    session["user_segment"] = consent_result["segment"]
                _store.save(phone)
                logger.info("[%s] CONSENT — accepted, segment=%s (known=%s)", tag, session["user_segment"], known_user is not None)

                from backend.handlers.greeting import get_greeting
                reply = get_greeting(session["user_segment"], language, phone=phone)
                await _send_structured(phone, reply)
                logger.info("[%s] PIPELINE DONE — sent greeting (%.1fs total)", tag, time.monotonic() - t_start)
                return

            # Send disclaimer
            if session.get("consent_pending_since") is None:
                from datetime import datetime, timezone
                session["consent_pending_since"] = datetime.now(timezone.utc).isoformat()
                _store.save(phone)

            logger.info("[%s] CONSENT — pending, sending disclaimer", tag)
            reply = get_disclaimer(language)
            await _send_structured(phone, reply)
            logger.info("[%s] PIPELINE DONE — sent disclaimer (%.1fs total)", tag, time.monotonic() - t_start)
            return

        # 2b. Check for TTA sub-selections (call/callback/email after TTA menu)
        if session.get("handoff_state") == "handoff_pending":
            tta_followup = get_tta_followup(message.strip().lower(), language)
            if tta_followup:
                session["handoff_state"] = "bot_active"
                _store.save(phone)
                logger.info("[%s] TTA FOLLOWUP — %s", tag, message.strip()[:30])
                await _send_text(phone, tta_followup)
                logger.info("[%s] PIPELINE DONE — TTA followup (%.1fs total)", tag, time.monotonic() - t_start)
                return

        # 2c. Map button payloads to natural language
        _BUTTON_MAP = {
            "action_goals": "I want to plan my financial goals",
            "action_learn": "I want to learn about mutual funds and investing",
            "action_advisor": "I want to talk to an advisor",
            "action_modify_plan": "I want to modify my investment plan",
            "action_plan_ok": "The plan looks good, thank you!",
            "action_portfolio": "Show me my portfolio summary",
            "action_stepup": "I want to step up my SIP",
            "action_restart_sip": "I want to restart my paused SIPs",
            "goal_retirement": "I want to plan for my retirement",
            "goal_education": "I want to plan for my child's education",
            "goal_consumption": "I want to save for a house, car, or big purchase",
            "goal_wealth": "I want to grow my wealth over the long term",
        }
        if message in _BUTTON_MAP:
            message = _BUTTON_MAP[message]
            logger.info("[%s] BUTTON MAPPED — %s", tag, message)

        # 3. Save user message (skip if already saved by voice pipeline)
        if not skip_save:
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
        reply = await route_intent(
            intent=intent,
            message=message,
            history=history[:-1],
            language=language,
            session=session,
        )
        logger.info("[%s] ROUTE — handler returned (%.1fs)", tag, time.monotonic() - t0)

        # 6. Process response: split Claude messages on ||| and send
        messages = _extract_messages(reply)
        template_name = reply.get("template_name") if isinstance(reply, dict) else None
        media_url = reply.get("media_url") if isinstance(reply, dict) else None
        pdf_text = reply.get("pdf_text") if isinstance(reply, dict) else None
        cta_text = reply.get("cta_text") if isinstance(reply, dict) else None

        # Log all response blocks
        for i, msg in enumerate(messages):
            logger.info("[%s] RESPONSE [%d/%d] ↓↓↓\n%s", tag, i + 1, len(messages), msg)

        # Save full response to history (joined), include media_url if present
        full_response = "\n\n".join(messages)
        _store.add_message(phone, "assistant", full_response, media_url=media_url)

        sender = _get_sender()

        # Goal-plan flow: plan summary → PDF attachment → action CTA.
        if pdf_text and media_url and cta_text:
            await sender.send_multi(to=phone, messages=messages, template_name=None)
            await asyncio.sleep(1.0)
            await sender.send_text(to=phone, text=pdf_text, media_url=media_url)
            await asyncio.sleep(1.2)
            await sender.send_with_buttons(to=phone, body=cta_text, template_name=template_name)
            logger.info("[%s] PLAN+PDF+CTA sent", tag)
        elif media_url:
            # Legacy PDF-request flow: single text + media, then TTA nudge.
            await sender.send_text(to=phone, text=messages[0], media_url=media_url)
            await asyncio.sleep(1.5)
            nudge = _post_pdf_nudge(language)
            await sender.send_with_buttons(to=phone, body=nudge, template_name=TEMPLATE_POST_PDF)
            logger.info("[%s] POST-PDF TTA NUDGE sent (with buttons)", tag)
        else:
            await sender.send_multi(to=phone, messages=messages, template_name=template_name)

        # 7. Agitation detection (every 3 user messages)
        agitation = await check_agitation(session.get("messages", []))
        if should_trigger_tta(agitation):
            logger.info("[%s] AGITATION TRIGGERED — score=%d, reason=%s",
                       tag, agitation["score"], agitation["reason"][:50])
            session["handoff_state"] = "handoff_pending"
            _store.save(phone)
            create_handoff(phone, session, reason="agitation_detected", urgency="high")
            tta_msg = get_proactive_tta_message(language)
            await asyncio.sleep(1.0)
            await _send_text(phone, tta_msg)

        # 8. Create handoff record on TTA intent
        if intent.get("intent") == "tta_request":
            create_handoff(phone, session, reason="user_requested", urgency="normal")

        elapsed = time.monotonic() - t_start
        logger.info("[%s] PIPELINE DONE — %d blocks sent, total %.1fs", tag, len(messages), elapsed)

    except Exception:
        logger.exception("[%s] PIPELINE ERROR", tag)
        await _send_text(phone, "Sorry, something went wrong. Please try again 🙏")


async def _process_voice_message(phone: str, audio_url: str) -> None:
    """Process a voice message: download → transcribe → pipeline → TTS reply.

    Flow:
      1. Download audio from Twilio, save MP3 locally
      2. Transcribe via Whisper
      3. Save user message (transcript + audio_url + media_type=voice)
      4. Run normal text pipeline → bot sends text reply
      5. Synthesize bot's reply to audio via TTS
      6. Send voice reply as follow-up message
      7. Tag assistant message with audio_url for dashboard playback
    """
    tag = _short_phone(phone)
    t_start = time.monotonic()

    try:
        settings = get_settings()

        if not settings.openai_api_key:
            logger.warning("[%s] VOICE — OpenAI key not set, cannot transcribe", tag)
            await _send_text(phone, "Voice messages are not configured yet. Please send a text message! 📝")
            return

        # 1. Download + transcribe audio (also saves incoming audio to static/audio/)
        logger.info("[%s] VOICE — transcribing audio...", tag)
        t0 = time.monotonic()
        result = await transcribe(
            audio_url,
            twilio_auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        )
        transcript = result["transcript"]
        incoming_audio_url = result["audio_url"]
        logger.info("[%s] VOICE — transcript: %r, audio saved: %s (%.1fs)",
                     tag, transcript[:80] if transcript else "", incoming_audio_url, time.monotonic() - t0)

        if not transcript:
            await _send_text(phone, "I couldn't understand that voice message. Could you try again or send a text? 🎤")
            return

        # 2. Save user message with transcript + voice audio file
        _store.add_message(phone, "user", transcript,
                           media_url=incoming_audio_url, media_type="voice")

        # 3. Check consent — if pending, just run text pipeline (no TTS for disclaimer)
        session = _store.get(phone)
        if not session["consent_given"]:
            await _process_message(phone, transcript, skip_save=True)
            logger.info("[%s] VOICE — consent pending, skipping TTS", tag)
            return

        # 4. Count messages BEFORE running pipeline (to find the NEW assistant reply after)
        msg_count_before = len(session.get("messages", []))

        # 5. Run normal text pipeline — this classifies intent, routes, sends text reply
        await _process_message(phone, transcript, skip_save=True)

        # 6. Find the NEW assistant message(s) added by the pipeline
        all_messages = session.get("messages", [])
        new_messages = [m for m in all_messages[msg_count_before:]
                        if m["role"] == "assistant"]

        if not new_messages:
            logger.warning("[%s] VOICE — no new assistant message after pipeline, skipping TTS", tag)
            elapsed = time.monotonic() - t_start
            logger.info("[%s] VOICE PIPELINE DONE — total %.1fs (no TTS)", tag, elapsed)
            return

        # 7. Synthesize the NEW response as voice
        if settings.voice_replies_enabled:
            latest_reply = new_messages[-1]
            tts_text = latest_reply["content"]
            # Clean markdown formatting for natural speech
            tts_text = tts_text.replace("*", "").replace("_", "").replace("|||", ". ")

            logger.info("[%s] VOICE — synthesizing TTS for: %r", tag, tts_text[:80])
            t0 = time.monotonic()
            reply_audio_url = await synthesize(tts_text)

            if reply_audio_url:
                logger.info("[%s] VOICE — TTS done (%.1fs), sending audio", tag, time.monotonic() - t0)
                sender = _get_sender()
                await sender.send_text(to=phone, text="🎧 *Voice reply:*", media_url=reply_audio_url)

                # Tag the assistant message with audio URL (for dashboard playback)
                latest_reply["audio_url"] = reply_audio_url
                latest_reply["media_type"] = "voice"
                _store.save(phone)
            else:
                logger.warning("[%s] VOICE — TTS synthesis failed, text-only reply sent", tag)

        elapsed = time.monotonic() - t_start
        logger.info("[%s] VOICE PIPELINE DONE — total %.1fs", tag, elapsed)

    except Exception:
        logger.exception("[%s] VOICE PIPELINE ERROR", tag)
        await _send_text(phone, "Sorry, I had trouble processing your voice message. Please try again 🙏")


def _extract_messages(reply) -> list:
    """Extract message list from handler response. Handles structured dict or plain text."""
    if isinstance(reply, dict):
        messages = reply.get("messages", [])
    elif isinstance(reply, str):
        messages = [reply]
    else:
        messages = [str(reply)]

    # Split any message blocks on ||| delimiter (Claude uses this)
    expanded = []
    for msg in messages:
        parts = [p.strip() for p in msg.split(_SPLIT_DELIMITER) if p.strip()]
        expanded.extend(parts)

    return expanded if expanded else ["I'm here to help! How can I assist you? 😊"]


def _post_pdf_nudge(language: str) -> str:
    """Post-PDF delivery TTA nudge message."""
    nudges = {
        "en": (
            "💡 *Pro tip:* Our expert advisors can review this plan with you, "
            "answer questions, and help you start investing right away!\n\n"
            "Say *\"talk to advisor\"* to connect 🧑‍💼"
        ),
        "hi": (
            "💡 *Pro tip:* Humare expert advisors is plan ko aapke saath review kar sakte hain, "
            "questions ka jawab de sakte hain, aur turant invest karna shuru kar sakte hain!\n\n"
            "Bol dijiye *\"advisor se baat karo\"* 🧑‍💼"
        ),
        "hinglish": (
            "💡 *Pro tip:* Humare expert advisors is plan ko review kar sakte hain, "
            "aapke questions answer kar sakte hain, aur help kar sakte hain start karne mein!\n\n"
            "Bol do *\"talk to advisor\"* 🧑‍💼"
        ),
    }
    return nudges.get(language, nudges["en"])


async def _send_structured(phone: str, reply: dict) -> None:
    """Send a structured response (messages + optional quick-reply buttons)."""
    tag = _short_phone(phone)
    messages = reply.get("messages", [])
    template_name = reply.get("template_name")

    for i, msg in enumerate(messages):
        logger.info("[%s] RESPONSE [%d/%d] ↓↓↓\n%s", tag, i + 1, len(messages), msg)

    try:
        sender = _get_sender()
        await sender.send_multi(to=phone, messages=messages, template_name=template_name)
        logger.info("[%s] TWILIO SEND — %d blocks delivered (template=%s)",
                    tag, len(messages), template_name)
    except Exception:
        logger.exception("[%s] TWILIO SEND — FAILED", tag)


async def _send_text(phone: str, text: str) -> None:
    """Send a single plain text message."""
    tag = _short_phone(phone)
    try:
        logger.info("[%s] TWILIO SEND — %d chars", tag, len(text))
        sender = _get_sender()
        await sender.send_text(to=phone, text=text)
        logger.info("[%s] TWILIO SEND — delivered", tag)
    except Exception:
        logger.exception("[%s] TWILIO SEND — FAILED", tag)
