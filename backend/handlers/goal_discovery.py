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
        fallbacks = {
            "hinglish": "Main aapki help karne ke liye ready hoon! 🎯 Bataiye aap kis goal ke liye save kar rahe hain — retirement, bacche ki padhai, ya kuch aur?",
            "hi": "मैं आपकी मदद करने को तैयार हूँ! 🎯 बताइए आप किस goal के लिए save कर रहे हैं — retirement, बच्चे की पढ़ाई, या कुछ और?",
        }
        return fallbacks.get(language, "I'd love to help you plan! 🎯 What are you saving for — retirement, a child's education, or a wealth target?")

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


# Fallback questions keyed by slot; used only when Haiku returns no next_question.
_FALLBACK_QUESTIONS = {
    "goal_type": {
        "en": "What are you saving for? 🎯\n\n• Retirement 🏖️\n• Child's education 🎓\n• House / car / travel 🏠\n• Wealth creation 💰",
        "hinglish": "Aap kis goal ke liye invest karna chahte hain? 🎯\n\n• Retirement 🏖️\n• Bacche ki education 🎓\n• Ghar/car/travel 🏠\n• Wealth creation 💰",
        "hi": "आप किस goal के लिए invest करना चाहते हैं? 🎯\n\n• Retirement 🏖️\n• बच्चे की education 🎓\n• घर / car / travel 🏠\n• Wealth creation 💰",
    },
    "child_age": {
        "en": "Saving for your child's education — that's wonderful! 🎓 How old is your child right now?",
        "hinglish": "Bacche ki education ke liye — that's wonderful! 🎓 Bachhe ki abhi kitni umar hai?",
        "hi": "बच्चे की शिक्षा के लिए — बहुत अच्छा! 🎓 बच्चे की अभी कितनी उम्र है?",
    },
    "current_age": {
        "en": "Retirement planning — love that! 🌅 How old are you currently?",
        "hinglish": "Retirement ki planning — superb! 🌅 Aap abhi kitne saal ke hain?",
        "hi": "Retirement की planning — बढ़िया! 🌅 आप अभी कितने साल के हैं?",
    },
    "tenure_years": {
        "en": "In how many years would you like to achieve this goal? ⏰",
        "hinglish": "Kitne saalon mein yeh goal achieve karna chahte hain? ⏰",
        "hi": "कितने साल में यह goal achieve करना चाहते हैं? ⏰",
    },
    "amount": {
        "en": "How much can you invest? 💸\n\n• Monthly SIP (e.g. ₹10,000/month)\n• Or a one-time lumpsum (e.g. ₹50,000 now)",
        "hinglish": "Kitna invest kar sakte hain? 💸\n\n• Monthly SIP (e.g. ₹10,000/month)\n• Ya ek saath lumpsum (e.g. ₹50,000 one-time)",
        "hi": "कितना invest कर सकते हैं? 💸\n\n• Monthly SIP (जैसे ₹10,000/month)\n• या एक साथ lumpsum (जैसे ₹50,000 one-time)",
    },
    "ready": {
        "en": "Got it — let me put your personalised plan together now. 🎯",
        "hinglish": "Samajh gaya — aapka personalised plan banata hoon abhi. 🎯",
        "hi": "समझ गया — अभी आपका personalised plan तैयार करता हूँ। 🎯",
    },
}

# Consumption target question uses a dynamic label, so templated separately.
_TARGET_QUESTION = {
    "en": "Approximately how much would the {label} cost? A rough ballpark is fine. 🏠",
    "hinglish": "Approximately kitne ka {label} sochenge? Rough idea bhi chalega. 🏠",
    "hi": "Approximately कितने का {label} सोच रहे हैं? Rough idea भी चलेगा। 🏠",
}


def _fallback(slot: str, language: str) -> str:
    table = _FALLBACK_QUESTIONS[slot]
    return table.get(language) or table["en"]


def _default_next_question(collected: dict, language: str) -> str:
    """Fallback question if Haiku returns an empty next_question. Keep warmth."""
    goal_type = collected.get("goal_type")
    goal_context = collected.get("goal_context")

    if not goal_type:
        return _fallback("goal_type", language)

    if goal_type == "child_education" and not collected.get("child_age"):
        return _fallback("child_age", language)

    if goal_type == "retirement" and not collected.get("current_age"):
        return _fallback("current_age", language)

    if not collected.get("tenure_years") and not collected.get("child_age") and not collected.get("current_age"):
        return _fallback("tenure_years", language)

    if goal_context == "consumption" and not collected.get("target_amount"):
        label = collected.get("goal_label") or "goal"
        template = _TARGET_QUESTION.get(language) or _TARGET_QUESTION["en"]
        return template.format(label=label)

    if not collected.get("sip_amount") and not collected.get("lumpsum_amount") and not collected.get("target_amount"):
        return _fallback("amount", language)

    return _fallback("ready", language)


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


# Localised labels for plan-summary output. Keep keys stable across languages.
_T = {
    "en": {
        "mod_prefix": "✅ *Done! Here's your updated plan:*\n\n",
        "plan_heading": "🎯 *Your {goal} Plan*",
        "target": "📊 Target",
        "inflation_adj": "(inflation-adjusted)",
        "timeline": "⏰ Timeline",
        "years": "years",
        "risk_profile": "🛡️ Risk Profile",
        "expected_return": "📈 Expected Return",
        "per_year": "year",
        "lumpsum_kickstart": "💼 *Lumpsum kickstart:* {amt} today grows to ~{fv} in {n} years",
        "set_forget": "💰 *Set-and-Forget Strategy*\n\nInvest *{sip}/month* for {n} years",
        "step_up": "🚀 *Step-Up Strategy*\n\nStart with *{base}/month*\nIncrease by {rate}% every year",
        "no_sip_needed": "✨ Your lumpsum alone covers this goal at the assumed return — no monthly SIP needed. A small SIP still adds a helpful cushion.",
        "milestone_head": "🌱 *Start small, grow big*",
        "milestone_body": "First milestone: {amt} in just {n} years with only {sip}/month",
        "projection_heading": "📈 *How your money could grow*",
        "projection_summary": "📊 {principal} → ~{fv} in {n} years",
        "principal_fallback": "your investment",
        "projection_lumpsum": "💼 Lumpsum: {amt} → *{fv}*",
        "projection_sip": "💰 SIP: {amt}/mo for {n} years → *{fv}*",
        "projection_total": "✨ *Total estimated corpus:* {fv}",
        "portfolio": "📂 *Your Portfolio*",
        "lumpsum_split": "📂 *How to split your lumpsum*",
        "no_funds": "_No fund split available for this amount._",
        "per_month_short": "/mo",
        "once": "once",
        "disclaimer": "⚠️ _Mutual fund investments are subject to market risks. This is an indicative plan, not a guarantee of returns. Our SEBI-registered advisors can help personalise it._",
    },
    "hinglish": {
        "mod_prefix": "✅ *Done! Aapka updated plan ready hai:*\n\n",
        "plan_heading": "🎯 *Aapka {goal} Plan*",
        "target": "📊 Target",
        "inflation_adj": "(inflation-adjusted)",
        "timeline": "⏰ Timeline",
        "years": "saal",
        "risk_profile": "🛡️ Risk Profile",
        "expected_return": "📈 Expected Return",
        "per_year": "saal",
        "lumpsum_kickstart": "💼 *Lumpsum kickstart:* {amt} aaj {n} saal mein ~{fv} ban jaata hai",
        "set_forget": "💰 *Set-and-Forget Strategy*\n\n{n} saal ke liye *{sip}/month* invest kariye",
        "step_up": "🚀 *Step-Up Strategy*\n\n*{base}/month* se shuru kariye\nHar saal {rate}% badhaiye",
        "no_sip_needed": "✨ Aapka lumpsum hi kaafi hai is goal ke liye — monthly SIP zaruri nahi. Thoda SIP rakhenge toh cushion mil jayega.",
        "milestone_head": "🌱 *Chhote steps, badi manzil*",
        "milestone_body": "Pehla milestone: sirf {sip}/month se {n} saal mein {amt}",
        "projection_heading": "📈 *Aapka paisa aise grow karega*",
        "projection_summary": "📊 {principal} → ~{fv} in {n} saal",
        "principal_fallback": "aapka investment",
        "projection_lumpsum": "💼 Lumpsum: {amt} → *{fv}*",
        "projection_sip": "💰 SIP: {amt}/mo, {n} saal → *{fv}*",
        "projection_total": "✨ *Kul estimated corpus:* {fv}",
        "portfolio": "📂 *Aapka Portfolio*",
        "lumpsum_split": "📂 *Lumpsum kaise split kare*",
        "no_funds": "_Is amount ke liye fund split available nahi hai._",
        "per_month_short": "/mo",
        "once": "ek baar",
        "disclaimer": "⚠️ _Mutual fund investments market risks ke adheen hain. Yeh indicative plan hai, guaranteed returns nahi. Personalised guidance ke liye SEBI-registered advisor baat kar sakte hain._",
    },
    "hi": {
        "mod_prefix": "✅ *हो गया! आपका updated plan तैयार है:*\n\n",
        "plan_heading": "🎯 *आपका {goal} Plan*",
        "target": "📊 Target",
        "inflation_adj": "(महंगाई-adjusted)",
        "timeline": "⏰ अवधि",
        "years": "साल",
        "risk_profile": "🛡️ Risk Profile",
        "expected_return": "📈 Expected Return",
        "per_year": "साल",
        "lumpsum_kickstart": "💼 *Lumpsum kickstart:* {amt} आज {n} साल में ~{fv} बन जाता है",
        "set_forget": "💰 *Set-and-Forget Strategy*\n\n{n} साल तक *{sip}/month* invest करें",
        "step_up": "🚀 *Step-Up Strategy*\n\n*{base}/month* से शुरू करें\nहर साल {rate}% बढ़ाएँ",
        "no_sip_needed": "✨ अकेले आपका lumpsum ही इस goal के लिए काफ़ी है — monthly SIP ज़रूरी नहीं। थोड़ा SIP रखेंगे तो cushion मिल जाएगा।",
        "milestone_head": "🌱 *छोटे steps, बड़ी मंज़िल*",
        "milestone_body": "पहला milestone: सिर्फ़ {sip}/month से {n} साल में {amt}",
        "projection_heading": "📈 *आपका पैसा ऐसे बढ़ेगा*",
        "projection_summary": "📊 {principal} → ~{fv} in {n} साल",
        "principal_fallback": "आपका investment",
        "projection_lumpsum": "💼 Lumpsum: {amt} → *{fv}*",
        "projection_sip": "💰 SIP: {amt}/mo, {n} साल → *{fv}*",
        "projection_total": "✨ *कुल अनुमानित corpus:* {fv}",
        "portfolio": "📂 *आपका Portfolio*",
        "lumpsum_split": "📂 *Lumpsum कैसे बाँटें*",
        "no_funds": "_इस amount के लिए fund split available नहीं है।_",
        "per_month_short": "/mo",
        "once": "एक बार",
        "disclaimer": "⚠️ _Mutual fund investments market risks के अधीन हैं। यह indicative plan है, guaranteed returns नहीं। Personalised guidance के लिए SEBI-registered advisor से बात कर सकते हैं।_",
    },
}


def _t(language: str) -> dict:
    return _T.get(language, _T["en"])


def _format_plan_summary(plan: dict, language: str, is_modification: bool = False) -> str:
    """Format plan as WhatsApp-friendly multi-message text in the user's language."""
    t = _t(language)
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

    mod_prefix = t["mod_prefix"] if is_modification else ""

    if mode == "projection":
        sections = _projection_sections(
            plan, mod_prefix, t, goal, tenure, risk, lumpsum, lumpsum_fv,
            user_sip, user_sip_fv, fv, fmt,
        )
    else:
        sections = _target_sections(
            plan, mod_prefix, t, goal, tenure, risk, sip, fv, stepup,
            milestones, lumpsum, lumpsum_fv, fmt,
        )

    sections.append(_fund_section(plan, t, fmt))
    sections.append(t["disclaimer"])

    return "|||".join(sections)


def _target_sections(plan, mod_prefix, t, goal, tenure, risk, sip, fv, stepup,
                     milestones, lumpsum, lumpsum_fv, fmt) -> list[str]:
    pv = plan["present_value"]

    msg1 = (
        f"{mod_prefix}"
        f"{t['plan_heading'].format(goal=goal)}\n\n"
        f"{t['target']}: {fmt(pv)} → {fmt(fv)} {t['inflation_adj']}\n"
        f"{t['timeline']}: {tenure} {t['years']}\n"
        f"{t['risk_profile']}: {risk}\n"
        f"{t['expected_return']}: {plan['assumptions']['expected_return']}/{t['per_year']}"
    )

    lumpsum_line = (
        t["lumpsum_kickstart"].format(amt=fmt(lumpsum), fv=fmt(lumpsum_fv), n=tenure) + "\n\n"
        if lumpsum > 0 else ""
    )

    if sip > 0:
        strategy = (
            t["set_forget"].format(sip=fmt(sip), n=tenure)
            + "\n\n"
            + t["step_up"].format(base=fmt(stepup["base_sip"]), rate=stepup["stepup_rate_pct"])
        )
    else:
        strategy = t["no_sip_needed"]
    msg2 = f"{lumpsum_line}{strategy}"

    sections = [msg1, msg2]

    if milestones:
        m1 = milestones[0]
        sections.append(
            f"{t['milestone_head']}\n\n"
            + t["milestone_body"].format(amt=fmt(m1["target_corpus"]), n=m1["time_years"], sip=fmt(m1["sip_required"]))
        )

    return sections


def _projection_sections(plan, mod_prefix, t, goal, tenure, risk, lumpsum,
                         lumpsum_fv, user_sip, user_sip_fv, fv, fmt) -> list[str]:
    principal_parts = []
    if lumpsum > 0:
        principal_parts.append(f"{fmt(lumpsum)} lumpsum")
    if user_sip > 0:
        principal_parts.append(f"{fmt(user_sip)}/mo SIP")
    principal_line = " + ".join(principal_parts) if principal_parts else t["principal_fallback"]

    msg1 = (
        f"{mod_prefix}"
        f"{t['plan_heading'].format(goal=goal)}\n\n"
        f"{t['projection_summary'].format(principal=principal_line, fv=fmt(fv), n=tenure)}\n"
        f"{t['timeline']}: {tenure} {t['years']}\n"
        f"{t['risk_profile']}: {risk}\n"
        f"{t['expected_return']}: {plan['assumptions']['expected_return']}/{t['per_year']}"
    )

    projection_lines = []
    if lumpsum > 0:
        projection_lines.append(t["projection_lumpsum"].format(amt=fmt(lumpsum), fv=fmt(lumpsum_fv)))
    if user_sip > 0:
        projection_lines.append(t["projection_sip"].format(amt=fmt(user_sip), n=tenure, fv=fmt(user_sip_fv)))
    projection_lines.append(t["projection_total"].format(fv=fmt(fv)))

    msg2 = t["projection_heading"] + "\n\n" + "\n".join(projection_lines)

    return [msg1, msg2]


def _fund_section(plan: dict, t: dict, fmt) -> str:
    funds = plan.get("recommended_funds") or []
    alloc = plan["allocation"]["main"]
    lumpsum = plan.get("lumpsum_amount", 0)

    lines = []
    for f in funds[:6]:
        parts = []
        if f.get("monthly_amount", 0) > 0:
            parts.append(f"{fmt(f['monthly_amount'])}{t['per_month_short']}")
        if f.get("lumpsum_amount", 0) > 0:
            parts.append(f"{fmt(f['lumpsum_amount'])} {t['once']}")
        amount_text = " + ".join(parts) if parts else "—"
        lines.append(f"• {f['category']}: *{f['name']}* — {amount_text}")

    header = t["portfolio"]
    if lumpsum > 0 and all(f.get("monthly_amount", 0) == 0 for f in funds):
        header = t["lumpsum_split"]

    return (
        f"{header}\n\n"
        f"Equity {alloc['equity']}% | Debt {alloc['debt']}% | Gold {alloc['gold']}%\n\n"
        + ("\n".join(lines) if lines else t["no_funds"])
    )
