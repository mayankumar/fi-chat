"""Portfolio handler — shows holdings, SIPs, goal progress for existing users."""
from __future__ import annotations

from datetime import date, timedelta

from backend.data.mock_users import get_user, get_portfolio, get_sips, get_goals, fmt_amount


def handle_portfolio_query(phone: str, language: str, query_type: str = "summary") -> dict:
    """Handle portfolio_query intent. Returns structured response.

    query_type: "summary" | "sips" | "goals"
    """
    user = get_user(phone)
    if not user:
        return _not_registered(language)

    if query_type == "sips":
        return _format_sips(phone, language)
    if query_type == "goals":
        return _format_goals(phone, language)
    return _format_summary(phone, language)


def handle_sip_action(phone: str, language: str, action: str, fund: str = "") -> dict:
    """Handle SIP pause/step-up requests.

    action: "pause" | "stepup"
    """
    user = get_user(phone)
    if not user:
        return _not_registered(language)

    if action == "pause":
        return _pause_sip_response(phone, fund, language)
    if action == "stepup":
        return _stepup_sip_response(phone, fund, language)
    return {"messages": ["I can help you pause or step-up your SIPs. What would you like to do?"], "template_name": None}


# -- Formatters --------------------------------------------------------------

def _format_summary(phone: str, language: str) -> dict:
    user = get_user(phone)
    portfolio = get_portfolio(phone)

    if not portfolio:
        msg = _no_portfolio_msg(language, user["name"])
        return {"messages": [msg], "template_name": None}

    gain = portfolio["current_value"] - portfolio["total_invested"]
    gain_pct = (gain / portfolio["total_invested"]) * 100

    if language == "hi":
        header = f"📊 *{user['name']}* — आपका Portfolio Summary\n"
        lines = [
            header,
            f"💰 *Invested:* {fmt_amount(portfolio['total_invested'])}",
            f"📈 *Current Value:* {fmt_amount(portfolio['current_value'])}",
            f"✨ *Total Gain:* {fmt_amount(gain)} (+{gain_pct:.1f}%)",
            f"📊 *XIRR:* {portfolio['xirr']}% p.a.",
            f"\n*Holdings ({len(portfolio['holdings'])} funds):*",
        ]
    elif language == "hinglish":
        header = f"📊 *{user['name']}* — Aapka Portfolio Summary\n"
        lines = [
            header,
            f"💰 *Invested:* {fmt_amount(portfolio['total_invested'])}",
            f"📈 *Current Value:* {fmt_amount(portfolio['current_value'])}",
            f"✨ *Total Gain:* {fmt_amount(gain)} (+{gain_pct:.1f}%)",
            f"📊 *XIRR:* {portfolio['xirr']}% p.a.",
            f"\n*Holdings ({len(portfolio['holdings'])} funds):*",
        ]
    else:
        header = f"📊 *{user['name']}* — Your Portfolio Summary\n"
        lines = [
            header,
            f"💰 *Invested:* {fmt_amount(portfolio['total_invested'])}",
            f"📈 *Current Value:* {fmt_amount(portfolio['current_value'])}",
            f"✨ *Total Gain:* {fmt_amount(gain)} (+{gain_pct:.1f}%)",
            f"📊 *XIRR:* {portfolio['xirr']}% p.a.",
            f"\n*Holdings ({len(portfolio['holdings'])} funds):*",
        ]

    for h in portfolio["holdings"]:
        h_gain = h["current"] - h["invested"]
        h_pct = (h_gain / h["invested"]) * 100
        sign = "+" if h_gain >= 0 else ""
        lines.append(f"  • {h['fund']}\n    {fmt_amount(h['invested'])} → {fmt_amount(h['current'])} ({sign}{h_pct:.1f}%)")

    summary_msg = "\n".join(lines)

    # Add goal progress if available
    goals = get_goals(phone)
    goal_msg = None
    if goals:
        goal_lines = ["\n🎯 *Goal Progress:*"]
        for g in goals:
            emoji = "✅" if g["status"] == "on_track" else "⚠️"
            goal_lines.append(f"  {emoji} *{g['name']}:* {g['progress_pct']:.0f}% achieved ({fmt_amount(g['achieved'])} / {fmt_amount(g['target_corpus'])})")
            if g.get("drift_alert"):
                goal_lines.append(f"     ⚠️ _{g['drift_alert']}_")
        goal_msg = "\n".join(goal_lines)

    messages = [summary_msg]
    if goal_msg:
        messages[0] += goal_msg

    tip = _get_tip(language)
    messages.append(tip)

    return {"messages": messages, "template_name": None}


def _format_sips(phone: str, language: str) -> dict:
    user = get_user(phone)
    sips = get_sips(phone)

    if not sips:
        return {"messages": [_no_sips_msg(language)], "template_name": None}

    today = date.today()
    active = [s for s in sips if s["status"] == "active"]
    paused = [s for s in sips if s["status"] == "paused"]

    total_monthly = sum(s["amount"] for s in active)

    if language == "hi":
        lines = [f"📋 *{user['name']}* — Active SIPs\n"]
        lines.append(f"💸 *Total Monthly SIP:* {fmt_amount(total_monthly)}\n")
    elif language == "hinglish":
        lines = [f"📋 *{user['name']}* — Active SIPs\n"]
        lines.append(f"💸 *Total Monthly SIP:* {fmt_amount(total_monthly)}\n")
    else:
        lines = [f"📋 *{user['name']}* — Your Active SIPs\n"]
        lines.append(f"💸 *Total Monthly SIP:* {fmt_amount(total_monthly)}\n")

    for s in active:
        next_date = _next_sip_date(s["day"], today)
        lines.append(f"  ✅ *{s['fund']}*\n     {fmt_amount(s['amount'])}/mo — next on {next_date.strftime('%d %b')}")

    if paused:
        lines.append("\n⏸️ *Paused SIPs:*")
        for s in paused:
            lines.append(f"  ⏸️ {s['fund']} — {fmt_amount(s['amount'])}/mo")

    msg = "\n".join(lines)

    if language == "en":
        tip = "\n\n💡 You can say _\"pause my SIP\"_ or _\"step up my SIP\"_ to make changes."
    elif language == "hi":
        tip = "\n\n💡 Aap _\"SIP pause karo\"_ ya _\"SIP badhao\"_ bol sakte hain."
    else:
        tip = "\n\n💡 Aap _\"pause my SIP\"_ ya _\"step up my SIP\"_ bol sakte hain."

    return {"messages": [msg + tip], "template_name": None}


def _format_goals(phone: str, language: str) -> dict:
    user = get_user(phone)
    goals = get_goals(phone)

    if not goals:
        return {"messages": [_no_goals_msg(language)], "template_name": None}

    if language == "en":
        lines = [f"🎯 *{user['name']}* — Your Goal Progress\n"]
    elif language == "hi":
        lines = [f"🎯 *{user['name']}* — Goal Progress\n"]
    else:
        lines = [f"🎯 *{user['name']}* — Aapka Goal Progress\n"]

    for g in goals:
        emoji = "✅" if g["status"] == "on_track" else "⚠️"
        bar = _progress_bar(g["progress_pct"])
        lines.append(f"{emoji} *{g['name']}*")
        lines.append(f"   {bar} {g['progress_pct']:.0f}%")
        lines.append(f"   Target: {fmt_amount(g['target_corpus'])} by {g['target_date'][:4]}")
        lines.append(f"   Achieved: {fmt_amount(g['achieved'])} | SIP: {fmt_amount(g['monthly_sip'])}/mo")
        if g.get("drift_alert"):
            lines.append(f"   ⚠️ _{g['drift_alert']}_")
        lines.append("")

    return {"messages": ["\n".join(lines)], "template_name": None}


# -- SIP Actions -------------------------------------------------------------

def _pause_sip_response(phone: str, fund: str, language: str) -> dict:
    sips = get_sips(phone)
    active_sips = [s for s in (sips or []) if s["status"] == "active"]

    if not active_sips:
        return {"messages": ["You don't have any active SIPs to pause."], "template_name": None}

    # If specific fund mentioned, confirm pause
    if fund:
        matched = [s for s in active_sips if fund.lower() in s["fund"].lower()]
        if matched:
            s = matched[0]
            msg = (
                f"⏸️ *Pause SIP Confirmation*\n\n"
                f"Fund: *{s['fund']}*\n"
                f"Amount: {fmt_amount(s['amount'])}/mo\n\n"
                f"Are you sure you want to pause this SIP? You can restart it anytime.\n\n"
                f"Reply *YES* to confirm or *NO* to cancel."
            )
            return {"messages": [msg], "template_name": None}

    # List SIPs to choose from
    lines = ["⏸️ *Which SIP would you like to pause?*\n"]
    for i, s in enumerate(active_sips, 1):
        lines.append(f"  {i}. {s['fund']} — {fmt_amount(s['amount'])}/mo")
    lines.append("\nReply with the fund name or number.")

    return {"messages": ["\n".join(lines)], "template_name": None}


def _stepup_sip_response(phone: str, fund: str, language: str) -> dict:
    sips = get_sips(phone)
    active_sips = [s for s in (sips or []) if s["status"] == "active"]

    if not active_sips:
        return {"messages": ["You don't have any active SIPs to step up."], "template_name": None}

    if fund:
        matched = [s for s in active_sips if fund.lower() in s["fund"].lower()]
        if matched:
            s = matched[0]
            new_amount = int(s["amount"] * 1.10)  # 10% step-up
            msg = (
                f"📈 *Step-Up SIP Confirmation*\n\n"
                f"Fund: *{s['fund']}*\n"
                f"Current: {fmt_amount(s['amount'])}/mo\n"
                f"New Amount: {fmt_amount(new_amount)}/mo (+10%)\n\n"
                f"A 10% annual step-up can grow your corpus by *~40% more* over 15 years! 🚀\n\n"
                f"Reply *YES* to confirm or suggest a different amount."
            )
            return {"messages": [msg], "template_name": None}

    lines = ["📈 *Which SIP would you like to step up?*\n"]
    for i, s in enumerate(active_sips, 1):
        new_amount = int(s["amount"] * 1.10)
        lines.append(f"  {i}. {s['fund']} — {fmt_amount(s['amount'])} → {fmt_amount(new_amount)}/mo")
    lines.append("\nReply with the fund name or number.")

    return {"messages": ["\n".join(lines)], "template_name": None}


# -- Helpers -----------------------------------------------------------------

def _next_sip_date(day: int, today: date) -> date:
    """Calculate next SIP debit date."""
    this_month = today.replace(day=min(day, 28))
    if this_month > today:
        return this_month
    # Next month
    if today.month == 12:
        return date(today.year + 1, 1, min(day, 28))
    return date(today.year, today.month + 1, min(day, 28))


def _progress_bar(pct: float) -> str:
    """Unicode progress bar."""
    filled = int(pct / 10)
    empty = 10 - filled
    return "▓" * filled + "░" * empty


def _get_tip(language: str) -> str:
    tips = {
        "en": "💡 You can ask me about your *SIPs*, *goal progress*, or say _\"step up my SIP\"_ to grow your investments faster!",
        "hi": "💡 Aap mujhse apne *SIPs*, *goal progress* ke baare mein pooch sakte hain, ya _\"SIP badhao\"_ bol sakte hain!",
        "hinglish": "💡 Aap mujhse *SIPs*, *goal progress* pooch sakte hain, ya _\"step up my SIP\"_ bol sakte hain!",
    }
    return tips.get(language, tips["en"])


def _no_portfolio_msg(language: str, name: str) -> str:
    msgs = {
        "en": f"Hi {name}! 👋 You don't have any investments with us yet. Would you like me to help you start your investment journey? 🚀",
        "hi": f"Hi {name}! 👋 Aapke paas abhi koi investment nahi hai. Kya main aapko investment start karne mein madad karun? 🚀",
        "hinglish": f"Hi {name}! 👋 Aapke paas abhi koi investment nahi hai. Shall I help you start your investment journey? 🚀",
    }
    return msgs.get(language, msgs["en"])


def _no_sips_msg(language: str) -> str:
    return "You don't have any SIPs set up yet. Would you like me to help you start a SIP? 💪"


def _no_goals_msg(language: str) -> str:
    return "You haven't set up any goals yet. Want me to help you plan one? 🎯"


def _not_registered(language: str) -> dict:
    msgs = {
        "en": "I don't see your account with FundsIndia yet. Would you like to start fresh with a goal plan? 🎯",
        "hi": "Aapka FundsIndia account nahi dikh raha. Kya aap ek goal plan se shuru karna chahenge? 🎯",
        "hinglish": "Aapka FundsIndia account nahi dikh raha. Want to start fresh with a goal plan? 🎯",
    }
    return {"messages": [msgs.get(language, msgs["en"])], "template_name": None}
