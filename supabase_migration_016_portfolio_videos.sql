-- Migration 016 — Admin-editable YouTube portfolio
--
-- Replaces the hardcoded Pexels placeholder array (website/lib/portfolio.js)
-- with a DB-backed, admin-managed set of real YouTube embeds. The public
-- /portfolio page reads the active rows via the backend (/api/portfolio) with
-- the same 60s ISR pattern used for pricing (/services → /api/pricing).
--
-- ARCHITECTURE DECISION — DIRECT-EDIT (no draft/publish), deliberately
-- different from pricing_catalog (Migration 013):
--   * Pricing uses a two-slot draft/published swap + a referential-integrity
--     guard because wrong prices have PAYMENT/LEGAL blast radius and tiers are
--     referenced by live bookings. A bad publish there can mis-charge a client.
--   * Portfolio videos are purely presentational, have NO downstream references
--     (no bookings/invoices point at them), and a mistake is trivially and
--     instantly reversible by re-editing one row.
--   * The `is_active` flag already provides a "stage before it goes live"
--     mechanism: add a row inactive, eyeball it, then flip it active.
--   * The stated goal is "paste an ID, save, it's live" — a separate publish
--     step would fight that. ISR (60s) is the only propagation delay.
--   => Row-per-video, edited in place. If version history is ever wanted, a
--      `portfolio_videos_history` table + trigger is the natural extension.
--
-- CATEGORIES: the 5 real site categories (ids from website/lib/portfolio.js).
--   weddings | birthdays | naming | corporate | lifestyle
--   (naming = "Naming & Gender Reveal", corporate = "Corporate/Brand".)
--
-- VALIDATION (defense-in-depth, mirrors the Bunny video-extension guardrail
-- being SERVER-enforced, not just a client warning): youtube_video_id is
-- CHECK-constrained to the canonical 11-char YouTube id charset. The backend
-- admin route ALSO normalizes a pasted URL → 11-char id and rejects anything
-- that doesn't match with a 422 BEFORE it ever reaches this table.
--
-- METADATA columns (title required; description/duration_seconds/upload_date/
-- thumbnail_url nullable) are included now so VideoObject JSON-LD can be built
-- from real metadata regardless of which sourcing approach we pick (YouTube
-- Data API auto-fill, oEmbed auto-fill of title+thumbnail, or admin-entered).
-- Nullable => no re-migration needed when we wire the chosen source.
--
-- RLS: anon + authenticated may SELECT only ACTIVE rows (public site fetch).
-- All writes go through backend admin routes using the service-role key
-- (which bypasses RLS) — no direct-to-DB authenticated write policy.
--
-- SEED: intentionally EMPTY. With zero active rows per category the public
-- page keeps the honest "Placeholder" treatment for that category (fallback
-- requirement #4). The admin populates real videos via the new UI.

begin;

-- ------------------------------------------------------------------------
-- 1) Table + constraints
-- ------------------------------------------------------------------------
create table if not exists public.portfolio_videos (
    id                uuid primary key default gen_random_uuid(),
    category          text not null
                        check (category in ('weddings','birthdays','naming','corporate','lifestyle')),
    youtube_video_id  text not null
                        check (youtube_video_id ~ '^[A-Za-z0-9_-]{11}$'),
    title             text not null check (length(btrim(title)) > 0),
    description       text,
    duration_seconds  integer check (duration_seconds is null or duration_seconds >= 0),
    upload_date       date,
    thumbnail_url     text,
    display_order     integer not null default 0,
    is_active         boolean not null default true,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now()
);

comment on table public.portfolio_videos is
  'Admin-editable YouTube portfolio (Migration 016). Row-per-video, direct-edit '
  '(no draft/publish — see migration header). Public /portfolio reads active rows '
  'via /api/portfolio with 60s ISR. Empty per-category => honest placeholder fallback.';

-- ------------------------------------------------------------------------
-- 2) Indexes — ordered reads per category, active filter
-- ------------------------------------------------------------------------
create index if not exists portfolio_videos_cat_order_idx
  on public.portfolio_videos (category, display_order asc, created_at asc);
create index if not exists portfolio_videos_active_idx
  on public.portfolio_videos (is_active);

-- ------------------------------------------------------------------------
-- 3) updated_at trigger — bump on every UPDATE (same shape as pricing)
-- ------------------------------------------------------------------------
create or replace function public.tg_portfolio_videos_bump_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end
$$;

drop trigger if exists portfolio_videos_bump_updated_at on public.portfolio_videos;
create trigger portfolio_videos_bump_updated_at
before update on public.portfolio_videos
for each row execute function public.tg_portfolio_videos_bump_updated_at();

-- ------------------------------------------------------------------------
-- 4) RLS — public reads ACTIVE rows only; writes are service-role/API only
-- ------------------------------------------------------------------------
alter table public.portfolio_videos enable row level security;

drop policy if exists portfolio_read_active on public.portfolio_videos;
create policy portfolio_read_active on public.portfolio_videos
  for select
  using (is_active = true);

-- No authenticated-write policy by design: the admin surface is API-mediated
-- (backend /api/admin/portfolio/* on the service-role key), not direct-to-DB.

commit;
