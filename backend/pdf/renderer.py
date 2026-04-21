"""PDF renderer — Jinja2 HTML template → PDF via Playwright (Chromium headless)."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime
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


async def generate_portfolio_report_pdf(phone: str) -> str | None:
    """Generate a portfolio report PDF for an existing user.

    Returns the file path, or None if the user has no portfolio on record.
    """
    from backend.data.mock_users import get_user, get_portfolio, get_sips, get_goals

    user = get_user(phone)
    portfolio = get_portfolio(phone)
    if not user or not portfolio:
        return None

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    context = _build_portfolio_context(user, portfolio, get_sips(phone), get_goals(phone))

    template = _jinja_env.get_template("portfolio_report.html")
    html_content = template.render(**context)

    phone_clean = phone.replace("whatsapp:", "").replace("+", "")
    filename = f"portfolio_{phone_clean}_{int(time.time())}.pdf"
    output_path = _OUTPUT_DIR / filename

    t0 = time.monotonic()
    await _render_pdf(html_content, str(output_path))
    logger.info("Portfolio PDF generated: %s (%.1fs)", filename, time.monotonic() - t0)
    return str(output_path)


def _build_portfolio_context(user: dict, portfolio: dict, sips: list | None, goals: list | None) -> dict:
    invested = portfolio["total_invested"]
    current = portfolio["current_value"]
    gain = current - invested
    gain_pct = (gain / invested * 100) if invested else 0

    holdings = []
    for h in portfolio.get("holdings", []):
        h_gain = h["current"] - h["invested"]
        h_pct = (h_gain / h["invested"] * 100) if h["invested"] else 0
        holdings.append({
            "fund": h["fund"],
            "category": h["category"],
            "invested": _fmt_amount(h["invested"]),
            "current": _fmt_amount(h["current"]),
            "gain": _fmt_amount(h_gain),
            "gain_raw": h_gain,
            "gain_pct": f"{h_pct:+.1f}",
        })

    sip_rows = []
    total_monthly = 0
    for s in (sips or []):
        if s["status"] == "active":
            total_monthly += s["amount"]
        sip_rows.append({
            "fund": s["fund"],
            "amount": _fmt_amount(s["amount"]),
            "day": s["day"],
            "started": _fmt_date(s.get("started")),
            "status": s["status"],
        })

    goal_rows = []
    for g in (goals or []):
        goal_rows.append({
            "name": g["name"],
            "target_corpus": _fmt_amount(g["target_corpus"]),
            "achieved": _fmt_amount(g["achieved"]),
            "monthly_sip": _fmt_amount(g["monthly_sip"]),
            "progress_pct": round(g["progress_pct"], 1),
            "target_year": (g.get("target_date") or "")[:4] or "—",
            "status": g["status"],
            "drift_alert": g.get("drift_alert"),
        })

    # Import lazily to avoid hard-wiring service imports at module load.
    from backend.services.consent import TERMS_URL, PRIVACY_URL

    return {
        "user_name": user["name"],
        "joined": _fmt_date(user.get("joined")),
        "risk_profile": user.get("risk_profile", "—"),
        "rm_name": user.get("rm_name", "your advisor"),
        "generated_on": date.today().strftime("%d %b %Y"),
        "total_invested": _fmt_amount(invested),
        "current_value": _fmt_amount(current),
        "total_gain": _fmt_amount(gain),
        "gain_raw": gain,
        "gain_pct": f"{gain_pct:+.1f}",
        "xirr": portfolio.get("xirr", 0),
        "holdings": holdings,
        "sips": sip_rows,
        "total_monthly_sip": _fmt_amount(total_monthly) if total_monthly else "",
        "total_monthly_sip_raw": total_monthly,
        "goals": goal_rows,
        "terms_url": TERMS_URL,
        "privacy_url": PRIVACY_URL,
    }


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        return datetime.strptime(iso, "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return iso


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
