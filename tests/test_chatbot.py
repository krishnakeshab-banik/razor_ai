"""
Tests the OFFLINE part of chatbot.py -- retrieve_relevant_records -- against
real reconciled data. This does NOT call the Gemini API and needs no API
key, so it can run in CI or on any machine.

It does NOT test the actual model response quality (that requires a live
GEMINI_API_KEY and a manual check -- see the instructions printed at the
end of this script for how to do that yourself).

Run: python tests/test_chatbot.py
(run from the razor-ai/ root directory, after generate_data.py has been run)
"""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from reconciliation import reconcile
from chatbot import retrieve_relevant_records

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def run():
    df = pd.read_csv(
        os.path.join(DATA_DIR, "synthetic_batch.csv"),
        parse_dates=["created_at", "settled_at"],
    )
    reconciled = reconcile(df)
    exceptions = reconciled[reconciled["reconciliation_status"] == "exception"]

    print("=== Test 1: question mentioning a real payment_id ===")
    real_id = exceptions.iloc[0]["payment_id"]
    result = retrieve_relevant_records(f"What happened with {real_id}?", reconciled)
    assert real_id in result["payment_id"].values, "Failed to retrieve the exact record asked about"
    assert len(result) <= 15, "Should never return more than the limit"
    print(f"  Asked about {real_id} -> retrieved {len(result)} record(s), correct one included: PASS\n")

    print("=== Test 2: question mentioning a mismatch type ===")
    result = retrieve_relevant_records("why are there fee miscalculation issues?", reconciled)
    if not result.empty:
        assert (result["mismatch_type"] == "fee_miscalculation").any(), \
            "Should retrieve at least one fee_miscalculation record"
    print(f"  Asked about 'fee miscalculation' -> retrieved {len(result)} record(s): PASS\n")

    print("=== Test 3: vague question with no matching keywords ===")
    result = retrieve_relevant_records("how is everything looking today?", reconciled)
    assert not result.empty, "Should fall back to exceptions rather than return nothing"
    assert (result["reconciliation_status"] == "exception").all(), \
        "Fallback should only contain exceptions, not matched records"
    print(f"  Vague question -> fell back to {len(result)} exception(s): PASS\n")

    print("=== Test 4: retrieval never returns more rows than exist ===")
    result = retrieve_relevant_records("show me everything", reconciled, limit=1000)
    assert len(result) <= len(reconciled), "Cannot retrieve more rows than the dataset contains"
    print(f"  Retrieved {len(result)} of {len(reconciled)} total rows: PASS\n")

    print("All offline retrieval tests passed.")
    print("\n--- To test the live Gemini responses yourself ---")
    print("1. pip install google-genai   (uninstall old google-generativeai if present)")
    print("2. Set your key:  export GEMINI_API_KEY=\"your-key-here\"")
    print("3. In a Python shell, from the razor-ai/backend folder, run:")
    print("     from chatbot import ask")
    print("     import pandas as pd")
    print("     from reconciliation import reconcile")
    print("     df = pd.read_csv('../data/synthetic_batch.csv', parse_dates=['created_at','settled_at'])")
    print("     reconciled = reconcile(df)")
    print("     result = ask('Why are there so many exceptions?', reconciled)")
    print("     print(result['answer'])")
    print("     print('Grounded in:', result['grounded_in'])")
    print("4. Check the printed answer: does it only mention payment IDs that")
    print("   are actually in your data (the grounded_in list)? Any ID it")
    print("   invents that isn't in that list is a grounding failure.")


if __name__ == "__main__":
    run()
