"""Segment-aware greeting handler — picks menu based on whether the user is new,
active (existing with live SIPs / holdings), or dormant (paused SIPs).

New users see a discovery menu (plan goals / learn / advisor).
Existing users see their personalised action menu plus a quick portfolio snapshot.
Dormant users get a nudge to restart paused SIPs.
"""
from __future__ import annotations

from backend.data.mock_users import get_user, get_portfolio, fmt_amount
from backend.services.twilio_sender import (
    TEMPLATE_GREETING_MENU,
    TEMPLATE_EXISTING_MENU,
    TEMPLATE_DORMANT_MENU,
)

_HINT_EN = "💡 You can also just type what's on your mind — \"step up my SIP\", \"plan for my daughter's college\", \"how's my portfolio?\""
_HINT_HINGLISH = "💡 Ya bas apne sawaal type kariye — \"SIP badhao\", \"bachche ki college planning\", \"portfolio kaisa chal raha hai?\""
_HINT_HI = "💡 आप सीधे सवाल भी पूछ सकते हैं — जैसे \"SIP कैसे बढ़ाऊँ\", \"बच्चों की पढ़ाई की planning\", \"portfolio कैसा है?\""


def get_greeting(segment: "str | None", language: str, phone: str = "") -> dict:
    """Return the post-consent greeting for this user.

    Shape: {"messages": [body, menu_prompt], "template_name": str}
    """
    lang = language if language in ("en", "hi", "hinglish") else "en"
    user = get_user(phone) if phone else None

    # Resolved segment: prefer what's in the user record; fall back to the raw arg; default to new.
    if user:
        seg = user.get("segment", "new")
    else:
        seg = segment if segment in ("new", "active", "dormant") else "new"

    if seg == "active" and user:
        body = _existing_body(user, lang)
        template = TEMPLATE_EXISTING_MENU
    elif seg == "dormant" and user:
        body = _dormant_body(user, lang)
        template = TEMPLATE_DORMANT_MENU
    else:
        body = _new_body(user, lang)
        template = TEMPLATE_GREETING_MENU

    menu_prompt = _menu_prompt(lang, seg) + "\n\n" + _hint(lang)

    return {"messages": [body, menu_prompt], "template_name": template}


# ─── body copy ────────────────────────────────────────────────────────────────

def _new_body(user: "dict | None", lang: str) -> str:
    name = user["name"].split()[0] if user else None
    if lang == "hi":
        hello = f"🎉 {name} जी, स्वागत है!\n\n" if name else "🎉 स्वागत है!\n\n"
        return (
            hello
            + "मैं *Finn* हूँ — FundsIndia पर आपका investment assistant।\n\n"
            + "चाहे पहली बार invest कर रहे हों या wealth grow करनी हो — मैं आपके साथ हूँ। "
            + "Goals plan करने से लेकर mutual funds समझने तक, बस पूछिए 🙌"
        )
    if lang == "hinglish":
        hello = f"🎉 Hi {name}! Welcome to FundsIndia.\n\n" if name else "🎉 Welcome to FundsIndia!\n\n"
        return (
            hello
            + "Main *Finn* hoon — aapka investment assistant.\n\n"
            + "Chahe pehli baar invest kar rahe ho ya wealth grow karni ho — main saath hoon. "
            + "Goals plan karne se lekar mutual funds samajhne tak, bas pooch lijiye 🙌"
        )
    hello = f"🎉 Hi {name}! Welcome to FundsIndia.\n\n" if name else "🎉 Welcome to FundsIndia!\n\n"
    return (
        hello
        + "I'm *Finn* — your investment assistant.\n\n"
        + "Whether you're starting out or looking to grow your wealth, I've got you. "
        + "From goal planning to fund explainers — just ask 🙌"
    )


def _existing_body(user: dict, lang: str) -> str:
    name = user["name"].split()[0]
    snapshot = _portfolio_snapshot(user["phone"], lang)

    if lang == "hi":
        head = f"👋 {name} जी, welcome back!"
        line = "यहाँ आपका latest snapshot है:" if snapshot else "आज कैसे मदद करूँ?"
    elif lang == "hinglish":
        head = f"👋 {name}, welcome back!"
        line = "Yeh raha aapka latest snapshot:" if snapshot else "Aaj kaise madad karun?"
    else:
        head = f"👋 Welcome back, {name}!"
        line = "Here's your latest snapshot:" if snapshot else "How can I help today?"

    body = head + "\n\n" + line
    if snapshot:
        body += "\n\n" + snapshot
    return body


def _dormant_body(user: dict, lang: str) -> str:
    name = user["name"].split()[0]
    if lang == "hi":
        return (
            f"👋 {name} जी, काफ़ी समय बाद!\n\n"
            "आपके SIPs अभी pause हैं — पर market अच्छा move कर रहा है। "
            "वापस start करने में मदद करूँ?"
        )
    if lang == "hinglish":
        return (
            f"👋 {name}, kaafi time baad!\n\n"
            "Aapke SIPs abhi pause hain — aur market acchi move kar raha hai. "
            "Wapas start karne mein help karun?"
        )
    return (
        f"👋 Hi {name} — long time!\n\n"
        "Your SIPs are on pause right now, but the market has been moving. "
        "Want help getting them restarted?"
    )


# ─── helpers ──────────────────────────────────────────────────────────────────

def _portfolio_snapshot(phone: str, lang: str) -> str:
    p = get_portfolio(phone)
    if not p:
        return ""
    gain = p["current_value"] - p["total_invested"]
    gain_pct = (gain / p["total_invested"] * 100) if p["total_invested"] else 0
    sign = "+" if gain >= 0 else ""
    if lang == "hi":
        return (
            f"📊 *Portfolio:* {fmt_amount(p['current_value'])}  "
            f"({sign}{gain_pct:.1f}%)\n"
            f"📈 *XIRR:* {p['xirr']}% प्रति वर्ष"
        )
    return (
        f"📊 *Portfolio:* {fmt_amount(p['current_value'])}  "
        f"({sign}{gain_pct:.1f}%)\n"
        f"📈 *XIRR:* {p['xirr']}% p.a."
    )


def _menu_prompt(lang: str, seg: str) -> str:
    if seg in ("active", "dormant"):
        if lang == "hi":
            return "👇 नीचे से कोई एक चुनिए:"
        if lang == "hinglish":
            return "👇 Neeche se kuch chuniye:"
        return "👇 Pick one below:"
    if lang == "hi":
        return "👇 कहाँ से शुरू करें?"
    if lang == "hinglish":
        return "👇 Kahan se shuru karein?"
    return "👇 Where would you like to start?"


def _hint(lang: str) -> str:
    return {"hi": _HINT_HI, "hinglish": _HINT_HINGLISH}.get(lang, _HINT_EN)
