"""Backend integration tests for the /api/booking/* flow (Phase 1)."""
import os
from datetime import date, timedelta
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://db-bridge-5.preview.emergentagent.com").rstrip("/")

# Fixed test dates so the cleanup fixture can target them without needing to
# thread state between tests.
TEST_DATE_1 = (date.today() + timedelta(days=400)).isoformat()
TEST_DATE_2 = (date.today() + timedelta(days=430)).isoformat()


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

    _wipe()
    yield
    _wipe()


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
        "email": "TEST_book@example.com",
        "full_name": "Test Booker",
        "phone": "+441234567890",
        "event_notes": "test",
        "origin_url": "https://flyboyvideography.com",
    }
    body.update(over)
    return body


def test_checkout_valid_returns_stripe_url(api):
    p = _payload(event_date=TEST_DATE_1)
    r = api.post(f"{BASE_URL}/api/booking/checkout", json=p)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["checkout_url"].startswith("https://checkout.stripe.com/"), data
    assert data["session_id"].startswith("cs_test_"), data
    # stash for later
    pytest.__test_session_id = data["session_id"]  # type: ignore


def test_checkout_invalid_package_returns_422(api):
    r = api.post(f"{BASE_URL}/api/booking/checkout", json=_payload(package_id="not_a_package"))
    assert r.status_code == 422, r.text


def test_checkout_past_date_returns_422(api):
    r = api.post(f"{BASE_URL}/api/booking/checkout", json=_payload(event_date=(date.today() - timedelta(days=1)).isoformat()))
    assert r.status_code == 422, r.text
    detail = r.json().get("detail", "")
    assert "future" in str(detail).lower()


def test_checkout_same_date_lock_returns_409(api):
    r1 = api.post(f"{BASE_URL}/api/booking/checkout", json=_payload(event_date=TEST_DATE_2))
    assert r1.status_code == 200, r1.text
    r2 = api.post(f"{BASE_URL}/api/booking/checkout", json=_payload(event_date=TEST_DATE_2, email="TEST_other@example.com"))
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
