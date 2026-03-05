"""Quick Snowflake connection test — full error output to file."""
import os
import traceback
from dotenv import load_dotenv
import snowflake.connector

load_dotenv()

with open("logs/conn_full.txt", "w", encoding="utf-8") as out:
    out.write(f"Account  : {os.getenv('SNOWFLAKE_ACCOUNT')}\n")
    out.write(f"User     : {os.getenv('SNOWFLAKE_USER')}\n")
    out.write(f"Warehouse: {os.getenv('SNOWFLAKE_WAREHOUSE')}\n")
    out.write(f"Database : {os.getenv('SNOWFLAKE_DATABASE')}\n")
    out.write(f"Role     : {os.getenv('SNOWFLAKE_ROLE')}\n\n")

    try:
        conn = snowflake.connector.connect(
            account      = os.getenv("SNOWFLAKE_ACCOUNT"),
            user         = os.getenv("SNOWFLAKE_USER"),
            password     = os.getenv("SNOWFLAKE_PASSWORD"),
            warehouse    = os.getenv("SNOWFLAKE_WAREHOUSE"),
            database     = os.getenv("SNOWFLAKE_DATABASE"),
            schema       = os.getenv("SNOWFLAKE_SCHEMA"),
            role         = os.getenv("SNOWFLAKE_ROLE"),
            login_timeout = 15
        )
        cur = conn.cursor()
        cur.execute("SELECT CURRENT_ACCOUNT(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA()")
        row = cur.fetchone()
        out.write("[OK] Connected!\n")
        out.write(f"  Account  : {row[0]}\n")
        out.write(f"  Role     : {row[1]}\n")
        out.write(f"  Database : {row[2]}\n")
        out.write(f"  Schema   : {row[3]}\n")

        cur.execute("SHOW TABLES IN SCHEMA PODCASTIQ.RAW")
        tables = [r[1] for r in cur.fetchall()]
        out.write(f"  Tables   : {tables}\n")

        cur.execute("SHOW STAGES IN SCHEMA PODCASTIQ.RAW")
        stages = [r[1] for r in cur.fetchall()]
        out.write(f"  Stages   : {stages}\n")

        conn.close()

    except Exception as e:
        out.write(f"[FAIL] {type(e).__name__}: {e}\n\n")
        out.write(traceback.format_exc())

print("Done — check logs/conn_full.txt")
