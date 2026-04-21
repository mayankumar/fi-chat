"""
Twilio message sender with WhatsApp quick-reply button support.

Uses Twilio Content API for interactive quick-reply buttons:
  - Each unique button set is a separate Content template
  - Templates created once on first use, SIDs cached globally
  - Template body is `{{1}}` — actual text injected at send time
  - Fallback to plain text if Content API unavailable
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client
from twilio.rest.content.v1.content import ContentList

from backend.config import get_settings

logger = logging.getLogger("fi-chat.twilio")

_WA_CHAR_LIMIT = 4096
_BODY_CHAR_LIMIT = 1024  # Content API body variable limit
_INTER_MESSAGE_DELAY = 0.8  # seconds between multi-message sends

# Global template cache: friendly_name -> content_sid (or "" if unavailable)
_template_cache: dict = {}


# ── Pre-defined button templates ──────────────────────────────────────
# Each template has a unique friendly_name and a set of quick-reply buttons.
# Templates are created once in Twilio and reused forever.

TEMPLATE_CONSENT = "fi_consent_v1"
TEMPLATE_GREETING_MENU = "fi_greeting_menu_v1"
TEMPLATE_EXISTING_MENU = "fi_existing_menu_v1"
TEMPLATE_DORMANT_MENU = "fi_dormant_menu_v1"
TEMPLATE_STOCK_REDIRECT = "fi_stock_redirect_v1"
TEMPLATE_TTA = "fi_tta_options_v1"
TEMPLATE_POST_PDF = "fi_post_pdf_v1"
TEMPLATE_PLAN_CTA = "fi_plan_cta_v1"

_TEMPLATE_DEFINITIONS = {
    TEMPLATE_CONSENT: [
        {"title": "✅ Let's Start!", "id": "consent_yes"},
        {"title": "🔬 I'm a Pro", "id": "consent_expert"},
    ],
    TEMPLATE_GREETING_MENU: [
        {"title": "🎯 Plan My Goals", "id": "action_goals"},
        {"title": "📚 Learn Investing", "id": "action_learn"},
        {"title": "💬 Talk to Advisor", "id": "action_advisor"},
    ],
    TEMPLATE_EXISTING_MENU: [
        {"title": "📊 My Portfolio", "id": "action_portfolio"},
        {"title": "📈 Step-up SIP", "id": "action_stepup"},
        {"title": "💬 Talk to Advisor", "id": "action_advisor"},
    ],
    TEMPLATE_DORMANT_MENU: [
        {"title": "▶️ Restart SIPs", "id": "action_restart_sip"},
        {"title": "📊 My Portfolio", "id": "action_portfolio"},
        {"title": "💬 Talk to Advisor", "id": "action_advisor"},
    ],
    TEMPLATE_STOCK_REDIRECT: [
        {"title": "🎯 Explore MF Instead", "id": "action_goals"},
        {"title": "💬 Talk to Advisor", "id": "action_advisor"},
    ],
    TEMPLATE_TTA: [
        {"title": "📞 Call Us Now", "id": "tta_call"},
        {"title": "🔙 Request Callback", "id": "tta_callback"},
        {"title": "✉️ Send Email", "id": "tta_email"},
    ],
    TEMPLATE_POST_PDF: [
        {"title": "💬 Talk to Advisor", "id": "action_advisor"},
        {"title": "🔄 Modify Plan", "id": "action_modify_plan"},
        {"title": "✅ Looks Good!", "id": "action_plan_ok"},
    ],
    TEMPLATE_PLAN_CTA: [
        {"title": "💬 Talk to Advisor", "id": "action_advisor"},
    ],
}


class TwilioSender:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        self._from = settings.twilio_whatsapp_from
        logger.info("TwilioSender initialized — from=%s", self._from)

    # ── Public API ────────────────────────────────────────────────────

    async def send_text(
        self, to: str, text: str, media_url: Optional[str] = None
    ) -> None:
        """Send a plain text message, optionally with a media attachment."""
        if len(text) > _WA_CHAR_LIMIT:
            logger.warning("Message too long (%d chars), truncating", len(text))
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

    async def send_with_buttons(
        self, to: str, body: str, template_name: str
    ) -> None:
        """Send a message with quick-reply buttons using a pre-defined Content API template.

        template_name: one of TEMPLATE_CONSENT, TEMPLATE_GREETING_MENU, etc.
        """
        body = body[:_BODY_CHAR_LIMIT]
        sid = await self._resolve_content_sid(template_name)

        if sid:
            try:
                result = await asyncio.to_thread(
                    self._client.messages.create,
                    **{
                        "from_": self._from,
                        "to": to,
                        "content_sid": sid,
                        "content_variables": json.dumps({"1": body}),
                    },
                )
                logger.info("Button message sent — sid=%s, template=%s", result.sid, template_name)
                return
            except TwilioRestException as exc:
                logger.warning("Content API send failed (%s) — falling back to text", exc.msg)

        # Fallback: plain text with button hints
        buttons = _TEMPLATE_DEFINITIONS.get(template_name, [])
        footer = "\n\n" + "\n".join(
            "👉 Reply *{}*".format(b["title"]) for b in buttons
        )
        await self.send_text(to, body + footer)

    async def send_multi(
        self, to: str, messages: list, template_name: str = None
    ) -> None:
        """Send multiple message blocks. Mode controlled by settings.message_mode.

        - "split": separate messages with delay, buttons on last (demo mode)
        - "compact": all blocks joined into one message (saves Twilio quota)
        """
        if not messages:
            return

        settings = get_settings()

        if settings.message_mode == "compact":
            # Join all blocks into one message
            combined = "\n\n".join(messages)
            if template_name:
                await self.send_with_buttons(to, combined, template_name)
            else:
                await self.send_text(to, combined)
            return

        # Split mode: send each block separately
        for msg in messages[:-1]:
            await self.send_text(to, msg)
            await asyncio.sleep(_INTER_MESSAGE_DELAY)

        # Last message: with buttons if template specified
        last = messages[-1]
        if template_name:
            await self.send_with_buttons(to, last, template_name)
        else:
            await self.send_text(to, last)

    # ── Content API template management ───────────────────────────────

    async def _resolve_content_sid(self, template_name: str) -> Optional[str]:
        """Return the Content SID for a template, creating it if needed. Cached globally."""
        global _template_cache

        if template_name in _template_cache:
            cached = _template_cache[template_name]
            return cached or None  # "" means known-unavailable

        try:
            sid = await asyncio.to_thread(self._get_or_create_template, template_name)
            _template_cache[template_name] = sid
            logger.info("Content SID resolved: %s -> %s", template_name, sid)
        except Exception as exc:
            logger.error("Content template setup failed for %s — buttons unavailable: %s",
                        template_name, exc)
            _template_cache[template_name] = ""  # mark unavailable, don't retry

        return _template_cache.get(template_name) or None

    def _get_or_create_template(self, template_name: str) -> str:
        """Synchronous: find or create a Content API template. Returns content SID."""
        buttons = _TEMPLATE_DEFINITIONS.get(template_name)
        if not buttons:
            raise ValueError(f"Unknown template: {template_name}")

        # Check if template already exists
        for content in self._client.content.v1.contents.list():
            if content.friendly_name == template_name:
                logger.info("Reusing existing Content template: %s (%s)", template_name, content.sid)
                return content.sid

        # Create new template using SDK typed objects (same pattern as POC)
        actions = [
            ContentList.QuickReplyAction({"title": b["title"], "id": b["id"]})
            for b in buttons
        ]

        request = ContentList.ContentCreateRequest({
            "friendly_name": template_name,
            "language": "en",
            "types": ContentList.Types({
                "twilio/quick-reply": ContentList.TwilioQuickReply({
                    "body": "{{1}}",
                    "actions": actions,
                })
            }),
        })

        content = self._client.content.v1.contents.create(request)
        logger.info("Created Content template: %s (%s)", template_name, content.sid)
        return content.sid
