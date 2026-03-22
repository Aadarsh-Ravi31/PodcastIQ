"""
Comparison Agent — compares viewpoints of two speakers or channels on a topic.

Handles queries like:
  - "Compare Sam Altman vs Elon Musk on AI"
  - "How do Huberman Lab and Diary of a CEO differ on fitness?"
  - "What does Marc Andreessen think vs Peter Thiel about startups?"
"""

import json
import logging
from langgraph_agents.state import PodcastIQState
from langgraph_agents.snowflake_client import execute, execute_scalar

log = logging.getLogger(__name__)

# ── SQL templates ──────────────────────────────────────────────────────────────

_SPEAKER_CLAIMS_SQL = """
SELECT
    CLAIM_TEXT,
    CLAIM_TYPE,
    TOPIC,
    CLAIM_DATE,
    YOUTUBE_URL,
    CHANNEL_NAME
FROM SEMANTIC.SEM_CLAIMS
WHERE LOWER(SPEAKER) LIKE %s
  AND (%s IS NULL OR LOWER(TOPIC) LIKE %s)
  AND LEN(CLAIM_TEXT) > 30
ORDER BY CLAIM_DATE DESC
LIMIT 15
"""

_CHANNEL_CLAIMS_SQL = """
SELECT
    CLAIM_TEXT,
    CLAIM_TYPE,
    TOPIC,
    CLAIM_DATE,
    YOUTUBE_URL,
    SPEAKER
FROM SEMANTIC.SEM_CLAIMS
WHERE LOWER(CHANNEL_NAME) LIKE %s
  AND (%s IS NULL OR LOWER(TOPIC) LIKE %s)
  AND LEN(CLAIM_TEXT) > 30
ORDER BY CLAIM_DATE DESC
LIMIT 15
"""

# ── Intent extractor ──────────────────────────────────────────────────────────

_EXTRACT_PROMPT = """Extract comparison intent from this podcast query.

Query: "{query}"

Return a JSON object with:
- entity1: first person or channel name (string)
- entity2: second person or channel name (string)
- topic: the topic to compare on (string, or null if general)
- entity_type: "speaker" if comparing people, "channel" if comparing podcasts

Examples:
- "Compare Sam Altman vs Elon Musk on AI" → {{"entity1": "Sam Altman", "entity2": "Elon Musk", "topic": "AI", "entity_type": "speaker"}}
- "How do Huberman and Diary of CEO differ on fitness?" → {{"entity1": "Huberman", "entity2": "Diary of a CEO", "topic": "fitness", "entity_type": "channel"}}
- "Peter Thiel vs Marc Andreessen on startups" → {{"entity1": "Peter Thiel", "entity2": "Marc Andreessen", "topic": "startups", "entity_type": "speaker"}}

Respond with ONLY valid JSON — no markdown, no explanation."""


def _extract_intent(query: str) -> dict:
    raw = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-8b', %s)",
        (_EXTRACT_PROMPT.format(query=query),),
    )
    if not raw:
        return {"entity1": None, "entity2": None, "topic": None, "entity_type": "speaker"}

    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()

    try:
        result = json.loads(raw)
        return {
            "entity1": result.get("entity1"),
            "entity2": result.get("entity2"),
            "topic": result.get("topic"),
            "entity_type": result.get("entity_type", "speaker"),
        }
    except Exception:
        return {"entity1": None, "entity2": None, "topic": None, "entity_type": "speaker"}


def _fetch_claims(entity: str, topic: str | None, entity_type: str) -> list[dict]:
    """Fetch claims for one entity (speaker or channel)."""
    kw = f"%{entity.lower()}%"
    topic_kw = f"%{topic.lower()}%" if topic else None

    if entity_type == "channel":
        rows = execute(_CHANNEL_CLAIMS_SQL, (kw, topic_kw, topic_kw))
    else:
        rows = execute(_SPEAKER_CLAIMS_SQL, (kw, topic_kw, topic_kw))

    return rows


def _format_claims_block(entity: str, rows: list[dict], entity_type: str) -> str:
    """Format claims for one entity into a readable block."""
    if not rows:
        return f"{entity}: No claims found."

    lines = [f"=== {entity} ==="]
    for r in rows[:8]:
        speaker = r.get("SPEAKER", "") if entity_type == "channel" else ""
        speaker_str = f" [{speaker}]" if speaker else ""
        date = str(r.get("CLAIM_DATE", ""))[:10]
        lines.append(f"• [{date}]{speaker_str} {r.get('CLAIM_TEXT', '')[:200]}")
    return "\n".join(lines)


def _synthesize(entity1: str, entity2: str, topic: str | None,
                rows1: list[dict], rows2: list[dict], query: str) -> str:
    """Use LLM to synthesize a comparison narrative."""
    block1 = _format_claims_block(entity1, rows1, "speaker")
    block2 = _format_claims_block(entity2, rows2, "speaker")
    topic_str = f" on '{topic}'" if topic else ""

    prompt = f"""You are a podcast intelligence assistant. Compare the viewpoints of two parties{topic_str}.

User question: "{query}"

{block1}

{block2}

Write a clear comparison (4-6 sentences):
- What do they AGREE on?
- Where do they DISAGREE or take opposite positions?
- What is UNIQUE to each person's perspective?
- Who takes a stronger or more nuanced stance?

Do NOT mention "database", "SQL", or "claims table". Answer naturally as if you listened to both podcasts."""

    answer = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', %s)",
        (prompt,),
    )
    return (answer or "").strip()


def comparison_agent(state: PodcastIQState) -> dict:
    """
    Comparison Agent — contrasts two speakers or channels on a topic.

    Args:
        state: Current graph state with user_query

    Returns:
        Updated state with summary and graph_results (claims from both entities)
    """
    query = state["user_query"]
    log.info(f"[Comparison] Processing: '{query}'")

    # Step 1: Extract intent
    intent = _extract_intent(query)
    entity1 = intent.get("entity1") or ""
    entity2 = intent.get("entity2") or ""
    topic = intent.get("topic")
    entity_type = intent.get("entity_type", "speaker")
    log.info(f"[Comparison] Intent: {intent}")

    if not entity1 or not entity2:
        return {
            "summary": "Could not identify two entities to compare. Try: 'Compare Sam Altman vs Elon Musk on AI'",
            "graph_results": [],
            "messages": ["Comparison: could not extract entities"],
        }

    # Step 2: Fetch claims for both entities
    rows1 = _fetch_claims(entity1, topic, entity_type)
    rows2 = _fetch_claims(entity2, topic, entity_type)
    log.info(f"[Comparison] {entity1}: {len(rows1)} claims | {entity2}: {len(rows2)} claims")

    # Step 3: Synthesize comparison
    summary = _synthesize(entity1, entity2, topic, rows1, rows2, query)

    return {
        "graph_results": rows1 + rows2,
        "summary": summary,
        "messages": [f"Comparison: {entity1}({len(rows1)}) vs {entity2}({len(rows2)}) → answer generated"],
    }
