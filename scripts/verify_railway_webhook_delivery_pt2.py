"""
Last-mile attempts to attribute the just-completed checkout's webhook
delivery to Railway vs preview:

  (a) Try undocumented Stripe endpoints that might expose per-endpoint
      delivery attempts or trigger a targeted test delivery.
  (b) Read the finalized booking row from Supabase and print its
      deposit_paid_at timestamp — compare to the checkout.session.completed
      event's `created` (16:48:53 UTC). Small clock diff between preview
      and Railway backends may be visible.
"""
import os
import json
import requests
import stripe
from dotenv import dotenv_values
from supabase import create_client

env = dotenv_values("/app/backend/.env")
stripe.api_key = env["STRIPE_SECRET_KEY"]

RAILWAY_ID = "we_1U6vR2EemFmdl6rE2LcEO13S"
SESSION_ID = "cs_test_a1CrFjsb8fYS4LnTGhkTaRFEtdIzSmzoZSqhJqvfelNjHLg3F354yB2lSy"
EVENT_ID = "evt_1U6vcfEemFmdl6rEAEKzsJFC"

# (a) Undocumented paths -- expanded set
print("=" * 90)
print("(a) Try more Stripe API paths for per-endpoint delivery visibility")
print("=" * 90)
paths = [
    ("POST", f"/v1/webhook_endpoints/{RAILWAY_ID}/test"),
    ("POST", f"/v1/webhook_endpoints/{RAILWAY_ID}/test_delivery"),
    ("POST", f"/v1/webhook_endpoints/{RAILWAY_ID}/deliveries"),
    ("GET",  f"/v1/webhook_endpoints/{RAILWAY_ID}/summary"),
    ("GET",  f"/v1/webhook_endpoints/{RAILWAY_ID}/messages"),
    ("GET",  f"/v1/events/{EVENT_ID}/attempts"),
    ("GET",  f"/v1/events/{EVENT_ID}/deliveries"),
    ("GET",  f"/v1/events/{EVENT_ID}/webhook_deliveries"),
    ("POST", f"/v1/events/{EVENT_ID}/retry"),  # dashboard-only "resend" -- may exist as API
    ("POST", f"/v1/events/{EVENT_ID}/replay"),
]
for method, path in paths:
    r = requests.request(
        method,
        f"https://api.stripe.com{path}",
        auth=(stripe.api_key, ""),
        headers={"Stripe-Version": "2026-07-29.dahlia"},
        data={"webhook_endpoint": RAILWAY_ID} if method == "POST" else None,
    )
    body = r.text[:400] if r.status_code != 200 else json.dumps(r.json(), indent=2)[:600]
    print(f"  {method:4s} {path}  ->  HTTP {r.status_code}")
    if r.status_code not in (404,):
        print(f"    body: {body}")

# (b) Look at the finalized booking row
print()
print("=" * 90)
print("(b) The Supabase row for this checkout")
print("=" * 90)
sb = create_client(env["SUPABASE_URL"], env["SUPABASE_SERVICE_ROLE_KEY"])

bk = sb.table("bookings").select("*").eq("stripe_session_id", SESSION_ID).limit(1).execute().data
if not bk:
    print("  NO booking row found for session -- something's wrong")
else:
    b = bk[0]
    print(f"  booking.id             : {b['id']}")
    print(f"  booking.event_date     : {b['event_date']}")
    print(f"  booking.deposit_paid_at: {b.get('deposit_paid_at')}")
    print(f"  booking.created_at     : {b.get('created_at')}")
    print(f"  booking.updated_at     : {b.get('updated_at')}")

tx = sb.table("payment_transactions").select("*").eq("session_id", SESSION_ID).limit(1).execute().data
if tx:
    t = tx[0]
    print(f"\n  payment_transactions.id           : {t['id']}")
    print(f"  payment_transactions.status       : {t['status']}")
    print(f"  payment_transactions.payment_status: {t['payment_status']}")
    print(f"  payment_transactions.created_at    : {t.get('created_at')}")
    print(f"  payment_transactions.updated_at    : {t.get('updated_at')}")

intent = sb.table("booking_intents").select("*").eq("session_id", SESSION_ID).limit(1).execute().data
if intent:
    i = intent[0]
    print(f"\n  booking_intents.id          : {i['id']}")
    print(f"  booking_intents.status      : {i['status']}")
    print(f"  booking_intents.updated_at  : {i.get('updated_at')}")
    print(f"  booking_intents.created_at  : {i.get('created_at')}")

# The event created time from Stripe
ev = stripe.Event.retrieve(EVENT_ID)
print(f"\n  Stripe event created       : {ev.created}  ({__import__('datetime').datetime.fromtimestamp(ev.created, tz=__import__('datetime').timezone.utc).isoformat()})")
print(f"  Stripe event pending_webhooks: {ev.pending_webhooks}")
