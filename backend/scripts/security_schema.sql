-- ============================================================
-- ALERT INTEGRITY SHIELD — Supabase Database Migration
-- ============================================================

-- 1. Extend alerts table with security inspection columns if not present
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'alerts' AND column_name = 'security_status') THEN
        ALTER TABLE alerts ADD COLUMN security_status VARCHAR(32) DEFAULT 'ACCEPTED';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'alerts' AND column_name = 'trust_score') THEN
        ALTER TABLE alerts ADD COLUMN trust_score DOUBLE PRECISION DEFAULT 100.0;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'alerts' AND column_name = 'quarantine_reason') THEN
        ALTER TABLE alerts ADD COLUMN quarantine_reason TEXT;
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_alerts_security_status ON alerts(security_status);
CREATE INDEX IF NOT EXISTS idx_alerts_trust_score ON alerts(trust_score);

-- 2. Webhook Sources Table
CREATE TABLE IF NOT EXISTS webhook_sources (
    id VARCHAR(64) PRIMARY KEY,
    source_name VARCHAR(64) UNIQUE NOT NULL,
    source_identifier VARCHAR(128) UNIQUE NOT NULL,
    secret VARCHAR(255) NOT NULL,
    secondary_secret VARCHAR(255),
    rotation_expires_at TIMESTAMPTZ,
    is_enabled BOOLEAN DEFAULT TRUE NOT NULL,
    rate_limit_per_minute INTEGER DEFAULT 1000 NOT NULL,
    trust_rating DOUBLE PRECISION DEFAULT 100.0 NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    last_used_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_webhook_sources_name ON webhook_sources(source_name);
CREATE INDEX IF NOT EXISTS idx_webhook_sources_identifier ON webhook_sources(source_identifier);

-- 3. Webhook Requests Table (Replay Protection)
CREATE TABLE IF NOT EXISTS webhook_requests (
    id VARCHAR(64) PRIMARY KEY,
    source VARCHAR(64) NOT NULL,
    request_id VARCHAR(128) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    processed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status VARCHAR(32) DEFAULT 'PROCESSED' NOT NULL,
    CONSTRAINT uq_webhook_source_request_id UNIQUE (source, request_id)
);

CREATE INDEX IF NOT EXISTS idx_webhook_requests_source_req ON webhook_requests(source, request_id);
CREATE INDEX IF NOT EXISTS idx_webhook_requests_time ON webhook_requests(timestamp);

-- 4. Security Events Table (Audit Log)
CREATE TABLE IF NOT EXISTS security_events (
    id VARCHAR(64) PRIMARY KEY,
    event_type VARCHAR(64) NOT NULL,
    source VARCHAR(64) NOT NULL,
    request_id VARCHAR(128),
    alert_id INTEGER,
    severity VARCHAR(32) DEFAULT 'INFO' NOT NULL,
    trust_score DOUBLE PRECISION DEFAULT 100.0 NOT NULL,
    action VARCHAR(32) NOT NULL,
    reason TEXT NOT NULL,
    metadata_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_security_events_created_at ON security_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_security_events_type ON security_events(event_type);
CREATE INDEX IF NOT EXISTS idx_security_events_source ON security_events(source);
CREATE INDEX IF NOT EXISTS idx_security_events_action ON security_events(action);

-- 5. Security Baselines Table (Volume Anomaly & Storm Detection)
CREATE TABLE IF NOT EXISTS security_baselines (
    id VARCHAR(64) PRIMARY KEY,
    source VARCHAR(64) NOT NULL,
    service VARCHAR(128),
    normal_rate_per_minute DOUBLE PRECISION DEFAULT 50.0 NOT NULL,
    last_window_count INTEGER DEFAULT 0 NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_security_baselines_src_svc ON security_baselines(source, service);

-- 6. Supabase Row Level Security (RLS) Configuration
ALTER TABLE webhook_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhook_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE security_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE security_baselines ENABLE ROW LEVEL SECURITY;

-- Note: Webhook Sources contains secrets; prevent public access. Only service_role can read/write directly.
DROP POLICY IF EXISTS "service_role_all_webhook_sources" ON webhook_sources;
CREATE POLICY "service_role_all_webhook_sources" ON webhook_sources
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Authenticated users (e.g. SRE dashboard) can read metadata but secrets are filtered at API level
DROP POLICY IF EXISTS "authenticated_select_webhook_sources" ON webhook_sources;
CREATE POLICY "authenticated_select_webhook_sources" ON webhook_sources
    FOR SELECT
    TO authenticated
    USING (true);

-- Webhook requests table: service_role has full control
DROP POLICY IF EXISTS "service_role_all_webhook_requests" ON webhook_requests;
CREATE POLICY "service_role_all_webhook_requests" ON webhook_requests
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Security events: Authenticated users can view audit trail
DROP POLICY IF EXISTS "authenticated_select_security_events" ON security_events;
CREATE POLICY "authenticated_select_security_events" ON security_events
    FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS "service_role_all_security_events" ON security_events;
CREATE POLICY "service_role_all_security_events" ON security_events
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Security baselines: Read-only for authenticated, full for service_role
DROP POLICY IF EXISTS "authenticated_select_security_baselines" ON security_baselines;
CREATE POLICY "authenticated_select_security_baselines" ON security_baselines
    FOR SELECT
    TO authenticated
    USING (true);

DROP POLICY IF EXISTS "service_role_all_security_baselines" ON security_baselines;
CREATE POLICY "service_role_all_security_baselines" ON security_baselines
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
