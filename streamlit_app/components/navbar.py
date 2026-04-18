"""
PodcastIQ — Shared top navigation bar.
Call render_navbar() at the top of every page.
"""

import streamlit as st


def render_navbar():
    """Render a full-width top navigation bar with logo + page links."""
    st.markdown("""
<div id="piq-loader">
  <div class="piq-spinner"></div>
  <div class="piq-loader-brand">Podcast<em>IQ</em></div>
</div>
<div class="topnav">
  <div class="topnav-tape"></div>
  <div class="topnav-inner">
    <a class="nav-brand" href="/">
      <span class="nav-brand-icon">
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <rect x="7" y="1" width="6" height="11" rx="3"/>
          <path d="M4 10a6 6 0 0 0 12 0"/>
          <line x1="10" y1="16" x2="10" y2="19"/>
          <line x1="7" y1="19" x2="13" y2="19"/>
        </svg>
      </span>
      <span class="nav-brand-text">Podcast<em>IQ</em></span>
    </a>
    <nav class="nav-links">
      <a href="/" class="nav-link" data-page="chat" target="_self">
        <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linecap="round" stroke-linejoin="round">
          <path d="M2 2.5A1.5 1.5 0 0 1 3.5 1h8A1.5 1.5 0 0 1 13 2.5v5.5A1.5 1.5 0 0 1 11.5 9.5H8l-3 3.5V9.5H3.5A1.5 1.5 0 0 1 2 8V2.5z"/>
        </svg>
        Chat
      </a>
      <a href="/Graph_Explorer" class="nav-link" data-page="graph" target="_self">
        <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linecap="round">
          <circle cx="7.5" cy="2" r="1.3" fill="currentColor" stroke="none"/>
          <circle cx="2" cy="12" r="1.3" fill="currentColor" stroke="none"/>
          <circle cx="13" cy="12" r="1.3" fill="currentColor" stroke="none"/>
          <line x1="7.5" y1="3.3" x2="2" y2="10.7"/>
          <line x1="7.5" y1="3.3" x2="13" y2="10.7"/>
          <line x1="2" y1="10.7" x2="13" y2="10.7"/>
        </svg>
        Graph
      </a>
      <a href="/Channel_Dashboard" class="nav-link" data-page="dashboard" target="_self">
        <svg width="15" height="15" viewBox="0 0 15 15" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linecap="round">
          <rect x="1.5" y="8" width="3" height="5.5" rx="0.5"/>
          <rect x="6" y="5" width="3" height="8.5" rx="0.5"/>
          <rect x="10.5" y="2" width="3" height="11.5" rx="0.5"/>
        </svg>
        Dashboard
      </a>
    </nav>
  </div>
</div>
""", unsafe_allow_html=True)
