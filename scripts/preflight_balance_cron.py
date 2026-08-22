"""Preflight verifier for the Balance Cron deploy on Railway.

Run this AFTER Railway auto-deploys the code + you've set
CRON_JOB_JWT_SECRET / PUBLIC_API_BASE / SELF_URL in Railway env.

What it checks (all safe — no writes, uses dry_run=1):
  1. /api/health responds 200 on the target
  2. /api/admin/jobs/run-daily-invoicing without a token → 401
  3. Wrong secret → 401
  4. Wrong audience → 401
  5. Wrong scope → 403
  6. Correct token → 200 with a well-formed dry-run summary
  7. /api/booking/pay-balance/<bogus-uuid> → 404 (proves route mounted)

Usage:
    # Point at Railway production
    export SELF_URL="https://flyboy-api-production.up.railway.app"
    export CRON_JOB_JWT_SECRET="<the secret you set on Railway>"
    python scripts/preflight_balance_cron.py

Exit code 0 = all green, 1 = any check failed.
"""
import json
import os
import sys
import time
import uuid

import httpx
import jwt

TARGET = os.environ.get("SELF_URL", "").rstrip("/")
SECRET = os.environ.get("CRON_JOB_JWT_SECRET", "")

if not TARGET or not SECRET:
    print("FAIL: set SELF_URL and CRON_JOB_JWT_SECRET in env first")
    sys.exit(1)

AUD = "flyboy:cron:daily-invoicing"


def mint(*, aud=AUD, scope="cron:invoicing", secret=None, expired=False):
    now = int(time.time())
    return jwt.encode(
        {
            "aud": aud,
            "scope": scope,
            "iat": now,
            "exp": now - 60 if expired else now + 300,
        },
        secret or SECRET,
        algorithm="HS256",
    )


results = []


def check(name, ok, detail=""):
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))
    results.append(ok)


print(f"\nPreflight against {TARGET}\n" + "-" * 60)

with httpx.Client(timeout=30.0) as c:
    # 1. Health
    r = c.get(f"{TARGET}/api/health")
    check("health returns 200", r.status_code == 200, f"HTTP {r.status_code}")

    # 2. No token
    r = c.post(f"{TARGET}/api/admin/jobs/run-daily-invoicing")
    check("no token → 401", r.status_code == 401, f"HTTP {r.status_code}")

    # 3. Wrong secret
    r = c.post(
        f"{TARGET}/api/admin/jobs/run-daily-invoicing",
        headers={"Authorization": f"Bearer {mint(secret='not_the_real_secret_at_all')}"},
    )
    check("wrong secret → 401", r.status_code == 401, f"HTTP {r.status_code}")

    # 4. Wrong audience
    r = c.post(
        f"{TARGET}/api/admin/jobs/run-daily-invoicing",
        headers={"Authorization": f"Bearer {mint(aud='not:the:right:aud')}"},
    )
    check("wrong audience → 401", r.status_code == 401, f"HTTP {r.status_code}")

    # 5. Wrong scope
    r = c.post(
        f"{TARGET}/api/admin/jobs/run-daily-invoicing",
        headers={"Authorization": f"Bearer {mint(scope='cron:wrong')}"},
    )
    check("wrong scope → 403", r.status_code == 403, f"HTTP {r.status_code}")

    # 6. Correct token → dry-run summary
    r = c.post(
        f"{TARGET}/api/admin/jobs/run-daily-invoicing?dry_run=1",
        headers={"Authorization": f"Bearer {mint()}"},
    )
    ok = r.status_code == 200
    detail = f"HTTP {r.status_code}"
    if ok:
        try:
            body = r.json()
            required = {"date", "dry_run", "invoice_target_date", "reminder_cutoff", "invoices_created", "reminders_sent", "errors"}
            missing = required - set(body.keys())
            ok = not missing and body.get("dry_run") is True
            detail = "well-formed summary" if ok else f"missing keys: {missing}"
        except Exception as e:
            ok = False
            detail = f"JSON parse error: {e}"
    check("valid token → 200 + well-formed dry-run summary", ok, detail)
    if r.status_code == 200:
        print("\nDry-run summary:")
        try:
            print("  " + json.dumps(r.json(), indent=2).replace("\n", "\n  "))
        except Exception:
            pass

    # 7. pay-balance route mounted
    r = c.get(f"{TARGET}/api/booking/pay-balance/{uuid.uuid4()}", follow_redirects=False)
    check("pay-balance route mounted (404 on bogus UUID)", r.status_code == 404, f"HTTP {r.status_code}")

print("-" * 60)
if all(results):
    print(f"ALL PREFLIGHT CHECKS PASSED — safe to add the Railway Cron schedule.")
    sys.exit(0)
else:
    failed = sum(1 for r in results if not r)
    print(f"{failed}/{len(results)} CHECK(S) FAILED — do not schedule the cron yet.")
    sys.exit(1)
