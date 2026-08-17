-- Migration 008 — rate_limit_events (persist 429 forensics for queryable history)
--
-- Purpose: today the layered rate limiter (booking.py) logs every 429 to
-- pod stderr with the raw client-identifying headers. That's forensic-grade
-- when an incident is happening in real time, but pod stderr rotates and
-- can't be queried after the fact. This table captures the same signal
-- durably so:
--   * a small admin dashboard (when it exists) can graph attack shapes
--     over time
--   * post-incident forensics don't depend on log retention being intact
--
-- PII minimisation (user directive 2026-02):
--   * `email_hash` stores a truncated SHA-256 of lower(email), NOT plaintext.
--     Investigations start from a suspect email → compute the same hash →
--     query. No lookup table is persisted; the investigator's own knowledge
--     of the suspect email IS the lookup, deliberately.
--   * `ip` and the raw header snapshots ARE stored — they're operational
--     security data (GDPR recital 49). Correlation across attempts is the
--     entire point of the table.
--
-- Data retention:
--   * TTL: rows older than 30 days are deleted by the lazy-purge query in
--     booking.py::_log_bypass_forensics (fires ~once per 429). If real
--     attack volume ever demands, replace with a pg_cron job. The 30-day
--     window is deliberately short — enough for incident correlation but
--     not a long-term store of who-tried-to-book-what.
--   * Access: RLS enabled, no policies. Only service-role (server-side)
--     reads/writes. The upcoming admin dashboard MUST use the service-role
--     key via the backend API, never expose this table via the anon key.
--
-- Introspection to verify AFTER applying:
--   SELECT to_regclass('public.rate_limit_events');
--   SELECT relrowsecurity FROM pg_class WHERE relname = 'rate_limit_events';
--   SELECT indexname FROM pg_indexes WHERE tablename = 'rate_limit_events'
--     ORDER BY indexname;
--
-- Cross-reference: booking.py::_log_bypass_forensics writes to this table.

CREATE TABLE IF NOT EXISTS public.rate_limit_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

  -- One of: per_email, per_ip, global_attempts,
  --         locks_per_email, locks_per_ip, locks_global
  reason TEXT NOT NULL,

  -- SHA-256(lower(email))[:16] — see booking.py::_hash_email.
  -- Deliberately NOT reversible; investigations start from the suspect
  -- email, hash it, and query.
  email_hash TEXT,

  ip TEXT,                  -- best-effort client IP (see _client_ip caveats)
  x_forwarded_for TEXT,     -- raw header, unmodified — the forensic gold
  x_real_ip TEXT,           -- raw header, unmodified
  user_agent TEXT,          -- truncated to 500 chars in the app layer
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Dashboards typically want "recent events by reason" and "events for
-- this IP/email in the last hour/day".
CREATE INDEX IF NOT EXISTS idx_rate_limit_events_created
  ON public.rate_limit_events (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rate_limit_events_reason_created
  ON public.rate_limit_events (reason, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rate_limit_events_ip_created
  ON public.rate_limit_events (ip, created_at DESC)
  WHERE ip IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_rate_limit_events_email_hash_created
  ON public.rate_limit_events (email_hash, created_at DESC)
  WHERE email_hash IS NOT NULL;

ALTER TABLE public.rate_limit_events ENABLE ROW LEVEL SECURITY;
-- No policies: service-role only. See notes above.
