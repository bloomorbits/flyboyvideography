"""Bunny webhook backfill / reconciliation job.

Repairs deliverables whose Bunny Stream webhook was missed (backend redeploy,
Bunny retry exhausted, video linked before the webhook was wired) and would
otherwise sit forever in a non-terminal status.

Two triggers, ONE shared core (`reconcile_bunny_statuses`):
  * POST /api/admin/jobs/run-bunny-reconcile  — cron-JWT gated (scheduled sweep).
      Reuses CRON_JOB_JWT_SECRET but with a DISTINCT audience+scope
      ('flyboy:cron:bunny-reconcile' / 'cron:bunny-reconcile') so an invoicing
      token can't trigger reconcile and vice-versa — narrow blast radius, and
      NOT the admin session token. No new secret to provision on Railway/GitHub.
  * POST /api/admin/bunny/reconcile           — require_admin gated (manual "Reconcile
      Bunny statuses" button in /admin). Same core, immediate repair on demand.

CORRECTNESS (the design-gate concerns):
  * STUCK QUERY targets ONLY rows that are (a) linked to Bunny, (b) in a
    non-terminal status (NULL/Queued/Processing/Encoding), AND (c) linked longer
    ago than the stale threshold (default 15 min). Terminal rows
    (Finished/ResolutionFinished/Failed) are NEVER re-polled.
  * A genuinely-still-processing video is NOT false-flagged: we write back
    exactly what Bunny reports. If Bunny still says Processing/Encoding, we record
    it as still-processing (updating the status string if it advanced) and leave
    it eligible for the next run — we NEVER fabricate a Failed. Only Bunny's own
    Failed(5)/PresignedUploadFailed(8) becomes Failed.
  * Idempotent: writing Bunny's current truth is repeat-safe; terminal rows drop
    out of the query next run, so no double-processing.

Audit: reuses public.cron_runs (Migration 014) with job_name='bunny_reconcile'.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

log = logging.getLogger(__name__)
router = APIRouter()
_bearer = HTTPBearer(auto_error=False)

# ---------- Config ----------
CRON_JOB_JWT_SECRET = os.environ.get("CRON_JOB_JWT_SECRET", "")
RECONCILE_AUDIENCE = "flyboy:cron:bunny-reconcile"
RECONCILE_SCOPE = "cron:bunny-reconcile"
STALE_MINUTES = int(os.environ.get("BUNNY_RECONCILE_STALE_MINUTES", "15"))

BUNNY_STREAM_LIBRARY_ID = os.environ.get("BUNNY_STREAM_LIBRARY_ID", "")
BUNNY_STREAM_API_KEY = os.environ.get("BUNNY_STREAM_API_KEY", "")

# Bunny Stream status int → name (mirrors bunny.STREAM_STATUS_NAMES).
STATUS_NAMES = {
    0: "Queued", 1: "Processing", 2: "Encoding", 3: "Finished",
    4: "ResolutionFinished", 5: "Failed", 6: "PresignedUploadStarted",
    7: "PresignedUploadFinished", 8: "PresignedUploadFailed",
}
# Non-terminal statuses we re-poll (the exact locked set + NULL handled in query).
NONTERMINAL = ("Queued", "Processing", "Encoding")
# Statuses that mean "done, keep it" vs "done, surface as failed".
TERMINAL_OK = ("Finished", "ResolutionFinished")
TERMINAL_FAILED = ("Failed", "PresignedUploadFailed")


def _sb():
    from server import get_sb  # lazy — avoids circular import
    return get_sb()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------- Auth ----------

def _require_reconcile_token(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    """Cron-JWT gate for the scheduled sweep. Same secret as invoicing but a
    DISTINCT audience+scope, so tokens don't cross endpoints. Fails closed."""
    if not CRON_JOB_JWT_SECRET:
        raise HTTPException(503, "CRON_JOB_JWT_SECRET not configured on the server.")
    if not creds:
        raise HTTPException(401, "Cron bearer token required.")
    try:
        payload = jwt.decode(
            creds.credentials, CRON_JOB_JWT_SECRET,
            algorithms=["HS256"], audience=RECONCILE_AUDIENCE,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Cron token expired.")
    except jwt.InvalidAudienceError:
        raise HTTPException(401, "Cron token audience mismatch.")
    except jwt.PyJWTError as e:
        tok = creds.credentials or ""
        if tok.count(".") != 2:
            raise HTTPException(401, "Cron token malformed — expected a signed JWT (3 segments).")
        log.warning("bunny-reconcile cron token verify failed: %s", e)
        raise HTTPException(401, "Invalid cron token.")
    if payload.get("scope") != RECONCILE_SCOPE:
        raise HTTPException(403, "Cron token scope mismatch.")
    return payload


def _require_admin(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    """Admin session gate for the manual trigger (reuses bunny.py's check)."""
    from bunny import _require_admin as bunny_admin
    return bunny_admin(creds)


# ---------- Bunny Stream poll ----------

def _poll_bunny_status(video_guid: str) -> dict:
    """GET the video from Bunny Stream. Returns:
      {"ok": True, "status_int": int, "status_name": str}          on 200
      {"ok": False, "http": 404, "reason": "not_found"}            on 404
      {"ok": False, "http": <code>, "reason": <str>}               otherwise
    Never raises — the caller records the reason and moves on."""
    if not (BUNNY_STREAM_LIBRARY_ID and BUNNY_STREAM_API_KEY):
        return {"ok": False, "http": 0, "reason": "bunny_stream_config_missing"}
    url = f"https://video.bunnycdn.com/library/{BUNNY_STREAM_LIBRARY_ID}/videos/{video_guid}"
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(url, headers={"AccessKey": BUNNY_STREAM_API_KEY, "accept": "application/json"})
    except Exception as e:
        return {"ok": False, "http": 0, "reason": f"request_error:{type(e).__name__}"}
    if r.status_code == 404:
        return {"ok": False, "http": 404, "reason": "not_found_in_bunny"}
    if r.status_code in (401, 403):
        return {"ok": False, "http": r.status_code, "reason": "bunny_auth_error"}
    if r.status_code != 200:
        return {"ok": False, "http": r.status_code, "reason": f"bunny_http_{r.status_code}"}
    try:
        status_int = int(r.json().get("status"))
    except Exception:
        return {"ok": False, "http": 200, "reason": "unparseable_status"}
    return {"ok": True, "status_int": status_int,
            "status_name": STATUS_NAMES.get(status_int, f"Unknown({status_int})")}


# ---------- Core ----------

def reconcile_bunny_statuses(dry_run: bool = False) -> dict:
    """Poll Bunny for stuck deliverables and write back the current truth.
    Idempotent. Returns a summary (same shape the endpoints return)."""
    sb = _sb()
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=STALE_MINUTES)).isoformat()

    summary = {
        "ran_at": _now_iso(),
        "dry_run": dry_run,
        "stale_minutes": STALE_MINUTES,
        "cutoff": cutoff,
        "candidates": 0,
        "resolved_finished": [],     # advanced to a terminal OK status
        "flagged_failed": [],        # Bunny reports Failed → surfaced in attention band
        "still_processing": [],      # Bunny still working — NOT flagged, re-checked next run
        "not_found_in_bunny": [],    # video GUID unknown to Bunny (deleted?) — surfaced, status untouched
        "errors": [],
    }

    # ---- Audit: open cron_runs row ----
    run_id: Optional[str] = None
    try:
        row = sb.table("cron_runs").insert({
            "job_name": "bunny_reconcile", "summary": {"dry_run": dry_run},
        }).execute().data
        if row:
            run_id = row[0]["id"]
    except Exception as e:
        log.warning("cron_runs audit-open failed (Mig 014?): %s", e)

    # ---- STUCK QUERY ----
    # linked to Bunny  AND  linked longer ago than the stale threshold
    # AND  (status IS NULL OR status IN non-terminal set).
    try:
        rows = (
            sb.table("deliverables")
            .select("id, title, bunny_video_guid, bunny_status, bunny_linked_at")
            .not_.is_("bunny_video_guid", "null")
            .lt("bunny_linked_at", cutoff)
            .or_("bunny_status.is.null,bunny_status.in.(Queued,Processing,Encoding)")
            .execute().data or []
        )
    except Exception as e:
        log.exception("bunny reconcile: stuck query failed")
        summary["errors"].append({"stage": "query", "err": f"{type(e).__name__}: {e}"})
        rows = []

    summary["candidates"] = len(rows)

    for d in rows:
        did, guid, cur = d["id"], d.get("bunny_video_guid"), d.get("bunny_status")
        try:
            res = _poll_bunny_status(guid)
            if not res["ok"]:
                if res["reason"] == "not_found_in_bunny":
                    summary["not_found_in_bunny"].append({"id": did, "guid": guid})
                else:
                    summary["errors"].append({"id": did, "guid": guid, "reason": res["reason"], "http": res.get("http")})
                continue

            new_name = res["status_name"]

            if new_name in TERMINAL_FAILED:
                if not dry_run and new_name != cur:
                    sb.table("deliverables").update({"bunny_status": new_name}).eq("id", did).execute()
                summary["flagged_failed"].append({"id": did, "guid": guid, "from": cur, "to": new_name})

            elif new_name in TERMINAL_OK:
                if not dry_run and new_name != cur:
                    sb.table("deliverables").update({"bunny_status": new_name}).eq("id", did).execute()
                summary["resolved_finished"].append({"id": did, "guid": guid, "from": cur, "to": new_name})

            else:
                # Still Queued/Processing/Encoding (or presigned-upload states).
                # DO NOT flag as failed. Reflect Bunny's truth if it advanced;
                # leave eligible for the next sweep.
                changed = new_name != cur
                if not dry_run and changed:
                    sb.table("deliverables").update({"bunny_status": new_name}).eq("id", did).execute()
                summary["still_processing"].append({"id": did, "guid": guid, "status": new_name, "changed": changed})

        except Exception as e:
            log.exception("bunny reconcile: row %s failed", did)
            summary["errors"].append({"id": did, "err": f"{type(e).__name__}: {e}"})

    # ---- Audit: close cron_runs row ----
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

    return summary


# ---------- Endpoints ----------

@router.post("/api/admin/jobs/run-bunny-reconcile")
def run_bunny_reconcile_cron(request: Request, _claims: dict = Depends(_require_reconcile_token)):
    """Scheduled sweep (GitHub Actions). dry_run=1 to compute without writing."""
    return reconcile_bunny_statuses(dry_run=request.query_params.get("dry_run") == "1")


@router.post("/api/admin/bunny/reconcile")
def run_bunny_reconcile_manual(request: Request, admin=Depends(_require_admin)):
    """Manual 'Reconcile Bunny statuses' trigger from /admin."""
    return reconcile_bunny_statuses(dry_run=request.query_params.get("dry_run") == "1")
