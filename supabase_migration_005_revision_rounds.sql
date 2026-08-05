-- ============================================================
-- MIGRATION 005 — Revision-round tracking + approval record
-- Run in: Supabase Dashboard → SQL Editor (idempotent)
-- NOTE: revision-round limits were never in the original schema
-- (nothing existed to decrement) — this adds them properly.
-- ============================================================
alter table public.deliverables add column if not exists included_revision_rounds integer not null default 2;
alter table public.deliverables add column if not exists revision_rounds_used integer not null default 0;
alter table public.deliverables add column if not exists approved_by_user_id uuid;
alter table public.deliverables add column if not exists approved_by_name text;
alter table public.deliverables add column if not exists approved_at timestamptz;

-- Verification
select column_name from information_schema.columns
where table_name = 'deliverables' and column_name in
  ('included_revision_rounds','revision_rounds_used','approved_by_user_id','approved_by_name','approved_at');
