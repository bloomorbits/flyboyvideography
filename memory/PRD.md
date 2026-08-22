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


## Security hardening (Feb 2026) — session 9
- **SEC-001 mitigated** — layered rate limiting + concurrent-lock caps on
  POST /api/booking/checkout. Migration 007 (`checkout_attempts` table +
  `ip` column on `date_slot_locks`) applied and introspected. Limits:
  per-email 3/15min + per-IP 5/15min best-effort + global 100/15min;
  concurrent locks 2/email + 3/IP + 50 global. All 429 responses log raw
  XFF/x-real-ip/client_host/UA for forensic analysis. Proof:
  `tests/sim_calendar_freeze_attack.py` runs 3 realistic attack scenarios;
  scenario C (XFF spoofing + per-request email variation) confirms the
  global lock cap fires at attempt 51 even under total per-source bypass.
- **SEC-002 mitigated** — `admin.create_user(email_confirm=False)` in
  `booking.py:_ensure_auth_user`. Account creation still happens only
  AFTER Stripe confirms payment (via webhook or the `/status` inline
  Stripe probe), and the recovery link mailed via Resend is the sole
  path that flips `email_confirmed_at` — so an unsolicited email
  captured mid-booking cannot be silently pre-verified.
- **Open redirect closed** — `ALLOWED_ORIGIN_URLS` env allowlist checked
  before embedding `origin_url` into Stripe's success/cancel URLs.
  Static list (no wildcards) per user directive: production domain, www
  subdomain, primary Vercel URL, Emergent preview, localhost dev.
- **CORS tightened at app layer** — `CORS_ORIGINS` env narrowed from `*`
  to the same list as `ALLOWED_ORIGIN_URLS`. Verified enforced at
  localhost:8001. **On the Emergent preview URL, the ingress overrides
  ACAO to `*` regardless of app-layer settings — flagged as
  PL-INFRA-2 (P0 pre-launch infra task) in CREDENTIAL_ROTATION.md.**
- **XFF trust boundary documented** — the Emergent preview ingress does
  not strip client-supplied X-Forwarded-For prefixes. The layered
  defense mitigates the impact, but the root fix requires ingress
  reconfiguration — flagged as PL-INFRA-1 (P0 pre-launch).
- **Secret rotation runbook updated** — CREDENTIAL_ROTATION.md now has a
  "Pre-launch infra tasks" section covering PL-INFRA-1 (XFF strip),
  PL-INFRA-2 (CORS override), and PL-INFRA-3 (rotate keys once before
  live traffic). These are explicitly P0 blockers before real,
  high-value traffic hits `/book`, not deferrable ops nice-to-haves.

## Security hardening (Feb 2026) — session 9, second pass
Follow-up on the re-audit findings:
- **SEC-001-residual FIXED** — `_rate_limit_or_429` now uses atomic
  insert-then-count in `booking.py`. The attempt row is inserted BEFORE
  the count query, so N concurrent racers each see a monotonically
  increasing count under Postgres READ COMMITTED. Comparisons flipped
  from `>=` to `>` accordingly. Re-ran the attack sim: scenario B (same
  IP, varying email) correctly bounds successes at `RL_MAX_PER_IP + 1`
  (the concurrent-lock cap catches the last one first).
- **SEC-002-residual STILL OPEN** — fully contingent on PL-INFRA-1. See
  CREDENTIAL_ROTATION.md; no additional app-layer mitigation planned.
- **SEC-003 FIXED** — both `tests/sim_calendar_freeze_attack.py` and
  `tests/test_booking_flow.py` now refuse to run without
  `ALLOW_ATTACK_SIM=1` AND a URL matching a safe-marker allowlist
  (`preview.emergentagent.com`, `localhost`, `127.0.0.1`, `staging`).
- **PII hashing in forensic logs FIXED** — `_hash_email` (SHA-256[:16])
  is used everywhere email would otherwise appear in a durable log:
  `_log_bypass_forensics` stderr line + the new `rate_limit_events`
  table (migration 008). `checkout_attempts.email` stays plaintext
  (ephemeral 24h counter, not a log/audit record).
- **CORS fail-closed** — `server.py` now uses an empty allowlist if
  `CORS_ORIGINS` is unset/empty (was silently `*` before).
- **Test fixture over-broad purge FIXED** — the autouse fixture in
  `test_booking_flow.py` now scopes deletions to the run's unique
  `EMAIL_PREFIX` only; the broad `%@example.com` etc. patterns were
  removed.
- **Runbook stale reference FIXED** — the `/api/_probe/ip` reference in
  PL-INFRA-1's verify step now describes a reproducible temporary
  probe pattern instead.
- **`rate_limit_events` persistence added** (migration 008 pending user
  application). `_log_bypass_forensics` writes to it best-effort with
  fail-open behaviour; verified via attack sim that a missing table
  triggers the fail-open path cleanly without bubbling exceptions.
  Retention: 30 days via lazy-purge on write.

### HARD GATE reminder (unchanged)
No live-mode Stripe traffic until PL-INFRA-1 (XFF strip) AND PL-INFRA-2
(CORS override) are verified resolved on the receiving deployment.


## Batch 1 (contact + admin security) — session 9, third pass
- **Public contact form live at `/contact`** — two-column form (name, email,
  package interest prefilled from `?package=`, event date, message) → POST
  `/api/contact/enquire` → row in `contact_enquiries` + Resend email to
  `CONTACT_TO_EMAIL` (defaults to `ADMIN_EMAIL`). Success state has explicit
  next-step CTAs back to /services and /book.
- **Independent rate-limit ledger** — `contact_attempts` (migration 009),
  deliberately separate from booking's `checkout_attempts` per user directive
  ("different threat models deserve independent tuning"). Layered caps:
  per-email 5/15min · per-IP 8/15min · global 200/15min. Same atomic
  insert-then-count pattern as `booking.py`. 429s persist to `rate_limit_events`
  with the `contact_*` prefix so the admin dashboard slices them separately.
- **Mailto sweep on conversion paths** — replaced across services, portfolio,
  home, book/cancel, FAQ. Services `enquireHref` helper deleted (dead code).
  Privacy Policy keeps `hello@flyboyvideography.com` as plain non-clickable
  text per user directive (GDPR requests need a deliberate, formal path,
  not a routing-to-inbox contact form).
- **Contact nav link** added to SiteHeader (hidden on mobile, keeps Book
  as the primary CTA visually).
- **Admin `/admin/security` dashboard** — new route in CRA portal, admin-only.
  Reads last 100 events from `GET /api/admin/rate-limit-events`. Suspect-email
  search via `POST /api/admin/rate-limit-events/search` hashes plaintext email
  server-side (never stored) and returns matching events. Event reasons are
  human-labelled and colour-toned by severity (global = red, per-source =
  amber, contact = cyan). Sidebar entry with a distinct `ShieldAlert` icon
  next to the existing Admin entry. `d3` (clear-attacker action) deferred
  per user directive — destructive admin actions get their own guarded
  treatment later.
- **Migration 009 applied and verified** — `contact_enquiries` +
  `contact_attempts` with RLS-enabled/no-policies (same posture as 007/008).



## Implemented (Feb 2026) — session 9 (Phase 1 Booking Flow)
- Client-facing project booking (one-off, non-retainer) live on public Next.js
  site at /book. Two-step form (package/tier/date → contact details) → Stripe
  Checkout (deposit only, DIY tax mode, GBP) → /book/success or /book/cancel.
- Schema: migration 006 introspected and confirmed applied (payment_transactions,
  date_slot_locks, booking_intents; 4 new columns on bookings; partial unique
  index bookings_one_confirmed_per_date verified via probe).
- Backend endpoints (all in /app/backend/booking.py, mounted from server.py):
  - GET  /api/booking/availability          → returns blocked_dates for 18mo ahead
  - POST /api/booking/checkout              → creates booking_intent + Stripe
                                              Checkout Session + soft
                                              date_slot_lock (5min TTL)
  - GET  /api/booking/status/{session_id}   → poll-safe, inline Stripe probe
                                              fallback for slow webhooks
  - POST /api/stripe/webhook                → signature-verified, idempotent;
                                              atomic bookings insert as the DB
                                              gate; on unique_violation issues
                                              stripe.Refund.create automatically
- Auth provisioning: on paid webhook the server creates (idempotent) a Supabase
  auth user + clients row, then generates a Supabase-issued recovery link
  (type=recovery, redirect_to=PORTAL_URL/auth?welcome=1) and emails it via
  Resend using /app/backend/emails/booking_confirmation.{html,txt}.
- Pricing source of truth: hardcoded constants mirrored in
  /app/website/lib/booking-packages.js (client) and /app/backend/packages.py
  (server, authoritative for actual charged amount). No packages table in
  Supabase — confirmed via introspection this session.
- Concurrency test /app/backend/tests/test_booking_concurrency.py — 10 threads
  race against the same event_date, Stripe mocked; asserts exactly 1 confirmed
  booking + 9 refunded_race + 9 refund calls. Passes 3/3 runs.
- SiteHeader now surfaces "Book" as the primary nav CTA (was "Enquire" mailto).
- New env vars in backend/.env: PUBLIC_SITE_URL, PORTAL_URL, RESEND_FROM_EMAIL.
- New env file website/.env.local: NEXT_PUBLIC_API_BASE (points at backend).

## Backlog (updated Feb 2026)
- P1: Phase 2 retainer signup via Stripe Subscriptions.
- P1: Client Portal restyle (dark/cyan → light/cream to match public site).
- P1: Public contact form (Resend) replacing mailto: links throughout.
- P2: V2 booking — short packages share the same calendar day (currently a
  short package still blocks the whole day).
- P2: Bunny.net for deliverable hosting.
- P2: Tawk.to widget (respect cookie consent).
- P2: Deliverable 90-day expiry + warning email.
- P2: Deliverable access/download logging.
- P2: T&Cs acceptance timestamp + IP capture at booking.


## Next-session pickup (fresh-context reference, 2026-02)

Tonight's work covered Phase 1 booking flow + full security hardening +
public contact form + admin security dashboard. Everything shipped is
verified end-to-end (10/10 pytests, real 429s persisted, admin dashboard
smoke-tested with real admin bearer). Backlog items no longer relevant
(struck through below) — these have been DONE this session:

- ~~P1: Public contact form (Resend) replacing mailto: links~~ — DONE
  (Batch 1 · session 9, third pass). Migration 009 applied.

The remaining backlog, ordered as the user directed at end of session 9:

1. **P1 · Retainer Schema Design** — sketch `retainers` / `subscriptions`
   table + Stripe Subscription price IDs so Phase 2 has a clean
   foundation. Fresh design decision; do NOT tack onto an existing
   migration. Introspect first (SCHEMA_MIGRATION_CHECKLIST rule).
2. **P1 · Retainer Signup Flow** — `/retain` page with tier picker +
   monthly Stripe Subscription checkout + portal integration for
   subscribers. Blocked on #1.
3. **P1 · Portal Restyle** — migrate CRA portal from dark/cyan to the
   cream/ink public-site design system so clients get one visual
   identity. Big enough to warrant `design_agent_full_stack` before
   touching code.
4. **P2 · Enquiry Inbox** — Studio admin view listing
   `contact_enquiries` (status: new/replied/archived) so submissions
   don't just sit in email. Backend read endpoint + a new tab in the
   admin dashboard.
5. **P2 · Enquiry Auto-Reply** — immediate "we've got it, will reply
   within one working day" acknowledgement to the enquirer so they
   don't wonder if the form worked.

### HARD GATES (do not skip when picking up)
- **PL-INFRA-1 + PL-INFRA-2** ~~unresolved~~ — **BOTH CLOSED on Railway (2026-02 cutover, session 10).** Empirical proof captured in `/app/docs/CREDENTIAL_ROTATION.md` under each PL-INFRA section (probe results table + scenario-C attack transcript). Live-mode Stripe from the edge-infra side is unblocked; PL-INFRA-3 (secret rotation) remains open, triggered when Stripe sandbox is claimed.
- ~~**SEC-002-residual** still open, fully contingent on PL-INFRA-1.~~ — **CLOSED transitively** with PL-INFRA-1.
- **Migration 010** will be needed for retainers. Follow the pattern
  from 006-009: file at `/app/supabase_migration_010_*.sql`, user
  applies manually in the Supabase SQL Editor, agent introspects to
  verify BEFORE writing any code that depends on the schema.

### Provider account state
- Stripe: sandbox provisioned, still pre-KYC. Live-mode promotion is a
  post-PL-INFRA-1+2 milestone.
- Resend: transactional-only usage (booking confirmation + contact
  notification). `CONTACT_TO_EMAIL` env defaults to `ADMIN_EMAIL`.
- Supabase: migrations 006-009 all applied and verified.


## Infrastructure cutover (Feb 2026) — session 10 (Railway backend + P0 security closure)

Tonight's session took the backend off the Emergent preview URL and onto
production Railway infrastructure, closed the two P0 hard-gate items
(PL-INFRA-1 XFF spoofing, PL-INFRA-2 CORS override), and fixed a HIGH
payment-integrity race surfaced by the mid-cutover security audit
(SEC-001 refund-race). Everything below verified empirically, not just
via code review.

### Deployed environments (canonical URLs)

| Env | Service | URL | Notes |
|:----|:--------|:----|:------|
| Prod | FastAPI backend (Railway) | `https://flyboyvideography-production.up.railway.app` | Railpack builder, `/backend` root dir, PORT 8080 target, Procfile-driven |
| Prod | Next.js public site (Vercel) | `https://flyboyvideography.vercel.app` + custom `flyboyvideography.com` | **Still pointed at PREVIEW backend via `NEXT_PUBLIC_API_BASE` — cutover happens in Step 12** |
| Prod | CRA client portal (Vercel) | `https://flyboyvideography-portal.vercel.app` | Live as of end of session 10. `REACT_APP_BACKEND_URL` points at Railway. Talks to Supabase directly for RLS-protected reads + Railway for `/api/*`. |
| Legacy | Preview pod | `https://db-bridge-5.preview.emergentagent.com` | Retire after Step 13 |

### Cutover step status (as of end of session 10)

| # | Step | Status |
|:-:|:-----|:-------|
| 0 | GitHub repo + client-ownership-transfer checklist | ✅ documented (`CREDENTIAL_ROTATION.md § GitHub repo ownership transfer`) |
| 1 | Railway service + Railpack builder | ✅ (Nixpacks deprecated → Railpack; `/backend` root dir; PORT 8080) |
| 2 | Env vars set (except `STRIPE_WEBHOOK_SECRET`) | ✅ |
| 3 | Railway URL captured in docs | ✅ |
| 4 | Stripe webhook created, `STRIPE_WEBHOOK_SECRET` set, test webhook `200` | ✅ |
| — | **SEC-001 payment-integrity race fix** (audit-triggered mid-cutover) | ✅ code + regression pytest + empirical smoke-test proof |
| 5 | Real end-to-end smoke test (real Stripe test-mode payment against Railway) | ✅ full chain verified: booking row, tx=paid, clients row, Resend email delivered, status endpoint, `date_slot_locks` cleaned up |
| 6-8 | XFF/CORS empirical verification + `_client_ip()` hardening | ✅ PL-INFRA-1 + PL-INFRA-2 CLOSED |
| 9 | Vercel CRA client portal deployment + CORS allowlist reconciliation | ✅ portal live at `flyboyvideography-portal.vercel.app`; Railway `CORS_ORIGINS` + `ALLOWED_ORIGIN_URLS` + `PORTAL_URL` updated; localhost drift cleaned up; second security audit PASSED; full CORS-drift root-cause documented in `CREDENTIAL_ROTATION.md § Railway Variables change-control` |
| 10 | Full end-to-end on Vercel portal + Railway | ✅ session 10 — full chain verified (real payment → Railway webhook → Supabase → Resend email → magic-link → Vercel portal session). Uncovered latent Supabase URL Configuration bug (Site URL still `http://localhost:3000`, allowlist missing all portal URLs); fixed in Dashboard, retest passed. Root cause + rules documented in `CREDENTIAL_ROTATION.md § Supabase Auth URL Configuration governance` |
| 11 | Seed-data purge via Admin Danger Zone + manual SQL | ✅ session 10 — `is_seed_data=true` rows purged via portal admin button, both smoke-test bookings (Step 5 + Step 10) deleted with FK-safe SQL, orphaned clients + `auth.users` deleted, diagnostic tables (checkout_attempts / contact_attempts / rate_limit_events) zeroed. Also surfaced: Supabase SQL editor's multi-statement batch behaviour is NOT reliably transactional — a mid-batch error can leave some statements committed and others silently skipped. Rule: always follow multi-statement DELETE batches with an explicit COUNT verification on every table touched. |
| 12 | Update `NEXT_PUBLIC_API_BASE` on Next.js Vercel project, redeploy | ✅ session 10 — Vercel `flyboyvideography` project (Next.js public site) env var flipped to Railway URL across all three environments, redeployed with build cache disabled. Empirical verification on `flyboyvideography.com/book`: DevTools Network filter `railway.app` shows `/api/booking/availability` returning 200; filter `preview.emergentagent.com` shows 0/25 requests. Preflight probes from all four production origins (`flyboyvideography.com`, `www.flyboyvideography.com`, `flyboyvideography.vercel.app`, control evil origin) match expected. |
| 13 | Live end-to-end verify on `flyboyvideography.com` | ⏳ **NEXT SESSION — real customer path, real payment** |
| 14 | Retire Emergent-preview Stripe webhook, mark PL-INFRA-1/2 verified-resolved | ⏳ |

### Key code changes (session 10)

- **`backend/booking.py` — `_client_ip()` refactor** (lines 150-183): now prefers `X-Real-IP` → leftmost XFF → `client.host` fallback. Docstring documents Railway's empirical strip behaviour AND warns future agents to re-probe if deployment ever moves off Railway. XFF trust is a deployment-property, not an application-property.
- **`backend/booking.py` — SEC-001 fix** (lines 843-877): new guard branch in `_finalise_paid_session` unique-violation handler. Before refunding, checks whether the winning booking's `stripe_session_id` matches ours. If yes → same-session concurrent replay (webhook + `/status` probe race) → treat as idempotent success, no refund. Only refund on genuine cross-session race.
- **`backend/tests/test_booking_concurrency.py`** — new pytest `test_same_session_concurrent_finalise_does_not_refund_customer` locks in the SEC-001 fix. Empirically validated: reverts to buggy code make the test fail with a clear regression message; restoring the fix makes it pass. Both concurrency tests (existing multi-session + new same-session) pass together in the suite.
- **`backend/requirements.txt`** — removed `emergentintegrations==0.2.0` and the `litellm` CDN-hosted wheel. Both were unused dead code from the Emergent CRA+FastAPI scaffold; both fail to resolve outside Emergent's build environment (private PyPI index / internal CDN URL). If ANY future `pip freeze` inside the preview pod regenerates `requirements.txt`, these will come back and Railway will fail. Fix is to re-remove.
- **`backend/Procfile`**, **`backend/.python-version`**, **`frontend/vercel.json`** — deployment config files (created earlier session, retained). Procfile uses `server:app` NOT `main:app`.
- **Probe endpoint `/api/_probe/ip`** was added, used to empirically verify Railway XFF/X-Real-IP stripping, then deleted in the same commit as the `_client_ip()` update. Confirmed absent post-redeploy (`curl` returns 404). No permanent header-echo attack surface.
- **`backend/tests/_scenario_c_railway.py`** — one-shot rate-limiter attack sim runner, hit Railway 7 times to prove PL-INFRA-1 empirically, then deleted. Kept to the "no drifting temporary fixtures" principle. Reproducible from git history if needed again.

### Documentation changes (session 10)

- **`/app/docs/CREDENTIAL_ROTATION.md`**:
  - New rotation-log rows for Railway cutover.
  - New "GitHub repo ownership transfer" section (parallel to Stripe's "Ownership handoff") — covers the easy-to-miss step of disconnecting/re-authorising Railway's AND Vercel's Git integrations from the client's account when the repo is transferred. Not just transferring the repo.
  - PL-INFRA-1 section: empirical proof table (spoofed inputs vs actual header values) + full scenario-C attack transcript (attempts 1-7, per-IP concurrent-lock cap firing at attempt 4, per-IP rate cap firing at attempt 6).
  - PL-INFRA-2 section: empirical proof (curl outputs showing Railway echoes only legit origins, drops the ACAO header entirely for evil origins, preflight from evil origin returns 400).
  - "HARD GATE STATUS" callout under the Pre-launch infra tasks heading now shows both P0 items CLOSED.
- **`/app/docs/RAILWAY_VERCEL_CUTOVER.md`**:
  - "Deployed environments" table at the top with canonical URLs.
  - "Domain gotcha" section: Railway's auto-generated `<service>-<env>.up.railway.app` domain is the ONLY one that should be trusted; the custom-short domain wizard is a footgun that drifted on redeploy during initial cutover attempt.
  - "Emergent-only dependencies removed from requirements.txt" section.
  - "Repo ownership context" pointer at the top → CREDENTIAL_ROTATION.md handoff checklist.

### Empirical verification evidence (all captured in CREDENTIAL_ROTATION.md)

- **XFF/X-Real-IP strip:** probe endpoint results for baseline + 4 spoofing tests. Pod public IP `34.16.56.64`. Spoofed values `1.2.3.4`, `5.6.7.8`, multi-hop XFF chains — all dropped, all headers replaced with pod IP.
- **CORS:** legit origin echoed correctly, evil origin gets no ACAO header, preflight from evil origin rejected 400.
- **Rate limiter behavioural proof:** on Railway, per-IP concurrent-lock cap (LOCK_CAP_PER_IP=3) fires at attempt 4, per-IP rate cap (RL_MAX_PER_IP=5) fires at attempt 6 — as designed. On Emergent preview the same attack needed attempt ~50-100 (global caps only) because XFF was spoofable.
- **SEC-001 fix under real production race:** end-to-end smoke test with real Stripe test-mode payment showed `payment_transactions.payment_status = 'paid'`, NOT `refunded_race`. Fix confirmed under the actual webhook + status-poll race.

### Backlog after session 10

Order preserved from session 9, with `SEC-001`, `PL-INFRA-1`, `PL-INFRA-2` all struck through as resolved. The critical work ahead is FRONTEND cutover (Steps 9-14), not backend features. **Feature freeze on the P1 backlog (Retainer signup, Enquiry Inbox, Portal restyle, Welcome tour, etc.) remains in effect until the full cutover ships.**

### Next-session pickup for a fresh agent

**⚠ Step 13 is a real end-to-end validation on the customer path — same weight as Step 10, but from the front door AND now against the consent-enforced flow shipped in session 11.** Real Stripe test-mode payment, real Resend email, real magic-link click-through, PLUS validation that the consent step is UX-visible + server-enforced. If it produces test data, follow the Step 11 pattern to purge.

**Consent capture — what shipped in session 11 (must be tested by Step 13, was NOT tested with a real payment yet):**
- Migrations 010 + 010B applied — 6 consent columns on `bookings` AND `booking_intents` (primary source of truth + defense-in-depth via Stripe metadata)
- `booking.py::CheckoutIn` extended, checkout endpoint hard-gates 400 if T&Cs unchecked or minors+missing guardian/safeguarding
- 6 pytests in `tests/test_consent_enforcement.py`, mutation-validated twice
- `/terms` rewritten with §7 cooling-off + solicitor banner; new `/model-release` + `/safeguarding-consent` pages with Nathan's copy (`LAST_UPDATED = null` renders "Not yet published — pending solicitor review")
- `/book` step 2 consent fieldset: T&Cs required, model-release pre-checked opt-out, minors radio → conditional guardian field + safeguarding checkbox. Pay button disabled until valid.
- **Nathan has NOT clicked through the consent UI in browser yet — that's a prerequisite for Step 13.**

1. Read `/app/docs/RAILWAY_VERCEL_CUTOVER.md` (deployed environments table + gotcha sections).
2. Read `/app/docs/CREDENTIAL_ROTATION.md` — HARD GATE STATUS + Railway Variables + Supabase Auth URL Configuration governance sections.
3. **Verify session-11 push reached Railway** — quick pre-check: `curl -X POST https://flyboyvideography-production.up.railway.app/api/booking/checkout -H "Content-Type: application/json" -d '{"package_id":"graduation","tier_name":"","event_date":"2029-01-01","email":"test@flyboytest.com","full_name":"pre-check","origin_url":"https://flyboyvideography.com","tc_accepted":false}'` should return `400` mentioning "Terms & Conditions". If it returns 200 or 500, session-11 hasn't deployed — resolve before proceeding.
4. **Nathan browser click-through** on `flyboyvideography.com/book` first: consent fieldset visible, model-release pre-checked, Pay button disabled until T&Cs ticked, minors=Yes reveals guardian field + safeguarding checkbox.
5. Confirm with user then proceed to Step 13.
6. Step 13 mechanics (same as Step 10 + consent verification):
   - Incognito browser → `flyboyvideography.com/book` → real Gmail plus-address (NOT literal `YOUR.EMAIL`) → date with no seed collision → fill consent step → complete Stripe with `4242 4242 4242 4242`.
   - Verify same 4 DB effects as Step 10.
   - **NEW: verify consent columns populated** — `SELECT tc_accepted_at, tc_accepted_ip, model_release_opted_in, minors_involved, safeguarding_guardian_name, safeguarding_consent_accepted_at FROM bookings WHERE stripe_session_id = '<sid>';`. Expect `tc_accepted_at` and `tc_accepted_ip` non-null; others matching what Nathan clicked.
   - Verify email + magic link → Vercel portal session.
7. If Step 13 passes: Step 14 — retire preview Stripe webhook, prune preview URL from Railway allowlists, decide `/app/website/.env.local` follow-up.
8. **Post-cutover P1 queue (freeze intact until Steps 13 + 14):**
   - Enquiry Inbox (admin view of `contact_enquiries`) — was #1 per session 10
   - Admin-editable pricing (packages table + admin UI, replaces `lib/pricing.js`) — proposed session 11, deferred per freeze; Nathan's call on ordering vs Enquiry Inbox
   - Retainer signup, Welcome tour, per backlog
9. If Step 13 surfaces bugs in consent OR payment chain, freeze remains — fix bug, don't detour to P1. Consent has mutation-tested pytests but has NOT survived a real Stripe round-trip yet.
10. Portal admin login unchanged — see `/app/memory/test_credentials.md`.


## Implemented (Feb 2026) — session 15 (Automated Balance Collection, Phases 1-6)

Goal: automate the balance-collection cycle end-to-end so a booking 10 days
out gets a balance invoice + Stripe Checkout link emailed automatically, and
gets a single gentle reminder if it's still unpaid inside 2 days of due_on.
Zero double-billing, no new webhooks, no ambiguity about "who fired what."

### What shipped

| Phase | Deliverable | Test coverage |
|---|---|---|
| 1 | `supabase_migration_012_balance_invoicing.sql` — adds `payment_purpose`, `reminder_sent_at`, partial unique index `invoices_one_balance_per_booking_uniq` | `backend/tests/introspect_012.py` — PASS, duplicate insert raises `23505` |
| 2 | `_finalise_paid_session` branches on `metadata.payment_purpose`; new `_finalise_balance_payment` does invoice→paid + tx→paid idempotently | `backend/tests/test_balance_finalise.py` — 9/9 PASS (first-call flip, no-op replay, 100× replay stress, 2 self-heal paths, missing-invoice_id refusal, wrong-purpose refusal, deposit-metadata-doesn't-touch-balance, invoice-not-found refusal) |
| 3 | `_create_balance_checkout_session()` helper + `GET /api/booking/pay-balance/{invoice_id}` public 302-to-Stripe endpoint. Metadata carries `payment_purpose`, `invoice_id`, `booking_id`, `client_email`. No `api_version` pin | Covered end-to-end by Phase 2 + 4 tests |
| 4 | `POST /api/admin/jobs/run-daily-invoicing` in `backend/daily_invoicing.py`. Auth via NEW `CRON_JOB_JWT_SECRET` + `aud=flyboy:cron:daily-invoicing` + `scope=cron:invoicing`. Balance formula = `bookings.budget − Σ(paid payment_transactions on this booking, incl. balance-paid invoices)` | `backend/tests/test_daily_invoicing.py` — 12/12 PASS |
| 5 | Reminder branch in same endpoint. Filters: `status='sent' AND due_on ≤ today+2 AND reminder_sent_at IS NULL`. Recomputes remaining balance; if ≤ 0, marks invoice paid + latches `reminder_sent_at` (no email); else sends reminder + latches | Covered by same 12-test suite — inc. explicit "reminder does NOT fire when balance settled outside Stripe checkout" |
| 6 | `docs/BALANCE_INVOICING_RUNBOOK.md` — Railway Cron wire-up, JWT-mint snippet, health-signal table, rollback plan | Manual deployment |

Email templates (approved copy, matching booking_confirmation voice + Bloomorbit credit):
- `backend/emails/balance_invoice.{html,txt}`
- `backend/emails/balance_reminder.{html,txt}`

Config added to `backend/.env`: `CRON_JOB_JWT_SECRET` (64-byte urlsafe). Same
key MUST be minted fresh on Railway before deploying the cron.

Defense-in-depth guards:
- DB physical: partial unique index on `invoices(booking_id) WHERE payment_purpose='balance'`
- Webhook: idempotency guard on `invoice.status='paid'` + tx `payment_status='paid'`
- Webhook: refuses if metadata says `balance` but invoice `payment_purpose ≠ 'balance'`
- Endpoint: refuses if `payment_purpose ≠ 'balance'` or `status NOT IN ('sent','overdue')`
- Cron: JWT `aud` + `scope` claims, dedicated secret separate from admin/session

### Files touched / created

- Modified: `backend/booking.py` (balance branch + helper + `/api/booking/pay-balance/{invoice_id}`)
- Modified: `backend/server.py` (mount `daily_invoicing_router`)
- Modified: `backend/tests/introspect_012.py` (removed stale `meta`/`currency` columns)
- Modified: `backend/.env` (`CRON_JOB_JWT_SECRET`)
- Modified: `memory/PRD.md`, `memory/test_credentials.md`
- New: `backend/daily_invoicing.py`
- New: `backend/emails/balance_invoice.{html,txt}`, `backend/emails/balance_reminder.{html,txt}`
- New: `backend/tests/test_balance_finalise.py`, `backend/tests/test_daily_invoicing.py`
- New: `docs/BALANCE_INVOICING_RUNBOOK.md`

### Dual-delivery observation status (Step 14 — still queued)

24h monitor at session start: `seen_by_both=1, railway_only=0, preview_only=0`.
Sample is thin (1 completed event); Nathan opted to keep Step 14 queued.
Rerun `python scripts/monitor_dual_delivery.py --hours 48` to widen window
before retiring the preview endpoint.

### Backlog after session 15

Order preserved. Balance-collection ships freezes lifted:

1. **P0** — Step 14 retirement (waiting on wider observation window)
2. **P1** — Magic-link recovery UI fix in `frontend/src/pages/AuthPage.js`
3. **P1** — Complete remaining SEO landing pages (skip Corporate)
4. **P1** — Admin-editable pricing (Migration 013)
5. **P1** — Enquiry Inbox (admin view of `contact_enquiries`) + auto-reply email
6. **P1** — Retainer signup via Stripe Subscriptions
7. **P2** — Welcome tour first-login flow
8. **P2** — Package-dependent day-blocking (V2 Booking)
9. **P2** — Deliverable 90-day expiration + warning email

### Deploy checklist for balance collection

1. Apply Migration 012 in Supabase (✅ done in this session)
2. Push code to `main` → Railway auto-deploy
3. Set `CRON_JOB_JWT_SECRET` in Railway env (fresh secret; not the same as local pytest secret)
4. Set `PUBLIC_API_BASE` in Railway env (= Railway backend URL)
5. Set `SELF_URL` in Railway env (= same, used by cron command)
6. Manual dry-run POST via curl (see runbook) → expect JSON summary with `dry_run=true`
7. Add Railway Cron schedule: daily 08:00 UTC, command from runbook
8. Watch first live run in Railway logs
