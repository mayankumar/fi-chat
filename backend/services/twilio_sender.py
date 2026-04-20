"""Send WhatsApp messages via Twilio REST API."""

import asyncio
import logging
from typing import Optional

from twilio.rest import Client

from backend.config import get_settings

logger = logging.getLogger("fi-chat.twilio")

# WhatsApp body limit
_WA_CHAR_LIMIT = 4096


class TwilioSender:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self._from = settings.twilio_whatsapp_from
        logger.info("TwilioSender initialized — from=%s", self._from)

    async def send_text(
        self, to: str, text: str, media_url: Optional[str] = None
    ) -> None:
        """Send a plain text message, optionally with a media attachment."""
        if len(text) > _WA_CHAR_LIMIT:
            logger.warning("Message too long (%d chars), truncating to %d", len(text), _WA_CHAR_LIMIT)
            text = text[: _WA_CHAR_LIMIT - 20] + "\n\n_(truncated)_"

        kwargs: dict = {"from_": self._from, "to": to, "body": text}
        if media_url:
            kwargs["media_url"] = [media_url]
            logger.info("Sending message with media: %s", media_url)

        try:
            result = await asyncio.to_thread(self._client.messages.create, **kwargs)
            logger.info("Message sent — sid=%s, status=%s", result.sid, result.status)
        except Exception:
            logger.exception("Twilio API error sending to %s", to)
            raise
