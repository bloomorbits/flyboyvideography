-- verify_021_catalog.sql — run in Supabase SQL Editor and paste the output.
-- These checks read pg_catalog / information_schema / cron, which PostgREST
-- does NOT expose over REST (only `public` + `graphql_public` are exposed),
-- so the agent's introspect_021.py cannot read them. Everything else was
-- proven behaviourally by introspect_021.py.

-- 1) secondary_contact_phone CHECK — name + exact definition (both tables)
select conrelid::regclass::text  as table_name,
       conname                   as constraint_name,
       pg_get_constraintdef(oid) as definition
from   pg_constraint
where  conname in (
         'booking_intents_secondary_phone_e164_chk',
         'bookings_secondary_phone_e164_chk',
         'booking_intents_guest_count_chk',
         'bookings_guest_count_chk')
order  by table_name, constraint_name;

-- 2) enforce_phone_e164() has search_path pinned to public
select proname,
       proconfig as function_settings   -- expect {search_path=public}
from   pg_proc
where  proname = 'enforce_phone_e164';

-- 3) event_start_time is time without time zone + nullable (both tables)
select table_name, column_name, data_type, is_nullable
from   information_schema.columns
where  table_schema = 'public'
  and  column_name  = 'event_start_time'
order  by table_name;

-- 4) event_date / date_slot_locks unchanged (types + row count)
select 'event_date.type'  as item, data_type as value
from   information_schema.columns
where  table_schema='public' and table_name='booking_intents' and column_name='event_date'
union all
select 'date_slot_locks.rows', count(*)::text from public.date_slot_locks;

-- 5) scheduled-jobs ledger unchanged. pg_cron is NOT installed on this project;
--    scheduled jobs run from GitHub Actions and write to public.cron_runs.
--    Migration 021 must not touch it — this returns its current row count.
select 'public.cron_runs.rows' as item, count(*)::text as value from public.cron_runs;
