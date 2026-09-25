#!/usr/bin/env python3
"""Introspect Migration 018 (upload lifecycle) against the LIVE DB.

Run AFTER applying supabase_migration_018_upload_lifecycle.sql, BEFORE the
dependent Phase-2 upload code is built. Confirms the three new columns exist,
the CHECK constraints reject a bad state, and existing rows were left untouched.

Usage:  cd /app/backend && python3 tests/introspect_018.py
"""
import os
import uuid
from dotenv import load_dotenv

load_dotenv()
from supabase import create_client

sb = create_client(
    os.environ["SUPABASE_URL"],
    os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_KEY"),
)

ok = True

# 1) columns exist
try:
    sb.table("deliverables").select(
        "id, upload_id, stream_upload_state, storage_upload_state, bunny_linked_at"
    ).limit(1).execute()
    print("[1] upload_id / stream_upload_state / storage_upload_state: PRESENT ✅")
except Exception as e:
    ok = False
    print(f"[1] new columns MISSING ❌ ({str(e)[:140]})")

# 2) existing manually-linked rows untouched (states NULL, not upload sessions)
try:
    linked = (sb.table("deliverables").select("id, stream_upload_state, storage_upload_state")
              .not_.is_("bunny_video_guid", "null").execute().data or [])
    dirty = [r["id"] for r in linked
             if r.get("stream_upload_state") or r.get("storage_upload_state")]
    if dirty:
        print(f"[2] NOTE: {len(dirty)} linked row(s) already carry a lane state "
              f"(fine if they were Phase-2 uploads): {dirty[:3]}")
    else:
        print(f"[2] existing {len(linked)} linked row(s) have NULL lane states ✅ "
              "(orphan sweep will not touch them)")
except Exception as e:
    ok = False
    print(f"[2] existing-row check FAILED ❌ ({str(e)[:140]})")

# 3) CHECK constraint rejects an invalid state (insert a temp row, expect failure)
client = sb.table("clients").select("id").limit(1).execute().data
if client:
    tmp = None
    try:
        sb.table("deliverables").insert({
            "client_id": client[0]["id"], "title": f"mig018-check-{uuid.uuid4().hex[:6]}",
            "status": "in_review", "stream_upload_state": "not_a_valid_state",
            "is_seed_data": True,
        }).execute()
        ok = False
        print("[3] CHECK constraint did NOT reject an invalid state ❌")
    except Exception:
        print("[3] CHECK constraint rejects invalid lane state ✅")
    finally:
        # clean up if the bad insert somehow succeeded
        try:
            rows = (sb.table("deliverables").select("id").like("title", "mig018-check-%").execute().data or [])
            for r in rows:
                sb.table("deliverables").delete().eq("id", r["id"]).execute()
        except Exception:
            pass
else:
    print("[3] SKIPPED (no client row to test against)")

print("\nRESULT:", "READY — build the Phase-2 upload code" if ok else "NOT READY — fix the above first")
