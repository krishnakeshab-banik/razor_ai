# Razor-AI Project Assessment

**Assessment date:** 2026-08-28  
**Perspective:** Razorpay payment operations and engineering review  
**Current stage:** Functional proof of concept, not production-ready

## Executive Summary

Razor-AI is a reconciliation assistant that compares payment records with settlement data, identifies exceptions, explains their likely root cause, and uses a Gemini chatbot for natural-language questions about the batch.

The strongest part of the project is the deterministic reconciliation engine. It is transparent, testable, and currently achieves perfect detection against the supplied seeded answer key. The chatbot is appropriately limited to the open-ended question-answering layer rather than being used to calculate financial truth.

The project is not yet a deployable Razorpay-grade product. The HTTP/API layer and frontend are not implemented in the current workspace, persistence modules are empty, dependency declaration is empty, and the live Gemini test requires manual API access and quota. The next phase should focus on turning the validated core into a secure, observable, reviewable workflow.

## What Has Been Completed

### 1. Deterministic reconciliation

`backend/reconciliation.py` processes a transaction batch and adds:

- `reconciliation_status`: `matched` or `exception`
- `mismatch_type`: classified exception cause
- `delta`: settlement difference in paise

The current rules cover:

- Duplicate payment records
- Missing settlement records
- Settlement arithmetic differences
- Settlement timing outside the configured 2-7 day window
- Fee miscalculation against an expected 2% fee
- Unaccounted refunds
- Unclassified discrepancies

The calculations use paise internally, which is the right direction for payment financial data because it avoids floating-point currency calculations.

### 2. Deterministic explanations

`backend/explainations.py` generates plain-language explanations from the reconciliation result. It does not ask an LLM to calculate or classify known financial facts, reducing hallucination risk.

The explanation layer has coverage for the currently generated mismatch types and includes safe handling for missing or unknown types.

### 3. Grounded chatbot retrieval

`backend/chatbot.py` retrieves a maximum of 15 relevant records using payment ID, mismatch type, or status keywords. If no keyword matches, it falls back to current exceptions, which is a reasonable behavior for vague operational questions.

The LLM receives only the retrieved records, not the complete dataset. Each response also returns `grounded_in`, the payment IDs used as context.

### 4. Gemini quota resilience

The chatbot now catches Gemini `429` quota errors and returns a deterministic, grounded fallback containing:

- A clear quota-unavailable message
- Retrieved exception count
- Exception categories and counts
- Real payment IDs for review

Other API errors are still raised, so unrelated failures are not silently hidden. The change was made in both chatbot implementations:

- `backend/chatbot.py`
- `razor-ai-step4/backend/chatbot.py`

### 5. Test coverage completed so far

The following checks have passed:

- Offline chatbot retrieval tests
- Reconciliation evaluation against the supplied answer key
- Deterministic explanation generation tests
- Python compilation for both chatbot implementations
- Simulated Gemini `429` fallback test

## Current Measured Results

The supplied synthetic batch contains 107 records:

| Metric | Result |
|---|---:|
| Total records | 107 |
| Matched records | 85 |
| Exceptions | 22 |
| Match rate | 79.44% |
| Seeded mismatches | 22 |
| Correctly detected | 22 |
| Missed mismatches | 0 |
| False positives | 0 |
| Detection rate | 100% |
| Matched amount reconciled | Rs 228,352.44 |

These results validate the current rules against the generated test fixture. They should not yet be presented as production accuracy because the data is synthetic and the answer key is created from the same controlled scenario.

## Razorpay Perspective

### What is valuable

- **Operational relevance:** Reconciliation exceptions, settlement gaps, duplicate records, refunds, and fee issues are meaningful payment operations problems.
- **Explainability:** Rule-based classifications can be shown to an operations analyst and audited.
- **Financial safety boundary:** Known arithmetic is kept deterministic; the LLM is used only for natural-language interpretation.
- **Grounding approach:** Restricting chatbot context to retrieved records is better than sending an entire batch and asking the model to reason over unbounded data.
- **Good initial evaluation discipline:** The project measures misses and false positives against an answer key instead of relying only on example outputs.
- **Graceful quota behavior:** A temporary free-tier quota problem no longer crashes the chatbot call path.

### Concerns before production use

- **No running API layer:** `backend/main.py` is empty, so there is currently no implemented service boundary, request validation, authentication, or upload workflow.
- **No frontend:** The `frontend` directory is empty, so there is no operational dashboard or analyst review experience.
- **No persistence:** `database.py` and `models.py` are empty. There is no batch history, audit trail, user ownership, exception state, or resolution tracking.
- **No production data contract:** Input schema validation, column typing, currency/country configuration, timezone rules, idempotency, and malformed-row handling are not implemented.
- **Hard-coded business rules:** The 2% fee and timing window are embedded in code. Real Razorpay products need configurable rules by merchant, payment method, geography, product, and effective date.
- **Potential duplicate semantics issue:** Duplicate rows are flagged after the first occurrence, but the business definition of a duplicate needs to distinguish replayed events, legitimate partial captures, retries, and genuinely duplicated payments.
- **Limited reconciliation model:** The current batch-level logic does not yet model partial settlements, chargebacks, reversals, multi-currency amounts, payout batches, ledger entries, or eventual consistency.
- **LLM dependency:** The live chatbot depends on external API availability, quota, latency, and cost. The fallback is useful but does not answer arbitrary questions with the same richness as Gemini.
- **Grounding is not fully verified:** `grounded_in` identifies records supplied to the model, but there is no automated check that every payment ID and number in generated text actually belongs to those records.
- **Secrets and dependencies:** A `.env` file exists in the workspace, while `backend/requirements.txt` is empty. Secret handling, dependency pinning, and deployment configuration need to be formalized.
- **Limited automated tests:** There are no visible API contract tests, security tests, property-based tests, load tests, malformed-input tests, or end-to-end UI tests.
- **No observability or controls:** There are no structured logs, metrics, tracing, alerting, role-based access controls, rate limiting, retention policy, or audit events.

## Ratings

| Area | Rating | Rationale |
|---|---:|---|
| Reconciliation core | 8/10 | Deterministic, readable, and 100% on the supplied seeded fixture |
| Explainability | 7/10 | Clear rule-based explanations with safe fallbacks |
| Chatbot design | 6/10 | Context restriction and quota fallback are sensible, but output verification is incomplete |
| Test discipline | 5/10 | Useful fixture-based tests, but limited production and adversarial coverage |
| Product completeness | 2/10 | API, frontend, persistence, and workflow are not implemented |
| Production readiness | 2.5/10 | Important deployment, security, reliability, and governance controls are absent |
| **Overall proof of concept** | **5.5/10** | A credible technical core that needs productization |

## Recommended Next Steps

### Priority 1: Make the core production-safe

1. Implement a FastAPI service in `backend/main.py`.
2. Add strict input schema validation and clear error responses.
3. Replace hard-coded fee and timing values with versioned configuration.
4. Add idempotency and explicit batch identifiers.
5. Add tests for malformed rows, nulls, duplicate event delivery, partial settlement, and currency precision.
6. Pin dependencies in `requirements.txt` and ensure `.env` is ignored and never committed.

### Priority 2: Build the analyst workflow

1. Create a dashboard showing batch status, match rate, exception counts, amount impact, and filters.
2. Add exception detail views with source values, calculated values, explanation, and resolution status.
3. Support analyst actions such as acknowledge, assign, resolve, and export.
4. Store immutable audit events for every reconciliation and analyst decision.

### Priority 3: Strengthen AI safety and operations

1. Add response validation that rejects generated IDs or figures absent from retrieved records.
2. Cache or deduplicate repeated questions to reduce quota use and latency.
3. Add timeouts, bounded retries, circuit breaking, and provider health metrics.
4. Log prompts and responses safely with sensitive-data redaction and retention controls.
5. Evaluate chatbot answers with a fixed question set and an automated grounding score.

### Priority 4: Validate against real payment operations

1. Test with anonymized production-like samples across merchants and payment methods.
2. Measure precision, recall, false-positive cost, processing time, and analyst review time.
3. Define the ownership model for each exception category.
4. Run a shadow deployment before allowing automated operational decisions.

## Final Verdict

This is a solid reconciliation-engine prototype with a credible design decision: deterministic logic owns financial correctness, while the LLM handles natural-language explanation. The perfect result on the supplied synthetic answer key is encouraging, but it demonstrates fixture correctness rather than production readiness.

From a Razorpay point of view, the project is worth continuing as an internal operations proof of concept. It should not yet be treated as a production reconciliation system or allowed to make unsupervised financial decisions. The highest-value next milestone is an end-to-end analyst workflow with a validated API, persistent audit trail, configurable rules, and real-world evaluation data.
