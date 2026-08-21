-- Migration 010B — mirror consent columns onto public.booking_intents
--
-- Purpose: eliminate the "transient Stripe API failure at webhook time
-- silently loses the guardian-consent record" class of bug. Per user
-- directive session 11: compliance records must never depend on a
-- non-deterministic external API being reachable at the moment we write
-- the audit trail. Same pattern already applied correctly to
-- erasure_audit_log in migration 004.
--
-- Design rationale:
-- - booking_intents is INSERTED at /api/booking/checkout time, BEFORE the
--   Stripe Checkout Session is created. Writing consent here means the
--   record lands the moment the user submits their form — no external
--   dependency, no eventual consistency.
-- - The bookings row's consent columns (Migration 010) are populated
--   FROM booking_intents at webhook-finalise time, not FROM Stripe
--   metadata. Stripe metadata is retained as defense-in-depth (a second
--   copy visible in the Stripe Dashboard for auditor cross-reference)
--   but is no longer the source of truth.
-- - If a booking never gets paid (Stripe fails or user abandons), the
--   booking_intents row (and its consent record) is rolled back / expires
--   with the intent — which is the correct behaviour: consent captured
--   for a booking that never happened is not a compliance record.
--
-- Introspection to verify AFTER applying:
--
--   SELECT column_name, data_type, is_nullable, column_default
--   FROM information_schema.columns
--   WHERE table_schema = 'public' AND table_name = 'booking_intents'
--     AND column_name IN (
--       'tc_accepted_at','tc_accepted_ip','model_release_opted_in',
--       'minors_involved','safeguarding_guardian_name',
--       'safeguarding_consent_accepted_at'
--     )
--   ORDER BY column_name;
--
--   -- Expect exactly 6 rows with the SAME nullability + defaults as the
--   -- corresponding bookings columns (Migration 010):
--   -- tc_accepted_at                    | timestamp with time zone | YES | NULL
--   -- tc_accepted_ip                    | text                     | YES | NULL
--   -- model_release_opted_in            | boolean                  | NO  | true
--   -- minors_involved                   | boolean                  | NO  | false
--   -- safeguarding_guardian_name        | text                     | YES | NULL
--   -- safeguarding_consent_accepted_at  | timestamp with time zone | YES | NULL

ALTER TABLE public.booking_intents
  ADD COLUMN IF NOT EXISTS tc_accepted_at TIMESTAMPTZ;

ALTER TABLE public.booking_intents
  ADD COLUMN IF NOT EXISTS tc_accepted_ip TEXT;

ALTER TABLE public.booking_intents
  ADD COLUMN IF NOT EXISTS model_release_opted_in BOOLEAN NOT NULL DEFAULT TRUE;

ALTER TABLE public.booking_intents
  ADD COLUMN IF NOT EXISTS minors_involved BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.booking_intents
  ADD COLUMN IF NOT EXISTS safeguarding_guardian_name TEXT;

ALTER TABLE public.booking_intents
  ADD COLUMN IF NOT EXISTS safeguarding_consent_accepted_at TIMESTAMPTZ;

-- No new indexes: booking_intents is queried by session_id (already
-- indexed) or by id (PK). The minors-audit query joins bookings, not
-- intents, so the partial index from Migration 010 covers the reporting
-- need. Adding an idx here would just be dead weight.

-- No RLS changes: booking_intents already has service-role-only access
-- from Migration 006. The new columns follow the same policy.
