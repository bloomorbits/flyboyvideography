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

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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
