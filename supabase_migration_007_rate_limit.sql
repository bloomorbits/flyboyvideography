-- Migration 007 — Rate-limit table for /api/booking/checkout (SEC-001)
--
-- Purpose: durable, restart-safe rate-limiting so a bot cannot freeze the
-- calendar by looping the un-authenticated checkout endpoint. Chosen over
-- an in-memory sliding window per user directive on 2026-02: in-memory
-- state does not survive a backend restart and does not scale across
-- multiple backend instances if we ever move beyond one process.
--
-- Access model: RLS enabled, no grants to anon/authenticated. The service-
-- role key (server-side only) is the sole reader/writer.
--
-- Retention: rows are kept for 24 hours (a purge is performed lazily on
-- every checkout call inside a 24h+ window). We do not need historical
-- data — the rate limiter reads only the last 15 minutes.
--
-- Introspection to verify AFTER applying:
--   SELECT to_regclass('public.checkout_attempts');   -- expect: checkout_attempts
--   SELECT indexname FROM pg_indexes WHERE tablename = 'checkout_attempts';

CREATE TABLE IF NOT EXISTS public.checkout_attempts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ip TEXT NOT NULL,
  email TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- The rate limiter's hot path queries the most recent N rows per IP
-- (last 15 minutes). A descending index on (ip, created_at) makes this
-- an index-only skip scan.
CREATE INDEX IF NOT EXISTS idx_checkout_attempts_ip_created
  ON public.checkout_attempts (ip, created_at DESC);

-- Same for the per-email cap (case-insensitive so a bot cannot bypass
-- the email cap by varying case).
CREATE INDEX IF NOT EXISTS idx_checkout_attempts_email_created
  ON public.checkout_attempts (lower(email), created_at DESC);

-- Keep the table clean without a cron. Any row older than 24 hours is
-- deleted on the next checkout call from the same IP or email.
CREATE INDEX IF NOT EXISTS idx_checkout_attempts_created
  ON public.checkout_attempts (created_at);

ALTER TABLE public.checkout_attempts ENABLE ROW LEVEL SECURITY;
-- Intentionally no policies: only service-role (which bypasses RLS) can
-- read or write this table. If a client-side call ever hits it with the
-- anon key, RLS returns an empty set — which is the right behaviour.


-- ---- Concurrent-active-lock cap requires knowing which IP holds each
-- lock. Add an `ip` column to date_slot_locks so the rate limiter can
-- count `WHERE ip = ? AND expires_at > NOW()`. Nullable because rows
-- inserted before this migration have no IP recorded — the limiter
-- treats NULL as "unknown, don't count against the cap".

ALTER TABLE public.date_slot_locks ADD COLUMN IF NOT EXISTS ip TEXT;

CREATE INDEX IF NOT EXISTS idx_date_slot_locks_ip_expires
  ON public.date_slot_locks (ip, expires_at)
  WHERE ip IS NOT NULL;

-- Verification queries (run these AFTER applying to confirm):
--
--   SELECT to_regclass('public.checkout_attempts');
--   -- expect: checkout_attempts
--
--   SELECT indexname FROM pg_indexes
--     WHERE tablename = 'checkout_attempts' ORDER BY indexname;
--   -- expect 4 rows:
--   --   checkout_attempts_pkey
--   --   idx_checkout_attempts_created
--   --   idx_checkout_attempts_email_created
--   --   idx_checkout_attempts_ip_created
--
--   SELECT relrowsecurity FROM pg_class
--     WHERE relname = 'checkout_attempts';
--   -- expect: t
--
--   SELECT column_name FROM information_schema.columns
--     WHERE table_name = 'date_slot_locks' AND column_name = 'ip';
--   -- expect: ip
