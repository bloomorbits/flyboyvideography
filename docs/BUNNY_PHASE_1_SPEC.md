# Bunny.net Phase 1 — build spec (locked)

**Status:** design locked; awaiting Nathan's Bunny.net account setup before build starts next session. No dependent code exists yet.

## ⚠ Update — MediaCage Basic DRM is ENABLED (revisits watermarking scope)

Nathan enabled **MediaCage Basic DRM** on the Stream library — this goes
beyond the original Phase 1 scope (which assumed static watermark + HTML
overlay as the *only* protection). What this changes, verified against
Bunny's current docs:

**Player integration — unchanged, and now mandatory.** MediaCage *requires*
playback through Bunny's proprietary embed iframe with Embed View Token
Authentication — which is exactly what endpoint #1 + the `DeliverableDetail`
rework already design (signed `token`/`expires` → `<iframe>`). So the plan
stands. BUT MediaCage also **forbids**:
- MP4 fallback, direct HLS manifest/segment access, third-party players,
  and "Early-Play". Any direct-file code path returns **403** by design.
- Therefore the legacy `<iframe src={deliv.video_url}>` direct render must be
  **fully retired**, not kept as a graceful fallback. Iframe-embed is the
  ONLY supported playback path.
- Canonical embed host: `https://iframe.mediadelivery.net/embed/{libraryId}/{videoGuid}?token={token}&expires={unix}`.

**Protection level — materially UP, but still NOT leak-traceable.**
- MediaCage Basic uses dynamic, session-based **clear-key** encryption. It
  genuinely defeats common downloaders and third-party players — the
  "someone rips the raw file and reposts it" vector is now real-protected,
  not just deterred. This is a substantive upgrade over the original
  "static watermark is the only protection" assumption.
- It is **not** studio-grade DRM (clear-key ≠ Widevine/PlayReady; that's
  MediaCage Enterprise). And it provides **no forensic traceability**: the
  burnt-in watermark is still identical for every viewer, and a determined
  screen-recording still produces a clean-ish copy. If a leak happens, the
  pixels still can't tell you *which* client leaked it.

**HTML session-code overlay — KEEP as a complementary layer, with a caveat.**
- MediaCage covers the download/rip vector; the overlay covers the
  screen-record vector (a visible per-client ref appears in any recording).
  They're complementary, not redundant.
- **Caveat (honest):** the overlay is a parent-page `<div>` positioned over
  the iframe, so it **vanishes in fullscreen** (fullscreen renders only
  iframe content). A fullscreen screen-recording won't capture it. It's a
  cheap deterrent, not robust protection, and still not per-view traceable.

**Download policy (resolved with Nathan):** "Download original" is
**client-facing, but ONLY for approved/final deliverables** — the client is
paying for their finished film, so they get their own copy of it. DRM's real
job here is protecting the review/draft phase, not restricting the paid,
approved final product. Drafts (`draft`/`in_review`/`revisions_requested`)
are stream-only under DRM and never expose the raw MP4 (endpoint #2 state
gate). See endpoint #2 for enforcement.

## Locked design decisions (session 15)

1. **New uploads only.** Zero deliverables in production; no migration tooling needed.
2. **URL-paste model, not in-portal upload.** Nathan uploads to Bunny.net via their dashboard; portal renders signed embeds and signed download URLs. In-portal upload flow is Phase 2, deferred.
3. **Watermarking = static library watermark + MediaCage Basic DRM (enabled) + a portal-rendered HTML overlay showing a short session/client reference code.**
   > **Revised protection note (post-DRM).** With MediaCage Basic enabled,
   > the "download/rip the raw file" vector is now genuinely protected
   > (dynamic session-based clear-key encryption blocks common downloaders
   > and third-party players) — a material upgrade over the original design,
   > where the static watermark was the *only* barrier.
   >
   > It still does **NOT** provide leak-traceability: the burnt-in watermark
   > is identical for every viewer, so a leaked copy's pixels can't identify
   > which client it came from. The remaining leak vector is screen-recording,
   > which no clear-key scheme prevents; the HTML overlay deters it but
   > disappears in fullscreen (see the MediaCage update section above).
   >
   > If leak-traceability ever becomes a real requirement, it still needs a
   > separate build — Bunny JIT/per-viewer watermarking or MediaCage
   > Enterprise (Widevine/PlayReady). Both remain out of Phase 1 scope.
4. **Storage backup is manual, not automated.** Nathan uploads each source file to Bunny Storage AND Bunny Stream separately from the Bunny dashboard. No backend copy-pipeline, no fetch-and-forward job. Two clicks in Bunny UI beats maintaining a background copier.
5. **Signed embed URL TTL: 30 minutes.** Long enough to watch a film without a mid-playback expiry, short enough to be uninteresting as a shared link.
6. **Signed Storage download URL TTL: 15 minutes.** Downloads are click-then-save; no legitimate need for a longer window.

## Migration 015 — schema

```sql
-- 015a: link deliverables to their Bunny assets
alter table public.deliverables
  add column if not exists bunny_video_guid text,           -- Stream video GUID
  add column if not exists bunny_storage_object text,       -- Storage object key (e.g. "clients/<client>/<file>.mp4")
  add column if not exists bunny_status text;               -- last webhook status: 'processing' | 'finished' | 'failed' | null

-- 015b: access log — one row per meaningful auth/action event
create table if not exists public.deliverable_access_events (
    id             uuid primary key default gen_random_uuid(),
    deliverable_id uuid not null references public.deliverables(id) on delete cascade,
    client_id      uuid references public.clients(id) on delete set null,
    actor_role     text not null check (actor_role in ('client','admin','anonymous')),
    event_type     text not null check (event_type in (
                     'playback_url_issued', 'download_url_issued',
                     'player_play', 'player_25', 'player_50', 'player_75',
                     'player_ended', 'player_heartbeat',
                     'entitlement_denied'
                   )),
    meta           jsonb not null default '{}'::jsonb,
    created_at     timestamptz not null default now()
);
create index if not exists deliverable_access_events_deliv_idx
  on public.deliverable_access_events (deliverable_id, created_at desc);

alter table public.deliverable_access_events enable row level security;
-- No policies. Service-role only (backend routes). Same convention as cron_runs / pricing_catalog draft.
```

## Environment variables (Railway)

```
BUNNY_STREAM_LIBRARY_ID
BUNNY_STREAM_API_KEY           # video management (Phase 2 mostly; webhook lookups)
BUNNY_STREAM_TOKEN_KEY         # signs embed URLs — never exposed to frontend
BUNNY_STREAM_READ_ONLY_KEY     # webhook HMAC verification
BUNNY_STORAGE_ZONE
BUNNY_STORAGE_PASSWORD         # HTTP AccessKey / S3 secret
BUNNY_STORAGE_S3_ENDPOINT      # e.g. https://<region>-s3.storage.bunnycdn.com
BUNNY_STORAGE_S3_REGION        # e.g. 'de'
```

None of these have `REACT_APP_*` counterparts — the frontend never sees them.

## Backend endpoints (all in a new `backend/bunny.py`)

### 1. `POST /api/deliverables/{id}/playback-token`
Auth: existing portal JWT (client) OR admin JWT.
Body: `{}`.
Response: `{ "embed_url": <signed URL>, "expires": <unix seconds>, "overlay_code": "AB12-C34D" }`

Behaviour:
1. Load deliverable; 404 if missing.
2. **Entitlement guard**: if actor is client, `deliverable.client_id == actor.client_id`. Admin bypasses. Failed check → log `entitlement_denied` event, 403.
3. If `bunny_video_guid` is null → 409 "not yet published to Bunny."
4. Sign the embed URL: `token = SHA256_HEX(BUNNY_STREAM_TOKEN_KEY + bunny_video_guid + expires)`, `expires = now + 1800`.
5. Compute overlay_code: HMAC-SHA256 with a stable session-scoped secret over `(deliverable_id, client_id, day-truncated timestamp)`, take first 8 chars formatted as `AB12-C34D`. Same client on the same day gets the same code (aids abuse investigation, doesn't uniquely trace a single view).
6. Insert `playback_url_issued` event.
7. Return `{ embed_url, expires, overlay_code }`.

### 2. `POST /api/deliverables/{id}/download-url`
Auth: same as above. Body: `{}`.
Response: `{ "url": <presigned S3 URL>, "expires_in": 900 }`

**Download is the paid, approved final product — gated on state.** DRM's job
here is protecting the review/draft phase; the client is entitled to download
their *finished* film, not a draft still under review. So the raw-MP4
download path is allowed ONLY when the deliverable has reached an
approved/final state.

Behaviour:
1. Same load + entitlement guard.
2. **State gate**: if `deliverable.status NOT IN ('approved', 'final_delivered')`
   → 409 "This deliverable isn't approved for download yet." (`draft`,
   `in_review`, `revisions_requested` never expose the raw file — they can
   only be *streamed* under DRM via endpoint #1.) Log an
   `entitlement_denied` event with `meta.reason = 'not_downloadable_state'`.
3. If `bunny_storage_object` is null → 409 "no backup file uploaded."
4. Generate S3 v4 presigned GET URL against `BUNNY_STORAGE_S3_ENDPOINT` with `ExpiresIn=900`.
5. Insert `download_url_issued` event.
6. Return.

> Streaming (endpoint #1) has NO such state gate — a client may watch a
> draft in review under DRM; they simply can't pull the raw file until it's
> approved/final. The frontend "Download original" button is therefore only
> rendered when `status IN ('approved','final_delivered')`, but the
> server-side 409 is the real enforcement (never trust the button's absence).

### 3. `POST /api/deliverables/{id}/play-event`
Auth: same as above. Body: `{ "event": "play" | "player_25" | "player_50" | "player_75" | "player_ended" | "player_heartbeat", "position_seconds": <float, optional> }`.
Response: `{ "ok": true }`.

Behaviour:
1. Load + entitlement guard.
2. Insert one `deliverable_access_events` row with the given event_type. Meta carries position_seconds if present.
3. Heartbeat is rate-limited server-side to at most 1 per 30 seconds per (client, deliverable) — enforced by a "reject if last heartbeat for this pair was < 30s ago" query. Prevents log spam.

### 4. `POST /api/bunny/webhook`
Auth: HMAC signature check using `BUNNY_STREAM_READ_ONLY_KEY`. Headers `X-BunnyStream-Signature-Version=v1`, `X-BunnyStream-Signature-Algorithm=hmac-sha256`, `X-BunnyStream-Signature=<hex>`. Verify against exact raw request bytes.

Behaviour:
1. On invalid signature/version/algorithm → 401.
2. On valid: parse JSON; look up `deliverables` by `bunny_video_guid == payload.VideoGuid`; update `bunny_status = payload.Status`. If no matching deliverable, log at INFO and 200 anyway (orphan Bunny videos are fine, not our problem).
3. Idempotent: same webhook fired twice produces one final state.

## Frontend rework — `DeliverableDetail.js`

Current: `<iframe src={deliv.video_url}>` static render.
New:
1. On page mount, if `deliv.bunny_video_guid`, show a **"Watch film"** button (not an auto-loading iframe — matches the playbook's "authorize-then-play" pattern).
2. Click → `POST /api/deliverables/{id}/playback-token` → render `<iframe src={data.embed_url}>`.
3. Overlay: `<div class="absolute bottom-2 right-2 opacity-40 font-mono text-xs">Client Ref: {overlay_code}</div>` positioned over the iframe wrapper. Non-clickable, non-interactive, always visible while playing.
4. Player event pings via postMessage listener on the iframe (Bunny fires playback events) OR a manual "I've watched" beacon — TBD during build; pings are best-effort, not required for correctness.
5. Download button: shown ONLY when `deliv.status IN ('approved','final_delivered')` AND `deliv.bunny_storage_object` is present — "Download original" → `POST /api/deliverables/{id}/download-url` → `window.location.href = data.url`. For drafts/in-review the button is hidden (and the endpoint 409s regardless — button absence is UX, not enforcement).
6. If `bunny_video_guid` is absent → show existing empty-state ("your editor hasn't uploaded yet"). **No direct-file legacy fallback:** MediaCage forbids MP4/direct-HLS rendering (403), and there are zero legacy deliverables in prod (design decision #1), so the old `<iframe src={deliv.video_url}>` path is removed entirely rather than kept as a fallback.

Admin form (`Admin.js`): the current "Video URL (embed)" field becomes **"Bunny Video GUID"** (paste the guid Bunny gives after upload, not a full URL). New optional field: **"Bunny Storage Object Path"** (e.g. `clients/jane-doe/wedding-final.mp4`).

## Pytest coverage — `backend/tests/test_bunny.py`

Must run against real Bunny credentials (session-scoped, guarded by `ALLOW_ATTACK_SIM=1` like other mutation-test files). Coverage:

1. **Signing correctness** — reproduce the SHA-256 algorithm in the test, compare against endpoint output. Same key + guid + expires → same token deterministically.
2. **Entitlement guard positive** — client A can generate playback token for a deliverable owned by client A.
3. **Entitlement guard negative** — client B trying the same deliverable → 403, `entitlement_denied` event logged.
4. **Admin bypass** — admin can generate for any deliverable.
5. **Missing GUID** — deliverable without `bunny_video_guid` → 409.
6. **Missing storage object** — deliverable without `bunny_storage_object` → download endpoint 409.
6b. **Download state gate** — deliverable in `in_review` (and `revisions_requested`, `draft`) → download endpoint 409 `not_downloadable_state` + `entitlement_denied` event; same deliverable flipped to `approved` (and `final_delivered`) → 200 with a presigned URL. Confirms drafts are stream-only and only approved/final expose the raw file.
7. **Expiry** — token generated with a past expiry (via direct algorithm reproduction) fails against Bunny; positive-case current-time token succeeds. Verified with a real HTTP HEAD against `player.mediadelivery.net`.
8. **Tampering** — mutate one character of the URL's token or expires → 403 from Bunny.
9. **Webhook signature** — construct a payload + valid HMAC, expect 200 and status update; mutate the signature or version header, expect 401.
10. **Webhook orphan** — VideoGuid that doesn't match any deliverable → 200 (no crash), no DB update.
11. **Heartbeat rate-limit** — fire 5 heartbeats in a second, expect 1 event row (or a small deterministic number ≤ 2 accounting for clock).
12. **Presigned URL correctness** — S3 v4 signature validates against Bunny's S3 endpoint (real HEAD request).

Total: ~13 tests. Same discipline as balance-collection + pricing-admin tests — real infrastructure, no mocks.

## Nathan's setup checklist (do this before next session)

Rough time: 30–45 minutes.

1. Create a Bunny.net account (free tier is fine for setup; usage-based billing kicks in with real files).
2. Create a **Stream video library**. Copy: Library ID, Stream API key, Token security key, Read-only API key.
3. In library settings:
   - **Enable Embed View Token Authentication.**
   - **MediaCage Basic DRM: ENABLED** (done). Note: this forces iframe-only
     playback and disables MP4/direct-HLS — the build accounts for this.
   - Add the portal hostname to Allowed Domains (exactly `portal.flyboyvideography.com` or wherever the CRA is hosted — no `https://` prefix, no scheme).
   - **Upload the Flyboy logo as the library watermark.** This is the static burnt-in watermark; it applies to every video encoded in this library.
4. Create a **Storage zone**. During creation, **enable S3 compatibility** (Bunny says it cannot be added later). Copy: zone name, password, S3 endpoint, S3 region.
5. Set the 8 Railway env variables listed above.
6. Ping me. I'll start the build against real infrastructure.

## Explicit non-goals for Phase 1

- No in-portal upload UX. Nathan uploads via Bunny dashboard.
- No dynamic per-viewer burnt-in watermark. Traceability is not a Phase 1 guarantee.
- No backend Stream→Storage copy pipeline. Two manual uploads.
- No client-side download tracking beyond what the signed-URL request itself proves (a signed URL issued ≠ a download completed).
- No migration script. Deliverables table starts empty.
- No cookie-consent gating on the embed player (Bunny's signed embed is essentially first-party and doesn't set marketing cookies; if this changes, revisit).

## Documents

- This spec: `/app/docs/BUNNY_PHASE_1_SPEC.md`
- Integration playbook (from `integration_playbook_expert_v2`) captured in session 15 chat — includes signing algorithm details, S3 presign code, webhook HMAC verification pattern. Refer to that during build for the authoritative Bunny.net HTTP surface.
