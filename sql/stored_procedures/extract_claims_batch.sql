/*
  PodcastIQ — Snowflake Python Stored Procedure: EXTRACT_CLAIMS_BATCH

  Runs entirely server-side on Snowflake — no local Python process needed.

  Usage (run from Snowflake UI Worksheet):
    CALL SEMANTIC.EXTRACT_CLAIMS_BATCH(2800);

  Args:
    batch_size INT — number of unprocessed chunks to handle in this call

  Output: Inserts into SEMANTIC.SEM_CLAIMS, returns a status string.
*/

CREATE OR REPLACE PROCEDURE SEMANTIC.EXTRACT_CLAIMS_BATCH(batch_size INT)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
PACKAGES = ('snowflake-snowpark-python')
HANDLER = 'main'
EXECUTE AS CALLER
AS $$
import json
import re


PROMPT_TMPL = """You are extracting claims from a podcast transcript.

Episode: "{title}"
Channel: {channel}
Published: {pub_date}
Participants:
  Host(s) : {hosts}
  Guest(s) : {guests}

Transcript excerpt (starting at {start_sec}s):
\"\"\"{text}\"\"\"

Extract every significant factual claim, prediction, statistic, or strong opinion.

For each claim return a JSON object with these exact keys:
  "claim_text"             : concise declarative sentence (max 200 chars)
  "speaker_name"           : full name of speaker or "Unknown"
  "speaker_role"           : "HOST" | "GUEST" | "UNKNOWN"
  "attribution_confidence" : "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN"
  "claim_type"             : "VERIFIABLE_FACT" | "PREDICTION" | "OPINION" | "STATISTICAL"
  "topic"                  : single topic keyword
  "sentiment"              : "positive" | "negative" | "neutral"

Return ONLY a valid JSON array. No markdown, no explanation. Return [] if no claims."""


VALID_TYPES = {'VERIFIABLE_FACT', 'PREDICTION', 'OPINION', 'STATISTICAL'}
VALID_ROLES = {'HOST', 'GUEST', 'UNKNOWN'}
VALID_CONF  = {'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN'}
VALID_SENT  = {'positive', 'negative', 'neutral'}


def _parse_claims(raw: str) -> list:
    if not raw:
        return []
    text = re.sub(r'```(?:json)?', '', raw).strip()
    m = re.search(r'\[.*\]', text, re.DOTALL)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except Exception:
        return []


def main(session, batch_size: int) -> str:
    import uuid as uuid_mod

    # ── 1. Fetch unprocessed chunks ──────────────────────────────────
    chunks = session.sql(f"""
        SELECT
            c.CHUNK_ID, c.VIDEO_ID, c.CHANNEL_NAME, c.EPISODE_TITLE,
            c.PUBLISH_DATE::DATE::VARCHAR AS PUBLISH_DATE,
            c.CHUNK_START_SEC::INT        AS CHUNK_START_SEC,
            c.CHUNK_TEXT, c.YOUTUBE_URL
        FROM CURATED.CUR_CHUNKS c
        WHERE c.CHUNK_ID NOT IN (
            SELECT DISTINCT CHUNK_ID FROM SEMANTIC.SEM_CLAIMS
        )
        ORDER BY c.VIDEO_ID, c.CHUNK_START_SEC
        LIMIT {batch_size}
    """).collect()

    if not chunks:
        return 'DONE: No unprocessed chunks remaining'

    # ── 2. Build participant map ──────────────────────────────────────
    parts = session.sql("""
        SELECT VIDEO_ID, PARTICIPANT_NAME, PARTICIPANT_ROLE
        FROM SEMANTIC.SEM_EPISODE_PARTICIPANTS
        WHERE CONFIDENCE IN ('HIGH', 'MEDIUM')
    """).collect()

    pmap = {}
    for p in parts:
        vid  = p[0]
        name = p[1]
        role = p[2]
        if vid not in pmap:
            pmap[vid] = {'hosts': [], 'guests': []}
        if role == 'HOST':
            pmap[vid]['hosts'].append(name)
        else:
            pmap[vid]['guests'].append(name)

    # ── 3. Extract claims per chunk ───────────────────────────────────
    rows = []
    errors = 0

    for chunk in chunks:
        chunk_id  = chunk[0]
        vid       = chunk[1]
        channel   = chunk[2]
        title     = chunk[3]
        pub_date  = chunk[4] or 'Unknown'
        start_sec = chunk[5] or 0
        text      = (chunk[6] or '')[:1800]
        yt_url    = chunk[7] or ''

        p      = pmap.get(vid, {})
        hosts  = ', '.join(p.get('hosts',  [])) or 'Unknown'
        guests = ', '.join(p.get('guests', [])) or 'Unknown'

        prompt = PROMPT_TMPL.format(
            title=title, channel=channel, pub_date=pub_date,
            hosts=hosts, guests=guests,
            start_sec=start_sec, text=text,
        )
        # Escape single quotes for inline SQL
        safe_prompt = prompt.replace("'", "''")

        try:
            result = session.sql(
                f"SELECT SNOWFLAKE.CORTEX.COMPLETE('llama3.1-70b', '{safe_prompt}')"
            ).collect()[0][0]

            raw_claims = _parse_claims(result)

            for c in raw_claims:
                ct = str(c.get('claim_text', '')).strip()[:1000]
                if len(ct) < 10:
                    continue

                ctype = str(c.get('claim_type', 'OPINION')).upper()
                if ctype not in VALID_TYPES:
                    ctype = 'OPINION'

                role = str(c.get('speaker_role', 'UNKNOWN')).upper()
                if role not in VALID_ROLES:
                    role = 'UNKNOWN'

                conf = str(c.get('attribution_confidence', 'UNKNOWN')).upper()
                if conf not in VALID_CONF:
                    conf = 'UNKNOWN'

                sent = str(c.get('sentiment', 'neutral')).lower()
                if sent not in VALID_SENT:
                    sent = 'neutral'

                speaker = str(c.get('speaker_name', 'Unknown')).strip()[:200]
                if not speaker:
                    speaker = 'Unknown'

                topic = str(c.get('topic', 'General')).strip()[:100]

                rows.append((
                    str(uuid_mod.uuid4()),      # CLAIM_ID
                    chunk_id,                   # CHUNK_ID
                    vid,                        # VIDEO_ID
                    ct,                         # CLAIM_TEXT
                    topic,                      # TOPIC
                    ctype,                      # CLAIM_TYPE
                    sent,                       # SENTIMENT
                    speaker,                    # SPEAKER
                    role,                       # SPEAKER_ROLE
                    conf,                       # ATTRIBUTION_CONFIDENCE
                    'LLM_INFERRED',             # ATTRIBUTION_SOURCE
                    pub_date,                   # CLAIM_DATE
                    channel[:100],              # CHANNEL_NAME
                    yt_url[:500],               # YOUTUBE_URL
                    'llama3.1-70b',             # EXTRACTION_MODEL
                ))

        except Exception:
            errors += 1
            continue

    # ── 4. Bulk insert ────────────────────────────────────────────────
    if rows:
        cols = [
            'CLAIM_ID', 'CHUNK_ID', 'VIDEO_ID',
            'CLAIM_TEXT', 'TOPIC', 'CLAIM_TYPE', 'SENTIMENT',
            'SPEAKER', 'SPEAKER_ROLE', 'ATTRIBUTION_CONFIDENCE', 'ATTRIBUTION_SOURCE',
            'CLAIM_DATE', 'CHANNEL_NAME', 'YOUTUBE_URL', 'EXTRACTION_MODEL',
        ]
        df = session.create_dataframe(rows, schema=cols)
        df.write.mode('append').save_as_table('SEMANTIC.SEM_CLAIMS')

    return (
        f'Processed {len(chunks)} chunks | '
        f'Inserted {len(rows)} claims | '
        f'Errors {errors}'
    )
$$;
