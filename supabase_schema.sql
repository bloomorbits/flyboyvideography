-- ============================================================
-- FRAME & FORM — Client Portal Schema for Supabase
-- Run this ONCE in: Supabase Dashboard → SQL Editor → New query
-- Creates all tables + Row Level Security in the same script.
--
-- ADMIN MODEL (flagged for your review):
--   clients.role is 'client' or 'admin'.
--   public.is_admin() is a SECURITY DEFINER helper that checks the
--   caller's clients.role. Every policy is "own rows OR is_admin()",
--   so admins get broad access through the SAME anon-key RLS path.
--   RLS prevents a client from setting their own role to 'admin'
--   (see clients insert/update policies).
--   To bootstrap your first admin, after that user signs up run:
--     update public.clients set role = 'admin' where email = 'you@example.com';
--   Alternatively the FastAPI backend auto-promotes any email listed
--   in its server-only ADMIN_EMAILS env var (service_role, bypasses RLS).
-- ============================================================

create extension if not exists pgcrypto;

-- ---------- TABLES ----------

create table if not exists public.clients (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null unique references auth.users(id) on delete cascade,
  email text not null,
  full_name text,
  company text,
  role text not null default 'client' check (role in ('client','admin')),
  created_at timestamptz not null default now()
);

create table if not exists public.bookings (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  title text not null,
  shoot_type text,
  shoot_date date,
  location text,
  status text not null default 'inquiry'
    check (status in ('inquiry','confirmed','shot','in_post','delivered','cancelled')),
  budget numeric(10,2),
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists public.retainer_subscriptions (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  package_name text not null,
  monthly_price numeric(10,2) not null default 0,
  videos_per_month integer not null default 1,
  status text not null default 'active' check (status in ('active','paused','cancelled')),
  started_on date default current_date,
  renews_on date,
  created_at timestamptz not null default now()
);

create table if not exists public.deliverables (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  booking_id uuid references public.bookings(id) on delete set null,
  subscription_id uuid references public.retainer_subscriptions(id) on delete set null,
  title text not null,
  version integer not null default 1,
  status text not null default 'draft'
    check (status in ('draft','in_review','revisions_requested','approved','final_delivered')),
  video_url text,
  final_file_url text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.review_threads (
  id uuid primary key default gen_random_uuid(),
  deliverable_id uuid not null references public.deliverables(id) on delete cascade,
  client_id uuid not null references public.clients(id) on delete cascade,
  author_user_id uuid not null references auth.users(id) on delete cascade,
  author_name text,
  author_role text not null default 'client' check (author_role in ('client','admin')),
  version integer not null default 1,
  timestamp_seconds numeric(8,2),
  comment text not null,
  resolved boolean not null default false,
  created_at timestamptz not null default now()
);

create table if not exists public.invoices (
  id uuid primary key default gen_random_uuid(),
  client_id uuid not null references public.clients(id) on delete cascade,
  booking_id uuid references public.bookings(id) on delete set null,
  subscription_id uuid references public.retainer_subscriptions(id) on delete set null,
  source_type text not null check (source_type in ('booking','subscription')),
  invoice_number text not null unique,
  amount numeric(10,2) not null,
  currency text not null default 'USD',
  status text not null default 'draft' check (status in ('draft','sent','paid','overdue','void')),
  issued_on date default current_date,
  due_on date,
  created_at timestamptz not null default now(),
  -- an invoice belongs to EXACTLY one of: a booking, or a subscription
  constraint invoice_exactly_one_source check (
    (source_type = 'booking' and booking_id is not null and subscription_id is null) or
    (source_type = 'subscription' and subscription_id is not null and booking_id is null)
  )
);

-- ---------- INDEXES ----------
create index if not exists idx_bookings_client on public.bookings(client_id);
create index if not exists idx_subs_client on public.retainer_subscriptions(client_id);
create index if not exists idx_deliverables_client on public.deliverables(client_id);
create index if not exists idx_deliverables_booking on public.deliverables(booking_id);
create index if not exists idx_review_deliverable on public.review_threads(deliverable_id);
create index if not exists idx_review_client on public.review_threads(client_id);
create index if not exists idx_invoices_client on public.invoices(client_id);

-- ---------- RLS HELPERS (SECURITY DEFINER avoids policy recursion) ----------

create or replace function public.current_client_id()
returns uuid
language sql stable security definer set search_path = public
as $$ select id from public.clients where user_id = auth.uid(); $$;

create or replace function public.is_admin()
returns boolean
language sql stable security definer set search_path = public
as $$ select exists(select 1 from public.clients where user_id = auth.uid() and role = 'admin'); $$;

-- ---------- ROW LEVEL SECURITY ----------

alter table public.clients enable row level security;
alter table public.bookings enable row level security;
alter table public.retainer_subscriptions enable row level security;
alter table public.deliverables enable row level security;
alter table public.review_threads enable row level security;
alter table public.invoices enable row level security;

-- clients: see/edit only own profile; cannot self-assign admin role
drop policy if exists clients_select on public.clients;
create policy clients_select on public.clients for select
  using (user_id = auth.uid() or public.is_admin());
drop policy if exists clients_insert on public.clients;
create policy clients_insert on public.clients for insert
  with check (user_id = auth.uid() and role = 'client');
drop policy if exists clients_update on public.clients;
create policy clients_update on public.clients for update
  using (user_id = auth.uid() or public.is_admin())
  with check ((user_id = auth.uid() and role = 'client') or public.is_admin());

-- bookings: clients read own + can submit booking requests; only admin edits/deletes
drop policy if exists bookings_select on public.bookings;
create policy bookings_select on public.bookings for select
  using (client_id = public.current_client_id() or public.is_admin());
drop policy if exists bookings_insert on public.bookings;
create policy bookings_insert on public.bookings for insert
  with check (client_id = public.current_client_id() or public.is_admin());
drop policy if exists bookings_update on public.bookings;
create policy bookings_update on public.bookings for update
  using (public.is_admin()) with check (public.is_admin());
drop policy if exists bookings_delete on public.bookings;
create policy bookings_delete on public.bookings for delete
  using (public.is_admin());

-- retainer_subscriptions: clients read own; admin-only writes
drop policy if exists subs_select on public.retainer_subscriptions;
create policy subs_select on public.retainer_subscriptions for select
  using (client_id = public.current_client_id() or public.is_admin());
drop policy if exists subs_write on public.retainer_subscriptions;
create policy subs_write on public.retainer_subscriptions for all
  using (public.is_admin()) with check (public.is_admin());

-- deliverables: clients read own; admin-only writes
drop policy if exists deliv_select on public.deliverables;
create policy deliv_select on public.deliverables for select
  using (client_id = public.current_client_id() or public.is_admin());
drop policy if exists deliv_write on public.deliverables;
create policy deliv_write on public.deliverables for all
  using (public.is_admin()) with check (public.is_admin());

-- review_threads: clients read own threads, comment as themselves on own deliverables
drop policy if exists review_select on public.review_threads;
create policy review_select on public.review_threads for select
  using (client_id = public.current_client_id() or public.is_admin());
drop policy if exists review_insert on public.review_threads;
create policy review_insert on public.review_threads for insert
  with check (
    (client_id = public.current_client_id() and author_user_id = auth.uid() and author_role = 'client')
    or public.is_admin()
  );
drop policy if exists review_update on public.review_threads;
create policy review_update on public.review_threads for update
  using (client_id = public.current_client_id() or public.is_admin())
  with check (client_id = public.current_client_id() or public.is_admin());
drop policy if exists review_delete on public.review_threads;
create policy review_delete on public.review_threads for delete
  using (author_user_id = auth.uid() or public.is_admin());

-- invoices: clients read own; admin-only writes (payments/status managed server-side)
drop policy if exists invoices_select on public.invoices;
create policy invoices_select on public.invoices for select
  using (client_id = public.current_client_id() or public.is_admin());
drop policy if exists invoices_write on public.invoices;
create policy invoices_write on public.invoices for all
  using (public.is_admin()) with check (public.is_admin());
