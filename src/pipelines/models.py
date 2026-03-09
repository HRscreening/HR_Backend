from langchain_google_genai import ChatGoogleGenerativeAI


# Gemini model (used for JD parsing, OCR, PDF extraction)
llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0,
    timeout=120,        # 120s HTTP request timeout — prevents indefinite hangs
    max_retries=2,      # Retry up to 2 times on transient errors
)


# Scoring model — uses gemini-2.5-flash (configurable via SCORING_MODEL env var).
# flash-lite is NOT recommended: the scoring schema is deeply nested
# (sections → criteria → sub_criteria + grounding_data) and flash-lite
# frequently returns mismatched keys or malformed JSON.
# Combined with with_structured_output() (native JSON mode), flash produces
# schema-compliant output reliably.
import os
_scoring_model_name = os.environ.get("SCORING_MODEL", "gemini-2.5-flash")
scoring_model = ChatGoogleGenerativeAI(
    model=_scoring_model_name,
    temperature=0,
    timeout=120,
    max_retries=2,
)






