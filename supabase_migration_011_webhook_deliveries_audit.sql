-- Migration 011: webhook_deliveries_audit
--
-- Purpose: DB-provable per-endpoint attribution of Stripe webhook deliveries.
-- Motivation: during the 2026-02 Railway cutover we discovered the preview
-- backend had been quietly handling ALL webhook deliveries (Railway's endpoint
-- was in a delivery-inert state due to the api_version param landmine — see
-- docs/RAILWAY_VERCEL_CUTOVER.md). Nothing in the DB let us prove which pod
-- processed which event. This table fixes that permanently.
--
-- Every webhook receipt is written here BEFORE the finalisation branch runs,
-- with a `pod_source` label taken from the POD_SOURCE_LABEL env var. During
-- the 24h dual-delivery window we expect exactly one row per pod per
-- checkout.session.completed event. Post-cutover, only the Railway pod
-- should be present.
--
-- Idempotent: `CREATE TABLE IF NOT EXISTS` + `CREATE INDEX IF NOT EXISTS`.

CREATE TABLE IF NOT EXISTS public.webhook_deliveries_audit (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stripe_event_id     TEXT NOT NULL,
    event_type          TEXT NOT NULL,
    session_id          TEXT,
    pod_source          TEXT NOT NULL,       -- 'railway', 'preview', 'local', 'unknown'
    received_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signature_valid     BOOLEAN NOT NULL,
    processing_ms       INTEGER,
    response_status     INTEGER,             -- 200 on success, 400/500 on error
    finalise_outcome    TEXT,                -- 'finalised', 'already_paid', 'skipped_non_target_type', 'refunded_race', 'error'
    error_message       TEXT,
    stripe_created_at   TIMESTAMPTZ,         -- from event.created — helps measure delivery latency

    -- Enforce one row per (event, pod) so replays from the same endpoint
    -- collapse into an upsert-style dedupe. Cross-pod deliveries produce
    -- two rows, which is exactly what we want for attribution.
    CONSTRAINT webhook_deliveries_audit_uniq UNIQUE (stripe_event_id, pod_source)
);

CREATE INDEX IF NOT EXISTS webhook_deliveries_audit_received_at_idx
    ON public.webhook_deliveries_audit (received_at DESC);

CREATE INDEX IF NOT EXISTS webhook_deliveries_audit_pod_type_idx
    ON public.webhook_deliveries_audit (pod_source, event_type, received_at DESC);

CREATE INDEX IF NOT EXISTS webhook_deliveries_audit_session_idx
    ON public.webhook_deliveries_audit (session_id)
    WHERE session_id IS NOT NULL;

COMMENT ON TABLE  public.webhook_deliveries_audit IS
    'Per-endpoint attribution of Stripe webhook deliveries. Written from booking.py stripe_webhook. See Migration 011 header and docs/RAILWAY_VERCEL_CUTOVER.md.';
COMMENT ON COLUMN public.webhook_deliveries_audit.pod_source IS
    'Value of POD_SOURCE_LABEL env var on the pod that processed the delivery. Must be set differently per deployment (railway/preview/local).';
COMMENT ON COLUMN public.webhook_deliveries_audit.finalise_outcome IS
    'Result of the branch that handled this event. "finalised" = booking row created; "already_paid" = idempotent skip; "skipped_non_target_type" = event type not in handler switch.';
