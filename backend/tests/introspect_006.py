"""One-shot schema introspection to prove migration 006 has been applied.
Run: cd /app/backend && python tests/introspect_006.py
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

results = {}

# 1. New tables exist and are readable (count returns 0 rows expected).
for t in ("payment_transactions", "date_slot_locks", "booking_intents"):
    try:
        r = sb.table(t).select("id", count="exact").limit(1).execute()
        results[f"table:{t}"] = {"exists": True, "row_count": r.count}
    except Exception as e:
        results[f"table:{t}"] = {"exists": False, "error": f"{type(e).__name__}: {e}"}

# 2. bookings has the 4 new columns.
try:
    r = sb.table("bookings").select(
        "id, event_date, deposit_paid_at, stripe_session_id, booking_intent_id"
    ).limit(1).execute()
    results["bookings_columns"] = {"selectable": True, "sample_row_count": len(r.data or [])}
except Exception as e:
    results["bookings_columns"] = {"selectable": False, "error": f"{type(e).__name__}: {e}"}

# 3. Partial unique index enforces one confirmed booking per date.
#    Insert two confirmed rows with the same event_date and expect the 2nd to fail.
import uuid
probe_date = "2099-12-31"  # sentinel far-future date
client_id = None
try:
    # find or create a temp client row to satisfy FK — use any existing admin
    admins = sb.table("clients").select("id").eq("role", "admin").limit(1).execute().data
    if not admins:
        results["unique_index_probe"] = {"skipped": "no admin client to satisfy FK"}
    else:
        client_id = admins[0]["id"]
        # cleanup any prior probe rows
        sb.table("bookings").delete().eq("event_date", probe_date).execute()
        row1 = sb.table("bookings").insert({
            "client_id": client_id,
            "title": "INDEX PROBE 1",
            "status": "confirmed",
            "event_date": probe_date,
            "is_seed_data": True,
        }).execute().data[0]
        second_failed = False
        second_err = None
        try:
            sb.table("bookings").insert({
                "client_id": client_id,
                "title": "INDEX PROBE 2",
                "status": "confirmed",
                "event_date": probe_date,
                "is_seed_data": True,
            }).execute()
        except Exception as e:
            second_failed = True
            second_err = f"{type(e).__name__}: {str(e)[:200]}"
        # cleanup
        sb.table("bookings").delete().eq("event_date", probe_date).execute()
        results["unique_index_probe"] = {
            "first_insert_ok": True,
            "second_insert_rejected": second_failed,
            "second_error_excerpt": second_err,
        }
except Exception as e:
    results["unique_index_probe"] = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
    if client_id:
        try:
            sb.table("bookings").delete().eq("event_date", probe_date).execute()
        except Exception:
            pass

# 4. Is there an existing packages table? (a2 vs a1 decision)
try:
    r = sb.table("packages").select("*", count="exact").limit(1).execute()
    results["packages_table"] = {
        "exists": True,
        "row_count": r.count,
        "sample": r.data[:1] if r.data else [],
    }
except Exception as e:
    results["packages_table"] = {"exists": False, "error_class": type(e).__name__, "excerpt": str(e)[:200]}

print(json.dumps(results, indent=2, default=str))
