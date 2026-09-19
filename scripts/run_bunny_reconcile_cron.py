#!/usr/bin/env python3
"""Mint a short-lived cron JWT and trigger the Bunny reconcile endpoint.

Scheduled sweep for Bunny webhook backfill — repairs deliverables whose Stream
webhook was missed and would otherwise sit forever in a non-terminal status.

Runs from GitHub Actions (see .github/workflows/bunny-reconcile.yml), NOT as a
Railway service (same reasoning as run_daily_invoicing_cron.py — Railway cron
re-runs a long-lived web server, no good for a one-shot mint-and-POST).

Uses the SAME CRON_JOB_JWT_SECRET as invoicing, but a DISTINCT audience+scope,
so an invoicing token can never trigger reconcile and vice-versa. It is NOT the
admin session token.

Env (from GitHub Actions secrets):
  CRON_JOB_JWT_SECRET  — same value set on the Railway backend
  SELF_URL             — Railway backend base URL, e.g. https://flyboy-api.up.railway.app
Optional:
  DRY_RUN=1            — append ?dry_run=1 (poll Bunny but don't write)

Exit code: 0 on HTTP 2xx, 1 otherwise (non-zero turns the Actions run red).
"""
import os
import sys
import time

import jwt
import httpx

AUDIENCE = "flyboy:cron:bunny-reconcile"
SCOPE = "cron:bunny-reconcile"


def main() -> int:
    secret = os.environ.get("CRON_JOB_JWT_SECRET", "")
    self_url = os.environ.get("SELF_URL", "").rstrip("/")
    if not secret:
        print("ERROR: CRON_JOB_JWT_SECRET is not set", file=sys.stderr)
        return 1
    if not self_url:
        print("ERROR: SELF_URL is not set", file=sys.stderr)
        return 1

    now = int(time.time())
    token = jwt.encode(
        {"aud": AUDIENCE, "scope": SCOPE, "iat": now, "exp": now + 300},
        secret,
        algorithm="HS256",
    )

    url = f"{self_url}/api/admin/jobs/run-bunny-reconcile"
    if os.environ.get("DRY_RUN") == "1":
        url += "?dry_run=1"

    print(f"POST {url}")
    try:
        r = httpx.post(url, headers={"Authorization": f"Bearer {token}"}, timeout=90.0)
    except Exception as e:
        print(f"ERROR: request failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    print(f"HTTP {r.status_code}")
    print(r.text[:4000])
    if r.status_code // 100 != 2:
        print(f"ERROR: endpoint returned {r.status_code}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
