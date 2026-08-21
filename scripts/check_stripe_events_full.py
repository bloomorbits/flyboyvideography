"""
Deeper sweep: pull ALL checkout.session.expired events on the account (test mode),
show which webhook endpoint they were delivered to, and confirm pending_webhooks
status for every one. Also lists all webhook endpoints (regardless of status).
"""
import json
from collections import Counter
from datetime import datetime, timezone

import stripe
from dotenv import dotenv_values

env = dotenv_values("/app/backend/.env")
stripe.api_key = env["STRIPE_SECRET_KEY"]

print(f"Mode: {env.get('STRIPE_MODE')}  Account: {env.get('STRIPE_ACCOUNT_ID')}")
print("=" * 90)

# 1. ALL webhook endpoints (including disabled)
print("ALL webhook endpoints on this account (any status):")
endpoints = list(stripe.WebhookEndpoint.list(limit=100).auto_paging_iter())
for we in endpoints:
    print(
        f"  id={we.id}\n"
        f"    url            : {we.url}\n"
        f"    status         : {we.status}\n"
        f"    livemode       : {we.livemode}\n"
        f"    enabled_events : {we.enabled_events}\n"
        f"    created        : {datetime.fromtimestamp(we.created, tz=timezone.utc).isoformat()}\n"
        f"    description    : {we.description}\n"
    )
print(f"Total endpoints on this test account: {len(endpoints)}")
print("=" * 90)

# 2. ALL checkout.session.expired events (all time in test mode; usually <1000)
print("\nScanning ALL checkout.session.expired events (test mode)...")
events = list(
    stripe.Event.list(type="checkout.session.expired", limit=100).auto_paging_iter()
)
print(f"Total: {len(events)}\n")

# 3. Group by pending_webhooks and by created date (UTC day)
by_pending = Counter()
by_day = Counter()
for ev in events:
    by_pending[ev.pending_webhooks] += 1
    day = datetime.fromtimestamp(ev.created, tz=timezone.utc).strftime("%Y-%m-%d")
    by_day[day] += 1

print("pending_webhooks distribution:")
for pw, c in sorted(by_pending.items()):
    print(f"  pending_webhooks={pw}  ->  {c} event(s)")

print("\nEvents grouped by UTC day (desc by count):")
for day, c in sorted(by_day.items(), key=lambda x: x[0], reverse=True):
    print(f"  {day}  ->  {c} event(s)")

# 4. Focus: any event with pending_webhooks > 0 (still-pending or failed?)
still_pending = [e for e in events if e.pending_webhooks > 0]
print(f"\nEvents with pending_webhooks > 0: {len(still_pending)}")
for e in still_pending[:5]:
    print(f"  {e.id}  pending={e.pending_webhooks}  created={datetime.fromtimestamp(e.created, tz=timezone.utc).isoformat()}")

# 5. Show the 8 most recent expired events with key fields (this matches the "8 failed" list feel)
print("\n=== Most recent 8 checkout.session.expired events ===")
for e in events[:8]:
    created_iso = datetime.fromtimestamp(e.created, tz=timezone.utc).isoformat()
    obj = e.data.object
    print(
        f"- {e.id}"
        f"\n    created         : {created_iso}"
        f"\n    pending_webhooks: {e.pending_webhooks}"
        f"\n    session         : {obj.get('id')}"
        f"\n    email           : {obj.get('customer_email')}"
        f"\n    metadata        : {obj.get('metadata')}"
        f"\n    livemode        : {e.livemode}"
    )

# 6. Dump full JSON for exactly 3 of the most recent expired events to a file
out_path = "/app/scripts/stripe_expired_events_raw.json"
with open(out_path, "w") as f:
    json.dump([e.to_dict() for e in events[:3]], f, indent=2, default=str)
print(f"\nWrote raw JSON for 3 events to {out_path}")
