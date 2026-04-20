"""Goal discovery handler — Sonnet-driven stateful collection → engine → plan summary.

Flow:
  1. User says something about a goal (detected by intent classifier)
  2. Sonnet extracts what's known, asks for what's missing — ONE question at a time
  3. When enough info collected → calls generate_plan()
  4. Sends text summary + offers PDF
"""
from __future__ import annotations

import json
import logging
import re

import anthropic

from backend.config import get_settings
from backend.recommender.engine import generate_plan
from backend.recommender.constants import SIP_MINIMUM

logger = logging.getLogger("fi-chat.goal_discovery")

_EXTRACTION_PROMPT = """You are a goal discovery assistant for FundsIndia's mutual fund advisory WhatsApp bot.

Your job: Extract investment goal parameters from the conversation and decide what to ask next.

== PARAMETERS TO COLLECT ==
1. goal_type: "retirement" | "child_education" | "wealth_creation"
2. target_amount: Target corpus in ₹ (e.g., 5000000 for ₹50 lakh)
3. tenure_years: How many years to achieve the goal
4. sip_amount: Monthly SIP the user can invest (in ₹)
5. child_age: (only for child_education) Child's current age
6. current_age: (only for retirement) User's current age

== RULES ==
- Extract any parameters mentioned in the conversation so far
- If goal_type is clear but target_amount is NOT specified, use defaults:
  - retirement: 5000000 (₹50 lakh)
  - child_education: 5000000 (₹50 lakh, private college)
  - wealth_creation: 10000000 (₹1 crore)
- For child_education: if child_age is known, tenure = 18 - child_age
- For retirement: if current_age is known, tenure = 60 - current_age
- A plan is READY when we have: goal_type + (tenure_years OR age to derive it) + sip_amount
- If user gives target_amount but not sip_amount, we can still generate (engine calculates SIP)
- So READY = goal_type + tenure info + (sip_amount OR target_amount)

== CONVERSATION CONTEXT ==
{history}

== CURRENT USER MESSAGE ==
{message}

== CURRENTLY COLLECTED ==
{collected}

== RESPOND WITH ONLY VALID JSON (no markdown) ==
{{
  "collected": {{
    "goal_type": "<string or null>",
    "target_amount": <int or null>,
    "tenure_years": <int or null>,
    "sip_amount": <int or null>,
    "child_age": <int or null>,
    "current_age": <int or null>
  }},
  "ready": <true if enough info to generate plan>,
  "next_question": "<friendly question to ask next, in user's language, with emoji. null if ready>",
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

    # Build history context
    recent = history[-8:] if history else []
    history_text = "\n".join(f"{m['role']}: {m['content'][:200]}" for m in recent)

    response = await client.messages.create(
        model=settings.haiku_model,
        max_tokens=400,
        messages=[{
            "role": "user",
            "content": _EXTRACTION_PROMPT.format(
                history=history_text,
                message=message,
                collected=json.dumps(collected),
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

    if not ready:
        # Ask next question
        question = result.get("next_question", "")
        if not question:
            question = _default_next_question(collected, language)
        return question

    # ── Plan generation ───────────────────────────────────────────
    logger.info("Goal collection complete: %s", collected)

    goal_type = collected.get("goal_type", "wealth_creation")
    plan = generate_plan(
        goal_type=goal_type,
        present_value=collected.get("target_amount"),
        tenure_years=collected.get("tenure_years"),
        sip_amount=collected.get("sip_amount"),
        child_age=collected.get("child_age"),
        current_age=collected.get("current_age"),
    )

    # Store plan in session
    flow["current_plan"] = plan
    session["flow_state"] = flow

    # Generate text summary
    summary = _format_plan_summary(plan, language)
    return summary


def _default_next_question(collected: dict, language: str) -> str:
    """Fallback question based on what's missing."""
    if not collected.get("goal_type"):
        if language == "hinglish":
            return "Aap kis goal ke liye invest karna chahte hain? 🎯\n\n• Retirement 🏖️\n• Bacche ki education 🎓\n• Wealth creation 💰"
        return "What are you saving for? 🎯\n\n• Retirement 🏖️\n• Child's education 🎓\n• Wealth creation 💰"

    if collected.get("goal_type") == "child_education" and not collected.get("child_age"):
        if language == "hinglish":
            return "Aapke bacche ki abhi kitni age hai? 👶"
        return "How old is your child? 👶"

    if collected.get("goal_type") == "retirement" and not collected.get("current_age"):
        if language == "hinglish":
            return "Aapki abhi kitni age hai? 🙂"
        return "How old are you currently? 🙂"

    if not collected.get("tenure_years") and not collected.get("child_age") and not collected.get("current_age"):
        if language == "hinglish":
            return "Kitne saalon mein yeh goal achieve karna chahte hain? ⏰"
        return "In how many years do you want to achieve this goal? ⏰"

    if not collected.get("sip_amount") and not collected.get("target_amount"):
        if language == "hinglish":
            return "Har mahine kitna invest kar sakte hain? 💸"
        return "How much can you invest monthly? 💸"

    return "Let me generate your personalized plan! 🎯"


def _format_plan_summary(plan: dict, language: str) -> str:
    """Format plan as WhatsApp-friendly multi-message text."""
    sip = plan["sip_required"]
    fv = plan["future_value"]
    pv = plan["present_value"]
    tenure = plan["tenure_years"]
    goal = plan["goal_name"]
    risk = plan["risk_label"]
    stepup = plan["stepup_scenario"]
    m1 = plan["milestones"][0]

    # Format amounts
    def fmt(amt):
        if amt >= 10_000_000:
            return f"₹{amt/10_000_000:.1f} Cr"
        if amt >= 100_000:
            return f"₹{amt/100_000:.1f} L"
        return f"₹{amt:,.0f}"

    # Message 1: Goal overview
    msg1 = (
        f"🎯 *Your {goal} Plan*\n\n"
        f"📊 Target: {fmt(pv)} → {fmt(fv)} (inflation-adjusted)\n"
        f"⏰ Timeline: {tenure} years\n"
        f"🛡️ Risk Profile: {risk}\n"
        f"📈 Expected Return: {plan['assumptions']['expected_return']}/year"
    )

    # Message 2: SIP Strategy
    msg2 = (
        f"💰 *The Set-and-Forget Strategy*\n\n"
        f"Invest *{fmt(sip)}/month* for {tenure} years\n\n"
        f"🚀 *The Step-Up Strategy*\n\n"
        f"Start with *{fmt(stepup['base_sip'])}/month*\n"
        f"Increase by {stepup['stepup_rate_pct']}% every year"
    )

    # Message 3: Milestones teaser
    msg3 = (
        f"🌱 *Start small, grow big!*\n\n"
        f"Your first milestone: {fmt(m1['target_corpus'])} in just {m1['time_years']} years "
        f"with only {fmt(m1['sip_required'])}/month\n\n"
    )

    # Message 4: Fund allocation
    funds = plan["recommended_funds"]
    fund_lines = []
    for f in funds[:6]:  # cap at 6 for readability
        fund_lines.append(f"• {f['category']}: *{f['name']}* — {fmt(f['monthly_amount'])}/mo")
    fund_text = "\n".join(fund_lines)

    alloc = plan["allocation"]["main"]
    msg4 = (
        f"📂 *Your Portfolio*\n\n"
        f"Equity {alloc['equity']}% | Debt {alloc['debt']}% | Gold {alloc['gold']}%\n\n"
        f"{fund_text}"
    )

    # Message 5: CTA
    msg5 = (
        f"✅ *Your personalized plan is ready!*\n\n"
        f"Want me to generate a detailed PDF report? 📄\n"
        f"Or connect with our expert advisor to get started? 🧑‍💼"
    )

    # Join with ||| delimiter for multi-message sending
    return f"{msg1}|||{msg2}|||{msg3}|||{msg4}|||{msg5}"
