# 5-minute demo script

This is what we actually show. It is not the feature list. The star loop is the track ask: **Reconciliation → Exceptions → Close the books**. Everything else is a flash or a backup answer.

Open `http://localhost:5173`, enter the controller (not the marketing tour unless asked).

---

## Minute 0:00–0:40 — Setup, one sentence

> “This is a finance controller on a Razorpay-shaped batch. Matching is deterministic — Gemini never calculates settlement. We measure detection against a hidden answer key the engine never sees.”

On **Dashboard**: point at match rate, amount at risk, and **Throughput** (`records / time.perf_counter()` around `reconcile()`, with wall time). Do not linger on the home cards.

---

## Minute 0:40–1:40 — Reconciliation (star)

Go to **Reconciliation**.

1. If the batch is empty: **Generate Demo Dataset** (100 is enough) → **Run engine**.
2. Show the ingest report in one breath: columns mapped, rupees vs paise, malformed rows **kept** (not silently dropped).
3. After the run: matched ₹ vs needs-attention. Say the number of exceptions out loud.

Skip CSV upload unless a judge asks. The live checkout belongs in the flash, not here.

---

## Minute 1:40–3:40 — Exceptions (star)

Go to **Exceptions**.

1. Confirm the **priority** column is not uniform — you should see Critical / High / Medium / Low on the same page (Critical = missing settlement ≥ ₹2,000; High = missing below that, or large amount/delta; Medium = fee/GST/partial/unknown; Low = timing with ~₹0 delta).
2. Click one **fee** or **GST** row → **Explain this difference** (waterfall: GMV → fee → GST → refund → credited → unexplained).
3. **Apply suggested fix**. Row leaves the open queue. Say: “Arithmetic we will rewrite. We will not invent a UTR.”
4. Click a **missing settlement** → show that **Apply fix is blocked**. **Escalate**. That is the honest list.

If time is tight, skip Investigate / cluster batch-resolve. They are backup.

---

## Minute 3:40–4:40 — Close the books (star)

1. **Close books** (from the home strip / close action — do not withdraw).
2. Go to **Reports**. Point at engine validation: seeded / detected / false positives / precision / recall / **Throughput** + **Reconcile time**.
3. Click **Download Word close report**. Open the `.docx` if the machine allows it — cover, KPIs, cash, GST, exception register, all from the live run.

One line: “Close stamps this run. Detection on the original seed stays on the report so we cannot hide leftovers by resolving them.”

---

## Minute 4:40–5:00 — 10-second flashes (pick two)

Do not equal-airtime 16 screens. Flash, then stop.

| Flash | What to show | What not to say |
| --- | --- | --- |
| **Payments** | Rail **All / Matched / Exceptions** — table changes, counts stay batch-wide | Do not walk date presets |
| **Cash** | Available vs in-transit vs at risk; T+2 | Do not run every what-if |
| **Store** | One checkout appears on Payments page 1 | Do not refund unless asked |
| **Chat** | “How do I use Exceptions?” (no batch needed) or a real `pay_…` from the queue | Do not ask it to invent a UTR |

Skip GST, Withdraw, Rules, Audit, Roadmap, Guide unless a judge navigates there.

---

## If they ask about duplicates

Honest answer — this is a known simplification, not a surprise:

> “Today `duplicate_record` means the same `payment_id` already appeared in this batch. The first row is classified on its own merits; the second is the duplicate. That is enough to catch a replayed CSV row.
>
> A production definition has to separate four different things: a **replayed event** (same id, same capture), a **legitimate partial capture** (same order, two amounts), a **retry** (new id, same merchant order), and a **genuinely duplicated payment** (customer charged twice). We do not claim to distinguish those. A real version would key off payment_id + order_id + capture amount + event type, and would not treat two authorized captures on one order as a duplicate.”

Do not improvise a fraud story. The anomaly card that mentions “duplicate-like” customer/amount pairs is a review hint, not a detection claim.

---

## If they ask about “100% detection”

That number is **fixture correctness**, not production accuracy.

- Current `data/synthetic_batch.csv`: 19 seeded / 19 detected / **0 false positives / 0 misses**.
- Fresh batches: 25 extra seeds (0–24) also came back 0 FP / 0 miss. Locked in `tests/test_reconciliation.py` on seeds 7, 11, 19.
- Why it is easy to hit 100% here: the hidden answer key is written by the same generator that injects the mismatch the rules look for. The engine never sees the key.
- Classification order if they probe an interaction: refund present → `unaccounted_refund` even if the credit is also short; fee checked before GST; `duplicate_record` only on the second row with that `payment_id`.
- Chat anti-hallucination is separate: invented `pay_…` tokens are stripped by `_ensure_grounding` (`tests/test_chatbot.py` Test 8).

If a live generate ever shows a false positive, read that payment_id in Exceptions, say the `mismatch_type` and the delta, and whether the key omitted it. Do not hand-wave.

---

## Backup one-liners (only if asked)

- **Throughput:** not a placeholder. `processing_time_seconds` is `time.perf_counter()` around `reconcile()`; `/s` is `rows / that time`.
- **Word report:** `GET /reports/word`, live figures, `python-docx`.
- **Payments rail:** `GET /payments?status=matched|exception`; rail totals are unfiltered.
- **Priority:** named thresholds in `config.py` (`CRITICAL_AMOUNT_PAISE` ₹2,000, `HIGH_AMOUNT_PAISE` ₹5,000, `HIGH_DELTA_PAISE` ₹1,000, `MEDIUM_DELTA_PAISE` ₹50).
- **Withdrawals:** synthetic ledger, not a bank payout.
- **Gemini:** Q&A only; will not share `.env`, answer key, or customer contact fields.
