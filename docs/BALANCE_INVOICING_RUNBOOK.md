# Automated balance collection — deployment runbook

Phased build complete: Migration 012 (DB), webhook branch (Phase 2), balance
checkout endpoint (Phase 3), daily invoicing + reminder job (Phase 4/5).
This doc is the deployment checklist for Phase 6 — wiring the Railway Cron
and validating the end-to-end path in production.

## What's shipped

| Component | File | Tested by |
|---|---|---|
| DB migration (`payment_purpose`, `reminder_sent_at`, partial unique index) | `supabase_migration_012_balance_invoicing.sql` | `backend/tests/introspect_012.py` (9505 duplicate rejection proven) |
| Webhook balance branch (`_finalise_balance_payment`) | `backend/booking.py` | `backend/tests/test_balance_finalise.py` (9 tests, 100× replay stress) |
| Balance Checkout Session helper + `/api/booking/pay-balance/{invoice_id}` | `backend/booking.py` | Covered by Phase 4 e2e via the checkout URL in emails |
| `POST /api/admin/jobs/run-daily-invoicing` + Resend emails | `backend/daily_invoicing.py` | `backend/tests/test_daily_invoicing.py` (12 tests including manual-payment suppression proof) |
| Email templates (invoice + reminder, HTML + text) | `backend/emails/balance_{invoice,reminder}.{html,txt}` | Rendered inside pytest |

## Environment variables to set on Railway (production backend)

```
CRON_JOB_JWT_SECRET=<64-byte urlsafe token>          # NEW — generate fresh, do NOT reuse
INVOICE_LEAD_DAYS=10                                  # optional, default 10
REMINDER_LEAD_DAYS=2                                  # optional, default 2
PUBLIC_API_BASE=https://<railway>/                    # optional; used for the pay-balance URL in emails. Falls back to REACT_APP_BACKEND_URL.
```

Local `backend/.env` already has `CRON_JOB_JWT_SECRET` for pytest. **Do not
share the same secret across environments** — generate a fresh one per env.

Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"`

## Cron token — how to mint one

The endpoint expects a JWT signed with `CRON_JOB_JWT_SECRET`, algorithm
`HS256`, with `aud=flyboy:cron:daily-invoicing` and `scope=cron:invoicing`
and a short-ish `exp` (5 min is fine for a cron process that runs once and
exits).

Reference minting snippet — copy into `scripts/mint_cron_token.py` on
Railway, or embed inside the cron command:

```python
import jwt, os, time
now = int(time.time())
print(jwt.encode({
    "aud": "flyboy:cron:daily-invoicing",
    "scope": "cron:invoicing",
    "iat": now,
    "exp": now + 300,  # 5 minutes
}, os.environ["CRON_JOB_JWT_SECRET"], algorithm="HS256"))
```

## Railway Cron setup

1. In the Railway dashboard, add a new Cron schedule to the backend service.
2. Frequency: **daily at 08:00 UTC** (early-morning window catches all EU
   timezones during working hours; no client is happy about receiving
   an invoice at 3am).
3. Command (single line — this is what Railway will run):

```
python -c "
import jwt, os, time, httpx
now = int(time.time())
tok = jwt.encode({
    'aud': 'flyboy:cron:daily-invoicing',
    'scope': 'cron:invoicing',
    'iat': now, 'exp': now + 300,
}, os.environ['CRON_JOB_JWT_SECRET'], algorithm='HS256')
r = httpx.post(
    os.environ.get('SELF_URL', 'https://<your-railway-domain>') + '/api/admin/jobs/run-daily-invoicing',
    headers={'Authorization': f'Bearer {tok}'}, timeout=90.0,
)
print(r.status_code, r.text[:2000])
r.raise_for_status()
"
```

Notes:
- `SELF_URL` avoids hard-coding the domain. Set it in Railway env to the
  backend's public URL (e.g. `https://flyboy-api.up.railway.app`).
- 90s timeout is generous — the job returns in <5s for typical volume.
- Non-2xx from the endpoint makes the cron run fail visibly in Railway
  logs, which is what we want.

## Deployment order

1. Merge the code changes to `main` and let Railway auto-deploy.
2. Set `CRON_JOB_JWT_SECRET` in Railway env.
3. Set `PUBLIC_API_BASE` in Railway env (points at the Railway backend URL —
   this is the URL that appears inside customer emails and 302-redirects
   to Stripe).
4. Set `SELF_URL` in Railway env (only used by the cron command).
5. **Run the preflight verifier from your laptop** (safe — read-only + dry-run only):
   ```bash
   export SELF_URL="https://<your-railway-domain>"
   export CRON_JOB_JWT_SECRET="<the secret you set on Railway>"
   python scripts/preflight_balance_cron.py
   ```
   All 7 checks must PASS before adding the cron schedule. Exit code 0 = green.
6. Add the Railway Cron schedule using the command below.
7. Wait for the first scheduled run — check Railway logs for the summary
   JSON output.

## Runtime health signals

The endpoint returns a JSON summary on every call. Monitor these fields:

| Field | Meaning | Alert threshold |
|---|---|---|
| `errors` | Per-row exceptions | > 0 → investigate |
| `invoices_created` | Successful new balance invoices | Expected 1-N per day depending on bookings |
| `invoices_skipped_already_exists` | Re-run same day | Expected on re-runs; not on first daily run |
| `reminders_skipped_paid_manually` | Client settled outside the flow | Expected occasionally; not the majority |

Errors caught by the endpoint are per-row, not per-endpoint — one bad
booking never blocks the rest of the batch.

## Rollback

The migration is additive-only. If the balance flow needs to be paused:

1. **Immediate pause:** disable the Railway Cron schedule. No invoices
   fire, no reminders fire. Manual payment collection continues as before
   (existing client-side booking flow untouched).
2. **Full rollback:** revert the code changes. The DB columns and index
   remain but have zero effect without the code that writes to them.

## Preview-webhook retirement (Step 14) — observation plan

Decision from session 15: do NOT retire on a single data point. Extend the
observation window and, if organic traffic stays thin, generate a small
number of controlled test bookings to fatten the sample.

Schedule:
- **T+24h** (session 15 baseline): `seen_by_both=1, railway_only=0, preview_only=0`. Healthy but statistically thin.
- **T+48h:** re-run `python scripts/monitor_dual_delivery.py --hours 48`.
  Look for: `seen_by_both ≥ 3`, `preview_only == 0`.
- **T+72h:** re-run `python scripts/monitor_dual_delivery.py --hours 72`.
  Look for: `seen_by_both ≥ 5`, `preview_only == 0`.
- **If sample still thin (< 3 events) at T+72h:** generate 2-3 controlled
  test bookings (real Stripe test-mode payments, real webhook fires) using
  the standard `@flyboytest.com` domain convention, then re-run the monitor
  with a fresh `--hours 24` window narrowly scoped to the test window. Any
  `preview_only > 0` blocks retirement.
- **Retirement gate**: `seen_by_both ≥ 5 AND preview_only == 0` on any run.

Only when the gate passes: execute `docs/STEP_14_PREVIEW_RETIREMENT.md`.

