# Railway + Vercel cutover — copy-paste reference

**Read this alongside `/app/docs/CREDENTIAL_ROTATION.md § Pre-launch infra tasks`. Deploying to Railway + Vercel is the concrete action that resolves PL-INFRA-1 and PL-INFRA-2, closing the HARD GATE on live-mode Stripe.**

## Deployed environments (as of 2026-02 cutover)

| Env | Service | URL | Notes |
|:----|:--------|:----|:------|
| Prod | FastAPI backend (Railway) | `https://flyboyvideography-production.up.railway.app` | Railpack builder, `/backend` root dir, Procfile-driven, PORT 8080 target. **Use the `-production` auto-generated domain, NOT a custom short domain** — the custom-short variant drifted out of sync on redeploy during initial cutover (2026-02) and was retired. See "Domain gotcha" below. |
| Prod | Next.js public site (Vercel) | `https://flyboyvideography.vercel.app` + custom `flyboyvideography.com` | Existing — needs `NEXT_PUBLIC_API_BASE` updated in Step 12 |
| Prod | CRA client portal (Vercel) | *pending Step 9* | Will be `https://<subdomain>.vercel.app` |
| Legacy | Preview pod | `https://db-bridge-5.preview.emergentagent.com` | Retire after Step 13 confirms end-to-end on prod |

### Domain gotcha (2026-02 lesson learned)

Railway auto-generates a default domain when the service is created: `<service>-<environment>.up.railway.app` (e.g. `flyboyvideography-production.up.railway.app`). This domain is **wired to the correct target port by Railway itself**, survives redeploys, and never drifts.

The "Generate Service Domain" wizard also offers to create a **second, custom short-name domain** (e.g. `flyboyvideography.up.railway.app`). It looks like a cleaner alternative but is a separate domain record whose target port can drift out of sync on redeploy. During the 2026-02 cutover, adding `STRIPE_WEBHOOK_SECRET` and redeploying appeared to knock the custom-short domain's target port off — the `-production` domain kept serving, the custom-short one started returning Railway's "train has not arrived at the station" 502 page for ~15 minutes.

**Rule:** Always use the `-<env>.up.railway.app` auto-generated domain as the canonical service URL. Only use the "Generate Service Domain" wizard when you need a CUSTOM DOMAIN CNAME (e.g. `api.flyboyvideography.com`) — not for a shorter-but-still-`railway.app` alias. The short alias is a footgun with no upside once you're on your real custom domain anyway.

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

## After Railway is up: verify the XFF trust boundary — ✅ DONE (2026-02 cutover)

This section is retained as a HISTORICAL record. The verification has already been executed against `flyboyvideography-production.up.railway.app` and the runbook items closed out. **Do NOT re-add the probe route** unless you're moving off Railway to a new deployment target — in which case, re-run this same procedure against the new target.

**What was done (commit trail):**
- `a4f0a68` — added temporary `/api/_probe/ip` route to `server.py`.
- Probe run against Railway with spoofed `X-Real-IP` and `X-Forwarded-For` inputs. 4 scenarios executed (A/B/C/D). Real pod public IP: `34.16.56.64`. Every spoofed prefix was dropped by Railway's ingress. Full result table lives in `CREDENTIAL_ROTATION.md § PL-INFRA-1 → "Verified resolved on Railway (2026-02 cutover)"`.
- `f0d53f9` — probe route removed, `_client_ip()` in `backend/booking.py:150-195` updated to prefer `X-Real-IP` (leftmost XFF fallback, then `request.client.host`). Confirmed 404 on `/api/_probe/ip` post-redeploy.

**Steady state:** `GET https://flyboyvideography-production.up.railway.app/api/_probe/ip` → `404 Not Found`. This is INTENTIONAL. PL-INFRA-1 is CLOSED.

**If the deployment ever moves off Railway** (new target = Fly, Render, custom k8s, etc.):

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
2. `curl -H "X-Forwarded-For: 1.2.3.4" -H "X-Real-IP: 1.2.3.4" https://<new-target>/api/_probe/ip`
3. Confirm `x_real_ip` in the response is NOT `1.2.3.4` (edge stripped the spoof) and matches your actual public IP.
4. If confirmed: no code change needed (the current `_client_ip()` already prefers `X-Real-IP`). If NOT confirmed: `_client_ip()` must be reworked — do NOT flip live until this is resolved.
5. Remove the probe endpoint in the same commit that captures the empirical table into `CREDENTIAL_ROTATION.md § PL-INFRA-1`.

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
