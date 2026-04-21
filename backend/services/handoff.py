"""Handoff service — structured records for TTA requests + RM briefs."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import anthropic

from backend.config import get_settings
from backend.data.mock_users import get_user, get_portfolio, get_goals, get_sips, fmt_amount

logger = logging.getLogger("fi-chat.handoff")

HANDOFFS_DIR = Path("handoffs")
HANDOFFS_DIR.mkdir(exist_ok=True)

# In-memory store
_handoffs: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_from_disk() -> None:
    """Rehydrate _handoffs from disk. For each phone, keep the latest record."""
    latest: dict[str, dict[str, Any]] = {}
    for path in HANDOFFS_DIR.glob("hoff_*.json"):
        try:
            record = json.loads(path.read_text())
        except Exception as exc:
            logger.warning("Skipping unreadable handoff %s: %s", path.name, exc)
            continue
        phone = record.get("phone")
        if not phone:
            continue
        existing = latest.get(phone)
        if not existing or record.get("created_at", "") > existing.get("created_at", ""):
            latest[phone] = record
    _handoffs.update(latest)
    pending = sum(1 for r in _handoffs.values() if r.get("status") == "pending")
    logger.info("Rehydrated %d handoffs from disk (%d pending)", len(_handoffs), pending)


_load_from_disk()


def create_handoff(
    phone: str,
    session: dict,
    reason: str = "user_requested",
    urgency: str = "normal",
) -> dict:
    """Create a structured handoff record when user requests TTA.

    reason: "user_requested" | "agitation_detected" | "post_pdf"
    urgency: "low" | "normal" | "high"
    """
    record = {
        "id": f"hoff_{phone.replace('+', '').replace(':', '_')}_{int(datetime.now(timezone.utc).timestamp())}",
        "phone": phone,
        "language": session.get("language", "en"),
        "user_segment": session.get("user_segment"),
        "reason": reason,
        "urgency": urgency,
        "active_intent": session.get("active_intent"),
        "message_count": len(session.get("messages", [])),
        "has_plan": bool(session.get("flow_state", {}).get("current_plan")),
        "status": "pending",  # pending | in_progress | resolved
        "created_at": _now(),
        "resolved_at": None,
    }

    _handoffs[phone] = record

    # Persist to disk
    path = HANDOFFS_DIR / f"{record['id']}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2))

    logger.info("Handoff created: %s (reason=%s, urgency=%s)", record["id"], reason, urgency)
    return record


def get_handoff(phone: str) -> dict | None:
    """Get pending handoff for a phone number."""
    return _handoffs.get(phone)


def get_all_handoffs() -> list[dict]:
    """Get all handoff records, sorted by urgency and creation time."""
    records = list(_handoffs.values())
    # Sort: high urgency first, then pending first, then by creation time
    urgency_order = {"high": 0, "normal": 1, "low": 2}
    status_order = {"pending": 0, "in_progress": 1, "resolved": 2}
    records.sort(key=lambda r: (
        urgency_order.get(r["urgency"], 1),
        status_order.get(r["status"], 0),
        r["created_at"],
    ))
    return records


def resolve_handoff(phone: str) -> bool:
    """Mark handoff as resolved."""
    record = _handoffs.get(phone)
    if not record:
        return False
    record["status"] = "resolved"
    record["resolved_at"] = _now()
    # Update disk
    path = HANDOFFS_DIR / f"{record['id']}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
    logger.info("Handoff resolved: %s", record["id"])
    return True


async def generate_handoff_brief(phone: str, session: dict) -> dict:
    """Generate Sonnet-powered handoff brief for RM — profile, goals, talking points."""
    messages = session.get("messages", [])
    flow = session.get("flow_state", {})
    current_plan = flow.get("current_plan")

    # Build context
    conv_text = "\n".join(
        f"{m['role'].upper()}: {m['content'][:300]}" for m in messages[-20:]
    )

    # Add known user data
    user_data = ""
    known_user = get_user(phone)
    if known_user:
        user_data += f"\nKnown client: {known_user['name']}, Age {known_user['age']}, Risk: {known_user['risk_profile']}"
        portfolio = get_portfolio(phone)
        if portfolio:
            user_data += f"\nPortfolio: {fmt_amount(portfolio['total_invested'])} invested, {fmt_amount(portfolio['current_value'])} current, {portfolio['xirr']}% XIRR"
        goals = get_goals(phone)
        if goals:
            for g in goals:
                user_data += f"\nGoal: {g['name']} — {g['progress_pct']:.0f}% achieved ({g['status']})"
        sips = get_sips(phone)
        if sips:
            active = [s for s in sips if s["status"] == "active"]
            user_data += f"\nActive SIPs: {len(active)}, Total: {fmt_amount(sum(s['amount'] for s in active))}/mo"

    plan_context = ""
    if current_plan:
        plan_context = (
            f"\nGenerated plan: {current_plan.get('goal_name')}, "
            f"SIP ₹{current_plan.get('sip_required', 0):,}/mo, "
            f"tenure {current_plan.get('tenure_years')}yr, "
            f"risk: {current_plan.get('risk_label')}"
        )

    prompt = f"""You are helping a Relationship Manager (RM) at FundsIndia prepare for a customer call/chat.

Generate a comprehensive handoff brief with:
1. Customer Profile (1-2 lines: who they are, what segment)
2. Summary (2-3 sentences: what happened in the conversation, what they want)
3. Goals & Plans (what financial goals they mentioned, any plans generated)
4. Recommended Actions (3-4 specific things the RM should do/discuss)
5. Talking Points (3-5 bullet points for the call, actionable and specific)
6. Tone Guidance (how to approach this customer — formal/casual, reassure/educate)

CONVERSATION:
{conv_text}
{user_data}
{plan_context}

Customer language: {session.get('language', 'en')}
Handoff reason: {session.get('handoff_state', 'unknown')}
User segment: {session.get('user_segment', 'unknown')}

Respond in JSON (no markdown fences):
{{"profile": "...", "summary": "...", "goals": "...", "recommended_actions": ["...", "..."], "talking_points": ["...", "..."], "tone_guidance": "..."}}"""

    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    try:
        response = await client.messages.create(
            model=settings.sonnet_model,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip code fences
        import re
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            raw = raw.strip()
        return json.loads(raw)
    except Exception as exc:
        logger.exception("Handoff brief generation failed: %s", exc)
        return {
            "profile": f"Customer at {phone}",
            "summary": "Unable to generate brief. Review transcript directly.",
            "goals": "See conversation history.",
            "recommended_actions": ["Review full transcript", "Ask about investment goals"],
            "talking_points": ["Understand current needs", "Offer personalized plan"],
            "tone_guidance": "Be warm and professional.",
        }
