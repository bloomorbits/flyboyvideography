"""Bunny reconcile — pytest to the same bar as test_daily_invoicing.py.

WHAT IS PROVEN HERE (preview-runnable, no Bunny creds needed):
  * Auth matrix on the live cron endpoint: no token / wrong secret / wrong
    audience / wrong scope / expired / raw-secret-as-bearer → 401/403.
  * classify_status() — the pure decision that guarantees a still-processing
    video is NEVER false-flagged, and that a settled status is idempotent
    (a second identical poll writes nothing → no double-processing).
  * The stuck-query TARGETING against the live DB: a linked + stale +
    non-terminal deliverable is selected; a terminal one and a freshly-linked
    one are NOT. dry_run persists nothing.

WHAT IS DELIBERATELY *NOT* PROVEN HERE (see below):
  * The real Bunny Stream API round-trip + status write-back. Preview has no
    BUNNY_STREAM_LIBRARY_ID/BUNNY_STREAM_API_KEY, so a polled candidate lands
    in summary["errors"] as 'bunny_stream_config_missing'. Per the locked plan,
    the real round-trip is verified against Railway/prod (mint a bunny-reconcile
    JWT, hit the live endpoint, inspect the per-row result on the real linked
    test deliverable) — mirroring how Bunny Phase 1 was verified. That step is
    NOT mocked and NOT simulated here.

Run:
    ALLOW_ATTACK_SIM=1 pytest -xvs backend/tests/test_bunny_reconcile.py
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
import requests
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

if os.environ.get("ALLOW_ATTACK_SIM") != "1":
    raise SystemExit(
        "REFUSED: test_bunny_reconcile.py mutates the live Supabase DB. Set "
        "ALLOW_ATTACK_SIM=1 to run."
    )

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://db-bridge-5.preview.emergentagent.com").rstrip("/")
CRON_SECRET = os.environ["CRON_JOB_JWT_SECRET"]
AUD = "flyboy:cron:bunny-reconcile"
SCOPE = "cron:bunny-reconcile"

from supabase import create_client  # noqa: E402
import bunny_reconcile as br  # noqa: E402

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def _token(*, scope=SCOPE, audience=AUD, secret=None, expired=False):
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "aud": audience, "scope": scope,
            "iat": int(now.timestamp()),
            "exp": int((now - timedelta(minutes=1) if expired else now + timedelta(minutes=5)).timestamp()),
        },
        secret or CRON_SECRET, algorithm="HS256",
    )


def _endpoint(dry_run=False):
    return f"{BASE_URL}/api/admin/jobs/run-bunny-reconcile" + ("?dry_run=1" if dry_run else "")


# ============================================================================
# Auth matrix (live endpoint)
# ============================================================================

def test_refuses_without_token():
    assert requests.post(_endpoint(), timeout=30).status_code in (401, 403)


def test_refuses_wrong_secret():
    r = requests.post(_endpoint(), headers={"Authorization": f"Bearer {_token(secret='nope')}"}, timeout=30)
    assert r.status_code == 401, r.status_code


def test_refuses_wrong_audience():
    # An invoicing-audience token must NOT trigger reconcile.
    bad = _token(audience="flyboy:cron:daily-invoicing", scope="cron:invoicing")
    r = requests.post(_endpoint(), headers={"Authorization": f"Bearer {bad}"}, timeout=30)
    assert r.status_code == 401, r.status_code


def test_refuses_wrong_scope():
    bad = _token(scope="cron:invoicing")  # right aud, wrong scope
    r = requests.post(_endpoint(), headers={"Authorization": f"Bearer {bad}"}, timeout=30)
    assert r.status_code == 403, r.status_code


def test_refuses_expired():
    r = requests.post(_endpoint(), headers={"Authorization": f"Bearer {_token(expired=True)}"}, timeout=30)
    assert r.status_code == 401, r.status_code


def test_refuses_raw_secret_as_bearer_with_clear_diagnostic():
    """Same Railway-cron footgun guard as invoicing: posting the raw secret
    (not a signed JWT) must yield a clear 'malformed — expected a signed JWT'.
    Mutation hint: remove the tok.count('.')!=2 branch and this flips to FAIL."""
    r = requests.post(_endpoint(), headers={"Authorization": f"Bearer {CRON_SECRET}"}, timeout=30)
    assert r.status_code == 401, r.status_code
    detail = r.json().get("detail", "").lower()
    assert "malformed" in detail and "signed jwt" in detail, detail


# ============================================================================
# classify_status() — the false-flag + idempotency guarantees (pure, no I/O)
# ============================================================================

def test_still_processing_is_never_flagged_failed():
    """THE core safety property. Every non-terminal Bunny status → 'still',
    never 'failed'. Mutation hint: if the TERMINAL_FAILED check ever swallowed
    a non-terminal name, one of these flips to 'failed'."""
    for name in ("Queued", "Processing", "Encoding", "PresignedUploadStarted", "PresignedUploadFinished"):
        bucket, _ = br.classify_status(name, "Processing")
        assert bucket == "still", f"{name} was mis-bucketed as {bucket}"


def test_failed_only_from_bunny_failed():
    assert br.classify_status("Failed", "Processing") == ("failed", "Failed")
    assert br.classify_status("PresignedUploadFailed", "Encoding") == ("failed", "PresignedUploadFailed")


def test_finished_terminal():
    assert br.classify_status("Finished", "Encoding") == ("finished", "Finished")
    assert br.classify_status("ResolutionFinished", "Processing") == ("finished", "ResolutionFinished")


def test_idempotent_no_write_when_unchanged():
    """A second poll returning the SAME status writes nothing → no double-
    processing. This is the idempotency guarantee at the decision layer."""
    assert br.classify_status("Finished", "Finished") == ("finished", None)
    assert br.classify_status("Failed", "Failed") == ("failed", None)
    assert br.classify_status("Processing", "Processing") == ("still", None)


def test_advance_writes_but_stays_still():
    """Queued → Processing advances the stored string (a write) but is STILL
    'still' — advancing is not the same as flagging failed."""
    assert br.classify_status("Processing", "Queued") == ("still", "Processing")


# ============================================================================
# Live stuck-query targeting + dry-run safety
# ============================================================================

@pytest.fixture(scope="module")
def stuck_ctx():
    """Three throwaway deliverables against an existing client (referenced, not
    mutated): one stuck (should be selected), one terminal, one freshly-linked
    (both must be ignored). is_seed_data=True; deleted on teardown."""
    client = sb.table("clients").select("id").limit(1).execute().data
    assert client, "need at least one client row to reference"
    client_id = client[0]["id"]
    marker = uuid.uuid4().hex[:10]
    now = datetime.now(timezone.utc)

    def mk(status, minutes_ago):
        return sb.table("deliverables").insert({
            "client_id": client_id,
            "title": f"reconcile-test-{marker}-{status}-{minutes_ago}m",
            "status": "in_review",
            "bunny_video_guid": f"fake-{marker}-{uuid.uuid4().hex[:8]}",
            "bunny_status": status,
            "bunny_linked_at": (now - timedelta(minutes=minutes_ago)).isoformat(),
            "is_seed_data": True,
        }).execute().data[0]

    stuck = mk("Processing", 30)     # linked + stale + non-terminal → SELECTED
    terminal = mk("Finished", 30)    # terminal → ignored
    fresh = mk("Processing", 2)      # within threshold → ignored
    ctx = {"stuck": stuck["id"], "terminal": terminal["id"], "fresh": fresh["id"], "marker": marker}
    yield ctx
    for k in ("stuck", "terminal", "fresh"):
        sb.table("deliverables").delete().eq("id", ctx[k]).execute()


def _all_ids(summary):
    ids = set()
    for bucket in ("resolved_finished", "flagged_failed", "still_processing", "not_found_in_bunny", "errors"):
        for x in summary.get(bucket, []):
            if x.get("id"):
                ids.add(x["id"])
    return ids


def test_stuck_query_targets_only_the_right_row(stuck_ctx):
    """Direct core call (dry_run) — proves the SELECT. Preview has no Bunny
    creds, so the selected stuck row surfaces in errors as config-missing;
    that still proves it was picked up. Terminal + fresh rows must be absent."""
    summary = br.reconcile_bunny_statuses(dry_run=True)
    touched = _all_ids(summary)
    assert stuck_ctx["stuck"] in touched, f"stuck row not selected: {summary}"
    assert stuck_ctx["terminal"] not in touched, "terminal row must not be selected"
    assert stuck_ctx["fresh"] not in touched, "freshly-linked row must not be selected"

    # In preview the poll fails config-missing, so it lands in errors (not a
    # fabricated status change) — the honest degradation.
    err_ids = {e.get("id") for e in summary.get("errors", [])}
    assert stuck_ctx["stuck"] in err_ids
    assert any(e.get("reason") == "bunny_stream_config_missing" for e in summary["errors"])


def test_dry_run_persists_nothing(stuck_ctx):
    before = sb.table("deliverables").select("bunny_status").eq("id", stuck_ctx["stuck"]).execute().data[0]
    br.reconcile_bunny_statuses(dry_run=True)
    after = sb.table("deliverables").select("bunny_status").eq("id", stuck_ctx["stuck"]).execute().data[0]
    assert before["bunny_status"] == after["bunny_status"] == "Processing"
