"""
Router Agent — classifies user query intent using Snowflake Cortex LLM.

Query types:
  SEARCH    — find relevant clips/segments about a topic
  SUMMARIZE — synthesize what experts across podcasts say about a topic
  COMPARE   — compare views of different people or channels on a topic
  RECOMMEND — suggest episodes similar to one the user liked
  TEMPORAL  — how claims/opinions have changed over time
  FACTCHECK — verify whether a specific claim is true or false
"""

import logging
from langgraph_agents.state import PodcastIQState
from langgraph_agents.snowflake_client import execute_scalar

log = logging.getLogger(__name__)

_VALID_TYPES = {"SEARCH", "SUMMARIZE", "COMPARE", "RECOMMEND", "GRAPH", "TEMPORAL", "INSIGHT", "FACTCHECK"}

_PROMPT = """You are a query classifier for a podcast intelligence system.

Classify the user's query into exactly ONE of these types:

- SUMMARIZE  : User wants to LEARN about a topic — asking what experts say, best practices,
               strategies, explanations, or insights. These are knowledge/information questions.
               e.g. "What are the best strategies for building a startup?",
               "What do experts say about longevity?", "How does intermittent fasting work?",
               "What is the consensus on AI safety?", "Explain machine learning"

- SEARCH     : User wants specific clips, quotes, or moments about a topic.
               e.g. "Find clips about AGI", "What did Sam Altman say about GPT-5?"

- RECOMMEND  : User explicitly wants episode/show SUGGESTIONS to watch or listen to.
               Must contain words like: recommend, suggest, watch, listen, episodes, show me, what should I.
               e.g. "Recommend episodes about startups", "What should I watch about AI?",
               "Show me episodes with Sam Altman", "Suggest something from Huberman Lab"

- COMPARE    : Compare viewpoints of two specific people or channels on a topic.
               e.g. "Compare Sam Altman vs Elon Musk on AI", "How do X and Y differ on Z?"

- INSIGHT    : Meta-analysis about channels, speakers, or statistics across the corpus.
               e.g. "Which channel has the most contradicted claims?", "Most debated topics?",
               "Give me a credibility report on Huberman Lab", "Top speakers by claim volume"

- GRAPH      : Questions about relationships, appearances, networks between people/topics.
               e.g. "Who has Sam Altman appeared with?", "Show X's network",
               "Which guests appeared on multiple shows?", "Who discussed AI safety?"

- TEMPORAL   : How claims or opinions have evolved or changed over time.
               e.g. "How has opinion on AGI changed?", "Who changed their mind about crypto?",
               "Show contradicted predictions", "What claims have been revised?"

- FACTCHECK  : Verify whether a specific claim is true, false, or outdated.
               e.g. "Fact check: GPT-5 released in 2024", "Is it true that X?",
               "Did Sam Altman say AGI arrives by 2025?", "Verify this statistic"

IMPORTANT: "What are strategies/tips/advice about X?" → SUMMARIZE (not RECOMMEND)
           "Recommend/suggest/show me episodes about X" → RECOMMEND

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
