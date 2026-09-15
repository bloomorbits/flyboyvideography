#!/usr/bin/env python3
"""Introspect Migration 017 (bunny_linked_at) against the LIVE DB.

Run AFTER applying supabase_migration_017_bunny_reconcile.sql in Supabase Studio,
BEFORE the dependent reconcile code is built. Confirms:
  1. deliverables.bunny_linked_at exists
  2. backfill applied — no Bunny-linked row is left with NULL bunny_linked_at
  3. cron_runs is reachable (reused with job_name='bunny_reconcile', no new table)

Usage:  cd /app/backend && python3 tests/introspect_017.py
"""
import os
from dotenv import load_dotenv

load_dotenv()
from supabase import create_client

url = os.environ.get("SUPABASE_URL")
key = (os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
       or os.environ.get("SUPABASE_KEY")
       or os.environ.get("SUPABASE_SERVICE_KEY"))
sb = create_client(url, key)

ok = True

# 1) column exists
try:
    sb.table("deliverables").select("id,bunny_video_guid,bunny_status,bunny_linked_at,created_at").limit(1).execute()
    print("[1] bunny_linked_at column: PRESENT ✅")
except Exception as e:
    ok = False
    print(f"[1] bunny_linked_at column: MISSING ❌  ({str(e)[:120]})")

# 2) backfill — linked rows must all have bunny_linked_at set
try:
    linked = sb.table("deliverables").select("id,bunny_linked_at").not_.is_("bunny_video_guid", "null").execute().data or []
    missing = [r["id"] for r in linked if not r.get("bunny_linked_at")]
    if missing:
        ok = False
        print(f"[2] backfill: {len(missing)} linked row(s) still NULL ❌  {missing[:5]}")
    else:
        print(f"[2] backfill: all {len(linked)} Bunny-linked row(s) have bunny_linked_at ✅")
except Exception as e:
    ok = False
    print(f"[2] backfill check FAILED ❌ ({str(e)[:120]})")

# 3) cron_runs reachable (reused, not a new table)
try:
    sb.table("cron_runs").select("id,job_name").limit(1).execute()
    print("[3] cron_runs reachable (will reuse job_name='bunny_reconcile') ✅")
except Exception as e:
    ok = False
    print(f"[3] cron_runs check FAILED ❌ ({str(e)[:120]})")

print("\nRESULT:", "READY — build the reconcile code" if ok else "NOT READY — fix the above first")
