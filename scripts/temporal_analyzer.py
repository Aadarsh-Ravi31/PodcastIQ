"""
Temporal Analysis Pipeline for PodcastIQ.

Finds claim pairs on the same topic across different time periods and
classifies how the discourse has evolved over time.

Algorithm:
  1. Find topics where claims span > min_days apart
  2. For each topic: pair earliest claim with latest claim
  3. Classify evolution via Cortex LLM (REVISED/ESCALATED/SOFTENED/CONTRADICTED/CONFIRMED)
  4. Insert into SEM_CLAIM_EVOLUTION (idempotent — skips existing pairs)

Usage:
    python scripts/temporal_analyzer.py
    python scripts/temporal_analyzer.py --max-topics 50
    python scripts/temporal_analyzer.py --min-days 60
"""

import os
import json
import hashlib
import logging
import argparse
from dataclasses import dataclass
from datetime import date

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

VALID_DRIFT_TYPES = {"REVISED", "ESCALATED", "SOFTENED", "CONTRADICTED", "CONFIRMED"}

EVOLUTION_PROMPT = """You are analyzing how a topic has evolved across podcast discussions over time.

Compare these two claims on the same topic:

ORIGINAL claim ({original_date}) by {original_speaker} on {original_channel}:
"{original_text}"

LATER claim ({evolved_date}) by {evolved_speaker} on {evolved_channel}:
"{evolved_text}"

Classify the evolution:
- REVISED      : Speaker updated or corrected their prior position
- ESCALATED    : Claim became stronger, more extreme, or more confident
- SOFTENED     : Claim became weaker, more hedged, or more cautious
- CONTRADICTED : The later claim directly contradicts the original
- CONFIRMED    : The later claim independently validates the original

Respond with ONLY valid JSON (no markdown, no extra text):
{{"drift_type": "REVISED|ESCALATED|SOFTENED|CONTRADICTED|CONFIRMED", "analysis": "1-2 sentence explanation"}}"""

INSERT_SQL = """
INSERT INTO SEMANTIC.SEM_CLAIM_EVOLUTION (
    EVOLUTION_ID, ORIGINAL_CLAIM_ID, EVOLVED_CLAIM_ID,
    DRIFT_TYPE, SAME_SPEAKER, TIME_DELTA_DAYS, SIMILARITY_SCORE, ANALYSIS,
    ORIGINAL_SPEAKER, EVOLVED_SPEAKER, TOPIC,
    ORIGINAL_DATE, EVOLVED_DATE, CHANNEL_ORIGINAL, CHANNEL_EVOLVED
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


@dataclass
class ClaimRecord:
    claim_id: str
    claim_text: str
    topic: str
    speaker: str
    channel_name: str
    claim_date: date


def _connect() -> snowflake.connector.SnowflakeConnection:
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


def _evolution_id(original_id: str, evolved_id: str) -> str:
    return hashlib.sha256(f"{original_id}{evolved_id}".encode()).hexdigest()


def _fetch_pairs(cur, min_days: int, max_topics: int) -> list[tuple[ClaimRecord, ClaimRecord]]:
    """Find (early, late) claim pairs per topic with temporal spread >= min_days."""
    # Load already-processed pairs to skip
    cur.execute("SELECT EVOLUTION_ID FROM SEMANTIC.SEM_CLAIM_EVOLUTION")
    existing_ids = {row[0] for row in cur.fetchall()}
    logger.info(f"Existing evolutions in table: {len(existing_ids)}")

    # Find topics with sufficient temporal spread, attributed claims only
    cur.execute(f"""
        SELECT
            TOPIC,
            DATEDIFF('day', MIN(CLAIM_DATE), MAX(CLAIM_DATE)) AS date_span,
            COUNT(*) AS claim_count
        FROM SEMANTIC.SEM_CLAIMS
        WHERE TOPIC IS NOT NULL
          AND TRIM(TOPIC) != ''
          AND CLAIM_DATE IS NOT NULL
          AND LEN(CLAIM_TEXT) > 50
          AND UPPER(TRIM(COALESCE(SPEAKER, 'UNKNOWN'))) != 'UNKNOWN'
        GROUP BY TOPIC
        HAVING date_span >= {min_days}
          AND claim_count >= 2
        ORDER BY claim_count DESC
        LIMIT {max_topics * 2}
    """)
    topics = cur.fetchall()
    logger.info(f"Topics with >={min_days} day temporal spread: {len(topics)}")

    pairs = []
    for (topic, date_span, _) in topics:
        if len(pairs) >= max_topics:
            break

        # Earliest claim on this topic
        cur.execute("""
            SELECT CLAIM_ID, CLAIM_TEXT, TOPIC, SPEAKER, CHANNEL_NAME, CLAIM_DATE
            FROM SEMANTIC.SEM_CLAIMS
            WHERE TOPIC = %s
              AND CLAIM_DATE IS NOT NULL
              AND LEN(CLAIM_TEXT) > 50
              AND UPPER(TRIM(COALESCE(SPEAKER, 'UNKNOWN'))) != 'UNKNOWN'
            ORDER BY CLAIM_DATE ASC
            LIMIT 1
        """, (topic,))
        early_row = cur.fetchone()

        # Latest claim on this topic
        cur.execute("""
            SELECT CLAIM_ID, CLAIM_TEXT, TOPIC, SPEAKER, CHANNEL_NAME, CLAIM_DATE
            FROM SEMANTIC.SEM_CLAIMS
            WHERE TOPIC = %s
              AND CLAIM_DATE IS NOT NULL
              AND LEN(CLAIM_TEXT) > 50
              AND UPPER(TRIM(COALESCE(SPEAKER, 'UNKNOWN'))) != 'UNKNOWN'
            ORDER BY CLAIM_DATE DESC
            LIMIT 1
        """, (topic,))
        late_row = cur.fetchone()

        if not early_row or not late_row:
            continue
        if early_row[0] == late_row[0]:
            continue  # Same claim, no evolution possible

        eid = _evolution_id(early_row[0], late_row[0])
        if eid in existing_ids:
            continue  # Already processed

        pairs.append((ClaimRecord(*early_row), ClaimRecord(*late_row)))

    logger.info(f"New pairs to analyze: {len(pairs)}")
    return pairs


def _classify(cur, early: ClaimRecord, late: ClaimRecord) -> dict | None:
    """Call Cortex LLM to classify the evolution between two claims."""
    prompt = EVOLUTION_PROMPT.format(
        original_date=str(early.claim_date),
        original_speaker=early.speaker,
        original_channel=early.channel_name,
        original_text=early.claim_text[:400],
        evolved_date=str(late.claim_date),
        evolved_speaker=late.speaker,
        evolved_channel=late.channel_name,
        evolved_text=late.claim_text[:400],
    )
    cur.execute(
        "SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', %s)",
        (prompt,),
    )
    row = cur.fetchone()
    if not row or not row[0]:
        return None

    raw = row[0].strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()

    try:
        result = json.loads(raw)
        drift_type = result.get("drift_type", "").upper().strip()
        analysis = result.get("analysis", "").strip()
        if drift_type not in VALID_DRIFT_TYPES:
            drift_type = "CONFIRMED"  # safe fallback
        return {"drift_type": drift_type, "analysis": analysis[:1000]}
    except json.JSONDecodeError:
        logger.warning(f"JSON parse failed: {raw[:100]}")
        return None


def run(max_topics: int = 300, min_days: int = 30):
    logger.info("Connecting to Snowflake...")
    conn = _connect()
    cur = conn.cursor()

    pairs = _fetch_pairs(cur, min_days=min_days, max_topics=max_topics)
    if not pairs:
        logger.info("No new pairs to process — done.")
        return

    inserted = skipped = 0
    total = len(pairs)

    for i, (early, late) in enumerate(pairs, 1):
        time_delta = (late.claim_date - early.claim_date).days
        same_speaker = (
            early.speaker.strip().lower() == late.speaker.strip().lower()
        ) if early.speaker and late.speaker else False

        result = _classify(cur, early, late)
        if not result:
            skipped += 1
            continue

        evolution_id = _evolution_id(early.claim_id, late.claim_id)
        try:
            cur.execute(INSERT_SQL, (
                evolution_id,
                early.claim_id,
                late.claim_id,
                result["drift_type"],
                same_speaker,
                time_delta,
                None,   # similarity_score — topic-based matching, not embedding-based
                result["analysis"],
                early.speaker,
                late.speaker,
                early.topic,
                early.claim_date,
                late.claim_date,
                early.channel_name,
                late.channel_name,
            ))
            conn.commit()
            inserted += 1
        except Exception as e:
            logger.warning(f"Insert failed for {evolution_id}: {e}")
            skipped += 1
            continue

        if i % 10 == 0 or i == total:
            logger.info(
                f"Progress: {i}/{total} | "
                f"inserted: {inserted} | skipped: {skipped} | "
                f"last drift: {result['drift_type']}"
            )

    # Final summary
    cur.execute("""
        SELECT
            COUNT(*) AS total,
            COUNT(DISTINCT TOPIC) AS topics,
            SUM(CASE WHEN DRIFT_TYPE = 'CONTRADICTED' THEN 1 ELSE 0 END) AS contradicted,
            SUM(CASE WHEN DRIFT_TYPE = 'REVISED'      THEN 1 ELSE 0 END) AS revised,
            SUM(CASE WHEN DRIFT_TYPE = 'CONFIRMED'    THEN 1 ELSE 0 END) AS confirmed,
            SUM(CASE WHEN DRIFT_TYPE = 'ESCALATED'    THEN 1 ELSE 0 END) AS escalated,
            SUM(CASE WHEN DRIFT_TYPE = 'SOFTENED'     THEN 1 ELSE 0 END) AS softened
        FROM SEMANTIC.SEM_CLAIM_EVOLUTION
    """)
    row = cur.fetchone()
    logger.info(
        f"\n═══ Final SEM_CLAIM_EVOLUTION Summary ═══\n"
        f"  Total pairs:   {row[0]:,}\n"
        f"  Unique topics: {row[1]:,}\n"
        f"  CONTRADICTED:  {row[2]}\n"
        f"  REVISED:       {row[3]}\n"
        f"  CONFIRMED:     {row[4]}\n"
        f"  ESCALATED:     {row[5]}\n"
        f"  SOFTENED:      {row[6]}\n"
    )

    cur.close()
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Temporal claim evolution analyzer")
    parser.add_argument("--max-topics", type=int, default=300, help="Max topic pairs to process (default: 300)")
    parser.add_argument("--min-days",   type=int, default=30,  help="Min days between claim pair (default: 30)")
    args = parser.parse_args()
    run(max_topics=args.max_topics, min_days=args.min_days)
