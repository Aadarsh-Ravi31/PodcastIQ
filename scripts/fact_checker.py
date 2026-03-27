"""
Batch Fact-Checker — processes all PENDING VERIFIABLE_FACT + STATISTICAL claims in SEM_CLAIMS.

Usage:
  python scripts/fact_checker.py                    # Process all (default budget: 500 web searches)
  python scripts/fact_checker.py --limit 100        # Process first 100 claims
  python scripts/fact_checker.py --stage1-only      # LLM pre-filter only, no web search
  python scripts/fact_checker.py --dry-run          # Preview without writing to Snowflake
  python scripts/fact_checker.py --web-budget 200   # Limit Brave Search calls

Pipeline:
  Stage 1: Cortex llama3.1-70b pre-filter on every claim
           HIGH confidence VERIFIED/FALSE → write immediately (LLM_ONLY)
           UNCERTAIN or LOW confidence   → queue for Stage 2
  Stage 2: Brave Search for uncertain claims (respects --web-budget)
  Stage 3: LLM verdict synthesis → final status + evidence
  Update:  SEM_CLAIMS.VERIFICATION_STATUS + EVIDENCE_SUMMARY + EVIDENCE_URLS
"""

import os
import sys
import json
import time
import logging
import argparse
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from langgraph_agents.snowflake_client import execute, execute_scalar, get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

BRAVE_API_KEY    = os.getenv("BRAVE_SEARCH", "")
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

# ── Fetch pending claims ───────────────────────────────────────────────────────

_FETCH_SQL = """
SELECT
    CLAIM_ID,
    CLAIM_TEXT,
    CLAIM_TYPE,
    SPEAKER,
    CHANNEL_NAME,
    CLAIM_DATE,
    YOUTUBE_URL
FROM SEMANTIC.SEM_CLAIMS
WHERE CLAIM_TYPE IN ('VERIFIABLE_FACT', 'STATISTICAL')
  AND VERIFICATION_STATUS = 'PENDING'
  AND LEN(CLAIM_TEXT) > 30
ORDER BY CLAIM_DATE DESC NULLS LAST
"""

# ── Update SEM_CLAIMS ──────────────────────────────────────────────────────────

_UPDATE_SQL = """
UPDATE SEMANTIC.SEM_CLAIMS
SET
    VERIFICATION_STATUS = %s,
    VERIFICATION_SOURCE = %s,
    LAST_VERIFIED       = CURRENT_TIMESTAMP(),
    EVIDENCE_SUMMARY    = %s,
    EVIDENCE_URLS       = PARSE_JSON(%s)
WHERE CLAIM_ID = %s
"""

# ── Stage 1: LLM pre-filter ────────────────────────────────────────────────────

_PREFILTER_PROMPT = """You are a fact-checking assistant. Evaluate this claim based on your training knowledge.

Claim: "{claim}"
Type: {claim_type}
Speaker: {speaker}

Classify as exactly one of:
- VERIFIED  : Clearly TRUE based on established, well-known facts (HIGH confidence only)
- FALSE     : Clearly FALSE based on established, well-known facts (HIGH confidence only)
- UNCERTAIN : Needs current web sources — recent statistics, forward-looking claims, debated facts

Return JSON:
- status: "VERIFIED" | "FALSE" | "UNCERTAIN"
- confidence: "HIGH" | "MEDIUM" | "LOW"
- explanation: 1 sentence reasoning

Respond with ONLY valid JSON — no markdown, no explanation."""


def _llm_prefilter(claim_text: str, claim_type: str, speaker: str) -> dict:
    prompt = _PREFILTER_PROMPT.format(
        claim=claim_text[:500],
        claim_type=claim_type,
        speaker=speaker or "Unknown",
    )
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
        r = json.loads(raw)
        return {
            "status":      r.get("status", "UNCERTAIN"),
            "confidence":  r.get("confidence", "LOW"),
            "explanation": r.get("explanation", ""),
        }
    except Exception:
        return {"status": "UNCERTAIN", "confidence": "LOW", "explanation": ""}


# ── Stage 2: Brave Search ──────────────────────────────────────────────────────

def _brave_search(claim_text: str) -> list[dict]:
    if not BRAVE_API_KEY:
        return []
    try:
        resp = requests.get(
            BRAVE_SEARCH_URL,
            headers={
                "Accept":               "application/json",
                "Accept-Encoding":      "gzip",
                "X-Subscription-Token": BRAVE_API_KEY,
            },
            params={"q": claim_text[:200], "count": 5},
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
        log.warning(f"Brave search failed: {e}")
        return []


# ── Stage 3: LLM verdict synthesis ────────────────────────────────────────────

_VERDICT_PROMPT = """Fact-check this claim using the provided web search results.

Claim: "{claim}"

Web search results:
{results_text}

Assign one verdict:
- VERIFIED  : Supported by credible sources in the results
- FALSE     : Contradicted by credible sources in the results
- OUTDATED  : Was true at some point but is now inaccurate
- DISPUTED  : Sources meaningfully disagree
- UNVERIFIED: Results don't clearly address the claim

Return JSON:
- status: one of the 5 verdicts above
- evidence_summary: 2-3 sentences citing specific sources
- evidence_urls: list of up to 3 relevant URLs

Respond with ONLY valid JSON — no markdown, no explanation."""


def _synthesize_verdict(claim_text: str, search_results: list[dict]) -> dict:
    results_text = "\n".join(
        f"{i+1}. {r['title']}\n   {r['url']}\n   {r['description'][:200]}"
        for i, r in enumerate(search_results)
    )
    prompt = _VERDICT_PROMPT.format(claim=claim_text[:400], results_text=results_text)

    raw = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', %s)",
        (prompt,),
    )
    if not raw:
        return {"status": "UNVERIFIED", "evidence_summary": "", "evidence_urls": []}

    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()

    try:
        r = json.loads(raw)
        return {
            "status":           r.get("status", "UNVERIFIED"),
            "evidence_summary": r.get("evidence_summary", ""),
            "evidence_urls":    r.get("evidence_urls", []),
        }
    except Exception:
        return {"status": "UNVERIFIED", "evidence_summary": raw[:500], "evidence_urls": []}


# ── Update helper ──────────────────────────────────────────────────────────────

def _update_claim(conn, claim_id: str, status: str, source: str, summary: str, urls: list):
    try:
        cur = conn.cursor()
        cur.execute(_UPDATE_SQL, (status, source, summary[:2000], json.dumps(urls), claim_id))
        conn.commit()
        cur.close()
    except Exception as e:
        log.error(f"Failed to update {claim_id}: {e}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Batch fact-checker for SEM_CLAIMS")
    parser.add_argument("--limit",       type=int, default=0,   help="Max claims to process (0=all)")
    parser.add_argument("--stage1-only", action="store_true",   help="LLM pre-filter only, no Brave Search")
    parser.add_argument("--dry-run",     action="store_true",   help="Don't write to Snowflake")
    parser.add_argument("--web-budget",  type=int, default=500, help="Max Brave Search calls (default 500)")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("Batch Fact-Checker Starting")
    log.info(f"  stage1-only : {args.stage1_only}")
    log.info(f"  web-budget  : {args.web_budget}")
    log.info(f"  dry-run     : {args.dry_run}")
    log.info("=" * 60)

    # Fetch claims
    claims = execute(_FETCH_SQL)
    if args.limit:
        claims = claims[:args.limit]

    log.info(f"Loaded {len(claims)} PENDING claims (VERIFIABLE_FACT + STATISTICAL)")
    if not claims:
        log.info("Nothing to process.")
        return

    conn = get_connection()

    stats       = {}
    web_searches = 0
    stage1_hits  = 0

    for i, row in enumerate(claims, 1):
        claim_id   = row["CLAIM_ID"]
        claim_text = row["CLAIM_TEXT"]
        claim_type = row["CLAIM_TYPE"]
        speaker    = row.get("SPEAKER") or "Unknown"

        if i % 25 == 0 or i == 1:
            log.info(f"[{i}/{len(claims)}] web_searches={web_searches} | stats={stats}")

        # Stage 1: LLM pre-filter
        pf = _llm_prefilter(claim_text, claim_type, speaker)

        if pf["status"] in ("VERIFIED", "FALSE") and pf["confidence"] == "HIGH":
            # Confident LLM verdict — skip web search
            status  = pf["status"]
            source  = "LLM_ONLY"
            summary = pf["explanation"]
            urls    = []
            stage1_hits += 1

        elif args.stage1_only or web_searches >= args.web_budget:
            # Budget exhausted or stage1-only mode
            status  = "UNVERIFIED" if pf["status"] == "UNCERTAIN" else pf["status"]
            source  = "LLM_ONLY"
            summary = pf["explanation"]
            urls    = []

        else:
            # Stage 2: Brave Search
            search_results = _brave_search(claim_text)
            web_searches  += 1

            if search_results:
                # Stage 3: Verdict synthesis
                verdict = _synthesize_verdict(claim_text, search_results)
                status  = verdict["status"]
                source  = "LLM_PLUS_WEB"
                summary = verdict["evidence_summary"]
                urls    = verdict["evidence_urls"]
            else:
                status  = "UNVERIFIED"
                source  = "LLM_ONLY"
                summary = pf["explanation"]
                urls    = []

        stats[status] = stats.get(status, 0) + 1

        if args.dry_run:
            log.info(f"  DRY-RUN [{claim_id[:8]}] {status:12s} [{source}] {claim_text[:80]}")
        else:
            _update_claim(conn, claim_id, status, source, summary, urls)

        time.sleep(0.05)  # small delay to avoid rate limits

    # Final report
    log.info("\n" + "=" * 60)
    log.info("Fact-Checker Complete")
    log.info(f"  Total processed : {len(claims)}")
    log.info(f"  Stage 1 hits    : {stage1_hits}  (confident LLM, no web search)")
    log.info(f"  Web searches    : {web_searches}")
    log.info("  Results:")
    for status, count in sorted(stats.items(), key=lambda x: -x[1]):
        pct = round(count * 100 / len(claims), 1)
        log.info(f"    {status:12s}: {count:5d} ({pct}%)")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
