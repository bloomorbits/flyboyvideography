"""Admin-editable pricing catalog — endpoints + strict Pydantic validator +
referential-integrity guard.

Public:
  GET  /api/pricing                     → published catalog (Next.js fetches this)

Admin (require_admin):
  GET  /api/admin/pricing/draft         → { draft, published, dirty, updated_at… }
  PUT  /api/admin/pricing/draft         → replace draft wholesale
                                          422 on invalid shape (Pydantic)
  POST /api/admin/pricing/publish       → atomic swap: published := draft
                                          409 if the diff would orphan a
                                          live booking's (package_id, tier_name)
                                          reference (see _find_orphaned_refs)
  POST /api/admin/pricing/publish?force=1
                                          → override the orphan-block. LOGGED.
  POST /api/admin/pricing/revert        → discard-my-draft: draft := published

Shape enforcement is application-layer (see class Catalog). The DB layer
only enforces `slot IN ('draft','published')`. Every write path here
rejects malformed edits with HTTP 422 before touching the DB.

Referential integrity is application-layer too. The design pick from
session 15: any live booking (confirmed OR active booking_intent) that
references a (package_id, tier_name) being removed by this publish
BLOCKS the publish by default. `force=1` overrides for the case where
Nathan has already reconciled the bookings manually.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

import packages as pricing_source  # for cache invalidation on publish

log = logging.getLogger(__name__)
router = APIRouter()


# ============================================================================
# STRICT PYDANTIC SCHEMA — the write-path guard against malformed edits.
# ============================================================================

class Tier(BaseModel):
    """One tier within a package.

    - name: "" is allowed for single-tier packages (e.g. Graduation modeled
      as a package with one empty-named tier for booking-checkout parity)
    - price: real number, 0 ≤ p ≤ 100000 (upper bound is a fat-finger guard)
    - coverage: non-empty
    """
    name: str = Field(..., max_length=40)
    price: float = Field(..., ge=0, le=100000)
    coverage: str = Field(..., min_length=1, max_length=200)
    popular: Optional[bool] = None
    leadIn: Optional[str] = Field(None, max_length=200)
    features: Optional[list[str]] = None

    model_config = ConfigDict(extra="forbid")


class Package(BaseModel):
    id: str = Field(..., min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9-]*$")
    title: str = Field(..., min_length=1, max_length=100)
    hoursOnly: Optional[bool] = None
    tiers: list[Tier] = Field(..., min_length=1)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _tier_names_unique(self) -> "Package":
        seen: set[str] = set()
        for t in self.tiers:
            if t.name in seen:
                raise ValueError(f"tier name {t.name!r} duplicated in package {self.id!r}")
            seen.add(t.name)
        return self


class Graduation(BaseModel):
    id: str = Field(..., pattern=r"^[a-z][a-z0-9-]*$")
    title: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., ge=0, le=100000)
    coverage: str = Field(..., min_length=1, max_length=200)
    features: Optional[list[str]] = None

    model_config = ConfigDict(extra="forbid")


class ExtraItem(BaseModel):
    label: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., ge=0, le=100000)
    model_config = ConfigDict(extra="forbid")


class Extras(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)
    subtitle: str = Field(..., min_length=1, max_length=200)
    items: list[ExtraItem] = Field(..., min_length=1)
    model_config = ConfigDict(extra="forbid")


class Catalog(BaseModel):
    """Full pricing catalog — what lives inside pricing_catalog.content."""
    packages: list[Package] = Field(..., min_length=1)
    graduation: Graduation
    extras: Extras
    bookingTerms: str = Field(..., min_length=1, max_length=500)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _package_ids_unique(self) -> "Catalog":
        seen: set[str] = set()
        for p in self.packages:
            if p.id in seen:
                raise ValueError(f"package id {p.id!r} duplicated")
            seen.add(p.id)
        # graduation.id must not collide with a package.id — booking checkout
        # dispatches on (package_id, tier_name) so a collision is broken.
        if self.graduation.id in seen:
            raise ValueError(f"graduation.id {self.graduation.id!r} collides with a package.id")
        return self


# ============================================================================
# Helpers
# ============================================================================

def _sb():
    from server import get_sb  # lazy — avoids circular
    return get_sb()


def _get_slot(slot: str) -> dict:
    if slot not in ("draft", "published"):
        raise HTTPException(400, f"invalid slot {slot!r}")
    try:
        rows = (
            _sb().table("pricing_catalog")
            .select("content, updated_at, updated_by")
            .eq("slot", slot)
            .limit(1)
            .execute()
            .data
        )
    except Exception as e:
        msg = str(e).lower()
        if "pgrst205" in msg or "does not exist" in msg or "schema cache" in msg:
            raise HTTPException(503, "pricing_catalog table not present — apply Migration 013 first.")
        raise HTTPException(500, f"pricing read failed: {e}")
    if not rows:
        raise HTTPException(404, f"pricing_catalog slot={slot!r} not seeded — apply Migration 013 first.")
    return rows[0]


def _extract_tier_pairs(content: dict) -> set[tuple[str, str]]:
    """Every (package_id, tier_name) tuple that the catalog exposes,
    including graduation-as-package (tier_name='')."""
    out: set[tuple[str, str]] = set()
    for p in content.get("packages", []) or []:
        pid = p.get("id")
        if not pid:
            continue
        for t in p.get("tiers", []) or []:
            out.add((pid, str(t.get("name", ""))))
    g = content.get("graduation")
    if isinstance(g, dict) and g.get("id"):
        out.add((str(g["id"]), ""))
    return out


def _find_orphaned_refs(pub_content: dict, draft_content: dict) -> list[dict]:
    """Compute (package_id, tier_name) tuples present in the CURRENT
    published catalog but MISSING from the proposed draft — then check
    whether any live booking still references them.

    "Live booking" = any of:
      - bookings.status IN ('confirmed', 'completed') (regardless of date;
        even completed shoots may still be within the deliverable window)
      - booking_intents.status IN ('created', 'paid') where no cancellation
        followed (defensive — a paid intent without a confirmed booking
        indicates an in-flight checkout)

    Returns a list of orphan-report dicts, one per removed tuple that has
    live references. Empty list = safe to publish.
    """
    pub_pairs = _extract_tier_pairs(pub_content)
    draft_pairs = _extract_tier_pairs(draft_content)
    removed = pub_pairs - draft_pairs
    if not removed:
        return []

    sb = _sb()
    orphans: list[dict] = []

    for (pkg_id, tier_name) in sorted(removed):
        # 1. Confirmed bookings referencing this via their booking_intent.
        #    bookings.booking_intent_id → booking_intents.(package_id, tier_name)
        intents = (
            sb.table("booking_intents")
            .select("id")
            .eq("package_id", pkg_id)
            .eq("tier_name", tier_name)
            .execute()
            .data or []
        )
        intent_ids = [r["id"] for r in intents]

        live_bookings: list[str] = []
        if intent_ids:
            bkg = (
                sb.table("bookings")
                .select("id, status, event_date")
                .in_("booking_intent_id", intent_ids)
                .in_("status", ["confirmed", "completed"])
                .execute()
                .data or []
            )
            live_bookings = [r["id"] for r in bkg]

        # 2. Booking intents still in-flight (paid but no confirmed booking yet)
        live_intents = (
            sb.table("booking_intents")
            .select("id")
            .eq("package_id", pkg_id)
            .eq("tier_name", tier_name)
            .in_("status", ["paid"])
            .execute()
            .data or []
        )

        if live_bookings or live_intents:
            orphans.append({
                "package_id": pkg_id,
                "tier_name": tier_name,
                "confirmed_booking_count": len(live_bookings),
                "in_flight_intent_count": len(live_intents),
                "sample_booking_ids": live_bookings[:5],
                "sample_intent_ids": [r["id"] for r in live_intents[:5]],
            })

    return orphans


# ============================================================================
# require_admin — local copy to keep pricing.py cleanly decoupled from
# server.py's module-load order. Duplicated logic is 5 lines; the
# alternative (a shared auth_deps module) is a bigger refactor for the
# same behaviour.
# ============================================================================

from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

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


# ============================================================================
# Public endpoint
# ============================================================================

@router.get("/api/pricing")
def get_public_pricing():
    """Public read of the published catalog. Fetched by the Next.js
    /services page with ISR revalidate (60s)."""
    row = _get_slot("published")
    return {"content": row["content"], "updated_at": row.get("updated_at")}


# ============================================================================
# Admin endpoints
# ============================================================================

@router.get("/api/admin/pricing/draft")
def admin_get_draft(admin=Depends(_require_admin)):
    draft = _get_slot("draft")
    published = _get_slot("published")
    return {
        "draft": draft["content"],
        "published": published["content"],
        "draft_updated_at": draft.get("updated_at"),
        "published_updated_at": published.get("updated_at"),
        "dirty": draft["content"] != published["content"],
    }


@router.put("/api/admin/pricing/draft")
def admin_put_draft(catalog: Catalog, admin=Depends(_require_admin)):
    """Replace draft wholesale. Pydantic-validated on ingress; 422 on
    shape errors before any DB write."""
    payload = catalog.model_dump(exclude_none=True)
    try:
        _sb().table("pricing_catalog").update({
            "content": payload,
            "updated_by": admin.get("user_id"),
        }).eq("slot", "draft").execute()
    except Exception as e:
        raise HTTPException(500, f"draft write failed: {e}")
    dirty = _get_slot("draft")["content"] != _get_slot("published")["content"]
    return {"ok": True, "dirty": dirty}


@router.post("/api/admin/pricing/publish")
def admin_publish(force: int = 0, admin=Depends(_require_admin)):
    """Atomic-ish swap: published.content := draft.content.

    BLOCKS by default (409) if publishing would orphan a live booking's
    (package_id, tier_name) reference. Pass `?force=1` to override — LOGGED.
    """
    draft = _get_slot("draft")
    published = _get_slot("published")

    if draft["content"] == published["content"]:
        return {"ok": True, "note": "no changes to publish", "published_at": published.get("updated_at")}

    orphans = _find_orphaned_refs(published["content"], draft["content"])
    if orphans and not force:
        log.warning("publish BLOCKED — %d orphaned reference(s): %s", len(orphans), orphans)
        raise HTTPException(
            status_code=409,
            detail={
                "error": "publish_would_orphan_live_bookings",
                "message": (
                    "Publishing would remove a (package_id, tier_name) tuple still "
                    "referenced by live bookings. Reconcile the affected bookings "
                    "first, or POST ?force=1 to override."
                ),
                "orphaned_refs": orphans,
            },
        )

    if orphans and force:
        log.warning(
            "publish FORCE-OVERRIDE by admin=%s — orphaning %d live ref(s): %s",
            admin.get("user_id"), len(orphans), orphans,
        )

    try:
        _sb().table("pricing_catalog").update({
            "content": draft["content"],
            "updated_by": admin.get("user_id"),
        }).eq("slot", "published").execute()
    except Exception as e:
        raise HTTPException(500, f"publish failed: {e}")

    pricing_source.invalidate_cache()

    return {
        "ok": True,
        "published_at": _get_slot("published").get("updated_at"),
        "forced": bool(orphans and force),
    }


@router.post("/api/admin/pricing/revert")
def admin_revert(admin=Depends(_require_admin)):
    pub = _get_slot("published")
    try:
        _sb().table("pricing_catalog").update({
            "content": pub["content"],
            "updated_by": admin.get("user_id"),
        }).eq("slot", "draft").execute()
    except Exception as e:
        raise HTTPException(500, f"revert failed: {e}")
    return {"ok": True, "dirty": False}
