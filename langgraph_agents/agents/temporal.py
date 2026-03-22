"""
Temporal Analysis Agent — answers questions about how claims evolve over time.

Queries SEM_CLAIM_EVOLUTION + SEM_CLAIMS from Snowflake to answer:
  - "How has opinion on AGI changed over time?"
  - "Who changed their mind about crypto?"
  - "Show me contradicted predictions from 2022"
  - "What claims have been revised on AI?"
"""

import logging
from langgraph_agents.state import PodcastIQState
from langgraph_agents.snowflake_client import execute, execute_scalar

log = logging.getLogger(__name__)

# ── SQL templates ─────────────────────────────────────────────────────────────

_TOPIC_EVOLUTION_SQL = """
SELECT
    ce.DRIFT_TYPE,
    ce.ORIGINAL_DATE,
    ce.EVOLVED_DATE,
    ce.TIME_DELTA_DAYS,
    ce.ORIGINAL_SPEAKER,
    ce.EVOLVED_SPEAKER,
    ce.SAME_SPEAKER,
    ce.CHANNEL_ORIGINAL,
    ce.CHANNEL_EVOLVED,
    ce.ANALYSIS,
    ce.TOPIC,
    c1.CLAIM_TEXT  AS original_text,
    c1.YOUTUBE_URL AS original_url,
    c2.CLAIM_TEXT  AS evolved_text,
    c2.YOUTUBE_URL AS evolved_url
FROM SEMANTIC.SEM_CLAIM_EVOLUTION ce
JOIN SEMANTIC.SEM_CLAIMS c1 ON ce.ORIGINAL_CLAIM_ID = c1.CLAIM_ID
JOIN SEMANTIC.SEM_CLAIMS c2 ON ce.EVOLVED_CLAIM_ID  = c2.CLAIM_ID
WHERE LOWER(ce.TOPIC) LIKE %s
ORDER BY ce.TIME_DELTA_DAYS DESC
LIMIT 10
"""

_SPEAKER_EVOLUTION_SQL = """
SELECT
    ce.DRIFT_TYPE,
    ce.ORIGINAL_DATE,
    ce.EVOLVED_DATE,
    ce.TIME_DELTA_DAYS,
    ce.ORIGINAL_SPEAKER,
    ce.EVOLVED_SPEAKER,
    ce.CHANNEL_ORIGINAL,
    ce.CHANNEL_EVOLVED,
    ce.ANALYSIS,
    ce.TOPIC,
    c1.CLAIM_TEXT  AS original_text,
    c1.YOUTUBE_URL AS original_url,
    c2.CLAIM_TEXT  AS evolved_text,
    c2.YOUTUBE_URL AS evolved_url
FROM SEMANTIC.SEM_CLAIM_EVOLUTION ce
JOIN SEMANTIC.SEM_CLAIMS c1 ON ce.ORIGINAL_CLAIM_ID = c1.CLAIM_ID
JOIN SEMANTIC.SEM_CLAIMS c2 ON ce.EVOLVED_CLAIM_ID  = c2.CLAIM_ID
WHERE (LOWER(ce.ORIGINAL_SPEAKER) LIKE %s OR LOWER(ce.EVOLVED_SPEAKER) LIKE %s)
ORDER BY ce.TIME_DELTA_DAYS DESC
LIMIT 10
"""

_DRIFT_TYPE_SQL = """
SELECT
    ce.DRIFT_TYPE,
    ce.ORIGINAL_DATE,
    ce.EVOLVED_DATE,
    ce.TIME_DELTA_DAYS,
    ce.ORIGINAL_SPEAKER,
    ce.EVOLVED_SPEAKER,
    ce.CHANNEL_ORIGINAL,
    ce.CHANNEL_EVOLVED,
    ce.ANALYSIS,
    ce.TOPIC,
    c1.CLAIM_TEXT  AS original_text,
    c1.YOUTUBE_URL AS original_url,
    c2.CLAIM_TEXT  AS evolved_text,
    c2.YOUTUBE_URL AS evolved_url
FROM SEMANTIC.SEM_CLAIM_EVOLUTION ce
JOIN SEMANTIC.SEM_CLAIMS c1 ON ce.ORIGINAL_CLAIM_ID = c1.CLAIM_ID
JOIN SEMANTIC.SEM_CLAIMS c2 ON ce.EVOLVED_CLAIM_ID  = c2.CLAIM_ID
WHERE ce.DRIFT_TYPE = %s
ORDER BY ce.TIME_DELTA_DAYS DESC
LIMIT 10
"""

_RECENT_SQL = """
SELECT
    ce.DRIFT_TYPE,
    ce.ORIGINAL_DATE,
    ce.EVOLVED_DATE,
    ce.TIME_DELTA_DAYS,
    ce.ORIGINAL_SPEAKER,
    ce.EVOLVED_SPEAKER,
    ce.CHANNEL_ORIGINAL,
    ce.CHANNEL_EVOLVED,
    ce.ANALYSIS,
    ce.TOPIC,
    c1.CLAIM_TEXT  AS original_text,
    c1.YOUTUBE_URL AS original_url,
    c2.CLAIM_TEXT  AS evolved_text,
    c2.YOUTUBE_URL AS evolved_url
FROM SEMANTIC.SEM_CLAIM_EVOLUTION ce
JOIN SEMANTIC.SEM_CLAIMS c1 ON ce.ORIGINAL_CLAIM_ID = c1.CLAIM_ID
JOIN SEMANTIC.SEM_CLAIMS c2 ON ce.EVOLVED_CLAIM_ID  = c2.CLAIM_ID
ORDER BY ce.TIME_DELTA_DAYS DESC
LIMIT 10
"""

# ── Keyword extractor ──────────────────────────────────────────────────────────

_EXTRACT_PROMPT = """Extract the key search terms from this temporal query about podcast claims.

Query: "{query}"

Return a JSON object with these fields:
- topic: keyword to search in topic names (or null if not topic-specific)
- speaker: person's name to search for (or null if not person-specific)
- drift_type: one of REVISED/ESCALATED/SOFTENED/CONTRADICTED/CONFIRMED (or null)

Examples:
- "How has AGI opinion changed?" → {{"topic": "AGI", "speaker": null, "drift_type": null}}
- "Who changed their mind about crypto?" → {{"topic": "crypto", "speaker": null, "drift_type": "REVISED"}}
- "Show Sam Altman's revised claims" → {{"topic": null, "speaker": "Sam Altman", "drift_type": "REVISED"}}
- "Contradicted predictions about AI" → {{"topic": "AI", "speaker": null, "drift_type": "CONTRADICTED"}}

Respond with ONLY valid JSON — no markdown, no explanation."""


def _extract_intent(query: str) -> dict:
    """Use LLM to extract topic/speaker/drift_type from natural language query."""
    raw = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-8b', %s)",
        (_EXTRACT_PROMPT.format(query=query),),
    )
    if not raw:
        return {"topic": None, "speaker": None, "drift_type": None}

    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()

    try:
        return {"topic": None, "speaker": None, "drift_type": None, **__import__("json").loads(raw)}
    except Exception:
        return {"topic": None, "speaker": None, "drift_type": None}


def _fetch_evolutions(intent: dict) -> list[dict]:
    """Query SEM_CLAIM_EVOLUTION based on extracted intent."""
    topic    = intent.get("topic")
    speaker  = intent.get("speaker")
    drift    = intent.get("drift_type", "").upper() if intent.get("drift_type") else None

    # Priority: speaker → topic → drift_type → recent
    if speaker:
        kw = f"%{speaker.lower()}%"
        return execute(_SPEAKER_EVOLUTION_SQL, (kw, kw))
    elif topic:
        kw = f"%{topic.lower()}%"
        return execute(_TOPIC_EVOLUTION_SQL, (kw,))
    elif drift and drift in {"REVISED", "ESCALATED", "SOFTENED", "CONTRADICTED", "CONFIRMED"}:
        return execute(_DRIFT_TYPE_SQL, (drift,))
    else:
        return execute(_RECENT_SQL)


def _format_timeline(rows: list[dict], query: str) -> str:
    """Synthesize evolution rows into a narrative timeline answer."""
    if not rows:
        return (
            "No claim evolution data found for this query. "
            "The temporal analysis table may still be populating — "
            "run `python scripts/temporal_analyzer.py` to generate evolution pairs."
        )

    rows_text = "\n\n".join(
        f"[{r.get('DRIFT_TYPE')}] Topic: {r.get('TOPIC')} | "
        f"{r.get('TIME_DELTA_DAYS')} days apart\n"
        f"  ORIGINAL ({r.get('ORIGINAL_DATE')}) by {r.get('ORIGINAL_SPEAKER')} "
        f"on {r.get('CHANNEL_ORIGINAL')}:\n  \"{str(r.get('original_text', ''))[:200]}\"\n"
        f"  LATER ({r.get('EVOLVED_DATE')}) by {r.get('EVOLVED_SPEAKER')} "
        f"on {r.get('CHANNEL_EVOLVED')}:\n  \"{str(r.get('evolved_text', ''))[:200]}\"\n"
        f"  Analysis: {r.get('ANALYSIS')}"
        for r in rows[:8]
    )

    prompt = f"""You are a podcast intelligence assistant specializing in how ideas evolve over time.

The user asked: "{query}"

Here are relevant claim evolution pairs from the knowledge graph:
{rows_text}

Write a clear, insightful answer (4-6 sentences) explaining how the discourse has evolved.
- Highlight the most significant shifts (CONTRADICTED, REVISED)
- Mention specific speakers and timeframes
- Note if the same person changed their view vs different people disagreeing
- Do NOT mention "database", "SQL", or "knowledge graph" — answer naturally"""

    answer = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', %s)",
        (prompt,),
    )
    return (answer or "").strip()


def temporal_agent(state: PodcastIQState) -> dict:
    """
    Temporal Analysis Agent — answers questions about claim evolution over time.

    Args:
        state: Current graph state with user_query

    Returns:
        Updated state with summary and graph_results (evolution rows)
    """
    query = state["user_query"]
    log.info(f"[Temporal] Processing: '{query}'")

    # Step 1: Extract intent
    intent = _extract_intent(query)
    log.info(f"[Temporal] Intent: {intent}")

    # Step 2: Query SEM_CLAIM_EVOLUTION
    rows = _fetch_evolutions(intent)
    log.info(f"[Temporal] Found {len(rows)} evolution pairs")

    # Step 3: Format into narrative
    summary = _format_timeline(rows, query)

    return {
        "graph_results": rows,
        "summary": summary,
        "messages": [f"Temporal: {len(rows)} evolution pairs → answer generated"],
    }
