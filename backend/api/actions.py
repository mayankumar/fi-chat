"""SIP Action Token API — generates secure single-use links for SIP operations.

Flow:
  1. WhatsApp bot (or RM) calls POST /api/actions/generate to get a token
  2. Token URL is sent to user via WhatsApp: {MEDIA_BASE_URL}/action/{token}
     (The Next.js dashboard at /action/[token] handles the UI)
  3. User opens link, sees action details, confirms
  4. Frontend calls POST /api/actions/{token}/confirm
  5. Backend marks token as used and notifies via WhatsApp
"""
from __future__ import annotations

import logging
import secrets
import time
from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import get_settings
from backend.data.mock_users import get_user, get_sips, get_portfolio, fmt_amount

logger = logging.getLogger("fi-chat.actions")

router = APIRouter(prefix="/api/actions", tags=["actions"])

ActionType = Literal["step_up", "buy_sip", "pause_sip", "download_report"]


def create_action_token(
    phone: str,
    action: ActionType,
    fund_name: str | None = None,
    current_amount: int | None = None,
    suggested_amount: int | None = None,
    note: str | None = None,
) -> str:
    """Generate a token and return the full action URL. Call this directly from handlers."""
    purge_expired()
    from backend.data.mock_users import get_user as _get_user
    user = _get_user(phone)
    token = secrets.token_urlsafe(24)
    _tokens[token] = {
        "token": token,
        "phone": phone,
        "action": action,
        "fund_name": fund_name,
        "current_amount": current_amount,
        "suggested_amount": suggested_amount,
        "note": note,
        "user_name": user["name"] if user else "Customer",
        "status": "pending",
        "created_at": time.time(),
        "expires_at": time.time() + TOKEN_TTL_SECONDS,
    }
    settings = get_settings()
    base = (settings.dashboard_base_url or "http://localhost:3000").rstrip("/")
    url = f"{base}/action/{token}"
    logger.info("Action token created internally: %s action=%s", token[:8], action)
    return url

# In-memory token store: {token -> action_data}
# In production this would be Redis with TTL
_tokens: dict[str, dict] = {}

TOKEN_TTL_SECONDS = 86400  # 24 hours


def _is_expired(data: dict) -> bool:
    return time.time() > data["expires_at"]


def purge_expired() -> None:
    expired = [t for t, d in _tokens.items() if _is_expired(d)]
    for t in expired:
        del _tokens[t]


# ── POST /api/actions/generate ───────────────────────────────────────

class GenerateActionRequest(BaseModel):
    phone: str                                   # whatsapp:+91XXXXXXXXXX
    action: ActionType
    fund_name: Optional[str] = None              # for step_up / buy_sip / pause_sip
    current_amount: Optional[int] = None         # current monthly SIP (for step_up)
    suggested_amount: Optional[int] = None       # new amount (for step_up / buy_sip)
    note: Optional[str] = None                   # optional human-readable context


@router.post("/generate")
async def generate_action(body: GenerateActionRequest):
    """Generate a one-time action token for a SIP operation."""
    purge_expired()

    user = get_user(body.phone)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = secrets.token_urlsafe(24)

    action_data: dict = {
        "token": token,
        "phone": body.phone,
        "action": body.action,
        "fund_name": body.fund_name,
        "current_amount": body.current_amount,
        "suggested_amount": body.suggested_amount,
        "note": body.note,
        "user_name": user["name"],
        "status": "pending",      # pending | confirmed | expired
        "created_at": time.time(),
        "expires_at": time.time() + TOKEN_TTL_SECONDS,
    }
    _tokens[token] = action_data

    settings = get_settings()
    base = settings.media_base_url.rstrip("/") if settings.media_base_url else "http://localhost:3000"
    action_url = f"{base}/action/{token}"

    logger.info("Action token generated: %s action=%s phone=%s", token[:8], body.action, body.phone)
    return {"token": token, "url": action_url, "expires_in_hours": 24}


# ── GET /api/actions/{token} ─────────────────────────────────────────

@router.get("/{token}")
async def get_action(token: str):
    """Fetch action details for rendering the landing page."""
    purge_expired()

    data = _tokens.get(token)
    if not data:
        raise HTTPException(status_code=404, detail="Action link not found or expired")
    if _is_expired(data):
        data["status"] = "expired"
        raise HTTPException(status_code=410, detail="Action link has expired")

    phone = data["phone"]
    sips = get_sips(phone) or []
    portfolio = get_portfolio(phone)

    enriched = {**data}
    enriched["sips"] = sips
    enriched["portfolio_value"] = fmt_amount(portfolio["current_value"]) if portfolio else None
    enriched["portfolio_xirr"] = portfolio["xirr"] if portfolio else None

    return enriched


# ── POST /api/actions/{token}/confirm ────────────────────────────────

@router.post("/{token}/confirm")
async def confirm_action(token: str):
    """Mark action as confirmed. Called by the landing page after user taps Confirm."""
    purge_expired()

    data = _tokens.get(token)
    if not data:
        raise HTTPException(status_code=404, detail="Action link not found or expired")
    if _is_expired(data):
        raise HTTPException(status_code=410, detail="Action link has expired")
    if data["status"] == "confirmed":
        raise HTTPException(status_code=409, detail="Action already confirmed")

    data["status"] = "confirmed"
    data["confirmed_at"] = time.time()
    logger.info("Action confirmed: %s action=%s phone=%s", token[:8], data["action"], data["phone"])

    # Build confirmation message for WhatsApp
    action_labels = {
        "step_up": "SIP Step-Up",
        "buy_sip": "New SIP",
        "pause_sip": "SIP Pause",
        "download_report": "Report Download",
    }
    label = action_labels.get(data["action"], data["action"])
    fund = data.get("fund_name", "")
    amount_str = ""
    if data.get("suggested_amount"):
        amount_str = f" of ₹{data['suggested_amount']:,}/month"

    confirmation_msg = (
        f"✅ *{label} Request Received*\n\n"
        f"Fund: {fund}\n"
        f"{('Amount: ' + amount_str.strip() + chr(10)) if amount_str else ''}"
        f"Our team will process this within 1 business day.\n\n"
        f"You'll receive a confirmation SMS once done. 🙏"
    )

    # Attempt WhatsApp confirmation (best-effort)
    try:
        from backend.services.twilio_sender import TwilioSender
        sender = TwilioSender()
        to = data["phone"] if data["phone"].startswith("whatsapp:") else f"whatsapp:{data['phone']}"
        await sender.send_text(to=to, text=confirmation_msg)
    except Exception as exc:
        logger.warning("Could not send WhatsApp confirmation: %s", exc)

    return {"status": "confirmed", "action": data["action"]}
