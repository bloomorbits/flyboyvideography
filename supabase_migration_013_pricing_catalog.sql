-- Migration 013 — Admin-editable pricing catalog
--
-- Adds a two-slot (draft / published) pricing catalog table. The current
-- pricing.js content is seeded into BOTH slots at migration time so the
-- public API (Phase 2, added after this migration lands) returns identical
-- data to what the site is compiled with right now — zero-drift cutover.
--
-- Model:
--   pricing_catalog.slot = 'draft'      — admin-editable working copy
--   pricing_catalog.slot = 'published'  — live source of truth read by:
--                                          - the public /api/pricing endpoint
--                                          - the Next.js /services page (with ISR)
--                                          - backend booking.py (via packages.py cache)
--
-- Publish workflow: admin edits draft → clicks Publish → backend copies
-- draft.content over published.content in a single UPDATE (atomic swap).
-- No history table for now; if we need version history later, a small
-- `pricing_catalog_history` table + trigger is the natural extension.
--
-- RLS: anon + authenticated may SELECT the 'published' row (needed for the
-- public site fetch). Draft is service-role only (admin backend routes).
--
-- SEED SAFETY: uses INSERT ... ON CONFLICT DO NOTHING so re-running this
-- migration in an env that already has pricing_catalog rows won't clobber
-- them. If you actually want to reset to the seed, DELETE the rows first.

begin;

-- ------------------------------------------------------------------------
-- 1) Table + constraint
-- ------------------------------------------------------------------------
create table if not exists public.pricing_catalog (
    slot         text primary key check (slot in ('draft', 'published')),
    content      jsonb not null,
    updated_at   timestamptz not null default now(),
    updated_by   uuid references auth.users(id) on delete set null
);

comment on table public.pricing_catalog is
  'Two-slot pricing catalog (Migration 013). draft = admin-editable; '
  'published = live source of truth for /api/pricing, /services, and booking checkout.';

-- ------------------------------------------------------------------------
-- 2) updated_at trigger — bump on every UPDATE
-- ------------------------------------------------------------------------
create or replace function public.tg_pricing_catalog_bump_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end
$$;

drop trigger if exists pricing_catalog_bump_updated_at on public.pricing_catalog;
create trigger pricing_catalog_bump_updated_at
before update on public.pricing_catalog
for each row execute function public.tg_pricing_catalog_bump_updated_at();

-- ------------------------------------------------------------------------
-- 3) RLS
-- ------------------------------------------------------------------------
alter table public.pricing_catalog enable row level security;

drop policy if exists pricing_read_published on public.pricing_catalog;
create policy pricing_read_published on public.pricing_catalog
  for select
  using (slot = 'published');

-- Service role bypasses RLS by design. All draft-editing and publish
-- actions go through backend admin routes that use the service-role key.
-- We intentionally do NOT create an authenticated-write policy — the admin
-- surface is API-mediated, not direct-to-DB.

-- ------------------------------------------------------------------------
-- 4) Seed BOTH slots with current pricing.js content (byte-for-byte)
--    ON CONFLICT DO NOTHING → safe to re-run.
-- ------------------------------------------------------------------------
insert into public.pricing_catalog (slot, content) values
(
  'published',
  jsonb_build_object(
    'packages', jsonb_build_array(
      jsonb_build_object(
        'id', 'wedding',
        'title', 'Wedding Videography',
        'tiers', jsonb_build_array(
          jsonb_build_object(
            'name', 'Basic',
            'price', 250,
            'coverage', '3 hours coverage',
            'features', jsonb_build_array(
              'Pre-event consultation',
              '1 highlight film (60–90 seconds)',
              'High-resolution delivery',
              'Delivered within 7 days'
            )
          ),
          jsonb_build_object(
            'name', 'Classic',
            'price', 400,
            'coverage', '6 hours coverage',
            'popular', true,
            'leadIn', 'Everything in Basic, plus:',
            'features', jsonb_build_array(
              'An additional 3–5 minute cinematic highlight film (alongside your 60–90 second social reel)',
              'Key moments captured — ceremony, speeches, cake cutting, and more',
              'Online gallery delivery'
            )
          ),
          jsonb_build_object(
            'name', 'Royale',
            'price', 700,
            'coverage', 'Full-day coverage (10–12 hours)',
            'leadIn', 'Everything in Classic, plus:',
            'features', jsonb_build_array(
              'Extended full-day coverage',
              'A third film — a 5–8 minute highlight film',
              'Delivered within 7–14 days'
            )
          )
        )
      ),
      jsonb_build_object(
        'id', 'birthday',
        'title', 'Birthday Celebration',
        'tiers', jsonb_build_array(
          jsonb_build_object(
            'name', 'Basic',
            'price', 250,
            'coverage', '3 hours coverage',
            'features', jsonb_build_array(
              'Pre-event consultation',
              '1 highlight film (60–90 seconds)',
              'High-resolution delivery',
              'Delivered within 7 days'
            )
          ),
          jsonb_build_object(
            'name', 'Classic',
            'price', 400,
            'coverage', '6 hours coverage',
            'popular', true,
            'leadIn', 'Everything in Basic, plus:',
            'features', jsonb_build_array(
              'An additional 3–5 minute cinematic highlight film',
              'Key moments captured — cake cutting, speeches, entrances, and more',
              'Online gallery delivery'
            )
          ),
          jsonb_build_object(
            'name', 'Royale',
            'price', 700,
            'coverage', 'Full-day coverage (10–12 hours)',
            'leadIn', 'Everything in Classic, plus:',
            'features', jsonb_build_array(
              'Extended full-day coverage',
              'A third film — a 5–8 minute highlight film',
              'Delivered within 7–14 days'
            )
          )
        )
      ),
      jsonb_build_object(
        'id', 'naming-ceremony',
        'title', 'Naming Ceremony & Gender Reveal',
        'hoursOnly', true,
        'tiers', jsonb_build_array(
          jsonb_build_object('name', 'Basic',   'price', 200, 'coverage', '2 hours coverage'),
          jsonb_build_object('name', 'Classic', 'price', 300, 'coverage', '4 hours coverage'),
          jsonb_build_object('name', 'Royale',  'price', 450, 'coverage', '6 hours coverage')
        )
      ),
      jsonb_build_object(
        'id', 'lifestyle',
        'title', 'Lifestyle Shoot',
        'hoursOnly', true,
        'tiers', jsonb_build_array(
          jsonb_build_object('name', 'Basic',   'price', 200, 'coverage', '2 hours coverage'),
          jsonb_build_object('name', 'Classic', 'price', 300, 'coverage', '4 hours coverage'),
          jsonb_build_object('name', 'Royale',  'price', 450, 'coverage', '6 hours coverage')
        )
      )
    ),
    'graduation', jsonb_build_object(
      'id', 'graduation',
      'title', 'Graduation Reels',
      'price', 150,
      'coverage', '1.5 hours coverage',
      'features', jsonb_build_array(
        '1 edited 30–45 second video',
        '5 edited photos'
      )
    ),
    'extras', jsonb_build_object(
      'title', 'Extra Reels',
      'subtitle', 'Add to any package',
      'items', jsonb_build_array(
        jsonb_build_object('label', '60–90 second reel', 'price', 50),
        jsonb_build_object('label', '3–5 minute reel',   'price', 100),
        jsonb_build_object('label', '5–8 minute reel',   'price', 200)
      )
    ),
    'bookingTerms', 'A 50% deposit secures your date. The remaining balance is due 3–5 days before your event.'
  )
)
on conflict (slot) do nothing;

-- Draft slot starts as an exact clone of published — so the admin panel
-- opens with "no unpublished changes" on first load.
insert into public.pricing_catalog (slot, content)
select 'draft', content
from public.pricing_catalog
where slot = 'published'
on conflict (slot) do nothing;

commit;
