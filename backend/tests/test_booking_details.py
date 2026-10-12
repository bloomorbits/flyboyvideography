"""Step 2 — Compulsory booking details (Migration 021) regression suite.

Mutation-testable server-side proof, same standard as test_consent_enforcement.py.
Uses FastAPI TestClient against the real route + Pydantic + validation stack;
Supabase is mocked at booking._sb() / server.sb so no DB is touched and no
Stripe calls are burned. Covers:

  1. Each required field missing / blank / whitespace-only -> 422 per-field.
  2. venue_tbc relaxes venue_name + postcode; postcode only required when known.
  3. Phone normalised to E.164 (UK local / +44 / international); junk -> per-field.
  4. event_start_time HH:MM and HH:MM:SS accepted + normalised; junk -> per-field.
  5. New detail fields land on the booking_intents row and are ABSENT from
     Stripe metadata (no free text in metadata).
  6. Finalise copies detail fields from the intent to bookings even when the
     Stripe metadata retrieve FAILS (persistence resilience).
  7. GET endpoints: contact source rule (intent->clients), legacy "check number"
     marker, HH:MM display, cross-client entitlement 403, admin-only fields, 404.

MUTATION NOTES (each enforcement branch, revert -> a named assertion fails):
  - Remove the `phone` required check in booking.create_checkout
      -> test_phone_required_missing fails (gets 200/Stripe instead of 422).
  - Remove `_normalise_phone` call / store body.phone raw
      -> test_phone_uk_local_normalised_to_e164 fails (intent phone != +44...).
  - Remove the `event_start_time` required/parse check
      -> test_start_time_required_blank / test_start_time_invalid_rejected fail.
  - Remove the `not venue_tbc and _blank(postcode)` branch
      -> test_postcode_required_when_venue_known fails.
  - Drop the detail fields from the bookings insert in _finalise_paid_session
      -> test_finalise_copies_details_even_when_stripe_metadata_fails fails.
  - Weaken the client entitlement check (client_id != client.id)
      -> test_client_cannot_read_other_clients_booking fails (403 -> 200).
"""
from __future__ import annotations
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import booking  # noqa: E402
import server  # noqa: E402
from server import app, get_auth_user  # noqa: E402

client = TestClient(app)

VALID = {
    "package_id": "graduation",
    "tier_name": "",
    "event_date": "2030-06-20",
    "email": "details.test@flyboytest.com",
    "full_name": "Details Test",
    "phone": "+447911123456",
    "origin_url": "https://flyboyvideography.com",
    "tc_accepted": True,
    "model_release_opted_in": True,
    "minors_involved": False,
    # compulsory booking details
    "venue_name": "The Grand Hall",
    "venue_tbc": False,
    "event_city": "Manchester",
    "event_postcode": "M1 1AA",
    "event_start_time": "14:30",
}


# --------------------------------------------------------------------------- #
# Checkout mock helpers (mirror test_consent_enforcement.py)                  #
# --------------------------------------------------------------------------- #
def _mock_sb():
    sb = MagicMock()
    sb._captured_intent_insert = None

    def _mk_chain(table_name):
        chain = MagicMock()
        res = MagicMock()
        res.data = [{"id": "intent_stub_id"}]
        res.count = 0
        chain.execute.return_value = res

        def _capture(payload):
            if table_name == "booking_intents":
                sb._captured_intent_insert = payload
            return chain
        chain.insert.side_effect = _capture
        for m in ("select", "update", "delete", "eq", "in_", "gt", "lt",
                  "gte", "lte", "limit", "order", "ilike", "neq"):
            getattr(chain, m).return_value = chain
        return chain

    sb.table.side_effect = _mk_chain
    return sb


def _stripe_session():
    s = MagicMock()
    s.id = "cs_test_details_stub"
    s.url = "https://checkout.stripe.com/c/pay/cs_test_details_stub"
    return s


def _post(payload, sb_mock=None, enforce=True):
    sb_mock = sb_mock or _mock_sb()
    with patch("booking._sb", return_value=sb_mock), \
         patch("booking._booking_details_enforced", return_value=enforce), \
         patch("booking._clean_expired_locks"), \
         patch("booking._confirmed_booking_exists", return_value=False), \
         patch("booking._active_lock_exists", return_value=False), \
         patch("booking._rate_limit_or_429"), \
         patch("booking._concurrent_lock_or_429"), \
         patch("booking.stripe.checkout.Session.create", return_value=_stripe_session()) as sc:
        r = client.post("/api/booking/checkout", json=payload)
    return r, sb_mock, sc


def _field_errors(r):
    detail = r.json().get("detail", {})
    if isinstance(detail, dict):
        return {e["field"]: e["message"] for e in detail.get("errors", [])}
    return {}


# --------------------------------------------------------------------------- #
# 0. Deploy-window flag OFF — OLD form (no new fields) must still check out    #
# --------------------------------------------------------------------------- #
def test_flag_off_old_form_without_new_fields_checks_out():
    """ENFORCE_BOOKING_DETAILS off: a legacy payload missing ALL new required
    fields must reach Stripe (no 422), so the old frontend keeps working during
    the deploy window."""
    legacy = {
        "package_id": "graduation", "tier_name": "", "event_date": "2030-06-20",
        "email": "legacy@flyboytest.com", "full_name": "Legacy Form",
        "origin_url": "https://flyboyvideography.com", "tc_accepted": True,
        "model_release_opted_in": True, "minors_involved": False,
    }
    r, sb_mock, sc = _post(legacy, enforce=False)
    assert r.status_code == 200, r.text
    assert sc.call_count == 1
    # new columns persisted as NULL/default, not fabricated
    intent = sb_mock._captured_intent_insert
    assert intent["venue_name"] is None and intent["event_city"] is None
    assert intent["event_start_time"] is None


def test_flag_off_still_validates_supplied_phone():
    """Even with the flag off, a phone that IS supplied is normalised; junk is
    rejected (never written raw to a field the DB trigger would bounce)."""
    r, sb_mock, _ = _post({
        "package_id": "graduation", "tier_name": "", "event_date": "2030-06-20",
        "email": "legacy2@flyboytest.com", "full_name": "Legacy Two",
        "origin_url": "https://flyboyvideography.com", "tc_accepted": True,
        "phone": "07911 123456",
    }, enforce=False)
    assert r.status_code == 200, r.text
    assert sb_mock._captured_intent_insert["phone"] == "+447911123456"

    r2, _, sc2 = _post({
        "package_id": "graduation", "tier_name": "", "event_date": "2030-06-21",
        "email": "legacy3@flyboytest.com", "full_name": "Legacy Three",
        "origin_url": "https://flyboyvideography.com", "tc_accepted": True,
        "phone": "notaphone",
    }, enforce=False)
    assert r2.status_code == 422 and "phone" in _field_errors(r2)
    assert sc2.call_count == 0


def test_flag_on_old_form_is_rejected():
    """Sanity: with the flag ON, the legacy payload (no new fields) 422s — this
    is why the flag defaults OFF until the new form ships."""
    legacy = {
        "package_id": "graduation", "tier_name": "", "event_date": "2030-06-22",
        "email": "legacy4@flyboytest.com", "full_name": "Legacy Four",
        "origin_url": "https://flyboyvideography.com", "tc_accepted": True,
    }
    r, _, sc = _post(legacy, enforce=True)
    assert r.status_code == 422
    assert {"phone", "event_start_time", "event_city", "venue_name"} <= set(_field_errors(r))
    assert sc.call_count == 0


# --------------------------------------------------------------------------- #
# 1 + 2. Required-field validation                                            #
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("field", ["phone", "event_start_time", "event_city", "venue_name", "event_postcode"])
def test_required_field_missing(field):
    payload = {k: v for k, v in VALID.items() if k != field}
    r, _, sc = _post(payload)
    assert r.status_code == 422, r.text
    assert field in _field_errors(r), f"{field} error missing: {r.text}"
    assert sc.call_count == 0, "Stripe was reached despite a missing required field"


@pytest.mark.parametrize("field", ["phone", "event_start_time", "event_city", "venue_name", "event_postcode"])
def test_required_field_whitespace_only_counts_as_missing(field):
    r, _, sc = _post({**VALID, field: "   "})
    assert r.status_code == 422, r.text
    assert field in _field_errors(r), f"{field} not flagged for whitespace-only: {r.text}"
    assert sc.call_count == 0


def test_phone_required_missing():
    r, _, sc = _post({k: v for k, v in VALID.items() if k != "phone"})
    assert r.status_code == 422 and "phone" in _field_errors(r)
    assert sc.call_count == 0


def test_venue_tbc_relaxes_venue_name_and_postcode():
    payload = {**VALID, "venue_tbc": True}
    payload.pop("venue_name")
    payload.pop("event_postcode")
    r, sb_mock, sc = _post(payload)
    assert r.status_code == 200, r.text
    assert sc.call_count == 1
    assert sb_mock._captured_intent_insert["venue_tbc"] is True
    assert sb_mock._captured_intent_insert["venue_name"] is None


def test_postcode_required_when_venue_known():
    payload = {**VALID}
    payload.pop("event_postcode")
    r, _, sc = _post(payload)
    assert r.status_code == 422, r.text
    assert "event_postcode" in _field_errors(r)
    assert sc.call_count == 0


def test_postcode_optional_when_tbc():
    payload = {**VALID, "venue_tbc": True, "venue_name": "Maybe Hall"}
    payload.pop("event_postcode")
    r, _, sc = _post(payload)
    assert r.status_code == 200, r.text
    assert sc.call_count == 1


# --------------------------------------------------------------------------- #
# 3. Phone normalisation                                                      #
# --------------------------------------------------------------------------- #
def test_phone_uk_local_normalised_to_e164():
    r, sb_mock, _ = _post({**VALID, "phone": "07911 123456"})
    assert r.status_code == 200, r.text
    assert sb_mock._captured_intent_insert["phone"] == "+447911123456"


def test_phone_plus44_accepted():
    r, sb_mock, _ = _post({**VALID, "phone": "+44 7911 123456"})
    assert r.status_code == 200, r.text
    assert sb_mock._captured_intent_insert["phone"] == "+447911123456"


def test_phone_international_accepted():
    r, sb_mock, _ = _post({**VALID, "phone": "+1 415 555 2671"})
    assert r.status_code == 200, r.text
    assert sb_mock._captured_intent_insert["phone"] == "+14155552671"


@pytest.mark.parametrize("bad", ["notaphone", "12345", "+44 123"])
def test_phone_invalid_rejected_with_fix_message(bad):
    r, _, sc = _post({**VALID, "phone": bad})
    assert r.status_code == 422, r.text
    errs = _field_errors(r)
    assert "phone" in errs and "fixing" in errs["phone"].lower(), r.text
    assert sc.call_count == 0


def test_secondary_phone_optional_but_validated():
    # invalid secondary -> rejected
    r, _, sc = _post({**VALID, "secondary_contact_phone": "nope"})
    assert r.status_code == 422 and "secondary_contact_phone" in _field_errors(r)
    assert sc.call_count == 0
    # valid secondary -> normalised onto intent
    r2, sb2, _ = _post({**VALID, "secondary_contact_name": "Backup", "secondary_contact_phone": "07911 222333"})
    assert r2.status_code == 200, r2.text
    assert sb2._captured_intent_insert["secondary_contact_phone"] == "+447911222333"


# --------------------------------------------------------------------------- #
# 4. event_start_time                                                         #
# --------------------------------------------------------------------------- #
def test_start_time_hhmm_accepted():
    r, sb_mock, _ = _post({**VALID, "event_start_time": "09:05"})
    assert r.status_code == 200, r.text
    assert sb_mock._captured_intent_insert["event_start_time"] == "09:05"


def test_start_time_hhmmss_normalised():
    r, sb_mock, _ = _post({**VALID, "event_start_time": "14:30:00"})
    assert r.status_code == 200, r.text
    assert sb_mock._captured_intent_insert["event_start_time"] == "14:30"


def test_start_time_required_blank():
    r, _, sc = _post({**VALID, "event_start_time": "   "})
    assert r.status_code == 422 and "event_start_time" in _field_errors(r)
    assert sc.call_count == 0


@pytest.mark.parametrize("bad", ["25:61", "abc", "99:99"])
def test_start_time_invalid_rejected(bad):
    r, _, sc = _post({**VALID, "event_start_time": bad})
    assert r.status_code == 422, r.text
    assert "event_start_time" in _field_errors(r)
    assert sc.call_count == 0


# --------------------------------------------------------------------------- #
# 5. Detail fields persist to intent and NOT to Stripe metadata               #
# --------------------------------------------------------------------------- #
def test_details_land_on_intent_and_not_in_stripe_metadata():
    r, sb_mock, sc = _post({**VALID, "guest_count": 80, "event_notes": "near the lake"})
    assert r.status_code == 200, r.text
    intent = sb_mock._captured_intent_insert
    assert intent["venue_name"] == "The Grand Hall"
    assert intent["event_city"] == "Manchester"
    assert intent["event_postcode"] == "M1 1AA"
    assert intent["guest_count"] == 80
    metadata = sc.call_args.kwargs.get("metadata", {})
    for leak in ("venue_name", "event_city", "event_postcode", "secondary_contact_name",
                 "secondary_contact_phone", "event_notes", "guest_count"):
        assert leak not in metadata, f"free text leaked into Stripe metadata: {leak}"


# --------------------------------------------------------------------------- #
# 6. Finalise copies details even when the Stripe metadata call fails         #
# --------------------------------------------------------------------------- #
def test_finalise_copies_details_even_when_stripe_metadata_fails():
    intent_row = {
        "id": "int1", "email": "copy@flyboytest.com", "full_name": "Copy Test",
        "phone": "+447911123456", "package_title": "Graduation Reels", "tier_name": "",
        "price_total": 150.0, "event_date": "2030-06-20", "event_notes": "n",
        # consent present so the SECOND Stripe retrieve isn't needed
        "tc_accepted_at": "2026-01-01T00:00:00Z", "tc_accepted_ip": "1.2.3.4",
        "model_release_opted_in": True, "minors_involved": False,
        "safeguarding_guardian_name": None, "safeguarding_consent_accepted_at": None,
        # Migration 021 detail fields
        "venue_name": "Lakeside", "venue_tbc": False, "event_city": "York",
        "event_postcode": "YO1 1AA", "event_start_time": "16:45", "guest_count": 120,
        "secondary_contact_name": "Sam", "secondary_contact_phone": "+447911222333",
    }
    capture = {}

    def chain_for(name):
        ch = MagicMock()
        res = MagicMock()
        res.count = 0
        if name == "bookings":
            res.data = []  # idempotency select -> not yet finalised
        elif name == "payment_transactions":
            res.data = [{"payment_status": "pending", "stripe_payment_intent_id": None, "session_id": "sess1"}]
        elif name == "booking_intents":
            res.data = [intent_row]
        else:
            res.data = [{"id": "x"}]
        ch.execute.return_value = res

        def _ins(payload):
            if name == "bookings":
                capture["bookings"] = payload
                ins = MagicMock()
                ins.data = [{"id": "bk1", **payload}]
                ch.execute.return_value = ins
            return ch
        ch.insert.side_effect = _ins
        for m in ("select", "update", "delete", "eq", "in_", "gt", "lt",
                  "gte", "lte", "limit", "order", "ilike", "neq"):
            getattr(ch, m).return_value = ch
        return ch

    sb = MagicMock()
    sb.table.side_effect = chain_for

    with patch("booking._sb", return_value=sb), \
         patch("booking.stripe.checkout.Session.retrieve", side_effect=Exception("stripe metadata down")) as sr, \
         patch("booking._ensure_auth_user", return_value="user1"), \
         patch("booking._ensure_client_row", return_value="client1"), \
         patch("booking._generate_invite_link", return_value="https://invite"), \
         patch("booking._render_email", return_value=("<html>", "text")), \
         patch("booking._send_confirmation_email"):
        result = booking._finalise_paid_session("sess1", "pi_1", metadata=None)

    assert sr.call_count >= 1, "the Stripe metadata retrieve path was not exercised"
    assert "bookings" in capture, "bookings insert never happened despite Stripe failure"
    b = capture["bookings"]
    assert b["venue_name"] == "Lakeside"
    assert b["event_city"] == "York"
    assert b["event_postcode"] == "YO1 1AA"
    assert b["event_start_time"] == "16:45"
    assert b["guest_count"] == 120
    assert b["secondary_contact_phone"] == "+447911222333"
    assert result.get("finalised") is True


# --------------------------------------------------------------------------- #
# 7. Detail endpoints: contact rule, legacy marker, entitlement, admin fields #
# --------------------------------------------------------------------------- #
CONSENT_COLS = {
    "tc_accepted_at": "2026-01-01T00:00:00Z", "model_release_opted_in": True,
    "minors_involved": False, "safeguarding_guardian_name": None,
    "safeguarding_consent_accepted_at": None,
}
BOOKING_A = {
    "id": "bkA", "client_id": "clientA", "booking_intent_id": "intA", "status": "confirmed",
    "title": "Wedding", "shoot_type": "Wedding", "event_date": "2030-01-01",
    "event_start_time": "14:30:00", "venue_name": "Hall", "venue_tbc": False,
    "event_city": "Leeds", "event_postcode": "LS1 1AA", "guest_count": 80,
    "secondary_contact_name": None, "secondary_contact_phone": None, "notes": "n",
    "budget": 2000.0, "deposit_paid_at": "2026-01-01T00:00:00Z", "stripe_session_id": "cs_A",
    **CONSENT_COLS,
}
STORE = {
    "clients": [
        {"id": "clientA", "user_id": "userA", "role": "client", "full_name": "Alice", "email": "alice@x.com", "phone": "+447911123456"},
        {"id": "clientB", "user_id": "userB", "role": "client", "full_name": "Bob", "email": "bob@x.com", "phone": "+447911999000"},
        {"id": "adminC", "user_id": "userAdmin", "role": "admin", "full_name": "Admin", "email": "admin@x.com", "phone": None},
    ],
    "bookings": [BOOKING_A],
    # intent has a LEGACY non-E.164 phone -> contact rule prefers it, marker expected
    "booking_intents": [{"id": "intA", "full_name": "Alice Intent", "email": "alice.intent@x.com", "phone": "07123 legacy"}],
}


class _FakeQuery:
    def __init__(self, store, table):
        self.store, self.table, self.filters = store, table, {}

    def select(self, *a, **k): return self
    def eq(self, col, val): self.filters[col] = val; return self
    def limit(self, *a, **k): return self
    def order(self, *a, **k): return self

    def execute(self):
        rows = [r for r in self.store.get(self.table, [])
                if all(r.get(c) == v for c, v in self.filters.items())]
        return SimpleNamespace(data=rows, count=len(rows))


class _FakeSB:
    def __init__(self, store):
        self.store, self.auth = store, MagicMock()

    def table(self, name):
        return _FakeQuery(self.store, name)


def _as_user(user_id):
    def _dep():
        return SimpleNamespace(id=user_id)
    return _dep


def _unit_test_hhmm_and_contact():
    assert server._hhmm("14:30:00") == "14:30"
    assert server._hhmm(None) is None
    c = server._resolve_contact({"full_name": "I", "email": "i@x", "phone": "07123 junk"}, None)
    assert c["phone_needs_check"] is True
    c2 = server._resolve_contact({"full_name": "I", "email": "i@x", "phone": "+447911123456"}, None)
    assert c2["phone_needs_check"] is False
    # intent-first, client fallback
    c3 = server._resolve_contact(None, {"full_name": "C", "email": "c@x", "phone": "+447911000000"})
    assert c3["full_name"] == "C"


def test_helpers_hhmm_and_contact_rule():
    _unit_test_hhmm_and_contact()


def test_client_reads_own_booking_with_legacy_marker():
    app.dependency_overrides[get_auth_user] = _as_user("userA")
    try:
        with patch.object(server, "sb", _FakeSB(STORE)):
            r = client.get("/api/bookings/bkA")
    finally:
        app.dependency_overrides.pop(get_auth_user, None)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["event_start_time"] == "14:30"  # normalised HH:MM
    assert body["contact"]["full_name"] == "Alice Intent"  # intent-first
    assert body["contact"]["phone"] == "07123 legacy"       # shown AS-IS
    assert body["contact"]["phone_needs_check"] is True      # marker
    assert "stripe_session_id" not in body                   # admin-only not leaked
    assert "tc_accepted_at" not in body


def test_client_cannot_read_other_clients_booking():
    app.dependency_overrides[get_auth_user] = _as_user("userB")  # Bob
    try:
        with patch.object(server, "sb", _FakeSB(STORE)):
            r = client.get("/api/bookings/bkA")  # Alice's booking
    finally:
        app.dependency_overrides.pop(get_auth_user, None)
    assert r.status_code == 403, r.text


def test_admin_reads_any_booking_with_admin_fields():
    app.dependency_overrides[get_auth_user] = _as_user("userAdmin")
    try:
        with patch.object(server, "sb", _FakeSB(STORE)):
            r = client.get("/api/admin/bookings/bkA")
    finally:
        app.dependency_overrides.pop(get_auth_user, None)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stripe_session_id"] == "cs_A"      # admin-only field present
    assert body["booking_intent_id"] == "intA"
    assert body["contact"]["phone_needs_check"] is True


def test_admin_booking_not_found_404():
    app.dependency_overrides[get_auth_user] = _as_user("userAdmin")
    try:
        with patch.object(server, "sb", _FakeSB(STORE)):
            r = client.get("/api/admin/bookings/does-not-exist")
    finally:
        app.dependency_overrides.pop(get_auth_user, None)
    assert r.status_code == 404, r.text


def test_admin_endpoint_requires_admin_role():
    app.dependency_overrides[get_auth_user] = _as_user("userA")  # non-admin
    try:
        with patch.object(server, "sb", _FakeSB(STORE)):
            r = client.get("/api/admin/bookings/bkA")
    finally:
        app.dependency_overrides.pop(get_auth_user, None)
    assert r.status_code == 403, r.text
