"""All tables, defaults, fund maps — single source of truth.

Matches FundsIndia's Main Brain sheet and Goal-Based Investing product brief.
"""
from __future__ import annotations

# ── Goal defaults ─────────────────────────────────────────────────────

GOAL_DEFAULTS = {
    "retirement": {
        "present_value": 5_000_000,  # ₹50L default corpus
        "tenure_years": 30,
        "inflation": 0.06,
        "monthly_expenses": 50_000,
        "retirement_age": 60,
        "life_expectancy": 75,
    },
    "child_education": {
        "present_value": 5_000_000,  # ₹50L (private college default)
        "tenure_years": 10,
        "inflation": 0.08,  # education inflation
        "college_costs": {
            "govt": 3_000_000,
            "private": 5_000_000,
            "abroad": 10_000_000,
        },
    },
    "wealth_creation": {
        "present_value": 10_000_000,  # ₹1 crore
        "tenure_years": 10,
        "inflation": 0.0,  # nominal target
    },
}

# ── Risk profiles & returns ───────────────────────────────────────────

RISK_PROFILES = {
    "conservative": {"annual_return": 0.10, "label": "Conservative"},
    "moderate":     {"annual_return": 0.12, "label": "Moderate"},
    "aggressive":   {"annual_return": 0.14, "label": "Aggressive"},
}

DEFAULT_RISK_PROFILE = "moderate"

# ── Asset allocation (% of total) ────────────────────────────────────

ALLOCATION = {
    "conservative": {"equity": 0.30, "debt": 0.45, "gold": 0.25},
    "moderate":     {"equity": 0.50, "debt": 0.25, "gold": 0.25},
    "aggressive":   {"equity": 1.00, "debt": 0.00, "gold": 0.00},
}

# Equity sub-allocation (% of TOTAL, not % of equity)
EQUITY_SUB = {
    "conservative": {"five_finger": 0.30, "global": 0.00, "high_risk": 0.00},
    "moderate":     {"five_finger": 0.40, "global": 0.10, "high_risk": 0.00},
    "aggressive":   {"five_finger": 0.60, "global": 0.20, "high_risk": 0.20},
}

# Debt sub-allocation (% of TOTAL)
DEBT_SUB = {
    "conservative": {"core": 0.315, "debt_plus": 0.135},
    "moderate":     {"core": 0.25,  "debt_plus": 0.00},
    "aggressive":   {"core": 0.00,  "debt_plus": 0.00},
}

# ── Fund map ──────────────────────────────────────────────────────────

# Default funds (conservative & moderate)
FUND_MAP = {
    "debt_core":          "Bandhan Income Plus Arbitrage FOF",
    "debt_plus":          "ICICI Prudential Equity Savings Fund",
    "gold":               "ICICI Pru Regular Gold Savings Fund (FOF)",
    "five_finger_quality":"UTI Flexi Cap Fund",
    "five_finger_value":  "ICICI Prudential Value Discovery Fund",
    "five_finger_garp":   "Parag Parikh Flexi Cap Fund",
    "five_finger_midcap": "DSP Midcap Fund",
    "five_finger_momentum":"360 One Quant Fund",
    "global":             "ICICI Pru NASDAQ 100 Index Fund",
    "high_risk":          "ICICI Prudential Banking & Financial Services Fund",
    "equity_blend":       "Parag Parikh Flexi Cap Fund",
    "debt_blend":         "Bandhan Income Plus Arbitrage FOF",
}

# Aggressive overrides
FUND_MAP_AGGRESSIVE = {
    "five_finger_quality": "DSP Quant Fund",
    "five_finger_garp":    "Mirae Asset Large & Midcap Fund",
}

# ── Simple blend allocation (< ₹20,000) ──────────────────────────────

SIMPLE_BLEND = {
    "conservative": {"equity": 0.30, "debt": 0.70},
    "moderate":     {"equity": 0.50, "debt": 0.50},
    "aggressive":   {"equity": 1.00, "debt": 0.00},
}

DIVERSIFIED_THRESHOLD = 20_000  # SIP >= this → full diversified allocation

# ── Milestones (front-loaded) ─────────────────────────────────────────

MILESTONE_RATIOS = [
    {"corpus_pct": 0.10, "time_pct": 0.30, "label": "First Steps 🌱"},
    {"corpus_pct": 0.25, "time_pct": 0.50, "label": "Gaining Momentum 📈"},
    {"corpus_pct": 0.50, "time_pct": 0.70, "label": "Halfway There 🎯"},
    {"corpus_pct": 0.75, "time_pct": 0.90, "label": "Almost There 🚀"},
    {"corpus_pct": 1.00, "time_pct": 1.00, "label": "Goal Achieved! 🏆"},
]

# ── Scenario starting SIPs ───────────────────────────────────────────

SCENARIO_SIPS = [10_000, 15_000, 20_000]

# Step-up defaults
DEFAULT_STEPUP_RATE = 0.10  # 10% annual
DEFAULT_STEPUP_BASE = 10_000  # ₹10,000 starting SIP

# ── Thresholds ────────────────────────────────────────────────────────

SIP_MINIMUM = 500
LUMPSUM_MINIMUM = 20_000
