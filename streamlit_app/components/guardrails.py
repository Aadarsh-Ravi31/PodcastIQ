"""
PodcastIQ — Input Guardrails
Validates user queries before they reach any agent.
Covers: length, prompt injection, language, scope.
"""

import re
from dataclasses import dataclass


@dataclass
class GuardrailResult:
    passed: bool
    message: str  # shown to user if failed, empty if passed


# ── 1.1 Query Length ───────────────────────────────────────────────────────────

MIN_CHARS = 3
MAX_CHARS = 500

def check_length(query: str) -> GuardrailResult:
    q = query.strip()
    if len(q) < MIN_CHARS:
        return GuardrailResult(False,
            "Your query is too short. Please ask a complete question.")
    if len(q) > MAX_CHARS:
        return GuardrailResult(False,
            f"Your query is too long ({len(q)} characters). "
            f"Please keep it under {MAX_CHARS} characters.")
    return GuardrailResult(True, "")


# ── 1.2 Prompt Injection Detection ────────────────────────────────────────────

_INJECTION_PATTERNS = [
    r"ignore\s+(your\s+)?(previous\s+)?instructions",
    r"you\s+are\s+now\s+a",
    r"pretend\s+(you\s+)?(have\s+no|are\s+a)",
    r"forget\s+(everything|all|your\s+instructions)",
    r"disregard\s+(your\s+)?(previous\s+)?instructions",
    r"act\s+as\s+(if\s+you\s+are|a\s+different)",
    r"jailbreak",
    r"dan\s+mode",
    r"developer\s+mode",
    r"override\s+(safety|instructions|guidelines)",
    r"system\s*prompt\s*[:=]",
    r"<\s*system\s*>",
]

_INJECTION_RE = re.compile(
    "|".join(_INJECTION_PATTERNS),
    re.IGNORECASE,
)

def check_injection(query: str) -> GuardrailResult:
    if _INJECTION_RE.search(query):
        return GuardrailResult(False,
            "I can't process that query. Please ask something about podcast content.")
    return GuardrailResult(True, "")


# ── 1.4 Scope Classification ───────────────────────────────────────────────────

_OUT_OF_SCOPE_PATTERNS = [
    # Medical advice
    r"\b(what\s+dose|how\s+much\s+should\s+i\s+take|should\s+i\s+take|"
    r"is\s+it\s+safe\s+to\s+take|can\s+i\s+take|dosage\s+for\s+me)\b",
    # Legal advice
    r"\b(am\s+i\s+liable|can\s+i\s+sue|is\s+it\s+legal\s+for\s+me|"
    r"my\s+legal\s+rights|legal\s+advice)\b",
    # Financial advice
    r"\b(should\s+i\s+invest|should\s+i\s+buy\s+stock|"
    r"financial\s+advice|investment\s+advice)\b",
    # Private info about individuals
    r"\b(home\s+address|phone\s+number\s+of|email\s+of|"
    r"where\s+does\s+.{0,30}live|personal\s+information\s+about)\b",
]

_SCOPE_RE = re.compile(
    "|".join(_OUT_OF_SCOPE_PATTERNS),
    re.IGNORECASE,
)

_SCOPE_REDIRECTS = {
    "medical":   "For medical questions, please consult a healthcare professional.",
    "legal":     "For legal questions, please consult a qualified lawyer.",
    "financial": "For financial advice, please consult a financial advisor.",
    "private":   "PodcastIQ doesn't look up personal information about individuals.",
}

def check_scope(query: str) -> GuardrailResult:
    q = query.lower()
    if re.search(r"\b(what\s+dose|how\s+much\s+should\s+i\s+take|should\s+i\s+take|dosage\s+for\s+me)\b", q):
        return GuardrailResult(False,
            "PodcastIQ explores what podcasters said — not personal medical advice. "
            + _SCOPE_REDIRECTS["medical"])
    if re.search(r"\b(am\s+i\s+liable|can\s+i\s+sue|legal\s+advice\s+for\s+me)\b", q):
        return GuardrailResult(False,
            "PodcastIQ explores what podcasters said — not personal legal advice. "
            + _SCOPE_REDIRECTS["legal"])
    if re.search(r"\b(should\s+i\s+invest|financial\s+advice\s+for\s+me|investment\s+advice)\b", q):
        return GuardrailResult(False,
            "PodcastIQ explores what podcasters said — not personal financial advice. "
            + _SCOPE_REDIRECTS["financial"])
    if re.search(r"\b(home\s+address|phone\s+number\s+of|where\s+does\s+\w+\s+live)\b", q):
        return GuardrailResult(False,
            "PodcastIQ doesn't surface personal information about individuals.")
    return GuardrailResult(True, "")


# ── 1.8 Language Detection ─────────────────────────────────────────────────────

# Detect clearly non-English scripts: CJK, Arabic, Cyrillic, Devanagari, Hebrew
_NON_ENGLISH_RE = re.compile(
    r"[\u0600-\u06FF"   # Arabic
    r"\u0400-\u04FF"    # Cyrillic
    r"\u0900-\u097F"    # Devanagari
    r"\u0590-\u05FF"    # Hebrew
    r"\u4E00-\u9FFF"    # CJK Unified Ideographs
    r"\u3040-\u30FF"    # Hiragana / Katakana
    r"\uAC00-\uD7AF"    # Korean Hangul
    r"]"
)

def check_language(query: str) -> GuardrailResult:
    non_eng = _NON_ENGLISH_RE.findall(query)
    # If more than 20% of chars are non-English script, reject
    if len(non_eng) / max(len(query), 1) > 0.2:
        return GuardrailResult(False,
            "PodcastIQ currently supports English queries only. "
            "Please rephrase your question in English.")
    return GuardrailResult(True, "")


# ── Master validator ───────────────────────────────────────────────────────────

def validate_query(query: str) -> GuardrailResult:
    """
    Run all input guardrails in priority order.
    Returns the first failure found, or a passing result.
    """
    for check in [check_length, check_injection, check_language, check_scope]:
        result = check(query)
        if not result.passed:
            return result
    return GuardrailResult(True, "")


# ── Disclaimer text ────────────────────────────────────────────────────────────

RESPONSE_DISCLAIMER = (
    "_PodcastIQ uses AI to extract and analyze podcast content. "
    "Speaker attributions and fact-check verdicts are AI-generated and may contain errors. "
    "Always verify important claims by watching the linked source._"
)
