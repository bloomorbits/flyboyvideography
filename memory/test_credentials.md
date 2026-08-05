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

## Important state
- The user runs /app/supabase_schema.sql themselves in the Supabase SQL Editor.
  Until they do, tables do not exist: backend /api/clients/ensure returns 503
  with a schema hint and the frontend shows a "Database schema not set up yet" banner.
- Email confirmation is still ENABLED in the Supabase project; new signups via the
  UI will get "check your email". The two accounts above are pre-confirmed.
- Supabase email validation rejects made-up domains (email_address_invalid); use
  gmail.com-style addresses for new signups.
