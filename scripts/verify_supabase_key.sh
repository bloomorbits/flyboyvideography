#!/usr/bin/env bash
# verify_supabase_key.sh — post-rotation canary for the Supabase service-role key.
#
# What this proves:
#   1. The Supabase anon key + admin email/password still authenticate
#      (i.e. Auth is reachable and the admin account is intact).
#   2. The BACKEND process running at $BASE_URL has the CURRENT
#      service-role key in memory — verified by hitting an admin
#      endpoint that internally uses SUPABASE_SERVICE_ROLE_KEY.
#
# Exit codes:
#   0  — everything green, rotation is fully live end-to-end
#   1  — precondition / config error (missing args, missing env, etc.)
#   2  — Supabase Auth login failed (anon key or admin creds are wrong)
#   3  — Backend admin endpoint did not return 200 (backend is running
#        with a stale service-role key, or has not been restarted)
#
# Usage:
#   SUPABASE_URL=https://xxx.supabase.co \
#   SUPABASE_ANON_KEY=sb_publishable_xxx \
#   ADMIN_EMAIL=you@example.com \
#   ADMIN_PASSWORD='...' \
#   ./scripts/verify_supabase_key.sh https://your-deployed-backend.example.com
#
# Notes:
#   - No secrets are ever accepted as CLI args or echoed to stdout.
#   - Password is read interactively if ADMIN_PASSWORD is not exported.
#   - Run this against BOTH preview and deployed backends after every
#     rotation. See docs/CREDENTIAL_ROTATION.md for the full runbook.

set -eu

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <BASE_URL>"
  echo "  BASE_URL must NOT include a trailing /api segment."
  exit 1
fi

BASE_URL="${1%/}"
CANARY_PATH="/api/admin/erasure-audit"

: "${SUPABASE_URL:?SUPABASE_URL not exported}"
: "${SUPABASE_ANON_KEY:?SUPABASE_ANON_KEY not exported (safe to expose — publishable key)}"
: "${ADMIN_EMAIL:?ADMIN_EMAIL not exported}"

if [ -z "${ADMIN_PASSWORD:-}" ]; then
  printf "Admin password (input hidden): "
  stty -echo
  IFS= read -r ADMIN_PASSWORD
  stty echo
  printf "\n"
fi

if [ -z "$ADMIN_PASSWORD" ]; then
  echo "ERROR: ADMIN_PASSWORD is empty" >&2
  exit 1
fi

command -v curl >/dev/null || { echo "ERROR: curl is required" >&2; exit 1; }
command -v python3 >/dev/null || { echo "ERROR: python3 is required" >&2; exit 1; }

echo "==> Target backend: $BASE_URL"
echo "==> Canary endpoint: $CANARY_PATH"
echo "==> Supabase project: $SUPABASE_URL"
echo

# ---- Step 1: Log in as admin against Supabase Auth ----
echo "[1/2] Logging in as admin against Supabase Auth ..."
LOGIN_BODY=$(python3 -c 'import json,os,sys; print(json.dumps({"email": os.environ["ADMIN_EMAIL"], "password": os.environ["ADMIN_PASSWORD"]}))')

LOGIN_TMP=$(mktemp)
trap 'rm -f "$LOGIN_TMP" "${AUDIT_TMP:-}"' EXIT

LOGIN_CODE=$(
  ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  curl -sS -o "$LOGIN_TMP" -w "%{http_code}" \
    -X POST "$SUPABASE_URL/auth/v1/token?grant_type=password" \
    -H "apikey: $SUPABASE_ANON_KEY" \
    -H "Content-Type: application/json" \
    --data-binary "$LOGIN_BODY"
)

if [ "$LOGIN_CODE" != "200" ]; then
  echo "  FAIL — Supabase Auth returned HTTP $LOGIN_CODE"
  echo "  Response: $(cat "$LOGIN_TMP")"
  echo
  echo "  Likely causes:"
  echo "    - Wrong SUPABASE_ANON_KEY / SUPABASE_URL"
  echo "    - Admin email or password incorrect"
  echo "    - Admin account was deleted or Auth is down"
  exit 2
fi

ACCESS_TOKEN=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["access_token"])' "$LOGIN_TMP")

if [ -z "$ACCESS_TOKEN" ]; then
  echo "  FAIL — login returned 200 but no access_token in body"
  exit 2
fi

echo "  OK — got access_token (Auth reachable, admin creds valid)"
echo

# ---- Step 2: Hit backend canary endpoint that requires service-role key ----
echo "[2/2] Calling backend canary $CANARY_PATH with admin JWT ..."
AUDIT_TMP=$(mktemp)

AUDIT_CODE=$(
  curl -sS -o "$AUDIT_TMP" -w "%{http_code}" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    "$BASE_URL$CANARY_PATH"
)

if [ "$AUDIT_CODE" != "200" ]; then
  echo "  FAIL — $CANARY_PATH returned HTTP $AUDIT_CODE"
  echo "  Response: $(cat "$AUDIT_TMP")"
  echo
  echo "  Likely causes:"
  echo "    - Deployed backend still holds the OLD service-role key in memory"
  echo "      (redeploy / restart the backend container so it re-reads env)"
  echo "    - Env var name in deployment settings is not SUPABASE_SERVICE_ROLE_KEY"
  echo "    - New key was pasted with whitespace/newline"
  exit 3
fi

# sanity-check the response is JSON
if ! python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$AUDIT_TMP" >/dev/null 2>&1; then
  echo "  FAIL — 200 returned but body is not valid JSON"
  echo "  First 200 chars: $(head -c 200 "$AUDIT_TMP")"
  exit 3
fi

ROWS=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(len(d) if isinstance(d,list) else "?")' "$AUDIT_TMP")

echo "  OK — HTTP 200, audit rows returned: $ROWS"
echo
echo "==> ROTATION VERIFIED"
echo "    Backend at $BASE_URL is running with the current service-role key."
exit 0
