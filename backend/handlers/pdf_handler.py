"""PDF generation handler — generates and delivers plan PDF via WhatsApp."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from backend.pdf.renderer import generate_pdf, get_pdf_url

logger = logging.getLogger("fi-chat.pdf_handler")

_MAX_PDF_REGEN = 2
_STATIC_PDF_DIR = Path("backend/static/pdfs")


async def handle_pdf_request(session: dict, language: str) -> dict:
    """Generate PDF from current plan and return response with media URL.

    Returns: {"messages": [...], "template_name": str | None, "media_url": str | None}
    """
    flow = session.get("flow_state", {})
    plan = flow.get("current_plan")

    if not plan:
        # No plan generated yet
        msg = _no_plan_msg(language)
        return {"messages": [msg], "template_name": None, "media_url": None}

    # Check regen limit
    regen_count = session.get("pdf_regen_count", 0)
    if regen_count >= _MAX_PDF_REGEN:
        msg = _regen_limit_msg(language)
        return {"messages": [msg], "template_name": "fi_tta_options_v1", "media_url": None}

    # Generate PDF
    phone = session.get("phone", "unknown")
    try:
        pdf_path = await generate_pdf(plan, phone)
    except Exception as exc:
        logger.exception("PDF generation failed: %s", exc)
        msg = _error_msg(language)
        return {"messages": [msg], "template_name": None, "media_url": None}

    # Copy to static dir for serving
    _STATIC_PDF_DIR.mkdir(parents=True, exist_ok=True)
    filename = Path(pdf_path).name
    static_path = _STATIC_PDF_DIR / filename
    shutil.copy2(pdf_path, static_path)

    # Update regen count
    session["pdf_regen_count"] = regen_count + 1

    # Build media URL
    media_url = get_pdf_url(pdf_path)

    msg = _success_msg(language, regen_count + 1)
    return {"messages": [msg], "template_name": None, "media_url": media_url}


def _no_plan_msg(language: str) -> str:
    if language == "hinglish":
        return "Abhi tak koi plan generate nahi hua hai 🤔\n\nPehle apna goal batao, phir main PDF bana dunga! 🎯"
    return "No plan has been generated yet 🤔\n\nTell me about your financial goal first, and I'll create your personalized plan! 🎯"


def _regen_limit_msg(language: str) -> str:
    if language == "hinglish":
        return "Aapne already 2 baar PDF generate kiya hai 📄\n\nAur customization ke liye humara advisor aapse baat kar sakta hai! 🧑‍💼"
    return "You've already generated 2 PDF reports 📄\n\nFor further customization, our expert advisor can help you! 🧑‍💼"


def _error_msg(language: str) -> str:
    if language == "hinglish":
        return "PDF banane mein kuch issue aaya 😅\n\nPlease thodi der mein try karo, ya advisor se baat karo! 🙏"
    return "There was an issue generating your PDF 😅\n\nPlease try again in a moment, or connect with an advisor! 🙏"


def _success_msg(language: str, count: int) -> str:
    remaining = _MAX_PDF_REGEN - count
    if language == "hinglish":
        msg = "Yeh raha aapka personalized investment plan! 📄✨\n\nIse apne advisor ke saath share kar sakte hain."
        if remaining > 0:
            msg += f"\n\n(Aap {remaining} aur baar PDF re-generate kar sakte hain)"
        return msg
    msg = "Here's your personalized investment plan! 📄✨\n\nFeel free to share it with your advisor."
    if remaining > 0:
        msg += f"\n\n(You can regenerate the PDF {remaining} more time{'s' if remaining > 1 else ''})"
    return msg
