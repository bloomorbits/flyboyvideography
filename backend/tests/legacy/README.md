# Legacy / archived tests — NOT part of the default suite

These files are **archived snapshots** from earlier build sessions (≈Aug 2026,
iterations 3–5). They are excluded from the default `pytest backend/tests/`
run via `norecursedirs = legacy` in `/app/pytest.ini`.

## Why they're here (and not deleted)

They still document the intent/behaviour of features built in those sessions,
but they can no longer pass as-is because they depend on data that no longer
exists:

- `backend_test.py`, `iteration3_test.py`, `iteration4_test.py`,
  `iteration5_test.py` — hardcode the **purged demo client**
  (`demo.client.frameform@gmail.com`) and specific hand-seeded rows
  (client A–D, "Q3 Teaser"/"May Recap" deliverables, GDPR erase-of-client-D).
  Those accounts/rows were erased in a later end-to-end purge, so setup now
  fails with `400 invalid_credentials` or missing-seed assertions. Some also
  read a legacy empty env URL (`requests MissingSchema`).
- `test_bunny.py` — a **runnable script**, not a pytest module: it executes at
  import and calls `sys.exit()`, which aborts pytest collection. The real,
  maintained Bunny coverage is the live-infra sim runs + the client/webhook
  rate-limit sims (`sim_bunny_webhook_flood.py`) and the endpoint behaviour is
  exercised end-to-end elsewhere.

## What replaced them

The maintained suites in `backend/tests/*.py` cover the same ground against the
**current** seed (the durable `bunny.owner@seed` / admin accounts) and
self-provision + clean up their own data:
`test_revision_rounds.py`, `test_booking_flow.py`, `test_pricing_admin.py`,
`test_daily_invoicing.py`, `test_cron_*`, `test_consent_enforcement.py`,
`test_balance_finalise.py`, `test_booking_concurrency.py`, `test_health.py`.

## If you really want to run these

`pytest backend/tests/legacy/ -q` — expect failures until they're rewritten
against the current seed (low priority; superseded coverage).
