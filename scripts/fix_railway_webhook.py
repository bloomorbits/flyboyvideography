"""
Fix: delete the broken Railway endpoint (created with api_version set,
which put it in a delivery-inert state) and recreate it WITHOUT the
api_version parameter — matching the preview endpoint's config, which
demonstrably receives deliveries.

Also cleans up the v2 probe endpoint created during investigation.
"""
import stripe
from dotenv import dotenv_values

env = dotenv_values("/app/backend/.env")
stripe.api_key = env["STRIPE_SECRET_KEY"]

BROKEN_ID = "we_1U6vR2EemFmdl6rE2LcEO13S"       # created with api_version set
V2_PROBE_ID = "we_1U6w0YEemFmdl6rEGX0y681U"     # investigation probe
RAILWAY_URL = "https://flyboyvideography-production.up.railway.app/api/stripe/webhook"

assert env.get("STRIPE_MODE") == "test", "safety: test mode only"
assert stripe.api_key.startswith("sk_test_"), "safety: test key only"

print("=" * 90)
print("1) Endpoints BEFORE fix")
print("=" * 90)
for we in stripe.WebhookEndpoint.list(limit=100).auto_paging_iter():
    print(f"  id={we.id}  url={we.url}  api_version={we.api_version}  status={we.status}  events={we.enabled_events}")

print("\n2) Deleting broken Railway endpoint:", BROKEN_ID)
stripe.WebhookEndpoint.delete(BROKEN_ID)
print("   deleted.")

print("\n3) Deleting v2 investigation probe:", V2_PROBE_ID)
stripe.WebhookEndpoint.delete(V2_PROBE_ID)
print("   deleted.")

print("\n4) Recreating Railway endpoint WITHOUT api_version param")
new_we = stripe.WebhookEndpoint.create(
    url=RAILWAY_URL,
    enabled_events=["checkout.session.completed", "checkout.session.expired"],
    description="Railway production backend (2026-02 cutover). Recreated 2026-08-21 without api_version param — the first create used api_version='2026-07-29.dahlia' which put the endpoint into a delivery-inert state (accepts writes, status=enabled, but Stripe routes zero events to it). Preview endpoint's api_version=null and delivers fine; matching that config here.",
)

print(f"\n   NEW endpoint id       : {new_we.id}")
print(f"   url                   : {new_we.url}")
print(f"   api_version           : {new_we.api_version}  (should be None/null)")
print(f"   status                : {new_we.status}")
print(f"   enabled_events        : {new_we.enabled_events}")
print(f"\n   >>> NEW SIGNING SECRET (paste into Railway STRIPE_WEBHOOK_SECRET):")
print(f"        {new_we.secret}")

print("\n5) Endpoints AFTER fix")
print("=" * 90)
for we in stripe.WebhookEndpoint.list(limit=100).auto_paging_iter():
    marker = "  <-- NEW" if we.id == new_we.id else ""
    print(f"  id={we.id}  url={we.url}  api_version={we.api_version}  status={we.status}  events={we.enabled_events}{marker}")
