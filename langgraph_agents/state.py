"""
PodcastIQ LangGraph state definition.
"""

import operator
from typing import Annotated, TypedDict


class SearchResult(TypedDict):
    chunk_id: str
    episode_title: str
    channel_name: str
    chunk_text: str
    youtube_url: str
    publish_date: str


class PodcastIQState(TypedDict):
    # Input
    user_query: str

    # Router output
    query_type: str          # SEARCH | SUMMARIZE | COMPARE | RECOMMEND | GRAPH

    # Search agent output
    search_results: list[SearchResult]

    # Knowledge Graph agent output
    graph_results: list[dict]

    # Summarization agent output
    summary: str

    # Append-only log of agent actions (for debugging / display)
    messages: Annotated[list[str], operator.add]
