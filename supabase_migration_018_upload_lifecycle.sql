-- Migration 018 — In-portal direct-upload lifecycle (Phase 2)
--
-- Apply in Supabase Studio SQL Editor (production). Agent introspects AFTER
-- (backend/tests/introspect_018.py) BEFORE any dependent code is written —
-- same discipline as 013/015/016/017.
--
-- CONTEXT
-- Phase 2 lets an admin upload two files DIRECTLY from the browser to Bunny:
--   * a streaming export  -> Bunny Stream  (existing bunny_video_guid)
--   * a full-res master   -> Bunny Storage (existing bunny_storage_object key)
-- The bytes never pass through our backend. Each file uploads in its OWN lane
-- with its own retry, and the backend independently VERIFIES each with Bunny
-- before the deliverable becomes client-visible. This migration adds the
-- orchestration state those lanes need.
--
-- WHAT THIS ADDS
--   deliverables.upload_id             uuid  — correlates one prepare/complete/
--                                              orphan-sweep upload session
--   deliverables.stream_upload_state   text  — the Stream lane's state
--   deliverables.storage_upload_state  text  — the Storage lane's state
--   State machine per lane (NULL = that target is not part of this deliverable):
--     NULL -> 'pending' (prepared) -> 'uploaded' (browser reported bytes sent)
--          -> 'confirmed' (backend verified with Bunny) | 'failed'
--   A deliverable is client-visible only when every NON-NULL lane is 'confirmed'.
--
-- REUSES (no new columns)
--   * bunny_linked_at (Mig 017) — set at prepare; the clock the orphan pass uses
--     (rows stuck 'pending'/'uploaded' past 2h are recovered or cleaned).
--   * bunny_video_guid / bunny_storage_object (Mig 015) — the Bunny targets.
--   * cron_runs (Mig 014) — the orphan pass folds into job_name='bunny_reconcile'.
--
-- SAFE FOR EXISTING ROWS
--   Manually paste-GUID-linked deliverables (incl. the Phase-1 test deliverable)
--   keep NULL lane states — they are NOT upload sessions, so the orphan sweep
--   (which only touches 'pending'/'uploaded') never disturbs them. No backfill.

begin;

alter table public.deliverables
  add column if not exists upload_id uuid,
  add column if not exists stream_upload_state text,
  add column if not exists storage_upload_state text;

-- Enum-style guards (nullable). Names kept short + explicit.
alter table public.deliverables
  drop constraint if exists deliverables_stream_upload_state_chk;
alter table public.deliverables
  add constraint deliverables_stream_upload_state_chk
  check (stream_upload_state is null
         or stream_upload_state in ('pending','uploaded','confirmed','failed'));

alter table public.deliverables
  drop constraint if exists deliverables_storage_upload_state_chk;
alter table public.deliverables
  add constraint deliverables_storage_upload_state_chk
  check (storage_upload_state is null
         or storage_upload_state in ('pending','uploaded','confirmed','failed'));

comment on column public.deliverables.upload_id is
  'Correlation id for one Phase-2 direct-upload session (prepare/complete/orphan-sweep). NULL for manually paste-GUID-linked deliverables.';
comment on column public.deliverables.stream_upload_state is
  'Stream lane: NULL(not used)->pending->uploaded->confirmed|failed. Confirmed = backend GET-verified with Bunny.';
comment on column public.deliverables.storage_upload_state is
  'Storage lane: NULL(not used)->pending->uploaded->confirmed|failed. Confirmed = backend S3 HEAD-verified.';

-- Index the orphan-sweep scan: only in-flight lanes, ordered by their clock.
create index if not exists deliverables_upload_inflight_idx
  on public.deliverables (bunny_linked_at)
  where stream_upload_state in ('pending','uploaded')
     or storage_upload_state in ('pending','uploaded');

commit;
