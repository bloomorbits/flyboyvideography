"""Admin-editable global site settings (Migration 019).

Homepage hero video settings:
  - a QUEUE of YouTube video ids (the homepage rotates through them per visit)
  - an optional poster image URL (shown instantly while the embed buffers)

Public:
  GET  /api/site-settings/hero-video
       → { youtube_video_ids: [...], poster_url: str|None, updated_at }
         (falls back to the default queue if the table/row is absent — the site
         never breaks on a missing setting; reads both the new list shape and
         the legacy single-id shape)
Admin (require_admin):
  PUT  /api/admin/site-settings/hero-video
       body { youtubes: [str, ...], poster_url: str|None }
       → each URL/id normalized to an 11-char id (422 on garbage), de-duped,
         order preserved; at least one required. poster_url must be http(s).

The Next.js homepage reads the public endpoint with ISR (60s), so admin edits
are live within a minute without a code deploy.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from portfolio import _normalize_youtube_id  # reuse the exact same parser/guard
from pricing import _require_admin  # reuse the exact same admin gate

log = logging.getLogger(__name__)
router = APIRouter()

# Owner-supplied default (https://youtu.be/MVE91GRuDVs).
DEFAULT_HERO_VIDEO_IDS = ["MVE91GRuDVs"]


def _sb():
    from server import get_sb  # lazy — avoids circular import
    return get_sb()


def _get_setting(key: str):
    rows = _sb().table("site_settings").select("*").eq("key", key).limit(1).execute().data
    return rows[0] if rows else None


def _hero_from_value(value: dict):
    """Read both the new list shape and the legacy single-id shape."""
    value = value or {}
    ids = value.get("youtube_video_ids")
    if not ids:
        legacy = value.get("youtube_video_id")
        ids = [legacy] if legacy else []
    ids = [i for i in ids if i]
    if not ids:
        ids = list(DEFAULT_HERO_VIDEO_IDS)
    return ids, (value.get("poster_url") or None)


@router.get("/api/site-settings/hero-video")
def get_hero_video():
    try:
        row = _get_setting("hero_video")
    except Exception as e:
        log.warning("hero-video read fell back to default: %s", e)
        row = None
    if not row:
        return {"youtube_video_ids": list(DEFAULT_HERO_VIDEO_IDS), "poster_url": None, "updated_at": None}
    ids, poster = _hero_from_value(row.get("value") or {})
    return {"youtube_video_ids": ids, "poster_url": poster, "updated_at": row.get("updated_at")}


class HeroVideoIn(BaseModel):
    youtubes: List[str]
    poster_url: Optional[str] = None


@router.put("/api/admin/site-settings/hero-video")
def put_hero_video(body: HeroVideoIn, admin=Depends(_require_admin)):
    ids: List[str] = []
    for raw in body.youtubes:
        if not raw or not raw.strip():
            continue
        vid = _normalize_youtube_id(raw.strip())  # 422 on bad input
        if vid not in ids:
            ids.append(vid)
    if not ids:
        raise HTTPException(422, "Add at least one valid YouTube URL or video ID")

    poster = (body.poster_url or "").strip() or None
    if poster and not poster.startswith(("http://", "https://")):
        raise HTTPException(422, "Poster URL must start with http:// or https://")

    try:
        _sb().table("site_settings").upsert(
            {
                "key": "hero_video",
                "value": {"youtube_video_ids": ids, "poster_url": poster},
                "updated_by": admin.get("user_id"),
            },
            on_conflict="key",
        ).execute()
    except Exception as e:
        raise HTTPException(500, f"hero video save failed: {e}")
    return {"ok": True, "youtube_video_ids": ids, "poster_url": poster}
