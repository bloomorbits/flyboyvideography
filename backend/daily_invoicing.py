"""Daily balance-invoicing job — Phase 4/5 of automated balance collection.

Endpoint: POST /api/admin/jobs/run-daily-invoicing
Auth: bearer token, signed with CRON_JOB_JWT_SECRET (deliberately NOT the
      general admin/session secret — narrow blast radius per SEC-001).

Two branches, both idempotent and re-runnable N times per day:

 1. INVOICE branch — create a balance invoice for any confirmed booking
    whose event_date is exactly `INVOICE_LEAD_DAYS` (default 10) days out
    and which doesn't already have a balance invoice.
    Balance formula:
        bookings.budget − Σ(payment_transactions.amount WHERE payment_status='paid')
        scoped to the booking (via booking_intent_id → booking_intents.id → matching booking).
    If the recomputed balance is <= 0, no invoice is created and the
    booking is skipped (edge case: bloated deposit / manual pre-payment).

 2. REMINDER branch — for balance invoices where due_on <= today+2 AND
    reminder_sent_at IS NULL AND status='sent':
      - Recompute the remaining balance using the SAME formula as invoicing.
      - If remaining <= 0 (client paid manually / partial paid outside of
        Stripe checkout): mark invoice paid, set reminder_sent_at (latches
        it closed), do NOT send email.
      - Else: send reminder email, set reminder_sent_at.

Physical safety net: `invoices_one_balance_per_booking_uniq` (Migration 012)
blocks a duplicate insert at the DB layer if two cron runs race. This code
should never fire that path (the "already exists" pre-check filters first),
but it's the belt to the "app-check" braces.
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import create_client

log = logging.getLogger(__name__)

router = APIRouter()

# ---------- Config ----------
CRON_JOB_JWT_SECRET = os.environ.get("CRON_JOB_JWT_SECRET", "")
CRON_JOB_JWT_AUDIENCE = "flyboy:cron:daily-invoicing"
INVOICE_LEAD_DAYS = int(os.environ.get("INVOICE_LEAD_DAYS", "10"))
REMINDER_LEAD_DAYS = int(os.environ.get("REMINDER_LEAD_DAYS", "2"))

_bearer = HTTPBearer(auto_error=False)


def _sb():
    from server import get_sb  # lazy — avoids circular
    return get_sb()


def _require_cron_token(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    """Verify the caller holds a JWT signed with CRON_JOB_JWT_SECRET and
    with the expected `aud` claim. Fails closed on any hiccup.

    This is deliberately not the admin session token: a leaked cron token
    can only invoke this ONE endpoint (blast radius scoped to
    balance-invoicing) — it can't read clients, list bookings, or edit
    anything else.
    """
    if not CRON_JOB_JWT_SECRET:
        raise HTTPException(503, "CRON_JOB_JWT_SECRET not configured on the server.")
    if not creds:
        raise HTTPException(401, "Cron bearer token required.")
    try:
        payload = jwt.decode(
            creds.credentials,
            CRON_JOB_JWT_SECRET,
            algorithms=["HS256"],
            audience=CRON_JOB_JWT_AUDIENCE,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Cron token expired.")
    except jwt.InvalidAudienceError:
        raise HTTPException(401, "Cron token audience mismatch.")
    except jwt.PyJWTError as e:
        # Specific diagnostic for the "raw secret pasted into Authorization
        # header instead of a signed JWT" failure mode. A real HS256 JWT
        # is always three dot-separated base64url segments. If the caller
        # posted a bare token_urlsafe secret (no dots), the message from
        # PyJWT is inscrutable ("Invalid header string: 'utf-8' can't
        # decode byte 0x9e..."). Detect and say plainly what happened.
        tok = creds.credentials or ""
        if tok.count(".") != 2:
            log.warning(
                "cron token verify failed — received %d-char string with %d dots; "
                "expected a signed HS256 JWT (three dot-separated segments). "
                "Most likely the cron command is posting the raw "
                "CRON_JOB_JWT_SECRET instead of minting a JWT signed with it. "
                "See docs/BALANCE_INVOICING_RUNBOOK.md for the correct mint-and-post one-liner.",
                len(tok), tok.count("."),
            )
            raise HTTPException(
                401,
                "Cron token malformed — expected a signed JWT (3 dot-separated segments). "
                "Check the cron command mints a JWT rather than posting the secret directly.",
            )
        log.warning("cron token verify failed: %s", e)
        raise HTTPException(401, "Invalid cron token.")
    # Scope claim — belt-and-braces so a future secret shared across
    # multiple cron jobs still can't dispatch to the wrong endpoint.
    if payload.get("scope") != "cron:invoicing":
        raise HTTPException(403, "Cron token scope mismatch.")
    return payload


# ---------- Balance calculation ----------

def _paid_amount_for_booking(sb, booking_id: str) -> float:
    """Sum of payment_transactions.amount for a booking, joined via the
    booking_intents table. Only rows with payment_status='paid' count.

    Deposit payments live under booking_intent_id (tied to the intent that
    kicked off the checkout). Balance payments are linked via metadata.invoice_id
    (invoice.booking_id = this booking) — since payment_transactions has no
    invoice_id column, we walk back through invoices to catch those.
    """
    # 1. Deposit(s): payment_transactions → booking_intents where the intent
    #    ended up producing this booking.
    intent_rows = sb.table("booking_intents").select("id").eq(
        "status", "paid"
    ).execute().data or []
    booking_row = sb.table("bookings").select("booking_intent_id").eq(
        "id", booking_id
    ).limit(1).execute().data
    intent_id = booking_row[0]["booking_intent_id"] if booking_row else None

    deposit_total = 0.0
    if intent_id:
        d = sb.table("payment_transactions").select("amount").eq(
            "booking_intent_id", intent_id
        ).eq("payment_status", "paid").execute().data or []
        deposit_total = sum(float(r["amount"]) for r in d)

    # 2. Balance(s) already paid via balance-checkout: session_id known via
    #    Stripe metadata → we can't join in SQL. Instead we walk the paid
    #    invoices for this booking; the amount on the invoice equals the
    #    balance that was collected.
    paid_inv = sb.table("invoices").select("amount").eq(
        "booking_id", booking_id
    ).eq("payment_purpose", "balance").eq("status", "paid").eq(
        "is_seed_data", False
    ).execute().data or []
    balance_total = sum(float(r["amount"]) for r in paid_inv)

    return deposit_total + balance_total


def _remaining_balance(sb, booking: dict) -> float:
    budget = float(booking.get("budget") or 0.0)
    paid = _paid_amount_for_booking(sb, booking["id"])
    return round(budget - paid, 2)


# ---------- Email rendering ----------

def _load(name: str) -> str:
    return (Path(__file__).parent / "emails" / name).read_text(encoding="utf-8")


def _fmt_gbp(amount: float) -> str:
    return f"£{amount:,.2f}"


def _fmt_event_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return d.strftime("%A, %-d %B %Y")


def _fmt_due(iso: str) -> str:
    d = date.fromisoformat(iso)
    return d.strftime("%-d %B %Y")


def _render_balance_email(
    kind: str,               # "invoice" | "reminder"
    *,
    first_name: str,
    package_title: str,
    tier_name: str,
    event_date_iso: str,
    package_total: float,
    deposit_paid: float,
    balance_due: float,
    due_on_iso: str,
    checkout_url: str,
) -> tuple[str, str]:
    if kind == "invoice":
        html_tpl = _load("balance_invoice.html")
        text_tpl = _load("balance_invoice.txt")
    elif kind == "reminder":
        html_tpl = _load("balance_reminder.html")
        text_tpl = _load("balance_reminder.txt")
    else:
        raise ValueError(f"unknown balance email kind: {kind!r}")

    import html as _html
    tier_suffix = f" — {tier_name}" if tier_name else ""
    ctx = {
        "{{first_name}}": _html.escape((first_name or "there").split(" ")[0] or "there"),
        "{{package_title}}": _html.escape(package_title or "Your booking"),
        "{{tier_suffix}}": _html.escape(tier_suffix),
        "{{event_date}}": _fmt_event_date(event_date_iso),
        "{{package_total}}": _fmt_gbp(package_total),
        "{{deposit_paid}}": _fmt_gbp(deposit_paid),
        "{{balance_due}}": _fmt_gbp(balance_due),
        "{{due_on}}": _fmt_due(due_on_iso),
        "{{checkout_url}}": checkout_url,
    }
    html_body = html_tpl
    text_body = text_tpl
    for k, v in ctx.items():
        html_body = html_body.replace(k, v)
        text_body = text_body.replace(k, v)
    return html_body, text_body


def _send_email(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    """Best-effort Resend send. Failures logged, do not raise — the invoice
    was persisted BEFORE the send, so a Resend outage doesn't roll back
    the DB record (the operator can resend from the DB row)."""
    import httpx
    resend_key = os.environ.get("RESEND_API_KEY", "")
    resend_from = os.environ.get("RESEND_FROM_EMAIL", "Flyboy Videography <bookings@flyboyvideography.com>")
    if not resend_key:
        log.warning("RESEND_API_KEY not set — skipping balance email to %s", to_email)
        return
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {resend_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": resend_from,
                    "to": [to_email],
                    "subject": subject,
                    "html": html_body,
                    "text": text_body,
                },
            )
        if r.status_code >= 400:
            log.warning("Resend send failed %s: %s", r.status_code, r.text[:400])
    except Exception as e:
        log.warning("Resend send exception: %s", e)


def _generate_invoice_number(sb) -> str:
    """Simple sequential-ish invoice number. Format: INV-BAL-YYYYMMDD-XXXX."""
    import secrets
    return f"INV-BAL-{date.today().strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"


# ---------- Public payment URL ----------

def _pay_balance_url(invoice_id: str) -> str:
    """Public URL the client hits from the email. Redirects to a fresh
    Stripe Checkout Session (see booking.pay_balance_redirect)."""
    api_base = os.environ.get("PUBLIC_API_BASE") or os.environ.get("REACT_APP_BACKEND_URL", "")
    return f"{api_base.rstrip('/')}/api/booking/pay-balance/{invoice_id}"


# ---------- The endpoint ----------

@router.post("/api/admin/jobs/run-daily-invoicing")
def run_daily_invoicing(request: Request, _claims: dict = Depends(_require_cron_token)):
    """Idempotent daily job. Safe to run N times per day; safe to run at
    any hour. Returns a summary of what fired.

    Query params (all optional; defaults from env):
      - dry_run=1 : compute but do not write / send

    Audit trail (Migration 014):
      * INSERT a `cron_runs` row at start (finished_at=NULL, ok=true default).
      * UPDATE that row with the full summary + error_count + finished_at
        + ok=(error_count==0) at the end.
      * If Migration 014 hasn't been applied, both write attempts silently
        fail and the invoicing work proceeds unaffected — the audit is
        best-effort by design.
    """
    dry_run = request.query_params.get("dry_run") == "1"
    sb = _sb()
    today = date.today()
    invoice_target_date = (today + timedelta(days=INVOICE_LEAD_DAYS)).isoformat()
    reminder_cutoff = (today + timedelta(days=REMINDER_LEAD_DAYS)).isoformat()

    # ---- Audit: open a run record ----
    run_id: Optional[str] = None
    try:
        row = sb.table("cron_runs").insert({
            "job_name": "daily_invoicing",
            "summary": {"dry_run": dry_run},
        }).execute().data
        if row:
            run_id = row[0]["id"]
    except Exception as e:
        # Silent — best-effort audit. Never block the actual work.
        log.warning("cron_runs audit-open failed (Mig 014 not applied?): %s", e)

    summary = {
        "date": today.isoformat(),
        "dry_run": dry_run,
        "invoice_target_date": invoice_target_date,
        "reminder_cutoff": reminder_cutoff,
        "invoices_created": [],
        "invoices_skipped_zero_balance": [],
        "invoices_skipped_already_exists": [],
        "reminders_sent": [],
        "reminders_skipped_paid_manually": [],
        "errors": [],
    }

    # ================================================================
    # 1. INVOICE BRANCH — bookings exactly INVOICE_LEAD_DAYS out
    # ================================================================
    bookings = sb.table("bookings").select(
        "id, client_id, title, shoot_type, event_date, budget, is_seed_data"
    ).eq("status", "confirmed").eq("event_date", invoice_target_date).eq(
        "is_seed_data", False
    ).execute().data or []

    for bk in bookings:
        try:
            existing = sb.table("invoices").select("id").eq(
                "booking_id", bk["id"]
            ).eq("payment_purpose", "balance").eq("is_seed_data", False).execute().data
            if existing:
                summary["invoices_skipped_already_exists"].append({
                    "booking_id": bk["id"], "invoice_id": existing[0]["id"],
                })
                continue

            remaining = _remaining_balance(sb, bk)
            if remaining <= 0.005:  # £0.01 tolerance for float rounding
                summary["invoices_skipped_zero_balance"].append({
                    "booking_id": bk["id"], "remaining": remaining,
                })
                continue

            if dry_run:
                summary["invoices_created"].append({
                    "booking_id": bk["id"], "amount": remaining, "dry_run": True,
                })
                continue

            cl = sb.table("clients").select("email, full_name").eq(
                "id", bk["client_id"]
            ).limit(1).execute().data
            if not cl:
                summary["errors"].append({"booking_id": bk["id"], "err": "client not found"})
                continue
            client_email = cl[0]["email"]

            inv_row = sb.table("invoices").insert({
                "client_id": bk["client_id"],
                "booking_id": bk["id"],
                "source_type": "booking",
                "payment_purpose": "balance",
                "invoice_number": _generate_invoice_number(sb),
                "amount": remaining,
                "currency": "GBP",
                "status": "sent",
                "issued_on": today.isoformat(),
                "due_on": (date.fromisoformat(bk["event_date"]) - timedelta(days=3)).isoformat(),
                "is_seed_data": False,
            }).execute().data[0]

            # Parse title / tier
            title = bk.get("title") or ""
            if " — " in title:
                package_title, tier_name = title.split(" — ", 1)
            else:
                package_title, tier_name = title, ""

            budget = float(bk["budget"] or 0.0)
            deposit_paid = budget - remaining
            checkout_url = _pay_balance_url(inv_row["id"])

            html_body, text_body = _render_balance_email(
                "invoice",
                first_name=(cl[0].get("full_name") or "").split(" ")[0] or "there",
                package_title=package_title,
                tier_name=tier_name,
                event_date_iso=bk["event_date"],
                package_total=budget,
                deposit_paid=deposit_paid,
                balance_due=remaining,
                due_on_iso=inv_row["due_on"],
                checkout_url=checkout_url,
            )
            subject = f"Balance due for your {package_title} — {_fmt_event_date(bk['event_date'])}"
            _send_email(client_email, subject, html_body, text_body)

            summary["invoices_created"].append({
                "booking_id": bk["id"],
                "invoice_id": inv_row["id"],
                "amount": remaining,
                "due_on": inv_row["due_on"],
                "email_sent_to": client_email,
            })
        except Exception as e:
            log.exception("invoice branch failed for booking %s", bk.get("id"))
            summary["errors"].append({"booking_id": bk.get("id"), "err": f"{type(e).__name__}: {e}"})

    # ================================================================
    # 2. REMINDER BRANCH — balance invoices due within REMINDER_LEAD_DAYS
    # ================================================================
    due_inv = sb.table("invoices").select(
        "id, client_id, booking_id, amount, due_on, invoice_number"
    ).eq("payment_purpose", "balance").eq("status", "sent").is_(
        "reminder_sent_at", "null"
    ).lte("due_on", reminder_cutoff).eq("is_seed_data", False).execute().data or []

    for inv in due_inv:
        try:
            bk_rows = sb.table("bookings").select(
                "id, title, event_date, budget"
            ).eq("id", inv["booking_id"]).limit(1).execute().data
            if not bk_rows:
                summary["errors"].append({"invoice_id": inv["id"], "err": "booking not found"})
                continue
            bk = bk_rows[0]

            remaining = _remaining_balance(sb, bk)

            if remaining <= 0.005:
                # Client paid manually / outside checkout. Mark invoice
                # paid and latch reminder_sent_at closed so we don't loop.
                if not dry_run:
                    sb.table("invoices").update({
                        "status": "paid",
                        "reminder_sent_at": _now_iso(),
                    }).eq("id", inv["id"]).execute()
                summary["reminders_skipped_paid_manually"].append({
                    "invoice_id": inv["id"],
                    "booking_id": bk["id"],
                    "remaining": remaining,
                })
                continue

            if dry_run:
                summary["reminders_sent"].append({
                    "invoice_id": inv["id"], "remaining": remaining, "dry_run": True,
                })
                continue

            cl = sb.table("clients").select("email, full_name").eq(
                "id", inv["client_id"]
            ).limit(1).execute().data
            if not cl:
                summary["errors"].append({"invoice_id": inv["id"], "err": "client not found"})
                continue
            client_email = cl[0]["email"]

            title = bk.get("title") or ""
            if " — " in title:
                package_title, tier_name = title.split(" — ", 1)
            else:
                package_title, tier_name = title, ""

            budget = float(bk["budget"] or 0.0)
            deposit_paid = budget - remaining
            checkout_url = _pay_balance_url(inv["id"])

            html_body, text_body = _render_balance_email(
                "reminder",
                first_name=(cl[0].get("full_name") or "").split(" ")[0] or "there",
                package_title=package_title,
                tier_name=tier_name,
                event_date_iso=bk["event_date"],
                package_total=budget,
                deposit_paid=deposit_paid,
                balance_due=remaining,
                due_on_iso=inv["due_on"],
                checkout_url=checkout_url,
            )
            subject = f"Friendly nudge — balance for your {_fmt_event_date(bk['event_date'])} booking"
            _send_email(client_email, subject, html_body, text_body)

            # Latch reminder_sent_at so we NEVER fire twice for the same
            # invoice, even if the cron runs multiple times today.
            sb.table("invoices").update({
                "reminder_sent_at": _now_iso(),
            }).eq("id", inv["id"]).is_("reminder_sent_at", "null").execute()

            summary["reminders_sent"].append({
                "invoice_id": inv["id"],
                "booking_id": bk["id"],
                "remaining": remaining,
                "email_sent_to": client_email,
            })
        except Exception as e:
            log.exception("reminder branch failed for invoice %s", inv.get("id"))
            summary["errors"].append({"invoice_id": inv.get("id"), "err": f"{type(e).__name__}: {e}"})

    # ---- Audit: close the run record ----
    if run_id:
        try:
            sb.table("cron_runs").update({
                "finished_at": _now_iso(),
                "summary": summary,
                "error_count": len(summary["errors"]),
                "ok": len(summary["errors"]) == 0,
            }).eq("id", run_id).execute()
        except Exception as e:
            log.warning("cron_runs audit-close failed: %s", e)

    # ---- Heartbeat: one-line "cron ran" email so the daily run self-reports.
    # Closes the loop on "how would we catch a silent failure sooner" — a
    # green note lands every morning; if it stops arriving (or GitHub Actions
    # emails a red run), that's the signal. Skipped on dry runs (test noise).
    summary["heartbeat_sent"] = False
    if not dry_run:
        summary["heartbeat_sent"] = _send_heartbeat(summary)

    return summary


def _send_heartbeat(summary: dict) -> bool:
    """Best-effort daily heartbeat email. Never raises. Returns True if a
    send was attempted (recipient configured), False otherwise."""
    to_email = (
        os.environ.get("CRON_HEARTBEAT_TO")
        or os.environ.get("CONTACT_TO_EMAIL")
        or os.environ.get("ADMIN_EMAIL")
        # Last resort: first entry of ADMIN_EMAILS (the admin-bootstrap list).
        # ADMIN_EMAIL (singular) often isn't set; ADMIN_EMAILS usually is.
        or (os.environ.get("ADMIN_EMAILS", "").split(",")[0])
        or ""
    ).strip()
    if not to_email:
        log.info("heartbeat: no recipient configured (set CRON_HEARTBEAT_TO) — skipping")
        return False

    errs = len(summary.get("errors", []))
    created = len(summary.get("invoices_created", []))
    reminders = len(summary.get("reminders_sent", []))
    manual = len(summary.get("reminders_skipped_paid_manually", []))
    ok = errs == 0
    icon = "✅" if ok else "⚠️"
    verdict = "ran green" if ok else f"ran with {errs} error(s)"
    date_str = summary.get("date", "")

    one_line = (
        f"{icon} Daily invoicing {verdict} — "
        f"{created} invoice(s) created, {reminders} reminder(s) sent"
        f"{f', {manual} settled outside checkout' if manual else ''}."
    )
    subject = f"{icon} Flyboy daily invoicing — {verdict} ({date_str})"
    text_body = (
        f"{one_line}\n\n"
        f"Date: {date_str}\n"
        f"Invoices created: {created}\n"
        f"Reminders sent: {reminders}\n"
        f"Settled outside checkout: {manual}\n"
        f"Errors: {errs}\n"
    )
    if errs:
        import json as _json
        text_body += "\nError detail:\n" + _json.dumps(summary.get("errors", []), indent=2)[:2000]
    html_body = (
        f'<p style="font-size:15px;margin:0 0 12px">{one_line}</p>'
        f'<table style="font:13px/1.6 monospace;color:#444">'
        f'<tr><td>Date</td><td style="padding-left:16px">{date_str}</td></tr>'
        f'<tr><td>Invoices created</td><td style="padding-left:16px">{created}</td></tr>'
        f'<tr><td>Reminders sent</td><td style="padding-left:16px">{reminders}</td></tr>'
        f'<tr><td>Settled outside checkout</td><td style="padding-left:16px">{manual}</td></tr>'
        f'<tr><td>Errors</td><td style="padding-left:16px;color:{"#c00" if errs else "#080"}">{errs}</td></tr>'
        f'</table>'
    )
    try:
        _send_email(to_email, subject, html_body, text_body)
        return True
    except Exception as e:
        log.warning("heartbeat send failed: %s", e)
        return False


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
