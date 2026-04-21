"""Core financial formulas — deterministic, no LLM.

All formulas match FundsIndia's Main Brain sheet.
Verified: ₹50L / 15yr / 12% → SIP ₹9,909/month.
"""
from __future__ import annotations

import math

from backend.recommender.constants import (
    MILESTONE_RATIOS, SCENARIO_SIPS,
    DEFAULT_STEPUP_RATE, DEFAULT_STEPUP_BASE,
)


def round_to_100(amount: float) -> int:
    """Round up to nearest ₹100."""
    return int(math.ceil(round(amount) / 100) * 100)


def future_value(present_value: float, inflation: float, years: int) -> float:
    """FV = PV × (1 + inflation)^years"""
    return present_value * ((1 + inflation) ** years)


def sip_required(fv: float, annual_return: float, months: int) -> float:
    """Monthly SIP for a target FV (annuity-due, Indian convention).

    SIP = FV × r / [((1+r)^n − 1) × (1+r)]
    """
    r = annual_return / 12
    if r == 0:
        return fv / months
    factor = ((1 + r) ** months - 1) * (1 + r)
    return fv * r / factor


def sip_future_value(sip: float, annual_return: float, months: int) -> float:
    """Future value of a monthly SIP (annuity-due, Indian convention).

    FV = SIP × [((1+r)^n − 1) / r] × (1+r)
    """
    if sip <= 0 or months <= 0:
        return 0.0
    r = annual_return / 12
    if r == 0:
        return sip * months
    return sip * ((1 + r) ** months - 1) / r * (1 + r)


def nper_months(fv: float, sip: float, annual_return: float) -> int:
    """Months needed to reach FV with fixed monthly SIP.

    months = log(1 + (FV × r) / (SIP × (1+r))) / log(1 + r)
    """
    r = annual_return / 12
    if r == 0:
        return int(math.ceil(fv / sip))
    if sip <= 0:
        return 999
    val = 1 + (fv * r) / (sip * (1 + r))
    if val <= 0:
        return 999
    return int(math.ceil(math.log(val) / math.log(1 + r)))


def stepup_sip(fv: float, annual_return: float, tenure_years: int,
               stepup_rate: float = DEFAULT_STEPUP_RATE) -> float:
    """Find base SIP with annual step-up that reaches FV.

    Uses binary search (50 iterations).
    """
    low, high = 0.0, fv
    for _ in range(50):
        mid = (low + high) / 2
        total = _simulate_stepup(mid, stepup_rate, annual_return, tenure_years)
        if total < fv:
            low = mid
        else:
            high = mid
    return (low + high) / 2


def _simulate_stepup(base_sip: float, stepup_rate: float,
                     annual_return: float, years: int) -> float:
    """Simulate step-up SIP and return accumulated FV."""
    r = annual_return / 12
    total = 0.0
    current_sip = base_sip
    for year in range(years):
        remaining_months = (years - year) * 12
        for month in range(12):
            months_left = remaining_months - month
            total += current_sip * ((1 + r) ** months_left)
        current_sip *= (1 + stepup_rate)
    return total


def compute_milestones(fv: float, tenure_years: int,
                       annual_return: float) -> list:
    """Compute 5 front-loaded milestones with SIP required for each."""
    milestones = []
    for m in MILESTONE_RATIOS:
        target = fv * m["corpus_pct"]
        months = max(1, int(round(tenure_years * 12 * m["time_pct"])))
        years = months / 12
        sip = round_to_100(sip_required(target, annual_return, months))
        milestones.append({
            "label": m["label"],
            "corpus_pct": m["corpus_pct"],
            "target_corpus": round(target),
            "time_years": round(years, 1),
            "months": months,
            "sip_required": sip,
        })
    return milestones


def compute_scenarios(fv: float, annual_return: float) -> list:
    """Compute how long different starting SIPs take to reach FV."""
    scenarios = []
    for sip in SCENARIO_SIPS:
        months = nper_months(fv, sip, annual_return)
        scenarios.append({
            "starting_sip": sip,
            "months": months,
            "years": round(months / 12, 1),
        })
    return scenarios


def compute_stepup_scenario(fv: float, annual_return: float,
                            tenure_years: int) -> dict:
    """Compute step-up strategy details."""
    base = stepup_sip(fv, annual_return, tenure_years)
    return {
        "base_sip": round_to_100(base),
        "stepup_rate_pct": int(DEFAULT_STEPUP_RATE * 100),
        "tenure_years": tenure_years,
        "target_fv": round(fv),
    }
