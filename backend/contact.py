"""Public contact / enquiry form — POST /api/contact/enquire.

Design mirrors the booking flow but with an INDEPENDENT rate-limit ledger
(`contact_attempts` — migration 009). Rationale (user directive 2026-02):
booking spam ties up real calendar dates and Stripe sessions, contact-form
spam just fills an inbox — different threat models deserve independent
tuning knobs and retention.

On success:
  1. Row inserted into public.contact_enquiries (durable record).
  2. Attempt row inserted into public.contact_attempts (rate ledger).
  3. Resend email sent to CONTACT_TO_EMAIL with the enquiry contents.

Rate limits (same layered pattern as booking, values chosen for enquiry
threat model — more permissive because the blast radius is smaller):
  - per-email  5 / 15 min
  - per-IP     8 / 15 min
  - global     200 / 15 min
"""
from __future__ import annotations

import hashlib
import html
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

log = logging.getLogger(__name__)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "Flyboy Videography <bookings@flyboyvideography.com>")
CONTACT_TO_EMAIL = os.environ.get("CONTACT_TO_EMAIL", os.environ.get("ADMIN_EMAIL", "hello@flyboyvideography.com"))

RL_WINDOW_MINUTES = 15
RL_MAX_PER_EMAIL = 5
RL_MAX_PER_IP = 8
RL_MAX_GLOBAL = 200
RL_PURGE_HOURS = 24

router = APIRouter()


class EnquireIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    email: EmailStr
    package_id: Optional[str] = Field(default=None, max_length=64)
    event_date: Optional[date] = None
    message: str = Field(..., min_length=1, max_length=4000)
    source_url: Optional[str] = Field(default=None, max_length=500)


class EnquireOut(BaseModel):
    id: str
    status: str = "received"


def _sb():
    from server import get_sb
    return get_sb()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _client_ip(request: Request) -> str:
    """Same best-effort XFF-leftmost extraction as booking.py — see
    PL-INFRA-1 in CREDENTIAL_ROTATION.md for the trust boundary caveat."""
    xff = request.headers.get("x-forwarded-for") or ""
    if xff:
        return xff.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    return request.client.host if request.client else "unknown"


def _hash_email(email: str) -> str:
    return hashlib.sha256((email or "").strip().lower().encode()).hexdigest()[:16]


def _log_and_persist_429(sb, request: Request, reason: str, email: str) -> None:
    """Same forensic write-through pattern as booking.py — hashed email
    in stderr line + rate_limit_events row. Fail-open on persistence."""
    xff = request.headers.get("x-forwarded-for")
    x_real_ip = request.headers.get("x-real-ip")
    ip = _client_ip(request)
    ehash = _hash_email(email)
    ua = (request.headers.get("user-agent") or "")[:500]

    log.warning(
        "CONTACT_429 reason=%s email_hash=%s ip=%s xff=%r x-real-ip=%r ua=%r",
        reason, ehash, ip, xff, x_real_ip, ua[:200],
    )
    try:
        sb.table("rate_limit_events").insert({
            "reason": f"contact_{reason}",
            "email_hash": ehash,
            "ip": ip,
            "x_forwarded_for": xff,
            "x_real_ip": x_real_ip,
            "user_agent": ua,
        }).execute()
    except Exception as e:
        log.info("rate_limit_events persist skipped: %s", e)


def _rate_limit_or_429(sb, request: Request, email: str) -> None:
    """Atomic insert-then-count (same fix as booking.py::_rate_limit_or_429
    after SEC-001-residual). Insert our attempt row first so N concurrent
    racers each see a monotonically increasing count."""
    ip = _client_ip(request)
    now = datetime.now(timezone.utc)
    window_start = (now - timedelta(minutes=RL_WINDOW_MINUTES)).isoformat()
    purge_before = (now - timedelta(hours=RL_PURGE_HOURS)).isoformat()

    # Retention purge (lazy).
    try:
        sb.table("contact_attempts").delete().lt("created_at", purge_before).execute()
    except Exception as e:
        log.warning("contact_attempts purge failed: %s", e)

    # Insert first — atomic gate.
    try:
        sb.table("contact_attempts").insert({"ip": ip, "email": email.lower()}).execute()
    except Exception as e:
        log.warning("contact_attempts insert failed: %s", e)

    # Compare with `>` because our own row is now included in the count.
    r = sb.table("contact_attempts").select("id", count="exact").ilike("email", email).gte(
        "created_at", window_start
    ).execute()
    if (r.count or 0) > RL_MAX_PER_EMAIL:
        _log_and_persist_429(sb, request, "per_email", email)
        raise HTTPException(429, "Too many enquiries from this email. Please try again in a few minutes.",
                            headers={"Retry-After": str(RL_WINDOW_MINUTES * 60)})

    r = sb.table("contact_attempts").select("id", count="exact").eq("ip", ip).gte(
        "created_at", window_start
    ).execute()
    if (r.count or 0) > RL_MAX_PER_IP:
        _log_and_persist_429(sb, request, "per_ip", email)
        raise HTTPException(429, "Too many enquiries from your network. Please try again in a few minutes.",
                            headers={"Retry-After": str(RL_WINDOW_MINUTES * 60)})

    r = sb.table("contact_attempts").select("id", count="exact").gte(
        "created_at", window_start
    ).execute()
    if (r.count or 0) > RL_MAX_GLOBAL:
        _log_and_persist_429(sb, request, "global_attempts", email)
        raise HTTPException(429, "We're experiencing unusually high enquiry traffic. Please try again shortly.",
                            headers={"Retry-After": str(RL_WINDOW_MINUTES * 60)})


def _send_notification(enquiry: dict) -> None:
    if not RESEND_API_KEY:
        log.warning("RESEND_API_KEY not set — enquiry stored but no email sent")
        return
    pkg = enquiry.get("package_id") or "—"
    ev = enquiry.get("event_date") or "—"
    src = enquiry.get("source_url") or "—"
    subject = f"New enquiry from {enquiry['name']}"
    body_lines = [
        f"Name:     {enquiry['name']}",
        f"Email:    {enquiry['email']}",
        f"Package:  {pkg}",
        f"Event:    {ev}",
        f"Source:   {src}",
        "",
        "Message:",
        enquiry["message"],
    ]
    text_body = "\n".join(body_lines)
    html_body = (
        f'<div style="font-family:system-ui,sans-serif;font-size:14px;color:#111;">'
        f'<h2 style="margin:0 0 12px 0;">New enquiry from {html.escape(enquiry["name"])}</h2>'
        f'<table style="border-collapse:collapse;">'
        f'<tr><td style="padding:4px 12px 4px 0;color:#555;">Email</td><td>{html.escape(enquiry["email"])}</td></tr>'
        f'<tr><td style="padding:4px 12px 4px 0;color:#555;">Package</td><td>{html.escape(pkg)}</td></tr>'
        f'<tr><td style="padding:4px 12px 4px 0;color:#555;">Event date</td><td>{html.escape(str(ev))}</td></tr>'
        f'<tr><td style="padding:4px 12px 4px 0;color:#555;">Source</td><td>{html.escape(src)}</td></tr>'
        f'</table>'
        f'<h3 style="margin:20px 0 8px 0;">Message</h3>'
        f'<pre style="white-space:pre-wrap;font-family:inherit;font-size:14px;background:#f5f0e6;padding:12px;border-radius:6px;">'
        f'{html.escape(enquiry["message"])}</pre>'
        f'</div>'
    )
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": RESEND_FROM_EMAIL,
                    "to": [CONTACT_TO_EMAIL],
                    "reply_to": enquiry["email"],
                    "subject": subject,
                    "html": html_body,
                    "text": text_body,
                },
            )
        if r.status_code >= 400:
            log.warning("Resend enquiry send failed %s: %s", r.status_code, r.text[:300])
    except Exception as e:
        log.exception("Resend enquiry send crashed: %s", e)


@router.post("/api/contact/enquire", response_model=EnquireOut)
def enquire(body: EnquireIn, request: Request):
    sb = _sb()

    # Rate limit (atomic; own ledger).
    _rate_limit_or_429(sb, request, str(body.email))

    row = sb.table("contact_enquiries").insert({
        "name": body.name.strip(),
        "email": str(body.email).lower(),
        "package_id": body.package_id,
        "event_date": body.event_date.isoformat() if body.event_date else None,
        "message": body.message.strip(),
        "source_url": body.source_url,
        "status": "new",
    }).execute().data[0]

    # Best-effort notify; a Resend outage MUST NOT lose the enquiry.
    _send_notification(row)

    return EnquireOut(id=row["id"], status="received")
