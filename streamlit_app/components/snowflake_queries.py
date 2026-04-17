"""
Cached Snowflake queries for Streamlit pages.
All functions use @st.cache_data to avoid re-querying on every rerender.
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from langgraph_agents.snowflake_client import execute


# ── Channels ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def get_channels() -> list[dict]:
    return execute("""
        SELECT
            CHANNEL_NAME,
            GENRE,
            COUNT(DISTINCT VIDEO_ID) AS episode_count,
            MIN(PUBLISH_DATE)        AS earliest,
            MAX(PUBLISH_DATE)        AS latest
        FROM CURATED.CUR_CHUNKS
        WHERE CHANNEL_NAME IS NOT NULL
        GROUP BY CHANNEL_NAME, GENRE
        ORDER BY episode_count DESC
    """)


@st.cache_data(ttl=3600, show_spinner=False)
def get_channel_names() -> list[str]:
    rows = execute("""
        SELECT DISTINCT CHANNEL_NAME
        FROM CURATED.CUR_CHUNKS
        WHERE CHANNEL_NAME IS NOT NULL
        ORDER BY CHANNEL_NAME
    """)
    return [r["CHANNEL_NAME"] for r in rows]


# ── Channel credibility stats ──────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def get_channel_verification_stats() -> list[dict]:
    return execute("""
        SELECT
            CHANNEL_NAME,
            COUNT(*)                                                        AS total_claims,
            SUM(CASE WHEN VERIFICATION_STATUS = 'VERIFIED'   THEN 1 ELSE 0 END) AS verified,
            SUM(CASE WHEN VERIFICATION_STATUS = 'FALSE'      THEN 1 ELSE 0 END) AS false_claims,
            SUM(CASE WHEN VERIFICATION_STATUS = 'OUTDATED'   THEN 1 ELSE 0 END) AS outdated,
            SUM(CASE WHEN VERIFICATION_STATUS = 'DISPUTED'   THEN 1 ELSE 0 END) AS disputed,
            SUM(CASE WHEN VERIFICATION_STATUS = 'UNVERIFIED' THEN 1 ELSE 0 END) AS unverified,
            SUM(CASE WHEN VERIFICATION_STATUS = 'PENDING'    THEN 1 ELSE 0 END) AS pending
        FROM SEMANTIC.SEM_CLAIMS
        WHERE CHANNEL_NAME IS NOT NULL
        GROUP BY CHANNEL_NAME
        ORDER BY total_claims DESC
    """)


@st.cache_data(ttl=3600, show_spinner=False)
def get_channel_top_topics(channel_name: str, limit: int = 10) -> list[dict]:
    return execute("""
        SELECT
            TOPIC,
            COUNT(*) AS claim_count
        FROM SEMANTIC.SEM_CLAIMS
        WHERE LOWER(CHANNEL_NAME) = LOWER(%s)
          AND TOPIC IS NOT NULL AND TRIM(TOPIC) != ''
        GROUP BY TOPIC
        ORDER BY claim_count DESC
        LIMIT %s
    """, (channel_name, limit))


@st.cache_data(ttl=3600, show_spinner=False)
def get_channel_guests(channel_name: str) -> list[dict]:
    return execute("""
        SELECT
            PARTICIPANT_NAME,
            PARTICIPANT_ROLE,
            COUNT(DISTINCT VIDEO_ID) AS episode_count
        FROM SEMANTIC.SEM_EPISODE_PARTICIPANTS
        WHERE LOWER(CHANNEL_NAME) = LOWER(%s)
          AND PARTICIPANT_ROLE = 'GUEST'
        GROUP BY PARTICIPANT_NAME, PARTICIPANT_ROLE
        ORDER BY episode_count DESC
        LIMIT 15
    """, (channel_name,))


# ── Episodes ──────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def search_episodes(query: str) -> list[dict]:
    kw = f"%{query.lower()}%"
    # Search by title first
    rows = execute("""
        SELECT DISTINCT
            VIDEO_ID,
            EPISODE_TITLE,
            CHANNEL_NAME,
            PUBLISH_DATE,
            YOUTUBE_URL
        FROM CURATED.CUR_CHUNKS
        WHERE LOWER(EPISODE_TITLE) LIKE %s
          AND EPISODE_TITLE IS NOT NULL
        ORDER BY PUBLISH_DATE DESC
        LIMIT 20
    """, (kw,))

    # Also search by participant name and merge
    participant_rows = execute("""
        SELECT DISTINCT
            c.VIDEO_ID,
            c.EPISODE_TITLE,
            c.CHANNEL_NAME,
            c.PUBLISH_DATE,
            c.YOUTUBE_URL
        FROM SEMANTIC.SEM_EPISODE_PARTICIPANTS p
        JOIN CURATED.CUR_CHUNKS c ON p.VIDEO_ID = c.VIDEO_ID
        WHERE LOWER(p.PARTICIPANT_NAME) LIKE %s
          AND c.EPISODE_TITLE IS NOT NULL
        ORDER BY c.PUBLISH_DATE DESC
        LIMIT 20
    """, (kw,))

    # Merge, deduplicate by VIDEO_ID
    seen_ids = {r["VIDEO_ID"] for r in rows if r.get("VIDEO_ID")}
    for r in participant_rows:
        if r.get("VIDEO_ID") and r["VIDEO_ID"] not in seen_ids:
            rows.append(r)
            seen_ids.add(r["VIDEO_ID"])

    return sorted(rows, key=lambda x: str(x.get("PUBLISH_DATE", "")), reverse=True)


@st.cache_data(ttl=3600, show_spinner=False)
def get_episode_summary(video_id: str) -> dict | None:
    rows = execute("""
        SELECT VIDEO_ID, EPISODE_TITLE, CHANNEL_NAME, SUMMARY_TEXT, PUBLISH_DATE
        FROM SEMANTIC.SEM_EPISODE_SUMMARIES
        WHERE VIDEO_ID = %s
        LIMIT 1
    """, (video_id,))
    return rows[0] if rows else None


@st.cache_data(ttl=3600, show_spinner=False)
def get_episode_participants(video_id: str) -> list[dict]:
    return execute("""
        SELECT PARTICIPANT_NAME, PARTICIPANT_ROLE, CONFIDENCE, EXTRACTION_METHOD
        FROM SEMANTIC.SEM_EPISODE_PARTICIPANTS
        WHERE VIDEO_ID = %s
        ORDER BY PARTICIPANT_ROLE, PARTICIPANT_NAME
    """, (video_id,))


@st.cache_data(ttl=3600, show_spinner=False)
def get_episode_claims(video_id: str, limit: int = 50) -> list[dict]:
    return execute("""
        SELECT
            CLAIM_TEXT,
            SPEAKER,
            CLAIM_TYPE,
            TOPIC,
            VERIFICATION_STATUS,
            YOUTUBE_URL,
            CLAIM_DATE
        FROM SEMANTIC.SEM_CLAIMS
        WHERE VIDEO_ID = %s
          AND CLAIM_TEXT IS NOT NULL
        ORDER BY CLAIM_DATE, CLAIM_TYPE
        LIMIT %s
    """, (video_id, limit))


@st.cache_data(ttl=3600, show_spinner=False)
def get_episodes_by_channel(channel_name: str) -> list[dict]:
    return execute("""
        SELECT DISTINCT
            VIDEO_ID,
            EPISODE_TITLE,
            PUBLISH_DATE,
            YOUTUBE_URL,
            COUNT(*) OVER (PARTITION BY VIDEO_ID) AS chunk_count
        FROM CURATED.CUR_CHUNKS
        WHERE LOWER(CHANNEL_NAME) = LOWER(%s)
          AND EPISODE_TITLE IS NOT NULL
        ORDER BY PUBLISH_DATE DESC
        LIMIT 50
    """, (channel_name,))


# ── Claim Timeline ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def get_claim_evolution(topic_query: str, limit: int = 30) -> list[dict]:
    kw = f"%{topic_query.lower()}%"
    return execute("""
        SELECT
            ce.EVOLUTION_ID,
            ce.DRIFT_TYPE,
            ce.TOPIC,
            ce.ORIGINAL_DATE,
            ce.EVOLVED_DATE,
            ce.TIME_DELTA_DAYS,
            ce.ORIGINAL_SPEAKER,
            ce.EVOLVED_SPEAKER,
            ce.SAME_SPEAKER,
            ce.CHANNEL_ORIGINAL,
            ce.CHANNEL_EVOLVED,
            ce.ANALYSIS,
            c1.CLAIM_TEXT  AS original_text,
            c1.YOUTUBE_URL AS original_url,
            c2.CLAIM_TEXT  AS evolved_text,
            c2.YOUTUBE_URL AS evolved_url
        FROM SEMANTIC.SEM_CLAIM_EVOLUTION ce
        JOIN SEMANTIC.SEM_CLAIMS c1 ON ce.ORIGINAL_CLAIM_ID = c1.CLAIM_ID
        JOIN SEMANTIC.SEM_CLAIMS c2 ON ce.EVOLVED_CLAIM_ID  = c2.CLAIM_ID
        WHERE LOWER(ce.TOPIC) LIKE %s
        ORDER BY ce.TIME_DELTA_DAYS DESC
        LIMIT %s
    """, (kw, limit))


@st.cache_data(ttl=3600, show_spinner=False)
def get_top_evolved_topics(limit: int = 20) -> list[dict]:
    return execute("""
        SELECT
            TOPIC,
            COUNT(*) AS evolution_count,
            SUM(CASE WHEN DRIFT_TYPE = 'CONTRADICTED' THEN 1 ELSE 0 END) AS contradictions,
            SUM(CASE WHEN DRIFT_TYPE = 'CONFIRMED'    THEN 1 ELSE 0 END) AS confirmations
        FROM SEMANTIC.SEM_CLAIM_EVOLUTION
        WHERE TOPIC IS NOT NULL AND TRIM(TOPIC) != ''
        GROUP BY TOPIC
        ORDER BY evolution_count DESC
        LIMIT %s
    """, (limit,))


# ── Global stats (for sidebar / home) ─────────────────────────────────────────

@st.cache_data(ttl=7200, show_spinner=False)
def get_global_stats() -> dict:
    rows = execute("""
        SELECT
            (SELECT COUNT(DISTINCT VIDEO_ID) FROM CURATED.CUR_CHUNKS)        AS episodes,
            (SELECT COUNT(*)                 FROM CURATED.CUR_CHUNKS)        AS chunks,
            (SELECT COUNT(*)                 FROM SEMANTIC.SEM_CLAIMS)       AS claims,
            (SELECT COUNT(*)                 FROM SEMANTIC.SEM_CLAIM_EVOLUTION) AS evolutions,
            (SELECT COUNT(DISTINCT CHANNEL_NAME) FROM CURATED.CUR_CHUNKS)   AS channels
    """)
    if rows:
        r = rows[0]
        return {
            "episodes":   r.get("EPISODES", 0),
            "chunks":     r.get("CHUNKS", 0),
            "claims":     r.get("CLAIMS", 0),
            "evolutions": r.get("EVOLUTIONS", 0),
            "channels":   r.get("CHANNELS", 0),
        }
    return {}
