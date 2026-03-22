"""Cancel all running EXTRACT_CLAIMS Snowflake jobs."""
from dotenv import load_dotenv; load_dotenv()
import os
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
import snowflake.connector

key_path = os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")
with open(key_path, "rb") as f:
    pk = serialization.load_pem_private_key(f.read(), password=os.environ.get("SNOWFLAKE_PRIVATE_KEY_PASSPHRASE","").encode() or None, backend=default_backend())
pk_bytes = pk.private_bytes(encoding=serialization.Encoding.DER, format=serialization.PrivateFormat.PKCS8, encryption_algorithm=serialization.NoEncryption())
conn = snowflake.connector.connect(account=os.getenv("SNOWFLAKE_ACCOUNT"), user=os.getenv("SNOWFLAKE_USER"), private_key=pk_bytes, warehouse="PODCASTIQ_WH", database="PODCASTIQ", schema="SEMANTIC", role="TRAINING_ROLE")
cur = conn.cursor()

cur.execute("""
    SELECT QUERY_ID FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY_BY_USER(
        USER_NAME => CURRENT_USER(), RESULT_LIMIT => 100
    ))
    WHERE EXECUTION_STATUS = 'RUNNING'
      AND QUERY_TEXT ILIKE '%EXTRACT_CLAIMS%'
""")
running = [r[0] for r in cur.fetchall()]
print(f"Found {len(running)} running EXTRACT_CLAIMS jobs")
for qid in running:
    cur.execute("SELECT SYSTEM$CANCEL_QUERY(%s)", (qid,))
    print(f"  Cancelled {qid}: {cur.fetchone()}")

cur.close(); conn.close()
print("Done.")
