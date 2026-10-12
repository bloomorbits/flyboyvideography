-- Migration 021 — Compulsory booking details + booking-details view support
--
-- Apply in Supabase Studio SQL Editor (production = same shared project).
--
-- Adds contact/venue/time columns to booking_intents AND bookings (same shape),
-- ALL NULLABLE — existing rows are untouched and never backfilled; enforcement
-- of the required fields lives in the API for NEW checkouts only.
--
-- Phone (reused existing booking_intents.phone / clients.phone): enforced to
-- E.164 by a BEFORE INSERT OR UPDATE OF phone trigger that fires ONLY when phone
-- is non-NULL and (on UPDATE) actually changes. Legacy junk-phone rows are never
-- scanned or broken, and an UPDATE to an unrelated column on such a row succeeds.
--
-- Does NOT touch: pricing, event_date (and anything keyed to it), RLS policies,
-- Bunny/uploads. Safe to re-run (idempotent).

begin;

-- 1) New columns on BOTH tables (all nullable) -----------------------------
alter table public.booking_intents
  add column if not exists venue_name              text,
  add column if not exists venue_tbc               boolean default false,
  add column if not exists event_city              text,
  add column if not exists event_postcode          text,
  add column if not exists event_start_time        time without time zone,
  add column if not exists guest_count             integer,
  add column if not exists secondary_contact_name  text,
  add column if not exists secondary_contact_phone text;

alter table public.bookings
  add column if not exists venue_name              text,
  add column if not exists venue_tbc               boolean default false,
  add column if not exists event_city              text,
  add column if not exists event_postcode          text,
  add column if not exists event_start_time        time without time zone,
  add column if not exists guest_count             integer,
  add column if not exists secondary_contact_name  text,
  add column if not exists secondary_contact_phone text;

-- 2) Cheap CHECKs on NEW columns (no legacy data → safe to validate now).
--    Dropped-then-added so the migration is idempotent.
alter table public.booking_intents drop constraint if exists booking_intents_guest_count_chk;
alter table public.booking_intents add  constraint booking_intents_guest_count_chk
  check (guest_count is null or guest_count >= 0);
alter table public.booking_intents drop constraint if exists booking_intents_secondary_phone_e164_chk;
alter table public.booking_intents add  constraint booking_intents_secondary_phone_e164_chk
  check (secondary_contact_phone is null or secondary_contact_phone ~ '^\+[1-9][0-9]{6,14}$');

alter table public.bookings drop constraint if exists bookings_guest_count_chk;
alter table public.bookings add  constraint bookings_guest_count_chk
  check (guest_count is null or guest_count >= 0);
alter table public.bookings drop constraint if exists bookings_secondary_phone_e164_chk;
alter table public.bookings add  constraint bookings_secondary_phone_e164_chk
  check (secondary_contact_phone is null or secondary_contact_phone ~ '^\+[1-9][0-9]{6,14}$');

-- 3) Phone E.164 trigger — fires ONLY when phone is set/changed -------------
--    (so legacy junk-phone rows survive, and unrelated-column UPDATEs succeed).
create or replace function public.enforce_phone_e164()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  -- TG_OP='INSERT' short-circuits before OLD is referenced (OLD is unset on INSERT).
  if NEW.phone is not null
     and (TG_OP = 'INSERT' or NEW.phone is distinct from OLD.phone)
     and NEW.phone !~ '^\+[1-9][0-9]{6,14}$' then
    raise exception 'phone must be E.164 format (e.g. +447911123456)'
      using errcode = 'check_violation';
  end if;
  return NEW;
end
$$;

drop trigger if exists booking_intents_phone_e164 on public.booking_intents;
create trigger booking_intents_phone_e164
  before insert or update of phone on public.booking_intents
  for each row execute function public.enforce_phone_e164();

drop trigger if exists clients_phone_e164 on public.clients;
create trigger clients_phone_e164
  before insert or update of phone on public.clients
  for each row execute function public.enforce_phone_e164();

commit;
