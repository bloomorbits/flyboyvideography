-- Migration 010 — consent capture columns on public.bookings
--
-- Purpose: legal-compliance columns for the /book flow's consent step
-- (added in session 11). Six columns total:
--
--   1. tc_accepted_at       — timestamptz  — WHEN the customer ticked the
--                                            required T&Cs box.
--   2. tc_accepted_ip       — text         — WHERE from (via _client_ip(),
--                                            trusted per PL-INFRA-1 fix).
--   3. model_release_opted_in  — boolean, default true — the opt-out
--                                            portfolio/marketing usage
--                                            checkbox (pre-checked by
--                                            default; unticks explicitly).
--   4. minors_involved      — boolean, default false — "will anyone under
--                                            18 appear?" Yes/No radio.
--   5. safeguarding_guardian_name        — text, nullable — captured only
--                                            when minors_involved=true.
--   6. safeguarding_consent_accepted_at  — timestamptz, nullable — WHEN
--                                            the guardian ticked the
--                                            required safeguarding box.
--
-- Design rationale (user directive, 2026-02 session 11):
-- - T&Cs are the hard legal gate: nullable in DB (existing rows pre-date
--   this migration and can't be back-filled), but the API enforces NOT NULL
--   at checkout for all NEW bookings.
-- - Model release defaults TRUE because opt-out model — most clients are
--   happy with portfolio use; the flow makes uncheck a deliberate action.
-- - Minors involvement defaults FALSE — the DB should not silently assume
--   minors in the absence of a positive statement.
-- - Guardian name + safeguarding acceptance are BOTH nullable because they
--   are legitimately unset when minors_involved=false. The API enforces
--   the conditional NOT-NULL when minors_involved=true.
-- - IP is captured for audit trail (dispute resolution / GDPR requests),
--   not for ambient identification. Using text not inet so the same
--   column can store IPv4, IPv6, or "unknown" without cast dance.
--
-- Introspection to verify AFTER applying (paste into SQL Editor):
--
--   SELECT column_name, data_type, is_nullable, column_default
--   FROM information_schema.columns
--   WHERE table_schema = 'public' AND table_name = 'bookings'
--     AND column_name IN (
--       'tc_accepted_at','tc_accepted_ip','model_release_opted_in',
--       'minors_involved','safeguarding_guardian_name',
--       'safeguarding_consent_accepted_at'
--     )
--   ORDER BY column_name;
--
--   -- Expect exactly 6 rows. Nullability and defaults per this table:
--   -- tc_accepted_at                    | timestamp with time zone | YES | NULL
--   -- tc_accepted_ip                    | text                     | YES | NULL
--   -- model_release_opted_in            | boolean                  | NO  | true
--   -- minors_involved                   | boolean                  | NO  | false
--   -- safeguarding_guardian_name        | text                     | YES | NULL
--   -- safeguarding_consent_accepted_at  | timestamp with time zone | YES | NULL

ALTER TABLE public.bookings
  ADD COLUMN IF NOT EXISTS tc_accepted_at TIMESTAMPTZ;

ALTER TABLE public.bookings
  ADD COLUMN IF NOT EXISTS tc_accepted_ip TEXT;

ALTER TABLE public.bookings
  ADD COLUMN IF NOT EXISTS model_release_opted_in BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE public.bookings
  ADD COLUMN IF NOT EXISTS minors_involved BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.bookings
  ADD COLUMN IF NOT EXISTS safeguarding_guardian_name TEXT;

ALTER TABLE public.bookings
  ADD COLUMN IF NOT EXISTS safeguarding_consent_accepted_at TIMESTAMPTZ;

-- Optional partial index — queries filtering "which bookings involve minors"
-- are expected to be rare (compliance-audit context only), but the index is
-- cheap on a mostly-false column via the WHERE clause.
CREATE INDEX IF NOT EXISTS idx_bookings_minors_involved
  ON public.bookings (created_at DESC) WHERE minors_involved = TRUE;

-- No RLS changes: bookings.rls policies from migration 006 already gate
-- reads (client sees own bookings; admin sees all). The new columns follow
-- the same policy set — no additional policy needed.
