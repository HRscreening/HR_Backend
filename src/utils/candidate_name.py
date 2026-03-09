import re
from typing import Optional


_TITLE_TOKENS = {
    "engineer",
    "developer",
    "consultant",
    "manager",
    "lead",
    "architect",
    "analyst",
    "intern",
    "director",
    "coordinator",
    "specialist",
    "principal",
    "head",
    "chief",
    "officer",
    "founder",
    "owner",
    "president",
    "vp",
}

_STOPWORDS = {
    "resume",
    "curriculum",
    "vitae",
    "cv",
    "profile",
    "summary",
    "contact",
    "email",
    "phone",
    "mobile",
    "address",
    "linkedin",
    "github",
    "portfolio",
}


_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.\w+\b")
_NAME_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'.-]*")


def _normalize_name(name: str) -> str:
    cleaned = " ".join(name.strip().split())
    if not cleaned:
        return cleaned
    # If it looks like "RAHUL VERMA", convert to title-case.
    if cleaned.upper() == cleaned:
        return " ".join(w.capitalize() for w in cleaned.split())
    return cleaned


def extract_candidate_full_name(text: str) -> Optional[str]:
    """
    Best-effort name extraction from resume text using strict heuristics.

    This is intentionally conservative (fallback only) to avoid hallucinating names.
    It is designed for texts where line breaks may be flattened into spaces.
    """
    if not text:
        return None

    snippet = " ".join(text.strip().split())[:250]
    if not snippet:
        return None

    # Names usually appear before email/phone/contact sections.
    m = _EMAIL_RE.search(snippet)
    if m:
        snippet = snippet[: m.start()].strip()

    snippet = re.split(r"\b(phone|mobile|contact|email)\b", snippet, flags=re.IGNORECASE)[0].strip()
    snippet = re.sub(r"^(resume|curriculum vitae|cv)\b[:\- ]*", "", snippet, flags=re.IGNORECASE).strip()

    tokens = _NAME_TOKEN_RE.findall(snippet)
    if len(tokens) < 2:
        return None

    # Try 4→2 tokens to capture full names, including middle names/initials.
    for n in (4, 3, 2):
        cand = tokens[:n]
        if len(cand) < 2:
            continue

        lower = [t.lower().strip(".'-") for t in cand]

        if any(t in _STOPWORDS for t in lower):
            continue
        if any(t in _TITLE_TOKENS for t in lower):
            continue

        # Reject things that look like "Software Engineer" (title) or contain digits (already filtered).
        joined = " ".join(cand)
        if len(joined) > 60:
            continue

        # Require at least two substantive tokens (not single-letter only).
        substantive = 0
        for t in cand:
            letters_only = re.sub(r"[^A-Za-z]", "", t)
            if len(letters_only) >= 2:
                substantive += 1
        if substantive < 2:
            continue

        return _normalize_name(joined)

    return None

