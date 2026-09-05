# Razor-AI — AI Finance Controller

Closes one finance-ops loop on a **50+ record** Razorpay-shaped batch: match payments to settlements, auto-fix the arithmetic, forecast cash, and leave an **honest exception list** for what the agent will not invent (missing UTRs).

The 2026 builder bar is **verification**, not generation speed. Throughput, measured accuracy against a hidden answer key, and exceptions the agent could not resolve.

## What is AI Finance Controller?

An ops employee for Razorpay settlements:

**Reconcile → Investigate → Explain → Resolve → Audit → Predict**

It is not a generic chatbot and not a CSV toy. Arithmetic, GST, fees, totals, and cash are **deterministic**. Gemini is used only to talk about evidence the engine already computed.

## Problem being solved

Razorpay finance teams still:

- Match payments vs settlements vs expected bank credit by hand
- Apply 2% fee and **18% GST on the fee** (not on GMV)
- Miss refunds that never reduced the credited amount
- Treat T+2 cash as if it were already in the current account
- Chase missing UTRs in Slack with no remaining-exception register

## Architecture

```
CSV / generate demo  →  ingest.py (validate, map, flag malformed)
                     →  reconciliation.py (match + classify + evidence)
                     →  investigate.py (waterfall + ranked causes)
                     →  resolution.py (fix / escalate / HITL / memory)
                     →  cash.py (position, 7-day, what-if, why-different)
                     →  withdrawals.py (eligible cash, preview, synthetic payout)
                     →  controller_intel.py (briefing, queue, clusters, health)
                     →  chatbot.py (tools JSON → Gemini explains, never calculates)
                     →  SQLite audit / notifications / rules / store orders
```

Frontend (Vite + React) talks to FastAPI on port 8000. Marketing, demo store, and controller are separate pages. **Manual guide** runs an interactive tour over the live UI. **EN | हिं** switches controller chrome and store header; the same preference is sent on `/chat` so Settlement Q&A can answer in Hindi. Each tour step has a mic toggle that reads that step aloud in the selected language (browser speech, off by default).

## Data flow

1. **Generate demo dataset** (50 / 100 / 250 / 500 / 1000) or **upload CSV/XLSX**.
2. Ingest reports detected columns, source type, units (rupees vs paise), warnings, and malformed rows. Invalid rows are **not silently dropped**.
3. The same `reconcile()` function processes generated and uploaded data.
4. Hidden `answer_key.csv` exists only for generated batches, for evaluation. The UI does not treat it as the operational answer.
5. Uploads **clear** the answer key so you cannot “validate” a file you did not seed.

## Reconciliation methodology

`expected_net = amount − fee − tax − refund`

- Fee should be `RAZOR_AI_FEE_PCT` of GMV (default 2%).
- GST should be `RAZOR_AI_TAX_PCT` of **fee** (default 18%).
- Settlement later than `RAZOR_AI_MAX_SETTLEMENT_DAYS` (default 7) is a timing break.
- Duplicate `payment_id` is flagged.
- Partial credits and unexplained adjustments are classified, not forced to match.
- One-to-many (same `order_id`) and many-to-one (same `settlement_id`) are annotated as `match_kind` without inventing money.

Every row gets **status, confidence, evidence signals, calculation, explanation**. Explanations are templates from those signals, not LLM prose.

## AI architecture

- **Never** the authority for arithmetic, tax, fee, totals, or balances.
- Chat runs **deterministic tools** first (`get_batch_summary`, `investigate_exception`, `get_cash_position`, `what_if`, …).
- Gemini only describes that JSON. If the model invents a `pay_…` ID that was not retrieved, the answer is rejected.
- `POST /chat` accepts `language` (`en` or `hi`). Hindi replies use Devanagari; `payment_id`, UTR, batch IDs, and amounts stay in Latin script. Leak/empty/quota fallbacks are also localized.
- If `GEMINI_API_KEY` is missing or quota is exhausted: recon, dashboard, exceptions, and explanations still work. The user sees that AI investigation is temporarily unavailable.

Uploaded descriptions are **data**, not system instructions.

## Exception workflow

Statuses: Open, Investigating, Awaiting Review, Resolved, Rejected, Unresolved.

Analyst actions (all audited): apply fix, waive, escalate, acknowledge, investigate, assign, add note, reject, reopen.

**Explain this difference** shows a waterfall: GMV → fee → GST → refunds → adjustments → expected net → actual credited → remaining unexplained.

Missing settlements are **never** auto-fixed. That is the honest remainder.

## Cash forecasting

Deterministic:

Available (matched, `settled_at` in the past)
+ in transit (matched, not yet settled)
− blocked (open exceptions)
+ dated inflows over 1 / 3 / 7 days

What-if scenarios (delay a settlement, refunds +20%, unresolved not received) recalculate the same formulas. **Why is cash different?** traces expected vs actual across payments, settlements, refunds, fees, GST and withdrawals. Synthetic withdrawals subtract from available cash; they are not bank transfers.

## Evaluation methodology

For generated batches only, `evaluate_against_answer_key` computes true positives, false positives, misses, precision, recall, detection rate. This is **fixture accuracy**, not production accuracy. The main dashboard shows operational match rate from the live batch.

## How to run locally

Backend:

```bash
cd backend
pip install -r requirements.txt
# optional, for settlement Q&A
# set GEMINI_API_KEY=your-key
uvicorn main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. API docs: `http://localhost:8000/docs`.

## How to deploy

This repo is two processes. **Vercel hosts the React UI.** The FastAPI engine (in-memory batch + SQLite) cannot stay durable as a Vercel serverless function, so the API goes on a small always-on host such as **Render**.

Do not put `GEMINI_API_KEY` or Razorpay secrets in Vercel. Those belong only on the API host.

### 1. API on Render

1. Open [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint** and connect `https://github.com/krishnakeshab-banik/razor_ai` (or **New Web Service** and point it at the same repo).
2. If you use the repo `render.yaml`: service name `razor-ai-api`, start command `uvicorn main:app --app-dir backend --host 0.0.0.0 --port $PORT`.
3. Set env vars on that service (never commit them):
   - `GEMINI_API_KEY` — optional, Settlement Q&A
   - `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` — optional, Test Mode checkout
4. Wait until the service is **Live**. Copy the URL, e.g. `https://razor-ai-api.onrender.com` (no trailing slash).
5. Free Render instances sleep after idle time. The first request after sleep can take ~30–50s.

SQLite and the in-memory batch reset when the API dyno restarts. That is expected for this demo.

### 2. UI on Vercel

The GitHub repo already has a root `vercel.json` (build `frontend/`, publish `frontend/dist`).

1. Open [Vercel](https://vercel.com/new) → **Import** `krishnakeshab-banik/razor_ai`.
2. Leave Root Directory empty (the root `vercel.json` already targets `frontend/`).
3. **Settings → Environment Variables** → add **Production** (and Preview if you want):
   - `VITE_API_URL` = the Render URL from step 1 (`https://….onrender.com`)
4. Deploy. `VITE_API_URL` is baked in at **build** time — if you change it later, Redeploy.

Or from this machine, already signed in to the Vercel CLI:

```bash
vercel --prod
```

Then set `VITE_API_URL` in the project Environment Variables and redeploy.

Local production-style (no Vercel): run uvicorn, `npm run build` in `frontend`, serve `frontend/dist`, with `VITE_API_URL` pointing at the API.

## Environment variables

See `.env.example`.

| Variable | Purpose |
| --- | --- |
| `GEMINI_API_KEY` | Optional chat |
| `RAZORPAY_KEY_ID` | Optional Razorpay Test Mode public key (Checkout.js) |
| `RAZORPAY_KEY_SECRET` | Optional Razorpay Test Mode secret (server HMAC only — never sent to the browser) |
| `VITE_API_URL` | Frontend API base (default `http://localhost:8000`) |
| `RAZOR_AI_FEE_PCT` | Default `0.02` |
| `RAZOR_AI_TAX_PCT` | Default `0.18` (on fee) |
| `RAZOR_AI_MAX_SETTLEMENT_DAYS` | Default `7` |
| `RAZOR_AI_TOLERANCE_PAISE` | Default `100` |
| `RAZOR_AI_MAX_UPLOAD_BYTES` | Default 8 MB |
| `RAZOR_AI_MAX_UPLOAD_ROWS` | Default 1000 |

## Supported data formats

CSV, TXT, XLS, XLSX. Combined Razorpay-shaped exports (payment + settlement columns) are the happy path. Optional columns: `customer_id`, `utr`, `adjustment`, `payment_method`, `gstin`. Amounts may be rupees or paise; ingest detects which.

## Product surface

Controller sidebar: Dashboard, Settlement Q&A, Payments, Reconciliation, Exceptions, Cash, GST, Withdraw, Audit logs, Rules, Manual guide, Reports.

- **Dashboard** — match rate, briefing, action queue, cash strip, exception preview, compact chat.
- **Settlement Q&A** — full-page conversation (same thread as the home panel). Tables/charts come from tool JSON, not Gemini.
- **Payments** — batch payments with date/time filters and All / Matched / Exceptions rail.
- **Exceptions** — queue, filters, Explain this difference, investigate, HITL resolve.
- **Cash** — available / pending / unresolved / projected; Why is my cash different?; what-if.
- **GST** — expected vs collected on the processing fee; tax-line table.
- **Withdraw** — eligible balance, analysis waterfall, synthetic confirm (not a bank transfer).
- **Manual guide** — Start Guided Tour (live UI, no fake screenshots) or explore pages manually.
- **Store** (header, not sidebar) — Northwind Goods checkout + Past orders refunds.
- **Language** — **EN | हिं** on the marketing header, controller topbar, and store header. Preference is stored in `localStorage` (`razorai-lang`). Sidebar, home KPIs, page titles, chat chips, and tour copy switch immediately. Table cells and engine IDs stay as recorded.

The tour highlights real controls. It will not auto-click Withdraw, Apply fix, Close books, Generate Demo Dataset, or Refund. Drag the instruction box to keep it out of the way — the position holds until you start a new tour. Each step can turn **voice on or off**; if left on, the browser reads that step’s title, meaning, and action in English or Hindi. English prefers a more natural installed voice. Voice preference is session-only (`razorai-tour-voice`) and defaults to off.

On a phone (about 360–428px) the controller and store use card lists, bottom sheets, and sticky Pay / Proceed actions. That is layout only — the same APIs run as on desktop.

For a 5-minute judging pass, follow `DEMO_SCRIPT.md` (Reconciliation → Exceptions → Close books). Do not equal-airtime every page.

## Demo workflow

1. Open the app → **Get started**.
2. Optional: switch **हिं** if you want the controller and answers in Hindi. **Manual guide → Start Guided Tour** walks the live product; turn the mic on for a spoken explanation of each step.
3. **Generate Demo Dataset** (100+) or upload a CSV on Reconciliation.
4. Engine runs. Dashboard shows match rate, exceptions, amount at risk (all calculated).
5. Open **Exceptions** → **Explain this difference** → **Investigate**.
6. Apply high-confidence arithmetic fixes, or escalate missing UTRs.
7. **Close books** auto-resolves only auto-fixable types.
8. Ask the assistant “How much cash tomorrow?” or “What if the ₹2 lakh settlement is delayed?” (in Hindi after switching हिं).
9. Read the audit trail. Preview a withdrawal without treating it as a bank payout.

Optional: **Store** checkout injects a live payment with a chosen settlement outcome. **Past orders** can refund through the same engine.

## Tests

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

Judging loop (not the full feature list): `DEMO_SCRIPT.md`.

## Known limitations

- Not connected to live Razorpay, banks, or GSTN.
- Default fee/GST/T+2 are demo config, not per-merchant production pricing.
- No login, RBAC, or multi-tenant isolation.
- SQLite audit is a demo log, not a WORM ledger.
- Withdrawals are synthetic ledger entries, not bank payouts.
- Chat grounding rejects invented payment IDs; it does not parse every rupee figure in free text.
- Hindi covers chrome, chat, and tour — not every table cell or intel briefing string.
- Tour voice uses the browser Web Speech API; a Hindi voice is only as good as the OS/browser voices installed.
- 100% detection on the synthetic answer key is **fixture correctness**, not a production accuracy claim.
- Chargebacks, FX, and live payout batches are out of scope.

## Design choices

- Paise internally, rupees in the UI.
- Answer key hidden from the engine.
- Missing settlement is never auto-fixed.
- No hard-coded dashboard metrics.
