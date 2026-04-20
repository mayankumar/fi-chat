"""T&C disclaimer gate — must be accepted before bot interaction."""

from typing import Optional

CONSENT_VERSION = "1.0"

_DISCLAIMER_EN = """Welcome to *FundsIndia AI Advisory* 🤖

Before we begin, please note:

• I am an AI assistant, not a SEBI-registered advisor
• My suggestions are educational and informational only
• For investment decisions, consult a qualified financial advisor
• Past performance does not guarantee future results
• Mutual fund investments are subject to market risks

By continuing, you agree to these terms.

👉 Reply *YES* to continue
👉 Reply *EXPERT* if you're a financial professional"""

_DISCLAIMER_HINGLISH = """*FundsIndia AI Advisory* mein aapka swagat hai 🤖

Shuru karne se pehle, yeh dhyan rakhein:

• Main ek AI assistant hoon, SEBI-registered advisor nahi
• Mere suggestions sirf educational aur informational hain
• Investment decisions ke liye qualified financial advisor se baat karein
• Past performance future results ki guarantee nahi deta
• Mutual fund investments market risks ke adheen hain

Aage badhne ke liye in terms ko accept karein.

👉 *YES* reply karein continue karne ke liye
👉 *EXPERT* reply karein agar aap financial professional hain"""


def get_disclaimer(language: str) -> str:
    if language in ("hi", "hinglish"):
        return _DISCLAIMER_HINGLISH
    return _DISCLAIMER_EN


def check_consent_reply(message: str) -> Optional[dict]:
    """Check if message is a consent reply. Returns segment info or None."""
    msg = message.strip().upper()

    if msg == "YES":
        return {"accepted": True, "segment": "new"}
    if msg == "EXPERT":
        return {"accepted": True, "segment": "active"}

    return None
