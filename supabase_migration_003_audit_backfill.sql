-- ============================================================
-- MIGRATION 003 — Backfilled-entry support + Client B audit backfill
-- Run in: Supabase Dashboard → SQL Editor (idempotent, safe to re-run)
-- ============================================================

-- 1) Mark reconstructed entries explicitly so the log never
--    misrepresents when it actually started operating
alter table public.erasure_audit_log add column if not exists backfilled boolean not null default false;
alter table public.erasure_audit_log add column if not exists note text;

-- 2) Backfill the ONE erasure that predates the audit log:
--    Client B (576baf05-…), erased ~2026-08-05 19:50 UTC during RLS/GDPR testing.
--    created_at is left as the INSERT time (i.e. when the backfill was made) —
--    the approximate time of the actual erasure lives in the note, so the
--    record is honest about being a reconstruction.
insert into public.erasure_audit_log
  (erased_client_id, erased_client_previous_role, anonymized_email,
   performed_by_client_id, performed_by_email,
   bookings_preserved, deliverables_preserved, invoices_preserved,
   backfilled, note)
select
  '576baf05-7323-4ec6-8493-d9c6eff7f971', 'client', 'erased-576baf05@anonymized.invalid',
  'a9661c12-178f-4875-aa01-6bf89bcb6785', 'flyboy.admin.demo@gmail.com',
  1, 1, 1,
  true,
  'BACKFILLED RECORD: erasure actually performed ~2026-08-05 19:50 UTC (automated GDPR-flow verification, seed Client B client.b@seed.flyboytest.com), before the audit log table existed. Reconstructed from testing records; counts verified against surviving rows.'
where not exists (
  select 1 from public.erasure_audit_log
  where erased_client_id = '576baf05-7323-4ec6-8493-d9c6eff7f971'
);

-- 3) Verification
select anonymized_email, backfilled, created_at, note is not null as has_note
from public.erasure_audit_log order by created_at;
