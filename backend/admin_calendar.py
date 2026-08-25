"""Admin calendar aggregator — GET /api/admin/calendar.

Returns a single sorted list of upcoming events pulled from multiple
source tables, so Nathan has one view of shoots + invoice-due dates
without hopping between /bookings and /invoices.

Response contract (session 15 — locked in with Nathan):

    {
      "range": { "from": ISO_DATE, "to": ISO_DATE },
      "events": [
        {
          "kind":  "shoot" | "invoice_deposit" | "invoice_balance",
          "date":  "YYYY-MM-DD",           # ISO date, sortable as string
          "title": str,
          "id":    "{kind}:{source-uuid}", # namespaced, unique across kinds
          "link":  str,                    # portal deep-link
          # optional per-kind — OMITTED (not null) when N/A:
          "status":       ...,
          "amount_gbp":   float,
          "client_name":  str,
          "meta":         dict,
        },
        ...
      ]
    }

Extensibility (documented in the design review):
  - Adding a new event kind = one new loader function + one line in SOURCES.
  - Never put contract-required fields (kind/date/title/id/link) inside
    `meta` — they'd be invisible to the generic UI.
"""
from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

log = logging.getLogger(__name__)
router = APIRouter()
_bearer = HTTPBearer(auto_error=False)

# The Supabase client is a single shared module-level instance and FastAPI
# runs sync endpoints in a threadpool, so concurrent requests (e.g. the
# dashboard firing /admin/dashboard + /admin/calendar together on load)
# share one pooled HTTP connection. A keep-alive connection the server has
# closed then surfaces as httpx.RemoteProtocolError ("Server disconnected")
# intermittently. These loaders are idempotent reads and httpx drops the
# dead connection on that error, so a short retry gets a fresh one.
_TRANSIENT_RETRIES = 3
_TRANSIENT_BACKOFF_S = 0.05


def _retry_transient(fn, *args):
    """Call fn(*args), retrying on transient httpx transport errors."""
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


def _sb():
    from server import get_sb  # lazy — avoids circular
    return get_sb()


def _require_admin(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    """Same shape as pricing.py._require_admin — self-contained so this
    module has no import-order coupling to server.py's module load."""
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
# SOURCE LOADERS — each returns a list of event dicts matching the contract.
# ============================================================================
#
# Contract for every loader:
#   def _load_X(sb, from_iso: str, to_iso: str) -> list[dict]
#     returns events dated between from_iso and to_iso (inclusive)
#     each event has {kind, date, title, id, link} + optional per-kind fields
#     omits optional fields entirely rather than returning None
# ----------------------------------------------------------------------------

def _client_name_map(sb, client_ids: list[str]) -> dict[str, str]:
    """Batch-fetch client names for a set of client_ids. Returns
    {client_id: full_name}. Empty dict for empty input."""
    if not client_ids:
        return {}
    ids = list(set(c for c in client_ids if c))
    rows = sb.table("clients").select("id, full_name, email").in_("id", ids).execute().data or []
    return {r["id"]: (r.get("full_name") or r.get("email") or "") for r in rows}


def _load_shoots(sb, from_iso: str, to_iso: str) -> list[dict]:
    rows = (
        sb.table("bookings")
        .select("id, client_id, title, event_date, status, is_seed_data")
        .gte("event_date", from_iso)
        .lte("event_date", to_iso)
        .in_("status", ["confirmed", "completed"])
        .eq("is_seed_data", False)
        .execute()
        .data or []
    )
    names = _client_name_map(sb, [r["client_id"] for r in rows])
    out = []
    for r in rows:
        evt = {
            "kind": "shoot",
            "date": r["event_date"],
            "title": r.get("title") or "Shoot",
            "id": f"shoot:{r['id']}",
            "link": f"/bookings",  # no per-booking detail page yet in the portal
            "status": r["status"],
        }
        cname = names.get(r["client_id"])
        if cname:
            evt["client_name"] = cname
        out.append(evt)
    return out


def _load_invoice_deposits(sb, from_iso: str, to_iso: str) -> list[dict]:
    rows = (
        sb.table("invoices")
        .select("id, client_id, booking_id, amount, currency, due_on, status, invoice_number, payment_purpose, is_seed_data")
        .gte("due_on", from_iso)
        .lte("due_on", to_iso)
        .eq("is_seed_data", False)
        .in_("status", ["sent", "overdue"])
        .execute()
        .data or []
    )
    # payment_purpose='deposit' OR NULL (legacy pre-Migration-012 invoices).
    rows = [r for r in rows if (r.get("payment_purpose") or "deposit") == "deposit"]
    names = _client_name_map(sb, [r["client_id"] for r in rows])
    out = []
    for r in rows:
        cname = names.get(r["client_id"], "")
        evt = {
            "kind": "invoice_deposit",
            "date": r["due_on"],
            "title": f"Deposit invoice due — {cname or 'client'}",
            "id": f"invoice_deposit:{r['id']}",
            "link": "/invoices",
            "status": r["status"],
            "amount_gbp": float(r["amount"]),
            "meta": {"invoice_id": r["id"], "invoice_number": r.get("invoice_number")},
        }
        if cname:
            evt["client_name"] = cname
        out.append(evt)
    return out


def _load_invoice_balances(sb, from_iso: str, to_iso: str) -> list[dict]:
    rows = (
        sb.table("invoices")
        .select("id, client_id, booking_id, amount, currency, due_on, status, invoice_number, reminder_sent_at, payment_purpose, is_seed_data")
        .gte("due_on", from_iso)
        .lte("due_on", to_iso)
        .eq("is_seed_data", False)
        .eq("payment_purpose", "balance")
        .in_("status", ["sent", "overdue"])
        .execute()
        .data or []
    )
    names = _client_name_map(sb, [r["client_id"] for r in rows])
    out = []
    for r in rows:
        cname = names.get(r["client_id"], "")
        evt = {
            "kind": "invoice_balance",
            "date": r["due_on"],
            "title": f"Balance due — {cname or 'client'}",
            "id": f"invoice_balance:{r['id']}",
            "link": "/invoices",
            "status": r["status"],
            "amount_gbp": float(r["amount"]),
            "meta": {
                "invoice_id": r["id"],
                "invoice_number": r.get("invoice_number"),
                "booking_id": r.get("booking_id"),
                "reminder_sent_at": r.get("reminder_sent_at"),
            },
        }
        if cname:
            evt["client_name"] = cname
        out.append(evt)
    return out


# Adding a new event kind later: write another _load_X function above,
# then append it here. That's the whole surface change.
SOURCES = [
    _load_shoots,
    _load_invoice_deposits,
    _load_invoice_balances,
]


# ============================================================================
# Endpoint
# ============================================================================

@router.get("/api/admin/calendar")
def get_calendar(
    from_: str = Query(..., alias="from", description="ISO date, inclusive."),
    to: str = Query(..., description="ISO date, inclusive."),
    admin=Depends(_require_admin),
):
    # Validate the range strictly. Rejecting bad input at the boundary
    # avoids weird downstream comparisons ("2026-13-99" > "2026-08-01" is
    # still a valid string compare, but nothing sensible comes out).
    try:
        d_from = date.fromisoformat(from_)
        d_to = date.fromisoformat(to)
    except ValueError:
        raise HTTPException(422, "Both 'from' and 'to' must be YYYY-MM-DD dates.")
    if d_to < d_from:
        raise HTTPException(422, "'to' must be on or after 'from'.")
    if (d_to - d_from) > timedelta(days=400):
        # Guardrail — no realistic calendar view exceeds a year of window.
        # Prevents accidental full-table scans if the frontend sends
        # bogus wide ranges.
        raise HTTPException(422, "Range exceeds 400 days.")

    sb = _sb()
    events: list[dict] = []
    for source in SOURCES:
        try:
            events.extend(_retry_transient(source, sb, from_, to))
        except Exception as e:
            # Per-source isolation: a broken loader doesn't take down the
            # whole endpoint. Log loudly and continue with the others.
            # (Transient transport blips are retried first — see
            # _retry_transient — so this only fires on a genuine error.)
            log.exception("calendar source %s failed", getattr(source, "__name__", "?"))
            events.append({
                "kind": "_error",
                "date": from_,
                "title": f"Source {getattr(source, '__name__', '?')} failed",
                "id": f"_error:{getattr(source, '__name__', 'unknown')}",
                "link": "",
                "meta": {"error": f"{type(e).__name__}: {e}"},
            })

    events.sort(key=lambda e: (e["date"], e["kind"], e["id"]))
    return {"range": {"from": from_, "to": to}, "events": events}
