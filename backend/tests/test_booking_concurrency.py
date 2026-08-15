"""Concurrency pytest for the HARD double-booking guard.

What we're proving: the partial unique index
    bookings_one_confirmed_per_date on bookings(event_date) WHERE status = 'confirmed'
holds under simultaneous webhook-time inserts. We do NOT hit real Stripe here —
we mock what the webhook would have received (payment_intent id + session id)
and hammer `_finalise_paid_session()` directly with 10 threads racing against
the same event_date. Exactly one insert must win; the other nine must land in
`status = 'refunded_race'` after Stripe.Refund.create is mocked/short-circuited.
"""
from __future__ import annotations

import concurrent.futures
import os
import uuid
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Import after env load so booking.py picks up STRIPE_SECRET_KEY etc.
import booking  # noqa: E402
from supabase import create_client  # noqa: E402

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

N_RACERS = 10
PROBE_DATE = (date.today() + timedelta(days=730)).isoformat()  # ~2 years out


def _seed_intent_and_tx(idx: int) -> tuple[str, str]:
    """Insert a booking_intents + payment_transactions pair as if
    checkout POST had just finished successfully. Returns (session_id, pi_id).
    All N pairs point at the same PROBE_DATE — that's the whole point."""
    session_id = f"cs_test_race_{uuid.uuid4().hex[:16]}"
    pi_id = f"pi_test_race_{uuid.uuid4().hex[:16]}"
    email = f"racer.{idx}.{uuid.uuid4().hex[:6]}@race.test"
    intent = sb.table("booking_intents").insert({
        "session_id": session_id,
        "email": email,
        "full_name": f"Racer {idx}",
        "package_id": "wedding",
        "package_title": "Wedding Videography",
        "tier_name": "Basic",
        "price_total": 250.0,
        "price_deposit": 125.0,
        "event_date": PROBE_DATE,
        "status": "pending",
    }).execute().data[0]
    sb.table("payment_transactions").insert({
        "session_id": session_id,
        "booking_intent_id": intent["id"],
        "email": email,
        "amount": 125.0,
        "currency": "gbp",
        "status": "initiated",
        "payment_status": "pending",
        "stripe_payment_intent_id": pi_id,
    }).execute()
    return session_id, pi_id


def _cleanup():
    # Wipe everything we produced under PROBE_DATE / racer emails.
    intents = sb.table("booking_intents").select("id,email").eq("event_date", PROBE_DATE).execute().data or []
    intent_ids = [i["id"] for i in intents]
    emails = [i["email"] for i in intents]
    # bookings
    sb.table("bookings").delete().eq("event_date", PROBE_DATE).execute()
    # payment_transactions by intent
    if intent_ids:
        sb.table("payment_transactions").delete().in_("booking_intent_id", intent_ids).execute()
    # locks
    sb.table("date_slot_locks").delete().eq("event_date", PROBE_DATE).execute()
    # intents
    sb.table("booking_intents").delete().eq("event_date", PROBE_DATE).execute()
    # any auth users we created via the finalise path
    for e in emails:
        try:
            url = os.environ["SUPABASE_URL"].rstrip("/") + f"/auth/v1/admin/users?email={e}"
            headers = {
                "apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
                "Authorization": f"Bearer {os.environ['SUPABASE_SERVICE_ROLE_KEY']}",
            }
            import httpx
            with httpx.Client(timeout=10.0) as c:
                r = c.get(url, headers=headers)
            users = (r.json().get("users") or []) if isinstance(r.json(), dict) else []
            for u in users:
                if (u.get("email") or "").lower() == e.lower():
                    sb.auth.admin.delete_user(u["id"])
                    sb.table("clients").delete().eq("user_id", u["id"]).execute()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def _clean_around_each_test():
    _cleanup()
    yield
    _cleanup()


def test_only_one_confirmed_booking_wins_under_concurrent_inserts():
    """Fire 10 finalisers in parallel against the same event_date. Exactly
    one succeeds, the other nine must be refunded_race — proving the DB
    unique index is the source of truth, not application-level checks.
    """
    pairs = [_seed_intent_and_tx(i) for i in range(N_RACERS)]

    refund_calls = []

    def _fake_refund_create(**kwargs):
        refund_calls.append(kwargs)
        return {"id": f"re_test_{uuid.uuid4().hex[:16]}", "status": "succeeded", **kwargs}

    # Stub out cross-service calls we don't want to test here (real Stripe
    # network, GoTrue admin API, Resend). We only care about the DB race.
    def _stub_invite(email): return f"https://portal.test/set-password?email={email}"
    def _stub_send(*a, **kw): return None
    def _stub_ensure_auth_user(sb_, email, full_name):
        # Return a fake user_id; we don't actually need auth for the race test.
        return f"user_{uuid.uuid4().hex[:16]}"

    # A shared "clients" row for all N racers keeps the client_id FK valid
    # without hitting Supabase Auth N times (which is what caused the
    # transient RemoteProtocolError we don't want in the assertion).
    admins = sb.table("clients").select("id").limit(1).execute().data
    assert admins, "need at least one existing clients row for the race test FK"
    shared_client_id = admins[0]["id"]

    def _stub_ensure_client(sb_, user_id, email, full_name, phone):
        return shared_client_id

    def _run(pair):
        sid, pi = pair
        try:
            return booking._finalise_paid_session(sid, pi)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    with patch("booking.stripe.Refund.create", side_effect=_fake_refund_create), \
         patch("booking._generate_invite_link", side_effect=_stub_invite), \
         patch("booking._send_confirmation_email", side_effect=_stub_send), \
         patch("booking._ensure_auth_user", side_effect=_stub_ensure_auth_user), \
         patch("booking._ensure_client_row", side_effect=_stub_ensure_client):
        with concurrent.futures.ThreadPoolExecutor(max_workers=N_RACERS) as ex:
            results = list(ex.map(_run, pairs))

    # If any transient HTTP-level error slipped in, we retry that racer once —
    # in production Stripe would redeliver the webhook. This isolates the
    # test to "does the unique index arbitrate correctly?".
    with patch("booking.stripe.Refund.create", side_effect=_fake_refund_create), \
         patch("booking._generate_invite_link", side_effect=_stub_invite), \
         patch("booking._send_confirmation_email", side_effect=_stub_send), \
         patch("booking._ensure_auth_user", side_effect=_stub_ensure_auth_user), \
         patch("booking._ensure_client_row", side_effect=_stub_ensure_client):
        for i, r in enumerate(results):
            if isinstance(r, dict) and "error" in r:
                sid, pi = pairs[i]
                try:
                    results[i] = booking._finalise_paid_session(sid, pi)
                except Exception as e:
                    results[i] = {"error_retry": f"{type(e).__name__}: {e}"}

    # 1. Exactly one confirmed booking exists for PROBE_DATE.
    confirmed = sb.table("bookings").select("id, stripe_session_id").eq(
        "event_date", PROBE_DATE
    ).eq("status", "confirmed").execute().data
    assert len(confirmed) == 1, f"expected 1 confirmed booking, got {len(confirmed)}: {confirmed}"

    # 2. Winner is exactly one of our N session_ids.
    winner_sid = confirmed[0]["stripe_session_id"]
    assert winner_sid in {p[0] for p in pairs}

    # 3. All other transactions are refunded_race and refunds were issued.
    losers = sb.table("payment_transactions").select("session_id, status, payment_status").in_(
        "session_id", [p[0] for p in pairs]
    ).execute().data
    losers_sorted = sorted(losers, key=lambda r: r["session_id"])
    winners = [r for r in losers_sorted if r["payment_status"] == "paid"]
    refunded = [r for r in losers_sorted if r["status"] == "refunded_race"]
    assert len(winners) == 1, f"expected 1 paid winner, got {len(winners)}: {winners}"
    assert len(refunded) == N_RACERS - 1, (
        f"expected {N_RACERS - 1} refunded_race, got {len(refunded)}: {refunded}"
    )

    # 4. Refund API was called once per loser.
    assert len(refund_calls) == N_RACERS - 1, (
        f"expected {N_RACERS - 1} refund calls, got {len(refund_calls)}"
    )
    # 5. Every refund call carried a payment_intent id.
    for call in refund_calls:
        assert call.get("payment_intent", "").startswith("pi_test_race_")

    # 6. No dangling date_slot_lock for the winner (finaliser deletes it).
    remaining_locks = sb.table("date_slot_locks").select("*").eq("event_date", PROBE_DATE).execute().data
    assert remaining_locks == [], f"expected no locks, got {remaining_locks}"
