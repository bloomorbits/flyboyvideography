-- Migration 017 — Bunny webhook backfill / reconciliation support
--
-- Apply in Supabase Studio SQL Editor (production). Agent introspects AFTER
-- (backend/tests/introspect_017.py) BEFORE any dependent code is written —
-- same discipline as Migrations 013/015/016.
--
-- WHY THIS EXISTS
-- The Bunny Stream webhook (/api/bunny/webhook) updates deliverables.bunny_status
-- as an encode progresses (Queued→Processing→Encoding→Finished/Failed). If a
-- webhook is missed (backend redeploying, Bunny retry exhausted, video linked
-- before the webhook was wired), a deliverable can sit forever in a non-terminal
-- status. The reconcile job polls Bunny for exactly those stuck rows and repairs
-- them. To target ONLY genuinely-stuck rows (not videos legitimately mid-encode),
-- we need to know how long a row has been linked to Bunny.
--
-- WHAT THIS ADDS (schema)
--   deliverables.bunny_linked_at timestamptz
--     Set to now() at the moment bunny_video_guid is first assigned (the code
--     that links a deliverable to its Bunny video will set this — added with the
--     dependent code, not here). This is the accurate clock for "stuck > N min".
--     - created_at is WRONG for this: a deliverable row often exists days before
--       its video is uploaded, which would make every old row look "stuck".
--     - updated_at is WRONG for this: it resets on every bunny_status write, so
--       a row updated by the webhook 1s ago would never look stuck.
--
-- WHAT THIS DOES NOT ADD (deliberately)
--   * NO new cron table — the reconcile job REUSES public.cron_runs (Migration
--     014) with job_name='bunny_reconcile'. cron_runs.job_name is a free string
--     built for exactly this (see its Migration 014 header). Same per-run history,
--     same dashboard observability path.
--   * NO new column for failed encodes — deliverables.bunny_status (Migration 015)
--     already stores 'Failed'. The admin dashboard attention band will query that
--     directly (new tile, code-only).
--
-- RECONCILE TARGET SET (enforced in code, documented here):
--   deliverables WHERE bunny_video_guid IS NOT NULL
--     AND bunny_status IS NULL OR bunny_status IN ('Queued','Processing','Encoding')
--     AND bunny_linked_at < now() - interval '15 minutes'  (BUNNY_RECONCILE_STALE_MINUTES)
--   Terminal rows ('Finished','ResolutionFinished','Failed') are NEVER re-polled.

begin;

-- ---------------------------------------------------------------------------
-- 1) The accurate "linked to Bunny at" clock
-- ---------------------------------------------------------------------------
alter table public.deliverables
  add column if not exists bunny_linked_at timestamptz;

comment on column public.deliverables.bunny_linked_at is
  'When bunny_video_guid was first assigned (set by the link code, Migration 017). '
  'The clock the reconcile job uses to find encodes stuck past the stale threshold. '
  'NULL for deliverables never linked to a Bunny video.';

-- ---------------------------------------------------------------------------
-- 2) Backfill EXISTING linked rows so an old stuck encode gets reconciled once.
--    created_at is only used as the backfill seed for pre-existing rows (best
--    available past timestamp) — new rows get an accurate now() from the code.
--    coalesce guards the (unlikely) case created_at is null.
-- ---------------------------------------------------------------------------
update public.deliverables
   set bunny_linked_at = coalesce(created_at, now())
 where bunny_video_guid is not null
   and bunny_linked_at is null;

-- ---------------------------------------------------------------------------
-- 3) Index the exact reconcile scan: linked rows, ordered by their clock.
--    Partial (only Bunny-linked rows) keeps it tiny.
-- ---------------------------------------------------------------------------
create index if not exists deliverables_bunny_reconcile_idx
  on public.deliverables (bunny_status, bunny_linked_at)
  where bunny_video_guid is not null;

commit;
