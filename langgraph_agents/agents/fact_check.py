"""
Fact-Check Agent — verifies claims using Cortex LLM + Brave Search.

Handles queries like:
  - "Is it true that coffee improves cognitive performance?"
  - "Fact check: Sam Altman said AGI will arrive by 2025"
  - "Verify Huberman's claim that cold showers boost testosterone"

Pipeline:
  Stage 1: Cortex llama3.1-70b pre-filter → VERIFIED / FALSE / UNCERTAIN
  Stage 2: Brave Search for UNCERTAIN claims → top 5 web results
  Stage 3: LLM verdict synthesis → VERIFIED / FALSE / OUTDATED / DISPUTED / UNVERIFIED
"""

import os
import json
import logging
import requests

from langgraph_agents.state import PodcastIQState
from langgraph_agents.snowflake_client import execute_scalar

log = logging.getLogger(__name__)

BRAVE_API_KEY = os.getenv("BRAVE_SEARCH", "")
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

# ── Stage 1: Extract claim from user query ─────────────────────────────────────

_EXTRACT_PROMPT = """Extract the factual claim from this podcast fact-check query.

Query: "{query}"

Return a JSON object with:
- claim: the specific claim to fact-check (string)
- speaker: who made the claim, if mentioned (string or null)

Examples:
- "Is it true that coffee improves cognitive performance?" → {{"claim": "coffee improves cognitive performance", "speaker": null}}
- "Fact check Sam Altman saying AGI arrives by 2025" → {{"claim": "AGI will arrive by 2025", "speaker": "Sam Altman"}}
- "Verify Huberman's claim that cold showers boost testosterone" → {{"claim": "cold showers boost testosterone", "speaker": "Andrew Huberman"}}

Respond with ONLY valid JSON — no markdown, no explanation."""


def _extract_claim(query: str) -> dict:
    raw = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-8b', %s)",
        (_EXTRACT_PROMPT.format(query=query),),
    )
    if not raw:
        return {"claim": query, "speaker": None}

    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()

    try:
        result = json.loads(raw)
        return {
            "claim":   result.get("claim", query),
            "speaker": result.get("speaker"),
        }
    except Exception:
        return {"claim": query, "speaker": None}


# ── Stage 1: LLM pre-filter ────────────────────────────────────────────────────

_PREFILTER_PROMPT = """You are a fact-checking assistant. Evaluate this claim based on your training knowledge.

Claim: "{claim}"
{speaker_line}

Classify the claim as exactly one of:
- VERIFIED  : Clearly and confidently TRUE based on established knowledge
- FALSE     : Clearly and confidently FALSE based on established knowledge
- UNCERTAIN : Needs current web sources to verify (recent stats, predictions, debated facts)

Return a JSON object:
- status: "VERIFIED" | "FALSE" | "UNCERTAIN"
- confidence: "HIGH" | "MEDIUM" | "LOW"
- explanation: 1-2 sentence reason for the classification

Respond with ONLY valid JSON — no markdown, no explanation."""


def _llm_prefilter(claim: str, speaker: str | None) -> dict:
    speaker_line = f"Attributed to: {speaker}" if speaker else ""
    prompt = _PREFILTER_PROMPT.format(claim=claim, speaker_line=speaker_line)

    raw = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', %s)",
        (prompt,),
    )
    if not raw:
        return {"status": "UNCERTAIN", "confidence": "LOW", "explanation": ""}

    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()

    try:
        result = json.loads(raw)
        return {
            "status":      result.get("status", "UNCERTAIN"),
            "confidence":  result.get("confidence", "LOW"),
            "explanation": result.get("explanation", ""),
        }
    except Exception:
        return {"status": "UNCERTAIN", "confidence": "LOW", "explanation": ""}


# ── Stage 2: Brave Search ──────────────────────────────────────────────────────

def _brave_search(claim: str) -> list[dict]:
    """Call Brave Search API and return top results."""
    if not BRAVE_API_KEY:
        log.warning("[FactCheck] BRAVE_SEARCH key not set — skipping web search")
        return []

    try:
        resp = requests.get(
            BRAVE_SEARCH_URL,
            headers={
                "Accept":               "application/json",
                "Accept-Encoding":      "gzip",
                "X-Subscription-Token": BRAVE_API_KEY,
            },
            params={"q": claim[:200], "count": 5},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            {
                "title":       item.get("title", ""),
                "url":         item.get("url", ""),
                "description": item.get("description", ""),
            }
            for item in data.get("web", {}).get("results", [])[:5]
        ]
    except Exception as e:
        log.error(f"[FactCheck] Brave Search error: {e}")
        return []


# ── Stage 3: LLM verdict synthesis ────────────────────────────────────────────

_VERDICT_PROMPT = """You are a fact-checking assistant. Given a claim and web search results, determine the final verdict.

Claim: "{claim}"
{speaker_line}

Web search results:
{results_text}

Based ONLY on the search results above, assign one verdict:
- VERIFIED  : Clearly supported by credible sources in the results
- FALSE     : Clearly contradicted by credible sources in the results
- OUTDATED  : Was true at some point but is no longer accurate
- DISPUTED  : Sources in the results meaningfully disagree
- UNVERIFIED: Results don't clearly address the claim

Return a JSON object:
- status: one of the 5 verdicts above
- evidence_summary: 2-3 sentences explaining the verdict, citing specific sources by name
- evidence_urls: list of the most relevant URLs (max 3)

Respond with ONLY valid JSON — no markdown, no explanation."""


def _synthesize_verdict(claim: str, speaker: str | None, search_results: list[dict]) -> dict:
    speaker_line = f"Attributed to: {speaker}" if speaker else ""
    results_text = "\n".join(
        f"{i+1}. {r['title']}\n   {r['url']}\n   {r['description'][:300]}"
        for i, r in enumerate(search_results)
    )

    prompt = _VERDICT_PROMPT.format(
        claim=claim,
        speaker_line=speaker_line,
        results_text=results_text,
    )

    raw = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', %s)",
        (prompt,),
    )
    if not raw:
        return {"status": "UNVERIFIED", "evidence_summary": "Could not synthesize verdict.", "evidence_urls": []}

    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()

    try:
        result = json.loads(raw)
        return {
            "status":           result.get("status", "UNVERIFIED"),
            "evidence_summary": result.get("evidence_summary", ""),
            "evidence_urls":    result.get("evidence_urls", []),
        }
    except Exception:
        return {"status": "UNVERIFIED", "evidence_summary": raw[:500], "evidence_urls": []}


# ── Main agent ─────────────────────────────────────────────────────────────────

_STATUS_BADGE = {
    "VERIFIED":   "✅ VERIFIED",
    "FALSE":      "❌ FALSE",
    "OUTDATED":   "⚠️ OUTDATED",
    "DISPUTED":   "⚠️ DISPUTED",
    "UNVERIFIED": "❓ UNVERIFIED",
}


def fact_check_agent(state: PodcastIQState) -> dict:
    """
    Fact-Check Agent — verifies a claim via LLM pre-filter + Brave Search.

    Args:
        state: Current graph state with user_query

    Returns:
        Updated state with summary (verdict narrative) and graph_results (evidence)
    """
    query = state["user_query"]
    log.info(f"[FactCheck] Processing: '{query}'")

    # Step 1: Extract claim from query
    intent = _extract_claim(query)
    claim  = intent["claim"]
    speaker = intent["speaker"]
    log.info(f"[FactCheck] Claim: '{claim}' | Speaker: {speaker}")

    # Step 2: LLM pre-filter
    prefilter = _llm_prefilter(claim, speaker)
    log.info(f"[FactCheck] Pre-filter: {prefilter['status']} ({prefilter['confidence']})")

    search_results = []
    verdict = {
        "status":           prefilter["status"],
        "evidence_summary": prefilter["explanation"],
        "evidence_urls":    [],
    }

    # Step 3: Brave Search only if LLM is uncertain or low-confidence
    if prefilter["status"] == "UNCERTAIN" or prefilter["confidence"] == "LOW":
        log.info(f"[FactCheck] Running Brave Search for: '{claim[:80]}'")
        search_results = _brave_search(claim)
        log.info(f"[FactCheck] Got {len(search_results)} web results")

        if search_results:
            verdict = _synthesize_verdict(claim, speaker, search_results)
        else:
            verdict["status"] = "UNVERIFIED"

    # Format the answer
    badge = _STATUS_BADGE.get(verdict["status"], "❓")
    speaker_str = f" (attributed to **{speaker}**)" if speaker else ""

    summary_lines = [
        f"{badge}",
        f"",
        f"**Claim:** \"{claim}\"{speaker_str}",
        f"",
        f"**Verdict:** {verdict.get('evidence_summary') or prefilter['explanation']}",
    ]
    if verdict.get("evidence_urls"):
        summary_lines.append("")
        summary_lines.append("**Sources:**")
        for url in verdict["evidence_urls"][:3]:
            summary_lines.append(f"- {url}")

    summary = "\n".join(summary_lines)

    evidence = {
        "claim":            claim,
        "speaker":          speaker,
        "status":           verdict["status"],
        "evidence_summary": verdict.get("evidence_summary", prefilter["explanation"]),
        "evidence_urls":    verdict.get("evidence_urls", []),
        "web_results_used": len(search_results),
        "llm_prefilter":    prefilter,
    }

    return {
        "graph_results": [evidence],
        "summary":       summary,
        "messages":      [f"FactCheck: '{claim[:50]}' → {verdict['status']} (web={len(search_results)})"],
    }
