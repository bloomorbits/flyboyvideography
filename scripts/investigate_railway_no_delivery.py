"""
Emergency investigation: why is the Railway webhook endpoint receiving
zero deliveries despite being registered as enabled with correct URL
and events?

1. Pull most recent checkout.session.completed events (there should be a
   brand-new one from the user's just-completed test checkout).
2. For each recent event: show pending_webhooks + timestamps.
3. Look at Supabase for the finalized booking of the newest session.
4. Investigate the Railway endpoint's actual state via BOTH v1 and v2
   API surfaces — the v2 view earlier showed `webhook_endpoint.url=null`
   which is highly suspicious.
5. Full raw dumps.
"""
import json
import time
from datetime import datetime, timezone

import requests
import stripe
from dotenv import dotenv_values
from supabase import create_client

env = dotenv_values("/app/backend/.env")
stripe.api_key = env["STRIPE_SECRET_KEY"]
RAILWAY_ID = "we_1U6vR2EemFmdl6rE2LcEO13S"
PREVIEW_ID = "we_1U4jtfEemFmdl6rEqcuUYuES"

now = int(time.time())
print(f"Now: {datetime.fromtimestamp(now, tz=timezone.utc).isoformat()}  (unix {now})")
print()

# ---------------------------------------------------------------------------
# 1. Most recent events (all types) — 15 min window
# ---------------------------------------------------------------------------
print("=" * 90)
print("1) Most recent events on the account, past 15 minutes, ALL types")
print("=" * 90)
recent = list(stripe.Event.list(created={"gte": now - 900}, limit=100).auto_paging_iter())
print(f"Total events past 15 minutes: {len(recent)}\n")
for ev in recent[:20]:
    obj = ev.data.object if hasattr(ev.data, "object") else {}
    age = now - ev.created
    print(
        f"- {ev.id}  ({ev.type})"
        f"\n    created         : {datetime.fromtimestamp(ev.created, tz=timezone.utc).isoformat()}  ({age}s ago)"
        f"\n    pending_webhooks: {ev.pending_webhooks}"
        f"\n    session/object  : {obj.get('id') if isinstance(obj, dict) else getattr(obj, 'id', None)}"
    )
print()

# ---------------------------------------------------------------------------
# 2. Latest checkout.session.completed — is there a new one from the user's fresh checkout?
# ---------------------------------------------------------------------------
print("=" * 90)
print("2) Latest checkout.session.completed events (last 3)")
print("=" * 90)
completed = list(stripe.Event.list(type="checkout.session.completed", limit=3).auto_paging_iter())
newest_completed = completed[0] if completed else None
for ev in completed:
    obj = ev.data.object
    print(f"- {ev.id}")
    print(f"    created         : {datetime.fromtimestamp(ev.created, tz=timezone.utc).isoformat()}")
    print(f"    pending_webhooks: {ev.pending_webhooks}")
    print(f"    session         : {obj.get('id')}")
    print(f"    email           : {obj.get('customer_email')}")
    print(f"    metadata        : {dict(obj.get('metadata') or {})}")
print()

# ---------------------------------------------------------------------------
# 3. Supabase state for the newest session
# ---------------------------------------------------------------------------
if newest_completed:
    session_id = newest_completed.data.object.id
    print("=" * 90)
    print(f"3) Supabase state for newest session {session_id}")
    print("=" * 90)
    sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])
    bk = sb.table("bookings").select("*").eq("stripe_session_id", session_id).limit(1).execute().data
    if bk:
        b = bk[0]
        print(f"  booking.id             : {b['id']}")
        print(f"  booking.deposit_paid_at: {b.get('deposit_paid_at')}")
        print(f"  booking.created_at     : {b.get('created_at')}")
        finalized_lag_ms = None
        if b.get("created_at"):
            b_created = datetime.fromisoformat(b["created_at"].replace("Z", "+00:00"))
            finalized_lag_ms = int((b_created.timestamp() - newest_completed.created) * 1000)
            print(f"  finalization lag (created_at - event.created): {finalized_lag_ms} ms")
    else:
        print("  NO booking row -- not yet finalized (webhook may not have fired)")

    tx = sb.table("payment_transactions").select("*").eq("session_id", session_id).limit(1).execute().data
    if tx:
        print(f"  payment_transactions.payment_status: {tx[0]['payment_status']}")
        print(f"  payment_transactions.updated_at    : {tx[0].get('updated_at')}")

# ---------------------------------------------------------------------------
# 4. Railway endpoint state — v1 vs v2 API surfaces (v2 showed nulls earlier!)
# ---------------------------------------------------------------------------
print()
print("=" * 90)
print("4) Railway endpoint state: v1 vs v2 API surfaces")
print("=" * 90)

print("\n[v1] GET /v1/webhook_endpoints/" + RAILWAY_ID)
r1 = requests.get(
    f"https://api.stripe.com/v1/webhook_endpoints/{RAILWAY_ID}",
    auth=(stripe.api_key, ""),
    headers={"Stripe-Version": "2026-07-29.dahlia"},
)
print(f"HTTP {r1.status_code}")
print(json.dumps(r1.json(), indent=2))

print("\n[v2] GET /v2/core/event_destinations/" + RAILWAY_ID)
r2 = requests.get(
    f"https://api.stripe.com/v2/core/event_destinations/{RAILWAY_ID}",
    auth=(stripe.api_key, ""),
    headers={"Stripe-Version": "2026-07-29.dahlia"},
)
print(f"HTTP {r2.status_code}")
print(json.dumps(r2.json(), indent=2))

# Compare to preview endpoint via v2 to see if the null-URL pattern is the same
print("\n[v2] GET /v2/core/event_destinations/" + PREVIEW_ID + "  (preview, for comparison)")
r3 = requests.get(
    f"https://api.stripe.com/v2/core/event_destinations/{PREVIEW_ID}",
    auth=(stripe.api_key, ""),
    headers={"Stripe-Version": "2026-07-29.dahlia"},
)
print(f"HTTP {r3.status_code}")
print(json.dumps(r3.json(), indent=2))

# ---------------------------------------------------------------------------
# 5. Preview backend log — look for the new session_id / event_id anywhere
# ---------------------------------------------------------------------------
print()
print("=" * 90)
print("5) Preview backend log: hit count since 15 min ago")
print("=" * 90)
import subprocess
res = subprocess.run(
    ["grep", "-c", 'POST /api/stripe/webhook HTTP/1.1" 200', "/var/log/supervisor/backend.out.log"],
    capture_output=True, text=True,
)
print(f"Total 200s (all-time in this log file): {res.stdout.strip()}")
res = subprocess.run(
    ["tail", "-n", "20", "/var/log/supervisor/backend.out.log"],
    capture_output=True, text=True,
)
print("Preview log — last 20 lines:")
print(res.stdout)
