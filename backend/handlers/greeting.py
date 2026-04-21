"""Segment-aware greeting handler with action menu buttons."""
from __future__ import annotations

from backend.data.mock_users import get_user
from backend.services.twilio_sender import TEMPLATE_GREETING_MENU

# -- Greeting messages (sent as first block) --

_GREETINGS = {
    "new": {
        "en": (
            "🎉 Awesome, let's get started!\n\n"
            "I'm *Finn* — your AI investment buddy at FundsIndia.\n\n"
            "Whether you're a first-time investor or looking to grow your wealth, "
            "I've got you covered 💪"
        ),
        "hi": (
            "🎉 चलिए शुरू करते हैं!\n\n"
            "मैं *Finn* हूँ — FundsIndia पर आपका AI investment buddy।\n\n"
            "चाहे आप पहली बार invest कर रहे हों या अपनी wealth बढ़ाना चाहते हों, "
            "मैं आपके साथ हूँ 💪"
        ),
        "hinglish": (
            "🎉 Awesome, chaliye shuru karte hain!\n\n"
            "Main *Finn* hoon — FundsIndia par aapka AI investment buddy.\n\n"
            "Chahe aap pehli baar invest kar rahe ho ya wealth grow karna chahte ho, "
            "main aapke saath hoon 💪"
        ),
    },
    "active": {
        "en": (
            "🎉 Great to have you back!\n\n"
            "Welcome back, pro! I'm *Finn* — ready to dive deeper into your investment journey 📈"
        ),
        "hi": (
            "🎉 आपका फिर से स्वागत है!\n\n"
            "Welcome back, pro! मैं *Finn* — आपकी investment journey में और गहराई से मदद करने को तैयार हूँ 📈"
        ),
        "hinglish": (
            "🎉 Welcome back, pro!\n\n"
            "Main *Finn* hoon — aapki investment journey mein aur deep dive karne ke liye ready 📈"
        ),
    },
}

# -- Action menu (sent as second block with quick-reply buttons) --

_MENU = {
    "en": "What would you like to do today? 👇",
    "hi": "आज आप क्या करना चाहेंगे? 👇",
    "hinglish": "Aaj aap kya karna chahenge? 👇",
}


def get_greeting(segment: "str | None", language: str, phone: str = "") -> dict:
    """Return structured greeting: {"messages": [...], "template_name": str}

    If the phone belongs to a known user, personalize with their name.
    """
    seg = segment if segment in _GREETINGS else "new"
    lang = language if language in ("en", "hi", "hinglish") else "en"

    greeting_text = _GREETINGS[seg][lang]

    # Personalize for known users
    if phone:
        user = get_user(phone)
        if user:
            name = user["name"].split()[0]  # first name
            greeting_text = _personalized_greeting(name, lang, seg)

    return {
        "messages": [greeting_text, _MENU[lang]],
        "template_name": TEMPLATE_GREETING_MENU,
    }


def _personalized_greeting(name: str, language: str, segment: str) -> str:
    """Generate personalized greeting for known users."""
    if segment == "active":
        greetings = {
            "en": (
                f"🎉 Welcome back, *{name}*! Great to see you.\n\n"
                f"I'm *Finn* — your AI investment buddy at FundsIndia.\n\n"
                f"Your portfolio is looking good! How can I help you today? 📈"
            ),
            "hi": (
                f"🎉 *{name}* ji, welcome back!\n\n"
                f"Main *Finn* hoon — FundsIndia par aapka AI investment buddy.\n\n"
                f"Aapka portfolio accha chal raha hai! Aaj kaise madad karun? 📈"
            ),
            "hinglish": (
                f"🎉 *{name}*, welcome back!\n\n"
                f"Main *Finn* hoon — FundsIndia par aapka AI investment buddy.\n\n"
                f"Aapka portfolio accha chal raha hai! How can I help today? 📈"
            ),
        }
    elif segment == "dormant":
        greetings = {
            "en": (
                f"👋 Hey *{name}*! Long time no see!\n\n"
                f"I'm *Finn* — your AI investment buddy at FundsIndia.\n\n"
                f"I noticed your SIPs are paused. Want to get back on track? 💪"
            ),
            "hi": (
                f"👋 *{name}* ji! Bahut din ho gaye!\n\n"
                f"Main *Finn* hoon — FundsIndia par aapka AI investment buddy.\n\n"
                f"Aapke SIPs pause hain. Kya wapas start karein? 💪"
            ),
            "hinglish": (
                f"👋 *{name}*! Bahut din ho gaye!\n\n"
                f"Main *Finn* hoon — FundsIndia par aapka AI investment buddy.\n\n"
                f"Aapke SIPs pause hain. Want to restart? 💪"
            ),
        }
    else:  # new
        greetings = {
            "en": (
                f"🎉 Hi *{name}*! Welcome to FundsIndia.\n\n"
                f"I'm *Finn* — your AI investment buddy.\n\n"
                f"Whether you're a first-time investor or looking to grow your wealth, "
                f"I've got you covered 💪"
            ),
            "hi": (
                f"🎉 *{name}* ji! FundsIndia mein aapka swagat hai.\n\n"
                f"Main *Finn* hoon — aapka AI investment buddy.\n\n"
                f"Chahe aap pehli baar invest kar rahe ho ya wealth grow karna chahte ho, "
                f"main aapke saath hoon 💪"
            ),
            "hinglish": (
                f"🎉 Hi *{name}*! Welcome to FundsIndia.\n\n"
                f"Main *Finn* hoon — aapka AI investment buddy.\n\n"
                f"Chahe pehli baar invest karna ho ya wealth grow karna ho, "
                f"main aapke saath hoon 💪"
            ),
        }
    return greetings.get(language, greetings["en"])
