"""Admin-editable global site settings (Migration 019).

Homepage hero video settings:
  - a QUEUE of YouTube videos, each with a WEIGHT (favourites appear more often
    in the homepage rotation)
  - a poster image (uploaded by the admin, stored in Supabase Storage and
    served from there — no external URL to manage) shown instantly while the
    embed buffers

Public:
  GET  /api/site-settings/hero-video
       → { videos: [{id, weight}], youtube_video_ids: [...], poster_url, updated_at }
         (falls back to the default queue if the table/row is absent — the site
         never breaks; reads the list+weights shape and the legacy single-id shape)
Admin (require_admin):
  PUT  /api/admin/site-settings/hero-video
       body { videos: [{youtube, weight}], poster_url }
       → each URL/id normalized to an 11-char id (422 on garbage), de-duped,
         order preserved, weight clamped 1..10; at least one required.
  POST /api/admin/site-settings/hero-poster   (multipart file)
       → uploads an image to the public 'hero-posters' bucket, stores its URL
         on the hero_video setting, returns { poster_url }.

The Next.js homepage reads the public endpoint with ISR (60s), so admin edits
are live within a minute without a code deploy.
"""
from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from portfolio import _normalize_youtube_id  # reuse the exact same parser/guard
from pricing import _require_admin  # reuse the exact same admin gate

log = logging.getLogger(__name__)
router = APIRouter()

# Owner-supplied default (https://youtu.be/MVE91GRuDVs).
DEFAULT_HERO_VIDEO_IDS = ["MVE91GRuDVs"]

POSTER_BUCKET = "hero-posters"
MAX_POSTER_BYTES = 5 * 1024 * 1024  # 5 MB
_POSTER_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/avif": "avif",
}


def _sb():
    from server import get_sb  # lazy — avoids circular import
    return get_sb()


def _get_setting(key: str):
    rows = _sb().table("site_settings").select("*").eq("key", key).limit(1).execute().data
    return rows[0] if rows else None


def _clamp_weight(w) -> int:
    try:
        w = int(w)
    except Exception:
        w = 1
    return max(1, min(10, w))


def _hero_from_value(value: dict):
    """Read the new list+weights shape and the legacy single-id shape."""
    value = value or {}
    ids = value.get("youtube_video_ids")
    if not ids:
        legacy = value.get("youtube_video_id")
        ids = [legacy] if legacy else []
    ids = [i for i in ids if i]
    if not ids:
        ids = list(DEFAULT_HERO_VIDEO_IDS)
    weights = value.get("weights") or []
    videos = []
    for i, vid in enumerate(ids):
        w = _clamp_weight(weights[i]) if i < len(weights) else 1
        videos.append({"id": vid, "weight": w})
    return videos, (value.get("poster_url") or None)


def _hero_response(row):
    if not row:
        return {
            "videos": [{"id": i, "weight": 1} for i in DEFAULT_HERO_VIDEO_IDS],
            "youtube_video_ids": list(DEFAULT_HERO_VIDEO_IDS),
            "poster_url": None,
            "updated_at": None,
        }
    videos, poster = _hero_from_value(row.get("value") or {})
    return {
        "videos": videos,
        "youtube_video_ids": [v["id"] for v in videos],
        "poster_url": poster,
        "updated_at": row.get("updated_at"),
    }


@router.get("/api/site-settings/hero-video")
def get_hero_video():
    try:
        row = _get_setting("hero_video")
    except Exception as e:
        log.warning("hero-video read fell back to default: %s", e)
        row = None
    return _hero_response(row)


class HeroVideoItem(BaseModel):
    youtube: str
    weight: int = 1


class HeroVideoIn(BaseModel):
    videos: List[HeroVideoItem]
    poster_url: Optional[str] = None


def _normalize_videos(items: List[HeroVideoItem]):
    ids: List[str] = []
    weights: List[int] = []
    for item in items:
        if not item.youtube or not item.youtube.strip():
            continue
        vid = _normalize_youtube_id(item.youtube.strip())  # 422 on bad input
        if vid in ids:
            continue
        ids.append(vid)
        weights.append(_clamp_weight(item.weight))
    if not ids:
        raise HTTPException(422, "Add at least one valid YouTube URL or video ID")
    return ids, weights


def _validate_poster(poster_url: Optional[str]) -> Optional[str]:
    poster = (poster_url or "").strip() or None
    if poster and not poster.startswith(("http://", "https://")):
        raise HTTPException(422, "Poster URL must start with http:// or https://")
    return poster


@router.put("/api/admin/site-settings/hero-video")
def put_hero_video(body: HeroVideoIn, admin=Depends(_require_admin)):
    ids, weights = _normalize_videos(body.videos)
    poster = _validate_poster(body.poster_url)
    try:
        _sb().table("site_settings").upsert(
            {
                "key": "hero_video",
                "value": {"youtube_video_ids": ids, "weights": weights, "poster_url": poster},
                "updated_by": admin.get("user_id"),
            },
            on_conflict="key",
        ).execute()
    except Exception as e:
        raise HTTPException(500, f"hero video save failed: {e}")
    return {"ok": True, "videos": [{"id": i, "weight": w} for i, w in zip(ids, weights)], "poster_url": poster}


def _ensure_poster_bucket():
    try:
        _sb().storage.create_bucket(POSTER_BUCKET, options={"public": True})
    except Exception:
        pass  # already exists — create is idempotent for our purposes


@router.post("/api/admin/site-settings/hero-poster")
async def upload_hero_poster(file: UploadFile = File(...), admin=Depends(_require_admin)):
    ct = (file.content_type or "").lower()
    if ct not in _POSTER_EXT:
        raise HTTPException(422, "Poster must be a JPEG, PNG, WebP, GIF or AVIF image")
    data = await file.read()
    if not data:
        raise HTTPException(422, "Empty file")
    if len(data) > MAX_POSTER_BYTES:
        raise HTTPException(422, "Poster must be 5MB or smaller")

    key = f"hero/{uuid.uuid4().hex}.{_POSTER_EXT[ct]}"
    _ensure_poster_bucket()
    try:
        _sb().storage.from_(POSTER_BUCKET).upload(
            key, data, {"content-type": ct, "upsert": "true"}
        )
        url = _sb().storage.from_(POSTER_BUCKET).get_public_url(key).rstrip("?")
    except Exception as e:
        raise HTTPException(500, f"poster upload failed: {e}")

    # Persist onto the hero_video setting so it's live immediately.
    try:
        row = _get_setting("hero_video")
        value = (row.get("value") if row else {}) or {}
        value["poster_url"] = url
        _sb().table("site_settings").upsert(
            {"key": "hero_video", "value": value, "updated_by": admin.get("user_id")},
            on_conflict="key",
        ).execute()
    except Exception as e:
        log.warning("poster uploaded but hero_video merge failed: %s", e)

    return {"ok": True, "poster_url": url}
