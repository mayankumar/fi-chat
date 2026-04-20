"""Firm refusal for stock/equity questions with TTA redirect."""

_RESPONSES = {
    "en": (
        "I appreciate your interest, but I'm not able to provide specific stock recommendations or equity trading advice.\n\n"
        "FundsIndia's strength is in *mutual fund advisory* — we can help you find funds that give you diversified equity exposure.\n\n"
        "If you'd like to discuss equity investments, I can connect you with our advisory team. Just say *'talk to advisor'*."
    ),
    "hi": (
        "आपकी रुचि की सराहना करता हूँ, लेकिन मैं specific stock recommendations या equity trading advice देने में असमर्थ हूँ।\n\n"
        "FundsIndia की विशेषता *mutual fund advisory* में है — हम आपको diversified equity exposure वाले funds खोजने में मदद कर सकते हैं।\n\n"
        "अगर आप equity investments पर चर्चा करना चाहते हैं, तो मैं आपको हमारी advisory team से जोड़ सकता हूँ। बस *'talk to advisor'* कहें।"
    ),
    "hinglish": (
        "Aapki interest ki main qadr karta hoon, lekin main specific stock recommendations ya equity trading advice nahi de sakta.\n\n"
        "FundsIndia ki strength *mutual fund advisory* mein hai — hum aapko diversified equity exposure wale funds dhundhne mein madad kar sakte hain.\n\n"
        "Agar aap equity investments discuss karna chahte hain, toh main aapko hamari advisory team se connect kar sakta hoon. Bas *'talk to advisor'* bolein."
    ),
}


def get_stock_redirect(language: str) -> str:
    return _RESPONSES.get(language, _RESPONSES["en"])
