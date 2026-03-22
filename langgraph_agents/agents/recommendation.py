"""
Recommendation Agent — suggests related episodes based on topics, guests, or channels.

Handles queries like:
  - "What else should I watch after the Sam Altman episode?"
  - "Recommend podcasts similar to Huberman Lab"
  - "Find episodes like the one about AI safety"
  - "What should I listen to about startups?"
"""

import json
import logging
from langgraph_agents.state import PodcastIQState
from langgraph_agents.snowflake_client import execute, execute_scalar

log = logging.getLogger(__name__)

# ── SQL templates ──────────────────────────────────────────────────────────────

_TOPIC_EPISODES_SQL = """
SELECT DISTINCT
    e.EPISODE_TITLE,
    e.CHANNEL_NAME,
    e.YOUTUBE_URL,
    e.PUBLISH_DATE,
    COUNT(c.CHUNK_ID) AS chunk_count
FROM CURATED.CUR_CHUNKS e
JOIN SEMANTIC.SEM_CLAIMS c ON e.CHUNK_ID = c.CHUNK_ID
WHERE LOWER(c.TOPIC) LIKE %s
  AND e.EPISODE_TITLE IS NOT NULL
GROUP BY e.EPISODE_TITLE, e.CHANNEL_NAME, e.YOUTUBE_URL, e.PUBLISH_DATE
ORDER BY chunk_count DESC
LIMIT 10
"""

_GUEST_EPISODES_SQL = """
SELECT DISTINCT
    e.EPISODE_TITLE,
    e.CHANNEL_NAME,
    e.YOUTUBE_URL,
    e.PUBLISH_DATE,
    COUNT(c.CHUNK_ID) AS chunk_count
FROM CURATED.CUR_CHUNKS e
JOIN SEMANTIC.SEM_CLAIMS c ON e.CHUNK_ID = c.CHUNK_ID
WHERE LOWER(c.SPEAKER) LIKE %s
  AND e.EPISODE_TITLE IS NOT NULL
GROUP BY e.EPISODE_TITLE, e.CHANNEL_NAME, e.YOUTUBE_URL, e.PUBLISH_DATE
ORDER BY chunk_count DESC
LIMIT 10
"""

_CHANNEL_EPISODES_SQL = """
SELECT DISTINCT
    EPISODE_TITLE,
    CHANNEL_NAME,
    YOUTUBE_URL,
    PUBLISH_DATE,
    COUNT(*) AS chunk_count
FROM CURATED.CUR_CHUNKS
WHERE LOWER(CHANNEL_NAME) LIKE %s
  AND EPISODE_TITLE IS NOT NULL
GROUP BY EPISODE_TITLE, CHANNEL_NAME, YOUTUBE_URL, PUBLISH_DATE
ORDER BY PUBLISH_DATE DESC
LIMIT 10
"""

# ── Intent extractor ──────────────────────────────────────────────────────────

_EXTRACT_PROMPT = """Extract recommendation intent from this podcast query.

Query: "{query}"

Return a JSON object with:
- topic: topic or subject to find episodes about (string, or null)
- guest: specific person/guest to find episodes featuring (string, or null)
- channel: specific podcast channel to recommend from (string, or null)

Examples:
- "What should I watch about AI?" → {{"topic": "AI", "guest": null, "channel": null}}
- "More episodes with Sam Altman" → {{"topic": null, "guest": "Sam Altman", "channel": null}}
- "Best Huberman Lab episodes" → {{"topic": null, "guest": null, "channel": "Huberman Lab"}}
- "Recommend startup episodes like MFM" → {{"topic": "startups", "guest": null, "channel": "My First Million"}}

Respond with ONLY valid JSON — no markdown, no explanation."""


def _extract_intent(query: str) -> dict:
    raw = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-8b', %s)",
        (_EXTRACT_PROMPT.format(query=query),),
    )
    if not raw:
        return {"topic": None, "guest": None, "channel": None}

    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()

    try:
        result = json.loads(raw)
        return {
            "topic":   result.get("topic"),
            "guest":   result.get("guest"),
            "channel": result.get("channel"),
        }
    except Exception:
        return {"topic": None, "guest": None, "channel": None}


def _fetch_episodes(intent: dict) -> list[dict]:
    """Fetch recommended episodes based on intent."""
    guest   = intent.get("guest")
    topic   = intent.get("topic")
    channel = intent.get("channel")

    # Priority: guest → channel → topic
    if guest:
        kw = f"%{guest.lower()}%"
        return execute(_GUEST_EPISODES_SQL, (kw,))
    elif channel:
        kw = f"%{channel.lower()}%"
        return execute(_CHANNEL_EPISODES_SQL, (kw,))
    elif topic:
        kw = f"%{topic.lower()}%"
        return execute(_TOPIC_EPISODES_SQL, (kw,))
    else:
        # Fallback: recent episodes
        return execute("""
            SELECT DISTINCT EPISODE_TITLE, CHANNEL_NAME, YOUTUBE_URL, PUBLISH_DATE,
                   COUNT(*) AS chunk_count
            FROM CURATED.CUR_CHUNKS
            WHERE EPISODE_TITLE IS NOT NULL
            GROUP BY EPISODE_TITLE, CHANNEL_NAME, YOUTUBE_URL, PUBLISH_DATE
            ORDER BY PUBLISH_DATE DESC
            LIMIT 10
        """)


def _format_answer(rows: list[dict], intent: dict, query: str) -> str:
    """Use LLM to format episode list into a recommendation narrative."""
    if not rows:
        return "No matching episodes found. Try a broader topic or different speaker name."

    ep_list = "\n".join(
        f"{i+1}. \"{r.get('EPISODE_TITLE', 'Unknown')}\" — {r.get('CHANNEL_NAME', '')} "
        f"({str(r.get('PUBLISH_DATE', ''))[:10]})\n   {r.get('YOUTUBE_URL', '')}"
        for i, r in enumerate(rows[:8])
    )

    guest   = intent.get("guest")
    topic   = intent.get("topic")
    channel = intent.get("channel")
    context = guest or topic or channel or "your interests"

    prompt = f"""You are a podcast recommendation assistant. The user asked: "{query}"

Here are the most relevant episodes about {context}:

{ep_list}

Write a brief, friendly recommendation (3-4 sentences):
- Highlight 2-3 standout episodes and why they're relevant
- Mention the variety of channels if applicable
- End with the full list of YouTube links so they can click through
Do NOT mention "database" or "SQL"."""

    answer = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', %s)",
        (prompt,),
    )
    return (answer or "").strip()


def recommendation_agent(state: PodcastIQState) -> dict:
    """
    Recommendation Agent — suggests relevant episodes based on topic, guest, or channel.

    Args:
        state: Current graph state with user_query

    Returns:
        Updated state with summary (recommendations) and graph_results (episode list)
    """
    query = state["user_query"]
    log.info(f"[Recommendation] Processing: '{query}'")

    intent = _extract_intent(query)
    log.info(f"[Recommendation] Intent: {intent}")

    rows = _fetch_episodes(intent)
    log.info(f"[Recommendation] Found {len(rows)} episodes")

    summary = _format_answer(rows, intent, query)

    return {
        "graph_results": rows,
        "summary": summary,
        "messages": [f"Recommendation: {len(rows)} episodes found → answer generated"],
    }
