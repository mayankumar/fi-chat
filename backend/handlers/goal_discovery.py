"""Goal discovery handler — Sonnet-driven stateful collection → engine → plan summary.

Flow:
  1. User says something about a goal (detected by intent classifier)
  2. Sonnet extracts what's known, asks for what's missing — ONE question at a time
  3. When enough info collected → calls generate_plan()
  4. Sends text summary + offers PDF
  5. If user modifies goal/SIP after plan → regenerates with new params
"""
from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import datetime
from pathlib import Path

import anthropic

from backend.config import get_settings
from backend.data.mock_users import get_user
from backend.pdf.renderer import generate_pdf, get_pdf_url
from backend.recommender.engine import generate_plan
from backend.recommender.constants import SIP_MINIMUM
from backend.services.twilio_sender import TEMPLATE_PLAN_CTA

_STATIC_PDF_DIR = Path("backend/static/pdfs")

logger = logging.getLogger("fi-chat.goal_discovery")

_EXTRACTION_PROMPT = """You are a warm, empathetic goal-discovery advisor for FundsIndia's WhatsApp bot.

Today's date: {today} (year {year}). When the user mentions a target year like "2040 tak", compute tenure_years = target_year − {year}.

Your job: act like the best RM the user has ever met — friendly, curious, genuinely interested in their life — while quietly extracting the parameters needed to generate an investment plan. Ask ONE focused question per turn. Sound human.

== PARAMETERS TO COLLECT ==
1. goal_type: "retirement" | "child_education" | "wealth_creation"
2. goal_context: "accumulation" | "consumption"
   - "accumulation": open-ended growth — retirement, generic "paisa badhana", wealth creation
   - "consumption": specific asset the user wants to buy — ghar/house, car, travel/honeymoon, shaadi/wedding, child education, down-payment
3. goal_label: 1-3 word label in the user's own words ("Ghar", "Car", "Bacche ki shaadi", "Retirement"). Used in plan title.
4. target_amount: Target corpus in ₹. ONLY if user states a number. NEVER invent a default.
5. tenure_years: Years to achieve the goal.
6. sip_amount: Monthly SIP in ₹. If user gives a range ("40-50K"), use the LOWER bound.
7. lumpsum_amount: One-time lumpsum in ₹.
8. risk_profile: "conservative" | "moderate" | "aggressive".
9. child_age / current_age: as applicable.

== HOW TO EXTRACT ==
- SIP vs lumpsum: "monthly/per month/mahine/SIP" → sip_amount. "one-time/lumpsum/bonus/have X now" → lumpsum_amount.
- goal_context: ghar/car/travel/shaadi/education → consumption. Retirement/paisa badhana/wealth → accumulation.
- For child_education: tenure_years = 18 − child_age (if child_age known).
- For retirement: tenure_years = 60 − current_age (if current_age known).
- If the user pushes back ("pata nahi"), proceed without that field.

== COLLECTION ORDER (ask one at a time, in this rough order) ==
1. goal_type (if unclear from first message)
2. goal-specific detail: child_age (education) / current_age (retirement) / target_amount (consumption only — "kitne ka ghar?")
3. tenure_years (if not already derivable)
4. sip_amount and/or lumpsum_amount ("how much can you invest — monthly, lumpsum, or both?")
5. RISK (only if is_known_user=false AND risk_profile is null) — ONE scenario-based question (see below)

== RISK ASSESSMENT ==
- If is_known_user=true: we already know their risk from their profile. DO NOT ask.
- If the user already volunteered risk comfort in their words: capture it. DO NOT re-ask.
- Otherwise, ask ONE scenario-based question AFTER gathering goal + tenure + amount. Never use jargon like "risk profile". Examples:
  - Hinglish: "Ek last sawaal — agar aapka investment 1 saal mein 20% neeche chala jaaye, aap kya karoge? 🤔\n\n(a) Withdraw kar lunga\n(b) Hold karke wait karunga\n(c) Aur invest karunga — sasta hai!"
  - English: "One last thing — if your investment dropped 20% in a year, what would you do? 🤔\n\n(a) Pull it out\n(b) Hold and wait it out\n(c) Invest more while it's cheap"
  - Hindi: "एक आख़िरी सवाल — अगर investment 1 साल में 20% गिर जाए, आप क्या करेंगे? 🤔\n\n(a) निकाल लूँगा\n(b) रुककर wait करूँगा\n(c) और invest करूँगा"
- Map user's answer: (a) → conservative, (b) → moderate, (c) → aggressive.

== WHEN TO ASK FOR target_amount ==
- goal_context == "consumption": ASK target — "Approximately kitne ka ghar sochenge?". Mark ready=false until target given or user declines ("pata nahi").
- goal_context == "accumulation": DO NOT ask target — projection on their SIP/lumpsum is the right plan.

== READY CRITERIA ==
Set ready=true when ALL of:
- goal_type known
- tenure_years (or derivable age) known
- at least one of (sip_amount, lumpsum_amount, target_amount) known
- For consumption goals: target_amount known OR user declined
- Risk: known (from user words / known profile) OR user answered the scenario question OR is_known_user=true
If plan_exists=true and user gives new values → is_modification=true, ready=true.

== TONE ==
- First response to a new goal = ONE line of genuine warmth/empathy + ONE focused question. Not a paragraph.
- Match the user's language exactly (en / hi / hinglish). Never switch.
- One emoji max per message. Conversational. Never corporate.
- Follow-up turns: skip the empathy opener, just the question with a light conversational connector ("Got it", "Samajh gaye", "Achha").

Warmth examples:
- Ghar: "Waah, ghar kharidna kiska sapna nahi hota! 🏠 Approximately kitne ka ghar sochenge?"
- Retirement: "Retirement ki planning abhi se — superb! 🌅 Aap abhi kitne saal ke hain?"
- Child education: "बच्चे की शिक्षा के लिए — बहुत अच्छी सोच! 🎓 बच्चे की अभी कितनी उम्र है?"
- Wealth: "Love that you want to grow your money! 💰 In how many years would you like to see it grow?"
- Shaadi: "Shaadi ki planning — bahut khaas! 💍 Shaadi ka budget approximately kitna soch rahe hain?"

== CONTEXT ==
User is a known FundsIndia client: {is_known_user}
Known risk profile (if any): {known_risk}

== CONVERSATION CONTEXT ==
{history}

== CURRENT USER MESSAGE ==
{message}

== CURRENTLY COLLECTED ==
{collected}

== PLAN ALREADY EXISTS ==
{plan_exists}

== RESPOND WITH ONLY VALID JSON (no markdown) ==
{{
  "collected": {{
    "goal_type": "<string or null>",
    "goal_context": "<accumulation|consumption or null>",
    "goal_label": "<short label or null>",
    "target_amount": <int or null>,
    "tenure_years": <int or null>,
    "sip_amount": <int or null>,
    "lumpsum_amount": <int or null>,
    "risk_profile": "<conservative|moderate|aggressive or null>",
    "child_age": <int or null>,
    "current_age": <int or null>
  }},
  "ready": <true if enough info OR modifying existing plan>,
  "is_modification": <true if user is changing an already-generated plan>,
  "next_question": "<warm, focused question in user's language with one emoji; null if ready>",
  "language": "<en|hi|hinglish — match user's language>"
}}"""


async def handle_goal_discovery(
    message: str,
    history: list[dict[str, str]],
    language: str,
    session: dict,
) -> str:
    """Process goal discovery conversation. Returns response text (may contain |||)."""
    settings = get_settings()
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    # Get current collected state
    flow = session.get("flow_state", {})
    collected = flow.get("goal_collected", {})
    plan_exists = flow.get("current_plan") is not None
    known_user = get_user(session.get("phone", ""))

    # Build history context
    recent = history[-8:] if history else []
    history_text = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in recent)

    today = datetime.now()
    is_known_user = known_user is not None
    known_risk = (known_user or {}).get("risk_profile") or "none"

    response = await client.messages.create(
        model=settings.haiku_model,
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": _EXTRACTION_PROMPT.format(
                today=today.strftime("%d %B %Y"),
                year=today.year,
                is_known_user=str(is_known_user).lower(),
                known_risk=known_risk,
                history=history_text,
                message=message,
                collected=json.dumps(collected),
                plan_exists=str(plan_exists).lower(),
            ),
        }],
    )

    raw = response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        raw = raw.strip()
    logger.info("Goal extraction raw: %s", raw)

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.error("Failed to parse goal extraction: %s", raw)
        return "I'd love to help you plan! 🎯 Could you tell me what you're saving for? (e.g., retirement, child's education, or a wealth target)"

    # Update collected state
    new_collected = result.get("collected", {})
    # Merge — keep previous values if new ones are null
    for k, v in new_collected.items():
        if v is not None:
            collected[k] = v

    flow["goal_collected"] = collected
    session["flow_state"] = flow

    ready = result.get("ready", False)
    is_modification = result.get("is_modification", False)

    if not ready:
        # Ask next question
        question = result.get("next_question", "")
        if not question:
            question = _default_next_question(collected, language)
        return question

    # ── Plan generation ───────────────────────────────────────────
    if is_modification:
        logger.info("Goal MODIFICATION detected — regenerating plan with: %s", collected)
    else:
        logger.info("Goal collection complete: %s", collected)

    goal_type = collected.get("goal_type", "wealth_creation")

    # Infer risk if the user never volunteered it (priority: user words → known
    # FundsIndia profile → heuristic on tenure + goal + age).
    risk = collected.get("risk_profile") or _infer_risk(collected, known_user)

    plan = generate_plan(
        goal_type=goal_type,
        present_value=collected.get("target_amount"),
        tenure_years=collected.get("tenure_years"),
        sip_amount=collected.get("sip_amount"),
        lumpsum_amount=collected.get("lumpsum_amount"),
        risk_profile=risk,
        child_age=collected.get("child_age"),
        current_age=collected.get("current_age"),
    )

    # Use user's own label (e.g. "Ghar", "Car") if provided; otherwise fall back
    # to the engine's generic goal_name.
    if collected.get("goal_label"):
        plan["goal_name"] = collected["goal_label"]
    plan["goal_context"] = collected.get("goal_context")

    # Store plan in session (overwrite any existing plan)
    flow["current_plan"] = plan
    session["flow_state"] = flow

    # Generate text summary
    summary = _format_plan_summary(plan, language, is_modification)

    # Generate PDF inline so it lands with the plan, not after a button tap.
    media_url = await _render_plan_pdf(plan, session.get("phone", ""))

    return {
        "messages": [summary],
        "pdf_text": _pdf_caption(language) if media_url else None,
        "media_url": media_url,
        "cta_text": _cta_text(language),
        "template_name": TEMPLATE_PLAN_CTA,
    }


async def _render_plan_pdf(plan: dict, phone: str) -> str | None:
    try:
        pdf_path = await generate_pdf(plan, phone or "unknown")
    except Exception as exc:
        logger.exception("PDF generation failed during goal_discovery: %s", exc)
        return None
    _STATIC_PDF_DIR.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copy2(pdf_path, _STATIC_PDF_DIR / Path(pdf_path).name)
    except Exception as exc:
        logger.warning("Could not mirror PDF to static dir: %s", exc)
    return get_pdf_url(pdf_path)


def _pdf_caption(language: str) -> str:
    if language == "hinglish":
        return "📄 *Yeh raha aapka detailed plan PDF*\n\nRakhiye ya apne advisor ke saath share kar sakte hain. ✨"
    if language == "hi":
        return "📄 *यह रहा आपका detailed plan PDF*\n\nइसे save करें या अपने advisor के साथ share करें। ✨"
    return "📄 *Here's your detailed plan PDF*\n\nSave it or share it with your advisor. ✨"


def _cta_text(language: str) -> str:
    if language == "hinglish":
        return "Ab aage kya? Hamare expert advisor se baat karna chahenge? 🧑‍💼"
    if language == "hi":
        return "आगे क्या? हमारे expert advisor से बात करना चाहेंगे? 🧑‍💼"
    return "What's next? Want to talk to one of our expert advisors? 🧑‍💼"


def _default_next_question(collected: dict, language: str) -> str:
    """Fallback question if Haiku returns an empty next_question. Keep warmth."""
    goal_type = collected.get("goal_type")
    goal_context = collected.get("goal_context")

    if not goal_type:
        if language == "hinglish":
            return "Aap kis goal ke liye invest karna chahte hain? 🎯\n\n• Retirement 🏖️\n• Bacche ki education 🎓\n• Ghar/car/travel 🏠\n• Wealth creation 💰"
        return "What are you saving for? 🎯\n\n• Retirement 🏖️\n• Child's education 🎓\n• House / car / travel 🏠\n• Wealth creation 💰"

    if goal_type == "child_education" and not collected.get("child_age"):
        if language == "hinglish":
            return "Bacche ki education ke liye — that's wonderful! 🎓 Bachhe ki abhi kitni umar hai?"
        return "Saving for your child's education — that's wonderful! 🎓 How old is your child right now?"

    if goal_type == "retirement" and not collected.get("current_age"):
        if language == "hinglish":
            return "Retirement ki planning — superb! 🌅 Aap abhi kitne saal ke hain?"
        return "Retirement planning — love that! 🌅 How old are you currently?"

    if not collected.get("tenure_years") and not collected.get("child_age") and not collected.get("current_age"):
        if language == "hinglish":
            return "Kitne saalon mein yeh goal achieve karna chahte hain? ⏰"
        return "In how many years would you like to achieve this goal? ⏰"

    # For consumption goals, ask target before SIP
    if goal_context == "consumption" and not collected.get("target_amount"):
        label = collected.get("goal_label") or "goal"
        if language == "hinglish":
            return f"Approximately kitne ka {label} sochenge? Rough idea bhi chalega. 🏠"
        return f"Approximately how much would the {label} cost? A rough ballpark is fine. 🏠"

    if not collected.get("sip_amount") and not collected.get("lumpsum_amount") and not collected.get("target_amount"):
        if language == "hinglish":
            return "Kitna invest kar sakte hain? 💸\n\n• Monthly SIP (e.g. ₹10,000/month)\n• Ya ek saath lumpsum (e.g. ₹50,000 one-time)"
        return "How much can you invest? 💸\n\n• Monthly SIP (e.g. ₹10,000/month)\n• Or a one-time lumpsum (e.g. ₹50,000 now)"

    return "Let me generate your personalized plan! 🎯"


def _infer_risk(collected: dict, known_user: dict | None) -> str:
    """Pick a risk profile without asking the user directly.

    Priority: known FundsIndia profile → heuristic on tenure/goal/age → moderate.
    Consumption goals (house, car, travel, wedding) are capped at moderate even
    on long tenures, because capital protection matters near the purchase date.
    """
    if known_user and known_user.get("risk_profile"):
        return known_user["risk_profile"]

    goal = (collected.get("goal_type") or "wealth_creation").lower()
    goal_context = (collected.get("goal_context") or "").lower()
    tenure = collected.get("tenure_years") or 0
    current_age = collected.get("current_age") or 0

    # Near-retirement pulls toward capital protection regardless of tenure.
    if goal == "retirement":
        if current_age >= 55:
            return "conservative"
        if current_age >= 45:
            return "moderate"

    # Short horizons need capital protection.
    if tenure and tenure <= 3:
        return "conservative"
    if tenure and tenure <= 7:
        return "moderate"

    # Consumption goals (buying house/car/etc.) cap at moderate — the target
    # isn't abstract wealth, it's a real purchase that can't tolerate late drawdowns.
    if goal_context == "consumption":
        return "moderate"

    # Long horizons for pure accumulation → lean aggressive.
    if tenure and tenure >= 12:
        return "aggressive"

    return "moderate"


def _format_plan_summary(plan: dict, language: str, is_modification: bool = False) -> str:
    """Format plan as WhatsApp-friendly multi-message text."""
    mode = plan.get("mode", "target")
    sip = plan["sip_required"]
    fv = plan["future_value"]
    tenure = plan["tenure_years"]
    goal = plan["goal_name"]
    risk = plan["risk_label"]
    stepup = plan["stepup_scenario"]
    milestones = plan.get("milestones") or []

    lumpsum = plan.get("lumpsum_amount", 0)
    lumpsum_fv = plan.get("lumpsum_future_value", 0)
    user_sip = plan.get("user_sip") or 0
    user_sip_fv = plan.get("user_sip_future_value", 0)

    def fmt(amt):
        if amt >= 10_000_000:
            return f"₹{amt/10_000_000:.1f} Cr"
        if amt >= 100_000:
            return f"₹{amt/100_000:.1f} L"
        return f"₹{amt:,.0f}"

    mod_prefix = ""
    if is_modification:
        mod_prefix = (
            "✅ *Done! Aapka updated plan ready hai:*\n\n"
            if language == "hinglish"
            else "✅ *Done! Here's your updated plan:*\n\n"
        )

    if mode == "projection":
        sections = _projection_sections(
            plan, mod_prefix, goal, tenure, risk, lumpsum, lumpsum_fv,
            user_sip, user_sip_fv, fv, fmt,
        )
    else:
        sections = _target_sections(
            plan, mod_prefix, goal, tenure, risk, sip, fv, stepup,
            milestones, lumpsum, lumpsum_fv, fmt,
        )

    sections.append(_fund_section(plan, fmt))
    sections.append(_disclaimer_section())

    return "|||".join(sections)


def _target_sections(plan, mod_prefix, goal, tenure, risk, sip, fv, stepup,
                     milestones, lumpsum, lumpsum_fv, fmt) -> list[str]:
    pv = plan["present_value"]

    msg1 = (
        f"{mod_prefix}"
        f"🎯 *Your {goal} Plan*\n\n"
        f"📊 Target: {fmt(pv)} → {fmt(fv)} (inflation-adjusted)\n"
        f"⏰ Timeline: {tenure} years\n"
        f"🛡️ Risk Profile: {risk}\n"
        f"📈 Expected Return: {plan['assumptions']['expected_return']}/year"
    )

    lumpsum_line = (
        f"💼 *Lumpsum kickstart:* {fmt(lumpsum)} today grows to ~{fmt(lumpsum_fv)} in {tenure} years\n\n"
        if lumpsum > 0 else ""
    )

    if sip > 0:
        strategy = (
            f"💰 *The Set-and-Forget Strategy*\n\n"
            f"Invest *{fmt(sip)}/month* for {tenure} years\n\n"
            f"🚀 *The Step-Up Strategy*\n\n"
            f"Start with *{fmt(stepup['base_sip'])}/month*\n"
            f"Increase by {stepup['stepup_rate_pct']}% every year"
        )
    else:
        strategy = (
            "✨ Your lumpsum alone is enough to cover this goal at the assumed return — "
            "no monthly SIP required. Consider a small SIP anyway for an extra cushion."
        )
    msg2 = f"{lumpsum_line}{strategy}"

    sections = [msg1, msg2]

    if milestones:
        m1 = milestones[0]
        sections.append(
            f"🌱 *Start small, grow big!*\n\n"
            f"Your first milestone: {fmt(m1['target_corpus'])} in just {m1['time_years']} years "
            f"with only {fmt(m1['sip_required'])}/month"
        )

    return sections


def _projection_sections(plan, mod_prefix, goal, tenure, risk, lumpsum,
                         lumpsum_fv, user_sip, user_sip_fv, fv, fmt) -> list[str]:
    principal_parts = []
    if lumpsum > 0:
        principal_parts.append(f"{fmt(lumpsum)} lumpsum today")
    if user_sip > 0:
        principal_parts.append(f"{fmt(user_sip)}/month SIP")
    principal_line = " + ".join(principal_parts) if principal_parts else "your investment"

    msg1 = (
        f"{mod_prefix}"
        f"🎯 *Your {goal} Plan*\n\n"
        f"📊 {principal_line} → ~{fmt(fv)} in {tenure} years\n"
        f"⏰ Timeline: {tenure} years\n"
        f"🛡️ Risk Profile: {risk}\n"
        f"📈 Expected Return: {plan['assumptions']['expected_return']}/year"
    )

    projection_lines = []
    if lumpsum > 0:
        projection_lines.append(f"💼 Lumpsum: {fmt(lumpsum)} → *{fmt(lumpsum_fv)}*")
    if user_sip > 0:
        projection_lines.append(
            f"💰 SIP: {fmt(user_sip)}/mo for {tenure} years → *{fmt(user_sip_fv)}*"
        )
    projection_lines.append(f"✨ *Total estimated corpus:* {fmt(fv)}")

    msg2 = "📈 *How your money could grow*\n\n" + "\n".join(projection_lines)

    return [msg1, msg2]


def _fund_section(plan: dict, fmt) -> str:
    funds = plan.get("recommended_funds") or []
    alloc = plan["allocation"]["main"]
    lumpsum = plan.get("lumpsum_amount", 0)

    lines = []
    for f in funds[:6]:
        parts = []
        if f.get("monthly_amount", 0) > 0:
            parts.append(f"{fmt(f['monthly_amount'])}/mo")
        if f.get("lumpsum_amount", 0) > 0:
            parts.append(f"{fmt(f['lumpsum_amount'])} once")
        amount_text = " + ".join(parts) if parts else "—"
        lines.append(f"• {f['category']}: *{f['name']}* — {amount_text}")

    header = "📂 *Your Portfolio*"
    if lumpsum > 0 and all(f.get("monthly_amount", 0) == 0 for f in funds):
        header = "📂 *How to split your lumpsum*"

    return (
        f"{header}\n\n"
        f"Equity {alloc['equity']}% | Debt {alloc['debt']}% | Gold {alloc['gold']}%\n\n"
        + ("\n".join(lines) if lines else "_No fund split available for this amount._")
    )


def _disclaimer_section() -> str:
    return (
        "⚠️ _Mutual fund investments are subject to market risks. "
        "This is an indicative plan, not guaranteed returns. "
        "Consult our SEBI-registered advisors before investing._"
    )
