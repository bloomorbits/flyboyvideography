"""Auth-only regression for /api/admin/jobs/run-daily-invoicing.

Isolated from test_daily_invoicing.py (which mutates the DB and is gated on
ALLOW_ATTACK_SIM). This module ONLY hits the auth surface — safe to run
without the safety guard.
"""
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import pytest
import requests
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://db-bridge-5.preview.emergentagent.com"
# Prefer frontend .env for the target URL (what user sees)
FRONTEND_ENV = Path("/app/frontend/.env")
if FRONTEND_ENV.exists():
    for line in FRONTEND_ENV.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

CRON_SECRET = os.environ["CRON_JOB_JWT_SECRET"]
AUD = "flyboy:cron:daily-invoicing"
ENDPOINT = f"{BASE_URL}/api/admin/jobs/run-daily-invoicing"


def _token(*, scope="cron:invoicing", audience=AUD, secret=None, expired=False):
    now = datetime.now(timezone.utc)
    payload = {
        "aud": audience,
        "scope": scope,
        "iat": int(now.timestamp()),
        "exp": int((now - timedelta(minutes=1) if expired else now + timedelta(minutes=5)).timestamp()),
    }
    return jwt.encode(payload, secret or CRON_SECRET, algorithm="HS256")


# ---------- 3 primary auth cases the user demanded ----------

def test_case1_raw_secret_as_bearer_returns_401_with_diagnostic():
    r = requests.post(ENDPOINT, headers={"Authorization": f"Bearer {CRON_SECRET}"}, timeout=30)
    assert r.status_code == 401, r.status_code
    detail = r.json().get("detail", "")
    print(f"CASE1 | 401 | {r.status_code} | 'malformed' & ('signed jwt'|'3 dot-separated') | {detail!r} | ", end="")
    assert "malformed" in detail.lower(), detail
    assert "signed jwt" in detail.lower() or "3 dot-separated" in detail.lower(), detail
    print("PASS")


def test_case2_valid_signed_jwt_dry_run_returns_200():
    tok = _token()
    r = requests.post(ENDPOINT + "?dry_run=1", headers={"Authorization": f"Bearer {tok}"}, timeout=60)
    print(f"CASE2 | 200 | {r.status_code} | dry_run=true+expected keys | (body keys) | ", end="")
    assert r.status_code == 200, (r.status_code, r.text[:400])
    body = r.json()
    required = {
        "date", "dry_run", "invoice_target_date", "reminder_cutoff",
        "invoices_created", "invoices_skipped_already_exists",
        "invoices_skipped_zero_balance", "reminders_sent",
        "reminders_skipped_paid_manually", "errors",
    }
    missing = required - set(body.keys())
    assert not missing, f"missing keys: {missing}; body={body}"
    assert body["dry_run"] is True, body
    print("PASS")


def test_case3_missing_token_returns_401():
    r = requests.post(ENDPOINT, timeout=30)
    assert r.status_code == 401, r.status_code
    detail = r.json().get("detail", "")
    print(f"CASE3 | 401 | {r.status_code} | 'Cron bearer token required.' | {detail!r} | ", end="")
    assert detail == "Cron bearer token required.", detail
    print("PASS")


# ---------- Regression sweep ----------

def test_wrong_secret_returns_401():
    bad = _token(secret="not_the_real_secret_XXXXXXXXXXXXXXXXXXXXXXXXXXX")
    r = requests.post(ENDPOINT, headers={"Authorization": f"Bearer {bad}"}, timeout=30)
    detail = r.json().get("detail", "")
    print(f"REG_wrong_secret | 401 | {r.status_code} | 'Invalid cron token.' | {detail!r}")
    assert r.status_code == 401
    assert detail == "Invalid cron token.", detail


def test_wrong_audience_returns_401():
    bad = _token(audience="flyboy:cron:something-else")
    r = requests.post(ENDPOINT, headers={"Authorization": f"Bearer {bad}"}, timeout=30)
    detail = r.json().get("detail", "")
    print(f"REG_wrong_aud | 401 | {r.status_code} | 'Cron token audience mismatch.' | {detail!r}")
    assert r.status_code == 401
    assert "audience" in detail.lower(), detail


def test_wrong_scope_returns_403():
    bad = _token(scope="cron:something-else")
    r = requests.post(ENDPOINT, headers={"Authorization": f"Bearer {bad}"}, timeout=30)
    detail = r.json().get("detail", "")
    print(f"REG_wrong_scope | 403 | {r.status_code} | 'Cron token scope mismatch.' | {detail!r}")
    assert r.status_code == 403
    assert "scope" in detail.lower(), detail


def test_expired_token_returns_401():
    bad = _token(expired=True)
    r = requests.post(ENDPOINT, headers={"Authorization": f"Bearer {bad}"}, timeout=30)
    detail = r.json().get("detail", "")
    print(f"REG_expired | 401 | {r.status_code} | 'Cron token expired.' | {detail!r}")
    assert r.status_code == 401
    assert "expired" in detail.lower(), detail
