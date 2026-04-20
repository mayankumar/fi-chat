"""Segment-aware greeting handler."""
from __future__ import annotations

_GREETINGS = {
    "new": {
        "en": "Hello! Welcome to FundsIndia 👋\n\nI'm Finn, your AI financial assistant. I can help you with mutual funds, SIPs, goal planning, and more.\n\nWhat would you like to know?",
        "hi": "नमस्ते! FundsIndia में आपका स्वागत है 👋\n\nमैं Finn हूँ, आपका AI financial assistant। मैं mutual funds, SIP, goal planning और बहुत कुछ में आपकी मदद कर सकता हूँ।\n\nआप क्या जानना चाहेंगे?",
        "hinglish": "Hello! FundsIndia mein aapka swagat hai 👋\n\nMain Finn hoon, aapka AI financial assistant. Main mutual funds, SIP, goal planning aur bahut kuch mein help kar sakta hoon.\n\nAap kya jaanna chahenge?",
    },
    "active": {
        "en": "Welcome back! 👋\n\nI'm Finn, your AI financial assistant. How can I help you today?",
        "hi": "वापस आने पर स्वागत है! 👋\n\nमैं Finn हूँ। आज मैं आपकी कैसे मदद कर सकता हूँ?",
        "hinglish": "Welcome back! 👋\n\nMain Finn hoon. Aaj main aapki kaise help kar sakta hoon?",
    },
}


def get_greeting(segment: "str | None", language: str) -> str:
    seg = segment if segment in _GREETINGS else "new"
    lang = language if language in ("en", "hi", "hinglish") else "en"
    return _GREETINGS[seg][lang]
