-- ============================================================
-- MIGRATION 004 — Client contact details
-- Run in: Supabase Dashboard → SQL Editor (idempotent)
-- ============================================================
alter table public.clients add column if not exists phone text;
