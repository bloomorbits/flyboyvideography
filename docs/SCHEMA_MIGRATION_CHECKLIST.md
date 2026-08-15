# Schema Migration Checklist

This document is the source of truth for how we introduce Supabase schema
changes on this project. It exists because of a specific, verifiable
mistake made in Feb 2026: SQL was generated against a migration file
(`006_bookings_payment_slots.sql`) that was committed to the repo but
never actually executed in Supabase's SQL Editor. The agent assumed the
file's presence implied its application. The database disagreed.

The rule below is short, mandatory, and cheap to run.

## The rule

**Before generating any code or SQL that assumes a not-yet-verified
migration has landed, run a live OpenAPI introspection against Supabase
and confirm the target tables and columns actually exist.** No
exceptions. "The migration file exists in the repo" is not proof.
"The user said they'd run it earlier" is not proof. Live schema is the
only proof.

## Why it matters

Committed SQL files are proposals. Live schema is state. The two drift
regularly and silently:

- Migration file committed, user hasn't opened the SQL Editor yet.
- Migration file committed, user ran it against a different project.
- Migration partially ran and errored halfway.
- Migration ran successfully but on a snapshot that was later restored.

Any of these produce code that references columns that do not exist,
which surfaces to the user as a confusing runtime error and — worse —
as a claim by the agent that "should just work."

## The check (30 seconds, copy-paste)

Run this from the preview pod any time you're about to write code or SQL
against a new-or-recently-added table or column:

```bash
python3 - <<'PY'
import os, json, urllib.request
env = {}
for line in open('/app/backend/.env'):
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1); env[k] = v
URL = env['SUPABASE_URL']; KEY = env['SUPABASE_SERVICE_ROLE_KEY']
spec = json.loads(urllib.request.urlopen(
    urllib.request.Request(URL + '/rest/v1/',
        headers={'apikey': KEY, 'Authorization': f'Bearer {KEY}'}),
    timeout=8).read())
defs = spec.get('definitions', {}) or spec.get('components', {}).get('schemas', {})

# EDIT THIS BLOCK per introspection —
EXPECTED_TABLES = ['payment_transactions', 'date_slot_locks', 'booking_intents']
EXPECTED_COLUMNS = {
    'bookings': ['event_date', 'deposit_paid_at', 'stripe_session_id', 'booking_intent_id'],
}
# ---

for t in EXPECTED_TABLES:
    print(f"  {'PRESENT' if t in defs else 'MISSING':<8} {t}")
for tbl, cols in EXPECTED_COLUMNS.items():
    present = list((defs.get(tbl) or {}).get('properties', {}).keys())
    for c in cols:
        print(f"  {'PRESENT' if c in present else 'MISSING':<8} {tbl}.{c}")
PY
```

If any row prints `MISSING`, stop. Do not write code that references it.
Ask the user to apply the migration and confirm before proceeding.

## Full migration workflow

Follow these steps in order. Do NOT skip step 5 — it's the one that was
skipped in the mistake that produced this document.

### 1. Draft the migration SQL file at the repo root

Name pattern: `supabase_migration_{NNN}_{description}.sql`. Idempotent
where possible (`create table if not exists`, `add column if not exists`,
`create index if not exists`). Include a verification-queries block at
the bottom of the file — the queries a user should run to confirm the
migration landed correctly.

### 2. Show the file to the user for review, before asking them to run it

Same standard as the Supabase migrations 002–005 and the booking
confirmation email drafts. Never surprise the user with a schema change.

### 3. Wait for explicit approval

The user's approval is a message that clearly acknowledges the migration
file itself. Not "sounds good" to a broader plan — an explicit yes on
the SQL. If they raise clarifying questions, treat those as unresolved
and answer them before proceeding.

### 4. Ask the user to run it in Supabase SQL Editor

The agent cannot run migrations directly. Cite the file path, tell them
to expect the verification queries at the bottom to return specific
counts, and give them the exact phrase to reply with — `NNN applied`
works well.

### 5. **Wait for the user's "NNN applied" reply. Then run the live introspection above and print the results.**

This is the step that was skipped. Do not assume. Do not proceed to
code that depends on the new schema before this step returns all
`PRESENT`. If the introspection shows anything `MISSING`, gently ask the
user to check the SQL Editor output — the migration may have errored
part-way or not been run against the right project.

### 6. Now, and only now, write code / SQL that references the new schema

If the introspection printed all `PRESENT`, proceed. Otherwise stop and
resolve step 5.

### 7. Log the migration in the schema migration log below

## Schema migration log

Append one row here per applied migration. Keep the log in the same
document so future agents can see, at a glance, what has actually landed
vs what's proposed.

| Migration | Applied | Verified via introspection | Notes |
|:----------|:--------|:---------------------------|:------|
| `001` base schema (`supabase_schema.sql`) | yes | yes — 6 tables + RLS | Initial project bootstrap. |
| `002` seed flag + audit | yes (user confirmed 2026-02) | yes — is_seed_data on 6 tables, erasure_audit_log added | Row counts matched expected values at time of check. |
| `003` audit backfill | yes (user confirmed 2026-02) | yes — backfilled + note columns present | Client B backfilled record correctly tagged. |
| `004` client phone | yes (user confirmed 2026-02) | yes — clients.phone present | RLS self-update policy left intact. |
| `005` revision rounds | yes (user confirmed 2026-02) | yes — 5 new columns on deliverables | `exceeds_included_rounds` is computed at query/app layer, not stored. |
| `006` booking flow (payment_transactions, date_slot_locks, booking_intents + bookings columns + unique partial index) | **yes — applied and verified 2026-02** | yes — 3 new tables PRESENT (0 rows each), bookings=15 cols with all 4 new cols PRESENT, constraint proven live: 4-step SQL test showed unique_violation on `bookings_one_confirmed_per_date` for a second `confirmed` insert on the same `event_date`, and inquiry-status same-date insert allowed (partial predicate correctly scoped) | Second-attempt success. First attempt failed on a partial unique index using `now()` in predicate (Postgres 42P17: non-IMMUTABLE function in index predicate); fixed by dropping the time-based predicate on `date_slot_locks` and moving that filter to the application layer. The hard double-booking guarantee is `bookings_one_confirmed_per_date` (uses `status='confirmed'`, immutable). The 42P17 trap is now called out in the "Failure modes this rule does NOT catch" section. |

## Failure modes this rule catches

- File in repo but never executed → `MISSING` on all expected tables/columns.
- Executed against wrong project → same signal.
- Partial application (statement failed halfway) → some `PRESENT`, some `MISSING`.
- Snapshot/restore rolled state backwards → previously-present items become `MISSING`.
- Two agents / two branches added the same column with different types → same table shows both columns; look at types.

## Failure modes this rule does NOT catch

- **Non-IMMUTABLE functions in index predicates** — Postgres rejects
  these at CREATE INDEX time with `42P17 "functions in index predicate
  must be marked IMMUTABLE"`. Common trap: using `now()`, `current_date`,
  `current_timestamp`, or any `timestamptz` comparison against them in
  a partial index `WHERE`. These are STABLE, not IMMUTABLE. The
  introspection check catches this only after the failure — it can't
  prevent the initial mistake. Rule of thumb when drafting migrations:
  if a partial index predicate references time, it will fail. Move the
  time filter to application-layer queries, or use an explicit boolean
  column that's maintained on write.

- Rename-in-place (drop-and-recreate with same name but different type / constraints)
  — the OpenAPI spec only lists column names, not types or nullability
  in usable detail. If you're doing something more subtle than
  additive changes, add a direct-SQL verification step for the specific
  constraint you introduced (e.g. attempt an insert that should fail
  the check constraint, expect a specific error).

- RLS policy changes — PostgREST does not expose `pg_policies` in the
  default schema. Verify RLS behaviour with a cross-user REST probe
  (adversarial-test style) rather than assuming the migration statement
  landed.

- Trigger/function changes — same story. Verify by exercising the
  trigger, not by trusting the DDL.
