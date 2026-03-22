"""
PodcastIQ — launch_parallel_claims.py

Launches 25 parallel async Snowflake stored procedure calls,
one per channel. Each runs entirely on Snowflake — no PC needed.

Each channel-specific call processes only that channel's unprocessed
chunks, so there is zero overlap and no duplicate-claim risk.
"""

import os
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import snowflake.connector

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


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
    )


def _create_channel_procedure(cur):
    """Create channel-specific stored procedure (wraps EXTRACT_CLAIMS_BATCH with channel filter)."""
    cur.execute("""
CREATE OR REPLACE PROCEDURE SEMANTIC.EXTRACT_CLAIMS_BY_CHANNEL(channel_name VARCHAR)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'main'
EXECUTE AS CALLER
AS $$
import json
import re


PROMPT_TMPL = \"\"\"You are extracting claims from a podcast transcript.

Episode: \"{title}\"
Channel: {channel}
Published: {pub_date}
Participants:
  Host(s) : {hosts}
  Guest(s) : {guests}

Transcript excerpt (starting at {start_sec}s):
\\\"\\\"\\\"{text}\\\"\\\"\\\"

Extract every significant factual claim, prediction, statistic, or strong opinion.

For each claim return a JSON object with these exact keys:
  "claim_text"             : concise declarative sentence (max 200 chars)
  "speaker_name"           : full name of speaker or "Unknown"
  "speaker_role"           : "HOST" | "GUEST" | "UNKNOWN"
  "attribution_confidence" : "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN"
  "claim_type"             : "VERIFIABLE_FACT" | "PREDICTION" | "OPINION" | "STATISTICAL"
  "topic"                  : single topic keyword
  "sentiment"              : "positive" | "negative" | "neutral"

Return ONLY a valid JSON array. No markdown, no explanation. Return [] if no claims.\"\"\"


VALID_TYPES = {'VERIFIABLE_FACT', 'PREDICTION', 'OPINION', 'STATISTICAL'}
VALID_ROLES = {'HOST', 'GUEST', 'UNKNOWN'}
VALID_CONF  = {'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'}
VALID_SENT  = {'positive', 'negative', 'neutral'}


def _parse_claims(raw):
    if not raw:
        return []
    text = re.sub(r'```(?:json)?', '', raw).strip()
    m = re.search(r'\\[.*\\]', text, re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except Exception:
        return []


def main(session, channel_name: str) -> str:
    import uuid as uuid_mod
    safe_ch = channel_name.replace("'", "''")

    chunks = session.sql(f\"\"\"
        SELECT c.CHUNK_ID, c.VIDEO_ID, c.CHANNEL_NAME, c.EPISODE_TITLE,
               c.PUBLISH_DATE::DATE::VARCHAR, c.CHUNK_START_SEC::INT,
               c.CHUNK_TEXT, c.YOUTUBE_URL
        FROM CURATED.CUR_CHUNKS c
        WHERE c.CHANNEL_NAME = '{safe_ch}'
          AND c.CHUNK_ID NOT IN (SELECT DISTINCT CHUNK_ID FROM SEMANTIC.SEM_CLAIMS)
        ORDER BY c.VIDEO_ID, c.CHUNK_START_SEC
    \"\"\").collect()

    if not chunks:
        return f'DONE: {channel_name} — no unprocessed chunks'

    parts = session.sql(f\"\"\"
        SELECT VIDEO_ID, PARTICIPANT_NAME, PARTICIPANT_ROLE
        FROM SEMANTIC.SEM_EPISODE_PARTICIPANTS
        WHERE CHANNEL_NAME = '{safe_ch}'
          AND CONFIDENCE IN ('HIGH', 'MEDIUM')
    \"\"\").collect()

    pmap = {}
    for p in parts:
        vid = p[0]
        if vid not in pmap:
            pmap[vid] = {'hosts': [], 'guests': []}
        if p[2] == 'HOST':
            pmap[vid]['hosts'].append(p[1])
        else:
            pmap[vid]['guests'].append(p[1])

    rows = []
    errors = 0
    for chunk in chunks:
        chunk_id, vid, channel, title = chunk[0], chunk[1], chunk[2], chunk[3]
        pub_date  = chunk[4] or 'Unknown'
        start_sec = chunk[5] or 0
        text      = (chunk[6] or '')[:1800]
        yt_url    = chunk[7] or ''

        p      = pmap.get(vid, {})
        hosts  = ', '.join(p.get('hosts',  [])) or 'Unknown'
        guests = ', '.join(p.get('guests', [])) or 'Unknown'

        prompt = PROMPT_TMPL.format(
            title=title, channel=channel, pub_date=pub_date,
            hosts=hosts, guests=guests, start_sec=start_sec, text=text,
        )
        safe_prompt = prompt.replace("'", "''")

        try:
            result = session.sql(
                f"SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', '{safe_prompt}')"
            ).collect()[0][0]

            for c in _parse_claims(result):
                ct = str(c.get('claim_text', '')).strip()[:1000]
                if len(ct) < 10:
                    continue
                ctype = str(c.get('claim_type', 'OPINION')).upper()
                if ctype not in VALID_TYPES: ctype = 'OPINION'
                role = str(c.get('speaker_role', 'UNKNOWN')).upper()
                if role not in VALID_ROLES: role = 'UNKNOWN'
                conf = str(c.get('attribution_confidence', 'UNKNOWN')).upper()
                if conf not in VALID_CONF: conf = 'UNKNOWN'
                sent = str(c.get('sentiment', 'neutral')).lower()
                if sent not in VALID_SENT: sent = 'neutral'
                speaker = str(c.get('speaker_name', 'Unknown')).strip()[:200] or 'Unknown'
                rows.append((
                    str(uuid_mod.uuid4()), chunk_id, vid, ct,
                    str(c.get('topic', 'General')).strip()[:100],
                    ctype, sent, speaker, role, conf, 'LLM_INFERRED',
                    pub_date, channel[:100], yt_url[:500], 'llama3.1-70b',
                ))
        except Exception:
            errors += 1

    if rows:
        cols = ['CLAIM_ID','CHUNK_ID','VIDEO_ID','CLAIM_TEXT','TOPIC','CLAIM_TYPE',
                'SENTIMENT','SPEAKER','SPEAKER_ROLE','ATTRIBUTION_CONFIDENCE',
                'ATTRIBUTION_SOURCE','CLAIM_DATE','CHANNEL_NAME','YOUTUBE_URL','EXTRACTION_MODEL']
        df = session.create_dataframe(rows, schema=cols)
        df.write.mode('append').save_as_table('SEMANTIC.SEM_CLAIMS')

    return f'{channel_name}: {len(chunks)} chunks, {len(rows)} claims, {errors} errors'
$$;
    """)
    log.info("EXTRACT_CLAIMS_BY_CHANNEL stored procedure created.")


def submit_channel_job(channel: str) -> tuple[str, str]:
    """Open a connection, submit async CALL for one channel, close connection."""
    conn = _get_connection()
    cur  = conn.cursor()
    safe = channel.replace("'", "''")
    cur.execute_async(f"CALL SEMANTIC.EXTRACT_CLAIMS_BY_CHANNEL('{safe}')")
    qid = cur.sfqid
    cur.close()
    conn.close()
    return channel, qid


def main():
    # Step 1: fetch distinct channels
    conn = _get_connection()
    cur  = conn.cursor()

    # Cancel previous single-threaded job (ignore error if already done)
    try:
        cur.execute("SELECT SYSTEM$CANCEL_QUERY('01c3201f-0108-261a-001a-e4430059f1f6')")
        log.info(f"Cancel previous job: {cur.fetchone()}")
    except Exception as e:
        log.info(f"Previous job cancel skipped: {e}")

    # Create channel-specific stored procedure
    _create_channel_procedure(cur)

    # Get channels that still have unprocessed chunks
    cur.execute("""
        SELECT DISTINCT c.CHANNEL_NAME, COUNT(*) AS pending
        FROM CURATED.CUR_CHUNKS c
        WHERE c.CHUNK_ID NOT IN (SELECT DISTINCT CHUNK_ID FROM SEMANTIC.SEM_CLAIMS)
        GROUP BY 1
        ORDER BY 2 DESC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    channels = [r[0] for r in rows]
    log.info(f"Channels with pending chunks: {len(channels)}")
    for ch, cnt in rows:
        log.info(f"  {ch}: {cnt} chunks")

    # Step 2: launch 25 async jobs in parallel
    log.info(f"\nLaunching {len(channels)} parallel async jobs on Snowflake...")
    query_ids = {}

    with ThreadPoolExecutor(max_workers=len(channels)) as executor:
        futures = {executor.submit(submit_channel_job, ch): ch for ch in channels}
        for future in as_completed(futures):
            ch = futures[future]
            try:
                channel, qid = future.result()
                query_ids[channel] = qid
                log.info(f"  Submitted: {channel[:45]:<45} → {qid}")
            except Exception as e:
                log.error(f"  Failed to submit {ch}: {e}")

    log.info(f"\nAll {len(query_ids)} jobs submitted to Snowflake.")
    log.info("Your PC is free — all processing runs on Snowflake servers.")
    log.info("\nQuery IDs (save these to check status tomorrow):")
    for ch, qid in query_ids.items():
        print(f"  {ch[:50]:<50} {qid}")

    log.info("\nCheck progress in Snowflake UI:")
    log.info("  SELECT COUNT(*), COUNT(DISTINCT VIDEO_ID) FROM SEMANTIC.SEM_CLAIMS;")


if __name__ == "__main__":
    main()
