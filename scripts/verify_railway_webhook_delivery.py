"""
Prove — or fail to prove — that Railway's webhook endpoint
we_1U6vR2EemFmdl6rE2LcEO13S received an actual 200 response from
Stripe for the fresh test checkout.

Public Stripe API historically only exposes:
  - Event.pending_webhooks (count of endpoints not yet done)
  - not per-endpoint success/failure

We'll try several approaches:
  1. WebhookEndpoint.retrieve() — dump every attribute
  2. List recent events since the endpoint's creation timestamp and show
     their pending_webhooks and how quickly it went to 0
  3. Raw HTTP: /v1/webhook_endpoints/{id} and any undocumented sub-resources
     that might exist in the 2026-07-29.dahlia API version
  4. If available, the newer /v2/core/events delivery info

Print everything so the user can see the raw evidence.
"""
import json
import time
from datetime import datetime, timezone

import requests
import stripe
from dotenv import dotenv_values

env = dotenv_values("/app/backend/.env")
stripe.api_key = env["STRIPE_SECRET_KEY"]

RAILWAY_ID = "we_1U6vR2EemFmdl6rE2LcEO13S"
PREVIEW_ID = "we_1U4jtfEemFmdl6rEqcuUYuES"

print("=" * 90)
print("1) WebhookEndpoint.retrieve — every attribute Stripe returns")
print("=" * 90)
we = stripe.WebhookEndpoint.retrieve(RAILWAY_ID)
for k in sorted(we.keys()):
    print(f"  {k:22s} = {we[k]}")
print()

# Endpoint creation time — anything after this can only be delivered here.
we_created = we.created
print(f"Endpoint created at: {datetime.fromtimestamp(we_created, tz=timezone.utc).isoformat()}  (unix {we_created})")
print()

print("=" * 90)
print("2) Recent events since the endpoint was created (both types we subscribe to)")
print("=" * 90)
events = list(
    stripe.Event.list(
        types=["checkout.session.completed", "checkout.session.expired"],
        created={"gte": we_created},
        limit=50,
    ).auto_paging_iter()
)
print(f"Total events created after Railway endpoint went live: {len(events)}\n")

for ev in events:
    obj = ev.data.object
    age_s = int(time.time()) - ev.created
    print(
        f"- {ev.id}"
        f"\n    type            : {ev.type}"
        f"\n    created         : {datetime.fromtimestamp(ev.created, tz=timezone.utc).isoformat()}  ({age_s}s ago)"
        f"\n    pending_webhooks: {ev.pending_webhooks}  (# of endpoints not yet closed on delivery)"
        f"\n    session         : {obj.get('id')}"
        f"\n    payment_status  : {obj.get('payment_status')}  status: {obj.get('status')}"
        f"\n    customer_email  : {obj.get('customer_email')}"
        f"\n    metadata        : {dict(obj.get('metadata') or {})}"
    )
print()

print("=" * 90)
print("3) Raw HTTP: /v1/webhook_endpoints/{id} — look for undocumented delivery fields")
print("=" * 90)
r = requests.get(
    f"https://api.stripe.com/v1/webhook_endpoints/{RAILWAY_ID}",
    auth=(stripe.api_key, ""),
    headers={"Stripe-Version": we.api_version},
)
print(f"HTTP {r.status_code}")
print(json.dumps(r.json(), indent=2))
print()

print("=" * 90)
print("4) Try undocumented /v1/webhook_endpoints/{id}/deliveries and /events")
print("=" * 90)
for path in [
    f"/v1/webhook_endpoints/{RAILWAY_ID}/deliveries",
    f"/v1/webhook_endpoints/{RAILWAY_ID}/events",
    f"/v1/webhook_endpoints/{RAILWAY_ID}/attempts",
    f"/v1/webhook_endpoints/{RAILWAY_ID}/logs",
]:
    r = requests.get(
        f"https://api.stripe.com{path}",
        auth=(stripe.api_key, ""),
        headers={"Stripe-Version": we.api_version},
    )
    print(f"  GET {path}  ->  HTTP {r.status_code}")
    if r.status_code == 200:
        print(f"    body: {r.text[:400]}")
print()

print("=" * 90)
print("5) Try v2 API — newer surface may expose delivery attempts")
print("=" * 90)
for path in [
    f"/v2/core/event_destinations/{RAILWAY_ID}",
    f"/v2/core/event_destinations/{RAILWAY_ID}/events",
    "/v2/core/event_destinations",
    "/v2/core/events",
]:
    r = requests.get(
        f"https://api.stripe.com{path}",
        auth=(stripe.api_key, ""),
        headers={"Stripe-Version": we.api_version},
    )
    print(f"  GET {path}  ->  HTTP {r.status_code}")
    if r.status_code == 200:
        body = r.json()
        print(f"    body preview: {json.dumps(body, indent=2)[:800]}")
    elif r.status_code == 404:
        pass
    else:
        print(f"    body: {r.text[:400]}")
print()

print("=" * 90)
print("6) Interpretation of pending_webhooks for the most recent event")
print("=" * 90)
if events:
    latest = events[0]
    age_s = int(time.time()) - latest.created
    endpoints_subscribed = 2  # preview (all events) + railway (session events)
    if latest.type in ("checkout.session.completed", "checkout.session.expired"):
        print(
            f"Most recent event {latest.id} ({latest.type}):\n"
            f"  age              : {age_s}s\n"
            f"  pending_webhooks : {latest.pending_webhooks}\n"
            f"  endpoints subscribed to this type: 2 (preview '*' + Railway ['completed','expired'])\n"
        )
        if latest.pending_webhooks == 0:
            print("  -> pending_webhooks is 0. ALL subscribed endpoints closed delivery.")
            print("     Stripe's retry schedule for 4xx/5xx is ~1min, 5min, 30min, 1h, ...")
            print(f"     If pending_webhooks hit 0 within {age_s}s of event creation and NO retries had time to run,")
            print("     that's consistent with BOTH endpoints returning 2xx on the first attempt.")
            print("     ('Consistent with' — NOT proof; we still need per-endpoint status.)")
        else:
            print(f"  -> pending_webhooks > 0 ({latest.pending_webhooks}). At least one endpoint hasn't closed yet.")
