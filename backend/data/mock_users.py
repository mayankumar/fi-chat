"""Mock user data — 6 existing FundsIndia clients for demo.

Each user has: profile, portfolio holdings, SIPs, and goal progress.
"""
from __future__ import annotations

from datetime import date

# -- User Profiles -----------------------------------------------------------

USERS = {
    "whatsapp:+919876543210": {
        "name": "Priya Sharma",
        "phone": "whatsapp:+919876543210",
        "segment": "new",
        "language": "hinglish",
        "age": 28,
        "risk_profile": "moderate",
        "joined": "2025-03-15",
        "rm_name": "Arun Kumar",
    },
    "whatsapp:+919876543211": {
        "name": "Ramesh Iyer",
        "phone": "whatsapp:+919876543211",
        "segment": "active",
        "language": "hi",
        "age": 45,
        "risk_profile": "conservative",
        "joined": "2019-06-10",
        "rm_name": "Arun Kumar",
    },
    "whatsapp:+919876543212": {
        "name": "Arjun Mehta",
        "phone": "whatsapp:+919876543212",
        "segment": "active",
        "language": "en",
        "age": 35,
        "risk_profile": "aggressive",
        "joined": "2021-01-22",
        "rm_name": "Arun Kumar",
    },
    "whatsapp:+919876543213": {
        "name": "Sneha Reddy",
        "phone": "whatsapp:+919876543213",
        "segment": "active",
        "language": "en",
        "age": 32,
        "risk_profile": "moderate",
        "joined": "2020-11-05",
        "rm_name": "Arun Kumar",
    },
    "whatsapp:+919876543214": {
        "name": "Vikram Singh",
        "phone": "whatsapp:+919876543214",
        "segment": "dormant",
        "language": "hinglish",
        "age": 40,
        "risk_profile": "moderate",
        "joined": "2018-04-18",
        "rm_name": "Arun Kumar",
    },
    "whatsapp:+919876543215": {
        "name": "Kavitha Nair",
        "phone": "whatsapp:+919876543215",
        "segment": "active",
        "language": "en",
        "age": 38,
        "risk_profile": "aggressive",
        "joined": "2022-07-30",
        "rm_name": "Arun Kumar",
    },
    "whatsapp:+918473970793": {
        "name": "Mayank Kumar",
        "phone": "whatsapp:+918473970793",
        "segment": "active",
        "language": "en",
        "age": 29,
        "risk_profile": "aggressive",
        "joined": "2023-09-01",
        "rm_name": "Arun Kumar",
    },
}

# -- Portfolio Holdings (for active/dormant users) ---------------------------

PORTFOLIOS = {
    "whatsapp:+919876543211": {
        "total_invested": 2400000,
        "current_value": 3150000,
        "xirr": 14.2,
        "holdings": [
            {"fund": "UTI Flexi Cap Fund", "category": "Equity - Flexi Cap", "invested": 600000, "current": 820000, "units": 3200.5, "nav": 256.2},
            {"fund": "ICICI Prudential Value Discovery Fund", "category": "Equity - Value", "invested": 500000, "current": 685000, "units": 2100.3, "nav": 326.1},
            {"fund": "Bandhan Income Plus Arbitrage FOF", "category": "Debt - Arbitrage", "invested": 800000, "current": 890000, "units": 45000.0, "nav": 19.78},
            {"fund": "ICICI Pru Regular Gold Savings Fund", "category": "Gold FOF", "invested": 300000, "current": 420000, "units": 12500.0, "nav": 33.6},
            {"fund": "Parag Parikh Flexi Cap Fund", "category": "Equity - Flexi Cap", "invested": 200000, "current": 335000, "units": 4100.0, "nav": 81.7},
        ],
    },
    "whatsapp:+919876543212": {
        "total_invested": 3600000,
        "current_value": 5200000,
        "xirr": 18.5,
        "holdings": [
            {"fund": "DSP Quant Fund", "category": "Equity - Quant", "invested": 800000, "current": 1250000, "units": 5600.0, "nav": 223.2},
            {"fund": "Mirae Asset Large & Midcap Fund", "category": "Equity - Large & Mid", "invested": 700000, "current": 1050000, "units": 4200.0, "nav": 250.0},
            {"fund": "ICICI Pru NASDAQ 100 Index Fund", "category": "Equity - International", "invested": 600000, "current": 920000, "units": 32000.0, "nav": 28.75},
            {"fund": "DSP Midcap Fund", "category": "Equity - Mid Cap", "invested": 500000, "current": 780000, "units": 3800.0, "nav": 205.3},
            {"fund": "360 One Quant Fund", "category": "Equity - Quant", "invested": 400000, "current": 580000, "units": 15000.0, "nav": 38.67},
            {"fund": "ICICI Prudential Banking & Financial Services Fund", "category": "Equity - Sectoral", "invested": 600000, "current": 620000, "units": 5500.0, "nav": 112.7},
        ],
    },
    "whatsapp:+919876543213": {
        "total_invested": 1800000,
        "current_value": 2250000,
        "xirr": 15.8,
        "holdings": [
            {"fund": "UTI Flexi Cap Fund", "category": "Equity - Flexi Cap", "invested": 500000, "current": 650000, "units": 2537.5, "nav": 256.2},
            {"fund": "Parag Parikh Flexi Cap Fund", "category": "Equity - Flexi Cap", "invested": 400000, "current": 560000, "units": 6854.3, "nav": 81.7},
            {"fund": "Bandhan Income Plus Arbitrage FOF", "category": "Debt - Arbitrage", "invested": 500000, "current": 545000, "units": 27553.1, "nav": 19.78},
            {"fund": "ICICI Pru Regular Gold Savings Fund", "category": "Gold FOF", "invested": 400000, "current": 495000, "units": 14732.1, "nav": 33.6},
        ],
    },
    "whatsapp:+919876543214": {
        "total_invested": 1200000,
        "current_value": 1450000,
        "xirr": 9.5,
        "holdings": [
            {"fund": "ICICI Prudential Value Discovery Fund", "category": "Equity - Value", "invested": 400000, "current": 520000, "units": 1594.6, "nav": 326.1},
            {"fund": "Bandhan Income Plus Arbitrage FOF", "category": "Debt - Arbitrage", "invested": 500000, "current": 560000, "units": 28311.4, "nav": 19.78},
            {"fund": "ICICI Pru Regular Gold Savings Fund", "category": "Gold FOF", "invested": 300000, "current": 370000, "units": 11011.9, "nav": 33.6},
        ],
    },
    "whatsapp:+919876543215": {
        "total_invested": 2800000,
        "current_value": 3850000,
        "xirr": 17.2,
        "holdings": [
            {"fund": "DSP Quant Fund", "category": "Equity - Quant", "invested": 700000, "current": 1020000, "units": 4569.4, "nav": 223.2},
            {"fund": "ICICI Pru NASDAQ 100 Index Fund", "category": "Equity - International", "invested": 600000, "current": 850000, "units": 29565.2, "nav": 28.75},
            {"fund": "DSP Midcap Fund", "category": "Equity - Mid Cap", "invested": 500000, "current": 720000, "units": 3507.5, "nav": 205.3},
            {"fund": "Parag Parikh Flexi Cap Fund", "category": "Equity - Flexi Cap", "invested": 500000, "current": 680000, "units": 8323.1, "nav": 81.7},
            {"fund": "360 One Quant Fund", "category": "Equity - Quant", "invested": 500000, "current": 580000, "units": 15000.0, "nav": 38.67},
        ],
    },
    "whatsapp:+918473970793": {
        "total_invested": 950000,
        "current_value": 1230000,
        "xirr": 21.4,
        "holdings": [
            {"fund": "Mirae Asset Large & Midcap Fund", "category": "Equity - Large & Mid", "invested": 300000, "current": 420000, "units": 1680.0, "nav": 250.0},
            {"fund": "Parag Parikh Flexi Cap Fund", "category": "Equity - Flexi Cap", "invested": 250000, "current": 365000, "units": 4467.6, "nav": 81.7},
            {"fund": "DSP Midcap Fund", "category": "Equity - Mid Cap", "invested": 200000, "current": 285000, "units": 1388.2, "nav": 205.3},
            {"fund": "ICICI Pru NASDAQ 100 Index Fund", "category": "Equity - International", "invested": 200000, "current": 160000, "units": 5565.2, "nav": 28.75},
        ],
    },
}

# -- Active SIPs -------------------------------------------------------------

SIPS = {
    "whatsapp:+919876543211": [
        {"fund": "UTI Flexi Cap Fund", "amount": 10000, "day": 5, "status": "active", "started": "2019-07-05"},
        {"fund": "ICICI Prudential Value Discovery Fund", "amount": 8000, "day": 5, "status": "active", "started": "2020-01-05"},
        {"fund": "Bandhan Income Plus Arbitrage FOF", "amount": 12000, "day": 10, "status": "active", "started": "2019-07-10"},
        {"fund": "ICICI Pru Regular Gold Savings Fund", "amount": 5000, "day": 10, "status": "active", "started": "2021-03-10"},
    ],
    "whatsapp:+919876543212": [
        {"fund": "DSP Quant Fund", "amount": 15000, "day": 1, "status": "active", "started": "2021-02-01"},
        {"fund": "Mirae Asset Large & Midcap Fund", "amount": 15000, "day": 1, "status": "active", "started": "2021-02-01"},
        {"fund": "ICICI Pru NASDAQ 100 Index Fund", "amount": 10000, "day": 15, "status": "active", "started": "2021-06-15"},
        {"fund": "DSP Midcap Fund", "amount": 10000, "day": 15, "status": "active", "started": "2022-01-15"},
        {"fund": "360 One Quant Fund", "amount": 8000, "day": 1, "status": "active", "started": "2023-04-01"},
    ],
    "whatsapp:+919876543213": [
        {"fund": "UTI Flexi Cap Fund", "amount": 10000, "day": 7, "status": "active", "started": "2020-12-07"},
        {"fund": "Parag Parikh Flexi Cap Fund", "amount": 8000, "day": 7, "status": "active", "started": "2021-03-07"},
        {"fund": "Bandhan Income Plus Arbitrage FOF", "amount": 10000, "day": 20, "status": "active", "started": "2021-01-20"},
        {"fund": "ICICI Pru Regular Gold Savings Fund", "amount": 7000, "day": 20, "status": "active", "started": "2022-06-20"},
    ],
    "whatsapp:+919876543214": [
        {"fund": "ICICI Prudential Value Discovery Fund", "amount": 5000, "day": 10, "status": "paused", "started": "2018-05-10"},
        {"fund": "Bandhan Income Plus Arbitrage FOF", "amount": 8000, "day": 10, "status": "paused", "started": "2018-05-10"},
    ],
    "whatsapp:+919876543215": [
        {"fund": "DSP Quant Fund", "amount": 12000, "day": 3, "status": "active", "started": "2022-08-03"},
        {"fund": "ICICI Pru NASDAQ 100 Index Fund", "amount": 10000, "day": 3, "status": "active", "started": "2022-08-03"},
        {"fund": "DSP Midcap Fund", "amount": 10000, "day": 18, "status": "active", "started": "2022-10-18"},
        {"fund": "Parag Parikh Flexi Cap Fund", "amount": 10000, "day": 18, "status": "active", "started": "2023-01-18"},
        {"fund": "360 One Quant Fund", "amount": 8000, "day": 3, "status": "active", "started": "2023-06-03"},
    ],
    "whatsapp:+918473970793": [
        {"fund": "Mirae Asset Large & Midcap Fund", "amount": 10000, "day": 5, "status": "active", "started": "2023-09-05"},
        {"fund": "Parag Parikh Flexi Cap Fund", "amount": 8000, "day": 5, "status": "active", "started": "2023-09-05"},
        {"fund": "DSP Midcap Fund", "amount": 7000, "day": 15, "status": "active", "started": "2024-01-15"},
    ],
}

# -- Goal Progress -----------------------------------------------------------

GOALS = {
    "whatsapp:+919876543211": [
        {
            "name": "Retirement",
            "target_corpus": 5000000,
            "achieved": 3150000,
            "progress_pct": 63.0,
            "target_date": "2044-06-01",
            "monthly_sip": 35000,
            "status": "on_track",
        },
    ],
    "whatsapp:+919876543212": [
        {
            "name": "Wealth Creation",
            "target_corpus": 10000000,
            "achieved": 5200000,
            "progress_pct": 52.0,
            "target_date": "2031-01-01",
            "monthly_sip": 58000,
            "status": "on_track",
        },
        {
            "name": "Daughter's Education",
            "target_corpus": 5000000,
            "achieved": 1800000,
            "progress_pct": 36.0,
            "target_date": "2035-06-01",
            "monthly_sip": 20000,
            "status": "on_track",
        },
    ],
    "whatsapp:+919876543213": [
        {
            "name": "House Down Payment",
            "target_corpus": 3000000,
            "achieved": 2250000,
            "progress_pct": 75.0,
            "target_date": "2027-12-01",
            "monthly_sip": 35000,
            "status": "on_track",
        },
    ],
    "whatsapp:+919876543214": [
        {
            "name": "Retirement",
            "target_corpus": 8000000,
            "achieved": 1450000,
            "progress_pct": 18.1,
            "target_date": "2043-04-01",
            "monthly_sip": 13000,
            "status": "behind",
            "drift_alert": "Your retirement goal is 12% behind schedule. Consider increasing SIP by ₹5,000/month to get back on track.",
        },
    ],
    "whatsapp:+919876543215": [
        {
            "name": "Early Retirement",
            "target_corpus": 15000000,
            "achieved": 3850000,
            "progress_pct": 25.7,
            "target_date": "2037-07-01",
            "monthly_sip": 50000,
            "status": "on_track",
        },
    ],
    "whatsapp:+918473970793": [
        {
            "name": "Early Retirement",
            "target_corpus": 20000000,
            "achieved": 1230000,
            "progress_pct": 6.2,
            "target_date": "2050-01-01",
            "monthly_sip": 25000,
            "status": "on_track",
        },
        {
            "name": "International Travel Fund",
            "target_corpus": 500000,
            "achieved": 320000,
            "progress_pct": 64.0,
            "target_date": "2026-12-01",
            "monthly_sip": 15000,
            "status": "on_track",
        },
    ],
}


# -- Lookup helpers ----------------------------------------------------------

def get_user(phone: str) -> dict | None:
    """Look up a user by phone. Returns None for unknown numbers."""
    return USERS.get(phone)


def get_portfolio(phone: str) -> dict | None:
    return PORTFOLIOS.get(phone)


def get_sips(phone: str) -> list | None:
    return SIPS.get(phone)


def get_goals(phone: str) -> list | None:
    return GOALS.get(phone)


def fmt_amount(amount: float) -> str:
    """Format amount in Indian style: ₹1.5L, ₹2.3Cr"""
    if amount >= 10000000:
        return f"₹{amount / 10000000:.1f}Cr"
    if amount >= 100000:
        return f"₹{amount / 100000:.1f}L"
    if amount >= 1000:
        return f"₹{amount / 1000:.1f}K"
    return f"₹{amount:.0f}"
