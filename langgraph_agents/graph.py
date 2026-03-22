"""
PodcastIQ LangGraph — main graph definition.

Flow:
  user_query → [Router] → [Search] → [Summarization] → answer
                       → [KnowledgeGraph] → answer
                       → [Temporal]       → answer
                       → [Comparison]     → answer

Router classifies intent:
  SEARCH / SUMMARIZE / RECOMMEND → Search → Summarization
  GRAPH      → KnowledgeGraph (Neo4j Cypher)
  TEMPORAL   → Temporal (SEM_CLAIM_EVOLUTION)
  COMPARE    → Comparison (SEM_CLAIMS side-by-side)
"""

import logging
from langgraph.graph import StateGraph, END

from langgraph_agents.state import PodcastIQState
from langgraph_agents.agents.router import router_agent
from langgraph_agents.agents.search import search_agent
from langgraph_agents.agents.summarization import summarization_agent
from langgraph_agents.agents.knowledge_graph import knowledge_graph_agent
from langgraph_agents.agents.temporal import temporal_agent
from langgraph_agents.agents.comparison import comparison_agent
from langgraph_agents.agents.recommendation import recommendation_agent
from langgraph_agents.agents.insight import insight_agent

log = logging.getLogger(__name__)


def _route(state: PodcastIQState) -> str:
    """Route to the appropriate agent based on query type."""
    qt = state.get("query_type", "SEARCH")
    if qt == "GRAPH":
        log.info("[Graph] Routing → knowledge_graph")
        return "knowledge_graph"
    if qt == "TEMPORAL":
        log.info("[Graph] Routing → temporal")
        return "temporal"
    if qt == "COMPARE":
        log.info("[Graph] Routing → comparison")
        return "comparison"
    if qt == "RECOMMEND":
        log.info("[Graph] Routing → recommendation")
        return "recommendation"
    if qt == "INSIGHT":
        log.info("[Graph] Routing → insight")
        return "insight"
    log.info(f"[Graph] Routing query_type={qt} → search")
    return "search"


def build_graph():
    graph = StateGraph(PodcastIQState)

    graph.add_node("router",          router_agent)
    graph.add_node("search",          search_agent)
    graph.add_node("summarization",   summarization_agent)
    graph.add_node("knowledge_graph", knowledge_graph_agent)
    graph.add_node("temporal",        temporal_agent)
    graph.add_node("comparison",      comparison_agent)
    graph.add_node("recommendation",  recommendation_agent)
    graph.add_node("insight",         insight_agent)

    graph.set_entry_point("router")

    graph.add_conditional_edges(
        "router",
        _route,
        {
            "search":          "search",
            "knowledge_graph": "knowledge_graph",
            "temporal":        "temporal",
            "comparison":      "comparison",
            "recommendation":  "recommendation",
            "insight":         "insight",
        },
    )

    graph.add_edge("search",          "summarization")
    graph.add_edge("summarization",   END)
    graph.add_edge("knowledge_graph", END)
    graph.add_edge("temporal",        END)
    graph.add_edge("comparison",      END)
    graph.add_edge("recommendation",  END)
    graph.add_edge("insight",         END)

    return graph.compile()


# Module-level compiled graph (import this to run queries)
app = build_graph()


def run(query: str) -> dict:
    """
    Run a query through the full agent pipeline.

    Args:
        query: Natural language question about podcast content

    Returns:
        Final state dict with keys: summary, search_results, graph_results, query_type, messages
    """
    initial_state: PodcastIQState = {
        "user_query":     query,
        "query_type":     "",
        "search_results": [],
        "graph_results":  [],
        "summary":        "",
        "messages":       [],
    }

    final_state = app.invoke(initial_state)
    return final_state


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    query = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "What are the best ways to build muscle?"
    print(f"\nQuery: {query}\n{'='*60}")

    result = run(query)

    print(f"\nQuery Type : {result['query_type']}")
    print(f"Agent Log  : {' | '.join(result['messages'])}")
    print(f"\n{'='*60}")
    print("ANSWER:")
    print(result["summary"])

    if result.get("graph_results"):
        print(f"\n{'='*60}")
        print(f"GRAPH DATA ({len(result['graph_results'])} rows):")
        for row in result["graph_results"][:10]:
            print(f"  {row}")
    elif result.get("search_results"):
        print(f"\n{'='*60}")
        print(f"TOP SOURCES ({len(result['search_results'])} clips):")
        for i, r in enumerate(result["search_results"], 1):
            print(f"  {i}. {r['episode_title'][:55]} — {r['channel_name']}")
            print(f"     {r['youtube_url']}")
