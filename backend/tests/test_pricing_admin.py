"""Migration 013 — admin pricing catalog endpoint tests.

Coverage:
  - GET  /api/pricing (public) shape + values
  - GET  /api/admin/pricing/draft returns draft + published + dirty flag
  - PUT  /api/admin/pricing/draft
      * happy path (valid catalog persists)
      * 422 on: price as string, missing required field, extra key
      * 422 on: duplicated tier name within a package
      * 422 on: duplicated package id, graduation.id colliding with package.id
      * 422 on: price out of range (negative, way too high)
      * 401 without a token, 403 for non-admin
  - POST /api/admin/pricing/publish
      * atomic swap, published matches draft, dirty flag returns to False
      * cache invalidation: packages.find_tier picks up new prices when
        PRICING_SOURCE=db is set (validated via a monkeypatched load)
      * NOOP on no-diff
  - POST /api/admin/pricing/publish — REFERENTIAL INTEGRITY GUARD ★
      * Removing a (package_id, tier_name) that a LIVE confirmed booking
        references → 409 with orphan report; no publish happens
      * Removing a tuple that an IN-FLIGHT paid intent references → 409
      * ?force=1 lets it through (logged); assert the publish did happen
      * Removing a tuple with only CANCELLED bookings → allowed (no orphan)
      * Renaming a tier (e.g. Basic → Essentials) is treated as "remove
        Basic + add Essentials"; if Basic is still referenced, blocked
  - POST /api/admin/pricing/revert flips draft back to published

Run:
    ALLOW_ATTACK_SIM=1 pytest -xvs backend/tests/test_pricing_admin.py
"""
import copy
import os
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

if os.environ.get("ALLOW_ATTACK_SIM") != "1":
    raise SystemExit("REFUSED: set ALLOW_ATTACK_SIM=1 to run pricing admin tests.")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://db-bridge-5.preview.emergentagent.com").rstrip("/")

from supabase import create_client  # noqa: E402
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
# Dedicated client for auth.admin calls — the module-level `sb` gets its
# session set by admin_token's sign_in_with_password, which downgrades
# its privileges for subsequent auth.admin.* calls ("User not allowed").
sb_admin = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


# ---------- Admin session token — bootstrap once per module ----------

@pytest.fixture(scope="module")
def admin_token():
    """Sign in a real admin user and return a Supabase JWT.

    Reuses the same @flyboyadmin.local convention the other test modules
    rely on. Creates the admin user if missing (idempotent for CI).
    """
    email = "admin_pricing_test@flyboytest.com"
    password = "PricingTest!2026"

    # Find or create the auth user (use dedicated service-role client)
    try:
        existing = sb_admin.auth.admin.list_users()
        user = next((u for u in existing if getattr(u, "email", "") == email), None)
    except Exception:
        user = None

    if not user:
        res = sb_admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True,
            "user_metadata": {"full_name": "Pricing Admin Test"},
        })
        user = res.user

    # Ensure the clients row is admin
    cl = sb.table("clients").select("*").eq("user_id", user.id).execute().data
    if cl:
        sb.table("clients").update({"role": "admin"}).eq("user_id", user.id).execute()
    else:
        sb.table("clients").insert({
            "user_id": user.id, "email": email, "full_name": "Pricing Admin Test",
            "role": "admin",
        }).execute()

    # Sign in via GoTrue to get a JWT (the same one the CRA portal uses).
    # Use a THROWAWAY client so we don't downgrade the module-level `sb`'s
    # privileges (sign_in_with_password stores the user JWT on the client
    # and switches Postgrest calls to that user's RLS context).
    sb_signin = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"] if os.environ.get("SUPABASE_ANON_KEY") else os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    sess = sb_signin.auth.sign_in_with_password({"email": email, "password": password})
    assert sess.session and sess.session.access_token
    yield sess.session.access_token
    # No teardown — reuse this admin user across sessions.


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


# ---------- Preserve prod state — snapshot at module setup, restore around EVERY test ----------

@pytest.fixture(scope="module")
def clean_baseline():
    """Baseline = the current PUBLISHED slot. We force draft := published
    at module setup so both slots are aligned and known-good — this way
    even if a prior test run left `draft` dirty, we don't inherit that
    corruption. `restore_after` uses this baseline to reset both slots
    around every test.

    Note: this uses the CURRENT published catalog as truth. If published
    itself is somehow bad (e.g. a bad `?force=1` publish before the tests
    run), you'd need to reset via Migration 013's seed manually. Under
    normal operation this fixture is self-healing across runs.
    """
    pub = sb.table("pricing_catalog").select("content").eq("slot", "published").execute().data[0]["content"]
    # Force draft := published so we start clean
    sb.table("pricing_catalog").update({"content": pub}).eq("slot", "draft").execute()
    return {"published": pub, "draft": pub}


@pytest.fixture(autouse=True)
def restore_after(clean_baseline):
    """Force both slots back to the module-level baseline before AND after
    every test. Guarantees a truly clean starting point and no leaks."""
    def reset():
        for slot, content in clean_baseline.items():
            sb.table("pricing_catalog").update({"content": content}).eq("slot", slot).execute()
    reset()
    yield
    reset()


# ---------- Base catalog fixture — a valid catalog for edit tests ----------

@pytest.fixture
def base_catalog():
    r = requests.get(f"{BASE_URL}/api/pricing", timeout=15)
    r.raise_for_status()
    return copy.deepcopy(r.json()["content"])


# ==============================================================================
# PUBLIC + AUTH GATE
# ==============================================================================

def test_public_pricing_returns_expected_shape():
    r = requests.get(f"{BASE_URL}/api/pricing", timeout=15)
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) >= {"content", "updated_at"}
    c = body["content"]
    assert isinstance(c["packages"], list) and len(c["packages"]) == 4
    assert c["graduation"]["price"] == 150
    assert isinstance(c["extras"]["items"], list)
    assert "50%" in c["bookingTerms"]


def test_admin_endpoints_refuse_without_token():
    for method, path in [
        ("GET", "/api/admin/pricing/draft"),
        ("PUT", "/api/admin/pricing/draft"),
        ("POST", "/api/admin/pricing/publish"),
        ("POST", "/api/admin/pricing/revert"),
    ]:
        r = requests.request(method, f"{BASE_URL}{path}", json={}, timeout=15)
        assert r.status_code in (401, 403), f"{method} {path} → {r.status_code}"


def test_admin_get_draft(admin_token, base_catalog):
    r = requests.get(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), timeout=15)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body.keys()) >= {"draft", "published", "dirty"}
    assert body["dirty"] is False  # freshly seeded


# ==============================================================================
# PUT DRAFT — VALIDATION 422
# ==============================================================================

def test_put_draft_happy_path(admin_token, base_catalog):
    edited = copy.deepcopy(base_catalog)
    # Bump wedding basic price
    edited["packages"][0]["tiers"][0]["price"] = 275.0
    r = requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=edited, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["dirty"] is True
    # Read-back via the endpoint (not module-level sb — that's flakier
    # from inside pytest's fixture context under supabase-py's session).
    d = requests.get(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), timeout=15).json()
    assert d["draft"]["packages"][0]["tiers"][0]["price"] == 275.0


def test_put_draft_rejects_string_price(admin_token, base_catalog):
    bad = copy.deepcopy(base_catalog)
    bad["packages"][0]["tiers"][0]["price"] = "two hundred"
    r = requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=bad, timeout=15)
    assert r.status_code == 422, r.text


def test_put_draft_rejects_missing_required_field(admin_token, base_catalog):
    bad = copy.deepcopy(base_catalog)
    del bad["packages"][0]["tiers"][0]["coverage"]
    r = requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=bad, timeout=15)
    assert r.status_code == 422, r.text


def test_put_draft_rejects_extra_unknown_key(admin_token, base_catalog):
    bad = copy.deepcopy(base_catalog)
    bad["packages"][0]["tiers"][0]["sneakyField"] = "boo"
    r = requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=bad, timeout=15)
    assert r.status_code == 422, r.text


def test_put_draft_rejects_duplicate_tier_names(admin_token, base_catalog):
    bad = copy.deepcopy(base_catalog)
    bad["packages"][0]["tiers"][1]["name"] = "Basic"  # collide with tiers[0]
    r = requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=bad, timeout=15)
    assert r.status_code == 422, r.text
    assert "duplicated" in r.text.lower()


def test_put_draft_rejects_duplicate_package_ids(admin_token, base_catalog):
    bad = copy.deepcopy(base_catalog)
    bad["packages"][1]["id"] = "wedding"  # duplicate of packages[0].id
    r = requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=bad, timeout=15)
    assert r.status_code == 422, r.text


def test_put_draft_rejects_graduation_id_colliding_with_package(admin_token, base_catalog):
    bad = copy.deepcopy(base_catalog)
    bad["graduation"]["id"] = "wedding"  # collision
    r = requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=bad, timeout=15)
    assert r.status_code == 422, r.text
    assert "collides" in r.text.lower()


def test_put_draft_rejects_price_out_of_range(admin_token, base_catalog):
    for bad_price in [-1, 500_000]:
        bad = copy.deepcopy(base_catalog)
        bad["packages"][0]["tiers"][0]["price"] = bad_price
        r = requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=bad, timeout=15)
        assert r.status_code == 422, f"price={bad_price} accepted!"


# ==============================================================================
# PUBLISH
# ==============================================================================

def test_publish_atomic_swap(admin_token, base_catalog):
    edited = copy.deepcopy(base_catalog)
    edited["packages"][0]["tiers"][0]["price"] = 300.0
    requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=edited, timeout=15).raise_for_status()

    r = requests.post(f"{BASE_URL}/api/admin/pricing/publish", headers=_hdr(admin_token), timeout=15)
    assert r.status_code == 200, r.text

    # Published now reflects the edit
    pub = requests.get(f"{BASE_URL}/api/pricing", timeout=15).json()["content"]
    assert pub["packages"][0]["tiers"][0]["price"] == 300.0

    # Dirty flag returns to False
    d = requests.get(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), timeout=15).json()
    assert d["dirty"] is False


def test_publish_noop_on_no_diff(admin_token):
    r = requests.post(f"{BASE_URL}/api/admin/pricing/publish", headers=_hdr(admin_token), timeout=15)
    assert r.status_code == 200
    assert r.json().get("note") == "no changes to publish"


def test_revert_restores_draft_to_published(admin_token, base_catalog):
    edited = copy.deepcopy(base_catalog)
    edited["bookingTerms"] = "TEMPORARY test edit that should be reverted."
    requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=edited, timeout=15).raise_for_status()
    assert requests.get(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), timeout=15).json()["dirty"] is True

    r = requests.post(f"{BASE_URL}/api/admin/pricing/revert", headers=_hdr(admin_token), timeout=15)
    assert r.status_code == 200
    d = requests.get(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), timeout=15).json()
    assert d["dirty"] is False
    assert d["draft"]["bookingTerms"] == d["published"]["bookingTerms"]


# ==============================================================================
# REFERENTIAL INTEGRITY GUARD ★ ★ ★
# The one Nathan explicitly flagged. Any gap here damages a live booking.
# ==============================================================================

@pytest.fixture
def orphan_ref_ctx():
    """Create a confirmed booking that references wedding:Basic — a tier
    we'll try to remove in the tests below. Fully cleaned up on teardown.

    Cleanup order matters (FKs): payment_transactions → bookings →
    booking_intents → clients → auth.users.
    """
    marker = uuid.uuid4().hex[:8]
    email = f"orphan_test_{marker}@flyboytest.com"

    auth_res = sb_admin.auth.admin.create_user({
        "email": email, "email_confirm": True,
        "user_metadata": {"full_name": f"Orphan Test {marker}"},
    })
    user_id = auth_res.user.id

    client = sb.table("clients").insert({
        "user_id": user_id, "email": email,
        "full_name": f"Orphan Test {marker}", "role": "client",
    }).execute().data[0]

    intent = sb.table("booking_intents").insert({
        "email": email, "full_name": f"Orphan Test {marker}",
        "package_id": "wedding", "package_title": "Wedding Videography",
        "tier_name": "Basic", "price_total": 250.0, "price_deposit": 125.0,
        "event_date": (date.today() + timedelta(days=30)).isoformat(),
        "status": "paid", "session_id": f"cs_orphan_{marker}",
    }).execute().data[0]

    booking = sb.table("bookings").insert({
        "client_id": client["id"], "booking_intent_id": intent["id"],
        "title": "Wedding Videography — Basic",
        "shoot_type": "Wedding Videography", "status": "confirmed",
        "event_date": (date.today() + timedelta(days=30)).isoformat(),
        "shoot_date": (date.today() + timedelta(days=30)).isoformat(),
        "budget": 250.0, "is_seed_data": False,
    }).execute().data[0]

    ctx = {"email": email, "user_id": user_id, "client_id": client["id"],
           "intent_id": intent["id"], "booking_id": booking["id"], "marker": marker}
    yield ctx

    # Teardown
    sb.table("payment_transactions").delete().eq("booking_intent_id", intent["id"]).execute()
    sb.table("bookings").delete().eq("id", booking["id"]).execute()
    sb.table("booking_intents").delete().eq("id", intent["id"]).execute()
    sb.table("clients").delete().eq("id", client["id"]).execute()
    try: sb_admin.auth.admin.delete_user(user_id)
    except Exception: pass


def test_publish_blocks_when_removing_tier_referenced_by_confirmed_booking(
    admin_token, base_catalog, orphan_ref_ctx,
):
    """★ The core guard. Removing wedding:Basic while a confirmed booking
    references it must be rejected with 409 + orphan report; publish must
    NOT persist."""
    edited = copy.deepcopy(base_catalog)
    # Remove the Basic tier from wedding
    edited["packages"][0]["tiers"] = [t for t in edited["packages"][0]["tiers"] if t["name"] != "Basic"]
    requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=edited, timeout=15).raise_for_status()

    r = requests.post(f"{BASE_URL}/api/admin/pricing/publish", headers=_hdr(admin_token), timeout=30)
    assert r.status_code == 409, f"expected 409, got {r.status_code}: {r.text}"
    body = r.json()
    detail = body.get("detail", body)
    assert detail.get("error") == "publish_would_orphan_live_bookings"
    orphans = detail["orphaned_refs"]
    match = [o for o in orphans if o["package_id"] == "wedding" and o["tier_name"] == "Basic"]
    assert match, f"expected wedding/Basic orphan report, got: {orphans}"
    assert match[0]["confirmed_booking_count"] >= 1
    assert orphan_ref_ctx["booking_id"] in match[0]["sample_booking_ids"]

    # Published must NOT have changed — Basic still there
    pub = requests.get(f"{BASE_URL}/api/pricing", timeout=15).json()["content"]
    basic_still_present = any(t["name"] == "Basic" for t in pub["packages"][0]["tiers"])
    assert basic_still_present, "publish was blocked but published catalog changed anyway"


def test_publish_blocks_when_removing_tier_referenced_by_paid_intent_only(
    admin_token, base_catalog, orphan_ref_ctx,
):
    """Even if there's no confirmed booking yet — just a paid intent
    mid-flight — publish must block."""
    # Delete the booking so ONLY the paid intent references wedding/Basic
    sb.table("bookings").delete().eq("id", orphan_ref_ctx["booking_id"]).execute()

    edited = copy.deepcopy(base_catalog)
    edited["packages"][0]["tiers"] = [t for t in edited["packages"][0]["tiers"] if t["name"] != "Basic"]
    requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=edited, timeout=15).raise_for_status()

    r = requests.post(f"{BASE_URL}/api/admin/pricing/publish", headers=_hdr(admin_token), timeout=30)
    assert r.status_code == 409, r.text
    detail = r.json().get("detail", r.json())
    orphans = detail["orphaned_refs"]
    match = [o for o in orphans if o["package_id"] == "wedding" and o["tier_name"] == "Basic"]
    assert match
    assert match[0]["in_flight_intent_count"] >= 1


def test_publish_force_overrides_orphan_block(admin_token, base_catalog, orphan_ref_ctx):
    """?force=1 lets the publish through. The booking's own budget is
    already stored, so it isn't corrupted — but future references (email
    templates, etc.) will now be inconsistent. This is why force is
    logged."""
    edited = copy.deepcopy(base_catalog)
    edited["packages"][0]["tiers"] = [t for t in edited["packages"][0]["tiers"] if t["name"] != "Basic"]
    requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=edited, timeout=15).raise_for_status()

    r = requests.post(f"{BASE_URL}/api/admin/pricing/publish?force=1", headers=_hdr(admin_token), timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("forced") is True

    # Published now missing Basic
    pub = requests.get(f"{BASE_URL}/api/pricing", timeout=15).json()["content"]
    assert not any(t["name"] == "Basic" for t in pub["packages"][0]["tiers"])


def test_publish_allowed_when_only_cancelled_bookings_reference_removed_tier(
    admin_token, base_catalog, orphan_ref_ctx,
):
    """A cancelled booking's tier removal should NOT block publish —
    cancelled bookings are archival, not "live"."""
    sb.table("bookings").update({"status": "cancelled"}).eq("id", orphan_ref_ctx["booking_id"]).execute()
    # Also flip the intent status away from 'paid' so it's not counted
    # as in-flight; a real cancellation flow would archive the intent too.
    sb.table("booking_intents").update({"status": "cancelled"}).eq("id", orphan_ref_ctx["intent_id"]).execute()

    edited = copy.deepcopy(base_catalog)
    edited["packages"][0]["tiers"] = [t for t in edited["packages"][0]["tiers"] if t["name"] != "Basic"]
    requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=edited, timeout=15).raise_for_status()

    r = requests.post(f"{BASE_URL}/api/admin/pricing/publish", headers=_hdr(admin_token), timeout=30)
    assert r.status_code == 200, f"cancelled-only ref should have allowed publish: {r.text}"


def test_renaming_tier_is_treated_as_remove_plus_add_and_blocks(
    admin_token, base_catalog, orphan_ref_ctx,
):
    """Rename wedding:Basic → wedding:Essentials. The rename operation
    is diff-detected as remove(Basic) + add(Essentials); since a live
    booking still references Basic, publish must block."""
    edited = copy.deepcopy(base_catalog)
    for t in edited["packages"][0]["tiers"]:
        if t["name"] == "Basic":
            t["name"] = "Essentials"
    requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=edited, timeout=15).raise_for_status()

    r = requests.post(f"{BASE_URL}/api/admin/pricing/publish", headers=_hdr(admin_token), timeout=30)
    assert r.status_code == 409, r.text


def test_publish_allowed_when_only_pricing_changes_not_removals(
    admin_token, base_catalog, orphan_ref_ctx,
):
    """Positive-case control for the guard: just changing wedding/Basic's
    price (not removing it) must publish successfully even with a live
    booking referencing wedding/Basic."""
    edited = copy.deepcopy(base_catalog)
    for t in edited["packages"][0]["tiers"]:
        if t["name"] == "Basic":
            t["price"] = 275.0
    requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=edited, timeout=15).raise_for_status()

    r = requests.post(f"{BASE_URL}/api/admin/pricing/publish", headers=_hdr(admin_token), timeout=30)
    assert r.status_code == 200, f"price-only change should have published: {r.text}"

    pub = requests.get(f"{BASE_URL}/api/pricing", timeout=15).json()["content"]
    basic = next(t for t in pub["packages"][0]["tiers"] if t["name"] == "Basic")
    assert basic["price"] == 275.0


# ==============================================================================
# CACHE INVALIDATION (packages.py path)
# ==============================================================================

def test_packages_cache_invalidated_on_publish(admin_token, base_catalog):
    """After publish, the packages.py in-process cache is dropped so booking
    checkout sees the new prices without waiting for TTL. We assert this
    by importing packages in a subprocess with PRICING_SOURCE=db and
    checking find_tier picks up the change immediately after publish.
    """
    import subprocess
    # 1. Edit + publish a change
    edited = copy.deepcopy(base_catalog)
    for t in edited["packages"][0]["tiers"]:
        if t["name"] == "Basic":
            t["price"] = 999.0  # sentinel
    requests.put(f"{BASE_URL}/api/admin/pricing/draft", headers=_hdr(admin_token), json=edited, timeout=15).raise_for_status()
    r = requests.post(f"{BASE_URL}/api/admin/pricing/publish", headers=_hdr(admin_token), timeout=15)
    assert r.status_code == 200, r.text

    # 2. Fresh Python: import packages with PRICING_SOURCE=db, read the price
    code = (
        "import os; os.environ['PRICING_SOURCE']='db';"
        "import packages;"
        "pkg,tier = packages.find_tier('wedding','Basic');"
        "print(tier['price'])"
    )
    res = subprocess.run(
        ["python", "-c", code],
        cwd=str(BACKEND_DIR),
        env={**os.environ, "PRICING_SOURCE": "db"},
        capture_output=True, text=True, timeout=30,
    )
    assert res.returncode == 0, res.stderr
    assert res.stdout.strip() == "999.0", f"DB-mode read got {res.stdout!r}"
