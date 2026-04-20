"""T&C disclaimer gate — must be accepted before bot interaction."""
from __future__ import annotations

from typing import Optional

from backend.services.twilio_sender import TEMPLATE_CONSENT

CONSENT_VERSION = "1.0"

# -- Disclaimer: sent as 2 separate messages + quick-reply buttons --

_WELCOME_EN = (
    "Hey there! 👋 Welcome to *FundsIndia* — India's trusted investment platform.\n\n"
    "I'm *Finn*, your personal AI investment assistant 🤖✨\n\n"
    "I'm here to help you plan your financial goals, understand mutual funds, "
    "and connect you with our *SEBI-registered advisors* whenever you need expert guidance."
)

_TERMS_EN = (
    "📋 *Quick note before we start:*\n\n"
    "• I provide *educational & informational* guidance\n"
    "• For personalized advice, our *expert advisors* are just a tap away 🧑‍💼\n"
    "• Mutual fund investments are subject to market risks\n"
    "• Past performance ≠ future returns\n\n"
    "Your trust matters to us 🤝"
)

_WELCOME_HINGLISH = (
    "Hey! 👋 *FundsIndia* mein aapka swagat hai — India ka trusted investment platform.\n\n"
    "Main *Finn* hoon, aapka personal AI investment assistant 🤖✨\n\n"
    "Main aapko financial goals plan karne, mutual funds samajhne, "
    "aur humare *SEBI-registered advisors* se connect karne mein madad karunga."
)

_TERMS_HINGLISH = (
    "📋 *Shuru karne se pehle:*\n\n"
    "• Main *educational aur informational* guidance deta hoon\n"
    "• Expert advice ke liye humare *advisors* bas ek tap door hain 🧑‍💼\n"
    "• Mutual fund investments market risks ke adheen hain\n"
    "• Past performance = future returns nahi\n\n"
    "Aapka trust humara sabse bada asset hai 🤝"
)


def get_disclaimer(language: str) -> dict:
    """Return structured disclaimer: {"messages": [...], "template_name": str}"""
    if language in ("hi", "hinglish"):
        return {
            "messages": [_WELCOME_HINGLISH, _TERMS_HINGLISH],
            "template_name": TEMPLATE_CONSENT,
        }
    return {
        "messages": [_WELCOME_EN, _TERMS_EN],
        "template_name": TEMPLATE_CONSENT,
    }


def check_consent_reply(message: str) -> Optional[dict]:
    """Check if message is a consent reply (button tap or typed text)."""
    msg = message.strip().lower()

    # Button payloads (from Content API ButtonPayload)
    if msg in ("consent_yes", "yes", "let's start!", "✅ let's start!", "lets start"):
        return {"accepted": True, "segment": "new"}
    if msg in ("consent_expert", "expert", "i'm a pro", "🔬 i'm a pro", "im a pro"):
        return {"accepted": True, "segment": "active"}

    return None
