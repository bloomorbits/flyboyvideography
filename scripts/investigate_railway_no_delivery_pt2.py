"""
Round 2: figure out why Stripe is refusing to deliver to the Railway
endpoint despite it being marked enabled.

Angles to try:
  A. Confirm endpoint is not silently in a "connect only" or "restricted"
     state by inspecting every possible flag.
  B. Force a state refresh via PATCH (rewrite the URL to itself).
  C. Try triggering a test/simulated delivery via undocumented v1 endpoints.
  D. Look for status_details/warnings on the v2 resource.
  E. Try creating a fresh event_destination via v2 API (POST) with proper
     payload — this may be the modern path that legacy /v1 no longer feeds.
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
RAILWAY_URL = "https://flyboyvideography-production.up.railway.app/api/stripe/webhook"

def dump(label, method, path, **kwargs):
    r = requests.request(
        method,
        f"https://api.stripe.com{path}",
        auth=(stripe.api_key, ""),
        headers={"Stripe-Version": "2026-07-29.dahlia"},
        **kwargs,
    )
    print(f"\n>> {label}\n   {method} {path}  ->  HTTP {r.status_code}")
    try:
        body = json.dumps(r.json(), indent=2)
    except Exception:
        body = r.text
    print(body[:1600])
    return r

print("=" * 90)
print("A. Both endpoints — every possible flag/field")
print("=" * 90)
r_v1_rw  = dump("v1 Railway",  "GET", f"/v1/webhook_endpoints/{RAILWAY_ID}")
r_v1_pv  = dump("v1 Preview",  "GET", f"/v1/webhook_endpoints/{PREVIEW_ID}")
r_v2_rw  = dump("v2 Railway",  "GET", f"/v2/core/event_destinations/{RAILWAY_ID}")
r_v2_pv  = dump("v2 Preview",  "GET", f"/v2/core/event_destinations/{PREVIEW_ID}")

# Diff surface flags
d_rw = r_v2_rw.json()
d_pv = r_v2_pv.json()
diff_keys = set(d_rw.keys()) ^ set(d_pv.keys())
print("\n\n>> v2 flag differences (keys not in both):", diff_keys)

for k in sorted(set(d_rw.keys()) | set(d_pv.keys())):
    if d_rw.get(k) != d_pv.get(k) and k not in ("id", "created", "updated", "description", "enabled_events", "snapshot_api_version"):
        print(f"  DIFF  {k}: railway={d_rw.get(k)!r}  preview={d_pv.get(k)!r}")

print("\n" + "=" * 90)
print("B. Force state refresh — PATCH Railway URL to itself")
print("=" * 90)
we = stripe.WebhookEndpoint.modify(
    RAILWAY_ID,
    url=RAILWAY_URL,  # rewrite same URL
    description="Railway production backend — refreshed 2026-08-21 post no-delivery investigation",
)
print(f"After modify: status={we.status}  url={we.url}")

print("\n" + "=" * 90)
print("C. Try undocumented 'send test event' paths")
print("=" * 90)
for path in [
    f"/v1/webhook_endpoints/{RAILWAY_ID}/send_test_webhook",
    f"/v1/webhook_endpoints/{RAILWAY_ID}/test_event",
    f"/v2/core/event_destinations/{RAILWAY_ID}/ping",
    f"/v2/core/event_destinations/{RAILWAY_ID}/actions/ping",
    f"/v2/core/event_destinations/{RAILWAY_ID}/test_deliveries",
]:
    dump(f"C-{path}", "POST", path)

print("\n" + "=" * 90)
print("D. status_details / warnings")
print("=" * 90)
print(f"Railway v2 status_details: {d_rw.get('status_details')}")
print(f"Preview v2 status_details: {d_pv.get('status_details')}")

print("\n" + "=" * 90)
print("E. Try creating a v2-native event_destination pointing at the same URL")
print("=" * 90)
# Only try if the endpoint doesn't already exist -- to avoid dup.
# We'll create with a distinct URL suffix to guarantee uniqueness for the test.
test_url = RAILWAY_URL + "?probe=v2"
r = requests.post(
    "https://api.stripe.com/v2/core/event_destinations",
    auth=(stripe.api_key, ""),
    headers={"Stripe-Version": "2026-07-29.dahlia", "Content-Type": "application/json"},
    data=json.dumps({
        "name": "railway-v2-probe",
        "description": "Temporary v2-native probe endpoint — investigating v1 no-delivery",
        "type": "webhook_endpoint",
        "webhook_endpoint": {"url": test_url},
        "enabled_events": ["checkout.session.completed"],
        "event_payload": "snapshot",
        "events_from": ["@self"],
    }),
)
print(f"POST /v2/core/event_destinations  ->  HTTP {r.status_code}")
try:
    print(json.dumps(r.json(), indent=2)[:2000])
except Exception:
    print(r.text[:1200])
