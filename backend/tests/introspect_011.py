"""One-shot schema introspection for migration 011 (webhook_deliveries_audit).

Run AFTER applying supabase_migration_011_webhook_deliveries_audit.sql
via the Supabase SQL Editor.

Verifies:
  1. Table exists and is selectable.
  2. All expected columns present.
  3. Unique constraint on (stripe_event_id, pod_source) rejects duplicates.
  4. Live insert/upsert/select round-trip works.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

results = {}

# 1. Table exists and is selectable.
try:
    r = sb.table("webhook_deliveries_audit").select(
        "id, stripe_event_id, event_type, session_id, pod_source, received_at, "
        "signature_valid, processing_ms, response_status, finalise_outcome, "
        "error_message, stripe_created_at",
        count="exact",
    ).limit(1).execute()
    results["table_exists"] = {"ok": True, "row_count": r.count}
except Exception as e:
    results["table_exists"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    print(json.dumps(results, indent=2, default=str))
    raise SystemExit(1)

# 2. Insert a synthetic row (introspect_marker).
probe_event_id = "evt_introspect_011_marker"
probe_pod = "introspect"
try:
    inserted = sb.table("webhook_deliveries_audit").insert({
        "stripe_event_id": probe_event_id,
        "event_type": "introspect.probe",
        "session_id": None,
        "pod_source": probe_pod,
        "signature_valid": True,
        "processing_ms": 12,
        "response_status": 200,
        "finalise_outcome": "introspect_only",
        "error_message": None,
        "stripe_created_at": None,
    }).execute().data[0]
    results["insert_roundtrip"] = {
        "ok": True,
        "id": inserted["id"],
        "received_at": inserted["received_at"],
    }
except Exception as e:
    results["insert_roundtrip"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

# 3. Unique (stripe_event_id, pod_source) enforcement — second identical
#    insert must fail; upsert (on_conflict) must succeed.
try:
    sb.table("webhook_deliveries_audit").insert({
        "stripe_event_id": probe_event_id,
        "event_type": "introspect.probe",
        "pod_source": probe_pod,
        "signature_valid": True,
        "response_status": 200,
        "finalise_outcome": "introspect_only",
    }).execute()
    results["unique_rejects_duplicate"] = {"ok": False, "note": "second insert did NOT raise — constraint missing"}
except Exception as e:
    results["unique_rejects_duplicate"] = {"ok": True, "error_kind": type(e).__name__}

# 4. Upsert on the same (event_id, pod) collapses.
try:
    upserted = sb.table("webhook_deliveries_audit").upsert({
        "stripe_event_id": probe_event_id,
        "event_type": "introspect.probe",
        "pod_source": probe_pod,
        "signature_valid": True,
        "processing_ms": 42,
        "response_status": 200,
        "finalise_outcome": "introspect_only_updated",
    }, on_conflict="stripe_event_id,pod_source").execute().data[0]
    results["upsert_collapses"] = {
        "ok": True,
        "processing_ms_after": upserted["processing_ms"],
        "outcome_after": upserted["finalise_outcome"],
    }
except Exception as e:
    results["upsert_collapses"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

# 5. Clean up the introspect rows.
try:
    sb.table("webhook_deliveries_audit").delete().eq("stripe_event_id", probe_event_id).execute()
    results["cleanup"] = {"ok": True}
except Exception as e:
    results["cleanup"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

print(json.dumps(results, indent=2, default=str))
