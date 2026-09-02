# Razor-AI Project Assessment

**Assessment date:** 2026-09-02  
**Perspective:** Razorpay payment operations and engineering review  
**Current stage:** Working AI Finance Controller demo for Buildathon Track 04. Not a production merchant integration.

## Executive Summary

Razor-AI closes one finance-ops loop on a 50+ record Razorpay-shaped batch: **Reconcile → Investigate → Explain → Resolve → Audit → Predict**.

The source of truth is a deterministic engine (`backend/reconciliation.py`). Fees, GST, totals, match rate, cash, withdrawals, and what-if scenarios are never delegated to an LLM. Gemini is optional Q&A over retrieved evidence. If the key is missing or quota is exhausted, books still close.

Measured detection against a **hidden** generated answer key is fixture correctness, not a production accuracy claim.

## What is working

- FastAPI backend + React controller (dashboard, payments, recon, exceptions, cash, GST, withdraw, audit, rules, reports) and a demo store with past-order refunds.
- Ingest with column mapping, malformed-row reporting (rows are kept, not dropped), rupee/paise detection.
- Demo dataset generator (50 / 100 / 250 / 500 / 1000) through the same pipeline as uploads.
- Structured evidence, confidence, exception IDs, HITL actions, SQLite audit, notifications.
- Explain-this-difference waterfall and investigation agent (deterministic).
- Cash position, 1/3/7-day forecast, alerts, what-if, and “Why is cash different?”.
- Synthetic withdrawals: eligibility, preview waterfall, confirm (not a bank transfer).
- Controller intel: briefing, action queue, what-changed, clusters, health, aging, search, timelines.
- Human-taught rules and resolution memory (guidance only; not auto-applied).
- Grounded chatbot with tools; invented `pay_…` IDs are rejected; confirm path for consequential chat actions. Product/how-to questions work without a batch. Secrets, `.env`, answer keys, and customer contact fields are stripped or refused.
- Dashboard home exception list and chat are height-capped with internal scroll.
- Interactive product tour on the live UI (Manual guide). The tour never mutates financial records.
- Tests: `test_reconciliation`, `test_explainations`, `test_chatbot`, `test_demo_payment`, `test_api`, `test_books`, `test_controller_features`, `test_ops_features`, `test_controller_intel`.

## Honest limits

- Not connected to live Razorpay, banks, or GSTN.
- SQLite audit is not a WORM ledger; there is no login or RBAC.
- Default 2% fee / 18% GST-on-fee / T+2 is demo config (`RAZOR_AI_*` env).
- Withdrawals are synthetic ledger entries, not Razorpay payouts.
- Chargebacks, FX, and live payout batches are out of scope.

See `README.md` for run, deploy, and architecture. See `PROJECT_STATUS.md` for the full inventory of what has been built.
