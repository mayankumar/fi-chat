# FundsIndia WhatsApp AI Advisory Bot — Master Plan

## Design Principles

- **Claude-native** — Anthropic SDK directly. Haiku for fast classification, Sonnet for reasoning. No abstraction layers.
- **Phone = identity** — Every session keyed by phone number from Twilio webhook. Simple dict + JSON snapshot.
- **Deterministic recommendations** — Fund engine is pure Python math. LLM never picks funds.
- **Beautiful PDF** — Modern card-based design (green gradients, illustrations, trust badges). HTML/CSS → PDF.
- **Ship working flows** — No unit tests, but every flow tested end-to-end before delivery.

---

## Architecture

```
WhatsApp User
      │
      ▼
┌──────────┐     POST /webhook      ┌─────────────────────────────────────┐
│  Twilio  │ ──────────────────────▶ │          FastAPI Backend            │
│ Sandbox  │ ◀────────────────────── │                                     │
└──────────┘     send_message()      │  ┌───────────┐  ┌───────────────┐  │
                                     │  │  Consent   │  │   Intent      │  │
                                     │  │  Gate      │  │  Classifier   │  │
                                     │  │            │  │  (Haiku)      │  │
                                     │  └─────┬──────┘  └───────┬───────┘  │
                                     │        │                 │          │
                                     │        ▼                 ▼          │
                                     │  ┌───────────────────────────────┐  │
                                     │  │        Intent Router          │  │
                                     │  │                               │  │
                                     │  │  goal_discovery → GoalFlow    │  │
                                     │  │  research       → Sonnet      │  │
                                     │  │  stock_question → Redirect    │  │
                                     │  │  tta_request    → Handoff     │  │
                                     │  │  portfolio      → [Phase 5]   │  │
                                     │  └───────┬───────────────────────┘  │
                                     │          │                          │
                                     │          ▼                          │
                                     │  ┌───────────────┐ ┌────────────┐  │
                                     │  │ Recommendation │ │    PDF     │  │
                                     │  │ Engine (Python)│→│ Generator  │  │
                                     │  │ ~300 lines     │ │ HTML→PDF   │  │
                                     │  └───────────────┘ └────────────┘  │
                                     │                                     │
                                     │  ┌───────────────────────────────┐  │
                                     │  │ Session Store (dict + JSON)   │  │
                                     │  │ per phone: messages, state,   │  │
                                     │  │ consent, language, flow_state │  │
                                     │  └───────────────────────────────┘  │
                                     └──────────────┬──────────────────────┘
                                                    │ REST APIs
                                     ┌──────────────▼──────────────────────┐
                                     │      RM Dashboard (Next.js)         │
                                     │  Queue │ Handoff Brief │ Call │ AI  │
                                     └─────────────────────────────────────┘
```

---

## Message Processing Pipeline

```
Twilio POST /webhook
      │
      ▼
  Parse form → extract phone + message
      │
      ▼
  Return empty TwiML immediately (ack)
      │
      ▼
  asyncio.create_task(_process_message)
      │
      ▼
  ┌── Get/create session by phone
  │
  ├── Language detection (Haiku) ← first message only
  │
  ├── Consent gate
  │   ├── Not consented → send disclaimer
  │   ├── Reply YES → segment=new, send greeting
  │   └── Reply EXPERT → segment=active, send greeting
  │
  ├── Save user message to history
  │
  ├── Classify intent (Haiku) → 12 types + entities
  │
  ├── Route to handler:
  │   ├── greeting       → segment-aware welcome
  │   ├── stock_question  → firm refusal + TTA redirect
  │   ├── tta_request     → advisor options (call/callback/email)
  │   ├── research        → Sonnet explains financial concepts
  │   ├── goal_discovery  → stateful collection → engine → PDF
  │   ├── off_topic       → polite redirect to finance
  │   └── *               → Sonnet general advisory
  │
  ├── Save assistant response to history
  │
  └── Send reply via Twilio REST API
```

---

## Session Shape

```python
{
    phone: str,
    language: str | None,            # "en" / "hi" / "hinglish"
    consent_given: bool,
    consent_version: str | None,
    consent_pending_since: str | None,
    messages: [{role, content, timestamp}],
    user_segment: str | None,        # "new" | "active" | "dormant"
    active_intent: str | None,
    flow_state: {},                  # goal discovery progress, etc.
    handoff_state: str,              # "bot_active" | "handoff_pending" | "rm_active"
    pdf_regen_count: int,
    created_at: str,
    updated_at: str,
}
```

---

## Intent Taxonomy

| Intent | Description | Handler |
|--------|-------------|---------|
| `greeting` | Hi, hello, good morning | Segment-aware greeting |
| `goal_discovery` | Wants help setting financial goals | GoalFlow (stateful) |
| `risk_assessment` | Wants to understand risk profile | Sonnet questionnaire |
| `portfolio_query` | Questions about existing holdings/returns | [Phase 5] |
| `transaction_action` | Buy, sell, redeem, switch, start/stop SIP | [Phase 5] |
| `research_question` | Learn about SIP, NAV, ELSS, mutual funds | Sonnet with guardrails |
| `stock_question` | Specific stocks, share prices, equity | Firm refusal + TTA |
| `product_inquiry` | Specific MF schemes or categories | Sonnet advisory |
| `pdf_modification` | Changes to advisory PDF/report | Re-run engine |
| `tta_request` | Talk to human advisor / RM | Handoff flow |
| `general_chat` | General finance conversation | Sonnet advisory |
| `off_topic` | Unrelated (weather, sports, politics) | Polite redirect |

---

## Key Patterns

| Pattern | Detail |
|---------|--------|
| **Empty TwiML** | Return `<Response/>` immediately to Twilio, send actual reply via REST API async |
| **asyncio.to_thread()** | Wrap blocking Twilio REST calls for async FastAPI |
| **Pydantic Settings** | `.env` file loaded via `pydantic_settings`, cached with `@lru_cache` |
| **Sliding window** | Keep last 20 messages per session for context |
| **JSON snapshots** | Session dict persisted to `sessions/{phone}.json` on every update |
| **Quick-reply buttons** | Twilio Content API templates with up to 3 buttons per message, auto-created and cached |
| **Multi-message blocks** | Responses split into separate WhatsApp messages (0.8s delay between), actionable block always last |
| **`\|\|\|` split delimiter** | Claude uses `\|\|\|` in responses to split into separate message blocks |
| **Conversational Q&A** | Risk assessment / goal discovery questions asked one-at-a-time, not all at once |
| **Fire-and-forget** | `asyncio.create_task()` for message processing after TwiML ack |

---

## File Structure

```
fi-chat/
├── backend/
│   ├── main.py                      # FastAPI app, webhook, health check
│   ├── config.py                    # Pydantic settings
│   ├── __init__.py
│   ├── services/
│   │   ├── session_store.py         # Phone-keyed session dict + JSON
│   │   ├── twilio_sender.py         # Send text + media via Twilio REST
│   │   ├── consent.py               # T&C disclaimer gate
│   │   ├── language.py              # Haiku language detection
│   │   ├── intent_classifier.py     # Haiku intent + entity extraction
│   │   ├── conversation_agent.py    # Sonnet advisory chat
│   │   └── __init__.py
│   ├── handlers/
│   │   ├── router.py                # Intent → handler dispatch
│   │   ├── greeting.py              # Segment-aware multilingual greeting
│   │   ├── stock_redirect.py        # Firm refusal + TTA redirect
│   │   ├── tta.py                   # Talk-to-advisor handoff
│   │   ├── research.py              # Financial concept explanations
│   │   └── __init__.py
│   ├── recommender/                 # [Phase 2] Deterministic engine
│   │   ├── constants.py
│   │   ├── formulas.py
│   │   └── engine.py
│   ├── data/                        # Generated PDFs, handoffs
│   ├── static/                      # Served files
│   └── utils/
├── dashboard/                       # [Phase 4] Next.js RM dashboard
├── requirements.txt
├── .env.example
├── .gitignore
└── PLAN.md
```

---

## Phase Breakdown

### Phase 1 — Foundation (Core WhatsApp Bot)

**What it delivers:** A working WhatsApp bot that receives messages, manages sessions, detects language, shows T&C disclaimer, classifies intent, routes to handlers, and responds via Claude Sonnet.

#### Config & Setup

| # | Task | File | Status |
|---|------|------|--------|
| 1 | FastAPI app, webhook, health check, static mount | `backend/main.py` | DONE |
| 2 | Pydantic settings (Anthropic, Twilio, models) | `backend/config.py` | DONE |
| 3 | Requirements file | `requirements.txt` | DONE |
| 4 | Environment template | `.env.example` | DONE |
| 5 | Gitignore | `.gitignore` | DONE |

#### Services

| # | Task | File | Status |
|---|------|------|--------|
| 6 | Session store (dict + JSON snapshot, message history) | `backend/services/session_store.py` | DONE |
| 7 | Twilio sender (text + media via REST) | `backend/services/twilio_sender.py` | DONE |
| 8 | T&C consent gate (disclaimer EN/Hinglish, YES/EXPERT) | `backend/services/consent.py` | DONE |
| 9 | Language detection via Haiku (en/hi/hinglish) | `backend/services/language.py` | DONE |
| 10 | Intent classification via Haiku (12 types + entities) | `backend/services/intent_classifier.py` | DONE |
| 11 | Conversation agent via Sonnet (system prompt + guardrails) | `backend/services/conversation_agent.py` | DONE |

#### Handlers

| # | Task | File | Status |
|---|------|------|--------|
| 12 | Intent router (dispatch to handlers) | `backend/handlers/router.py` | DONE |
| 13 | Greeting handler (segment-aware, multilingual) | `backend/handlers/greeting.py` | DONE |
| 14 | Stock redirect (firm refusal + TTA redirect) | `backend/handlers/stock_redirect.py` | DONE |
| 15 | Talk-to-advisor handoff | `backend/handlers/tta.py` | DONE |
| 16 | Research handler (financial concept explanations) | `backend/handlers/research.py` | DONE |

#### Cross-cutting

| # | Task | Status |
|---|------|--------|
| 17 | Logging (full pipeline tracing: timing, tokens, response body) | DONE |
| 18 | Python 3.9 compatibility (`__future__` annotations, no match/case) | DONE |

#### UX Improvements (v1.1)

| # | Issue | Fix | Status |
|---|-------|-----|--------|
| 19 | Disclaimer too cold/generic | Warmer copy, promote FundsIndia advisors, trustworthy tone | DONE |
| 20 | No quick-reply buttons | Twilio Content API buttons on disclaimer, greeting, TTA, stock redirect | DONE |
| 21 | Long messages with `---` separators | Multi-message blocks (0.8s delay), actionable part always last | DONE |
| 22 | No emojis, flat visual feel | Emojis throughout all static messages + system prompt updated | DONE |
| 23 | Risk assessment dumps all questions at once | System prompt: ask ONE question at a time conversationally | DONE |
| 24 | Button payload handling | Webhook reads ButtonPayload from Twilio, routes as message | DONE |
| 25 | TTA sub-selection (call/callback/email) | TTA followup handler after button tap | DONE |
| 26 | Claude `\|\|\|` split | Claude uses delimiter to split responses into separate WhatsApp messages | DONE |

#### Verification

| # | Test Case | Status |
|---|-----------|--------|
| V1 | Server starts: `python3 -m uvicorn backend.main:app --reload` | DONE |
| V2 | `curl /health` returns ok | DONE |
| V3 | Send WhatsApp message → disclaimer (2 blocks + buttons) | NOT TESTED |
| V4 | Tap "Let's Start!" button → greeting (2 blocks + action menu buttons) | NOT TESTED |
| V5 | Ask "What is SIP?" → research answer (split into blocks) | NOT TESTED |
| V6 | Ask "What about Reliance stock?" → firm redirect + buttons | NOT TESTED |
| V7 | Tap "Talk to Advisor" → TTA menu with call/callback/email buttons | NOT TESTED |
| V8 | Send Hinglish message → bot responds in Hinglish with emojis | NOT TESTED |
| V9 | Tap TTA sub-option → correct followup (phone number / callback / email) | NOT TESTED |

---

### Phase 2 — Goal Engine + Conversational Discovery

**What it delivers:** Pure Python recommendation engine + LLM-driven goal collection over 3-5 messages → structured investment plan.

| # | Task | Files | Status |
|---|------|-------|--------|
| 1 | Constants: allocation tables, fund maps, goal defaults | `backend/recommender/constants.py` | DONE |
| 2 | Formulas: FV, SIP, NPER, step-up, milestones, scenarios | `backend/recommender/formulas.py` | DONE |
| 3 | Engine: `generate_plan()` orchestration | `backend/recommender/engine.py` | DONE |
| 4 | Goal discovery handler (Haiku extraction + stateful collection) | `backend/handlers/goal_discovery.py` | DONE |
| 5 | Text summary of plan (5 blocks via |||) | (in goal handler) | DONE |
| 6 | Router wiring (goal_discovery + mid-flow routing + button mapping) | `backend/handlers/router.py` | DONE |

**Goal discovery flow:**
```
User: "I want to save for my daughter's education"
      │
      ▼
Sonnet collects over 3-5 messages:
  → Goal type (education, retirement, house, emergency, wedding)
  → Age / tenure
  → Monthly SIP amount (or target corpus)
      │
      ▼
Returns: {response_text, collected_updates, ready_for_plan}
      │
      ▼ (when ready)
generate_plan() → stores in flow_state["current_plan"]
      │
      ▼
Send text summary → offer PDF
```

**Verification:**
- "Save for daughter's education" → 3-question conversation → plan generated
- Engine output matches Main Brain sheet (Rs 9,909 for Rs 50L/15yr/12%) — VERIFIED ✅

---

### Phase 2b — PDF Generation

**What it delivers:** Beautiful branded PDF matching FundsIndia's style, delivered via WhatsApp.

| # | Task | Status |
|---|------|--------|
| 1 | HTML/CSS template with Jinja2 (green gradients, cards, illustrations) | DONE |
| 2 | PDF rendering (HTML → PDF via Playwright Chromium) | DONE |
| 3 | PDF delivery via Twilio media attachment | DONE |
| 4 | PDF regeneration (max 2, then TTA nudge) | DONE |

**PDF layout (from reference design):**
```
┌─────────────────────────────────────┐
│  Green gradient header + FI logo    │
│  Goal title + tenure illustration   │
├─────────────────────────────────────┤
│  Card 1: "The Set-and-Forget"       │
│  SIP amount, fund allocation bar    │
│  (Equity 60% / Debt 30% / Gold 10%)│
├─────────────────────────────────────┤
│  Card 2: "The Step-up Strategy"     │
│  Lower starting SIP + step-up rate  │
│  allocation bar                     │
├─────────────────────────────────────┤
│  "Did you know?" insight callout    │
├─────────────────────────────────────┤
│  "Get in touch with your advisor"   │
│  Services grid (Goal Planning,      │
│  Portfolio Review, Investment Advice)│
├─────────────────────────────────────┤
│  Trust badge (4.6★, AUM, track rec) │
│  Disclaimer footer                  │
└─────────────────────────────────────┘
```

---

### Phase 3 — Handoff + Agitation + Memory

**What it delivers:** TTA flow end-to-end, sentiment monitoring, session summaries for returning users.

| # | Task | Status |
|---|------|--------|
| 1 | Handoff service (structured record: phone, language, reason, urgency, summary) | DONE |
| 2 | Handoff brief (Sonnet-generated: profile, goals, recommendations, talking points) | DONE |
| 3 | Agitation detection (Haiku every 3-4 msgs, score 0-10, proactive TTA if ≥6) | DONE |
| 4 | Tier 2 memory (session summary on close → JSON for returning user context) | DONE |
| 5 | Post-PDF TTA nudge (auto-offer TTA after PDF v1 delivery) | DONE |
| 6 | CTA buttons via Twilio Content API | DONE |
| 7 | Handoff data exposed via `/api/handoffs` for dashboard | DONE |

**Agitation detection flow:**
```
Every 3-4 user messages:
  Haiku evaluates conversation → {score: 0-10, reason: "..."}
  Score ≥ 6 → proactive TTA offer
  Score < 6 → continue normally
```

---

### Phase 4 — RM Dashboard (Next.js)

**What it delivers:** Simple, clean dashboard for RMs. When a customer asks to connect with an advisor (TTA), the RM sees the user in a list, reads their conversation + AI-generated summary with talking points, and can send a message or call.

#### Backend APIs (FastAPI)

| # | Task | Files | Status |
|---|------|-------|--------|
| 1 | `GET /api/users` — list all users with last message, intent, language, TTA status | `backend/api/dashboard.py` | DONE |
| 2 | `GET /api/users/{phone}/chat` — full conversation transcript | `backend/api/dashboard.py` | DONE |
| 3 | `GET /api/users/{phone}/summary` — AI summary + talking points (Haiku) | `backend/api/dashboard.py` | DONE |
| 4 | `POST /api/users/{phone}/send` — RM sends WhatsApp message to user | `backend/api/dashboard.py` | DONE |

#### Frontend (Next.js + Tailwind)

| # | Task | Status |
|---|------|--------|
| 5 | Dashboard scaffold (Next.js + Tailwind, single page) | DONE |
| 6 | User list — card per user (name/phone, language, last message, TTA badge, click to expand) | DONE |
| 7 | Chat detail panel — full transcript (WhatsApp-style bubbles) + AI summary card + talking points | DONE |
| 8 | Send message input — RM types message → POST to API → delivered via Twilio | DONE |
| 9 | Call button — `tel:` link to user's phone number | DONE |

**Flow:**
```
Customer says "connect me to advisor"
      │
      ▼
Bot sends TTA menu (call/callback/email)
Session marked: handoff_state = "handoff_pending"
      │
      ▼
RM opens dashboard → sees user with 🔴 TTA badge
      │
      ▼
RM clicks user → sees:
  • Full chat transcript (WhatsApp-style)
  • AI Summary: "User wants to save for daughter's education,
    age 5, SIP ₹15K/mo. Plan generated. Wants expert guidance."
  • Talking Points: "Discuss step-up strategy, college abroad options"
      │
      ▼
RM can: Send WhatsApp message | Call user
```

---

### Phase 5 — Existing Users + Demo Polish

**What it delivers:** Support for existing FundsIndia clients (mocked data), 3 polished demo personas.

| # | Task | Status |
|---|------|--------|
| 1 | Mock data (6 users, 3 portfolios, 12 fund products) | DONE |
| 2 | Phone lookup → personalized greeting by name | DONE |
| 3 | Portfolio summary (holdings, AUM, XIRR) | DONE |
| 4 | Active SIPs list with next debit dates | DONE |
| 5 | Goal progress with drift alerts | DONE |
| 6 | Self-serve: pause SIP, step-up SIP (with confirmation) | DONE |
| 7 | Portfolio statement PDF | SKIPPED |
| 8 | Proactive nudges (goal-miss alert, step-up suggestions) | DONE |

**Demo personas:**
| Persona | Segment | Language | Demo Flow |
|---------|---------|----------|-----------|
| Priya | New | Hinglish | Consent → assessment → PDF → TTA |
| Ramesh | Active | Hindi | Portfolio view → goal-miss nudge → step-up |
| Arjun | Active | English | Stock question → redirect → TTA → RM dashboard → call |

---

## Critical Path

```
Phase 1 (Webhook+Intent+Agent) → Phase 2 (Goal Engine) → Phase 2b (PDF) → Phase 3 (Handoff+Agitation)
                                                                                      │
                                                                               Phase 4 (RM Dashboard)
                                                                                      │
                                                                               Phase 5 (Existing Users)
```

**Parallelizable:**
- Dev 1: Phase 1 → Phase 2 → Phase 2b → Phase 3
- Dev 2: Phase 4 (dashboard) once Phase 1 APIs are stable

---

## Key Architecture Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| LLM | Claude (Haiku + Sonnet) | PRD specifies; better multilingual, Hinglish |
| LLM abstraction | None (direct Anthropic SDK) | Hackathon speed, no provider switching needed |
| Rec engine | Pure Python, no LLM | Deterministic, auditable, compliance requirement |
| Session storage | Dict + JSON snapshot | Simplest for hackathon; Redis upgrade path clear |
| PDF library | HTML/CSS → PDF (Jinja2 templates) | Beautiful design, fast iteration |
| Dashboard | Next.js + Tailwind | Fast to build, professional look |
| Intent routing | Haiku classifier | Cheap, fast (~200ms), structured JSON output |
| Fund recs | Never from LLM | Compliance — deterministic engine only |
| Tests | Manual E2E only | Hackathon constraint — every flow tested on real WhatsApp |

---

## Summary

| Phase | What | Tasks | Done | Status |
|-------|------|-------|------|--------|
| 1 | Foundation + UX polish (webhook, sessions, consent, intent, handlers, buttons, multi-msg) | 26 | 26 | COMPLETE |
| 2 | Goal engine + conversational discovery | 6 | 6 | COMPLETE |
| 2b | PDF generation + delivery | 4 | 4 | COMPLETE |
| 3 | Handoff + agitation + memory | 7 | 7 | COMPLETE |
| 4 | RM Dashboard (APIs + Next.js) | 9 | 9 | COMPLETE |
| 5 | Existing users + demo polish | 8 | 7 | COMPLETE |
| | **Total** | **60** | **59** | **98% complete** |
