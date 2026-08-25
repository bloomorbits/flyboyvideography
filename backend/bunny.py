"""Bunny.net integration — Phase 1.

First piece: a safe, admin-gated config-presence check so we can verify the
8 Railway env vars are actually reaching the backend BEFORE writing any code
that depends on them (same "confirm it's real, not assumed" discipline used
for the cron). It reports presence + length + light format sanity flags and
NEVER returns the secret values themselves.

The playback-token / download-url / play-event / webhook endpoints (and the
schema they depend on, Migration 015) are built in the next step, after this
check confirms the config and after Migration 015 is applied + introspected.
See docs/BUNNY_PHASE_1_SPEC.md.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

log = logging.getLogger(__name__)
router = APIRouter()
_bearer = HTTPBearer(auto_error=False)

# The exact 8 names from docs/BUNNY_PHASE_1_SPEC.md — kept in one place so
# the check and the eventual consumers reference identical strings.
BUNNY_ENV_VARS = [
    "BUNNY_STREAM_LIBRARY_ID",
    "BUNNY_STREAM_API_KEY",
    "BUNNY_STREAM_TOKEN_KEY",
    "BUNNY_STREAM_READ_ONLY_KEY",
    "BUNNY_STORAGE_ZONE",
    "BUNNY_STORAGE_PASSWORD",
    "BUNNY_STORAGE_S3_ENDPOINT",
    "BUNNY_STORAGE_S3_REGION",
]


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


def _format_hints(name: str, value: str) -> list[str]:
    """Non-secret sanity flags that catch the common paste mistakes flagged
    in the spec (scheme on the wrong field, a URL pasted into the region,
    a non-numeric library id). Returns a list of warning strings; empty =
    looks fine. Never echoes the value."""
    hints: list[str] = []
    if name == "BUNNY_STORAGE_S3_ENDPOINT":
        if not value.startswith("https://"):
            hints.append("expected to start with 'https://'")
    if name == "BUNNY_STORAGE_S3_REGION":
        if "/" in value or "." in value or len(value) > 12:
            hints.append("expected a short bare region code (e.g. 'de'), not a URL")
    if name == "BUNNY_STREAM_LIBRARY_ID":
        if not value.isdigit():
            hints.append("expected a numeric library id")
    return hints


@router.get("/api/admin/bunny/config-check")
def bunny_config_check(admin=Depends(_require_admin)):
    """Report presence (not values) of the 8 Bunny env vars + format hints.

    Response:
      {
        "all_present": bool,
        "vars": {
          "<NAME>": {"present": bool, "length": int, "hints": [str, ...]},
          ...
        }
      }
    """
    out = {}
    all_present = True
    for name in BUNNY_ENV_VARS:
        raw = os.environ.get(name, "")
        val = raw.strip()
        present = bool(val)
        if not present:
            all_present = False
        out[name] = {
            "present": present,
            "length": len(val),
            "hints": _format_hints(name, val) if present else [],
        }
    return {"all_present": all_present, "vars": out}


# ============================================================================
# Config / constants
# ============================================================================

STREAM_LIBRARY_ID = os.environ.get("BUNNY_STREAM_LIBRARY_ID", "")
STREAM_TOKEN_KEY = os.environ.get("BUNNY_STREAM_TOKEN_KEY", "")
STREAM_READ_ONLY_KEY = os.environ.get("BUNNY_STREAM_READ_ONLY_KEY", "")
STORAGE_ZONE = os.environ.get("BUNNY_STORAGE_ZONE", "")
STORAGE_PASSWORD = os.environ.get("BUNNY_STORAGE_PASSWORD", "")
STORAGE_S3_ENDPOINT = os.environ.get("BUNNY_STORAGE_S3_ENDPOINT", "")
STORAGE_S3_REGION = os.environ.get("BUNNY_STORAGE_S3_REGION", "")

EMBED_TTL_SECONDS = 1800   # 30 min (spec decision #5)
DOWNLOAD_TTL_SECONDS = 900  # 15 min (spec decision #6)

# Deliverable states whose RAW original may be downloaded (paid, approved
# final product). Drafts/in-review are stream-only under DRM.
DOWNLOADABLE_STATES = ("approved", "final_delivered")

STREAM_STATUS_NAMES = {
    0: "Queued", 1: "Processing", 2: "Encoding", 3: "Finished",
    4: "ResolutionFinished", 5: "Failed", 6: "PresignedUploadStarted",
    7: "PresignedUploadFinished", 8: "PresignedUploadFailed",
    9: "CaptionsGenerated", 10: "TitleOrDescriptionGenerated",
}

# play-event body value -> DB event_type (constraint-valid names)
PLAY_EVENT_MAP = {
    "play": "player_play",
    "player_play": "player_play",
    "player_25": "player_25",
    "player_50": "player_50",
    "player_75": "player_75",
    "player_ended": "player_ended",
    "player_heartbeat": "player_heartbeat",
}
HEARTBEAT_MIN_INTERVAL_S = 30


# ============================================================================
# Auth + entitlement
# ============================================================================

def _authed_client(creds: HTTPAuthorizationCredentials):
    """Authenticate a portal user (client OR admin) and return their clients
    row. 401 if the token is bad, 404 if no clients row."""
    if not creds:
        raise HTTPException(401, "Bearer token required")
    sb = _sb()
    try:
        res = sb.auth.get_user(creds.credentials)
    except Exception:
        raise HTTPException(401, "Invalid or expired token")
    if not res or not res.user:
        raise HTTPException(401, "Invalid or expired token")
    rows = sb.table("clients").select("*").eq("user_id", res.user.id).limit(1).execute().data
    if not rows:
        raise HTTPException(404, "Client profile not found")
    return rows[0]


def _load_deliverable(sb, deliverable_id: str) -> dict:
    r = sb.table("deliverables").select("*").eq("id", deliverable_id).limit(1).execute().data
    if not r:
        raise HTTPException(404, "Deliverable not found")
    return r[0]


def _entitled_or_403(sb, deliverable: dict, client: dict):
    """Client may only touch their own deliverable; admin bypasses. On a
    failed check, log an entitlement_denied event then 403."""
    is_admin = client.get("role") == "admin"
    if is_admin:
        return "admin"
    if deliverable["client_id"] != client["id"]:
        _log_event(sb, deliverable["id"], client["id"], "client",
                   "entitlement_denied", {"reason": "not_owner"})
        raise HTTPException(403, "Not your deliverable")
    return "client"


# ============================================================================
# Helpers — signing, overlay, logging, S3
# ============================================================================

def _sign_embed_url(video_guid: str, expires: int) -> str:
    """Bunny Embed View token: lowercase-hex SHA256(TOKEN_KEY + guid + str(expires)).
    No separators, no HMAC, no base64. expires is unix seconds."""
    material = (STREAM_TOKEN_KEY + video_guid + str(expires)).encode("utf-8")
    token = hashlib.sha256(material).hexdigest()
    return (
        f"https://iframe.mediadelivery.net/embed/"
        f"{STREAM_LIBRARY_ID}/{video_guid}?token={token}&expires={expires}"
    )


def _overlay_code(deliverable_id: str, client_id: str) -> str:
    """Short per-client-per-day reference shown as an on-player overlay.
    HMAC over (deliverable, client, UTC day) so the same client on the same
    day sees a stable code (aids abuse investigation), but it's not a
    per-view unique trace. Formatted AB12-C34D."""
    day = date.today().isoformat()
    msg = f"{deliverable_id}:{client_id}:{day}".encode("utf-8")
    digest = hmac.new(STREAM_TOKEN_KEY.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    raw = digest[:8].upper()
    return f"{raw[:4]}-{raw[4:]}"


def _log_event(sb, deliverable_id: str, client_id, actor_role: str,
               event_type: str, meta: dict | None = None):
    try:
        sb.table("deliverable_access_events").insert({
            "deliverable_id": deliverable_id,
            "client_id": client_id,
            "actor_role": actor_role,
            "event_type": event_type,
            "meta": meta or {},
        }).execute()
    except Exception as e:
        log.warning("access-event log failed (%s): %s", event_type, e)


_s3_client = None


def _s3():
    global _s3_client
    if _s3_client is None:
        import boto3
        from botocore.config import Config
        _s3_client = boto3.client(
            "s3",
            aws_access_key_id=STORAGE_ZONE,
            aws_secret_access_key=STORAGE_PASSWORD,
            endpoint_url=STORAGE_S3_ENDPOINT.rstrip("/"),
            region_name=STORAGE_S3_REGION,
            config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        )
    return _s3_client


# ============================================================================
# 1. Playback token
# ============================================================================

@router.post("/api/deliverables/{deliverable_id}/playback-token")
def playback_token(deliverable_id: str, creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    client = _authed_client(creds)
    sb = _sb()
    deliverable = _load_deliverable(sb, deliverable_id)
    actor_role = _entitled_or_403(sb, deliverable, client)

    guid = deliverable.get("bunny_video_guid")
    if not guid:
        raise HTTPException(409, "This film hasn't been published to streaming yet.")

    expires = int(datetime.now(timezone.utc).timestamp()) + EMBED_TTL_SECONDS
    embed_url = _sign_embed_url(guid, expires)
    overlay = _overlay_code(deliverable_id, deliverable["client_id"])
    _log_event(sb, deliverable_id, client["id"], actor_role, "playback_url_issued",
               {"expires": expires})
    return {"embed_url": embed_url, "expires": expires, "overlay_code": overlay}


# ============================================================================
# 2. Download URL (approved/final only)
# ============================================================================

@router.post("/api/deliverables/{deliverable_id}/download-url")
def download_url(deliverable_id: str, creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    client = _authed_client(creds)
    sb = _sb()
    deliverable = _load_deliverable(sb, deliverable_id)
    actor_role = _entitled_or_403(sb, deliverable, client)

    # State gate — the raw original is the paid, approved final product.
    if deliverable.get("status") not in DOWNLOADABLE_STATES:
        _log_event(sb, deliverable_id, client["id"], actor_role, "entitlement_denied",
                   {"reason": "not_downloadable_state", "status": deliverable.get("status")})
        raise HTTPException(409, "This deliverable isn't approved for download yet.")

    obj = deliverable.get("bunny_storage_object")
    if not obj:
        raise HTTPException(409, "No backup file uploaded for this deliverable.")

    key = obj.lstrip("/")
    if ".." in key.split("/"):
        raise HTTPException(400, "Invalid object key")

    url = _s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": STORAGE_ZONE, "Key": key},
        ExpiresIn=DOWNLOAD_TTL_SECONDS,
        HttpMethod="GET",
    )
    _log_event(sb, deliverable_id, client["id"], actor_role, "download_url_issued",
               {"expires_in": DOWNLOAD_TTL_SECONDS})
    return {"url": url, "expires_in": DOWNLOAD_TTL_SECONDS}


# ============================================================================
# 3. Play event
# ============================================================================

class PlayEventBody(BaseModel):
    event: str
    position_seconds: float | None = None


@router.post("/api/deliverables/{deliverable_id}/play-event")
def play_event(deliverable_id: str, body: PlayEventBody,
               creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    client = _authed_client(creds)
    sb = _sb()
    deliverable = _load_deliverable(sb, deliverable_id)
    actor_role = _entitled_or_403(sb, deliverable, client)

    event_type = PLAY_EVENT_MAP.get(body.event)
    if not event_type:
        raise HTTPException(422, f"Unknown event '{body.event}'")

    # Heartbeat rate-limit: skip if one fired < 30s ago for this pair.
    if event_type == "player_heartbeat":
        cutoff = (datetime.now(timezone.utc) - timedelta(seconds=HEARTBEAT_MIN_INTERVAL_S)).isoformat()
        recent = (
            sb.table("deliverable_access_events")
            .select("id")
            .eq("deliverable_id", deliverable_id)
            .eq("client_id", client["id"])
            .eq("event_type", "player_heartbeat")
            .gte("created_at", cutoff)
            .limit(1)
            .execute()
            .data
        )
        if recent:
            return {"ok": True, "throttled": True}

    meta = {}
    if body.position_seconds is not None:
        meta["position_seconds"] = body.position_seconds
    _log_event(sb, deliverable_id, client["id"], actor_role, event_type, meta)
    return {"ok": True}


# ============================================================================
# 4. Webhook receiver
# ============================================================================

def _verify_webhook(raw_body: bytes, request: Request) -> bool:
    version = request.headers.get("X-BunnyStream-Signature-Version")
    algorithm = request.headers.get("X-BunnyStream-Signature-Algorithm")
    received = request.headers.get("X-BunnyStream-Signature", "")
    if version != "v1" or algorithm != "hmac-sha256":
        return False
    if len(received) != 64:
        return False
    expected = hmac.new(
        STREAM_READ_ONLY_KEY.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, received)


@router.post("/api/bunny/webhook")
async def bunny_webhook(request: Request):
    raw_body = await request.body()
    if not _verify_webhook(raw_body, request):
        raise HTTPException(401, "Invalid Bunny Stream signature")

    import json as _json
    try:
        payload = _json.loads(raw_body)
    except ValueError:
        raise HTTPException(400, "Invalid JSON")

    for k in ("VideoLibraryId", "VideoGuid", "Status"):
        if k not in payload:
            raise HTTPException(400, "Missing webhook fields")

    if STREAM_LIBRARY_ID and str(payload["VideoLibraryId"]) != str(STREAM_LIBRARY_ID):
        raise HTTPException(401, "Wrong Stream library")

    guid = str(payload["VideoGuid"])
    status_int = int(payload["Status"])
    status_name = STREAM_STATUS_NAMES.get(status_int, f"Unknown({status_int})")

    sb = _sb()
    rows = sb.table("deliverables").select("id").eq("bunny_video_guid", guid).execute().data or []
    if not rows:
        # Orphan Bunny video (not linked to a deliverable) — fine, not ours.
        log.info("bunny webhook: no deliverable for guid %s (status %s)", guid, status_name)
        return {"ok": True, "matched": False}

    for d in rows:
        sb.table("deliverables").update({"bunny_status": status_name}).eq("id", d["id"]).execute()
    return {"ok": True, "matched": True, "status": status_name}
