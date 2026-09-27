-- Migration 020 — Featured projects for the homepage "Recent Work" section
--
-- Apply in Supabase Studio SQL Editor (production).
--
-- CONTEXT: admins need to curate exactly which portfolio projects appear in the
-- homepage "Recent Work" section, and in what order. This adds two columns to
-- portfolio_videos:
--   is_featured    — mark a project for the homepage Recent Work section
--   featured_order — its position in that section (ascending; 0 = first)
--
-- The homepage renders the first 4 featured+active projects by featured_order
-- (public GET /api/portfolio/featured). Existing rows default to not-featured,
-- so nothing changes on the homepage until an admin features projects.
--
-- Safe to re-run (IF NOT EXISTS / idempotent).

begin;

alter table public.portfolio_videos
  add column if not exists is_featured boolean not null default false,
  add column if not exists featured_order integer not null default 0;

-- Supports the homepage query: featured + active, ordered.
create index if not exists portfolio_videos_featured_idx
  on public.portfolio_videos (featured_order, created_at)
  where is_featured = true and is_active = true;

comment on column public.portfolio_videos.is_featured is
  'Marked for the homepage Recent Work section (Migration 020).';
comment on column public.portfolio_videos.featured_order is
  'Position in the homepage Recent Work section, ascending, 0 = first (Migration 020).';

commit;
