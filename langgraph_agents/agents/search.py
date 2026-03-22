"""
Search Agent — queries Snowflake Cortex Search (PODCASTIQ_SEARCH service).

Returns the top-K most relevant chunks with YouTube timestamp links.
"""

import json
import logging
from langgraph_agents.state import PodcastIQState, SearchResult
from langgraph_agents.snowflake_client import execute_scalar

log = logging.getLogger(__name__)

SEARCH_SERVICE = "PODCASTIQ.SEMANTIC.PODCASTIQ_SEARCH"
RETURN_COLUMNS = ["CHUNK_TEXT", "EPISODE_TITLE", "CHANNEL_NAME", "YOUTUBE_URL", "PUBLISH_DATE", "CHUNK_ID"]
DEFAULT_LIMIT  = 8


def search_agent(state: PodcastIQState) -> dict:
    """Query Cortex Search and populate search_results in state."""
    query = state["user_query"]
    log.info(f"[Search] Querying Cortex Search: '{query}'")

    payload = json.dumps({
        "query":   query,
        "columns": RETURN_COLUMNS,
        "limit":   DEFAULT_LIMIT,
    })

    raw = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(%s, %s) AS response",
        (SEARCH_SERVICE, payload),
    )

    if not raw:
        log.warning("[Search] Empty response from Cortex Search")
        return {
            "search_results": [],
            "messages": ["Search: no results found"],
        }

    data = json.loads(raw)
    raw_results = data.get("results", [])

    results: list[SearchResult] = [
        SearchResult(
            chunk_id      = r.get("CHUNK_ID", ""),
            episode_title = r.get("EPISODE_TITLE", ""),
            channel_name  = r.get("CHANNEL_NAME", ""),
            chunk_text    = r.get("CHUNK_TEXT", ""),
            youtube_url   = r.get("YOUTUBE_URL", ""),
            publish_date  = str(r.get("PUBLISH_DATE", "")),
        )
        for r in raw_results
    ]

    log.info(f"[Search] Found {len(results)} results")

    return {
        "search_results": results,
        "messages": [f"Search: found {len(results)} relevant chunks"],
    }
