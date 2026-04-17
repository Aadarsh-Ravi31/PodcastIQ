"""
PodcastIQ — Shared top navigation bar.
Call render_navbar() at the top of every page.
"""

import streamlit as st


def render_navbar():
    """Render a full-width top navigation bar with logo + page links."""
    st.markdown("""
<div class="topnav">
  <div class="topnav-inner">
    <a class="nav-brand" href="/">
      <span class="nav-brand-icon">🎙️</span>
      <span class="nav-brand-text">PodcastIQ</span>
    </a>
    <nav class="nav-links">
      <a href="/"                  class="nav-link" data-page="chat"      target="_self">💬&nbsp; Chat</a>
      <a href="/Graph_Explorer"    class="nav-link" data-page="graph"     target="_self">🕸️&nbsp; Graph</a>
      <a href="/Channel_Dashboard" class="nav-link" data-page="dashboard" target="_self">📊&nbsp; Dashboard</a>
    </nav>
  </div>
</div>
<script>
(function () {
  try {
    var path = window.location.pathname;
    var map = {
      "chat":      ["/"],
      "graph":     ["/Graph_Explorer"],
      "dashboard": ["/Channel_Dashboard"]
    };
    Object.keys(map).forEach(function(page) {
      map[page].forEach(function(p) {
        if (path === p || path.endsWith(p)) {
          var el = document.querySelector('.nav-link[data-page="' + page + '"]');
          if (el) el.classList.add("nav-active");
        }
      });
    });
    // fallback: home page
    if (path === "/" || path === "") {
      var el = document.querySelector('.nav-link[data-page="chat"]');
      if (el) el.classList.add("nav-active");
    }
  } catch(e) {}
})();
</script>
""", unsafe_allow_html=True)
