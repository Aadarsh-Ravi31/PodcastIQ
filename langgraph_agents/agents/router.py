"""
Router Agent — classifies user query intent using Snowflake Cortex LLM.

Query types:
  SEARCH    — find relevant clips/segments about a topic
  SUMMARIZE — synthesize what experts across podcasts say about a topic
  COMPARE   — compare views of different people or channels on a topic
  RECOMMEND — suggest episodes similar to one the user liked
  TEMPORAL  — how claims/opinions have changed over time
"""

import logging
from langgraph_agents.state import PodcastIQState
from langgraph_agents.snowflake_client import execute_scalar

log = logging.getLogger(__name__)

_VALID_TYPES = {"SEARCH", "SUMMARIZE", "COMPARE", "RECOMMEND", "GRAPH", "TEMPORAL", "INSIGHT"}

_PROMPT = """You are a query classifier for a podcast intelligence system.

Classify the user's query into exactly ONE of these types:
- SEARCH     : Find specific clips or quotes about a topic
- SUMMARIZE  : Synthesize what experts say about a topic across many podcasts
- COMPARE    : Compare viewpoints of two specific people or channels on a topic
               e.g. "Compare Sam Altman vs Elon Musk on AI", "How do X and Y differ on Z?"
- RECOMMEND  : Suggest episodes or channels to explore based on topic, guest, or channel
               e.g. "What should I watch about AI?", "More episodes with Sam Altman"
- INSIGHT    : Meta-analysis questions about channels, speakers, or topic statistics
               e.g. "Which channel has the most contradicted claims?", "What are the most debated topics?",
               "Give me a report on Huberman Lab", "Which speakers make the most predictions?"
- GRAPH      : Questions about relationships, networks, or connections between people/topics
               e.g. "Who has discussed X?", "Show X's network", "Who appeared most?",
               "What topics does X cover?", "Which guests appeared on multiple shows?"
- TEMPORAL   : Questions about how claims or opinions have evolved over time
               e.g. "How has opinion on AGI changed?", "Who changed their mind about crypto?",
               "Show contradicted predictions", "What claims have been revised on AI?"

Respond with ONLY the type word — no explanation, no punctuation.

Query: {query}"""


def router_agent(state: PodcastIQState) -> dict:
    """Classify the user query and set query_type in state."""
    query = state["user_query"]
    log.info(f"[Router] Classifying query: '{query}'")

    prompt = _PROMPT.format(query=query)

    raw = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-8b', %s)",
        (prompt,),
    )

    query_type = (raw or "SEARCH").strip().upper()
    # Sanitise — fall back to SEARCH if LLM returns something unexpected
    if query_type not in _VALID_TYPES:
        query_type = "SEARCH"

    log.info(f"[Router] Query type: {query_type}")

    return {
        "query_type": query_type,
        "messages": [f"Router: classified as {query_type}"],
    }
