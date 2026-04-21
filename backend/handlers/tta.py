"""Talk-to-advisor handoff handler — auto-confirms a callback within 10 minutes."""
from __future__ import annotations

_CALLBACK_RESPONSE = {
    "en": (
        "✅ Got it! I've arranged a callback for you.\n\n"
        "📞 Our advisor will call you back within *10 minutes*.\n\n"
        "Sit tight — help is on the way! 🚀"
    ),
    "hi": (
        "✅ Samajh gaya! Maine aapke liye callback arrange kar diya hai.\n\n"
        "📞 Hamara advisor aapko *10 minute* mein call karega.\n\n"
        "Bas thodi der! 🚀"
    ),
    "hinglish": (
        "✅ Done! Maine aapke liye callback arrange kar diya hai.\n\n"
        "📞 Hamara advisor aapko *10 minute* mein call karega.\n\n"
        "Bas thodi der — help on the way! 🚀"
    ),
}


def get_tta_response(language: str) -> dict:
    """Auto-confirm a 10-minute callback. No menu, no follow-up choice needed."""
    lang = language if language in _CALLBACK_RESPONSE else "en"
    return {
        "messages": [_CALLBACK_RESPONSE[lang]],
        "template_name": None,
    }


def get_tta_followup(selection: str, language: str) -> str | None:
    """Back-compat shim — legacy menu selections now all map to the same callback
    confirmation, since we no longer show the menu. Returns None for unknown input
    so the main pipeline can fall through to normal intent routing."""
    lang = language if language in _CALLBACK_RESPONSE else "en"
    legacy_selections = {
        "tta_call", "tta_callback", "tta_email",
        "call us now", "📞 call us now",
        "request callback", "🔙 request callback",
        "send email", "✉️ send email",
        "1", "2", "3",
    }
    if selection in legacy_selections:
        return _CALLBACK_RESPONSE[lang]
    return None
