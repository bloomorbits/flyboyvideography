# Railway + Vercel cutover — copy-paste reference

**Read this alongside `/app/docs/CREDENTIAL_ROTATION.md § Pre-launch infra tasks`. Deploying to Railway + Vercel is the concrete action that resolves PL-INFRA-1 and PL-INFRA-2, closing the HARD GATE on live-mode Stripe.**

## Repo ownership context (2026-02)

Cutover connects Railway and Vercel to **`github.com/bloomorbits/flyboyvideography`** (Bloom Orbit-owned). This is deliberate during build-out. When the client takes ownership, transferring the GitHub repo alone is NOT sufficient — Railway and Vercel Git integrations must be explicitly disconnected and re-authorised from the client's account. Full checklist: `CREDENTIAL_ROTATION.md § GitHub repo ownership transfer`.

## Files added for the cutover (session 9)
- `/app/backend/Procfile` — Railway entrypoint. **Uses `server:app`, not `main:app`.**
- `/app/backend/.python-version` — pins Python 3.11 (matches the codebase's local venv).
- `/app/frontend/vercel.json` — SPA rewrite so `/dashboard`, `/deliverables/:id`, etc. resolve to `index.html`.

## Emergent-only dependencies removed from requirements.txt (session 9)

The Emergent CRA+FastAPI scaffold ships `requirements.txt` with two entries that ONLY resolve inside Emergent's build environment and will hard-fail on Railway / Vercel / any external Python builder:

- `emergentintegrations==0.2.0` — internal LLM-router wrapper (private PyPI index).
- `litellm @ https://customer-assets.emergentagent.com/internal-asset/library/litellm-...whl` — Emergent-CDN-hosted wheel; unreachable outside Emergent's network.

Both were dead code in this backend (zero imports) — removed before the Railway cutover. If a future agent regenerates `requirements.txt` via `pip freeze` inside the preview pod, these WILL be re-added and Railway builds WILL fail again. The fix is to re-remove them (or, cleaner, `pip freeze` inside a pyenv/venv that never installed them).

**Also unused but harmless (kept for surgical change):** `motor`, `pymongo` — MongoDB clients from the scaffold. Backend is Supabase/Postgres only. Cleanup deferred to post-cutover backlog.

## Env vars to set on Railway (FastAPI backend)

Copy verbatim from the preview pod's `/app/backend/.env` for the secret ones, then override the origin-list vars with the exact strings below:

```
SUPABASE_URL             = <copy from preview .env>
SUPABASE_SERVICE_ROLE_KEY = <copy from preview .env>
STRIPE_SECRET_KEY        = <copy from preview .env>
STRIPE_WEBHOOK_SECRET    = <NEW value from Railway-URL Stripe webhook — see Stripe step below>
STRIPE_MODE              = test
RESEND_API_KEY           = <copy from preview .env>
RESEND_FROM_EMAIL        = Flyboy Videography <bookings@flyboyvideography.com>
CONTACT_TO_EMAIL         = hello@flyboyvideography.com
ADMIN_EMAILS             = <copy from preview .env>
PUBLIC_SITE_URL          = https://flyboyvideography.vercel.app
PORTAL_URL               = https://<your-cra-portal>.vercel.app

CORS_ORIGINS             = https://flyboyvideography.com,https://www.flyboyvideography.com,https://flyboyvideography.vercel.app,https://<your-cra-portal>.vercel.app
ALLOWED_ORIGIN_URLS      = https://flyboyvideography.com,https://www.flyboyvideography.com,https://flyboyvideography.vercel.app,https://<your-cra-portal>.vercel.app
```

Replace `<your-cra-portal>` with the actual Vercel-assigned subdomain after step 3 below. Until you know it, leave the two Vercel-portal entries off — the public site + custom domain are the ones that matter for the booking cutover.

## Stripe webhook endpoint (do BEFORE cutting over)
1. Stripe Dashboard → Developers → Webhooks → Add endpoint
2. URL: `https://<your-railway-app>.up.railway.app/api/stripe/webhook`
3. Events: `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.async_payment_failed`, `checkout.session.expired`
4. Copy the signing secret (`whsec_...`) → paste as `STRIPE_WEBHOOK_SECRET` on Railway
5. **Do NOT delete the old Emergent-preview webhook yet** — leave both live until step 4 of the cutover confirms the new one is healthy.

## Env var to update on Vercel (Next.js public site) at cutover
Vercel dashboard → `flyboyvideography` project → Settings → Environment Variables:
```
NEXT_PUBLIC_API_BASE = https://<your-railway-app>.up.railway.app
```
**Then redeploy** — `NEXT_PUBLIC_*` is baked at build time.

## After Railway is up: verify the XFF trust boundary
Per user directive (session 9): do NOT trust `X-Real-IP` on Railway blind. Repeat the empirical probe used against Emergent before flipping `_client_ip()` to prefer it:

1. Temporarily add to `server.py`:
   ```python
   @app.get("/api/_probe/ip")
   def _probe_ip(request: Request):
       return {
           "client_host": request.client.host if request.client else None,
           "x_forwarded_for": request.headers.get("x-forwarded-for"),
           "x_real_ip": request.headers.get("x-real-ip"),
           "cf_connecting_ip": request.headers.get("cf-connecting-ip"),
       }
   ```
2. `curl -H "X-Forwarded-For: 1.2.3.4" -H "X-Real-IP: 1.2.3.4" https://<railway>/api/_probe/ip`
3. Confirm `x_real_ip` in the response is NOT `1.2.3.4` (Railway stripped the spoof) and matches your actual public IP.
4. If confirmed: update `_client_ip()` in `booking.py` to prefer `x-real-ip` before XFF fallback.
5. Remove the probe endpoint.
6. Only then mark PL-INFRA-1 as verified-resolved in `CREDENTIAL_ROTATION.md`.

## Pre-live-traffic checklist (Supabase side)
Per your decision to keep the existing Supabase project (preserves the migration 006–009 introspection trail):

1. Deploy backend + verify webhook works end-to-end with a real Stripe test-mode checkout.
2. Sign in to portal as admin → Admin → Danger zone → **Purge seed data**. This clears every row tagged `is_seed_data=true` PLUS the matching test-login accounts, but PRESERVES the erasure_audit_log (compliance record).
3. Also worth manually deleting any leftover `contact_enquiries`, `checkout_attempts`, `contact_attempts`, `rate_limit_events` rows from tonight's testing (they aren't `is_seed_data`-tagged). One-liner:
   ```sql
   DELETE FROM contact_enquiries WHERE email ILIKE '%@flyboytest.com' OR email ILIKE '%@example.com';
   DELETE FROM contact_attempts   WHERE email ILIKE '%@flyboytest.com' OR email ILIKE '%@example.com';
   DELETE FROM checkout_attempts  WHERE email ILIKE '%@flyboytest.com' OR email ILIKE '%@race.test';
   DELETE FROM rate_limit_events; -- test-only forensics, safe to zero out pre-launch
   ```
4. Only then update `NEXT_PUBLIC_API_BASE` and redeploy the public site.
