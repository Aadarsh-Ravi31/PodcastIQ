"""
PodcastIQ — claim_extractor.py
Tier 2: LLM-based claim extraction + per-claim speaker inference.

For every chunk in CUR_CHUNKS (not yet processed), calls Snowflake Cortex
COMPLETE to extract factual claims, predictions, and strong opinions.
Incorporates episode participant context from SEM_EPISODE_PARTICIPANTS so
the LLM can infer which speaker (host vs. guest) made each claim.

Output: INSERT into SEMANTIC.SEM_CLAIMS
Schema: claim_id, video_id, chunk_id, channel_name, episode_title,
        publish_date, speaker_name, speaker_role, attribution_confidence,
        claim_text, claim_type, topic, sentiment, extraction_model
"""

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass, field

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from dotenv import load_dotenv
import snowflake.connector

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

BATCH_SIZE   = 20      # chunks per batch (controls credit burn rate)
MODEL        = "llama3.1-70b"
MAX_CHUNKS   = None    # set to int to limit for testing (None = all)


# ─────────────────────────────────────────────
# Prompt
# ─────────────────────────────────────────────

CLAIM_PROMPT = """You are an AI assistant extracting claims from podcast transcripts.

Episode: "{episode_title}"
Channel: {channel_name}
Published: {publish_date}
Participants:
  Host(s) : {hosts}
  Guest(s) : {guests}

Transcript excerpt (starting at {chunk_start_sec}s):
\"\"\"
{chunk_text}
\"\"\"

Extract every significant factual claim, prediction, statistic, or strong opinion from this excerpt.

For each claim return a JSON object with these exact keys:
  "claim_text"             : the claim as a concise declarative sentence (max 200 chars)
  "speaker_name"           : full name of who made this claim (use participant list above), or "Unknown"
  "speaker_role"           : "HOST" | "GUEST" | "UNKNOWN"
  "attribution_confidence" : "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN"
  "claim_type"             : "VERIFIABLE_FACT" | "PREDICTION" | "OPINION" | "STATISTICAL"
  "topic"                  : single main topic keyword (e.g., "AI", "nutrition", "startups", "longevity")
  "sentiment"              : "positive" | "negative" | "neutral"

Attribution guidance:
- HIGH   : speaker explicitly says "I" or is clearly speaking in first person
- MEDIUM : speaker name mentioned nearby in the text or inferred from Q&A pattern
- LOW    : general discussion — unclear who is speaking
- UNKNOWN: no way to infer speaker

Return ONLY a valid JSON array of claim objects. No explanation, no markdown, no code fences.
If no significant claims are found, return an empty array: []"""


# ─────────────────────────────────────────────
# Data helpers
# ─────────────────────────────────────────────

@dataclass
class Participant:
    name: str
    role: str   # HOST | GUEST


@dataclass
class ChunkContext:
    chunk_id:      str
    video_id:      str
    channel_name:  str
    episode_title: str
    publish_date:  str
    chunk_start:   int
    chunk_text:    str
    youtube_url:   str = ""
    participants:  list[Participant] = field(default_factory=list)


def _get_connection():
    key_path = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
    with open(key_path, "rb") as f:
        pk = serialization.load_pem_private_key(
            f.read(),
            password=os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE", "").encode() or None,
            backend=default_backend(),
        )
    pk_bytes = pk.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        private_key=pk_bytes,
        warehouse="PODCASTIQ_WH",
        database="PODCASTIQ",
        schema="SEMANTIC",
        role="TRAINING_ROLE",
        session_parameters={"CLIENT_SESSION_KEEP_ALIVE": True},
    )


def _fetch_unprocessed_chunks(cur, limit=None) -> list[ChunkContext]:
    """Fetch chunks not yet in SEM_CLAIMS, with participant context joined in."""
    limit_clause = f"LIMIT {limit}" if limit else ""
    cur.execute(f"""
        SELECT
            c.CHUNK_ID,
            c.VIDEO_ID,
            c.CHANNEL_NAME,
            c.EPISODE_TITLE,
            c.PUBLISH_DATE,
            c.CHUNK_START_SEC,
            c.CHUNK_TEXT,
            c.YOUTUBE_URL
        FROM CURATED.CUR_CHUNKS c
        WHERE c.CHUNK_ID NOT IN (
            SELECT DISTINCT CHUNK_ID FROM SEMANTIC.SEM_CLAIMS
        )
        ORDER BY c.VIDEO_ID, c.CHUNK_START_SEC
        {limit_clause}
    """)
    rows = cur.fetchall()
    log.info(f"Fetched {len(rows)} unprocessed chunks")

    # Build dict: video_id → list[Participant]
    cur.execute("""
        SELECT DISTINCT VIDEO_ID, PARTICIPANT_NAME, PARTICIPANT_ROLE
        FROM SEMANTIC.SEM_EPISODE_PARTICIPANTS
        WHERE CONFIDENCE IN ('HIGH', 'MEDIUM')
    """)
    participants_map: dict[str, list[Participant]] = {}
    for vid, name, role in cur.fetchall():
        participants_map.setdefault(vid, []).append(Participant(name=name, role=role))

    chunks = []
    for chunk_id, video_id, channel, title, pub_date, start_sec, text, yt_url in rows:
        chunks.append(ChunkContext(
            chunk_id      = chunk_id,
            video_id      = video_id,
            channel_name  = channel,
            episode_title = title,
            publish_date  = str(pub_date)[:10] if pub_date else "Unknown",
            chunk_start   = int(start_sec or 0),
            chunk_text    = text or "",
            youtube_url   = yt_url or "",
            participants  = participants_map.get(video_id, []),
        ))
    return chunks


# ─────────────────────────────────────────────
# LLM extraction
# ─────────────────────────────────────────────

def _build_prompt(ctx: ChunkContext) -> str:
    hosts  = [p.name for p in ctx.participants if p.role == "HOST"] or ["Unknown"]
    guests = [p.name for p in ctx.participants if p.role == "GUEST"] or ["Unknown"]
    return CLAIM_PROMPT.format(
        episode_title  = ctx.episode_title,
        channel_name   = ctx.channel_name,
        publish_date   = ctx.publish_date,
        hosts          = ", ".join(hosts),
        guests         = ", ".join(guests),
        chunk_start_sec= ctx.chunk_start,
        chunk_text     = ctx.chunk_text[:2000],   # safety cap on prompt size
    )


def _parse_claims(raw_response: str) -> list[dict]:
    """Parse LLM JSON output — tolerates markdown fences and minor formatting issues."""
    if not raw_response:
        return []
    # Strip markdown code fences if present
    text = re.sub(r"```(?:json)?", "", raw_response).strip()
    # Find the JSON array
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return []


VALID_TYPES       = {"VERIFIABLE_FACT", "PREDICTION", "OPINION", "STATISTICAL"}
VALID_ROLES       = {"HOST", "GUEST", "UNKNOWN"}
VALID_CONF        = {"HIGH", "MEDIUM", "LOW", "UNKNOWN"}
VALID_SENTIMENTS  = {"positive", "negative", "neutral"}


def _sanitize_claim(raw: dict, ctx: ChunkContext) -> dict | None:
    """Validate and normalize a single claim dict from LLM output."""
    text = str(raw.get("claim_text", "")).strip()
    if len(text) < 10:
        return None

    claim_type = str(raw.get("claim_type", "OPINION")).upper()
    if claim_type not in VALID_TYPES:
        claim_type = "OPINION"

    role = str(raw.get("speaker_role", "UNKNOWN")).upper()
    if role not in VALID_ROLES:
        role = "UNKNOWN"

    conf = str(raw.get("attribution_confidence", "UNKNOWN")).upper()
    if conf not in VALID_CONF:
        conf = "UNKNOWN"

    sentiment = str(raw.get("sentiment", "neutral")).lower()
    if sentiment not in VALID_SENTIMENTS:
        sentiment = "neutral"

    speaker_name = str(raw.get("speaker_name", "Unknown")).strip()
    if not speaker_name or speaker_name.lower() == "unknown":
        speaker_name = "Unknown"
        role = "UNKNOWN"
        conf = "UNKNOWN"

    topic = str(raw.get("topic", "General")).strip()[:100]

    return {
        "claim_id"              : str(uuid.uuid4()),
        "chunk_id"              : ctx.chunk_id,
        "video_id"              : ctx.video_id,
        "claim_text"            : text[:1000],
        "topic"                 : topic,
        "claim_type"            : claim_type,
        "sentiment"             : sentiment,
        "speaker"               : speaker_name[:200],
        "speaker_role"          : role,
        "attribution_confidence": conf,
        "attribution_source"    : "LLM_INFERRED",
        "claim_date"            : ctx.publish_date,
        "channel_name"          : ctx.channel_name,
        "youtube_url"           : ctx.youtube_url,
        "extraction_model"      : MODEL,
    }


def _extract_claims_for_chunk(cur, ctx: ChunkContext) -> list[dict]:
    prompt = _build_prompt(ctx)
    cur.execute(
        f"SELECT SNOWFLAKE.CORTEX.COMPLETE('{MODEL}', %s)",
        (prompt,),
    )
    row = cur.fetchone()
    raw_text = (row[0] or "") if row else ""
    raw_claims = _parse_claims(raw_text)

    sanitized = []
    for rc in raw_claims:
        claim = _sanitize_claim(rc, ctx)
        if claim:
            sanitized.append(claim)
    return sanitized


# ─────────────────────────────────────────────
# INSERT helpers
# ─────────────────────────────────────────────

INSERT_SQL = """
INSERT INTO SEMANTIC.SEM_CLAIMS (
    CLAIM_ID, CHUNK_ID, VIDEO_ID,
    CLAIM_TEXT, TOPIC, CLAIM_TYPE, SENTIMENT,
    SPEAKER, SPEAKER_ROLE, ATTRIBUTION_CONFIDENCE, ATTRIBUTION_SOURCE,
    CLAIM_DATE, CHANNEL_NAME, YOUTUBE_URL, EXTRACTION_MODEL
) VALUES (
    %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s,
    %s, %s, %s, %s
)
"""


def _insert_claims(cur, conn, claims: list[dict]):
    if not claims:
        return
    rows = [
        (
            c["claim_id"], c["chunk_id"], c["video_id"],
            c["claim_text"], c["topic"], c["claim_type"], c["sentiment"],
            c["speaker"], c["speaker_role"], c["attribution_confidence"], c["attribution_source"],
            c["claim_date"], c["channel_name"], c["youtube_url"], c["extraction_model"],
        )
        for c in claims
    ]
    cur.executemany(INSERT_SQL, rows)
    conn.commit()


# ─────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────

def run(max_chunks: int = None, batch_size: int = BATCH_SIZE):
    conn = _get_connection()
    cur  = conn.cursor()

    chunks = _fetch_unprocessed_chunks(cur, limit=max_chunks)
    total  = len(chunks)

    if not total:
        log.info("Nothing to do — all chunks already have claims extracted.")
        cur.close()
        conn.close()
        return

    stats = {
        "chunks_processed": 0,
        "claims_extracted": 0,
        "chunks_empty"    : 0,
        "errors"          : 0,
    }

    for i in range(0, total, batch_size):
        batch = chunks[i : i + batch_size]
        batch_claims = []

        for ctx in batch:
            try:
                claims = _extract_claims_for_chunk(cur, ctx)
                if claims:
                    batch_claims.extend(claims)
                    stats["claims_extracted"] += len(claims)
                else:
                    stats["chunks_empty"] += 1
                stats["chunks_processed"] += 1
            except Exception as e:
                log.warning(f"  Error on chunk {ctx.chunk_id}: {e}")
                stats["errors"] += 1

        # Batch insert after each group
        if batch_claims:
            _insert_claims(cur, conn, batch_claims)

        pct = round((i + len(batch)) / total * 100, 1)
        log.info(
            f"Batch {i // batch_size + 1} done | "
            f"{i + len(batch)}/{total} chunks ({pct}%) | "
            f"+{len(batch_claims)} claims | "
            f"total so far: {stats['claims_extracted']}"
        )

    log.info(
        f"\nExtraction complete:\n"
        f"  Chunks processed : {stats['chunks_processed']}\n"
        f"  Claims extracted : {stats['claims_extracted']}\n"
        f"  Chunks with 0    : {stats['chunks_empty']}\n"
        f"  Errors           : {stats['errors']}\n"
        f"  Avg claims/chunk : {stats['claims_extracted'] / max(stats['chunks_processed'], 1):.1f}"
    )

    # Final coverage report
    cur.execute("""
        SELECT
            COUNT(*)                                          AS total_claims,
            COUNT(DISTINCT VIDEO_ID)                          AS episodes_covered,
            COUNT(DISTINCT CHUNK_ID)                          AS chunks_covered,
            COUNT(CASE WHEN CLAIM_TYPE = 'VERIFIABLE_FACT'    THEN 1 END) AS verifiable,
            COUNT(CASE WHEN CLAIM_TYPE = 'PREDICTION'         THEN 1 END) AS predictions,
            COUNT(CASE WHEN CLAIM_TYPE = 'OPINION'            THEN 1 END) AS opinions,
            COUNT(CASE WHEN CLAIM_TYPE = 'STATISTICAL'        THEN 1 END) AS statistical,
            COUNT(CASE WHEN ATTRIBUTION_CONFIDENCE = 'HIGH'   THEN 1 END) AS high_conf,
            COUNT(CASE WHEN ATTRIBUTION_CONFIDENCE = 'MEDIUM' THEN 1 END) AS med_conf,
            COUNT(CASE WHEN SPEAKER != 'Unknown'              THEN 1 END) AS attributed_claims
        FROM SEMANTIC.SEM_CLAIMS
    """)
    row = cur.fetchone()
    total_claims, episodes, chunks_cov, vf, pred, op, stat, hi, med, attr = row
    log.info(
        f"\nSEM_CLAIMS summary:\n"
        f"  Total claims     : {total_claims}\n"
        f"  Episodes covered : {episodes}\n"
        f"  Chunks covered   : {chunks_cov}\n"
        f"  Types: VERIFIABLE={vf} | PREDICTION={pred} | OPINION={op} | STATISTICAL={stat}\n"
        f"  Confidence: HIGH={hi} | MEDIUM={med}\n"
        f"  Speaker attributed : {attr} ({round(attr*100/max(total_claims,1),1)}%)"
    )

    cur.close()
    conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract claims from podcast transcript chunks")
    parser.add_argument("--max-chunks",  type=int, default=None, help="Limit chunks processed (for testing)")
    parser.add_argument("--batch-size",  type=int, default=BATCH_SIZE, help=f"Chunks per batch (default {BATCH_SIZE})")
    args = parser.parse_args()

    run(max_chunks=args.max_chunks, batch_size=args.batch_size)
