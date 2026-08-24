# Automated balance collection — deployment runbook

Phased build complete: Migration 012 (DB), webhook branch (Phase 2), balance
checkout endpoint (Phase 3), daily invoicing + reminder job (Phase 4/5).
This doc is the deployment checklist for Phase 6 — wiring the scheduled
cron (GitHub Actions) and validating the end-to-end path in production.

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

The scheduled cron runs from **GitHub Actions**, not Railway, so `SELF_URL`
is a **GitHub Actions secret**, not a Railway env var (see the GitHub Actions
section below). `CRON_JOB_JWT_SECRET` is needed in **both** places and the
two values MUST match: Railway signs-verifies with it, GitHub Actions signs
with it.

Local `backend/.env` already has `CRON_JOB_JWT_SECRET` for pytest. **Do not
share the same secret across environments** — generate a fresh one per env
(the Railway value and the GitHub Actions value are the same secret; the
local pytest value is a different one).

Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"`

## Scheduled cron — GitHub Actions (NOT a Railway "Command" field)

> **Architecture correction.** Earlier revisions of this runbook told you to
> "add a Cron schedule to the backend service" and paste a one-liner into a
> "Command" field. **That field does not exist.** Railway's cron feature
> re-runs a service's existing **Start Command** on a schedule — and our
> backend's Start Command (`backend/Procfile`) is
> `uvicorn server:app --host 0.0.0.0 --port $PORT`, a long-lived web server.
> Attaching a cron to it would just spin up another web server; it would
> never mint a JWT or POST the endpoint. This mismatch is why no genuine
> scheduled run ever landed in `cron_runs`.
>
> The real cron runs from **GitHub Actions**:
> `.github/workflows/daily-invoicing.yml` → `scripts/run_daily_invoicing_cron.py`.
> Chosen deliberately over a second Railway service because it (a) adds no
> ongoing Railway service to monitor/hand over, (b) keeps the cron secret in
> a separate credential store (GitHub Actions secrets) from the app, and
> (c) gives real per-run history + logs, which Railway cron does not have
> natively.

### How it works

- `scripts/run_daily_invoicing_cron.py` mints a short-lived HS256 JWT
  (`aud=flyboy:cron:daily-invoicing`, `scope=cron:invoicing`, `exp` +5min)
  signed with `CRON_JOB_JWT_SECRET`, POSTs it to
  `$SELF_URL/api/admin/jobs/run-daily-invoicing`, prints the summary, and
  exits non-zero on any non-2xx — so a failure shows up as a **red run** in
  the Actions history (and GitHub emails the repo admins on failure).
- `.github/workflows/daily-invoicing.yml` runs it daily at **08:00 UTC**
  (`cron: "0 8 * * *"`) and also on-demand via **workflow_dispatch** (with an
  optional `dry_run` toggle for safe verification).

### Setup steps

1. Add two **repository secrets** (Settings → Secrets and variables → Actions):
   - `CRON_JOB_JWT_SECRET` — MUST be byte-identical to the value set on the
     Railway backend (mint fresh for production; do NOT reuse the local
     pytest secret).
   - `SELF_URL` — the Railway backend base URL, e.g.
     `https://flyboy-api.up.railway.app` (no trailing slash needed).
2. Merge the workflow to the default branch so GitHub registers the schedule.
   (Scheduled workflows only run from the **default branch**.)
3. **Verify manually first** — Actions tab → "Daily balance invoicing" →
   "Run workflow" → tick `dry_run` → Run. Confirm the run is green and the
   logs show `HTTP 200` + a summary JSON with `"dry_run": true`.
4. Run it once more **without** `dry_run` to do a real pass, then confirm a
   `cron_runs` row appears with `dry_run=false, ok=true, error_count=0`.
5. Leave the daily schedule to fire on its own thereafter.

### Reference: the minted token

The endpoint expects an HS256 JWT signed with `CRON_JOB_JWT_SECRET`, with
`aud=flyboy:cron:daily-invoicing`, `scope=cron:invoicing`, and a short `exp`.
`scripts/run_daily_invoicing_cron.py` builds exactly this — you don't need to
mint by hand. For a manual `curl` probe from your laptop, the equivalent
mint snippet is:

```python
import jwt, os, time
now = int(time.time())
print(jwt.encode({
    "aud": "flyboy:cron:daily-invoicing",
    "scope": "cron:invoicing",
    "iat": now, "exp": now + 300,
}, os.environ["CRON_JOB_JWT_SECRET"], algorithm="HS256"))
```

Notes:
- `SELF_URL` avoids hard-coding the domain in the script.
- The endpoint returns in <5s for typical volume; the workflow allows 5min.
- A non-2xx makes the Actions run fail visibly — that's the point.

## Deployment order

1. Merge the code changes (incl. `.github/workflows/daily-invoicing.yml` and
   `scripts/run_daily_invoicing_cron.py`) to the default branch and let
   Railway auto-deploy the backend.
2. Set `CRON_JOB_JWT_SECRET` in **Railway** env.
3. Set `PUBLIC_API_BASE` in Railway env (points at the Railway backend URL —
   this is the URL that appears inside customer emails and 302-redirects
   to Stripe).
4. Add **GitHub Actions repository secrets**: `CRON_JOB_JWT_SECRET` (same
   value as Railway) and `SELF_URL` (the Railway backend base URL). `SELF_URL`
   is NOT a Railway env var — it belongs to the Actions runner.
5. **Run the preflight verifier from your laptop** (safe — read-only + dry-run only):
   ```bash
   export SELF_URL="https://<your-railway-domain>"
   export CRON_JOB_JWT_SECRET="<the secret you set on Railway>"
   python scripts/preflight_balance_cron.py
   ```
   All 7 checks must PASS before relying on the schedule. Exit code 0 = green.
6. In the GitHub Actions tab, run **"Daily balance invoicing" → Run workflow**
   with `dry_run` ticked. Confirm a green run + `HTTP 200` + `"dry_run": true`
   summary in the logs.
7. Run it once more without `dry_run` (a real pass), then confirm a
   `cron_runs` row with `dry_run=false, ok=true, error_count=0`. The daily
   `0 8 * * *` schedule then runs on its own; failures show as red runs in
   the Actions history (GitHub emails repo admins).

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

1. **Immediate pause:** disable the GitHub Actions workflow ("Daily balance
   invoicing" → ⋯ → Disable workflow), or comment out the `schedule:` block.
   No invoices fire, no reminders fire. Manual payment collection continues
   as before (existing client-side booking flow untouched).
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

