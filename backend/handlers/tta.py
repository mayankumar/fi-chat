"""Talk-to-advisor handoff handler with quick-reply buttons."""
from __future__ import annotations

from backend.services.twilio_sender import TEMPLATE_TTA

_RESPONSES = {
    "en": (
        "Absolutely! 🤝 Our advisory team is here for you.\n\n"
        "How would you like to connect?"
    ),
    "hi": (
        "बिल्कुल! 🤝 हमारी advisory team आपके लिए तैयार है।\n\n"
        "आप कैसे connect करना चाहेंगे?"
    ),
    "hinglish": (
        "Bilkul! 🤝 Hamari advisory team aapke liye ready hai.\n\n"
        "Aap kaise connect karna chahenge?"
    ),
}

_CALL_RESPONSE = {
    "en": "📞 You can reach our advisors at *044-4032 4444*\n⏰ Mon-Sat, 9AM-6PM\n\nThey'll be happy to help! 😊",
    "hi": "📞 Humare advisors se baat karein: *044-4032 4444*\n⏰ Mon-Sat, 9AM-6PM\n\nWoh aapki madad karne ko taiyaar hain! 😊",
    "hinglish": "📞 Humare advisors se baat karein: *044-4032 4444*\n⏰ Mon-Sat, 9AM-6PM\n\nWoh aapki madad karne ko ready hain! 😊",
}

_CALLBACK_RESPONSE = {
    "en": "✅ Got it! Our advisor will call you back within *2 hours* during business hours.\n\nSit tight, help is on the way! 🚀",
    "hi": "✅ Samajh gaya! Hamara advisor aapko *2 ghante* mein call karega (business hours mein).\n\nHelp aa rahi hai! 🚀",
    "hinglish": "✅ Done! Hamara advisor aapko *2 ghante* mein call karega (business hours mein).\n\nHelp on the way! 🚀",
}

_EMAIL_RESPONSE = {
    "en": "✉️ Email us at *advisory@fundsindia.com*\n\nOur team typically responds within *24 hours*. 📩",
    "hi": "✉️ Humein email karein: *advisory@fundsindia.com*\n\nHamari team *24 ghante* mein reply karti hai. 📩",
    "hinglish": "✉️ Humein email karein: *advisory@fundsindia.com*\n\nHamari team *24 ghante* mein reply karti hai. 📩",
}


def get_tta_response(language: str) -> dict:
    """Return structured response with quick-reply buttons."""
    text = _RESPONSES.get(language, _RESPONSES["en"])
    return {
        "messages": [text],
        "template_name": TEMPLATE_TTA,
    }


def get_tta_followup(selection: str, language: str) -> str:
    """Handle TTA sub-selection (call/callback/email) from button tap or typed text."""
    lang = language if language in ("en", "hi", "hinglish") else "en"

    if selection in ("tta_call", "1", "call us now", "📞 call us now"):
        return _CALL_RESPONSE[lang]
    if selection in ("tta_callback", "2", "request callback", "🔙 request callback"):
        return _CALLBACK_RESPONSE[lang]
    if selection in ("tta_email", "3", "send email", "✉️ send email"):
        return _EMAIL_RESPONSE[lang]

    return _CALL_RESPONSE[lang]
