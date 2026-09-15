"""Admin-editable YouTube portfolio — endpoints + server-side validation.

Public:
  GET  /api/portfolio                 → active videos (Next.js /portfolio, 60s ISR)

Admin (require_admin):
  GET    /api/admin/portfolio         → all rows (active + inactive) + category list
  POST   /api/admin/portfolio         → create (normalize URL→id, 422 on bad id;
                                         oEmbed auto-fills real title + thumbnail)
  PATCH  /api/admin/portfolio/{id}    → partial update (re-oEmbeds if id changes)
  DELETE /api/admin/portfolio/{id}    → remove

DESIGN: direct-edit (row-per-video + is_active), no draft/publish — portfolio is
presentational, has no downstream refs, and is instantly reversible. See
Migration 016 header for the full reasoning.

VALIDATION (server-enforced, mirrors the Bunny extension guard): a pasted URL is
normalized to the canonical 11-char id; anything that isn't a real YouTube id/URL
is rejected with 422 BEFORE the DB (which also has a CHECK as defense-in-depth).
oEmbed (no API key) verifies the video is real + embeddable and yields its real
title + thumbnail; an unavailable/private/embedding-disabled video is rejected.
"""
from __future__ import annotations

import logging
import re
import urllib.parse
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

log = logging.getLogger(__name__)
router = APIRouter()

# The 5 real site categories (ids match website/lib/portfolio.js + Migration 016).
CATEGORY_LABELS = {
    "weddings": "Weddings",
    "birthdays": "Birthday Celebrations",
    "naming": "Naming Ceremony & Gender Reveal",
    "lifestyle": "Lifestyle Reels",
    "corporate": "Corporate/Brand",
}
CATEGORIES = list(CATEGORY_LABELS.keys())

_YT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YT_URL_RE = re.compile(r"(?:youtu\.be/|/shorts/|/embed/|/v/|/live/)([A-Za-z0-9_-]{11})")


# ============================================================================
# Helpers
# ============================================================================

def _sb():
    from server import get_sb  # lazy — avoids circular import
    return get_sb()


_bearer = HTTPBearer(auto_error=False)


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


def _normalize_youtube_id(raw: str) -> str:
    """Accept a bare 11-char id OR any common YouTube URL; return the id.
    422 on anything else — the same server-enforced discipline as the Bunny
    video-extension guardrail (no trusting the client)."""
    raw = (raw or "").strip()
    if not raw:
        raise HTTPException(422, "A YouTube video ID or URL is required.")
    if _YT_ID_RE.match(raw):
        return raw
    m = _YT_URL_RE.search(raw)
    if m:
        return m.group(1)
    try:
        parsed = urllib.parse.urlparse(raw)
        v = urllib.parse.parse_qs(parsed.query).get("v", [None])[0]
        if v and _YT_ID_RE.match(v):
            return v
    except Exception:
        pass
    raise HTTPException(
        422,
        "That doesn't look like a YouTube video. Paste a full watch/share/shorts "
        "URL or the 11-character video ID (letters, digits, - and _).",
    )


def _fetch_oembed(video_id: str) -> dict:
    """No-key oEmbed lookup — verifies the video is real + embeddable and
    returns its REAL title + thumbnail. Rejects unavailable/private videos so
    a broken tile never reaches the public site."""
    url = ("https://www.youtube.com/oembed?url="
           + urllib.parse.quote(f"https://www.youtube.com/watch?v={video_id}", safe="")
           + "&format=json")
    try:
        r = httpx.get(url, timeout=10.0, follow_redirects=True)
    except Exception as e:
        raise HTTPException(502, f"Could not reach YouTube to verify the video: {e}")
    if r.status_code in (401, 403, 404):
        raise HTTPException(
            422,
            "YouTube reports this video is unavailable or not embeddable "
            "(private, deleted, or embedding disabled). Use a public, embeddable video.",
        )
    if r.status_code != 200:
        raise HTTPException(422, f"YouTube couldn't verify this video (oEmbed {r.status_code}).")
    data = r.json()
    return {"title": data.get("title"), "thumbnail_url": data.get("thumbnail_url")}


def _table_missing(e: Exception) -> bool:
    msg = str(e).lower()
    return "pgrst205" in msg or "does not exist" in msg or "schema cache" in msg


# ============================================================================
# Request models
# ============================================================================

class PortfolioCreate(BaseModel):
    category: str
    youtube: str                       # 11-char id OR any YouTube URL
    title: Optional[str] = None        # override; otherwise oEmbed title is used
    description: Optional[str] = None
    display_order: Optional[int] = 0
    is_active: Optional[bool] = True
    model_config = ConfigDict(extra="forbid")


class PortfolioPatch(BaseModel):
    category: Optional[str] = None
    youtube: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None
    model_config = ConfigDict(extra="forbid")


# ============================================================================
# Public endpoint
# ============================================================================

@router.get("/api/portfolio")
def get_public_portfolio():
    """Active videos, ordered per category. Fetched by Next.js /portfolio with
    60s ISR. Table-missing degrades gracefully to empty (site falls back to the
    honest per-category placeholder treatment)."""
    try:
        rows = (
            _sb().table("portfolio_videos")
            .select("id,category,youtube_video_id,title,description,thumbnail_url,duration_seconds,upload_date,display_order")
            .eq("is_active", True)
            .order("category").order("display_order").order("created_at")
            .execute().data or []
        )
    except Exception as e:
        if _table_missing(e):
            log.warning("portfolio_videos table missing — returning empty (apply Migration 016)")
            return {"videos": [], "categories": CATEGORY_LABELS}
        raise HTTPException(500, f"portfolio read failed: {e}")
    return {"videos": rows, "categories": CATEGORY_LABELS}


# ============================================================================
# Admin endpoints
# ============================================================================

@router.get("/api/admin/portfolio")
def admin_list(admin=Depends(_require_admin)):
    try:
        rows = (
            _sb().table("portfolio_videos").select("*")
            .order("category").order("display_order").order("created_at")
            .execute().data or []
        )
    except Exception as e:
        if _table_missing(e):
            raise HTTPException(503, "portfolio_videos table not present — apply Migration 016 first.")
        raise HTTPException(500, f"portfolio read failed: {e}")
    return {"videos": rows, "categories": CATEGORY_LABELS}


@router.post("/api/admin/portfolio")
def admin_create(body: PortfolioCreate, admin=Depends(_require_admin)):
    if body.category not in CATEGORIES:
        raise HTTPException(422, f"Unknown category {body.category!r}. Must be one of {CATEGORIES}.")
    vid = _normalize_youtube_id(body.youtube)
    meta = _fetch_oembed(vid)
    row = {
        "category": body.category,
        "youtube_video_id": vid,
        "title": (body.title or meta.get("title") or "Untitled").strip()[:300],
        "description": body.description,
        "thumbnail_url": meta.get("thumbnail_url"),
        "display_order": body.display_order or 0,
        "is_active": True if body.is_active is None else body.is_active,
    }
    try:
        created = _sb().table("portfolio_videos").insert(row).execute().data
    except Exception as e:
        if _table_missing(e):
            raise HTTPException(503, "portfolio_videos table not present — apply Migration 016 first.")
        raise HTTPException(422, f"Could not save video: {e}")
    return created[0]


@router.patch("/api/admin/portfolio/{video_id}")
def admin_update(video_id: str, body: PortfolioPatch, admin=Depends(_require_admin)):
    updates: dict = {}
    if body.category is not None:
        if body.category not in CATEGORIES:
            raise HTTPException(422, f"Unknown category {body.category!r}.")
        updates["category"] = body.category
    if body.youtube is not None:
        new_id = _normalize_youtube_id(body.youtube)
        meta = _fetch_oembed(new_id)
        updates["youtube_video_id"] = new_id
        updates["thumbnail_url"] = meta.get("thumbnail_url")
        if body.title is None:  # refresh title from the new video unless overridden
            updates["title"] = (meta.get("title") or "Untitled").strip()[:300]
    if body.title is not None:
        updates["title"] = body.title.strip()[:300]
    if body.description is not None:
        updates["description"] = body.description
    if body.display_order is not None:
        updates["display_order"] = body.display_order
    if body.is_active is not None:
        updates["is_active"] = body.is_active
    if not updates:
        raise HTTPException(400, "No fields to update.")
    try:
        res = _sb().table("portfolio_videos").update(updates).eq("id", video_id).execute().data
    except Exception as e:
        raise HTTPException(422, f"Could not update video: {e}")
    if not res:
        raise HTTPException(404, "Video not found.")
    return res[0]


@router.delete("/api/admin/portfolio/{video_id}")
def admin_delete(video_id: str, admin=Depends(_require_admin)):
    res = _sb().table("portfolio_videos").delete().eq("id", video_id).execute().data
    if not res:
        raise HTTPException(404, "Video not found.")
    return {"ok": True, "deleted": video_id}
