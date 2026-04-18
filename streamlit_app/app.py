"""
PodcastIQ — Chat Interface  v2.0
"""

import os
import sys
import time
import html as html_lib
import streamlit as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

st.set_page_config(
    page_title="PodcastIQ",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ──────────────────────────────────────────────────────────────────────
_css_path = os.path.join(os.path.dirname(__file__), "components", "styles.css")
_css = open(_css_path, encoding="utf-8").read()
st.markdown(f"<style>{_css}</style>", unsafe_allow_html=True)

# ── Navbar ───────────────────────────────────────────────────────────────────
from components.navbar import render_navbar
from components.guardrails import validate_query, RESPONSE_DISCLAIMER
from components.gpt4o_validator import validate_response, AGENTS_TO_VALIDATE
render_navbar()

# ── Session state ────────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def esc(text: str) -> str:
    """HTML-escape a value safely."""
    return html_lib.escape(str(text or ""))


def stream_words(text: str):
    """Yield words one at a time for a typewriter effect."""
    for word in text.split(" "):
        yield word + " "
        time.sleep(0.025)


def badge(status: str) -> str:
    s = status.lower().replace(" ", "-")
    return f'<span class="badge badge-{s}">{esc(status)}</span>'


def verdict_icon(status: str) -> str:
    return {"VERIFIED": "✅", "FALSE": "❌", "OUTDATED": "⚠️",
            "DISPUTED": "⚠️", "UNVERIFIED": "❓"}.get(status.upper(), "❓")


def verdict_color(status: str) -> str:
    return {"VERIFIED": "#10b981", "FALSE": "#ef4444",
            "OUTDATED": "#f59e0b", "DISPUTED": "#f59e0b",
            "UNVERIFIED": "#475569"}.get(status.upper(), "#475569")


# ─────────────────────────────────────────────────────────────────────────────
# Rich result renderers
# ─────────────────────────────────────────────────────────────────────────────

def render_sources(results: list):
    if not results:
        return
    st.markdown('<div class="section-label">Sources</div>', unsafe_allow_html=True)
    st.markdown('<div class="source-cards-grid">', unsafe_allow_html=True)
    for i, r in enumerate(results[:6], 1):
        title = esc(r.get("EPISODE_TITLE") or r.get("episode_title", ""))
        chan   = esc(r.get("CHANNEL_NAME")  or r.get("channel_name", ""))
        text   = esc(r.get("CHUNK_TEXT")   or r.get("chunk_text", ""))[:300]
        url    = r.get("YOUTUBE_URL")  or r.get("youtube_url", "")
        date   = str(r.get("PUBLISH_DATE") or r.get("publish_date", ""))[:10]
        score_raw = r.get("relevance_score") or r.get("@scores")
        if isinstance(score_raw, dict):
            score_raw = score_raw.get("cosine_similarity", 0)
        score_pct = int(float(score_raw) * 100) if score_raw else None
        score_color = (
            "#10b981" if score_pct and score_pct >= 80 else
            "#f59e0b" if score_pct and score_pct >= 60 else
            "#94a3b8"
        )
        score_pill = (
            f'<span style="font-size:.65rem;font-weight:700;padding:.15rem .5rem;'
            f'border-radius:999px;background:{score_color}22;color:{score_color};'
            f'border:1px solid {score_color}55;font-family:\'JetBrains Mono\',monospace;">'
            f'{score_pct}% match</span>'
        ) if score_pct is not None else ""
        yt_btn = (f'<a class="sc-link" href="{esc(url)}" target="_blank">'
                  f'▶ Watch on YouTube</a>') if url else ""
        st.markdown(f"""
<div class="source-card">
  <div class="sc-header">
    <span class="sc-title">{title}</span>
    <span class="sc-num">#{i:02d}</span>
  </div>
  <div class="sc-meta">
    <span class="sc-channel-pill">{chan}</span>
    <span>{date}</span>
    {score_pill}
  </div>
  <div class="sc-text">{text}</div>
  {yt_btn}
</div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def render_episode_cards(results: list):
    if not results:
        return
    # Deduplicate by (title, channel) — timestamped URLs create false duplicates
    seen: set = set()
    deduped = []
    for r in results:
        key = (r.get("EPISODE_TITLE") or r.get("episode_title", ""),
               r.get("CHANNEL_NAME")  or r.get("channel_name", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    st.markdown('<div class="section-label">Recommended Episodes</div>', unsafe_allow_html=True)
    st.markdown('<div class="episode-grid">', unsafe_allow_html=True)
    for r in deduped[:8]:
        title = esc(r.get("EPISODE_TITLE") or r.get("episode_title", ""))
        chan   = esc(r.get("CHANNEL_NAME")  or r.get("channel_name", ""))
        url    = r.get("YOUTUBE_URL")  or r.get("youtube_url", "")
        date   = str(r.get("PUBLISH_DATE") or r.get("publish_date", ""))[:10]
        yt_btn = (f'<a class="ep-link" href="{esc(url)}" target="_blank">'
                  f'▶ Watch episode</a>') if url else ""
        st.markdown(f"""
<div class="episode-card">
  <div class="ep-title">{title}</div>
  <div class="ep-meta">{chan} · {date}</div>
  {yt_btn}
</div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)


def render_factcheck(results: list):
    if not results:
        return
    ev      = results[0]
    status  = str(ev.get("status", "UNVERIFIED")).upper()
    claim   = esc(ev.get("claim", ""))
    summary = esc(ev.get("evidence_summary", ""))
    urls    = ev.get("evidence_urls", []) or []
    web_n   = ev.get("web_results_used", 0)
    icon    = verdict_icon(status)
    color   = verdict_color(status)
    src_note = (f"🌐 Verified via {web_n} web sources"
                if web_n else "🤖 Verified from AI training knowledge")
    v_cls = f"verdict-{status.lower()}"
    st.markdown(f"""
<div class="verdict-card {v_cls}">
  <div class="verdict-top">
    <span class="verdict-icon">{icon}</span>
    <span class="verdict-status-text" style="color:{color};">{status}</span>
  </div>
  <div class="verdict-claim">"{claim}"</div>
  <div class="verdict-summary">{summary}</div>
  <div class="verdict-source-note">{src_note}</div>
</div>""", unsafe_allow_html=True)

    if urls:
        st.markdown('<div class="section-label">Evidence</div>', unsafe_allow_html=True)
        st.markdown('<div class="evidence-links">', unsafe_allow_html=True)
        for u in urls[:4]:
            st.markdown(
                f'<a class="evidence-link" href="{esc(u)}" target="_blank">'
                f'🔗 {esc(u)}</a>',
                unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


def render_temporal(results: list):
    if not results:
        return
    # Only show cards for same-speaker pairs — cross-speaker noise looks broken
    same_speaker = [r for r in results
                    if r.get("ORIGINAL_SPEAKER") == r.get("EVOLVED_SPEAKER")]
    display = same_speaker if same_speaker else []
    if not display:
        return  # text-only answer is better than misleading cross-speaker cards
    st.markdown('<div class="section-label">Claim Evolution</div>', unsafe_allow_html=True)
    for r in display[:5]:
        drift = (r.get("DRIFT_TYPE") or r.get("drift_type", "REVISED")).upper()
        orig  = esc(r.get("ORIGINAL_TEXT") or r.get("original_text", ""))[:260]
        evol  = esc(r.get("EVOLVED_TEXT")  or r.get("evolved_text", ""))[:260]
        o_spk = esc(r.get("ORIGINAL_SPEAKER") or r.get("original_speaker", "Unknown"))
        e_spk = esc(r.get("EVOLVED_SPEAKER")  or r.get("evolved_speaker", "Unknown"))
        o_dt  = str(r.get("ORIGINAL_DATE") or r.get("original_date", ""))[:10]
        e_dt  = str(r.get("EVOLVED_DATE")  or r.get("evolved_date", ""))[:10]
        o_url = r.get("ORIGINAL_URL") or r.get("original_url", "")
        e_url = r.get("EVOLVED_URL")  or r.get("evolved_url", "")
        days  = r.get("TIME_DELTA_DAYS") or r.get("time_delta_days", "")
        o_link = (f'<a class="sc-link" href="{esc(o_url)}" target="_blank" '
                  f'style="font-size:.65rem;padding:.12rem .45rem;">▶</a>') if o_url else ""
        e_link = (f'<a class="sc-link" href="{esc(e_url)}" target="_blank" '
                  f'style="font-size:.65rem;padding:.12rem .45rem;">▶</a>') if e_url else ""
        st.markdown(f"""
<div class="evolution-pair">
  <div class="claim-card original">
    <div class="claim-text">{orig}</div>
    <div class="claim-meta">
      <span class="claim-speaker">{o_spk}</span>
      <span style="display:flex;align-items:center;gap:.3rem;">{o_dt} {o_link}</span>
    </div>
  </div>
  <div class="evolution-connector">
    {badge(drift)}
    <span class="evolution-days">{days}d</span>
    <span class="evolution-arrow">→</span>
  </div>
  <div class="claim-card evolved">
    <div class="claim-text">{evol}</div>
    <div class="claim-meta">
      <span class="claim-speaker">{e_spk}</span>
      <span style="display:flex;align-items:center;gap:.3rem;">{e_dt} {e_link}</span>
    </div>
  </div>
</div>""", unsafe_allow_html=True)


def render_comparison(results: list):
    if not results:
        return
    # Group by speaker so we show claims from BOTH entities, not just the first
    from collections import defaultdict
    by_speaker: dict = defaultdict(list)
    for r in results:
        spk = r.get("SPEAKER") or r.get("speaker", "Unknown")
        by_speaker[spk].append(r)

    st.markdown('<div class="section-label">Claims Compared</div>', unsafe_allow_html=True)
    for spk_name, rows in by_speaker.items():
        st.markdown(
            f'<div style="color:#a855f7;font-size:.7rem;font-weight:700;'
            f'letter-spacing:.08em;text-transform:uppercase;margin:.8rem 0 .3rem;">'
            f'{esc(spk_name)}</div>',
            unsafe_allow_html=True)
        for r in rows[:5]:
            txt  = esc(r.get("CLAIM_TEXT") or r.get("claim_text", ""))
            url  = r.get("YOUTUBE_URL") or r.get("youtube_url", "")
            chan = esc(r.get("CHANNEL_NAME") or r.get("channel_name", ""))
            ct   = esc((r.get("CLAIM_TYPE") or r.get("claim_type", "CLAIM")).upper())
            link = (f'<a class="sc-link" href="{esc(url)}" target="_blank" '
                    f'style="font-size:.68rem;padding:.18rem .55rem;">▶ Watch</a>') if url else ""
            st.markdown(f"""
<div class="comparison-card">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:.3rem;">
    <span class="sc-channel-pill">{chan}</span>
    {badge(ct)}
  </div>
  <div class="cmp-text">{txt}</div>
  <div style="margin-top:.4rem;">{link}</div>
</div>""", unsafe_allow_html=True)


def render_insight(results: list):
    if not results:
        return
    st.markdown('<div class="section-label">Analysis</div>', unsafe_allow_html=True)

    # Build HTML table — st.dataframe renders in a white iframe we can't style
    cols = list(results[0].keys())
    headers = "".join(
        f'<th style="padding:.55rem .9rem;text-align:left;font-size:.72rem;'
        f'font-weight:600;color:#a855f7;letter-spacing:.06em;text-transform:uppercase;'
        f'border-bottom:1px solid rgba(168,85,247,.25);white-space:nowrap;">'
        f'{esc(c.replace("_"," ").title())}</th>'
        for c in cols
    )
    rows_html = ""
    for i, r in enumerate(results):
        bg = "rgba(255,255,255,.025)" if i % 2 == 0 else "transparent"
        cells = "".join(
            f'<td style="padding:.5rem .9rem;font-size:.8rem;color:#dde1ea;'
            f'border-bottom:1px solid rgba(255,255,255,.04);">'
            f'{esc(str(r.get(c, "")))}</td>'
            for c in cols
        )
        rows_html += f'<tr style="background:{bg};">{cells}</tr>'

    st.markdown(f"""
<div style="overflow-x:auto;border-radius:.8rem;border:1px solid rgba(255,255,255,.07);
            background:#0d0d1f;margin-top:.4rem;">
  <table style="width:100%;border-collapse:collapse;">
    <thead><tr style="background:rgba(109,40,217,.15);">{headers}</tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
</div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Agent labels
# ─────────────────────────────────────────────────────────────────────────────

AGENT_LABELS = {
    "SEARCH":    "Search Agent",
    "SUMMARIZE": "Summarization Agent",
    "GRAPH":     "Knowledge Graph Agent",
    "TEMPORAL":  "Temporal Analysis Agent",
    "COMPARE":   "Comparison Agent",
    "RECOMMEND": "Recommendation Agent",
    "INSIGHT":   "Insight Agent",
    "FACTCHECK": "Fact-Check Agent",
}

AGENT_ICONS = {
    "SEARCH": "🔍", "SUMMARIZE": "📝", "GRAPH": "🕸️",
    "TEMPORAL": "⏳", "COMPARE": "⚖️", "RECOMMEND": "🎯",
    "INSIGHT": "📊", "FACTCHECK": "✅",
}


# ─────────────────────────────────────────────────────────────────────────────
# Message renderer
# ─────────────────────────────────────────────────────────────────────────────

def render_message(msg: dict, is_new: bool = False):
    role    = msg["role"]
    content = msg["content"]
    meta    = msg.get("meta", {})

    if role == "user":
        st.markdown(f"""
<div class="chat-wrap">
  <div class="msg-user">
    <div class="msg-user-bubble">{esc(content)}</div>
  </div>
</div>""", unsafe_allow_html=True)

    else:
        qt = meta.get("query_type", "")
        sr = meta.get("search_results", [])
        gr = meta.get("graph_results", [])

        # Avatar + body in narrow/wide columns
        col_icon, col_body = st.columns([0.06, 0.94])
        with col_icon:
            st.markdown('<div class="msg-avatar">🎙️</div>', unsafe_allow_html=True)
        with col_body:
            # Native Streamlit markdown so bold/italic/code/links render correctly
            st.markdown(f'<div class="msg-body">', unsafe_allow_html=True)
            # For FACTCHECK, the verdict card already shows claim + verdict + summary,
            # so skip the markdown text to avoid duplicate rendering.
            if not (qt == "FACTCHECK" and gr):
                # Stream word-by-word for text-heavy responses; render instantly otherwise
                if is_new and qt in ("SUMMARIZE", "SEARCH", ""):
                    st.write_stream(stream_words(content))
                else:
                    st.markdown(content)
            st.markdown("</div>", unsafe_allow_html=True)

            # Rich result block
            if qt in ("SEARCH", "SUMMARIZE"):   render_sources(sr)
            elif qt == "RECOMMEND":             render_episode_cards(gr)
            elif qt == "FACTCHECK":             render_factcheck(gr)
            elif qt == "TEMPORAL":              render_temporal(gr)
            elif qt == "COMPARE":               render_comparison(gr)
            elif qt == "INSIGHT":               render_insight(gr)

            # Disclaimer — shown whenever real people / claims are involved
            if qt:
                st.markdown(
                    f'<div class="response-disclaimer">{RESPONSE_DISCLAIMER}</div>',
                    unsafe_allow_html=True)
                icon  = AGENT_ICONS.get(qt, "⚡")
                label = AGENT_LABELS.get(qt, qt)
                st.markdown(
                    f'<div class="agent-tag">{icon} {label}</div>',
                    unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Hero (shown before any messages)
# ─────────────────────────────────────────────────────────────────────────────

if not st.session_state.messages:
    st.markdown("""
<div class="hero-wrap">
  <div class="hero-eyebrow">
    <span class="hero-eyebrow-dot"></span>
    AI Podcast Intelligence Platform
  </div>
  <div class="hero-title">PodcastIQ</div>
  <div class="hero-sub">
    Search, summarize, fact-check, and explore 290+ episodes
    from 25 channels — powered by 9 specialized AI agents.
  </div>
  <div class="hero-stats">
    <div class="hero-stat">
      <span class="hero-stat-value">290+</span>
      <span class="hero-stat-label">Episodes</span>
    </div>
    <div class="hero-stat">
      <span class="hero-stat-value">25</span>
      <span class="hero-stat-label">Channels</span>
    </div>
    <div class="hero-stat">
      <span class="hero-stat-value">13.8K</span>
      <span class="hero-stat-label">Chunks</span>
    </div>
    <div class="hero-stat">
      <span class="hero-stat-value">8.6K</span>
      <span class="hero-stat-label">Claims</span>
    </div>
    <div class="hero-stat">
      <span class="hero-stat-value">9</span>
      <span class="hero-stat-label">AI Agents</span>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Chat history
# ─────────────────────────────────────────────────────────────────────────────

for msg in st.session_state.messages:
    render_message(msg)

# Clear button
if st.session_state.messages:
    st.markdown('<div class="clear-btn-wrap">', unsafe_allow_html=True)
    if st.button("✕  Clear conversation", key="clear"):
        st.session_state.messages = []
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Chat input
# ─────────────────────────────────────────────────────────────────────────────

user_input = st.chat_input("Ask anything about podcasts")

if user_input:
    # ── Guardrails ────────────────────────────────────────────────────────────
    guard = validate_query(user_input)
    if not guard.passed:
        st.session_state.messages.append({"role": "user", "content": user_input, "meta": {}})
        render_message({"role": "user", "content": user_input})
        blocked = {
            "role": "assistant",
            "content": guard.message,
            "meta": {},
        }
        st.session_state.messages.append(blocked)
        render_message(blocked)
        st.stop()

    st.session_state.messages.append({"role": "user", "content": user_input, "meta": {}})
    render_message({"role": "user", "content": user_input})

    # Thinking indicator
    ph = st.empty()
    ph.markdown("""
<div class="chat-wrap">
  <div class="thinking-row">
    <div class="msg-avatar">🎙️</div>
    <div class="thinking-dots">
      <div class="dot"></div><div class="dot"></div><div class="dot"></div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    try:
        from langgraph_agents.graph import run as agent_run
        result = agent_run(user_input)
        ph.empty()

        qt  = result.get("query_type", "SEARCH")
        ans = result.get("summary", "No answer found. Try rephrasing your question.")
        msg = {
            "role": "assistant",
            "content": ans,
            "meta": {
                "query_type":     qt,
                "search_results": result.get("search_results", []),
                "graph_results":  result.get("graph_results", []),
            },
        }
        st.session_state.messages.append(msg)
        render_message(msg, is_new=True)

        # ── GPT-4o validator (runs after llama answer is visible) ─────────────
        if qt in AGENTS_TO_VALIDATE:
            gpt_placeholder = st.empty()
            gpt_placeholder.markdown(
                '<div style="font-size:.78rem;color:#6B7280;padding:.4rem 0 0 3.5rem;">'
                '🤖 Verifying with GPT-4o...</div>',
                unsafe_allow_html=True,
            )
            validation = validate_response(
                query        = user_input,
                answer       = ans,
                search_results = result.get("search_results", []),
                query_type   = qt,
            )
            if validation and validation.get("verdict") != "ERROR":
                conf    = validation["confidence"]
                verdict = validation["verdict"]
                flag    = validation.get("flag")

                color = (
                    "#0B8A7C" if conf and conf >= 85 else
                    "#2563EB" if conf and conf >= 65 else
                    "#D97706" if conf and conf >= 40 else
                    "#DC2626"
                )
                icon = (
                    "✅" if verdict == "VERIFIED" else
                    "🔵" if verdict == "MOSTLY_ACCURATE" else
                    "⚠️" if verdict == "PARTIALLY_ACCURATE" else
                    "❌"
                )
                label = verdict.replace("_", " ").title()
                flag_html = (
                    f'<span style="color:#6B7280;font-size:.72rem;margin-left:.5rem;">'
                    f'· {esc(flag)}</span>'
                ) if flag else ""

                gpt_placeholder.markdown(
                    f'<div style="display:flex;align-items:center;gap:.4rem;'
                    f'padding:.4rem 0 0 3.5rem;font-size:.78rem;">'
                    f'{icon} <span style="font-weight:600;color:{color};">{label}</span>'
                    f'<span style="color:{color};font-family:\'JetBrains Mono\',monospace;'
                    f'font-size:.72rem;background:{color}18;padding:.1rem .4rem;'
                    f'border-radius:.3rem;border:1px solid {color}44;">{conf}%</span>'
                    f'<span style="color:#9CA3AF;font-size:.7rem;">GPT-4o verified</span>'
                    f'{flag_html}</div>',
                    unsafe_allow_html=True,
                )
            else:
                gpt_placeholder.empty()

    except Exception as e:
        ph.empty()
        err = {
            "role": "assistant",
            "content": f"Something went wrong: `{str(e)[:200]}`",
            "meta": {},
        }
        st.session_state.messages.append(err)
        render_message(err)
