"""Verify Migration 015 (Bunny Phase 1 schema) landed correctly.

Checks:
  1. deliverables has bunny_video_guid / bunny_storage_object / bunny_status.
  2. deliverable_access_events table exists with expected columns.
  3. CHECK constraints reject a bad actor_role and a bad event_type, and
     accept valid values (uses a real deliverable id if one exists; else
     skips the insert-based checks with a note).
  4. FK cascade shape: deliverable_id is NOT NULL (insert without it fails).
  5. RLS: anon SELECT returns 0 rows (no read policy) — service-role only.

Run:
    python backend/tests/introspect_015.py
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

from supabase import create_client  # noqa: E402

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
_anon_key = None
try:
    for line in (Path("/app/frontend/.env").read_text()).splitlines():
        if line.startswith("REACT_APP_SUPABASE_ANON_KEY="):
            _anon_key = line.split("=", 1)[1].strip()
            break
except Exception:
    pass
anon = create_client(os.environ["SUPABASE_URL"], _anon_key) if _anon_key else None

results = {}
inserted_ids = []

# 1) deliverables columns
try:
    row = sb.table("deliverables").select(
        "id, bunny_video_guid, bunny_storage_object, bunny_status"
    ).limit(1).execute().data
    results["deliverables_columns"] = {"ok": True, "sample_present": bool(row)}
except Exception as e:
    results["deliverables_columns"] = {"ok": False, "err": f"{type(e).__name__}: {e}"}

# 2) table + columns
try:
    row = sb.table("deliverable_access_events").select("*").limit(1).execute().data
    cols_seen = set(row[0].keys()) if row else set()
    if not row:
        # nothing to inspect yet; column presence proven via a targeted select
        sb.table("deliverable_access_events").select(
            "id, deliverable_id, client_id, actor_role, event_type, meta, created_at"
        ).limit(1).execute()
        cols_seen = {"id", "deliverable_id", "client_id", "actor_role", "event_type", "meta", "created_at"}
    expected = {"id", "deliverable_id", "client_id", "actor_role", "event_type", "meta", "created_at"}
    missing = expected - cols_seen
    results["access_events_table"] = {"ok": not missing, "missing": list(missing)}
except Exception as e:
    results["access_events_table"] = {"ok": False, "err": f"{type(e).__name__}: {e}"}

# find a real deliverable id for insert-based checks
deliv_id = None
try:
    d = sb.table("deliverables").select("id, client_id").limit(1).execute().data
    if d:
        deliv_id = d[0]["id"]
        deliv_client = d[0].get("client_id")
except Exception:
    pass

# 3) CHECK constraints
if not deliv_id:
    results["check_constraints"] = {"ok": True, "skipped": "no deliverable row to reference"}
else:
    sub = {}
    # bad actor_role
    try:
        sb.table("deliverable_access_events").insert({
            "deliverable_id": deliv_id, "actor_role": "wizard", "event_type": "player_play",
        }).execute()
        sub["bad_actor_role_rejected"] = False
    except Exception as e:
        m = str(e).lower()
        sub["bad_actor_role_rejected"] = "check" in m or "23514" in m
    # bad event_type
    try:
        sb.table("deliverable_access_events").insert({
            "deliverable_id": deliv_id, "actor_role": "client", "event_type": "teleport",
        }).execute()
        sub["bad_event_type_rejected"] = False
    except Exception as e:
        m = str(e).lower()
        sub["bad_event_type_rejected"] = "check" in m or "23514" in m
    # valid insert accepted
    try:
        r = sb.table("deliverable_access_events").insert({
            "deliverable_id": deliv_id, "actor_role": "admin",
            "event_type": "playback_url_issued", "meta": {"introspect": True},
        }).execute().data[0]
        inserted_ids.append(r["id"])
        sub["valid_insert_accepted"] = True
    except Exception as e:
        sub["valid_insert_accepted"] = False
        sub["valid_insert_err"] = str(e)[:200]
    sub["ok"] = all(v is True for k, v in sub.items() if k.endswith("_rejected") or k == "valid_insert_accepted")
    results["check_constraints"] = sub

# 4) NOT NULL deliverable_id
try:
    sb.table("deliverable_access_events").insert({
        "actor_role": "client", "event_type": "player_play",
    }).execute()
    results["deliverable_id_not_null"] = {"ok": False, "note": "insert without deliverable_id accepted"}
except Exception as e:
    m = str(e).lower()
    results["deliverable_id_not_null"] = {"ok": "null" in m or "23502" in m or "violates" in m, "err_excerpt": str(e)[:160]}

# 5) RLS anon isolation
if anon is None:
    results["rls_isolation"] = {"ok": True, "skipped": "no anon key"}
else:
    try:
        n = len(anon.table("deliverable_access_events").select("id").execute().data)
        results["rls_isolation"] = {"ok": n == 0, "anon_saw": n}
    except Exception as e:
        m = str(e).lower()
        if "permission" in m or "rls" in m or "policy" in m or "42501" in m:
            results["rls_isolation"] = {"ok": True, "note": "anon errored (expected)"}
        else:
            results["rls_isolation"] = {"ok": False, "err": str(e)}

# cleanup
for _id in inserted_ids:
    try:
        sb.table("deliverable_access_events").delete().eq("id", _id).execute()
    except Exception:
        pass

results["_verdict"] = "PASS" if all(
    r.get("ok") for r in results.values() if isinstance(r, dict)
) else "FAIL"
print(json.dumps(results, indent=2, default=str))
