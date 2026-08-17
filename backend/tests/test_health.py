"""Tests for GET /api/health live Supabase probe.

The endpoint should:
  - Return 200 with {"status":"ok","database":"supabase"} when Supabase is reachable.
  - Return 503 with {"status":"unavailable","database":"supabase","error_class":<str>}
    when Supabase is unreachable, without leaking exception details.
  - Complete within ~2.5s (internal socket timeout is 2s).
  - Restore the default socket timeout afterwards (finally block).
"""
import os
import time
from pathlib import Path

import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for line in Path("/app/frontend/.env").read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

HEALTH = f"{BASE_URL}/api/health"


def _get_health():
    return requests.get(HEALTH, timeout=5)


def test_health_returns_valid_status():
    """Status must be either 200 (up) or 503 (down); never anything else."""
    r = _get_health()
    assert r.status_code in (200, 503), f"unexpected status {r.status_code}: {r.text}"


def test_health_response_shape():
    r = _get_health()
    body = r.json()
    assert body.get("database") == "supabase"
    if r.status_code == 200:
        assert body.get("status") == "ok"
        assert set(body.keys()) == {"status", "database"}, body
    else:
        assert body.get("status") == "unavailable"
        assert isinstance(body.get("error_class"), str) and body["error_class"]
        assert set(body.keys()) == {"status", "database", "error_class"}, body


def test_health_does_not_leak_raw_exception_details():
    """Body must never contain hostnames, JWT fragments, tracebacks, or paths."""
    r = _get_health()
    text = r.text.lower()
    forbidden = [
        "pnqqmzszasvfnvnnonvd",
        "supabase.co",
        "traceback",
        "service_role",
        "/app/backend",
        "eyj",  # JWT prefix
        "exception",
    ]
    for f in forbidden:
        assert f not in text, f"health body leaked '{f}': {r.text}"


def test_health_latency_bounded():
    """Endpoint should return within ~2.5s (2s socket timeout + overhead)."""
    start = time.perf_counter()
    r = _get_health()
    elapsed = time.perf_counter() - start
    assert r.status_code in (200, 503)
    assert elapsed < 4.0, f"health probe took {elapsed:.2f}s, expected <4s"


def test_socket_timeout_restored_after_health_call():
    """Unrelated auth endpoint must still respond normally after /api/health."""
    _get_health()  # trigger the setdefaulttimeout/finally path
    start = time.perf_counter()
    r = requests.get(
        f"{BASE_URL}/api/admin/erasure-audit",
        headers={"Authorization": "Bearer faketoken123"},
        timeout=10,
    )
    elapsed = time.perf_counter() - start
    assert r.status_code == 401, f"expected 401, got {r.status_code}: {r.text}"
    assert elapsed < 5.0, f"followup call took {elapsed:.2f}s — timeout may not be restored"


def test_health_is_idempotent_across_repeated_calls():
    """Multiple back-to-back calls should not degrade or leak state."""
    results = []
    for _ in range(3):
        r = _get_health()
        results.append(r.status_code)
    assert all(s == results[0] for s in results), f"inconsistent statuses: {results}"
