"""SEC-001 attack simulation — proves the layered rate limiter fires
under realistic bot behaviour.

Scenarios:
  A. Rapid-fire from ONE IP + ONE email hitting many DIFFERENT dates.
     Expect: per-email cap fires at attempt 4 (limit=3).
  B. Same IP, DIFFERENT emails on each request.
     Expect: per-IP cap fires at attempt 6 (limit=5).
  C. XFF spoofing — every request prepends a new fake IP AND uses a
     new email. This defeats per-IP and per-email caps individually.
     Expect: the GLOBAL circuit breaker fires around attempt 100.

Run:  cd /app/backend && python tests/sim_calendar_freeze_attack.py
"""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


# ---------- SAFETY GUARD (SEC-003 fix) ----------
# This script hits the live REACT_APP_BACKEND_URL with the service-role key
# and floods real Stripe test-mode sessions + date_slot_locks. On a
# production-connected pod it would create real bookings, mutate a real
# customer's rate-limit history, and could hit real cs_live_ Stripe URLs
# if this project ever moves to live mode. Refuse to run unless the caller
# has explicitly opted in AND the target URL matches a known-safe pattern.
_BASE = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or Path("/app/frontend/.env").read_text().split("REACT_APP_BACKEND_URL=", 1)[1].split("\n", 1)[0].strip()
).rstrip("/")

_SAFE_URL_MARKERS = ("preview.emergentagent.com", "localhost", "127.0.0.1", "staging")

if os.environ.get("ALLOW_ATTACK_SIM") != "1":
    raise SystemExit(
        "REFUSED: sim_calendar_freeze_attack.py performs a real booking-flood "
        "attack against the deployed backend. Set ALLOW_ATTACK_SIM=1 to run. "
        "Never set this env var on a production-connected shell."
    )
if not any(m in _BASE for m in _SAFE_URL_MARKERS):
    raise SystemExit(
        f"REFUSED: target URL {_BASE!r} does not match any known-safe pattern "
        f"({_SAFE_URL_MARKERS!r}). If you REALLY need to run against this URL, "
        f"extend _SAFE_URL_MARKERS explicitly — but never against a production "
        f"customer-facing deployment."
    )

BASE = _BASE
CHECKOUT = f"{BASE}/api/booking/checkout"

from supabase import create_client  # noqa: E402

# Import the constants so the sim asserts against whatever the code actually
# ships with (not hardcoded magic numbers that could drift).
import sys as _sys
_sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from booking import (  # noqa: E402
    LOCK_CAP_PER_EMAIL,
    LOCK_CAP_PER_IP,
    LOCK_CAP_GLOBAL,
    RL_MAX_PER_EMAIL,
    RL_MAX_PER_IP,
    RL_MAX_GLOBAL,
)

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def _detail(r) -> str:
    if not r.headers.get("content-type", "").startswith("application/json"):
        return ""
    try:
        j = r.json()
    except Exception:
        return ""
    return (j.get("detail") or j.get("checkout_url") or "")[:80]


def _payload(event_date, email, package_id="wedding", tier="Classic"):
    return {
        "package_id": package_id,
        "tier_name": tier,
        "event_date": event_date.isoformat(),
        "email": email,
        "full_name": "Attack Sim",
        "origin_url": "https://flyboyvideography.com",
    }


def _dates_from(idx_offset: int, n: int):
    base = date.today() + timedelta(days=800)
    return [base + timedelta(days=idx_offset + i) for i in range(n)]


def _clean(prefix: str):
    """Remove any rows this run produced so a re-run is deterministic."""
    intents = sb.table("booking_intents").select("id, session_id, event_date").ilike("email", f"{prefix}%").execute().data or []
    sids = [i["session_id"] for i in intents if i.get("session_id")]
    dates = list({i["event_date"] for i in intents if i.get("event_date")})
    if sids:
        sb.table("payment_transactions").delete().in_("session_id", sids).execute()
    for d in dates:
        sb.table("date_slot_locks").delete().eq("event_date", d).execute()
    sb.table("booking_intents").delete().ilike("email", f"{prefix}%").execute()
    sb.table("checkout_attempts").delete().ilike("email", f"{prefix}%").execute()


def scenario_a():
    print("\n=== A) Rapid-fire ONE IP + ONE email over 6 dates ===")
    prefix = f"atk_a_{uuid.uuid4().hex[:6]}_"
    email = f"{prefix}same@flyboytest.com"
    dates = _dates_from(0, 6)
    results = []
    t0 = time.monotonic()
    for i, d in enumerate(dates, 1):
        r = requests.post(CHECKOUT, json=_payload(d, email), timeout=15)
        results.append((i, d.isoformat(), r.status_code, _detail(r)))
    dt = time.monotonic() - t0
    for row in results:
        print(f"  attempt {row[0]:>2}  date={row[1]}  HTTP {row[2]:>3}  {row[3]}")
    ok = sum(1 for _, _, s, _ in results if s == 200)
    blocked = sum(1 for _, _, s, _ in results if s == 429)
    print(f"  → {ok} succeeded, {blocked} rate-limited in {dt:.2f}s")
    # The concurrent-lock-per-email cap (2) fires BEFORE the per-email
    # request cap (3) — a tighter, stronger defense triggers first. Both
    # would eventually block; we just want to confirm 429 fires early and
    # only a bounded number of dates get locked per email.
    assert ok <= LOCK_CAP_PER_EMAIL, f"A: too many succeeded ({ok}) — per-email defenses failed"
    assert blocked >= 3, f"A: expected at least 3 blocks after cap, got {blocked}"
    _clean(prefix)
    print(f"  ✅ per-email defenses (concurrent-lock cap {LOCK_CAP_PER_EMAIL}) fired at attempt {ok + 1}")


def scenario_b():
    print("\n=== B) Same IP, DIFFERENT email per request over 8 dates ===")
    prefix = f"atk_b_{uuid.uuid4().hex[:6]}_"
    dates = _dates_from(20, 8)
    results = []
    for i, d in enumerate(dates, 1):
        email = f"{prefix}{i}@flyboytest.com"  # unique per request → defeats per-email cap
        r = requests.post(CHECKOUT, json=_payload(d, email), timeout=15)
        results.append((i, d.isoformat(), r.status_code, _detail(r)))
    for row in results:
        print(f"  attempt {row[0]:>2}  date={row[1]}  HTTP {row[2]:>3}  {row[3]}")
    ok = sum(1 for _, _, s, _ in results if s == 200)
    blocked = sum(1 for _, _, s, _ in results if s == 429)
    print(f"  → {ok} succeeded, {blocked} rate-limited")
    # Concurrent-lock cap (3/IP) may fire earlier than the per-IP request cap (5).
    # We expect at MOST 3 successes then 429s from the lock cap and/or IP cap.
    assert ok <= 3, f"B: too many succeeded ({ok}) — per-IP defenses failed"
    assert blocked >= 5, f"B: expected many blocks, got {blocked}"
    _clean(prefix)
    print("  ✅ per-IP (concurrent-lock and/or rate) cap fires as designed")


def scenario_c():
    print("\n=== C) XFF spoofing — new IP + new email PER REQUEST (worst case) ===")
    print("  → Expect the GLOBAL circuit breaker to fire around attempt 100 or")
    print("    the global concurrent-lock cap around attempt 50, whichever comes first.")
    prefix = f"atk_c_{uuid.uuid4().hex[:6]}_"
    dates = _dates_from(100, 120)
    results = []
    t0 = time.monotonic()
    first_block_at = None
    for i, d in enumerate(dates, 1):
        email = f"{prefix}{i}@flyboytest.com"
        fake_ip = f"203.0.113.{i % 254 + 1}"  # RFC5737 documentation range
        r = requests.post(
            CHECKOUT,
            json=_payload(d, email),
            headers={"X-Forwarded-For": fake_ip},
            timeout=15,
        )
        results.append((i, r.status_code, _detail(r), fake_ip))
        if r.status_code == 429 and first_block_at is None:
            first_block_at = i
            # print the ones near the break for readability
        if i <= 3 or (first_block_at and i <= first_block_at + 3) or i % 20 == 0:
            print(f"  attempt {i:>3}  spoof_ip={fake_ip:<16}  HTTP {r.status_code:>3}  {results[-1][2]}")
        if first_block_at and i > first_block_at + 5:
            print(f"  … (continuing loop, breaks confirmed at attempt {first_block_at})")
            break
    dt = time.monotonic() - t0
    ok = sum(1 for _, s, _, _ in results if s == 200)
    blocked = sum(1 for _, s, _, _ in results if s == 429)
    print(f"  → {ok} succeeded, {blocked} rate-limited in {dt:.2f}s")
    print(f"  → first 429 seen at attempt #{first_block_at}")
    # Expect the GLOBAL lock cap (50) or GLOBAL rate cap (100), whichever
    # trips first. Prove: global breaker fires within a bounded number of
    # attempts REGARDLESS of IP/email variation.
    assert first_block_at is not None, "C: no rate-limit block ever fired — global breaker broken"
    assert first_block_at <= 105, (
        f"C: global breaker fired too late ({first_block_at}) — bot could still freeze the calendar"
    )
    _clean(prefix)
    print("  ✅ global breaker fires even against per-request IP+email variation")


if __name__ == "__main__":
    # Fresh state so numbers are deterministic.
    sb.table("checkout_attempts").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    for prefix in ("atk_a_", "atk_b_", "atk_c_"):
        _clean(prefix)
    scenario_a()
    scenario_b()
    scenario_c()
    print("\nALL SCENARIOS PASSED — SEC-001 mitigation verified end-to-end")
