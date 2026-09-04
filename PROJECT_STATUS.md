# Razor-AI — Project status

**Date:** 5 September 2026  
**Stage:** End-to-end AI Finance Controller demo on synthetic Razorpay-shaped batches  
**Audience:** Buildathon judges, teammates, and anyone picking up the repo

This document is the **full inventory of what exists in the repository today**. It is not a production readiness review. If a feature is only sketched in code and not wired to the UI, that is called out.

---

## 1. Problem the project closes

Razorpay merchants still close the books by hand:

- payments CSV vs settlement file vs expected bank credit
- 2% processing fee, and **18% GST on the fee** (not on GMV)
- refunds that never reduced the credited amount
- T+2 cash treated as if it were already in the current account
- missing UTRs chased in Slack with no remaining-exception register

The 2026 builder bar is **verification**, not generation. One cherry-picked match proves nothing. Razor-AI runs the loop on a **50+ record** batch, reports **match rate**, **detection against a hidden answer key**, auto-fixes arithmetic, and leaves an **honest exception list** for what it will not invent (a bank UTR).

Loop: **Reconcile → Investigate → Explain → Resolve → Audit → Predict**.

---

## 2. What a first-time evaluator can do

1. Open the marketing site (`Overview`) and understand the close loop.
2. Read **How it works** (ingest → match → resolve → forecast) and **Roadmap** (Phase 1 live vs later integrations).
3. Click **Get started** (opens the controller) or **Try a live checkout** (Northwind Goods store).
4. **Manual guide → Start Guided Tour** (or topbar **Tour**). The tour navigates the **real** controller (Dashboard → Payments → Exceptions → Cash → GST → Withdraw → Audit → Rules → Reports → Marketplace → Reconciliation). It highlights live UI; it does not click Withdraw, Apply fix, Close books, Generate Demo Dataset, or Refund. Each step has a **mic on/off** control that reads that step in the current language (EN or Hindi). Voice defaults to off.
5. Or buy a product in the **Northwind Goods** demo store (UPI / card / netbanking), pick a simulated settlement outcome, then refund from **Past orders**. Checkout and refunds land in the same reconciliation batch and create controller notifications.
6. Generate (50 / 100 / 250 / 500 / 1000) or upload a CSV/XLSX/TXT batch and run the engine.
7. See match rate, amount at risk, today's briefing, the action queue, cash (available / in transit / blocked / projected), GST lines, and payments with date filters.
8. Open an exception → **Explain this difference** (read-only waterfall) → **Investigate**. Apply arithmetic fixes, acknowledge, waive, escalate missing UTRs, or reopen. Missing settlements are never auto-fixed.
9. Preview a **synthetic withdrawal** (fees / tax / refunds / net received) without the tour submitting it.
10. **Close the books** — auto-fix fee, GST, refund, duplicate, and timing; leftover rows stay on the honest list.
11. Ask settlement **or product/how-to** questions in chat (home compact panel or sidebar **Settlement Q&A**). Matching never calls an LLM. Chat is the only Gemini path. Secrets, API keys, `.env`, answer keys, emails, phones, and invented `pay_…` IDs are refused or stripped. Switch **EN | हिं** to run the dashboard chrome and get answers in Hindi (IDs and amounts stay Latin).

Typical live close on a seeded demo batch: **~100 records, ~80% match before close, ~97% after auto-resolve**, with remaining rows all `missing_settlement`. Exact counts move if you regenerate the seed.

---

## 3. Design rules (unchanged)

| Rule | Why |
| --- | --- |
| Paise internally, rupees in the UI | Avoid float money |
| `expected = amount − fee − tax − refund` | Settlement arithmetic is certain |
| Fee = 2% of GMV; GST = 18% **of the fee** (env-overridable) | Razorpay-shaped pricing |
| Answer key is **hidden** from the engine | Detection rate is measured, not claimed |
| Missing settlement is **never** auto-fixed | The engine will not invent a bank credit |
| Gemini only on `/chat` (and optional confirm) | Reconciliation, cash, GST, withdrawals, and explanations stay deterministic |
| Upload of a merchant file **clears** the answer key | You cannot validate a file you did not seed |
| The product tour never mutates financial records | Education layer over the live app |
| Store GST is 18% **on goods**; recon GST is 18% **on fee** | Two different taxes, labelled |
| Chat never receives API keys, `.env`, answer_key, emails, phones, or card fields | Leak prevention |
| Language preference is local (`razorai-lang`); tour voice is session-only and off by default | Opt-in speech; no extra vendor TTS |

---

## 4. Repository layout

```
Razor_AI/
  backend/                 FastAPI + engine modules (port 8000)
    main.py                HTTP layer
    reconciliation.py      Deterministic match + classify
    explainations.py       Template diagnoses
    investigate.py         Waterfall + ranked causes
    resolution.py          HITL + close-the-books
    cash.py                Position, forecast, what-if, why-different
    ledgers.py             Three-way ledgers + GST lines
    withdrawals.py         Synthetic payout ledger
    controller_intel.py    Briefing, queue, clusters, health, search
    chatbot.py             Only Gemini call
    tools.py               Deterministic tools for chat
    catalog.py             Payments / exception list + filters
    demo_payment.py        Store capture + refunds
    ingest.py              CSV/XLSX mapping + malformed-row report
    notifications.py       Flagged checkout / refund / exception alerts
    recurrence.py          Recurring exception clusters
    time_filters.py        Date/time presets
    database.py            SQLite persistence
    serialize.py           JSON-safe paise/rupees
    config.py              Fee / tax / upload limits
    reports.py             Word close-report builder (`GET /reports/word`)
  frontend/                Vite + React 18 (port 5173)
    src/App.jsx            Marketing / store / controller shell
    src/AppContext.jsx     All live state + API
    src/pages/             Every screen listed in §8
    src/components/        Chat, tour, search, notifications, drawer, language toggle
    src/tour/              Guided-tour steps + TourProvider
    src/i18n/              EN/HI strings, tour Hindi copy, Web Speech helper
    src/lib/api.js         HTTP client (`language` on `/chat`)
    src/lib/format.js      INR, CSV export, chat starter
    public/products/       Store images (jpg + svg)
  data/
    generate_data.py       Seeded batch + hidden answer key
    synthetic_batch.csv    Default ~100-row demo
    answer_key.csv         Ground truth — never fed to the engine
  tests/                   Engine, API, books, store, ops, intel, chatbot
  README.md                How to run
  PROJECT_STATUS.md        This document
  DEMO_SCRIPT.md           5-minute judging script (not the full feature list)
  PROJECT_ASSESSMENT.md    Short review snapshot
  .env.example             GEMINI_API_KEY, VITE_API_URL, RAZOR_AI_*
```

Stack: FastAPI + pandas + SQLite; Vite + React 18 (no React Router — navigation is `activeTab` + `dashPage`). Frontend dependencies: `react`, `react-dom`, `vite` (pinned in `frontend/package.json`). Backend: see `backend/requirements.txt` (pinned: `fastapi`, `uvicorn`, `pandas`, `python-dotenv`, `python-multipart`, `openpyxl`, `google-genai`, `httpx`, `eval_type_backport`, `python-docx`). Python 3.9 venv is supported (`python main.py` or uvicorn). Prefer 3.10+ when available.

---

## 5. Application surface map

Navigation is tab/state, not URL routing.

| `activeTab` | Screen | File |
| --- | --- | --- |
| `overview` | Marketing landing | `LandingPage.jsx` |
| `how-it-works` | Close-loop explainer | `HowItWorksPage.jsx` |
| `roadmap` | Phase 1 live vs later | `RoadmapPage.jsx` |
| `merchant-checkout` | Northwind Goods store | `MerchantPage.jsx` |
| `dashboard` | Controller shell | `Dashboard.jsx` + sub-pages |

Controller `dashPage` (sidebar):

| Group | `dashPage` | Sidebar label |
| --- | --- | --- |
| Control | `home` | Dashboard |
| Control | `chat` | Settlement Q&A |
| Control | `guide` | Manual guide |
| Operations | `payments` | Payments |
| Operations | `reconciliation` | Reconciliation |
| Operations | `exceptions` | Exceptions (badge = open count) |
| Finance | `cash` | Cash |
| Finance | `gst` | GST |
| Finance | `withdraw` | Withdraw |
| Records | `audit` | Audit logs |
| Records | `knowledge` | Rules |
| Records | `reports` | Reports |

Marketplace is **not** in the sidebar. Open it from top bar **Store**, landing **Try a live checkout**, or Manual guide → Marketplace.

---

## 6. Backend — every module

Thin FastAPI app in `backend/main.py`. In-memory `_state` holds the current batch, reconciled frame, resolutions, pending chat action, and ingest report. SQLite holds audit, notifications, withdrawals, store orders, rules, and memory.

### 6.1 Deterministic reconciliation — `reconciliation.py`

Classifies each row:

| `mismatch_type` | Meaning |
| --- | --- |
| `duplicate_record` | Same `payment_id` appears twice |
| `missing_settlement` | No settlement_id / credited amount |
| `timing_mismatch` | Settled later than `RAZOR_AI_MAX_SETTLEMENT_DAYS` (default 7) |
| `fee_miscalculation` | Fee is not the configured % of GMV |
| `tax_line_mismatch` | GST is not the configured % of fee |
| `unaccounted_refund` | Refund did not reduce credited amount |
| `partial_settlement` | Credit is only part of expected net |
| `unknown_adjustment` / `unclassified_discrepancy` | Unexplained remainder |

Outputs `reconciliation_status` (`matched` / `exception`), `mismatch_type`, `delta` (paise), `priority` (Critical / High / Medium / Low), `amount_at_risk`, evidence, `mismatch_breakdown`, `match_kind` (one-to-one / one-to-many / many-to-one annotations without inventing money).

Evaluates against the hidden answer key: seeded / detected / false positives / detection rate. After **close**, the original validation snapshot is kept so detection on the original seed stays honest.

### 6.2 Explanations and investigation — `explainations.py`, `investigate.py`

- Template diagnosis from the classified row. No LLM.
- **Explain this difference:** waterfall GMV → fee → GST → refunds → credited → unexplained.
- **Investigate:** deterministic scan across payment, settlement, fee, GST, refunds; ranked cause; recommended action; related records (same order / settlement / UTR). No invented evidence. Human-taught rules may be quoted; they never post a UTR.

### 6.3 Close the books — `resolution.py`

| Mismatch | Action |
| --- | --- |
| Fee / GST / refund / duplicate | `apply_fix` — rewrite the arithmetic and re-run |
| Timing | `waive` — amounts match; window only |
| Missing settlement / unclassified | `escalate` only — stay on the honest list |

`POST /exceptions/resolve` with `apply_fix` on a missing UTR returns **400**. That is intentional.

HITL actions (all audited): `apply_fix`, `waive`, `escalate`, `acknowledge`, `investigate`, add note, `reject`, `reopen`. Optional **remember this pattern** writes resolution memory; it does not auto-apply later.

`POST /books/close` auto-resolves every auto-fixable row in one pass and returns initial vs final metrics, remaining exceptions, and cash.

`POST /exceptions/batch-resolve` with `confirm: false` previews a cluster; `confirm: true` applies.

### 6.4 Cash — `cash.py`

- **Available** — matched and `settled_at` already passed, minus withdrawals
- **In transit / pending** — matched, not yet dated as settled (typical T+2)
- **Blocked / unresolved** — still in open exceptions
- **Projected** — available + in-transit
- **1 / 3 / 7-day forecast** — expected inflows vs blocked per day
- **Alerts** — unresolved settlements, no inflow, shortfall risk
- **What-if** — delay a settlement (₹ amount), refunds +20%, unresolved not received, extra payout
- **Why is cash different?** (`/cash/why`) — traces expected vs actual across payments, settlements, refunds, fees, GST, withdrawals. Calculation only; it does not move money.

### 6.5 Ledgers and GST — `ledgers.py`

- Three-way view: payments vs settlements vs expected bank credit
- Tax-line matcher: expected GST = configured rate on **fee** vs actual `tax` column (tolerance `RAZOR_AI_TOLERANCE_PAISE`, default ₹1.00)

### 6.6 Withdrawals — `withdrawals.py`

Synthetic payout ledger, **not** a Razorpay payout API and **not** a bank transfer.

- Eligible amount up to an as-of datetime; previously withdrawn funds excluded
- Preview waterfall: requested → fees → tax → refunds/adjustments → net received
- Confirm records the withdrawal, updates cash, and writes audit

### 6.7 Controller intelligence — `controller_intel.py`

All money math is deterministic. Gemini may only describe these payloads.

- Today's finance briefing and health score (0–100 with deductions)
- What changed (yesterday / 7d / previous batch / comparable week)
- Action queue (ranked next steps from live exceptions)
- Recurring clusters + batch-resolve preview vs apply
- Aging, anomalies, refunds, merchant summaries, AI vs human performance
- Record timelines
- Finance search (payments, exceptions, refunds, settlements, GST, withdrawals, audit, customers)
- Human-taught rules and resolution memory (guidance only; not auto-applied)

### 6.8 Chat — `chatbot.py` + `tools.py` (only Gemini call)

Model: `gemini-2.5-flash` via `google-genai`. Key from `GEMINI_API_KEY` only — never hardcoded.

**What it may answer**

1. How the website works (pages, buttons, store, reports, tour) from a built-in **PRODUCT GUIDE**.
2. This merchant's current batch from **retrieved records + tool JSON** only.

**Grounding**

- Keyword retrieval (`retrieve_relevant_records`), cap 15 rows unless the question is a summary
- Columns sent to the model are a whitelist (`SAFE_RECORD_COLUMNS`): payment/order IDs, amounts, fees, tax, refunds, settlement, status, mismatch, GSTIN, method — **no email, phone, name, card**
- Tool JSON and extra context are PII-stripped and truncated before the prompt
- Invented `pay_…` IDs are rejected
- Leak questions (API key, `.env`, answer_key, secrets, customer email, card, OTP) are refused **without calling Gemini**
- Product/how-to questions work with **no batch loaded**
- Finance questions still require a reconciled batch
- Extra context always includes public fee/GST/T+2 config plus redacted cash / GST / batch totals when a run exists
- `/chat` accepts optional `language` (`en` / `hi`). Hindi system rule: Devanagari reply; keep `payment_id`, UTR, batch IDs, GSTIN, and amounts in Latin script. Offline leak / empty-batch / quota fallbacks use the same language.
- `/chat/confirm` for actions that need a human confirm
- Missing API key and Gemini 429 fall back to a grounded summary; recon still works
- Audit stores a truncated Q/A, not secrets

**Deterministic tools** (`tools.py`): `get_batch_summary`, `get_cash_position`, `get_forecast`, `what_if`, `investigate_exception`, `calculate_difference`, `get_high_priority_exceptions`, `get_recurring_discrepancies`, `compare_periods`, `get_tax_lines`, `search_transactions`, `search_financial_records`, `propose_action`.

### 6.9 Demo store — `demo_payment.py`, `catalog.py`

Checkout builds one (or two, for duplicates) live row with the same mismatch vocabulary as `generate_data.py`.

Valid store outcomes: `clean`, `missing_settlement`, `unaccounted_refund`, `fee_miscalculation`, `tax_line_mismatch`, `timing_mismatch`, `duplicate_record`.

`GET /demo/orders` lists past store orders. `POST /demo/refund` (with `confirm`) posts a refund through the engine: batch, recon, cash, GST, notifications, and flagged exceptions update together.

`catalog.py` lists payments **newest first**, with optional `status=all|matched|exception`, search, and date filters. Exception search includes undated rows when no date range is set.

### 6.10 Notifications, recurrence, time filters

- `notifications.py` — new exceptions, live checkout captures (`payment_captured`, not bulk reconcile), refunds; no duplicate on reload
- `recurrence.py` — recurring exception clusters
- `time_filters.py` — presets: all time, today, yesterday, last 7 days, last 30 days, custom date+time. Used by payments, exceptions, audit, withdrawals. If start and end are both empty, the frame is unchanged (undated live checkouts are kept).

### 6.11 Audit and persistence — `database.py`

SQLite file `razorai.db` next to the backend working directory.

| Table | Purpose |
| --- | --- |
| `audit_trail` | Append-only engine / human / Gemini actions |
| `investigations` | Saved investigation payloads |
| `analyst_notes` | HITL notes on a payment |
| `notifications` | Flagged checkouts, refunds, exceptions |
| `withdrawals` | Synthetic payout ledger |
| `store_orders` | Marketplace checkouts |
| `metric_snapshots` | Period comparison snapshots |
| `resolution_memory` | “Remember this pattern” |
| `controller_rules` | Human-taught investigation notes |

Audit source is `rule_engine`, `ops_controller`, `human`, or `gemini_api`.

### 6.12 Ingest — `ingest.py`

- CSV, TXT, XLS, XLSX
- Maps common Razorpay-ish column names (`paymentid`, `gmv`, `gst`, `bank_utr`, …)
- Detects source type (payments / settlements / combined export / …)
- Rupee vs paise detection
- Limits: 8 MB, 1000 rows (env-overridable)
- Upload **clears** `answer_key`
- Malformed rows are kept and flagged, not dropped
- Batch IDs are stable for a loaded batch
- JSON via `serialize.py` (pandas / NaN / timestamps are JSON-safe)

### 6.13 Word report — `reports.py`

`build_word_report(...)` assembles a `.docx` from live figures: cover, executive KPIs, cash, GST, exception register, monthly earnings, recent audit. Served at `GET /reports/word`. Download from Reports (**Download Word close report**) or the Account menu. CSV and text analysis remain available.

### 6.14 Config — `config.py`

| Variable | Default | Meaning |
| --- | --- | --- |
| `RAZOR_AI_FEE_PCT` | `0.02` | Processing fee of GMV |
| `RAZOR_AI_TAX_PCT` | `0.18` | GST of **fee** |
| `RAZOR_AI_MAX_SETTLEMENT_DAYS` | `7` | Timing-break window |
| `RAZOR_AI_EXPECTED_SETTLEMENT_DAYS` | `2` | T+2 display |
| `RAZOR_AI_TOLERANCE_PAISE` | `100` | ₹1 GST/fee tolerance |
| `RAZOR_AI_AUTO_RESOLVE_CONFIDENCE` | `0.90` | Close-books threshold |
| `RAZOR_AI_REVIEW_CONFIDENCE` | `0.60` | Human-review threshold |
| `RAZOR_AI_MAX_UPLOAD_BYTES` | 8 MB | Upload cap |
| `RAZOR_AI_MAX_UPLOAD_ROWS` | 1000 | Upload cap |
| `RAZOR_AI_CRITICAL_AMOUNT_PAISE` | 200000 | Missing settlement ≥ ₹2,000 → Critical |
| `RAZOR_AI_HIGH_AMOUNT_PAISE` | 500000 | Amount ≥ ₹5,000 → High |
| `RAZOR_AI_HIGH_DELTA_PAISE` | 100000 | Unexplained delta > ₹1,000 → High |
| `RAZOR_AI_MEDIUM_DELTA_PAISE` | 5000 | Unexplained delta ≥ ₹50 → Medium |
| `RAZOR_AI_CURRENCY` | `INR` | Display currency |
| `GEMINI_API_KEY` | empty | Optional chat |
| `VITE_API_URL` | `http://localhost:8000` | Frontend API base |

Allowed generate sizes: **50 / 100 / 250 / 500 / 1000**.

### 6.15 API surface

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | Health + public config |
| GET | `/config` | Fee / tax / window config |
| POST | `/batch/load` | Load `data/synthetic_batch.csv` |
| POST | `/batch/generate-fresh?count=` | New batch + hidden answer key |
| POST | `/batch/upload` | Merchant CSV / XLSX / TXT |
| GET | `/batch/status` | Loaded or not |
| GET | `/batch/ingest-report` | Last ingest report |
| POST | `/reconcile/run` | Deterministic match |
| GET | `/reconcile/metrics` | Match rate, validation, amount at risk |
| GET | `/reconcile/exceptions` | Open (or include closed) exceptions |
| GET | `/payments` | Payment list: date/search/`status`/page |
| GET | `/exceptions/search` | Exception search + date + mismatch type |
| GET | `/exceptions/{id}/investigate` | Deterministic investigation |
| GET | `/exceptions/{id}/difference` | Explain-this-difference waterfall |
| GET | `/exceptions/{id}/notes` | Analyst notes |
| POST | `/exceptions/resolve` | `apply_fix` / `escalate` / `waive` / notes |
| POST | `/exceptions/batch-resolve` | Cluster preview or apply |
| POST | `/books/close` | Auto-fix + remainder + cash |
| GET | `/cash/position` | Cash + 7-day forecast + alerts |
| POST | `/cash/what-if` | Scenario recalculation |
| GET | `/cash/why` | Expected vs actual cash breakdown |
| GET | `/ledgers/sources` | Three-way ledgers |
| GET | `/tax/lines` | GST line match |
| GET | `/analytics/summary` | GMV, fees, GST, net, monthly/yearly |
| GET | `/reports/word` | Live `.docx` close report |
| GET | `/audit-trail` | Demo audit log (filterable) |
| GET | `/recurring` | Recurring discrepancy clusters |
| GET | `/withdrawals` | Withdrawal history |
| GET | `/withdrawals/availability` | Eligible balance as-of |
| POST | `/withdrawals/preview` | Analysis waterfall |
| POST | `/withdrawals` | Record synthetic withdrawal |
| GET | `/notifications` | Controller notifications |
| POST | `/notifications/{id}/read` | Mark one read |
| POST | `/notifications/read-all` | Mark all read |
| GET/POST | `/search` | Finance record search |
| GET | `/records/{id}/timeline` | Event timeline |
| GET | `/controller/overview` | Briefing + queue + health + what-changed |
| GET | `/controller/briefing` | Today's briefing |
| GET | `/controller/what-changed` | Period comparison |
| GET | `/controller/clusters` | Recurring exception clusters |
| GET | `/controller/action-queue` | Ranked next actions |
| GET | `/controller/health` | Controller health score |
| GET | `/controller/anomalies` | Anomaly list |
| GET | `/controller/refunds` | Refund view |
| GET | `/controller/aging` | Exception aging |
| GET | `/controller/performance` | Auto vs human |
| GET | `/controller/merchants` | Merchant summaries |
| GET | `/controller/rules` | Human-taught rules |
| POST/PATCH/DELETE | `/controller/rules` | Manage rules (not auto-applied) |
| GET | `/controller/memory` | Resolution memory |
| POST | `/chat` | Grounded Q&A (product + finance) |
| POST | `/chat/confirm` | Confirm a proposed chat action |
| POST | `/demo/simulate-payment` | Store capture |
| GET | `/demo/orders` | Past store orders |
| POST | `/demo/refund` | Store refund through the engine |
| POST | `/demo/reset` | Clear batch + audit + notifications + withdrawals |

Interactive docs: `http://localhost:8000/docs`.

---

## 7. Data generator — `data/generate_data.py`

- Default ~100 rows (~18% seeded mismatches)
- Writes **only** under `data/` (`synthetic_batch.csv`, `answer_key.csv`)
- Extra columns: `payment_method`, `gstin`, `source`, `adjustment`, `utr`
- Seeded types: `missing_settlement`, `unaccounted_refund`, `fee_miscalculation`, `tax_line_mismatch`, `duplicate_record`, `timing_mismatch`, `partial_settlement`, `unknown_adjustment`
- `answer_key.csv` is ground truth and is never fed to the engine
- UI generate sizes: 50 / 100 / 250 / 500 / 1000 through the same pipeline as uploads

---

## 8. Frontend — every page, what it does, and which functions it uses

React 18 + Vite. Marketing, checkout, and controller are separate screens so copy and money state do not mix. `AppContext` owns API, cart, batch, chat, resolve, close, withdrawals, refunds, and a live poll while the controller is open. `LanguageProvider` wraps the shell; `getLocale()` is attached to every `/chat` call.

Error boundary in `main.jsx` catches render crashes and clears a stuck tour from `sessionStorage`. Context modules persist identity across Vite Fast Refresh.

### 8.0 Screen index

| Screen | How you open it | File | Job in one line |
| --- | --- | --- | --- |
| Overview | Header **Overview** / logo | `LandingPage.jsx` | Pitch the close loop; jump to store or controller |
| How it works | Header **How it works** | `HowItWorksPage.jsx` | Explain ingest → match → close → Gemini |
| Roadmap | Header **Roadmap** | `RoadmapPage.jsx` | Phase 1 live vs later integrations |
| Store | **Try a live checkout** / top-bar **Store** | `MerchantPage.jsx` | Demo checkout + refunds into the live batch |
| Controller shell | **Get started** / **Open the controller** | `Dashboard.jsx` | Sidebar, top bar, Close books, Account |
| Dashboard | Sidebar **Dashboard** | `HomePage` in `Dashboard.jsx` | KPIs, cash strip, work queue, exceptions + compact chat |
| Settlement Q&A | Sidebar **Settlement Q&A** | `ChatPage.jsx` | Full-page chat + tool visuals |
| Manual guide | Sidebar **Manual guide** | `GuidePage.jsx` | Start tour or jump to any live page |
| Payments | Sidebar **Payments** | `PaymentsPage.jsx` | Every captured payment, newest first |
| Reconciliation | Sidebar **Reconciliation** | `ReconciliationPage` in `Dashboard.jsx` | Upload / generate / run the engine |
| Exceptions | Sidebar **Exceptions** | `ExceptionsPage` in `Dashboard.jsx` | HITL queue, investigate, fix, escalate |
| Cash | Sidebar **Cash** | `CashPage.jsx` | Available / transit / blocked + what-if |
| GST | Sidebar **GST** | `GstPage.jsx` | Fee-based GST lines vs collected |
| Withdraw | Sidebar **Withdraw** | `WithdrawPage.jsx` | Synthetic payout preview + confirm |
| Audit logs | Sidebar **Audit logs** | `AuditPage` in `Dashboard.jsx` | Append-only engine / human / Gemini trail |
| Rules | Sidebar **Rules** | `KnowledgePage.jsx` | Human investigation notes (not auto-fix) |
| Reports | Sidebar **Reports** | `ReportsPage` in `Dashboard.jsx` | Live earnings charts + engine validation |

Marketplace is **not** in the sidebar.

---

### 8.1 Overview — `LandingPage.jsx`

**Purpose.** Marketing home. Convince a judge that this is a verified close loop, not a chatbot.

| Control | Handler | Effect |
| --- | --- | --- |
| Try a live checkout | `setMerchantView('store'); setActiveTab('merchant-checkout')` | Opens Northwind Goods |
| Open the controller | `setActiveTab('dashboard')` | Opens the finance shell |
| Load demo batch (when no run) | `handleLoadBatch` then `handleRunReconciliation` | `POST /batch/load` + `POST /reconcile/run` |
| Sign in (header) | `triggerToast(...)` | Demo toast only — no auth |

**Shows.** Hero “Close the books. Know the cash.” Live mockup of match rate, record count, open exceptions, and amount matched from the real engine when a batch is already running (`metrics`, `reconciliationRun`, `isConnected`).

---

### 8.2 How it works — `HowItWorksPage.jsx`

**Purpose.** Static explainer of the close loop. No API calls.

**Content.** Three cards: (1) ingest payments / settlements / implied bank credit; (2) rule engine `expected = amount − fee − tax − refund`; (3) close arithmetic then ask Gemini only against retrieved rows. Missing UTRs stay on the honest list.

---

### 8.3 Roadmap — `RoadmapPage.jsx`

**Purpose.** Separate what is live in this repo from later phases that are **not** implemented.

| Phase | Status | Claim |
| --- | --- | --- |
| 1 Finance controller on a 50+ batch | **LIVE** | Match, close, cash, GST, grounded Q&A |
| 2 Live Razorpay + bank hooks | Not built | Production files instead of synthetic batch |
| 3 Route-level fee cards | Not built | UPI vs card MDR instead of flat 2% |
| 4 Autonomous chase | Not built | Tickets for missing UTRs without inventing credits |

---

### 8.4 Store — `MerchantPage.jsx` (`activeTab === 'merchant-checkout'`)

**Purpose.** Inject a real row into the current batch so Dashboard / Payments / Exceptions / Audit update together.

**Views** (`merchantView`): `store` · `cart` · `checkout` · `success` · `orders`.

**Catalogue (₹):** Earbuds 4,999 · Lamp 2,499 · Notebook 899 · Keyboard 6,500 · Stand 3,200 · USB-C Hub 1,899.

| Control | Handler | API |
| --- | --- | --- |
| + / Add to cart | `addToCart` | local cart |
| Qty − / + / remove | `updateCartQty`, `removeCartItem` | local cart |
| Proceed to checkout | `setMerchantView('checkout')` | — |
| Pay (UPI / Card / Netbanking + outcome) | `handleMerchantCheckout` | `POST /demo/simulate-payment` then recon |
| Past orders list | `loadOrders` | `GET /demo/orders` |
| Refund | `refund` → `handleRefundOrder` preview then confirm | `POST /demo/refund` |
| Header Home / Marketplace / Past orders / Controller / Tour / EN–हिं | `setActiveTab`, `setMerchantView`, `openChooser`, `LanguageToggle` | — |

Checkout GST is **18% on goods**. Recon GST is **18% on fee**. Simulated outcomes: clean, missing settlement, unaccounted refund, fee miscalculation, GST mismatch, timing, duplicate.

---

### 8.5 Controller shell — `Dashboard.jsx` (`export default function Dashboard`)

**Purpose.** Chrome around every `dashPage`. Not a money screen itself.

**Sidebar.** Brand click → `setActiveTab('overview')`. Progress bar from `matchPercent(metrics)` and open-exception count. Four groups from §5.

| Control | Handler | API / effect |
| --- | --- | --- |
| ☰ | `setSidebarOpen` | mobile drawer |
| Finance search | `FinanceSearch.run` | `/search` → Exceptions |
| Home | `setActiveTab('overview')` | marketing |
| Store | `setMerchantView('store'); setActiveTab('merchant-checkout')` | store |
| EN / हिं | `LanguageToggle` → `setLocale` | `localStorage` `razorai-lang`; `document.documentElement.lang` |
| Tour | `openChooser` | tour chooser |
| Close books / Load & close | `handleCloseBooks` | load if needed, then `POST /books/close` |
| Bell | `NotificationMenu` | `GET /notifications`; click uses `handleOpenNotification` |
| Account | `setProfileMenuOpen` | Cash, Exception queue, CSV / Word / analysis downloads, `handleResetDemo` (`POST /demo/reset`) |

Live poll: 8s while `activeTab === 'dashboard'` and `isConnected`. **Close books** auto-fixes arithmetic types only.

---

### 8.6 Dashboard home — `HomePage()` (`dashPage === 'home'`)

**Purpose.** Controller desk: how the books look right now, what to do next, and Settlement Q&A.

| Control | Handler | API |
| --- | --- | --- |
| Exception queue / Load a batch | `setDashPage('exceptions' \| 'reconciliation')` | — |
| Cash strip click | `setDashPage('cash')` | — |
| Work-queue row | `setDashPage(item.href)`; `setSelectedExcId(item.focus_id)` | — |
| What-changed chips | `setVersus(...)` | `GET /controller/overview?versus=` |
| Expand exception preview | `setExpandedExc` | — |
| View all / Open queue | `setDashPage('exceptions')` | — |
| Settlement Q&A | `ChatPanel` → `handleSendChat` / `handleSuggestedClick` | `POST /chat` |
| Audit snippet pagination | `setAuditPage` | `GET /audit-trail` |

**Shows.** Greeting + “Controller home”. KPI row (match rate, gross processed, amount matched, open exceptions + at risk). Cash strip (available / T+2 / blocked / 7-day). Work queue (up to 5 ranked actions). Books health ring + deductions. What changed (yesterday / 7d / previous batch / comparable week). Secondary strip (throughput, auto-resolved, human review, GST issues). Engine validation banner when an answer key exists. Books-closed banner after close. **Open exceptions** (up to 40 newest rows, expand for explanation) and **Settlement Q&A** both **480px** with internal scroll (420px under 1024px). Audit snippet (engine vs Gemini).

Intel load: `api.controllerOverview(versus)` whenever a run exists.

---

### 8.7 Manual guide — `GuidePage.jsx` (`dashPage === 'guide'`)

**Purpose.** Teach the live product without fake screenshots.

| Control | Handler |
| --- | --- |
| Start Guided Tour | `startTour()` |
| Hands-on tour | `startTour({ handsOn: true })` |
| Explore manually cards | `go(id)` → `setDashPage(id)` or store for Marketplace |
| Hide / show manual sections | `setManualOpen` |

Cards cover Dashboard, Payments, Exceptions, Cash, GST, Audit, Rules, Marketplace, Withdraw, Reconciliation. Lists real mutating buttons (Generate Demo Dataset, Explain this difference, Investigate, Apply suggested fix, Close books, Confirm withdrawal).

---

### 8.8 Payments — `PaymentsPage.jsx`

**Purpose.** Full payment catalogue (matched **and** exceptions), newest first, so a live checkout appears on page 1.

| Control | Handler | API |
| --- | --- | --- |
| Date/time presets | `setPaymentFilter`; reset page | `GET /payments` |
| Rail All / Matched / Exceptions | `setPaymentStatus` | `GET /payments?status=` |
| Search | `setPaymentSearch` | same |
| Click exception row | `setSelectedExcId`; `setDashPage('exceptions')` | — |
| Prev / Next | `setPaymentPage` | same |

**Shows.** Count, GMV, matched, exceptions. Table: ID, workflow (Unreviewed / Closed), match status, amount, input method, trade date, settlement. Empty until `reconciliationRun`. Rail counts stay batch-wide; the table filters to the selected status.

---

### 8.9 Reconciliation — `ReconciliationPage()` in `Dashboard.jsx`

**Purpose.** Get a batch into memory and run the deterministic engine.

| Control | Handler | API |
| --- | --- | --- |
| Drop file | `handleDropBatch` | `POST /batch/upload` |
| Browse files | `handleBatchFileSelection` | same |
| Download template | `downloadBatchTemplate` | client CSV |
| Run / Re-run engine | `handleRunReconciliation({ force: true })` | `POST /reconcile/run` |
| Size select | `setGenerateCount` | 50–1000 |
| Generate Demo Dataset | `handleGenerateFresh` | `POST /batch/generate-fresh?count=` |

**Shows.** Ingest report (source, units, columns, missing required, warnings, malformed rows kept, preview). Matched ₹ / active batch / needs-attention. Current batch table (stable `batch_id`, loaded time, status, match rate, source).

---

### 8.10 Exceptions — `ExceptionsPage()` in `Dashboard.jsx`

**Purpose.** Human-in-the-loop queue. Arithmetic can be fixed. Missing settlements can only be escalated.

| Control | Handler | API |
| --- | --- | --- |
| Date filter | `setExceptionFilter` | `GET /exceptions/search` |
| Search / mismatch select | `setSearchQuery`, `setMismatchFilter` | same |
| Re-run engine | `handleRunReconciliation({ force: true })` | `POST /reconcile/run` |
| All trades / Unreviewed | `setWorkflow` | client filter |
| Cluster row | `previewCluster` | `POST /exceptions/batch-resolve` `confirm: false` |
| Confirm cluster | `confirmCluster` | same, `confirm: true` |
| Row / payment ID | `setSelectedExcId`; `openPanel('details')` | — |
| Explain this difference | `handleExplainDifference` | `GET /exceptions/{id}/difference` |
| Investigate | `handleInvestigate` | `GET /exceptions/{id}/investigate` |
| Timeline tab | `api.timeline` | `GET /records/{id}/timeline` |
| Apply fix / acknowledge / escalate / waive / reopen | `handleResolveException` | `POST /exceptions/resolve` |
| Remember this pattern | `remember` flag on resolve | resolution memory |
| Escape | `closePanel` | — |

**Shows.** Totals (count, amount affected, high/critical). Ops table: ID, workflow, match status, confidence, issue, priority (Critical / High / Medium / Low from amount and delta — not a single hardcoded badge), captured, expected vs credited, age. Side panel: details, waterfall, investigation, notes. Apply suggested fix is blocked on missing UTR (API 400).

---

### 8.11 Cash — `CashPage.jsx`

**Purpose.** T+2 cash position. Calculation only — this page never posts a payout.

| Control | Handler | API |
| --- | --- | --- |
| Why is my cash different? | `loadWhy` | `GET /cash/why` |
| Delay ₹2L / Refunds +20% / Unresolved not received | `handleWhatIf` | `POST /cash/what-if` |

**Shows.** Available now vs projected (available + in-transit). Cards: available, pending settlement, at risk, expected outgoing. Waterfall + formula. Already-withdrawn note. Alerts. 7-day inflow bars. Last-close remainder if books were closed. Empty until reconciled. Position data: `GET /cash/position` via `fetchFinanceViews`.

---

### 8.12 GST — `GstPage.jsx`

**Purpose.** Tax-line matcher: GST is **18% of processing fee**, not of GMV.

| Control | Handler | Effect |
| --- | --- | --- |
| Click mismatched line | `setSelectedExcId`; `setDashPage('exceptions')` | Opens that payment in Exceptions |

**Shows.** Demo GSTIN `29AABCU9603R1ZX`. Filing status in-balance vs exceptions open. Taxable fee, expected GST, collected, difference. Expected vs collected bars. Statement table (up to 20 lines). Data: `GET /tax/lines`.

---

### 8.13 Withdraw — `WithdrawPage.jsx`

**Purpose.** Synthetic payout ledger (`RAZOR-AI / 000182`). **Not** a bank transfer.

| Control | Handler | API |
| --- | --- | --- |
| As-of datetime / history filter / search | `setAsOf`, `setHistoryFilter`, `setHistorySearch` | `fetchWithdrawals` |
| Amount (debounced 250ms) | `handlePreviewWithdraw` | `POST /withdrawals/preview` |
| Review confirmation | `setConfirmOpen(true)` | — |
| Confirm in modal | `handleConfirmWithdraw` | `POST /withdrawals` |

**Shows.** Available / earned / already withdrawn / refunds in eligible set. Preview waterfall (requested → fees → tax → refunds → net). Last payout. History table. Confirm disabled unless `preview.can_withdraw`.

---

### 8.14 Audit logs — `AuditPage()` in `Dashboard.jsx`

**Purpose.** Append-only demo trail. Rows are never rewritten.

| Control | Handler | Effect |
| --- | --- | --- |
| Date / text / actor / action | `setAuditFilter`, `setAuditSearch`, `setAuditSource`, `setAuditActionType` | `GET /audit-trail` |
| Expand card | `setOpenId` | full details + previous → new state |
| Open `pay_…` | `setSelectedExcId`; `setDashPage('exceptions')` | Exceptions |
| Open `wd_…` | `setDashPage('withdraw')` | Withdraw |

Actors: Rule engine, Controller / human, Gemini. Action filters: exception, match, apply_fix, escalate, investigate, withdrawal, chat.

---

### 8.15 Rules — `KnowledgePage.jsx`

**Purpose.** Standing human guidance quoted by investigation. **Never** auto-fixes money or invents a UTR.

| Control | Handler | API |
| --- | --- | --- |
| Load list | `load` | `GET /controller/rules` |
| Save rule | `create` | `POST /controller/rules` |
| Enable / Disable | `api.updateRule` | `PATCH /controller/rules/{id}` |
| Delete | `api.deleteRule` | `DELETE /controller/rules/{id}` |

Form fields: title, guidance, mismatch type (fee / GST / refund / timing / unknown adjustment), optional payment method and merchant key. List shows influence count (how often investigation quoted the rule).

---

### 8.16 Reports — `ReportsPage()` in `Dashboard.jsx`

**Purpose.** Earning analysis from `/analytics/summary` — live figures, not placeholders.

| Control | Handler | API |
| --- | --- | --- |
| Load & reconcile (empty) | `handleLoadBatch` + `handleRunReconciliation` | batch + recon |
| Overall / Monthly / Yearly | `setPeriod` | client tabs on `analytics` |
| AI vs human strip | `ControllerPerformance` | `GET /controller/performance` |
| Download Word close report | `downloadWordReport` | `GET /reports/word` |

**Shows.** Orders, GMV, GST collected, net settlement. Earnings-mix bars, GMV vs net by month, yearly bars. Engine validation (seeded / detected / false positives / precision / recall / throughput from `time.perf_counter()` around `reconcile()`, plus reconcile wall time) when an answer key exists. Word report is a live `.docx` (cover, KPIs, cash, GST, exception register) — not a placeholder.

---

### 8.17 Shared overlays (not sidebar pages)

| Component | Functions | Role |
| --- | --- | --- |
| `ChatPanel.jsx` | `handleSendChat`, `handleSuggestedClick`, `handleConfirmChatAction`, `handleGroundedTagClick` | Compact home panel + full `ChatPage`. Sends `language: getLocale()`. Chips and intro follow EN/HI. `POST /chat`, `POST /chat/confirm` |
| `LanguageToggle.jsx` + `i18n/` | `useLanguage`, `t()`, `getLocale()` | EN/HI chrome. Stored as `razorai-lang` |
| `ExceptionDrawer.jsx` | `handleOpenDrawer`, resolve / investigate | Deep-dive from grounded `pay_…` chips |
| `DateRangeFilter.jsx` | `onChange` presets + custom date/time | Payments, Exceptions, Audit, Withdraw history |
| `FinanceSearch.jsx` | `run`, `openPayment` | Top-bar search → Exceptions |
| `NotificationMenu.jsx` | `handleOpenNotification`, `handleMarkAllNotificationsRead` | Unread badge; click-through to Payments / Exceptions / GST / Withdraw |
| `ProductTour.jsx` + `TourContext.jsx` | `startTour`, `openChooser`, `localizeTourStep`, `speakText` | Live-DOM steps; Hindi copy from `tourHi.js`; per-step mic (Web Speech, `hi-IN` / `en-IN`); never auto-clicks mutating buttons |
| `Toasts.jsx` | `triggerToast` | Action feedback |

**Chat.** Home compact card 480px with inner scroll; expand opens `dashPage === 'chat'` (same thread). Starter: matching is rule-based; ask how to use a page **or** about this batch; will not share keys or contact fields. Suggestion chips follow the selected language. Disclaimer (compact only): only this panel calls Gemini. Full page shows tool tables/charts from `tool_payload`.

**Tour.** Spotlight + tethered popover on real `data-tour` hooks. Resume via `sessionStorage` key `razorai-product-tour`. Hands-on waits for a real click. **Never** auto-clicks Generate Demo Dataset, Run reconciliation, Apply suggested fix, Close books, Confirm withdrawal, or Refund. Each step can toggle **voice on/off** (`sessionStorage` `razorai-tour-voice`, default off). If left on, the browser reads title + body + meaning + action in EN or Hindi. Speech stops on skip, finish, or unmount.

---

## 9. Tests

Run from repo root:

```bash
python tests/test_reconciliation.py
python tests/test_explainations.py
python tests/test_chatbot.py
python tests/test_ingest.py
python tests/test_demo_payment.py
python tests/test_api.py
python tests/test_books.py
python tests/test_controller_features.py
python tests/test_ops_features.py
python tests/test_controller_intel.py
```

| File | Covers |
| --- | --- |
| `test_reconciliation.py` | Match / classify vs answer key; measured throughput; four priority bands; prints FP / miss IDs |
| `test_explainations.py` | Template text for each mismatch |
| `test_chatbot.py` | Retrieval, leak refuse (EN + Hindi), product Q with empty books, PII strip, invented `pay_…` IDs (offline) |
| `test_chatbot_live.py` | Optional live Gemini |
| `test_ingest.py` | Column aliases, rupee vs paise, malformed rows kept, empty / unsupported files |
| `test_api.py` | HTTP contract (`/chat` skipped — needs a key) |
| `test_demo_payment.py` | Checkout outcomes + refunds |
| `test_books.py` | 50+ load → cash → ledgers → tax → resolve → escalate missing UTR → close |
| `test_controller_features.py` | Controller APIs added for the ops loop |
| `test_ops_features.py` | Payments rail `status=`, Word `.docx`, notifications, withdrawals, date filters |
| `test_controller_intel.py` | Briefing, clusters, cash-why, search, rules, batch-resolve |

---

## 10. How to run

Backend:

```bash
cd backend
pip install -r requirements.txt
# optional
# set GEMINI_API_KEY=your-key
python main.py
# or: python -m uvicorn main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. API is `http://localhost:8000` (see `.env.example`). Docs: `http://localhost:8000/docs`.

Production-style: `npm run build` then serve `frontend/dist` with `VITE_API_URL` pointing at the API.

Regenerate seed data:

```bash
python data/generate_data.py
```

---

## 11. Present in code but not fully productized

These exist in the repo and should not be claimed as finished product features:

| Item | Status |
| --- | --- |
| Settings cog vs Account | Removed — one **Account** menu |
| Marketing **Sign in** | Demo toast only — no auth |

Payments rail All / Matched / Exceptions and the Word `.docx` close report are **wired** (see §8.8 and §8.16). Duplicate detection is still a simplification — see `DEMO_SCRIPT.md`.

---

## 12. What this is not (still out of scope)

- Not connected to live Razorpay, banks, or GSTN
- Default 2% fee / 18% GST-on-fee / T+2 is demo config (`RAZOR_AI_*` env), not per-merchant production pricing
- No login, RBAC, or multi-tenant isolation
- SQLite audit is a demo log, not a WORM ledger
- Withdrawals are synthetic ledger entries, not bank payouts
- Chat grounding rejects invented payment IDs; it does not parse every rupee figure in free text
- Hindi is chrome + chat + tour, not a full translation of every table, briefing, or intel string
- Tour narration depends on the browser/OS having an English or Hindi voice
- 100% detection on the synthetic answer key is **fixture correctness**, not a production accuracy claim
- Chargebacks, FX, and live payout batches are out of scope

Phase 1 in the in-app roadmap is this demo. Later phases (real exports, bank files, production payouts) are described on the Roadmap page and are **not** implemented.

---

## 13. Changelog (after the first controller demo)

Since the first React controller + store + close-the-books loop:

- **Payments** page with backend date/time filters; list is newest-first so live checkouts appear on page 1
- Dedicated **Cash**, **GST**, **Withdraw**, **Rules**, **Manual guide**, and **Reports** pages
- **Marketplace refunds** + **Past orders**; Marketplace removed from the sidebar (Store / guide only)
- Controller **intel**: briefing, what-changed, action queue, clusters, health, aging, anomalies, timelines
- **Why is my cash different?**, finance search, notifications (exceptions, captured checkouts, refunds)
- Resolution **memory**, human-taught **rules**, cluster **batch-resolve** (preview vs confirm)
- Chat **confirm** for consequential suggestions
- Chat **product/how-to** answers without a loaded batch; **leak/PII stripping** before Gemini
- **EN / हिं** language toggle (chrome, store header, chat chips, page titles). Preference in `localStorage`. `/chat` receives `language` so Gemini and fallbacks reply in Hindi (IDs stay Latin)
- Full-page **Settlement Q&A** (`dashPage === 'chat'`) sharing the home conversation; tool visuals from books JSON
- Home **Open exceptions** + **Settlement Q&A** capped at 480px with internal scroll
- Ops-style payments and exceptions tables
- **Interactive product tour** on the live UI (spotlight, route wait, skip missing, hands-on, no auto-mutation). Per-step **mic** narrates the step in the preferred language (Web Speech API, off by default)
- 8-second live refresh of dashboard, payments, cash, GST, notifications
- Error boundary + HMR-safe React context so a tour crash cannot white-screen the app
- Page-by-page inventory in this document (purpose, controls, handlers, APIs)
- Backend runnable as `python main.py` on Python 3.9 venvs (`eval_type_backport`)
- Payments rail All / Matched / Exceptions filters via `GET /payments?status=`
- Word close report: `GET /reports/word` + Reports / Account download
- Throughput is `records / time.perf_counter()` around `reconcile()`, shown with wall time
- Priority bands Critical / High / Medium / Low from named amount and delta thresholds
- Pinned `backend/requirements.txt` and `frontend/package.json`
- Dedicated tests: invented `pay_…` IDs, `ingest.py`, payments rail, Word bytes
- 5-minute demo script in `DEMO_SCRIPT.md`

---

## 14. One-line summary

Razor-AI is a **verified close loop** on a synthetic Razorpay batch: deterministic match, measured detection, auto-fix of arithmetic, cash / GST / withdrawals, a live demo checkout with refunds, a guided tour of the real product (optional spoken steps in EN/Hindi), and Gemini only for questions about the website and the loaded books — in English or Hindi — with missing settlements left on an honest list instead of a generated UTR.
