-- Migration 006: booking flow — payment tracking + slot locks + hard double-booking guard.
-- Run in the Supabase SQL Editor. Idempotent (all CREATE statements are IF NOT EXISTS
-- or use ON CONFLICT DO NOTHING patterns where relevant).
--
-- What this adds:
--   1. payment_transactions — one row per Stripe Checkout Session, our source of truth
--      for payment state independent of Stripe. Written before redirect (status=initiated),
--      flipped to paid by the webhook (idempotency guard: payment_status != 'paid').
--   2. date_slot_locks — soft, time-limited hold on a calendar date while a visitor is
--      inside Stripe Checkout. Auto-released when expires_at passes. NOT a substitute
--      for the hard double-booking guard below; just prevents two visitors seeing the
--      same date as available while one is mid-checkout.
--   3. booking_intents — carries the visitor's chosen package + date + email across the
--      Checkout redirect, keyed by session_id. The webhook reads this to build the
--      final bookings row after payment.
--   4. bookings.event_date + bookings.deposit_paid_at + bookings.stripe_session_id
--      columns so a confirmed booking carries its payment provenance.
--   5. Unique partial index on bookings(event_date) WHERE status = 'confirmed' —
--      the HARD double-booking guard. Even if two webhooks fire in the same millisecond
--      for the same date, only one insert succeeds; the second raises a unique violation
--      which the backend catches and refunds automatically.

-- ---------- 1. payment_transactions ----------

create table if not exists public.payment_transactions (
    id                      uuid primary key default gen_random_uuid(),
    session_id              text unique not null,           -- Stripe Checkout Session ID
    stripe_payment_intent_id text,
    booking_intent_id       uuid,                            -- FK set below once table exists
    email                   text not null,
    amount                  numeric(10, 2) not null,         -- amount in GBP (float, per Stripe playbook)
    currency                text not null default 'gbp',
    status                  text not null default 'initiated', -- initiated | completed | failed | expired
    payment_status          text not null default 'pending',   -- pending | paid | failed | expired
    created_at              timestamptz not null default now(),
    updated_at              timestamptz not null default now()
);

create index if not exists payment_transactions_email_idx on public.payment_transactions(email);
create index if not exists payment_transactions_status_idx on public.payment_transactions(payment_status);

alter table public.payment_transactions enable row level security;

-- No client-facing read policies — payment records are backend/service-role only.
-- The public /api/booking/status/{session_id} endpoint returns only session_id + status
-- via the backend, never via direct anon PostgREST access.

-- ---------- 2. date_slot_locks ----------

create table if not exists public.date_slot_locks (
    id           uuid primary key default gen_random_uuid(),
    event_date   date not null,
    session_id   text unique not null,        -- Stripe Checkout Session that owns this lock
    email        text not null,
    expires_at   timestamptz not null,        -- typically now() + interval '5 minutes'
    created_at   timestamptz not null default now()
);

-- Query-performance index only. Deliberately NOT a partial unique index
-- with `WHERE expires_at > now()` — Postgres rejects non-IMMUTABLE
-- functions in index predicates, and `now()` is STABLE. Enforcing "one
-- active lock per date" is done at the application layer:
--   1. Availability queries filter `WHERE expires_at > now()`.
--   2. Checkout-create DELETEs expired locks for the requested date in
--      the same transaction as the INSERT of the new lock.
--   3. If a race slips through (both requests INSERT before either sees
--      the other), the HARD guarantee is `bookings_one_confirmed_per_date`
--      below, which is a proper partial unique index — one of the two
--      races will fail unique_violation at webhook time and be auto-refunded.
-- The lock table is a soft UX helper; the hard invariant is on `bookings`.
create index if not exists date_slot_locks_event_date_idx on public.date_slot_locks(event_date);
create index if not exists date_slot_locks_expires_idx    on public.date_slot_locks(expires_at);

alter table public.date_slot_locks enable row level security;
-- No public policies — locks are backend/service-role only.

-- ---------- 3. booking_intents ----------

create table if not exists public.booking_intents (
    id                 uuid primary key default gen_random_uuid(),
    session_id         text unique,                        -- populated once Stripe Session is created
    email              text not null,
    full_name          text,
    phone              text,
    package_id         text not null,                      -- e.g. 'wedding-classic', matches website/lib/pricing.js
    package_title      text not null,                      -- captured for the confirmation email + booking row
    tier_name          text,                               -- Basic / Classic / Royale (null for single-tier packages)
    price_total        numeric(10, 2) not null,            -- full package price
    price_deposit      numeric(10, 2) not null,            -- 50% deposit charged now
    event_date         date not null,
    event_notes        text,
    status             text not null default 'pending',    -- pending | paid | failed | expired
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);

create index if not exists booking_intents_email_idx on public.booking_intents(email);
create index if not exists booking_intents_status_idx on public.booking_intents(status);

alter table public.booking_intents enable row level security;
-- No public policies — intents are backend/service-role only.

-- FK payment_transactions → booking_intents (deferred to after both tables exist)
do $$ begin
    alter table public.payment_transactions
        add constraint payment_transactions_booking_intent_fk
        foreign key (booking_intent_id) references public.booking_intents(id) on delete set null;
exception when duplicate_object then null;
end $$;

-- ---------- 4. bookings — new columns for payment provenance ----------

alter table public.bookings add column if not exists event_date date;
alter table public.bookings add column if not exists deposit_paid_at timestamptz;
alter table public.bookings add column if not exists stripe_session_id text;
alter table public.bookings add column if not exists booking_intent_id uuid references public.booking_intents(id) on delete set null;

-- ---------- 5. HARD double-booking guard ----------
-- Only one confirmed booking may exist per event_date. This is enforced at the
-- database level so concurrent webhooks racing for the same date cannot both
-- succeed — exactly one insert wins, the other raises a unique_violation which
-- the webhook handler catches and issues an automatic Stripe refund on.

create unique index if not exists bookings_one_confirmed_per_date
    on public.bookings(event_date)
    where status = 'confirmed';

-- ---------- Verification ----------
-- Expected results after running this migration:
--   select count(*) from public.payment_transactions;   -- 0 (empty)
--   select count(*) from public.date_slot_locks;         -- 0 (empty)
--   select count(*) from public.booking_intents;         -- 0 (empty)
--   select column_name from information_schema.columns
--    where table_schema='public' and table_name='bookings'
--      and column_name in ('event_date','deposit_paid_at','stripe_session_id','booking_intent_id');
--   -- expect 4 rows
--   select indexname from pg_indexes
--    where tablename='bookings' and indexname='bookings_one_confirmed_per_date';
--   -- expect 1 row
