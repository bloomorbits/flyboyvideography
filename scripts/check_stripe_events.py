"""
Pull raw Stripe event data for the 8/17 "failed" checkout.session.expired
deliveries so we can visually confirm pending_webhooks == 0 and there's no
actual data loss before retiring the preview webhook endpoint.

Reads STRIPE_SECRET_KEY from /app/backend/.env.
"""
import json
import os
import sys
from datetime import datetime, timezone

import stripe
from dotenv import dotenv_values

ENV_PATH = "/app/backend/.env"
env = dotenv_values(ENV_PATH)
stripe.api_key = env.get("STRIPE_SECRET_KEY")
if not stripe.api_key:
    print("STRIPE_SECRET_KEY missing from", ENV_PATH, file=sys.stderr)
    sys.exit(1)

print(f"Mode: {env.get('STRIPE_MODE')}  Account: {env.get('STRIPE_ACCOUNT_ID')}")
print("-" * 80)

# 1. List webhook endpoints so we know which one is Railway
print("Webhook endpoints on this account:")
for we in stripe.WebhookEndpoint.list(limit=20).auto_paging_iter():
    print(f"  id={we.id}  url={we.url}  status={we.status}  enabled_events={len(we.enabled_events)}")
print("-" * 80)

# 2. Search checkout.session.expired events around 8/17.
# Try both 2025-08-17 and 2024-08-17 windows since handoff didn't specify year.
def dt(y, m, d, h=0):
    return int(datetime(y, m, d, h, tzinfo=timezone.utc).timestamp())

windows = [
    ("2025-08-17", dt(2025, 8, 16), dt(2025, 8, 19)),
    ("2024-08-17", dt(2024, 8, 16), dt(2024, 8, 19)),
]

all_matches = []
for label, gte, lt in windows:
    print(f"\nScanning checkout.session.expired events in window {label} ({gte}..{lt})")
    matches = []
    for ev in stripe.Event.list(
        type="checkout.session.expired",
        created={"gte": gte, "lt": lt},
        limit=100,
    ).auto_paging_iter():
        matches.append(ev)
    print(f"  found {len(matches)} events")
    all_matches.extend(matches)

if not all_matches:
    # Fallback: last 30 days of expired events, show most recent 8
    print("\nNo events in 8/17 windows. Fallback: latest 8 checkout.session.expired events overall")
    for ev in stripe.Event.list(type="checkout.session.expired", limit=8).auto_paging_iter():
        all_matches.append(ev)

# 3. Print raw JSON for up to 3 events, focused on pending_webhooks + request + delivery
print("\n" + "=" * 80)
print("RAW EVENT DUMPS (first 3):")
print("=" * 80)

for ev in all_matches[:3]:
    raw = ev.to_dict_recursive() if hasattr(ev, "to_dict_recursive") else dict(ev)
    created_iso = datetime.fromtimestamp(ev["created"], tz=timezone.utc).isoformat()
    print(f"\n--- Event {ev['id']} ---")
    print(f"  type            : {ev['type']}")
    print(f"  created         : {created_iso}  (unix {ev['created']})")
    print(f"  pending_webhooks: {ev.get('pending_webhooks')}")
    print(f"  livemode        : {ev.get('livemode')}")
    print(f"  api_version     : {ev.get('api_version')}")
    print(f"  request         : {ev.get('request')}")
    obj = raw.get("data", {}).get("object", {})
    print(f"  session.id      : {obj.get('id')}")
    print(f"  session.status  : {obj.get('status')}")
    print(f"  session.payment_status: {obj.get('payment_status')}")
    print(f"  session.expires_at    : {obj.get('expires_at')}")
    print(f"  session.metadata      : {obj.get('metadata')}")
    print("  --- full raw JSON follows ---")
    print(json.dumps(raw, indent=2, default=str))

# 4. Summary of pending_webhooks across ALL matches so we can prove none are still pending
print("\n" + "=" * 80)
print("PENDING_WEBHOOKS SUMMARY across all matched events:")
print("=" * 80)
pending_counts = {}
for ev in all_matches:
    pw = ev.get("pending_webhooks", 0)
    pending_counts[pw] = pending_counts.get(pw, 0) + 1
for pw, count in sorted(pending_counts.items()):
    print(f"  pending_webhooks = {pw}  ->  {count} event(s)")

print(f"\nTotal events inspected: {len(all_matches)}")
print("If all pending_webhooks == 0, Stripe considers delivery closed (success or given up).")
