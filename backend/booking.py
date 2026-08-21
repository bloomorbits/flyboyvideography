"""Client-facing booking flow — Phase 1 (one-off bookings).

Endpoints:
  GET  /api/booking/availability
  POST /api/booking/checkout
  GET  /api/booking/status/{session_id}          (unauth, poll-safe)
  POST /api/stripe/webhook                       (Stripe → server, signature-verified)

Flow:
  1. Client picks package + tier + date + contact info on the Next.js site.
  2. POST /api/booking/checkout
       - Validates against public.bookings (unique confirmed per date) AND
         public.date_slot_locks (soft hold, cleaned lazily by lock TTL).
       - Inserts booking_intents row (pending).
       - Creates Stripe Checkout Session for the DEPOSIT amount (50%).
       - Inserts payment_transactions row (initiated/pending).
       - Inserts date_slot_locks row (5 min TTL).
       - Returns { checkout_url }.
  3. User pays. Stripe redirects to /book/success?session_id=... which polls
     GET /api/booking/status/{session_id}.
  4. Webhook fires (also, /status/{session_id} does an inline fallback probe
     to Stripe so a slow/failed webhook doesn't strand the success page):
       - Verifies signature (STRIPE_WEBHOOK_SECRET).
       - Idempotency guard: skip if payment_transactions.payment_status == 'paid'.
       - Updates payment_transactions -> paid.
       - Creates a Supabase auth user (idempotent) + clients row (idempotent).
       - Inserts bookings row (status='confirmed').
       - On unique_violation on bookings(event_date) WHERE status='confirmed':
           AUTO-REFUND via Stripe, mark payment_transactions status='refunded_race'.
       - Otherwise: generate a Supabase invite link and send the confirmation
         email via Resend.
"""
from __future__ import annotations

import hashlib
import html
import logging
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import httpx
import stripe
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from packages import DEPOSIT_PERCENTAGE, deposit_gbp, find_tier

log = logging.getLogger(__name__)

# ---------- Config ----------

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "Flyboy Videography <bookings@flyboyvideography.com>")
PUBLIC_SITE_URL = os.environ.get("PUBLIC_SITE_URL", "https://flyboyvideography.com")
PORTAL_URL = os.environ.get("PORTAL_URL", os.environ.get("REACT_APP_BACKEND_URL", ""))

LOCK_TTL_MINUTES = 5

# Availability window: how far ahead we let visitors book.
AVAILABILITY_MONTHS_AHEAD = 18

# ---------- SEC-001 rate-limit config (see supabase_migration_007_rate_limit.sql) ----------
# Layered defense — no single spoofable signal is the whole guard. The EMAIL
# limits are the hardest to bypass cheaply (attacker needs many real inboxes
# to receive the Stripe redirect). The IP limits are best-effort (defeatable
# via X-Forwarded-For prepending on the current Emergent edge — see
# CREDENTIAL_ROTATION.md → "Pre-launch infra tasks" for the ops-side fix).
# The GLOBAL caps are the anti-calendar-freeze backstop that works even if
# an attacker fully bypasses the per-IP checks.

RL_WINDOW_MINUTES = 15
RL_MAX_PER_EMAIL = 3          # per 15-min window
RL_MAX_PER_IP = 5             # per 15-min window
RL_MAX_GLOBAL = 100           # per 15-min window, system-wide

LOCK_CAP_PER_EMAIL = 2        # concurrent active locks
LOCK_CAP_PER_IP = 3           # concurrent active locks
LOCK_CAP_GLOBAL = 50          # concurrent active locks, system-wide

# Retention: purge attempt rows older than this on every checkout call
# (cheap; keeps the table from unbounded growth without needing a cron).
RL_PURGE_HOURS = 24

# origin_url allowlist for Stripe success/cancel URLs (SEC — open redirect).
# Comma-separated env var. If unset, defaults to the safe production +
# preview + localhost list.
_default_origin_allowlist = ",".join([
    "https://flyboyvideography.com",
    "https://www.flyboyvideography.com",
    "https://flyboyvideography.vercel.app",
    "https://db-bridge-5.preview.emergentagent.com",
    "http://localhost:3001",
])
ALLOWED_ORIGIN_URLS = {
    o.strip().rstrip("/")
    for o in os.environ.get("ALLOWED_ORIGIN_URLS", _default_origin_allowlist).split(",")
    if o.strip()
}

EMAIL_TEMPLATE_DIR = Path(__file__).parent / "emails"

router = APIRouter()


# ---------- Request/Response models ----------


class CheckoutIn(BaseModel):
    package_id: str = Field(..., min_length=1)
    tier_name: str = ""  # "" for single-tier packages (e.g. graduation)
    event_date: date
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=200)
    phone: Optional[str] = Field(default=None, max_length=40)
    event_notes: Optional[str] = Field(default=None, max_length=2000)
    origin_url: str = Field(..., min_length=1)  # e.g. "https://flyboyvideography.com"
    # ---- Consent capture (Migration 010, session 11) ----
    # T&Cs are the hard legal gate — MUST be true. Enforced below in the
    # checkout handler, not just as `= True` here, because Pydantic-side
    # defaults are silently accepted while a server-side raise gives a
    # clear 400 message the frontend can render.
    tc_accepted: bool = False
    model_release_opted_in: bool = True  # opt-out model, pre-checked in UI
    minors_involved: bool = False
    # Conditional: only required when minors_involved=true. Both nullable at
    # Pydantic level so an over-eager frontend can't accidentally send empty
    # strings that pass server validation; the handler enforces truthy when
    # minors_involved is set.
    safeguarding_guardian_name: Optional[str] = Field(default=None, max_length=200)
    safeguarding_consent_accepted: bool = False


class CheckoutOut(BaseModel):
    checkout_url: str
    session_id: str


class StatusOut(BaseModel):
    session_id: str
    status: str
    payment_status: str


# ---------- Helpers ----------


def _sb():
    """Get the Supabase service-role client. Imported lazily so server.py
    boot-hardening (503 vs crash-loop) still applies."""
    from server import get_sb  # local import avoids circular deps at import time
    return get_sb()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- SEC-001 rate limiter ----------

def _client_ip(request: Request) -> str:
    """Client IP extraction, hardened for the Railway edge.

    Empirical result of PL-INFRA-1 verification (2026-02, see
    CREDENTIAL_ROTATION.md § 'Pre-launch infra tasks'): Railway's ingress
    strips ALL client-supplied `X-Real-IP` and `X-Forwarded-For` headers
    and sets them from its own view of the TCP peer. Verified with
    spoofed inputs `X-Real-IP: 5.6.7.8` and `X-Forwarded-For: 1.2.3.4`
    both being completely dropped and replaced with the actual public
    IP of the caller.

    Preference order:
      1. X-Real-IP — single-value, Railway-set on every request, cannot
         be spoofed because Railway overwrites it at the edge.
      2. Leftmost X-Forwarded-For — same-source guarantee on Railway;
         still preferred over #3 because it matches proxy convention.
      3. request.client.host — CGNAT-space Railway internal address
         (100.64.0.0/10); the TCP peer from FastAPI's perspective. Safe
         fallback if both headers somehow disappear.

    DO NOT REVERT this to trust XFF-leftmost blindly if the deployment
    ever moves off Railway. The XFF trust boundary is deployment-specific
    and must be re-verified with an /api/_probe/ip endpoint against the
    new target BEFORE any code here assumes headers are trustworthy.
    """
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip:
        return real_ip
    xff = request.headers.get("x-forwarded-for") or ""
    if xff:
        return xff.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    return request.client.host if request.client else "unknown"


def _hash_email(email: str) -> str:
    """Truncated SHA-256 of lower(email). Used everywhere email would
    otherwise appear in a durable log (stderr forensics + rate_limit_events
    table). NOT reversible — investigations start from a suspect email,
    hash it, then query. See migration 008 comments for the PII rationale.
    """
    return hashlib.sha256((email or "").strip().lower().encode()).hexdigest()[:16]


# rate_limit_events retention (see migration 008). Purge fires lazily on
# each _log_bypass_forensics call — cheap, no cron required.
RL_EVENTS_RETENTION_DAYS = 30


def _log_bypass_forensics(sb, request: Request, reason: str, email: str) -> None:
    """Log everything we'd need to retro-analyse a rate-limit bypass
    attempt. Deliberately noisy — cheap now, would be the first thing
    worth having if real forensic analysis is ever needed later.

    PII posture (see migration 008): the email is HASHED in both the
    stderr log line and the persisted `rate_limit_events` row. IP and
    raw header snapshots remain plaintext as operational security data
    (GDPR recital 49). Rows in `rate_limit_events` are auto-purged after
    RL_EVENTS_RETENTION_DAYS.
    """
    xff = request.headers.get("x-forwarded-for")
    x_real_ip = request.headers.get("x-real-ip")
    client_host = request.client.host if request.client else None
    ua = (request.headers.get("user-agent") or "")[:500]
    ip = _client_ip(request)
    ehash = _hash_email(email)

    log.warning(
        "RL_429 reason=%s email_hash=%s ip=%s xff=%r x-real-ip=%r client_host=%r ua=%r",
        reason, ehash, ip, xff, x_real_ip, client_host, ua[:200],
    )

    # Best-effort persist to rate_limit_events. Fail-open — a persistence
    # error must never block the 429 response the caller is about to raise.
    try:
        sb.table("rate_limit_events").insert({
            "reason": reason,
            "email_hash": ehash,
            "ip": ip,
            "x_forwarded_for": xff,
            "x_real_ip": x_real_ip,
            "user_agent": ua,
        }).execute()
        # Lazy retention purge (skipped on failure — the next 429 will retry).
        cutoff = (datetime.now(timezone.utc) - timedelta(days=RL_EVENTS_RETENTION_DAYS)).isoformat()
        sb.table("rate_limit_events").delete().lt("created_at", cutoff).execute()
    except Exception as e:
        # Common transient reasons: migration 008 not applied yet, network
        # blip. Never propagate — the 429 must still fly.
        log.info("rate_limit_events persist skipped: %s", e)


def _record_checkout_attempt(sb, request: Request, email: str) -> None:
    """Insert the attempt row FIRST — this is the atomic gate for the rate
    limiter. Any race window between reading and writing is closed because
    the write happens BEFORE the count query in `_rate_limit_or_429`.
    """
    try:
        sb.table("checkout_attempts").insert({
            "ip": _client_ip(request),
            "email": email.lower(),
        }).execute()
    except Exception as e:
        # Never let a rate-limit ledger write block a real booking. If the
        # limiter can't record, the next request from the same source
        # simply doesn't see the earlier attempt — fail-open on the LEDGER
        # while the actual limits still fire based on whatever rows did
        # persist. This is a conscious asymmetry.
        log.warning("checkout_attempts insert failed: %s", e)


def _rate_limit_or_429(sb, request: Request, email: str) -> None:
    """Enforce the layered rate limits BEFORE any Stripe/DB writes.

    ATOMIC PATTERN (SEC-001-residual fix, 2026-02):
      1. Insert this attempt into checkout_attempts FIRST.
      2. Count rows in the sliding window — the count now includes our
         own row, so N concurrent racers will each see a monotonically
         increasing count as their inserts commit under READ COMMITTED.
      3. Compare with `>` not `>=` — the Nth attempt sees count=N, which
         is fine iff N <= cap.

    A previous (2026-02 first cut) implementation read counts BEFORE
    inserting, which let N simultaneous requests all see count<cap and
    proceed. The audit flagged this as SEC-001-residual [MEDIUM].
    """
    ip = _client_ip(request)
    now = datetime.now(timezone.utc)
    window_start = (now - timedelta(minutes=RL_WINDOW_MINUTES)).isoformat()
    purge_before = (now - timedelta(hours=RL_PURGE_HOURS)).isoformat()

    # Lazy retention purge (fire-and-forget style — failures here must never
    # block a legitimate booking).
    try:
        sb.table("checkout_attempts").delete().lt("created_at", purge_before).execute()
    except Exception as e:
        log.warning("checkout_attempts purge failed: %s", e)

    # Step 1 — insert FIRST so the count query below is atomic under
    # concurrency (READ COMMITTED means later reads see all committed rows).
    _record_checkout_attempt(sb, request, email)

    # Step 2 — count. All comparisons use `>` because the count includes
    # our own just-inserted row.

    # 2a. per-email
    r = sb.table("checkout_attempts").select("id", count="exact").ilike("email", email).gte(
        "created_at", window_start
    ).execute()
    if (r.count or 0) > RL_MAX_PER_EMAIL:
        _log_bypass_forensics(sb, request, "per_email", email)
        raise HTTPException(
            status_code=429,
            detail=f"Too many booking attempts for this email. Try again in {RL_WINDOW_MINUTES} minutes.",
            headers={"Retry-After": str(RL_WINDOW_MINUTES * 60)},
        )

    # 2b. per-IP (best-effort — see PL-INFRA-1 in CREDENTIAL_ROTATION.md)
    r = sb.table("checkout_attempts").select("id", count="exact").eq("ip", ip).gte(
        "created_at", window_start
    ).execute()
    if (r.count or 0) > RL_MAX_PER_IP:
        _log_bypass_forensics(sb, request, "per_ip", email)
        raise HTTPException(
            status_code=429,
            detail=f"Too many booking attempts from your network. Try again in {RL_WINDOW_MINUTES} minutes.",
            headers={"Retry-After": str(RL_WINDOW_MINUTES * 60)},
        )

    # 2c. global circuit breaker — see SEC-002-residual in the audit; this
    # is fully contingent on PL-INFRA-1 (XFF strip) to bound its damage.
    r = sb.table("checkout_attempts").select("id", count="exact").gte(
        "created_at", window_start
    ).execute()
    if (r.count or 0) > RL_MAX_GLOBAL:
        _log_bypass_forensics(sb, request, "global_attempts", email)
        raise HTTPException(
            status_code=429,
            detail="We're experiencing unusually high booking traffic. Please try again in a few minutes.",
            headers={"Retry-After": str(RL_WINDOW_MINUTES * 60)},
        )


def _concurrent_lock_or_429(sb, request: Request, email: str) -> None:
    """Enforce concurrent-active-lock caps. Complements the request-rate
    limiter above: someone pacing under the rate cap can still be blocked
    from tying up too many dates at once.

    NOTE (documented residual): the concurrent-lock check is check-then-
    write (locks are inserted later in create_checkout after Stripe
    returns, and we can't insert before Stripe because we need the
    session_id). Under concurrency this cap can be exceeded by ~1 per
    racing request. The rate limiter above (now atomic) bounds this
    residual race to at most `RL_MAX_PER_IP` simultaneous racers, which
    is well under the global lock cap.
    """
    ip = _client_ip(request)
    now_iso = _now_iso()

    # per-email
    r = sb.table("date_slot_locks").select("id", count="exact").ilike("email", email).gt(
        "expires_at", now_iso
    ).execute()
    if (r.count or 0) >= LOCK_CAP_PER_EMAIL:
        _log_bypass_forensics(sb, request, "locks_per_email", email)
        raise HTTPException(
            status_code=429,
            detail=f"You already have {LOCK_CAP_PER_EMAIL} pending booking(s). Finish or cancel one before starting another.",
            headers={"Retry-After": str(LOCK_TTL_MINUTES * 60)},
        )

    # per-IP (best-effort — same caveat as the rate check)
    r = sb.table("date_slot_locks").select("id", count="exact").eq("ip", ip).gt(
        "expires_at", now_iso
    ).execute()
    if (r.count or 0) >= LOCK_CAP_PER_IP:
        _log_bypass_forensics(sb, request, "locks_per_ip", email)
        raise HTTPException(
            status_code=429,
            detail="Too many pending bookings from your network. Please finish or cancel one before starting another.",
            headers={"Retry-After": str(LOCK_TTL_MINUTES * 60)},
        )

    # global circuit breaker
    r = sb.table("date_slot_locks").select("id", count="exact").gt("expires_at", now_iso).execute()
    if (r.count or 0) >= LOCK_CAP_GLOBAL:
        _log_bypass_forensics(sb, request, "locks_global", email)
        raise HTTPException(
            status_code=429,
            detail="We're experiencing unusually high booking traffic. Please try again in a few minutes.",
            headers={"Retry-After": str(LOCK_TTL_MINUTES * 60)},
        )


# ---------- Availability helpers ----------


def _clean_expired_locks(sb, event_date: str) -> None:
    """Delete any lock rows for this date whose TTL has passed. Cheap; keeps
    the lock table honest without needing a cron."""
    try:
        sb.table("date_slot_locks").delete().eq("event_date", event_date).lt(
            "expires_at", _now_iso()
        ).execute()
    except Exception as e:
        log.warning("lock cleanup failed for %s: %s", event_date, e)


def _confirmed_booking_exists(sb, event_date: str) -> bool:
    r = sb.table("bookings").select("id").eq("event_date", event_date).eq(
        "status", "confirmed"
    ).limit(1).execute()
    return bool(r.data)


def _active_lock_exists(sb, event_date: str) -> bool:
    r = sb.table("date_slot_locks").select("id").eq("event_date", event_date).gt(
        "expires_at", _now_iso()
    ).limit(1).execute()
    return bool(r.data)


def _ensure_auth_user(sb, email: str, full_name: str) -> str:
    """Idempotent: return the Supabase auth user_id for this email, creating
    a fresh confirmed user if one doesn't already exist. Password is never
    set by the server — the client sets it via the invite link.
    """
    # supabase-py doesn't expose list_users by email natively via the SDK's
    # admin.list_users(), so we go through the GoTrue REST endpoint directly.
    url = os.environ["SUPABASE_URL"].rstrip("/") + f"/auth/v1/admin/users?email={email}"
    headers = {
        "apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        "Authorization": f"Bearer {os.environ['SUPABASE_SERVICE_ROLE_KEY']}",
    }
    with httpx.Client(timeout=10.0) as client:
        r = client.get(url, headers=headers)
    r.raise_for_status()
    users = (r.json().get("users") or []) if isinstance(r.json(), dict) else []
    for u in users:
        if (u.get("email") or "").lower() == email.lower():
            return u["id"]

    # SEC-002 — do NOT pre-confirm the email. The user only becomes verified
    # when they click the Supabase-issued recovery link we email post-payment;
    # that click completes both email verification AND password setup in one
    # step. Leaving `email_confirm=False` here means an unsolicited email
    # captured mid-booking cannot be silently pre-verified in our auth store.
    created = sb.auth.admin.create_user({
        "email": email,
        "email_confirm": False,
        "user_metadata": {"full_name": full_name},
    })
    return created.user.id


def _ensure_client_row(sb, user_id: str, email: str, full_name: str, phone: Optional[str]) -> str:
    """Upsert-style: return clients.id for this user_id, inserting on miss."""
    r = sb.table("clients").select("*").eq("user_id", user_id).limit(1).execute()
    if r.data:
        c = r.data[0]
        updates: dict[str, Any] = {}
        if not c.get("full_name") and full_name:
            updates["full_name"] = full_name
        if phone and not c.get("phone"):
            updates["phone"] = phone
        if updates:
            sb.table("clients").update(updates).eq("id", c["id"]).execute()
        return c["id"]
    inserted = sb.table("clients").insert({
        "user_id": user_id,
        "email": email,
        "full_name": full_name,
        "phone": phone,
        "role": "client",
    }).execute()
    return inserted.data[0]["id"]


def _generate_invite_link(email: str) -> str:
    """Generate a Supabase-issued single-use recovery link so the client can
    set their portal password. We use `type=recovery` rather than `invite`
    because `invite` requires the user to not exist yet — but we've just
    created (or found) them above."""
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/auth/v1/admin/generate_link"
    portal_url = os.environ.get("PORTAL_URL") or os.environ.get("REACT_APP_BACKEND_URL", "")
    redirect_to = f"{portal_url.rstrip('/')}/auth?welcome=1"
    payload = {
        "type": "recovery",
        "email": email,
        "options": {"redirect_to": redirect_to} if portal_url else {},
    }
    headers = {
        "apikey": os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        "Authorization": f"Bearer {os.environ['SUPABASE_SERVICE_ROLE_KEY']}",
        "Content-Type": "application/json",
    }
    with httpx.Client(timeout=10.0) as client:
        r = client.post(url, headers=headers, json=payload)
    if r.status_code >= 400:
        log.warning("generate_link failed %s: %s", r.status_code, r.text[:200])
        return f"{portal_url.rstrip('/')}/auth" if portal_url else ""
    data = r.json()
    return data.get("properties", {}).get("action_link") or data.get("action_link", "")


def _format_event_date(d: date) -> str:
    # e.g. "Saturday, 12 July 2026"
    return d.strftime("%A, %-d %B %Y") if hasattr(d, "strftime") else str(d)


def _compose_details_html(phone: Optional[str], notes: Optional[str]) -> str:
    parts = []
    if phone:
        parts.append(f'<p style="margin:0 0 4px 0;font-size:14px;">Phone: <strong>{html.escape(phone)}</strong></p>')
    if notes:
        parts.append(
            f'<p style="margin:8px 0 0 0;font-size:14px;white-space:pre-wrap;">Your notes:<br />{html.escape(notes)}</p>'
        )
    if not parts:
        return ""
    header = (
        '<p style="margin:0 0 6px 0;font-family:\'JetBrains Mono\',monospace;'
        'font-size:10px;letter-spacing:0.25em;text-transform:uppercase;color:#6b6558;">What you told us</p>'
    )
    inner = "".join(parts)
    return (
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" '
        f'style="margin:0 0 24px 0;background:#ffffff;border:1px solid #e9e1d2;border-radius:8px;">'
        f'<tr><td style="padding:16px 20px;">{header}{inner}</td></tr></table>'
    )


def _compose_details_text(phone: Optional[str], notes: Optional[str]) -> str:
    parts = []
    if phone:
        parts.append(f"  Phone: {phone}")
    if notes:
        parts.append(f"  Notes: {notes}")
    if not parts:
        return ""
    return "WHAT YOU TOLD US\n" + "\n".join(parts) + "\n\n"


def _load_template(name: str) -> str:
    return (EMAIL_TEMPLATE_DIR / name).read_text(encoding="utf-8")


def _render_email(intent: dict, invite_url: str) -> tuple[str, str]:
    """Return (html_body, text_body). Substitutes all {{placeholders}}."""
    html_tpl = _load_template("booking_confirmation.html")
    text_tpl = _load_template("booking_confirmation.txt")

    first_name = (intent.get("full_name") or "").split(" ")[0] or "there"
    tier = intent.get("tier_name") or ""
    tier_suffix = f" — {tier}" if tier else ""
    deposit = intent["price_deposit"]
    balance = float(intent["price_total"]) - float(deposit)
    ev = intent["event_date"]
    if isinstance(ev, str):
        ev = date.fromisoformat(ev)
    balance_due_by = (ev - timedelta(days=3)).strftime("%-d %B %Y")

    ctx = {
        "{{first_name}}": html.escape(first_name),
        "{{package_title}}": html.escape(intent["package_title"]),
        "{{tier_suffix}}": html.escape(tier_suffix),
        "{{event_date}}": _format_event_date(ev),
        "{{deposit_paid}}": f"£{float(deposit):.2f}",
        "{{balance_due}}": f"£{balance:.2f}",
        "{{balance_due_by}}": balance_due_by,
        "{{invite_url}}": invite_url or "",
        "{{your_details_block}}": _compose_details_html(intent.get("phone"), intent.get("event_notes")),
    }
    text_ctx = {
        **ctx,
        "{{your_details_block_text}}": _compose_details_text(intent.get("phone"), intent.get("event_notes")),
    }

    html_body = html_tpl
    for k, v in ctx.items():
        html_body = html_body.replace(k, v)

    # Strip the pseudo-code composer footer that lives at the bottom of the .txt
    # template as author notes (`--\n{{your_details_block_text}} composer …`).
    text_body = text_tpl.split("\n--\n{{your_details_block_text}} composer", 1)[0]
    for k, v in text_ctx.items():
        text_body = text_body.replace(k, v)
    return html_body, text_body


def _send_confirmation_email(to_email: str, subject: str, html_body: str, text_body: str) -> None:
    if not RESEND_API_KEY:
        log.warning("RESEND_API_KEY not set — skipping confirmation email to %s", to_email)
        return
    with httpx.Client(timeout=10.0) as client:
        r = client.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": RESEND_FROM_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
                "text": text_body,
            },
        )
    if r.status_code >= 400:
        log.warning("Resend send failed %s: %s", r.status_code, r.text[:400])


# ---------- Endpoints ----------


@router.get("/api/booking/availability")
def availability(months_ahead: int = AVAILABILITY_MONTHS_AHEAD):
    """Return the list of blocked calendar dates in the next N months.
    A date is blocked if:
      - a confirmed booking exists for it, OR
      - an active (non-expired) date_slot_lock exists for it.
    The frontend uses this to grey out unavailable days in the picker.
    """
    sb = _sb()
    today = date.today()
    horizon = today + timedelta(days=months_ahead * 31)

    confirmed = sb.table("bookings").select("event_date").eq("status", "confirmed").gte(
        "event_date", today.isoformat()
    ).lte("event_date", horizon.isoformat()).execute().data or []

    now_iso = _now_iso()
    locks = sb.table("date_slot_locks").select("event_date").gt("expires_at", now_iso).gte(
        "event_date", today.isoformat()
    ).lte("event_date", horizon.isoformat()).execute().data or []

    blocked = sorted({b["event_date"] for b in confirmed if b.get("event_date")} |
                     {l["event_date"] for l in locks if l.get("event_date")})

    return {
        "today": today.isoformat(),
        "horizon": horizon.isoformat(),
        "blocked_dates": blocked,
    }


@router.post("/api/booking/checkout", response_model=CheckoutOut)
def create_checkout(body: CheckoutIn, request: Request):
    sb = _sb()

    # SEC-001 — rate limit + concurrent-lock cap BEFORE any Stripe/DB writes.
    # These raise 429 with a Retry-After header and log the raw forensics.
    _rate_limit_or_429(sb, request, str(body.email))
    _concurrent_lock_or_429(sb, request, str(body.email))

    pkg, tier = find_tier(body.package_id, body.tier_name)
    if pkg is None or tier is None:
        raise HTTPException(422, f"Unknown package/tier: {body.package_id}/{body.tier_name}")

    if body.event_date <= date.today():
        raise HTTPException(422, "Pick a future date.")

    # SEC — open redirect: validate origin_url is on the allowlist BEFORE
    # embedding it into the Stripe Checkout Session's success/cancel URLs.
    origin = body.origin_url.rstrip("/")
    if origin not in ALLOWED_ORIGIN_URLS:
        log.warning("open-redirect attempt: origin_url=%r not in allowlist", body.origin_url)
        raise HTTPException(422, "Unsupported origin_url.")

    # ---- Consent enforcement (Migration 010, session 11) ----
    # Server-side gate. Frontend also disables the pay button on the same
    # conditions, but the frontend is UX — this is the actual legal boundary.
    # A booking cannot exist without a T&Cs acceptance timestamp.
    if not body.tc_accepted:
        raise HTTPException(400, "You must accept the Terms & Conditions to book.")
    guardian_name = (body.safeguarding_guardian_name or "").strip()
    if body.minors_involved:
        if not guardian_name:
            raise HTTPException(
                400,
                "A guardian's full name is required when anyone under 18 will appear in the session.",
            )
        if not body.safeguarding_consent_accepted:
            raise HTTPException(
                400,
                "Guardian safeguarding consent must be accepted when anyone under 18 will appear in the session.",
            )
    # Timestamps + IP captured at the moment the checkbox was submitted.
    # Persisted TWICE by design (Migration 010 + 010B):
    #   1. Primary: booking_intents (this row) — written NOW, no external
    #      dependency, no eventual consistency. This is the audit-trail
    #      source of truth and is copied to bookings at webhook time.
    #   2. Defense-in-depth: Stripe session metadata (server-set, echoed
    #      through webhook, tamper-proof from client, visible in Stripe
    #      Dashboard as an auditor cross-reference).
    # If the intent write succeeds and Stripe fails, the intent is rolled
    # back on line 786; consent for an unpaid booking is not a compliance
    # record so this is correct.
    consent_now = _now_iso()
    consent_ip = _client_ip(request)  # trusted per PL-INFRA-1 empirical proof
    consent_cols_for_intent = {
        "tc_accepted_at": consent_now,
        "tc_accepted_ip": consent_ip,
        "model_release_opted_in": body.model_release_opted_in,
        "minors_involved": body.minors_involved,
        "safeguarding_guardian_name": guardian_name if body.minors_involved else None,
        "safeguarding_consent_accepted_at": consent_now if body.minors_involved else None,
    }
    consent_meta = {
        "consent_tc_at": consent_now,
        "consent_tc_ip": consent_ip,
        "consent_model_release_opted_in": "true" if body.model_release_opted_in else "false",
        "consent_minors_involved": "true" if body.minors_involved else "false",
    }
    if body.minors_involved:
        consent_meta["consent_guardian_name"] = guardian_name[:400]  # Stripe metadata value cap is 500
        consent_meta["consent_safeguarding_at"] = consent_now

    event_iso = body.event_date.isoformat()

    # Cheap availability re-check (races caught by the DB unique index at
    # webhook time — this is the friendly UX-level guard).
    _clean_expired_locks(sb, event_iso)
    if _confirmed_booking_exists(sb, event_iso):
        raise HTTPException(409, "That date is already booked. Please pick another.")
    if _active_lock_exists(sb, event_iso):
        raise HTTPException(409, "Someone else is checking out for that date right now — try again in a few minutes or pick another.")

    price_total = float(tier["price"])
    price_deposit = deposit_gbp(price_total)

    # 1. booking_intent (pending) — session_id filled in after Stripe returns.
    #    Consent columns land HERE at checkout time (Migration 010B) —
    #    primary source of truth for the audit trail, independent of any
    #    later Stripe webhook success.
    intent_row = sb.table("booking_intents").insert({
        "email": str(body.email),
        "full_name": body.full_name,
        "phone": body.phone,
        "package_id": pkg["id"],
        "package_title": pkg["title"],
        "tier_name": body.tier_name or None,
        "price_total": price_total,
        "price_deposit": price_deposit,
        "event_date": event_iso,
        "event_notes": body.event_notes,
        "status": "pending",
        **consent_cols_for_intent,
    }).execute().data[0]

    # 2. Stripe Checkout Session (DIY tax mode; user is not VAT-registered)
    origin = body.origin_url.rstrip("/")
    tier_desc = f" · {body.tier_name}" if body.tier_name else ""
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[{
                "quantity": 1,
                "price_data": {
                    "currency": "gbp",
                    "unit_amount": int(round(price_deposit * 100)),  # pence
                    "product_data": {
                        "name": f"{pkg['title']}{tier_desc}",
                        "description": (
                            f"{int(DEPOSIT_PERCENTAGE * 100)}% deposit · "
                            f"Event on {body.event_date.isoformat()} · "
                            f"Balance £{price_total - price_deposit:.2f} due 3 days before."
                        ),
                    },
                },
            }],
            customer_email=str(body.email),
            success_url=f"{origin}/book/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/book/cancel",
            metadata={
                "booking_intent_id": intent_row["id"],
                "package_id": pkg["id"],
                "tier_name": body.tier_name or "",
                "event_date": event_iso,
                **consent_meta,
            },
            expires_at=int((datetime.now(timezone.utc) + timedelta(minutes=30)).timestamp()),
        )
    except Exception as e:
        # Roll back the intent row on failure so we don't leak orphan rows.
        sb.table("booking_intents").delete().eq("id", intent_row["id"]).execute()
        log.exception("Stripe session create failed")
        raise HTTPException(502, f"Payment provider error: {e}")

    # 3. payment_transactions (initiated)
    sb.table("payment_transactions").insert({
        "session_id": session.id,
        "booking_intent_id": intent_row["id"],
        "email": str(body.email),
        "amount": price_deposit,
        "currency": "gbp",
        "status": "initiated",
        "payment_status": "pending",
    }).execute()

    # 4. stamp session_id back onto intent
    sb.table("booking_intents").update({
        "session_id": session.id,
        "updated_at": _now_iso(),
    }).eq("id", intent_row["id"]).execute()

    # 5. date_slot_locks (soft hold) — now records the client IP so the
    #    concurrent-lock cap can arithmetic against it. Insert AFTER Stripe
    #    session creation so a Stripe failure doesn't leave an orphan lock.
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=LOCK_TTL_MINUTES)).isoformat()
    try:
        sb.table("date_slot_locks").insert({
            "event_date": event_iso,
            "session_id": session.id,
            "email": str(body.email),
            "expires_at": expires_at,
            "ip": _client_ip(request),
        }).execute()
    except Exception as e:
        # Duplicate session_id (extremely unlikely) — non-fatal, hard guard is
        # still the bookings unique index at webhook time.
        log.warning("date_slot_lock insert failed for %s: %s", event_iso, e)

    return CheckoutOut(checkout_url=session.url, session_id=session.id)


@router.get("/api/booking/status/{session_id}", response_model=StatusOut)
def booking_status(session_id: str):
    """Public-safe: returns ONLY {session_id, status, payment_status}. Used by
    /book/success to poll after Stripe redirect. Includes an inline Stripe
    probe so a slow/failed webhook doesn't strand the success page."""
    sb = _sb()
    r = sb.table("payment_transactions").select("*").eq("session_id", session_id).limit(1).execute()
    if not r.data:
        raise HTTPException(404, "Session not found")
    tx = r.data[0]

    if tx.get("payment_status") != "paid":
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            if s.payment_status == "paid" or s.status == "complete":
                # Same idempotent finalisation the webhook runs.
                _finalise_paid_session(session_id, s.payment_intent)
                tx = sb.table("payment_transactions").select("*").eq("session_id", session_id).limit(1).execute().data[0]
        except stripe.error.StripeError as e:  # transient — leave state alone
            log.info("Stripe probe on status endpoint failed: %s", e)
        except Exception as e:
            log.warning("finalise from status endpoint failed: %s", e)

    return StatusOut(
        session_id=tx["session_id"],
        status=tx["status"],
        payment_status=tx["payment_status"],
    )


def _finalise_paid_session(session_id: str, payment_intent_id: Optional[str]) -> dict:
    """Idempotent finalisation: turn a paid Stripe session into a confirmed
    booking. Called from both the webhook and the /status endpoint's
    inline probe. Returns a small diagnostic dict.

    Order matters: the bookings INSERT is the atomic gate (partial unique
    index does the arbitration). We mark payment_transactions='paid' AFTER
    a successful insert so that a crash / transient network error mid-way
    can be safely replayed by the next webhook retry (Stripe retries up
    to 3 days on non-2xx).
    """
    sb = _sb()

    # Step 0 — idempotency: has this session already been finalised?
    existing = sb.table("bookings").select("id").eq("stripe_session_id", session_id).limit(1).execute().data
    if existing:
        # Ensure tx is marked paid (self-heal in case we crashed between
        # insert and the tx update on a prior attempt).
        sb.table("payment_transactions").update({
            "status": "completed",
            "payment_status": "paid",
            "stripe_payment_intent_id": payment_intent_id,
            "updated_at": _now_iso(),
        }).eq("session_id", session_id).eq("payment_status", "pending").execute()
        return {"skipped": "already finalised", "booking_id": existing[0]["id"]}

    tx_rows = sb.table("payment_transactions").select("*").eq("session_id", session_id).limit(1).execute().data
    if not tx_rows:
        return {"skipped": "no payment_transaction"}
    tx = tx_rows[0]
    if tx["payment_status"] in ("paid", "refunded"):
        return {"skipped": f"already {tx['payment_status']}"}

    intent = sb.table("booking_intents").select("*").eq("session_id", session_id).limit(1).execute().data
    if not intent:
        return {"skipped": "no booking_intent"}
    intent = intent[0]

    # Consent capture (Migrations 010 + 010B, session 11): consent lives in
    # TWO places for defense-in-depth. Primary source is the booking_intents
    # row itself (columns written at checkout time — no external dependency).
    # Fallback is the Stripe session metadata (server-set → tamper-proof →
    # echoed through webhook). If BOTH somehow miss, columns land NULL —
    # but the actual enforcement gate ran at checkout, so the booking still
    # exists validly; this is audit-trail writing, not enforcement.
    def _parse_bool(v, default):
        if v is None:
            return default
        return str(v).lower() == "true"

    # Prefer intent columns (Migration 010B).
    consent_cols = {
        "tc_accepted_at": intent.get("tc_accepted_at"),
        "tc_accepted_ip": intent.get("tc_accepted_ip"),
        "model_release_opted_in": intent.get("model_release_opted_in", True),
        "minors_involved": intent.get("minors_involved", False),
        "safeguarding_guardian_name": intent.get("safeguarding_guardian_name"),
        "safeguarding_consent_accepted_at": intent.get("safeguarding_consent_accepted_at"),
    }

    # Defense-in-depth: if intent is somehow missing consent (e.g. an
    # older intent row from before Migration 010B — shouldn't exist in
    # practice given we purged at Step 11, but for future-proofing), try
    # Stripe metadata as a fallback.
    if consent_cols["tc_accepted_at"] is None:
        try:
            s = stripe.checkout.Session.retrieve(session_id)
            meta = dict(s.metadata or {})
            if meta.get("consent_tc_at"):
                log.info("consent fallback: intent row missing tc_accepted_at, using Stripe metadata for session %s", session_id)
                consent_cols["tc_accepted_at"] = meta.get("consent_tc_at")
                consent_cols["tc_accepted_ip"] = meta.get("consent_tc_ip")
                consent_cols["model_release_opted_in"] = _parse_bool(meta.get("consent_model_release_opted_in"), True)
                consent_cols["minors_involved"] = _parse_bool(meta.get("consent_minors_involved"), False)
                consent_cols["safeguarding_guardian_name"] = meta.get("consent_guardian_name")
                consent_cols["safeguarding_consent_accepted_at"] = meta.get("consent_safeguarding_at")
        except Exception as e:
            log.warning("consent Stripe-fallback fetch failed for session %s (booking will proceed, consent columns may be null): %s", session_id, e)

    # Provision auth user + client row (idempotent). Done BEFORE the atomic
    # insert so that on a crash between insert and email we still have a
    # coherent auth account for the client.
    try:
        user_id = _ensure_auth_user(sb, intent["email"], intent.get("full_name") or "")
        client_id = _ensure_client_row(sb, user_id, intent["email"], intent.get("full_name") or "", intent.get("phone"))
    except Exception:
        log.exception("auth provisioning failed for session %s — will be retried on next webhook delivery", session_id)
        raise

    # Atomic gate — partial unique index arbitrates the race.
    booking_row: Optional[dict] = None
    try:
        booking_row = sb.table("bookings").insert({
            "client_id": client_id,
            "title": intent["package_title"] + (f" — {intent['tier_name']}" if intent.get("tier_name") else ""),
            "shoot_type": intent["package_title"],
            "status": "confirmed",
            "event_date": intent["event_date"],
            "shoot_date": intent["event_date"],  # legacy column
            "deposit_paid_at": _now_iso(),
            "stripe_session_id": session_id,
            "booking_intent_id": intent["id"],
            "budget": float(intent["price_total"]),
            "notes": intent.get("event_notes"),
            "is_seed_data": False,
            **consent_cols,
        }).execute().data[0]
    except Exception as e:
        msg = str(e).lower()
        log.warning("bookings insert exception on session %s: %s: %s", session_id, type(e).__name__, str(e)[:400])
        is_race = (
            "bookings_one_confirmed_per_date" in msg
            or "unique constraint" in msg
            or "23505" in msg
            or "duplicate key" in msg
        )
        if is_race:
            # SEC-001 (2026-02 audit): before assuming a cross-customer race
            # and refunding, verify the winning booking on this date isn't
            # OURS. The webhook and the /api/booking/status probe both call
            # _finalise_paid_session for the same session; the Step-0
            # check-then-insert idempotency guard is non-atomic, so under
            # concurrent replay BOTH calls can pass Step 0 and BOTH can
            # reach this insert — the loser sees a unique_violation whose
            # "winner" is actually our own prior insert from THIS session.
            # Refunding here would refund the legitimate paying customer.
            winner = sb.table("bookings").select("id, stripe_session_id").eq(
                "event_date", intent["event_date"]
            ).eq("status", "confirmed").limit(1).execute().data
            if winner and winner[0]["stripe_session_id"] == session_id:
                log.info(
                    "same-session concurrent replay for session %s — treating as idempotent success (no refund)",
                    session_id,
                )
                # Self-heal: ensure tx + intent reflect paid state (winning
                # path may already have done this, but a partial-crash
                # window on the winner's side leaves tx=pending — heal it).
                sb.table("payment_transactions").update({
                    "status": "completed",
                    "payment_status": "paid",
                    "stripe_payment_intent_id": payment_intent_id or tx.get("stripe_payment_intent_id"),
                    "updated_at": _now_iso(),
                }).eq("session_id", session_id).eq("payment_status", "pending").execute()
                sb.table("booking_intents").update({
                    "status": "paid",
                    "updated_at": _now_iso(),
                }).eq("id", intent["id"]).eq("status", "pending").execute()
                sb.table("date_slot_locks").delete().eq("session_id", session_id).execute()
                return {"skipped": "same-session concurrent replay", "booking_id": winner[0]["id"]}

            log.warning("double-booking race — issuing refund for session %s", session_id)
            try:
                pi = payment_intent_id or tx.get("stripe_payment_intent_id")
                if pi:
                    stripe.Refund.create(payment_intent=pi)
                else:
                    log.error("REFUND SKIPPED — no payment_intent id for session %s (manual review required)", session_id)
            except Exception as refund_err:
                log.error("REFUND FAILED for session %s: %s — manual intervention required", session_id, refund_err)
            # Latch: mark refunded_race so replays don't refund again.
            sb.table("payment_transactions").update({
                "status": "refunded_race",
                "payment_status": "refunded",
                "stripe_payment_intent_id": payment_intent_id or tx.get("stripe_payment_intent_id"),
                "updated_at": _now_iso(),
            }).eq("session_id", session_id).execute()
            sb.table("booking_intents").update({
                "status": "refunded_race",
                "updated_at": _now_iso(),
            }).eq("id", intent["id"]).execute()
            # Release lock for the winner's benefit.
            sb.table("date_slot_locks").delete().eq("session_id", session_id).execute()
            return {"finalised": False, "refunded": True}
        # Not a unique-violation — bubble so webhook returns non-2xx and Stripe retries.
        raise

    # We won — flip tx to paid and mark intent paid.
    sb.table("payment_transactions").update({
        "status": "completed",
        "payment_status": "paid",
        "stripe_payment_intent_id": payment_intent_id,
        "updated_at": _now_iso(),
    }).eq("session_id", session_id).execute()

    sb.table("booking_intents").update({
        "status": "paid",
        "updated_at": _now_iso(),
    }).eq("id", intent["id"]).execute()

    # Release the soft lock for cleanliness (index now enforces uniqueness).
    sb.table("date_slot_locks").delete().eq("session_id", session_id).execute()

    # Send confirmation email with Supabase-issued recovery link. Best-effort;
    # a send failure does NOT roll back the booking.
    try:
        invite_url = _generate_invite_link(intent["email"])
        html_body, text_body = _render_email(intent, invite_url)
        subject = f"Your {intent['package_title']} booking is confirmed"
        _send_confirmation_email(intent["email"], subject, html_body, text_body)
    except Exception as e:
        log.exception("Confirmation email failed for session %s: %s", session_id, e)

    return {"finalised": True, "booking_id": booking_row["id"] if booking_row else None}


@router.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")
    except Exception as e:
        log.warning("webhook parse failed: %s", e)
        raise HTTPException(400, "Bad payload")

    et = event["type"]
    obj = event["data"]["object"]
    sb = _sb()

    if et == "checkout.session.completed":
        _finalise_paid_session(obj["id"], obj.get("payment_intent"))
    elif et == "checkout.session.async_payment_succeeded":
        _finalise_paid_session(obj["id"], obj.get("payment_intent"))
    elif et == "checkout.session.async_payment_failed":
        sb.table("payment_transactions").update({
            "status": "failed",
            "payment_status": "failed",
            "updated_at": _now_iso(),
        }).eq("session_id", obj["id"]).execute()
        sb.table("booking_intents").update({"status": "failed", "updated_at": _now_iso()}).eq("session_id", obj["id"]).execute()
        sb.table("date_slot_locks").delete().eq("session_id", obj["id"]).execute()
    elif et == "checkout.session.expired":
        sb.table("payment_transactions").update({
            "status": "expired",
            "payment_status": "expired",
            "updated_at": _now_iso(),
        }).eq("session_id", obj["id"]).execute()
        sb.table("booking_intents").update({"status": "expired", "updated_at": _now_iso()}).eq("session_id", obj["id"]).execute()
        sb.table("date_slot_locks").delete().eq("session_id", obj["id"]).execute()

    return {"ok": True}
