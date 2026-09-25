"""Phase 2 — in-portal direct upload: prepare + complete.

Backend orchestrates; bytes go browser->Bunny directly. Two independent lanes:
  * Stream  — backend creates the video object + mints a 1h TUS signature scoped
              to that one videoId (SHA256(lib+key+expire+guid)).
  * Storage — backend mints a 15-min S3 presigned PUT to one random single-use key.
The long-lived Bunny secrets never leave the backend. Both lanes are verified
INDEPENDENTLY with Bunny on /complete — the client's "done" is never trusted.

Lifecycle (Migration 018): row created at prepare (upload_pending per lane) ->
'uploaded' (client reports) is skipped here; we go straight to backend-verified
'confirmed' | 'failed'. Orphan/partial cleanup is handled by the bunny_reconcile
sweep (folded in separately).
"""
from __future__ import annotations

import hashlib
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import PurePosixPath
from typing import Literal, Optional

import boto3
import httpx
from botocore.config import Config
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)

# ---- Config (values live on Railway; absent in preview -> clear 503 at call time) ----
STREAM_LIB = os.environ.get("BUNNY_STREAM_LIBRARY_ID", "")
STREAM_KEY = os.environ.get("BUNNY_STREAM_API_KEY", "")
TUS_TTL = int(os.environ.get("BUNNY_TUS_UPLOAD_TTL_SECONDS", "3600"))
TUS_ENDPOINT = "https://video.bunnycdn.com/tusupload"

STORAGE_ZONE = os.environ.get("BUNNY_STORAGE_ZONE", "")
STORAGE_PASSWORD = os.environ.get("BUNNY_STORAGE_PASSWORD", "")
STORAGE_REGION = os.environ.get("BUNNY_STORAGE_REGION", "")
STORAGE_S3_ENDPOINT = os.environ.get("BUNNY_STORAGE_S3_ENDPOINT", "")
STORAGE_PUT_TTL = int(os.environ.get("BUNNY_STORAGE_PRESIGN_TTL_SECONDS", "900"))

VIDEO_EXTS = (".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi", ".m2ts", ".mts", ".wmv", ".flv")


def _sb():
    from server import get_sb  # lazy — avoid circular import
    return get_sb()


def _require_admin(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    from bunny import _require_admin as bunny_admin
    return bunny_admin(creds)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_video_ext(name: str) -> str:
    ext = PurePosixPath(name or "").suffix.lower()
    if ext not in VIDEO_EXTS:
        raise HTTPException(422, f"filename must be a video file ({', '.join(VIDEO_EXTS)}) — got '{name}'")
    return ext


def _s3():
    if not (STORAGE_ZONE and STORAGE_PASSWORD and STORAGE_REGION and STORAGE_S3_ENDPOINT):
        raise HTTPException(503, "Bunny Storage S3 not configured (BUNNY_STORAGE_* env).")
    return boto3.client(
        "s3", endpoint_url=STORAGE_S3_ENDPOINT, region_name=STORAGE_REGION,
        aws_access_key_id=STORAGE_ZONE, aws_secret_access_key=STORAGE_PASSWORD,
        config=Config(signature_version="s3v4"),
    )


# ---------------------------------------------------------------------------
# PREPARE
# ---------------------------------------------------------------------------
class PrepareIn(BaseModel):
    client_id: str
    title: str = Field(min_length=1, max_length=200)
    booking_id: Optional[str] = None
    subscription_id: Optional[str] = None
    want_stream: bool = True
    want_storage: bool = True
    storage_filename: Optional[str] = None  # sets the reserved key's video extension
    content_type: str = "application/octet-stream"


@router.post("/api/uploads/prepare")
def prepare(body: PrepareIn, admin=Depends(_require_admin)):
    if not (body.want_stream or body.want_storage):
        raise HTTPException(422, "At least one of want_stream / want_storage must be true.")
    if not body.booking_id and not body.subscription_id:
        raise HTTPException(422, "Link the deliverable to a booking_id or subscription_id.")
    if body.want_storage and not body.storage_filename:
        raise HTTPException(422, "storage_filename is required when want_storage is true.")

    sb = _sb()
    upload_id = str(uuid.uuid4())
    row = {
        "client_id": body.client_id, "title": body.title, "status": "draft",
        "upload_id": upload_id, "bunny_linked_at": _now_iso(),
    }
    if body.booking_id:
        row["booking_id"] = body.booking_id
    if body.subscription_id:
        row["subscription_id"] = body.subscription_id

    resp = {"uploadId": upload_id, "libraryId": STREAM_LIB}

    # ---- Stream lane: create video object + 1h scoped TUS signature ----
    if body.want_stream:
        if not (STREAM_LIB and STREAM_KEY):
            raise HTTPException(503, "Bunny Stream not configured (BUNNY_STREAM_* env).")
        try:
            with httpx.Client(timeout=20) as c:
                r = c.post(
                    f"https://video.bunnycdn.com/library/{STREAM_LIB}/videos",
                    headers={"AccessKey": STREAM_KEY, "Content-Type": "application/json", "Accept": "application/json"},
                    json={"title": body.title},
                )
        except Exception as e:
            raise HTTPException(502, f"Bunny video create failed: {type(e).__name__}")
        if r.status_code >= 300:
            raise HTTPException(502, f"Bunny video create failed: HTTP {r.status_code}")
        guid = r.json()["guid"]
        expire = int(time.time()) + TUS_TTL
        sig = hashlib.sha256(f"{STREAM_LIB}{STREAM_KEY}{expire}{guid}".encode()).hexdigest()
        row["bunny_video_guid"] = guid
        row["stream_upload_state"] = "pending"
        resp["stream"] = {
            "endpoint": TUS_ENDPOINT, "videoId": guid, "signature": sig,
            "expires": expire, "expiresIn": TUS_TTL,
        }

    # ---- Storage lane: random single-use key + 15-min presigned PUT ----
    if body.want_storage:
        ext = _safe_video_ext(body.storage_filename)
        key = f"deliverables/{upload_id}{ext}"
        put_url = _s3().generate_presigned_url(
            "put_object",
            Params={"Bucket": STORAGE_ZONE, "Key": key, "ContentType": body.content_type},
            ExpiresIn=STORAGE_PUT_TTL, HttpMethod="PUT",
        )
        row["bunny_storage_object"] = key
        row["storage_upload_state"] = "pending"
        resp["storage"] = {
            "key": key, "putUrl": put_url, "expiresIn": STORAGE_PUT_TTL,
            "contentType": body.content_type,
        }

    created = sb.table("deliverables").insert(row).execute().data[0]
    resp["deliverableId"] = created["id"]
    return resp


# ---------------------------------------------------------------------------
# COMPLETE — independent backend verification per lane
# ---------------------------------------------------------------------------
class CompleteIn(BaseModel):
    upload_id: str
    kind: Literal["stream", "storage"]


def _set_state(sb, did, col, val):
    sb.table("deliverables").update({col: val}).eq("id", did).execute()


def _summary(d):
    lanes = {k: d.get(k) for k in ("stream_upload_state", "storage_upload_state") if d.get(k) is not None}
    return {
        "deliverableId": d["id"], "upload_id": d.get("upload_id"), "lanes": lanes,
        "all_confirmed": bool(lanes) and all(v == "confirmed" for v in lanes.values()),
    }


@router.post("/api/uploads/complete")
def complete(body: CompleteIn, admin=Depends(_require_admin)):
    sb = _sb()
    rows = sb.table("deliverables").select("*").eq("upload_id", body.upload_id).execute().data
    if not rows:
        raise HTTPException(404, "unknown upload_id")
    d = rows[0]

    if body.kind == "stream":
        col = "stream_upload_state"
        if d.get(col) == "confirmed":
            return _summary(d)  # idempotent
        guid = d.get("bunny_video_guid")
        if not guid:
            raise HTTPException(409, "no stream target on this upload")
        from bunny_reconcile import _poll_bunny_status
        res = _poll_bunny_status(guid)
        if not res["ok"]:
            _set_state(sb, d["id"], col, "failed")
            raise HTTPException(502, f"stream verify failed: {res['reason']}")
        if res["status_name"] in ("Failed", "PresignedUploadFailed"):
            _set_state(sb, d["id"], col, "failed")
            raise HTTPException(422, "Bunny reports the stream encode Failed")
        _set_state(sb, d["id"], col, "confirmed")  # exists + not failed (encode may still run)
    else:
        col = "storage_upload_state"
        if d.get(col) == "confirmed":
            return _summary(d)
        key = d.get("bunny_storage_object")
        if not key:
            raise HTTPException(409, "no storage target on this upload")
        try:
            head = _s3().head_object(Bucket=STORAGE_ZONE, Key=key)
        except Exception:
            _set_state(sb, d["id"], col, "failed")
            raise HTTPException(502, "storage verify failed: object not found")
        if head.get("ContentLength", 0) <= 0:
            _set_state(sb, d["id"], col, "failed")
            raise HTTPException(422, "storage object is empty")
        _set_state(sb, d["id"], col, "confirmed")

    fresh = sb.table("deliverables").select("*").eq("id", d["id"]).execute().data[0]
    return _summary(fresh)
