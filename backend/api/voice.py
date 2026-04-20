"""Twilio Voice API — browser-based calling for RM dashboard.

Flow:
  1. RM clicks "Call" → frontend fetches access token from /api/voice/token
  2. Frontend initializes Twilio Device with token
  3. RM clicks call → Device.connect({To: customerPhone})
  4. Twilio hits our /api/voice/twiml webhook → returns <Dial> to customer
  5. Customer's phone rings, RM talks from browser
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import Response
from twilio.jwt.access_token import AccessToken
from twilio.jwt.access_token.grants import VoiceGrant
from twilio.twiml.voice_response import VoiceResponse

from backend.config import get_settings

logger = logging.getLogger("fi-chat.voice")

router = APIRouter(prefix="/api/voice", tags=["voice"])

_RM_IDENTITY = "fundsindia-rm"


@router.get("/token")
async def get_voice_token():
    """Generate a Twilio Access Token with Voice Grant for the RM browser client."""
    settings = get_settings()

    if not settings.twilio_api_key_sid or not settings.twilio_api_key_secret:
        return {"error": "Voice not configured. Set TWILIO_API_KEY_SID and TWILIO_API_KEY_SECRET in .env"}

    token = AccessToken(
        settings.twilio_account_sid,
        settings.twilio_api_key_sid,
        settings.twilio_api_key_secret,
        identity=_RM_IDENTITY,
    )

    voice_grant = VoiceGrant(
        outgoing_application_sid=settings.twilio_twiml_app_sid,
        incoming_allow=False,
    )
    token.add_grant(voice_grant)

    jwt = token.to_jwt()
    logger.info("Voice token generated for identity=%s", _RM_IDENTITY)
    return {"token": jwt, "identity": _RM_IDENTITY}


@router.post("/twiml")
async def voice_twiml(request: Request):
    """TwiML webhook — Twilio calls this when the browser client initiates a call.

    Returns TwiML that dials the customer's phone number.
    """
    form = await request.form()
    to = form.get("To", "")

    # Debug: log all form fields to identify what Twilio sends
    all_fields = {k: v for k, v in form.items()}
    logger.info("Voice TwiML — ALL FORM FIELDS: %s", all_fields)
    logger.info("Voice TwiML request — dialing %s", to)

    response = VoiceResponse()

    if to:
        # Dial the customer's phone — use Twilio number as caller ID
        settings = get_settings()
        # Use the Twilio WhatsApp number (strip whatsapp: prefix) or a dedicated voice number
        caller_id = settings.twilio_whatsapp_from.replace("whatsapp:", "")
        logger.info("Voice TwiML — caller_id=%s, To=%s", caller_id, to)
        dial = response.dial(caller_id=caller_id)
        dial.number(to)
    else:
        response.say("No phone number provided.", voice="alice")

    return Response(content=str(response), media_type="application/xml")
