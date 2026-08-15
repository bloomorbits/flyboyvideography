"""Server-side mirror of /app/website/lib/pricing.js.

MUST match the public site's pricing 1:1. If you change one, change the other.
No prices are ever accepted from the frontend — the backend computes the deposit
from this module using (package_id, tier_name) so a tampered client cannot pay
£1 for a £700 wedding shoot.

Deposit rule (per public site's booking terms): 50% of the tier price.
Balance rule: due 3 days before the event.
"""
from __future__ import annotations

from typing import Optional, TypedDict

DEPOSIT_PERCENTAGE = 0.50


class Tier(TypedDict):
    name: str          # "Basic" | "Classic" | "Royale"
    price: float       # full package price in GBP
    coverage: str


class Package(TypedDict):
    id: str
    title: str
    tiers: list[Tier]


# Kept identical to /app/website/lib/pricing.js. Descriptive fields
# (features/leadIn/popular) are omitted here — the backend only cares
# about (id, title, tier name, tier price, tier coverage) for pricing +
# email composition.
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
    # Graduation is a single-tier package. We model it as a package with one
    # tier named "" so the same (package_id, tier_name) contract works for
    # single- and multi-tier packages without special-casing the frontend.
    {
        "id": "graduation",
        "title": "Graduation Reels",
        "tiers": [
            {"name": "",  "price": 150.0, "coverage": "1.5 hours coverage"},
        ],
    },
]


def find_package(package_id: str) -> Optional[Package]:
    return next((p for p in PACKAGES if p["id"] == package_id), None)


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
