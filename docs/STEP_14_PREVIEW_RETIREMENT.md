# Step 14 — Preview Infrastructure Retirement Runbook

**Status:** DRAFT — do not execute until the 24h dual-delivery observation window closes clean.
**Window start:** 2026-08-21T18:50Z (first Railway audit row landed)
**Earliest safe execution:** 2026-08-22T18:50Z
**Executor:** you (with agent standing by for verification steps)
**Execution mode:** you execute each phase manually; agent verifies before you proceed to the next. **NO back-to-back automation of Phases 1→3.** A hard checkpoint (agent verification + your explicit "proceed") sits between every phase. Rationale: tonight established that things can look fine right up until they aren't — the api_version landmine was invisible at every API-surface check until we hit the dashboard delivery tab. Same discipline applies to every destructive step here.
**Rollback safety:** every destructive step (delete endpoint, remove env var) has a documented rollback below.

---

## Pre-flight gates — ALL must pass before starting

Do NOT proceed to Phase 1 until every checkbox is green.

- [ ] **Gate 1 — Observation window duration.**
      `monitor_dual_delivery.py --hours 24` shows `span >= 24h` (or as long as you're actually observing).

- [ ] **Gate 2 — Attribution health.**
      Monitor output: `preview_only == 0` AND `railway_only == 0` for every checkpoint (6h/12h/24h).
      Any single `preview_only > 0` event means Railway missed a delivery → do NOT retire until root-caused.

- [ ] **Gate 3 — Railway received real traffic.**
      Monitor: `by_pod.railway.total >= 3` (arbitrary floor — enough to know it's not just one lucky delivery).
      If your business volume is lower, extend the observation window until you have at least 3 completed-event deliveries on Railway.

- [ ] **Gate 4 — No error outcomes on Railway.**
      Monitor: `by_pod.railway.err == 0`. Any Railway 4xx/5xx (except one-time signature failures during whsec rotation) blocks retirement.

- [ ] **Gate 5 — Railway finalisation-path latency test (blind-spot mitigation).**
      During dual-delivery, preview always wins the race and Railway hits the skip path, so we have no `finalised`-path numbers for Railway. Run the controlled test in **Phase 0** below to get at least ONE `finalised` sample from Railway before proceeding.

---

## Phase 0 — Controlled Railway finalisation latency test (10 min)

**Why:** without this we retire preview blind to whether Railway's `_finalise_paid_session` path performs acceptably. Preview's numbers are ~2.4s p95 — we need to know Railway is in the same ballpark, not 15s.

**Steps:**

1. **Temporarily disable the preview endpoint via Stripe API** (do NOT delete — we're not committed yet):
   ```bash
   cd /app && python3 -c "
   import stripe
   from dotenv import dotenv_values
   env = dotenv_values('/app/backend/.env')
   stripe.api_key = env['STRIPE_SECRET_KEY']
   we = stripe.WebhookEndpoint.modify('we_1U4jtfEemFmdl6rEqcuUYuES', disabled=True)
   print('preview endpoint status now:', we.status)
   "
   ```
   Expected: `disabled`.

2. **Trigger one real test checkout** on `flyboyvideography.com/book`. Complete payment.

3. **Wait ~10s, then run the monitor** for the last 30 min:
   ```bash
   python3 /app/scripts/monitor_dual_delivery.py --hours 0.5
   ```
   Expected: `by_pod.railway.processing_ms_finalised.n >= 1`, and the number should be in the same order of magnitude as preview's ~2.4s p95 (call it OK up to ~5s; > 8s warrants investigation before retirement).

4. **Re-enable preview immediately** (regardless of test outcome — we want dual-delivery back on until we've decided):
   ```bash
   cd /app && python3 -c "
   import stripe
   from dotenv import dotenv_values
   env = dotenv_values('/app/backend/.env')
   stripe.api_key = env['STRIPE_SECRET_KEY']
   we = stripe.WebhookEndpoint.modify('we_1U4jtfEemFmdl6rEqcuUYuES', disabled=False)
   print('preview endpoint status now:', we.status)
   "
   ```

5. **Evaluate:**
   - Railway `processing_ms_finalised` avg < 5000ms → ✅ proceed to Phase 1
   - Railway `processing_ms_finalised` avg 5000-8000ms → ⚠️ investigate Supabase network hop from Railway region; retirement can proceed but track as tech-debt
   - Railway `processing_ms_finalised` avg > 8000ms OR outcome != `finalised` → 🛑 STOP. Do not retire. Investigate.

---

## Phase 1 — Disable preview endpoint (reversible)

Stripe distinguishes "disabled" from "deleted". Disabled endpoints reject no events at the API level but stop receiving deliveries. We use this as a 24h burn-in period where Railway is the sole delivery target, but we can flip preview back on instantly if anything breaks.

1. **Disable preview endpoint via API:**
   ```bash
   cd /app && python3 -c "
   import stripe
   from dotenv import dotenv_values
   env = dotenv_values('/app/backend/.env')
   stripe.api_key = env['STRIPE_SECRET_KEY']
   we = stripe.WebhookEndpoint.modify('we_1U4jtfEemFmdl6rEqcuUYuES', disabled=True)
   print('preview endpoint status:', we.status)
   "
   ```

2. **Record the disable timestamp** (so we can measure the burn-in window).

3. **Verify in dashboard**: `https://dashboard.stripe.com/acct_1U4cyqEemFmdl6rE/test/workbench/webhooks` — preview endpoint should show as Disabled.

4. **Trigger one real test checkout** and confirm:
   - Booking finalises correctly (Supabase `bookings` row appears)
   - Monitor shows the event delivered to Railway ONLY:
     ```bash
     python3 /app/scripts/monitor_dual_delivery.py --hours 0.25
     ```
   - Expected: `railway_only == 1`, `preview_only == 0`, `seen_by_both == 0` for that event.

**Rollback in Phase 1**: re-enable preview by flipping `disabled=False` on the same script.

---

## Phase 2 — Burn-in period (Railway sole delivery, 24h minimum)

Same monitoring cadence as the dual-delivery window: 6h / 12h / 24h checkpoints.

**Pass criteria at each checkpoint:**
- `preview_only == 0` (should be trivially true — preview is disabled)
- `by_pod.railway.err == 0`
- `by_pod.railway.processing_ms_finalised` avg stays in the range established in Phase 0
- All completed checkouts show up in `webhook_deliveries_audit` with `pod_source='railway'` AND have a matching `bookings` row

**Fail criteria (rollback trigger):**
- Any Railway 4xx/5xx that wasn't a signature-failure recovery
- Any completed Stripe event whose session didn't finalise a `bookings` row within 60s
- Any customer complaint about booking not confirming

**Rollback in Phase 2**: re-enable preview (`disabled=False`) → dual-delivery immediately restored. No data lost because `_finalise_paid_session` is idempotent and audit table absorbs replays.

---

## Phase 3 — Delete preview endpoint (irreversible)

Only after Phase 2 completes clean.

1. **Delete via API** (this is what makes the retirement irreversible — the endpoint id and `whsec_...` are gone forever):
   ```bash
   cd /app && python3 -c "
   import stripe
   from dotenv import dotenv_values
   env = dotenv_values('/app/backend/.env')
   stripe.api_key = env['STRIPE_SECRET_KEY']
   stripe.WebhookEndpoint.delete('we_1U4jtfEemFmdl6rEqcuUYuES')
   print('preview endpoint deleted.')
   print('Remaining endpoints:')
   for we in stripe.WebhookEndpoint.list(limit=10).auto_paging_iter():
       print(f'  {we.id}  {we.url}  {we.status}')
   "
   ```
   Expected remaining: only `we_1U6w1UEemFmdl6rEIe1f8pi1` (Railway).

**Rollback in Phase 3**: not truly possible — you'd have to recreate a new preview endpoint (new id, new whsec_), update preview's `STRIPE_WEBHOOK_SECRET`, redeploy preview. Which is fine as a disaster recovery path, but not "rollback" in a meaningful sense.

---

## Phase 4 — Strip preview URL from Railway env vars

Preview URL is currently in Railway's `CORS_ORIGINS` and `ALLOWED_ORIGIN_URLS` so the preview backend could accept requests. With preview retired, those entries are dead weight and a potential open-redirect / attack-surface risk if the preview URL is ever reassigned to a different tenant.

1. **Get current values** — Railway dashboard → backend service → Variables. Screenshot both values BEFORE editing.

2. **Edit `CORS_ORIGINS`**:
   - Before: `https://flyboyvideography.com,https://www.flyboyvideography.com,https://flyboyvideography.vercel.app,https://db-bridge-5.preview.emergentagent.com,https://<cra-portal>.vercel.app`
   - After: `https://flyboyvideography.com,https://www.flyboyvideography.com,https://flyboyvideography.vercel.app,https://<cra-portal>.vercel.app`
   - Removed: `https://db-bridge-5.preview.emergentagent.com`

3. **Edit `ALLOWED_ORIGIN_URLS`** (same removal — used by booking.py for Stripe success/cancel URL allowlisting):
   - Same before/after as above.

4. **Railway redeploys automatically on env change.** Wait for the deploy to go green.

5. **Verify CORS is enforced post-edit** — a request from the preview URL must now be rejected:
   ```bash
   curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
     -H "Origin: https://db-bridge-5.preview.emergentagent.com" \
     -X OPTIONS https://flyboyvideography-production.up.railway.app/api/booking/availability
   ```
   Expected: `HTTP 400` or missing `Access-Control-Allow-Origin` header. NOT a 2xx with the preview origin echoed back.

6. **Verify legitimate origin still works:**
   ```bash
   curl -sS -o /dev/null -w "HTTP %{http_code}\n" \
     -H "Origin: https://flyboyvideography.com" \
     -X OPTIONS https://flyboyvideography-production.up.railway.app/api/booking/availability
   ```
   Expected: `HTTP 2xx`.

**Rollback in Phase 4**: paste the screenshotted "before" values back into Railway. Redeploys automatically.

---

## Phase 5 — Clean up Vercel `.env.local` and public site env

The Next.js public site (`/app/website/`) currently has `NEXT_PUBLIC_API_BASE=https://db-bridge-5.preview.emergentagent.com` in the ed dev container's `.env.local`. That doesn't affect production (Vercel uses its own env vars set via dashboard), but it's still stale and confusing for future dev sessions.

1. **Verify Vercel production env is already correct:**
   Vercel dashboard → `flyboyvideography` (public site) project → Settings → Environment Variables → look at `NEXT_PUBLIC_API_BASE` for the `Production` environment. Should be `https://flyboyvideography-production.up.railway.app`. If not, fix it there first — that's the one that matters.

2. **Confirm current production build is using the right base:**
   ```bash
   curl -sSI https://flyboyvideography.com/book | head -20
   # Then in browser DevTools -> Network tab on flyboyvideography.com/book:
   # confirm /api/booking/availability requests are going to Railway, not preview.
   ```

3. **Update ed dev `.env.local`** so future forks don't get confused:
   ```bash
   # /app/website/.env.local
   NEXT_PUBLIC_API_BASE=https://flyboyvideography-production.up.railway.app
   ```
   (Or delete the line entirely and rely on a fresh dev backend URL if you spin up a new preview.)

4. **Update CRA portal `.env.local` if needed:**
   Same rationale — check `REACT_APP_BACKEND_URL` in `/app/frontend/.env` and Vercel prod env for the CRA portal project.

**Rollback in Phase 5**: cosmetic only — no production impact if you skip or defer.

---

## Phase 6 — Final verification + close-out

1. **Run the monitor one final time** with a wide window covering both dual-delivery and burn-in:
   ```bash
   python3 /app/scripts/monitor_dual_delivery.py --hours 72
   ```
   Expected: clean audit trail showing the transition from dual to Railway-only.

2. **Update `docs/CREDENTIAL_ROTATION.md § PL-INFRA-*`** to close out the preview endpoint retirement and log the final state.

3. **Update `docs/RAILWAY_VERCEL_CUTOVER.md`** to mark Step 14 DONE with the completion timestamp.

4. **Update `/app/memory/PRD.md`** feature freeze status: unblock the deferred features (Admin Pricing / Enquiry Inbox / Phase 2 subscriptions / AuthPage.js magic-link recovery fix). Feature freeze is officially over.

5. **Consider retention policy for `webhook_deliveries_audit`** — the table grows unbounded. Suggested policy: keep 90 days of rows, purge older via a daily job or `pg_cron`. Not urgent but worth queueing as a P2 task.

---

## Emergency rollback (if disaster strikes post-Phase-3)

If preview is deleted and Railway starts failing:

1. Create a NEW webhook endpoint on Railway URL via API (same script we used originally — omit `api_version`):
   ```bash
   python3 /app/scripts/create_railway_stripe_webhook.py  # will refuse if endpoint exists; delete broken one first
   ```
2. Paste new `whsec_...` into Railway `STRIPE_WEBHOOK_SECRET`.
3. Railway redeploys.
4. Any events fired during the outage: they're already in Stripe with `pending_webhooks > 0` — Stripe's retry schedule (~1min, 5min, 30min, 1h, 2h, 4h, 8h up to 3 days) will deliver them once Railway's endpoint is back.
5. For customers stranded on `/book/success` during the outage: the inline `/api/booking/status` fallback probe will finalise them when they refresh. If they closed the tab: the retry queue catches them within the hour.

**No customer money is lost during the outage** because Stripe holds the payment intent and doesn't refund unilaterally. The booking simply won't finalise on our side until the webhook (or the polling fallback) fires.

---

## Endpoints, IDs, and secrets referenced in this runbook

| Name | Value |
|---|---|
| Stripe account (test mode) | `acct_1U4cyqEemFmdl6rE` |
| Preview endpoint id (to disable → delete) | `we_1U4jtfEemFmdl6rEqcuUYuES` |
| Preview endpoint URL | `https://db-bridge-5.preview.emergentagent.com/api/stripe/webhook` |
| Railway endpoint id (keep) | `we_1U6w1UEemFmdl6rEIe1f8pi1` |
| Railway endpoint URL | `https://flyboyvideography-production.up.railway.app/api/stripe/webhook` |
| Railway backend URL | `https://flyboyvideography-production.up.railway.app` |
| Monitor script | `/app/scripts/monitor_dual_delivery.py` |
| Audit table | `public.webhook_deliveries_audit` (Migration 011) |
| Pod source labels | Railway=`railway`, preview=`preview` |

Do NOT paste `whsec_...` values into this runbook. If you need to rotate the Railway secret, use the `stripe.WebhookEndpoint.create()` pattern from Phase 3 emergency rollback and rotate the env var directly on Railway.
