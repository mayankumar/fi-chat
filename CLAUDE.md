# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

FundsIndia WhatsApp AI Advisory Bot — a Claude-powered chatbot for financial advisory via WhatsApp (Twilio), with a Next.js RM (Relationship Manager) dashboard for monitoring conversations, calling customers, and viewing AI-generated briefs.

## Running the project

**Backend (FastAPI):**
```bash
python3 -m uvicorn backend.main:app --reload
```

**Dashboard (Next.js):**
```bash
cd dashboard && npm run dev   # dev server at localhost:3000
cd dashboard && npm run build # production build
cd dashboard && npm run lint  # ESLint
```

**Environment:** Copy `.env.example` to `.env`. Required: `ANTHROPIC_API_KEY`, `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM`. For voice calling: `TWILIO_API_KEY_SID`, `TWILIO_API_KEY_SECRET`, `TWILIO_TWIML_APP_SID`. For webhooks in dev: `MEDIA_BASE_URL` (ngrok URL).

No tests — all flows are validated end-to-end via WhatsApp sandbox.

## Architecture

```
WhatsApp User → Twilio → POST /webhook → FastAPI → asyncio.create_task(_process_message)
                                                           │
                              ┌────────────────────────────┤
                              │  Language detect (Haiku)   │
                              │  Consent gate              │
                              │  Intent classify (Haiku)   │
                              │  Route to handler          │
                              │  Recommendation engine     │
                              │  PDF generator             │
                              │  Session save              │
                              └────────────────────────────┘
                                          │ REST APIs
                              RM Dashboard (Next.js)
```

**Key design decisions:**
- Webhook returns empty TwiML immediately; processing is fire-and-forget via `asyncio.create_task()`
- Phone number = session identity; sessions stored as dicts + JSON snapshots at `sessions/{phone}.json`
- Haiku for fast classification (intent, language); Sonnet for reasoning (research, goal flow, advisory)
- Recommendation engine is pure deterministic Python — LLM never picks funds
- Multi-message responses use `|||` as a delimiter; `twilio_sender.py` splits and sends each part separately
- `message_mode: "split"` sends separate messages (demo), `"compact"` sends one (testing) — controlled via `.env`

## Backend structure

- `backend/main.py` — FastAPI app, `/webhook` handler, async message pipeline
- `backend/config.py` — Pydantic settings loaded from `.env`; singleton via `get_settings()`
- `backend/services/` — Language detection, intent classification, consent, session store, Twilio sender, conversation agent, handoff, agitation, session memory
- `backend/handlers/` — One handler per intent: `greeting`, `stock_redirect`, `tta`, `research`, `goal_discovery`, `portfolio`, `pdf_handler`; `router.py` dispatches by intent
- `backend/recommender/` — Deterministic fund allocation engine (`engine.py`), SIP formulas (`formulas.py`), constants
- `backend/pdf/` — Jinja2 HTML templates rendered to PDF via Playwright (headless Chromium)
- `backend/api/` — `dashboard.py` (RM REST APIs), `voice.py` (Twilio Voice token + TwiML)
- `backend/data/mock_users.py` — Mock user data for dashboard

## Dashboard (Next.js)

Single-page app at `dashboard/app/page.tsx` — user list, chat transcript viewer, AI-generated brief panel, voice calling via Twilio Voice SDK.

**Important:** This project uses a version of Next.js with breaking changes from older versions. Before writing any Next.js code, read the relevant guide in `node_modules/next/dist/docs/`. Do not assume API conventions from older Next.js versions.

Styling: Tailwind CSS v4 + custom CSS in `globals.css`.

## Intent taxonomy

12 intent types: `greeting`, `goal_discovery`, `stock_question`, `research`, `tta_request`, `portfolio`, `off_topic`, and fallback to Sonnet general advisory. The `goal_discovery` flow is stateful — it collects age, SIP amount, and tenure across multiple turns, runs the recommendation engine, and generates a PDF.

## Models

- `haiku_model`: `claude-haiku-4-5-20251001` — used for language detection and intent classification
- `sonnet_model`: `claude-sonnet-4-6` — used for reasoning, research answers, and goal discovery conversation
- `max_tokens`: 600, `max_history_messages`: 20
