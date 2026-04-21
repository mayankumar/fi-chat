"""T&C disclaimer gate — must be accepted before bot interaction."""
from __future__ import annotations

from backend.services.twilio_sender import TEMPLATE_CONSENT

CONSENT_VERSION = "1.1"

# Legal links surfaced in the consent message.
# Update these if/when FundsIndia provides canonical URLs.
TERMS_URL = "https://www.fundsindia.com/terms"
PRIVACY_URL = "https://www.fundsindia.com/privacy-policy"


_WELCOME_EN = (
    "Hi there 👋  Welcome to *FundsIndia*.\n\n"
    "I'm *Finn* — your personal investment assistant. "
    "I can help you plan goals, review your portfolio, step-up or pause SIPs, "
    "answer mutual-fund questions, and loop in a SEBI-registered advisor whenever you want one.\n\n"
    "Tell me what's on your mind, or just say *Hi* to see what I can do."
)

_TERMS_EN = (
    "*Before we begin* — a quick heads-up:\n\n"
    "• I share educational and informational guidance; for personalised advice our human advisors step in\n"
    "• Mutual-fund investments are subject to market risks — past performance isn't a guarantee of future returns\n"
    "• Your messages are processed securely to power this chat\n\n"
    f"📄  Terms: {TERMS_URL}\n"
    f"🔒  Privacy: {PRIVACY_URL}\n\n"
    "Tap a button below to continue 👇"
)

_WELCOME_HINGLISH = (
    "Hi 👋  *FundsIndia* mein aapka swagat hai.\n\n"
    "Main *Finn* hoon — aapka personal investment assistant. "
    "Main goals plan karne, portfolio review karne, SIP step-up ya pause karne, "
    "mutual-fund doubts clear karne, aur zarurat pade toh SEBI-registered advisor se connect karne mein madad karta hoon.\n\n"
    "Bataiye kya help chahiye, ya sirf *Hi* likhiye."
)

_TERMS_HINGLISH = (
    "*Shuru karne se pehle* — ek quick note:\n\n"
    "• Main educational aur informational guidance deta hoon; personalised advice ke liye humare human advisors available hain\n"
    "• Mutual-fund investments market risks ke adheen hain — past returns future ki guarantee nahi dete\n"
    "• Aapke messages securely process hote hain taaki yeh chat chal sake\n\n"
    f"📄  Terms: {TERMS_URL}\n"
    f"🔒  Privacy: {PRIVACY_URL}\n\n"
    "Neeche button tap karke continue kijiye 👇"
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


def check_consent_reply(message: str) -> bool:
    """Return True if the user's reply accepts consent (either button or typed text).

    Segment detection happens later via phone lookup, so we no longer need to
    thread a self-reported segment through from the button payload.
    """
    msg = message.strip().lower()
    return msg in {
        # "Let's start" button / typed equivalents
        "consent_yes", "yes", "let's start!", "✅ let's start!", "lets start",
        # "I'm a Pro" button / typed equivalents — both buttons accept consent
        "consent_expert", "expert", "i'm a pro", "🔬 i'm a pro", "im a pro",
    }
