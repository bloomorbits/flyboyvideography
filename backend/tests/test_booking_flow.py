"""Backend integration tests for the /api/booking/* flow (Phase 1)."""
import os
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://db-bridge-5.preview.emergentagent.com").rstrip("/")

# ---------- SAFETY GUARD (SEC-003 fix) ----------
# This suite hits the live backend with the service-role key and creates
# real Stripe test-mode sessions + date_slot_locks + auth users. Refuse to
# collect if the target isn't a known-safe URL. Set ALLOW_ATTACK_SIM=1 to
# opt in (see sim_calendar_freeze_attack.py for the same guard).
_SAFE_URL_MARKERS = ("preview.emergentagent.com", "localhost", "127.0.0.1", "staging")
if os.environ.get("ALLOW_ATTACK_SIM") != "1":
    raise SystemExit(
        "REFUSED: test_booking_flow.py mutates the live Supabase DB via the "
        "service-role key and creates real Stripe test-mode sessions. Set "
        "ALLOW_ATTACK_SIM=1 to run. Never set this on a production-connected shell."
    )
if not any(m in BASE_URL for m in _SAFE_URL_MARKERS):
    raise SystemExit(
        f"REFUSED: target URL {BASE_URL!r} does not match any known-safe pattern "
        f"({_SAFE_URL_MARKERS!r}). Extend explicitly if genuinely intended."
    )

# Fixed test dates so the cleanup fixture can target them without needing to
# thread state between tests.
TEST_DATE_1 = (date.today() + timedelta(days=400)).isoformat()
TEST_DATE_2 = (date.today() + timedelta(days=430)).isoformat()

# Unique per-test-run email prefix so we don't collide with the rate limiter
# across pytest invocations run back-to-back.
EMAIL_PREFIX = f"flowtest_{uuid.uuid4().hex[:8]}"


def _fresh_email(suffix: str) -> str:
    """Every test gets its own email so the per-email rate limit
    (3/15min) doesn't cause cross-test bleeding."""
    return f"{EMAIL_PREFIX}_{suffix}@flyboytest.com"


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module", autouse=True)
def _cleanup_test_rows():
    """Delete any booking_intents / payment_transactions / date_slot_locks
    that this test module created, so we don't leak rows in Supabase between
    runs. Uses the service-role key from backend/.env."""
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    def _wipe():
        for d in (TEST_DATE_1, TEST_DATE_2):
            intents = sb.table("booking_intents").select("id,session_id").eq("event_date", d).execute().data or []
            sids = [i["session_id"] for i in intents if i.get("session_id")]
            if sids:
                sb.table("payment_transactions").delete().in_("session_id", sids).execute()
            sb.table("date_slot_locks").delete().eq("event_date", d).execute()
            sb.table("booking_intents").delete().eq("event_date", d).execute()
        # Rate-limiter ledger — remove rows from this test run only.
        sb.table("checkout_attempts").delete().ilike("email", f"{EMAIL_PREFIX}%").execute()

    _wipe()
    yield
    _wipe()


@pytest.fixture(autouse=True)
def _clear_ratelimit_between_tests():
    """The rate limiter fires at per-IP=5/15min. Running the whole module
    from the same source IP would hit the cap around the 6th test. Purge
    the ledger between each test so tests remain independent.

    SCOPED PURGE (SEC-003 hardening): purge ONLY rows created by THIS
    pytest run's unique EMAIL_PREFIX. Earlier iterations of this fixture
    swept `%@example.com` and other broad patterns, which would have
    wiped a real customer's rate-limit history if any of them happened
    to use a test domain. Broad patterns removed 2026-02.
    """
    from supabase import create_client
    sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    sb.table("checkout_attempts").delete().ilike("email", f"{EMAIL_PREFIX}%").execute()
    yield


# --- availability ---

def test_availability_shape(api):
    r = api.get(f"{BASE_URL}/api/booking/availability")
    assert r.status_code == 200, r.text
    data = r.json()
    assert set(data.keys()) >= {"today", "horizon", "blocked_dates"}
    today = date.fromisoformat(data["today"])
    horizon = date.fromisoformat(data["horizon"])
    assert today == date.today()
    # ~18 months ahead
    assert 500 <= (horizon - today).days <= 600
    assert isinstance(data["blocked_dates"], list)


# --- checkout ---

def _payload(event_date=None, **over):
    ed = event_date or TEST_DATE_1
    body = {
        "package_id": "wedding",
        "tier_name": "Classic",
        "event_date": ed.isoformat() if isinstance(ed, date) else ed,
        "email": _fresh_email("default"),
        "full_name": "Test Booker",
        "phone": "+441234567890",
        "event_notes": "test",
        "origin_url": "https://flyboyvideography.com",
    }
    body.update(over)
    return body


def test_checkout_valid_returns_stripe_url(api):
    p = _payload(event_date=TEST_DATE_1, email=_fresh_email("valid"))
    r = api.post(f"{BASE_URL}/api/booking/checkout", json=p)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["checkout_url"].startswith("https://checkout.stripe.com/"), data
    assert data["session_id"].startswith("cs_test_"), data
    # stash for later
    pytest.__test_session_id = data["session_id"]  # type: ignore


def test_checkout_invalid_package_returns_422(api):
    r = api.post(f"{BASE_URL}/api/booking/checkout", json=_payload(email=_fresh_email("invpkg"), package_id="not_a_package"))
    assert r.status_code == 422, r.text


def test_checkout_past_date_returns_422(api):
    r = api.post(f"{BASE_URL}/api/booking/checkout", json=_payload(email=_fresh_email("pastdate"), event_date=(date.today() - timedelta(days=1)).isoformat()))
    assert r.status_code == 422, r.text
    detail = r.json().get("detail", "")
    assert "future" in str(detail).lower()


def test_checkout_bad_origin_returns_422(api):
    """SEC — open-redirect allowlist blocks unknown origin_url."""
    r = api.post(f"{BASE_URL}/api/booking/checkout", json=_payload(email=_fresh_email("badorig"), origin_url="https://evil.example.com"))
    assert r.status_code == 422, r.text
    assert "origin" in (r.json().get("detail") or "").lower()


def test_checkout_same_date_lock_returns_409(api):
    r1 = api.post(f"{BASE_URL}/api/booking/checkout", json=_payload(event_date=TEST_DATE_2, email=_fresh_email("locka")))
    assert r1.status_code == 200, r1.text
    r2 = api.post(f"{BASE_URL}/api/booking/checkout", json=_payload(event_date=TEST_DATE_2, email=_fresh_email("lockb")))
    assert r2.status_code == 409, r2.text


# --- status ---

def test_status_for_created_session_pending(api):
    sid = getattr(pytest, "__test_session_id", None)
    if not sid:
        pytest.skip("no session from checkout test")
    r = api.get(f"{BASE_URL}/api/booking/status/{sid}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["session_id"] == sid
    assert data["status"] == "initiated"
    assert data["payment_status"] == "pending"


def test_status_for_fake_session_returns_404(api):
    r = api.get(f"{BASE_URL}/api/booking/status/cs_test_bogus_does_not_exist_xyz")
    assert r.status_code == 404, r.text


# --- webhook ---

def test_webhook_without_signature_returns_400(api):
    r = requests.post(
        f"{BASE_URL}/api/stripe/webhook",
        data=b'{"type":"checkout.session.completed"}',
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 400, r.text
    assert "signature" in r.text.lower()
