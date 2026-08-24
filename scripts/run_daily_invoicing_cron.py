#!/usr/bin/env python3
"""Mint a short-lived cron JWT and trigger the daily-invoicing endpoint.

This is the real scheduled cron for the automated balance-collection cycle.
It runs from GitHub Actions (see .github/workflows/daily-invoicing.yml), NOT
as a Railway service — Railway cron re-runs a service's Start Command, which
for our backend is `uvicorn server:app` (a long-lived web server), so it can
never be the vehicle for a one-shot mint-and-POST. GitHub Actions gives us a
one-shot runner with real per-run history/logs and keeps the cron secret in
a credential store separate from the app.

Env (from GitHub Actions secrets):
  CRON_JOB_JWT_SECRET  — same value set on the Railway backend
  SELF_URL             — Railway backend base URL, e.g. https://flyboy-api.up.railway.app

Optional:
  DRY_RUN=1            — append ?dry_run=1 (compute but don't write/send)

Exit code:
  0 on HTTP 2xx, 1 otherwise — a non-zero exit turns the GitHub Actions run
  red so a silent failure becomes a visible one (email + red run in history).
"""
import os
import sys
import time

import jwt
import httpx

AUDIENCE = "flyboy:cron:daily-invoicing"
SCOPE = "cron:invoicing"


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

    url = f"{self_url}/api/admin/jobs/run-daily-invoicing"
    if os.environ.get("DRY_RUN") == "1":
        url += "?dry_run=1"

    print(f"POST {url}")
    try:
        r = httpx.post(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=90.0,
        )
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
