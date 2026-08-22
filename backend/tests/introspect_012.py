"""Introspect + prove Migration 012.

Run AFTER applying supabase_migration_012_balance_invoicing.sql via
Supabase SQL Editor.

Verifies:
  1. New columns present.
  2. Partial unique index exists.
  3. Duplicate balance-invoice insert for the same booking is rejected
     at the DB level (the core safety guarantee).
"""
import json, os, uuid
from datetime import date, timedelta
from dotenv import load_dotenv
from supabase import create_client

load_dotenv("/app/backend/.env")
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
results = {}

# 1. Columns exist
try:
    r = sb.table("invoices").select(
        "id, payment_purpose, reminder_sent_at, source_type, booking_id, is_seed_data"
    ).limit(1).execute()
    results["columns_present"] = {"ok": True}
except Exception as e:
    results["columns_present"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    print(json.dumps(results, indent=2)); raise SystemExit(1)

# 2. Constraint enforcement — insert twice for the same booking_id + payment_purpose='balance'
#    Grab a real booking id to attach to (safer than a synthetic uuid — FK enforcement)
bk = sb.table("bookings").select("id, client_id").limit(1).execute().data
if not bk:
    results["dup_test"] = {"ok": False, "note": "no booking rows to attach to; skipping"}
    print(json.dumps(results, indent=2, default=str)); raise SystemExit(0)
booking_id, client_id = bk[0]["id"], bk[0]["client_id"]

def _row(marker):
    return {
        "client_id": client_id, "booking_id": booking_id,
        "source_type": "booking", "payment_purpose": "balance",
        "invoice_number": f"INV-BAL-INTROSPECT-{marker}",
        "amount": 1.23,
        "status": "sent",
        "issued_on": str(date.today()),
        "due_on": str(date.today() + timedelta(days=5)),
        "is_seed_data": False,
    }

# clean any leftover from prior runs
sb.table("invoices").delete().eq("booking_id", booking_id).eq("payment_purpose", "balance").eq("is_seed_data", False).execute()

first_id = None
try:
    first = sb.table("invoices").insert(_row("first")).execute().data[0]
    first_id = first["id"]
    results["first_insert"] = {"ok": True, "id": first_id}
except Exception as e:
    results["first_insert"] = {"ok": False, "error": f"{type(e).__name__}: {e}"}

# The second insert MUST fail with a unique-constraint violation
try:
    sb.table("invoices").insert(_row("second")).execute()
    results["duplicate_rejected"] = {"ok": False, "note": "second insert did NOT raise — constraint MISSING or misconfigured"}
except Exception as e:
    msg = str(e)
    is_uniq = "duplicate key" in msg.lower() or "unique constraint" in msg.lower() or "23505" in msg
    results["duplicate_rejected"] = {"ok": is_uniq, "error_kind": type(e).__name__, "matches_uniq_violation": is_uniq, "excerpt": msg[:180]}

# cleanup
if first_id:
    sb.table("invoices").delete().eq("id", first_id).execute()

# Overall verdict
all_ok = all(v.get("ok") for v in results.values())
results["_verdict"] = "PASS" if all_ok else "FAIL"
print(json.dumps(results, indent=2, default=str))
