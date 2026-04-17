"""
Cached Neo4j queries for the Graph Explorer page.
"""

import os
import sys
import streamlit as st
from neo4j import GraphDatabase
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER     = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "podcastiq123")

_driver = None


def get_driver():
    global _driver
    if _driver is None:
        _driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return _driver


def _run(cypher: str, params: dict = {}) -> list[dict]:
    driver = get_driver()
    with driver.session() as session:
        result = session.run(cypher, params)
        return [dict(record) for record in result]


# ── Graph Explorer queries ─────────────────────────────────────────────────────

@st.cache_data(ttl=1800, show_spinner=False)
def get_top_nodes(limit: int = 150) -> tuple[list[dict], list[dict]]:
    """Return top nodes by degree + their edges for visualization."""
    nodes_raw = _run("""
        MATCH (n)
        WHERE n:Person OR n:Topic OR n:Channel OR n:Episode OR n:Claim
        WITH n, labels(n)[0] AS label,
             size([(n)--() | 1]) AS degree
        ORDER BY degree DESC
        LIMIT $limit
        RETURN
            id(n)      AS id,
            label,
            degree,
            CASE label
                WHEN 'Person'  THEN coalesce(n.name, '')
                WHEN 'Topic'   THEN coalesce(n.name, '')
                WHEN 'Channel' THEN coalesce(n.channel_name, '')
                WHEN 'Episode' THEN coalesce(n.title, '')
                WHEN 'Claim'   THEN left(coalesce(n.text, ''), 60) + '...'
                ELSE ''
            END AS display_name,
            CASE label
                WHEN 'Claim' THEN coalesce(n.verification_status, 'PENDING')
                ELSE null
            END AS verification_status,
            coalesce(n.youtube_url, '') AS youtube_url
    """, {"limit": limit})

    node_ids = [n["id"] for n in nodes_raw]
    edges_raw = _run("""
        MATCH (a)-[r]->(b)
        WHERE id(a) IN $ids AND id(b) IN $ids
        RETURN id(a) AS source, id(b) AS target, type(r) AS rel_type
        LIMIT 600
    """, {"ids": node_ids})

    return nodes_raw, edges_raw


@st.cache_data(ttl=1800, show_spinner=False)
def get_node_neighborhood(node_id: int, depth: int = 1) -> tuple[list[dict], list[dict]]:
    """Return ego network around a specific node."""
    nodes_raw = _run("""
        MATCH (n) WHERE id(n) = $nid
        OPTIONAL MATCH (n)-[r]-(neighbor)
        WITH collect(DISTINCT n) + collect(DISTINCT neighbor) AS all_nodes
        UNWIND all_nodes AS node
        WITH DISTINCT node, labels(node)[0] AS label
        RETURN
            id(node) AS id,
            label,
            size([(node)--() | 1]) AS degree,
            CASE label
                WHEN 'Person'  THEN coalesce(node.name, '')
                WHEN 'Topic'   THEN coalesce(node.name, '')
                WHEN 'Channel' THEN coalesce(node.channel_name, '')
                WHEN 'Episode' THEN coalesce(node.title, '')
                WHEN 'Claim'   THEN left(coalesce(node.text, ''), 60) + '...'
                ELSE ''
            END AS display_name,
            CASE label
                WHEN 'Claim' THEN coalesce(node.verification_status, 'PENDING')
                ELSE null
            END AS verification_status,
            coalesce(node.youtube_url, '') AS youtube_url
    """, {"nid": node_id})

    node_ids = [n["id"] for n in nodes_raw]
    edges_raw = _run("""
        MATCH (a)-[r]->(b)
        WHERE id(a) IN $ids AND id(b) IN $ids
        RETURN id(a) AS source, id(b) AS target, type(r) AS rel_type
    """, {"ids": node_ids})

    return nodes_raw, edges_raw


@st.cache_data(ttl=1800, show_spinner=False)
def search_graph_nodes(query: str, label_filter: str = "All") -> list[dict]:
    """Search nodes by name."""
    kw = query.lower()
    label_clause = f"AND n:{label_filter}" if label_filter != "All" else ""
    return _run(f"""
        MATCH (n)
        WHERE (n:Person OR n:Topic OR n:Channel OR n:Episode OR n:Claim)
          {label_clause}
          AND (
              toLower(coalesce(n.name, '')) CONTAINS $kw OR
              toLower(coalesce(n.title, '')) CONTAINS $kw OR
              toLower(coalesce(n.channel_name, '')) CONTAINS $kw OR
              toLower(coalesce(n.text, '')) CONTAINS $kw
          )
        WITH n, labels(n)[0] AS label, size([(n)--() | 1]) AS degree
        ORDER BY degree DESC
        LIMIT 30
        RETURN
            id(n) AS id,
            label,
            degree,
            CASE label
                WHEN 'Person'  THEN coalesce(n.name, '')
                WHEN 'Topic'   THEN coalesce(n.name, '')
                WHEN 'Channel' THEN coalesce(n.channel_name, '')
                WHEN 'Episode' THEN coalesce(n.title, '')
                WHEN 'Claim'   THEN left(coalesce(n.text, ''), 80)
                ELSE ''
            END AS display_name,
            coalesce(n.youtube_url, '') AS youtube_url
    """, {"kw": kw})


@st.cache_data(ttl=1800, show_spinner=False)
def get_graph_stats() -> dict:
    rows = _run("""
        MATCH (n) RETURN labels(n)[0] AS label, count(*) AS cnt
    """)
    stats = {}
    for r in rows:
        if r.get("label"):
            stats[r["label"]] = r["cnt"]
    return stats
