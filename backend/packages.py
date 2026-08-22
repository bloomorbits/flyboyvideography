"""Server-side pricing source of truth for booking checkout.

Two modes controlled by the PRICING_SOURCE env var:
  - "code" (default) → the hardcoded PACKAGES list below. Byte-identical to
    /app/website/lib/pricing.js as of Migration 013 cut-over. This is the
    original behaviour; keeps working with zero DB dependency.
  - "db"             → read the 'published' row from Supabase's
    pricing_catalog table (Migration 013). Cached in-process for
    PRICING_CACHE_TTL_SECONDS (default 60) so we don't hammer Supabase on
    every checkout.

The public API of this module — `find_package`, `find_tier`, `deposit_gbp`,
`DEPOSIT_PERCENTAGE` — is IDENTICAL in both modes. booking.py does not
change; it just gets fresher prices when PRICING_SOURCE=db.

Safety net: any failure reading from the DB (network, missing row,
malformed content) falls back to the hardcoded PACKAGES list and logs a
WARN. Booking checkout NEVER breaks because the DB is down.

No prices are ever accepted from the frontend — the backend computes the
deposit from this module using (package_id, tier_name) so a tampered
client cannot pay £1 for a £700 wedding shoot.

Deposit rule (per public site's booking terms): 50% of the tier price.
Balance rule: due 3 days before the event.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from typing import Optional, TypedDict

log = logging.getLogger(__name__)

DEPOSIT_PERCENTAGE = 0.50

PRICING_SOURCE = os.environ.get("PRICING_SOURCE", "code").lower()
PRICING_CACHE_TTL_SECONDS = int(os.environ.get("PRICING_CACHE_TTL_SECONDS", "60"))


class Tier(TypedDict, total=False):
    name: str          # "Basic" | "Classic" | "Royale" | "" (single-tier)
    price: float       # full package price in GBP
    coverage: str


class Package(TypedDict, total=False):
    id: str
    title: str
    tiers: list[Tier]


# ------------------------------------------------------------------------
# Hardcoded fallback / default source. Kept identical to
# /app/website/lib/pricing.js. Descriptive fields (features/leadIn/popular)
# are omitted here — the backend only needs (id, title, tier name, tier
# price, tier coverage) for pricing + email composition.
# ------------------------------------------------------------------------
PACKAGES: list[Package] = [
    {
        "id": "wedding",
        "title": "Wedding Videography",
        "tiers": [
            {"name": "Basic",   "price": 250.0, "coverage": "3 hours coverage"},
            {"name": "Classic", "price": 400.0, "coverage": "6 hours coverage"},
            {"name": "Royale",  "price": 700.0, "coverage": "Full-day coverage (10–12 hours)"},
        ],
    },
    {
        "id": "birthday",
        "title": "Birthday Celebration",
        "tiers": [
            {"name": "Basic",   "price": 250.0, "coverage": "3 hours coverage"},
            {"name": "Classic", "price": 400.0, "coverage": "6 hours coverage"},
            {"name": "Royale",  "price": 700.0, "coverage": "Full-day coverage (10–12 hours)"},
        ],
    },
    {
        "id": "naming-ceremony",
        "title": "Naming Ceremony & Gender Reveal",
        "tiers": [
            {"name": "Basic",   "price": 200.0, "coverage": "2 hours coverage"},
            {"name": "Classic", "price": 300.0, "coverage": "4 hours coverage"},
            {"name": "Royale",  "price": 450.0, "coverage": "6 hours coverage"},
        ],
    },
    {
        "id": "lifestyle",
        "title": "Lifestyle Shoot",
        "tiers": [
            {"name": "Basic",   "price": 200.0, "coverage": "2 hours coverage"},
            {"name": "Classic", "price": 300.0, "coverage": "4 hours coverage"},
            {"name": "Royale",  "price": 450.0, "coverage": "6 hours coverage"},
        ],
    },
    # Graduation is a single-tier package. Modelled as one tier with name=""
    # so the same (package_id, tier_name) contract works for single- and
    # multi-tier packages without special-casing the frontend.
    {
        "id": "graduation",
        "title": "Graduation Reels",
        "tiers": [
            {"name": "",  "price": 150.0, "coverage": "1.5 hours coverage"},
        ],
    },
]


# ------------------------------------------------------------------------
# DB path — cached loader for the published pricing_catalog row.
# ------------------------------------------------------------------------

# Module-level cache. Simple TTL, protected by a lock so we don't
# thundering-herd Supabase when the cache is cold.
_cache_lock = threading.Lock()
_cache_packages: Optional[list[Package]] = None
_cache_loaded_at: float = 0.0


def _catalog_to_package_list(content: dict) -> list[Package]:
    """Fold the published-catalog JSON (packages[] + graduation object) into
    the flat list of Package dicts this module has always returned. The
    graduation object gets normalised to a package-with-one-empty-tier so
    booking.py's `find_tier(package_id, tier_name="")` still works.
    """
    out: list[Package] = []
    for p in content.get("packages", []) or []:
        tiers_out: list[Tier] = []
        for t in p.get("tiers", []) or []:
            # Coerce price to float here (catalog stores 250 as JSON number;
            # older seeded rows might have int, we want float for consistent
            # Stripe rounding downstream).
            tiers_out.append({
                "name": str(t.get("name", "")),
                "price": float(t.get("price", 0)),
                "coverage": str(t.get("coverage", "")),
            })
        out.append({
            "id": str(p["id"]),
            "title": str(p["title"]),
            "tiers": tiers_out,
        })

    g = content.get("graduation")
    if isinstance(g, dict) and g.get("id"):
        out.append({
            "id": str(g["id"]),
            "title": str(g.get("title", "Graduation Reels")),
            "tiers": [{
                "name": "",
                "price": float(g.get("price", 0)),
                "coverage": str(g.get("coverage", "")),
            }],
        })
    return out


def _load_from_db_uncached() -> list[Package]:
    """One-shot Supabase read of the 'published' pricing catalog. Raises
    on failure — the caller wraps to fall back to hardcoded PACKAGES."""
    # Local import so the module has zero DB dependency in code-only mode.
    from supabase import create_client
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    sb = create_client(url, key)
    rows = (
        sb.table("pricing_catalog")
        .select("content")
        .eq("slot", "published")
        .limit(1)
        .execute()
        .data
    )
    if not rows:
        raise RuntimeError("pricing_catalog has no 'published' row")
    return _catalog_to_package_list(rows[0]["content"])


def _get_packages() -> list[Package]:
    """Return the effective package list based on PRICING_SOURCE + cache."""
    if PRICING_SOURCE != "db":
        return PACKAGES

    global _cache_packages, _cache_loaded_at
    now = time.monotonic()

    if _cache_packages is not None and (now - _cache_loaded_at) < PRICING_CACHE_TTL_SECONDS:
        return _cache_packages

    with _cache_lock:
        # Re-check inside the lock — another thread may have refreshed.
        now = time.monotonic()
        if _cache_packages is not None and (now - _cache_loaded_at) < PRICING_CACHE_TTL_SECONDS:
            return _cache_packages
        try:
            _cache_packages = _load_from_db_uncached()
            _cache_loaded_at = now
            return _cache_packages
        except Exception as e:
            # Safety net: never break checkout because of a Supabase blip.
            # Fall back to hardcoded, keep the (possibly stale) cache we had
            # if any, and log LOUDLY so we notice.
            log.warning("pricing_catalog DB read failed, falling back to hardcoded PACKAGES: %s", e)
            if _cache_packages is not None:
                return _cache_packages
            return PACKAGES


def invalidate_cache() -> None:
    """Drop the in-process cache. Called from the admin publish endpoint so
    a fresh publish takes effect immediately instead of waiting up to
    PRICING_CACHE_TTL_SECONDS."""
    global _cache_packages, _cache_loaded_at
    with _cache_lock:
        _cache_packages = None
        _cache_loaded_at = 0.0


# ------------------------------------------------------------------------
# Public API — unchanged signatures; booking.py imports these.
# ------------------------------------------------------------------------

def find_package(package_id: str) -> Optional[Package]:
    return next((p for p in _get_packages() if p["id"] == package_id), None)


def find_tier(package_id: str, tier_name: str) -> tuple[Optional[Package], Optional[Tier]]:
    """Look up (package, tier) by id + tier name. For single-tier packages,
    pass tier_name="" (matches the empty-name convention above)."""
    pkg = find_package(package_id)
    if pkg is None:
        return None, None
    tier = next((t for t in pkg["tiers"] if t["name"] == tier_name), None)
    return pkg, tier


def deposit_gbp(full_price: float) -> float:
    """50% deposit, rounded to 2dp so Stripe amounts don't drift on floats."""
    return round(full_price * DEPOSIT_PERCENTAGE, 2)
