"""Server-side consent enforcement — regression pytest (Migration 010, session 11).

Proves the /api/booking/checkout endpoint enforces the four consent rules on
the server, independent of the frontend's disabled-button UX:

  1. Reject with 400 if tc_accepted is false
  2. Reject with 400 if minors_involved=true and safeguarding_guardian_name is missing/blank
  3. Reject with 400 if minors_involved=true and safeguarding_consent_accepted is false
  4. Accept when all conditions are met (and consent metadata flows into
     Stripe.checkout.Session.create's metadata parameter — proving the
     capture path, not just the reject path)

Same standard as test_booking_concurrency::test_same_session_concurrent_finalise_does_not_refund_customer
(SEC-001 regression) — mutation-testable: reverting the enforcement branch
in booking.py makes at least one assertion fail with a clear diagnostic.

Uses FastAPI's TestClient so we hit the actual route + Pydantic + validation
stack, and mocks Stripe.checkout.Session.create so we don't burn API calls
or DB residue. Supabase is patched at booking.py's _sb() import so we don't
touch the real DB either.
"""
from __future__ import annotations
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

# Load env before importing server (server crashes on missing SUPABASE_URL)
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server import app  # noqa: E402

client = TestClient(app)

VALID_PAYLOAD_MINIMAL = {
    "package_id": "graduation",
    "tier_name": "",
    "event_date": "2028-06-20",
    "email": "consent.test@flyboytest.com",
    "full_name": "Consent Test",
    "phone": "+447700900001",
    "event_notes": "consent enforcement test",
    "origin_url": "https://flyboyvideography.com",
    # ---- consent block ----
    "tc_accepted": True,
    "model_release_opted_in": True,
    "minors_involved": False,
    "safeguarding_guardian_name": None,
    "safeguarding_consent_accepted": False,
}


def _mock_sb_for_happy_path():
    """A Supabase mock that lets the happy-path checkout progress to Stripe.

    Returns a MagicMock chain matching sb.table(...).insert/select/eq(...).execute()
    minimally enough for the checkout handler to reach stripe.checkout.Session.create.
    Records the payload passed to booking_intents.insert() so tests can assert
    consent columns land on the intent row (Migration 010B).
    """
    sb = MagicMock()
    # Container the test can read AFTER the request. Populated on insert calls.
    sb._captured_intent_insert = None

    def _mk_chain(table_name):
        chain = MagicMock()
        exec_result = MagicMock()
        exec_result.data = [{"id": "intent_stub_id"}]
        exec_result.count = 0
        chain.execute.return_value = exec_result

        def _capture_insert(payload):
            # Only the booking_intents insert has the columns we care about here.
            if table_name == "booking_intents":
                sb._captured_intent_insert = payload
            return chain
        chain.insert.side_effect = _capture_insert

        chain.select.return_value = chain
        chain.update.return_value = chain
        chain.delete.return_value = chain
        chain.eq.return_value = chain
        chain.in_.return_value = chain
        chain.gt.return_value = chain
        chain.lt.return_value = chain
        chain.gte.return_value = chain
        chain.lte.return_value = chain
        chain.limit.return_value = chain
        chain.order.return_value = chain
        chain.ilike.return_value = chain
        return chain

    sb.table.side_effect = _mk_chain
    return sb


def _mock_stripe_session():
    s = MagicMock()
    s.id = "cs_test_consent_regression_stub"
    s.url = "https://checkout.stripe.com/c/pay/cs_test_consent_regression_stub"
    return s


# ------------------------------------------------------------------------- #
# Rejection tests — the actual security gate                                #
# ------------------------------------------------------------------------- #

def test_rejects_when_tc_not_accepted():
    """SEC-CONSENT-001: T&Cs unchecked → 400, booking never reaches Stripe."""
    payload = {**VALID_PAYLOAD_MINIMAL, "tc_accepted": False}
    with patch("booking._sb", return_value=_mock_sb_for_happy_path()), \
         patch("booking.stripe.checkout.Session.create") as stripe_create:
        r = client.post("/api/booking/checkout", json=payload)
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
    body = r.json()
    assert "terms" in body.get("detail", "").lower() or "t&c" in body.get("detail", "").lower(), (
        f"detail should mention T&Cs, got: {body}"
    )
    assert stripe_create.call_count == 0, (
        "SEC-CONSENT-001 REGRESSION: Stripe session was created despite unchecked T&Cs"
    )


def test_rejects_minors_missing_guardian_name():
    """SEC-CONSENT-002: minors=true + no guardian name → 400."""
    payload = {
        **VALID_PAYLOAD_MINIMAL,
        "minors_involved": True,
        "safeguarding_guardian_name": None,
        "safeguarding_consent_accepted": True,  # accepted, but name blank
    }
    with patch("booking._sb", return_value=_mock_sb_for_happy_path()), \
         patch("booking.stripe.checkout.Session.create") as stripe_create:
        r = client.post("/api/booking/checkout", json=payload)
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
    assert "guardian" in r.json().get("detail", "").lower(), (
        f"detail should mention guardian, got: {r.json()}"
    )
    assert stripe_create.call_count == 0, (
        "SEC-CONSENT-002 REGRESSION: Stripe session created despite missing guardian name"
    )


def test_rejects_minors_guardian_name_whitespace_only():
    """Guarding against 'submit spaces to bypass' — same class as SEC-CONSENT-002."""
    payload = {
        **VALID_PAYLOAD_MINIMAL,
        "minors_involved": True,
        "safeguarding_guardian_name": "   ",
        "safeguarding_consent_accepted": True,
    }
    with patch("booking._sb", return_value=_mock_sb_for_happy_path()), \
         patch("booking.stripe.checkout.Session.create") as stripe_create:
        r = client.post("/api/booking/checkout", json=payload)
    assert r.status_code == 400
    assert "guardian" in r.json().get("detail", "").lower()
    assert stripe_create.call_count == 0


def test_rejects_minors_without_safeguarding_consent():
    """SEC-CONSENT-003: minors=true + guardian name present + safeguarding_consent=false → 400."""
    payload = {
        **VALID_PAYLOAD_MINIMAL,
        "minors_involved": True,
        "safeguarding_guardian_name": "Jane Doe",
        "safeguarding_consent_accepted": False,
    }
    with patch("booking._sb", return_value=_mock_sb_for_happy_path()), \
         patch("booking.stripe.checkout.Session.create") as stripe_create:
        r = client.post("/api/booking/checkout", json=payload)
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
    assert "safeguarding" in r.json().get("detail", "").lower(), (
        f"detail should mention safeguarding, got: {r.json()}"
    )
    assert stripe_create.call_count == 0, (
        "SEC-CONSENT-003 REGRESSION: Stripe session created despite unchecked safeguarding consent"
    )


# ------------------------------------------------------------------------- #
# Acceptance test — proves consent data flows through to Stripe metadata    #
# ------------------------------------------------------------------------- #

def test_accepts_valid_consent_and_passes_metadata_to_stripe():
    """Happy path: consent is captured, passed to Stripe.checkout.Session.create
    as metadata (server-set → tamper-proof from client). Proves the whole
    capture path, not just the reject path.
    """
    payload = {
        **VALID_PAYLOAD_MINIMAL,
        "minors_involved": True,
        "safeguarding_guardian_name": "Jane Doe",
        "safeguarding_consent_accepted": True,
        "model_release_opted_in": False,  # explicitly opted out
    }
    sb_mock = _mock_sb_for_happy_path()
    with patch("booking._sb", return_value=sb_mock), \
         patch("booking._clean_expired_locks"), \
         patch("booking._confirmed_booking_exists", return_value=False), \
         patch("booking._active_lock_exists", return_value=False), \
         patch("booking._rate_limit_or_429"), \
         patch("booking._concurrent_lock_or_429"), \
         patch("booking.stripe.checkout.Session.create", return_value=_mock_stripe_session()) as stripe_create:
        r = client.post("/api/booking/checkout", json=payload)

    assert r.status_code == 200, f"happy path failed: {r.status_code}: {r.text}"
    assert stripe_create.call_count == 1, "Stripe session should have been created once"

    # ---- Migration 010B: consent must land on booking_intents row directly ----
    intent_payload = sb_mock._captured_intent_insert
    assert intent_payload is not None, "booking_intents.insert() was never called"
    assert intent_payload.get("tc_accepted_at"), (
        "SEC-CONSENT-010B REGRESSION: tc_accepted_at missing from booking_intents row — "
        "Stripe-metadata-only fallback would silently lose audit trail on Stripe API failure"
    )
    assert intent_payload.get("tc_accepted_ip"), "tc_accepted_ip missing from intent"
    assert intent_payload.get("model_release_opted_in") is False, (
        f"model_release_opted_in should be False (explicit opt-out), got {intent_payload.get('model_release_opted_in')!r}"
    )
    assert intent_payload.get("minors_involved") is True
    assert intent_payload.get("safeguarding_guardian_name") == "Jane Doe"
    assert intent_payload.get("safeguarding_consent_accepted_at"), (
        "safeguarding_consent_accepted_at missing from intent when minors=true"
    )

    # ---- Migration 010: same info ALSO in Stripe metadata (defense-in-depth) ----
    call_kwargs = stripe_create.call_args.kwargs
    metadata = call_kwargs.get("metadata", {})
    assert metadata.get("consent_tc_at"), "consent_tc_at timestamp missing from Stripe metadata"
    assert metadata.get("consent_tc_ip"), "consent_tc_ip missing from Stripe metadata"
    assert metadata.get("consent_model_release_opted_in") == "false", (
        f"model_release opt-out should serialize as 'false', got {metadata.get('consent_model_release_opted_in')!r}"
    )
    assert metadata.get("consent_minors_involved") == "true", (
        f"minors_involved should serialize as 'true', got {metadata.get('consent_minors_involved')!r}"
    )
    assert metadata.get("consent_guardian_name") == "Jane Doe", (
        f"guardian name mismatch: {metadata.get('consent_guardian_name')!r}"
    )
    assert metadata.get("consent_safeguarding_at"), "safeguarding_at timestamp missing"

    # Also verify existing metadata still present (didn't accidentally overwrite)
    assert metadata.get("booking_intent_id"), "existing booking_intent_id metadata was displaced"
    assert metadata.get("package_id") == "graduation"


def test_accepts_valid_consent_no_minors_omits_safeguarding_metadata():
    """When minors_involved=false, guardian/safeguarding metadata should be
    ABSENT from Stripe metadata AND NULL on the intent row's guardian
    columns — not present-with-empty-string. Keeps the audit trail clean."""
    payload = {**VALID_PAYLOAD_MINIMAL, "minors_involved": False}
    sb_mock = _mock_sb_for_happy_path()
    with patch("booking._sb", return_value=sb_mock), \
         patch("booking._clean_expired_locks"), \
         patch("booking._confirmed_booking_exists", return_value=False), \
         patch("booking._active_lock_exists", return_value=False), \
         patch("booking._rate_limit_or_429"), \
         patch("booking._concurrent_lock_or_429"), \
         patch("booking.stripe.checkout.Session.create", return_value=_mock_stripe_session()) as stripe_create:
        r = client.post("/api/booking/checkout", json=payload)

    assert r.status_code == 200

    # Intent row: guardian columns MUST be NULL, not empty-string
    intent_payload = sb_mock._captured_intent_insert
    assert intent_payload.get("minors_involved") is False
    assert intent_payload.get("safeguarding_guardian_name") is None, (
        f"guardian_name should be NULL when no minors, got {intent_payload.get('safeguarding_guardian_name')!r}"
    )
    assert intent_payload.get("safeguarding_consent_accepted_at") is None, (
        f"safeguarding_at should be NULL when no minors, got {intent_payload.get('safeguarding_consent_accepted_at')!r}"
    )

    # Stripe metadata: same rule, absence not empty-string
    metadata = stripe_create.call_args.kwargs.get("metadata", {})
    assert metadata.get("consent_minors_involved") == "false"
    assert "consent_guardian_name" not in metadata, (
        "guardian_name key should be absent when no minors involved"
    )
    assert "consent_safeguarding_at" not in metadata, (
        "safeguarding_at key should be absent when no minors involved"
    )
