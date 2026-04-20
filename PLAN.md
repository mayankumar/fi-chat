# FundsIndia WhatsApp AI Advisory Bot — Build Plan

## Phase 1 — Foundation (Core WhatsApp Bot)

### Config & Setup
| # | Task | File | Status |
|---|------|------|--------|
| 1 | FastAPI app, webhook, health check, static mount | `backend/main.py` | DONE |
| 2 | Pydantic settings (Anthropic, Twilio, models) | `backend/config.py` | DONE |
| 3 | Requirements file | `requirements.txt` | DONE |
| 4 | Environment template | `.env.example` | DONE |
| 5 | Gitignore | `.gitignore` | DONE |

### Services
| # | Task | File | Status |
|---|------|------|--------|
| 6 | Session store (dict + JSON snapshot, message history) | `backend/services/session_store.py` | DONE |
| 7 | Twilio sender (text + media via REST) | `backend/services/twilio_sender.py` | DONE |
| 8 | T&C consent gate (disclaimer, YES/EXPERT handling) | `backend/services/consent.py` | DONE |
| 9 | Language detection via Haiku (en/hi/hinglish) | `backend/services/language.py` | DONE |
| 10 | Intent classification via Haiku (12 types + entities) | `backend/services/intent_classifier.py` | DONE |
| 11 | Conversation agent via Sonnet (system prompt + guardrails) | `backend/services/conversation_agent.py` | DONE |

### Handlers
| # | Task | File | Status |
|---|------|------|--------|
| 12 | Intent router (dispatch to handlers) | `backend/handlers/router.py` | DONE |
| 13 | Greeting handler (segment-aware, multilingual) | `backend/handlers/greeting.py` | DONE |
| 14 | Stock redirect (firm refusal + TTA redirect) | `backend/handlers/stock_redirect.py` | DONE |
| 15 | Talk-to-advisor handoff | `backend/handlers/tta.py` | DONE |
| 16 | Research handler (financial concept explanations) | `backend/handlers/research.py` | DONE |

### Cross-cutting
| # | Task | Status |
|---|------|--------|
| 17 | Logging (full pipeline tracing with timing, tokens, response body) | DONE |
| 18 | Python 3.9 compatibility (`__future__` annotations, no match/case) | DONE |

### Verification (manual testing via WhatsApp)
| # | Test Case | Status |
|---|-----------|--------|
| V1 | Server starts: `python3 -m uvicorn backend.main:app --reload` | DONE |
| V2 | `curl /health` returns ok | DONE |
| V3 | Send WhatsApp message → disclaimer appears | NOT TESTED |
| V4 | Reply YES → greeting | NOT TESTED |
| V5 | Ask "What is SIP?" → research answer | NOT TESTED |
| V6 | Ask "What about Reliance stock?" → firm redirect | NOT TESTED |
| V7 | Say "connect me to advisor" → TTA confirmation | NOT TESTED |
| V8 | Send Hinglish message → bot responds in Hinglish | NOT TESTED |

---

## Phase 2 — Advisory Flows (PLANNED, NOT STARTED)

| # | Task | Status |
|---|------|--------|
| 1 | Goal discovery conversational flow | NOT STARTED |
| 2 | Risk assessment questionnaire flow | NOT STARTED |
| 3 | Fund recommendation engine | NOT STARTED |
| 4 | PDF report generation (advisory deck) | NOT STARTED |
| 5 | PDF modification handler | NOT STARTED |
| 6 | Portfolio review flow | NOT STARTED |
| 7 | User segment detection (new/active/dormant from CRM) | NOT STARTED |

## Phase 3 — Production Readiness (PLANNED, NOT STARTED)

| # | Task | Status |
|---|------|--------|
| 1 | Twilio signature validation | NOT STARTED |
| 2 | Rate limiting per phone number | NOT STARTED |
| 3 | Error recovery & retry logic | NOT STARTED |
| 4 | Session expiry & cleanup | NOT STARTED |
| 5 | Metrics / observability | NOT STARTED |
| 6 | Docker deployment | NOT STARTED |
| 7 | CRM / backend API integration | NOT STARTED |

---

## Summary

| Phase | Total | Done | Remaining |
|-------|-------|------|-----------|
| Phase 1 — Foundation | 18 tasks + 8 tests | 18/18 tasks, 2/8 tests | 6 manual tests |
| Phase 2 — Advisory Flows | 7 tasks | 0 | 7 |
| Phase 3 — Production | 7 tasks | 0 | 7 |
