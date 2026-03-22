"""
Summarization Agent — synthesizes search results into a coherent answer.

Uses Snowflake Cortex LLM to produce a 2-4 paragraph response with
YouTube timestamp citations embedded inline.
"""

import logging
from langgraph_agents.state import PodcastIQState
from langgraph_agents.snowflake_client import execute_scalar

log = logging.getLogger(__name__)

_PROMPT = """You are a podcast intelligence assistant. Answer the user's question using ONLY the transcript excerpts below.

Rules:
- Be concise and direct (2-4 paragraphs max)
- Cite sources inline as [Episode Title - Channel] after each insight
- Include the YouTube link for the most relevant clip at the end of each paragraph
- If excerpts don't contain enough info, say so honestly

User question: {query}

Transcript excerpts:
{context}

Answer:"""


def _build_context(results: list) -> str:
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(
            f"[{i}] \"{r['episode_title']}\" on {r['channel_name']} ({r['publish_date'][:10] if r['publish_date'] else 'n/a'})\n"
            f"URL: {r['youtube_url']}\n"
            f"Excerpt: {r['chunk_text'][:500]}"
        )
    return "\n\n".join(parts)


def summarization_agent(state: PodcastIQState) -> dict:
    """Synthesize search results into a final answer."""
    results = state.get("search_results", [])
    query   = state["user_query"]

    if not results:
        return {
            "summary": "No relevant podcast clips found for your query. Try rephrasing or broadening your search.",
            "messages": ["Summarization: no results to summarize"],
        }

    log.info(f"[Summarization] Synthesizing {len(results)} results")

    context = _build_context(results)
    prompt  = _PROMPT.format(query=query, context=context)

    summary = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', %s)",
        (prompt,),
    )

    summary = (summary or "").strip()
    log.info(f"[Summarization] Generated {len(summary)} char summary")

    return {
        "summary": summary,
        "messages": [f"Summarization: generated answer ({len(summary)} chars)"],
    }
