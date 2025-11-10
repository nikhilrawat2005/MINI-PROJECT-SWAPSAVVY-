# scripts/add_missing_columns.py
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("instance") / "swapsavvy.db"

if not DB_PATH.exists():
    print("Error: DB not found at", DB_PATH)
    sys.exit(1)

def column_exists(cur, table, column):
    cur.execute(f"PRAGMA table_info({table});")
    cols = [r[1] for r in cur.fetchall()]  # r[1] is name
    return column in cols

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()

try:
    # 1) profile_mode (store as TEXT; defaults to 'both')
    if not column_exists(cur, "users", "profile_mode"):
        print("Adding column: profile_mode")
        cur.execute("ALTER TABLE users ADD COLUMN profile_mode TEXT DEFAULT 'both';")
    else:
        print("Column exists: profile_mode")

    # 2) hourly_rate (store as REAL; nullable)
    if not column_exists(cur, "users", "hourly_rate"):
        print("Adding column: hourly_rate")
        cur.execute("ALTER TABLE users ADD COLUMN hourly_rate REAL;")
    else:
        print("Column exists: hourly_rate")

    # 3) response_time (TEXT; nullable)
    if not column_exists(cur, "users", "response_time"):
        print("Adding column: response_time")
        cur.execute("ALTER TABLE users ADD COLUMN response_time TEXT;")
    else:
        print("Column exists: response_time")

    # If your model expects other new columns, add similar blocks here.
    conn.commit()
    print("Done. Columns added (if they were missing).")
except Exception as e:
    print("Error while altering table:", e)
    conn.rollback()
finally:
    conn.close()
