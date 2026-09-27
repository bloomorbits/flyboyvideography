-- Migration 019 — Global site settings (admin-editable, DB-backed)
--
-- Apply in Supabase Studio SQL Editor (production).
--
-- CONTEXT: the homepage hero background must be an admin-editable YouTube
-- video that goes live WITHOUT a code deploy. This adds a small generic
-- key/value settings table (room to grow for other global toggles) and
-- seeds the one setting we need now: hero_video.
--
-- Model: one row per setting key. value is JSONB so a setting can hold more
-- than a scalar later (e.g. hero_video could gain a poster/override field).
--
-- READ PATH: the public GET /api/site-settings/hero-video (backend, service
-- role) reads this; the Next.js homepage fetches that endpoint with ISR (60s)
-- so an admin edit is live within a minute. WRITE PATH: PUT
-- /api/admin/site-settings/hero-video (admin-guarded) upserts here.
--
-- RLS: service role (backend) bypasses RLS for all reads/writes. A narrow
-- anon SELECT policy is added as defence-in-depth only (hero_video is public
-- info anyway); all writes stay API-mediated, never direct-to-DB.
--
-- SEED SAFETY: INSERT ... ON CONFLICT DO NOTHING — safe to re-run.

begin;

-- ------------------------------------------------------------------------
-- 1) Table
-- ------------------------------------------------------------------------
create table if not exists public.site_settings (
    key         text primary key,
    value       jsonb not null default '{}'::jsonb,
    updated_at  timestamptz not null default now(),
    updated_by  uuid references auth.users(id) on delete set null
);

comment on table public.site_settings is
  'Generic global site settings (Migration 019). One row per key; value is '
  'JSONB. API-mediated writes only (admin routes, service role).';

-- ------------------------------------------------------------------------
-- 2) updated_at trigger — bump on every UPDATE (incl. upsert-as-update)
-- ------------------------------------------------------------------------
create or replace function public.tg_site_settings_bump_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end
$$;

drop trigger if exists site_settings_bump_updated_at on public.site_settings;
create trigger site_settings_bump_updated_at
before update on public.site_settings
for each row execute function public.tg_site_settings_bump_updated_at();

-- ------------------------------------------------------------------------
-- 3) RLS — narrow anon read (defence-in-depth); writes are service-role only
-- ------------------------------------------------------------------------
alter table public.site_settings enable row level security;

drop policy if exists site_settings_read_public on public.site_settings;
create policy site_settings_read_public on public.site_settings
  for select
  using (true);

-- ------------------------------------------------------------------------
-- 4) Seed the hero_video setting with the owner-supplied default video.
--    Shape: { youtube_video_ids: [...], poster_url: null }. The backend also
--    reads a legacy { youtube_video_id } scalar for safety.
--    ON CONFLICT DO NOTHING → safe to re-run.
-- ------------------------------------------------------------------------
insert into public.site_settings (key, value) values
  ('hero_video', jsonb_build_object(
     'youtube_video_ids', jsonb_build_array('MVE91GRuDVs'),
     'poster_url', null
   ))
on conflict (key) do nothing;

commit;
