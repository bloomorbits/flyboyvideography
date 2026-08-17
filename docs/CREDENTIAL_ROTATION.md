# Credential Rotation Runbook

This document is the source of truth for how we rotate any credential
(Supabase service-role key, Stripe key, Resend key, etc.) used by the
Flyboy Videography portal + public site. Every rotation MUST end with an
empirical verification step against a live endpoint — the deploy
pipeline reporting "success" is not proof that the running process has
the new value.

## Why this runbook exists

On 2026-02 we rotated the Supabase service-role key after a push-protection
incident. The `.env` file was updated correctly, the deploy pipeline
reported success, but the FastAPI process was still holding the previous
key in memory. Every backend endpoint that used the service-role key
returned `401 Invalid or expired token` until we ran
`sudo supervisorctl restart backend` in the preview pod. The lesson: the
running process's memory, not the deploy artefact, is what matters.
Verify it directly, every single time.

## Rotation flow

Follow these steps in order. Do NOT skip step 5.

### 1. Rotate at the provider
- Supabase: Dashboard → Project Settings → API → rotate the
  `service_role` key. Copy the new value.
- Stripe / Resend / others: equivalent rotation UI at the provider.
- Immediately treat the OLD value as compromised — assume it will
  continue to work at the provider for a short overlap window (varies
  by provider) and use that window to update consumers before the old
  key hard-fails.

### 2. Update `backend/.env` (preview pod)
- Edit `SUPABASE_SERVICE_ROLE_KEY` in `/app/backend/.env` on the preview
  pod. Do not add comments or quotes; do not commit `.env` (it is in
  `.gitignore`).
- Restart the backend so it re-reads `.env`:
  ```
  sudo supervisorctl restart backend
  ```
  Hot-reload rescans Python code, NOT env vars. A restart is required.

### 3. Update the deployment env
- Emergent deploy: update `SUPABASE_SERVICE_ROLE_KEY` in the deployment
  env-var UI.
- Whether Emergent auto-restarts the container on env-var change is
  currently **NOT DEFINITIVELY CONFIRMED** — an official answer is
  pending from support@emergent.sh (ticket opened 2026-02). Until the
  official answer lands, treat every env-var change as requiring a
  manual redeploy of the backend service.
- If deploying to Vercel / Railway / other: consult that provider's
  docs. Most require a redeploy for env changes to take effect at
  runtime.

### 4. Verify locally against the preview pod
Export the same env values into your shell (or `source backend/.env`
carefully — do not paste it into chat) and run:

```bash
SUPABASE_URL="https://your-project.supabase.co" \
SUPABASE_ANON_KEY="sb_publishable_..." \
ADMIN_EMAIL="flyboy.admin.demo@gmail.com" \
./scripts/verify_supabase_key.sh https://db-bridge-5.preview.emergentagent.com
```

The script will prompt for the admin password (hidden input) if
`ADMIN_PASSWORD` is not exported. Do NOT pass the password as a CLI
argument — it will end up in shell history.

Expected: `ROTATION VERIFIED`, exit code 0.

### 5. Verify against the DEPLOYED backend (mandatory)
Repeat step 4 with `BASE_URL` pointing at the production/deployment URL,
not the preview pod. This is the step that catches "deploy succeeded
but the process is still holding the old key".

```bash
SUPABASE_URL="https://your-project.supabase.co" \
SUPABASE_ANON_KEY="sb_publishable_..." \
ADMIN_EMAIL="flyboy.admin.demo@gmail.com" \
./scripts/verify_supabase_key.sh https://api.flyboyvideography.com
```

Expected: `ROTATION VERIFIED`, exit code 0.

If you get `HTTP 401` at this step:
- The deployed backend is running with the OLD key in memory.
- Trigger a manual redeploy / container restart on the deployment
  target, then re-run step 5.
- Do NOT consider the rotation closed until step 5 returns exit 0.

### 6. Confirm old key is inert (recommended)
Optional but strongly recommended for time-sensitive rotations
(e.g. an actual leak, not just hygiene). Attempt one direct call to the
provider using the OLD key and confirm it now fails. This proves the
provider actually invalidated the old key rather than silently keeping
both live. For Supabase:

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -H "apikey: <OLD_SERVICE_ROLE_KEY>" \
  -H "Authorization: Bearer <OLD_SERVICE_ROLE_KEY>" \
  "https://your-project.supabase.co/rest/v1/clients?select=id&limit=1"
```

Expected: `401`. If it returns `200` the provider is still honouring
the old key — check the provider's rotation UI to see whether the old
key has an explicit expiry / revoke action.

### 7. Update rotation log
Append a line to the "Rotation log" section below with the date, which
credential rotated, and any incidents / anomalies observed.

## Exit code reference for `verify_supabase_key.sh`

| Exit | Meaning |
|-----:|:--------|
| 0 | Everything green. Rotation is live end-to-end. |
| 1 | Script config error (missing env var, missing curl/python3, wrong arg). |
| 2 | Supabase Auth login failed. Wrong anon key or wrong admin credentials. |
| 3 | Backend canary endpoint did not return 200. Deployed process is running with stale key, or the env var name is wrong, or the pasted key had whitespace. |

## What the canary actually tests

`GET /api/admin/erasure-audit` was chosen because:

1. It is admin-scoped, so the backend must decode the caller's Supabase
   Auth JWT to authorize the request. That exercises the Auth path.
2. Internally the endpoint reads `erasure_audit_log` using the
   server-side service-role key (RLS blocks the anon path for admin
   reads). If the backend process is holding a stale service-role key,
   this endpoint fails, even though the deploy artefact looks fine.
3. It is idempotent and read-only, so running the canary repeatedly is
   safe.

If the backend surface changes and `/api/admin/erasure-audit` is
renamed or removed, update the `CANARY_PATH` variable in
`scripts/verify_supabase_key.sh` and this document.

## Rotation log

| Date | Credential | Ticket / reason | Verified preview | Verified deploy | Notes |
|:-----|:-----------|:----------------|:-----------------|:----------------|:------|
| 2026-02 | Supabase service-role | GitHub push-protection block on hardcoded test-file literal; history rewritten; provider key rotated | yes (post backend restart) | yes (via /api/admin/erasure-audit canary) | Backend needed manual `supervisorctl restart` in preview — hot-reload does not re-read `.env`. |
| 2026-02 | Stripe sandbox provisioned | Phase 1 booking flow — claimable sandbox `acct_1U4cyqEemFmdl6rE`, job_id below | yes (backend restarted, /api/health returned 200) | not yet deployed | Test mode only. Not yet claimed to a live Stripe account (deferred until client is ready — see Ownership handoff section). |
| 2026-02 | Railway backend cutover | Migrating off Emergent preview to `https://flyboyvideography.up.railway.app` (PL-INFRA-1/2 hard gate) | yes (via `/api/health` returning `{"status":"ok","database":"supabase"}`) | in progress — Stripe webhook + full smoke test still pending | Railpack builder (Nixpacks deprecated), `/backend` root dir, target port 8080. Emergent-only deps (`emergentintegrations`, `litellm` CDN wheel) removed from requirements.txt to unblock build. |

## Stripe sandbox (provisioned 2026-02)


The Stripe integration uses an Emergent-managed **claimable sandbox**.
Key identifiers you will need if you ever have to re-provision, tear
down, or hand ownership to the client:

| Field | Value |
|:------|:------|
| Sandbox job_id (idempotent — POST-ing again returns the same sandbox) | `dc553f4d-1789-490a-8367-9a077316a503` |
| Stripe sandbox account_id | `acct_1U4cyqEemFmdl6rE` |
| Onboarding URL (single-use — click to claim as a real live Stripe account) | See `/tmp/onboarding_url.txt` in the preview pod after provisioning, or ask the agent to re-fetch via a status GET |
| Env vars auto-injected on provision | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_ACCOUNT_ID`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_MODE=test` |

### Ownership handoff (going live)

The sandbox has no legal owner until someone clicks `onboarding_url`
and completes Stripe KYC (business details + bank + ID). Per the
project's ownership rule: **only the client should click that URL** —
they become the Stripe account holder in their own name. Neither
Bloom Orbit nor the agent should ever complete KYC on this sandbox.

When KYC completes, Stripe auto-promotes the sandbox test data
structure to a live account, the platform triggers a redeployment that
swaps sandbox keys for live keys, and `STRIPE_MODE` flips from `test`
to `live`. Nothing to change in code.

### Teardown / re-provision

The `job_id` above is idempotent — POST-ing to `/stripe/sandboxes`
again with it returns the **existing** sandbox, never a duplicate. If
a full reset is genuinely needed (destructive — loses all catalog /
products / prices):

1. Ask the user first via `ask_human` — never DELETE on assumption.
2. `DELETE {INTEGRATION_PROXY_URL}/stripe/jobs/dc553f4d-1789-490a-8367-9a077316a503/sandbox`
   with the same bearer key used at provision time.
3. Remove all `STRIPE_*` values from `backend/.env` in the same turn.
4. Either drop Stripe code entirely, or POST again to get a fresh
   sandbox and re-run catalog setup. Do NOT leave the app in a
   half-deleted state.

### Tax mode revisit triggers

Current tax mode is **DIY** — Stripe processes the payment, we
handle tax filing ourselves. Chosen because the client is not
VAT-registered as of 2026-02 and UK event videography services below
the £90k threshold don't need VAT collection at checkout.

**Flip to `calc_only` (Stripe calculates tax at checkout, +0.5%/txn)
when any of the following becomes true:**

- Client turnover approaches / crosses the UK VAT threshold (£90k as
  of 2026, verify current threshold at
  https://www.gov.uk/vat-registration/how-to-register).
- Client voluntarily registers for VAT (some businesses do this
  below-threshold to reclaim input VAT).
- Client starts selling into other EU/UK-adjacent tax jurisdictions
  where OSS/IOSS or equivalent applies.

The tax mode switch is a small code change (one branch in the
`create_checkout_session` call) plus enabling Stripe Tax in the
Stripe Dashboard. The change point is marked in code with a
`TAX MODE` comment near the `stripe.checkout.Session.create(...)` call.

## GitHub repo ownership transfer (deferred until client handoff)

The codebase currently lives at **`github.com/bloomorbits/flyboyvideography`**
(Bloom Orbit-owned). Railway and Vercel are being connected to this repo
during the 2026-02 cutover — this is deliberate for now, so Bloom Orbit
retains push/deploy access during build-out. When the project is handed
to the client, the repo will move to a client-owned location (either a
transfer of the existing repo, or a fresh push to a client-created repo).

**Critical, easy-to-miss step at handoff:** Transferring the repo alone
is NOT sufficient. Railway's and Vercel's Git integrations are bound to
the repo's Bloom Orbit-owned identity at the moment they were connected;
transferring ownership of the GitHub repo does not automatically re-point
those integrations. Both must be explicitly disconnected and re-authorised
from the client's account.

**Handoff checklist (repo + CI/CD):**

1. Confirm client has GitHub organisation / user account ready to receive
   the repo (or a new empty repo they've pre-created).
2. **Repo:** Use GitHub's "Transfer ownership" flow
   (Settings → Danger zone → Transfer) if keeping the same repo, OR push
   this codebase to the client's fresh repo and archive the Bloom Orbit
   copy. Preserve `main` branch history either way.
3. **Railway:**
   - Log into Railway as the client (they must create/own the Railway
     project going forward — same principle as the Stripe KYC rule).
   - In the FastAPI service → Settings → Source → **Disconnect** the
     `bloomorbits/flyboyvideography` connection.
   - Reconnect via the client's GitHub account, pointing at the new repo
     location. Confirm the deploy branch (`main`) and root dir (`/backend`)
     re-populate correctly.
   - Trigger a manual redeploy, verify it picks up the client's GitHub
     webhook (test: push a trivial change → confirm auto-deploy fires).
4. **Vercel (Next.js public site):**
   - Same pattern — Settings → Git → Disconnect, then reconnect via the
     client's Vercel account (which must be linked to their GitHub).
   - Verify the `NEXT_PUBLIC_*` env vars survived the disconnect (they're
     stored on the Vercel project, not the Git connection — but confirm
     empirically after reconnect, don't assume).
   - Push a trivial change, confirm auto-deploy fires from the new
     connection.
5. **Vercel (CRA client portal), if separate project:** same as step 4.
6. **Bloom Orbit access removal:** After the client confirms all three
   redeploys work end-to-end, remove Bloom Orbit's GitHub access to the
   repo (or accept the transfer completing this automatically), and
   remove Bloom Orbit from Railway and Vercel project members.

**Why this section exists:** it's the kind of infra-side detail that's
invisible until it breaks. Left undocumented, a future agent (or future
Nathan) transferring the repo will find CI/CD silently continuing to
deploy from Bloom Orbit's GitHub identity, or — worse — will disconnect
Bloom Orbit's GitHub access first and break production deploys until
the client-side reconnect is figured out.

## Pre-launch infra tasks (P0 — MUST be resolved before real, high-value traffic)

> **HARD GATE (user directive, 2026-02):** NO live-mode Stripe traffic goes
> to the `/book` page or the FastAPI booking endpoints until BOTH
> **PL-INFRA-1** (XFF strip) and **PL-INFRA-2** (CORS override) are
> verified resolved on the deployment that will receive real payments.
> The layered defense shipped in the app (rate limiter + concurrent-lock
> caps + global circuit breaker) is a MITIGATION not a FIX; it converts
> the attack from "trivially freeze the calendar" into "requires a
> sustained flood to hold the global brake open" — which is still a
> customer-facing DoS. This gate is not a nice-to-have; it exists because
> the residual DoS was flagged MEDIUM in the 2026-02 security audit
> (SEC-002-residual) and both root causes live at the edge, not in the
> application code. Do not promote the Stripe sandbox to live mode until
> both PL-INFRA items are verified per their "Verify" sections below.

These are edge/ingress-layer misconfigurations, not code bugs. They cannot
be fully mitigated from the FastAPI app because the ingress runs *in
front* of it and overrides headers on the way in and out. The layered
defenses shipped in the app on 2026-02 (rate-limiter + concurrent-lock
caps + global circuit breaker for SEC-001; static allowlist for the open
redirect; ALLOWED_ORIGIN_URLS + CORS_ORIGINS env vars) are mitigations,
not fixes. Do not consider the SEC audit closed until these are done.

### PL-INFRA-1 [P0] — Strip client-supplied `X-Forwarded-For` at the edge

**Related unresolved audit finding: SEC-002-residual [MEDIUM].** The
global circuit breaker in `booking.py::_rate_limit_or_429` / `_concurrent_lock_or_429`
converts a per-attacker DoS into a whole-site lockout because we cannot
identify individual attackers under XFF spoofing. This is **fully
contingent on PL-INFRA-1 completing** — no additional application-layer
mitigation is planned or possible without a trustworthy client IP.
Status: **STILL OPEN, mitigated only by PL-INFRA-1**.

**Empirical finding (2026-02):** The Emergent preview ingress does NOT
strip a client-supplied `X-Forwarded-For` prefix — it merely appends its
own hops. `curl -H "X-Forwarded-For: 1.2.3.4" $BACKEND/api/_probe/ip`
reaches FastAPI with the spoofed value still in the leftmost position of
the header. Standard nginx-ingress with `use-forwarded-headers: false`
or `use-forwarded-headers: true` combined with `enable-real-ip: true` +
`set-real-ip-from: <trusted-proxy-cidr>` would drop this.

**Impact:** IP-based rate limiting (`RL_MAX_PER_IP`, `LOCK_CAP_PER_IP` in
`/app/backend/booking.py`) is best-effort only. A bot that varies both the
XFF header AND the email address on every request will bypass every
per-source cap. The GLOBAL circuit breaker (`RL_MAX_GLOBAL`,
`LOCK_CAP_GLOBAL`) is the current backstop but it's a system-wide brake,
not a per-attacker one — a determined attacker can still starve
legitimate users.

**Fix (choose one, in order of preference):**
1. Configure the ingress to REPLACE (not append to) `X-Forwarded-For` at
   the edge so only the trusted proxy chain is visible to the app.
2. Have the ingress set a bespoke, non-spoofable header like
   `X-Emergent-Client-IP: <real>` after stripping the client-supplied
   version. Update `_client_ip()` in `booking.py` to prefer it.
3. If neither is available on Emergent Deploy: put a Cloudflare Worker
   or equivalent in front that sets `CF-Connecting-IP` and drop trust
   in XFF entirely.

**Verify:** Send a probe request with a spoofed `X-Forwarded-For` prefix
against the deployed backend, e.g. via a temporary probe endpoint added
for the check (a 5-line FastAPI route that echoes back
`request.headers.get("x-forwarded-for")`, `request.headers.get("x-real-ip")`,
and `request.client.host`, then removed immediately after). Expect that
`1.2.3.4` does NOT appear anywhere in the header FastAPI sees. Then
re-run scenario C in `/app/backend/tests/sim_calendar_freeze_attack.py`
against the deployed backend and confirm the **per-IP** cap fires around
attempt 6, not the global one at attempt 51.

### PL-INFRA-2 [P0] — Do not inject `Access-Control-Allow-Origin: *` at the edge

**Empirical finding (2026-02):** The Emergent preview ingress rewrites
`access-control-allow-origin` to `*` on every response (verified via
`curl -i -H "Origin: https://evil.example.com" $BACKEND/api/health`
returning `access-control-allow-origin: *` regardless of what FastAPI
set). FastAPI-level tightening
(`CORS_ORIGINS=https://flyboyvideography.com,...`) is correctly applied
on `localhost:8001` (direct-to-app) — verified — but is masked on the
public preview URL by the ingress override.

**Impact:** Any origin can currently make cross-origin XHR/fetch calls
to the preview backend from a user's browser. The API's own auth (bearer
JWT) still applies, but this defeats the defense-in-depth CORS layer we
would otherwise have.

**Fix:** Configure the ingress / Emergent Deploy to pass through the
application's `Access-Control-Allow-*` headers verbatim rather than
overriding them. If Emergent Deploy runs a global "dev-mode friendly"
CORS at the platform layer, request an opt-out for production
deployments.

**Verify:**
```
curl -i -H "Origin: https://evil.example.com" $DEPLOYED/api/health \
  | grep -i access-control-allow-origin
```
Expect NO `access-control-allow-origin` header (or one that echoes only
allow-listed origins), never `*`.

### PL-INFRA-3 [P0] — Rotate all secrets before live traffic

The `.env` currently in the preview pod holds:
- `SUPABASE_SERVICE_ROLE_KEY` (bypasses all RLS)
- `STRIPE_SECRET_KEY` + `STRIPE_WEBHOOK_SECRET` (currently sandbox — will
  become live keys the moment the client claims the sandbox via KYC)
- `RESEND_API_KEY`

They were confirmed clean from git history in the 2026-02 scrub, and are
not exposed to the frontend or the public Next.js site. But they have
been visible in this preview pod / deployment logs during dev, and every
credential visible outside its provider dashboard should be rotated once
before real traffic.

**Fix:** After the sandbox is claimed (KYC completed by the client and
Stripe promotes to a live account), rotate ALL three provider keys in
sequence following the flow in the "Rotation flow" section above. Verify
each rotation against the DEPLOYED backend (step 5 of the flow), not the
preview pod.

### Cross-reference

- Application-layer mitigations that partially cover the above are in
  `/app/backend/booking.py`:
  - `_rate_limit_or_429`, `_concurrent_lock_or_429` (SEC-001)
  - `ALLOWED_ORIGIN_URLS` allowlist (open redirect)
  - `email_confirm=False` on `admin.create_user` (SEC-002)
- Concurrency + rate-limit proof: `tests/test_booking_concurrency.py`
  and `tests/sim_calendar_freeze_attack.py`.
