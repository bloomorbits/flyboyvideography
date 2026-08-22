-- Migration 012: balance invoicing schema
--
-- Adds columns + a partial unique index to invoices so the scheduled
-- daily-invoicing job can create exactly one balance invoice per
-- booking, physically enforced at the DB level rather than app-checked.
--
-- See docs (PRD.md § Balance Invoicing) and the phased build plan for
-- why we're doing this at the DB layer: if the daily cron fires twice
-- (retry, Railway restart mid-run, human trigger racing cron), the
-- second insert must fail cleanly, not create a duplicate invoice and
-- send a second email to a real client.
--
-- Idempotent: uses IF NOT EXISTS everywhere.

-- 1. payment_purpose: 'deposit' | 'balance' | NULL (legacy/seed).
--    Nullable because existing rows predate this concept; forward
--    balance invoices will always set it explicitly.
ALTER TABLE public.invoices
    ADD COLUMN IF NOT EXISTS payment_purpose TEXT;

-- 2. reminder_sent_at: single-fire reminder timestamp for the daily job.
--    IS NULL check is the idempotency guard for the reminder branch.
ALTER TABLE public.invoices
    ADD COLUMN IF NOT EXISTS reminder_sent_at TIMESTAMPTZ;

-- 3. Partial unique index: one balance invoice per booking, ever.
--    Scoped by payment_purpose='balance' so this doesn't conflict with:
--      - existing deposit invoices (payment_purpose IS NULL or 'deposit')
--      - future subscription invoices (source_type='subscription')
--      - seed data (is_seed_data=true)
--    Physical DB enforcement — makes the duplicate-cron-fire scenario
--    impossible, not merely "checked in Python".
CREATE UNIQUE INDEX IF NOT EXISTS invoices_one_balance_per_booking_uniq
    ON public.invoices (booking_id)
    WHERE payment_purpose = 'balance'
      AND is_seed_data = FALSE;

COMMENT ON COLUMN public.invoices.payment_purpose IS
    'deposit | balance | NULL. Set by the balance-invoicing scheduler and by Stripe metadata on balance checkout sessions. See Migration 012.';
COMMENT ON COLUMN public.invoices.reminder_sent_at IS
    'When the single reminder email was sent (idempotency guard: WHERE IS NULL). See Migration 012.';
COMMENT ON INDEX public.invoices_one_balance_per_booking_uniq IS
    'Physical guard against double-invoicing when the daily cron fires twice. See Migration 012.';
