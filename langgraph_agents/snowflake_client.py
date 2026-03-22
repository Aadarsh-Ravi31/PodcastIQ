"""
Snowflake connection singleton for LangGraph agents.
All agents share one connection per process.
"""

import os
import logging
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

_conn: snowflake.connector.SnowflakeConnection | None = None


def _create_connection() -> snowflake.connector.SnowflakeConnection:
    key_path = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
    if not key_path:
        raise ValueError("SNOWFLAKE_PRIVATE_KEY_PATH not set in .env")

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
        account   = os.getenv("SNOWFLAKE_ACCOUNT"),
        user      = os.getenv("SNOWFLAKE_USER"),
        private_key = pk_bytes,
        warehouse = os.getenv("SNOWFLAKE_WAREHOUSE", "PODCASTIQ_WH"),
        database  = os.getenv("SNOWFLAKE_DATABASE",  "PODCASTIQ"),
        schema    = os.getenv("SNOWFLAKE_SCHEMA",     "SEMANTIC"),
        role      = os.getenv("SNOWFLAKE_ROLE",       "TRAINING_ROLE"),
    )


def get_connection() -> snowflake.connector.SnowflakeConnection:
    """Return the shared Snowflake connection, creating it if needed."""
    global _conn
    if _conn is None or _conn.is_closed():
        log.info("Connecting to Snowflake...")
        _conn = _create_connection()
    return _conn


def execute(sql: str, params: tuple = ()) -> list[dict]:
    """Run a SQL query and return rows as a list of dicts."""
    conn = get_connection()
    cur = conn.cursor(snowflake.connector.DictCursor)
    try:
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        cur.close()


def execute_scalar(sql: str, params: tuple = ()) -> str | None:
    """Run a SQL query and return the first column of the first row."""
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        cur.close()
