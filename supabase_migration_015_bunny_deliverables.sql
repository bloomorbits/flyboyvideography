-- Migration 015 — Bunny.net Phase 1 schema
-- Apply in Supabase Studio SQL Editor (production). Agent introspects after
-- via backend/tests/introspect_015.py BEFORE any dependent code is written.
--
-- Two parts:
--   015a — link deliverables to their Bunny assets
--   015b — deliverable access-event log (service-role only, like cron_runs)

-- ---------------------------------------------------------------------------
-- 015a: link deliverables to their Bunny assets
-- ---------------------------------------------------------------------------
alter table public.deliverables
  add column if not exists bunny_video_guid text,       -- Stream video GUID
  add column if not exists bunny_storage_object text,   -- Storage object key (e.g. "clients/<client>/<file>.mp4")
  add column if not exists bunny_status text;           -- last webhook status: 'processing' | 'finished' | 'failed' | null

-- ---------------------------------------------------------------------------
-- 015b: access log — one row per meaningful auth/action event
-- ---------------------------------------------------------------------------
create table if not exists public.deliverable_access_events (
    id             uuid primary key default gen_random_uuid(),
    deliverable_id uuid not null references public.deliverables(id) on delete cascade,
    client_id      uuid references public.clients(id) on delete set null,
    actor_role     text not null check (actor_role in ('client','admin','anonymous')),
    event_type     text not null check (event_type in (
                     'playback_url_issued', 'download_url_issued',
                     'player_play', 'player_25', 'player_50', 'player_75',
                     'player_ended', 'player_heartbeat',
                     'entitlement_denied'
                   )),
    meta           jsonb not null default '{}'::jsonb,
    created_at     timestamptz not null default now()
);

create index if not exists deliverable_access_events_deliv_idx
  on public.deliverable_access_events (deliverable_id, created_at desc);

alter table public.deliverable_access_events enable row level security;
-- No policies. Service-role only (backend routes). Same convention as
-- cron_runs / pricing_catalog draft.
