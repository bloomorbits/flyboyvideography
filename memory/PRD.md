# PRD — Flyboy Videography Client Portal + Public Site

## Implemented (June 2026) — session 7 (PUBLIC SITE PIVOT)
- New SEPARATE Next.js 15 app at /app/website (App Router, TRUE SSR) — runs on
  port 3001 in this env (only port 3000 is externally routable; deploy target is
  two separate Vercel projects: public site at root domain, CRA portal on
  portal./app. subdomain, per user).
- Services & Pricing page (/services) with client's EXACT content: Wedding &
  Birthday (Basic £250/Classic £400 MOST POPULAR/Royale £700 with full
  deliverables), Naming Ceremony & Gender Reveal + Lifestyle (hours/price ONLY —
  client explicitly forbade inventing deliverables: £200/2h, £300/4h, £450/6h),
  Graduation Reels £150, Extra Reels £50/£100/£200, booking terms (50% deposit,
  balance 3–5 days before). Data in /app/website/lib/pricing.js.
- Public-site design tokens (CONFIRMED this session): bg #FAF8F4, surfaces
  #F1EBE0/#E9E1D2, ink #17140F, dark hero #141210; Space Grotesk headlines,
  Inter body, JetBrains Mono pricing/meta.
- SSR + JSON-LD (GBP OfferCatalog) verified in raw HTML; iteration_8: 100% pass,
  content verbatim, zero invented deliverables, portal + backend regression OK.

## Implemented (June 2026) — session 8 (design system layer on public site)
- Services & Pricing + home upgraded with the client's full interaction spec —
  ALL implemented, nothing cut (caveats flagged & accepted: cursor desktop-only,
  scrubber/mute are real mechanics on a simulated timeline labeled
  "Showreel · placeholder" until real reel footage arrives):
  sticky transparent→frosted nav, custom ring cursor with "view" label,
  IntersectionObserver scroll reveals, marquee dividers, dark hero (#141210)
  with drifting warm blobs + film grain + working player bar (ticking timecode,
  click-to-seek, mute toggle), headline "Turning visuals into value" (client's
  phrase), glass pricing cards (rgba white 0.45 + blur 14px + hover lift).
- iteration_9: 100% pass, zero console errors. JSON-LD "duplicate" investigated:
  only 1 real script tag; 2nd match is escaped RSC flight payload (normal Next).
- Components: /app/website/app/components/{Cursor,SiteHeader,Reveal,Marquee,HeroPlayer}.js
- CARRY FORWARD to Portfolio page: play-icon overlay + JetBrains Mono duration
  badge on video cards; stills get NO play icon (that absence distinguishes
  them); hover lift; same reveals/marquee/cursor system.
- Website dev server: cd /app/website && nohup yarn dev > /var/log/website.log 2>&1 &
  (port 3001; NOT supervisor-managed — restart manually after pod restarts).

## Implemented (Feb 2026) — session 9 (Portfolio page)
- New /portfolio route on the public Next site with hybrid video/stills grid.
- Client component: /app/website/app/components/PortfolioGrid.js
  - 6 filter chips (All + 5 categories) with live counts, ARIA tabs semantics.
  - Categories: Weddings, Birthday Celebrations, Naming & Gender Reveal,
    Corporate Events (NEW — portfolio-only, no matching services package),
    Lifestyle Reels.
  - Card rules honoured per PRD carry-forward:
    * video cards → play glyph overlay + JetBrains Mono duration badge
    * still cards → STILL badge, NO play overlay
    * both → hover lift + subtle scale, same beige/coal gradient + film grain
      as the hero (no invented imagery; every tile labelled "Placeholder")
  - Bento rhythm via optional "wide"/"tall" span per item.
- Data: /app/website/lib/portfolio.js — 15 placeholder items, 3 per category,
  each tagged kind=video|still with tone hues matching hero blobs.
- Server component wrapper: /app/website/app/portfolio/page.js
  - Metadata title/description + JSON-LD CollectionPage schema.
  - Reuses HeroPlayer (headline "Work in motion, moments held still."), Marquee,
    Reveal — no design drift.
- SiteHeader now exposes "Work" link. Home hero gets a "See the work" CTA.
- Verified in preview: SSR renders all 15 cards + all 6 filter chips + JSON-LD,
  filter switching updates card set (corporate → 3 cards: 2 video + 1 still),
  custom cursor VIEW label fires on card hover, no console errors.

## TRACKED FOLLOW-UPS (user-ordered, NOT started)
- P0 next: Contact / enquiry form on the public site (hold until Portfolio was
  accepted — user asked to hold this behind Portfolio).
- P1: PORTAL RESTYLE onto the white/black/beige token system (replace dark theme
  + cyan accent) — user said "flag as tracked follow-up, don't start today".
- P1: Subdomain deployment split (Vercel: root = Next site, portal = subdomain).
- Held: purge confirmation modal, new-cut upload flow, invoice PDFs, Stripe,
  Resend alerts, erasure request notes, approve-cut extras.


## Implemented (June 2026) — session 6
- Request Changes: POST /api/deliverables/{id}/request-changes (owner-scoped, from
  in_review/approved only, note required) — flips to revisions_requested, clears
  approval stamps, writes "[REVISION ROUND N] note" into review_threads, increments
  revision_rounds_used. FLAGGED HONESTLY: round-limit fields never existed in schema
  (nor in original brief) — migration 005 (user ran) added included_revision_rounds
  (default 2) + revision_rounds_used + approved_by_user_id/name/approved_at.
- Extra rounds: flag-but-allow per user. Surfaced: pre-submit warning banner when
  allowance exhausted, warning toast on submit, rounds chip on detail page, and
  "N extra rounds — billable" badge in admin deliverables list.
- Approval Record: approve endpoint stamps approved_by/at; shown on detail page.
- Purge transparency (user-requested verification): purge response now returns
  auth_users_deleted list + auth_users_failed_review_manually (on auth-delete
  failure the clients row is PRESERVED for retry, never silently orphaned).
  GENUINE E2E PURGE executed via the real UI button (iteration_6): fresh batch +
  demo client purged, 0 tagged rows in all 6 tables, GoTrue left with ONLY the
  admin (no orphaned logins), audit log's 3 entries untouched. Demo client
  recreated + re-seeded afterwards.
- NOTE: request-changes UI approve/request buttons verified by curl (round
  tracking, guards 409/422, thread notes) + earlier UI patterns; full UI pass of
  the new request-changes panel included in next testing cycle.


## Implemented (June 2026) — session 5
- Approve Cut Button: POST /api/deliverables/{id}/approve (owner-scoped, only from
  in_review/revisions_requested, 409 otherwise, admin may approve on behalf);
  approve-cut-btn on deliverable detail. Verified 9/9 + UI.
- Client Profile Editing: /profile page (nav-profile) — full_name/company/phone
  self-update via anon+JWT under RLS (migration 004 added clients.phone, user ran it).
  Role escalation re-verified blocked.
- Overdue Invoice Flag (status-only, NO emails per user): sweep_overdue_invoices()
  flips sent→overdue when due_on < today; runs on /api/clients/ensure (each login)
  and /api/admin/overview. Future-due and paid untouched. Demo invoice
  INV-B-OVERDUE-8922 shows OVERDUE.
- Demo deliverables now: Q3 Teaser=approved, June Social Edit #3=approved,
  May Recap=final_delivered (approve tests flipped them).
- Review-noted future optimizations (not built): approver audit column, nightly
  sweep cron + (status,due_on) index at scale.


## Original problem statement
Connect the project to the user's existing Supabase database (NO MongoDB). Use the
publishable/anon key client-side, secret/service_role key server-side only. RLS on
every table with client data so no client can query another client's records.
Fresh app: client portal for a videography business (Flyboy Videography, UK/GBP).

## Architecture
- Frontend: React (CRA) + Tailwind, supabase-js (anon key) for auth + direct
  RLS-protected reads/writes; axios → FastAPI for profile ensure / seed / admin ops.
- Backend: FastAPI (port 8001, /api prefix) using supabase-py with the
  SERVICE_ROLE key (server-only, in backend/.env). Verifies Supabase JWTs via
  auth.get_user(). Deliberately bypasses RLS for admin operations.
- Database: Supabase Postgres. Schema + RLS in /app/supabase_schema.sql —
  USER RUNS IT MANUALLY in the Supabase SQL Editor (declined to share DB
  connection string).

## Tables (all with RLS)
clients, bookings, retainer_subscriptions, deliverables, review_threads, invoices.
- Admin model: clients.role ('client'|'admin'); SECURITY DEFINER helpers
  public.is_admin() and public.current_client_id(); every policy is
  "own rows OR is_admin()". Clients cannot self-assign admin (insert/update
  policies pin role='client').
- Admin bootstrap: backend ADMIN_EMAILS env var auto-promotes on /api/clients/ensure,
  or manual UPDATE in SQL.
- invoices: exactly-one-of booking_id/subscription_id check; currency default GBP;
  client_id ON DELETE RESTRICT (UK financial record retention / GDPR Art. 17(3)).
- review_threads UPDATE policy: author_user_id = auth.uid() (clients can only
  update their own comments — fixed after user review, 2026-06).

## Implemented (June 2026) — session 4
- Migration 003 (user ran): erasure_audit_log gained backfilled + note columns;
  Client B's pre-log erasure BACKFILLED (backfilled=true, note with ~19:50 UTC
  actual time). Audit log = 3 entries.
- Seed Data Purge: POST /api/admin/purge-seed-data (typed {confirmation:"PURGE"}
  required, 422 otherwise; admin-only). Deletes all is_seed_data rows + seed auth
  accounts; skips admins + clients with non-seed invoices (checked BEFORE deletes);
  audit log preserved. Admin UI Danger zone with window.prompt typed confirmation.
- REAL PURGE EXECUTED with user approval + proof shown (0 tagged rows in all 6
  tables, admin intact, audit intact). User then manually cleared remaining auth
  users, which deleted admin + demo accounts → both RECREATED fresh (new user_ids).
  Admin account untagged (is_seed_data=false) so purge never eligible.
- Seed bug fixed: first booking dict missing is_seed_data.
- Testing agent iteration_4: 11/11 backend + full frontend pass (guard-only, no
  destructive calls). Purge ordering hardened post-report.

## Implemented (June 2026) — session 3
- Migration 002 (user ran it, verified): is_seed_data boolean on all 6 tables,
  retroactive tagging of ALL test data (4 clients incl. erased Client B; 0 untagged
  rows anywhere), erasure_audit_log table (RLS admin-only SELECT, service_role-only writes).
- Erasure Audit Log feature: erase endpoint writes audit row (who/whom/when/preserved
  counts); GET /api/admin/erasure-audit; Admin UI audit section. Erase button hidden
  for already-erased clients. Verified by testing agent (10/10 + frontend).
- KNOWN GAP (flagged to user): Client B (576baf05) was erased BEFORE the audit table
  existed, so it has NO audit row (log has entries for C and D only). Backfill needs
  user decision (timestamp would be approximate).
- Seed convention: *@seed.flyboytest.com / SeedTest#2026!, is_seed_data=true,
  company=SEED_TEST_DATA. Clients B, C, D erased; Client A intact control.

## Implemented (June 2026)
- Full schema + RLS SQL — RUN BY USER, tables live in Supabase.
- Adversarial RLS test /app/tests/rls_adversarial_test.py — 16/16 passed both
  directions (Client A/B seed accounts @seed.flyboytest.com, company=SEED_TEST_DATA;
  note: schema has no is_seed_data column). Client B later GDPR-erased in testing.
- GDPR Erasure Flow: POST /api/admin/clients/{id}/erase — auth account updated
  FIRST (email anonymized, password rotated, 100y ban), then clients row +
  review author names anonymized; bookings/deliverables/invoices preserved.
  400 for admins, 409 if already erased (@anonymized.invalid check). Admin UI
  "GDPR erase" button (admin-erase-client-btn) with confirm.
- Demo seed fixed (review_threads bulk insert needed explicit resolved:false).
- Full schema + RLS SQL file (user-reviewed, 3 fixes applied: review_update policy,
  GBP default, invoice delete restrict; renamed Frame&Form → Flyboy Videography).
- Auth: email/password via Supabase Auth; login/signup page.
- Pages: Dashboard (stats + demo seed), Bookings (list + request form),
  Retainers, Deliverables (list + detail with video embed, timestamped review
  thread, resolve toggles, final file link), Invoices (booking vs retainer badges),
  Admin console (client picker, create booking/sub/deliverable/invoice, status updates).
- Backend: /api/health, /api/clients/ensure, /api/me, /api/demo/seed,
  /api/admin/* (clients, overview, bookings, subscriptions, deliverables, invoices).
- Graceful "schema not run yet" handling (503 + frontend banner).

## Pending / blocked on user
- Stripe invoicing + email alerts (Resend) ON HOLD until user sets up accounts.
- Email confirmation still enabled in Supabase project.

## Seed/test accounts state
- Client A client.a@seed.flyboytest.com / SeedTest#2026! — intact (control).
- Client B client.b@seed.flyboytest.com — GDPR-ERASED (login disabled, email now erased-*@anonymized.invalid).
- Demo client has 1 TEST_ Playwright booking + 1 TEST_ comment (harmless leftovers).

## Backlog
- P1: Stripe payments/webhooks for invoices (user mentioned as backend purpose).
- P1: File upload for final deliverables (Supabase Storage).
- P2: Email notifications on new cuts/comments.
- P2: GDPR erasure flow (anonymize client, keep invoices).
