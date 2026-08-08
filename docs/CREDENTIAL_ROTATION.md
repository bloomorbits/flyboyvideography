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
| 2026-02 | Supabase service-role | GitHub push-protection block on hardcoded test-file literal; history rewritten; provider key rotated | yes (post backend restart) | pending user | Backend needed manual `supervisorctl restart` in preview — hot-reload does not re-read `.env`. |
