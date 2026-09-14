"""
Attack simulation — Bunny webhook flood guard.

Proves the layered per-IP throttle on POST /api/bunny/webhook (built to stop a
flood of bad-signature POSTs from burning HMAC-verification CPU). Mirrors the
shape of sim_calendar_freeze_attack.py.

Coverage:
  A) Rolling-window cap, per IP  — real HTTP: same X-Real-IP, bad signatures.
       First WH_MAX_PER_IP pass the throttle (→ 401 bad-sig, HMAC ran), the
       rest are rejected by the throttle (→ 429, HMAC SKIPPED = CPU saved).
  B) Global rolling-window cap    — real HTTP: a *new* spoofed IP per request,
       proving the global backstop fires even under per-request IP variation.
  C) Concurrent in-flight cap, per IP — deterministic, in-process: acquire the
       per-IP slot cap+2 times without releasing; the last 2 must 429.

SAFETY: refuses to run against anything that isn't localhost/preview.

    python backend/tests/sim_bunny_webhook_flood.py
"""
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bunny import (  # noqa: E402
    WH_MAX_PER_IP,
    WH_MAX_GLOBAL,
    WH_CONCURRENT_PER_IP,
    _WebhookThrottle,
)
from fastapi import HTTPException  # noqa: E402

_BASE = os.environ.get("WEBHOOK_BASE", "http://localhost:8001").rstrip("/")
_SAFE = ("localhost", "127.0.0.1", "preview.emergentagent.com", "staging")
if not any(m in _BASE for m in _SAFE):
    raise SystemExit(f"Refusing to run against non-safe URL {_BASE!r} (allowed: {_SAFE})")

WEBHOOK = f"{_BASE}/api/bunny/webhook"


def _post(ip: str):
    # Deliberately-invalid signature headers → _verify_webhook() returns False.
    return requests.post(
        WEBHOOK,
        data=b'{"VideoLibraryId":1,"VideoGuid":"x","Status":3}',
        headers={
            "X-Real-IP": ip,
            "Content-Type": "application/json",
            "X-BunnyStream-Signature": "0" * 64,
            "X-BunnyStream-Signature-Version": "v1",
            "X-BunnyStream-Signature-Algorithm": "hmac-sha256",
        },
        timeout=15,
    )


def scenario_a():
    print("\n=== A) Rolling-window cap, per IP (bad-signature flood, one IP) ===")
    ip = f"198.51.100.{uuid.uuid4().int % 200 + 1}"
    n = WH_MAX_PER_IP + 5
    codes = []
    first_429 = None
    t0 = time.monotonic()
    for i in range(1, n + 1):
        r = _post(ip)
        codes.append(r.status_code)
        if r.status_code == 429 and first_429 is None:
            first_429 = i
    dt = time.monotonic() - t0
    passed_to_hmac = sum(1 for c in codes if c == 401)   # throttle admitted, HMAC ran + failed
    rejected = sum(1 for c in codes if c == 429)          # throttle rejected, HMAC SKIPPED
    print(f"  sent {n} from ip={ip} in {dt:.2f}s")
    print(f"  → {passed_to_hmac} reached HMAC (401 bad-sig), {rejected} rejected by throttle (429, HMAC skipped)")
    print(f"  → first 429 at attempt #{first_429}")
    assert first_429 == WH_MAX_PER_IP + 1, f"A: expected first 429 at {WH_MAX_PER_IP+1}, got {first_429}"
    print(f"  ✅ per-IP rolling-window cap ({WH_MAX_PER_IP}/window) fires exactly at attempt {WH_MAX_PER_IP+1}")
    print(f"  ✅ {rejected} bad-signature POSTs rejected BEFORE HMAC (CPU-burn averted)")


def scenario_b():
    print("\n=== B) Global cap — new spoofed IP per request (worst case) ===")
    print(f"  → expect the GLOBAL backstop ({WH_MAX_GLOBAL}) to fire regardless of IP variation")
    first_429 = None
    sent = 0
    t0 = time.monotonic()
    for i in range(1, WH_MAX_GLOBAL + 30):
        r = _post(f"203.0.113.{i % 254 + 1}.{i}")  # unique-ish per request
        sent += 1
        if r.status_code == 429 and first_429 is None:
            first_429 = i
            break
    dt = time.monotonic() - t0
    print(f"  sent {sent} across distinct IPs in {dt:.2f}s")
    print(f"  → first global 429 at attempt #{first_429}")
    assert first_429 is not None, "B: global backstop never fired"
    assert first_429 <= WH_MAX_GLOBAL + 5, f"B: global cap fired too late ({first_429})"
    print(f"  ✅ global rolling-window backstop fires under per-request IP variation")


def scenario_c():
    print("\n=== C) Concurrent in-flight cap, per IP (deterministic, in-process) ===")
    ip = "9.9.9.9"
    slots = [_WebhookThrottle(ip) for _ in range(WH_CONCURRENT_PER_IP + 2)]
    admitted, rejected = 0, 0
    for s in slots:
        try:
            s.acquire()
            admitted += 1
        except HTTPException as e:
            assert e.status_code == 429
            rejected += 1
    print(f"  acquired {WH_CONCURRENT_PER_IP + 2} slots without releasing: {admitted} admitted, {rejected} rejected")
    assert admitted == WH_CONCURRENT_PER_IP, f"C: expected {WH_CONCURRENT_PER_IP} admitted, got {admitted}"
    assert rejected == 2, f"C: expected 2 concurrent rejections, got {rejected}"
    for s in slots:
        s.release()
    print(f"  ✅ per-IP concurrent cap ({WH_CONCURRENT_PER_IP}) rejects overflow in-flight requests")


if __name__ == "__main__":
    scenario_a()
    scenario_b()
    scenario_c()
    print("\nAll webhook flood-guard scenarios passed.")
