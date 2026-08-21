"""
Create a NEW Stripe webhook endpoint pointing at Railway.

Deliberately additive:
  - Does NOT touch the existing preview endpoint
  - Subscribes ONLY to checkout.session.completed + checkout.session.expired
    (matches what backend/booking.py branches on; matches the "don't
    over-subscribe" discipline from Step 4)

Prints the whsec_ so it can be pasted into Railway's STRIPE_WEBHOOK_SECRET.
"""
import stripe
from dotenv import dotenv_values

env = dotenv_values("/app/backend/.env")
stripe.api_key = env["STRIPE_SECRET_KEY"]

RAILWAY_URL = "https://flyboyvideography-production.up.railway.app/api/stripe/webhook"
ENABLED_EVENTS = ["checkout.session.completed", "checkout.session.expired"]

# Safety check 1: make sure we're in test mode.
assert env.get("STRIPE_MODE") == "test", f"STRIPE_MODE must be test, got {env.get('STRIPE_MODE')}"
assert stripe.api_key.startswith("sk_test_"), "Refusing to run: secret key is not a test key"

# Safety check 2: don't create a duplicate.
print("Existing endpoints on this account BEFORE creation:")
existing = list(stripe.WebhookEndpoint.list(limit=100).auto_paging_iter())
for we in existing:
    print(f"  id={we.id}  url={we.url}  status={we.status}  events={we.enabled_events}")
for we in existing:
    if we.url == RAILWAY_URL:
        print(f"\nERROR: an endpoint at {RAILWAY_URL} already exists (id={we.id}). Aborting to avoid dup.")
        raise SystemExit(1)

print(f"\nCreating NEW endpoint at {RAILWAY_URL} with events {ENABLED_EVENTS} ...")
new_we = stripe.WebhookEndpoint.create(
    url=RAILWAY_URL,
    enabled_events=ENABLED_EVENTS,
    description="Railway production backend (2026-02 cutover). Dual-delivery with preview endpoint during 24h validation window; preview will be disabled then deleted afterward.",
    api_version="2026-07-29.dahlia",  # match current preview endpoint's api_version to keep event shape identical
)

print("\n=== CREATED ===")
print(f"  id           : {new_we.id}")
print(f"  url          : {new_we.url}")
print(f"  status       : {new_we.status}")
print(f"  livemode     : {new_we.livemode}")
print(f"  enabled_events: {new_we.enabled_events}")
print(f"  api_version  : {new_we.api_version}")

# Signing secret is ONLY available on the create() response. If we lose it,
# we have to rotate via a separate reveal step. Print it clearly.
print(f"\n  SIGNING SECRET (paste into Railway env var STRIPE_WEBHOOK_SECRET):\n    {new_we.secret}\n")

print("Full endpoint list AFTER creation:")
for we in stripe.WebhookEndpoint.list(limit=100).auto_paging_iter():
    marker = "  <-- NEW" if we.id == new_we.id else ""
    print(f"  id={we.id}  url={we.url}  events={we.enabled_events}{marker}")
