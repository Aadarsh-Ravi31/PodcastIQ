"""
Knowledge Graph Agent — translates natural language to Cypher and queries Neo4j.

Handles queries like:
  - "Who has discussed AI safety?"
  - "Show Sam Altman's network across podcasts"
  - "What topics does Lex Fridman cover most?"
  - "Which guests appeared on the most podcasts?"
"""

import os
import logging
from neo4j import GraphDatabase
from dotenv import load_dotenv

from langgraph_agents.state import PodcastIQState
from langgraph_agents.snowflake_client import execute_scalar

load_dotenv()
log = logging.getLogger(__name__)

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "podcastiq123")

# ── Graph schema description for the LLM ──────────────────────────────────────
_SCHEMA = """
Neo4j graph schema:

Node labels and key properties:
  - Channel  : channel_name, genre, youtube_url
  - Episode  : video_id, title, channel_name, publish_date, youtube_url, genre
  - Person   : name, primary_role (HOST|GUEST), primary_channel
  - Topic    : name
  - Claim    : claim_id, text, claim_type (VERIFIABLE_FACT|PREDICTION|OPINION|STATISTICAL),
               sentiment (POSITIVE|NEGATIVE|NEUTRAL), speaker, attribution_confidence,
               claim_date, channel_name, youtube_url, verification_status

Relationships:
  - (Episode)-[:BELONGS_TO]->(Channel)
  - (Person)-[:APPEARED_ON]->(Episode)
  - (Person)-[:MADE_CLAIM]->(Claim)
  - (Person)-[:LIKELY_MADE_CLAIM]->(Claim)
  - (Claim)-[:DISCUSSED_IN]->(Episode)
  - (Claim)-[:ABOUT]->(Topic)
  - (Claim)-[:SOURCED_FROM]->(Episode)
"""

_CYPHER_PROMPT = """You are an expert Neo4j Cypher query generator for a podcast knowledge graph.

{schema}

STRICT RULES — violating these will cause a syntax error:
1. ALWAYS use single quotes for string values: 'AI safety' NOT "AI safety"
2. Relationships are ONE direction only: (a)-[:REL]->(b) NOT (a)-[:REL]<-[:REL]-(b)
3. Always end with LIMIT 25
4. Return human-readable column aliases (AS person, AS topic, AS count)
5. Use toLower() for case-insensitive partial matching: toLower(n.name) CONTAINS toLower('value')
6. Return ONLY the raw Cypher — no markdown, no explanation, no backticks

CRITICAL DESIGN NOTE:
- Claims have denormalized properties: c.speaker, c.channel_name, c.topic, c.text, c.claim_date
- For "who discussed X" queries: scan Claim nodes directly using c.speaker — do NOT traverse Person relationships
- Person-[:MADE_CLAIM] edges are sparse (only HIGH confidence). Always prefer c.speaker for speaker lookups.
- For appearance queries (who appeared on most shows): use Person-[:APPEARED_ON]->Episode

EXAMPLES of correct queries:

Who discussed AI safety?
MATCH (c:Claim)
WHERE toLower(c.topic) CONTAINS 'ai' OR toLower(c.text) CONTAINS 'ai safety'
RETURN c.speaker AS person, c.channel_name AS channel, COUNT(c) AS claims
ORDER BY claims DESC LIMIT 25

What topics does Lex Fridman cover most?
MATCH (c:Claim)
WHERE toLower(c.channel_name) CONTAINS 'lex fridman'
RETURN c.topic AS topic, COUNT(c) AS mentions
ORDER BY mentions DESC LIMIT 25

Who appeared on the most episodes?
MATCH (p:Person)-[:APPEARED_ON]->(e:Episode)
RETURN p.name AS person, COUNT(e) AS episodes
ORDER BY episodes DESC LIMIT 25

Show Sam Altman's claims:
MATCH (c:Claim)
WHERE toLower(c.speaker) CONTAINS 'sam altman'
RETURN c.topic AS topic, c.text AS claim, c.claim_date AS date, c.channel_name AS channel
ORDER BY date DESC LIMIT 25

Which guests appeared on multiple channels?
MATCH (p:Person)-[:APPEARED_ON]->(e:Episode)-[:BELONGS_TO]->(ch:Channel)
WITH p, COUNT(DISTINCT ch) AS channel_count, COLLECT(DISTINCT ch.channel_name) AS channels
WHERE channel_count > 1
RETURN p.name AS person, channel_count, channels
ORDER BY channel_count DESC LIMIT 25

What are the most discussed topics across all podcasts?
MATCH (c:Claim)
RETURN c.topic AS topic, COUNT(c) AS mentions
ORDER BY mentions DESC LIMIT 25

Now generate a Cypher query for:
"{query}"

Cypher:"""


def _get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def _clean_cypher(raw: str) -> str:
    """Strip markdown fences and whitespace from LLM output."""
    cypher = raw.strip()
    if cypher.startswith("```"):
        lines = cypher.split("\n")
        cypher = "\n".join(
            l for l in lines if not l.strip().startswith("```")
        ).strip()
    return cypher


def _generate_cypher(query: str, error_feedback: str = "") -> str:
    """Use Cortex LLM to generate a Cypher query from natural language."""
    prompt = _CYPHER_PROMPT.format(schema=_SCHEMA, query=query)
    if error_feedback:
        prompt += f"\n\nYour previous attempt failed with: {error_feedback}\nFix the error and try again with a simpler query.\nCypher:"

    raw = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', %s)",
        (prompt,),
    )
    return _clean_cypher(raw) if raw else None


def _run_cypher(cypher: str) -> list[dict]:
    """Execute Cypher against Neo4j and return rows as dicts."""
    driver = _get_driver()
    try:
        with driver.session() as session:
            result = session.run(cypher)
            return [dict(record) for record in result]
    finally:
        driver.close()


def _format_results(rows: list[dict], query: str) -> str:
    """Format raw Neo4j rows into a readable answer using Cortex LLM."""
    if not rows:
        return (
            "No results found in the knowledge graph for this specific query. "
            "This may mean the topic is stored under a different name. "
            "Try broader terms (e.g. 'AI' instead of 'AI safety') or check the Neo4j browser at localhost:7474."
        )

    # Build a compact text representation of the rows
    rows_text = "\n".join(
        ", ".join(f"{k}: {v}" for k, v in row.items())
        for row in rows[:20]  # cap at 20 for prompt size
    )

    prompt = f"""You are a podcast intelligence assistant.

The user asked: "{query}"

Here are the knowledge graph results:
{rows_text}

Write a clear, concise answer (3-6 sentences) based on these results.
Include specific names, numbers, and topics from the data.
Do not mention "Cypher", "Neo4j", or "graph database" — just answer naturally."""

    answer = execute_scalar(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', %s)",
        (prompt,),
    )
    return (answer or "").strip()


def knowledge_graph_agent(state: PodcastIQState) -> dict:
    """
    Knowledge Graph Agent — answers relationship and network queries via Neo4j.

    Args:
        state: Current graph state with user_query

    Returns:
        Updated state with graph_results and summary
    """
    query = state["user_query"]
    log.info(f"[KnowledgeGraph] Processing: '{query}'")

    # Step 1: Generate Cypher (with up to 2 retries on syntax errors)
    cypher = None
    rows = []
    error_feedback = ""
    for attempt in range(3):
        cypher = _generate_cypher(query, error_feedback)
        if not cypher:
            log.warning(f"[KnowledgeGraph] LLM returned empty Cypher (attempt {attempt+1})")
            continue

        log.info(f"[KnowledgeGraph] Attempt {attempt+1} Cypher:\n{cypher}")

        try:
            rows = _run_cypher(cypher)
            log.info(f"[KnowledgeGraph] Query returned {len(rows)} rows")
            break  # success
        except Exception as e:
            error_feedback = str(e)[:300]
            log.warning(f"[KnowledgeGraph] Attempt {attempt+1} failed: {error_feedback}")
            if attempt == 2:
                log.error("[KnowledgeGraph] All attempts failed")
                return {
                    "graph_results": [],
                    "summary": "I couldn't generate a valid graph query for this question. Try rephrasing.",
                    "messages": [f"KnowledgeGraph: failed after 3 attempts — {error_feedback}"],
                }

    # Step 3: Format into natural language answer
    summary = _format_results(rows, query)

    return {
        "graph_results": rows,
        "summary": summary,
        "messages": [f"KnowledgeGraph: {len(rows)} results → answer generated"],
    }
