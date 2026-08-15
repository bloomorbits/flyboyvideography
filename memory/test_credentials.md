# Test Credentials — Flyboy Videography Client Portal

Supabase project: https://pnqqmzszasvfnvnnonvd.supabase.co (auth + Postgres; NO MongoDB)

## Admin account (recreated 2026-06 after purge/manual auth cleanup; auto-promoted via ADMIN_EMAILS)
- Email: flyboy.admin.demo@gmail.com
- Password: AdminStudio#2026
- clients row is_seed_data=false (protected from purge)

## Client account (recreated + freshly seeded after genuine E2E purge, session 6)
- Email: demo.client.frameform@gmail.com
- Password: DemoClient#2026
- Seed data: 2 bookings, 1 retainer, 3 deliverables, 2 comments, 2 invoices (all is_seed_data=true)

## Current DB state
- Exactly 2 clients (admin + demo). Old seed clients A-D purged/erased.
- erasure_audit_log: 3 entries (B backfilled=true with note, C, D) — never purged.
- DANGER: /api/admin/purge-seed-data with confirmation "PURGE" deletes all tagged
  data including the demo client. Test the guard only (wrong text → 422).

## Notes
- Email confirmation still ENABLED in Supabase; fake domains rejected on signup.
  Create test users via GoTrue admin API with email_confirm=true, convention
  *@seed.flyboytest.com / SeedTest#2026!, always is_seed_data=true.


## Booking flow (Phase 1, session 9)
- No pre-seeded booking accounts. Each successful checkout creates a fresh
  Supabase auth user via GoTrue admin API + a clients row on the fly.
- To test the /book flow end-to-end WITHOUT charging a real card:
  - The concurrency pytest at /app/backend/tests/test_booking_concurrency.py
    mocks Stripe and directly exercises the DB race condition.
  - For a real Stripe test-mode redirect, POST /api/booking/checkout returns
    a live cs_test_... URL; the user can complete payment with card
    `4242 4242 4242 4242` and confirm the webhook fires from the Stripe
    Dashboard. Success page polls /api/booking/status/{session_id}.
- Test emails created by the flow should use *@flyboytest.com so they're
  easy to spot and delete via the GoTrue admin API afterwards.
