# Test Credentials — Flyboy Videography Client Portal

Supabase project: https://pnqqmzszasvfnvnnonvd.supabase.co (auth + Postgres; NO MongoDB)

## Admin account (recreated 2026-06 after purge/manual auth cleanup; auto-promoted via ADMIN_EMAILS)
- Email: flyboy.admin.demo@gmail.com
- Password: AdminStudio#2026
- clients row is_seed_data=false (protected from purge)

## Client account (recreated + freshly seeded)
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
