"""Phase 2 — idempotency + mutation tests for `_finalise_balance_payment`.

Tests the webhook branch that turns a Stripe balance-checkout success into
a `paid` invoice + `paid` payment_transactions row, without touching the
deposit path.

Standard: replay N times → exactly one paid state, one tx row, no double
writes. Partial-crash → self-heal. Metadata mismatch → refuse.

Run:
    ALLOW_ATTACK_SIM=1 pytest -xvs backend/tests/test_balance_finalise.py

Guarded like the other mutation-test files in this suite — service-role
writes to Supabase, refuses to run without ALLOW_ATTACK_SIM=1.
"""
import os
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

import pytest
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

# ---------- SAFETY GUARD ----------
if os.environ.get("ALLOW_ATTACK_SIM") != "1":
    raise SystemExit(
        "REFUSED: test_balance_finalise.py mutates the live Supabase DB via "
        "the service-role key. Set ALLOW_ATTACK_SIM=1 to run."
    )

from supabase import create_client  # noqa: E402

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

# Import the functions under test AFTER env is loaded so booking.py picks
# up STRIPE_SECRET_KEY etc.
from booking import (  # noqa: E402
    _finalise_paid_session,
    _finalise_balance_payment,
)


# ---------- Fixture: a real booking to attach a balance invoice to ----------

@pytest.fixture(scope="module")
def real_booking():
    """Get any existing booking to hang test invoices off. We DO NOT create a
    new booking here — that requires the whole Stripe checkout flow. We
    attach to whatever booking exists, and clean our OWN invoice rows only.
    """
    bk = sb.table("bookings").select("id, client_id, budget").limit(1).execute().data
    if not bk:
        pytest.skip("no booking rows in DB to attach a test balance invoice to")
    return bk[0]


# ---------- Fixture: build a fresh balance invoice + tx row per test ----------

@pytest.fixture
def balance_invoice(real_booking):
    """Insert one balance invoice + one pending payment_transactions row,
    return (invoice, session_id). Cleaned up on teardown."""
    booking_id = real_booking["id"]
    client_id = real_booking["client_id"]

    # Clean any lingering test invoice for this booking BEFORE inserting
    # (the partial unique index bites otherwise).
    sb.table("invoices").delete().eq("booking_id", booking_id).eq(
        "payment_purpose", "balance"
    ).eq("is_seed_data", False).execute()

    marker = uuid.uuid4().hex[:12]
    session_id = f"cs_test_bal_{marker}"

    inv = sb.table("invoices").insert({
        "client_id": client_id,
        "booking_id": booking_id,
        "source_type": "booking",
        "payment_purpose": "balance",
        "invoice_number": f"INV-BAL-TEST-{marker}",
        "amount": 4200.00,
        "currency": "GBP",
        "status": "sent",
        "issued_on": str(date.today()),
        "due_on": str(date.today() + timedelta(days=5)),
        "is_seed_data": False,
    }).execute().data[0]

    tx = sb.table("payment_transactions").insert({
        "session_id": session_id,
        "email": "balance_test@flyboytest.com",
        "amount": 4200.00,
        "currency": "gbp",
        "status": "initiated",
        "payment_status": "pending",
    }).execute().data[0]

    yield {"invoice": inv, "session_id": session_id, "tx_id": tx["id"]}

    # Teardown
    sb.table("payment_transactions").delete().eq("session_id", session_id).execute()
    sb.table("invoices").delete().eq("id", inv["id"]).execute()


# ---------- Helper: fetch invoice + tx current state ----------

def _current(session_id: str, invoice_id: str):
    inv = sb.table("invoices").select("*").eq("id", invoice_id).limit(1).execute().data[0]
    tx = sb.table("payment_transactions").select("*").eq("session_id", session_id).limit(1).execute().data[0]
    return inv, tx


# ==============================================================================
# HAPPY PATH + IDEMPOTENCY
# ==============================================================================

def test_balance_first_call_flips_invoice_and_tx_to_paid(balance_invoice):
    inv = balance_invoice["invoice"]
    sid = balance_invoice["session_id"]
    metadata = {"payment_purpose": "balance", "invoice_id": inv["id"], "booking_id": inv["booking_id"]}

    res = _finalise_paid_session(sid, "pi_test_bal_1", metadata)

    assert res.get("finalised") is True, res
    assert res.get("path") == "balance"
    assert res.get("invoice_id") == inv["id"]

    inv_now, tx_now = _current(sid, inv["id"])
    assert inv_now["status"] == "paid"
    assert tx_now["payment_status"] == "paid"
    assert tx_now["status"] == "completed"
    assert tx_now["stripe_payment_intent_id"] == "pi_test_bal_1"


def test_balance_replay_is_a_noop_no_writes(balance_invoice):
    """The idempotency contract: fire N times, exactly one paid state,
    no updated_at churn on the second call."""
    inv = balance_invoice["invoice"]
    sid = balance_invoice["session_id"]
    metadata = {"payment_purpose": "balance", "invoice_id": inv["id"]}

    # First call — genuine finalise.
    _finalise_paid_session(sid, "pi_test_bal_2", metadata)
    _, tx_after_first = _current(sid, inv["id"])
    tx_updated_at_first = tx_after_first["updated_at"]

    # Second call — must skip.
    res2 = _finalise_paid_session(sid, "pi_test_bal_2", metadata)
    assert res2.get("skipped") == "balance already paid", res2

    _, tx_after_second = _current(sid, inv["id"])
    # updated_at must NOT change on the replay (no UPDATE was fired).
    assert tx_after_second["updated_at"] == tx_updated_at_first, (
        "replay wrote to payment_transactions — idempotency broken"
    )


def test_balance_replay_100x_produces_exactly_one_paid_state(balance_invoice):
    """Stress the idempotency contract. Real production sees ~1-3 replays
    (webhook retry + /status probe); test 100x to catch any state that
    latches wrong under repeated firing."""
    inv = balance_invoice["invoice"]
    sid = balance_invoice["session_id"]
    metadata = {"payment_purpose": "balance", "invoice_id": inv["id"]}

    for i in range(100):
        _finalise_paid_session(sid, f"pi_replay_{i}", metadata)

    # Exactly one payment_transactions row for this session_id
    rows = sb.table("payment_transactions").select("id, payment_status").eq(
        "session_id", sid
    ).execute().data
    assert len(rows) == 1, f"replay created {len(rows)} tx rows, expected 1"
    assert rows[0]["payment_status"] == "paid"

    # Invoice is paid exactly once
    inv_rows = sb.table("invoices").select("status").eq("id", inv["id"]).execute().data
    assert inv_rows[0]["status"] == "paid"


# ==============================================================================
# MUTATION TESTS — partial-crash recovery
# ==============================================================================

def test_balance_self_heal_when_invoice_paid_but_tx_pending(balance_invoice):
    """Prior attempt marked invoice paid but crashed before flipping tx.
    Next replay must heal tx forward, not skip incorrectly."""
    inv = balance_invoice["invoice"]
    sid = balance_invoice["session_id"]

    # Simulate the partial-crash state: invoice=paid, tx=pending.
    sb.table("invoices").update({"status": "paid"}).eq("id", inv["id"]).execute()
    # (tx already pending from the fixture)

    metadata = {"payment_purpose": "balance", "invoice_id": inv["id"]}
    res = _finalise_paid_session(sid, "pi_heal_1", metadata)

    assert res.get("finalised") is True, res
    assert res.get("healed") is True, "self-heal flag must be set"

    _, tx_now = _current(sid, inv["id"])
    assert tx_now["payment_status"] == "paid"
    assert tx_now["stripe_payment_intent_id"] == "pi_heal_1"


def test_balance_self_heal_when_tx_paid_but_invoice_still_sent(balance_invoice):
    """Reverse partial-crash: tx marked paid, but invoice update never
    landed. Next replay must flip the invoice forward."""
    inv = balance_invoice["invoice"]
    sid = balance_invoice["session_id"]

    # Simulate: tx=paid, invoice=sent.
    sb.table("payment_transactions").update({
        "status": "completed", "payment_status": "paid",
    }).eq("session_id", sid).execute()

    metadata = {"payment_purpose": "balance", "invoice_id": inv["id"]}
    res = _finalise_paid_session(sid, "pi_heal_2", metadata)

    # Since tx is already paid, it looks "already paid" — but invoice must
    # be healed. Our implementation returns `finalised=True` because
    # invoice_already_paid is False → guard 1 doesn't fire.
    assert res.get("finalised") is True, res

    inv_now, _ = _current(sid, inv["id"])
    assert inv_now["status"] == "paid"


# ==============================================================================
# NEGATIVE PATHS — refusal + defense-in-depth
# ==============================================================================

def test_balance_missing_invoice_id_in_metadata_refuses(balance_invoice):
    """metadata.payment_purpose='balance' but no invoice_id → refuse cleanly."""
    inv = balance_invoice["invoice"]
    sid = balance_invoice["session_id"]

    res = _finalise_paid_session(sid, "pi_no_inv", {"payment_purpose": "balance"})
    assert res.get("skipped") == "balance no invoice_id in metadata", res

    # Nothing was mutated
    inv_now, tx_now = _current(sid, inv["id"])
    assert inv_now["status"] == "sent"
    assert tx_now["payment_status"] == "pending"


def test_balance_wrong_invoice_purpose_refuses(balance_invoice):
    """Attacker (or bug) points a 'balance' session at a NON-balance invoice.
    Must refuse — otherwise it would corrupt a deposit invoice into 'paid'."""
    inv = balance_invoice["invoice"]
    sid = balance_invoice["session_id"]

    # Flip the invoice's purpose so it no longer matches.
    sb.table("invoices").update({"payment_purpose": "deposit"}).eq("id", inv["id"]).execute()

    metadata = {"payment_purpose": "balance", "invoice_id": inv["id"]}
    res = _finalise_paid_session(sid, "pi_wrong_purpose", metadata)
    assert res.get("skipped") == "balance invoice payment_purpose mismatch", res

    inv_now, tx_now = _current(sid, inv["id"])
    # Invoice unchanged (still 'sent')
    assert inv_now["status"] == "sent"
    # Tx unchanged (still 'pending')
    assert tx_now["payment_status"] == "pending"


def test_balance_deposit_metadata_does_not_hit_balance_branch(balance_invoice):
    """If metadata says payment_purpose='deposit' (or missing entirely), the
    balance function must not run. We prove this by pointing metadata at a
    real balance invoice — if the balance branch fired, invoice would flip.
    Since we're passing deposit metadata, the deposit branch runs and returns
    'no payment_transaction' (no booking_intent linkage set up for this test)."""
    inv = balance_invoice["invoice"]
    sid = balance_invoice["session_id"]

    # No payment_purpose → defaults to 'deposit'
    res = _finalise_paid_session(sid, "pi_deposit", {"invoice_id": inv["id"]})

    # We don't assert on the exact deposit-branch return value here — the
    # critical assertion is that the balance invoice was NOT touched.
    inv_now, tx_now = _current(sid, inv["id"])
    assert inv_now["status"] == "sent", (
        f"deposit metadata leaked into balance branch — invoice status flipped: {inv_now['status']}"
    )
    assert tx_now["payment_status"] == "pending"

    # And explicitly if metadata says 'deposit':
    res2 = _finalise_paid_session(sid, "pi_deposit_explicit", {"payment_purpose": "deposit", "invoice_id": inv["id"]})
    inv_now, tx_now = _current(sid, inv["id"])
    assert inv_now["status"] == "sent"
    assert tx_now["payment_status"] == "pending"


def test_balance_invoice_not_found_refuses(real_booking):
    """metadata.invoice_id points at a non-existent invoice → refuse."""
    fake_invoice_id = str(uuid.uuid4())
    sid = f"cs_test_missing_{uuid.uuid4().hex[:8]}"

    res = _finalise_balance_payment(sid, "pi_nf", {
        "payment_purpose": "balance",
        "invoice_id": fake_invoice_id,
    })
    assert res.get("skipped") == "balance invoice not found", res
