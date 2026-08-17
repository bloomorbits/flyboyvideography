-- Migration 009 — contact enquiries + independent rate limiter
--
-- Two tables, deliberately separate from the booking flow's ledger so
-- future tuning of the contact-form threat model doesn't leak into the
-- booking flow's threshold decisions (user directive 2026-02: "booking
-- spam ties up real calendar dates and Stripe sessions, contact-form
-- spam just fills an inbox").
--
-- Introspection to verify AFTER applying:
--   SELECT to_regclass('public.contact_enquiries');
--   SELECT to_regclass('public.contact_attempts');
--   SELECT relrowsecurity FROM pg_class
--     WHERE relname IN ('contact_enquiries','contact_attempts');
--   -- both should be `t`

-- --------- contact_enquiries: durable record of every enquiry submitted
CREATE TABLE IF NOT EXISTS public.contact_enquiries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  email TEXT NOT NULL,
  package_id TEXT,           -- may be null; prefilled from ?package= deep link
  event_date DATE,           -- may be null; optional field
  message TEXT NOT NULL,
  source_url TEXT,           -- referring page (portfolio/services/home/etc.)
  status TEXT NOT NULL DEFAULT 'new',   -- new | replied | archived | spam
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contact_enquiries_created
  ON public.contact_enquiries (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_contact_enquiries_status_created
  ON public.contact_enquiries (status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_contact_enquiries_email
  ON public.contact_enquiries (lower(email));

ALTER TABLE public.contact_enquiries ENABLE ROW LEVEL SECURITY;
-- No policies: service-role writes (via /api/contact/enquire), admin reads
-- via /api/admin/enquiries (future). No anon exposure.

-- --------- contact_attempts: independent rate-limit ledger (see booking.py
-- for the analogous checkout_attempts table). Intentional separation per
-- user directive so contact thresholds can be tuned independently.
CREATE TABLE IF NOT EXISTS public.contact_attempts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ip TEXT NOT NULL,
  email TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_contact_attempts_ip_created
  ON public.contact_attempts (ip, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_contact_attempts_email_created
  ON public.contact_attempts (lower(email), created_at DESC);
CREATE INDEX IF NOT EXISTS idx_contact_attempts_created
  ON public.contact_attempts (created_at);

ALTER TABLE public.contact_attempts ENABLE ROW LEVEL SECURITY;
-- Service-role only; RLS on with no policies blocks anon path by default.
