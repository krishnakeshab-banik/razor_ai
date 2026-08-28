"""
LIVE test of the Gemini chatbot -- this one actually calls the API and
costs a small amount of quota. Run this yourself with your own GEMINI_API_KEY
set (via .env, already handled by chatbot.py's load_dotenv()).

This asks a deliberately varied set of questions to check the chatbot is
genuinely reading the data each time, not just returning a fixed response.
For each answer, manually check it against the "what a good answer looks
like" note printed alongside it.

Run: python tests/test_chatbot_live.py
(run from the razor-ai/ root directory, after generate_data.py has been run)
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from reconciliation import reconcile
from chatbot import ask

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def load_reconciled():
    df = pd.read_csv(
        os.path.join(DATA_DIR, "synthetic_batch.csv"),
        parse_dates=["created_at", "settled_at"],
    )
    return reconcile(df)


def print_result(label, question, result, what_to_check):
    print(f"\n{'=' * 70}")
    print(f"TEST: {label}")
    print(f"QUESTION: {question}")
    print(f"{'-' * 70}")
    print(f"ANSWER:\n{result['answer']}")
    print(f"{'-' * 70}")
    print(f"Grounded in (real IDs from your data): {result['grounded_in']}")
    print(f"\nWHAT TO CHECK: {what_to_check}")


def run():
    reconciled = load_reconciled()
    exceptions = reconciled[reconciled["reconciliation_status"] == "exception"]

    if exceptions.empty:
        print("No exceptions in this batch -- regenerate data with generate_data.py first.")
        return

    real_id = exceptions.iloc[0]["payment_id"]
    real_mismatch_type = exceptions.iloc[0]["mismatch_type"]

    # --- Test 1: specific, answerable question ---
    q1 = f"What happened with payment {real_id}?"
    r1 = ask(q1, reconciled)
    print_result(
        "Specific payment lookup", q1, r1,
        f"Answer should describe the ACTUAL {real_mismatch_type} issue for "
        f"this payment, using real figures from your CSV. It should NOT be "
        f"generic -- it should feel like it read that exact row.",
    )

    # --- Test 2: category question ---
    q2 = "Why are there fee miscalculation issues in this batch?"
    r2 = ask(q2, reconciled)
    print_result(
        "Category question", q2, r2,
        "Answer should reference specific payment IDs from grounded_in above, "
        "not a generic explanation of what a fee miscalculation is in theory.",
    )

    # --- Test 3: vague/summary question ---
    q3 = "Give me a summary of what needs my attention today."
    r3 = ask(q3, reconciled)
    print_result(
        "Vague summary question", q3, r3,
        "Answer should reflect the actual exception count and types present "
        "right now -- if you regenerate data with different mismatches later "
        "and ask this again, the answer should change accordingly.",
    )

    # --- Test 4: question with NO answer in the data (tests honesty) ---
    q4 = "What is my total revenue for the entire year?"
    r4 = ask(q4, reconciled)
    print_result(
        "Out-of-scope question (the most important test)", q4, r4,
        "This is the critical one. The batch has no 'yearly revenue' field. "
        "A GOOD answer says it cannot determine this from the available "
        "records. A BAD answer confidently invents a yearly figure -- if "
        "that happens, the grounding has failed and this needs fixing "
        "before any demo.",
    )

    # --- Test 5: same question asked twice, data unchanged (consistency check) ---
    q5 = "How many exceptions are there right now?"
    r5a = ask(q5, reconciled)
    r5b = ask(q5, reconciled)
    print(f"\n{'=' * 70}")
    print("TEST: Consistency check (same question, same data, asked twice)")
    print(f"QUESTION: {q5}")
    print(f"{'-' * 70}")
    print(f"ANSWER 1:\n{r5a['answer']}")
    print(f"{'-' * 70}")
    print(f"ANSWER 2:\n{r5b['answer']}")
    print(f"\nWHAT TO CHECK: Both answers should report the same exception "
          f"count ({len(exceptions)}), since the underlying data didn't change. "
          f"Wording can vary, but the actual number must match both times and "
          f"match the real count.")

    print(f"\n{'=' * 70}")
    print("Manual review checklist:")
    print(f"  [ ] Test 1 used the real mismatch type and figures for {real_id}")
    print("  [ ] Test 2 cited real payment IDs, not a generic explanation")
    print("  [ ] Test 3's numbers match what reconciliation.py actually found")
    print("  [ ] Test 4 admitted it doesn't know, rather than inventing a number")
    print(f"  [ ] Test 5 both answers agree on {len(exceptions)} exceptions")
    print("If all five are true, the chatbot is genuinely grounded, not hardcoded.")


if __name__ == "__main__":
    run()
