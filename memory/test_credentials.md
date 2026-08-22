# Test Credentials — Flyboy Videography Client Portal

Supabase project: https://pnqqmzszasvfnvnnonvd.supabase.co (auth + Postgres; NO MongoDB)

## Admin account (recreated 2026-06 after purge/manual auth cleanup; auto-promoted via ADMIN_EMAILS)
- Email: flyboy.admin.demo@gmail.com
- Password: AdminStudio#2026
- clients row is_seed_data=false (protected from purge)

## Client account (recreated + freshly seeded after genuine E2E purge, session 6)
- Email: demo.client.frameform@gmail.com
- Password: DemoClient#2026
- Seed data: 2 bookings, 1 retainer, 3 deliverables, 2 comments, 2 invoices (all is_seed_data=true)

## Current DB state
- Exactly 2 clients (admin + demo). Old seed clients A-D purged/erased.
- erasure_audit_log: 3 entries (B backfilled=true with note, C, D) — never purged.
- DANGER: /api/admin/purge-seed-data with confirmation "PURGE" deletes all tagged
  data including the demo client. Test the guard only (wrong text → 422).

## Notes
- Email confirmation still ENABLED in Supabase; fake domains rejected on signup.
  Create test users via GoTrue admin API with email_confirm=true, convention
  *@seed.flyboytest.com / SeedTest#2026!, always is_seed_data=true.


## Booking flow (Phase 1, session 9)
- No pre-seeded booking accounts. Each successful checkout creates a fresh
  Supabase auth user via GoTrue admin API + a clients row on the fly.
- To test the /book flow end-to-end WITHOUT charging a real card:
  - The concurrency pytest at /app/backend/tests/test_booking_concurrency.py
    mocks Stripe and directly exercises the DB race condition.
  - For a real Stripe test-mode redirect, POST /api/booking/checkout returns
    a live cs_test_... URL; the user can complete payment with card
    `4242 4242 4242 4242` and confirm the webhook fires from the Stripe
    Dashboard. Success page polls /api/booking/status/{session_id}.
- Test emails created by the flow should use *@flyboytest.com so they're
  easy to spot and delete via the GoTrue admin API afterwards.


## Rate-limit / SEC-001 test hygiene (session 9)
- The rate limiter uses a `checkout_attempts` table keyed by ip + email
  with a 15-minute sliding window and per-IP cap = 5. Automated test suites
  running from the same source IP MUST purge this table between tests, or
  hit spurious 429s on the ~6th checkout POST.
- Convention: test emails ALWAYS live on one of these domains — `@flyboytest.com`,
  `@example.com`, `@race.test`, or `@seed.flyboytest.com`. The
  autouse fixture in `tests/test_booking_flow.py` and the sim
  `tests/sim_calendar_freeze_attack.py` both purge the ledger for these
  patterns before/after they run. Any human ad-hoc probe should use one
  of these domains so it gets swept up by the same fixtures.


## Cron job authentication (session 15 — automated balance collection)

- `CRON_JOB_JWT_SECRET` is set in `backend/.env` (64-byte urlsafe). Used ONLY
  by `POST /api/admin/jobs/run-daily-invoicing`.
- Deliberately separate from admin/session tokens — narrow blast radius.
- Token requirements (all enforced by `_require_cron_token`):
  - `algorithm=HS256`
  - `aud=flyboy:cron:daily-invoicing`
  - `scope=cron:invoicing`
  - `exp` in the future (recommended: 5 min from issue)
- Mint locally:
  ```python
  import jwt, os, time
  now = int(time.time())
  print(jwt.encode({
      "aud": "flyboy:cron:daily-invoicing",
      "scope": "cron:invoicing",
      "iat": now, "exp": now + 300,
  }, os.environ["CRON_JOB_JWT_SECRET"], algorithm="HS256"))
  ```
- Production: mint a **fresh** secret on Railway; do NOT reuse the local
  pytest secret. Deploy runbook: `/app/docs/BALANCE_INVOICING_RUNBOOK.md`.
- Test flows for the endpoint live in `backend/tests/test_daily_invoicing.py`
  (guarded by `ALLOW_ATTACK_SIM=1`).

## Balance-payment test fixtures (session 15)

- `backend/tests/test_balance_finalise.py` creates one balance invoice per
  test attached to any existing booking, cleans up on teardown.
- `backend/tests/test_daily_invoicing.py` creates its own dedicated
  auth-user + client + booking + booking_intent + deposit-tx per module,
  fully cleaned up at end.
- Email domain convention: `@flyboytest.com` — same as existing tests.


## Pricing admin test account (session 15 — Migration 013)

- Email: `admin_pricing_test@flyboytest.com`
- Password: `PricingTest!2026`
- Role: `admin` (idempotent seed in `backend/tests/test_pricing_admin.py::admin_token`)
- Purpose: exercises `/api/admin/pricing/*` endpoints + the AdminPricing UI.
- Requires `SUPABASE_ANON_KEY` in env to run the tests (loaded from
  `frontend/.env` REACT_APP_SUPABASE_ANON_KEY at test time; the sign-in
  step uses a throwaway client to avoid downgrading the module-level
  service-role client — same isolation pattern the daily-invoicing tests
  now follow).
- Test suite: `ALLOW_ATTACK_SIM=1 SUPABASE_ANON_KEY=<...> pytest -v backend/tests/test_pricing_admin.py`
  21 tests, ~60s runtime.
