"""
PodcastIQ — Knowledge Graph Explorer
Interactive force-directed graph via pyvis.
"""

import os
import sys
import streamlit as st
import streamlit.components.v1 as components

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

st.set_page_config(
    page_title="Graph Explorer · PodcastIQ",
    page_icon="🕸️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
_css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "components", "styles.css")
with open(_css_path, encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Navbar ────────────────────────────────────────────────────────────────────
from components.navbar import render_navbar
render_navbar()

# ── Imports ───────────────────────────────────────────────────────────────────
from components.neo4j_queries import (
    get_top_nodes, get_node_neighborhood, search_graph_nodes, get_graph_stats
)

# ── Node colours ──────────────────────────────────────────────────────────────
NODE_COLORS = {
    "Person":  "#f472b6",
    "Topic":   "#818cf8",
    "Channel": "#fbbf24",
    "Episode": "#34d399",
    "Claim":   "#64748b",
}

VERIFY_COLORS = {
    "VERIFIED":   "#34d399",
    "FALSE":      "#f87171",
    "OUTDATED":   "#fbbf24",
    "DISPUTED":   "#fbbf24",
    "UNVERIFIED": "#64748b",
    "PENDING":    "#475569",
}


def build_pyvis_graph(nodes: list, edges: list, height: str = "620px") -> str:
    from pyvis.network import Network

    net = Network(height=height, width="100%", bgcolor="#0d0d1a",
                  font_color="#94a3b8", directed=False)
    net.set_options("""
    {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -60,
          "centralGravity": 0.005,
          "springLength": 120,
          "springConstant": 0.08
        },
        "solver": "forceAtlas2Based",
        "stabilization": { "iterations": 150 }
      },
      "edges": {
        "color": { "color": "rgba(255,255,255,0.08)", "highlight": "#a855f7" },
        "width": 1,
        "smooth": { "type": "continuous" }
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 100,
        "navigationButtons": false
      }
    }
    """)

    added_ids = set()
    for n in nodes:
        nid   = n["id"]
        label = n.get("label", "Node")
        name  = n.get("display_name", str(nid))
        deg   = n.get("degree", 1)
        size  = max(10, min(40, 10 + deg * 0.6))

        if label == "Claim":
            vstatus = n.get("verification_status", "PENDING") or "PENDING"
            color   = VERIFY_COLORS.get(vstatus, "#64748b")
        else:
            color = NODE_COLORS.get(label, "#64748b")

        title = f"<b style='color:#e2e8f0'>{label}</b>: {name}<br><span style='color:#64748b'>Connections: {deg}</span>"
        url   = n.get("youtube_url", "")
        if url:
            title += f"<br><a href='{url}' target='_blank' style='color:#a855f7'>▶ Watch</a>"

        net.add_node(nid, label=name[:30], title=title,
                     color=color, size=size, font={"size": 11, "color": "#94a3b8"})
        added_ids.add(nid)

    for e in edges:
        src, tgt = e["source"], e["target"]
        if src in added_ids and tgt in added_ids:
            net.add_edge(src, tgt, title=e.get("rel_type", ""), width=1)

    tmp = os.path.join(os.path.dirname(__file__), "_graph_tmp.html")
    net.save_graph(tmp)
    with open(tmp, "r", encoding="utf-8") as f:
        html = f.read()
    os.remove(tmp)
    return html

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="page-title">Knowledge Graph Explorer</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-subtitle">Explore relationships between speakers, topics, episodes, channels, and claims.</div>',
    unsafe_allow_html=True,
)

# ── Graph stats ───────────────────────────────────────────────────────────────
try:
    with st.spinner("Loading graph stats..."):
        gstats = get_graph_stats()

    if gstats:
        cols = st.columns(len(gstats))
        for i, (label, count) in enumerate(gstats.items()):
            color = NODE_COLORS.get(label, "#7c3aed")
            with cols[i]:
                st.markdown(f"""
<div class="stat-tile">
  <div class="stat-tile-value" style="color:{color};">{count:,}</div>
  <div class="stat-tile-label">{label}s</div>
</div>""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
except Exception as e:
    st.warning(f"Could not load graph stats: {e}")

# ── Controls ──────────────────────────────────────────────────────────────────
col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([3, 2, 1])

with col_ctrl1:
    search_query = st.text_input(
        "Search nodes",
        placeholder="e.g. Sam Altman, AI safety, Lex Fridman...",
        label_visibility="collapsed",
    )
with col_ctrl2:
    label_filter = st.selectbox(
        "Filter by type",
        ["All", "Person", "Topic", "Channel", "Episode", "Claim"],
        label_visibility="collapsed",
    )
with col_ctrl3:
    node_limit = st.selectbox("Nodes", [100, 150, 200], index=1, label_visibility="collapsed")

# ── Legend ────────────────────────────────────────────────────────────────────
legend_html = " &nbsp; ".join(
    f'<span style="display:inline-flex;align-items:center;gap:5px;font-size:0.75rem;color:#64748b;">'
    f'<span style="width:9px;height:9px;border-radius:50%;background:{c};display:inline-block;"></span>'
    f'{l}</span>'
    for l, c in NODE_COLORS.items()
)
st.markdown(f'<div style="margin-bottom:1rem;">{legend_html}</div>', unsafe_allow_html=True)

# ── Graph rendering ───────────────────────────────────────────────────────────
try:
    if search_query.strip():
        with st.spinner("Searching graph..."):
            found_nodes = search_graph_nodes(search_query.strip(), label_filter)
            if found_nodes:
                node_ids = [n["id"] for n in found_nodes[:1]]
                nodes, edges = get_node_neighborhood(node_ids[0])
            else:
                nodes, edges = [], []

        if not nodes and not found_nodes:
            st.info("No nodes found. Try a different search term.")
        elif found_nodes:
            st.markdown(
                f'<div class="section-label">Search results — {len(found_nodes)} nodes found</div>',
                unsafe_allow_html=True,
            )
            for n in found_nodes[:10]:
                col_a, col_b = st.columns([6, 1])
                with col_a:
                    lbl   = n.get("label", "")
                    name  = n.get("display_name", "")
                    deg   = n.get("degree", 0)
                    color = NODE_COLORS.get(lbl, "#64748b")
                    st.markdown(
                        f'<span style="display:inline-flex;align-items:center;gap:7px;">'
                        f'<span style="width:9px;height:9px;border-radius:50%;background:{color};'
                        f'display:inline-block;flex-shrink:0;"></span>'
                        f'<b style="font-size:0.875rem;color:#e2e8f0;">{name}</b>'
                        f'<span style="font-size:0.75rem;color:#475569;">{lbl} · {deg} connections</span>'
                        f'</span>',
                        unsafe_allow_html=True,
                    )
                with col_b:
                    if st.button("Explore", key=f"exp_{n['id']}"):
                        st.session_state["explore_node_id"]   = n["id"]
                        st.session_state["explore_node_name"] = n["display_name"]
                        st.rerun()

    # Ego-network mode
    if "explore_node_id" in st.session_state:
        nid  = st.session_state["explore_node_id"]
        name = st.session_state.get("explore_node_name", str(nid))

        col_h, col_x = st.columns([8, 1])
        with col_h:
            st.markdown(
                f'<div class="section-label">Neighborhood of: '
                f'<span style="color:#c4b5fd;">{name}</span></div>',
                unsafe_allow_html=True,
            )
        with col_x:
            if st.button("✕ Clear", key="clear_ego"):
                del st.session_state["explore_node_id"]
                st.rerun()

        with st.spinner("Building neighborhood graph..."):
            nodes, edges = get_node_neighborhood(nid)
        st.markdown(
            f'<div style="font-size:.75rem;color:#64748b;margin-bottom:.5rem;">'
            f'{len(nodes)} nodes · {len(edges)} edges loaded</div>',
            unsafe_allow_html=True,
        )

    else:
        with st.spinner("Loading knowledge graph..."):
            nodes, edges = get_top_nodes(node_limit)
        st.markdown(
            f'<div style="font-size:.75rem;color:#64748b;margin-bottom:.5rem;">'
            f'{len(nodes)} nodes · {len(edges)} edges loaded</div>',
            unsafe_allow_html=True,
        )

    if nodes:
        graph_html = build_pyvis_graph(nodes, edges)
        components.html(graph_html, height=640, scrolling=False)
    else:
        st.info("No graph data available.")

except Exception as e:
    st.error(f"Graph error: {e}")
    st.info("Make sure Neo4j is running: `docker start neo4j-podcastiq`")
