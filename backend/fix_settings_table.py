"""
Run this script to add missing columns to the settings table.
Usage: python fix_settings_table.py
"""
from dotenv import load_dotenv
load_dotenv('.env')
import os

try:
    import psycopg2
except ImportError:
    print("Installing psycopg2...")
    import subprocess, sys
    subprocess.check_call([sys.executable, "-m", "pip", "install", "psycopg2-binary", "-q"])
    import psycopg2

db_url = os.getenv('DATABASE_URL', '')
if not db_url:
    print("ERROR: DATABASE_URL not set in .env")
    exit(1)

# Supabase pooler uses port 6543 for session mode (5432 is transaction mode)
# Also try decoding any URL-encoded chars in the password
import urllib.parse
parsed = urllib.parse.urlparse(db_url)
raw_password = parsed.password or ''
decoded_password = urllib.parse.unquote(raw_password)
password_candidates = list(dict.fromkeys([raw_password, decoded_password]))
user = parsed.username
host = parsed.hostname
port = parsed.port or 5432
dbname = parsed.path.lstrip('/')

print(f"Connecting: host={host} port={port} user={user} db={dbname}")

# Try session mode port first (6543), fall back to 5432. Some DATABASE_URL
# values store an already-literal password, while others URL-encode it.
for try_port in [6543, 5432]:
    for password in password_candidates:
        try:
            conn = psycopg2.connect(
                host=host, port=try_port, user=user,
                password=password, dbname=dbname,
                connect_timeout=10,
                sslmode='require',
            )
            print(f"Connected on port {try_port}")
            break
        except Exception as e:
            print(f"Port {try_port} failed: {e}")
    else:
        continue
    break
else:
    print("ERROR: Could not connect to database")
    exit(1)
conn.autocommit = True
cur = conn.cursor()

columns = [
    ("auto_scroll",               "boolean NOT NULL DEFAULT true"),
    ("show_sources",              "boolean NOT NULL DEFAULT true"),
    ("save_chat_history",         "boolean NOT NULL DEFAULT true"),
    ("default_upload_collection", "uuid NULL"),
    ("rag_mode",                  "text NOT NULL DEFAULT 'balanced'"),
    ("response_style",            "text NOT NULL DEFAULT 'professional'"),
    ("default_collection_id",     "uuid NULL"),
    ("preferred_model",           "text NOT NULL DEFAULT 'gemini'"),
    ("temperature",               "float NOT NULL DEFAULT 0.3"),
    ("max_context_chunks",        "integer NOT NULL DEFAULT 5"),
    ("chunk_size",                "integer NOT NULL DEFAULT 1000"),
    ("chunk_overlap",             "integer NOT NULL DEFAULT 200"),
    ("theme",                     "text NOT NULL DEFAULT 'dark'"),
    ("updated_at",                "timestamptz NOT NULL DEFAULT now()"),
]

for col_name, col_def in columns:
    try:
        cur.execute(f"ALTER TABLE public.settings ADD COLUMN IF NOT EXISTS {col_name} {col_def}")
        print(f"  + {col_name}")
    except Exception as e:
        print(f"  ~ {col_name}: {e}")

# Verify
cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='settings' ORDER BY ordinal_position")
cols = [r[0] for r in cur.fetchall()]
print(f"\nFinal columns ({len(cols)}):", cols)

conn.close()
print("\nDone! Settings table is ready.")
