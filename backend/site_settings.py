"""Admin-editable global site settings (Migration 019).

One setting so far: the homepage hero YouTube video.

Public:
  GET  /api/site-settings/hero-video          → { youtube_video_id, updated_at }
                                                 (falls back to the default id if
                                                 the table/row is absent — the
                                                 site never breaks on a missing
                                                 setting)
Admin (require_admin):
  PUT  /api/admin/site-settings/hero-video     body { youtube } → normalize the
                                                 pasted URL/id to an 11-char id
                                                 (422 on garbage) → upsert.

The Next.js homepage reads the public endpoint with ISR (60s), so an admin
edit is live within a minute without a code deploy.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from portfolio import _normalize_youtube_id  # reuse the exact same parser/guard
from pricing import _require_admin  # reuse the exact same admin gate

log = logging.getLogger(__name__)
router = APIRouter()

# Owner-supplied default (https://youtu.be/MVE91GRuDVs). Used as the honest
# fallback whenever the setting hasn't been stored yet.
DEFAULT_HERO_VIDEO_ID = "MVE91GRuDVs"


def _sb():
    from server import get_sb  # lazy — avoids circular import
    return get_sb()


def _get_setting(key: str):
    rows = _sb().table("site_settings").select("*").eq("key", key).limit(1).execute().data
    return rows[0] if rows else None


@router.get("/api/site-settings/hero-video")
def get_hero_video():
    try:
        row = _get_setting("hero_video")
    except Exception as e:
        # Table not applied yet / transient DB error — never break the site.
        log.warning("hero-video read fell back to default: %s", e)
        row = None
    if not row:
        return {"youtube_video_id": DEFAULT_HERO_VIDEO_ID, "updated_at": None}
    vid = (row.get("value") or {}).get("youtube_video_id") or DEFAULT_HERO_VIDEO_ID
    return {"youtube_video_id": vid, "updated_at": row.get("updated_at")}


class HeroVideoIn(BaseModel):
    youtube: str


@router.put("/api/admin/site-settings/hero-video")
def put_hero_video(body: HeroVideoIn, admin=Depends(_require_admin)):
    vid = _normalize_youtube_id(body.youtube)  # 422 on bad input
    try:
        _sb().table("site_settings").upsert(
            {
                "key": "hero_video",
                "value": {"youtube_video_id": vid},
                "updated_by": admin.get("user_id"),
            },
            on_conflict="key",
        ).execute()
    except Exception as e:
        raise HTTPException(500, f"hero video save failed: {e}")
    return {"ok": True, "youtube_video_id": vid}
