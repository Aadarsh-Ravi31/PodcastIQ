"""
Neo4j Knowledge Graph Loader for PodcastIQ.

Reads from Snowflake and populates Neo4j with:
  Nodes:   Channel, Episode, Person, Topic, Claim
  Edges:   BELONGS_TO, APPEARED_ON, MADE_CLAIM, LIKELY_MADE_CLAIM,
           DISCUSSED_IN, ABOUT, SOURCED_FROM

Usage:
    python scripts/neo4j_loader.py
    python scripts/neo4j_loader.py --wipe   # clear graph first
"""

import os
import logging
import argparse
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

import snowflake.connector
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "podcastiq123")
BATCH_SIZE = 500


# ─────────────────────────────────────────────
# Connections
# ─────────────────────────────────────────────

def _snowflake_connect() -> snowflake.connector.SnowflakeConnection:
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


def _fetch(conn: snowflake.connector.SnowflakeConnection, sql: str) -> list[dict]:
    cur = conn.cursor(snowflake.connector.DictCursor)
    try:
        cur.execute(sql)
        return cur.fetchall()
    finally:
        cur.close()


def _batches(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i : i + size]


# ─────────────────────────────────────────────
# Graph setup
# ─────────────────────────────────────────────

def wipe_graph(driver):
    """Delete all nodes and relationships (for a clean reload)."""
    with driver.session() as s:
        s.run("MATCH (n) DETACH DELETE n")
    logger.info("Graph wiped")


def create_constraints(driver):
    constraints = [
        "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Channel)  REQUIRE c.channel_name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Episode)  REQUIRE e.video_id IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Person)   REQUIRE p.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (t:Topic)    REQUIRE t.name IS UNIQUE",
        "CREATE CONSTRAINT IF NOT EXISTS FOR (cl:Claim)   REQUIRE cl.claim_id IS UNIQUE",
    ]
    with driver.session() as s:
        for c in constraints:
            s.run(c)
    logger.info("Constraints ready")


# ─────────────────────────────────────────────
# Node loaders
# ─────────────────────────────────────────────

def load_channels(driver, conn):
    rows = _fetch(conn, """
        SELECT CHANNEL_ID, CHANNEL_NAME, GENRE, YOUTUBE_URL
        FROM RAW.CHANNELS
    """)
    with driver.session() as s:
        for batch in _batches(rows, BATCH_SIZE):
            s.run("""
                UNWIND $rows AS row
                MERGE (c:Channel {channel_name: row.CHANNEL_NAME})
                SET c.channel_id  = row.CHANNEL_ID,
                    c.genre       = row.GENRE,
                    c.youtube_url = row.YOUTUBE_URL
            """, rows=batch)
    logger.info(f"  Channels:  {len(rows):,}")


def load_episodes(driver, conn):
    rows = _fetch(conn, """
        SELECT DISTINCT
            VIDEO_ID, EPISODE_TITLE, CHANNEL_NAME,
            TO_VARCHAR(PUBLISH_DATE, 'YYYY-MM-DD') AS PUBLISH_DATE,
            YOUTUBE_URL, GENRE
        FROM CURATED.CUR_CHUNKS
        WHERE VIDEO_ID IS NOT NULL
    """)
    with driver.session() as s:
        for batch in _batches(rows, BATCH_SIZE):
            s.run("""
                UNWIND $rows AS row
                MERGE (e:Episode {video_id: row.VIDEO_ID})
                SET e.title        = row.EPISODE_TITLE,
                    e.channel_name = row.CHANNEL_NAME,
                    e.publish_date = row.PUBLISH_DATE,
                    e.youtube_url  = row.YOUTUBE_URL,
                    e.genre        = row.GENRE
            """, rows=batch)
    logger.info(f"  Episodes:  {len(rows):,}")


def load_persons(driver, conn):
    rows = _fetch(conn, """
        SELECT DISTINCT PARTICIPANT_NAME, PARTICIPANT_ROLE, CHANNEL_NAME
        FROM SEMANTIC.SEM_EPISODE_PARTICIPANTS
        WHERE PARTICIPANT_NAME IS NOT NULL
    """)
    with driver.session() as s:
        for batch in _batches(rows, BATCH_SIZE):
            s.run("""
                UNWIND $rows AS row
                MERGE (p:Person {name: row.PARTICIPANT_NAME})
                SET p.primary_role    = row.PARTICIPANT_ROLE,
                    p.primary_channel = row.CHANNEL_NAME
            """, rows=batch)
    logger.info(f"  Persons:   {len(rows):,}")


def load_topics(driver, conn):
    rows = _fetch(conn, """
        SELECT DISTINCT TOPIC AS TOPIC
        FROM SEMANTIC.SEM_CLAIMS
        WHERE TOPIC IS NOT NULL AND TRIM(TOPIC) != ''
    """)
    with driver.session() as s:
        for batch in _batches(rows, BATCH_SIZE):
            s.run("""
                UNWIND $rows AS row
                MERGE (t:Topic {name: row.TOPIC})
            """, rows=batch)
    logger.info(f"  Topics:    {len(rows):,}")


def load_claims(driver, conn):
    rows = _fetch(conn, """
        SELECT
            CLAIM_ID, VIDEO_ID,
            CLAIM_TEXT, TOPIC, CLAIM_TYPE, SENTIMENT,
            SPEAKER, SPEAKER_ROLE, ATTRIBUTION_CONFIDENCE,
            TO_VARCHAR(CLAIM_DATE, 'YYYY-MM-DD') AS CLAIM_DATE,
            CHANNEL_NAME, YOUTUBE_URL, VERIFICATION_STATUS
        FROM SEMANTIC.SEM_CLAIMS
        WHERE CLAIM_ID IS NOT NULL
    """)
    with driver.session() as s:
        for batch in _batches(rows, BATCH_SIZE):
            s.run("""
                UNWIND $rows AS row
                MERGE (cl:Claim {claim_id: row.CLAIM_ID})
                SET cl.text                   = row.CLAIM_TEXT,
                    cl.topic                  = row.TOPIC,
                    cl.claim_type             = row.CLAIM_TYPE,
                    cl.sentiment              = row.SENTIMENT,
                    cl.speaker                = row.SPEAKER,
                    cl.speaker_role           = row.SPEAKER_ROLE,
                    cl.attribution_confidence = row.ATTRIBUTION_CONFIDENCE,
                    cl.claim_date             = row.CLAIM_DATE,
                    cl.channel_name           = row.CHANNEL_NAME,
                    cl.youtube_url            = row.YOUTUBE_URL,
                    cl.verification_status    = row.VERIFICATION_STATUS,
                    cl.video_id               = row.VIDEO_ID
            """, rows=batch)
    logger.info(f"  Claims:    {len(rows):,}")


# ─────────────────────────────────────────────
# Edge creators
# ─────────────────────────────────────────────

def create_belongs_to(driver, conn):
    """Episode -[:BELONGS_TO]-> Channel"""
    rows = _fetch(conn, """
        SELECT DISTINCT VIDEO_ID, CHANNEL_NAME FROM CURATED.CUR_CHUNKS
        WHERE VIDEO_ID IS NOT NULL AND CHANNEL_NAME IS NOT NULL
    """)
    with driver.session() as s:
        for batch in _batches(rows, BATCH_SIZE):
            s.run("""
                UNWIND $rows AS row
                MATCH (e:Episode {video_id: row.VIDEO_ID})
                MATCH (c:Channel {channel_name: row.CHANNEL_NAME})
                MERGE (e)-[:BELONGS_TO]->(c)
            """, rows=batch)
    logger.info(f"  BELONGS_TO:        {len(rows):,}")


def create_appeared_on(driver, conn):
    """Person -[:APPEARED_ON]-> Episode"""
    rows = _fetch(conn, """
        SELECT VIDEO_ID, PARTICIPANT_NAME, PARTICIPANT_ROLE, CONFIDENCE, EXTRACTION_METHOD
        FROM SEMANTIC.SEM_EPISODE_PARTICIPANTS
        WHERE PARTICIPANT_NAME IS NOT NULL AND VIDEO_ID IS NOT NULL
    """)
    with driver.session() as s:
        for batch in _batches(rows, BATCH_SIZE):
            s.run("""
                UNWIND $rows AS row
                MATCH (p:Person  {name: row.PARTICIPANT_NAME})
                MATCH (e:Episode {video_id: row.VIDEO_ID})
                MERGE (p)-[r:APPEARED_ON]->(e)
                SET r.role             = row.PARTICIPANT_ROLE,
                    r.confidence       = row.CONFIDENCE,
                    r.extraction_method = row.EXTRACTION_METHOD
            """, rows=batch)
    logger.info(f"  APPEARED_ON:       {len(rows):,}")


def create_claim_edges(driver, conn):
    """
    Person -[:MADE_CLAIM]->        Claim  (HIGH confidence, known speaker)
    Person -[:LIKELY_MADE_CLAIM]-> Claim  (MEDIUM confidence, known speaker)
    Claim  -[:DISCUSSED_IN]->      Episode (UNKNOWN / missing speaker)
    """
    rows = _fetch(conn, """
        SELECT CLAIM_ID, VIDEO_ID, SPEAKER, ATTRIBUTION_CONFIDENCE
        FROM SEMANTIC.SEM_CLAIMS
        WHERE CLAIM_ID IS NOT NULL
    """)

    high, medium, unknown = [], [], []
    for r in rows:
        spk = (r["SPEAKER"] or "").strip().upper()
        conf = (r["ATTRIBUTION_CONFIDENCE"] or "").upper()
        if spk in ("", "UNKNOWN") or conf == "UNKNOWN":
            unknown.append(r)
        elif conf == "HIGH":
            high.append(r)
        else:
            medium.append(r)

    with driver.session() as s:
        # MADE_CLAIM
        for batch in _batches(high, BATCH_SIZE):
            s.run("""
                UNWIND $rows AS row
                MATCH (cl:Claim {claim_id: row.CLAIM_ID})
                MERGE (p:Person {name: row.SPEAKER})
                MERGE (p)-[:MADE_CLAIM]->(cl)
            """, rows=batch)

        # LIKELY_MADE_CLAIM
        for batch in _batches(medium, BATCH_SIZE):
            s.run("""
                UNWIND $rows AS row
                MATCH (cl:Claim {claim_id: row.CLAIM_ID})
                MERGE (p:Person {name: row.SPEAKER})
                MERGE (p)-[:LIKELY_MADE_CLAIM]->(cl)
            """, rows=batch)

        # DISCUSSED_IN
        for batch in _batches(unknown, BATCH_SIZE):
            s.run("""
                UNWIND $rows AS row
                MATCH (cl:Claim  {claim_id: row.CLAIM_ID})
                MATCH (e:Episode {video_id: row.VIDEO_ID})
                MERGE (cl)-[:DISCUSSED_IN]->(e)
            """, rows=batch)

    logger.info(
        f"  MADE_CLAIM:        {len(high):,}\n"
        f"                     LIKELY_MADE_CLAIM: {len(medium):,}\n"
        f"                     DISCUSSED_IN:      {len(unknown):,}"
    )


def create_about(driver, conn):
    """Claim -[:ABOUT]-> Topic"""
    rows = _fetch(conn, """
        SELECT CLAIM_ID, TOPIC FROM SEMANTIC.SEM_CLAIMS
        WHERE CLAIM_ID IS NOT NULL AND TOPIC IS NOT NULL AND TRIM(TOPIC) != ''
    """)
    with driver.session() as s:
        for batch in _batches(rows, BATCH_SIZE):
            s.run("""
                UNWIND $rows AS row
                MATCH (cl:Claim {claim_id: row.CLAIM_ID})
                MATCH (t:Topic  {name: row.TOPIC})
                MERGE (cl)-[:ABOUT]->(t)
            """, rows=batch)
    logger.info(f"  ABOUT:             {len(rows):,}")


def create_sourced_from(driver, conn):
    """Claim -[:SOURCED_FROM]-> Episode"""
    rows = _fetch(conn, """
        SELECT CLAIM_ID, VIDEO_ID FROM SEMANTIC.SEM_CLAIMS
        WHERE CLAIM_ID IS NOT NULL AND VIDEO_ID IS NOT NULL
    """)
    with driver.session() as s:
        for batch in _batches(rows, BATCH_SIZE):
            s.run("""
                UNWIND $rows AS row
                MATCH (cl:Claim  {claim_id: row.CLAIM_ID})
                MATCH (e:Episode {video_id: row.VIDEO_ID})
                MERGE (cl)-[:SOURCED_FROM]->(e)
            """, rows=batch)
    logger.info(f"  SOURCED_FROM:      {len(rows):,}")


# ─────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────

def print_summary(driver):
    with driver.session() as s:
        nodes = s.run("""
            MATCH (n) RETURN labels(n)[0] AS label, COUNT(*) AS count
            ORDER BY count DESC
        """).data()
        edges = s.run("""
            MATCH ()-[r]->() RETURN type(r) AS rel, COUNT(*) AS count
            ORDER BY count DESC
        """).data()

    logger.info("═══ Graph Summary ═══")
    logger.info("Nodes:")
    for r in nodes:
        logger.info(f"  {r['label']:<12} {r['count']:>8,}")
    logger.info("Edges:")
    for r in edges:
        logger.info(f"  {r['rel']:<20} {r['count']:>8,}")


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

def run(wipe: bool = False):
    logger.info("Connecting to Snowflake...")
    sf_conn = _snowflake_connect()

    logger.info("Connecting to Neo4j...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    driver.verify_connectivity()
    logger.info("Neo4j connected")

    try:
        if wipe:
            wipe_graph(driver)

        create_constraints(driver)

        logger.info("--- Loading Nodes ---")
        load_channels(driver, sf_conn)
        load_episodes(driver, sf_conn)
        load_persons(driver, sf_conn)
        load_topics(driver, sf_conn)
        load_claims(driver, sf_conn)

        logger.info("--- Creating Edges ---")
        create_belongs_to(driver, sf_conn)
        create_appeared_on(driver, sf_conn)
        create_claim_edges(driver, sf_conn)
        create_about(driver, sf_conn)
        create_sourced_from(driver, sf_conn)

        print_summary(driver)
        logger.info("Knowledge graph load complete ✓")

    finally:
        driver.close()
        sf_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--wipe", action="store_true", help="Delete all graph data before loading")
    args = parser.parse_args()
    run(wipe=args.wipe)
