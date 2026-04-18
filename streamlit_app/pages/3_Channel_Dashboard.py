"""
PodcastIQ — Channel Dashboard
Per-channel episode coverage, topics, and guest network.
"""

import os
import sys
import html as html_lib
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

st.set_page_config(
    page_title="Channel Dashboard · PodcastIQ",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

_css_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "components", "styles.css")
with open(_css_path, encoding="utf-8") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

from components.navbar import render_navbar
render_navbar()
st.markdown("<style>#piq-loader{display:none!important}</style>", unsafe_allow_html=True)

from components.snowflake_queries import (
    get_channels, get_channel_top_topics, get_channel_guests,
)


def esc(t):
    return html_lib.escape(str(t or ""))


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown('<div class="page-title">Channel Dashboard</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="page-subtitle">Episode coverage, top topics, and guest networks per channel.</div>',
    unsafe_allow_html=True,
)

# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner("Loading channel data..."):
    try:
        channels = get_channels()
    except Exception as e:
        st.error(f"Could not load data: {e}")
        st.stop()

channel_names = [r["CHANNEL_NAME"] for r in channels]

# ── Overview table (HTML — no white iframe) ───────────────────────────────────
st.markdown('<div class="section-label">All Channels — Overview</div>', unsafe_allow_html=True)

cols_def = ["Channel", "Genre", "Episodes", "Coverage"]
headers  = "".join(
    f'<th style="padding:.55rem .9rem;text-align:left;font-size:.72rem;font-weight:600;'
    f'color:#E8531A;letter-spacing:.06em;text-transform:uppercase;'
    f'border-bottom:1px solid rgba(232,83,26,.25);white-space:nowrap;">{c}</th>'
    for c in cols_def
)
rows_html = ""
for i, ch in enumerate(sorted(channels, key=lambda x: x.get("EPISODE_COUNT", 0), reverse=True)):
    name      = esc(ch.get("CHANNEL_NAME", ""))
    genre     = esc(ch.get("GENRE", "—"))
    eps       = ch.get("EPISODE_COUNT", 0)
    earliest  = str(ch.get("EARLIEST", ""))[:10]
    latest    = str(ch.get("LATEST", ""))[:10]
    coverage  = f"{earliest} → {latest}" if earliest and latest else "—"
    bg        = "rgba(255,255,255,.03)" if i % 2 == 0 else "transparent"
    rows_html += f"""
<tr style="background:{bg};">
  <td style="padding:.5rem .9rem;font-size:.82rem;color:#F0EDE8;
             border-bottom:1px solid rgba(255,255,255,.05);font-weight:500;">{name}</td>
  <td style="padding:.5rem .9rem;font-size:.8rem;color:rgba(240,237,232,.55);
             border-bottom:1px solid rgba(255,255,255,.05);">{genre}</td>
  <td style="padding:.5rem .9rem;font-size:.8rem;color:#F2873A;
             border-bottom:1px solid rgba(255,255,255,.05);text-align:right;">{eps}</td>
  <td style="padding:.5rem .9rem;font-size:.76rem;color:rgba(240,237,232,.38);
             border-bottom:1px solid rgba(255,255,255,.05);">{coverage}</td>
</tr>"""

st.markdown(f"""
<div style="overflow-x:auto;border-radius:.8rem;border:1px solid rgba(255,255,255,.08);
            background:#141210;margin-top:.4rem;">
  <table style="width:100%;border-collapse:collapse;">
    <thead><tr style="background:rgba(232,83,26,.08);">{headers}</tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Channel deep-dive ─────────────────────────────────────────────────────────
st.markdown('<div class="section-label">Channel Deep Dive</div>', unsafe_allow_html=True)

selected_channel = st.selectbox(
    "Select channel",
    channel_names,
    label_visibility="collapsed",
    placeholder="Choose a channel...",
)

if selected_channel:
    ep_row   = next((r for r in channels if r["CHANNEL_NAME"] == selected_channel), {})
    earliest = str(ep_row.get("EARLIEST", ""))[:10]
    latest   = str(ep_row.get("LATEST",   ""))[:10]

    # ── Stat tiles ─────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    tiles = [
        (col1, str(ep_row.get("EPISODE_COUNT", 0)), "Episodes"),
        (col2, earliest or "—",                     "First Episode"),
        (col3, latest   or "—",                     "Latest Episode"),
    ]
    for col, val, label in tiles:
        with col:
            st.markdown(f"""
<div class="stat-tile">
  <div class="stat-tile-value" style="font-size:1.1rem;">{val}</div>
  <div class="stat-tile-label">{label}</div>
</div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Top topics bar ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Top Topics</div>', unsafe_allow_html=True)
    try:
        with st.spinner("Loading topics..."):
            topics = get_channel_top_topics(selected_channel, 10)

        if topics:
            df_topics = pd.DataFrame(topics)
            df_topics.columns = [c.upper() for c in df_topics.columns]
            fig_bar = go.Figure(go.Bar(
                x=df_topics["CLAIM_COUNT"],
                y=df_topics["TOPIC"],
                orientation="h",
                marker_color="#E8531A",
                marker_line_width=0,
                opacity=0.85,
            ))
            fig_bar.update_layout(
                height=320,
                margin=dict(l=0, r=0, t=5, b=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(255,255,255,.02)",
                xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,.06)",
                           title="", color="rgba(240,237,232,.4)",
                           tickfont=dict(color="rgba(240,237,232,.4)")),
                yaxis=dict(showgrid=False, autorange="reversed", title="",
                           tickfont=dict(size=11, color="rgba(240,237,232,.62)")),
                font=dict(family="DM Sans", size=11, color="rgba(240,237,232,.55)"),
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No topic data for this channel.")
    except Exception as e:
        st.warning(f"Topics error: {e}")

    # ── Guest list ─────────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Notable Guests</div>', unsafe_allow_html=True)
    try:
        with st.spinner("Loading guests..."):
            guests = get_channel_guests(selected_channel)

        if guests:
            gcols = st.columns(4)
            for i, g in enumerate(guests[:12]):
                name   = g.get("PARTICIPANT_NAME", "")
                ep_cnt = g.get("EPISODE_COUNT", 0)
                with gcols[i % 4]:
                    st.markdown(f"""
<div class="result-card" style="padding:0.7rem 0.875rem;text-align:center;">
  <div style="width:36px;height:36px;border-radius:50%;
    background:rgba(232,83,26,.15);border:1px solid rgba(232,83,26,.28);
    display:flex;align-items:center;justify-content:center;
    font-size:0.9rem;font-weight:700;color:#F2873A;
    margin:0 auto 0.5rem;">
    {esc(name[0].upper()) if name else "?"}
  </div>
  <div style="font-size:0.825rem;font-weight:600;color:#F0EDE8;">{esc(name)}</div>
  <div style="font-size:0.68rem;color:rgba(240,237,232,.38);margin-top:0.15rem;">
    {ep_cnt} episode{"s" if ep_cnt != 1 else ""}
  </div>
</div>""", unsafe_allow_html=True)
        else:
            st.info("No guest data for this channel.")
    except Exception as e:
        st.warning(f"Guests error: {e}")
