"""Talk-to-advisor handoff handler."""

_RESPONSES = {
    "en": (
        "I'll connect you with our advisory team! 📞\n\n"
        "Here are your options:\n"
        "1️⃣ *Call us*: 044-4032 4444 (Mon-Sat, 9AM-6PM)\n"
        "2️⃣ *Request callback*: Our advisor will call you within 2 hours\n"
        "3️⃣ *Email*: advisory@fundsindia.com\n\n"
        "Reply with 1, 2, or 3 to proceed."
    ),
    "hi": (
        "मैं आपको हमारी advisory team से जोड़ता हूँ! 📞\n\n"
        "आपके विकल्प:\n"
        "1️⃣ *कॉल करें*: 044-4032 4444 (सोम-शनि, सुबह 9-शाम 6)\n"
        "2️⃣ *कॉलबैक अनुरोध*: हमारे advisor 2 घंटे में कॉल करेंगे\n"
        "3️⃣ *ईमेल*: advisory@fundsindia.com\n\n"
        "आगे बढ़ने के लिए 1, 2, या 3 reply करें।"
    ),
    "hinglish": (
        "Main aapko hamari advisory team se connect karta hoon! 📞\n\n"
        "Aapke options:\n"
        "1️⃣ *Call karein*: 044-4032 4444 (Mon-Sat, 9AM-6PM)\n"
        "2️⃣ *Callback request*: Hamara advisor 2 ghante mein call karega\n"
        "3️⃣ *Email*: advisory@fundsindia.com\n\n"
        "Aage badhne ke liye 1, 2, ya 3 reply karein."
    ),
}


def get_tta_response(language: str) -> str:
    return _RESPONSES.get(language, _RESPONSES["en"])
