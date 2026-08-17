"""One-shot schema introspection for migration 007 (rate limit + lock IP).
Run: cd /app/backend && python tests/introspect_007.py
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

results = {}

# 1. checkout_attempts table exists and is empty.
try:
    r = sb.table("checkout_attempts").select("id, ip, email, created_at", count="exact").limit(1).execute()
    results["checkout_attempts"] = {"exists": True, "row_count": r.count}
except Exception as e:
    results["checkout_attempts"] = {"exists": False, "error": f"{type(e).__name__}: {e}"}

# 2. date_slot_locks now has an ip column.
try:
    r = sb.table("date_slot_locks").select("id, ip, event_date, session_id, expires_at").limit(1).execute()
    results["date_slot_locks_ip_column"] = {"selectable": True, "sample_rows": len(r.data or [])}
except Exception as e:
    results["date_slot_locks_ip_column"] = {"selectable": False, "error": f"{type(e).__name__}: {e}"}

# 3. Live insert/select round-trip against checkout_attempts.
try:
    sample = sb.table("checkout_attempts").insert({
        "ip": "1.2.3.4",
        "email": "introspect@flyboytest.com",
    }).execute().data[0]
    sb.table("checkout_attempts").delete().eq("id", sample["id"]).execute()
    results["insert_delete_roundtrip"] = {"ok": True, "id_shape": bool(sample.get("id")), "created_at": sample.get("created_at")}
except Exception as e:
    results["insert_delete_roundtrip"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

print(json.dumps(results, indent=2, default=str))
