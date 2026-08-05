-- ============================================================
-- MIGRATION 002 — Seed-data flag + Erasure audit log
-- Run in: Supabase Dashboard → SQL Editor (safe to re-run; idempotent)
-- ============================================================

-- 1) is_seed_data column on every client-data table
alter table public.clients                add column if not exists is_seed_data boolean not null default false;
alter table public.bookings               add column if not exists is_seed_data boolean not null default false;
alter table public.retainer_subscriptions add column if not exists is_seed_data boolean not null default false;
alter table public.deliverables           add column if not exists is_seed_data boolean not null default false;
alter table public.review_threads         add column if not exists is_seed_data boolean not null default false;
alter table public.invoices               add column if not exists is_seed_data boolean not null default false;

-- 2) Retroactively tag EVERY test/seed record created during testing so far.
--    Explicit client IDs from this project's test sessions:
--      aacc769e-7f9e-4617-91f0-4ba445d85004  demo client  (demo.client.frameform@gmail.com)
--      a9661c12-178f-4875-aa01-6bf89bcb6785  demo admin   (flyboy.admin.demo@gmail.com)
--      e2903767-1440-47e5-a062-0b7349a398a3  Client A     (client.a@seed.flyboytest.com)
--      576baf05-7323-4ec6-8493-d9c6eff7f971  Client B     (GDPR-erased → erased-576baf05@anonymized.invalid)
update public.clients set is_seed_data = true
where id in (
  'aacc769e-7f9e-4617-91f0-4ba445d85004',
  'a9661c12-178f-4875-aa01-6bf89bcb6785',
  'e2903767-1440-47e5-a062-0b7349a398a3',
  '576baf05-7323-4ec6-8493-d9c6eff7f971'
)
   or email like '%@seed.flyboytest.com'
   or email like 'erased-%@anonymized.invalid';

-- Tag all child records belonging to seed clients (covers Client B's preserved
-- booking/deliverable/invoice, the demo client's seeded rows, and the
-- TEST_Playwright booking + TEST_ comment left by automated testing)
update public.bookings               set is_seed_data = true where client_id in (select id from public.clients where is_seed_data);
update public.retainer_subscriptions set is_seed_data = true where client_id in (select id from public.clients where is_seed_data);
update public.deliverables           set is_seed_data = true where client_id in (select id from public.clients where is_seed_data);
update public.review_threads         set is_seed_data = true where client_id in (select id from public.clients where is_seed_data);
update public.invoices               set is_seed_data = true where client_id in (select id from public.clients where is_seed_data);

-- 3) Erasure audit log (compliance record of every GDPR erasure)
--    Intentionally NO foreign key to clients: the log must stand on its own.
--    RLS: admins may read; NOBODY may write via the anon key — rows are
--    inserted only by the backend using the service_role key (bypasses RLS),
--    making the log effectively append-only from the client side.
create table if not exists public.erasure_audit_log (
  id uuid primary key default gen_random_uuid(),
  erased_client_id uuid not null,
  erased_client_previous_role text,
  anonymized_email text not null,
  performed_by_client_id uuid,
  performed_by_email text,
  bookings_preserved integer not null default 0,
  deliverables_preserved integer not null default 0,
  invoices_preserved integer not null default 0,
  created_at timestamptz not null default now()
);

alter table public.erasure_audit_log enable row level security;
drop policy if exists erasure_audit_select on public.erasure_audit_log;
create policy erasure_audit_select on public.erasure_audit_log for select
  using (public.is_admin());
-- no insert/update/delete policies on purpose (service_role writes only)

-- 4) Verification — run after the above; every count should be > 0 except
--    erasure_audit_log (0 until the next erasure is performed)
select 'clients' t, count(*) from public.clients where is_seed_data
union all select 'bookings', count(*) from public.bookings where is_seed_data
union all select 'retainer_subscriptions', count(*) from public.retainer_subscriptions where is_seed_data
union all select 'deliverables', count(*) from public.deliverables where is_seed_data
union all select 'review_threads', count(*) from public.review_threads where is_seed_data
union all select 'invoices', count(*) from public.invoices where is_seed_data;
