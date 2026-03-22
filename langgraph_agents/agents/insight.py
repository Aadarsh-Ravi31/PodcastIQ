"""
Insight Agent — answers meta-analysis questions about the podcast knowledge graph.

Handles queries like:
  - "Which channel has the most contradicted claims?"
  - "What are the most debated topics?"
  - "Give me a credibility report for All-In Podcast"
  - "Which speakers make the most predictions?"
  - "What topics does Joe Rogan cover most?"
"""

import json
import logging
from langgraph_agents.state import PodcastIQState
from langgraph_agents.snowflake_client import execute, execute_scalar

log = logging.getLogger(__name__)

# ── SQL templates ──────────────────────────────────────────────────────────────

_CHANNEL_DRIFT_STATS_SQL = """
SELECT
    ce.CHANNEL_ORIGINAL AS channel,
    COUNT(*) AS total_evolutions,
    SUM(CASE WHEN ce.DRIFT_TYPE = 'CONTRADICTED' THEN 1 ELSE 0 END) AS contradicted,
    SUM(CASE WHEN ce.DRIFT_TYPE = 'REVISED'      THEN 1 ELSE 0 END) AS revised,
    SUM(CASE WHEN ce.DRIFT_TYPE = 'CONFIRMED'    THEN 1 ELSE 0 END) AS confirmed,
    SUM(CASE WHEN ce.DRIFT_TYPE = 'ESCALATED'    THEN 1 ELSE 0 END) AS escalated,
    SUM(CASE WHEN ce.DRIFT_TYPE = 'SOFTENED'     THEN 1 ELSE 0 END) AS softened
FROM SEMANTIC.SEM_CLAIM_EVOLUTION ce
GROUP BY ce.CHANNEL_ORIGINAL
ORDER BY contradicted DESC
LIMIT 10
"""

_TOP_TOPICS_SQL = """
SELECT
    TOPIC,
    COUNT(*) AS claim_count,
    COUNT(DISTINCT SPEAKER) AS speaker_count,
    COUNT(DISTINCT CHANNEL_NAME) AS channel_count
FROM SEMANTIC.SEM_CLAIMS
WHERE TOPIC IS NOT NULL AND TRIM(TOPIC) != ''
GROUP BY TOPIC
ORDER BY claim_count DESC
LIMIT 15
"""

_CHANNEL_REPORT_SQL = """
SELECT
    CLAIM_TYPE,
    COUNT(*) AS cnt,
    COUNT(DISTINCT SPEAKER) AS speakers,
    COUNT(DISTINCT TOPIC) AS topics
FROM SEMANTIC.SEM_CLAIMS
WHERE LOWER(CHANNEL_NAME) LIKE %s
GROUP BY CLAIM_TYPE
ORDER BY cnt DESC
"""

_SPEAKER_CLAIMS_SQL = """
SELECT
    SPEAKER,
    COUNT(*) AS claim_count,
    COUNT(DISTINCT TOPIC) AS topic_count,
    SUM(CASE WHEN CLAIM_TYPE = 'PREDICTION' THEN 1 ELSE 0 END) AS predictions,
    SUM(CASE WHEN CLAIM_TYPE = 'STATISTICAL' THEN 1 ELSE 0 END) AS stats
FROM SEMANTIC.SEM_CLAIMS
WHERE SPEAKER IS NOT NULL
  AND UPPER(TRIM(SPEAKER)) != 'UNKNOWN'
GROUP BY SPEAKER
ORDER BY claim_count DESC
LIMIT 15
"""

_TOPIC_DEBATE_SQL = """
SELECT
    ce.TOPIC,
    COUNT(*) AS evolution_count,
    SUM(CASE WHEN ce.DRIFT_TYPE = 'CONTRADICTED' THEN 1 ELSE 0 END) AS contradictions,
    COUNT(DISTINCT ce.ORIGINAL_SPEAKER) + COUNT(DISTINCT ce.EVOLVED_SPEAKER) AS speakers_involved
FROM SEMANTIC.SEM_CLAIM_EVOLUTION ce
WHERE ce.TOPIC IS NOT NULL
GROUP BY ce.TOPIC
ORDER BY contradictions DESC
LIMIT 10
"""

# ── Intent extractor ──────────────────────────────────────────────────────────

_EXTRACT_PROMPT = """Classify this podcast analytics query.

Query: "{query}"

Return a JSON object with:
- insight_type: one of "channel_report", "top_topics", "most_debated", "top_speakers", "channel_drift"
- channel: specific channel name if mentioned (string or null)
- speaker: specific speaker if mentioned (string or null)

Examples:
- "Which channel has the most contradicted claims?" → {{"insight_type": "channel_drift", "channel": null, "speaker": null}}
- "Give me a report on Huberman Lab" → {{"insight_type": "channel_report", "channel": "Huberman Lab", "speaker": null}}
- "What are the most debated topics?" → {{"insight_type": "most_debated", "channel": null, "speaker": null}}
- "Which speakers make the most predictions?" → {{"insight_type": "top_speakers", "channel": null, "speaker": null}}
- "What topics does Joe Rogan cover?" → {{"insight_type": "top_topics", "channel": null, "speaker": "Joe Rogan"}}

Respond with ONLY valid JSON — no markdown, no explanation."""


def _extract_intent(query: str) -> dict:
    raw = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-8b', %s)",
        (_EXTRACT_PROMPT.format(query=query),),
    )
    if not raw:
        return {"insight_type": "top_topics", "channel": None, "speaker": None}

    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()

    try:
        result = json.loads(raw)
        return {
            "insight_type": result.get("insight_type", "top_topics"),
            "channel":      result.get("channel"),
            "speaker":      result.get("speaker"),
        }
    except Exception:
        return {"insight_type": "top_topics", "channel": None, "speaker": None}


def _fetch_data(intent: dict) -> tuple[list[dict], str]:
    """Fetch data based on insight type. Returns (rows, data_description)."""
    itype   = intent.get("insight_type", "top_topics")
    channel = intent.get("channel")
    speaker = intent.get("speaker")

    if itype == "channel_drift":
        rows = execute(_CHANNEL_DRIFT_STATS_SQL)
        return rows, "channel contradiction/drift statistics"

    elif itype == "channel_report" and channel:
        kw = f"%{channel.lower()}%"
        rows = execute(_CHANNEL_REPORT_SQL, (kw,))
        return rows, f"claim breakdown for {channel}"

    elif itype == "most_debated":
        rows = execute(_TOPIC_DEBATE_SQL)
        return rows, "most debated topics by contradiction count"

    elif itype == "top_speakers":
        rows = execute(_SPEAKER_CLAIMS_SQL)
        return rows, "top speakers by claim count"

    else:  # top_topics or fallback
        rows = execute(_TOP_TOPICS_SQL)
        return rows, "most discussed topics"


def _synthesize(rows: list[dict], data_desc: str, query: str) -> str:
    """Use LLM to turn raw stats into an insight narrative."""
    if not rows:
        return "No data found for this query."

    rows_text = "\n".join(str(r) for r in rows[:12])

    prompt = f"""You are a podcast analytics expert. Answer this question: "{query}"

Here is the relevant data ({data_desc}):
{rows_text}

Write a clear, insightful answer (3-5 sentences):
- Lead with the most interesting finding
- Use specific numbers and names from the data
- Draw a meaningful conclusion about podcast discourse patterns
Do NOT mention "database", "SQL", or "rows". Answer naturally."""

    answer = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', %s)",
        (prompt,),
    )
    return (answer or "").strip()


def insight_agent(state: PodcastIQState) -> dict:
    """
    Insight Agent — meta-analysis queries about channels, speakers, and topics.

    Args:
        state: Current graph state with user_query

    Returns:
        Updated state with summary (insight) and graph_results (raw stats)
    """
    query = state["user_query"]
    log.info(f"[Insight] Processing: '{query}'")

    intent = _extract_intent(query)
    log.info(f"[Insight] Intent: {intent}")

    rows, data_desc = _fetch_data(intent)
    log.info(f"[Insight] Fetched {len(rows)} rows ({data_desc})")

    summary = _synthesize(rows, data_desc, query)

    return {
        "graph_results": rows,
        "summary": summary,
        "messages": [f"Insight: {len(rows)} rows ({data_desc}) → answer generated"],
    }
