"""Unit tests for the dashboard's daily-invoicing cron staleness flag.

The flag exists to convert a silently-stalled cron (fails invisibly for an
unknown period until someone happens to check) into a visible red flag on
the admin dashboard. `stale` is True when there is NO successful (ok=true)
run inside CRON_STALE_HOURS (default 26h).

Mutation-verified (SEC-001 standard): flip `hours_since_ok > CRON_STALE_HOURS`
to `>=` or the branch to a constant and the boundary tests below flip
PASS -> FAIL.

Run:
    cd /app/backend && python -m pytest tests/test_cron_staleness.py -q
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import admin_dashboard as ad  # noqa: E402


class _Query:
    """Minimal chainable stub mimicking supabase-py's query builder."""

    def __init__(self, last_run_rows, last_ok_rows):
        self._last_run_rows = last_run_rows
        self._last_ok_rows = last_ok_rows
        self._filtering_ok = False

    def select(self, *a, **k):
        return self

    def eq(self, col, val):
        if col == "ok" and val is True:
            self._filtering_ok = True
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        rows = self._last_ok_rows if self._filtering_ok else self._last_run_rows
        return type("R", (), {"data": rows})()


class _SB:
    def __init__(self, last_run_rows, last_ok_rows):
        self._last_run_rows = last_run_rows
        self._last_ok_rows = last_ok_rows

    def table(self, name):
        assert name == "cron_runs"
        return _Query(self._last_run_rows, self._last_ok_rows)


def _iso(hours_ago):
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def _run_row(started_hours_ago, ok=True, error_count=0):
    return {
        "id": "run-1",
        "job_name": "daily_invoicing",
        "started_at": _iso(started_hours_ago),
        "finished_at": _iso(started_hours_ago),
        "summary": {},
        "error_count": error_count,
        "ok": ok,
    }


def _call(last_run_rows, last_ok_rows):
    return ad._tile_cron_last_run(_SB(last_run_rows, last_ok_rows))


# ---------------------------------------------------------------------------

def test_none_when_no_runs():
    assert _call([], []) is None


def test_fresh_success_is_not_stale():
    row = _run_row(1)  # succeeded 1h ago
    out = _call([row], [{"started_at": row["started_at"]}])
    assert out["stale"] is False
    assert out["hours_since_last_ok"] < 26


def test_just_inside_threshold_not_stale():
    # 25h ago — still inside the 26h window.
    row = _run_row(25)
    out = _call([row], [{"started_at": row["started_at"]}])
    assert out["stale"] is False


def test_just_past_threshold_is_stale():
    # 27h ago — past the 26h window -> stale.
    row = _run_row(27)
    out = _call([row], [{"started_at": row["started_at"]}])
    assert out["stale"] is True
    assert out["hours_since_last_ok"] > 26


def test_recent_failure_but_no_recent_success_is_stale():
    # Last run failed 1h ago; last success was 30h ago -> stale
    # (a red row does NOT reset the staleness clock).
    failed = _run_row(1, ok=False, error_count=2)
    out = _call([failed], [{"started_at": _iso(30)}])
    assert out["stale"] is True
    assert out["ok"] is False
    assert out["error_count"] == 2


def test_never_succeeded_is_stale():
    # A run exists but none ever succeeded -> stale, last_ok_at None.
    failed = _run_row(2, ok=False, error_count=1)
    out = _call([failed], [])
    assert out["stale"] is True
    assert out["last_ok_at"] is None
    assert out["hours_since_last_ok"] is None


def test_threshold_reported_in_payload():
    row = _run_row(1)
    out = _call([row], [{"started_at": row["started_at"]}])
    assert out["stale_threshold_hours"] == ad.CRON_STALE_HOURS


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-q"]))
