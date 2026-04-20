"""Main orchestration — generate_plan() ties everything together.

Input:  goal_type, present_value, tenure_years, risk_profile, sip_amount (optional)
Output: Complete InvestmentPlan dict ready for PDF generation.
"""
from __future__ import annotations

import logging

from backend.recommender.constants import (
    GOAL_DEFAULTS, RISK_PROFILES, DEFAULT_RISK_PROFILE,
    ALLOCATION, EQUITY_SUB, DEBT_SUB,
    FUND_MAP, FUND_MAP_AGGRESSIVE, SIMPLE_BLEND,
    DIVERSIFIED_THRESHOLD, SIP_MINIMUM,
)
from backend.recommender.formulas import (
    future_value, sip_required, round_to_100,
    compute_milestones, compute_scenarios, compute_stepup_scenario,
)

logger = logging.getLogger("fi-chat.engine")


def generate_plan(
    goal_type: str,
    present_value: int = None,
    tenure_years: int = None,
    risk_profile: str = None,
    sip_amount: int = None,
    child_age: int = None,
    current_age: int = None,
) -> dict:
    """Generate a complete investment plan.

    Returns a structured dict with all data needed for text summary + PDF.
    """
    # ── 1. Resolve defaults ───────────────────────────────────────────
    goal_type = _normalize_goal_type(goal_type)
    defaults = GOAL_DEFAULTS[goal_type]
    risk = risk_profile or DEFAULT_RISK_PROFILE
    risk_info = RISK_PROFILES[risk]
    annual_return = risk_info["annual_return"]

    # Tenure
    if tenure_years is None:
        if goal_type == "child_education" and child_age is not None:
            tenure_years = max(1, 18 - child_age)
        elif goal_type == "retirement" and current_age is not None:
            tenure_years = max(1, defaults["retirement_age"] - current_age)
        else:
            tenure_years = defaults["tenure_years"]

    # Present value
    if present_value is None:
        present_value = defaults["present_value"]

    inflation = defaults["inflation"]

    # ── 2. Goal math ──────────────────────────────────────────────────
    fv = future_value(present_value, inflation, tenure_years)
    months = tenure_years * 12
    vanilla_sip = round_to_100(sip_required(fv, annual_return, months))
    real_value = present_value  # what FV means in today's money

    # If user specified a SIP amount, use it (they want to know timeline)
    user_sip = sip_amount

    # ── 3. Milestones, scenarios, step-up ─────────────────────────────
    milestones = compute_milestones(fv, tenure_years, annual_return)
    scenarios = compute_scenarios(fv, annual_return)
    stepup = compute_stepup_scenario(fv, annual_return, tenure_years)

    # ── 4. Allocation ─────────────────────────────────────────────────
    effective_sip = user_sip or vanilla_sip
    alloc = _compute_allocation(risk, effective_sip)

    # ── 5. Fund selection ─────────────────────────────────────────────
    funds = _select_funds(risk, effective_sip, alloc)

    # ── 6. Defaults tracking ──────────────────────────────────────────
    defaults_used = []
    if risk_profile is None:
        defaults_used.append("Risk profile: Moderate (default)")
    if sip_amount is None:
        defaults_used.append(f"SIP amount: ₹{vanilla_sip:,}/month (calculated)")
    if present_value == defaults.get("present_value"):
        defaults_used.append(f"Target corpus: ₹{present_value:,} (default for {goal_type})")

    logger.info("Plan generated: goal=%s, FV=₹%.0f, SIP=₹%d, risk=%s, tenure=%dy",
                goal_type, fv, vanilla_sip, risk, tenure_years)

    return {
        "goal_type": goal_type,
        "goal_name": _goal_display_name(goal_type),
        "present_value": present_value,
        "future_value": round(fv),
        "tenure_years": tenure_years,
        "inflation_rate": inflation,
        "risk_profile": risk,
        "risk_label": risk_info["label"],
        "expected_return": annual_return,
        "sip_required": vanilla_sip,
        "user_sip": user_sip,
        "real_value_at_maturity": real_value,
        "allocation": alloc,
        "recommended_funds": funds,
        "milestones": milestones,
        "scenarios": scenarios,
        "stepup_scenario": stepup,
        "defaults_used": defaults_used,
        "assumptions": {
            "inflation": f"{inflation*100:.0f}%",
            "expected_return": f"{annual_return*100:.0f}%",
            "risk_profile": risk_info["label"],
        },
    }


# ── Internals ─────────────────────────────────────────────────────────

def _normalize_goal_type(raw: str) -> str:
    raw = raw.lower().strip()
    if any(k in raw for k in ("retire", "old age", "post-60", "pension")):
        return "retirement"
    if any(k in raw for k in ("child", "kid", "son", "daughter", "education",
                               "college", "school", "university")):
        return "child_education"
    return "wealth_creation"


def _goal_display_name(goal_type: str) -> str:
    return {
        "retirement": "Retirement Planning",
        "child_education": "Child's Education",
        "wealth_creation": "Wealth Creation",
    }.get(goal_type, "Wealth Creation")


def _compute_allocation(risk: str, sip: int) -> dict:
    """Return allocation breakdown with percentages and amounts."""
    main = ALLOCATION[risk]
    equity_sub = EQUITY_SUB[risk]
    debt_sub = DEBT_SUB[risk]

    is_diversified = sip >= DIVERSIFIED_THRESHOLD

    result = {
        "is_diversified": is_diversified,
        "main": {k: round(v * 100) for k, v in main.items()},
        "equity_sub": {k: round(v * 100) for k, v in equity_sub.items()},
        "debt_sub": {k: round(v * 100) for k, v in debt_sub.items()},
        "amounts": {},
    }

    if is_diversified:
        # Full diversified allocation
        for slot, pct in equity_sub.items():
            if pct > 0:
                result["amounts"][slot] = round_to_100(sip * pct)
        for slot, pct in debt_sub.items():
            if pct > 0:
                result["amounts"][slot] = round_to_100(sip * pct)
        if main["gold"] > 0:
            result["amounts"]["gold"] = round_to_100(sip * main["gold"])
    else:
        # Simple blend
        blend = SIMPLE_BLEND[risk]
        if blend["equity"] > 0:
            result["amounts"]["equity_blend"] = round_to_100(sip * blend["equity"])
        if blend.get("debt", 0) > 0:
            result["amounts"]["debt_blend"] = round_to_100(sip * blend["debt"])

    return result


def _select_funds(risk: str, sip: int, alloc: dict) -> list:
    """Select specific funds with per-fund amounts."""
    fund_map = dict(FUND_MAP)
    if risk == "aggressive":
        fund_map.update(FUND_MAP_AGGRESSIVE)

    is_diversified = alloc["is_diversified"]
    funds = []

    # Map slot → fund name and category
    _SLOT_META = {
        "five_finger":   ("five_finger_quality", "five_finger_value",
                          "five_finger_garp", "five_finger_midcap",
                          "five_finger_momentum"),
        "global":        ("global",),
        "high_risk":     ("high_risk",),
        "core":          ("debt_core",),
        "debt_plus":     ("debt_plus",),
        "gold":          ("gold",),
        "equity_blend":  ("equity_blend",),
        "debt_blend":    ("debt_blend",),
    }

    _SLOT_CATEGORY = {
        "debt_core": "Debt",
        "debt_plus": "Debt+",
        "gold": "Gold",
        "five_finger_quality": "Equity - Quality",
        "five_finger_value": "Equity - Value",
        "five_finger_garp": "Equity - GARP",
        "five_finger_midcap": "Equity - Mid Cap",
        "five_finger_momentum": "Equity - Momentum",
        "global": "Equity - Global",
        "high_risk": "Equity - Thematic",
        "equity_blend": "Equity",
        "debt_blend": "Debt",
    }

    amounts = alloc["amounts"]

    if is_diversified:
        # 5 Finger: split equally among 5 funds
        ff_total = amounts.get("five_finger", 0)
        if ff_total > 0:
            per_fund = round_to_100(ff_total / 5)
            for slot in _SLOT_META["five_finger"]:
                funds.append({
                    "name": fund_map[slot],
                    "category": _SLOT_CATEGORY[slot],
                    "monthly_amount": per_fund,
                })

        # Other equity slots
        for slot_key in ("global", "high_risk"):
            amt = amounts.get(slot_key, 0)
            if amt > 0:
                fund_slot = _SLOT_META[slot_key][0]
                funds.append({
                    "name": fund_map[fund_slot],
                    "category": _SLOT_CATEGORY[fund_slot],
                    "monthly_amount": amt,
                })

        # Debt slots
        for slot_key in ("core", "debt_plus"):
            amt = amounts.get(slot_key, 0)
            if amt > 0:
                fund_slot = _SLOT_META[slot_key][0]
                funds.append({
                    "name": fund_map[fund_slot],
                    "category": _SLOT_CATEGORY[fund_slot],
                    "monthly_amount": amt,
                })

        # Gold
        amt = amounts.get("gold", 0)
        if amt > 0:
            funds.append({
                "name": fund_map["gold"],
                "category": "Gold",
                "monthly_amount": amt,
            })
    else:
        # Simple blend
        for slot_key in ("equity_blend", "debt_blend"):
            amt = amounts.get(slot_key, 0)
            if amt > 0:
                fund_slot = slot_key
                funds.append({
                    "name": fund_map[fund_slot],
                    "category": _SLOT_CATEGORY[fund_slot],
                    "monthly_amount": amt,
                })

    return funds
