"""RM Dashboard APIs — user list, chat transcript, AI summary, send message, handoffs."""
from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path
from typing import Optional

import anthropic
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from backend.config import get_settings
from backend.services.session_store import get_session_store
from backend.services.twilio_sender import TwilioSender
from backend.services.handoff import get_all_handoffs, get_handoff, resolve_handoff, generate_handoff_brief
from backend.data.mock_users import get_user

logger = logging.getLogger("fi-chat.dashboard")

router = APIRouter(prefix="/api", tags=["dashboard"])

_store = get_session_store()
_sender: Optional[TwilioSender] = None


def _get_sender() -> TwilioSender:
    global _sender
    if _sender is None:
        _sender = TwilioSender()
    return _sender


def _short_phone(phone: str) -> str:
    return phone.replace("whatsapp:", "").replace("+", "")


# ── GET /api/users — list all users ─────────────────────────────────

@router.get("/users")
async def list_users():
    """Return all users with key info for the dashboard list view."""
    sessions = _store.get_all()
    users = []
    for phone, session in sessions.items():
        messages = session.get("messages", [])
        last_msg = messages[-1] if messages else None

        # Check for known user data
        known_user = get_user(phone)
        handoff = get_handoff(phone)

        users.append({
            "phone": phone,
            "phone_display": _short_phone(phone),
            "name": known_user["name"] if known_user else None,
            "language": session.get("language", "en"),
            "user_segment": session.get("user_segment"),
            "consent_given": session.get("consent_given", False),
            "active_intent": session.get("active_intent"),
            "handoff_state": session.get("handoff_state", "bot_active"),
            "is_tta": session.get("handoff_state") == "handoff_pending",
            "handoff_reason": handoff["reason"] if handoff else None,
            "handoff_urgency": handoff["urgency"] if handoff else None,
            "message_count": len(messages),
            "last_message": {
                "role": last_msg["role"],
                "content": last_msg["content"][:150],
                "timestamp": last_msg.get("timestamp", ""),
            } if last_msg else None,
            "has_plan": bool(session.get("flow_state", {}).get("current_plan")),
            "created_at": session.get("created_at", ""),
            "updated_at": session.get("updated_at", ""),
        })

    # Sort: TTA pending first, then by updated_at descending
    users.sort(key=lambda u: (not u["is_tta"], u.get("updated_at", "")), reverse=False)
    users.sort(key=lambda u: u["is_tta"], reverse=True)

    return {"users": users, "total": len(users)}


# ── GET /api/users/{phone}/chat — full transcript ───────────────────

@router.get("/users/{phone}/chat")
async def get_chat(phone: str):
    """Return full conversation transcript for a user."""
    # Try with and without whatsapp: prefix
    session = _store.get_existing(phone)
    if not session:
        session = _store.get_existing(f"whatsapp:+{phone}")
    if not session:
        raise HTTPException(status_code=404, detail="User not found")

    messages = session.get("messages", [])
    return {
        "phone": phone,
        "language": session.get("language", "en"),
        "message_count": len(messages),
        "messages": messages,
    }


# ── GET /api/users/{phone}/summary — AI summary + talking points ────

@router.get("/users/{phone}/summary")
async def get_summary(phone: str):
    """Generate AI summary of conversation with talking points for RM."""
    session = _store.get_existing(phone)
    if not session:
        session = _store.get_existing(f"whatsapp:+{phone}")
    if not session:
        raise HTTPException(status_code=404, detail="User not found")

    messages = session.get("messages", [])
    if not messages:
        return {
            "summary": "No conversation yet.",
            "talking_points": [],
            "goal_info": None,
        }

    # Build conversation text for Sonnet
    conv_text = "\n".join(
        f"{m['role'].upper()}: {m['content'][:300]}" for m in messages[-20:]
    )

    # Goal info from session
    flow = session.get("flow_state", {})
    goal_collected = flow.get("goal_collected", {})
    current_plan = flow.get("current_plan")

    goal_context = ""
    if goal_collected:
        goal_context = f"\nCollected goal parameters: {goal_collected}"
    if current_plan:
        goal_context += (
            f"\nPlan generated: {current_plan.get('goal_name')}, "
            f"SIP ₹{current_plan.get('sip_required', 0):,}/mo, "
            f"tenure {current_plan.get('tenure_years')}yr, "
            f"risk {current_plan.get('risk_label')}"
        )

    prompt = f"""You are an AI assistant helping a Relationship Manager (RM) at FundsIndia prepare for a call with a customer.

Read this WhatsApp conversation and provide:
1. A brief summary (2-3 sentences) of what the customer wants
2. 3-5 specific talking points the RM should bring up during the call
3. The customer's mood/sentiment (positive, neutral, frustrated)

CONVERSATION:
{conv_text}
{goal_context}

Customer language: {session.get('language', 'en')}
Handoff state: {session.get('handoff_state', 'bot_active')}

Respond in JSON format (no markdown):
{{"summary": "...", "talking_points": ["...", "..."], "sentiment": "positive|neutral|frustrated"}}"""

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        response = await client.messages.create(
            model=settings.haiku_model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip code fences
        import re
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            raw = raw.strip()

        import json
        result = json.loads(raw)
    except Exception as exc:
        logger.exception("AI summary generation failed: %s", exc)
        result = {
            "summary": "Unable to generate summary. Please review the transcript.",
            "talking_points": [],
            "sentiment": "neutral",
        }

    # Add goal info
    result["goal_info"] = {
        "collected": goal_collected,
        "plan_generated": current_plan is not None,
        "plan_summary": {
            "goal_name": current_plan.get("goal_name"),
            "sip_required": current_plan.get("sip_required"),
            "tenure_years": current_plan.get("tenure_years"),
            "risk_label": current_plan.get("risk_label"),
            "future_value": current_plan.get("future_value"),
        } if current_plan else None,
    }

    return result


# ── POST /api/users/{phone}/send — RM sends message ─────────────────

class SendMessageRequest(BaseModel):
    message: str


@router.post("/users/{phone}/send")
async def send_message(phone: str, body: SendMessageRequest):
    """RM sends a WhatsApp message to the user via Twilio."""
    session = _store.get_existing(phone)
    if not session:
        session = _store.get_existing(f"whatsapp:+{phone}")
        if session:
            phone = f"whatsapp:+{phone}"
    if not session:
        raise HTTPException(status_code=404, detail="User not found")

    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    try:
        sender = _get_sender()
        # Ensure whatsapp: prefix
        to = phone if phone.startswith("whatsapp:") else f"whatsapp:+{phone}"
        await sender.send_text(to=to, text=body.message.strip())

        # Save to conversation history
        _store.add_message(phone, "assistant", f"[RM] {body.message.strip()}")

        logger.info("RM message sent to %s: %s", _short_phone(phone), body.message[:50])
        return {"status": "sent", "to": _short_phone(phone)}
    except Exception as exc:
        logger.exception("Failed to send RM message: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── POST /api/users/{phone}/send-file — RM sends file/attachment ─────

_UPLOADS_DIR = Path("backend/static/uploads")
_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

_ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".doc", ".docx", ".xls", ".xlsx", ".csv"}
_MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB (Twilio limit)


@router.post("/users/{phone}/send-file")
async def send_file(
    phone: str,
    file: UploadFile = File(...),
    caption: str = Form(default=""),
):
    """RM sends a file/attachment to the user via Twilio WhatsApp.

    Supported: PDF, images (PNG/JPG/GIF), Office docs, CSV.
    File is uploaded to static/uploads/ and sent as media_url.
    """
    session = _store.get_existing(phone)
    if not session:
        session = _store.get_existing(f"whatsapp:+{phone}")
        if session:
            phone = f"whatsapp:+{phone}"
    if not session:
        raise HTTPException(status_code=404, detail="User not found")

    # Validate file extension
    filename = file.filename or "attachment"
    ext = Path(filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type {ext} not supported. Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    # Read and validate size
    content = await file.read()
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum 16MB.")

    # Save to static uploads directory with unique name
    unique_name = f"{uuid.uuid4().hex[:12]}_{filename}"
    file_path = _UPLOADS_DIR / unique_name
    file_path.write_bytes(content)

    # Build public URL
    settings = get_settings()
    base_url = settings.media_base_url.rstrip("/") if settings.media_base_url else "http://localhost:8000"
    media_url = f"{base_url}/static/uploads/{unique_name}"

    try:
        sender = _get_sender()
        to = phone if phone.startswith("whatsapp:") else f"whatsapp:+{phone}"

        # Send with caption (or default)
        text = caption.strip() if caption.strip() else f"📎 {filename}"
        await sender.send_text(to=to, text=text, media_url=media_url)

        # Save to conversation history
        _store.add_message(
            phone, "assistant",
            f"[RM] 📎 {filename}" + (f"\n{caption}" if caption.strip() else ""),
            media_url=media_url,
        )

        logger.info("RM file sent to %s: %s (%d bytes)", _short_phone(phone), filename, len(content))
        return {"status": "sent", "to": _short_phone(phone), "file": filename, "url": media_url}
    except Exception as exc:
        # Clean up file on send failure
        file_path.unlink(missing_ok=True)
        logger.exception("Failed to send RM file: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── GET /api/handoffs — list all handoff requests ────────────────────

@router.get("/handoffs")
async def list_handoffs():
    """Return all handoff records, sorted by urgency."""
    handoffs = get_all_handoffs()
    return {"handoffs": handoffs, "total": len(handoffs)}


# ── GET /api/handoffs/{phone}/brief — AI-generated handoff brief ─────

@router.get("/handoffs/{phone}/brief")
async def handoff_brief(phone: str):
    """Generate a detailed handoff brief for RM preparation."""
    session = _store.get_existing(phone)
    if not session:
        session = _store.get_existing(f"whatsapp:+{phone}")
        if not session:
            raise HTTPException(status_code=404, detail="User not found")
        phone = f"whatsapp:+{phone}"

    brief = await generate_handoff_brief(phone, session)
    return brief


# ── POST /api/handoffs/{phone}/resolve — mark handoff as resolved ────

@router.post("/handoffs/{phone}/resolve")
async def resolve_handoff_api(phone: str):
    """Mark a handoff as resolved after RM has addressed it."""
    # Try with whatsapp prefix
    success = resolve_handoff(phone)
    if not success:
        success = resolve_handoff(f"whatsapp:+{phone}")
    if not success:
        raise HTTPException(status_code=404, detail="Handoff not found")

    # Also update session state
    session = _store.get_existing(phone) or _store.get_existing(f"whatsapp:+{phone}")
    if session:
        session["handoff_state"] = "bot_active"
        actual_phone = session.get("phone", phone)
        _store.save(actual_phone)

    return {"status": "resolved"}
