"""Phase 4/5 — pytest for /api/admin/jobs/run-daily-invoicing.

Covers:
  - Auth: unauth, wrong-secret, wrong-audience, wrong-scope → 401/403
  - Invoice branch:
      * Booking exactly 10 days out with no existing invoice → invoice created
      * Same booking, second run same day → skipped_already_exists (idempotency)
      * Booking already fully paid (deposit == budget) → skipped_zero_balance,
        no invoice, no email
  - Reminder branch:
      * Invoice due within 2 days, remaining > 0, reminder_sent_at NULL → reminder sent,
        reminder_sent_at latched
      * Same invoice, second run → skipped (WHERE reminder_sent_at IS NULL filters it out)
      * Manual full payment before reminder → invoice marked paid, reminder_sent_at set,
        NO reminder email fired (the key edge case the user demanded a proof for)

Run:
    ALLOW_ATTACK_SIM=1 pytest -xvs backend/tests/test_daily_invoicing.py
"""
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
import requests
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

# ---------- SAFETY GUARD ----------
if os.environ.get("ALLOW_ATTACK_SIM") != "1":
    raise SystemExit(
        "REFUSED: test_daily_invoicing.py mutates the live Supabase DB. Set "
        "ALLOW_ATTACK_SIM=1 to run."
    )

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://db-bridge-5.preview.emergentagent.com").rstrip("/")
CRON_SECRET = os.environ["CRON_JOB_JWT_SECRET"]
AUD = "flyboy:cron:daily-invoicing"

from supabase import create_client  # noqa: E402
sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def _token(*, scope="cron:invoicing", audience=AUD, secret=None, expired=False):
    now = datetime.now(timezone.utc)
    payload = {
        "aud": audience,
        "scope": scope,
        "iat": int(now.timestamp()),
        "exp": int((now - timedelta(minutes=1) if expired else now + timedelta(minutes=5)).timestamp()),
    }
    return jwt.encode(payload, secret or CRON_SECRET, algorithm="HS256")


def _endpoint(dry_run=False):
    return f"{BASE_URL}/api/admin/jobs/run-daily-invoicing" + ("?dry_run=1" if dry_run else "")


# ---------- Fixture: reserved test client + booking ----------

@pytest.fixture(scope="module")
def test_context():
    """Create one dedicated client + booking so we don't mutate real data.
    The booking's event_date is exactly INVOICE_LEAD_DAYS (10) from today,
    so the invoice branch will pick it up. Cleaned up on teardown.
    """
    marker = uuid.uuid4().hex[:10]
    email = f"cron_test_{marker}@flyboytest.com"

    # Create auth user first (client_id FK to auth.users)
    auth_res = sb.auth.admin.create_user({
        "email": email,
        "email_confirm": True,
        "user_metadata": {"full_name": f"Cron Test {marker}"},
    })
    user_id = auth_res.user.id

    client_row = sb.table("clients").insert({
        "user_id": user_id,
        "email": email,
        "full_name": f"Cron Test {marker}",
        "role": "client",
    }).execute().data[0]

    event_date = (date.today() + timedelta(days=10)).isoformat()
    booking = sb.table("bookings").insert({
        "client_id": client_row["id"],
        "title": "Wedding Videography — Classic",
        "shoot_type": "Wedding Videography",
        "status": "confirmed",
        "event_date": event_date,
        "shoot_date": event_date,
        "budget": 4250.00,
        "is_seed_data": False,
    }).execute().data[0]

    # Seed a paid "deposit" tx via a booking_intent so the balance calc
    # sees £2125 already paid.
    intent = sb.table("booking_intents").insert({
        "email": email,
        "full_name": f"Cron Test {marker}",
        "package_id": "wedding",
        "package_title": "Wedding Videography",
        "tier_name": "Classic",
        "price_total": 4250.00,
        "price_deposit": 2125.00,
        "event_date": event_date,
        "status": "paid",
        "session_id": f"cs_test_seed_{marker}",
    }).execute().data[0]

    sb.table("bookings").update({"booking_intent_id": intent["id"]}).eq("id", booking["id"]).execute()

    sb.table("payment_transactions").insert({
        "session_id": f"cs_test_seed_{marker}",
        "booking_intent_id": intent["id"],
        "email": email,
        "amount": 2125.00,
        "currency": "gbp",
        "status": "completed",
        "payment_status": "paid",
    }).execute()

    ctx = {
        "email": email,
        "user_id": user_id,
        "client_id": client_row["id"],
        "booking_id": booking["id"],
        "booking_intent_id": intent["id"],
        "event_date": event_date,
        "marker": marker,
    }

    yield ctx

    # Teardown — reverse order of FKs
    sb.table("invoices").delete().eq("booking_id", booking["id"]).execute()
    sb.table("payment_transactions").delete().eq("booking_intent_id", intent["id"]).execute()
    sb.table("bookings").delete().eq("id", booking["id"]).execute()
    sb.table("booking_intents").delete().eq("id", intent["id"]).execute()
    sb.table("clients").delete().eq("id", client_row["id"]).execute()
    try:
        sb.auth.admin.delete_user(user_id)
    except Exception:
        pass


# ---------- Auth tests ----------

def test_endpoint_refuses_without_token():
    r = requests.post(_endpoint(), timeout=30)
    assert r.status_code in (401, 403), r.status_code


def test_endpoint_refuses_wrong_secret():
    bad = _token(secret="not_the_real_secret")
    r = requests.post(_endpoint(), headers={"Authorization": f"Bearer {bad}"}, timeout=30)
    assert r.status_code == 401, r.status_code


def test_endpoint_refuses_wrong_audience():
    bad = _token(audience="flyboy:cron:something-else")
    r = requests.post(_endpoint(), headers={"Authorization": f"Bearer {bad}"}, timeout=30)
    assert r.status_code == 401, r.status_code


def test_endpoint_refuses_wrong_scope():
    bad = _token(scope="cron:something-else")
    r = requests.post(_endpoint(), headers={"Authorization": f"Bearer {bad}"}, timeout=30)
    assert r.status_code == 403, r.status_code


def test_endpoint_refuses_expired_token():
    bad = _token(expired=True)
    r = requests.post(_endpoint(), headers={"Authorization": f"Bearer {bad}"}, timeout=30)
    assert r.status_code == 401, r.status_code


# ---------- Invoice branch tests ----------

def _run(dry_run=False):
    tok = _token()
    r = requests.post(_endpoint(dry_run=dry_run), headers={"Authorization": f"Bearer {tok}"}, timeout=60)
    r.raise_for_status()
    return r.json()


def test_invoice_created_for_booking_10_days_out(test_context):
    ctx = test_context
    summary = _run()
    # Find our booking in either created OR skipped_already_exists (depending
    # on whether a prior test in this session already created it).
    created = [x for x in summary["invoices_created"] if x.get("booking_id") == ctx["booking_id"]]
    skipped = [x for x in summary["invoices_skipped_already_exists"] if x.get("booking_id") == ctx["booking_id"]]
    assert created or skipped, f"our booking wasn't touched: {summary}"

    # Whether it fired now or on a prior test, an invoice must exist for it now.
    inv_rows = sb.table("invoices").select("*").eq("booking_id", ctx["booking_id"]).eq(
        "payment_purpose", "balance"
    ).execute().data
    assert len(inv_rows) == 1, f"expected 1 balance invoice, found {len(inv_rows)}"
    inv = inv_rows[0]
    assert float(inv["amount"]) == 2125.00, f"balance calc wrong: {inv['amount']}"
    assert inv["status"] == "sent"


def test_invoice_branch_is_idempotent(test_context):
    """Run twice back-to-back. Second run must see 'already exists', not
    create a second invoice or attempt to insert (which the DB unique
    index would catch as a fallback)."""
    ctx = test_context
    _run()
    summary = _run()

    matched_skip = [x for x in summary["invoices_skipped_already_exists"] if x.get("booking_id") == ctx["booking_id"]]
    matched_create = [x for x in summary["invoices_created"] if x.get("booking_id") == ctx["booking_id"]]
    assert matched_skip and not matched_create, (
        f"second run should have skipped, not created — {summary}"
    )
    # DB truth: still exactly one invoice.
    inv_rows = sb.table("invoices").select("id").eq("booking_id", ctx["booking_id"]).eq(
        "payment_purpose", "balance"
    ).execute().data
    assert len(inv_rows) == 1


def test_invoice_branch_skips_when_zero_balance(test_context):
    """Bump the deposit tx amount to == budget so remaining balance = 0.
    Reset the invoice for this booking so the branch tries to run and
    must skip on the balance calc."""
    ctx = test_context
    # Nuke prior invoice
    sb.table("invoices").delete().eq("booking_id", ctx["booking_id"]).execute()
    # Bump tx to full amount
    sb.table("payment_transactions").update({"amount": 4250.00}).eq(
        "booking_intent_id", ctx["booking_intent_id"]
    ).execute()

    summary = _run()
    matched = [x for x in summary["invoices_skipped_zero_balance"] if x.get("booking_id") == ctx["booking_id"]]
    assert matched, f"expected zero-balance skip: {summary}"

    inv_rows = sb.table("invoices").select("id").eq("booking_id", ctx["booking_id"]).execute().data
    assert not inv_rows, "no invoice should have been created for a fully-paid booking"

    # Restore for later tests
    sb.table("payment_transactions").update({"amount": 2125.00}).eq(
        "booking_intent_id", ctx["booking_intent_id"]
    ).execute()


# ---------- Reminder branch tests ----------

def _seed_invoice_due_soon(ctx, *, days_from_now: int, amount: float = 2125.00):
    """Insert a balance invoice with due_on = today + days_from_now, keep it
    'sent'. Clean before insert to avoid the unique index."""
    sb.table("invoices").delete().eq("booking_id", ctx["booking_id"]).execute()
    due_on = (date.today() + timedelta(days=days_from_now)).isoformat()
    return sb.table("invoices").insert({
        "client_id": ctx["client_id"],
        "booking_id": ctx["booking_id"],
        "source_type": "booking",
        "payment_purpose": "balance",
        "invoice_number": f"INV-BAL-REMTEST-{uuid.uuid4().hex[:8]}",
        "amount": amount,
        "currency": "GBP",
        "status": "sent",
        "issued_on": date.today().isoformat(),
        "due_on": due_on,
        "is_seed_data": False,
    }).execute().data[0]


def test_reminder_fires_when_due_within_2_days(test_context):
    ctx = test_context
    inv = _seed_invoice_due_soon(ctx, days_from_now=1)

    # Also move event_date away from the invoice-branch trigger so we're
    # ONLY testing the reminder branch. Bookings 10 days out get NEW
    # invoices — we already have one so it'd be skipped_already_exists,
    # which is fine, but keep the assertions clean.
    summary = _run()

    matched = [x for x in summary["reminders_sent"] if x.get("invoice_id") == inv["id"]]
    assert matched, f"reminder should have fired: {summary}"

    # DB proof: reminder_sent_at is latched
    inv_now = sb.table("invoices").select("reminder_sent_at, status").eq("id", inv["id"]).execute().data[0]
    assert inv_now["reminder_sent_at"] is not None, "reminder_sent_at not latched"
    assert inv_now["status"] == "sent", "status should remain 'sent' until payment lands"


def test_reminder_is_idempotent(test_context):
    """Second run same day: reminder_sent_at IS NOT NULL, so the query
    filter (is_ null) excludes it. No second email."""
    ctx = test_context
    inv_rows = sb.table("invoices").select("*").eq("booking_id", ctx["booking_id"]).execute().data
    assert inv_rows and inv_rows[0]["reminder_sent_at"] is not None, "precondition: reminder must already be latched from prior test"

    summary = _run()
    matched = [x for x in summary["reminders_sent"] if x.get("invoice_id") == inv_rows[0]["id"]]
    assert not matched, f"reminder fired twice: {summary}"


def test_reminder_suppressed_when_manually_paid_full(test_context):
    """The KEY edge case the user demanded proof of.

    A client pays their balance manually (e.g. bank transfer or manual
    Stripe charge outside the balance-checkout flow) after the invoice
    was created but before the reminder fires. We simulate this by
    inserting an additional payment_transactions row that brings the
    booking to fully-paid state. The reminder branch must:
      - Recompute remaining using the SAME formula as invoicing
      - See remaining ≤ 0
      - Mark the invoice `paid`
      - Latch reminder_sent_at
      - NOT send an email (must not appear in `reminders_sent`)
    """
    ctx = test_context
    # Reset invoice to a fresh "reminder needed" state
    inv = _seed_invoice_due_soon(ctx, days_from_now=1)

    # Simulate manual payment: insert a paid tx tied to the SAME
    # booking_intent, amount = the outstanding balance.
    manual_session = f"cs_test_manual_{uuid.uuid4().hex[:10]}"
    sb.table("payment_transactions").insert({
        "session_id": manual_session,
        "booking_intent_id": ctx["booking_intent_id"],
        "email": ctx["email"],
        "amount": 2125.00,  # covers the balance in full
        "currency": "gbp",
        "status": "completed",
        "payment_status": "paid",
    }).execute()

    try:
        summary = _run()
        matched_sent = [x for x in summary["reminders_sent"] if x.get("invoice_id") == inv["id"]]
        matched_skipped = [x for x in summary["reminders_skipped_paid_manually"] if x.get("invoice_id") == inv["id"]]

        assert not matched_sent, "reminder MUST NOT fire when balance is genuinely settled"
        assert matched_skipped, f"expected manual-paid skip: {summary}"

        inv_now = sb.table("invoices").select("status, reminder_sent_at").eq("id", inv["id"]).execute().data[0]
        assert inv_now["status"] == "paid", "invoice should have been marked paid on manual settlement"
        assert inv_now["reminder_sent_at"] is not None, "reminder_sent_at should latch to prevent re-firing"
    finally:
        sb.table("payment_transactions").delete().eq("session_id", manual_session).execute()


def test_dry_run_does_not_persist(test_context):
    ctx = test_context
    # Reset invoice + fully-paid tx state
    sb.table("invoices").delete().eq("booking_id", ctx["booking_id"]).execute()

    summary = _run(dry_run=True)
    # Whether it landed in created/skipped depends on state; the assertion is
    # that no invoice row exists after the dry run.
    inv_rows = sb.table("invoices").select("id").eq("booking_id", ctx["booking_id"]).execute().data
    assert not inv_rows, "dry-run must not persist an invoice"
    assert summary["dry_run"] is True
