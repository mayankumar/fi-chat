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
    future_value, sip_required, sip_future_value, round_to_100,
    compute_milestones, compute_scenarios, compute_stepup_scenario,
)

logger = logging.getLogger("fi-chat.engine")


def generate_plan(
    goal_type: str,
    present_value: int = None,
    tenure_years: int = None,
    risk_profile: str = None,
    sip_amount: int = None,
    lumpsum_amount: int = None,
    child_age: int = None,
    current_age: int = None,
) -> dict:
    """Generate a complete investment plan.

    Returns a structured dict with all data needed for text summary + PDF.
    """
    # ── 1. Resolve defaults ───────────────────────────────────────────
    goal_type = _normalize_goal_type(goal_type)
    defaults = GOAL_DEFAULTS[goal_type]
    risk = (risk_profile or DEFAULT_RISK_PROFILE).lower()
    if risk not in RISK_PROFILES:
        risk = DEFAULT_RISK_PROFILE
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

    inflation = defaults["inflation"]
    months = tenure_years * 12

    lumpsum = int(lumpsum_amount) if lumpsum_amount else 0
    user_sip = int(sip_amount) if sip_amount else 0

    # ── 2. Determine mode: target-based vs. projection ───────────────
    # Target mode: user gave a target corpus OR gave nothing (use goal default).
    # Projection mode: user gave only lumpsum and/or SIP, no target → show what that grows to.
    explicit_target = present_value is not None
    mode = "target" if (explicit_target or (lumpsum == 0 and user_sip == 0)) else "projection"

    if mode == "target":
        if present_value is None:
            present_value = defaults["present_value"]
        fv = future_value(present_value, inflation, tenure_years)
        lumpsum_fv = lumpsum * ((1 + annual_return) ** tenure_years) if lumpsum > 0 else 0
        user_sip_fv = sip_future_value(user_sip, annual_return, months) if user_sip > 0 else 0
        remaining_fv = max(0.0, fv - lumpsum_fv - user_sip_fv)
        vanilla_sip = round_to_100(sip_required(remaining_fv, annual_return, months)) if remaining_fv > 0 else 0
    else:
        # Projection — user asked "what does my money grow to?"
        lumpsum_fv = lumpsum * ((1 + annual_return) ** tenure_years) if lumpsum > 0 else 0
        user_sip_fv = sip_future_value(user_sip, annual_return, months) if user_sip > 0 else 0
        fv = lumpsum_fv + user_sip_fv
        # "Present value" becomes the total principal actually invested.
        present_value = lumpsum + (user_sip * months)
        remaining_fv = 0.0
        vanilla_sip = 0

    real_value = present_value

    # ── 3. Milestones, scenarios, step-up ─────────────────────────────
    # Milestones/scenarios/step-up only make sense in target mode where there's
    # a gap the SIP must fill. In projection mode we leave them empty.
    if mode == "target":
        sip_target_fv = remaining_fv if (lumpsum > 0 or user_sip > 0) else fv
        milestones = compute_milestones(sip_target_fv, tenure_years, annual_return)
        scenarios = compute_scenarios(sip_target_fv, annual_return)
        stepup = compute_stepup_scenario(sip_target_fv, annual_return, tenure_years)
    else:
        milestones = []
        scenarios = []
        stepup = {
            "base_sip": 0,
            "stepup_rate_pct": 0,
            "tenure_years": tenure_years,
            "target_fv": round(fv),
        }

    # ── 4. Allocation (covers both SIP and lumpsum) ───────────────────
    effective_sip = user_sip or vanilla_sip
    alloc = _compute_allocation(risk, effective_sip, lumpsum)

    # ── 5. Fund selection ─────────────────────────────────────────────
    funds = _select_funds(risk, alloc)

    # ── 6. Defaults tracking ──────────────────────────────────────────
    defaults_used = []
    if risk_profile is None:
        defaults_used.append(f"Risk profile: {risk_info['label']} (inferred)")
    if mode == "target" and sip_amount is None and lumpsum == 0:
        defaults_used.append(f"SIP amount: ₹{vanilla_sip:,}/month (calculated)")
    if mode == "target" and not explicit_target:
        defaults_used.append(f"Target corpus: ₹{present_value:,} (default for {goal_type})")

    logger.info(
        "Plan generated: mode=%s, goal=%s, FV=₹%.0f, SIP=₹%d, lumpsum=₹%d, risk=%s, tenure=%dy",
        mode, goal_type, fv, vanilla_sip, lumpsum, risk, tenure_years,
    )

    return {
        "mode": mode,
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
        "user_sip": user_sip if user_sip else None,
        "user_sip_future_value": round(user_sip_fv) if user_sip else 0,
        "lumpsum_amount": lumpsum,
        "lumpsum_future_value": round(lumpsum_fv),
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


def _compute_allocation(risk: str, sip: int, lumpsum: int = 0) -> dict:
    """Return allocation breakdown with percentages and both SIP + lumpsum amounts.

    Diversification is triggered when either the SIP or lumpsum is large enough
    to spread across the full fund lineup. A lumpsum of ≥ 5× the SIP diversified
    threshold (₹1L by default) is treated as "diversifiable".
    """
    main = ALLOCATION[risk]
    equity_sub = EQUITY_SUB[risk]
    debt_sub = DEBT_SUB[risk]

    lumpsum_diversified_threshold = DIVERSIFIED_THRESHOLD * 5
    is_diversified = (
        sip >= DIVERSIFIED_THRESHOLD or lumpsum >= lumpsum_diversified_threshold
    )

    result = {
        "is_diversified": is_diversified,
        "main": {k: round(v * 100) for k, v in main.items()},
        "equity_sub": {k: round(v * 100) for k, v in equity_sub.items()},
        "debt_sub": {k: round(v * 100) for k, v in debt_sub.items()},
        "monthly_amounts": {},
        "lumpsum_amounts": {},
    }

    def _apply(principal: int, bucket: str) -> None:
        if principal <= 0:
            return
        if is_diversified:
            for slot, pct in equity_sub.items():
                if pct > 0:
                    result[bucket][slot] = round_to_100(principal * pct)
            for slot, pct in debt_sub.items():
                if pct > 0:
                    result[bucket][slot] = round_to_100(principal * pct)
            if main["gold"] > 0:
                result[bucket]["gold"] = round_to_100(principal * main["gold"])
        else:
            blend = SIMPLE_BLEND[risk]
            if blend["equity"] > 0:
                result[bucket]["equity_blend"] = round_to_100(principal * blend["equity"])
            if blend.get("debt", 0) > 0:
                result[bucket]["debt_blend"] = round_to_100(principal * blend["debt"])

    _apply(sip, "monthly_amounts")
    _apply(lumpsum, "lumpsum_amounts")

    # Backwards compat: legacy "amounts" key still points to the monthly breakdown.
    result["amounts"] = result["monthly_amounts"]

    return result


# Fund slot metadata shared by _select_funds
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


def _select_funds(risk: str, alloc: dict) -> list:
    """Return per-fund allocations with both monthly_amount and lumpsum_amount."""
    fund_map = dict(FUND_MAP)
    if risk == "aggressive":
        fund_map.update(FUND_MAP_AGGRESSIVE)

    is_diversified = alloc["is_diversified"]
    monthly = alloc.get("monthly_amounts", {})
    lump = alloc.get("lumpsum_amounts", {})

    def _m(slot: str) -> int:
        return int(monthly.get(slot, 0))

    def _l(slot: str) -> int:
        return int(lump.get(slot, 0))

    funds: list[dict] = []

    if is_diversified:
        # 5 Finger — split evenly across 5 funds for each bucket
        ff_monthly = _m("five_finger")
        ff_lumpsum = _l("five_finger")
        per_fund_monthly = round_to_100(ff_monthly / 5) if ff_monthly > 0 else 0
        per_fund_lumpsum = round_to_100(ff_lumpsum / 5) if ff_lumpsum > 0 else 0
        if per_fund_monthly > 0 or per_fund_lumpsum > 0:
            for slot in _SLOT_META["five_finger"]:
                funds.append({
                    "name": fund_map[slot],
                    "category": _SLOT_CATEGORY[slot],
                    "monthly_amount": per_fund_monthly,
                    "lumpsum_amount": per_fund_lumpsum,
                })

        for slot_key in ("global", "high_risk"):
            m, l = _m(slot_key), _l(slot_key)
            if m > 0 or l > 0:
                fund_slot = _SLOT_META[slot_key][0]
                funds.append({
                    "name": fund_map[fund_slot],
                    "category": _SLOT_CATEGORY[fund_slot],
                    "monthly_amount": m,
                    "lumpsum_amount": l,
                })

        for slot_key in ("core", "debt_plus"):
            m, l = _m(slot_key), _l(slot_key)
            if m > 0 or l > 0:
                fund_slot = _SLOT_META[slot_key][0]
                funds.append({
                    "name": fund_map[fund_slot],
                    "category": _SLOT_CATEGORY[fund_slot],
                    "monthly_amount": m,
                    "lumpsum_amount": l,
                })

        m, l = _m("gold"), _l("gold")
        if m > 0 or l > 0:
            funds.append({
                "name": fund_map["gold"],
                "category": "Gold",
                "monthly_amount": m,
                "lumpsum_amount": l,
            })
    else:
        for slot_key in ("equity_blend", "debt_blend"):
            m, l = _m(slot_key), _l(slot_key)
            if m > 0 or l > 0:
                funds.append({
                    "name": fund_map[slot_key],
                    "category": _SLOT_CATEGORY[slot_key],
                    "monthly_amount": m,
                    "lumpsum_amount": l,
                })

    return funds
