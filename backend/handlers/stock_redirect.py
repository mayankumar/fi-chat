"""Firm refusal for stock/equity questions with TTA redirect buttons."""
from __future__ import annotations

from backend.services.twilio_sender import TEMPLATE_STOCK_REDIRECT

_RESPONSES = {
    "en": (
        "I appreciate the interest! 🙌\n\n"
        "However, I specialize in *mutual funds & goal-based investing* — "
        "I'm not able to help with specific stock picks or equity trading.\n\n"
        "For *diversified equity exposure*, mutual funds are a great option! 📈\n"
        "Or I can connect you with our *expert advisory team* for equity guidance."
    ),
    "hi": (
        "आपकी रुचि की सराहना करता हूँ! 🙌\n\n"
        "लेकिन मेरी विशेषता *mutual funds और goal-based investing* में है — "
        "specific stock picks या equity trading में मैं मदद नहीं कर पाऊंगा।\n\n"
        "Diversified equity exposure के लिए mutual funds बेहतरीन option है! 📈\n"
        "या मैं आपको हमारी *expert advisory team* से connect करा सकता हूँ।"
    ),
    "hinglish": (
        "Interest ke liye thanks! 🙌\n\n"
        "Lekin meri specialty *mutual funds aur goal-based investing* mein hai — "
        "specific stock picks ya equity trading mein main help nahi kar paunga.\n\n"
        "Diversified equity exposure ke liye mutual funds great option hai! 📈\n"
        "Ya main aapko hamari *expert advisory team* se connect kara sakta hoon."
    ),
}


def get_stock_redirect(language: str) -> dict:
    """Return structured response with quick-reply buttons."""
    text = _RESPONSES.get(language, _RESPONSES["en"])
    return {
        "messages": [text],
        "template_name": TEMPLATE_STOCK_REDIRECT,
    }
