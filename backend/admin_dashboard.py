"""Admin dashboard aggregator + enquiries CRUD.

Endpoints:
  GET  /api/admin/dashboard      — attention-band summary (batched)
  GET  /api/admin/enquiries      — list contact_enquiries, filter by ?status=
  PATCH /api/admin/enquiries/{id} — update status (new|replied|archived|spam)

Design notes:
  * The dashboard aggregator makes 4 Supabase queries in one endpoint so
    the frontend fires ONE round-trip on load. Returning top-N per tile
    (with a total count) keeps the payload small; the tile then deep-links
    to the full listing when needed.
  * Cron section is a placeholder (returns null) until Migration 014
    lands + we wire the audit write in daily_invoicing.py. Frontend
    tolerates cron=null gracefully.
  * enquiries endpoints keep the mutation surface tiny — a PATCH that
    accepts ONLY a status field. Anything richer (reply notes, assigned
    to, etc.) can be added later without breaking clients that only send
    {status: X}.
"""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)
router = APIRouter()
_bearer = HTTPBearer(auto_error=False)

# See admin_calendar._retry_transient — the shared Supabase client's pooled
# connection can surface httpx.RemoteProtocolError under FastAPI's concurrent
# threadpool. These reads are idempotent, so retry on the dropped connection.
_TRANSIENT_RETRIES = 3
_TRANSIENT_BACKOFF_S = 0.05


def _retry_transient(fn, *args):
    last = None
    for attempt in range(_TRANSIENT_RETRIES):
        try:
            return fn(*args)
        except httpx.TransportError as e:
            last = e
            log.warning("transient transport error (attempt %d/%d): %s",
                        attempt + 1, _TRANSIENT_RETRIES, e)
            time.sleep(_TRANSIENT_BACKOFF_S * (attempt + 1))
    raise last

ATTENTION_ITEMS_PER_TILE = 5
BALANCE_HORIZON_DAYS = 7
REMINDER_QUEUED_WINDOW_DAYS = 2  # matches daily_invoicing.REMINDER_LEAD_DAYS

# Staleness threshold for the daily cron. The job is scheduled once a day
# (24h cadence); 26h gives a 2h grace before we flag a silent failure.
# The whole point: convert an invisible, silently-stalled job into a
# visible red flag automatically, instead of relying on someone checking.
import os as _os
CRON_STALE_HOURS = float(_os.environ.get("CRON_STALE_HOURS", "26"))

ALLOWED_ENQUIRY_STATUSES = ("new", "replied", "archived", "spam")


def _sb():
    from server import get_sb
    return get_sb()


def _require_admin(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    if not creds:
        raise HTTPException(401, "Bearer token required")
    sb = _sb()
    try:
        res = sb.auth.get_user(creds.credentials)
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    if not res or not res.user:
        raise HTTPException(401, "Invalid or expired token")
    try:
        rows = sb.table("clients").select("*").eq("user_id", res.user.id).limit(1).execute().data
    except Exception as e:
        raise HTTPException(500, f"admin lookup failed: {e}")
    if not rows or rows[0].get("role") != "admin":
        raise HTTPException(403, "Admin access required")
    return rows[0]


# ============================================================================
# Attention tile loaders
# ============================================================================

def _tile_enquiries(sb) -> dict:
    """New enquiries awaiting reply."""
    rows = (
        sb.table("contact_enquiries")
        .select("id, name, email, package_id, event_date, message, source_url, status, created_at")
        .eq("status", "new")
        .order("created_at", desc=True)
        .limit(ATTENTION_ITEMS_PER_TILE)
        .execute()
        .data or []
    )
    # Count of ALL new ones, not just the top 5.
    count_res = sb.table("contact_enquiries").select("id", count="exact").eq("status", "new").execute()
    total = count_res.count if hasattr(count_res, "count") else len(count_res.data or [])
    return {
        "count": total,
        "items": [
            {
                "id": r["id"],
                "name": r["name"],
                "email": r["email"],
                "package_id": r.get("package_id"),
                "event_date": r.get("event_date"),
                "created_at": r["created_at"],
                # Truncate the message so a war-and-peace enquiry doesn't
                # blow up the dashboard payload.
                "message_preview": (r["message"] or "")[:200],
            }
            for r in rows
        ],
    }


def _tile_overdue_invoices(sb) -> dict:
    rows = (
        sb.table("invoices")
        .select("id, client_id, amount, currency, due_on, status, invoice_number, payment_purpose")
        .eq("status", "overdue")
        .eq("is_seed_data", False)
        .order("due_on", desc=False)
        .execute()
        .data or []
    )
    # Client names in one batched fetch
    client_ids = list({r["client_id"] for r in rows if r.get("client_id")})
    names = {}
    if client_ids:
        cl = sb.table("clients").select("id, full_name, email").in_("id", client_ids).execute().data or []
        names = {c["id"]: (c.get("full_name") or c.get("email") or "") for c in cl}
    total_gbp = round(sum(float(r["amount"]) for r in rows), 2)
    items = [
        {
            "id": r["id"],
            "invoice_number": r.get("invoice_number"),
            "client_name": names.get(r["client_id"], ""),
            "amount_gbp": float(r["amount"]),
            "due_on": r["due_on"],
            "purpose": r.get("payment_purpose") or "deposit",
        }
        for r in rows[:ATTENTION_ITEMS_PER_TILE]
    ]
    return {"count": len(rows), "total_gbp": total_gbp, "items": items}


def _tile_balance_actions(sb) -> dict:
    """Balance invoices due in the next BALANCE_HORIZON_DAYS.

    Adds a `reminder_queued` flag on rows where the daily cron will fire
    a reminder tomorrow (reminder_sent_at IS NULL AND due_on <= today+2).
    """
    today = date.today()
    horizon_iso = (today + timedelta(days=BALANCE_HORIZON_DAYS)).isoformat()
    reminder_cutoff_iso = (today + timedelta(days=REMINDER_QUEUED_WINDOW_DAYS)).isoformat()

    rows = (
        sb.table("invoices")
        .select("id, client_id, amount, due_on, status, invoice_number, reminder_sent_at, booking_id")
        .eq("payment_purpose", "balance")
        .in_("status", ["sent", "overdue"])
        .lte("due_on", horizon_iso)
        .eq("is_seed_data", False)
        .order("due_on", desc=False)
        .execute()
        .data or []
    )
    client_ids = list({r["client_id"] for r in rows if r.get("client_id")})
    names = {}
    if client_ids:
        cl = sb.table("clients").select("id, full_name, email").in_("id", client_ids).execute().data or []
        names = {c["id"]: (c.get("full_name") or c.get("email") or "") for c in cl}
    items = []
    for r in rows[:ATTENTION_ITEMS_PER_TILE]:
        items.append({
            "id": r["id"],
            "invoice_number": r.get("invoice_number"),
            "client_name": names.get(r["client_id"], ""),
            "amount_gbp": float(r["amount"]),
            "due_on": r["due_on"],
            "status": r["status"],
            "reminder_queued": (
                r.get("reminder_sent_at") is None
                and r["due_on"] <= reminder_cutoff_iso
            ),
            "reminder_sent_at": r.get("reminder_sent_at"),
        })
    return {"count": len(rows), "items": items}


def _tile_deliverables_in_review(sb) -> dict:
    rows = (
        sb.table("deliverables")
        .select("id, client_id, booking_id, title, status, updated_at")
        .in_("status", ["in_review", "revisions_requested"])
        .order("updated_at", desc=True)
        .execute()
        .data or []
    )
    client_ids = list({r["client_id"] for r in rows if r.get("client_id")})
    names = {}
    if client_ids:
        cl = sb.table("clients").select("id, full_name, email").in_("id", client_ids).execute().data or []
        names = {c["id"]: (c.get("full_name") or c.get("email") or "") for c in cl}
    items = [
        {
            "id": r["id"],
            "title": r.get("title") or "(untitled)",
            "status": r["status"],
            "client_name": names.get(r["client_id"], ""),
            "updated_at": r["updated_at"],
        }
        for r in rows[:ATTENTION_ITEMS_PER_TILE]
    ]
    return {"count": len(rows), "items": items}


def _parse_ts(iso: Optional[str]):
    """Parse a Supabase timestamptz string to an aware datetime, or None."""
    if not iso:
        return None
    from datetime import datetime
    try:
        s = iso.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            from datetime import timezone as _tz
            dt = dt.replace(tzinfo=_tz.utc)
        return dt
    except Exception:
        return None


def _tile_cron_last_run(sb) -> Optional[dict]:
    """Last daily-invoicing cron run + a staleness signal. Returns None if:
      - Migration 014 (cron_runs table) not applied yet, OR
      - no runs recorded yet.
    Frontend tolerates None → renders "no data yet" placeholder.

    Staleness: `stale` is True when there has been NO successful (ok=true)
    run within CRON_STALE_HOURS. This flags the "job died silently and
    nobody noticed" failure mode — a red row (or no row) for >26h surfaces
    automatically instead of waiting for someone to check.
    """
    try:
        rows = _retry_transient(lambda: (
            sb.table("cron_runs")
            .select("id, job_name, started_at, finished_at, summary, error_count, ok")
            .eq("job_name", "daily_invoicing")
            .order("started_at", desc=True)
            .limit(1)
            .execute()
            .data or []
        ))
    except Exception as e:
        msg = str(e).lower()
        if "does not exist" in msg or "pgrst205" in msg or "schema cache" in msg:
            return None  # Mig 014 not applied yet — degrade gracefully
        log.exception("cron_last_run read failed")
        return None
    if not rows:
        return None
    r = rows[0]

    # Last SUCCESSFUL run — the "green row" the staleness check keys off.
    last_ok_at = None
    try:
        ok_rows = _retry_transient(lambda: (
            sb.table("cron_runs")
            .select("started_at")
            .eq("job_name", "daily_invoicing")
            .eq("ok", True)
            .order("started_at", desc=True)
            .limit(1)
            .execute()
            .data or []
        ))
        if ok_rows:
            last_ok_at = ok_rows[0]["started_at"]
    except Exception:
        log.exception("cron last-ok read failed")

    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    ok_dt = _parse_ts(last_ok_at)
    hours_since_ok = round((now - ok_dt).total_seconds() / 3600.0, 1) if ok_dt else None
    # Stale when there's no green row inside the window (never succeeded, or
    # last success is older than the threshold).
    stale = (hours_since_ok is None) or (hours_since_ok > CRON_STALE_HOURS)

    return {
        "id": r["id"],
        "started_at": r["started_at"],
        "finished_at": r.get("finished_at"),
        "ok": r["ok"],
        "error_count": r["error_count"],
        "summary": r.get("summary") or {},
        "stale": stale,
        "last_ok_at": last_ok_at,
        "hours_since_last_ok": hours_since_ok,
        "stale_threshold_hours": CRON_STALE_HOURS,
    }


# ============================================================================
# GET /api/admin/dashboard
# ============================================================================

@router.get("/api/admin/dashboard")
def get_dashboard(admin=Depends(_require_admin)):
    sb = _sb()
    # Per-tile isolation — one failing loader doesn't break the whole
    # dashboard. Each loader is small, so this is cheap safety net.
    def _safe(fn):
        try:
            return _retry_transient(fn, sb)
        except Exception as e:
            log.exception("dashboard tile %s failed", fn.__name__)
            return {"count": 0, "items": [], "error": f"{type(e).__name__}: {e}"}

    return {
        "attention": {
            "enquiries": _safe(_tile_enquiries),
            "overdue_invoices": _safe(_tile_overdue_invoices),
            "balance_actions": _safe(_tile_balance_actions),
            "deliverables_in_review": _safe(_tile_deliverables_in_review),
        },
        "cron": {
            "daily_invoicing": _tile_cron_last_run(sb),
        },
    }


# ============================================================================
# Enquiries CRUD
# ============================================================================

@router.get("/api/admin/enquiries")
def list_enquiries(
    status: Optional[str] = Query(None, description=f"Filter by status. Any of: {ALLOWED_ENQUIRY_STATUSES}"),
    limit: int = Query(50, ge=1, le=200),
    admin=Depends(_require_admin),
):
    if status is not None and status not in ALLOWED_ENQUIRY_STATUSES:
        raise HTTPException(422, f"status must be one of {ALLOWED_ENQUIRY_STATUSES}")
    q = _sb().table("contact_enquiries").select("*")
    if status:
        q = q.eq("status", status)
    rows = q.order("created_at", desc=True).limit(limit).execute().data or []
    return rows


class EnquiryStatusPatch(BaseModel):
    status: str = Field(..., description=f"One of {ALLOWED_ENQUIRY_STATUSES}")


@router.patch("/api/admin/enquiries/{enquiry_id}")
def update_enquiry_status(enquiry_id: str, patch: EnquiryStatusPatch, admin=Depends(_require_admin)):
    if patch.status not in ALLOWED_ENQUIRY_STATUSES:
        raise HTTPException(422, f"status must be one of {ALLOWED_ENQUIRY_STATUSES}")
    from datetime import datetime, timezone
    try:
        rows = (
            _sb().table("contact_enquiries")
            .update({"status": patch.status, "updated_at": datetime.now(timezone.utc).isoformat()})
            .eq("id", enquiry_id)
            .execute()
            .data or []
        )
    except Exception as e:
        raise HTTPException(500, f"update failed: {e}")
    if not rows:
        raise HTTPException(404, "Enquiry not found")
    return rows[0]
