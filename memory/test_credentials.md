# Test Credentials — Flyboy Videography Client Portal

Supabase project: https://pnqqmzszasvfnvnnonvd.supabase.co (auth + Postgres; NO MongoDB)

## Admin account (auto-promoted via backend ADMIN_EMAILS on first login AFTER schema SQL is run)
- Email: flyboy.admin.demo@gmail.com
- Password: AdminStudio#2026
- Created via Supabase admin API, email pre-confirmed.

## Client account
- Email: demo.client.frameform@gmail.com
- Password: DemoClient#2026
- Email pre-confirmed.

## Seed test clients (RLS adversarial test)
- Client A: client.a@seed.flyboytest.com / SeedTest#2026! (intact)
- Clients B, C, D (@seed.flyboytest.com) — GDPR-ERASED, logins permanently disabled
- All seed rows carry is_seed_data=true (migration 002 applied)

## Important state
- Schema SQL HAS been run by the user; tables + RLS live. Demo data seeded for demo client.
- Email confirmation is still ENABLED in the Supabase project; new signups via the
  UI will get "check your email". The two accounts above are pre-confirmed.
- Supabase email validation rejects made-up domains (email_address_invalid); use
  gmail.com-style addresses for new signups.
