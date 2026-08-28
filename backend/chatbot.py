"""
Chatbot service for Razor-AI. This is the ONLY file in the project that
calls an LLM. Everything else (reconciliation.py, explanations.py) is
deterministic and does not use AI, because those problems already have a
fully known, certain answer.

The chatbot exists for a genuinely different kind of task: an arbitrary
merchant question in natural language ("why is this week lower than last
week?") that a fixed template cannot anticipate. That is the correct place
for an LLM, and only there.

GROUNDING STRATEGY (this is what prevents hallucinated numbers):
1. Never send the whole dataset to the model.
2. Filter down to only the records plausibly relevant to the question
   (retrieve_relevant_records).
3. Pass ONLY that filtered subset into the prompt as context.
4. Instruct the model explicitly to only use what's in that context, and to
   say so plainly if the answer isn't there, rather than guessing.
5. Return which record IDs were used alongside the answer, so the grounding
   is visible and checkable in the UI -- not just claimed.

Uses Google's current Gen AI SDK (google-genai), not the deprecated
google-generativeai package.
    pip install google-genai
"""

import os
from google import genai
from google.genai import errors
from google.genai import types
import pandas as pd
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

SYSTEM_PROMPT = """You are Razor-AI's financial assistant, answering a merchant's
questions about one reconciliation batch.

Rules you must follow:
- Only use the transaction records provided in the context below. Never invent
  a number, payment ID, or date that is not present in the context.
- If the answer cannot be determined from the provided records, say so plainly
  instead of guessing or estimating.
- Keep answers short and specific. Always cite at least one payment_id from the
    context, and for summaries include the exception count and categories.
- Use a plain, professional tone. You report facts about this batch only --
  you do not give financial or legal advice.
"""

MODEL_NAME = "gemini-2.5-flash"


def get_client() -> genai.Client:
    """
    Reads the API key from the environment -- never hardcode it in this file
    or commit it to version control. Set it before starting the backend:
        export GEMINI_API_KEY="your-key-here"       (Mac/Linux)
        set GEMINI_API_KEY=your-key-here             (Windows cmd)
        $env:GEMINI_API_KEY="your-key-here"           (Windows PowerShell)
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Set it as an environment variable "
            "before starting the backend (never hardcode it in this file)."
        )
    return genai.Client(api_key=api_key)


def retrieve_relevant_records(question: str, reconciled_df: pd.DataFrame, limit: int = 15) -> pd.DataFrame:
    """
    Simple keyword-based retrieval -- no vector database needed at this data
    scale. Filters to records whose payment_id, mismatch_type, or status is
    mentioned in the question. Falls back to the current exceptions if
    nothing matches, since that's the most likely thing a merchant is asking
    about with a vague question.

    This function has NO dependency on the Gemini API and can be tested
    completely offline, which is exactly what test_chatbot.py does.
    """
    if reconciled_df.empty:
        return reconciled_df

    q = question.lower()

    def row_matches(r):
        pid = str(r.get("payment_id", "")).lower()
        mtype = str(r.get("mismatch_type", "") or "").lower()
        status = str(r.get("status", "")).lower()
        return (pid and pid in q) or (mtype and mtype.replace("_", " ") in q) or (status and status in q)

    mask = reconciled_df.apply(row_matches, axis=1)
    matched = reconciled_df[mask]

    if matched.empty:
        matched = reconciled_df[reconciled_df["reconciliation_status"] == "exception"]

    return matched.head(limit)


def _quota_fallback(context_df: pd.DataFrame) -> str:
    """Return a grounded answer when the model quota is temporarily exhausted."""
    ids = ", ".join(str(payment_id) for payment_id in context_df["payment_id"])
    mismatch_counts = context_df["mismatch_type"].value_counts()
    categories = ", ".join(
        f"{str(mismatch_type).replace('_', ' ')} ({count})"
        for mismatch_type, count in mismatch_counts.items()
    )
    return (
        "Gemini is temporarily unavailable because the API quota is exhausted. "
        f"The retrieved records contain {len(context_df)} exception(s): {categories}. "
        f"Review payment ID(s): {ids}."
    )


def _is_summary_question(question: str) -> bool:
    terms = ("summary", "attention", "exceptions", "exception count", "overview")
    question_lower = question.lower()
    return any(term in question_lower for term in terms)


def _summary_fallback(context_df: pd.DataFrame) -> str:
    mismatch_counts = context_df["mismatch_type"].value_counts()
    categories = ", ".join(
        f"{str(mismatch_type).replace('_', ' ')} ({count})"
        for mismatch_type, count in mismatch_counts.items()
    )
    ids = ", ".join(str(payment_id) for payment_id in context_df["payment_id"])
    return (
        f"There are {len(context_df)} exceptions requiring attention: {categories}. "
        f"Records reviewed: {ids}."
    )


def _ensure_grounding(answer: str, grounded_ids: list) -> str:
    if any(str(payment_id) in answer for payment_id in grounded_ids):
        return answer
    ids = ", ".join(str(payment_id) for payment_id in grounded_ids)
    return f"{answer.rstrip()} Records used: {ids}."


def ask(question: str, reconciled_df: pd.DataFrame) -> dict:
    """
    Returns {"answer": str, "grounded_in": [payment_id, ...]} so the frontend
    can display which records the answer was based on -- making the "no
    hallucination" claim visually checkable, not just asserted.
    """
    retrieval_limit = len(reconciled_df) if _is_summary_question(question) else 15
    context_df = retrieve_relevant_records(question, reconciled_df, limit=retrieval_limit)
    grounded_ids = context_df["payment_id"].tolist() if not context_df.empty else []

    if context_df.empty:
        return {
            "answer": "There is no data loaded yet for this batch. Load and reconcile a batch first.",
            "grounded_in": [],
        }

    context_json = context_df.to_json(orient="records", date_format="iso")

    client = get_client()
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=f"Context records (JSON):\n{context_json}\n\nQuestion: {question}",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
                max_output_tokens=400,
            ),
        )
    except errors.ClientError as exc:
        if getattr(exc, "code", None) != 429:
            raise
        return {
            "answer": _quota_fallback(context_df),
            "grounded_in": grounded_ids,
        }

    answer = response.text.strip()
    if _is_summary_question(question) and len(answer.replace("*", "").strip()) < 40:
        answer = _summary_fallback(context_df)
    else:
        answer = _ensure_grounding(answer, grounded_ids)

    return {
        "answer": answer,
        "grounded_in": grounded_ids,
    }
