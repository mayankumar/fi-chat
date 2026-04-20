"""PDF renderer — Jinja2 HTML template → PDF via Playwright (Chromium headless)."""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from backend.config import get_settings

logger = logging.getLogger("fi-chat.pdf")

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_OUTPUT_DIR = Path("backend/data/pdfs")

_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=True,
)


def _fmt_amount(amt) -> str:
    """Format amount in Indian style (L/Cr)."""
    amt = float(amt)
    if amt >= 10_000_000:
        return f"\u20b9{amt/10_000_000:.1f} Cr"
    if amt >= 100_000:
        return f"\u20b9{amt/100_000:.1f} L"
    return f"\u20b9{amt:,.0f}"


async def generate_pdf(plan: dict, phone: str) -> str:
    """Generate a branded PDF from a plan dict.

    Returns: file path to the generated PDF.
    """
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Prepare template context
    context = _build_context(plan)

    # Render HTML
    template = _jinja_env.get_template("plan_report.html")
    html_content = template.render(**context)

    # Generate PDF via Playwright
    phone_clean = phone.replace("whatsapp:", "").replace("+", "")
    timestamp = int(time.time())
    filename = f"plan_{phone_clean}_{timestamp}.pdf"
    output_path = _OUTPUT_DIR / filename

    t0 = time.monotonic()
    await _render_pdf(html_content, str(output_path))
    logger.info("PDF generated: %s (%.1fs)", filename, time.monotonic() - t0)

    return str(output_path)


async def _render_pdf(html: str, output_path: str) -> None:
    """Render HTML to PDF using Playwright Chromium."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        await page.pdf(
            path=output_path,
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        await browser.close()


def get_pdf_url(file_path: str) -> str:
    """Convert local file path to a publicly accessible URL."""
    settings = get_settings()
    filename = Path(file_path).name
    base = settings.media_base_url.rstrip("/")
    return f"{base}/static/pdfs/{filename}"


def _build_context(plan: dict) -> dict:
    """Build Jinja2 template context from plan dict."""
    alloc = plan["allocation"]["main"]
    funds = plan["recommended_funds"]
    milestones = plan["milestones"]
    stepup = plan["stepup_scenario"]

    # Fund allocation for chart-like display
    fund_items = []
    for f in funds[:8]:
        fund_items.append({
            "name": f["name"],
            "category": f["category"],
            "amount": _fmt_amount(f["monthly_amount"]),
            "raw_amount": f["monthly_amount"],
        })

    # Milestone items
    milestone_items = []
    for m in milestones[:5]:
        milestone_items.append({
            "label": m["label"],
            "target": _fmt_amount(m["target_corpus"]),
            "time": f"{m['time_years']} yrs",
            "sip": _fmt_amount(m["sip_required"]),
        })

    return {
        "goal_name": plan["goal_name"],
        "goal_type": plan["goal_type"],
        "target_amount": _fmt_amount(plan["present_value"]),
        "future_value": _fmt_amount(plan["future_value"]),
        "tenure_years": plan["tenure_years"],
        "risk_label": plan["risk_label"],
        "expected_return": plan["assumptions"]["expected_return"],
        "inflation": plan["assumptions"]["inflation"],
        "sip_required": _fmt_amount(plan["sip_required"]),
        "sip_raw": plan["sip_required"],
        "equity_pct": alloc["equity"],
        "debt_pct": alloc["debt"],
        "gold_pct": alloc["gold"],
        "funds": fund_items,
        "milestones": milestone_items,
        "stepup_base": _fmt_amount(stepup["base_sip"]),
        "stepup_rate": stepup["stepup_rate_pct"],
        "stepup_final": _fmt_amount(stepup.get("final_sip", stepup["base_sip"] * 2)),
        "defaults_used": plan.get("defaults_used", []),
    }
